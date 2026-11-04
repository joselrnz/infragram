"""The multicloud document and catalog: schema migration, qualified components, providers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from infragram.catalog import (
    load_composite_catalog,
    load_default_provider_registry,
)
from infragram.projects import CloudProject


def legacy_project_payload(provider: str = "gcp") -> dict:
    return {
        "schema_version": 1,
        "slug": f"{provider}-legacy-api",
        "title": f"{provider.upper()} legacy API",
        "description": "A version-one project that must migrate without data loss.",
        "provider": provider,
        "presentation": {"size": "fit", "detail": "balanced"},
        "topology": {
            "id": "root",
            "name": "Application",
            "type": "group",
            "children": [
                {
                    "id": "api",
                    "name": "API",
                    "type": "service",
                    "attributes": {"icon": "cloud-run"},
                    "connections": [{"target": "database", "kind": "traffic", "label": "SQL"}],
                },
                {
                    "id": "database",
                    "name": "Database",
                    "type": "database",
                    "attributes": {"icon": "cloud-sql"},
                },
            ],
        },
    }


def multicloud_project_payload() -> dict:
    return {
        "schema_version": 2,
        "kind": "multicloud",
        "slug": "azure-aws-gcp-platform",
        "title": "Azure, AWS, and GCP platform",
        "description": "A mixed-provider application with cross-cloud traffic.",
        "providers": [
            {"id": "azure", "enabled": True},
            {"id": "aws", "enabled": True},
            {"id": "gcp", "enabled": True},
        ],
        "default_library": "all",
        "layers": [
            {
                "id": "provider:azure",
                "name": "Azure",
                "kind": "provider",
                "provider": "azure",
                "order": 10,
            },
            {
                "id": "provider:aws",
                "name": "AWS",
                "kind": "provider",
                "provider": "aws",
                "order": 20,
            },
            {
                "id": "provider:gcp",
                "name": "Google Cloud",
                "kind": "provider",
                "provider": "gcp",
                "order": 30,
            },
        ],
        "presentation": {"size": "fit", "detail": "faithful"},
        "topology": {
            "id": "root",
            "name": "Multicloud application",
            "type": "group",
            "children": [
                {
                    "id": "azure-api",
                    "name": "Azure API Management",
                    "type": "service",
                    "component": {
                        "provider": "azure",
                        "service_id": "api-management-services",
                    },
                    "layer_id": "provider:azure",
                    "connections": [
                        {"target": "aws-function", "kind": "private", "label": "HTTPS"}
                    ],
                },
                {
                    "id": "aws-function",
                    "name": "AWS Lambda",
                    "type": "service",
                    "component": {
                        "provider": "aws",
                        "service_id": "lambda",
                    },
                    "layer_id": "provider:aws",
                    "connections": [
                        {"target": "gcp-database", "kind": "replication", "label": "EVENTS"}
                    ],
                },
                {
                    "id": "gcp-database",
                    "name": "Cloud SQL",
                    "type": "database",
                    "component": {
                        "provider": "gcp",
                        "service_id": "cloud-sql",
                        "icon_ref": "gcp:cloud-sql",
                    },
                    "layer_id": "provider:gcp",
                },
            ],
        },
    }


def test_version_one_project_migrates_in_memory_without_rewriting_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy.infragram.json"
    original = json.dumps(legacy_project_payload(), indent=2) + "\n"
    source.write_text(original, encoding="utf-8")

    project = CloudProject.load(source)

    assert source.read_text(encoding="utf-8") == original
    assert project.schema_version == 3
    assert project.kind == "single-cloud"
    assert [(item.id, item.enabled) for item in project.providers] == [("gcp", True)]
    assert project.default_library == "gcp"
    assert project.provider == "gcp"
    assert project.layers[0].id == "provider:gcp"
    assert project.layers[0].provider == "gcp"
    assert project.topology.index()["api"].component.icon_ref == "gcp:cloud-run"
    assert project.topology.index()["api"].layer_id == "provider:gcp"


def test_migrated_project_saves_at_the_current_schema_version(tmp_path: Path) -> None:
    project = CloudProject.model_validate(legacy_project_payload("azure"))
    output = tmp_path / "migrated.infragram.json"

    project.save(output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 3
    assert payload["kind"] == "single-cloud"
    assert payload["providers"] == [{"id": "azure", "enabled": True}]
    assert "provider" not in payload


def test_azure_aws_gcp_project_round_trips_with_qualified_components(
    tmp_path: Path,
) -> None:
    project = CloudProject.model_validate(multicloud_project_payload())
    output = tmp_path / "multicloud.infragram.json"

    project.save(output)
    loaded = CloudProject.load(output)

    assert loaded == project
    assert loaded.schema_version == 3
    assert loaded.kind == "multicloud"
    assert loaded.provider_ids == ("azure", "aws", "gcp")
    assert loaded.topology.index()["azure-api"].component.icon_ref == (
        "azure:api-management-services"
    )
    assert loaded.topology.index()["aws-function"].component.icon_ref == "aws:lambda"
    assert loaded.topology.index()["gcp-database"].component.icon_ref == "gcp:cloud-sql"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload["providers"].append({"id": "gcp"}), "duplicate provider"),
        (
            lambda payload: payload["topology"]["children"][0]["component"].update(
                {"provider": "digitalocean"}
            ),
            "not enabled in this project",
        ),
        (
            lambda payload: payload["topology"]["children"][0].update(
                {"layer_id": "provider:missing"}
            ),
            "unknown layer",
        ),
        (
            lambda payload: payload["layers"][0].update({"provider": "digitalocean"}),
            "not enabled in this project",
        ),
    ],
)
def test_multicloud_project_rejects_ambiguous_provider_and_layer_references(
    mutation,
    message: str,
) -> None:
    payload = multicloud_project_payload()
    mutation(payload)

    with pytest.raises(ValidationError, match=message):
        CloudProject.model_validate(payload)


def test_component_ref_rejects_mismatched_qualified_icon() -> None:
    payload = multicloud_project_payload()
    payload["topology"]["children"][1]["component"]["icon_ref"] = "gcp:lambda"

    with pytest.raises(ValidationError, match="icon_ref must use provider prefix aws"):
        CloudProject.model_validate(payload)


def test_provider_registry_describes_all_registered_libraries_and_gcp() -> None:
    registry = load_default_provider_registry()

    assert tuple(provider.id for provider in registry.providers) == (
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
    )
    assert registry["gcp"].display_name == "Google Cloud"
    assert registry["gcp"].short_name == "GCP"
    assert registry["gcp"].kind == "cloud"
    assert registry["gcp"].coverage == "full"
    assert registry["gcp"].source_url.startswith("https://cloud.google.com/")
    assert registry["gcp"].terms
    assert registry["kubernetes"].kind == "platform"
    assert (
        registry["databricks"].kind == "platform" and registry["databricks"].coverage == "reviewed"
    )
    # Imported catalogs are reviewed; the five with no importable artwork are
    # reviewed on drawn service tiles of their own.
    assert registry["oracle"].coverage == "reviewed"
    assert registry["ibm"].coverage == "reviewed"
    assert registry["alibaba"].coverage == "reviewed"
    assert registry["openstack"].kind == "platform"
    assert registry["openstack"].coverage == "reviewed"
    assert {
        registry[slug].coverage
        for slug in ("ovhcloud", "vultr", "akamai", "vmware", "proxmox", "equinix")
    } == {"reviewed"}
    assert {registry[slug].kind for slug in ("vmware", "proxmox")} == {"platform"}
    assert {registry[slug].kind for slug in ("ovhcloud", "vultr", "akamai")} == {"cloud"}


def test_composite_catalog_qualifies_services_and_deduplicates_custom_shapes() -> None:
    catalog = load_composite_catalog(("azure", "aws", "gcp"))

    assert tuple(provider.id for provider in catalog.providers) == (
        "azure",
        "aws",
        "gcp",
    )
    qualified_ids = {component.qualified_id for component in catalog.components}
    assert "azure:virtual-machine" in qualified_ids
    assert "aws:lambda" in qualified_ids
    assert "gcp:compute-engine" in qualified_ids
    assert "infragram:custom-annotation" in qualified_ids
    assert (
        sum(
            component.qualified_id == "infragram:custom-annotation"
            for component in catalog.components
        )
        == 1
    )
    assert all(":" in component.qualified_id for component in catalog.components)
    assert len(catalog.components) > 1_250


def test_composite_catalog_searches_names_aliases_and_provider_names() -> None:
    catalog = load_composite_catalog(("azure", "aws", "gcp"))

    assert catalog.search("lambda")[0].qualified_id == "aws:lambda"
    assert any(
        result.qualified_id == "gcp:compute-engine"
        for result in catalog.search("google compute engine")
    )


def test_composite_catalog_rejects_duplicate_or_unknown_provider_selection() -> None:
    with pytest.raises(ValueError, match="duplicate provider"):
        load_composite_catalog(("azure", "azure"))

    with pytest.raises(ValueError, match="unknown provider"):
        load_composite_catalog(("mystery-cloud",))
