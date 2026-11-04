from __future__ import annotations

import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from pydantic import ValidationError

from infragram import compose
from infragram.builders.architecture import load_icon_set
from infragram.catalog import load_default_provider_registry
from infragram.editor import load_sidebar_catalog
from infragram.editor.shell import library_catalog_from_html
from infragram.exports import (
    ExportError,
    export_project,
    extract_svg,
    finish_standalone_svg,
    render_project_html,
    render_project_svg,
)
from infragram.nodes import reset_ids
from infragram.nodes.azure import compute
from infragram.projects import CloudProject


def standalone_svg(html: str) -> str:
    """The drawing a page embeds, finished as a file of its own."""
    return finish_standalone_svg(extract_svg(html))


def project_payload() -> dict:
    return {
        "schema_version": 1,
        "slug": "azure-api",
        "title": "Azure API",
        "description": "Client traffic flows through an API to storage.",
        "provider": "azure",
        "presentation": {
            "size": "doc-inline",
            "detail": "balanced",
            "audience": "mixed",
            "eyebrow": "Azure architecture",
        },
        "topology": {
            "id": "root",
            "name": "Azure API",
            "type": "group",
            "children": [
                {
                    "id": "client",
                    "name": "Client",
                    "type": "client",
                    "connections": [{"target": "api", "kind": "solid", "label": "HTTPS"}],
                },
                {
                    "id": "api",
                    "name": "API",
                    "type": "service",
                    "role": "hub",
                    "connections": [{"target": "storage", "kind": "solid", "label": "WRITES"}],
                },
                {
                    "id": "storage",
                    "name": "Storage",
                    "type": "storage",
                },
            ],
        },
    }


def embedded_library(html: str) -> dict:
    return library_catalog_from_html(html)


def test_cloud_project_round_trips_as_a_versioned_template(tmp_path: Path) -> None:
    project = CloudProject.model_validate(project_payload())
    output = tmp_path / "azure-api.infragram.json"

    project.save(output)
    loaded = CloudProject.load(output)

    assert loaded == project
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 3
    assert saved["providers"] == [{"id": "azure", "enabled": True}]
    assert "provider" not in saved


def test_connector_label_placement_round_trips_into_editor_state() -> None:
    payload = project_payload()
    payload["topology"]["children"][0]["connections"][0]["label_placement"] = {
        "mode": "manual",
        "dx": 24,
        "dy": -16,
    }

    project = CloudProject.model_validate(payload)
    connection = project.topology.children[0].connections[0]

    assert connection.label_placement is not None
    assert connection.label_placement.mode == "manual"
    assert connection.label_placement.dx == 24
    assert connection.label_placement.dy == -16

    html = render_project_html(project)
    match = re.search(
        r'<script type="application/json" id="infragram-editor-state"[^>]*>'
        r"(.*?)</script>",
        html,
        flags=re.DOTALL,
    )
    assert match is not None
    state = json.loads(match.group(1))
    https_edge = next(edge for edge in state["edges"] if edge["label"] == "HTTPS")
    assert https_edge["labelPlacement"] == {
        "mode": "manual",
        "dx": 24.0,
        "dy": -16.0,
    }


def test_connector_label_placement_rejects_unknown_modes() -> None:
    payload = project_payload()
    payload["topology"]["children"][0]["connections"][0]["label_placement"] = {
        "mode": "floating",
        "dx": 0,
        "dy": 0,
    }

    with pytest.raises(ValidationError, match="label_placement"):
        CloudProject.model_validate(payload)


def test_aws_vpn_template_preserves_reference_architecture_boundaries() -> None:
    source = (
        Path(__file__).parents[2]
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "templates"
        / "cloud"
        / "aws-site-to-site-vpn.infragram.json"
    )
    project = CloudProject.load(source)
    elements = project.topology.index()

    assert project.provider == "aws"
    assert project.presentation.size == "fit"
    assert elements["aws-cloud"].type == "cloud"
    assert elements["aws-region"] in elements["aws-cloud"].children
    assert elements["vpc"] in elements["aws-region"].children
    assert elements["zone-a"] in elements["vpc"].children
    assert elements["zone-b"] in elements["vpc"].children
    assert elements["public-subnet"].type == "subnet-public"
    assert elements["private-subnet"].type == "subnet-private"
    assert elements["public-subnet"] in elements["zone-a"].children
    assert elements["private-subnet"] in elements["zone-b"].children

    kinds = {
        connection.kind for element in project.topology.walk() for connection in element.connections
    }
    assert kinds == {"local", "vif", "vpn"}


def test_interactive_aws_vpn_keeps_boundary_and_editor_layers_separate() -> None:
    source = (
        Path(__file__).parents[2]
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "templates"
        / "cloud"
        / "aws-site-to-site-vpn.infragram.json"
    )
    html = render_project_html(CloudProject.load(source))

    assert 'data-static-cluster-layer="true"' in html
    assert 'data-static-link-layer="true"' in html
    assert 'data-static-node-layer="true"' in html
    assert 'data-static-meta-layer="true"' in html
    assert "[data-static-cluster-layer],[data-static-link-layer],[data-static-node-layer]" in html
    assert "data-graph-boundary" in html
    assert "data-boundary-resize" in html
    assert "addBoundary" in html
    assert "child.dataset.staticLayer = 'true'" not in html


def test_interactive_aws_vpn_embeds_nested_dynamic_boundary_geometry() -> None:
    source = (
        Path(__file__).parents[2]
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "templates"
        / "cloud"
        / "aws-site-to-site-vpn.infragram.json"
    )
    html = render_project_html(CloudProject.load(source))
    match = re.search(
        r'<script type="application/json" id="infragram-editor-state"[^>]*>'
        r"(.*?)</script>",
        html,
        flags=re.DOTALL,
    )

    assert match is not None
    state = json.loads(match.group(1))
    boundaries = {boundary["id"]: boundary for boundary in state["boundaries"]}
    nodes = {node["id"]: node for node in state["nodes"]}

    assert state["schemaVersion"] == 3
    assert set(boundaries) == {
        "aws-cloud",
        "aws-region",
        "vpc",
        "zone-a",
        "public-subnet",
        "zone-b",
        "private-subnet",
        "direct-connect-location",
        "corporate-network",
    }
    assert boundaries["aws-region"]["parentId"] == "aws-cloud"
    assert boundaries["vpc"]["parentId"] == "aws-region"
    assert boundaries["zone-a"]["parentId"] == "vpc"
    assert boundaries["public-subnet"]["parentId"] == "zone-a"
    assert nodes["instance-a"]["boundaryId"] == "public-subnet"
    assert nodes["instance-b"]["boundaryId"] == "private-subnet"
    assert nodes["virtual-private-gateway"]["boundaryId"] == "aws-region"
    assert boundaries["public-subnet"]["stroke"] == "#7aa116"
    assert boundaries["private-subnet"]["stroke"] == "#00a4a6"
    # the icon deck draws the Region dotted; only the line separates
    # it from the Availability Zone, which shares its colour
    assert boundaries["aws-region"]["dash"] == "2,3"
    assert boundaries["aws-region"]["pad"] == 24
    cloud_icon = (
        __import__("base64")
        .b64decode(boundaries["aws-cloud"]["iconUri"].partition(",")[2])
        .decode("utf-8")
    )
    assert "currentColor" not in cloud_icon
    # The deck writes its hex in capitals; the reversed-out mark is still white.
    assert "#ffffff" in cloud_icon.lower()


def test_interactive_aws_vpn_preserves_provider_link_styles_and_footer_clearance() -> None:
    source = (
        Path(__file__).parents[2]
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "templates"
        / "cloud"
        / "aws-site-to-site-vpn.infragram.json"
    )
    html = render_project_html(CloudProject.load(source))
    state_match = re.search(
        r'<script type="application/json" id="infragram-editor-state"[^>]*>'
        r"(.*?)</script>",
        html,
        flags=re.DOTALL,
    )
    assert state_match is not None
    state = json.loads(state_match.group(1))
    # The runtime reads a wire's width and dash from the edge, and its colour
    # by kind from the link-styles block the shell writes beside the state.
    styles = {edge["kind"]: (edge["width"], edge.get("dash")) for edge in state["edges"]}
    assert styles["vif"] == (1.4, "7,4")
    assert styles["vpn"] == (1.4, "8,3,2,3")
    assert styles["local"] == (1.1, None)
    assert not any("paint" in edge or "markerId" in edge for edge in state["edges"])
    link_styles_match = re.search(
        r'<script type="application/json" id="infragram-link-styles">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert link_styles_match is not None
    link_styles = json.loads(link_styles_match.group(1))
    assert link_styles["vif"]["color"] == "#147eba"
    assert link_styles["vpn"]["color"] == "#c7254e"
    assert (
        link_styles["local"]["role"] == "soft"
    )  # the local kind takes the soft tone, not the wire default

    cloud = re.search(
        r'data-static-cluster-layer="true">\s*<rect x="\d+" y="(\d+)" '
        r'width="\d+" height="(\d+)"',
        html,
    )
    mark = re.search(
        r'<!-- Brand mark -->\s*<svg data-brand-mark="" x="\d+" y="(\d+)" width="\d+" height="(\d+)"',
        html,
    )
    assert cloud is not None and mark is not None
    cloud_y, cloud_height = (int(value) for value in cloud.groups())
    mark_y, _ = (int(value) for value in mark.groups())
    assert cloud_y + cloud_height + 24 <= mark_y

    purple_boundaries = re.findall(
        r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"[^>]*/>\s*'
        r'<path[^>]+stroke="#8c4fff"',
        html,
    )
    vpn_label = re.search(
        r'<text x="(\d+)" y="(\d+)"[^>]*>AWS Site-to-Site VPN</text>',
        html,
    )
    vif_label = re.search(
        r'<text x="(\d+)" y="(\d+)"[^>]*>Direct Connect public VIF</text>',
        html,
    )
    # The VPC is the only purple boundary: the deck defines no Direct Connect
    # location group, so ours takes the generic grey instead of borrowing the
    # VPC's colour. The location is found by its own stroke.
    location_boundaries = re.findall(
        r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"[^>]*/>\s*'
        r'<path[^>]+stroke="#7d8998"',
        html,
    )
    assert purple_boundaries and vpn_label is not None and vif_label is not None
    assert location_boundaries, "the Direct Connect location lost its generic grey"
    # Where the two captions stand is the editor's placement, which the
    # static picture follows (builders/captions.py): like every caption, on or
    # beside its own wire -- a circuit's and a tunnel's no longer stand a fixed
    # distance off it -- which the checker holds the picture to, and the
    # browser parity gate holds both pictures to one another.
    from infragram.cli.user.checker import checker
    from infragram.exports import render_project_svg

    errors: list[str] = []
    checker().check_svg(render_project_svg(CloudProject.load(source)), errors)
    assert not [error for error in errors if "caption" in error], errors


@pytest.mark.parametrize(
    "provider", [entry.id for entry in load_default_provider_registry().providers]
)
def test_cloud_project_accepts_every_registered_provider(provider: str) -> None:
    payload = project_payload()
    payload["provider"] = provider

    assert CloudProject.model_validate(payload).provider == provider


@pytest.mark.parametrize(
    ("filename", "provider", "expected_icons", "expected_flow"),
    [
        (
            "digitalocean-application-delivery.infragram.json",
            "digitalocean",
            {"load-balancer", "app-platform", "spaces-docs", "databases"},
            ["client", "load-balancer", "app-platform", "database", "spaces"],
        ),
        (
            "hetzner-application-delivery.infragram.json",
            "hetzner",
            {"load-balancer", "cloud", "object-storage", "storage-box"},
            ["client", "load-balancer", "cloud-server", "database", "object-storage"],
        ),
    ],
)
def test_provider_application_delivery_templates_use_reviewed_service_icons_and_shared_sidebar(
    filename: str,
    provider: str,
    expected_icons: set[str],
    expected_flow: list[str],
) -> None:
    source = (
        Path(__file__).parents[2]
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "templates"
        / "cloud"
        / filename
    )

    project = CloudProject.load(source)
    html = render_project_html(project)
    elements = project.topology.index()
    icons = {
        str(element.attributes.get("icon"))
        for element in elements.values()
        if element.attributes.get("icon")
    }

    assert project.provider == provider
    assert project.presentation.size == "fit"
    assert icons == expected_icons
    assert [element.id for element in project.topology.children] == expected_flow
    for source_id, target_id in zip(expected_flow, expected_flow[1:], strict=False):
        assert [connection.target for connection in elements[source_id].connections] == [target_id]
    assert elements[expected_flow[-1]].connections == []
    assert html.count('data-category-id="') == 21
    assert "--md-sys-color-surface:" in html
    assert "--md-sys-color-surface-container:" in html
    assert "--md-sys-color-surface-container:" in html
    assert "--canvas-bg:#141414" in html
    assert "data-theme-toggle" in html
    assert 'aria-label="Infrastructure components"' in html
    assert 'class="provider-mark"' in html


def test_cloud_project_rejects_unknown_providers() -> None:
    payload = project_payload()
    payload["provider"] = "mystery-cloud"

    with pytest.raises(ValidationError, match="unsupported cloud provider"):
        CloudProject.model_validate(payload)


def test_cloud_project_rejects_connections_to_missing_elements() -> None:
    payload = project_payload()
    payload["topology"]["children"][0]["connections"][0]["target"] = "missing"

    with pytest.raises(ValidationError, match="unknown target"):
        CloudProject.model_validate(payload)


def test_cloud_project_rejects_unversioned_or_future_templates() -> None:
    payload = project_payload()
    payload["schema_version"] = 4

    with pytest.raises(ValidationError, match="schema_version"):
        CloudProject.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("slug", "Not A Slug", "slug must"), ("title", "   ", "must not be empty")],
)
def test_cloud_project_rejects_invalid_identity_fields(
    field: str, value: str, message: str
) -> None:
    payload = project_payload()
    payload[field] = value

    with pytest.raises(ValidationError, match=message):
        CloudProject.model_validate(payload)


def test_project_renders_canonical_accessible_inline_svg_html() -> None:
    html = render_project_html(CloudProject.model_validate(project_payload()))

    assert html.startswith("<!DOCTYPE html>")
    assert 'class="provider-sidebar" data-testid="provider-sidebar"' in html
    assert '<input type="search"' in html
    assert "data-sidebar-search" in html
    assert html.count('data-category-id="') == 21
    library = embedded_library(html)
    assert (
        sum(component["provider"] in {"azure", "infragram"} for component in library["components"])
        == load_sidebar_catalog("azure").component_count
    )
    assert 'data-library-render-mode="lazy"' in html
    assert 'viewBox="0 0 960 600"' in html
    assert "data-infragram-diagram" in html
    assert "data-graph-layer" in html
    assert 'data-editor-action="undo"' in html
    assert 'data-editor-action="redo"' in html
    assert 'data-editor-action="delete"' in html
    assert 'data-editor-action="zoom-in"' in html
    assert 'data-editor-action="zoom-out"' in html
    assert 'data-editor-action="zoom-fit"' in html
    assert "data-download-html" in html
    assert "data-editor-state" in html
    assert "window.infragramEditor" in html
    assert 'aria-labelledby="azure-api-title azure-api-desc"' in html
    assert '<title id="azure-api-title">Azure API</title>' in html
    assert (
        '<desc id="azure-api-desc">Client traffic flows through an API to storage.</desc>' in html
    )
    assert "<image" not in extract_svg(html)


def test_editor_state_embeds_initial_nodes_connections_and_icon_artwork() -> None:
    html = render_project_html(CloudProject.model_validate(project_payload()))
    match = re.search(
        r'<script type="application/json" id="infragram-editor-state"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL,
    )

    assert match is not None
    state = json.loads(match.group(1))
    assert state["schemaVersion"] == 3
    assert state["boundaries"] == []
    assert [node["id"] for node in state["nodes"]] == ["client", "api", "storage"]
    assert all(node["boundaryId"] is None for node in state["nodes"])
    assert len(state["edges"]) == 2
    assert state["edges"][0]["source"] == "client"
    assert state["edges"][0]["target"] == "api"
    assert state["nodes"][1]["x"] % 4 == 0
    assert state["nodes"][1]["y"] % 4 == 0


def test_sidebar_keeps_the_approved_category_order_and_embeds_icons() -> None:
    html = render_project_html(CloudProject.model_validate(project_payload()))
    expected = [
        "custom",
        "ai-machine-learning",
        "analytics",
        "compute",
        "containers",
        "databases",
        "devops",
        "hybrid-multicloud",
        "identity",
        "integration",
        "internet-of-things",
        "energy",
        "industrial",
        "facilities",
        "governance",
        "mobile",
        "networking",
        "power-platform",
        "security",
        "storage",
        "web",
    ]

    positions = [html.index(f'data-category-id="{category}"') for category in expected]

    assert positions == sorted(positions)
    assert 'src="data:image/svg+xml;base64,' in html
    qualified = {component["qualifiedId"] for component in embedded_library(html)["components"]}
    assert {"azure:application-gateways", "infragram:custom-annotation"} <= qualified
    assert 'data-category-id="power-platform"' in html


def test_sidebar_uses_real_inline_category_icons_and_a_colored_provider_mark() -> None:
    html = render_project_html(CloudProject.model_validate(project_payload()))
    expected = {
        "custom",
        "ai-machine-learning",
        "analytics",
        "compute",
        "containers",
        "databases",
        "devops",
        "hybrid-multicloud",
        "identity",
        "integration",
        "internet-of-things",
        "energy",
        "industrial",
        "facilities",
        "governance",
        "mobile",
        "networking",
        "power-platform",
        "security",
        "storage",
        "web",
    }

    assert html.count('class="category-icon"') == 21
    assert {value for value in re.findall(r'data-category-icon="([^"]+)"', html)} == expected
    assert html.count("md-expand-icon chevron-icon") == 21
    assert '<span class="category-glyph"' not in html

    mark = re.search(r'<img class="provider-mark" src="data:image/svg\+xml;base64,([^"]+)"', html)
    assert mark is not None
    decoded = __import__("base64").b64decode(mark.group(1)).decode("utf-8")
    assert 'xmlns="http://www.w3.org/2000/svg"' in decoded
    assert "currentColor" not in decoded
    assert "#0078d4" in decoded
    assert 'viewBox="0 0 96 96"' in decoded
    assert "linearGradient" in decoded


def test_inverse_hetzner_service_artwork_has_a_brand_backplate_for_light_surfaces() -> None:
    inverse_icons = {
        "ax-server",
        "dns-console",
        "domain-registration",
        "ex-server",
        "gpu-server",
        "load-balancer",
        "managed-server",
        "object-storage",
        "rx-server",
        "ssl-certificate",
        "storage-box",
        "sx-server",
        "webhosting",
    }
    icons = load_icon_set("hetzner")

    for slug in sorted(inverse_icons):
        icon = icons[slug]
        artwork = icon.path.read_text(encoding="utf-8")
        assert hashlib.sha256(icon.path.read_bytes()).hexdigest() == icon.sha256
        assert re.search(
            r'<(?:circle|rect)\b[^>]*fill="#D50(?:C2D|F2E)"',
            artwork,
            flags=re.IGNORECASE,
        ), f"{slug} remains invisible on the light provider sidebar"


def test_aws_sidebar_lists_every_reviewed_service_in_the_full_canonical_category_set() -> None:
    payload = project_payload()
    payload.update(
        {
            "slug": "aws-api",
            "title": "AWS API",
            "description": "Client traffic flows through AWS services.",
            "provider": "aws",
        }
    )
    catalog = load_sidebar_catalog("aws")
    reviewed = load_icon_set("aws")
    html = render_project_html(CloudProject.model_validate(payload))
    sidebar_ids = {
        component.id for category in catalog.categories for component in category.components
    }

    # 305 services, 419 + 47 resources (the deck's general icons among them)
    # and 13 group shapes: the deck's three tiers.
    assert len(reviewed) == 784
    assert {icon.slug for icon in reviewed} <= sidebar_ids
    assert catalog.component_count > len(reviewed)
    assert all(
        component.mapping_status == "mapped"
        for category in catalog.categories
        for component in category.components
    )
    assert len(catalog.categories) == 21
    assert "Power Platform" in [category.label for category in catalog.categories]
    library = embedded_library(html)
    assert (
        sum(component["provider"] in {"aws", "infragram"} for component in library["components"])
        == catalog.component_count
    )
    assert 'data-provider-label="AWS Diagrams"' in html
    assert 'data-category-id="power-platform"' in html
    assert catalog.categories[17].id == "power-platform"
    assert catalog.categories[17].components == ()
    assert "No components in the selected libraries" in html
    assert sum(
        component["componentKind"] == "boundary" and component["provider"] in {"aws", "infragram"}
        for component in library["components"]
    ) == sum(
        component.component_kind == "boundary"
        for category in catalog.categories
        for component in category.components
    )
    assert {
        "custom-section",
        "custom-boundary-aws-cloud",
        "custom-boundary-region",
        "custom-boundary-vpc",
        "custom-boundary-availability-zone",
        "custom-boundary-public-subnet",
        "custom-boundary-private-subnet",
        "custom-boundary-direct-connect-location",
        "custom-boundary-corporate-network",
    } <= sidebar_ids

    # navy letters for the light theme, white for the dark ones; the smile is orange in both
    marks = dict(
        (look, base64.b64decode(data).decode("utf-8"))
        for data, look in re.findall(
            r'<img class="provider-mark" src="data:image/svg\+xml;base64,([^"]+)"[^>]*data-mark-look="(\w+)"',
            html,
        )
    )
    assert set(marks) == {"light", "dark"}
    assert "#232f3e" in marks["light"] and "#ffffff" in marks["dark"]
    assert all("#F90" in mark for mark in marks.values())


def test_cloud_categories_use_clear_semantic_icons_for_ai_governance_devops_and_containers() -> (
    None
):
    html = render_project_html(CloudProject.model_validate(project_payload()))

    assert 'data-category-icon="ai-machine-learning" data-category-icon-kind="brain"' in html
    assert 'data-category-icon="analytics" data-category-icon-kind="bar-chart"' in html
    assert 'data-category-icon="governance" data-category-icon-kind="governance-scale"' in html
    assert 'data-category-icon="devops" data-category-icon-kind="ci-cd"' in html
    assert 'data-category-icon="containers" data-category-icon-kind="github-container"' in html
    assert '<path d="M15.5 13a3.5 3.5 0 0 0-3.5 3.5v1a3.5 3.5 0 0 0 7 0v-1.8"/>' in html
    assert '<path d="M9 12l-3-6l-3 6a3 3 0 0 0 6 0"/>' in html
    assert '<path d="M9.828 9.172a4 4 0 1 0 0 5.656' in html
    assert (
        '<path fill="currentColor" stroke="none" d="M13.152.682a2.251 2.251 0 0 1 2.269 0' in html
    )
    assert '<path d="M9.5 4.5A3.5 3.5 0 0 0 6 8v.7' not in html
    assert '<path d="M5 4v16M5 7h8' not in html
    assert '<path d="M3 7l6 5-6 5V7' not in html
    assert '<path d="M12 2l5 3v6l-5 3' not in html
    assert ".category>summary:hover .category-icon" in html
    # an open category takes Material's active indicator, not a tinted glyph
    assert ".category[open]>summary{background:var(--md-sys-color-surface-container-high)" in html
    assert ".component-card{cursor:grab}" in html


@pytest.mark.parametrize("provider", ["azure", "aws", "digitalocean", "hetzner", "kubernetes"])
def test_every_infrastructure_provider_uses_the_shared_workspace_theme(
    provider: str,
) -> None:
    payload = project_payload()
    payload["provider"] = provider
    payload["topology"] = {
        "id": "root",
        "name": "Infrastructure",
        "type": "group",
        "children": [
            {"id": "client", "name": "Client", "type": "client"},
            {"id": "service", "name": "Service", "type": "service"},
        ],
    }

    html = render_project_html(CloudProject.model_validate(payload))

    # Diagrams are only ever seen on white, so the workspace opens light.
    # Both palettes still ship: the toggle and ?theme= switch between them.
    assert '<body data-workspace-theme="light">' in html
    # the chrome's roles: dark on :root, light on the body (Plane's palette)
    assert "--md-sys-color-surface-container-low:#0E0F10" in html
    assert "--md-sys-color-surface-container-low:#F4F5F5" in html
    assert "--md-sys-color-primary-container:#006399" in html
    # and the canvas palette the runtime paints the drawing with
    assert "--canvas-bg:#141414" in html
    assert "--diagram-surface:#141414" in html
    assert "data-theme-toggle" in html
    assert 'aria-label="Theme: Light"' in html
    assert 'aria-label="Infrastructure components"' in html


def test_sidebar_collapses_to_an_icon_rail_and_previews_from_the_provider_logo() -> None:
    html = render_project_html(CloudProject.model_validate(project_payload()))

    assert 'id="provider-sidebar"' in html
    assert 'class="md-nav-item provider-brand"' in html
    assert "data-sidebar-logo-trigger" in html
    assert 'aria-controls="provider-sidebar"' in html
    assert 'aria-expanded="true"' in html
    assert 'class="provider-name"' in html
    assert 'class="sidebar-state-icon" data-sidebar-control-icon' in html
    assert '<rect x="1.75" y="2.25" width="12.5" height="11.5" rx="2"/>' in html
    assert '<path d="M5.75 2.25v11.5"/>' in html
    assert '<path d="M10 3L5 8l5 5"/>' not in html
    assert "body.sidebar-collapsed .workspace{grid-template-columns:56px minmax(0,1fr)}" in html
    assert "body.sidebar-collapsed.sidebar-preview .provider-sidebar" in html
    assert "sidebarLogoTrigger.addEventListener('pointerenter'" in html
    assert "sidebar.addEventListener('pointerleave'" in html
    assert "data-sidebar-toggle" not in html
    assert 'class="document-title"' not in html


def test_sidebar_hides_scrollbar_chrome_without_disabling_scrolling() -> None:
    html = render_project_html(CloudProject.model_validate(project_payload()))

    assert "--md-sys-color-surface-container:" in html
    assert "--canvas-bg:#141414" in html
    assert (
        "flex-direction:column;border-right:1px solid var(--md-sys-color-outline-variant);background:var(--md-sys-color-surface-container-low)"
        in html
    )
    assert (
        ".editor-main{position:relative;display:grid;grid-template-rows:auto minmax(0,1fr) auto;min-width:0"
        in html
    )
    assert "background-color:var(--canvas-bg)" in html
    assert ".category-list{min-height:0;overflow:auto" in html
    assert "scrollbar-width:none" in html
    assert ".category-list::-webkit-scrollbar{width:0;height:0}" in html


def test_sidebar_component_icons_do_not_precede_the_export_diagram_svg() -> None:
    html = render_project_html(CloudProject.model_validate(project_payload()))
    svg = extract_svg(html)

    assert '<title id="azure-api-title">Azure API</title>' in svg
    assert "provider-sidebar" not in svg


def test_presentation_and_fit_presets_change_the_rendered_canvas() -> None:
    slide = project_payload()
    slide["presentation"]["size"] = "slide-16x9"
    slide_html = render_project_html(CloudProject.model_validate(slide))

    fitted = project_payload()
    fitted["presentation"]["size"] = "fit"
    fit_html = render_project_html(CloudProject.model_validate(fitted))

    assert 'viewBox="0 0 1280 720"' in slide_html
    assert 'viewBox="0 0 960 600"' not in fit_html
    # A slide takes the editor's type like every other size: the editor,
    # which draws every export, has one set of sizes.
    assert 'font-size="16"' not in extract_svg(slide_html)


def test_fixed_preset_rejects_content_that_would_grow_the_canvas() -> None:
    payload = project_payload()
    payload["topology"]["children"] = [
        {"id": f"node-{index}", "name": f"Node {index}", "type": "service"} for index in range(6)
    ]

    with pytest.raises(ExportError, match="exceeds doc-inline"):
        render_project_html(CloudProject.model_validate(payload))


def test_provider_mark_clears_the_legend_footer() -> None:
    payload = project_payload()
    payload["presentation"]["size"] = "doc-wide"
    payload["presentation"]["legend"] = [["solid", "Request flow"]]

    html = render_project_html(CloudProject.model_validate(payload))
    mark = re.search(
        r"<!-- Brand mark -->\s*<svg data-brand-mark=\"\" x=\"\d+\" y=\"(\d+)\" "
        r"width=\"\d+\" height=\"(\d+)\"",
        html,
    )

    assert mark is not None
    mark_y, mark_height = (int(value) for value in mark.groups())
    legend_y = 720 - 84
    assert mark_y + mark_height <= legend_y - 12


def test_a_drawing_of_shared_parts_alone_carries_no_vendor_mark() -> None:
    """A homelab or another cloud's estate drawn from shared parts falls back
    to the first provider for its theme; the vendor's lockup there would
    credit a vendor the picture does not show."""
    from infragram.author import Diagram, Edge
    from infragram.nodes import infragram as shared
    from infragram.nodes.frames import generic

    with Diagram("Shared parts only", slug="shared-parts-only") as diagram:
        with generic.Cloud("Another cloud"):
            browser = shared.web.BrowserClient("Browser")
            edge = shared.networking.CDNEdge("Edge")
        browser >> Edge("HTTPS") >> edge
    project = diagram.to_project()
    drawn = re.compile(r"<svg data-brand-mark=")

    assert not drawn.search(render_project_html(project))
    assert not drawn.search(render_project_svg(project))
    # a drawing that names its provider with plain cards keeps the mark
    assert drawn.search(render_project_html(CloudProject.model_validate(project_payload())))


def test_frame_lines_weigh_every_frame_alike_in_every_export() -> None:
    """``presentation.frame_lines`` multiplies each frame's own width: the
    static picture, the editor page's state and draw.io all draw it."""
    from infragram.builders.scene import FRAME_LINES
    from infragram.exports.drawio import render_project_drawio

    border = re.compile(
        r'rx="[\d.]+" fill="[^"]*"/>\s*<path d="[^"]*" fill="none" stroke="[^"]*" '
        r'stroke-width="([\d.]+)"'
    )
    template = (
        Path(__file__).parents[2] / "plugin/skills/infragram-architect/assets/templates/cloud"
    )
    thin = CloudProject.model_validate_json(
        (template / "azure-aks-baseline.infragram.json").read_text(encoding="utf-8")
    )
    thick = thin.model_copy(
        update={"presentation": thin.presentation.model_copy(update={"frame_lines": "thick"})}
    )
    widths = [float(width) for width in border.findall(render_project_svg(thin))]
    assert widths, "the picture draws its frames"
    assert [float(width) for width in border.findall(render_project_svg(thick))] == [
        pytest.approx(width * FRAME_LINES["thick"]) for width in widths
    ]
    assert '"frameLines":"thick"' in render_project_html(thick).replace(" ", "")
    drawio = re.compile(r"container=1;[^\"]*strokeWidth=([\d.]+);")
    assert [float(width) for width in drawio.findall(render_project_drawio(thick))] == [
        pytest.approx(float(width) * FRAME_LINES["thick"])
        for width in drawio.findall(render_project_drawio(thin))
    ]
    with pytest.raises(ValidationError):
        CloudProject.model_validate({**project_payload(), "presentation": {"frame_lines": "heavy"}})


def test_extract_svg_returns_only_the_first_diagram() -> None:
    html = '<main><svg viewBox="0 0 4 4"><title>A</title></svg><svg><title>B</title></svg></main>'

    assert extract_svg(html) == '<svg viewBox="0 0 4 4"><title>A</title></svg>'


def test_extract_svg_rejects_non_diagram_html() -> None:
    with pytest.raises(ExportError, match="does not contain an SVG"):
        extract_svg("<html><body>Nothing here</body></html>")


def test_standalone_svg_is_well_formed_accessible_xml() -> None:
    html = render_project_html(CloudProject.model_validate(project_payload()))

    svg = standalone_svg(html)
    root = ET.fromstring(svg)
    children = list(root)

    assert svg.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["viewBox"] == "0 0 960 600"
    assert children[0].tag == "{http://www.w3.org/2000/svg}title"
    assert "fonts.googleapis.com" not in svg, "the faces travel with the picture"
    # the face it draws with, and no other: this picture is set in Inter
    assert "@font-face{font-family:'Inter'" in svg
    assert "data:font/woff2;base64," in svg
    assert svg.count("<defs>") == 1


def test_the_static_picture_of_a_badged_frame_is_xml() -> None:
    """A frame's corner badge was written with attributes that carried no
    value, which HTML allows and XML does not: a browser opening the .svg
    drew nothing past the first badge."""
    from infragram.author import Diagram
    from infragram.exports import render_project_svg
    from infragram.nodes import azure
    from infragram.nodes.frames import azure as frames

    with Diagram("Badged subnet", "A subnet that wears its NSG.") as diagram:
        with (
            frames.VNet("vnet"),
            frames.Subnet("snet-web").badge(azure.NetworkSecurityGroups, label="nsg-web"),
        ):
            azure.VirtualMachine("vm-web")
    svg = render_project_svg(diagram.to_project())
    assert "data-frame-badge" in svg
    ET.fromstring(svg)


def test_standalone_svg_requires_a_viewbox() -> None:
    with pytest.raises(ExportError, match="viewBox"):
        standalone_svg("<svg><title>Missing frame</title></svg>")


def test_standalone_svg_adds_namespace_and_defs_without_moving_the_title() -> None:
    svg = standalone_svg(
        '<svg viewBox="0 0 40 40" role="img"><title id="x-title">X</title>'
        '<desc id="x-desc">Example.</desc><rect width="40" height="40"/>'
        "<text font-family=\"'Inter', sans-serif\">X</text></svg>"
    )
    root = ET.fromstring(svg)

    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert list(root)[0].tag == "{http://www.w3.org/2000/svg}title"
    assert svg.count("<defs>") == 1


def test_export_project_writes_template_html_and_svg_from_one_render(tmp_path: Path) -> None:
    project = CloudProject.model_validate(project_payload())

    result = export_project(project, tmp_path, formats=("template", "html", "svg"))

    assert result.template == tmp_path / "azure-api.infragram.json"
    assert result.html == tmp_path / "azure-api.html"
    assert result.svg == tmp_path / "azure-api.svg"
    assert result.png is None
    assert result.template.is_file()
    assert result.html.is_file()
    assert ET.fromstring(result.svg.read_text(encoding="utf-8")).tag.endswith("svg")


def test_export_project_uses_an_injected_png_renderer(tmp_path: Path) -> None:
    calls: list[tuple[Path, Path, float]] = []

    def fake_renderer(source: Path, output: Path, scale: float) -> None:
        calls.append((source, output, scale))
        output.write_bytes(b"PNG")

    project = CloudProject.model_validate(project_payload())
    result = export_project(
        project,
        tmp_path,
        formats=("html", "png"),
        scale=3,
        png_renderer=fake_renderer,
    )

    assert result.png == tmp_path / "azure-api.png"
    assert result.png.read_bytes() == b"PNG"
    # Drawn in the staging folder beside the output, then moved into place.
    assert [(source.name, output.name, scale) for source, output, scale in calls] == [
        ("azure-api.html", "azure-api.png", 3)
    ]
    assert calls[0][1].parent.parent == tmp_path
    assert sorted(path.name for path in tmp_path.iterdir()) == ["azure-api.html", "azure-api.png"]


@pytest.mark.parametrize("scale", [0.5, 0, 4.1])
def test_export_project_rejects_unsafe_png_scales(tmp_path: Path, scale: float) -> None:
    project = CloudProject.model_validate(project_payload())

    with pytest.raises(ExportError, match="between 1 and 4"):
        export_project(project, tmp_path, formats=("png",), scale=scale)


def test_export_project_rejects_unknown_formats(tmp_path: Path) -> None:
    project = CloudProject.model_validate(project_payload())

    with pytest.raises(
        ExportError,
        match=r"unsupported export format: psd; use drawio, html, png, svg, "
        r"template, terraform, terraform-modules",
    ):
        export_project(project, tmp_path, formats=("psd",))


def test_export_project_requires_a_format(tmp_path: Path) -> None:
    project = CloudProject.model_validate(project_payload())

    with pytest.raises(ExportError, match="at least one"):
        export_project(project, tmp_path, formats=())


def test_export_project_protects_existing_artifacts(tmp_path: Path) -> None:
    project = CloudProject.model_validate(project_payload())
    export_project(project, tmp_path, formats=("html",))
    # What the last export wrote, untouched since, is simply replaced.
    export_project(project, tmp_path, formats=("html",))

    page = tmp_path / "azure-api.html"
    page.write_text(page.read_text(encoding="utf-8") + "<!-- edited -->", encoding="utf-8")
    with pytest.raises(ExportError, match="refusing to overwrite"):
        export_project(project, tmp_path, formats=("html",))

    replaced = export_project(project, tmp_path, formats=("html",), overwrite=True)
    assert replaced.html == page


def test_export_project_never_replaces_a_file_it_did_not_write(tmp_path: Path) -> None:
    project = CloudProject.model_validate(project_payload())
    (tmp_path / "azure-api.html").write_text("someone else's page", encoding="utf-8")
    with pytest.raises(ExportError, match="refusing to overwrite"):
        export_project(project, tmp_path, formats=("html",))
    assert (tmp_path / "azure-api.html").read_text(encoding="utf-8") == "someone else's page"


def test_a_mark_drawn_differently_on_dark_themes_ships_both_looks() -> None:
    """AWS's wordmark is navy on the light theme and white on the dark ones;
    a library with one mark for both ships one."""
    from infragram.editor import load_sidebar_catalog

    aws = load_sidebar_catalog("aws")
    light = base64.b64decode(aws.provider_mark_uri.split(",", 1)[1]).decode("utf-8")
    dark = base64.b64decode(aws.provider_mark_dark_uri.split(",", 1)[1]).decode("utf-8")
    assert "#232f3e" in light and "#ffffff" not in light.lower()
    assert "#ffffff" in dark and "#232f3e" not in dark
    assert load_sidebar_catalog("azure").provider_mark_dark_uri == ""


def test_the_svg_export_refuses_a_picture_that_outgrew_its_preset() -> None:
    reset_ids()
    elements = [compute.VirtualMachine(f"VM {n}") for n in range(12)]
    project = compose.to_project(
        elements, slug="wide", title="Wide", description="x.", size="doc-inline"
    )
    with pytest.raises(ExportError, match="exceeds doc-inline"):
        render_project_svg(project)
