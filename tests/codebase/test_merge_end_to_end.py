"""Merge check (run on the merge computer after all four branches land).

understand() -> compile_program() (+ make_driver() for subprograms) -> run the real COBOL on
the shared inputs -> must equal the hand-written reference Python. No model calls.
Then run the real pipeline:  python tools/isolated_run.py --mode real --legacy-dir samples/legacy
"""
import legacy
import agents
from cbhelpers import INPUTS, SAMPLES, call_or_pending, needs_cobc, pending, reference, run_binary

pytestmark = needs_cobc


def test_sample_codebase_end_to_end(tmp_path):
    modules = agents.understand(str(SAMPLES))
    if "kind" not in modules[0]:
        pending("P3", "understand() codebase keys")
    assert [m["module_id"] for m in modules].index("discount") < [m["module_id"] for m in modules].index("invoice")
    for module in modules:
        mid = module["module_id"]
        if module["kind"] == "subprogram":
            driver = tmp_path / f"{mid}_driver.cbl"
            driver.write_text(call_or_pending("P3", agents.make_driver, (SAMPLES / f"{mid}.cbl").read_text()))
            binary = call_or_pending("P2", legacy.compile_program, str(driver),
                                     link=[module["cobol_path"], *module["link"]], copy_dirs=module["copy_dirs"])
        else:
            binary = call_or_pending("P2", legacy.compile_program, module["cobol_path"],
                                     link=module["link"], copy_dirs=module["copy_dirs"])
        ref = reference(mid)
        for line in INPUTS[mid]:
            assert run_binary(binary, line) == ref.main(line), (mid, line)
