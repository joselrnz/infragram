"""Regression tests for the data-driven cloud-provider catalog."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import infragram

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())

CATALOG = ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "themes" / "catalog.json"
EXPECTED_ORDER = [
    "azure",
    "aws",
    "gcp",
    "cloudflare",
    "digitalocean",
    "oracle",
    "ibm",
    "alibaba",
    "kubernetes",
    "hetzner",
    "onprem",
    "ovhcloud",
    "vultr",
    "akamai",
    "openstack",
    "vmware",
    "proxmox",
    "databricks",
    "equinix",
]
INFRASTRUCTURE_CATEGORIES = {
    "analytics",
    "compute",
    "containers",
    "data",
    "integration",
    "networking",
    "security",
    "storage",
}


def expect_invalid_tree(module, catalog: dict, manifests: dict[str, dict], message: str) -> None:
    with tempfile.TemporaryDirectory(prefix="provider-tree-") as temp_dir:
        root = Path(temp_dir)
        path = root / "catalog.json"
        path.write_text(json.dumps(catalog), encoding="utf-8")
        for relative, payload in manifests.items():
            payload = json.loads(json.dumps(payload))
            # These fixtures exercise manifest-level failures, not the icon
            # registry. Keep them independent from production role mappings
            # and from asset_ref resolution against the real icons/ tree.
            payload.pop("service_icons", None)
            if isinstance(payload.get("icons"), dict):
                payload["icons"] = {
                    "categories": payload["icons"].get("categories") or ["compute"],
                    "items": [],
                }
            # Library-referenced marks (logos:aws#mono) resolve against the real
            # icons tree, which these fixtures deliberately lack.
            if isinstance(payload.get("mark"), str) and ":" in payload["mark"]:
                payload["mark"] = f"marks/{payload.get('slug', 'fixture')}.svg"
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload), encoding="utf-8")
            mark_rel = payload.get("mark")
            if isinstance(mark_rel, str):
                mark_target = (target.parent / mark_rel).resolve()
                if mark_target.is_relative_to(root.resolve()):
                    mark_target.parent.mkdir(parents=True, exist_ok=True)
                    mark_target.write_text(
                        '<svg viewBox="0 0 24 24"><path d="M2 2h20v20H2z"/></svg>',
                        encoding="utf-8",
                    )
        try:
            module.load_catalog(path, root)
        except ValueError as error:
            if message not in str(error):
                raise AssertionError(f"expected {message!r}, got {error!r}") from error
        else:
            raise AssertionError("invalid provider tree was accepted")


def providers():
    return infragram.load_catalog(CATALOG)


def raw_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def azure_manifest() -> dict:
    return json.loads((CATALOG.parent / raw_catalog()["providers"][0]).read_text(encoding="utf-8"))


def test_providers_load_in_the_catalog_order() -> None:
    slugs = [provider.slug for provider in providers()]
    assert slugs == EXPECTED_ORDER, f"unexpected provider order: {slugs}"


def test_azure_icon_palette_keeps_databricks_red() -> None:
    azure = providers()[0]
    assert "#ff3621" in azure.icon_palette, "Azure icon palette must preserve Databricks red"


def test_every_provider_owns_its_manifest_icons_and_mark() -> None:
    marks_dir = CATALOG.parent / "marks"
    icons_dir = CATALOG.parent.parent / "icons"
    for provider in providers():
        assert provider.manifest_path == CATALOG.parent / f"{provider.slug}.json", (
            f"provider manifest is not provider-owned: {provider.slug}"
        )
        # A mark is either theme-owned (marks/<slug>.svg) or a reference into a
        # provenance-tracked artwork library (logos:aws#mono); never a stray file.
        owned = provider.mark_path == marks_dir / f"{provider.slug}.svg"
        assert owned or provider.mark_path.is_relative_to(icons_dir), (
            f"provider mark is neither theme-owned nor a library reference: {provider.slug}"
        )
        assert provider.icon_catalog_path == provider.manifest_path, (
            f"icon registry must be inline in the theme manifest: {provider.slug}"
        )
        assert set(provider.icon_categories) == INFRASTRUCTURE_CATEGORIES, (
            f"incomplete infrastructure categories for {provider.slug}"
        )
        assert provider.mark_path.is_file(), (
            f"missing mark for {provider.slug}: {provider.mark_path}"
        )
        mark = provider.mark_path.read_text(encoding="utf-8")
        if owned:
            assert mark.startswith("<svg") and 'viewBox="0 0 24 24"' in mark, (
                f"invalid standalone mark for {provider.slug}"
            )
            assert not any(token in mark for token in (' x="', ' y="', ' width="', ' height="')), (
                f"mark owns layout instead of the renderer: {provider.slug}"
            )
        else:
            assert "<svg" in mark and "viewBox=" in mark, (
                f"library mark is not a scalable standalone SVG: {provider.slug}"
            )


def test_root_catalog_is_a_schema_v2_manifest_index() -> None:
    raw = raw_catalog()
    assert raw.get("schema_version") == 2 and all(
        isinstance(item, str) for item in raw["providers"]
    ), "root catalog must be a schema-v2 ordered manifest index"


def test_duplicate_provider_slug_is_refused() -> None:
    raw = raw_catalog()
    duplicate = {"schema_version": 2, "providers": [raw["providers"][0], raw["providers"][0]]}
    expect_invalid_tree(
        infragram, duplicate, {"azure.json": azure_manifest()}, "duplicate provider slug"
    )


def test_invalid_theme_colour_is_refused() -> None:
    bad_color = azure_manifest()
    bad_color["theme"]["paper"] = "navy"
    expect_invalid_tree(
        infragram,
        {"schema_version": 2, "providers": ["azure.json"]},
        {"azure.json": bad_color},
        "invalid color",
    )


def test_invalid_icon_colour_is_refused() -> None:
    bad_icon_color = azure_manifest()
    bad_icon_color["icon_palette"] = ["databricks-red"]
    expect_invalid_tree(
        infragram,
        {"schema_version": 2, "providers": ["azure.json"]},
        {"azure.json": bad_icon_color},
        "invalid icon color",
    )


def test_duplicate_icon_colour_is_refused() -> None:
    duplicate_icon_color = azure_manifest()
    duplicate_icon_color["icon_palette"] = ["#ff3621", "#FF3621"]
    expect_invalid_tree(
        infragram,
        {"schema_version": 2, "providers": ["azure.json"]},
        {"azure.json": duplicate_icon_color},
        "duplicate icon color",
    )


def test_a_mark_outside_the_theme_tree_is_refused() -> None:
    escaped_manifest = azure_manifest()
    escaped_manifest["mark"] = "../../outside.svg"
    expect_invalid_tree(
        infragram,
        {"schema_version": 2, "providers": ["azure.json"]},
        {"azure.json": escaped_manifest},
        "must stay inside",
    )


# ---------------------------------------- the count the prose commits to

#: Written-out counts, as the comments and docs spell them. The number is
#: load-bearing wherever it appears: each sentence uses it to explain why a
#: shared component may not name a provider, so being wrong about it
#: undercuts the rule it is there to justify. Six places said "nineteen"
#: while the catalog shipped seventeen.
WRITTEN = {
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

#: Where a library count is written in prose rather than read from here.
PROSE = (
    "plugin/src/infragram/editor/ui/__init__.py",
    "plugin/src/infragram/editor/ui/views/sidebar.py",
    "plugin/src/infragram/catalog/providers.py",
)

COUNTED = re.compile(r"\b(" + "|".join(WRITTEN) + r")\b", re.IGNORECASE)

#: What makes a numeral a library count rather than any other number. The
#: word that says so often sits on the line before or after, so the window is
#: measured over the whole text and not line by line.
ABOUT = re.compile(r"librar|provider|export", re.IGNORECASE)
WINDOW = 90


def counted_wrongly(text: str, shipped: int) -> list[tuple[int, str]]:
    """Every written library count in *text* that disagrees with *shipped*,
    as (line number, the word). One less is allowed: the prose says "a bug in
    sixteen of the seventeen exports"."""
    found: list[tuple[int, str]] = []
    for match in COUNTED.finditer(text):
        near = text[max(0, match.start() - WINDOW) : match.end() + WINDOW]
        if not ABOUT.search(near):
            continue
        if WRITTEN[match.group(1).lower()] in (shipped, shipped - 1):
            continue
        found.append((text.count("\n", 0, match.start()) + 1, match.group(1)))
    return found


def test_the_prose_counts_the_libraries_that_actually_ship() -> None:
    """A comment that says nineteen in a product that ships seventeen is a
    comment a reader has no reason to trust about anything else."""
    shipped = len(EXPECTED_ORDER)
    wrong = [
        f"{relative}:{line} says {word!r} of the libraries; {shipped} ship"
        for relative in PROSE
        for line, word in counted_wrongly((ROOT / relative).read_text(encoding="utf-8"), shipped)
    ]
    assert wrong == [], "\n".join(wrong)


def test_that_scan_can_tell_a_wrong_count_from_a_right_one() -> None:
    """It is only worth having if a wrong number reaches it, and the numeral
    and the word that makes it a count are on different lines in every place
    this guards. A line-by-line version of it quietly found nothing."""
    shipped = len(EXPECTED_ORDER)
    sample = (
        "#: Whether the sidebar offers this library a one-click filter.\n"
        "#: Three of the {word} do.\n"
    )
    assert counted_wrongly(sample.format(word="twenty"), shipped), (
        "a wrong count spanning two lines is not seen"
    )
    assert not counted_wrongly(sample.format(word="nineteen"), shipped), (
        "the right count is reported as wrong"
    )
    assert not counted_wrongly("seventeen apples and nineteen pears\n", shipped), (
        "a number that is not about libraries is counted anyway"
    )


def test_the_catalog_and_the_node_packages_agree_on_what_ships() -> None:
    """The prose is checked against this list, so this list has to be checked
    against the tree: a provider with components and no catalog entry, or the
    other way round, would make every count above meaningless."""
    packages = {
        path.name
        for path in (ROOT / "plugin" / "src" / "infragram" / "nodes").iterdir()
        if path.is_dir() and not path.name.startswith(("_", "."))
    }
    # `infragram` is the shared library every document can reach, and
    # `frames` and `logos` are artwork rather than components.
    providers = packages - {"infragram", "frames", "logos"}
    assert providers == set(EXPECTED_ORDER), (
        f"only in the tree: {sorted(providers - set(EXPECTED_ORDER))}; "
        f"only in the catalog: {sorted(set(EXPECTED_ORDER) - providers)}"
    )


# ------------------------------------------- the face every label is set in

THEMES = ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "themes"


def test_no_skin_sets_its_own_face_for_the_drawn_labels() -> None:
    """A skin's ``typography.font`` is applied to ``Style.sans``, which is
    the face *every drawn label* uses -- not the heading the field is
    documented for.

    Two skins set it, both to a stack that restated the default and added a
    fallback the HTML wrapper's own rule already appends. Nothing compared
    the skins to each other, so aws and azure declared one face while the
    other fifteen declared another, in every picture they drew.
    """
    from infragram.builders.scene import Style

    default = Style().sans
    wrong: list[str] = []
    for path in sorted(THEMES.glob("*.json")):
        if path.stem == "catalog":
            continue
        typography = json.loads(path.read_text(encoding="utf-8")).get("typography") or {}
        font = typography.get("font")
        if font is not None and font != default:
            wrong.append(f"{path.name} sets typography.font to {font!r}, not {default!r}")
    assert not wrong, (
        "\n".join(wrong) + "\n\nA skin may have its own colours and its own artwork. The face"
        " every label is set in is the product's, not the vendor's."
    )
