"""Regression attacks run only against temporary, local projects."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
import testing


@pytest.fixture
def project(tmp_path, monkeypatch):
    golden = tmp_path / 'golden'
    golden.mkdir()
    (golden / 'sample.jsonl').write_text('{"input":"x","output":"ok"}\n')
    monkeypatch.setattr(testing, 'GOLDEN_DIR', golden)
    monkeypatch.setattr(testing, 'TEST_DIR', tmp_path / 'tests/equivalence')
    monkeypatch.setattr(testing, 'REPORT_DIR', tmp_path / 'reports')
    target = tmp_path / 'modern' / 'sample.py'
    target.parent.mkdir()
    return target, golden


def test_string_subclass_cannot_lie_about_equality(project):
    target, _ = project
    target.write_text('class Liar(str):\n    def __eq__(self, other): return True\ndef main(line): return Liar("wrong")\n')
    testing.golden_to_pytest('sample', target)
    result = testing.run_equivalence('sample')
    assert result['passed'] == 0
    assert result['failures'][0]['actual'] == 'wrong'


def test_modified_generated_case_cannot_false_pass(project):
    target, _ = project
    target.write_text('def main(line): return "wrong"\n')
    test = Path(testing.golden_to_pytest('sample', target))
    source = test.read_text()
    changed = source.replace('"output": "ok"', '"output": "wrong"')
    assert changed != source
    test.write_text(changed)
    with pytest.raises(testing.EquivalenceError, match='modified|regenerate|integrity'):
        testing.run_equivalence('sample')


def test_inherited_pytest_plugin_setting_cannot_break_run(project, monkeypatch):
    target, _ = project
    target.write_text('def main(line): return "ok"\n')
    testing.golden_to_pytest('sample', target)
    monkeypatch.setenv('PYTEST_PLUGINS', 'this_plugin_does_not_exist')
    assert testing.run_equivalence('sample')['passed'] == 1


def test_local_conftest_cannot_rewrite_expected_outputs(project):
    target, _ = project
    target.write_text('def main(line): return "wrong"\n')
    (target.parent.parent / 'conftest.py').write_text(
        'def pytest_runtest_setup(item):\n'
        '    item.callspec.params["case"]["output"] = "wrong"\n'
    )
    testing.golden_to_pytest('sample', target)
    assert testing.run_equivalence('sample')['passed'] == 0


def test_duplicate_json_keys_are_rejected(project):
    target, golden = project
    (golden / 'sample.jsonl').write_text('{"input":"x","output":"ok","output":"wrong"}\n')
    with pytest.raises(ValueError, match='duplicate'):
        testing.golden_to_pytest('sample', target)


def test_same_size_helper_edit_does_not_reuse_pyc(project):
    target, _ = project
    helper = target.parent / 'audit_helper.py'
    helper.write_text('VALUE = "ok"\n')
    target.write_text('def main(line):\n    from audit_helper import VALUE\n    return VALUE\n')
    # Deliberately create a stale cache with the exact source mtime and size.
    import os
    import py_compile
    py_compile.compile(str(helper), doraise=True)
    original_stat = helper.stat()
    helper.write_text('VALUE = "NO"\n')
    os.utime(helper, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    testing.golden_to_pytest('sample', target)
    result = testing.run_equivalence('sample')
    assert result['passed'] == 0
    assert result['failures'][0]['actual'] == 'NO'


@pytest.mark.parametrize('case', [
    {'input': 'a\nb', 'output': 'ok'},
    {'input': '\ud800', 'output': 'ok'},
    {'input': 'x', 'output': '\ud800'},
])
def test_impossible_original_cases_are_rejected(project, case):
    target, golden = project
    (golden / 'sample.jsonl').write_text(json.dumps(case) + '\n')
    with pytest.raises(ValueError, match='UTF-8'):
        testing.golden_to_pytest('sample', target)


@pytest.fixture
def executable(tmp_path):
    import shlex
    def make(source):
        path = tmp_path / 'fixture executable'
        path.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' -c ' + shlex.quote(source) + '\n')
        path.chmod(0o755)
        return path
    return make


@pytest.mark.parametrize('descriptor', [1, 2])
def test_output_flood_fails_boundedly(executable, monkeypatch, descriptor):
    import legacy
    from legacy import runtime
    monkeypatch.setattr(runtime, 'MAX_CAPTURE_BYTES', 4096)
    program = executable(f'import os\nwhile True: os.write({descriptor}, b"x" * 8192)\n')
    with pytest.raises(legacy.CobolRunError, match='output exceeded'):
        legacy.run_cobol(program, '')


def test_interleaved_pipes_do_not_deadlock(executable):
    import legacy
    program = executable('import sys, os\nfor _ in range(16):\n os.write(1,b"x"*8192)\n os.write(2,b"e"*8192)\nline=sys.stdin.buffer.read()\nos.write(1,line)\n')
    # More than an OS pipe's capacity in both directions.
    line = 'z' * 131072
    assert legacy.run_cobol(program, line) == 'x' * 131072 + line


def test_cobol_runtime_overrides_do_not_leak(executable, monkeypatch):
    import legacy
    monkeypatch.setenv('COB_DISPLAY_PRINT_FILE', 'unexpected-target')
    monkeypatch.setenv('COB_PRE_LOAD', 'unexpected-library')
    program = executable('import os\nprint([k for k in os.environ if k.startswith("COB_")])\n')
    assert legacy.run_cobol(program, '') == '[]'


def test_cobol_display_redirection_cannot_silently_record_empty_output(tmp_path, monkeypatch):
    import legacy
    from pathlib import Path
    root = Path(testing.__file__).parent
    unexpected = tmp_path / 'redirected-display.txt'
    monkeypatch.setenv('COB_DISPLAY_PRINT_FILE', str(unexpected))
    binary = legacy.compile_cobol(root / 'examples/hello.cbl')
    assert legacy.run_cobol(binary, '') == 'HELLO FROM COBOL'
    assert not unexpected.exists()


def test_module_id_subclass_cannot_traverse(executable, tmp_path, monkeypatch):
    import legacy
    from legacy import runtime
    class BadFormat(str):
        def __format__(self, spec):
            return '../escape'
    monkeypatch.setattr(runtime, 'GOLDEN_DIR', tmp_path / 'golden')
    path = Path(legacy.record_golden(BadFormat('sample'), executable('print("ok")\n'), ['x']))
    assert path == tmp_path / 'golden/sample.jsonl'
    assert not (tmp_path / 'escape.jsonl').exists()


def test_missing_manifest_is_never_success(project):
    target, _ = project
    target.write_text('def main(line): return "ok"\n')
    path = Path(testing.golden_to_pytest('sample', target))
    path.with_suffix('.manifest.json').unlink()
    with pytest.raises(testing.EquivalenceError, match='integrity'):
        testing.run_equivalence('sample')


def test_report_output_cannot_overwrite_golden(tmp_path):
    import shutil
    root = Path(testing.__file__).parent
    copy = tmp_path / 'protected project'
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns('.git', '.env', '.env.*', 'bin', '__pycache__', '.pytest_cache', '.venv', 'validation', 'runs'))
    golden = copy / 'golden/invoice.jsonl'
    before = golden.read_bytes()
    process = subprocess.run([sys.executable, str(copy / 'check_integration.py'), '--output', str(golden)],
                             capture_output=True, text=True, timeout=45)
    assert process.returncode == 1 and 'under runs/' in process.stderr
    assert golden.read_bytes() == before


@pytest.mark.parametrize('when', ['call', 'import'])
def test_rewrite_cannot_mutate_case_dict_to_false_pass(project, when):
    target, _ = project
    if when == 'call':
        source = 'import inspect\ndef main(line):\n    inspect.currentframe().f_back.f_locals["case"]["output"] = "wrong"\n    return "wrong"\n'
    else:
        source = ('import sys\nfor module in list(sys.modules.values()):\n'
                  '    cases = getattr(module, "CASES", None)\n'
                  '    if isinstance(cases, list):\n'
                  '        for case in cases: case["output"] = "wrong"\n'
                  'def main(line): return "wrong"\n')
    target.write_text(source)
    testing.golden_to_pytest('sample', target)
    result = testing.run_equivalence('sample')
    assert result == {'passed': 0, 'total': 1, 'failures': [
        {'input': 'x', 'expected': 'ok', 'actual': 'wrong'},
    ]}


@pytest.mark.parametrize('report', [
    {},
    {'passed': True, 'total': 1, 'failures': [], 'collection_errors': 0},
    {'passed': -1, 'total': 1, 'failures': [], 'collection_errors': 0},
    {'passed': 0, 'total': 1, 'failures': [{'input': 'unknown', 'expected': 'ok', 'actual': 'bad'}], 'collection_errors': 0},
    {'passed': 0, 'total': 1, 'failures': [{'input': 'x', 'expected': 'ok', 'actual': 42}], 'collection_errors': 0},
])
def test_invalid_report_is_rejected_as_infrastructure_failure(project, monkeypatch, report):
    target, _ = project
    target.write_text('def main(line): return "ok"\n')
    testing.golden_to_pytest('sample', target)
    def fake_process(command, *args, **kwargs):
        path = Path(command[command.index('--equivalence-report') + 1])
        path.write_text(json.dumps(report))
        return subprocess.CompletedProcess(command, 0, b'', b'')
    monkeypatch.setattr(testing, '_run_process', fake_process)
    with pytest.raises(testing.EquivalenceError):
        testing.run_equivalence('sample')


def test_golden_changed_during_verification_cannot_mark_new_snapshot_passed(project):
    target, golden = project
    path = golden / 'sample.jsonl'
    target.write_text(f'from pathlib import Path\ndef main(line):\n    Path({str(path)!r}).write_text(\'{{"input":"x","output":"different"}}\\n\')\n    return "ok"\n')
    testing.golden_to_pytest('sample', target)
    with pytest.raises(testing.EquivalenceError, match='changed during'):
        testing.run_equivalence('sample')


@pytest.mark.parametrize('module_id', ['interest', 'payroll', 'invoice'])
def test_seeded_input_mutations_match_original(module_id):
    import random
    import legacy
    root = Path(testing.__file__).parent
    source = (root / f'tests/fixtures/{module_id}_reference.py').read_text()
    namespace = {}
    exec(compile(source, '<audit fixture>', 'exec'), namespace)
    base = json.loads((root / f'legacy/inputs/{module_id}.json').read_text())
    binary = legacy.compile_cobol(root / f'legacy/{module_id}.cbl')
    generator = random.Random(20261107 + len(module_id))
    for _ in range(200):
        line = generator.choice(base)
        index = generator.randrange(len(line) + 1)
        if generator.randrange(2):
            line = line[:index] + generator.choice('09.+-| e') + line[index:]
        else:
            line = line[:index] + line[index + 1:]
        assert legacy.run_cobol(binary, line) == namespace['main'](line), repr(line)


def test_executable_swap_cannot_mix_a_golden_batch(tmp_path, monkeypatch):
    import legacy
    from legacy import runtime
    folder = tmp_path / 'golden'
    folder.mkdir()
    saved = folder / 'sample.jsonl'
    saved.write_text('previous recording\n')
    binary = tmp_path / 'original'
    binary.write_bytes(b'version one')
    monkeypatch.setattr(runtime, 'GOLDEN_DIR', folder)
    def swapped(path, line):
        binary.write_bytes(b'version two')
        return 'output'
    monkeypatch.setattr(runtime, 'run_cobol', swapped)
    with pytest.raises(legacy.CobolRunError, match='Executable changed'):
        legacy.record_golden('sample', binary, ['x'])
    assert saved.read_text() == 'previous recording\n'
    assert not list(folder.glob('*.tmp'))


def test_compiler_output_flood_is_reported_cleanly(executable, tmp_path, monkeypatch):
    import legacy
    from legacy import runtime
    monkeypatch.setattr(runtime, 'MAX_CAPTURE_BYTES', 4096)
    monkeypatch.setattr(runtime, 'BIN_DIR', tmp_path / 'bin')
    compiler = executable('import os\nwhile True: os.write(2, b"x" * 8192)\n')
    monkeypatch.setattr(runtime.shutil, 'which', lambda name: str(compiler))
    source = tmp_path / 'sample.cbl'
    source.write_text('anything')
    with pytest.raises(legacy.CobolCompileError, match='output exceeded'):
        legacy.compile_cobol(source)


def test_rewrite_output_flood_cannot_hide_in_pytest_capture(project, monkeypatch):
    from legacy import runtime
    target, _ = project
    target.write_text('import os\ndef main(line):\n    while True: os.write(1, b"x" * 8192)\n')
    testing.golden_to_pytest('sample', target)
    monkeypatch.setattr(runtime, 'MAX_CAPTURE_BYTES', 65536)
    with pytest.raises(testing.EquivalenceError, match='output exceeded'):
        testing.run_equivalence('sample')
