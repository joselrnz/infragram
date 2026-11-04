"""An export can carry only what the diagram draws, for a page small enough to send.

Every export embeds whole libraries so the reader can keep building offline,
which is what makes a page a few megabytes -- 14.8 MB for a hybrid estate,
of which the drawing itself uses about 150 KB of artwork. ``--libraries
drawn`` ships the components the document places plus the shared frames and
basic elements, and says so on the page, because a library that is nearly
empty otherwise looks broken rather than deliberate.
"""

from __future__ import annotations

import pytest

from infragram.editor.shell import EMBEDDED_LIBRARIES, library_catalog_from_html
from infragram.exports import ExportError, render_project_html
from infragram.paths import skill_assets
from infragram.projects import CloudProject

TEMPLATE = skill_assets() / "templates" / "cloud" / "hybrid-bgp-edge.infragram.json"


@pytest.fixture(scope="module")
def project() -> CloudProject:
    return CloudProject.load(TEMPLATE)


@pytest.fixture(scope="module")
def pages(project: CloudProject) -> dict[str, str]:
    return {mode: render_project_html(project, libraries=mode) for mode in ("project", "drawn")}


def _drawn(project: CloudProject) -> set[str]:
    return {
        f"{element.component.provider}:{element.component.service_id}"
        for element in project.topology.walk()
        if element.component is not None
    }


def test_drawn_is_one_of_the_modes() -> None:
    assert "drawn" in EMBEDDED_LIBRARIES
    with pytest.raises((ExportError, ValueError)):
        render_project_html(CloudProject.load(TEMPLATE), libraries="lean")


def test_a_drawn_page_carries_every_component_it_draws(
    project: CloudProject, pages: dict[str, str]
) -> None:
    carried = {
        component["qualifiedId"]
        for component in library_catalog_from_html(pages["drawn"])["components"]
    }
    missing = _drawn(project) - carried
    assert not missing, f"drawn but not carried: {sorted(missing)}"


def test_a_drawn_page_still_carries_the_frames_and_basic_elements(pages: dict[str, str]) -> None:
    components = library_catalog_from_html(pages["drawn"])["components"]
    shared = [component for component in components if component["provider"] == "infragram"]
    assert any(component.get("componentKind") == "boundary" for component in shared), (
        "frames to arrange with"
    )
    assert any(component.get("componentKind") != "boundary" for component in shared), (
        "basic elements"
    )
    every = library_catalog_from_html(pages["project"])["components"]
    assert len(shared) == len([c for c in every if c["provider"] == "infragram"])


def test_a_drawn_page_leaves_the_rest_of_the_libraries_behind(pages: dict[str, str]) -> None:
    drawn = library_catalog_from_html(pages["drawn"])["components"]
    every = library_catalog_from_html(pages["project"])["components"]
    assert len(drawn) < len(every) / 4, (len(drawn), len(every))
    sizes = {mode: len(page.encode("utf-8")) for mode, page in pages.items()}
    assert sizes["drawn"] < sizes["project"] / 4, sizes
    # the libraries themselves are still offered, so layers and the selector hold
    assert (
        library_catalog_from_html(pages["drawn"])["providers"]
        == library_catalog_from_html(pages["project"])["providers"]
    )


def test_a_drawn_page_adds_no_paragraph_to_the_sidebar(pages: dict[str, str]) -> None:
    """What a small copy carries is said where it matters, when a search
    finds nothing (the runtime's searchEmptyText), not in a standing note."""
    for page in pages.values():
        assert "drawn-only-note" not in page
        assert "This copy carries only the components" not in page
    assert library_catalog_from_html(pages["drawn"])["drawnOnly"] is True


def test_a_drawn_page_leaves_out_the_3d_renderer_a_drawing_never_uses(
    pages: dict[str, str],
) -> None:
    """The renderer is 1.6 MB and rides along for an on-premises project,
    which is most of what a small page is trying to shed; a document that
    draws a 3D item still gets it."""
    assert "onprem" in CloudProject.load(TEMPLATE).provider_ids
    assert "THREE" not in pages["drawn"]
    assert "THREE" in pages["project"]


def test_a_drawing_with_an_item_rendered_by_spec_keeps_the_renderer() -> None:
    """A shipped isometric icon is artwork and needs nothing; an item the
    page renders from its own recipe cannot be drawn without the renderer,
    so that document carries it however small the page is asked to be."""
    from infragram.author import Diagram
    from infragram.nodes import reset_ids
    from infragram.nodes.iso import Iso

    reset_ids()
    with Diagram("Rack", "one item by spec", slug="rack-drawn", providers=("onprem",)) as diagram:
        Iso("Node", "1U", recipe="rack")
    project = diagram.to_project()
    assert any(element.attributes.get("iso_artwork") for element in project.topology.walk())
    assert "THREE" in render_project_html(project, libraries="drawn")
