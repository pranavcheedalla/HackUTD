"""Exercise real subprocesses and the original, not mocked output comparisons."""

import json
from decimal import Decimal, ROUND_HALF_UP
import os
from pathlib import Path
import random
import shlex
import signal
import subprocess
import sys
import time

import pytest

import legacy
from legacy import runtime

ROOT = Path(__file__).resolve().parents[2]
INPUTS = json.loads((ROOT / "legacy/inputs/interest.json").read_text())
# Independent, handwritten checks. Golden files are always produced by COBOL.
EXPECTED = [
    "INTEREST=0000100.00", "INTEREST=0000281.31", "INTEREST=0000100.00",
    "INTEREST=0000000.00", "INTEREST=0000000.00", "INTEREST=0000000.00",
    "ERROR:INVALID_INPUT", "ERROR:INVALID_INPUT", "ERROR:INVALID_INPUT",
    "INTEREST=9899999.01", "INTEREST=0000010.00", "INTEREST=0000000.00",
    "INTEREST=0000000.01", "ERROR:INVALID_INPUT", "ERROR:INVALID_INPUT",
]


@pytest.fixture(scope="module")
def interest_binary():
    return legacy.compile_cobol(ROOT / "legacy/interest.cbl")


@pytest.fixture
def executable(tmp_path):
    def make(body):
        script = tmp_path / "fixture executable"
        script.write_text(
            "#!/bin/sh\nexec " + shlex.quote(sys.executable)
            + " -c " + shlex.quote(body) + ' "$@"\n', encoding="utf-8",
        )
        script.chmod(0o755)
        return script
    return make


@pytest.mark.parametrize("input_line,expected", list(zip(INPUTS, EXPECTED)))
def test_interest_original_outputs(interest_binary, input_line, expected):
    assert legacy.run_cobol(interest_binary, input_line) == expected


@pytest.mark.parametrize("input_line", [
    "", "100|5", "100|5|1|", "|5|1", "100||1", "100|5|",
    "100|5|100", "100|5|1.0", "1.234|5|1", "1e3|5|1", "NaN|5|1",
    "1.|5|1", ".5|5|1", "+1|5|1", "1,000|5|1", "1..0|5|1",
])
def test_interest_rejects_malformed_inputs(interest_binary, input_line):
    assert legacy.run_cobol(interest_binary, input_line) == "ERROR:INVALID_INPUT"


def test_interest_allows_spaces_around_fields(interest_binary):
    assert legacy.run_cobol(interest_binary, " 1000 | 5 | 2 ") == "INTEREST=0000100.00"


@pytest.mark.parametrize("raw,expected", [
    (b"  VALUE=0001.20  \n", "  VALUE=0001.20  "),
    (b"first\nsecond\n\n", "first\nsecond\n"),
    (b"VALUE\r\n", "VALUE"),
    (b"first\r\nsecond\r\n", "first\r\nsecond"),
    (b"VALUE\r", "VALUE\r"),
    (b"no newline  ", "no newline  "),
    (b"", ""),
])
def test_stdout_is_preserved(executable, raw, expected):
    binary = executable(f"import os\nos.write(1, {raw!r})\n")
    assert legacy.run_cobol(binary, "") == expected


def test_sends_exactly_one_input_line_and_keeps_stderr_separate(executable):
    binary = executable(
        "import sys\n"
        "data = sys.stdin.buffer.read()\n"
        "sys.stderr.write('diagnostic only\\n')\n"
        "sys.stdout.buffer.write(data)\n"
    )
    assert legacy.run_cobol(binary, "  0001|5  ") == "  0001|5  "


@pytest.mark.parametrize("input_line", ["one\ntwo", "one\rtwo"])
def test_rejects_multiline_input(executable, input_line):
    with pytest.raises(ValueError, match="one line"):
        legacy.run_cobol(executable("pass\n"), input_line)


def test_nonzero_exit_is_not_a_golden_output(executable):
    binary = executable("import sys\nprint('partial')\nsys.stderr.write('bad')\nsys.exit(7)\n")
    with pytest.raises(legacy.CobolRunError, match=r"failed \(7\)") as error:
        legacy.run_cobol(binary, "input")
    assert "partial" in str(error.value) and "bad" in str(error.value)


def test_missing_executable_is_clear(tmp_path):
    with pytest.raises(legacy.CobolRunError, match="Cannot execute"):
        legacy.run_cobol(tmp_path / "missing", "input")


def test_runtime_timeout(executable, monkeypatch):
    monkeypatch.setattr(runtime, "RUN_TIMEOUT_SECONDS", 0.1)
    with pytest.raises(legacy.CobolRunError, match="timed out"):
        legacy.run_cobol(executable("import time\ntime.sleep(10)\n"), "input")


def test_non_utf8_stdout_is_clear(executable):
    with pytest.raises(legacy.CobolRunError, match="not valid UTF-8"):
        legacy.run_cobol(executable("import os\nos.write(1, b'\\xff')\n"), "")


def test_missing_source_is_clear(tmp_path):
    with pytest.raises(FileNotFoundError, match="source does not exist"):
        legacy.compile_cobol(tmp_path / "missing.cbl")


def test_compile_error_preserves_previous_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "BIN_DIR", tmp_path / "bin")
    source = tmp_path / "original.cbl"
    source.write_text(
        'identification division.\nprogram-id. original.\n'
        'procedure division.\ndisplay "OLD"\nstop run.\n'
    )
    binary = legacy.compile_cobol(source)
    original_bytes = Path(binary).read_bytes()
    source.write_text("this is deliberately invalid COBOL\n")
    with pytest.raises(legacy.CobolCompileError, match="Compilation failed"):
        legacy.compile_cobol(source)
    assert Path(binary).read_bytes() == original_bytes
    assert not list(runtime.BIN_DIR.glob(".compile-*"))


def test_missing_compiler_is_clear(tmp_path, monkeypatch):
    source = tmp_path / "sample.cbl"
    source.write_text("anything")
    monkeypatch.setattr(runtime.shutil, "which", lambda name: None)
    with pytest.raises(legacy.CobolCompileError, match="brew install gnucobol"):
        legacy.compile_cobol(source)


def test_compiler_timeout(tmp_path, executable, monkeypatch):
    source = tmp_path / "sample.cbl"
    source.write_text("anything")
    compiler = executable("import time\ntime.sleep(10)\n")
    monkeypatch.setattr(runtime, "BIN_DIR", tmp_path / "bin")
    monkeypatch.setattr(runtime, "COMPILE_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(runtime.shutil, "which", lambda name: str(compiler))
    with pytest.raises(legacy.CobolCompileError, match="timed out"):
        legacy.compile_cobol(source)
    assert not list(runtime.BIN_DIR.glob(".compile-*"))


def test_record_actual_interest_outputs_from_another_cwd(
    interest_binary, tmp_path, monkeypatch
):
    monkeypatch.setattr(runtime, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.chdir(tmp_path)
    path = Path(legacy.record_golden("interest", interest_binary, INPUTS))
    cases = [json.loads(line) for line in path.read_text().splitlines()]
    assert path.is_absolute()
    assert cases == [
        {"input": input_line, "output": expected}
        for input_line, expected in zip(INPUTS, EXPECTED)
    ]
    assert len(cases) == 15


def test_record_round_trips_json_and_preserves_duplicates(
    executable, tmp_path, monkeypatch
):
    monkeypatch.setattr(runtime, "GOLDEN_DIR", tmp_path / "golden")
    inputs = ['  "café"\\value  ', '  "café"\\value  ']
    binary = executable("import os\nos.write(1, b' first\\nsecond  \\n')\n")
    path = Path(legacy.record_golden("sample", binary, inputs))
    cases = [json.loads(line) for line in path.read_text().splitlines()]
    assert cases == [{"input": value, "output": " first\nsecond  "} for value in inputs]


def test_failed_record_leaves_prior_file_unchanged(executable, tmp_path, monkeypatch):
    folder = tmp_path / "golden"
    folder.mkdir()
    destination = folder / "sample.jsonl"
    original = b'{"input":"old","output":"old"}\n'
    destination.write_bytes(original)
    monkeypatch.setattr(runtime, "GOLDEN_DIR", folder)
    binary = executable(
        "import sys\nline = sys.stdin.readline().rstrip('\\n')\n"
        "sys.exit(3) if line == 'bad' else print(line)\n"
    )
    with pytest.raises(legacy.CobolRunError):
        legacy.record_golden("sample", binary, ["good", "bad"])
    assert destination.read_bytes() == original
    assert not list(folder.glob("*.tmp"))


@pytest.mark.parametrize("module_id", ["../escape", "a/b", "", "a-b"])
def test_invalid_module_id_is_rejected(module_id):
    with pytest.raises(ValueError, match="module_id"):
        legacy.record_golden(module_id, "unused", ["input"])


def test_empty_record_is_rejected():
    with pytest.raises(ValueError, match="nonempty"):
        legacy.record_golden("sample", "unused", [])


def test_shipped_golden_is_complete_and_matches_handwritten_checks():
    path = ROOT / "golden/interest.jsonl"
    cases = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(INPUTS) == len(EXPECTED) == len(cases) == 15
    assert cases == [
        {"input": input_line, "output": expected}
        for input_line, expected in zip(INPUTS, EXPECTED)
    ]
    assert len((ROOT / "legacy/interest.cbl").read_text().splitlines()) < 150


def test_interest_against_independent_decimal_oracle(interest_binary):
    # Seeded arithmetic audit: never used by the production golden recorder.
    generator = random.Random(7112026)
    examples = [(1, 50, 1), (1, 49, 1), (1, 51, 1), (9999999, 10000, 99)]
    examples += [
        (generator.randrange(10000000), generator.randrange(10001), generator.randrange(100))
        for _ in range(128)
    ]
    for principal_cents, rate_hundredths, years in examples:
        principal = Decimal(principal_cents) / 100
        rate = Decimal(rate_hundredths) / 100
        line = f"{principal:.2f}|{rate:.2f}|{years}"
        interest = (principal * rate * years / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )
        expected = f"INTEREST={interest:010.2f}"
        assert legacy.run_cobol(interest_binary, line) == expected, line


def test_same_basename_sources_do_not_overwrite_each_other(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "BIN_DIR", tmp_path / "binaries with spaces")
    binaries = []
    for label in ("A", "B"):
        folder = tmp_path / f"module {label} ü"
        folder.mkdir()
        source = folder / "sample.cbl"
        source.write_text(
            'identification division.\nprogram-id. sample.\nprocedure division.\n'
            f'display "{label}"\nstop run.\n'
        )
        binaries.append(legacy.compile_cobol(source))
    assert binaries[0] != binaries[1]
    assert [legacy.run_cobol(binary, "") for binary in binaries] == ["A", "B"]


@pytest.mark.parametrize("parent_exits", [False, True])
def test_timeout_stops_children_that_hold_output_pipes(
    executable, tmp_path, monkeypatch, parent_exits
):
    marker = tmp_path / "child survived"
    group_file = tmp_path / "process group"
    body = (
        "import os, time\nfrom pathlib import Path\n"
        f"Path({str(group_file)!r}).write_text(str(os.getpgrp()))\n"
        "child = os.fork()\nif child == 0:\n"
        "    time.sleep(1)\n"
        f"    Path({str(marker)!r}).write_text('unexpected descendant')\n"
        "    os._exit(0)\n"
        + ("os._exit(0)\n" if parent_exits else "time.sleep(10)\n")
    )
    monkeypatch.setattr(runtime, "RUN_TIMEOUT_SECONDS", 0.3)
    try:
        started = time.monotonic()
        with pytest.raises(legacy.CobolRunError, match="timed out"):
            legacy.run_cobol(executable(body), "input")
        assert time.monotonic() - started < 2
        time.sleep(1.1)
        assert not marker.exists(), "timeout left a child process running"
    finally:
        if group_file.exists():
            try:
                os.killpg(int(group_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_numeric_locale_is_stable(executable, monkeypatch):
    monkeypatch.setenv("LC_ALL", "invalid_parent_locale")
    binary = executable("import os\nprint(os.environ['LC_ALL'])\n")
    assert legacy.run_cobol(binary, "") == "C"


@pytest.mark.parametrize("create_nonexecutable", [False, True])
def test_successful_compiler_must_produce_an_executable(
    tmp_path, executable, monkeypatch, create_nonexecutable
):
    source = tmp_path / "sample.cbl"
    source.write_text("anything")
    compiler = executable(
        "import sys\nfrom pathlib import Path\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text('not executable')\n"
        if create_nonexecutable else "pass\n"
    )
    monkeypatch.setattr(runtime, "BIN_DIR", tmp_path / "bin")
    monkeypatch.setattr(runtime.shutil, "which", lambda name: str(compiler))
    with pytest.raises(legacy.CobolCompileError, match="no executable"):
        legacy.compile_cobol(source)


@pytest.mark.parametrize("bad_input,error", [(123, TypeError), ("\ud800", ValueError)])
def test_invalid_python_inputs_fail_before_execution(bad_input, error):
    with pytest.raises(error):
        legacy.run_cobol("executable-that-must-not-start", bad_input)


def test_entire_batch_is_validated_before_first_execution(executable, tmp_path, monkeypatch):
    marker = tmp_path / "started"
    folder = tmp_path / "golden"
    monkeypatch.setattr(runtime, "GOLDEN_DIR", folder)
    binary = executable(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    with pytest.raises(ValueError, match="one line"):
        legacy.record_golden("sample", binary, ["first valid input", "bad\nsecond line"])
    assert not marker.exists()
    assert not folder.exists()


def test_failed_atomic_replace_preserves_reference(executable, tmp_path, monkeypatch):
    folder = tmp_path / "golden"
    folder.mkdir()
    destination = folder / "sample.jsonl"
    destination.write_text("old reference\n")
    monkeypatch.setattr(runtime, "GOLDEN_DIR", folder)
    def fail_replace(source, target):
        raise OSError("simulated write failure")
    monkeypatch.setattr(runtime.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated write failure"):
        legacy.record_golden("sample", executable("print('new output')\n"), ["input"])
    assert destination.read_text() == "old reference\n"
    assert not list(folder.glob("*.tmp"))


def test_setup_smoke_command_works_from_another_directory(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "check_setup.py")], cwd=tmp_path,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "HELLO FROM COBOL" in result.stdout


def test_cli_detects_reference_drift_and_requires_explicit_update(tmp_path):
    # Exercise an isolated relocated copy so this test cannot alter the oracle.
    import shutil
    copy = tmp_path / "handoff with spaces"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(
        ".git", ".env", ".env.*", "runs", "bin", "__pycache__", ".pytest_cache", ".venv", "validation",
    ))
    golden = copy / "golden/interest.jsonl"
    original = golden.read_bytes()
    cases = [json.loads(line) for line in original.splitlines()]
    cases[0]["output"] = "deliberately incorrect reference"
    golden.write_text("".join(json.dumps(case) + "\n" for case in cases))
    modified = golden.read_bytes()
    def invoke(*arguments):
        return subprocess.run(
            [sys.executable, str(copy / "record_interest.py"), *arguments],
            cwd=tmp_path, capture_output=True, text=True, timeout=30,
        )
    result = invoke("--check")
    assert result.returncode == 1
    assert "Case 1:" in result.stderr and "Reference preserved" in result.stderr
    assert golden.read_bytes() == modified
    assert invoke().returncode == 1  # default must also preserve a differing file
    assert golden.read_bytes() == modified
    result = invoke("--update")
    assert result.returncode == 0, result.stderr
    assert golden.read_bytes() == original
    assert invoke("--check").returncode == 0
    golden.unlink()
    assert invoke("--check").returncode == 1
    assert not golden.exists()
    assert invoke().returncode == 0
    assert golden.read_bytes() == original
