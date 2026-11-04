"""The gate that keeps every text file LF.

``.gitattributes`` normalises line endings (``* text=auto eol=lf``), and
the gate reads what git reports so a CRLF that slipped past -- a file added
before the attributes, a checkout with odd settings -- fails loudly. SVG
artwork is ``-text``: its bytes are hashed in the catalogs and stay as they
are. These check the gate itself, because a gate nobody tests is a gate that
reports a pass it never earned.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
GATE = ROOT / "scripts" / "verify" / "line-endings.py"


def _gate():
    """The gate module, loaded from its hyphenated path."""
    spec = importlib.util.spec_from_file_location("line_endings_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_a_crlf_or_mixed_text_file_is_named_and_artwork_is_not() -> None:
    listing = "\n".join(
        [
            "i/lf    w/lf    attr/text=auto eol=lf \tsrc/fine.py",
            "i/crlf  w/crlf  attr/text=auto eol=lf \tsrc/committed.py",
            "i/lf    w/mixed attr/text=auto eol=lf \tsrc/edited.py",
            "i/crlf  w/crlf  attr/-text            \tassets/icon.svg",
            "i/-text w/-text attr/-text            \tassets/icon.png",
        ]
    )
    assert _gate().offenders(listing) == [
        "src/committed.py (committed, working copy)",
        "src/edited.py (working copy)",
    ]


def test_the_gate_fails_on_a_crlf_and_passes_once_it_is_lf(tmp_path: Path) -> None:
    """End to end in a throwaway repository with the same attributes."""
    repo = tmp_path / "repo"
    (repo / ".claude-plugin").mkdir(parents=True)
    (repo / ".claude-plugin" / "plugin.json").write_bytes(b"{}\n")
    (repo / "scripts" / "verify").mkdir(parents=True)
    (repo / "scripts" / "verify" / "line-endings.py").write_bytes(GATE.read_bytes())
    (repo / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    (repo / "icon.svg").write_bytes(b"<svg>\r\n</svg>\r\n")
    module = repo / "module.py"
    module.write_bytes(b"one\ntwo\n")

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    git("config", "core.autocrlf", "false")
    git("config", "user.email", "gate@example.invalid")
    git("config", "user.name", "Gate")
    git("add", "-A")
    git("commit", "-qm", "first")

    def gate() -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(repo / "scripts" / "verify" / "line-endings.py")],
            cwd=repo,
            capture_output=True,
            text=True,
        )

    assert gate().returncode == 0, "LF text and CRLF artwork pass"
    untracked = repo / "new.py"
    untracked.write_bytes(b"new\r\n")
    failed = gate()
    assert failed.returncode == 1 and "new.py (working copy)" in failed.stdout, failed.stdout
    untracked.write_bytes(b"new\n")
    module.write_bytes(b"one\r\ntwo\r\n")
    failed = gate()
    assert failed.returncode == 1 and "module.py (working copy)" in failed.stdout, failed.stdout
    module.write_bytes(b"one\ntwo\n")
    assert gate().returncode == 0, "writing it LF again clears it"


def test_the_repository_is_lf() -> None:
    done = subprocess.run(
        ["git", "ls-files", "--eol", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert done.stdout.strip(), "the gate must actually inspect files"
    assert _gate().offenders(done.stdout) == []


def test_the_gate_checks_an_unborn_repository_and_ignores_caches(tmp_path: Path) -> None:
    gate = _gate()
    gate.ROOT = tmp_path
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    assert gate.main([]) == 1, "an empty scan cannot pass"
    (tmp_path / ".gitignore").write_bytes(b"cache/\n")
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "private.txt").write_bytes(b"ignored\r\n")
    source = tmp_path / "source.py"
    source.write_bytes(b"untracked\r\n")
    assert gate.main([]) == 1
    source.write_bytes(b"untracked\n")
    assert gate.main([]) == 0, "publishable files pass without staging or committing"


def test_the_gate_is_registered_so_it_actually_runs() -> None:
    """A gate that no command and no CI step calls protects nothing."""
    from infragram.cli import COMMANDS, VERIFY_ALL, VERIFY_QUICK

    assert COMMANDS["verify:line-endings"][0] == "verify/line-endings.py"
    assert ("verify/line-endings.py", ()) in VERIFY_ALL
    assert ("verify/line-endings.py", ()) in VERIFY_QUICK
    workflows = sorted(ROOT.glob(".*/workflows/ci.yml"))
    assert workflows, "no CI workflow found"
    for workflow in workflows:
        # a workflow runs the gate by its script, or through verify:quick,
        # which runs it (asserted above)
        text = workflow.read_text(encoding="utf-8")
        assert "scripts/verify/line-endings.py" in text or "infragram verify:quick" in text, (
            f"{workflow.relative_to(ROOT)} does not run the gate"
        )
