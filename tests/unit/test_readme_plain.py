"""README.md reads cleanly in any Markdown viewer, not only on a forge.

GitHub and Forgejo hide raw HTML such as ``<a id="3d"></a>`` and
``<!-- commands:end -->``, but a viewer that escapes HTML (an editor's preview,
a chat client) prints it as text in the middle of the page. The README
therefore carries no raw HTML outside code: anchors are the headings' own,
and the command reference's markers are Markdown link definitions.
"""

from __future__ import annotations

import re

from infragram.paths import repo_root

README = repo_root() / "README.md"
FENCE = re.compile(r"^```.*?^```", re.M | re.S)
#: A code span may wrap onto the next line, but not across a blank one.
INLINE_CODE = re.compile(r"`(?:[^`\n]|\n(?!\n))*`")
RAW_HTML = re.compile(r"<(?:!--|/?[A-Za-z][A-Za-z0-9-]*(?:\s[^>]*)?/?>)")


def raw_html(markdown: str) -> list[str]:
    """Raw HTML a plain viewer would print, outside fenced and inline code."""
    prose = INLINE_CODE.sub("", FENCE.sub("", markdown))
    return RAW_HTML.findall(prose)


def test_the_readme_carries_no_raw_html() -> None:
    assert raw_html(README.read_text(encoding="utf-8")) == []


def test_the_check_sees_anchors_and_comments_but_not_code() -> None:
    assert raw_html('<a id="3d"></a>\n\n### Drawn in 3D') == ['<a id="3d">', "</a>"]
    assert raw_html("text\n<!-- commands:end -->") == ["<!--"]
    assert raw_html("Run `infragram <command> --help`.\n\n```\n<div>\n```") == []
    assert raw_html("run `python <repo>/plugin\nexport:project` from anywhere") == []
