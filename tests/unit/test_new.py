"""``infragram new`` starts a diagram file from a shipped example, or with
``--template`` a document from a shipped template.

``new`` copied the example diagram files only; the reference diagrams that
ship as ``.infragram.json`` documents had to be found in the package and
copied by hand, keeping the template's slug, so the copy's exported page
shared the template's saved state. The copy gets its own title and slug, as
an example's does; a copied example says how to draw it (``infragram compose``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from infragram.cli.user.compose import project_from_spec
from infragram.cli.user.new import examples, main
from infragram.cli.user.templates import templates
from infragram.projects import CloudProject


def test_the_list_names_every_example_with_what_it_draws(capsys) -> None:
    assert main(["--list"]) == 0
    listed = capsys.readouterr().out
    assert "aws_three_tier" in listed and "Three-tier web application on AWS" in listed
    assert len(examples()) >= 20


def test_a_copy_gets_its_own_title_and_slug_and_draws(tmp_path: Path, capsys) -> None:
    target = tmp_path / "shop.py"
    assert main(["aws_three_tier", str(target), "--title", "Shop platform"]) == 0
    project = project_from_spec(target)
    assert project.title == "Shop platform" and project.slug == "shop-platform"
    assert main(["aws_three_tier", str(target)]) == 2, "an existing file is kept"
    assert "exists" in capsys.readouterr().err


def test_a_misspelt_example_says_which_was_meant(tmp_path: Path, capsys) -> None:
    assert main(["aws_three_teir", str(tmp_path / "x.py")]) == 2
    assert "did you mean aws_three_tier" in capsys.readouterr().err


def test_a_copied_example_says_how_to_draw_the_copy(tmp_path: Path, monkeypatch) -> None:
    from infragram.cli.user.new import main

    monkeypatch.chdir(tmp_path)
    assert main(["aws_three_tier", "mine.py"]) == 0
    text = (tmp_path / "mine.py").read_text(encoding="utf-8")
    assert "infragram compose mine.py" in text
    assert "scripts/infragram.py" not in text and "examples/aws_three_tier.py" not in text


# ---------------------------------------------- new --template


def test_a_template_copy_gets_its_own_title_and_slug_and_loads(tmp_path: Path, capsys) -> None:
    target = tmp_path / "shop.infragram.json"
    assert main(["--template", "aws-three-tier-web", str(target), "--title", "Shop platform"]) == 0
    assert "from template aws-three-tier-web, slug shop-platform" in capsys.readouterr().out
    project = CloudProject.load(target)
    assert project.title == "Shop platform" and project.slug == "shop-platform"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["topology"]["name"] == "Shop platform", "the root group is renamed with it"
    shipped = json.loads(templates()["aws-three-tier-web"].path.read_text(encoding="utf-8"))
    assert data["topology"]["children"] == shipped["topology"]["children"]


def test_the_copy_keeps_the_title_and_takes_its_slug_from_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["--template", "campus-lan-wan", "branch-office"]) == 0
    written = tmp_path / "branch-office.infragram.json"
    project = CloudProject.load(written)
    assert project.slug == "branch-office"
    assert project.title == templates()["campus-lan-wan"].title
    # with no destination, the template's own name here
    assert main(["--template", "soc-siem"]) == 0
    assert (tmp_path / "soc-siem.infragram.json").is_file()
    capsys.readouterr()


def test_an_existing_document_is_kept_unless_forced(tmp_path: Path, capsys) -> None:
    target = tmp_path / "vpn.infragram.json"
    assert main(["--template", "aws-site-to-site-vpn", str(target)]) == 0
    assert main(["--template", "aws-site-to-site-vpn", str(target)]) == 2
    assert "exists" in capsys.readouterr().err
    assert main(["--template", "azure-api", str(target), "--force"]) == 0
    assert CloudProject.load(target).slug == "vpn"


@pytest.mark.parametrize(
    ("given", "written"),
    [("shop", "shop.infragram.json"), ("shop.json", "shop.infragram.json")],
)
def test_the_document_suffix_is_added(tmp_path: Path, given: str, written: str, capsys) -> None:
    assert main(["--template", "azure-api", str(tmp_path / given)]) == 0
    assert (tmp_path / written).is_file()
    capsys.readouterr()


def test_a_misspelt_or_mistaken_name_says_what_was_meant(tmp_path: Path, capsys) -> None:
    assert main(["--template", "aws-three-teir-web", str(tmp_path / "x")]) == 2
    assert "did you mean aws-three-tier-web" in capsys.readouterr().err
    assert main(["--template", "aws_three_tier", str(tmp_path / "x")]) == 2
    assert "aws_three_tier is an example: infragram new aws_three_tier" in capsys.readouterr().err
    assert main(["aws-three-tier-web", str(tmp_path / "x.py")]) == 2
    assert "is a template: infragram new --template aws-three-tier-web" in capsys.readouterr().err
    assert main(["--template", "azure-api", str(tmp_path / "a"), str(tmp_path / "b")]) == 2
    assert "one destination" in capsys.readouterr().err
    assert not any(tmp_path.iterdir()), "nothing is written for a refused call"


def test_the_list_names_the_examples_then_the_templates(capsys) -> None:
    assert main(["--list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    shipped = examples()
    # the examples are listed first, line for line as before
    assert [line.split()[0] for line in lines[: len(shipped)]] == list(shipped)
    section = lines.index(next(line for line in lines if line.startswith("templates (")))
    assert section == len(shipped) + 1 and lines[len(shipped)] == ""
    listed = [line.split()[0] for line in lines[section + 1 :]]
    assert listed == list(templates())
