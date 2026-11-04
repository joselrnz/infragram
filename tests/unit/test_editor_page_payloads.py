"""Review fixes in the exported editor page that a page render can prove.

The browser suite drives the behaviour; these check what the shell and the
state builder write, so a regression fails in the unit run first.
"""

from __future__ import annotations

import json
import re

import pytest

from infragram.builders import arrowheads, metrics
from infragram.editor.shell import script_safe
from infragram.exports import render_project_html
from infragram.projects import CloudProject

BREAKOUTS = ("</script>", "</SCRIPT >", "<!--", "&amp;", "<b>bold</b>")


def _project() -> CloudProject:
    return CloudProject.model_validate(
        {
            "schema_version": 1,
            "slug": "review-fixes",
            "title": "Review fixes",
            "description": "A page for the review-fix checks.",
            "provider": "azure",
            "topology": {
                "id": "root",
                "name": "Root",
                "type": "group",
                "children": [
                    {
                        "id": "client",
                        "name": "Client",
                        "type": "client",
                        "connections": [{"target": "api", "kind": "solid", "label": "HTTPS"}],
                    },
                    {"id": "api", "name": "API", "type": "service"},
                ],
            },
        }
    )


def _script_block(html: str, element_id: str) -> str:
    match = re.search(
        rf'<script type="application/json" id="{element_id}"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None, element_id
    return match.group(1)


@pytest.mark.parametrize("breakout", BREAKOUTS)
def test_script_safe_keeps_a_payload_inside_its_script_element(breakout: str) -> None:
    payload = json.dumps({"text": breakout, "list": [breakout]})
    escaped = script_safe(payload)
    assert "<" not in escaped and ">" not in escaped and "&" not in escaped
    assert json.loads(escaped) == json.loads(payload)


def test_every_runtime_payload_goes_through_the_one_escaping() -> None:
    """The arrowhead and metrics specs escape the way the shell does: none
    of the three characters that can end a script block survive."""
    for payload in (arrowheads.runtime_json(), metrics.runtime_json()):
        assert not set(payload) & set("<>&"), payload[:80]
        json.loads(payload)
    assert arrowheads.runtime_json() == script_safe(
        json.dumps(arrowheads.spec(), separators=(",", ":"))
    )
    assert metrics.runtime_json() == script_safe(json.dumps(metrics.spec(), separators=(",", ":")))


def test_a_breakout_in_the_document_cannot_end_the_state_block() -> None:
    project = _project()
    project.topology.children[1].name = "API </script><!-- <b>x</b> &amp;"
    html = render_project_html(project)
    state = json.loads(_script_block(html, "infragram-editor-state"))
    assert state["nodes"][1]["name"] == "API </script><!-- <b>x</b> &amp;"
    body = html.partition('id="infragram-editor-state"')[2]
    # the only "</script>" after the state block's opening tag are real end tags
    assert "</script><!--" not in body


def test_text_panel_reports_the_colour_the_light_canvas_draws() -> None:
    html = render_project_html(_project())
    light = re.search(r'body\[data-workspace-theme="light"\]\{([^}]*)\}', html)
    assert light is not None
    tokens = dict(item.split(":", 1) for item in light.group(1).split(";") if item.startswith("--"))
    control = re.search(
        r'<input[^>]*type="color" data-text-control="textColor" value="([^"]+)"', html
    )
    assert control is not None
    assert control.group(1).lower() == tokens["--text-canvas"].lower()
    assert '<body data-workspace-theme="light">' in html


def test_editor_state_carries_no_field_the_runtime_never_reads() -> None:
    html = render_project_html(_project())
    state = json.loads(_script_block(html, "infragram-editor-state"))
    assert state["edges"], "the project connects client to api"
    for edge in state["edges"]:
        assert "paint" not in edge and "markerId" not in edge
        assert {"width", "dash", "kind"} <= set(edge)
    for node in state["nodes"]:
        assert "focal" not in node
        assert "ink" in node and "inkEdges" in node
    # the frame looks still carry their badge artwork through frame_visual
    assert state["boundaryStyles"]["cloud"]
