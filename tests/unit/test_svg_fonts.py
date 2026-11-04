"""A standalone picture carries only the faces it draws with.

Every SVG carried every shipped face, Latin and Latin Extended -- once about
300 KB of a 406 KB file, though every picture sets its text in one face and
most in plain Latin. It now
carries the families its text names, and of each only the subsets holding a
character it draws. The editor page keeps every face: a reader types there.
"""

from __future__ import annotations

from infragram.catalog.fonts import font_css_for, font_face_css, used_faces


def _svg(text: str, family: str = "'Inter', sans-serif") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        f'<text font-family="{family}">{text}</text></svg>'
    )


def test_plain_latin_in_inter_carries_one_face() -> None:
    assert used_faces(_svg("Web servers &amp; the database")) == ["inter-normal-latin.woff2"]


def test_a_letter_outside_latin_brings_the_extended_subset() -> None:
    faces = used_faces(_svg("Łódź office"))
    assert faces == ["inter-normal-latin.woff2", "inter-normal-latin-ext.woff2"]


def test_a_second_family_named_by_the_text_comes_along() -> None:
    svg = _svg("CPU 70 %") + _svg("10.0.0.0/16", "'Geist Mono', monospace")
    faces = used_faces(svg)
    assert "inter-normal-latin.woff2" in faces and "geist-mono-normal-latin.woff2" in faces
    assert not any(face.startswith("inter-normal-latin-ext") for face in faces)


def test_the_rules_ignore_the_faces_already_written() -> None:
    # a picture that already holds every rule is judged by its text, not by them
    svg = f"<svg><style>{font_face_css()}</style>" + _svg("plain")[5:]
    assert used_faces(svg) == ["inter-normal-latin.woff2"]
    assert len(font_css_for(svg)) < len(font_face_css()) / 3
