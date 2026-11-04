"""Group artwork is the box, never a node.

A vendor ships a third kind of drawing beside its services and its resource
glyphs: the box drawn *around* things. AWS files thirteen that way -- the
Region outline, the VPC outline, the two subnet outlines. Every one of them
also becomes a component class, and five of those class names collide exactly
with the frame that does the same job::

    nodes.aws.architecture_group.Region     draws a card
    nodes.frames.aws.Region                 contains things

Reach for the first and the diagram shows a card labelled "Region" that holds
nothing, which reads as a region while modelling none. Nothing stopped that
before this existed: no shipped template got it wrong, but nothing said it
was wrong either.

Detection is the vendor's own tier, so it cannot fall behind the artwork. The
frame to reach for instead is reviewed by hand, because pairing the two by
name automatically put the VPC glyph with the Cloud frame and every
on-premises ``network-*`` product with the Network frame -- a wrong pairing
being worse than none at all.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import pkgutil
from pathlib import Path

import pytest

from infragram.catalog import tiers
from infragram.nodes._base import Frame as BaseFrame

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
VENDORS = ROOT / "plugin/skills/infragram-architect/assets/icons/vendors"
TABLE = ROOT / "plugin/skills/infragram-architect/assets/catalog/container-artwork.json"


def _checker():
    spec = importlib.util.spec_from_file_location(
        "project_check", ROOT / "plugin/skills/infragram-architect/scripts/project_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _shipped_group_icons() -> dict[str, set[str]]:
    """provider -> every icon id the vendor's own catalog files as a group."""
    found: dict[str, set[str]] = {}
    for catalog in sorted(VENDORS.glob("*/catalog.json")):
        icons = json.loads(catalog.read_text(encoding="utf-8")).get("icons") or []
        ids = {str(i.get("id")) for i in icons if tiers.is_container(i)}
        if ids:
            found[catalog.parent.name] = ids
    return found


def test_the_table_covers_every_piece_of_group_artwork() -> None:
    """Import new artwork filed as a group and this fails until it is reviewed.

    That is the point: the table is written by hand, so the only thing keeping
    it honest is a test that reads the catalogs instead of trusting it.
    """
    shipped = _shipped_group_icons()
    assert shipped, "the AWS deck files thirteen icons as group artwork"
    table = json.loads(TABLE.read_text(encoding="utf-8"))["providers"]
    for provider, ids in shipped.items():
        listed = set(table.get(provider) or {})
        assert ids <= listed, f"{provider}: unreviewed group artwork {sorted(ids - listed)}"
        assert listed <= ids, f"{provider}: stale rows for {sorted(listed - ids)}"


def test_every_frame_the_table_names_is_a_frame_that_ships() -> None:
    """A pointer to a frame that does not exist is worse than no pointer."""
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    named = [
        row["frame"]
        for rows in table["providers"].values()
        for row in rows.values()
        if row.get("frame")
    ]
    assert len(named) == 8, "eight of the thirteen have a frame counterpart"

    def resolve(dotted: str) -> type:
        assert dotted.startswith("frames."), dotted
        _, group, cls = dotted.split(".", 2)
        module = importlib.import_module(f"infragram.nodes.frames.{group}")
        frame = getattr(module, cls, None)
        assert frame is not None, f"{dotted} names no frame"
        assert issubclass(frame, BaseFrame), f"{dotted} is not a frame"
        return frame

    for dotted in named:
        # A provider frame carries the id the editor draws it by.
        assert getattr(resolve(dotted), "FRAME_ID", ""), f"{dotted} carries no frame id"
    # The fallback is the untyped frame itself, which takes any label.
    assert resolve(table["fallback"]) is BaseFrame


def test_a_row_without_a_frame_says_what_to_draw_instead() -> None:
    """Five of the thirteen have no counterpart, so they carry the reason."""
    table = json.loads(TABLE.read_text(encoding="utf-8"))["providers"]
    bare = [(p, i) for p, rows in table.items() for i, row in rows.items() if not row.get("frame")]
    assert bare, "some group boxes have no frame; they must still advise"
    for provider, icon_id in bare:
        advice = tiers.container_advice(provider, icon_id)
        assert advice.startswith("No frame ships for it: "), advice
        assert len(advice) > 30, f"{icon_id} advises nothing useful"


def test_every_generated_class_warns_where_a_caller_meets_it() -> None:
    """The docstring is where the choice is made, so it carries the warning."""
    shipped = _shipped_group_icons()
    seen = 0
    for provider, ids in shipped.items():
        package = importlib.import_module(f"infragram.nodes.{provider}")
        for info in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(f"infragram.nodes.{provider}.{info.name}")
            for name in dir(module):
                cls = getattr(module, name)
                if not isinstance(getattr(cls, "ICON", None), str) or cls.ICON not in ids:
                    continue
                seen += 1
                doc = cls.__doc__ or ""
                assert "Group artwork" in doc, f"{info.name}.{name} does not warn"
                assert "contains nothing" in doc, f"{info.name}.{name} does not say why"
                assert "To contain, use ``frames." in doc or "No frame ships for it:" in doc, (
                    f"{info.name}.{name} advises nothing"
                )
    assert seen >= 13, f"only {seen} group classes were examined"


@pytest.mark.parametrize(
    "icon_id,frame",
    [
        ("virtual-private-cloud-vpc", "frames.aws.VPC"),
        ("region", "frames.aws.Region"),
        ("private-subnet", "frames.aws.PrivateSubnet"),
    ],
)
def test_the_checker_refuses_a_group_box_drawn_as_a_node(icon_id: str, frame: str) -> None:
    """A document that draws one is reported, and told which frame to use."""
    checker = _checker()
    document = {
        "topology": {
            "id": "root",
            "name": "Root",
            "type": "group",
            "children": [
                {
                    "id": "a",
                    "name": "Boundary",
                    "type": "service",
                    "component": {"provider": "aws", "service_id": icon_id},
                },
            ],
        }
    }
    errors: list[str] = []
    checker.check_components(document, errors)
    assert len(errors) == 1, errors
    assert icon_id in errors[0] and frame in errors[0]
    assert "contains nothing" in errors[0]


def test_the_checker_leaves_an_ordinary_service_alone() -> None:
    """The rule must not fire on the services a real diagram is made of."""
    checker = _checker()
    document = {
        "topology": {
            "id": "root",
            "name": "Root",
            "type": "group",
            "children": [
                {
                    "id": "a",
                    "name": "Web",
                    "type": "service",
                    "component": {"provider": "aws", "service_id": "ec2"},
                },
                {
                    "id": "b",
                    "name": "Database",
                    "type": "service",
                    "component": {"provider": "aws", "service_id": "rds"},
                },
            ],
        }
    }
    errors: list[str] = []
    assert checker.check_components(document, errors) == 2
    assert errors == []


def test_no_shipped_template_draws_a_group_box_as_a_node() -> None:
    """What the rule protects, checked against everything we ship."""
    checker = _checker()
    templates = sorted(
        (ROOT / "plugin/skills/infragram-architect/assets/templates").rglob("*.infragram.json")
    )
    assert len(templates) >= 30
    for path in templates:
        errors: list[str] = []
        checker.check_components(json.loads(path.read_text(encoding="utf-8")), errors)
        assert errors == [], f"{path.name}: {errors}"
