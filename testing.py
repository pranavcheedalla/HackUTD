"""Shared contract: golden recordings -> pytest -> structured equivalence results."""
from __future__ import annotations

import hashlib
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from legacy.runtime import OutputLimitExceeded, _encode_input, _run_process

PROJECT_ROOT = Path(__file__).resolve().parent
GOLDEN_DIR = PROJECT_ROOT / 'golden'
TEST_DIR = PROJECT_ROOT / 'tests/equivalence'
REPORT_DIR = PROJECT_ROOT / 'runs/equivalence'
EQUIVALENCE_TIMEOUT_SECONDS = 30


class EquivalenceError(RuntimeError):
    """The test infrastructure could not produce a trustworthy result."""


# A verified rewrite must compute its answer, never look it up. Rewrites may import only
# pure standard-library modules plus already-verified sibling modules (e.g. `discount`),
# and may not reach files, the process, or the interpreter's internals.
SAFE_IMPORTS = frozenset({
    '__future__', 'decimal', 're', 'math', 'string', 'typing', 'dataclasses', 'functools',
    'itertools', 'collections', 'enum', 'datetime', 'fractions', 'numbers', 'operator', 'sys',
})
FORBIDDEN_CALLS = frozenset({'open', 'exec', 'eval', 'compile', '__import__', 'breakpoint',
                             'globals', 'vars', 'input', 'memoryview'})
FORBIDDEN_ATTRS = frozenset({'modules', '_getframe', 'f_back', 'f_globals', 'f_locals',
                             '__builtins__', '__globals__', '__subclasses__', '__code__',
                             '__loader__', '__spec__', '__dict__', 'gi_frame', 'cr_frame',
                             'stdin', 'argv', 'path', 'meta_path'})


def rewrite_violations(source: str, local_modules=()) -> list[str]:
    """Reasons a rewrite is not a self-contained computation (empty list = acceptable)."""
    import ast
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f'SyntaxError: {exc.msg} (line {exc.lineno})']
    allowed = SAFE_IMPORTS | {str(m) for m in local_modules}
    problems = []

    def script_block(node) -> bool:
        # `if __name__ == "__main__":` only runs when the file is executed by hand (stdin/argv
        # there is the convention); verification imports the module, so it never runs.
        test = getattr(node, 'test', None)
        return (isinstance(node, ast.If) and isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name) and test.left.id == '__name__')

    def walk(node):
        yield node
        for child in ast.iter_child_nodes(node):
            if not script_block(child):
                yield from walk(child)

    for node in walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '__import__'
                and len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
                and str(node.args[0].value) in allowed):
            continue  # __import__("re") inline is just an import of an allowed module
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = ['.' if node.level else (node.module or '')]
        else:
            names = []
        for name in names:
            if name.split('.')[0] not in allowed:
                problems.append(f'line {node.lineno}: import of {name!r} is not allowed '
                                f'(allowed: {", ".join(sorted(allowed))})')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            problems.append(f'line {node.lineno}: {node.func.id}() is not allowed; '
                            'compute the result from input_line only')
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            problems.append(f'line {node.lineno}: access to .{node.attr} is not allowed')
        if isinstance(node, ast.Name) and node.id in ('__builtins__', '__loader__', '__spec__'):
            problems.append(f'line {node.lineno}: {node.id} is not allowed')
    return list(dict.fromkeys(problems))


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'duplicate JSON key: {key}')
        value[key] = item
    return value


def _module_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise ValueError('module_id must be an identifier')
    return str.__str__(value)


def _cases(module_id):
    path = GOLDEN_DIR / f'{_module_id(module_id)}.jsonl'
    raw = path.read_bytes()
    cases = []
    for number, line in enumerate(raw.splitlines(), 1):
        try:
            case = json.loads(line, object_pairs_hook=_unique_object)
        except ValueError as exc:
            raise ValueError(f'{path}: invalid JSON on line {number}: {exc}') from exc
        if not isinstance(case, dict) or set(case) != {'input', 'output'} or not all(
            isinstance(case[key], str) for key in ('input', 'output')
        ):
            raise ValueError(f'{path}: line {number} must contain input/output strings')
        try:
            _encode_input(case['input'])
            case['output'].encode('utf-8')
        except ValueError as exc:
            raise ValueError(f'{path}: line {number} is not a valid UTF-8 input/output case') from exc
        cases.append(case)
    if not cases:
        raise ValueError(f'{path}: golden file must not be empty')
    return cases, hashlib.sha256(raw).hexdigest()


def golden_to_pytest(module_id, py_module_path) -> str:
    """Generate tests without importing or requiring the not-yet-written rewrite."""
    module_id = _module_id(module_id)
    cases, digest = _cases(module_id)
    target = Path(py_module_path).expanduser().resolve()
    try:
        relative = target.relative_to(PROJECT_ROOT).as_posix()
        expression = f'ROOT / {relative!r}'
    except ValueError:
        expression = f'Path({str(target)!r})'
    source = f'''# Generated by testing.golden_to_pytest; regenerate when golden changes.
# golden-sha256: {digest}
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import pytest

ROOT = Path(__file__).resolve().parents[2]
TARGET = {expression}
CASES = json.loads({json.dumps(cases, ensure_ascii=True)!r})

@pytest.fixture(scope="module")
def rewritten_module():
    # Compile the current source directly: rapid, same-size edits must not reuse pyc.
    name = "_equivalence_{module_id}"
    spec = importlib.util.spec_from_file_location(name, TARGET)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.path.insert(0, str(TARGET.parent))
    cache = tempfile.TemporaryDirectory(prefix="rewrite-cache-")
    old_cache = sys.pycache_prefix
    old_write = sys.dont_write_bytecode
    sys.pycache_prefix = cache.name
    sys.dont_write_bytecode = True
    try:
        exec(compile(TARGET.read_bytes(), str(TARGET), "exec"), module.__dict__)
        yield module
    finally:
        sys.pycache_prefix = old_cache
        sys.dont_write_bytecode = old_write
        cache.cleanup()
        sys.path.pop(0)
        sys.modules.pop(name, None)

@pytest.mark.parametrize("case", CASES, ids=[f"case-{{i:03d}}" for i in range(len(CASES))])
def test_golden(case, rewritten_module, record_property):
    expected = case["output"]
    actual = rewritten_module.main(case["input"])
    if not isinstance(actual, str):
        record_property("actual", f"<non-str {{type(actual).__name__}}> {{actual!r}}")
        pytest.fail("main(input_line) must return str")
    # Use the built-in character value, never a subclass's overloaded equality.
    actual = str.__str__(actual)
    record_property("actual", actual)
    assert actual == expected
'''
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    destination = TEST_DIR / f'test_{module_id}.py'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=TEST_DIR, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(source)
        os.replace(temporary, destination)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    # Pin generated content as well as the golden snapshot. Publish the test
    # first: interruption or concurrent regeneration makes the pair fail closed.
    manifest = destination.with_suffix('.manifest.json')
    integrity = {'golden_sha256': digest,
                 'test_sha256': hashlib.sha256(source.encode('utf-8')).hexdigest()}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=TEST_DIR, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(integrity, stream)
        os.replace(temporary, manifest)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return str(destination)


def run_equivalence(module_id) -> dict:
    """Run one generated test file in a fresh process; never count zero as success."""
    module_id = _module_id(module_id)
    cases, digest = _cases(module_id)
    test = TEST_DIR / f'test_{module_id}.py'
    if not test.is_file():
        raise EquivalenceError(f'Generate equivalence tests first: {test}')
    if f'# golden-sha256: {digest}\n' not in test.read_text(encoding='utf-8'):
        raise EquivalenceError('Golden file changed; regenerate equivalence tests')
    try:
        integrity = json.loads(test.with_suffix('.manifest.json').read_text(encoding='utf-8'))
        valid = integrity == {'golden_sha256': digest,
                              'test_sha256': hashlib.sha256(test.read_bytes()).hexdigest()}
    except (OSError, ValueError):
        valid = False
    if not valid:
        raise EquivalenceError('Generated test integrity changed; regenerate modified tests')
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'{module_id}-', dir=REPORT_DIR) as folder:
        report = Path(folder) / 'report.json'
        bootstrap = ('import sys; sys.path.insert(0, sys.argv[1]); import pytest; '
                     'raise SystemExit(pytest.main(sys.argv[2:]))')
        command = [sys.executable, '-I', '-c', bootstrap, str(PROJECT_ROOT),
                   '-q', '--tb=short', '--capture=no', '-c', os.devnull, '--noconftest',
                   '--rootdir', str(PROJECT_ROOT), '--assert=rewrite', '-p',
                   'testing_reporter', '--equivalence-report', str(report), str(test)]
        # Explicit plugin + clean pytest options keep results independent of the
        # developer's installed third-party plugins and terminal configuration.
        try:
            process = _run_process(command, EQUIVALENCE_TIMEOUT_SECONDS, extra_env={
                'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTEST_ADDOPTS': '', 'PYTEST_PLUGINS': '',
                'PYTHONPATH': str(PROJECT_ROOT),
            }, cwd=PROJECT_ROOT)
        except subprocess.TimeoutExpired as exc:
            raise EquivalenceError(f'Equivalence run timed out after {EQUIVALENCE_TIMEOUT_SECONDS}s') from exc
        except OutputLimitExceeded as exc:
            raise EquivalenceError(str(exc)) from exc
        except OSError as exc:
            raise EquivalenceError(f'Cannot start pytest: {exc}') from exc
        if process.returncode not in (0, 1) or not report.is_file():
            diagnostic = (process.stdout + process.stderr).decode('utf-8', errors='replace')
            raise EquivalenceError(f'pytest infrastructure failed ({process.returncode}):\n{diagnostic}')
        try:
            result = json.loads(report.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
        except (OSError, ValueError) as exc:
            raise EquivalenceError('pytest did not write a valid structured result') from exc
    try:
        stable = (
            hashlib.sha256((GOLDEN_DIR / f'{module_id}.jsonl').read_bytes()).hexdigest() == digest
            and hashlib.sha256(test.read_bytes()).hexdigest() == integrity['test_sha256']
            and json.loads(test.with_suffix('.manifest.json').read_text()) == integrity
        )
    except (OSError, ValueError):
        stable = False
    if not stable:
        raise EquivalenceError('Golden or generated tests changed during verification; regenerate')
    if not isinstance(result, dict) or set(result) != {'passed', 'total', 'failures', 'collection_errors'}:
        raise EquivalenceError('Invalid structured report schema')
    if any(type(result[key]) is not int or result[key] < 0
           for key in ('passed', 'total', 'collection_errors')) or not isinstance(result['failures'], list):
        raise EquivalenceError('Invalid structured report counts')
    remaining = Counter((case['input'], case['output']) for case in cases)
    for failure in result['failures']:
        if not isinstance(failure, dict) or set(failure) != {'input', 'expected', 'actual'} or not all(
            isinstance(value, str) for value in failure.values()
        ):
            raise EquivalenceError('Invalid structured failure schema')
        identity = (failure['input'], failure['expected'])
        remaining[identity] -= 1
        if remaining[identity] < 0:
            raise EquivalenceError('Report contains an unknown or duplicated failure case')
    if result['collection_errors'] or result['total'] != len(cases):
        raise EquivalenceError('Collection failed or not every golden case executed')
    if result['passed'] + len(result['failures']) != result['total']:
        raise EquivalenceError('Incomplete equivalence results')
    if (process.returncode == 0) != (result['passed'] == result['total']):
        raise EquivalenceError('pytest exit status disagrees with case results')
    return {key: result[key] for key in ('passed', 'total', 'failures')}
