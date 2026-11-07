"""Compile originals, preserve their output, and atomically record golden cases."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "legacy" / "bin"
GOLDEN_DIR = PROJECT_ROOT / "golden"
COMPILE_TIMEOUT_SECONDS = 30
RUN_TIMEOUT_SECONDS = 5


class LegacyError(RuntimeError):
    """An infrastructure failure, rather than a program's business response."""


class CobolCompileError(LegacyError):
    """The compiler was missing, timed out, or rejected the source."""


class CobolRunError(LegacyError):
    """The executable failed to start, timed out, or exited unsuccessfully."""


def _diagnostic(data: bytes | None) -> str:
    return (data or b"").decode("utf-8", errors="replace")


def _kill_process_group(process: subprocess.Popen) -> None:
    """Clean up the entire compiler/runtime job on macOS and other POSIX hosts."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_process(command: list[str], timeout: float, data: bytes | None = None,
                 *, extra_env: dict | None = None, cwd=None):
    # Inherit PATH and linker settings, but make numeric/diagnostic locale stable.
    environment = dict(os.environ, LC_ALL="C", LANG="C")
    environment.update(extra_env or {})
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True, env=environment, cwd=cwd,
    ) as process:
        try:
            stdout, stderr = process.communicate(input=data, timeout=timeout)
        except subprocess.TimeoutExpired:
            # Killing just cobc can leave its C compiler alive. A runtime child
            # can also hold stdout open even after its parent has exited.
            _kill_process_group(process)
            try:
                stdout, stderr = process.communicate(timeout=1)
            except subprocess.TimeoutExpired as cleanup:
                # A descendant that deliberately changed sessions is outside
                # this process group. Do not wait forever on its inherited pipe.
                stdout, stderr = cleanup.output or b"", cleanup.stderr or b""
                process.stdout.close()
                process.stderr.close()
                process.wait()
            raise subprocess.TimeoutExpired(command, timeout, stdout, stderr) from None
        except BaseException:
            _kill_process_group(process)
            process.wait()
            raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _encode_input(input_line: str) -> bytes:
    if not isinstance(input_line, str):
        raise TypeError("input_line must be a string")
    if "\n" in input_line or "\r" in input_line:
        raise ValueError("input_line must contain exactly one line, without CR/LF")
    try:
        return (input_line + "\n").encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("input_line must be valid UTF-8 text") from exc


def compile_cobol(cobol_path) -> str:
    """Build a free-format .cbl file; return an absolute executable path.

    Relative source paths are relative to the caller's working directory.
    A failed compilation never replaces the last successfully built binary.
    The caller must use the returned path only after this function succeeds.
    """
    source = Path(cobol_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"COBOL source does not exist: {source}")
    if source.suffix.lower() != ".cbl":
        raise ValueError(f"Expected a .cbl source file: {source}")
    compiler = shutil.which("cobc")
    if compiler is None:
        raise CobolCompileError("cobc is missing; install with: brew install gnucobol")

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    # Different modules may have identical basenames in different directories.
    source_id = hashlib.sha256(os.fsencode(source)).hexdigest()[:12]
    binary = BIN_DIR / f"{source.stem}-{source_id}"
    with tempfile.TemporaryDirectory(prefix=".compile-", dir=BIN_DIR) as folder:
        staged = Path(folder) / source.stem
        command = [compiler, "-x", "-free", "-o", str(staged), str(source)]
        try:
            result = _run_process(command, COMPILE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            raise CobolCompileError(
                f"Compilation timed out after {COMPILE_TIMEOUT_SECONDS}s: {source}"
                f"\n{_diagnostic(exc.stderr)}"
            ) from exc
        except OSError as exc:
            raise CobolCompileError(f"Cannot start compiler: {exc}") from exc
        if result.returncode != 0:
            raise CobolCompileError(
                f"Compilation failed ({result.returncode}): {source}\n"
                f"{_diagnostic(result.stdout)}{_diagnostic(result.stderr)}"
            )
        if not staged.is_file() or not os.access(staged, os.X_OK):
            raise CobolCompileError(f"Compiler produced no executable: {source}")
        os.replace(staged, binary)
    return str(binary)


def run_cobol(binary_path, input_line: str) -> str:
    """Send one UTF-8 line; return stdout minus exactly one final newline.

    Internal newlines and all spaces survive. stderr never enters the result.
    A final CRLF is treated as one line ending; a lone final CR is preserved.
    """
    data = _encode_input(input_line)
    binary = Path(binary_path).expanduser().resolve()
    try:
        result = _run_process([str(binary)], RUN_TIMEOUT_SECONDS, data)
    except subprocess.TimeoutExpired as exc:
        raise CobolRunError(
            f"Execution timed out after {RUN_TIMEOUT_SECONDS}s: {binary}; "
            f"input={input_line!r}"
            f"\nstderr: {_diagnostic(exc.stderr)}"
        ) from exc
    except OSError as exc:
        raise CobolRunError(f"Cannot execute {binary}: {exc}") from exc
    if result.returncode != 0:
        raise CobolRunError(
            f"Execution failed ({result.returncode}): {binary}; "
            f"input={input_line!r}\n"
            f"stdout: {_diagnostic(result.stdout)}\n"
            f"stderr: {_diagnostic(result.stderr)}"
        )
    output = result.stdout
    if output.endswith(b"\r\n"):
        output = output[:-2]
    elif output.endswith(b"\n"):
        output = output[:-1]
    try:
        return output.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise CobolRunError(f"stdout is not valid UTF-8: {binary}") from exc


def record_golden(module_id, binary_path, inputs: list[str]) -> str:
    """Record actual original outputs to golden/<module_id>.jsonl.

    Writes atomically: a failed input leaves any prior golden file intact.
    Output paths are anchored to this package, independent of the caller's cwd.
    Business errors printed by COBOL are valid outputs; runtime errors abort.
    """
    if not isinstance(module_id, str) or not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*", module_id
    ):
        raise ValueError("module_id must be an identifier, e.g. 'interest'")
    if not isinstance(inputs, list) or not inputs:
        raise ValueError("inputs must be a nonempty list of strings")
    if not all(isinstance(item, str) for item in inputs):
        raise TypeError("every input must be a string")
    # Validate the complete batch before starting any original executable.
    inputs = list(inputs)
    for input_line in inputs:
        _encode_input(input_line)

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    destination = GOLDEN_DIR / f"{module_id}.jsonl"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=GOLDEN_DIR,
            prefix=f".{module_id}-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            for input_line in inputs:
                output = run_cobol(binary_path, input_line)
                stream.write(json.dumps(
                    {"input": input_line, "output": output}, ensure_ascii=False
                ) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return str(destination)
