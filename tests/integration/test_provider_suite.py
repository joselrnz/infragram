"""Provider icon suite: registry contract and DigitalOcean service artwork.

Consolidates the former test-provider-service-registry.py and
test-digitalocean-service-icons.py into one catalog-driven run. The
browser-based selection-overlay test stays separate (it needs Playwright).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from infragram import SERVICE_ROLES, load_catalog

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())

CATALOG = ROOT / "plugin/skills/infragram-architect/assets/themes/catalog.json"


@pytest.fixture
def providers() -> dict:
    """The catalog keyed by slug, as main() builds it for the script path."""
    return {provider.slug: provider for provider in load_catalog(CATALOG)}


def test_service_registry(providers) -> None:
    """Aliases, provenance, hashes, and SVG safety for every registered icon."""
    minimums = {"aws": 12, "azure": 12, "gcp": 12, "digitalocean": 4}
    expected_aliases = {
        "aws": {
            "lambda": "lambda",
            "serverless function": "lambda",
            "s3": "simple-storage-service",
        },
        "azure": {
            "vnet": "virtual-network",
            "aks": "kubernetes-service",
            "blob": "storage-accounts",
        },
        "gcp": {"gke": "kubernetes-engine", "vm": "compute-engine", "gcs": "cloud-storage"},
        "digitalocean": {"droplet": "droplet", "vm": "droplet", "object storage": "spaces"},
    }

    for slug, minimum in minimums.items():
        provider = providers[slug]
        assert len(provider.icons) >= minimum, (
            f"{slug} needs at least {minimum} registered service icons"
        )
        for query, expected in expected_aliases[slug].items():
            assert provider.icons[provider.icon_aliases[query.casefold()]].slug == expected, (
                f"{slug} alias {query!r}"
            )
        for icon in provider.icons.values():
            assert icon.category in provider.icon_categories
            assert icon.path.is_file() and icon.path.suffix.lower() == ".svg"
            assert hashlib.sha256(icon.path.read_bytes()).hexdigest() == icon.sha256
            assert icon.source_url.startswith("https://")
            assert icon.terms_url.startswith("https://")
            svg = icon.path.read_text(encoding="utf-8")
            lowered = svg.lower()
            assert "<svg" in lowered and "viewbox=" in lowered
            assert "<script" not in lowered and "<foreignobject" not in lowered
            assert "javascript:" not in lowered

    for provider in providers.values():
        for role, path in provider.service_icon_paths.items():
            assert (
                path
                == provider.icons[
                    provider.icon_aliases[provider.service_icon_slugs[role].casefold()]
                ].path
            )

    print("PASS: provider service registry contract")


def test_digitalocean_icons(providers) -> None:
    """DigitalOcean ships one self-contained, on-palette icon per service role."""
    provider = providers["digitalocean"]
    if tuple(provider.service_icon_paths) != SERVICE_ROLES:
        raise AssertionError(
            f"unexpected DigitalOcean icon roles: {tuple(provider.service_icon_paths)}"
        )
    for role, path in provider.service_icon_paths.items():
        if not path.is_file():
            raise AssertionError(f"missing {role} icon: {path}")
        source = path.read_text(encoding="utf-8").casefold()
        # Official docs artwork ships at its own square-ish viewBox and may carry
        # an XML prolog; the renderer scales it through the <symbol> viewBox, so
        # the contract is "standalone, scalable, on-brand" - not one fixed size.
        if "<svg" not in source or "viewbox=" not in source:
            raise AssertionError(f"invalid standalone {role} icon: {path.name}")
        palette = {color.casefold() for color in provider.icon_palette}
        if not any(color in source for color in palette):
            raise AssertionError(
                f"{role} icon uses no declared DigitalOcean palette color: {path.name}"
            )

    print("PASS: DigitalOcean service icons are self-contained and on-palette")
