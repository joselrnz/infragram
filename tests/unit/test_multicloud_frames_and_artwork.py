"""Multicloud frames and sidebar artwork: each provider's boundaries, presets and icons draw."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

from infragram.catalog import (
    ARCHITECTURE_BOUNDARY_GROUPS,
    ARCHITECTURE_BOUNDARY_SPECS,
    ARCHITECTURE_FRAME_PRESETS,
)
from infragram.editor import load_sidebar_catalog
from infragram.editor.artwork import artwork_bytes
from infragram.editor.shell import library_catalog_from_html
from infragram.exports import render_project_html
from infragram.projects import CloudProject

ROOT = Path(__file__).parents[2]
TEMPLATE = (
    ROOT
    / "plugin"
    / "skills"
    / "infragram-architect"
    / "assets"
    / "templates"
    / "cloud"
    / "multicloud-base.infragram.json"
)


def _json_script(html: str, element_id: str) -> dict:
    match = re.search(
        rf'<script type="application/json" id="{element_id}"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def test_multicloud_starter_does_not_render_a_canvas_legend() -> None:
    project = CloudProject.load(TEMPLATE)
    html = render_project_html(project)

    assert project.presentation.legend == ()
    assert "Cross-provider application flow" not in html
    assert "<!-- Legend strip -->" not in html


def test_editor_places_masked_edge_labels_on_open_connector_segments() -> None:
    html = render_project_html(CloudProject.load(TEMPLATE))

    assert 'class="edge-label-mask"' in html
    assert "const straightHorizontal" in html
    assert "const straightVertical" in html
    assert "side = 'vertical'" in html
    assert 'data-edge-label="${escapeText(item.edge.id)}"' in html
    assert 'data-placement-mode="${labelPosition.mode}"' in html


def test_multicloud_template_uses_the_official_kubernetes_brand_mark() -> None:
    project = CloudProject.load(TEMPLATE)
    html = render_project_html(project)
    state = _json_script(html, "infragram-editor-state")
    library = library_catalog_from_html(html)

    node = next(item for item in state["nodes"] if item["id"] == "kubernetes-platform")
    component = next(
        item for item in library["components"] if item["qualifiedId"] == "kubernetes:kubernetes"
    )
    artwork = artwork_bytes(component["iconUri"]).decode("utf-8")

    assert node["componentQualifiedId"] == "kubernetes:kubernetes"
    assert node["iconUri"] == component["iconUri"]
    assert "#326ce5" in artwork.casefold()
    assert "viewBox" in artwork


def test_digitalocean_frames_use_upstream_diagrams_vpc_and_doks_symbols_in_their_own_ink() -> None:
    library = library_catalog_from_html(render_project_html(CloudProject.load(TEMPLATE)))
    components = {component["serviceId"]: component for component in library["components"]}

    doks = components["custom-boundary-do-doks"]
    kubernetes = components["custom-boundary-kubernetes-cluster"]
    generic = components["custom-boundary-cluster"]
    digitalocean_vpc = components["custom-boundary-do-vpc"]
    generic_vpc = components["custom-boundary-vpc"]

    assert doks["boundaryStyle"]["iconUri"] != kubernetes["boundaryStyle"]["iconUri"]
    assert doks["boundaryStyle"]["iconUri"] != generic["boundaryStyle"]["iconUri"]
    doks_artwork = artwork_bytes(doks["boundaryStyle"]["iconUri"]).decode("utf-8")
    vpc_artwork = artwork_bytes(digitalocean_vpc["boundaryStyle"]["iconUri"]).decode("utf-8")

    assert "M12 8V4" in doks_artwork
    assert "#0055b8" not in doks_artwork.casefold()
    # DigitalOcean frames take a paper tab (theme ``tab_fill: paper``). The tab
    # is the paper, so the vendor's badge paints itself there and keeps the
    # colour it ships with, never reversed out in white. Repainting it in the
    # frame's ink flattened full-colour vendor artwork -- it drew Azure's cyan
    # resource-group cube grey -- and disagreed with the static renderer, which
    # never repainted. See test_frame_badge_colours.
    assert doks["boundaryStyle"]["tabFill"].casefold() == "#ffffff"
    assert "#0069ff" in doks_artwork.casefold()
    assert "#ffffff" not in doks_artwork.casefold()
    assert digitalocean_vpc["boundaryStyle"]["iconUri"] != generic_vpc["boundaryStyle"]["iconUri"]
    assert 'viewBox="0 0 256 256"' in vpc_artwork
    assert "data:image/png;base64," in vpc_artwork


def test_custom_library_includes_interactive_architecture_boundaries_for_every_provider() -> None:
    catalog = load_sidebar_catalog("azure")
    custom = next(category for category in catalog.categories if category.id == "custom")
    components = {component.name: component for component in custom.components}

    expected = {
        "Cloud boundary",
        "On-premises site",
        "AWS account",
        "Amazon VPC",
        "Azure subscription",
        "Azure virtual network",
        "Google Cloud project",
        "Google Cloud VPC",
        "DigitalOcean VPC",
        "OCI compartment",
        "IBM Cloud resource group",
        "Alibaba Cloud VPC",
        "Kubernetes cluster",
        "Kubernetes namespace",
        "Hetzner network",
    }

    assert expected <= set(components)
    assert all(components[name].component_kind == "boundary" for name in expected)
    assert all(components[name].boundary_kind for name in expected)


def test_architecture_boundaries_are_grouped_and_use_site_to_site_aws_styles() -> None:
    project = CloudProject.load(TEMPLATE)
    library = library_catalog_from_html(render_project_html(project))
    frames = {
        component["serviceId"]: component
        for component in library["components"]
        if component["componentKind"] == "boundary"
    }

    # Core frames first, then one group per library, in the catalog's order.
    assert library["frameGroups"] == [
        {"id": group_id, "label": label, "order": order}
        for order, (group_id, label) in enumerate(ARCHITECTURE_BOUNDARY_GROUPS)
    ]
    assert library["frameGroups"][0] == {"id": "generic", "label": "Core frames", "order": 0}
    assert library["frameGroups"][1] == {"id": "onprem", "label": "Local & On-Premises", "order": 1}

    aws_cloud = frames["custom-boundary-aws-cloud"]
    aws_region = frames["custom-boundary-region"]
    aws_vpc = frames["custom-boundary-vpc"]
    public_subnet = frames["custom-boundary-public-subnet"]

    assert aws_cloud["frameGroup"] == "aws"
    assert aws_cloud["boundaryStyle"]["stroke"] == "#232f3e"
    # Light-only: the editor carries no second stroke for a dark canvas.
    assert "darkStroke" not in aws_cloud["boundaryStyle"]
    assert aws_cloud["boundaryStyle"]["strokeWidth"] == 1.8
    assert aws_region["boundaryStyle"]["stroke"] == "#00a4a6"
    # dotted per the AWS Architecture Icons deck
    assert aws_region["boundaryStyle"]["dash"] == "2,3"
    assert aws_vpc["boundaryStyle"]["stroke"] == "#8c4fff"
    assert aws_vpc["boundaryStyle"]["dash"] is None
    assert aws_vpc["boundaryStyle"]["tabbed"] is True
    assert aws_vpc["boundaryStyle"]["iconUri"].startswith("data:image/svg+xml;")
    assert public_subnet["boundaryStyle"]["stroke"] == "#7aa116"
    assert public_subnet["boundaryStyle"]["fill"].startswith("rgba(122,161,22,")
    assert aws_vpc["defaultSize"] == {"width": 400, "height": 280}
    assert public_subnet["hierarchyLevel"] > aws_vpc["hierarchyLevel"]


def test_azure_frames_use_distinct_official_service_icons() -> None:
    project = CloudProject.load(TEMPLATE)
    library = library_catalog_from_html(render_project_html(project))
    azure_frames = [
        component for component in library["components"] if component.get("frameGroup") == "azure"
    ]

    assert len(azure_frames) == 10
    assert all(frame["boundaryStyle"]["tabbed"] for frame in azure_frames)
    icon_uris = {frame["boundaryStyle"]["iconUri"] for frame in azure_frames}
    assert len(icon_uris) == len(azure_frames)
    assert all(uri.startswith("data:image/svg+xml;") for uri in icon_uris)
    for frame in azure_frames:
        preview = artwork_bytes(frame["iconUri"]).decode("utf-8")
        assert "<image " in preview
        assert "data:image/svg+xml;" in preview


def test_every_architecture_frame_has_a_visible_semantic_icon() -> None:
    project = CloudProject.load(TEMPLATE)
    library = library_catalog_from_html(render_project_html(project))
    frames = [
        component
        for component in library["components"]
        if component.get("componentKind") == "boundary" and component.get("frameGroup")
    ]

    assert len(frames) == len(ARCHITECTURE_BOUNDARY_SPECS)
    assert all(frame["boundaryStyle"]["tabbed"] for frame in frames)
    assert all(frame["boundaryStyle"]["iconUri"] for frame in frames)
    for group in library["frameGroups"]:
        group_frames = [frame for frame in frames if frame["frameGroup"] == group["id"]]
        assert len({frame["boundaryStyle"]["iconUri"] for frame in group_frames}) >= 3


def test_editor_runtime_declares_nested_custom_sections_and_frame_galleries() -> None:
    html = render_project_html(CloudProject.load(TEMPLATE))

    assert "data-component-section" in html
    assert "architecture-frames" in html
    assert "data-frame-group" in html
    assert "frame-grid" in html
    assert "renderCustomCategory" in html
    assert "const iconOnly = node.displayMode === 'icon'" in html
    assert "const iconY = iconOnly" in html
    assert "const titleY = node.height / 2 - 2" in html
    assert "const detailY = node.height / 2 + 14" in html


def test_editor_declares_compact_frames_provider_presets_and_full_selection_tools() -> None:
    html = render_project_html(CloudProject.load(TEMPLATE))
    library = library_catalog_from_html(html)

    presets = {preset["id"]: preset for preset in library["framePresets"]}
    # Every starter stack the catalog defines reaches the editor, one per library.
    assert set(presets) == {preset["id"] for preset in ARCHITECTURE_FRAME_PRESETS}
    assert {
        "aws-network-foundation",
        "azure-landing-zone",
        "onprem-datacenter-foundation",
        "openstack-foundation",
        "vmware-vsphere-foundation",
        "proxmox-ve-foundation",
    } <= set(presets)
    assert presets["gcp-network-foundation"]["componentIds"] == [
        "custom-boundary-gcp-organization",
        "custom-boundary-gcp-folder",
        "custom-boundary-gcp-project",
        "custom-boundary-gcp-vpc",
        "custom-boundary-gcp-region",
        "custom-boundary-gcp-subnet",
    ]
    assert presets["azure-landing-zone"]["componentIds"] == [
        "custom-boundary-azure-tenant",
        "custom-boundary-azure-management-group",
        "custom-boundary-azure-subscription",
        "custom-boundary-azure-resource-group",
        "custom-boundary-azure-vnet",
        "custom-boundary-azure-subnet",
    ]
    assert presets["aws-network-foundation"]["componentIds"] == [
        "custom-boundary-aws-cloud",
        "custom-boundary-region",
        "custom-boundary-vpc",
        "custom-boundary-availability-zone",
        "custom-boundary-public-subnet",
    ]
    assert presets["aws-network-foundation"].get("layout") != "detached"
    assert presets["aws-network-foundation"]["layoutBase"] == "azure-landing-zone"
    assert presets["aws-network-foundation"]["frameSizes"] == [
        {"width": 592, "height": 472},
        {"width": 544, "height": 424},
        {"width": 496, "height": 376},
        {"width": 448, "height": 328},
        {"width": 256, "height": 144},
    ]
    assert presets["digitalocean-application"]["label"] == ("DigitalOcean DOKS foundation")
    assert presets["digitalocean-application"]["componentIds"] == [
        "custom-boundary-do-team",
        "custom-boundary-do-project",
        "custom-boundary-do-region",
        "custom-boundary-do-vpc",
        "custom-boundary-do-doks",
        "custom-boundary-do-cluster-subnet",
        "custom-boundary-do-service-subnet",
        "custom-boundary-do-node-pool",
        "custom-boundary-do-workloads",
    ]
    components = {component["serviceId"]: component for component in library["components"]}
    digitalocean_team = components["custom-boundary-do-team"]
    assert digitalocean_team["boundaryKind"] == "team"
    assert digitalocean_team["subtitle"] == ("DigitalOcean resource and billing boundary")
    assert (
        digitalocean_team["boundaryStyle"]["iconUri"]
        != components["custom-boundary-gcp-organization"]["boundaryStyle"]["iconUri"]
    )
    digitalocean_project = components["custom-boundary-do-project"]
    assert digitalocean_project["subtitle"] == ("DigitalOcean resource grouping boundary")
    assert (
        digitalocean_project["boundaryStyle"]["iconUri"]
        != components["custom-boundary-gcp-project"]["boundaryStyle"]["iconUri"]
    )
    project_icon = artwork_bytes(digitalocean_project["boundaryStyle"]["iconUri"]).decode("utf-8")
    assert "m18.41 0.48999" in project_icon
    # Paper tab: the tab is the paper and the vendor's badge paints itself, so
    # its own colour survives and it is never white. This used to repaint the
    # glyph in the frame's ink, which flattened full-colour vendor artwork --
    # it drew Azure's cyan resource-group cube grey -- and disagreed with the
    # static renderer, which never repainted. See test_frame_badge_colours.
    assert digitalocean_project["boundaryStyle"]["tabFill"].casefold() == "#ffffff"
    assert 'fill="#005dff"' in project_icon.casefold()
    assert 'fill="#ffffff"' not in project_icon.casefold()
    assert presets["digitalocean-application"]["frameSizes"] == [
        {"width": 1320, "height": 960},
        {"width": 1272, "height": 912},
        {"width": 1224, "height": 864},
        {"width": 1000, "height": 720},
        {"width": 928, "height": 592},
        {"width": 880, "height": 336},
        {"width": 880, "height": 144},
        {"width": 376, "height": 280},
        {"width": 432, "height": 280},
    ]
    assert [
        placement["parentIndex"]
        for placement in presets["digitalocean-application"]["framePlacements"]
    ] == [None, 0, 1, 2, 3, 4, 4, 5, 5]
    placements = presets["digitalocean-application"]["framePlacements"]
    sizes = presets["digitalocean-application"]["frameSizes"]

    def horizontal_center(index: int) -> int:
        return placements[index]["x"] + sizes[index]["width"] // 2

    assert horizontal_center(3) == horizontal_center(4)
    assert horizontal_center(4) == horizontal_center(5)
    assert horizontal_center(4) == horizontal_center(6)
    assert placements[7]["x"] - placements[5]["x"] == 24
    assert placements[8]["x"] - (placements[7]["x"] + sizes[7]["width"]) == 24
    assert (placements[5]["x"] + sizes[5]["width"] - placements[8]["x"] - sizes[8]["width"]) == 24
    assert [node["qualifiedId"] for node in presets["digitalocean-application"]["nodes"]] == [
        "infragram:custom-resource",
        "digitalocean:load-balancer",
        "digitalocean:kubernetes",
        "digitalocean:droplets",
        "digitalocean:droplets",
        "digitalocean:droplets",
        "kubernetes:ing",
        "kubernetes:deploy",
        "kubernetes:svc",
        "kubernetes:pvc",
        "digitalocean:volumes",
    ]
    kubernetes_workloads = presets["digitalocean-application"]["nodes"][6:10]
    components_by_qualified_id = {
        component["qualifiedId"]: component for component in library["components"]
    }
    assert all(
        components_by_qualified_id[node["qualifiedId"]]["iconUri"] for node in kubernetes_workloads
    )
    workers = presets["digitalocean-application"]["nodes"][3:6]
    assert [worker["name"] for worker in workers] == [
        "DOKS worker node 1",
        "DOKS worker node 2",
        "DOKS worker node 3",
    ]
    assert all(worker["parentFrameIndex"] == 7 for worker in workers)
    assert all(worker["x"] == sizes[7]["width"] // 2 for worker in workers)
    assert presets["digitalocean-application"]["nodes"][1]["parentFrameIndex"] == 3
    assert presets["digitalocean-application"]["nodes"][2]["parentFrameIndex"] == 2
    assert presets["digitalocean-application"]["nodes"][2] == {
        "qualifiedId": "digitalocean:kubernetes",
        "parentFrameIndex": 2,
        "name": "Managed DOKS control plane",
        "detail": "DigitalOcean-managed · HA · Kubernetes API",
        "x": 360,
        "y": 104,
        "width": 320,
        "height": 64,
    }
    assert presets["digitalocean-application"]["nodes"][8]["parentFrameIndex"] == 6
    assert presets["digitalocean-application"]["nodes"][10]["parentFrameIndex"] == 2
    assert presets["digitalocean-application"]["nodes"][10]["x"] == 1080
    assert presets["digitalocean-application"]["nodes"][10]["width"] == 256
    assert presets["digitalocean-application"]["nodes"][0]["y"] == 216
    assert presets["digitalocean-application"]["nodes"][1]["y"] == 48
    workloads = {
        node["name"]: node
        for node in presets["digitalocean-application"]["nodes"]
        if node["parentFrameIndex"] == 8
    }
    assert [
        (workloads[name]["x"], workloads[name]["y"])
        for name in (
            "Gateway / Ingress controller",
            "PersistentVolumeClaim",
            "Application Deployment",
        )
    ] == [(216, 68), (216, 140), (216, 212)]
    assert all(node["width"] == 320 for node in workloads.values())
    assert all(node["height"] == 52 for node in workloads.values())
    assert [
        connection["label"] for connection in presets["digitalocean-application"]["connections"]
    ] == [
        "HTTPS traffic",
        "LoadBalancer service",
        "Route",
        "Endpoints",
        "Mount",
        "CSI volume",
        "Kubernetes API",
    ]
    assert presets["digitalocean-application"]["connections"][2]["sourcePort"] == "bottom"
    assert presets["digitalocean-application"]["connections"][4] == {
        "sourceNodeIndex": 7,
        "targetNodeIndex": 9,
        "sourcePort": "top",
        "targetPort": "bottom",
        "label": "Mount",
    }
    assert presets["digitalocean-application"]["connections"][-1]["targetNodeIndex"] == 3
    assert presets["digitalocean-application"]["connections"][-1]["sourcePort"] == "bottom"
    assert presets["digitalocean-application"]["connections"][-1]["targetPort"] == "top"
    assert presets["digitalocean-application"]["connections"][-1]["kind"] == "dashed"
    assert "layoutBase" not in presets["azure-landing-zone"]
    assert "frameSizes" not in presets["azure-landing-zone"]
    assert "editableFoundation" not in presets["azure-landing-zone"]
    for preset_id in {
        "aws-network-foundation",
        "gcp-network-foundation",
        "digitalocean-application",
        "oracle-cloud-foundation",
        "ibm-cloud-vpc",
        "alibaba-cloud-vpc",
        "kubernetes-workload",
        "hetzner-network",
    }:
        assert presets[preset_id]["layoutBase"] == "azure-landing-zone"
        assert presets[preset_id]["editableFoundation"] is True
    assert "cloud → region → vpc" in presets["aws-network-foundation"]["detail"].casefold()
    assert presets["hetzner-network"]["componentIds"] == [
        "custom-boundary-hetzner-project",
        "custom-boundary-hetzner-network",
        "custom-boundary-hetzner-zone",
        "custom-boundary-hetzner-subnet",
    ]

    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in html
    assert "data-selection-toolbar" in html
    assert "data-selection-count-chip" in html
    assert "data-selection-bbox" in html
    assert "data-marquee-selection" in html
    assert "data-frame-tree" in html
    assert 'data-arrange-action="to-front"' in html
    assert "data-arrange-selection-kind" in html
    assert "Align and distribute" in html
    assert 'data-arrange-action="align-left"' in html
    assert 'data-arrange-action="distribute-horizontal"' in html
    assert 'data-arrange-action="detach"' in html
    assert 'data-arrange-action="group"' in html
    assert 'data-editor-action="zoom-reset"' in html
    assert "pinch or wheel to zoom" in html
    assert "middle-drag to pan" in html
    assert "data-panning" in html
    assert "event.button !== 1" in html
    assert 'data-text-control="fontSize"' in html
    assert 'data-content-control="name"' in html
    assert 'data-content-control="detail"' in html
    assert 'data-display-mode="card"' in html
    assert 'data-display-mode="icon"' in html
    assert "node.displayMode === 'icon'" in html
    assert "data-canvas-context-menu" in html
    assert 'aria-label="Canvas actions"' in html
    assert 'data-context-action="edit-text"' in html
    assert 'data-context-action="display-card"' in html
    assert 'data-context-action="display-icon"' in html
    assert 'data-context-action="to-front"' in html
    assert 'data-context-action="detach"' in html
    assert 'data-context-action="lock"' in html
    assert 'data-context-action="delete"' in html
    assert "diagram.addEventListener('contextmenu'" in html
    assert "if (event.button === 2) return" in html
    assert "selectedBoundaryIds" in html
    assert "updateDropTarget" in html
    assert "applyZOrder" in html
    assert "finishMarquee" in html
    assert "boundaryStyle" in html


def test_every_provider_frame_preset_references_its_own_shipped_boundary_components() -> None:
    library = library_catalog_from_html(render_project_html(CloudProject.load(TEMPLATE)))
    frames = {
        component["serviceId"]: component
        for component in library["components"]
        if component["componentKind"] == "boundary"
    }

    for preset in library["framePresets"]:
        component_ids = preset["componentIds"]
        assert len(component_ids) == len(set(component_ids)), preset["id"]
        assert all(component_id in frames for component_id in component_ids), preset["id"]
        assert all(
            frames[component_id]["frameGroup"] == preset["group"] for component_id in component_ids
        ), preset["id"]
        hierarchy = [frames[component_id]["hierarchyLevel"] for component_id in component_ids]
        assert all(isinstance(level, int) and level >= 0 for level in hierarchy)
        assert hierarchy[0] <= hierarchy[-1]


def test_every_shipped_sidebar_component_has_decodable_svg_artwork() -> None:
    providers = (
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
    )

    for provider in providers:
        for category in load_sidebar_catalog(provider).categories:
            for component in category.components:
                artwork = artwork_bytes(component.icon_uri)
                assert artwork is not None and b"<svg" in artwork, (
                    provider,
                    category.id,
                    component.id,
                )


def test_hetzner_and_digitalocean_catalogs_keep_distinct_hash_tracked_svg_artwork() -> None:
    vendor_root = (
        ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "icons" / "vendors"
    )

    for provider, minimum, source_host in (
        ("hetzner", 26, "hetzner.com"),
        ("digitalocean", 53, "digitalocean.com"),
    ):
        provider_root = vendor_root / provider
        manifest = json.loads((provider_root / "catalog.json").read_text(encoding="utf-8"))
        icons = manifest["icons"]
        assert len(icons) >= minimum
        assert source_host in manifest["source"]["url"]
        hashes: set[str] = set()
        for icon in icons:
            path = provider_root / icon["file"]
            artwork = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert path.suffix == ".svg"
            assert "<svg" in artwork and "viewBox" in artwork
            assert "<script" not in artwork.casefold()
            assert digest == icon["sha256"]
            hashes.add(digest)
        assert len(hashes) == len(icons), f"{provider} contains duplicated service artwork"


def test_digitalocean_catalog_includes_every_unique_platform_page_artwork() -> None:
    root = (
        ROOT
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "icons"
        / "vendors"
        / "digitalocean"
    )
    manifest = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    icons = {icon["id"]: icon for icon in manifest["icons"]}

    assert {
        "ai-assistant",
        "community",
        "ip-ranges",
        "organizations",
        "platform-logomark",
        "product-lifecycle",
        "regional-availability",
        "release-notes",
        "service-level-agreements",
        "teams",
    } <= set(icons)
    assert all(
        icon["source_url"] == "https://docs.digitalocean.com/platform/"
        for slug, icon in icons.items()
        if slug
        in {
            "ai-assistant",
            "community",
            "ip-ranges",
            "organizations",
            "platform-logomark",
            "product-lifecycle",
            "regional-availability",
            "release-notes",
            "service-level-agreements",
            "teams",
        }
    )
    assert "DigitalOcean Resource Limits" in icons["projects"]["aliases"]
    assert "DigitalOcean Support Plans" in icons["support"]["aliases"]


def test_digitalocean_vpc_wraps_the_exact_diagrams_repository_png() -> None:
    root = (
        ROOT
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "icons"
        / "vendors"
        / "digitalocean"
    )
    manifest = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    vpc = next(icon for icon in manifest["icons"] if icon["id"] == "vpc")
    artwork = (root / vpc["file"]).read_text(encoding="utf-8")
    embedded = re.search(r"data:image/png;base64,([^\"]+)", artwork)

    assert embedded is not None
    assert 'viewBox="0 0 256 256"' in artwork
    assert hashlib.sha256(base64.b64decode(embedded.group(1))).hexdigest() == vpc["source_sha256"]
    assert vpc["source_sha256"] == (
        "32da0596e7ddce4c9cae2ae76543970ed611f816bd5a326c92eea5120bc82b9b"
    )


def test_runtime_declares_an_expandable_world_and_content_based_fit() -> None:
    html = render_project_html(CloudProject.load(TEMPLATE))

    assert "ensureCanvasExtent" in html
    assert "syncCanvasGeometry" in html
    assert "data-inspector-canvas" in html
    assert "contentBounds" in html
    assert "ResizeObserver" in html
    fit_source = html.split("const fitZoom", maxsplit=1)[1].split(
        "\n\n  document.querySelectorAll('[data-editor-action]')", maxsplit=1
    )[0]
    # the fit measures the cards, and the brand mark under them (fitBounds)
    assert "fitBounds()" in fit_source
    assert "let bounds = contentBounds();" in html.split("const fitBounds", maxsplit=1)[1]
    assert "preserveFit: true" in fit_source
    assert "requestAnimationFrame(() => requestAnimationFrame" in fit_source
    assert "if (!bounds)" in fit_source
    assert "maxNameChars" in html
    qualified = {
        component["qualifiedId"] for component in library_catalog_from_html(html)["components"]
    }
    for qualified_id in (
        "kubernetes:ing",
        "kubernetes:deploy",
        "kubernetes:svc",
        "kubernetes:pvc",
    ):
        assert qualified_id in qualified
