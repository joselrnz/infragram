"""A resource glyph says which service it belongs to.

The vendor ships two kinds of artwork. A service icon stands for the service;
a resource glyph is the drawing placed inside that service's group box. Their
classes sit side by side in the same module and read alike -- ``RDSMultiAz``
next to ``RDS``, ``ElasticacheElasticacheForRedis`` next to ``Elasticache`` --
and picking the wrong one produces a diagram that looks plausible and is
wrong. It happened, in two diagrams, before this existed.

So every resource glyph whose service also ships names that service in its
docstring, and says to use it instead.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from infragram.catalog import tiers

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
VENDORS = ROOT / "plugin/skills/infragram-architect/assets/icons/vendors"


def _resource_pairs(icons: list[dict]) -> dict[str, str]:
    """Resource id -> service id, for every pair a caller could confuse."""
    services = tiers.service_names(icons)
    pairs = {}
    for entry in icons:
        service = tiers.parent_service(entry, services)
        if service is not None:
            pairs[str(entry.get("id") or "")] = str(service.get("id") or "")
    return pairs


def _pairs() -> list[tuple[str, str, str]]:
    """(provider, resource id, service id) for every confusable pair, asked of
    the one module that owns the rule."""
    found = []
    for catalog in sorted(VENDORS.glob("*/catalog.json")):
        icons = json.loads(catalog.read_text(encoding="utf-8")).get("icons") or []
        for resource, service in _resource_pairs(icons).items():
            found.append((catalog.parent.name, resource, service))
    return found


def test_the_confusable_pairs_are_a_known_quantity() -> None:
    """If this number moves, artwork was imported and the pairs changed."""
    pairs = _pairs()
    assert len(pairs) > 250, "the AWS deck ships hundreds of resource glyphs"
    assert {p[0] for p in pairs} == {"aws"}, "only AWS files artwork this way today"


@pytest.mark.parametrize(
    "resource_id",
    [
        "rds-multi-az",
        "elasticache-elasticache-for-redis",
        "emr-cluster",
    ],
)
def test_a_resource_glyph_points_at_its_service(resource_id: str) -> None:
    from infragram.builders.architecture import load_icon_set

    icon = load_icon_set("aws").find(resource_id)
    assert icon.tier == "resource"


def test_every_generated_resource_class_names_its_service() -> None:
    """The docstring is where a caller meets the choice, so it carries it."""
    import pkgutil

    import infragram.nodes.aws as aws

    checked, missing = 0, []
    known = {p[1] for p in _pairs()}
    for module_info in pkgutil.iter_modules(aws.__path__):
        module = importlib.import_module(f"infragram.nodes.aws.{module_info.name}")
        for name in dir(module):
            cls = getattr(module, name)
            icon = getattr(cls, "ICON", None)
            if not isinstance(icon, str) or icon not in known:
                continue
            checked += 1
            doc = cls.__doc__ or ""
            if "Resource glyph" not in doc or "For the service use" not in doc:
                missing.append(f"{module_info.name}.{name}")
    assert checked > 200, f"only {checked} resource classes were examined"
    assert missing == [], missing[:10]
