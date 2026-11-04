"""The editor page carries the 3D builder: one classic script and its vocabulary."""

from __future__ import annotations

import re

from infragram.author import Diagram
from infragram.exports import render_project_html
from infragram.iso3d.bundle import bundle_source
from infragram.iso3d.vocabulary import FAMILY_COLOURS, GLYPHS, runtime_payload
from infragram.nodes.azure import compute


def test_the_bundle_is_one_classic_script_that_sets_the_renderer() -> None:
    source = bundle_source()
    assert source.startswith("(function () {")
    assert not re.search(r"^(import|export)\s", source, re.MULTILINE), (
        "module statements would not load from a file"
    )
    assert "const THREE = (function () {" in source
    assert "const RoomEnvironment = (function (THREE) {" in source
    assert (
        "window.iso3d = { render, recipes: Object.keys(R), knobs: knobsOf, size: SIZE };" in source
    )


def test_the_vocabulary_payload_carries_families_glyphs_and_the_measurer() -> None:
    payload = runtime_payload()
    assert payload["families"] == FAMILY_COLOURS
    assert set(payload["glyphs"]) == set(GLYPHS) and all(payload["glyphs"].values())
    assert payload["familyGlyph"]["energy"] == "power"
    assert "const size = 128" in payload["measure"] and payload["size"] == 128


def test_every_export_carries_the_builder_once() -> None:
    with Diagram("Small", "One card.", slug="small", providers=("azure",)) as diagram:
        compute.VirtualMachine("VM")
    html = render_project_html(diagram.to_project())
    assert html.count("<script data-infragram-iso3d>") == 1
    assert html.count('id="infragram-iso3d-vocabulary"') == 1
    assert (
        'data-bottom-tab="builder"' in html
        and "[data-iso-builder]" in html
        or "data-iso-builder" in html
    )
    # the script's own closing tags are escaped so none can end the block early
    start = html.index("<script data-infragram-iso3d>")
    end = html.index("</script>", start)
    assert "</" not in html[start + len("<script data-infragram-iso3d>") : end]
