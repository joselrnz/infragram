"""The component inventory accounts for everything the libraries ship and stays current."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from infragram.paths import skill_assets

ROOT = Path(__file__).parents[2]
BUILDER = ROOT / "scripts" / "inventory" / "build.py"


@pytest.fixture(scope="module")
def inventory_module():
    spec = importlib.util.spec_from_file_location("inventory_build", BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built(inventory_module):
    inventory, problems = inventory_module.build_inventory()
    return inventory, problems


def test_every_component_has_decodable_artwork(built) -> None:
    _inventory, problems = built
    assert problems == []


def test_inventory_covers_every_library_and_its_frames(built) -> None:
    inventory, _ = built
    providers = json.loads(
        (ROOT / "plugin/skills/infragram-architect/assets/catalog/providers.json").read_text(
            encoding="utf-8"
        )
    )["providers"]

    assert [library["id"] for library in inventory["libraries"]] == [p["id"] for p in providers]
    assert inventory["totals"]["libraries"] == len(providers)
    # every library has frames and a starter stack; full libraries carry
    # hundreds of icons
    assert all(library["frames"] for library in inventory["libraries"])
    assert all(library["starter_stack"] for library in inventory["libraries"])
    by_id = {library["id"]: library for library in inventory["libraries"]}
    assert by_id["aws"]["icons"] >= 300 and by_id["azure"]["icons"] >= 700
    assert by_id["onprem"]["kind"] == "on-prem" and by_id["onprem"]["icons"] >= 190
    assert by_id["vmware"]["icons"] >= 20 and by_id["vmware"]["frames"]
    assert by_id["cloudflare"]["icons"] >= 4
    assert {library["coverage"] for library in inventory["libraries"]} <= {"full", "reviewed"}
    assert inventory["totals"]["frames"] == len(inventory["core_frames"]) + sum(
        len(library["frames"]) for library in inventory["libraries"]
    )
    assert inventory["totals"]["templates"] == len(
        list(
            (ROOT / "plugin/skills/infragram-architect/assets/templates/cloud").glob(
                "*.infragram.json"
            )
        )
    )


def test_committed_inventory_is_current(inventory_module, built) -> None:
    inventory, _ = built
    assert inventory_module.check(inventory) == []


def test_docs_page_shows_a_picture_of_every_library(inventory_module, built) -> None:
    inventory, _ = built
    page = inventory_module.render_docs_markdown(inventory)
    images = set(inventory_module.referenced_images(page))

    assert (
        "frames-tabs.png" in images
        and "icons-shared.png" in images
        and "frames-generic.png" in images
    )
    for library in inventory["libraries"]:
        assert f"icons-{library['id']}.png" in images, library["id"]
        if library["frames"]:
            assert f"frames-{library['id']}.png" in images, library["id"]
    # the pictures the page embeds exist in the docs folder
    docs = ROOT / "docs" / "inventory"
    missing = sorted(image for image in images if not (docs / image).exists())
    assert missing == []


def test_check_reports_a_stale_inventory(inventory_module, built, tmp_path: Path) -> None:
    inventory, _ = built
    stale = json.loads(json.dumps(inventory))
    stale["libraries"][0]["components"].pop()
    stale["libraries"][0]["icons"] -= 1
    stale["totals"]["vendor_icons"] -= 1
    json_path = tmp_path / "inventory.json"
    json_path.write_text(json.dumps(stale), encoding="utf-8")
    markdown_path = tmp_path / "inventory.md"
    markdown_path.write_text(inventory_module.render_markdown(inventory), encoding="utf-8")

    errors = inventory_module.check(inventory, json_path, markdown_path)

    assert any("out of date" in error for error in errors)
    assert any(inventory["libraries"][0]["id"] in error for error in errors)


def test_the_onprem_reference_counts_what_the_library_ships(built) -> None:
    """The prose of references/providers/onprem.md: its counts, and every
    neutral operational component by name, as the inventory has them."""
    inventory, _ = built
    text = " ".join(
        (ROOT / "plugin/skills/infragram-architect/references/providers/onprem.md")
        .read_text(encoding="utf-8")
        .split()
    )
    library = next(entry for entry in inventory["libraries"] if entry["id"] == "onprem")
    catalog = json.loads(
        (
            ROOT / "plugin/skills/infragram-architect/assets/icons/vendors/onprem/catalog.json"
        ).read_text(encoding="utf-8")
    )
    categories = [icon["category"] for icon in catalog["icons"]]
    sets = {
        name: sum(c.startswith(f"{name}-") for c in categories)
        for name in ("generic", "elastic", "iso")
    }
    onprem = len(categories) - sum(sets.values())
    assert f"**{onprem + sets['generic'] + sets['elastic']} product icons**" in text
    assert (
        f"`diagrams.onprem` catalog ({onprem} icons) across "
        f"{len({c for c in categories if not c.startswith(('generic-', 'elastic-', 'iso-'))})} source categories"
        in text
    )
    assert f"`diagrams.generic` set ({sets['generic']} icons)" in text
    assert f"`diagrams.elastic` set ({sets['elastic']} icons)" in text
    assert f"**{sets['iso']} rendered 3D models**" in text
    icons = {icon["id"] for icon in catalog["icons"]}
    neutral = [
        component["name"] for component in library["components"] if component["id"] not in icons
    ]
    assert f"**{len(neutral)} neutral operational components**" in text
    named = text.split("neutral operational components** (", 1)[1].split("):", 1)[0].lower()
    assert sorted(named.split(", ")) == sorted(name.lower() for name in neutral)


INVENTORY = json.loads((skill_assets() / "catalog" / "inventory.json").read_text("utf-8"))


def test_the_readme_counts_are_the_inventorys() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    totals = INVENTORY["totals"]
    found = re.search(r"(\d+) libraries, ([\d,]+) icons", readme)
    assert found and (int(found[1]), int(found[2].replace(",", ""))) == (
        totals["libraries"],
        totals["vendor_icons"],
    )
    usage = (ROOT / "docs/usage.md").read_text(encoding="utf-8")
    found = re.search(r"(\d+) frames in\s+(\d+) groups", usage)
    assert found and (int(found[1]), int(found[2])) == (totals["frames"], totals["frame_groups"])
    azure = next(item for item in INVENTORY["libraries"] if item.get("id") == "azure")
    count = azure.get("icons") or azure.get("count")
    assert f"Azure ({count})" in usage
    page = skill_assets().parent / "references" / "providers" / "azure.md"
    assert f"{count} icons" in page.read_text(encoding="utf-8")
