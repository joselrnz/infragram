"""A gate that checked nothing never says OK.

The lint gate reads the page's JavaScript as well as the Python: a syntax
error in the editor runtime or the 3D renderer passed every gate but the
opt-in browser suite, and ``node --check`` names it now. ``verify:install``
fails when it installed nothing at all, and with ``--strict`` every part a
missing tool left unchecked.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
NODE = shutil.which("node")


@pytest.fixture(scope="module")
def lint():
    spec = importlib.util.spec_from_file_location("lint_gate", ROOT / "scripts/verify/lint.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(NODE is None, reason="needs node on the PATH")
def test_the_gate_names_a_syntax_error(lint) -> None:
    errors = lint.syntax_errors(
        {"good": "(async () => { await 1; })();", "broken": "(async () => { const a = ; })();"},
        NODE,
    )
    assert len(errors) == 1 and errors[0].startswith("broken: ") and "SyntaxError" in errors[0]


@pytest.mark.skipif(NODE is None, reason="needs node on the PATH")
def test_the_page_scripts_pass(lint) -> None:
    scripts = lint.page_scripts()
    assert set(scripts) == {"the editor runtime", "the 3D renderer"}
    assert all(len(text) > 10_000 for text in scripts.values())
    assert lint.syntax_errors(scripts, NODE) == []


# ------------------------------------------------------------------ verify:install
@pytest.fixture(scope="module")
def install():
    spec = importlib.util.spec_from_file_location(
        "install_gate", ROOT / "scripts/verify/install.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_the_install_gate_never_passes_having_installed_nothing(install, capsys) -> None:
    built = [Path("infragram.whl"), Path("infragram.tgz")]
    missing = [
        "no claude on the PATH: Claude Code's installs were not checked",
        "no codex on the PATH: Codex's install was not checked",
    ]
    assert install.report(built, [], [], missing) == 1
    assert "nothing was installed" in capsys.readouterr().err
    # a missing tool is a note, or before a release a failure
    assert install.report(built, ["Codex from the repository"], [], missing[:1]) == 0
    captured = capsys.readouterr()
    assert "NOTE no claude" in captured.out and "OK install" in captured.out
    assert install.report(built, ["Codex from the repository"], [], missing[:1], strict=True) == 1
    assert "FAIL not checked (--strict): no claude on the PATH" in capsys.readouterr().err


# ------------------------------------------------------------------ the test tools
def test_the_test_tools_are_pinned_to_what_ci_runs() -> None:
    """Playwright is the version CI's image carries the browser for, and ruff
    a range whose rules the tree has met; CI installs them from the extra."""
    import re
    import tomllib

    extra = tomllib.loads((ROOT / "plugin/pyproject.toml").read_text(encoding="utf-8"))
    test = extra["project"]["optional-dependencies"]["test"]
    ci = (ROOT / ".forgejo/workflows/ci.yml").read_text(encoding="utf-8")
    images = set(re.findall(r"mcr\.microsoft\.com/playwright:v([\d.]+)", ci))
    assert len(images) == 1 and f"playwright=={images.pop()}" in test, test
    assert any(re.fullmatch(r"ruff>=0\.\d+,<0\.\d+", spec) for spec in test), test
    assert "playwright==" not in ci, "the pin lives in the test extra, once"
