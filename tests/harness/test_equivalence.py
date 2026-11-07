import json
from pathlib import Path
import pytest
import testing


@pytest.fixture
def project(tmp_path, monkeypatch):
    golden = tmp_path / 'golden'
    golden.mkdir()
    monkeypatch.setattr(testing, 'GOLDEN_DIR', golden)
    monkeypatch.setattr(testing, 'TEST_DIR', tmp_path / 'tests/equivalence')
    monkeypatch.setattr(testing, 'REPORT_DIR', tmp_path / 'reports')
    target = tmp_path / 'rewrite with spaces.py'
    def prepare(cases, source=None):
        (golden / 'sample.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in cases))
        if source is not None:
            target.write_text(source)
        return Path(testing.golden_to_pytest('sample', target))
    return prepare, target, golden


def test_exact_matches_and_escaped_strings(project):
    prepare, target, _ = project
    cases = [{'input': s, 'output': s} for s in ['  0001.20  ', 'quote"slash\\', 'café', 'unicode\u2028separator', '', 'same', 'same']]
    prepare(cases, 'def main(line):\n    return line\n')
    assert testing.run_equivalence('sample') == {'passed': 7, 'total': 7, 'failures': []}


def test_failures_return_exact_strings_and_fresh_edits(project):
    prepare, target, _ = project
    cases = [{'input': 'x', 'output': 'A'}, {'input': 'y', 'output': 'A'}]
    prepare(cases, 'def main(line): return "A"\n')
    assert testing.run_equivalence('sample')['passed'] == 2
    target.write_text('def main(line): return "B"\n')  # same size, immediate edit
    assert testing.run_equivalence('sample') == {
        'passed': 0, 'total': 2,
        'failures': [{'input': c['input'], 'expected': 'A', 'actual': 'B'} for c in cases],
    }


@pytest.mark.parametrize('source', [
    'def main(line): raise ValueError("broken rewrite")\n',
    'def main(line): return 123\n',
    'this is invalid python!\n',
    'x = 1\n',
])
def test_bad_rewrites_are_reported_per_case(project, source):
    prepare, _, _ = project
    prepare([{'input': 'x', 'output': 'A'}], source)
    result = testing.run_equivalence('sample')
    assert result['passed'] == 0 and result['total'] == 1
    assert result['failures'][0]['input'] == 'x'
    assert isinstance(result['failures'][0]['actual'], str)


def test_generation_precedes_missing_rewrite(project):
    prepare, target, _ = project
    path = prepare([{'input': 'x', 'output': 'A'}])
    assert path.exists() and not target.exists()
    result = testing.run_equivalence('sample')
    assert result['passed'] == 0 and result['total'] == 1
    assert 'FileNotFoundError' in result['failures'][0]['actual']


def test_stale_golden_requires_regeneration(project):
    prepare, _, golden = project
    prepare([{'input': 'x', 'output': 'x'}], 'def main(line): return line\n')
    (golden / 'sample.jsonl').write_text('{"input":"y","output":"y"}\n')
    with pytest.raises(testing.EquivalenceError, match='regenerate'):
        testing.run_equivalence('sample')


def test_collection_failure_is_never_success(project):
    prepare, _, _ = project
    path = prepare([{'input': 'x', 'output': 'x'}], 'def main(line): return line\n')
    path.write_text(path.read_text() + '\nthis is invalid!\n')
    import hashlib
    manifest = path.with_suffix('.manifest.json')
    metadata = json.loads(manifest.read_text())
    metadata['test_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(metadata))
    with pytest.raises(testing.EquivalenceError, match='infrastructure'):
        testing.run_equivalence('sample')


def test_skipping_all_cases_is_never_success(project):
    prepare, _, _ = project
    prepare([{'input': 'x', 'output': 'x'}], 'import pytest\ndef main(line): pytest.skip("skip")\n')
    with pytest.raises(testing.EquivalenceError, match='every golden case'):
        testing.run_equivalence('sample')


def test_timeout(project, monkeypatch):
    prepare, _, _ = project
    prepare([{'input': 'x', 'output': 'x'}], 'import time\ndef main(line): time.sleep(20)\n')
    monkeypatch.setattr(testing, 'EQUIVALENCE_TIMEOUT_SECONDS', 0.5)
    with pytest.raises(testing.EquivalenceError, match='timed out'):
        testing.run_equivalence('sample')


@pytest.mark.parametrize('raw', ['', '\n', '{bad}\n', '{"input":1,"output":"x"}\n', '[]\n'])
def test_invalid_goldens_are_rejected(project, raw):
    _, target, golden = project
    (golden / 'sample.jsonl').write_text(raw)
    with pytest.raises(ValueError):
        testing.golden_to_pytest('sample', target)


def test_actual_interest_recording_passes_handwritten_decimal_fixture(project):
    prepare, _, _ = project
    root = Path(testing.__file__).parent
    cases = [json.loads(line) for line in (root / 'golden/interest.jsonl').read_text().splitlines()]
    prepare(cases, r'''from decimal import Decimal, ROUND_HALF_UP
import re
def main(line):
    fields = line.split('|')
    if len(fields) != 3: return 'ERROR:INVALID_INPUT'
    p, r, y = [value.strip(' ') for value in fields]
    patterns = [r'[0-9]{1,5}(?:\.[0-9]{1,2})?', r'[0-9]{1,3}(?:\.[0-9]{1,2})?', r'[0-9]{1,2}']
    if not all(re.fullmatch(pattern, value) for pattern, value in zip(patterns, [p,r,y])):
        return 'ERROR:INVALID_INPUT'
    p, r, y = Decimal(p), Decimal(r), Decimal(y)
    if r > 100: return 'ERROR:INVALID_INPUT'
    value = (p * r * y / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return f'INTEREST={value:010.2f}'
''')
    assert testing.run_equivalence('sample') == {'passed': 15, 'total': 15, 'failures': []}


def test_mixed_results_preserve_exact_failure_details(project):
    prepare, _, _ = project
    prepare([{'input': 'good', 'output': 'good'}, {'input': ' bad ', 'output': 'bad'}],
            'def main(line): return line\n')
    assert testing.run_equivalence('sample') == {
        'passed': 1, 'total': 2,
        'failures': [{'input': ' bad ', 'expected': 'bad', 'actual': ' bad '}],
    }


def test_dataclasses_and_imports_inside_main(project):
    prepare, target, _ = project
    (target.parent / 'late_helper.py').write_text('VALUE = "works"\n')
    prepare([{'input': 'x', 'output': 'works'}], '''from dataclasses import dataclass
@dataclass
class Result:
    value: str
def main(line):
    from late_helper import VALUE
    return Result(VALUE).value
''')
    assert testing.run_equivalence('sample')['passed'] == 1
