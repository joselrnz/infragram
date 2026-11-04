"""A multicloud document in the editor keeps each provider's identity, layers and artwork."""

from __future__ import annotations

import json
import re
from pathlib import Path

from infragram.catalog import load_default_provider_registry
from infragram.editor.shell import library_catalog_from_html
from infragram.exports import render_project_html
from infragram.projects import CloudProject


def multicloud_project() -> CloudProject:
    return CloudProject.model_validate(
        {
            "schema_version": 2,
            "kind": "multicloud",
            "slug": "global-platform",
            "title": "Global Platform",
            "description": "Azure, AWS, and GCP services in one workspace.",
            "providers": [{"id": item} for item in ("azure", "aws", "gcp")],
            "default_library": "all",
            "layers": [
                {
                    "id": f"provider:{provider}",
                    "name": name,
                    "kind": "provider",
                    "provider": provider,
                    "order": index,
                }
                for index, (provider, name) in enumerate(
                    (("azure", "Azure"), ("aws", "AWS"), ("gcp", "Google Cloud"))
                )
            ],
            "topology": {
                "id": "root",
                "name": "Global Platform",
                "type": "group",
                "children": [
                    {
                        "id": "gateway",
                        "name": "Gateway",
                        "type": "service",
                        "component": {
                            "provider": "azure",
                            "service_id": "application-gateways",
                        },
                        "layer_id": "provider:azure",
                        "connections": [{"target": "worker", "kind": "solid"}],
                    },
                    {
                        "id": "worker",
                        "name": "Worker",
                        "type": "service",
                        "component": {"provider": "aws", "service_id": "lambda"},
                        "layer_id": "provider:aws",
                        "connections": [{"target": "database", "kind": "dashed"}],
                    },
                    {
                        "id": "database",
                        "name": "Database",
                        "type": "database",
                        "component": {"provider": "gcp", "service_id": "cloud-sql"},
                        "layer_id": "provider:gcp",
                    },
                ],
            },
        }
    )


def _json_script(html: str, element_id: str) -> dict:
    match = re.search(
        rf'<script type="application/json" id="{element_id}"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def test_editor_state_v3_preserves_provider_identity_layers_and_artwork() -> None:
    html = render_project_html(multicloud_project())
    state = _json_script(html, "infragram-editor-state")
    library = library_catalog_from_html(html)
    artwork = {
        component["qualifiedId"]: component["iconUri"] for component in library["components"]
    }

    assert state["schemaVersion"] == 3
    assert state["projectSlug"] == "global-platform"
    assert state["providers"] == ["azure", "aws", "gcp"]
    assert [layer["id"] for layer in state["layers"]] == [
        "provider:azure",
        "provider:aws",
        "provider:gcp",
    ]
    nodes = {node["id"]: node for node in state["nodes"]}
    assert nodes["gateway"]["layerId"] == "provider:azure"
    assert nodes["worker"]["layerId"] == "provider:aws"
    assert nodes["database"]["layerId"] == "provider:gcp"
    assert nodes["worker"]["iconUri"] == artwork["aws:lambda"]
    assert nodes["database"]["iconUri"] == artwork["gcp:cloud-sql"]


def test_inspector_exposes_provider_context_layers_and_arrange_controls() -> None:
    html = render_project_html(multicloud_project())

    assert 'data-inspector-tab="arrange"' in html
    assert 'data-inspector-tab="layers"' in html
    assert "data-inspector-provider" in html
    assert "data-inspector-component" in html
    assert 'data-exact-field="x"' in html
    assert 'data-exact-field="y"' in html
    assert 'data-exact-field="width"' in html
    assert 'data-exact-field="height"' in html
    for action in (
        "align-left",
        "align-center",
        "align-right",
        "align-top",
        "align-middle",
        "align-bottom",
        "distribute-horizontal",
        "distribute-vertical",
    ):
        assert f'data-arrange-action="{action}"' in html
    assert "data-layer-list" in html


def test_runtime_declares_v2_recovery_migration_and_non_exported_guides() -> None:
    html = render_project_html(multicloud_project())

    assert "migrateSavedState" in html
    assert "saved.schemaVersion === 2" in html
    assert "migrated.schemaVersion = 3" in html
    assert "data-alignment-guide-layer" in html
    export_source = html.split("const exportSvg", maxsplit=1)[1]
    assert "[data-alignment-guide-layer]" in export_source


def test_shipped_multicloud_base_template_places_six_provider_components() -> None:
    template = (
        Path(__file__).parents[2]
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "templates"
        / "cloud"
        / "multicloud-base.infragram.json"
    )

    project = CloudProject.load(template)
    state = _json_script(render_project_html(project), "infragram-editor-state")

    assert project.kind == "multicloud"
    # The base template installs every registered library, in registry order.
    assert project.provider_ids == tuple(
        provider.id for provider in load_default_provider_registry().providers
    )
    assert {node["componentProvider"] for node in state["nodes"]} == {
        "azure",
        "aws",
        "gcp",
        "digitalocean",
        "kubernetes",
        "hetzner",
    }
    assert all(node["iconUri"].startswith("data:image/svg+xml;") for node in state["nodes"])
