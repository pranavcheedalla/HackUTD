"""Run model-generated code in a separate Python process with a timeout.

Used by the agents to check Nemotron's output before handing it to the pipeline:
the generated module never runs inside the pipeline process, so an infinite loop or
a crash in generated code can't take the run down.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from legacy.runtime import _run_process, OutputLimitExceeded

MODERN_DIR = Path(__file__).resolve().parent.parent / "modern"  # accepted rewrites

_DRIVER = r"""
import json, os, sys, traceback, importlib.util
# `python -I` does not put the script's folder on sys.path: add the candidate's folder so
# verified dependency modules written next to it (`import discount`) can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[1])))
spec = importlib.util.spec_from_file_location("candidate", sys.argv[1])
results = []
try:
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
except Exception:
    print(json.dumps({"import_error": traceback.format_exc(limit=3)}))
    sys.exit(0)
for line in json.load(open(sys.argv[2])):
    try:
        out = mod.main(line)
        results.append({"ok": True, "output": out if isinstance(out, str) else repr(out),
                        "type_ok": isinstance(out, str)})
    except Exception as e:
        results.append({"ok": False, "error": f"{type(e).__name__}: {e}",
                        "trace": traceback.format_exc(limit=3)})
print(json.dumps({"results": results}))
"""


def run_main(code: str, inputs: list[str], timeout: float = 20,
             modules: dict[str, str] | None = None) -> dict:
    """Run main(line) for each input. `modules` = {module_id: python_src} of dependencies,
    written next to the candidate so it can `import <module_id>`. Returns
    {"import_error": str} | {"timeout": True} | {"results": [{ok, output|error, ...}, ...]}"""
    with tempfile.TemporaryDirectory(prefix="p4_sbx_") as d:
        mod, inp, drv = Path(d, "candidate.py"), Path(d, "inputs.json"), Path(d, "driver.py")
        for module_id, src in (modules or {}).items():
            if module_id not in ("candidate", "driver", "inputs"):
                Path(d, f"{module_id}.py").write_text(src)
        mod.write_text(code)
        inp.write_text(json.dumps(inputs))
        drv.write_text(_DRIVER)
        try:
            r = _run_process([sys.executable, "-I", str(drv), str(mod), str(inp)], timeout, cwd=d)
        except subprocess.TimeoutExpired:
            return {"timeout": True}
        except OutputLimitExceeded:
            return {'import_error': 'Candidate exceeded the output limit'}
        if r.returncode:
            return {'import_error': f'Candidate process exited {r.returncode}: {r.stderr.decode(errors="replace")[-1500:]}'}
        try:
            result = json.loads(r.stdout.strip().splitlines()[-1])
            if not isinstance(result, dict) or not ('import_error' in result or isinstance(result.get('results'), list)):
                raise ValueError('Invalid candidate result')
            return result
        except (IndexError, ValueError):
            return {"import_error": (r.stderr or r.stdout).decode(errors='replace')[-1500:]}


def run_pytest(module_id: str, code: str, test_src: str, timeout: float = 90,
               modern_dir: str | Path | None = None) -> dict:
    """Run a generated test file against the module, laid out as modern/<module_id>.py.
    Every other accepted module in the project's modern/ is copied in too, and <tmp>/modern is
    on PYTHONPATH, so a caller that does `import discount` works (callees are accepted first).
    Returns {"ok": bool, "collected_error": bool, "failed": [test names], "output": tail}"""
    with tempfile.TemporaryDirectory(prefix="p4_pyt_") as d:
        (Path(d) / "modern").mkdir()
        (Path(d) / "modern" / "__init__.py").write_text("")
        src_dir = Path(modern_dir) if modern_dir else MODERN_DIR
        if src_dir.is_dir():
            for f in src_dir.glob("*.py"):
                if f.stem not in (module_id, "__init__"):
                    (Path(d) / "modern" / f.name).write_text(f.read_text())
        (Path(d) / "modern" / f"{module_id}.py").write_text(code)
        test_file = Path(d) / f"test_{module_id}.py"
        test_file.write_text(test_src)
        env = {'PYTHONPATH': d + os.pathsep + str(Path(d) / "modern"),
               'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTEST_ADDOPTS': ''}
        try:
            r = _run_process(
                [sys.executable, "-m", "pytest", "-q", '-c', os.devnull, '--noconftest', '--capture=no',
                 "-p", "no:cacheprovider", "-o", "addopts=",
                 "--rootdir", d, str(test_file)],
                timeout, cwd=d, extra_env=env)
        except subprocess.TimeoutExpired:
            return {"ok": False, "collected_error": True, "failed": [], "output": "pytest timed out"}
        except OutputLimitExceeded:
            return {'ok': False, 'collected_error': True, 'failed': [], 'output': 'pytest exceeded the output limit'}
        out = (r.stdout + r.stderr).decode(errors='replace')
        # test-level FAILED and setup ERROR lines name the test; a file-level ERROR has no "::"
        failed = sorted(set(re.findall(r"^(?:FAILED|ERROR) \S*::(\w+)", out, flags=re.MULTILINE)))
        last = out.strip().splitlines()[-1] if out.strip() else ""
        # rc 2 = collection/import error, 5 = no tests; "N error(s)" in summary = setup errors
        collected_error = r.returncode not in (0, 1) or "error" in last.lower()
        return {"ok": r.returncode == 0, "collected_error": collected_error,
                "failed": failed, "output": out[-3000:]}
