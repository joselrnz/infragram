"""``infragram recipes NAME --svg`` draws one 3D item in Chromium.

A browser suite (``verify:browser`` runs it): the rest of the command is
tested without a browser in tests/unit/test_recipes_command.py.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infragram.cli.user.recipes import main


@pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium render checks",
)
def test_a_recipe_draws_to_an_svg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path / "cache"))
    out = tmp_path / "db.svg"
    argv = ["server", "--svg", str(out), "--family", "storage", "--glyph", "database"]
    assert main([*argv, "--set", "units=3", "--set", "drivesN=12"]) == 0
    said = capsys.readouterr().out
    assert said.startswith(f"SVG      {out} (") and "spec server:[3,12]" in said
    svg = out.read_text(encoding="utf-8")
    assert svg.startswith("<svg") and "data:image/png;base64," in svg
