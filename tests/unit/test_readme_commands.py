"""README.md's command reference is the CLI registry's, and the docs gate says so.

The table between ``[//]: # (commands:start)`` and ``[//]: # (commands:end)`` is
generated from ``infragram.cli.commands.project.COMMANDS`` by
``scripts/verify/docs-sync.py --write-commands``; the gate fails when a
command is added, renamed, dropped or re-described without regenerating it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from infragram.cli.commands import project
from infragram.paths import repo_root

ROOT = repo_root()


@pytest.fixture(scope="module")
def docs_sync():
    spec = importlib.util.spec_from_file_location(
        "infragram_docs_sync", ROOT / "scripts" / "verify" / "docs-sync.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_readme_lists_every_user_command_with_its_help(docs_sync) -> None:
    errors: list[str] = []
    docs_sync.check_commands_table(errors)
    assert errors == []
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name, (_target, help_text) in project.COMMANDS.items():
        assert f"| `{name}` | {help_text} |" in readme


def test_a_command_the_readme_lacks_fails_the_gate(docs_sync, tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        (ROOT / "README.md").read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
    )
    grown = {**project.COMMANDS, "made:up": ("call:nowhere:main", "a command nobody wrote down")}
    errors: list[str] = []
    docs_sync.check_commands_table(errors, readme, grown)
    assert len(errors) == 1 and "made:up" in errors[0] and "--write-commands" in errors[0]

    assert docs_sync.write_commands_table(readme, grown) is True
    errors = []
    docs_sync.check_commands_table(errors, readme, grown)
    assert errors == []
    assert "| `made:up` | a command nobody wrote down |" in readme.read_text(encoding="utf-8")
    assert docs_sync.write_commands_table(readme, grown) is False


def test_the_markers_are_required_once_each(docs_sync, tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n\nNo command reference here.\n", encoding="utf-8")
    errors: list[str] = []
    docs_sync.check_commands_table(errors, readme)
    assert len(errors) == 1 and docs_sync.COMMANDS_START in errors[0]
    with pytest.raises(ValueError):
        docs_sync.write_commands_table(readme)


def test_a_pipe_in_a_help_line_stays_inside_its_cell(docs_sync) -> None:
    table = docs_sync.commands_table({"x": ("call:x:main", "this | that")})
    assert "| `x` | this \\| that |" in table.splitlines()
