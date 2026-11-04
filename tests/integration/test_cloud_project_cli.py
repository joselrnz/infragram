from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = next(path for path in Path(__file__).resolve().parents if (path / ".claude-plugin").is_dir())


def template_payload() -> dict:
    return {
        "schema_version": 1,
        "slug": "cli-cloud",
        "title": "CLI Cloud",
        "description": "A client connects to a cloud service.",
        "provider": "azure",
        "topology": {
            "id": "root",
            "name": "CLI Cloud",
            "type": "group",
            "children": [
                {
                    "id": "client",
                    "name": "Client",
                    "type": "client",
                    "connections": [{"target": "service", "label": "HTTPS"}],
                },
                {"id": "service", "name": "Service", "type": "service"},
            ],
        },
    }


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "plugin" / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "infragram", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_export_project_cli_writes_html_and_svg(tmp_path: Path) -> None:
    source = tmp_path / "source.infragram.json"
    source.write_text(json.dumps(template_payload()), encoding="utf-8")
    output = tmp_path / "dist"

    result = run_cli(
        "export:project",
        str(source),
        "--formats",
        "template,html,svg",
        "--output-dir",
        str(output),
    )

    assert result.returncode == 0, result.stderr
    assert (output / "cli-cloud.infragram.json").is_file()
    assert (output / "cli-cloud.html").is_file()
    assert (output / "cli-cloud.svg").is_file()
    assert "HTML" in result.stdout
    assert "SVG" in result.stdout


def test_export_project_cli_reports_validation_errors_without_tracebacks(tmp_path: Path) -> None:
    source = tmp_path / "bad.infragram.json"
    payload = template_payload()
    payload["provider"] = "unknown"
    source.write_text(json.dumps(payload), encoding="utf-8")

    result = run_cli("export:project", str(source), "--output-dir", str(tmp_path / "dist"))

    assert result.returncode == 2
    assert "ERROR:" in result.stderr
    assert "unsupported cloud provider" in result.stderr
    assert "Traceback" not in result.stderr


def test_export_project_cli_replaces_its_own_export_but_not_an_edited_one(tmp_path: Path) -> None:
    source = tmp_path / "source.infragram.json"
    source.write_text(json.dumps(template_payload()), encoding="utf-8")
    output = tmp_path / "dist"

    first = run_cli("export:project", str(source), "--formats", "html", "--output-dir", str(output))
    second = run_cli(
        "export:project", str(source), "--formats", "html", "--output-dir", str(output)
    )
    assert first.returncode == 0
    assert second.returncode == 0, "exporting again replaces what the last export wrote"

    page = next(output.glob("*.html"))
    page.write_text(
        page.read_text(encoding="utf-8") + "<!-- saved from the editor -->", encoding="utf-8"
    )
    third = run_cli("export:project", str(source), "--formats", "html", "--output-dir", str(output))
    assert third.returncode == 2
    assert "refusing to overwrite" in third.stderr and page.name in third.stderr


def test_export_project_cli_runs_from_any_directory(tmp_path: Path) -> None:
    # A user exports a diagram from their own project folder: relative paths
    # resolve there, and only the plugin's src has to be on the Python path.
    workdir = tmp_path / "someone-elses-project"
    workdir.mkdir()
    (workdir / "site.infragram.json").write_text(json.dumps(template_payload()), encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "plugin" / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "infragram",
            "export:project",
            "site.infragram.json",
            "--formats",
            "template,html",
            "--output-dir",
            "out",
        ],
        cwd=workdir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (workdir / "out" / "cli-cloud.html").is_file()
    assert (workdir / "out" / "cli-cloud.infragram.json").is_file()
    checker = subprocess.run(
        [
            sys.executable,
            str(ROOT / "plugin/skills/infragram-architect/scripts/project_check.py"),
            "out/cli-cloud.html",
        ],
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert checker.returncode == 0, checker.stdout + checker.stderr
