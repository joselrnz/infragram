"""Regression tests for quote-independent URL SVG normalization."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
BUILD = ROOT / "scripts" / "build" / "icons.py"

SINGLE_QUOTED = (
    "<svg viewBox='0 0 32 16'>"
    "<path style='fill:#123456;stroke:#654321;opacity:.5' d='M0 0h32v16H0z'/>"
    "<circle fill='#abcdef' stroke='#111111' cx='8' cy='8' r='4'/>"
    "</svg>"
)


def load_build_module():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("infragram_build_icons", BUILD)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load icons.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_single_quoted_viewbox_is_preserved() -> None:
    normalized = load_build_module().normalize_url(SINGLE_QUOTED)
    assert 'viewBox="0 0 32 16"' in normalized, (
        f"single-quoted viewBox was not preserved: {normalized}"
    )


def test_single_quoted_colours_are_normalized_to_current_colour() -> None:
    normalized = load_build_module().normalize_url(SINGLE_QUOTED)
    assert not any(color in normalized for color in ("#123456", "#654321", "#abcdef", "#111111")), (
        f"source colors escaped normalization: {normalized}"
    )
    path = re.search(r"<path\b([^>]*)>", normalized)
    assert path is not None, f"normalized path is missing: {normalized}"
    path_attributes = path.group(1)
    for declaration in ("fill:currentColor", "stroke:currentColor", "opacity:.5"):
        assert declaration in path_attributes, (
            f"path lost or failed to normalize {declaration}: {normalized}"
        )
    assert 'fill="currentColor"' in normalized and 'stroke="currentColor"' in normalized, (
        f"standalone quoted colours were not normalized: {normalized}"
    )
