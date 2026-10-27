"""The cast (P17.1.3): every board desk is a person in web/src/office/cast.ts, with the fields the HQ shows."""
import re
from pathlib import Path

from frameflow import boardview

OFFICE = Path(__file__).resolve().parent.parent / "web" / "src" / "office"


def entries(ts):
    return {m.group(1): m.group(0) for m in re.finditer(r'\{ id: "([a-z]+)",.*\}', ts)}


def test_every_desk_has_a_person():
    desks = set(re.findall(r'\{ id: "([a-z]+)", label:', (OFFICE / "desks.ts").read_text()))
    cast = entries((OFFICE / "cast.ts").read_text())
    assert desks == {k for k, _ in boardview.DESKS}   # desks.ts follows boardview's desks
    assert desks <= set(cast), f"desks without a cast entry: {sorted(desks - set(cast))}"
    for pid, row in cast.items():
        for field in ("name", "title", "catchphrase", "rival", "cue", "voice"):
            assert re.search(rf'{field}: "[^"]+"', row), f"{pid} has no {field}"


def test_habit_is_bade_sahab_ka_khaas():
    cast = entries((OFFICE / "cast.ts").read_text())
    assert 'name: "Habit"' in cast["narrator"] and 'title: "Bade Sahab ka Khaas"' in cast["narrator"]
    assert 'name: "Bade Sahab"' in cast["you"]
