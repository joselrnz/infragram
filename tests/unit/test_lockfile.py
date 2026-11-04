"""uv.lock is made from plugin/pyproject.toml as it stands.

The audit gate (scripts/verify/audit.py) checks the versions the lock pins,
so a lock left behind after a requirement or the version changed would be
audited in place of what the package asks for. uv notices that itself
(``uv lock --check``); CI's image has no uv, so this reads the two files
and compares what uv records of the project with what the project says.
Run ``uv lock`` at the repository root after changing either.
"""

from __future__ import annotations

import importlib.util
import tomllib

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

from infragram.paths import repo_root

ROOT = repo_root()
LOCK = ROOT / "uv.lock"
PROJECT = ROOT / "plugin" / "pyproject.toml"

Wanted = frozenset[tuple[str, str, SpecifierSet]]


def _declared() -> tuple[str, Wanted, list[str]]:
    """The version, the requirements (name, extra, specifier) and the extras
    plugin/pyproject.toml declares."""
    project = tomllib.loads(PROJECT.read_text(encoding="utf-8"))["project"]
    wanted = {
        (canonicalize_name(r.name), "", r.specifier)
        for r in map(Requirement, project.get("dependencies", []))
    }
    extras = project.get("optional-dependencies", {})
    for extra, requirements in extras.items():
        wanted |= {
            (canonicalize_name(r.name), extra, r.specifier) for r in map(Requirement, requirements)
        }
    return project["version"], frozenset(wanted), list(extras)


def _locked() -> tuple[str, Wanted, list[str]]:
    """The same three as uv recorded them when it made the lock."""
    packages = tomllib.loads(LOCK.read_text(encoding="utf-8"))["package"]
    package = next(p for p in packages if p["name"] == "infragram")
    metadata = package["metadata"]
    wanted = set()
    for entry in metadata["requires-dist"]:
        marker = entry.get("marker", "")
        extra = marker.removeprefix("extra == '").removesuffix("'") if marker else ""
        assert not marker or extra != marker, f"a marker the test does not read: {marker}"
        wanted.add(
            (canonicalize_name(entry["name"]), extra, SpecifierSet(entry.get("specifier", "")))
        )
    return package["version"], frozenset(wanted), metadata.get("provides-extras", [])


def test_the_lock_is_made_from_the_package_as_it_stands() -> None:
    version, wanted, extras = _declared()
    locked_version, locked, locked_extras = _locked()
    assert locked_version == version, "uv.lock is behind the package's version: run `uv lock`"
    assert locked == wanted, (
        "uv.lock is behind plugin/pyproject.toml's requirements: run `uv lock`\n"
        f"  only in pyproject: {sorted(map(str, wanted - locked))}\n"
        f"  only in the lock:  {sorted(map(str, locked - wanted))}"
    )
    assert sorted(locked_extras) == sorted(extras)


def test_the_lock_takes_the_package_from_the_plugin_folder() -> None:
    packages = tomllib.loads(LOCK.read_text(encoding="utf-8"))["package"]
    package = next(p for p in packages if p["name"] == "infragram")
    assert package["source"] == {"editable": "plugin"}


def test_the_audit_checks_every_pinned_file_by_its_hash() -> None:
    spec = importlib.util.spec_from_file_location(
        "infragram_audit", ROOT / "scripts" / "verify" / "audit.py"
    )
    assert spec is not None and spec.loader is not None
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    lines = audit.pinned(LOCK)
    names = {line.split("==")[0] for line in lines}
    assert {"pydantic", "playwright", "pillow", "pytest", "ruff", "mypy", "pip-audit"} <= names
    assert "infragram" not in names  # the project is a folder, not a release
    assert all("--hash=sha256:" in line for line in lines), [
        line for line in lines if "--hash=" not in line
    ]


def test_the_lock_lives_where_uv_looks_for_it() -> None:
    root = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert root["tool"]["uv"]["workspace"]["members"] == ["plugin"]
    assert not (ROOT / "plugin" / "uv.lock").exists(), "one lock, at the workspace root"
