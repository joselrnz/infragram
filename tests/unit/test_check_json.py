"""`infragram check --json`: the report as one JSON document, for CI and agents.

The text report is for a person; a pipeline had to scrape "FAIL <path>: n
problem(s)" lines to know which file failed and why. With --json every file
checked comes back with its kind, verdict, problems and summary counts, and
the exit status is the same as without it.
"""

from __future__ import annotations

import json
from pathlib import Path

from infragram.cli.user.check import main
from infragram.paths import repo_root

EXAMPLE = repo_root() / "plugin/examples/aws_three_tier.py"


def _run(capsys, *arguments: str) -> tuple[int, dict]:
    code = main([*arguments, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_a_good_document_and_a_diagram_file_report_ok(tmp_path: Path, capsys) -> None:
    template = next(
        (repo_root() / "plugin/skills/infragram-architect/assets/templates").rglob(
            "*.infragram.json"
        )
    )
    code, report = _run(capsys, str(template), str(EXAMPLE))
    assert code == 0 and report["ok"] is True
    kinds = {Path(item["path"]).name: (item["kind"], item["ok"]) for item in report["files"]}
    assert kinds[EXAMPLE.name] == ("diagram", True)
    assert kinds[template.name] == ("project", True)
    project = next(item for item in report["files"] if item["kind"] == "project")
    assert project["summary"]["elements"] > 0 and project["problems"] == []


def test_every_problem_comes_back_and_the_exit_status_says_so(tmp_path: Path, capsys) -> None:
    broken = tmp_path / "broken.infragram.json"
    broken.write_text("{not json", encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()
    code, report = _run(capsys, str(broken), str(empty))
    assert code == 1 and report["ok"] is False
    by_kind = {item["kind"]: item for item in report["files"]}
    assert by_kind["project"]["problems"][0].startswith("not valid JSON")
    assert by_kind["folder"]["problems"] == ["no documents, pages or pictures in this folder"]
