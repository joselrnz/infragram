"""``infragram export:set``: a folder of diagram files, one folder per diagram.

Held here: it refuses what it cannot do before anything is written -- a
folder with no specs, two specs that draw one diagram, a diagram folder that
exists (without ``--force``), and a README the set did not write, which is
the user's -- and it knows the README it wrote itself.
"""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path

from infragram.cli.user.export_set import README_MARK, _ours, main
from infragram.paths import plugin_root

EXAMPLE = plugin_root() / "examples" / "aws_three_tier.py"


def _folder(tmp_path: Path) -> Path:
    folder = tmp_path / "set"
    folder.mkdir()
    shutil.copy(EXAMPLE, folder / "three_tier.py")
    return folder


def test_a_readme_the_set_did_not_write_is_the_users(tmp_path: Path, capsys) -> None:
    folder = _folder(tmp_path)
    (folder / "README.md").write_text("MY OWN README\n", encoding="utf-8")
    assert main([str(folder)]) == 2
    assert "which export:set did not write" in capsys.readouterr().err
    assert (folder / "README.md").read_text(encoding="utf-8") == "MY OWN README\n"
    assert sorted(path.name for path in folder.iterdir()) == ["README.md", "three_tier.py"], (
        "nothing was written"
    )


def test_the_set_knows_its_own_readme(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(f"{README_MARK}\n# set\n", encoding="utf-8")
    assert _ours(readme)
    readme.write_text(
        "# set\n\n1 diagram, drawn with infragram 0.4.0.\n\n## Rebuilding\n\n"
        "```bash\ninfragram export:set set --force\n```\n",
        encoding="utf-8",
    )
    assert _ours(readme), "a set built before the mark"
    readme.write_text("# My notes\n\n## Rebuilding\nby hand\n", encoding="utf-8")
    assert not _ours(readme)


def test_what_cannot_be_done_is_refused_before_anything_is_written(tmp_path: Path, capsys) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main([str(empty)]) == 2
    folder = _folder(tmp_path)
    shutil.copy(EXAMPLE, folder / "same_diagram.py")
    assert main([str(folder)]) == 2
    err = capsys.readouterr().err
    assert "no diagrams (*.py or *.infragram.json)" in err
    assert "two specs draw the same diagram" in err
    (folder / "same_diagram.py").unlink()
    (folder / "aws-three-tier-composed").mkdir()
    assert main([str(folder)]) == 2
    err = capsys.readouterr().err
    assert "refusing to replace" in err and "aws-three-tier-composed; pass --force" in err


def test_the_set_takes_the_export_options_compose_takes(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """``--formats`` and ``--prices`` mean what they mean for one diagram; the
    README lists what was written and rebuilds it with the same options."""
    import json

    from infragram.pricing import fetch
    from infragram.pricing.aws import LOCATIONS

    def offline(url: str) -> bytes:
        if url == LOCATIONS:
            return json.dumps(
                {
                    "US East (N. Virginia)": {
                        "name": "US East (N. Virginia)",
                        "code": "us-east-1",
                        "type": "AWS Region",
                    }
                }
            ).encode()
        row = {
            "price": "0.0960000000",
            "Instance Type": "m6i.large",
            "vCPU": "2",
            "Memory": "8 GiB",
        }
        return json.dumps(
            {
                "manifest": {
                    "hawkFilePublicationDate": "2026-09-24T00:00:00Z",
                    "currencyCode": "USD",
                },
                "regions": {"US East (N. Virginia)": {"m6i.large US East (N. Virginia)": row}},
            }
        ).encode()

    monkeypatch.setattr(fetch, "cached_fetch", offline)
    folder = _folder(tmp_path)
    out = tmp_path / "out"
    assert (
        main(
            [
                str(folder),
                "--output-dir",
                str(out),
                "--formats",
                "template,html",
                "--prices",
                "--passes",
                "0",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "PRICED   " in captured.out and "USD" in captured.out
    diagram = out / "aws-three-tier-composed"
    assert sorted(path.name for path in diagram.iterdir()) == [
        "aws-three-tier-composed.html",
        "aws-three-tier-composed.infragram.json",
        "aws-three-tier-composed.py",
    ]
    document = json.loads(
        (diagram / "aws-three-tier-composed.infragram.json").read_text(encoding="utf-8")
    )
    assert '"price"' in json.dumps(document), "the priced document is what was written"
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert (
        "`aws-three-tier-composed.infragram.json`" in readme
        and "`aws-three-tier-composed.html`" in readme
    )
    assert "--formats template,html" in readme and "--prices" in readme and "--passes 0" in readme


def test_the_rebuild_command_reads_back_with_spaces() -> None:
    from infragram.cli.user.export_set import _quoted

    for path in ("plain/dir", "my set", "C:/a b/c", 'it"s'):
        assert shlex.split(_quoted(path)) == [path]
