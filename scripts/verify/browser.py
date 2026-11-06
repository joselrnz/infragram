#!/usr/bin/env python3
"""Run the Chromium editor suite, which pytest otherwise skips.

The browser tests render exported pages in Chromium and exercise what the
runtime owns: drag, connect, frames, layers, arrange, zoom, the display
toggle, tooltips, captions, undo, the downloads, and PNG export. They need
Playwright's Chromium, so pytest skips them unless
``INFRAGRAM_RUN_BROWSER_TESTS=1`` is set. This is the one place that sets it,
so CI and a developer run the same thing the same way.

Usage::

    python -m infragram verify:browser [pytest args...]
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = next(path for path in Path(__file__).resolve().parents if (path / ".claude-plugin").is_dir())
SUITES = (
    ROOT / "tests" / "integration" / "test_cloud_editor_browser.py",
    ROOT / "tests" / "integration" / "test_cloud_project_png.py",
    ROOT / "tests" / "integration" / "test_element_popup_browser.py",
    ROOT / "tests" / "integration" / "test_cost_tab_browser.py",
    ROOT / "tests" / "integration" / "test_editor_clipboard_browser.py",
    ROOT / "tests" / "integration" / "test_editor_controls_browser.py",
    ROOT / "tests" / "integration" / "test_editor_editing_browser.py",
    ROOT / "tests" / "integration" / "test_frame_fit_browser.py",
    ROOT / "tests" / "integration" / "test_chrome_components_browser.py",
    ROOT / "tests" / "integration" / "test_engines_browser.py",
    ROOT / "tests" / "integration" / "test_routed_wires_meet_squarely.py",
    ROOT / "tests" / "integration" / "test_parallel_routing_browser.py",
    ROOT / "tests" / "integration" / "test_crossing_bridges_browser.py",
    ROOT / "tests" / "integration" / "test_iso_render.py",
    ROOT / "tests" / "integration" / "test_iso_builder_browser.py",
    ROOT / "tests" / "integration" / "test_recipe_try.py",
    ROOT / "tests" / "integration" / "test_recipes_browser.py",
    ROOT / "tests" / "integration" / "test_export_pictures.py",
    ROOT / "tests" / "integration" / "test_renderer_parity_browser.py",
    ROOT / "tests" / "integration" / "test_frame_corner_badges_browser.py",
    ROOT / "tests" / "integration" / "test_click_and_touch_browser.py",
    ROOT / "tests" / "integration" / "test_steps_browser.py",
    ROOT / "tests" / "integration" / "test_layout_round_trip_browser.py",
    ROOT / "tests" / "integration" / "test_lenses_browser.py",
    ROOT / "tests" / "integration" / "test_editor_save_keeps_browser.py",
    ROOT / "tests" / "integration" / "test_optional_legend_browser.py",
    ROOT / "tests" / "integration" / "test_download_framing_browser.py",
    ROOT / "tests" / "integration" / "test_unused_flag_browser.py",
    ROOT / "tests" / "integration" / "test_changes_findings_browser.py",
    ROOT / "tests" / "integration" / "test_panels_browser.py",
    ROOT / "tests" / "integration" / "test_drill_down_browser.py",
    ROOT / "tests" / "integration" / "test_refresh_lens_browser.py",
)


def main(argv: list[str] | None = None) -> int:
    try:
        import playwright  # noqa: F401
    except ImportError:
        print(
            'ERROR: Playwright isn\'t installed. Run `pip install -e ".[test]"` and '
            "`playwright install chromium`.",
            file=sys.stderr,
        )
        return 2
    # A suite that is not there is a gate that cannot fail; name it and stop,
    # rather than quietly running the ones that are.
    missing = [suite for suite in SUITES if not suite.is_file()]
    if missing:
        for suite in missing:
            print(
                f"FAIL browser: suite not found: {suite.relative_to(ROOT).as_posix()}",
                file=sys.stderr,
            )
        return 1
    env = {**os.environ, "INFRAGRAM_RUN_BROWSER_TESTS": "1", "PYTHONIOENCODING": "utf-8"}
    command = [
        sys.executable,
        "-m",
        "pytest",
        *(str(suite) for suite in SUITES),
        "-q",
        "-p",
        "no:cacheprovider",
        *(argv or []),
    ]
    return subprocess.call(command, cwd=str(ROOT), env=env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
