"""Every JSON asset the renderers read loads through a model.

A typo in a shared number, a glyph or the badge record used to surface as a
KeyError deep inside a render or a failing test. Each asset now validates at
load with a field name in the message, and the objects the derivation hands
around are models too.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import infragram.nodes.frames as frames_package
from infragram.builders import metrics
from infragram.builders.architecture import load_style, load_theme
from infragram.builders.frame_style import FrameGlyphs, FramePaint, frame_paint
from infragram.catalog.tiers import container_artwork
from infragram.editor.artwork import FrameVisual, frame_visual

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
CATALOG = ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "catalog"


# ``tests/fixtures/frame-badges.json`` is the reviewed record of what every
# frame wears in its tab: per library, the kinds that carry the vendor's own
# artwork and, for every other kind, why it is blank. Only the tests read it
# (test_frame_badges.py holds the themes to it), so its model lives here;
# loading it through one means a malformed record fails with a field name.
class LibraryBadges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: A library-level remark (AWS: how the deck files its group boxes).
    note: str = ""
    #: kind -> ``collection:slug`` of the vendor artwork the tab carries.
    badges: dict[str, str] = Field(default_factory=dict)
    #: kind -> why this kind is deliberately unbadged.
    blank: dict[str, str] = Field(default_factory=dict)
    #: kind -> why a badge that is not the vendor's own group box is allowed.
    reasons: dict[str, str] = Field(default_factory=dict)
    #: kind -> the recorded exception to the library's rule (AWS Organization).
    exceptions: dict[str, str] = Field(default_factory=dict)


class FrameBadgeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = ""
    source_of_truth: str = ""
    libraries: dict[str, LibraryBadges]


def frame_badges() -> FrameBadgeRecord:
    path = ROOT / "tests" / "fixtures" / "frame-badges.json"
    return FrameBadgeRecord.model_validate_json(path.read_text(encoding="utf-8"))


def test_render_metrics_validate_and_a_missing_number_names_its_field() -> None:
    model = metrics.load()
    assert model.frame.tab == 20 and model.mark.gap == 16
    assert metrics.spec() == model.model_dump()
    broken = json.loads((CATALOG / "render-metrics.json").read_text(encoding="utf-8"))
    del broken["frame"]["tab"]
    with pytest.raises(ValidationError, match="tab"):
        metrics.RenderMetrics.model_validate(broken)


def test_the_frame_defaults_that_used_to_be_constants_are_data() -> None:
    frame = metrics.frame()
    assert "cluster" in frame["dashed_kinds"] and "vpc" not in frame["dashed_kinds"]
    assert frame["widths"] == {"cloud": 1.8}
    style = load_style("kubernetes").cluster
    assert style.dash_for("cluster") == "5,4" and style.dash_for("network") is None
    assert style.width_for("cloud") == 1.8 and style.width_for("network") == 1.0


def test_the_generic_glyphs_load_as_a_model() -> None:
    doc = FrameGlyphs.model_validate_json(
        (CATALOG / "frame-glyphs.json").read_text(encoding="utf-8")
    )
    assert doc.view_box == "0 0 18 18" and len(doc.glyphs) >= 37
    assert all(body.strip() for body in doc.glyphs.values())


def test_the_badge_record_loads_and_covers_every_frame_group() -> None:
    record = frame_badges()
    assert set(frames_package.GROUPS) <= set(record.libraries)
    azure = record.libraries["azure"]
    assert azure.badges["subscription"] == "azure:subscriptions" and "zone" in azure.blank


def test_the_container_artwork_table_loads_as_a_model() -> None:
    table = container_artwork()
    assert table["fallback"] == "frames.generic.Frame"
    assert table["providers"]["aws"]["account"]["frame"] == "frames.aws.Account"


def test_frame_paint_is_a_frozen_model() -> None:
    paint = frame_paint(load_style("azure").cluster, load_theme("azure"), "subscription")
    assert isinstance(paint, FramePaint) and paint.stroke == "#ffcb12"
    with pytest.raises(ValidationError):
        paint.stroke = "#000000"  # type: ignore[misc]


def test_the_runtime_frame_dict_is_a_model_in_camel_case() -> None:
    visual = frame_visual(load_style("azure").cluster, load_theme("azure"), "subscription")
    # Every key is a field of the model under its camelCase alias; "dark" is
    # the night look a light theme's frame carries beside them.
    aliases = {field.alias or name for name, field in FrameVisual.model_fields.items()}
    assert set(visual) == aliases | {"dark"}
    assert {"stroke", "strokeWidth", "tabFill", "iconUri", "labelColor", "labelCase", "pad"} <= set(
        visual
    )
    assert "darkStroke" not in visual and "stroke_width" not in visual
