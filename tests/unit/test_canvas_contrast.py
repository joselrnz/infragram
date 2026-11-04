"""Every theme's canvas ink stands out from the ground it is drawn on.

The canvas is painted from twelve tokens on ``body`` (``canvasPalette`` in
runtime/08-theme-and-layout.js), one set per theme. The light theme's wires
read at 8:1 against its canvas; the dark themes' read at 1.7:1 and 2.2:1,
which is why a diagram's connectors all but disappeared on them -- and the
same arithmetic is what says a caption or a title is legible. These hold each
ink to a floor against the surface it is drawn on, per theme, so a palette
cannot be retinted into something nobody can read.

Ratios are WCAG 2.1 contrast on the sRGB relative luminance of the two
colours. The floors are the level each ink is held to, not the level it sits
at: the shipped palettes are all above them.
"""

from __future__ import annotations

import re

import pytest

from infragram.editor import bundle

#: (ink token, ground token, floor). Text is held to 4.5:1, the level a
#: reader with low vision needs for small type; a line that carries meaning
#: rather than words is held to 3:1, the level non-text needs.
PAIRS = (
    ("--text-canvas", "--card-bg", 4.5),
    ("--text-canvas", "--canvas-bg", 4.5),
    ("--text-secondary", "--card-bg", 4.5),
    ("--wire-color", "--canvas-bg", 3.0),
    ("--wire-selected", "--canvas-bg", 3.0),
    ("--accent", "--canvas-bg", 3.0),
)
# A drag handle is not ink: it is a filled dot with a ring around it, drawn
# over whatever it sits on, so it is held to nothing here.

#: The three shipped palettes, by the selector that carries their tokens.
THEMES = {
    "dark": ":root",
    "light": 'body[data-workspace-theme="light"]',
    "darker": 'body[data-workspace-palette="darker"]',
}


def _tokens() -> dict[str, dict[str, str]]:
    """Each theme's canvas tokens, a theme inheriting what it does not set."""
    text = (bundle.UI / "styles/tokens.css").read_text(encoding="utf-8")
    blocks: dict[str, dict[str, str]] = {}
    for selector, body in re.findall(r"([^{}]*)\{([^{}]*)\}", text):
        # a comment may sit before a selector; the selector is what follows
        # it, and one selector may carry several blocks (:root holds the
        # canvas tokens, the M3 roles and the shape scale in three).
        name = selector.split("*/")[-1].strip()
        blocks.setdefault(name, {}).update(re.findall(r"(--[a-z-]+):\s*([^;]+)", body))
    base = blocks[THEMES["dark"]]
    return {name: {**base, **blocks[selector]} for name, selector in THEMES.items()}


def _luminance(colour: str) -> float:
    value = colour.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(channel * 2 for channel in value)
    assert re.fullmatch(r"[0-9a-fA-F]{6}", value), colour
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(ink: str, ground: str) -> float:
    first, second = _luminance(ink), _luminance(ground)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("theme", sorted(THEMES))
def test_every_canvas_ink_is_legible_on_its_ground(theme: str) -> None:
    tokens = _tokens()[theme]
    weak = []
    for ink, ground, floor in PAIRS:
        ratio = _contrast(tokens[ink], tokens[ground])
        if ratio < floor:
            weak.append(
                f"{theme}: {ink} {tokens[ink]} on {ground} {tokens[ground]} is {ratio:.2f}:1, under {floor}:1"
            )
    assert not weak, "\n".join(weak)


def test_a_dark_theme_draws_its_connectors_as_plainly_as_the_light_one() -> None:
    """The point of the floors above: a wire is not a hairline on one theme
    and a clear line on another. Within a factor of two of the light theme's
    is close enough that a diagram reads the same on all three."""
    tokens = _tokens()
    light = _contrast(tokens["light"]["--wire-color"], tokens["light"]["--canvas-bg"])
    for theme in ("dark", "darker"):
        ratio = _contrast(tokens[theme]["--wire-color"], tokens[theme]["--canvas-bg"])
        assert ratio >= light / 2, (
            f"{theme} wires read at {ratio:.2f}:1 against light's {light:.2f}:1"
        )
