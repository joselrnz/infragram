"""The AWS library carries the deck's resource tier, not only its services.

AWS draws a service as a coloured tile and the things inside a service -- a
NAT gateway, an internet gateway, a VPC endpoint, an EC2 instance -- as line
glyphs. Both tiers ship in one official package, and both are imported by the
same importer, so a VPC diagram never has to borrow a neutral stand-in for a
thing AWS has a picture of.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from infragram.catalog import load_provider_component_catalog

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
AWS = ROOT / "plugin/skills/infragram-architect/assets/icons/vendors/aws"
CATALOG = json.loads((AWS / "catalog.json").read_text(encoding="utf-8"))
ICONS = {icon["id"]: icon for icon in CATALOG["icons"]}


@pytest.mark.parametrize(
    "icon_id, name",
    [
        ("vpc-nat-gateway", "NAT Gateway (Amazon VPC)"),
        ("vpc-internet-gateway", "Internet Gateway (Amazon VPC)"),
        ("vpc-endpoints", "Endpoints (Amazon VPC)"),
        ("vpc-router", "Router (Amazon VPC)"),
        ("ec2-instance", "Instance (Amazon EC2)"),
        (
            "elastic-load-balancing-application-load-balancer",
            "Application Load Balancer (Elastic Load Balancing)",
        ),
    ],
)
def test_the_vpc_resources_a_diagram_needs_are_real_icons(icon_id: str, name: str) -> None:
    icon = ICONS[icon_id]
    assert icon["name"] == name
    assert icon["tier"] == "resource"
    assert (AWS / icon["file"]).is_file()
    assert "Resource-Icons_" in icon["source_path"]


@pytest.mark.parametrize(
    "icon_id, name",
    [
        ("general-users", "Users (General)"),
        ("general-client", "Client (General)"),
        ("general-mobile-client", "Mobile client (General)"),
        ("general-internet", "Internet (General)"),
        ("general-servers", "Servers (General)"),
        ("general-office-building", "Office building (General)"),
    ],
)
def test_the_decks_general_icons_are_resources_drawn_from_the_light_variant(
    icon_id: str, name: str
) -> None:
    icon = ICONS[icon_id]
    assert icon["name"] == name
    assert icon["tier"] == "resource"
    assert icon["category"] == "general-icons"
    assert icon["source_path"].endswith("_48_Light.svg")
    assert (AWS / icon["file"]).is_file()


def test_no_dark_general_icon_was_imported() -> None:
    # The general icons ship as Light and Dark files; only the drawing on
    # paper comes in. (The service tier's own "_Dark" variants predate this.)
    dark = [
        icon["id"]
        for icon in CATALOG["icons"]
        if icon.get("tier") == "resource" and "_Dark" in icon.get("source_path", "")
    ]
    assert not dark


def test_the_group_shapes_the_theme_tabs_use_are_still_here() -> None:
    for icon_id in ("region", "public-subnet", "private-subnet"):
        icon = ICONS[icon_id]
        assert icon["category"] == "architecture-group"
        assert icon["tier"] == "group"
        assert "Architecture-Group-Icons_" in icon["source_path"]


def test_ids_are_unique_and_a_resource_never_steals_a_services_id() -> None:
    ids = [icon["id"] for icon in CATALOG["icons"]]
    assert len(ids) == len(set(ids))
    # the one true collision in the deck takes the suffix, the service keeps the bare id
    assert (
        ICONS["ec2-auto-scaling"]["tier"] is None if "tier" in ICONS["ec2-auto-scaling"] else True
    )
    assert ICONS["ec2-auto-scaling-resource"]["tier"] == "resource"


def test_every_resource_icon_is_a_safe_measurable_svg() -> None:
    resources = [icon for icon in CATALOG["icons"] if icon.get("tier") == "resource"]
    assert len(resources) >= 400, "the deck's resource tier is a few hundred glyphs"
    for icon in resources:
        text = (AWS / icon["file"]).read_text(encoding="utf-8")
        assert 'viewBox="0 0 48 48"' in text, icon["id"]
        assert not re.search(r"<script|onload=|javascript:|<foreignObject", text, re.I), icon["id"]


def test_the_component_catalog_exposes_the_resource_tier() -> None:
    catalog = load_provider_component_catalog("aws")
    ids = {component.service_id for component in catalog.components}
    assert {"vpc-nat-gateway", "vpc-internet-gateway", "vpc-endpoints", "ec2-instance"} <= ids


def test_the_tiers_are_counted_together() -> None:
    assert CATALOG["counts"]["icons"] == len(CATALOG["icons"]) >= 700
