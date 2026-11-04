"""Every picture carries its faces inline; nothing is fetched to draw text.

Inter sets every label of a drawing, the editor's controls and the static
page's heading: one face across the product. Geist Mono ships for monospaced
frame titles and an author who picks it in the Text panel.
"""

from __future__ import annotations

import hashlib
import json
import re

from infragram.catalog.fonts import (
    FAMILIES,
    font_face_css,
    font_style_element,
    fonts_dir,
    load_font_catalog,
    used_faces,
)
from infragram.exports import (
    extract_svg,
    finish_standalone_svg,
    render_project_html,
    render_project_svg,
)
from infragram.projects import CloudProject

TEMPLATES = fonts_dir().parent / "templates" / "cloud"


def standalone_svg(html: str) -> str:
    """The drawing a page embeds, finished as a file of its own."""
    return finish_standalone_svg(extract_svg(html))


def test_the_catalog_and_the_files_agree() -> None:
    catalog = load_font_catalog()
    faces = catalog["faces"]
    assert catalog["counts"]["faces"] == len(faces) == 4
    for face in faces:
        path = fonts_dir() / face["file"]
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == face["sha256"], face["file"]
        assert data[:4] == b"wOF2", face["file"]
        assert (fonts_dir() / face["license_file"]).is_file(), face["license_file"]
        assert face["source_url"].startswith("https://fonts.gstatic.com/")
    assert {face["family"] for face in faces} == set(FAMILIES)
    assert FAMILIES[0] == "Inter"


def test_the_rules_carry_the_files_inline() -> None:
    css = font_face_css()
    assert css.count("@font-face{") == 4
    for family in FAMILIES:
        assert f"font-family:'{family}'" in css
    assert "http" not in css, "no network"
    assert css.count("data:font/woff2;base64,") == 4
    assert "font-weight:400 600" in css and "font-weight:400 700" in css, (
        "the variable files cover the range"
    )
    assert len(css) < 400_000
    assert font_style_element().startswith("<style ")


def test_the_editor_page_and_both_svgs_carry_the_faces() -> None:
    project = CloudProject.load(TEMPLATES / "azure-api.infragram.json")
    page = render_project_html(project)
    assert "fonts.googleapis.com" not in page
    assert page.count("@font-face{") == 4
    # the controls and the drawing's labels are set in the one face
    assert "--md-ref-typeface-plain:'Inter'" in page and "--md-ref-typeface-brand:'Inter'" in page
    static_svg = render_project_svg(project)
    assert "fonts.googleapis.com" not in static_svg
    assert 0 < static_svg.count("@font-face{") < 4, "modern SVGs carry only their used faces"
    assert "font-family:'Inter'" in static_svg
    svg = standalone_svg(page)
    # the faces it draws with travel with the picture, once each
    assert svg.count("@font-face{") == len(used_faces(svg)) >= 1
    assert "font-family:'Inter'" in svg
    # the notice the OFL asks to travel with the fonts is in the skill
    for notice_file in ("OFL-inter.txt", "OFL-geist-mono.txt"):
        notice = (fonts_dir() / notice_file).read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE" in notice.upper(), notice_file
    assert json.loads((fonts_dir() / "catalog.json").read_text(encoding="utf-8"))["source"][
        "license"
    ].startswith("SIL")


def test_every_theme_sets_its_type_in_a_face_the_document_carries() -> None:
    """A theme naming a face nobody ships is a picture nobody can reproduce.

    Two of them did. The AWS skin asked for Amazon Ember and the Azure skin
    for Segoe UI -- neither is in ``assets/fonts``, and neither is licensed
    to be -- so those diagrams drew in whatever the viewer's machine had, or
    in a fallback, which is exactly the drift that embedding the faces was
    meant to end. Everything else about the picture travels with it; the
    typeface has to as well.
    """
    import json

    from infragram.catalog.fonts import FAMILIES, fonts_dir

    shipped = {
        face["family"]
        for face in json.loads((fonts_dir() / "catalog.json").read_text(encoding="utf-8"))["faces"]
    }
    assert shipped == set(FAMILIES), "the catalog and FAMILIES disagree about what ships"

    themes = sorted((fonts_dir().parent / "themes").glob("*.json"))
    assert themes, "no themes found"
    declared: list[tuple[str, str]] = []
    for path in themes:
        theme = json.loads(path.read_text(encoding="utf-8"))
        # the stack lives under `typography`, and a skin that names none
        # inherits the house face
        stack = (theme.get("typography") or {}).get("font") or theme.get("font")
        if stack:
            declared.append((path.name, stack.split(",")[0].strip().strip("'\"")))
    assert declared, "no theme declares a type stack -- this is looking in the wrong place"

    unshipped = [
        f"{name} asks for {family!r}" for name, family in declared if family not in shipped
    ]
    assert unshipped == [], unshipped


def test_every_label_in_a_drawing_is_set_in_inter() -> None:
    """Card titles, details, frame labels, connector labels and the legend:
    the static picture sets each in the one face it embeds, so no text falls
    back to whatever face the viewer's machine has (the Azure look's Segoe UI
    did), and no label is monospaced wider than the room it was given."""
    for template in sorted(TEMPLATES.glob("*.infragram.json")):
        svg = render_project_svg(CloudProject.load(template))
        families = set(re.findall(r'<text\b[^>]*font-family="([^"]*)"', svg))
        assert families, template.name
        assert all(family.startswith("'Inter'") for family in families), (template.name, families)


def test_modern_standalone_svg_keeps_the_subset_needed_by_extended_latin() -> None:
    def picture(text: str, family: str = "Inter") -> str:
        return finish_standalone_svg(
            f'<svg viewBox="0 0 80 30"><text font-family="{family}">' + text + "</text></svg>"
        )

    plain = picture("Azure office")
    extended = picture("Łódź office")
    stacked = picture("Łódź office", "'Inter', sans-serif")
    assert plain.count("@font-face{") == 1
    assert extended.count("@font-face{") == stacked.count("@font-face{") == 2
    assert picture("Azure office", "InterDisplay").count("@font-face{") == 0
    assert "Łódź office" in extended
    assert "data:font/woff2;base64," in extended
    assert "fonts.googleapis.com" not in extended
