"""A candidate recipe is staged, named, refused or written the way the tools promise."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

from infragram.iso3d import recipes
from infragram.iso3d.recipes import (
    MARKER,
    RecipeError,
    add_recipe,
    builder_name,
    spec_for,
    table_line,
    with_candidate,
)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
CANDIDATE = """// A crate: a box on a plate with the badge on its front.
R.crate = (fam, tex, wide = false) => {
  const g = new THREE.Group(); plate7(g, 12, 10);
  g.add(boxMesh(wide ? 10 : 6, 5, 5, glossAccent(fam.colour), 0, 2.9, 0));
  badge(g, tex, 1.6, 0, 2.9, 2.54); return g;
};
"""


def test_the_candidate_names_its_one_builder() -> None:
    assert builder_name(CANDIDATE) == "crate"
    with pytest.raises(RecipeError, match="exactly one builder"):
        builder_name("const x = 1;")
    with pytest.raises(RecipeError, match="found crate, box"):
        builder_name(CANDIDATE + "R.box = (fam, tex) => { return new THREE.Group(); };")


def test_the_candidate_lands_before_the_render_section_and_never_twice() -> None:
    scene = recipes.SCENE.read_text(encoding="utf-8")
    staged = with_candidate(scene, CANDIDATE)
    assert staged.index("R.crate = ") < staged.index(MARKER)
    assert staged.count("R.crate = ") == 1
    with pytest.raises(RecipeError, match="already has a recipe 'server'"):
        with_candidate(scene, "R.server = (fam, tex) => { return new THREE.Group(); };")


def test_a_spec_takes_the_family_colour_and_glyph_or_its_own() -> None:
    spec = spec_for("crate", args=(True,), family="storage")
    assert spec["colour"] == "#0f9d8a" and spec["args"] == [True] and spec["glyph"]
    assert spec_for("crate", colour="#ABCDEF", badge=False)["colour"] == "#abcdef"
    assert spec_for("crate", badge=False)["glyph"] == ""
    with pytest.raises(RecipeError, match="unknown family"):
        spec_for("crate", family="mystery")
    with pytest.raises(RecipeError, match="#rrggbb"):
        spec_for("crate", colour="teal")
    with pytest.raises(RecipeError, match="unknown glyph"):
        spec_for("crate", glyph="unicorn")


def test_the_table_line_is_the_tables_own_form() -> None:
    assert (
        table_line("crate", "Crate", "storage", "crate")
        == '    item("crate", "Crate", "storage", "crate"),'
    )
    assert table_line("wide-crate", "Wide crate", "storage", "crate", (True,), ("box",)) == (
        '    item("wide-crate", "Wide crate", "storage", "crate", True, aliases=("box",)),'
    )
    assert table_line("kiln", "Kiln", "industrial", "process", ("kiln",), ("oven", "furnace")) == (
        '    item("kiln", "Kiln", "industrial", "process", "kiln", aliases=("oven", "furnace")),'
    )


def test_adding_writes_the_scene_and_the_table_and_the_flat_kit_still_draws(tmp_path: Path) -> None:
    scene_copy = tmp_path / "scene.js"
    table_copy = tmp_path / "iso-icons.py"
    (tmp_path / ".claude-plugin").mkdir()  # the table script finds its repository by this folder
    shutil.copy(recipes.SCENE, scene_copy)
    shutil.copy(recipes.TABLE, table_copy)
    written = add_recipe(
        CANDIDATE,
        item_id="crate",
        name="Crate",
        family="storage",
        args=(True,),
        aliases=("box",),
        scene_path=scene_copy,
        table_path=table_copy,
    )
    assert written == [scene_copy, table_copy]
    staged = scene_copy.read_text(encoding="utf-8")
    assert staged.index("R.crate = ") < staged.index(MARKER)
    table = table_copy.read_text(encoding="utf-8")
    line = '    item("crate", "Crate", "storage", "crate", True, aliases=("box",)),'
    assert table.count(line) == 1 and table.index(line) < table.index(recipes.TABLE_END)
    # the shipped files were not touched
    assert "R.crate = " not in recipes.SCENE.read_text(encoding="utf-8")
    assert 'item("crate"' not in recipes.TABLE.read_text(encoding="utf-8")
    # a second add of the same id is refused
    with pytest.raises(RecipeError, match="already has 'crate'"):
        add_recipe(
            CANDIDATE,
            item_id="crate",
            name="Crate",
            family="storage",
            scene_path=scene_copy,
            table_path=table_copy,
        )
    with pytest.raises(RecipeError, match="lower-case words"):
        add_recipe(
            CANDIDATE,
            item_id="Crate!",
            name="Crate",
            family="storage",
            scene_path=scene_copy,
            table_path=table_copy,
        )
    # the amended table imports and draws the new item flat, with the generic stand-in
    spec = importlib.util.spec_from_file_location("iso_icons_copy", table_copy)
    module = importlib.util.module_from_spec(spec)
    sys.modules["iso_icons_copy"] = module
    try:
        spec.loader.exec_module(module)
        entry = next(item for item in module.ITEMS if item.id == "crate")
        assert entry.recipe == "crate" and entry.args == (True,) and entry.aliases == ("box",)
        svg = module.draw(entry)
        assert svg.startswith("<svg") and svg.endswith("</svg>")
    finally:
        sys.modules.pop("iso_icons_copy", None)
