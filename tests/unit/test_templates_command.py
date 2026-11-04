"""``infragram templates`` lists the shipped template documents.

Only the MCP server's ``list_templates`` could name them; the command line
had no way to see what ``.infragram.json`` reference diagrams ship. The
listing reads the documents themselves and counts what each draws the way
the inventory does, so it is held against the inventory here.
"""

from __future__ import annotations

import json

from infragram.cli.cli import main as cli_main
from infragram.cli.commands import project
from infragram.cli.user.templates import SUFFIX, lookup, main, templates
from infragram.paths import skill_assets


def _inventory() -> dict[str, dict]:
    data = json.loads((skill_assets() / "catalog" / "inventory.json").read_text(encoding="utf-8"))
    return {entry["file"]: entry for entry in data["templates"]}


def test_every_shipped_template_is_listed_with_what_the_inventory_records() -> None:
    shipped = templates()
    files = sorted((skill_assets() / "templates" / "cloud").glob(f"*{SUFFIX}"))
    assert len(shipped) == len(files) >= 30
    inventory = _inventory()
    for name, template in shipped.items():
        recorded = inventory[template.path.name]
        assert name == template.path.name.removesuffix(SUFFIX)
        assert (template.slug, template.title, template.kind) == (
            recorded["slug"],
            recorded["title"],
            recorded["kind"],
        )
        assert list(template.providers) == recorded["libraries"]
        assert (template.elements, template.frames, template.connections) == (
            recorded["elements"],
            recorded["frames"],
            recorded["connections"],
        )


def test_a_template_is_found_by_its_name_its_file_or_its_slug() -> None:
    by_name = lookup("azure-api")
    assert by_name is not None
    assert lookup("azure-api.infragram.json") == by_name
    assert lookup(by_name.slug) == by_name and by_name.slug != by_name.name
    assert lookup("no-such-template") is None


def test_the_command_lists_names_titles_and_counts(capsys) -> None:
    assert main([]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(templates())
    first = next(iter(templates().values()))
    assert lines[0].startswith(first.name) and first.title in lines[0]
    assert f"{first.elements} elements, {first.connections} connections" in lines[0]


def test_json_carries_each_template_as_data(capsys) -> None:
    assert main(["--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [row["name"] for row in rows] == list(templates())
    row = next(row for row in rows if row["name"] == "aws-three-tier-web")
    assert row["file"] == "aws-three-tier-web.infragram.json"
    assert row["providers"] == ["aws"] and row["elements"] > 0 and row["connections"] > 0
    assert set(row) >= {"slug", "title", "description", "kind", "frames", "path"}


def test_the_listing_commands_are_user_commands_beside_new_find_and_schema(capsys) -> None:
    order = list(project.COMMANDS)
    assert order.index("templates") == order.index("new") + 1
    assert order.index("recipes") == order.index("find") + 1
    assert order.index("docs") == order.index("schema") + 1
    for name in ("templates", "recipes", "docs"):
        target, help_text = project.COMMANDS[name]
        assert target.endswith(f"infragram.cli.user.{name}:main") and help_text
    assert cli_main(["templates"]) == 0
    assert "aws-three-tier-web" in capsys.readouterr().out
