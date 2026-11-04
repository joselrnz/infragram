#!/usr/bin/env python3
"""Check tracked and non-ignored untracked files for private working data.

Reject a machine-specific path or a personal contact address in file names
and text. Reject sensitive file names, and require project attribution in
the project's own licenses and package metadata. Third-party license notices
keep their original attribution. Ignored local files and Git history require
a separate audit.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())

# Patterns describe private-data shapes without recording a person's identity.
_SEGMENT = r"[^\\/\s\"'<>]+"
_SLASHES = r"[\\/]+"
_HOME_DIRECTORIES = (
    r"\b[A-Za-z]:" + _SLASHES + "Users" + _SLASHES + _SEGMENT,  # Windows profile
    r"(?<![\w.-])" + "/" + "Users" + "/" + _SEGMENT,  # macOS home
    r"(?<![\w.-])" + "/" + "home" + "/" + _SEGMENT,  # Linux home
)
FORBIDDEN = (
    ("a machine-specific path", re.compile("(?:" + "|".join(_HOME_DIRECTORIES) + ")")),
    (
        "a personal contact address",
        re.compile(
            r"(?<![\w.+-])[\w.+-]{1,64}@"
            r"(?:gmail|outlook|hotmail|yahoo|icloud|protonmail|proton)\.(?:com|me)\b",
            re.IGNORECASE,
        ),
    ),
)
SENSITIVE_FILES = re.compile(
    r"(?:^|/)(?:\.env(?:\.[^/]+)?|(?:credentials?|secrets)\.[^/]+|"
    r"id_(?:rsa|ed25519)|[^/]+\.(?:pem|key|pfx|p12|tfstate(?:\.backup)?|bak|orig|swp))$",
    re.IGNORECASE,
)
PROJECT_HOLDER = "Infragram Architect contributors"
# This small, synthetic state is regression input, not a captured live estate.
PUBLIC_FIXTURES = frozenset({"tests/fixtures/estate/terraform.tfstate"})


def sensitive_file(relative: str) -> bool:
    """Allow the reviewed fixture, while rejecting state files elsewhere."""
    return relative not in PUBLIC_FIXTURES and SENSITIVE_FILES.search(relative) is not None


def attribution_errors(root: Path) -> list[str]:
    """Check only project-owned notices; upstream licenses stay intact."""
    errors = []
    for rel in ("LICENSE", "plugin/LICENSE"):
        text = (root / rel).read_text(encoding="utf-8")
        holders = re.findall(r"^Copyright \(c\) [\d-]+ (.+)$", text, re.MULTILINE)
        if holders != [PROJECT_HOLDER]:
            errors.append(f"{rel}: use the project contributor attribution")
    metadata = tomllib.loads((root / "plugin/pyproject.toml").read_text(encoding="utf-8"))
    if metadata.get("project", {}).get("authors") != [{"name": PROJECT_HOLDER}]:
        errors.append("plugin/pyproject.toml: use the project contributor attribution")
    return errors


def git() -> str:
    """The git executable, by its full path."""
    found = shutil.which("git")
    if not found:
        raise SystemExit("git is not on the PATH")
    return found


def tracked_and_untracked() -> list[str]:
    listing = subprocess.run(
        [git(), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    return sorted({rel for rel in listing.split("\0") if rel})


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    ).parse_args(argv)
    hits: list[str] = attribution_errors(ROOT)
    files = tracked_and_untracked()
    for rel in files:
        if sensitive_file(rel):
            hits.append(f"{rel} (sensitive file name)")
        for label, pattern in FORBIDDEN:
            if pattern.search(rel):
                hits.append(f"{rel} (file name carries {label})")
        path = ROOT / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data[:8000]:
            continue
        for number, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
            for label, pattern in FORBIDDEN:
                if pattern.search(line):
                    hits.append(f"{rel}:{number}: {label}: {line.strip()[:100]}")
    if hits:
        print(f"FAIL naming: {len(hits)} leak(s) that must not ship")
        for hit in hits[:50]:
            print(f"  - {hit}")
        if len(hits) > 50:
            print(f"  ... {len(hits) - 50} more")
        return 1
    print(
        f"OK naming: {len(files)} files, no private paths, personal contacts or sensitive files; "
        "project attribution is neutral"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
