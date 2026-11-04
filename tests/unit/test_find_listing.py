"""``infragram find`` lists a whole library, the libraries, and the patterns.

Without a query ``find --library aws`` stopped at an argparse error, so a
library's classes were only readable through the MCP server's catalog
resource; nothing listed the library ids ``--library`` takes; and the
patterns (``MultiAZ``, ``Guardrails``, ``DirectConnectUplink``...) were not
found at all. The patterns are listed after the classes, apart, so every
query still answers with the classes it did.
"""

from __future__ import annotations

import importlib
import json

import pytest

from infragram.catalog.find import (
    find,
    find_patterns,
    libraries,
    library_classes,
    node_classes,
    pattern_classes,
)
from infragram.catalog.providers import load_default_provider_registry
from infragram.cli.user.find import main


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("multi az", "MultiAZ"),
        ("guardrails", "Guardrails"),
        ("direct connect uplink", "DirectConnectUplink"),
        ("endpoint subnet", "EndpointSubnet"),
        ("blueprint", "Blueprint"),
        ("availability zone", "Zone"),
    ],
)
def test_a_pattern_is_found_by_its_name_or_its_words(query: str, expected: str) -> None:
    hits = find_patterns(query)
    assert hits and hits[0].name == expected, [hit.name for hit in hits]


def test_every_pattern_imports_from_the_line_it_is_listed_with() -> None:
    patterns = pattern_classes()
    names = {found.name for found in patterns}
    assert {"MultiAZ", "Zone", "Guardrails", "EndpointSubnet", "DirectConnectUplink"} <= names
    assert {"Blueprint", "Pattern"} <= names
    assert "PatternError" not in names and "ServiceSpec" not in names, "not something to build"
    for found in patterns:
        assert isinstance(getattr(importlib.import_module(found.module), found.name), type)
        assert found.library == "patterns" and found.title
    blueprint = next(found for found in patterns if found.name == "Blueprint")
    assert blueprint.import_line == "from infragram.patterns import Blueprint"


def test_the_class_search_never_answers_with_a_pattern() -> None:
    for query in ("guardrails", "multi az", "zone", "blueprint"):
        assert all(hit.library != "patterns" for hit in find(query))


def test_a_query_prints_the_classes_then_the_patterns(capsys) -> None:
    assert main(["guardrails", "--limit", "3"]) == 0
    lines = capsys.readouterr().out.splitlines()
    classes = [hit.import_line for hit in find("guardrails")[:3]]
    assert [line.split("  #")[0] for line in lines[: len(classes)]] == classes
    header = lines.index("# patterns (infragram.patterns; patterns.md)")
    assert lines[header + 1].startswith("from infragram.patterns.aws import Guardrails  # ")
    assert main(["multi", "az", "--library", "patterns", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["import"] == "from infragram.patterns.aws import MultiAZ"
    assert all(row["library"] == "patterns" for row in rows)


def test_a_whole_library_is_listed_by_category(capsys) -> None:
    classes = library_classes("kubernetes")
    assert classes and any(found.frame for found in classes)
    assert main(["--library", "kubernetes"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"# kubernetes: {len(classes)} classes")
    assert "## frames (infragram.nodes.frames.kubernetes)" in out
    for found in classes:
        assert f"{found.import_line}  # {found.title}" in out
    assert main(["--library", "kubernetes", "--json", "--limit", "5"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 5 and all("category" in row and row["import"] for row in rows)


def test_an_unknown_library_says_which_was_meant(capsys) -> None:
    assert main(["--library", "kubernets"]) == 1
    assert "did you mean kubernetes" in capsys.readouterr().err


def test_no_query_and_no_library_is_still_an_error() -> None:
    with pytest.raises(SystemExit) as stopped:
        main([])
    assert stopped.value.code == 2


def test_the_libraries_are_listed_with_their_names_and_counts(capsys) -> None:
    listed = {library.id: library for library in libraries()}
    registry = load_default_provider_registry()
    providers = list(
        registry.providers.values() if isinstance(registry.providers, dict) else registry.providers
    )
    for provider in providers:
        assert listed[provider.id].name == provider.display_name
    assert listed["aws"].nodes == sum(
        1 for found in node_classes() if found.library == "aws" and not found.frame
    )
    assert listed["frames"].frames == sum(1 for found in node_classes() if found.frame)
    assert listed["patterns"].patterns == len(pattern_classes())
    # every id listed is one --library takes
    for library_id in listed:
        assert library_classes(library_id), library_id
    assert main(["--libraries"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].split()[0] == providers[0].id
    aws = listed["aws"]
    assert f"{aws.nodes} nodes, {aws.frames} frames" in out
    assert out.splitlines()[-1].split()[0] == "patterns"
    assert main(["--libraries", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [row["id"] for row in rows] == list(listed)
