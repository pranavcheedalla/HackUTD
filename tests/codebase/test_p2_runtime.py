"""P2 (Madhav): legacy.compile_program links CALLed subprograms, finds copybooks, handles fixed format."""
import pytest

import legacy
from legacy.runtime import CobolCompileError
from cbhelpers import FIXTURES, INPUTS, ROOT, SAMPLES, call_or_pending, needs_cobc, reference, run_binary

pytestmark = needs_cobc
OWNER = "P2 Madhav, legacy/runtime.py"


def test_links_callee_and_finds_copybook():
    binary = call_or_pending(OWNER, legacy.compile_program, str(SAMPLES / "invoice.cbl"),
                             link=[str(SAMPLES / "discount.cbl")], copy_dirs=[str(SAMPLES / "copybooks")])
    ref = reference("invoice")
    for line in INPUTS["invoice"]:
        assert run_binary(binary, line) == ref.main(line), line


def test_fixed_format_program_without_dependencies():
    binary = call_or_pending(OWNER, legacy.compile_program, str(SAMPLES / "interest.cbl"))
    ref = reference("interest")
    for line in INPUTS["interest"]:
        assert run_binary(binary, line) == ref.main(line), line


def test_free_format_driver_linked_with_fixed_format_subprogram():
    binary = call_or_pending(OWNER, legacy.compile_program,
                             str(FIXTURES / "drivers" / "discount_driver.cbl"), link=[str(SAMPLES / "discount.cbl")])
    ref = reference("discount")
    for line in INPUTS["discount"]:
        assert run_binary(binary, line) == ref.main(line), line


def test_existing_free_format_programs_unchanged():
    binary = call_or_pending(OWNER, legacy.compile_program, str(ROOT / "legacy" / "interest.cbl"))
    assert legacy.run_cobol(binary, "1000.00|5.00|2") == legacy.run_cobol(
        legacy.compile_cobol(str(ROOT / "legacy" / "interest.cbl")), "1000.00|5.00|2")


def test_missing_copybook_dir_is_a_clear_compile_error():
    with pytest.raises(CobolCompileError):
        call_or_pending(OWNER, legacy.compile_program, str(SAMPLES / "invoice.cbl"),
                        link=[str(SAMPLES / "discount.cbl")])


def test_different_links_never_share_a_cached_binary():
    with_link = call_or_pending(OWNER, legacy.compile_program, str(SAMPLES / "invoice.cbl"),
                                link=[str(SAMPLES / "discount.cbl")], copy_dirs=[str(SAMPLES / "copybooks")])
    alone = call_or_pending(OWNER, legacy.compile_program, str(FIXTURES / "drivers" / "discount_driver.cbl"),
                            link=[str(SAMPLES / "discount.cbl")])
    assert with_link != alone
