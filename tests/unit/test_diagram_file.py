"""A broken diagram file is told from its own lines, with the nearest real
name, and ``check`` reads a diagram file instead of parsing it as JSON."""

from __future__ import annotations

from pathlib import Path

import pytest

from infragram.cli.user import check
from infragram.cli.user.checker import checker
from infragram.cli.user.compose import project_from_spec
from infragram.exports import ExportError

HEAD = "from infragram.author import Diagram\n"


def _spec(tmp_path: Path, body: str, name: str = "diagram.py") -> Path:
    path = tmp_path / name
    path.write_text(HEAD + body, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("body", "told"),
    [
        (
            "from infragram.nodes.aws import compte\n\nwith Diagram('x'):\n    compte.EC2('a')\n",
            [
                "diagram.py, line 2: from infragram.nodes.aws import compte",
                "ImportError: cannot import name 'compte' from 'infragram.nodes.aws'",
                "infragram.nodes.aws has no compte; did you mean compute",
            ],
        ),
        (
            "from infragram.nodes.aws import compute\n\nwith Diagram('x'):\n    compute.RDS('a')\n",
            [
                "diagram.py, line 5: compute.RDS('a')",
                "infragram.nodes.aws.compute has no RDS; it is infragram.nodes.aws.databases.RDS",
            ],
        ),
        (
            "import infragram.nodes.aws.compte as c\n\nwith Diagram('x'):\n    c.EC2('a')\n",
            [
                "diagram.py, line 2: import infragram.nodes.aws.compte as c",
                "infragram.nodes.aws has no module compte; did you mean infragram.nodes.aws.compute",
            ],
        ),
        (
            "from infragram.nodes.aws import compute\n\nwith Diagram('x'):\n    web = compute.EC2('a'\n",
            ["diagram.py, line 5", "SyntaxError"],
        ),
        (
            "from infragram.nodes.aws import compute\n\nwith Diagram('x'):\n    compute.EC2('a') >> db\n",
            ["diagram.py, line 5: compute.EC2('a') >> db", "NameError: name 'db' is not defined"],
        ),
    ],
)
def test_a_broken_diagram_file_is_told_from_its_own_lines(
    tmp_path: Path, body: str, told: list[str]
) -> None:
    with pytest.raises(ExportError) as caught:
        project_from_spec(_spec(tmp_path, body))
    message = str(caught.value)
    for part in told:
        assert part in message, message
    # not the runner's traceback, nor where the package is installed
    assert "runpy" not in message and "Traceback" not in message and "__init__.py" not in message


def test_check_reads_a_diagram_file_and_never_runs_it(tmp_path: Path, capsys) -> None:
    ran = tmp_path / "ran"
    good = _spec(
        tmp_path,
        "from infragram.nodes.aws import compute\n\nwith Diagram('x'):\n"
        f"    open({str(ran)!r}, 'w')\n    compute.EC2('a')\n",
        "good.py",
    )
    bad = _spec(
        tmp_path,
        "from infragram.nodes.aws import compte\n\nwith Diagram('x'):\n    compte.EC2('a')\n",
        "bad.py",
    )
    plain = tmp_path / "plain.py"
    plain.write_text("print('hello')\n", encoding="utf-8")

    assert check.main([str(good)]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"OK {good}: diagram file, read without running it") and "--verify" in out
    assert check.main([str(bad)]) == 1
    assert "infragram.nodes.aws has no compte; did you mean compute" in capsys.readouterr().out
    assert check.main([str(plain)]) == 1
    assert "not a diagram file" in capsys.readouterr().out
    assert not ran.exists(), "check ran the diagram file"


def test_check_mixes_diagram_files_with_documents(tmp_path: Path, capsys) -> None:
    good = _spec(
        tmp_path,
        "from infragram.nodes.aws import compute\n\nwith Diagram('x'):\n    compute.EC2('a')\n",
        "good.py",
    )
    missing = tmp_path / "missing.infragram.json"
    assert check.main([str(good), str(missing)]) == 1
    out = capsys.readouterr().out
    assert f"OK {good}" in out and f"FAIL {missing}" in out


def test_the_standalone_checker_says_what_a_diagram_file_needs(tmp_path: Path) -> None:
    spec = _spec(tmp_path, "with Diagram('x'):\n    pass\n")
    ok, message = checker().check_path(spec)
    assert not ok and "not valid JSON" not in message and "compose" in message
