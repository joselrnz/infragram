"""What sits in the user's folder is data until the user composes it.

- a diagram file whose name is a standard library module's (``logging.py``)
  does not stand in for that module when a tool runs a command there: the
  MCP server and ``compose --watch`` start Python with ``-P``;
- ``check`` reads a diagram file without running it, and that includes the
  user's own helper modules: only the infragram package itself is imported to
  ask whether a class exists, never ``infragram_helpers``.
"""

from __future__ import annotations

from pathlib import Path

from infragram.mcp import handle
from infragram.paths import repo_root

EXAMPLE = repo_root() / "plugin/examples/aws_three_tier.py"


def _call(name: str, arguments: dict) -> dict:
    answer = handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert answer is not None
    return answer["result"]


def test_a_diagram_named_like_the_standard_library_shadows_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source = EXAMPLE.read_text(encoding="utf-8")
    written = _call(
        "compose_source",
        {"source": source, "spec": "logging.py", "formats": "template", "verify": False},
    )
    assert written["isError"] is False, written["content"][0]["text"]
    checked = _call("check", {"paths": ["logging.py"]})
    assert checked["isError"] is False, checked["content"][0]["text"]
    assert "partially initialized module" not in checked["content"][0]["text"]


def test_check_never_runs_a_helper_module_beside_the_diagram(tmp_path: Path, monkeypatch) -> None:
    from infragram.cli.user.check import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "infragram_helpers.py").write_text(
        "from pathlib import Path\nPath('RAN.txt').write_text('ran')\n", encoding="utf-8"
    )
    (tmp_path / "d.py").write_text(
        "import infragram_helpers\n"
        "from infragram.author import Diagram\n"
        "from infragram.nodes.aws.compute import EC2\n"
        "with Diagram('D'):\n"
        "    EC2('web')\n",
        encoding="utf-8",
    )
    main(["d.py"])
    assert not (tmp_path / "RAN.txt").exists(), "check reads; it does not run the user's modules"
