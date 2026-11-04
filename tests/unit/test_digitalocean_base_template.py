from __future__ import annotations

import json
from pathlib import Path

from infragram.exports import render_project_html
from infragram.projects import CloudProject

ROOT = Path(__file__).parents[2]
ASSETS = ROOT / "plugin" / "skills" / "infragram-architect" / "assets"
ICON_ROOT = ASSETS / "icons" / "vendors" / "digitalocean"
TEMPLATE = ASSETS / "templates" / "cloud" / "digitalocean-base.infragram.json"
KUBERNETES_TEMPLATE = (
    ASSETS / "templates" / "cloud" / "digitalocean-kubernetes-cluster.infragram.json"
)


UPSTREAM_NODES = {
    "compute": {
        "containers": "Containers",
        "docker": "Docker",
        "droplet-connect": "Droplet Connect",
        "droplet-snapshot": "Droplet Snapshot",
        "droplet": "Droplet",
        "k8s-cluster": "Kubernetes Cluster",
        "k8s-node-pool": "Kubernetes Node Pool",
        "k8s-node": "Kubernetes Node",
    },
    "database": {
        "dbaas-primary-standby-more": "DBaaS Primary, Standby & Read-only",
        "dbaas-primary": "DBaaS Primary",
        "dbaas-read-only": "DBaaS Read-only",
        "dbaas-standby": "DBaaS Standby",
    },
    "network": {
        "certificate": "Certificate",
        "domain-registration": "Domain Registration",
        "domain": "Domain",
        "firewall": "Firewall",
        "floating-ip": "Floating IP",
        "internet-gateway": "Internet Gateway",
        "load-balancer": "Load Balancer",
        "managed-vpn": "Managed VPN",
        "vpc": "VPC",
    },
    "storage": {
        "folder": "Folder",
        "space": "Space",
        "volume-snapshot": "Volume Snapshot",
        "volume": "Volume",
    },
}


def test_catalog_includes_every_canonical_diagrams_digitalocean_node() -> None:
    catalog = json.loads((ICON_ROOT / "catalog.json").read_text(encoding="utf-8"))
    by_id = {icon["id"]: icon for icon in catalog["icons"]}

    for category, nodes in UPSTREAM_NODES.items():
        for service_id, short_name in nodes.items():
            icon = by_id[service_id]
            assert icon["category"] == category
            assert icon["name"] == f"DigitalOcean {short_name}"
            assert icon["source_path"] == (f"resources/digitalocean/{category}/{service_id}.png")
            assert icon["source_url"].startswith(
                "https://github.com/mingrammer/diagrams/blob/364c61d"
            )
            assert icon["terms_url"].endswith("/mingrammer/diagrams/blob/master/LICENSE")
            asset = ICON_ROOT / icon["file"]
            assert asset.is_file()
            assert "data:image/png;base64," in asset.read_text(encoding="utf-8")


def test_generated_python_api_matches_upstream_digitalocean_modules() -> None:
    from infragram.nodes import digitalocean

    expected = {
        "compute": (
            "Containers",
            "Docker",
            "DropletConnect",
            "DropletSnapshot",
            "Droplet",
            "K8SCluster",
            "K8SNodePool",
            "K8SNode",
        ),
        "database": (
            "DbaasPrimaryStandbyMore",
            "DbaasPrimary",
            "DbaasReadOnly",
            "DbaasStandby",
        ),
        "network": (
            "Certificate",
            "DomainRegistration",
            "Domain",
            "Firewall",
            "FloatingIp",
            "InternetGateway",
            "LoadBalancer",
            "ManagedVpn",
            "Vpc",
        ),
        "storage": ("Folder", "Space", "VolumeSnapshot", "Volume"),
    }
    for module_name, class_names in expected.items():
        module = getattr(digitalocean, module_name)
        assert all(hasattr(module, class_name) for class_name in class_names)

    assert hasattr(digitalocean.containers, "K8SCluster")
    assert hasattr(digitalocean.networking, "LoadBalancer")
    assert hasattr(digitalocean.networking, "VPC")


def test_digitalocean_base_template_is_saved_with_a_visible_reference_brief() -> None:
    project = CloudProject.load(TEMPLATE)
    html = render_project_html(project)

    assert project.kind == "single-cloud"
    assert project.provider_ids == ("digitalocean",)
    assert project.default_library == "digitalocean"
    assert "diagrams.digitalocean.compute.Containers" in project.template_brief
    assert "diagrams.digitalocean.storage.Volume" in project.template_brief
    assert "data-template-brief" in html
    assert "DigitalOcean node reference" in html
    assert "diagrams.digitalocean.network.Vpc" in html


def test_digitalocean_kubernetes_template_matches_documented_doks_boundaries() -> None:
    project = CloudProject.load(KUBERNETES_TEMPLATE)
    elements = project.topology.index()

    assert project.kind == "hybrid"
    assert project.provider_ids == ("digitalocean", "kubernetes")
    assert project.default_library == "digitalocean"
    assert project.presentation.size == "fit"
    assert project.presentation.detail == "faithful"
    assert "docs.digitalocean.com/products/kubernetes/details/managed" in (project.template_brief)
    assert "Illustrative pod placement" in project.template_brief

    expected_frames = {
        "do-vpc": ("vpc", None),
        "doks-cluster": ("cluster", "do-vpc"),
        "app-namespace": ("namespace", "doks-cluster"),
        "worker-pool": ("node-pool", "app-namespace"),
        "worker-node-1": ("group", "worker-pool"),
        "worker-node-2": ("group", "worker-pool"),
        "worker-node-3": ("group", "worker-pool"),
    }
    for element_id, (kind, parent_id) in expected_frames.items():
        element = elements[element_id]
        parent = project.topology.parent_of(element)
        assert element.type == kind
        assert (parent.id if parent is not project.topology else None) == parent_id
        # The template pins no frame sizes: the layout places it,
        # and the golden pictures verify the result.
        assert "editor_width" not in element.attributes
        assert "editor_height" not in element.attributes
        frame_paint = element.attributes["editor_boundary_style"]
        assert frame_paint["fill"] == "none"
        assert frame_paint["stroke"] in {"#0080ff", "#326ce5"}
        assert frame_paint["strokeWidth"] == 1.0

    expected_components = {
        "load-balancer": "digitalocean:load-balancer",
        "managed-control-plane": "digitalocean:k8s-cluster",
        "gateway": "kubernetes:ing",
        "web-ui-pod": "kubernetes:pod",
        "user-api-pod": "kubernetes:pod",
        "photo-api-pod": "kubernetes:pod",
        "managed-postgresql": "digitalocean:dbaas-primary-standby-more",
        "spaces": "digitalocean:space",
    }
    for element_id, icon_ref in expected_components.items():
        assert elements[element_id].component is not None
        assert elements[element_id].component.icon_ref == icon_ref

    connections = {
        (element.id, connection.target, connection.label)
        for element in project.topology.walk()
        for connection in element.connections
    }
    assert connections == {
        ("internet-client", "load-balancer", "HTTPS"),
        ("load-balancer", "gateway", "LoadBalancer"),
        ("gateway", "web-ui-pod", "web"),
        ("web-ui-pod", "user-api-pod", "User API"),
        ("web-ui-pod", "photo-api-pod", "Photo API"),
        ("user-api-pod", "managed-postgresql", "SQL"),
        ("photo-api-pod", "spaces", "S3 API"),
    }

    html = render_project_html(project)
    assert "DigitalOcean Kubernetes application cluster" in html
    assert "Illustrative pod placement" in html
    # This template names no starter preset, so the brief carries no button.
    # The class, not the hook: the runtime carries `[data-template-starter]`
    # as a selector, so looking for the hook finds the editor's own source.
    assert 'class="toolbar-button template-starter"' not in html
