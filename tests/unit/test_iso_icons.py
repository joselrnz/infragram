"""The isometric on-prem set is generated, installed and measured.

``scripts/build/iso-icons.py`` draws every icon from its table; ``--install``
writes them into the Local & On-Premises collection. The two must agree, so
a change to the table or a recipe without a reinstall fails here, and every
installed icon must be one the renderers can seat a link on.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from infragram.catalog import ink

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
COLLECTION = ROOT / "plugin/skills/infragram-architect/assets/icons/vendors/onprem"


def _generator():
    spec = importlib.util.spec_from_file_location("iso_icons", ROOT / "scripts/build/iso-icons.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Registered before it runs: its dataclasses resolve their annotations
    # through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _installed() -> dict[str, dict]:
    catalog = json.loads((COLLECTION / "catalog.json").read_text(encoding="utf-8"))
    return {
        entry["id"]: entry for entry in catalog["icons"] if entry["category"].startswith("iso-")
    }


def test_the_set_is_over_a_hundred_items_in_every_family() -> None:
    generator = _generator()
    assert len(generator.ITEMS) >= 150
    assert {entry.family for entry in generator.ITEMS} == set(generator.FAMILIES)
    assert len({entry.id for entry in generator.ITEMS}) == len(generator.ITEMS), "ids are unique"


def _renderer():
    spec = importlib.util.spec_from_file_location(
        "iso_render", ROOT / "scripts/build/iso-render.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_every_item_is_installed_from_its_current_render_spec() -> None:
    """The catalog records the hash of each item's render spec -- its line in
    the table plus the three.js builder -- and the hash of the installed
    file. Change the table or scene.js without reinstalling, or touch an
    installed file by hand, and this is the test that says so."""
    generator, renderer = _generator(), _renderer()
    installed = _installed()
    for entry in generator.ITEMS:
        slug = f"iso-{entry.id}"
        assert slug in installed, f"{slug} is in the table but not installed"
        record = installed[slug]
        assert record["source_sha256"] == renderer.spec_hash(generator, entry), (
            f"{slug}: the render spec changed since it was installed"
        )
        data = (COLLECTION / record["file"]).read_bytes()
        assert record["sha256"] == hashlib.sha256(data).hexdigest(), (
            f"{slug}: the installed file differs from its record"
        )
        assert b"data:image/png;base64," in data, f"{slug} is not a wrapped render"
        assert record["category"] == f"iso-{entry.family}"
    assert set(installed) == {f"iso-{entry.id}" for entry in generator.ITEMS}, (
        "nothing installed that is not in the table"
    )


def test_the_flat_kit_still_draws_every_item() -> None:
    """The flat isometric drawing stays as the table's fallback and the
    recipes' reference: every item must still draw to a valid SVG."""
    generator = _generator()
    for entry in generator.ITEMS:
        svg = generator.draw(entry)
        assert svg.startswith("<svg") and svg.endswith("</svg>"), entry.id


def test_every_installed_icon_is_measured_and_seatable() -> None:
    """Every icon keeps air in its square and has edge lines, so a link on
    any side is seated on the drawing."""
    for slug, record in _installed().items():
        data = (COLLECTION / record["file"]).read_bytes()
        assert ink.profile(data) is not None, (
            f"{slug} has no ink profile; run scripts/tools/ink-profiles.py"
        )
        code = ink.edges(data)
        assert code is not None, f"{slug} has no edge lines"
        for side in ("left", "right", "top"):
            assert ink.usable_middle(code, side) is not None, f"{slug}: no seat on its {side}"


def test_custom_servers_come_in_the_shapes_the_helper_offers() -> None:
    """``custom_server(units=, bays=, family=)`` resolves to a generated class,
    so the helper's shapes and the table's grid must be the same set."""
    from infragram.nodes import custom

    generator = _generator()
    assert (
        tuple((units, bays) for units, bays, _, _ in generator.CUSTOM_SERVER_SHAPES)
        == custom.CUSTOM_SERVER_SHAPES
    )
    assert tuple(generator.FAMILIES) == custom.FAMILIES
    node = custom.custom_server("Build", "2U", units=2, bays=8, family="platform")
    assert type(node).__name__ == "IsoCustomServerPlatform2u8"
    for units, bays in custom.CUSTOM_SERVER_SHAPES:
        for family in custom.FAMILIES:
            custom.custom_server("x", units=units, bays=bays, family=family)


def test_the_families_reach_the_sidebar_under_canonical_categories() -> None:
    generator = _generator()
    mapping = json.loads(
        (
            ROOT / "plugin/skills/infragram-architect/assets/catalog/provider-category-map.json"
        ).read_text(encoding="utf-8")
    )
    native = mapping["providers"]["onprem"]["native_categories"]
    for family, canonical in generator.SIDEBAR_CATEGORY.items():
        assert native[f"iso-{family}"] == canonical
