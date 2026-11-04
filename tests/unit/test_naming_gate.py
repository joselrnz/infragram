"""Privacy checks reject local paths, personal contacts and private attribution."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())


def _gate():
    spec = importlib.util.spec_from_file_location("naming", ROOT / "scripts/verify/naming.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _match(text: str) -> str | None:
    for label, pattern in _gate().FORBIDDEN:
        if pattern.search(text):
            return label
    return None


WINDOWS_HOME = "C:" + chr(92) + "Users" + chr(92) + "someone" + chr(92) + "private"
MAC_HOME = "/" + "Users" + "/someone/private"
LINUX_HOME = "/" + "home" + "/someone/private"
PERSONAL_CONTACT = "person" + "@" + "gmail" + ".com"


@pytest.mark.parametrize(
    "text,expected",
    [
        (WINDOWS_HOME, "a machine-specific path"),
        (LINUX_HOME, "a machine-specific path"),
        (MAC_HOME, "a machine-specific path"),
        (PERSONAL_CONTACT, "a personal contact address"),
        (PERSONAL_CONTACT.upper(), "a personal contact address"),
    ],
)
def test_the_gate_catches_private_data(text: str, expected: str) -> None:
    assert _match(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Copyright (c) 2025-2026 Infragram Architect contributors",
        "Infragram Architect draws infrastructure.",
        "frames.aws.VPC contains the subnets",
        "upstream/icons/home/home.svg",
        "fixture@example.invalid",
        "iVBORw0KGgoAAAencodedpayloadNSUhEUgAAAQAAAAEACAYAAA",
    ],
)
def test_the_gate_leaves_project_and_fixture_content_alone(text: str) -> None:
    assert _match(text) is None


@pytest.mark.parametrize("name", [".env.local", "local.tfstate", "secret.pfx", "credentials.json"])
def test_sensitive_filenames_are_rejected(name: str) -> None:
    assert _gate().sensitive_file(name)


def test_only_the_reviewed_synthetic_state_is_allowed() -> None:
    gate = _gate()
    assert not gate.sensitive_file("tests/fixtures/estate/terraform.tfstate")
    assert gate.sensitive_file("tests/fixtures/estate/private.tfstate")
    assert gate.sensitive_file("terraform.tfstate")


def test_project_attribution_uses_the_project_name() -> None:
    assert _gate().attribution_errors(ROOT) == []


def test_private_attribution_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "plugin").mkdir()
    license_text = "MIT License\n\nCopyright (c) 2025-2026 Example Maintainer\n"
    for path in (tmp_path / "LICENSE", tmp_path / "plugin/LICENSE"):
        path.write_text(license_text, encoding="utf-8")
    (tmp_path / "plugin/pyproject.toml").write_text(
        '[project]\nauthors = [{ name = "Example Maintainer" }]\n', encoding="utf-8"
    )
    assert len(_gate().attribution_errors(tmp_path)) == 3


def test_every_forbidden_class_is_documented() -> None:
    gate = _gate()
    assert len(gate.FORBIDDEN) == 2
    for label, _pattern in gate.FORBIDDEN:
        assert label in (gate.__doc__ or "")
