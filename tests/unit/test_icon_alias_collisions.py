"""Alias collisions in the shipped packs are counted, so growth is visible.

A pack may give several entries one name: the on-premises library alone has
hundreds of tiles that answer to "server". ``IconSet.find`` resolves such a
name to the first entry in catalog order, every time, and reports the rest
through ``alias_collisions``. This test records the count per pack. When a
pack changes, update the number here in the same change and say why in the
commit: a rising count means a new entry is shadowed by an old one and a
``find`` by that name will not return it.
"""

from __future__ import annotations

from pathlib import Path

from infragram.registries.icons import IconSet

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
ICONS = ROOT / "plugin/skills/infragram-architect/assets/icons"

#: pack -> how many claims on an already-taken name it carries (the number
#: of entries that ``find`` can never return by that name).
SHADOWED = {
    "akamai": 0,
    "alibaba": 9,
    "aws": 2,
    "azure": 76,
    "cloudflare": 0,
    "databricks": 0,
    "digitalocean": 0,
    "equinix": 0,
    "gcp": 9,
    "hetzner": 0,
    "ibm": 43,
    "kubernetes": 0,
    "logos": 0,
    "onprem": 1932,
    "openstack": 0,
    "oracle": 0,
    "ovhcloud": 0,
    "proxmox": 0,
    "vmware": 0,
    "vultr": 0,
}


def _packs() -> dict[str, IconSet]:
    return {
        path.parent.name: IconSet(path.parent.name, path.parent)
        for path in sorted(ICONS.glob("**/catalog.json"))
    }


def test_find_is_deterministic_and_the_first_claim_wins() -> None:
    pack = _packs()["onprem"]
    collisions = pack.alias_collisions()
    assert collisions, "the test needs a pack with a shared name"
    alias, ids = next(iter(collisions.items()))
    assert len(ids) > 1
    assert pack.find(alias).slug == ids[0] == pack.find(alias.upper()).slug
    # every claimant is still reachable by its own id, which is never shared
    for slug in ids:
        assert pack[slug].slug == slug


def test_the_collision_count_per_pack_is_the_recorded_one() -> None:
    packs = _packs()
    assert set(packs) == set(SHADOWED), (
        f"packs changed: {sorted(set(packs) ^ set(SHADOWED))}; add or remove them in SHADOWED"
    )
    counted = {
        name: sum(len(ids) - 1 for ids in pack.alias_collisions().values())
        for name, pack in packs.items()
    }
    drift = {
        name: (SHADOWED[name], counted[name]) for name in counted if counted[name] != SHADOWED[name]
    }
    assert not drift, (
        "alias collisions moved (recorded -> now): "
        + ", ".join(f"{name} {a} -> {b}" for name, (a, b) in sorted(drift.items()))
        + ". If the pack change is intended, update SHADOWED in tests/unit/test_icon_alias_collisions.py "
        "and note which names are now shadowed (IconSet.alias_collisions() lists them)."
    )
