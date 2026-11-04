"""The plugin's live parts: the check hook, the MCP server, and the command
that registers the plugin with an agent.

Held here:

- the hook reads the file a tool call wrote as Claude Code names it
  (``tool_input.file_path``) and as Codex's ``apply_patch`` does (the patch),
  checks only diagrams, passes a good one silently, blocks a broken document
  and a diagram file that does not build with what is wrong, keeps what a
  diagram file prints off stdout, and lets any input it cannot read be;
- the MCP server answers the protocol (initialize in the client's version,
  tools/list with a schema a client can call, tools/call, ping, errors for an
  unknown method or tool), runs a command as the user would and reports its
  failure as a tool error, answers with what the command wrote as data and on
  request the PNG, keeps every export option the command line has, answers
  the read-only tools in-process, serves the references, templates, examples
  and schema as resources and a few prompts, and writes nothing but JSON-RPC
  on stdout;
- plugin:install registers the plugin folder this copy carries, with each
  agent's own commands.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from infragram.cli.user import hook_check
from infragram.cli.user.plugin_install import install_commands
from infragram.mcp import TOOLS, handle, serve
from infragram.paths import plugin_root, repo_root, skill_assets

TEMPLATE = (
    plugin_root()
    / "skills"
    / "infragram-architect"
    / "assets"
    / "templates"
    / "cloud"
    / "gcp-three-tier-web.infragram.json"
)
EXAMPLE = plugin_root() / "examples" / "aws_three_tier.py"


def _hook(event: dict, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    assert hook_check.main([]) == 0
    return capsys.readouterr().out.strip()


def _broken(folder: Path) -> Path:
    document = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    document["slug"] = "Not A Slug!"
    path = folder / "broken.infragram.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


# ------------------------------------------------------------------ hook
def test_the_hook_reads_the_file_each_agent_names(tmp_path: Path) -> None:
    claude = {"cwd": str(tmp_path), "tool_input": {"file_path": "a/diagram.py"}}
    assert hook_check.written_paths(claude) == [(tmp_path / "a" / "diagram.py").resolve()]
    patch = (
        "*** Begin Patch\n*** Add File: new.infragram.json\n+{}\n*** Update File: old.py\n"
        "@@\n-x\n+y\n*** Move to: moved.py\n*** Delete File: gone.py\n*** End Patch"
    )
    codex = {"cwd": str(tmp_path), "tool_input": {"command": patch}}
    assert hook_check.written_paths(codex) == [
        (tmp_path / name).resolve() for name in ("new.infragram.json", "old.py", "moved.py")
    ]
    assert hook_check.written_paths({"tool_input": {"command": "ls -la"}}) == []
    assert hook_check.written_paths({"tool_input": "not an object"}) == []


def test_the_hook_passes_a_good_diagram_and_anything_else_silently(
    tmp_path, capsys, monkeypatch
) -> None:
    (tmp_path / "good.infragram.json").write_bytes(TEMPLATE.read_bytes())
    (tmp_path / "notes.py").write_text("print('not a diagram')\n", encoding="utf-8")
    (tmp_path / "readme.md").write_text("# hi\n", encoding="utf-8")
    for name in ("good.infragram.json", "notes.py", "readme.md", "missing.infragram.json"):
        assert (
            _hook({"cwd": str(tmp_path), "tool_input": {"file_path": name}}, capsys, monkeypatch)
            == ""
        ), name


def test_the_hook_blocks_a_broken_document_with_what_is_wrong(
    tmp_path, capsys, monkeypatch
) -> None:
    _broken(tmp_path)
    said = json.loads(
        _hook(
            {"cwd": str(tmp_path), "tool_input": {"file_path": "broken.infragram.json"}},
            capsys,
            monkeypatch,
        )
    )
    assert said["decision"] == "block" and "slug must be a slug" in said["reason"]


def test_the_hook_reads_a_diagram_file_and_never_runs_it(tmp_path, capsys, monkeypatch) -> None:
    """Permission to write a file is not permission to run it: the hook reads
    a diagram file and finds what reading can."""
    example = EXAMPLE.read_text(encoding="utf-8")
    ran = tmp_path / "ran.txt"
    good = tmp_path / "diagram.py"
    good.write_text(f"{example}\nopen({str(ran)!r}, 'w').write('ran')\n", encoding="utf-8")
    assert (
        _hook(
            {"cwd": str(tmp_path), "tool_input": {"file_path": "diagram.py"}}, capsys, monkeypatch
        )
        == ""
    )
    assert not ran.exists(), "the hook ran the diagram file"

    def block(text: str) -> str:
        (tmp_path / "edited.py").write_text(text, encoding="utf-8")
        said = json.loads(
            _hook(
                {"cwd": str(tmp_path), "tool_input": {"file_path": "edited.py"}},
                capsys,
                monkeypatch,
            )
        )
        assert said["decision"] == "block"
        return said["reason"]

    assert "Edgee is used and never defined; did you mean Edge" in block(
        example.replace("Edge(", "Edgee(", 1)
    )
    assert "compute has no RDS; it is infragram.nodes.aws.databases.RDS" in block(
        example.replace("compute.EC2(", "compute.RDS(", 1)
    )
    assert "invalid syntax" in block(example.replace("with aws.Cloud", "with aws.Cloud((", 1))


def test_the_hook_leaves_python_that_is_no_diagram_file(tmp_path, capsys, monkeypatch) -> None:
    """A module that mentions Diagram( in a function, a docstring or a test is
    no diagram file, and passes."""
    for name, text in (
        (
            "tests_like.py",
            "from infragram.author import Diagram\n\ndef build():\n"
            "    with Diagram('x'):\n        pass\n",
        ),
        ("docs.py", '"""Call Diagram(...) to start."""\nimport os\n'),
    ):
        (tmp_path / name).write_text(text, encoding="utf-8")
        assert (
            _hook({"cwd": str(tmp_path), "tool_input": {"file_path": name}}, capsys, monkeypatch)
            == ""
        ), name


def test_the_hook_lets_input_it_cannot_read_be(capsys, monkeypatch) -> None:
    for raw in ("", "not json", "[1, 2]", '{"tool_input": 3}'):
        monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
        assert hook_check.main([]) == 0
        assert capsys.readouterr().out == ""


# ------------------------------------------------------------------ MCP server
def _call(name: str, arguments: dict) -> dict:
    answer = handle(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert answer is not None and answer["id"] == 7
    return answer["result"]


def test_the_server_speaks_the_protocol() -> None:
    init = handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t"},
            },
        }
    )
    assert init["result"]["protocolVersion"] == "2025-06-18"
    assert init["result"]["capabilities"] == {
        "tools": {"listChanged": False},
        "resources": {"listChanged": False, "subscribe": False},
        "prompts": {"listChanged": False},
    }
    assert init["result"]["serverInfo"]["name"] == "infragram" and init["result"]["instructions"]
    unknown_version = handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "1999-01-01"},
        }
    )
    assert unknown_version["result"]["protocolVersion"] == "2025-11-25"
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert handle({"jsonrpc": "2.0", "id": 3, "method": "ping"})["result"] == {}
    assert (
        handle({"jsonrpc": "2.0", "id": 4, "method": "sampling/createMessage"})["error"]["code"]
        == -32601
    )
    assert (
        handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "nope"}})[
            "error"
        ]["code"]
        == -32602
    )
    assert handle({"id": 6, "method": "ping"})["error"]["code"] == -32600


def test_every_tool_has_a_schema_a_client_can_call() -> None:
    listing = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    assert [tool["name"] for tool in listing] == [tool.name for tool in TOOLS]
    for tool in listing:
        schema = tool["inputSchema"]
        assert schema["type"] == "object" and set(schema["required"]) <= set(schema["properties"])
        assert tool["description"] and tool["annotations"]["destructiveHint"] is False
    read_only = {tool["name"] for tool in listing if tool["annotations"]["readOnlyHint"]}
    assert read_only == {
        "check",
        "check_policy",
        "verify_render",
        "list_templates",
        "list_examples",
        "find_components",
        "views",
        "recipes",
        "docs",
    }
    for tool in listing:
        output = tool["outputSchema"]
        assert output["type"] == "object" and set(output["required"]) <= set(output["properties"])


def test_a_tool_runs_the_command_and_reports_its_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "good.infragram.json").write_bytes(TEMPLATE.read_bytes())
    _broken(tmp_path)
    good = _call("check", {"paths": ["good.infragram.json"]})
    assert good["isError"] is False and "OK good.infragram.json" in good["content"][0]["text"]
    assert good["structuredContent"]["ok"] is True
    assert [check["ok"] for check in good["structuredContent"]["checks"]] == [True]
    bad = _call("check", {"paths": ["broken.infragram.json"]})
    assert bad["isError"] is True and "slug must be a slug" in bad["content"][0]["text"]
    assert bad["structuredContent"]["exit_code"] != 0
    assert bad["structuredContent"]["checks"][0]["ok"] is False
    missing = _call("compose", {})
    assert missing["isError"] is True and "missing argument: spec" in missing["content"][0]["text"]
    assert missing["structuredContent"]["errors"] == ["missing argument: spec"]


def test_the_read_only_tools_answer_in_process() -> None:
    templates = _call("list_templates", {})["content"][0]["text"]
    assert "34 templates" in templates and "gcp-three-tier-web.infragram.json" in templates
    found = _call("find_components", {"query": "load balancer", "library": "gcp"})["content"][0][
        "text"
    ]
    assert "from infragram.nodes.gcp.legacy import CloudLoadBalancing" in found
    frames = _call("find_components", {"query": "private subnet", "library": "aws"})["content"][0][
        "text"
    ]
    assert "from infragram.nodes.frames.aws import PrivateSubnet" in frames
    # a word matches the start of a word, never the middle of one
    assert (
        "IsoWaterLeakSensor"
        not in _call("find_components", {"query": "aks", "limit": 50})["content"][0]["text"]
    )


def test_a_malformed_request_is_answered_never_fatal(monkeypatch) -> None:
    import infragram.mcp.protocol as server

    assert (
        handle({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": [1, 2]})["error"]["code"]
        == -32602
    )
    assert (
        handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": "x"})["error"]["code"]
        == -32602
    )
    monkeypatch.setattr(server, "handle", lambda message: 1 / 0)
    out = io.BytesIO()
    lines = [json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"}), "[]"]
    serve(io.BytesIO(("\n".join(lines) + "\n").encode("utf-8")), out)
    first, second = (json.loads(line) for line in out.getvalue().decode("utf-8").splitlines())
    assert first["id"] == 3 and first["error"]["code"] == -32603, "the server lives on"
    assert second["error"]["code"] == -32600, "an empty batch is an invalid request"


def test_tool_arguments_are_held_to_their_schema(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "good.infragram.json").write_bytes(TEMPLATE.read_bytes())
    one = _call("check", {"paths": "good.infragram.json"})
    assert one["isError"] is False and "OK good.infragram.json" in one["content"][0]["text"], (
        "a single path where a list is asked is a list of one"
    )
    for name, arguments, says in (
        ("check", {"paths": 7}, "a list of paths"),
        ("check", {"paths": ["a"], "force": True}, "takes no force"),
        ("compose", {"spec": "a.py", "display": "sideways"}, "display is one of"),
        ("compose", {"spec": "a.py", "verify": "yes"}, "true or false"),
        ("find_components", {"query": "vpc", "limit": 0}, "1 or more"),
        ("find_components", {"query": "   "}, "name a query, a library, or ask for the libraries"),
    ):
        answer = _call(name, arguments)
        assert answer["isError"] is True and says in answer["content"][0]["text"], (name, arguments)


def test_the_server_writes_only_json_rpc_on_stdout() -> None:
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        "not json",
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps(
            [
                {"jsonrpc": "2.0", "id": 2, "method": "ping"},
                {"jsonrpc": "2.0", "id": 3, "method": "ping"},
            ]
        ),
    ]
    out = io.BytesIO()
    serve(io.BytesIO(("\n".join(lines) + "\n").encode("utf-8")), out)
    answers = [json.loads(line) for line in out.getvalue().decode("utf-8").splitlines()]
    assert answers[0] == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert answers[1]["error"]["code"] == -32700
    assert [answer["id"] for answer in answers[2]] == [2, 3] and len(answers) == 3


def test_the_command_serves_over_stdio(tmp_path: Path) -> None:
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
    done = subprocess.run(
        [sys.executable, "-m", "infragram", "mcp"],
        input=request,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=tmp_path,
        timeout=120,
        env={**__import__("os").environ, "PYTHONPATH": str(repo_root() / "plugin" / "src")},
    )
    assert done.returncode == 0, done.stderr
    assert len(json.loads(done.stdout)["result"]["tools"]) == len(TOOLS)


def test_the_png_hint_names_the_python_that_is_running(monkeypatch, tmp_path) -> None:
    """``python -m pip`` may be another Python; a Python uv made has no pip."""
    from infragram.exports.browser import install_hint

    monkeypatch.setattr(sys, "executable", "/opt/py/bin/python3.12")
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "no-venv"))
    assert install_hint() == (
        '"/opt/py/bin/python3.12" -m pip install playwright pillow, '
        'then "/opt/py/bin/python3.12" -m playwright install chromium'
    )
    # an installed tool or uvx: uv made it, so its pyvenv.cfg says so
    tool = tmp_path / "uv" / "tools" / "infragram"
    tool.mkdir(parents=True)
    (tool / "pyvenv.cfg").write_text("home = /opt/py/bin\nuv = 0.12.6\n", encoding="utf-8")
    monkeypatch.setattr(sys, "prefix", str(tool))
    hint = install_hint()
    assert "uv pip install --python" in hint and "uv tool install --reinstall" in hint
    assert "-m pip install" not in hint
    assert (
        install_hint(chromium_only=True)
        == '"/opt/py/bin/python3.12" -m playwright install chromium'
    )


def test_a_project_venv_uv_made_gets_the_uv_hint(monkeypatch, tmp_path) -> None:
    """``uv venv`` makes a project's ``.venv`` in no folder called uv, and with
    no pip in it; deciding by the path gave it a pip command that cannot run.
    The reverse holds too: a pip-made venv under a folder named uv has pip."""
    from infragram.exports.browser import install_hint

    monkeypatch.setattr(sys, "executable", "/work/app/.venv/bin/python")
    project = tmp_path / "app" / ".venv"
    project.mkdir(parents=True)
    (project / "pyvenv.cfg").write_text(
        "home = /usr/bin\nimplementation = CPython\nuv = 0.12.6\nversion_info = 3.12\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "prefix", str(project))
    assert install_hint().startswith(
        'this Python is one uv made, without pip: uv pip install --python "/work/app/.venv/bin/python"'
    )

    pip_made = tmp_path / "uv" / ".venv"
    pip_made.mkdir(parents=True)
    (pip_made / "pyvenv.cfg").write_text(
        "home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.12.6\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "prefix", str(pip_made))
    assert install_hint().startswith('"/work/app/.venv/bin/python" -m pip install playwright')


def test_the_mcp_server_starts_with_what_a_png_needs() -> None:
    for name, root in ((".mcp.json", "${CLAUDE_PLUGIN_ROOT}"), ("mcp.json", "${PLUGIN_ROOT}")):
        config = json.loads((plugin_root() / name).read_text(encoding="utf-8"))["mcpServers"][
            "infragram"
        ]
        assert config["command"] == "uvx" and config["args"] == [
            "--from",
            f"{root}[png]",
            "infragram",
            "mcp",
        ]


# ------------------------------------------------------------------ plugin:install
def test_plugin_install_uses_each_agents_own_commands(tmp_path: Path) -> None:
    assert install_commands("claude", tmp_path) == [
        ["claude", "plugin", "marketplace", "add", str(tmp_path)],
        ["claude", "plugin", "install", "infragram-architect@infragram-architect"],
    ]
    assert install_commands("claude", tmp_path, "project")[1][-2:] == ["--scope", "project"]
    assert install_commands("codex", tmp_path) == [
        ["codex", "plugin", "marketplace", "add", str(tmp_path)],
        ["codex", "plugin", "add", "infragram-architect@infragram-architect"],
    ]
    assert install_commands("pi", tmp_path) == [["pi", "install", str(tmp_path)]]
    with pytest.raises(ValueError):
        install_commands("vim", tmp_path)


def test_plugin_path_and_a_dry_run_name_this_copys_plugin(capsys) -> None:
    from infragram.cli.user.plugin_install import install_main, path_main

    assert path_main([]) == 0 and capsys.readouterr().out.strip() == str(plugin_root())
    assert install_main(["codex", "--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert "codex plugin marketplace add" in printed and str(plugin_root()) in printed


# ------------------------------------------------------------------ the command line
def test_an_installed_copy_lists_the_commands_it_can_run(monkeypatch) -> None:
    from infragram.cli import cli

    checkout = cli.build_parser().format_help()
    assert "maintainer commands (need a checkout):" in checkout and "verify:quick" in checkout
    monkeypatch.setattr(cli, "SCRIPTS", None)
    installed = cli.build_parser().format_help()
    assert "compose" in installed and "plugin:install" in installed
    assert "verify:quick" not in installed and "gen:nodes" not in installed
    assert "maintainer commands run from a checkout of the repository" in installed
    assert "The maintainer commands run scripts" not in installed


def test_a_misspelt_command_names_the_nearest(capsys) -> None:
    from infragram.cli import cli

    assert cli.main(["compse"]) == 2
    assert "did you mean compose? Run infragram --help" in capsys.readouterr().err
    assert cli.main(["zzz"]) == 2
    assert capsys.readouterr().err.strip() == "ERROR: unknown command 'zzz'; run infragram --help"


def test_the_export_options_read_plainly(tmp_path: Path, capsys) -> None:
    from infragram.cli.user import export_project

    usage = export_project.build_parser().format_usage()
    for shown in ("--formats LIST", "--output-dir DIR", "--scale N", "--background COLOUR"):
        assert shown in usage, usage
    assert export_project.main([str(tmp_path / "missing.infragram.json")]) == 2
    assert f"no such document: {tmp_path / 'missing.infragram.json'}" in capsys.readouterr().err


# ------------------------------------------------------------------ MCP: data, parity, resources
def test_a_command_answers_with_the_files_it_wrote(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "good.infragram.json").write_bytes(TEMPLATE.read_bytes())
    answer = _call(
        "export_project",
        {"document": "good.infragram.json", "formats": "svg,template", "output_dir": "out"},
    )
    assert answer["isError"] is False, answer["content"][0]["text"]
    data = answer["structuredContent"]
    kinds = {entry["kind"]: entry for entry in data["files"]}
    assert set(kinds) >= {"SVG", "TEMPLATE"}, data
    svg = Path(kinds["SVG"]["path"])
    assert (svg if svg.is_absolute() else tmp_path / svg).stat().st_size == kinds["SVG"]["bytes"]
    assert any(check["ok"] and check["path"].endswith(".svg") for check in data["checks"])
    shown = _call(
        "export_project",
        {
            "document": "good.infragram.json",
            "formats": "svg",
            "output_dir": "out",
            "preview": True,
            "force": True,
        },
    )
    assert len(shown["content"]) == 1
    assert "no PNG was written to preview" in shown["structuredContent"]["notes"][-1]


def test_the_output_is_read_as_data(tmp_path) -> None:
    from infragram.mcp.run import _read_output

    (tmp_path / "a.svg").write_text("<svg/>", encoding="utf-8")
    read = _read_output(
        "PROJECT  a | single-cloud | aws | 3 elements\n"
        "SVG      a.svg (6 bytes)\n"
        "PNG      gone.png (9 bytes)\n"
        "NOTE     the names begin with 'x-'\n"
        "OK a.svg: picture - 1 components\n"
        "FAIL b.html: slug must be a slug\n"
        "ERROR: no such document: c.json",
        tmp_path,
    )
    assert read["files"] == [{"kind": "SVG", "path": "a.svg", "bytes": 6}], "only files on disk"
    assert [check["ok"] for check in read["checks"]] == [True, False]
    assert read["errors"] == ["no such document: c.json"]
    assert "the names begin with 'x-'" in read["notes"]


def test_a_preview_is_the_png_scaled_down(tmp_path) -> None:
    image = pytest.importorskip("PIL.Image")
    import base64

    from infragram.mcp.run import PREVIEW_WIDTH, _preview

    image.new("RGB", (PREVIEW_WIDTH * 2, 100), "white").save(tmp_path / "wide.png")
    block, why = _preview([{"kind": "PNG", "path": "wide.png", "bytes": 1}], tmp_path)
    assert block is not None and not why and block["mimeType"] == "image/png"
    with image.open(io.BytesIO(base64.b64decode(block["data"]))) as shown:
        assert shown.width == PREVIEW_WIDTH


def test_every_export_option_of_the_command_line_is_a_tool_argument() -> None:
    import argparse

    from infragram.cli.user.options import add_export_options

    parser = argparse.ArgumentParser()
    add_export_options(parser, libraries="drawn")
    # write_looks only matters on disk with display both; embed is no_embed here
    wanted = {action.dest for action in parser._actions if action.dest != "help"}
    wanted = (wanted - {"write_looks", "embed"}) | {"no_embed"}
    for name in ("compose", "compose_source", "export_project", "diff", "import_terraform"):
        tool = next(tool for tool in TOOLS if tool.name == name)
        assert wanted <= set(tool.properties), (name, wanted - set(tool.properties))
    compose = next(tool for tool in TOOLS if tool.name == "compose")
    assert compose.argv is not None
    assert compose.argv(
        {
            "spec": "a.py",
            "theme": "dark",
            "scale": 2,
            "libraries": "all",
            "drawio_icons": "embedded",
            "no_embed": True,
            "verify": False,
        }
    ) == [
        "compose",
        "a.py",
        "--theme",
        "dark",
        "--scale",
        "2",
        "--libraries",
        "all",
        "--drawio-icons",
        "embedded",
        "--no-embed",
    ]
    refused = _call("compose", {"spec": "a.py", "scale": 9})["content"][0]["text"]
    assert refused == "scale is a number from 1 through 4"


def test_compose_source_writes_the_file_it_composes_and_nothing_else(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    escape = _call("compose_source", {"source": "x = 1\n", "spec": "../out.py"})
    assert escape["isError"] and "inside the folder" in escape["content"][0]["text"]
    assert not (tmp_path.parent / "out.py").exists()
    (tmp_path / "mine.py").write_text("keep = 1\n", encoding="utf-8")
    kept = _call("compose_source", {"source": "x = 1\n", "spec": "mine.py"})
    assert kept["isError"] and "exists" in kept["content"][0]["text"]
    assert (tmp_path / "mine.py").read_text(encoding="utf-8") == "keep = 1\n"
    drawn = _call(
        "compose_source",
        {
            "source": (repo_root() / "plugin/examples/aws_three_tier.py").read_text("utf-8"),
            "spec": "three.py",
            "formats": "template",
            "output_dir": "out",
            "verify": False,
        },
    )
    assert drawn["isError"] is False, drawn["content"][0]["text"]
    assert drawn["structuredContent"]["notes"][0].startswith("wrote three.py")
    assert [entry["kind"] for entry in drawn["structuredContent"]["files"]] == ["TEMPLATE"]


def test_the_examples_and_references_are_served(tmp_path, monkeypatch) -> None:
    examples = _call("list_examples", {})["structuredContent"]["examples"]
    assert "aws_three_tier" in {example["name"] for example in examples}
    listed = handle({"jsonrpc": "2.0", "id": 1, "method": "resources/list"})["result"]
    uris = {resource["uri"] for resource in listed["resources"]}
    assert {
        "infragram://references/compose.md",
        "infragram://examples/aws_three_tier.py",
        "infragram://schema/project",
    } <= uris
    assert any(uri.startswith("infragram://templates/") for uri in uris)
    read = handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/read",
            "params": {"uri": "infragram://schema/project"},
        }
    )["result"]["contents"][0]
    assert json.loads(read["text"])["title"] == "Infragram Architect project"
    missing = handle(
        {"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "file:///etc"}}
    )
    assert missing["error"]["code"] == -32002, "only what is listed is read"
    templates = handle({"jsonrpc": "2.0", "id": 4, "method": "resources/templates/list"})
    assert templates["result"]["resourceTemplates"][0]["uriTemplate"] == (
        "infragram://catalog/{library}"
    )
    catalog = handle(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "infragram://catalog/kubernetes"},
        }
    )["result"]["contents"][0]["text"]
    assert catalog.startswith("# kubernetes: ") and "## infragram.nodes.kubernetes" in catalog
    monkeypatch.chdir(tmp_path)
    started = _call("new_diagram", {"example": "aws_three_tier", "path": "mine.py"})
    assert started["isError"] is False and (tmp_path / "mine.py").is_file()


def test_the_prompts_start_the_usual_jobs() -> None:
    listed = handle({"jsonrpc": "2.0", "id": 1, "method": "prompts/list"})["result"]["prompts"]
    assert {prompt["name"] for prompt in listed} == {
        "draw_architecture",
        "diagram_from_terraform",
        "review_diagram",
    }
    got = handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "prompts/get",
            "params": {"name": "draw_architecture", "arguments": {"description": "a web app"}},
        }
    )["result"]
    assert "a web app" in got["messages"][0]["content"]["text"]
    unnamed = {"jsonrpc": "2.0", "id": 3, "method": "prompts/get"}
    assert handle({**unnamed, "params": {"name": "review_diagram"}})["error"]["code"] == -32602


HUB_SPOKE = skill_assets() / "templates" / "cloud" / "azure-hub-spoke-landing-zone.infragram.json"


def test_the_mcp_timeout_is_taken(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "t.infragram.json").write_bytes(HUB_SPOKE.read_bytes())
    answer = _call(
        "export_project",
        {"document": "t.infragram.json", "formats": "template", "timeout": 30, "verify": False},
    )
    assert answer["isError"] is False, answer["content"][0]["text"]
    refused = _call("export_project", {"document": "t.infragram.json", "timeout": 0})
    assert refused["content"][0]["text"] == "timeout is a number greater than 0"


def test_an_unknown_library_is_named_as_one() -> None:
    answer = _call("find_components", {"library": "nosuch"})
    assert answer["isError"] is True
    assert "no library 'nosuch'" in answer["content"][0]["text"]
