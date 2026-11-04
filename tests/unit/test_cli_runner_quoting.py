"""A value handed to a cloud's CLI reaches it as one literal argument.

On Windows ``az`` and ``gcloud`` are batch files, which run through cmd.exe;
Python's own quoting is the C runtime's, not cmd.exe's, so a subscription
like ``x"&echo PWNED>pwned.txt&"`` used to run the command after the ``&``.
The runner now quotes every argument for cmd.exe, so a value -- a
subscription, a resource group, a Resource Graph query's JSON body -- is
data, never a command.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from infragram.estate.discover import CallError, cli_runner

pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="batch files run through cmd.exe on Windows"
)

HOSTILE = [
    'x"&echo PWNED>pwned.txt&"',
    "a&b|c<d>e^f",
    'say "hi" & (bye)',
    '{"query": "resources | where type =~ \'microsoft.network/virtualnetworks\'"}',
    "",
    "trailing\\",
    'quote\\"inside',
]


def _fake_cli(folder: Path) -> None:
    """``fakecli.cmd``: prints the arguments it was given, as JSON."""
    script = folder / "echo_args.py"
    script.write_text("import json, sys\nprint(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
    (folder / "fakecli.cmd").write_text(
        f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8", newline=""
    )


def test_a_batch_cli_gets_every_argument_literally(tmp_path: Path, monkeypatch) -> None:
    _fake_cli(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    run = cli_runner("fakecli")
    assert run(HOSTILE) == HOSTILE
    assert not (tmp_path / "pwned.txt").exists(), "nothing after an & ran"


def test_what_cmd_exe_would_expand_is_refused(tmp_path: Path, monkeypatch) -> None:
    _fake_cli(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    run = cli_runner("fakecli")
    for value in ("%PATH%", "line\nbreak"):
        with pytest.raises(CallError, match="cmd.exe"):
            run(["--subscription", value])
    assert json.loads(json.dumps(run(["plain"]))) == ["plain"]
