"""An export embeds the project's libraries by default, every library on request."""

from __future__ import annotations

import pytest

from infragram.catalog import load_default_provider_registry
from infragram.editor.shell import library_catalog_from_html
from infragram.exports import ExportError, render_project_html
from infragram.projects import CloudProject


def _library(html: str) -> dict:
    return library_catalog_from_html(html)


def _onprem_project() -> CloudProject:
    return CloudProject.model_validate(
        {
            "schema_version": 2,
            "kind": "single-cloud",
            "slug": "one-rack",
            "title": "One rack",
            "description": "A single on-premises server.",
            "providers": [{"id": "onprem", "enabled": True}],
            "default_library": "onprem",
            "presentation": {"size": "fit"},
            "topology": {
                "id": "root",
                "name": "One rack",
                "type": "group",
                "children": [
                    {
                        "id": "srv",
                        "name": "Bare-metal server",
                        "type": "service",
                        "component": {
                            "provider": "onprem",
                            "service_id": "bare-metal-server",
                            "icon_ref": "onprem:bare-metal-server",
                        },
                        "attributes": {"editor_x": 200, "editor_y": 200},
                    }
                ],
            },
        }
    )


def test_default_export_embeds_only_the_projects_libraries() -> None:
    html = render_project_html(_onprem_project())
    library = _library(html)

    assert [provider["id"] for provider in library["providers"]] == ["onprem"]
    assert library["selectedProviders"] == ["onprem"]
    providers_present = {component["provider"] for component in library["components"]}
    # the library itself plus the shared primitives and frames, nothing else
    assert providers_present == {"onprem", "infragram"}
    assert any(component["componentKind"] == "boundary" for component in library["components"])
    # the sidebar offers no quick filter for a library that is not embedded
    assert 'data-provider-quick-filter="azure"' not in html
    assert "data-provider-summary>All 1<" in html


def test_all_libraries_export_still_embeds_every_installed_library() -> None:
    registry = load_default_provider_registry()
    slim = render_project_html(_onprem_project())
    full = render_project_html(_onprem_project(), libraries="all")
    library = _library(full)

    assert [provider["id"] for provider in library["providers"]] == [
        provider.id for provider in registry.providers
    ]
    assert 'data-provider-quick-filter="azure"' in full
    # the whole point: a single-library export is a fraction of the workspace.
    # On-prem is the heaviest library by far -- 421 rendered 3D icons and the
    # imported PNG artwork -- so the bound is two thirds, not a third: the
    # workspace lost 4.8 MB when IBM's PNG wrappers became Carbon line icons
    # (26.5 MB to 21.7 MB), and this export is 13.0 MB of it.
    assert len(slim) < len(full) * 2 / 3


def test_slim_export_also_ships_libraries_its_starter_stacks_need() -> None:
    # The DigitalOcean DOKS starter stack places Kubernetes workloads, so a
    # DigitalOcean-only export must carry the Kubernetes library or the stack
    # would come up with holes in it.
    project = CloudProject.model_validate(
        {
            "schema_version": 2,
            "kind": "single-cloud",
            "slug": "do-only",
            "title": "DigitalOcean only",
            "description": "One droplet.",
            "providers": [{"id": "digitalocean", "enabled": True}],
            "default_library": "digitalocean",
            "presentation": {"size": "fit"},
            "topology": {
                "id": "root",
                "name": "DigitalOcean only",
                "type": "group",
                "children": [
                    {
                        "id": "web",
                        "name": "Droplet",
                        "type": "service",
                        "component": {
                            "provider": "digitalocean",
                            "service_id": "droplets",
                            "icon_ref": "digitalocean:droplets",
                        },
                        "attributes": {"editor_x": 200, "editor_y": 200},
                    }
                ],
            },
        }
    )

    library = _library(render_project_html(project))

    assert [provider["id"] for provider in library["providers"]] == ["digitalocean", "kubernetes"]
    assert library["selectedProviders"] == ["digitalocean"]
    assert any(
        component["qualifiedId"] == "kubernetes:deploy" for component in library["components"]
    )


def test_unknown_libraries_choice_is_rejected() -> None:
    with pytest.raises(ExportError):
        render_project_html(_onprem_project(), libraries="some")
