"""Every export option the command line accepts reaches the export.

``export:set --no-embed`` and ``--drawio-icons`` were parsed and then left out
of the call that drew, so the flag did nothing; ``import:diagram --comment``
wrote no file; ``compose --watch`` dropped ``--view``. The shared options are
now turned into the export's keywords in one place
(:func:`~infragram.cli.user.options.export_keywords`), and these tests hold
every command to it by recording what the export was actually handed.
Also here: the size frame, ``compose`` reading several documents or standard
input, the Terraform zip, and the page URL's routing.
"""

from __future__ import annotations

import inspect
import io
import json
import re
import zipfile

import pytest

from infragram import compose
from infragram.cli.user import compose as compose_command, export_project, export_set, options
from infragram.exports import ExportError, ExportResult
from infragram.exports.browser import editor_page_url
from infragram.exports.framing import SIZES, frame_svg
from infragram.paths import skill_assets
from infragram.terraform import write_zip

TEMPLATE = skill_assets() / "templates" / "cloud" / "aws-three-tier-web.infragram.json"
EVERY_OPTION = [
    "--no-embed",
    "--drawio-icons",
    "embedded",
    "--size",
    "slide-4x3",
    "--renderer",
    "static",
    "--routing",
    "direct",
    "--terraform-zip",
    "--theme",
    "dark",
    "--scale",
    "2",
    "--background",
    "transparent",
    "--display",
    "icon",
]
WANTED = {
    "embed": False,
    "drawio_icons": "embedded",
    "size": "slide-4x3",
    "renderer": "static",
    "routing": "direct",
    "terraform_zip": True,
    "theme": "dark",
    "scale": 2.0,
    "background": "transparent",
    "display": "icon",
}


@pytest.fixture
def recorded(monkeypatch) -> list[dict]:
    """What each export was handed, in place of drawing it."""
    calls: list[dict] = []

    def fake_export_project(project, output_dir, **keywords):
        calls.append({"slug": project.slug, "title": project.title, **keywords})
        output_dir.mkdir(parents=True, exist_ok=True)
        page = output_dir / f"{project.slug}.html"
        page.write_text("<html></html>", encoding="utf-8")
        return ExportResult(html=page)

    monkeypatch.setattr(compose.document, "export_project", fake_export_project)
    return calls


def test_the_keywords_name_every_choice_the_export_takes() -> None:
    """A keyword compose.export takes that the options never fill is an option
    the command line cannot reach."""
    taken = set(inspect.signature(compose.export).parameters) - {
        "source",
        "output_dir",
        "formats",
        "overwrite",
        "check",
        "project_kwargs",
        # read from the file beside the document, not an option (ADR 0009)
        "comments",
    }
    parser = export_project.build_parser()
    assert set(options.export_keywords(parser.parse_args([str(TEMPLATE)]))) == taken


def test_export_project_hands_every_option_to_the_export(recorded, tmp_path) -> None:
    status = export_project.main(
        [str(TEMPLATE), "--formats", "html", "--output-dir", str(tmp_path), *EVERY_OPTION]
    )
    assert status == 0
    assert {key: recorded[0][key] for key in WANTED} == WANTED


def test_export_set_hands_every_option_to_the_export(recorded, tmp_path) -> None:
    folder = tmp_path / "set"
    folder.mkdir()
    (folder / "shop.infragram.json").write_bytes(TEMPLATE.read_bytes())
    status = export_set.main(
        [str(folder), "--formats", "html", "--passes", "0", "--status", "TARGET", *EVERY_OPTION]
    )
    assert status == 0
    assert {key: recorded[0][key] for key in WANTED} == WANTED
    carried = folder / "aws-three-tier-web" / "aws-three-tier-web.infragram.json"
    assert carried.is_file(), "a document is carried beside what it drew, as a .py is"
    readme = (folder / "README.md").read_text(encoding="utf-8")
    for flag in ("--no-embed", "--drawio-icons embedded", "--size slide-4x3", "--terraform-zip"):
        assert flag in readme, f"the rebuild command drops {flag}"
    assert "**Status:** TARGET" in readme


def test_export_set_draws_several_at_once(recorded, tmp_path) -> None:
    folder = tmp_path / "set"
    folder.mkdir()
    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    for slug in ("one", "two", "three"):
        (folder / f"{slug}.infragram.json").write_text(
            json.dumps({**document, "slug": slug}), encoding="utf-8"
        )
    assert export_set.main([str(folder), "--formats", "html", "--passes", "0", "--jobs", "3"]) == 0
    assert sorted(call["slug"] for call in recorded) == ["one", "three", "two"]
    assert export_set.main([str(folder), "--jobs", "0"]) == 2


def test_title_override_and_status_metadata_reach_the_export(recorded, tmp_path) -> None:
    args = [str(TEMPLATE), "--formats", "html", "--output-dir", str(tmp_path)]
    assert export_project.main([*args, "--title", "Shop platform", "--status", "PROPOSED"]) == 0
    assert recorded[0]["title"] == "Shop platform"
    project = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    namespace = export_project.build_parser().parse_args([*args, "--status", "PROPOSED"])
    from infragram.projects import CloudProject

    changed = options.with_overrides(CloudProject.model_validate(project), namespace)
    assert changed.presentation.status == "PROPOSED" and changed.title == project["title"]


def test_offline_and_timeout_are_set_for_the_run(monkeypatch) -> None:
    monkeypatch.delenv("INFRAGRAM_RENDER_OFFLINE", raising=False)
    monkeypatch.delenv("INFRAGRAM_RENDER_TIMEOUT_MS", raising=False)
    parser = export_project.build_parser()
    options.apply_render_settings(
        parser.parse_args([str(TEMPLATE), "--offline", "--timeout", "90"])
    )
    import os

    assert os.environ["INFRAGRAM_RENDER_OFFLINE"] == "1"
    assert os.environ["INFRAGRAM_RENDER_TIMEOUT_MS"] == "90000"
    with pytest.raises(ValueError, match="more than 0"):
        options.apply_render_settings(parser.parse_args([str(TEMPLATE), "--timeout", "0"]))


# ------------------------------------------------------------ compose sources
_TWO = """
from infragram.nodes.aws import compute, databases
from infragram.patterns import Blueprint

web = Blueprint("web-tier", "Web tier", "The web servers.")
web.add(compute.EC2("web"))
data = Blueprint("data-tier", "Data tier", "The database.")
data.add(databases.RDS("orders"))
PROJECTS = [web, data]
"""


def test_compose_exports_every_document_a_file_lists(recorded, tmp_path) -> None:
    spec = tmp_path / "two.py"
    spec.write_text(_TWO, encoding="utf-8")
    assert (
        compose_command.main([str(spec), "--formats", "html", "--output-dir", str(tmp_path)]) == 0
    )
    assert [call["slug"] for call in recorded] == ["web-tier", "data-tier"]
    with pytest.raises(ExportError, match="describes 2 diagrams"):
        compose_command.project_from_spec(spec)


def test_compose_refuses_two_documents_of_one_slug(tmp_path) -> None:
    spec = tmp_path / "same.py"
    spec.write_text(_TWO.replace('"data-tier"', '"web-tier"'), encoding="utf-8")
    with pytest.raises(ExportError, match="repeats the slug web-tier"):
        compose_command.projects_from_spec(spec)


def test_compose_takes_a_blueprint_as_project(recorded, tmp_path) -> None:
    spec = tmp_path / "one.py"
    spec.write_text(_TWO.replace("PROJECTS = [web, data]", "PROJECT = data"), encoding="utf-8")
    assert (
        compose_command.main([str(spec), "--formats", "html", "--output-dir", str(tmp_path)]) == 0
    )
    assert [call["slug"] for call in recorded] == ["data-tier"]


def test_compose_reads_standard_input(recorded, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(_TWO.replace("PROJECTS = [web, data]", "PROJECT = web"))
    )
    assert compose_command.main(["-", "--formats", "html", "--output-dir", str(tmp_path)]) == 0
    assert [call["slug"] for call in recorded] == ["web-tier"]
    assert compose_command.main(["-", "--watch"]) == 2


def test_watch_forwards_the_view_title_and_status(monkeypatch, tmp_path) -> None:
    seen: dict = {}

    def fake_watch(spec, output_dir, arguments, port):
        seen["arguments"] = arguments
        return 0

    import infragram.cli.user.watch as watch_module

    monkeypatch.setattr(watch_module, "watch", fake_watch)
    spec = tmp_path / "x.py"
    spec.write_text("", encoding="utf-8")
    compose_command.main(
        [str(spec), "--watch", "--view", "tag:env=prod", "--title", "T", "--status", "S"]
    )
    arguments = seen["arguments"]
    for flag, value in (("--view", "tag:env=prod"), ("--title", "T"), ("--status", "S")):
        assert arguments[arguments.index(flag) + 1] == value


# ------------------------------------------------------------ the size frame
_PICTURE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
    'viewBox="10 20 400 100" width="400" height="100"><rect data-export-background="" '
    'x="10" y="20" width="400" height="100" fill="#fff"/><g/></svg>\n'
)


def test_fit_leaves_the_picture_as_drawn() -> None:
    assert frame_svg(_PICTURE, "fit") == _PICTURE


def test_a_size_puts_the_drawing_centred_on_its_canvas() -> None:
    framed = frame_svg(_PICTURE, "slide-16x9")
    tag = re.search(r"<svg\b[^>]*>", framed).group(0)
    assert 'width="1280"' in tag and 'height="720"' in tag
    x, y, w, h = (float(n) for n in re.search(r'viewBox="([^"]+)"', tag).group(1).split())
    assert abs(w / h - 1280 / 720) < 1e-3
    # the drawing's own box sits in the middle of the window
    assert abs((x + w / 2) - (10 + 400 / 2)) < 0.01 and abs((y + h / 2) - (20 + 100 / 2)) < 0.01
    ground = re.search(r"<rect data-export-background=\"\"[^>]*/>", framed).group(0)
    assert f'width="{w:g}"' in ground or f'width="{round(w, 2):g}"' in ground


def test_every_size_the_command_line_offers_is_a_preset() -> None:
    assert set(SIZES) == set(options.SIZES)
    with pytest.raises(ExportError, match="unknown size"):
        frame_svg(_PICTURE, "poster")


# ------------------------------------------------------------ the rest
def test_the_terraform_zip_is_laid_out_like_the_page_gives_it(tmp_path) -> None:
    files = {"main.tf": "# main\n", "modules/network/main.tf": "# network\n"}
    first, second = tmp_path / "a.zip", tmp_path / "b.zip"
    write_zip(files, first, folder="shop-terraform")
    write_zip(files, second, folder="shop-terraform")
    assert first.read_bytes() == second.read_bytes(), "the same skeleton makes the same bytes"
    names = zipfile.ZipFile(first).namelist()
    assert names == ["shop-terraform/main.tf", "shop-terraform/modules/network/main.tf"]


def test_the_page_opens_with_straight_wires_only_when_asked(tmp_path) -> None:
    page = tmp_path / "p.html"
    assert "routing" not in editor_page_url(page, "light")
    assert "routing=direct" in editor_page_url(page, "light", routing="direct")
    with pytest.raises(ExportError, match="unknown routing"):
        editor_page_url(page, routing="sideways")


def test_a_diagram_import_writes_its_comment(tmp_path) -> None:
    from infragram.cli.user.import_diagram import import_diagram
    from infragram.paths import repo_root

    source = repo_root() / "tests" / "fixtures" / "diagrams" / "aws-web.drawio"
    comment = tmp_path / "comment.md"
    status = import_diagram(
        [str(source), "--output-dir", str(tmp_path), "--no-export", "--comment", str(comment)]
    )
    assert status == 0
    text = comment.read_text(encoding="utf-8")
    assert text.startswith("### Diagram imported: ") and "drawn" in text
    assert text.count("### Diagram imported: ") == 2, "both pages of the file, in one comment"


def test_export_set_carries_a_saved_layout(recorded, tmp_path) -> None:
    folder = tmp_path / "set"
    folder.mkdir()
    spec = folder / "shop.py"
    spec.write_text(_TWO.replace("PROJECTS = [web, data]", "PROJECT = web"), encoding="utf-8")
    (folder / "shop.layout.json").write_text(json.dumps({}), encoding="utf-8")
    assert export_set.main([str(folder), "--formats", "html", "--passes", "0"]) == 0
    assert (folder / "web-tier" / "web-tier.layout.json").is_file()
