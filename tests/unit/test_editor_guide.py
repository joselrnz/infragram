"""The editor guide names controls the exported page actually has.

``references/editor.md`` is what the skill hands a reader along with the
page: what they can do with the file in front of them. A guide that names a
menu item the page does not have is worse than no guide, and nothing else
would catch it -- the page is markup, the guide is prose. Every control the
guide puts in bold has to be findable in a rendered page, and every URL
option it offers has to be one the runtime reads.
"""

from __future__ import annotations

import re

import pytest

from infragram.exports import render_project_html
from infragram.paths import skill_assets
from infragram.projects import CloudProject

GUIDE = skill_assets().parent / "references" / "editor.md"

#: Bold phrases that name something other than a control on the page: a
#: pointer gesture, or a word in a sentence. Each is here with its reason.
NOT_A_CONTROL = {
    "?": "the key that opens the shortcut sheet is drawn as a glyph, not that character",
    "Shift": "a modifier held while clicking, named in prose",
    "Alt": "a modifier held while dragging, named in prose",
    "as cards": "the second half of 'Show contents as icons / as cards'",
}


@pytest.fixture(scope="module")
def page() -> str:
    template = skill_assets() / "templates" / "cloud" / "hybrid-bgp-edge.infragram.json"
    return render_project_html(CloudProject.load(template))


def _bold() -> list[str]:
    text = GUIDE.read_text(encoding="utf-8")
    return sorted({phrase.strip() for phrase in re.findall(r"\*\*([^*]+)\*\*", text)})


def test_every_control_the_guide_names_is_on_the_page(page: str) -> None:
    assert _bold(), "the guide names controls in bold"
    missing = [phrase for phrase in _bold() if phrase not in NOT_A_CONTROL and phrase not in page]
    assert not missing, f"named in editor.md, not found in the page: {missing}"


def test_every_url_option_the_guide_offers_is_read_by_the_runtime() -> None:
    from infragram.editor import bundle

    runtime = bundle.runtime_script()
    offered = set(re.findall(r"`\?([a-z]+)=", GUIDE.read_text(encoding="utf-8")))
    assert offered, "the guide offers URL options"
    unread = sorted(
        name
        for name in offered
        if f"workspaceParams.get('{name}')" not in runtime
        and f"workspaceParams.has('{name}')" not in runtime
    )
    assert not unread, f"offered in editor.md, never read by the runtime: {unread}"


def test_the_guide_is_reachable_from_the_skill() -> None:
    skill = (skill_assets().parent / "SKILL.md").read_text(encoding="utf-8")
    assert "references/editor.md" in skill
