"""``infragram recipes`` lists the 3D vocabulary and draws one item.

The recipes, their knobs, the families and the glyphs were a Python call
away (``infragram.iso3d.vocabulary.recipes()``), with the knobs' types and
the values a text knob takes nowhere at all. The knobs are read from the
builders in ``scene.js`` themselves, so these tests hold the listing to
them. Drawing one (``--svg``) renders in Chromium: that render is a browser
suite of its own (tests/integration/test_recipes_browser.py, which
``verify:browser`` runs), and nothing here starts a browser.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from infragram.cli.user import recipes as command
from infragram.cli.user.recipes import main
from infragram.iso3d.vocabulary import (
    FAMILY_COLOURS,
    GLYPHS,
    SCENE,
    Knob,
    KnobError,
    recipe_knobs,
    recipes,
    summary,
)


def _knob(recipe: str, name: str) -> Knob:
    return next(knob for knob in recipe_knobs()[recipe] if knob.name == name)


def test_every_recipe_has_its_knobs_typed_with_the_builders_defaults() -> None:
    table = recipe_knobs()
    assert set(table) == set(recipes()) and len(table) > 200
    for recipe, knobs in recipes().items():
        assert [(knob.name, knob.default) for knob in table[recipe]] == knobs
    assert _knob("server", "units") == Knob(name="units", type="int", default=2)
    assert _knob("switch", "tall").type == "bool" and _knob("switch", "tall").default is False


def test_a_text_knob_lists_the_values_its_builder_tells_apart() -> None:
    scene = SCENE.read_text(encoding="utf-8")
    assert _knob("reactor", "kind").choices == ("unit", "smr"), "the default first"
    # a lookup table's keys: UNIT[unit]
    assert set(_knob("cluster", "unit").choices) == {
        "server",
        "gpu",
        "appliance",
        "switch",
        "firewall",
        "shelf",
    }
    # ['laptop', 'operator', ...].includes(kind)
    assert {"laptop", "operator", "threat", "courier"} <= set(_knob("person", "kind").choices)
    for knobs in recipe_knobs().values():
        for knob in knobs:
            if knob.type == "str":
                assert knob.choices[0] == knob.default
                assert all(choice in scene for choice in knob.choices)
            else:
                assert knob.choices == ()


def test_a_knob_value_is_read_by_the_knobs_type() -> None:
    assert _knob("server", "units").parse("3") == 3
    assert _knob("switch", "tall").parse("yes") is True
    assert _knob("switch", "tall").parse("false") is False
    assert _knob("reactor", "kind").parse("smr") == "smr"
    with pytest.raises(KnobError):
        _knob("server", "units").parse("three")
    with pytest.raises(KnobError):
        _knob("switch", "tall").parse("maybe")
    anything = Knob(name="x", type="any")
    assert (anything.parse("2"), anything.parse("2.5"), anything.parse("true")) == (2, 2.5, True)
    assert anything.parse("steel") == "steel"


def test_the_listing_names_every_recipe_family_and_glyph(capsys) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    for recipe in recipe_knobs():
        assert any(line.split()[:1] == [recipe] for line in lines), recipe
    assert "units: int = 2, drivesN: int = 4, rows: int = 0" in out
    assert "kind: 'unit' | 'smr' = 'unit'" in out
    for family, colour in FAMILY_COLOURS.items():
        assert f"{family:<12} {colour}" in out
    assert all(glyph in out for glyph in GLYPHS)


def test_one_recipe_in_detail_and_as_json(capsys) -> None:
    assert main(["server"]) == 0
    out = capsys.readouterr().out
    assert "KNOB     units: int = 2" in out
    assert 'Iso("Name", recipe="server", family="compute", units=2, drivesN=4, rows=0)' in out
    assert main(["reactor", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["recipe"] == "reactor" and data["knobs"][0]["choices"] == ["unit", "smr"]
    assert 'kind="unit"' in data["usage"]
    assert main(["--json"]) == 0
    whole = json.loads(capsys.readouterr().out)
    assert whole == json.loads(json.dumps(summary()))
    assert whole["families"]["storage"] == {
        "colour": FAMILY_COLOURS["storage"],
        "glyph": "database",
    }


def test_a_misspelt_recipe_says_which_was_meant(capsys) -> None:
    assert main(["reactr"]) == 2
    assert "did you mean reactor" in capsys.readouterr().err


def test_a_spec_the_builder_cannot_build_is_refused_before_any_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    def no_browser() -> str:
        raise AssertionError("the browser was asked for")

    monkeypatch.setattr(command, "_browser_missing", no_browser)
    out = tmp_path / "x.svg"
    for argv, said in (
        (["--set", "bays=3"], "has no knob 'bays'; it takes units, drivesN, rows"),
        (["--set", "units=three"], "units is a whole number"),
        (["--set", "units"], "--set takes KNOB=VALUE"),
        (["--family", "lava"], "unknown family 'lava'"),
        (["--colour", "red"], "colour must be #rrggbb"),
        (["--glyph", "no-such-glyph"], "unknown glyph"),
    ):
        assert main(["server", "--svg", str(out), *argv]) == 2
        assert said in capsys.readouterr().err
    assert main(["--svg", str(out)]) == 2
    assert "name it" in capsys.readouterr().err
    assert not out.exists()


def test_without_a_browser_the_drawing_fails_in_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(
        command, "_browser_missing", lambda: "Playwright isn't installed (pip install playwright)"
    )
    out = tmp_path / "server.svg"
    assert main(["server", "--svg", str(out), "--set", "units=3"]) == 2
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and err.startswith("ERROR: drawing a recipe renders it in Chromium")
    assert "Playwright isn't installed" in err and not out.exists()


def test_an_existing_picture_is_kept_unless_forced(tmp_path: Path, capsys) -> None:
    out = tmp_path / "server.svg"
    out.write_text("<svg/>", encoding="utf-8")
    assert main(["server", "--svg", str(out)]) == 2
    assert "exists" in capsys.readouterr().err
    assert out.read_text(encoding="utf-8") == "<svg/>"
