"""Every frame draws the badge somebody decided it should.

A frame's title tab carries a small piece of vendor artwork. Which piece is
decided by the frame's *kind* and the theme's ``boundaries.icons`` map, and
this file checks that map against a written record.

The rule: a frame's badge is the vendor's own artwork for that boundary, and
where the vendor ships none the frame takes the generic tab. An AWS account,
an Auto Scaling group and the corporate datacenter each draw the group box
the AWS deck ships for them, not the generic tab. And an Azure availability
zone never draws the Availability Sets mark, which is a different construct
-- a set spreads across fault domains inside one datacenter, a zone is a
separate datacenter -- so the picture would state something false.

``tests/fixtures/frame-badges.json`` records every badge and every blank with
its reason, and this file fails when a theme disagrees with it.
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

import pytest

import infragram.nodes.frames as frames_package
from infragram.builders.architecture import load_icon_set, load_style

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
RECORD = ROOT / "tests/fixtures/frame-badges.json"
VENDORS = ROOT / "plugin/skills/infragram-architect/assets/icons/vendors"


def _record() -> dict:
    return json.loads(RECORD.read_text(encoding="utf-8"))["libraries"]


def _theme_badges(group: str) -> dict[str, str]:
    provider = "onprem" if group == "generic" else group
    return dict(load_style(provider).cluster.icons or {})


def _kinds(group: str) -> set[str]:
    module = importlib.import_module(f"infragram.nodes.frames.{group}")
    return {
        cls.KIND
        for name in dir(module)
        if inspect.isclass(cls := getattr(module, name))
        and getattr(cls, "KIND", None)
        and getattr(cls, "FRAME_ID", None)
    }


def test_every_library_is_recorded() -> None:
    assert set(_record()) == set(frames_package.GROUPS)


@pytest.mark.parametrize("group", sorted(frames_package.GROUPS))
def test_the_record_covers_every_frame_kind(group: str) -> None:
    """Add a frame and this fails until its badge is decided either way."""
    entry = _record()[group]
    covered = set(entry.get("badges") or {}) | set(entry["blank"])
    assert covered == _kinds(group), sorted(covered ^ _kinds(group))


@pytest.mark.parametrize("group", sorted(frames_package.GROUPS))
def test_the_theme_matches_the_record(group: str) -> None:
    """The themes are what the renderers read; the record is the review."""
    assert _theme_badges(group) == dict(_record()[group].get("badges") or {})


@pytest.mark.parametrize("group", sorted(frames_package.GROUPS))
def test_every_blank_says_why(group: str) -> None:
    """A blank badge is a decision. An undecided one is a bug."""
    for kind, reason in _record()[group]["blank"].items():
        assert isinstance(reason, str) and len(reason) > 20, f"{group}.{kind}: {reason!r}"


@pytest.mark.parametrize("group", sorted(frames_package.GROUPS))
def test_every_badge_resolves_to_artwork_that_ships(group: str) -> None:
    """A reference that does not load leaves a frame silently unbranded."""
    for kind, reference in (_record()[group].get("badges") or {}).items():
        assert ":" in reference, f"{group}.{kind}: {reference}"
        collection, _, slug = reference.partition(":")
        pack = load_icon_set(collection)
        icon = pack[slug] if "#" in slug else pack.find(slug)
        assert icon.path.is_file(), f"{group}.{kind} -> {reference} has no file"


def test_aws_uses_every_group_box_that_names_a_frame() -> None:
    """The regression that started this: artwork in the tree, never wired up.

    AWS is the one deck that files artwork as a group, and each of those
    boxes is exactly a frame's badge. Any that names a frame must be used.
    """
    catalog = json.loads((VENDORS / "aws" / "catalog.json").read_text(encoding="utf-8"))
    group_art = {i["id"] for i in catalog["icons"] if (i.get("tier") or "service") == "group"}
    for expected in (
        "account",
        "auto-scaling-group",
        "corporate-data-center",
        "cloud-logo",
        "region",
        "private-subnet",
        "public-subnet",
        "virtual-private-cloud-vpc",
    ):
        assert expected in group_art, f"{expected} is no longer in the deck"
    # Every frame badge AWS declares is one of those group boxes, with one
    # recorded exception. Not the service icon of the same name -- the VPC
    # frame once wore "Amazon Virtual Private Cloud", a service, when
    # "Virtual private cloud VPC", the group box, was in the tree -- and not a
    # mark from a third-party logo pack. The exception is the organization:
    # the deck ships no group box for it, and AWS's own reference diagrams
    # draw that boundary with the Organizations service icon. An exception is
    # allowed only when the record names the kind and says why.
    aws = _record()["aws"]
    excepted = set(aws.get("exceptions") or {})
    for kind, reference in (aws.get("badges") or {}).items():
        assert reference.startswith("aws:"), f"{kind} borrows {reference} from outside the deck"
        slug = reference.partition(":")[2]
        assert slug in group_art or kind in excepted, (
            f"{kind} wears {reference}, a service icon, and no exception is recorded for it"
        )
    for kind, reason in (aws.get("exceptions") or {}).items():
        assert kind in (aws.get("badges") or {}), f"exception for {kind} but no badge"
        assert len(reason) > 40, f"exception for {kind} does not say why"
    assert excepted == {"organization"}, sorted(excepted)


def test_an_availability_zone_never_borrows_the_availability_set_mark() -> None:
    """The specific falsehood this file was written after finding."""
    for group in frames_package.GROUPS:
        badges = _record()[group].get("badges") or {}
        assert "availability-set" not in str(badges.get("zone", "")), group
