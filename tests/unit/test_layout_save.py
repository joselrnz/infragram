"""``infragram layout:save``: what was moved in the editor, kept beside the diagram file."""

from __future__ import annotations

import json
from pathlib import Path

from infragram.paths import skill_assets

TEMPLATE = skill_assets() / "templates" / "cloud" / "azure-hub-spoke-landing-zone.infragram.json"


def test_a_refused_layout_save_keeps_the_layout(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.layout import main

    spec = tmp_path / "v1.py"
    spec.write_text("# a diagram file\n", encoding="utf-8")
    layout = tmp_path / "v1.layout.json"
    layout.write_text(json.dumps({"version": 1, "elements": {"a": {"editor_x": 1}}}), "utf-8")
    assert main([str(TEMPLATE), "--for", str(spec)]) == 2, "a template holds no saved placement"
    assert "holds no placement" in capsys.readouterr().err
    assert json.loads(layout.read_text("utf-8"))["elements"] == {"a": {"editor_x": 1}}
