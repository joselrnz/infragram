"""The chrome is primitives, views composed from them, and a page of views.

A markup refactor has no compiler behind it. Nothing here throws when a view
is dropped from the page, when a control loses the attribute that names it,
or when a button inside the 3D builder's form quietly becomes a submit -- the
page still renders, and the fault shows up as a region that is missing, a
control a screen reader cannot announce, or a reload that throws the diagram
away. These hold the parts of that contract a test can hold.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from infragram.editor import bundle
from infragram.editor.ui import views
from infragram.editor.ui.components import field, icon_button, text_input
from infragram.editor.ui.views.canvas import SHORTCUTS
from infragram.editor.ui.views.inspector.diagram import template_brief
from infragram.exports import render_project_html
from infragram.projects import CloudProject

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
TEMPLATES = ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "templates"
TEMPLATE = next(TEMPLATES.rglob("*.infragram.json"))
#: The one template that carries a starter brief, so the panel that used to
#: name a provider is actually rendered by these.
BRIEFED = next(TEMPLATES.rglob("digitalocean-base*.infragram.json"))
#: The one template that draws more than one provider's library, so the
#: chrome that only a multicloud document carries is actually rendered.
MULTICLOUD = next(TEMPLATES.rglob("multicloud-base*.infragram.json"))
VIEWS = Path(views.__file__).parent
UI = VIEWS.parent


def test_reference_keeps_full_text_and_escapes_short_overview() -> None:
    project = CloudProject.load(BRIEFED).model_copy(
        update={
            "description": "<script>example</script> " + "Architecture detail " * 40,
            "template_brief": "Full reference\n<a>original text & links</a>",
        }
    )
    markup = template_brief(project, "Cloud")
    assert "data-template-brief open" not in markup
    assert "<script>" not in markup
    assert "&lt;script&gt;example&lt;/script&gt;" in markup
    assert "<pre>Full reference\n&lt;a&gt;original text &amp; links&lt;/a&gt;</pre>" in markup
    overview = re.search(r"<p>(.*?)</p>", markup)
    assert overview and len(overview.group(1)) < 320
    assert template_brief(project.model_copy(update={"template_brief": ""}), "Cloud") == ""


#: Two letters or digits in a row: enough for a word, not enough for "L".
WORD = re.compile(r"[0-9A-Za-z]{2}")

BUTTON = re.compile(r"<button\b([^>]*)>(.*?)</button>", re.S)

#: A named, decimal or hexadecimal character reference.
ENTITY = re.compile(r"&(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#[xX][0-9a-fA-F]+);")

#: Elements that carry no closing tag, in HTML and in the inline SVG.
VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
    "path",
    "circle",
    "rect",
    "use",
    "stop",
    "line",
    "polygon",
    "polyline",
    "ellipse",
    "image",
    "animate",
    "feOffset",
    "feGaussianBlur",
    "feBlend",
}


class _Balance(HTMLParser):
    """Every end tag closes the element that is actually open."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []
        self.bad: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            open_now = self.stack[-1] if self.stack else "nothing"
            self.bad.append(f"line {self.getpos()[0]}: </{tag}> closes {open_now}")
        else:
            self.stack.pop()


@pytest.fixture(scope="module")
def page() -> str:
    return render_project_html(CloudProject.load(TEMPLATE))


@pytest.fixture(scope="module")
def chrome(page: str) -> str:
    """The page's own markup, without the payloads and the runtime it carries.

    The runtime writes markup too -- the sidebar's cards, the layer rows --
    and its source holds the same ``data-`` hooks as selectors. Scanning the
    whole file would be scanning the editor's source as if it were the page.
    """
    return page.split('<script type="application/octet-stream"')[0]


@pytest.fixture(scope="module")
def markup(chrome: str) -> str:
    """The chrome's elements, without the stylesheet the page carries inline.

    A `data-` hook is a selector in the stylesheet as well as an attribute on
    an element, so a scan that includes the `<style>` block counts the rules
    as if they were controls -- which is how the panel-order check once read
    six panels where the page has five.
    """
    return chrome.split("</style>")[-1]


@pytest.fixture(scope="module")
def briefed_chrome() -> str:
    """The chrome of the one template that opens a starter brief."""
    html = render_project_html(CloudProject.load(BRIEFED))
    return html.split('<script type="application/octet-stream"')[0]


def test_the_chrome_escapes_every_ampersand_it_writes(chrome: str, briefed_chrome: str) -> None:
    """A bare `&` in text is a character reference nobody finished.

    Browsers recover from it, which is exactly why it survives: one heading
    read `Transform & containment` beside a sibling that read
    `Align &amp; distribute`, and both looked right. It stops looking right
    the moment a label holds `&a` followed by anything a parser can read as
    an entity name -- and the labels here are the document's own text.
    """
    for markup in (chrome, briefed_chrome):
        bare = [
            markup[max(0, at.start() - 50) : at.start() + 15].replace("\n", " ")
            for at in re.finditer("&", markup)
            if not ENTITY.match(markup, at.start())
        ]
        assert bare == [], bare


def test_every_tag_the_chrome_opens_is_the_one_it_closes(chrome: str, briefed_chrome: str) -> None:
    """A view is a Python f-string: nothing checks that its tags nest.

    A `</div>` one line early moves the inspector inside the canvas, and the
    page still renders -- crookedly, in a way that looks like a CSS bug.
    """
    for markup in (chrome, briefed_chrome):
        parser = _Balance()
        parser.feed(markup)
        assert parser.bad == [], parser.bad
        # the chrome is cut before the page's own closing tags
        assert parser.stack == ["html", "body"], parser.stack


def test_every_button_in_the_page_declares_its_type(chrome: str) -> None:
    """A `<button>` with no type is a submit button.

    The 3D builder is a real `<form>`, so a bare button inside it submits the
    page and reloads it -- which, for a local-first editor holding unsaved
    work in memory, throws the diagram away.
    """
    untyped = [attrs.strip() for attrs, _ in BUTTON.findall(chrome) if 'type="button"' not in attrs]
    assert untyped == [], untyped


def test_a_button_with_no_words_on_it_says_what_it_does(chrome: str) -> None:
    """The chrome's tight spots label their buttons with glyphs and initials.

    A sighted reader gets the glyph and the tooltip. Everyone else gets the
    accessible name or nothing at all: the selection toolbar announced two of
    its buttons as "L" and "T", and its delete button -- a bare backspace
    glyph -- as nothing whatsoever. A name pointed at with `aria-labelledby`
    counts: the grid switch is named by the row it sits in.
    """
    nameless = [
        attrs.strip()
        for attrs, content in BUTTON.findall(chrome)
        if not WORD.search(re.sub(r"<[^>]*>", "", content))
        and "aria-label=" not in attrs
        and "aria-labelledby=" not in attrs
    ]
    assert nameless == [], nameless


def test_no_view_in_the_chrome_names_a_provider() -> None:
    """Nineteen libraries ship. A provider written into the chrome is a bug
    in nineteen of the nineteen exports.

    Everything a region shows about a library comes from the catalog: the
    brand mark and its monogram, the name a chip wears, which libraries get a
    one-click filter, the label on a starter stack's button. This held four
    hardcodes before it existed -- an "Azure outline" style preset, a summary
    special-casing one library's abbreviation, a tuple of three ids deciding
    the quick filters, and a panel heading naming DigitalOcean at every
    reader of every other library.
    """
    from infragram.catalog import load_default_provider_registry

    registry = load_default_provider_registry()
    found: list[str] = []
    for path in sorted([*UI.rglob("*.py"), *UI.rglob("*.css")]):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for provider in registry.providers:
                named = (
                    re.search(rf"\b{re.escape(provider.id)}\b", line, re.I)
                    or provider.display_name in line
                )
                if named:
                    found.append(f"{path.relative_to(UI).as_posix()}:{number} names {provider.id}")
                    break
    assert found == [], found


def test_the_chip_a_library_wears_comes_from_the_catalog() -> None:
    """One library's abbreviation reads as a name and another's does not.

    `short_name` is the badge on a component card -- "AZ", "DO", "K8S". The
    library selector's summary is prose, and "AZ + AWS" is not how anyone
    writes it, which is why both renderers used to carry the same `if id ==
    'azure'`. The catalog says which name to use now, and both read it.
    """
    from infragram.catalog import load_default_provider_registry

    registry = load_default_provider_registry()
    assert registry["azure"].chip == "Azure"
    assert registry["azure"].short_name == "AZ", "the card badge stays an abbreviation"
    assert registry["aws"].chip == "AWS", "a library with no chip name of its own uses the badge"
    quick = [provider.id for provider in registry.providers if provider.quick_filter]
    assert quick == ["azure", "aws", "gcp"], quick


def test_a_control_is_named_once_and_wears_it_twice() -> None:
    """An icon button's name is written as `title` and `aria-label` at once.

    They are the same sentence every time the chrome writes them, and the two
    drifting apart is invisible in the page -- the tooltip says one thing and
    the screen reader another. An icon button has no words of its own, so it
    cannot opt out."""
    markup = icon_button("fit", "Fit diagram to window")
    assert 'title="Fit diagram to window"' in markup
    assert 'aria-label="Fit diagram to window"' in markup
    assert 'class="md-icon-button"' in markup


def test_a_field_wraps_the_control_it_names() -> None:
    """The label is the hit area, not a word sitting next to one."""
    markup = field("Name", text_input('type="text" data-content-control="name"'))
    assert markup.startswith('<label class="md-field">Name<input')
    assert markup.endswith("></label>")


def test_a_tab_says_whether_it_is_the_one_showing() -> None:
    """`aria-selected` is what the stylesheet underlines and what a screen
    reader announces, so a tab row where none is selected is a row that looks
    unvisited and reads as unvisited."""
    from infragram.editor.ui.views.inspector import tab

    chosen, other = tab("diagram", "Diagram", True), tab("style", "Style", False)
    assert 'aria-selected="true"' in chosen and 'class="md-tab inspector-tab"' in chosen
    assert 'aria-selected="false"' in other


def test_every_region_of_the_chrome_reaches_the_page(chrome: str) -> None:
    """A view dropped from `page()` throws nothing: the page renders without
    it, one region short."""
    for marker in (
        'class="provider-sidebar"',
        'class="editor-header"',
        'class="canvas-viewport"',
        'class="right-inspector"',
        'class="bottom-drawer"',
        'data-infragram-diagram="true"',
    ):
        assert marker in chrome, marker


def test_every_inspector_panel_has_a_tab_and_they_are_in_the_same_order(markup: str) -> None:
    """The tab row and the panels are built from one list, so a panel added
    without a tab -- or a tab pointing at a panel that is not there -- is a
    dead tab that blanks the inspector when it is clicked."""
    from infragram.editor.ui.views.inspector import PANELS

    tabs = re.findall(r'data-inspector-tab="([^"]+)"', markup)
    panels = re.findall(r'data-inspector-panel="([^"]+)"', markup)
    assert tabs == panels == [name for name, _ in PANELS]


def test_every_drawer_panel_has_a_tab_and_they_are_in_the_same_order(markup: str) -> None:
    from infragram.editor.ui.views.drawer import PANELS

    assert re.findall(r'data-bottom-tab="([^"]+)"', markup) == [name for name, _ in PANELS]
    assert re.findall(r'data-bottom-panel="([^"]+)"', markup) == [name for name, _ in PANELS]


def test_every_view_module_is_reached_from_the_package() -> None:
    """A view nobody imports is markup somebody wrote and no reader ever
    sees. Add one and this fails until it is composed into the page."""
    on_disk = {path.stem for path in VIEWS.glob("*.py")} - {"__init__"}
    assert on_disk == {"page", "sidebar", "header", "canvas", "drawer"}, on_disk
    source = (VIEWS / "__init__.py").read_text(encoding="utf-8")
    for name in on_disk:
        assert f"from .{name} import" in source, name


def test_every_inspector_panel_module_is_reached_from_its_package() -> None:
    from infragram.editor.ui.views.inspector import PANELS

    folder = VIEWS / "inspector"
    on_disk = {path.stem for path in folder.glob("*.py")} - {"__init__"}
    assert on_disk == {name for name, _ in PANELS}, on_disk


def test_the_single_file_shell_is_gone() -> None:
    """`shell.py` held the markup, the stylesheet and the composition in one
    689-line f-string. It prepares the data now and composes the views."""
    shell = ROOT / "plugin" / "src" / "infragram" / "editor" / "shell.py"
    text = shell.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" not in text, "the page's markup belongs to ui/views/page.py"
    assert "views.page(" in text
    # counted as ruff formats it, which lays a long call out one argument a line
    assert len(text.splitlines()) < 340


def test_every_component_class_the_page_writes_is_styled(markup: str) -> None:
    """A component class with no rules is a control that renders as a box.

    The chrome's look lives entirely in the stylesheets, so a view that asks
    for `md-button--text` where no such variant exists gets a button with no
    variant at all -- and nothing throws. This found three: a button variant
    that was never defined, a tooltip wearing a class one letter off the one
    the sheet styles, and the header's saved-state note, whose rule went out
    with the stylesheet it used to live in.

    The runtime writes markup too, and its rows came out of the port
    unstyled, so what it writes is read here as well.
    """
    styled: set[str] = set()
    for sheet in UI.rglob("*.css"):
        styled |= set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", sheet.read_text(encoding="utf-8")))

    written: set[str] = set()
    for value in re.findall(r'class="([^"]*)"', markup):
        written |= set(value.split())
    runtime = UI.parent / "runtime"
    for module in runtime.glob("*.js"):
        for value in re.findall(r'class="([^"$]*)"', module.read_text(encoding="utf-8")):
            written |= set(value.split())

    unstyled = sorted(name for name in written - styled if name.startswith("md-"))
    assert unstyled == [], unstyled


def test_both_renderers_draw_in_the_same_typeface() -> None:
    """The picture and the editor are two renderers of one document.

    The static side reads `Typography.sans`; the runtime writes the family
    into the SVG it builds, where it was a literal. So moving the document's
    face moved the picture and left the editor drawing the old one -- the
    same document in two faces depending on which renderer you looked at,
    which is exactly the drift the shared arrowhead and metric specs exist to
    stop.
    """
    from infragram.builders.scene import Style

    style = Style()
    family = style.sans.split(",")[0].strip().strip("'\"")
    mono = style.mono.split(",")[0].strip().strip("'\"")

    runtime = UI.parent / "runtime"
    stray: list[str] = []
    for module in sorted(runtime.glob("*.js")):
        for number, line in enumerate(module.read_text(encoding="utf-8").splitlines(), 1):
            if "RETIRED_FACES = " in line:
                continue  # the faces an old drawing names, redrawn in the document's
            for quoted in re.findall(r"'([A-Z][A-Za-z ]+)'", line):
                if quoted in {family, mono} or " " in quoted and quoted.startswith(mono):
                    continue
                if quoted in {"Geist", "Roboto", "Instrument Serif"}:
                    stray.append(
                        f"{module.name}:{number} draws in {quoted!r}, not the document's {family!r}"
                    )
    assert stray == [], stray


# ---------------------------------------------------------- the shortcut sheet


def test_every_shortcut_on_the_sheet_is_one_the_runtime_listens_for() -> None:
    """A sheet that promises a key nothing handles is worse than no sheet:
    the reader stops trusting the rows that are true.

    Each row is checked against the runtime that would have to handle it --
    the modifier the row names, and the key itself.
    """
    runtime = bundle.runtime_script()
    for _, rows in SHORTCUTS:
        for what, keys in rows:
            for key in _keys(keys):
                assert _handled(key, runtime), f"nothing listens for {key} ({what})"


#: How a key on the sheet is written in the runtime that handles it.
LISTENED_FOR = {
    "Ctrl+Z": "toLocaleLowerCase() === 'z'",
    "Ctrl+Shift+Z": "event.shiftKey ? 'redo' : 'undo'",
    "Ctrl+Y": "toLocaleLowerCase() === 'y'",
    "Ctrl+C": "event.key.toLocaleLowerCase() === 'c'",
    "Ctrl+X": "event.key.toLocaleLowerCase() === 'x'",
    "Ctrl+V": "event.key.toLocaleLowerCase() === 'v'",
    "Ctrl+D": "event.key.toLocaleLowerCase() === 'd'",
    "Delete": "event.key === 'Delete'",
    "Backspace": "event.key === 'Backspace'",
    "Ctrl+A": "toLocaleLowerCase() === 'a'",
    "Shift-click": "event.shiftKey || event.ctrlKey || event.metaKey",
    "Tab": "event.key === 'Tab'",
    "Shift+Tab": "event.shiftKey ? -1 : 1",
    "Escape": "event.key === 'Escape'",
    "Arrows": "'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'",
    "Shift+Arrows": "event.shiftKey ? 10 : 1",
    "Alt": "event.altKey",
    "Ctrl+]": "event.key === ']'",
    "Ctrl+[": "event.key === '['",
    "Ctrl+Shift+]": "arrangeSelection(event.shiftKey ? 'forward' : 'to-front')",
    "Ctrl+Shift+[": "arrangeSelection(event.shiftKey ? 'backward' : 'to-back')",
    "Ctrl+G": "toLocaleLowerCase() === 'g'",
    "Ctrl+Shift+G": "event.shiftKey ? 'detach' : 'group'",
    "Ctrl+Shift+L": "event.shiftKey && event.key.toLocaleLowerCase() === 'l'",
    "Ctrl+=": "['+', '='].includes(event.key)",
    "Ctrl+-": "event.key === '-'",
    "Ctrl+0": "event.key === '0'",
    "+": "['+', '=', '-', '0', '1'].includes(event.key)",
    "-": "['+', '=', '-', '0', '1'].includes(event.key)",
    "0": "if (event.key === '0') fitZoom()",
    "1": "else if (event.key === '1') setZoom(1)",
    "?": "event.key === '?'",
    "/": "event.key !== '/'",
}


def _keys(cell: str) -> list[str]:
    """One cell of the sheet, split into the keystrokes it names."""
    return [
        part.strip() for chunk in cell.split("·") for part in chunk.split(" or ") if part.strip()
    ]


def _handled(key: str, runtime: str) -> bool:
    assert key in LISTENED_FOR, f"{key} is on the sheet but not in this map"
    return LISTENED_FOR[key] in runtime


def test_the_map_of_what_listens_for_what_covers_the_sheet_exactly() -> None:
    """The map above is only as good as its fit: an entry nothing on the
    sheet uses is a row somebody deleted without deleting its proof."""
    on_sheet = {key for _, rows in SHORTCUTS for _, cell in rows for key in _keys(cell)}
    assert on_sheet == set(LISTENED_FOR), "the sheet and the map have drifted"


# ---------------------------------------------- hooks the tests reach for

#: Where the browser suites live. A hook they name has to exist somewhere:
#: on the chrome, or in the runtime that writes the rest of the page.
BROWSER_SUITES = ROOT / "tests" / "integration"

#: A `data-` hook as a test writes it in a selector.
HOOK_IN_SELECTOR = re.compile(r"\[(data-[a-z0-9-]+)")

#: Hooks a test builds a selector from rather than naming: `data-{kind}` and
#: friends, where the attribute is assembled at run time.
ASSEMBLED = re.compile(r"\[data-[a-z0-9-]*\{")

# A regression that asserts a removed control is absent does not drive it.
CHECKS_ABSENCE = re.compile(r"^\s*assert .+\.count\(\)\s*==\s*0\b")


def hooks_the_tests_drive() -> dict[str, set[str]]:
    """Every `data-` hook named in a browser suite, by the file naming it."""
    found: dict[str, set[str]] = {}
    for path in sorted(BROWSER_SUITES.glob("*_browser.py")):
        text = path.read_text(encoding="utf-8")
        named = {
            hook
            for line in text.splitlines()
            if not ASSEMBLED.search(line) and not CHECKS_ABSENCE.search(line)
            for hook in HOOK_IN_SELECTOR.findall(line)
        }
        if named:
            found[path.name] = named
    assert found, "no browser suites found; is the path right?"
    return found


def test_hook_gate_distinguishes_required_controls_from_removed_controls(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "BROWSER_SUITES", tmp_path)
    (tmp_path / "sample_browser.py").write_text(
        "page.locator('[data-download-png]').click()\n"
        "assert page.locator('[data-removed-status]').count() == 0\n",
        encoding="utf-8",
    )
    assert hooks_the_tests_drive() == {"sample_browser.py": {"data-download-png"}}


@pytest.fixture(scope="module")
def every_kind_of_page(page: str) -> str:
    """One page of each kind, joined.

    Some chrome only exists on a document that calls for it: the starter
    brief on a briefed template, the multicloud mark on a document that draws
    more than one library. A hook is present if any kind of page writes it.
    """
    return "\n".join(
        (
            page,
            render_project_html(CloudProject.load(BRIEFED)),
            render_project_html(CloudProject.load(MULTICLOUD)),
        )
    )


def test_every_hook_a_browser_test_drives_still_exists(every_kind_of_page: str) -> None:
    """A hook removed from the chrome and left in a test is a nineteen-minute
    timeout, and the browser gate is the only thing that says so.

    Renaming ``data-inspector-routing-toggle`` to a pair of segmented options
    left four tests waiting two minutes each for an element that no longer
    existed. Nothing cheaper than the gate noticed. This does, in a second,
    and names the file and the hook.
    """
    missing: list[str] = []
    for suite, hooks in hooks_the_tests_drive().items():
        for hook in sorted(hooks):
            if hook not in every_kind_of_page:
                missing.append(f"{suite} drives [{hook}], which the page never writes")
    assert not missing, "\n".join(missing)
