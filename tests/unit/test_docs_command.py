"""``infragram docs`` lists and prints the reference documents the skill ships.

The references were served to an MCP client (``infragram://references/*``)
but an installed copy's command line had no way to find them: they live
inside the package. The command reads them through
``infragram.paths.skill_references`` like the server does.
"""

from __future__ import annotations

from infragram.cli.user.docs import main, references, resolve
from infragram.paths import skill_references


def test_every_markdown_reference_is_listed_with_what_it_is_about() -> None:
    root = skill_references()
    shipped = references()
    on_disk = sorted(root.glob("*.md")) + sorted((root / "providers").glob("*.md"))
    assert [reference.path for reference in shipped.values()] == on_disk
    assert {"compose", "frames", "export", "providers/aws", "providers/onprem"} <= set(shipped)
    assert shipped["compose"].title == "Compose a diagram as code"
    assert all(reference.title for reference in shipped.values())


def test_a_reference_is_named_the_ways_a_person_would() -> None:
    compose = resolve("compose")
    assert compose is not None
    assert resolve("compose.md") == resolve("Compose") == compose
    aws = resolve("providers/aws")
    assert aws is not None and aws.path.name == "aws.md"
    assert resolve("aws") == resolve("providers\\aws.md") == resolve("providers/aws.md") == aws
    assert resolve("no-such-document") is None


def test_the_listing_the_document_and_its_path(capsys) -> None:
    assert main([]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines] == list(references())
    assert main(["compose"]) == 0
    assert capsys.readouterr().out == references()["compose"].path.read_text(encoding="utf-8")
    assert main(["aws", "--path"]) == 0
    assert capsys.readouterr().out.strip() == str(references()["providers/aws"].path.resolve())
    assert main(["--path"]) == 0
    assert capsys.readouterr().out.strip() == str(skill_references().resolve())


def test_a_misspelt_name_says_which_was_meant(capsys) -> None:
    assert main(["compse"]) == 2
    assert "did you mean compose" in capsys.readouterr().err
    assert main(["kubernets"]) == 2
    assert "did you mean providers/kubernetes" in capsys.readouterr().err
