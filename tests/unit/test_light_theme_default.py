"""The workspace opens light, everywhere, every time.

A diagram is only ever seen on white: printed, pasted into a document,
exported to PNG or SVG. Opening the editor dark meant the first look at a
drawing was in a theme the finished artwork would never ship in.

Dark is still there as a viewer preference -- the toggle, the `?theme=`
parameter and the saved localStorage choice all still work. What must not
come back is dark as the *default*, which lives in three places that have to
agree: the body attribute, the runtime's fallback, and the toggle's initial
label, which is what a reader sees before any script runs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from infragram.editor.bundle import runtime_script
from infragram.exports import render_project_html
from infragram.projects import CloudProject

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
TEMPLATES = ROOT / "plugin/skills/infragram-architect/assets/templates/cloud"
RUNTIME_SOURCE = runtime_script()

TEMPLATE_SLUGS = ("aws-three-tier-web", "onprem-datacenter", "azure-api")


def _html(slug: str) -> str:
    import json

    project = CloudProject.model_validate(
        json.loads((TEMPLATES / f"{slug}.infragram.json").read_text(encoding="utf-8"))
    )
    return render_project_html(project)


@pytest.mark.parametrize("slug", TEMPLATE_SLUGS)
def test_the_page_opens_light(slug: str) -> None:
    html = _html(slug)
    assert '<body data-workspace-theme="light">' in html
    assert '<body data-workspace-theme="dark">' not in html


@pytest.mark.parametrize("slug", TEMPLATE_SLUGS)
def test_the_palette_opens_on_light(slug: str) -> None:
    """Before any script runs, the control must describe the state the page
    is actually in. A palette that opens with Dark checked on a light page is
    what you get when the markup and the default drift apart."""
    html = _html(slug)
    assert 'aria-label="Theme: Light"' in html
    assert 'data-theme-choice="light" aria-checked="true"' in html
    for other in ("dark", "darker"):
        assert f'data-theme-choice="{other}" aria-checked="false"' in html


def test_the_runtime_falls_back_to_light() -> None:
    """The body attribute is the first default; this is the second. A reader
    with no saved preference and no attribute still lands on light."""
    source = RUNTIME_SOURCE
    match = re.search(
        r"let savedTheme = document\.body\.dataset\.workspaceTheme \|\| '(\w+)';",
        source,
    )
    assert match, "the savedTheme fallback moved; check it still defaults light"
    assert match.group(1) == "light"


@pytest.mark.parametrize("slug", TEMPLATE_SLUGS)
def test_dark_is_still_reachable(slug: str) -> None:
    """Light is the default, not the only option: the dark palette still
    ships and the toggle still has something to switch to."""
    html = _html(slug)
    assert "data-theme-toggle" in html
    assert 'body[data-workspace-theme="light"]' in html
    assert "--canvas-bg:#141414" in html
    # and the third palette, which is dark on neutral near-black surfaces
    assert 'body[data-workspace-palette="darker"]' in html
    assert "--canvas-bg:#0D0D0D" in html
