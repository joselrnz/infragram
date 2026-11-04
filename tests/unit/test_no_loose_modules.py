"""The package root holds packages, not loose modules.

Every module belongs to a package named for what it does -- ``review/diff``,
``projects/views``, ``models/changes``, ``mcp/protocol`` -- so the folder
listing reads as the package's map and the README's module table stays whole.
Only ``__init__.py`` and ``__main__.py`` (``python -m infragram``) sit at the
root.
"""

from __future__ import annotations

from pathlib import Path

import infragram

PACKAGE = Path(infragram.__file__).resolve().parent


def test_only_the_package_files_sit_at_the_root() -> None:
    loose = sorted(path.name for path in PACKAGE.glob("*.py"))
    assert loose == ["__init__.py", "__main__.py"], (
        f"{', '.join(name for name in loose if not name.startswith('__'))} at the package root: "
        "put each in the package it belongs to"
    )


def test_every_folder_of_modules_is_a_package() -> None:
    folders = {
        path.parent
        for path in PACKAGE.rglob("*.py")
        if "__pycache__" not in path.parts and path.parent != PACKAGE
    }
    missing = sorted(
        str(folder.relative_to(PACKAGE))
        for folder in folders
        if not (folder / "__init__.py").exists()
    )
    assert not missing, f"modules in a folder with no __init__.py: {missing}"


def test_the_readme_maps_every_package() -> None:
    readme = (PACKAGE / "README.md").read_text(encoding="utf-8")
    packages = sorted(
        path.name
        for path in PACKAGE.iterdir()
        if path.is_dir() and (path / "__init__.py").exists() and not path.name.startswith("_")
    )
    unmapped = [name for name in packages if f"`{name}/`" not in readme]
    assert not unmapped, f"the package README's module table leaves out {unmapped}"
