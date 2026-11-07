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

_DRIVER = r"""
import json, sys, traceback, importlib.util
spec = importlib.util.spec_from_file_location("candidate", sys.argv[1])
results = []
try:
    mod = importlib.util.module_from_spec(spec)
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


def run_main(code: str, inputs: list[str], timeout: float = 20) -> dict:
    """Run main(line) for each input. Returns
    {"import_error": str} | {"timeout": True} | {"results": [{ok, output|error, ...}, ...]}"""
    with tempfile.TemporaryDirectory(prefix="p4_sbx_") as d:
        mod, inp, drv = Path(d, "candidate.py"), Path(d, "inputs.json"), Path(d, "driver.py")
        mod.write_text(code)
        inp.write_text(json.dumps(inputs))
        drv.write_text(_DRIVER)
        try:
            r = subprocess.run([sys.executable, "-I", str(drv), str(mod), str(inp)],
                               capture_output=True, text=True, timeout=timeout, cwd=d)
        except subprocess.TimeoutExpired:
            return {"timeout": True}
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            return {"import_error": (r.stderr or r.stdout)[-1500:]}


def run_pytest(module_id: str, code: str, test_src: str, timeout: float = 90) -> dict:
    """Run a generated test file against the module, laid out as modern/<module_id>.py.
    Returns {"ok": bool, "collected_error": bool, "failed": [test names], "output": tail}"""
    with tempfile.TemporaryDirectory(prefix="p4_pyt_") as d:
        (Path(d) / "modern").mkdir()
        (Path(d) / "modern" / "__init__.py").write_text("")
        (Path(d) / "modern" / f"{module_id}.py").write_text(code)
        test_file = Path(d) / f"test_{module_id}.py"
        test_file.write_text(test_src)
        env = {**os.environ, "PYTHONPATH": d}
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=",
                 "--rootdir", d, str(test_file)],
                capture_output=True, text=True, timeout=timeout, cwd=d, env=env)
        except subprocess.TimeoutExpired:
            return {"ok": False, "collected_error": True, "failed": [], "output": "pytest timed out"}
        out = r.stdout + r.stderr
        failed = sorted(set(re.findall(r"^FAILED \S*::(\w+)", out, flags=re.MULTILINE)))
        last = out.strip().splitlines()[-1] if out.strip() else ""
        # rc 2 = collection/import error, 5 = no tests; "N error(s)" in summary = setup errors
        collected_error = r.returncode not in (0, 1) or "error" in last.lower()
        return {"ok": r.returncode == 0, "collected_error": collected_error,
                "failed": failed, "output": out[-3000:]}
