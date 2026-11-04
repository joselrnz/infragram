"""An exported page is as small as its libraries allow: the payload travels deflated, the 3D renderer only where it can be used."""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram
from infragram.editor.shell import (
    LIBRARY_ENCODING,
    library_catalog_from_html,
    page_carries_3d_renderer,
)
from infragram.exports import render_project_html
from infragram.nodes.onprem import iso_compute
from infragram.projects import CloudProject

TEMPLATES = (
    Path(__file__).resolve().parents[2]
    / "plugin"
    / "skills"
    / "infragram-architect"
    / "assets"
    / "templates"
    / "cloud"
)


def _template(name: str) -> CloudProject:
    return CloudProject.load(TEMPLATES / f"{name}.infragram.json")


def test_the_library_payload_travels_deflated_and_reads_back() -> None:
    html = render_project_html(_template("azure-api"))
    assert f'id="infragram-library-catalog" data-encoding="{LIBRARY_ENCODING}"' in html
    library = library_catalog_from_html(html)
    assert library["selectedProviders"] == ["azure"]
    assert any(component["provider"] == "azure" for component in library["components"])
    assert "DecompressionStream" in html, "the page inflates it itself"


def test_a_cloud_page_leaves_the_3d_renderer_out_and_says_so() -> None:
    project = _template("azure-api")
    assert page_carries_3d_renderer(project, "project") is False
    html = render_project_html(project)
    assert "/* no 3D renderer" in html and "THREE" not in html
    assert "data-iso-unavailable" in html
    assert page_carries_3d_renderer(project, "all") is True
    assert "THREE" in render_project_html(project, libraries="all")


def test_an_on_premises_page_and_a_page_with_a_3d_item_carry_the_renderer() -> None:
    assert page_carries_3d_renderer(_template("onprem-datacenter"), "project") is True
    # An explicit providers= is the whole set, so the on-premises library the
    # 3D item comes from is named beside the primary one.
    with Diagram("Rack", "one 3D item", slug="rack-3d", providers=("aws", "onprem")) as diagram:
        iso_compute.IsoBareMetalHost("Node", "1U")
    project = diagram.to_project()
    assert project.provider_ids == ("aws", "onprem")
    assert page_carries_3d_renderer(project, "project") is True


def test_exported_pages_stay_small() -> None:
    """The budgets catch what costs megabytes -- a payload that stopped
    travelling deflated, a 3D renderer on a page that cannot use it -- not
    the editor's own growth. AWS's page is the largest cloud page: about
    2.07 MB of it is the AWS icon catalog and 0.36 MB the editor runtime,
    wire editing included (bend handles, reconnecting an end, pinned sides,
    the frame review, the card popup's prices and links with the table of
    where each component is read about). Every page also offers every
    library's frames with their badge artwork: Databricks' four added about
    26 KB to each page. The runtime that draws a frame's corner badges (a
    subnet's NSG and route table) took the AWS page just past 3.15 MB. The
    right-click menu's lenses added 8 KB to each page, which took Azure's
    past 2.50 MB. Wires drawn apart where they share a line, kept off frame
    borders, and captions kept beside their own wire added about 11 KB of
    runtime to each, which took Azure's past 2.52 MB and AWS's past 3.20 MB.
    Crossing controls and transparent bridge masks add about 9 KB of runtime,
    taking Azure's page just past 2.54 MB. Optional legends, cropped downloads,
    quality controls and inline mascot artwork bring the current pages to
    about 2.60 MB (Azure) and 3.28 MB (AWS). The Cost tab, the header's cost
    chip and the price lines in the card popup add about 18 KB of runtime and
    styles, taking Azure's to 2.62 MB and AWS's to 3.30 MB. The inventory (its
    table, Savings and Changes views, details sheet and lenses) and Inter in
    place of Roboto add about 95 KB, taking Azure's to 2.72 MB and AWS's to
    3.40 MB. The right-click menu's icons, its view entries and its More
    actions submenu add about 17 KB, taking Azure's to 2.78 MB and AWS's to
    3.46 MB. The budgets leave a small margin
    for editor growth while still catching an uncompressed catalog or a
    needless 3D bundle."""
    sizes = {
        name: len(render_project_html(_template(name)).encode("utf-8"))
        for name in ("azure-api", "aws-three-tier-web")
    }
    assert sizes["azure-api"] < 2_800_000, sizes
    assert sizes["aws-three-tier-web"] < 3_480_000, sizes
