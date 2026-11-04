"""The page carries the diagram's Terraform for its download menu.

Both styles, exactly the files the export's ``terraform`` and
``terraform-modules`` formats write, and only for a diagram that draws
something on AWS, Azure or Google Cloud: a page with nothing to write offers
no Terraform at all. The browser suite downloads them
(tests/integration/test_editor_controls_browser.py); this checks what the
shell writes, so a regression fails in the unit run first.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from infragram.editor.shell import LIBRARY_ENCODING
from infragram.editor.terraform_payload import ENCODING, terraform_from_html, terraform_payload
from infragram.editor.ui.icons import ICON_PATHS
from infragram.editor.ui.views.header import TERRAFORM_ITEMS, download_menu
from infragram.exports import render_project_html
from infragram.projects import CloudProject
from infragram.terraform import folder_name, terraform_files

TEMPLATES = (
    Path(__file__).resolve().parents[2]
    / "plugin"
    / "skills"
    / "infragram-architect"
    / "assets"
    / "templates"
)
ITEM = re.compile(r'data-download-terraform="(\w+)"')


def _template(name: str) -> CloudProject:
    return CloudProject.load(next(TEMPLATES.rglob(f"{name}.infragram.json")))


@pytest.mark.parametrize(
    "name", ["aws-three-tier-web", "azure-api", "gcp-three-tier-web", "multicloud-base"]
)
def test_a_cloud_page_carries_its_terraform_in_both_styles(name: str) -> None:
    project = _template(name)
    html = render_project_html(project)
    assert f'id="infragram-terraform" data-encoding="{LIBRARY_ENCODING}"' in html, (
        "deflated, like the library"
    )
    carried = terraform_from_html(html)
    assert list(carried) == ["resources", "modules"]
    for style, folder in carried.items():
        assert folder["folder"] == folder_name(project.slug, style)
        assert folder["files"] == terraform_files(project, style)[1], (
            f"{style}: not what the export writes"
        )
    assert ITEM.findall(html) == ["resources", "modules"], "one item a style, in the menu's order"


def test_the_terraform_travels_as_the_library_does() -> None:
    """The runtime reads both with one reader, so they share one encoding."""
    assert ENCODING == LIBRARY_ENCODING


def test_a_page_with_nothing_on_the_three_clouds_offers_no_terraform() -> None:
    project = _template("onprem-datacenter")
    html = render_project_html(project)
    assert terraform_payload(project) == {}
    assert terraform_from_html(html) == {}
    assert 'id="infragram-terraform"' not in html
    assert not ITEM.findall(html)


def test_the_menu_offers_what_the_page_carries_with_terraforms_mark() -> None:
    plain = download_menu()
    assert not ITEM.findall(plain)
    assert "data-download-infrastructure" not in plain, "no empty infrastructure section"
    assert plain.count('role="separator"') == 1, "sharing formats precede editable project formats"

    assert ITEM.findall(download_menu(("resources",))) == ["resources"]
    both = download_menu(("modules", "resources"))
    assert ITEM.findall(both) == [style for style, _label, _what in TERRAFORM_ITEMS], (
        "the menu's order, not the caller's"
    )
    assert both.count('role="separator"') == 1
    assert 'aria-label="Infrastructure" data-download-infrastructure' in both
    assert both.count(ICON_PATHS["terraform"]) == 2, "each item wears Terraform's mark"
    for _style, label, what in TERRAFORM_ITEMS:
        assert label.replace("'", "&#x27;") in both and ".zip" in both
        assert f'title="{what.replace(chr(39), "&#x27;")}"' in both
