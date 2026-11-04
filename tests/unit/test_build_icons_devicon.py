"""Regression tests for Devicon viewBox preservation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
BUILD = ROOT / "scripts" / "build" / "icons.py"


def load_build_module():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("infragram_build_icons", BUILD)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load icons.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_devicon_normalization_preserves_the_source_viewbox_and_inherits_colour() -> None:
    build_icons = load_build_module()
    svg = '<svg viewBox="0 0 32 32"><path fill="#123456" d="M0 0h32v32H0z"/></svg>'
    normalized = build_icons.normalize_devicon(svg)
    assert 'viewBox="0 0 32 32"' in normalized, f"source viewBox was not preserved: {normalized}"
    assert 'fill="#123456"' not in normalized, "source fill escaped currentColor normalization"
    assert 'fill="currentColor"' in normalized, "normalized icon does not inherit currentColor"
