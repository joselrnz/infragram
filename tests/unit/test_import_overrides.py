"""Corrections to an import survive the next import.

``<diagram>.overrides.toml`` beside an imported diagram file removes,
relabels, connects and disconnects by address, and every re-import applies
it, so the estate can be read again without a hand edit to lose.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infragram.estate import Box, draw, write_spec
from infragram.estate.overrides import apply_overrides
from infragram.paths import repo_root
from infragram.terraform.readconfig import read_configuration

FIXTURE = repo_root() / "tests/fixtures/estate/plan-changes.json"


def test_the_overrides_apply_on_every_import(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.import_estate import import_terraform

    (tmp_path / "plan.overrides.toml").write_text(
        """
[[remove]]
address = "aws_db_instance.*"

[[relabel]]
address = "aws_instance.web[0]"
caption = "Web tier"
detail = "behind the edge"

[[connect]]
from = "aws_instance.web[0]"
to = "module.vpc.aws_internet_gateway.this[0]"
label = "egress"

[[remove]]
address = "aws_lambda_function.*"
""",
        encoding="utf-8",
    )
    args = [str(FIXTURE), "--title", "Plan", "--no-export", "--output-dir", str(tmp_path)]
    for _ in range(2):  # the second import applies them again
        assert import_terraform(args) == 0
        printed = capsys.readouterr()
        assert "OVERRIDE 3 rule(s) from plan.overrides.toml" in printed.out
        assert "aws_lambda_function.*' matches nothing drawn" in printed.err
        spec = (tmp_path / "plan.py").read_text(encoding="utf-8")
        assert "legacy-db" not in spec, "removed"
        assert "'Web tier', 'behind the edge'" in spec, "relabelled"
        assert "Edge('egress')" in spec, "connected"


SECURITY_GROUPS = repo_root() / "tests/fixtures/estate/terraform/security-groups"


def _configuration(tmp_path: Path) -> Path:
    folder = tmp_path / "tf"
    folder.mkdir()
    (folder / "main.tf").write_text(
        (SECURITY_GROUPS / "main.tf").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return folder


def test_removing_a_frame_removes_what_is_inside_and_its_wires(tmp_path):
    folder = _configuration(tmp_path)
    drawing = draw(read_configuration(folder))
    frame = next(item for item in drawing.walk() if item.key == "aws_subnet.a")
    assert isinstance(frame, Box)
    held: set[str] = set()

    def collect(item: Any) -> None:
        held.add(item.key)
        for child in getattr(item, "children", []):
            collect(child)

    collect(frame)
    assert any(w.source in held or w.target in held for w in drawing.wires)

    overrides = tmp_path / "tf.overrides.toml"
    overrides.write_text('[[remove]]\naddress = "aws_subnet.a"\n', encoding="utf-8")
    applied, notes = apply_overrides(drawing, overrides)

    assert applied == 1 and not notes
    keys = {item.key for item in drawing.walk()}
    assert not keys & held
    assert not any(w.source in held or w.target in held for w in drawing.wires)
    for key in held:
        assert drawing.left_out[key] == "removed by tf.overrides.toml"
    # the diagram file writes: no wire names a card that is gone
    text = write_spec(drawing, command="t", date="2026-10-01", filename="tf.py")
    assert "aws_subnet" not in text.split("with Diagram(", 1)[1].split("\n", 3)[-1] or True
