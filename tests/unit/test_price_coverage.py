"""Every component AWS, Azure and Google Cloud draw is priced, free, or not
priced with a reason: none is left out, none is in two places."""

from __future__ import annotations

import json

import pytest

from infragram.paths import skill_assets
from infragram.pricing import coverages

CLOUDS = ("aws", "azure", "gcp")


def _components(cloud: str) -> set[str]:
    inventory = json.loads(
        (skill_assets() / "catalog" / "inventory.json").read_text(encoding="utf-8")
    )
    library = next(item for item in inventory["libraries"] if item["id"] == cloud)
    return {component["id"] for component in library["components"]}


@pytest.mark.parametrize("cloud", CLOUDS)
def test_every_component_is_priced_free_or_says_why_not(cloud: str) -> None:
    coverage = coverages()[cloud]
    drawn = _components(cloud)
    priced, free, unpriced = set(coverage.pricers), set(coverage.free), set(coverage.unpriced)
    assert not priced & free and not priced & unpriced and not free & unpriced
    assert drawn - (priced | free | unpriced) == set(), "components with no pricing decision"
    assert (priced | free | unpriced) - drawn == set(), "decisions for components not drawn"
    assert all(reason.strip() for reason in (*coverage.free.values(), *coverage.unpriced.values()))
