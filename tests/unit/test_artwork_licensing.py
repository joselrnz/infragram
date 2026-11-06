"""How we came by each piece of artwork, recorded and enforced.

Every icon in the index carries a ``license_status``, derived from
``license_basis`` in the provider registry. One label for every vendor icon
would say nothing at all: the on-premises set comes from an MIT upstream with
a per-file hash, AWS ships an asset pack whose own terms permit diagram use,
and two libraries were fetched off a vendor web page with no grant ever
established. That is the only distinction that matters before publishing a
repository under MIT.

This file is what stops the status drifting. The count of unverified artwork
is pinned deliberately: it may shrink, and it must never grow by accident.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from infragram.builders.index import build_index, license_bases

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
PROVIDERS = ROOT / "plugin/skills/infragram-architect/assets/catalog/providers.json"

#: Every basis a collection may declare, and what each one means.
RECOGNISED = {
    "upstream-permissive",  # an OSS licence grants redistribution
    "provider-terms",  # the vendor's asset pack permits diagram use
    "permissive",  # a CC0/MIT logo set
    "vendor-unverified",  # fetched from a vendor page; no grant established
    "original-artwork",  # tiles drawn for this project from MIT glyphs; not the vendor's icons
}

#: Libraries whose artwork carries no established redistribution grant, and
#: how many icons that is. Both were fetched from a vendor's own web pages:
#: DigitalOcean's docs and hetzner.com. Their recorded terms links are
#: trademark guidance and a notice of liability, neither of which is a grant.
UNVERIFIED = {"digitalocean", "hetzner"}
UNVERIFIED_ICONS = 170


def _providers() -> list[dict]:
    return json.loads(PROVIDERS.read_text(encoding="utf-8"))["providers"]


@pytest.fixture(scope="module")
def index(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """A fresh index built into scratch. Calling ``build_index()`` bare writes
    the tracked icons/index.json during the test run, which is how a test
    once left the tree modified; the committed copy has its own gate."""
    _path, built = build_index(tmp_path_factory.mktemp("icon-index") / "index.json")
    return built


def test_every_library_declares_how_we_came_by_its_artwork() -> None:
    """A library with no declared basis is the bug this field exists to catch."""
    missing = [p["id"] for p in _providers() if not p.get("license_basis")]
    assert missing == [], f"no licence basis recorded for {missing}"
    unknown = {
        p["id"]: p["license_basis"] for p in _providers() if p["license_basis"] not in RECOGNISED
    }
    assert unknown == {}, unknown


def test_the_index_carries_the_basis_rather_than_a_constant(index: dict) -> None:
    """The regression this replaced: one hard-coded label on everything."""
    seen = Counter(icon.get("license_status") for icon in index["icons"])
    assert "unrecorded" not in seen, "a collection reached the index with no basis"
    assert set(seen) <= RECOGNISED, sorted(set(seen) - RECOGNISED)
    # More than one value, which is the whole point of the change.
    assert len(seen) >= 4, f"the field is uniform again: {dict(seen)}"


def test_unverified_artwork_is_exactly_what_we_know_about(index: dict) -> None:
    """It may shrink. It must never grow without somebody deciding to."""
    unverified = [i for i in index["icons"] if i.get("license_status") == "vendor-unverified"]
    libraries = {str(i["source"]).split(":")[-1] for i in unverified}
    assert libraries == UNVERIFIED, f"the unverified set moved: {sorted(libraries)}"
    assert len(unverified) == UNVERIFIED_ICONS, (
        f"{len(unverified)} unverified icons, expected {UNVERIFIED_ICONS}; "
        "if artwork was cleared or removed, update the number and say why"
    )


@pytest.mark.parametrize(
    "provider,expected",
    [
        ("onprem", "upstream-permissive"),
        ("oracle", "upstream-permissive"),
        ("kubernetes", "upstream-permissive"),
        ("aws", "provider-terms"),
        ("azure", "provider-terms"),
        ("digitalocean", "vendor-unverified"),
        ("hetzner", "vendor-unverified"),
        ("vultr", "original-artwork"),
        ("proxmox", "original-artwork"),
        ("equinix", "original-artwork"),
        ("cloudflare", "original-artwork"),
    ],
)
def test_a_library_claims_only_what_it_has(provider: str, expected: str) -> None:
    """Each of the four real cases, pinned so none drifts into another."""
    assert license_bases()[provider] == expected


def test_the_gallery_ships_nothing_it_cannot_redistribute() -> None:
    """Five glyphs were once fetched from a vendor page and said so.

    No licence-clean brand mark exists for Apache Hop, Pentaho, Dagster, SAS
    or Stata, so each carries a generic glyph instead of a logo we had no
    right to ship. Nothing in the gallery may carry that warning again.
    """
    gallery = (ROOT / "plugin/skills/infragram-architect/references/primitive-icons.md").read_text(
        encoding="utf-8"
    )
    flagged = [
        line
        for line in gallery.splitlines()
        if line.startswith("Source: ") and "verify license" in line.lower()
    ]
    assert flagged == [], flagged
    assert "Direct fetch /" not in gallery, "a glyph is sourced from a vendor page again"


def _official_logos() -> dict[str, dict[str, str]]:
    """The OFFICIAL table of scripts/build/icons.py, read without running it."""
    import ast

    source = (ROOT / "scripts/build/icons.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "OFFICIAL":
            assert node.value is not None
            table = ast.literal_eval(node.value)
            assert isinstance(table, dict)
            return table
    raise AssertionError("scripts/build/icons.py has no OFFICIAL table")


def test_every_project_logo_is_pinned_kept_and_accounted_for() -> None:
    """A logo taken from a project's own repository is the exception the
    gallery allows, and only with its paper trail: a pinned commit, the
    unmodified file kept beside the others, its entry in
    THIRD_PARTY_LICENSES.md, and the gallery naming where it came from."""
    logos = _official_logos()
    assert logos, "no project logos: drop this test with the table"
    notices = (ROOT / "plugin/THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
    gallery = (ROOT / "plugin/skills/infragram-architect/references/primitive-icons.md").read_text(
        encoding="utf-8"
    )
    for slot, entry in logos.items():
        assert len(entry["commit"]) == 40, f"{slot}: pin a full commit, not a branch"
        assert (ROOT / "scripts/vendor/icons/official" / f"{slot}.svg").is_file(), slot
        assert entry["commit"] in notices and entry["path"] in notices, (
            f"{slot} is not recorded in THIRD_PARTY_LICENSES.md"
        )
        assert f"`{entry['repository']}` `{entry['path']}`" in gallery, slot
    # a permissive logo ships its notice; one without a grant says so
    assert (ROOT / "plugin/licenses/valkey.txt").is_file()
    assert "Rights status:** Redpanda" in notices
