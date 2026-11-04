#!/usr/bin/env python3
"""Fail when a tracked or untracked publishable text file is not LF.

Every text file in this repository is LF, and ``.gitattributes`` keeps it
so: ``* text=auto eol=lf`` normalises what is committed and what is checked
out, on Windows and Linux alike, so an editor's newline or a generator's
platform default cannot bring a CRLF back. The one exception is artwork:
icon and mark SVGs are content-addressed -- each pack's catalog records their
sha256 -- so they are ``-text`` and stay byte for byte as their source made
them.

This reads what git itself reports (``git ls-files --eol``): a file whose
committed or working copy carries a CRLF, or mixes the two, fails, unless
its attributes say it is not text.

    python scripts/verify/line-endings.py
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())

#: What git reports for a file with a CRLF in it, alone or mixed with LF.
BAD = frozenset({"crlf", "mixed"})


def git() -> str:
    """The git executable, by its full path."""
    found = shutil.which("git")
    if not found:
        raise SystemExit("git is not on the PATH")
    return found


def offenders(listing: str) -> list[str]:
    """The text files ``git ls-files --eol`` reports with a CRLF: one line per
    file, ``i/<index> w/<worktree> attr/<attributes>`` then a tab and the path."""
    found = []
    for line in listing.splitlines():
        meta, _, path = line.partition("\t")
        index, work, *rest = meta.split()
        attributes = " ".join(rest).removeprefix("attr/").split()
        if "-text" in attributes:
            continue
        where = [
            name
            for name, value in (("committed", index), ("working copy", work))
            if value.partition("/")[2] in BAD
        ]
        if where:
            found.append(f"{path} ({', '.join(where)})")
    return found


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    ).parse_args(argv)
    done = subprocess.run(
        [git(), "ls-files", "--eol", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if done.returncode != 0:
        print(f"FAIL line endings: git ls-files failed: {done.stderr.strip()}", file=sys.stderr)
        return 2
    listing = done.stdout
    if not listing.strip():
        print("FAIL line endings: no publishable files were checked", file=sys.stderr)
        return 1
    bad = offenders(listing)
    if bad:
        print(f"FAIL line endings: {len(bad)} text file(s) carry CRLF")
        for item in bad[:30]:
            print(f"  - {item}")
        if len(bad) > 30:
            print(f"  ... {len(bad) - 30} more")
        print('Every text file is LF: write it with newline="\\n", then `git add --renormalize .`.')
        return 1
    print(f"OK line endings: {len(listing.splitlines())} publishable files, every text file LF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
