"""An icon that names a frame's job points at the frame.

Only AWS files artwork as a group box. Every other vendor draws its
containment concepts as ordinary service icons: Azure ships "Virtual
Networks", IBM ships "VPC", Oracle ships "VCN", DigitalOcean ships a VPC and
a Kubernetes cluster. Those are genuine icons, and placing one is not an
error -- an inventory diagram may want exactly that drawing.

But an icon contains nothing. So when the intent is containment, each of
these says which frame does the job, and the checker stays out of it. That
difference is the point of this file: group artwork is refused, a counterpart
is only pointed at.

Recall comes from ``candidate_frames`` below, which matches exact words and
initials of three letters or more. Everything it finds must be reviewed into
the table; the table may go further, where an abbreviation defeats matching.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import pkgutil
import re
from functools import lru_cache
from pathlib import Path

import pytest

import infragram.nodes.frames as frames_package
from infragram.catalog import tiers
from infragram.paths import skill_assets

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
VENDORS = ROOT / "plugin/skills/infragram-architect/assets/icons/vendors"


# ------------------------------------------------ the recall matcher
# Exact words and initials of three letters or more; anything it finds must
# be reviewed into the container table. It lives here because the table is
# what ships; the matcher only guards it.


#: Vendor words that appear in icon names but in no provider record.
VENDOR_ALIASES = {
    "aws": ("amazon web services", "amazon"),
    "azure": ("microsoft",),
    "alibaba": ("aliyun",),
    "akamai": ("linode",),
}


@lru_cache(maxsize=1)
def _provider_phrases() -> dict[str, tuple[str, ...]]:
    """Provider -> the names of itself, longest first, from the catalog."""
    path = skill_assets() / "catalog" / "providers.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    phrases: dict[str, tuple[str, ...]] = {}
    for record in catalog.get("providers") or []:
        provider = str(record.get("id") or "")
        names = {
            provider,
            str(record.get("display_name") or ""),
            str(record.get("short_name") or ""),
        }
        names.update(VENDOR_ALIASES.get(provider, ()))
        cleaned = {n.strip().lower() for n in names if n and n.strip()}
        phrases[provider] = tuple(sorted(cleaned, key=len, reverse=True))
    return phrases


_WORD = re.compile(r"[^a-z0-9]+")


def _words(text: str, provider: str = "", strip_vendor: bool = True) -> list[str]:
    """Lowercase words, the provider's own name removed, plurals folded.

    "IBM Cloud subnet" and "Subnet" have to meet in the middle, so the
    provider's names come out whole -- dropping "cloud" on its own would
    also gut "Virtual Private Cloud", which is the thing being matched.
    """
    lowered = str(text).lower()
    if strip_vendor:
        for phrase in _provider_phrases().get(provider, ()):
            lowered = re.sub(r"\b" + re.escape(phrase) + r"\b", " ", lowered)
    words = []
    for word in _WORD.split(lowered):
        if word:
            words.append(word[:-1] if len(word) > 3 and word.endswith("s") else word)
    return words


#: Shortest abbreviation trusted to mean one thing. Two letters do not: "sg"
#: is Security Group and also Storage Gateway and also SDK General, and every
#: one of those paired wrongly before this floor existed.
ACRONYM_FLOOR = 3


def _acronym(words: list[str]) -> str:
    """ "virtual private cloud" -> "vpc"; too short or too few words, nothing."""
    if len(words) < 2:
        return ""
    initials = "".join(w[0] for w in words)
    return initials if len(initials) >= ACRONYM_FLOOR else ""


def candidate_frames(provider: str, icons: list[dict], frames: list[dict]) -> dict[str, list[str]]:
    """Icons that name a frame of the same library, by icon id.

    Two matches, both exact rather than approximate: the icon's words equal
    the frame's label or kind, or one side's initials spell the other. That
    is what pairs "VCN" with "OCI virtual cloud network". Group artwork is
    left out, the container table already covers it.

    The answer is a list because a library can hold two frames of one kind --
    Google Cloud has a VPC and a Shared VPC -- so which one is right is a
    judgement the reviewed table makes, not this function.
    """
    found: dict[str, list[str]] = {}
    for icon in icons:
        if tiers.is_container(icon):
            continue
        words = _words(icon.get("name") or "", provider)
        if not words:
            continue
        name, initials = frozenset(words), _acronym(words)
        for frame in frames:
            label = _words(frame.get("label") or "", provider)
            kind = _words(frame.get("kind") or "", strip_vendor=False)
            if (
                name in (frozenset(label), frozenset(kind))
                or (initials and initials in ("".join(kind), _acronym(label)))
                or (
                    len(words) == 1
                    and len(words[0]) >= ACRONYM_FLOOR
                    and words[0] == _acronym(label)
                )
            ):
                found.setdefault(str(icon.get("id") or ""), []).append(str(frame["cls"]))
    return found


def counterpart_ids(provider: str) -> set[str]:
    """Every icon of a provider that has a frame doing the same job."""
    return set((tiers.container_artwork().get("frame_counterparts") or {}).get(provider, {}))


def _frames(group: str) -> list[dict]:
    module = importlib.import_module(f"infragram.nodes.frames.{group}")
    found = []
    for name in dir(module):
        cls = getattr(module, name)
        if inspect.isclass(cls) and getattr(cls, "KIND", None) and getattr(cls, "FRAME_ID", None):
            found.append({"cls": name, "kind": cls.KIND, "label": cls.LABEL})
    return found


def _icons(provider: str) -> list[dict]:
    catalog = VENDORS / provider / "catalog.json"
    if not catalog.is_file():
        return []
    return json.loads(catalog.read_text(encoding="utf-8")).get("icons") or []


def _providers() -> list[str]:
    return [
        c.parent.name
        for c in sorted(VENDORS.glob("*/catalog.json"))
        if c.parent.name in frames_package.GROUPS
    ]


def test_the_table_reaches_beyond_aws() -> None:
    """The whole point: every library with a counterpart, not just one."""
    covered = {p for p in _providers() if counterpart_ids(p)}
    assert len(covered) >= 9, f"only {sorted(covered)} are covered"
    assert {"azure", "gcp", "ibm", "oracle", "alibaba", "digitalocean"} <= covered


def test_every_candidate_the_rule_finds_has_been_reviewed() -> None:
    """Import artwork that names a frame and this fails until someone looks.

    The rule supplies recall; a person supplies the judgement. Neither is
    trusted alone, which is why the derived set is checked against the table
    rather than used as the table.
    """
    unreviewed = []
    for provider in _providers():
        candidates = candidate_frames(provider, _icons(provider), _frames(provider))
        listed = counterpart_ids(provider)
        unreviewed += [f"{provider}:{i}" for i in sorted(set(candidates) - listed)]
    assert unreviewed == [], unreviewed


def test_every_row_names_an_icon_that_ships() -> None:
    """A pointer hung on an icon that no longer exists helps nobody."""
    for provider in _providers():
        shipped = {str(i.get("id")) for i in _icons(provider)}
        for icon_id in sorted(counterpart_ids(provider)):
            assert icon_id in shipped, f"{provider}:{icon_id} is not in the catalog"


def test_every_row_names_a_frame_that_ships() -> None:
    for provider in _providers():
        for icon_id in sorted(counterpart_ids(provider)):
            dotted = tiers.frame_counterpart(provider, icon_id)
            assert dotted and dotted.startswith("frames."), f"{provider}:{icon_id} -> {dotted}"
            _, group, cls = dotted.split(".", 2)
            module = importlib.import_module(f"infragram.nodes.frames.{group}")
            frame = getattr(module, cls, None)
            assert frame is not None, f"{dotted} names no frame"
            assert getattr(frame, "FRAME_ID", ""), f"{dotted} is not a frame"


def test_the_ambiguous_pair_resolved_to_the_plain_vpc() -> None:
    """Google Cloud has two frames of kind vpc, so the rule cannot choose.

    Left to itself it offered Shared VPC first, which is a different
    arrangement entirely. The table is what stops that being shipped.
    """
    candidates = candidate_frames("gcp", _icons("gcp"), _frames("gcp"))
    assert sorted(candidates["virtual-private-cloud"]) == ["SharedVPC", "VPC"]
    assert tiers.frame_counterpart("gcp", "virtual-private-cloud") == "frames.gcp.VPC"


def test_every_counterpart_class_carries_the_pointer() -> None:
    """The docstring is where a caller meets the icon, so it points."""
    seen = 0
    for provider in _providers():
        ids = counterpart_ids(provider)
        if not ids:
            continue
        reached = set()
        package = importlib.import_module(f"infragram.nodes.{provider}")
        for info in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(f"infragram.nodes.{provider}.{info.name}")
            for name in dir(module):
                cls = getattr(module, name)
                if not isinstance(getattr(cls, "ICON", None), str) or cls.ICON not in ids:
                    continue
                reached.add(cls.ICON)
                seen += 1
                doc = cls.__doc__ or ""
                assert "also ships as a frame" in doc, f"{provider}.{info.name}.{name}"
                assert "frames." in doc, f"{provider}.{info.name}.{name} names no frame"
        assert reached == ids, f"{provider}: no class carries {sorted(ids - reached)}"
    assert seen >= 28


@pytest.mark.parametrize(
    "provider,icon_id",
    [
        ("azure", "virtual-networks"),
        ("ibm", "network-vpc"),
        ("oracle", "network-vcn"),
        ("gcp", "virtual-private-cloud"),
    ],
)
def test_the_checker_allows_a_counterpart(provider: str, icon_id: str) -> None:
    """A pointer is not a refusal. These icons are real and may be placed."""
    spec = importlib.util.spec_from_file_location(
        "project_check", ROOT / "plugin/skills/infragram-architect/scripts/project_check.py"
    )
    checker = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(checker)
    document = {
        "topology": {
            "id": "root",
            "name": "Root",
            "type": "group",
            "children": [
                {
                    "id": "a",
                    "name": "Network",
                    "type": "service",
                    "component": {"provider": provider, "service_id": icon_id},
                },
            ],
        }
    }
    errors: list[str] = []
    assert checker.check_components(document, errors) == 1
    assert errors == [], errors


def test_a_two_letter_abbreviation_is_never_trusted() -> None:
    """ "sg" is Security Group, Storage Gateway and SDK General at once.

    Every one of those paired wrongly before the floor existed, so the floor
    is asserted rather than left to be re-learned.
    """
    assert ACRONYM_FLOOR >= 3
    candidates = candidate_frames("aws", _icons("aws"), _frames("aws"))
    for junk in ("general-sdk", "storage-gateway", "professional-services"):
        assert junk not in candidates, f"{junk} matched on initials again"
