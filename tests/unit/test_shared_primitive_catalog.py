from __future__ import annotations

import base64

from infragram.catalog import (
    ARCHITECTURE_BOUNDARY_GROUPS,
    CLOUDFLARE_COMPONENT_SPECS,
    ONPREM_COMPONENT_SPECS,
    SHARED_PRIMITIVE_SPECS,
    load_composite_catalog,
    load_default_provider_registry,
)
from infragram.catalog.components import PRIMITIVE_INK
from infragram.editor import load_sidebar_catalog


def _component_map(provider: str, owner: str) -> dict[str, object]:
    catalog = load_sidebar_catalog(provider)
    return {
        component.id: component
        for category in catalog.categories
        for component in category.components
        if component.provider_id == owner
    }


def test_shared_primitive_library_exposes_every_shipped_architecture_icon() -> None:
    # A pinned count, so adding or losing a primitive is a decision somebody
    # made rather than a drift nobody noticed.
    assert len(SHARED_PRIMITIVE_SPECS) == 367
    assert {
        "public-users",
        "browser-client",
        "mobile-client",
        "desktop-client",
        "physical-server",
        "virtual-machine",
        "public-internet",
        "cdn-edge",
        "network-gateway",
        "message-queue",
        "backup-recovery",
        "kubernetes-pod",
        "api-endpoint",
        "ci-cd-pipeline",
        "ci-runner",
        "approval-gate",
        "signed-artifact",
        "oidc-token",
        "identity-provider",
        "brand-github-actions",
        "monitoring",
        "brand-docker",
        "brand-postgres",
        "data-airflow",
        "data-power-bi",
        "language-python",
        "statistics-qgis",
        "format-excel",
        "brand-valkey",
        "brand-redpanda",
    } <= {spec.service_id for spec in SHARED_PRIMITIVE_SPECS}


def test_shared_primitives_are_categorized_and_embedded_in_every_sidebar() -> None:
    components = _component_map("azure", "infragram")
    for spec in SHARED_PRIMITIVE_SPECS:
        component = components[spec.service_id]
        assert component.category_id == spec.category_id
        assert component.icon_uri.startswith("data:image/svg+xml;base64,")
        decoded = base64.b64decode(component.icon_uri.partition(",")[2])
        assert b"<svg" in decoded
        if not spec.icon_id.startswith("logo:"):
            assert b"currentColor" not in decoded
            assert PRIMITIVE_INK.encode() in decoded

    assert components["public-users"].category_id == "identity"
    assert components["browser-client"].category_id == "web"
    assert components["mobile-client"].category_id == "mobile"
    assert components["physical-server"].category_id == "compute"
    assert components["firewall"].category_id == "security"


def test_shared_primitives_are_deduplicated_in_multicloud_catalogs() -> None:
    catalog = load_composite_catalog(("azure", "aws", "gcp"))
    qualified_ids = [component.qualified_id for component in catalog.components]

    assert qualified_ids.count("infragram:public-users") == 1
    assert qualified_ids.count("infragram:browser-client") == 1
    assert catalog.search("public users")[0].qualified_id == "infragram:public-users"
    assert catalog.search("browser client")[0].qualified_id == "infragram:browser-client"


def test_local_on_premises_is_a_reviewed_provider_library() -> None:
    provider = load_default_provider_registry()["onprem"]

    assert provider.display_name == "Local & On-Premises"
    assert provider.short_name == "LOCAL"
    assert provider.kind == "on-prem"
    assert provider.coverage == "reviewed"


def test_local_on_premises_library_covers_core_datacenter_components() -> None:
    assert len(ONPREM_COMPONENT_SPECS) >= 20
    components = _component_map("onprem", "onprem")
    required = {
        "bare-metal-server",
        "hypervisor-host",
        "onprem-virtual-machine",
        "application-server",
        "database-server",
        "file-server",
        "backup-appliance",
        "directory-service",
        "network-switch",
        "router-gateway",
        "perimeter-firewall",
        "vpn-gateway",
        "workstation",
        "container-host",
        "kubernetes-cluster",
    }

    assert required <= set(components)
    for service_id in required:
        component = components[service_id]
        assert component.icon_uri.startswith("data:image/svg+xml;base64,")
        assert component.mapping_status == "mapped"

    assert len(components) >= 190
    assert {
        "compute-server",
        "network-cisco-router",
        "network-cisco-switch-l2",
        "network-pfsense",
        "network-opnsense",
        "proxmox-pve",
        "database-postgresql",
        "monitoring-prometheus",
        "monitoring-grafana",
        "queue-rabbitmq",
        "storage-ceph",
        "security-vault",
        "ci-jenkins",
        "gitops-argocd",
        "container-k3s",
    } <= set(components)
    assert all(component.mapping_status == "mapped" for component in components.values())


def test_local_on_premises_has_a_dedicated_architecture_frame_group() -> None:
    assert ("onprem", "Local & On-Premises") in ARCHITECTURE_BOUNDARY_GROUPS
    frames = _component_map("onprem", "infragram")
    local_frame_ids = {
        component.id for component in frames.values() if component.frame_group == "onprem"
    }

    assert {
        "custom-boundary-onprem-datacenter",
        "custom-boundary-onprem-site",
        "custom-boundary-onprem-network",
        "custom-boundary-onprem-subnet",
        "custom-boundary-onprem-security-zone",
        "custom-boundary-onprem-cluster",
        "custom-boundary-onprem-rack",
    } <= local_frame_ids


def test_cloudflare_is_a_dedicated_reviewed_provider_library() -> None:
    provider = load_default_provider_registry()["cloudflare"]
    components = _component_map("cloudflare", "cloudflare")

    assert provider.display_name == "Cloudflare"
    assert provider.kind == "cloud"
    assert provider.coverage == "reviewed"
    # The four product marks stay beside the 33 drawn service tiles: the
    # marks are the vendor's artwork, the tiles this project's own.
    assert len(CLOUDFLARE_COMPONENT_SPECS) == 4
    assert {"cloudflare", "workers", "pages", "workers-ai"} <= set(components)
    assert len(components) == 37
    assert {component.category_id for component in components.values()} == {
        "ai-machine-learning",
        "analytics",
        "compute",
        "databases",
        "integration",
        "networking",
        "security",
        "storage",
        "web",
    }
    assert components["cloudflare"].category_id == "networking"
    assert components["workers"].category_id == "compute"
    assert components["pages"].category_id == "web"
    assert components["workers-ai"].category_id == "ai-machine-learning"
    assert all(
        component.icon_uri.startswith("data:image/svg+xml;base64,")
        for component in components.values()
    )
