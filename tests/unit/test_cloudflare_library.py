"""Cloudflare is a full library: four product marks beside 33 drawn tiles.

The sidebar, the node generator and the inventory must all route Cloudflare
through the merged library, not a four-mark special case; otherwise
``infragram check`` refuses ``cloudflare:d1`` and the node package exposes
four categories. These tests pin the merged library on every path: the
reference lists what the checker knows, the node package covers every
category, and a tile composes and passes the shipped checker.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from infragram.author import Diagram, Edge
from infragram.catalog import CLOUDFLARE_COMPONENT_SPECS, load_provider_component_catalog
from infragram.compose import export
from infragram.editor import load_sidebar_catalog
from infragram.nodes import _scope, cloudflare as cf, reset_ids
from infragram.nodes.cloudflare import compute, databases, security, web
from infragram.paths import skill_assets, skill_references

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
REFERENCE = skill_references() / "providers" / "cloudflare.md"
INVENTORY = skill_assets() / "catalog" / "inventory.json"
MARKS = {"cloudflare", "workers", "pages", "workers-ai"}


@pytest.fixture(autouse=True)
def _clean_scopes():
    _scope.reset()
    reset_ids()
    yield
    _scope.reset()


def _checker():
    spec = importlib.util.spec_from_file_location(
        "project_check", ROOT / "plugin/skills/infragram-architect/scripts/project_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _reference_ids() -> set[str]:
    return set(re.findall(r"`cloudflare:([a-z0-9-]+)`", REFERENCE.read_text(encoding="utf-8")))


def _inventory_ids() -> set[str]:
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    library = next(item for item in data["libraries"] if item["id"] == "cloudflare")
    return {component["id"] for component in library["components"]}


def test_every_id_the_reference_lists_is_one_the_checker_knows() -> None:
    known = _checker().known_components()
    assert known is not None
    listed = _reference_ids()
    assert len(listed) == 37
    assert {f"cloudflare:{item}" for item in listed} <= known


def test_the_reference_and_the_inventory_agree_on_the_library() -> None:
    assert _inventory_ids() == _reference_ids()
    assert _inventory_ids() >= MARKS


def test_the_reference_has_one_frames_section_that_lists_the_frames() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    assert text.count("\n## Frames\n") == 1
    assert "has no frames" not in text
    for frame in ("Cloudflare account", "Cloudflare zone", "Cloudflare global network"):
        assert frame in text


def test_the_python_catalog_and_the_sidebar_offer_the_same_37() -> None:
    catalog = {c.service_id for c in load_provider_component_catalog("cloudflare").components}
    sidebar = {
        component.id
        for category in load_sidebar_catalog("cloudflare").categories
        for component in category.components
        if component.provider_id == "cloudflare"
    }
    assert catalog == sidebar == _inventory_ids()
    assert len(catalog) == 37
    # the marks are the vendor's artwork; a tile must not have taken an id
    tiles = json.loads(
        (skill_assets() / "icons" / "vendors" / "cloudflare" / "catalog.json").read_text(
            encoding="utf-8"
        )
    )
    assert {spec.service_id for spec in CLOUDFLARE_COMPONENT_SPECS} == MARKS
    assert MARKS.isdisjoint({icon["id"] for icon in tiles["icons"]})


def test_the_node_package_exposes_every_category_with_the_marks_inside() -> None:
    assert cf.CATEGORIES == (
        "ai_machine_learning",
        "analytics",
        "compute",
        "databases",
        "integration",
        "networking",
        "security",
        "storage",
        "web",
    )
    assert security.WAF.ICON == "waf" and security.WAF.COLLECTION == "cloudflare"
    assert databases.D1.ICON == "d1"
    assert compute.Workers.ICON == "workers"
    assert web.Pages.ICON == "pages"
    assert cf.WorkersAI.ICON == "workers-ai"
    assert cf.Cloudflare.ICON == "cloudflare"
    icons = {
        getattr(getattr(cf, category), name).ICON
        for category in cf.CATEGORIES
        for name in getattr(cf, category).__all__
    }
    assert icons == _inventory_ids()


def test_a_tile_composes_and_passes_the_shipped_checker(tmp_path: Path) -> None:
    with Diagram("Cloudflare WAF in front of D1") as diagram:
        waf = security.WAF("Edge WAF", "managed ruleset")
        d1 = databases.D1("App database", "D1 SQLite")
        waf >> Edge("HTTPS") >> d1
    result = export(diagram.to_project(), tmp_path, formats=("template", "html", "svg"))
    assert result.template is not None and result.svg is not None
    document = json.loads(result.template.read_text(encoding="utf-8"))
    placed = {
        element["component"]["service_id"]
        for element in document["topology"]["children"]
        if element.get("component")
    }
    assert placed == {"waf", "d1"}
    checker = _checker()
    assert checker.main([str(result.template), str(result.svg)]) == 0
