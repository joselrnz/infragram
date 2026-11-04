"""A token derived from a theme's colour is declared where the theme sets it.

A custom property whose value reads another resolves on the element it is
declared on, and is inherited as the resolved value. Two of them --
``--md-disabled-content`` and ``--md-disabled-container``, both
``color-mix`` of ``--md-sys-color-on-surface`` -- were declared on ``:root``,
where on-surface is the dark theme's. The light and darker themes override
on-surface on ``body`` and never re-derived them, so every disabled control
on the light theme (the default) was a pale grey on a pale surface at about
1:1: undo and redo at page open, a preset with nothing selected, a disabled
field, a disabled chip.

This holds every derived token to the element its ingredients are set on.
"""

from __future__ import annotations

import re

from infragram.editor import bundle

#: Where each palette's tokens live; :root carries the dark theme.
ROOT = ":root"


def _blocks() -> list[tuple[str, str]]:
    text = (bundle.UI / "styles/tokens.css").read_text(encoding="utf-8")
    return [
        (selector.split("*/")[-1].strip(), body)
        for selector, body in re.findall(r"([^{}]*)\{([^{}]*)\}", text)
    ]


def _declared(body: str) -> dict[str, str]:
    return dict(re.findall(r"(--[a-z0-9-]+):\s*([^;]+)", body))


def test_a_token_derived_from_an_overridden_colour_is_not_stranded_on_root() -> None:
    blocks = _blocks()
    overridden: set[str] = set()
    for selector, body in blocks:
        if selector != ROOT:
            overridden |= set(_declared(body))
    stranded = []
    for selector, body in blocks:
        if selector != ROOT:
            continue
        for name, value in _declared(body).items():
            ingredients = set(re.findall(r"var\((--[a-z0-9-]+)", value))
            missed = sorted(ingredients & overridden)
            if missed:
                stranded.append(
                    f"{name} on :root reads {', '.join(missed)}, which a theme overrides"
                )
    assert not stranded, (
        "declare these where their ingredients are set (on body), or every theme "
        "but the one :root carries gets the wrong value:\n" + "\n".join(stranded)
    )


def test_every_theme_derives_its_own_disabled_tokens() -> None:
    """The case above, named: a theme that sets on-surface has the derived
    tokens available on the same element."""
    on_body = [
        selector for selector, body in _blocks() if "--md-disabled-content" in _declared(body)
    ]
    assert on_body == ["body"], on_body
    themes = [
        selector for selector, body in _blocks() if "--md-sys-color-on-surface" in _declared(body)
    ]
    assert any(selector.startswith("body") for selector in themes), themes
