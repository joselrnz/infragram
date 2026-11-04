"""The rendered 3D set draws bare -- the object with its caption beneath,
no card -- everywhere the default look is resolved: the sidebar, the
editor state, the exports."""

from __future__ import annotations

from infragram.catalog.display import default_display
from infragram.editor import load_sidebar_catalog


def test_every_3d_icon_defaults_to_the_icon_look() -> None:
    catalog = load_sidebar_catalog("onprem")
    seen = 0
    for category in catalog.categories:
        for component in category.components:
            if component.id.startswith("iso-"):
                seen += 1
                assert (
                    default_display(
                        "onprem", component.id, tier=component.tier, category=category.id
                    )
                    == "icon"
                ), component.id
    assert seen >= 600


def test_the_vendor_logos_beside_them_keep_their_card() -> None:
    assert default_display("onprem", "docker", tier="service", category="container") == "card"
    assert (
        default_display("onprem", "iso-rack-server", tier="service", category="iso-compute")
        == "icon"
    )
