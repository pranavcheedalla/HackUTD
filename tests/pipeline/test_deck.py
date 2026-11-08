"""The three presenter slides live inside NorthBound and hand off to it and back."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_three_slides_that_hand_off_to_northbound_and_back():
    deck = (ROOT / "web" / "deck.html").read_text()
    assert len(re.findall(r'<section class="slide" data-n="\d"', deck)) == 3
    assert "location.href = './'" in deck  # slide 2 → the live product
    assert "deck.html#3" in (ROOT / "web" / "galaxy.js").read_text()  # C in NorthBound → the wrap-up
    # only assets the page already ships with: no external fonts or scripts
    assert "http://" not in deck and "https://" not in deck


def test_the_wrap_up_numbers_match_the_recordings():
    deck = (ROOT / "web" / "deck.html").read_text()
    rep = json.loads((ROOT / "web" / "replays" / "retail.json").read_text())
    done = [m for m in rep["modules"] if m["status"] == "done"]
    assert f"{len(done)} / {len(rep['modules'])}" in deck  # 6 / 6
    assert f"<b>{sum(m['tests_total'] for m in done)}</b>" in deck  # 163
    settle = next(m for m in rep["modules"] if m["id"] == "settle")
    assert f"verified {settle['tests_passed']} / {settle['tests_total']}" in deck  # 28 / 28
