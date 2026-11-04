"""The plugin folder, ``plugin/``: what installs, and nothing else.

Every route installs that folder whole -- a marketplace names ``./plugin``,
the npm package is its ``files``, the wheel carries it as
``infragram/_plugin`` -- so everything the skills, the hook, the agent and the
MCP server need must be inside it, and nothing from the development tree may
be. The launcher inside it runs from any folder, and in a copy of it (an
agent's install) a maintainer command says it needs a checkout.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
PLUGIN = ROOT / "plugin"
LAUNCHER = "skills/infragram-architect/scripts/infragram.py"
COMMANDS = ("compose", "export-project", "import", "discover", "check", "check-terraform")
#: Every name at the top of the plugin folder, and nothing else.
TOP_LEVEL = {
    ".claude-plugin",
    ".codex-plugin",
    ".agents",
    "plugin.json",
    "package.json",
    ".mcp.json",
    "mcp.json",
    "skills",
    "agents",
    "hooks",
    "examples",
    "src",
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "THIRD_PARTY_LICENSES.md",
    # the licence texts and notices of what the plugin bundles
    "licenses",
}


@pytest.fixture(scope="module")
def shipped() -> set[str]:
    """The plugin's files, plugin-relative: every file git tracks, or would track, under plugin/."""
    listed = (
        subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "plugin"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode("utf-8")
        .split("\0")
    )
    return {path.removeprefix("plugin/") for path in listed if path and (ROOT / path).is_file()}


def run(launcher: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(launcher), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_the_plugin_holds_everything_an_install_needs(shipped: set[str]) -> None:
    needed = {
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        ".codex-plugin/plugin.json",
        ".agents/plugins/marketplace.json",
        "plugin.json",
        "package.json",
        ".mcp.json",
        "mcp.json",
        "hooks/hooks.json",
        "hooks/codex.json",
        "hooks/run",
        "agents/diagram-reviewer.md",
        "skills/infragram-architect/SKILL.md",
        LAUNCHER,
        "skills/infragram-architect/scripts/project_check.py",
        "src/infragram/__init__.py",
        "src/infragram/__main__.py",
        "src/infragram/mcp/protocol.py",
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "THIRD_PARTY_LICENSES.md",
        *(f"skills/{name}/SKILL.md" for name in COMMANDS),
        *(f"skills/{name}/agents/openai.yaml" for name in COMMANDS),
    }
    missing = sorted(needed - shipped)
    assert not missing, f"the plugin folder leaves out: {', '.join(missing)}"


def test_nothing_from_the_development_tree_is_in_the_plugin(shipped: set[str]) -> None:
    tops = {path.split("/")[0] for path in shipped}
    assert tops == TOP_LEVEL, (
        f"unexpected at the top of plugin/: {sorted(tops - TOP_LEVEL)}; missing {sorted(TOP_LEVEL - tops)}"
    )
    leaked = sorted(
        path for path in shipped if "__pycache__" in path or path.endswith((".pyc", ".env", ".tgz"))
    )
    assert not leaked, f"the plugin carries files it should not: {', '.join(leaked[:10])}"
    assert (ROOT / "LICENSE").read_bytes() == (PLUGIN / "LICENSE").read_bytes(), (
        "the repository's LICENSE and the plugin's are the same licence"
    )


def test_every_package_carries_the_whole_plugin(shipped: set[str]) -> None:
    """The npm package's files, the wheel's inclusions and the sdist's are the
    plugin folder, every top-level entry of it, and nothing that is not there."""
    package = json.loads((PLUGIN / "package.json").read_text(encoding="utf-8"))
    npm = {entry.rstrip("/") for entry in package["files"] if not entry.startswith("!")}
    tops = {entry.split("/")[0] for entry in npm}
    assert tops == TOP_LEVEL - {"package.json"}, sorted(
        tops ^ (TOP_LEVEL - {"package.json"})
    )  # npm adds it itself
    assert {"!**/__pycache__/**", "!**/*.pyc"} <= set(package["files"])
    config = tomllib.loads((PLUGIN / "pyproject.toml").read_text(encoding="utf-8"))
    targets = config["tool"]["hatch"]["build"]["targets"]
    wheel = {source.rstrip("/") for source in targets["wheel"]["force-include"]}
    assert {source.split("/")[0] for source in wheel} == TOP_LEVEL, (
        f"the wheel's plugin differs: {sorted(wheel)}"
    )
    assert all(
        target.startswith("infragram/_plugin/")
        for target in targets["wheel"]["force-include"].values()
    )
    sdist = set(targets["sdist"]["include"]) | set(targets["sdist"]["force-include"])
    assert sdist == TOP_LEVEL - {"src"} | {"src/infragram"}, sorted(sdist ^ TOP_LEVEL)
    for source in (*npm, *wheel, *sdist):
        assert source in shipped or any(path.startswith(source + "/") for path in shipped), (
            f"a package names {source}, which the plugin does not hold"
        )


def test_every_path_the_plugin_names_is_in_it(shipped: set[str]) -> None:
    """A path a skill, the agent, a hook or the MCP configuration names under
    the plugin root is a file or folder the plugin ships."""
    named: list[tuple[str, str]] = []
    sources = [
        *PLUGIN.glob("skills/*/SKILL.md"),
        *PLUGIN.glob("agents/*.md"),
        *PLUGIN.glob("hooks/*.json"),
    ]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for relative in re.findall(
            r"(?:\$\{CLAUDE_PLUGIN_ROOT\}|\$\{PLUGIN_ROOT\}|<plugin>)/([^\s\"'`)\\]+)", text
        ):
            named.append((source.relative_to(PLUGIN).as_posix(), relative.rstrip(".,:;")))
    assert len(named) > 12, named
    for where, relative in named:
        assert relative in shipped or any(
            path.startswith(relative.rstrip("/") + "/") for path in shipped
        ), f"{where} names {relative}, which the plugin does not ship"


def test_the_commands_are_skills_the_user_runs() -> None:
    """A command is a skill only the user invokes, in Claude Code and in Codex;
    the main skill is the one the agent picks on its own."""
    for name in COMMANDS:
        text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        front = text.split("---")[1]
        assert re.search(rf"^name: {re.escape(name)}$", front, re.M), name
        assert re.search(r"^disable-model-invocation: true$", front, re.M), name
        assert re.search(r"^argument-hint: ", front, re.M) and re.search(
            r"^description: .{40,}", front, re.M
        ), name
        assert "$ARGUMENTS" in text and "infragram.py" in text, name
        # Codex and Pi expand neither variable: a command reads the same in every agent
        for command in re.findall(r"```bash\n(.*?)```", text, re.S):
            assert "CLAUDE_PLUGIN_ROOT" not in command and "$ARGUMENTS" not in command, (
                name,
                command,
            )
            assert command.startswith(
                'python "<plugin>/skills/infragram-architect/scripts/infragram.py" '
            ), command
        assert "in Codex or Pi the folder two above this skill's own" in " ".join(text.split()), (
            name
        )
        policy = (PLUGIN / "skills" / name / "agents" / "openai.yaml").read_text(encoding="utf-8")
        assert "allow_implicit_invocation: false" in policy, name
    main = (
        (PLUGIN / "skills" / "infragram-architect" / "SKILL.md")
        .read_text(encoding="utf-8")
        .split("---")[1]
    )
    assert "disable-model-invocation" not in main


def test_the_guide_runs_commands_on_the_users_files(shipped: set[str]) -> None:
    """A command reads its paths from the user's folder, so an example that
    names a file inside the plugin would find nothing there."""
    guide = (PLUGIN / "README.md").read_text(encoding="utf-8")
    runs = re.findall(r"^/infragram-architect:\S+ (\S+)", guide, re.M)
    assert len(runs) >= 4, runs
    for path in runs:
        assert not any(
            shipped_path == path or shipped_path.startswith(path.rstrip("/") + "/")
            for shipped_path in shipped
        ), f"the guide runs a command on the plugin's own {path}"
    assert '"$(infragram plugin:path)/examples/' in guide


def test_pi_finds_the_skills_from_the_repository_too() -> None:
    """``pi install git:<repository>`` reads the repository's own package.json,
    which points at the plugin's skills and is never published."""
    root = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    plugin = json.loads((PLUGIN / "package.json").read_text(encoding="utf-8"))
    assert root["private"] is True and "files" not in root and "version" not in root
    assert [(ROOT / path).resolve() for path in root["pi"]["skills"]] == [
        (PLUGIN / path).resolve() for path in plugin["pi"]["skills"]
    ]


def test_every_skill_loads_in_codex() -> None:
    """Codex refuses a skill whose description is past 1024 characters and
    whose name is not the folder's, in lowercase words joined by hyphens."""
    skills = sorted(PLUGIN.glob("skills/*/SKILL.md"))
    assert len(skills) == len(COMMANDS) + 1
    for skill in skills:
        front = skill.read_text(encoding="utf-8").split("---")[1]
        description = re.search(r"^description: (.*)$", front, re.M).group(1)
        assert 0 < len(description) <= 1024, (skill.parent.name, len(description))
        assert re.search(rf"^name: {re.escape(skill.parent.name)}$", front, re.M), skill.parent.name
        assert (
            re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill.parent.name)
            and len(skill.parent.name) <= 64
        )


def test_the_plugins_launcher_runs_from_any_folder(tmp_path: Path) -> None:
    manifest = PLUGIN / ".claude-plugin" / "plugin.json"
    version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    work = tmp_path / "work"
    work.mkdir()
    result = run(PLUGIN / LAUNCHER, "--version", cwd=work)
    assert result.returncode == 0 and result.stdout.strip() == f"infragram {version}", (
        result.stdout + result.stderr
    )

    # an agent's copy of the plugin has no repository around it
    copy = tmp_path / "cache" / "infragram-architect" / version
    shutil.copytree(PLUGIN, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "assets"))
    shutil.copytree(
        PLUGIN / "skills" / "infragram-architect" / "assets" / "catalog",
        copy / "skills" / "infragram-architect" / "assets" / "catalog",
    )
    result = run(copy / LAUNCHER, "--version", cwd=work)
    assert result.returncode == 0 and result.stdout.strip() == f"infragram {version}", (
        result.stdout + result.stderr
    )
    refused = run(copy / LAUNCHER, "verify:naming", cwd=work)
    assert refused.returncode == 2 and "maintainer command" in refused.stderr, (
        f"a maintainer command in an installed copy did not say it needs a checkout:\n"
        f"{refused.stdout}{refused.stderr}"
    )
