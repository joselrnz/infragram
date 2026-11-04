from __future__ import annotations

from html.parser import HTMLParser

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
                },
                {
                    "id": "provider:aws",
                    "name": "AWS",
                    "kind": "provider",
                    "provider": "aws",
                },
                {
                    "id": "provider:gcp",
                    "name": "Google Cloud",
                    "kind": "provider",
                    "provider": "gcp",
                },
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
                        "connections": [{"target": "worker", "kind": "solid", "label": "HTTPS"}],
                    },
                    {
                        "id": "worker",
                        "name": "Worker",
                        "type": "service",
                        "component": {"provider": "aws", "service_id": "lambda"},
                        "layer_id": "provider:aws",
                        "connections": [
                            {"target": "database", "kind": "dashed", "label": "EVENTS"}
                        ],
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


def _library_payload(html: str) -> dict:
    return library_catalog_from_html(html)


def _elements(html: str, tag: str) -> list[dict[str, str | None]]:
    """Read tag attributes without depending on their order or whitespace."""

    class Elements(HTMLParser):
        found: list[dict[str, str | None]]

        def __init__(self):
            super().__init__()
            self.found = []

        def handle_starttag(self, name, attrs):
            if name == tag:
                self.found.append(dict(attrs))

    parser = Elements()
    parser.feed(html)
    return parser.found


def test_multicloud_workspace_uses_neutral_connected_cloud_brand() -> None:
    html = render_project_html(multicloud_project())

    assert 'data-provider-label="Multicloud Diagrams"' in html
    assert 'data-multicloud-mark="true"' in html
    assert "<strong>Multicloud Diagrams</strong>" in html
    assert 'aria-label="Collapse Multicloud Diagrams sidebar"' in html
    assert "<small>Multicloud architecture</small>" in html
    assert "<!-- Brand mark -->" not in html


def test_provider_library_selector_lists_every_registered_library_and_coverage() -> None:
    # the full workspace export embeds every installed library so the menu can add any
    html = render_project_html(multicloud_project(), libraries="all")

    assert "data-provider-menu-trigger" in html
    # three libraries give a real choice, so the selector shows, naming the two the page selects
    selector = next(
        item
        for item in _elements(html, "section")
        if "provider-selector" in (item.get("class") or "").split()
    )
    assert selector["aria-label"] == "Provider libraries"
    assert "Libraries · <strong data-provider-summary>Azure + AWS + GCP</strong>" in html
    assert '<p class="md-menu__header provider-group-label">Cloud providers</p>' in html
    assert '<p class="md-menu__header provider-group-label">Platforms</p>' in html
    registered = load_default_provider_registry().providers
    assert html.count('data-provider-option="') == len(registered)
    for provider in registered:
        assert f'data-provider-option="{provider.id}"' in html
    assert 'data-provider-option="azure" checked' in html
    assert 'data-provider-option="aws" checked' in html
    assert 'data-provider-option="gcp" checked' in html
    assert 'data-provider-option="cloudflare"' in html
    assert 'data-provider-option="oracle"' in html
    assert 'data-provider-option="onprem"' in html
    # every registered library is reviewed or full
    assert 'data-coverage="reviewed"' in html and 'data-coverage="full"' in html
    assert 'data-provider-quick-filter="azure"' in html
    assert (
        'data-provider-quick-filter="azure"\n                aria-pressed="true">Azure</button>'
        in html
    )
    assert 'data-provider-quick-filter="aws"' in html
    assert 'data-provider-quick-filter="gcp"' in html
    assert "data-provider-apply" in html


def test_offline_library_payload_uses_qualified_ids_and_shared_custom_once() -> None:
    payload = _library_payload(render_project_html(multicloud_project(), libraries="all"))

    assert tuple(provider["id"] for provider in payload["providers"]) == tuple(
        provider.id for provider in load_default_provider_registry().providers
    )
    components = payload["components"]
    qualified = [component["qualifiedId"] for component in components]
    assert "azure:virtual-machine" in qualified
    assert "aws:lambda" in qualified
    assert "gcp:compute-engine" in qualified
    assert qualified.count("infragram:custom-annotation") == 1
    assert all(":" in component["qualifiedId"] for component in components)
    assert all(component["iconUri"].startswith("data:image/svg+xml;") for component in components)


def test_sidebar_defers_component_cards_until_a_category_or_search_is_opened() -> None:
    html = render_project_html(multicloud_project())

    assert 'data-library-render-mode="lazy"' in html
    assert 'data-component-list="custom"' in html
    shell = html.split(
        '<script type="application/octet-stream" id="infragram-library-catalog"', maxsplit=1
    )[0]
    assert 'class="component-card" draggable="true"' not in shell
    assert "renderVisibleCatalog" in html
    assert "providerSelection" in html


def test_provider_filter_runtime_keeps_canvas_visibility_separate_from_library_scope() -> None:
    html = render_project_html(multicloud_project())

    assert "applyProviderSelection" in html
    assert "renderVisibleCatalog" in html
    assert (
        "state.nodes = state.nodes.filter"
        not in html.split("const applyProviderSelection", maxsplit=1)[1].split("};", maxsplit=1)[0]
    )
    assert (
        "state.boundaries = state.boundaries.filter"
        not in html.split("const applyProviderSelection", maxsplit=1)[1].split("};", maxsplit=1)[0]
    )
