"""The shipped picture checker judges dashes by the table the editor draws from.

A connector is dashed exactly when its kind has a dash in the provider's link
table: the built-in dotted and dashed, then whatever the provider theme adds
under ``style.links``. The checker reads that table for the provider whose
theme styles the document, resolved the way the model resolves it.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from infragram.author import Diagram, Edge
from infragram.builders.architecture import load_style
from infragram.exports import render_project_svg
from infragram.nodes import reset_ids
from infragram.nodes.azure import compute
from infragram.paths import skill_assets

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())


def _checker():
    spec = importlib.util.spec_from_file_location(
        "project_check", ROOT / "plugin/skills/infragram-architect/scripts/project_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_the_checker_reads_the_same_dash_table_the_renderer_draws_from() -> None:
    checker = _checker()
    for provider in ("aws", "azure", "gcp", "onprem", "kubernetes"):
        style = load_style(provider)
        drawn = {kind: link.dash for kind, link in style.links.items() if link.dash}
        judged = {kind: dash for kind, dash in checker.link_dashes(provider).items() if dash}
        assert judged == drawn, provider


def test_aws_dashes_its_hybrid_kinds_and_keeps_local_solid() -> None:
    dashes = _checker().link_dashes("aws")
    assert dashes["vpn"] and dashes["vif"]
    assert dashes["dotted"] and dashes["dashed"]
    assert dashes["local"] is None
    assert dashes.get("solid") is None


def test_an_unknown_provider_falls_back_to_the_built_in_kinds() -> None:
    checker = _checker()
    assert checker.link_dashes("no-such-provider") == checker.default_link_dashes()
    assert checker.link_dashes(None) == checker.default_link_dashes()


@pytest.mark.parametrize(
    "document, expected",
    [
        ({"providers": [{"id": "aws", "enabled": True}]}, "aws"),
        (
            {"providers": [{"id": "aws", "enabled": False}, {"id": "onprem", "enabled": True}]},
            "onprem",
        ),
        ({"providers": ["gcp", "aws"]}, "gcp"),
        ({"default_library": "azure", "providers": [{"id": "aws"}]}, "azure"),
        ({"default_library": "all", "providers": [{"id": "aws"}]}, "aws"),
        ({"provider": "hetzner"}, "hetzner"),
        ({}, None),
    ],
)
def test_the_primary_provider_resolves_like_the_model(document: dict, expected: str | None) -> None:
    assert _checker().primary_provider(document) == expected


def test_every_shipped_template_resolves_to_a_provider_with_a_theme() -> None:
    checker = _checker()
    themes = skill_assets() / "themes"
    for path in sorted((skill_assets() / "templates").rglob("*.infragram.json")):
        provider = checker.primary_provider(json.loads(path.read_text(encoding="utf-8")))
        assert provider, path.name
        assert (themes / f"{provider}.json").is_file(), f"{path.name}: {provider} has no theme"


def test_an_unknown_connection_kind_is_refused_by_name_everywhere() -> None:
    reset_ids()
    with Diagram("Kinds", providers=("azure",)) as diagram:
        web = compute.VirtualMachine("Web")
        db = compute.VirtualMachine("DB")
        web.to(db, kind="teleport")
    project = diagram.to_project()
    with pytest.raises(ValueError, match="unknown kind 'teleport'.*solid"):
        render_project_svg(project)
    errors: list[str] = []
    _checker().check_project(json.loads(project.model_dump_json(exclude_none=True)), errors)
    assert any(
        "kind 'teleport' is not in the link table of this document's libraries" in error
        for error in errors
    )
    # a kind the library knows passes both
    reset_ids()
    with Diagram("Kinds", providers=("azure",)) as diagram:
        web = compute.VirtualMachine("Web")
        db = compute.VirtualMachine("DB")
        web >> Edge("x", dashed=True) >> db
    project = diagram.to_project()
    render_project_svg(project)
    errors = []
    _checker().check_project(json.loads(project.model_dump_json(exclude_none=True)), errors)
    assert not [error for error in errors if "kind" in error]


def test_a_link_kind_from_any_of_the_documents_libraries_draws() -> None:
    """A hybrid diagram styled by its first library, Cloudflare, still draws
    the AWS theme's ``vpn``, and the checker agrees with the renderer."""
    from infragram.nodes.aws import compute as aws_compute, networking_content_delivery as aws_net
    from infragram.nodes.cloudflare import networking as cf_net

    reset_ids()
    with Diagram("Hybrid kinds") as diagram:
        edge = cf_net.CDN("Edge")
        gateway = aws_net.SiteToSiteVPN("VPN")
        web = aws_compute.EC2("Web")
        edge >> web
        gateway >> Edge("tunnel", kind="vpn") >> web
    project = diagram.to_project()
    assert project.default_library == "cloudflare"
    svg = render_project_svg(project)
    errors: list[str] = []
    _checker().check_project(json.loads(project.model_dump_json(exclude_none=True)), errors)
    _checker().check_svg(svg, errors, project.model_dump(mode="json"))
    assert errors == []
