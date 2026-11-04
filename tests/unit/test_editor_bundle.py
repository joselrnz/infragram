"""The runtime is a folder of numbered modules, joined in evaluation order.

It used to be one file of five thousand lines. Splitting it is only safe under
one condition: the modules share a single closure, so the order they are
joined in *is* the order the statements evaluate. A module moved, renumbered
or dropped does not fail loudly -- it produces a page whose runtime references
a `const` declared later, which throws at load and leaves the reader an empty
canvas.

These hold the contract the split depends on.
"""

from __future__ import annotations

import re
from pathlib import Path

from infragram.editor import bundle
from infragram.exports import render_project_html
from infragram.projects import CloudProject

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
TEMPLATE = next(
    (ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "templates").rglob(
        "*.infragram.json"
    )
)


def test_every_module_is_numbered_once_and_names_itself() -> None:
    """Add a module and this fails until it has a number nobody else uses and
    a header saying what it holds."""
    modules = bundle.runtime_modules()
    assert len(modules) >= 2
    numbers = [path.name.split("-", 1)[0] for path in modules]
    assert all(re.fullmatch(r"\d{2}", number) for number in numbers), numbers
    assert len(set(numbers)) == len(numbers), "two runtime modules share a number"
    for path in modules:
        header = path.read_text(encoding="utf-8").partition("\n")[0]
        assert header.startswith(f"// @module {path.stem}: "), (
            f"{path.name} must start with its @module line"
        )


def test_the_modules_are_joined_in_the_order_they_are_numbered() -> None:
    """The join order is the evaluation order, so it is the numbering."""
    names = [path.name for path in bundle.runtime_modules()]
    assert names == sorted(names)


def test_the_first_module_opens_the_closure_and_the_last_one_closes_it() -> None:
    """One closure. The two ends of it are two specific files, and a module
    inserted before the first or after the last would break the page."""
    script = bundle.runtime_script()
    assert script.startswith("(async () => {")
    assert script.rstrip().endswith("});")
    modules = bundle.runtime_modules()
    assert modules[0].stem.endswith("bootstrap")
    assert modules[-1].stem.endswith("api-and-start")


def test_a_module_without_its_header_is_refused() -> None:
    """The header is how a reader landing in the middle of the bundle knows
    which file to open. A module without one is a module nobody can find."""
    import pytest

    original = bundle.runtime_script.__wrapped__  # past the cache
    victim = bundle.runtime_modules()[0]
    saved = victim.read_bytes()
    try:
        victim.write_bytes(b"const x = 1;\n")
        with pytest.raises(ValueError, match="@module"):
            original()
    finally:
        victim.write_bytes(saved)


def test_the_page_carries_the_whole_runtime_and_none_of_its_headers() -> None:
    """What ships is the joined script. The headers are for the repository:
    a reader opening an exported diagram should not find thirty-five
    comments about a folder layout they cannot see."""
    html = render_project_html(CloudProject.load(TEMPLATE))
    assert bundle.runtime_script().rstrip("\n") in html
    assert "// @module" not in html, "module headers stay in the repository"


def test_every_stylesheet_has_one_place_in_the_cascade() -> None:
    """Add a .css and this fails until it is placed in STYLE_ORDER.

    Cascade order is the behaviour: a rule that moves above the one that
    overrode it is a different page. A file nobody ordered is a file the page
    never loads, which is worse -- it is styling somebody wrote and cannot
    see.
    """
    on_disk = sorted(path.relative_to(bundle.UI).as_posix() for path in bundle.UI.rglob("*.css"))
    assert sorted(bundle.STYLE_ORDER) == on_disk, (
        "add a new .css to bundle.STYLE_ORDER where it belongs"
    )
    assert len(set(bundle.STYLE_ORDER)) == len(bundle.STYLE_ORDER)
    # tokens first, because everything under them reads them; the media
    # queries last, because they override what they narrow
    assert bundle.STYLE_ORDER[0] == "styles/tokens.css"
    assert bundle.STYLE_ORDER[-1] == "styles/responsive.css"


def test_the_stage_rule_is_sized_for_the_diagram_it_draws() -> None:
    """The one rule in the stylesheet that is not the same for every diagram.

    It was an f-string interpolation while the stylesheet lived inside
    shell.py, which is why the stylesheet could not simply become a file:
    moved as it was, every page shipped the literal text ``{scene.width}px``.
    """
    sized = bundle.stylesheet(1280, 720)
    assert "width:1280px;height:720px" in sized
    assert bundle.STAGE_WIDTH not in sized and bundle.STAGE_HEIGHT not in sized
    # and it is still where it ran, not appended to the end: before the
    # responsive sheet's media queries, which narrow it
    stage = sized.index(".diagram-stage svg{display:block")
    assert stage < sized.rindex("@media"), "the stage rule moved past the media queries"


def test_a_page_is_the_same_page_every_time_it_is_rendered() -> None:
    """Two exports of one document were two different files.

    `boundaryStyles` was built by iterating a set, whose order Python
    randomises per process, so the same template produced a different page in
    every run. Nothing read those keys in order, so nothing broke -- but an
    export nobody can reproduce cannot be diffed, cached, or checked against
    the copy somebody else made.
    """
    import json
    import re

    html = render_project_html(CloudProject.load(TEMPLATE))
    state = re.search(r'id="infragram-editor-state"[^>]*>(.*?)</script>', html, re.S)
    assert state is not None
    keys = list(json.loads(state.group(1))["boundaryStyles"])
    assert keys == sorted(keys), "boundary styles are not in a settled order"


def test_the_single_file_is_gone() -> None:
    """It was `plugin/src/infragram/editor_runtime.js` and it is the folder now.
    Left behind, it would be the copy somebody edited while the page ran the
    other one."""
    assert not (ROOT / "plugin" / "src" / "infragram" / "editor_runtime.js").exists()
