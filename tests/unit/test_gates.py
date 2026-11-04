"""A gate that cannot fail is worse than no gate: it reports a pass nobody earned.

Each test here closes one way a gate could pass without checking anything:

- a ``test:*`` command runs its module under pytest, because a module that
  only defines test functions exits 0 as a plain script having run none;
- every ``test:*`` module collects at least one test, or pytest exits 5 and
  the command can never pass;
- ``verify:all`` runs the whole suite, and CI's ``gates`` job step for step,
  rather than naming test modules one at a time;
- a ``verify:*`` command passes ``--check`` exactly once, so it verifies what
  it was asked to verify instead of regenerating it;
- ``verify:render`` checks the page it was given, saved layout and all;
- the inventory holds every component the product ships, because the shipped
  checker reads it;
- the catalog, the sidebar and compose agree on what a library offers, and
  compose accepts every shipped template;
- every script a CI step names exists, and every browser suite is one the
  browser gate runs.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from infragram import cli
from infragram.catalog import load_provider_component_catalog
from infragram.catalog.specs import CUSTOM_COMPONENT_SPECS
from infragram.editor.sidebar import load_sidebar_catalog
from infragram.paths import repo_root
from infragram.projects import CloudProject

ROOT = repo_root()
INVENTORY = (
    ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "catalog" / "inventory.json"
)
TEMPLATES = ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "templates" / "cloud"
FORGEJO_CI = ROOT / ".forgejo" / "workflows" / "ci.yml"

#: A script path as a `run:` line names it.
_SCRIPT_PATH = re.compile(r"(?<![\w/.-])((?:scripts|tests|skills)/[A-Za-z0-9_./-]+\.py)")
#: A command line in a `run:` step, inline or in a block, that runs python.
_RUN_LINE = re.compile(r"^\s*(?:-\s*)?(?:run:\s*)?(python .+?)\s*$", re.MULTILINE)


def _job_text(workflow: Path, job: str) -> str:
    """The text of one job in a workflow file, from its key to the next
    job's; a two-space key under `jobs:` is how the workflow lays them out."""
    text = workflow.read_text(encoding="utf-8")
    match = re.search(rf"(?ms)^  {re.escape(job)}:\n(.*?)(?=^  \w[\w-]*:\n|\Z)", text)
    assert match is not None, f"{workflow.name} has no job {job!r}"
    return match.group(1)


def _ci_plan(job_text: str) -> list[str]:
    """CI's steps as `cli.verify_all_plan()` writes them, in order:
    ``scripts/verify/naming.py``, ``pytest:<targets>``,
    ``scripts/tools/generate-nodes.py --check``,
    ``step:export-templates`` for the shell loop over the templates and the
    checker run over what it wrote."""
    plan: list[str] = []
    for line in _RUN_LINE.findall(job_text):
        if " -m pip " in line or " -m playwright " in line or line == "python --version":
            continue  # installing, not a gate
        if line.startswith("python -m pytest "):
            targets = line[len("python -m pytest ") :].split(" -q")[0]
            plan.append(f"pytest:{targets}")
        elif "export:project" in line:
            plan.append("step:export-templates")
        elif "project_check.py" in line and plan and plan[-1] == "step:export-templates":
            continue  # the checker run that closes the export loop
        else:
            match = _SCRIPT_PATH.search(line)
            assert match is not None, f"unrecognised CI run line: {line!r}"
            flags = line.split(match.group(1), 1)[1].strip()
            plan.append(f"{match.group(1)} {flags}".strip())
    return plan


def _workflow_scripts(workflow: Path) -> set[str]:
    """Every script a workflow's steps name; comment lines are prose."""
    lines = [
        line
        for line in workflow.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    return set(_SCRIPT_PATH.findall("\n".join(lines)))


# ------------------------------------------------------- the CLI's own gates
def test_every_test_command_runs_its_module_under_pytest(monkeypatch) -> None:
    """Run as a plain script, a pytest-only module exits 0 having run nothing."""
    captured: list[list[str]] = []

    class Completed:
        returncode = 0

    monkeypatch.setattr(
        cli.runner.subprocess,
        "run",
        lambda argv, **kwargs: (captured.append(list(argv)), Completed())[1],
    )
    commands = {name: entry for name, entry in cli.COMMANDS.items() if name.startswith("test:")}
    assert commands, "no test:* commands found; the table moved"
    for name, (script, _help) in commands.items():
        captured.clear()
        assert cli.run_script(script, ()) == 0
        argv = captured[0]
        assert "pytest" in argv, f"{name} runs {script} as a plain script: {argv}"


def test_verify_all_runs_the_suite_rather_than_naming_modules() -> None:
    suite = [script for script, _ in cli.VERIFY_ALL if script.startswith(cli.PYTEST_PREFIX)]
    assert len(suite) == 1, f"expected one suite entry, got {suite}"
    targets = suite[0][len(cli.PYTEST_PREFIX) :].split()
    assert (
        "tests/unit" in targets and "tests/skill" in targets and "tests/integration" in targets
    ), targets

    named = [
        script
        for script, _ in cli.VERIFY_ALL
        if "tests/" in script and not script.startswith(cli.PYTEST_PREFIX)
    ]
    assert named == [], f"verify:all names test modules one by one: {named}"


def test_verify_quick_is_the_fast_part_of_verify_all() -> None:
    """The per-change check runs only gates the release check runs, and the
    unit and skill suites less the tests marked slow."""
    suite = [
        (script, args) for script, args in cli.VERIFY_QUICK if script.startswith(cli.PYTEST_PREFIX)
    ]
    assert len(suite) == 1 and suite[0][1] == ("-m", "not slow"), suite
    assert set(suite[0][0][len(cli.PYTEST_PREFIX) :].split()) == {"tests/unit", "tests/skill"}
    gates = {script for script, _ in cli.VERIFY_QUICK if not script.startswith(cli.PYTEST_PREFIX)}
    assert gates <= {script for script, _ in cli.VERIFY_ALL}, gates
    assert "verify/lint.py" in gates


def test_verify_all_is_ci_no_browser_job_in_ci_order() -> None:
    """The local gate and the `gates` job are the same list, step for step."""
    assert cli.verify_all_plan() == _ci_plan(_job_text(FORGEJO_CI, "gates"))


def test_every_test_command_module_collects_at_least_one_test() -> None:
    """A module that keeps its checks in main() only collects nothing under
    pytest, which exits 5, so its test:* command could never pass."""
    modules = sorted(
        {script for name, (script, _) in cli.COMMANDS.items() if name.startswith("test:")}
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            *modules,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    collected = [
        line.split("::", 1)[0].replace("\\", "/")
        for line in result.stdout.splitlines()
        if "::" in line
    ]
    empty = [module for module in modules if module not in collected]
    assert empty == [], (
        f"no test collected from {empty}\n{result.stdout[-1500:]}{result.stderr[-1500:]}"
    )


def test_verify_commands_pass_their_check_flag_exactly_once(monkeypatch) -> None:
    """Without --check a verify command regenerates what it was asked to
    verify, and exits 0."""
    captured: list[list[str]] = []

    class Completed:
        returncode = 0

    monkeypatch.setattr(
        cli.runner.subprocess,
        "run",
        lambda argv, **kwargs: (captured.append(list(argv)), Completed())[1],
    )
    assert "verify:inventory" in cli.FIXED_ARGS and "verify:ink" in cli.FIXED_ARGS
    for command, fixed in cli.FIXED_ARGS.items():
        assert "--check" in fixed, f"{command} is a verify command that does not check"
        captured.clear()
        assert cli.main([command]) == 0
        argv = captured[0]
        assert argv.count("--check") == 1 and argv[1].endswith(
            cli.COMMANDS[command][0].rsplit("/", 1)[1]
        ), argv
        captured.clear()
        assert cli.main([command, "--check"]) == 2, f"{command} accepted a second --check"
        assert captured == [], f"{command} ran with a doubled flag: {captured}"


# ---------------------------------------------------------- the workflow file
def test_every_ci_run_step_names_a_script_that_exists() -> None:
    scripts = _workflow_scripts(FORGEJO_CI)
    assert scripts, f"{FORGEJO_CI} runs no scripts"
    missing = sorted(script for script in scripts if not (ROOT / script).is_file())
    assert missing == [], (
        f"{FORGEJO_CI.relative_to(ROOT)} runs scripts that do not exist: {missing}"
    )


# --------------------------------------------------- what verify:render checks
def test_verify_render_checks_the_page_it_was_given_for_the_documents_own_look(tmp_path) -> None:
    """A re-export drops the saved editor geometry, so the placed layout would
    never be the one rendered."""
    from infragram.cli.user import render_gate as module

    project = CloudProject.load(sorted(TEMPLATES.glob("*.infragram.json"))[0])
    page = tmp_path / "page.html"
    page.write_text("<html></html>", encoding="utf-8")

    for look in (None, "project", project.presentation.display):
        assert module.page_for_look(project, page, look, tmp_path) is page, look


# ------------------------------------- the inventory the shipped checker reads
def _inventory_component_ids() -> set[str]:
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    known = {f"infragram:{item['id']}" for item in data["shared_primitives"]}
    known |= {f"infragram:{item['id']}" for item in data["core_frames"]}
    for library in data["libraries"]:
        known |= {f"{library['id']}:{item['id']}" for item in library["components"]}
        known |= {f"infragram:{item['id']}" for item in library["frames"]}
    return known


@pytest.mark.parametrize("spec", CUSTOM_COMPONENT_SPECS, ids=lambda spec: spec[0])
def test_every_shipped_custom_component_reaches_the_inventory(spec) -> None:
    """A boundary belonging to no library is still a component the product
    ships; dropping it makes `infragram check` reject honest documents."""
    assert f"infragram:{spec[0]}" in _inventory_component_ids()


def test_the_catalog_offers_the_platform_card_the_sidebar_offers() -> None:
    """The sidebar shows the Kubernetes platform card and a shipped template
    places it, so compose must qualify it too."""
    catalog = {
        component.service_id
        for component in load_provider_component_catalog("kubernetes").components
    }
    # The sidebar also lists the shared primitives and the generic frames,
    # which belong to no library; only its own cards are the catalog's to hold.
    sidebar = {
        component.id
        for category in load_sidebar_catalog("kubernetes").categories
        for component in category.components
        if component.provider_id == "kubernetes"
    }
    assert "kubernetes" in catalog, "the platform card is missing from the catalog"
    assert sidebar - catalog == set(), (
        f"the sidebar offers what compose refuses: {sidebar - catalog}"
    )


def test_every_shipped_template_qualifies() -> None:
    """`infragram compose` must accept every document the product ships."""
    from infragram import compose

    failures = []
    for path in sorted(TEMPLATES.glob("*.infragram.json")):
        try:
            compose.qualify(CloudProject.load(path).topology)
        except Exception as error:  # noqa: BLE001 - the message is the report
            failures.append(f"{path.name}: {error}")
    assert failures == [], failures


def test_every_browser_suite_is_one_the_browser_gate_runs() -> None:
    """A browser test nobody runs is a feature nobody checks.

    `scripts/verify/browser.py` names its suites one by one rather than
    globbing, so a new file guarded by INFRAGRAM_RUN_BROWSER_TESTS is skipped
    everywhere at once: the ordinary suite skips it for want of the flag, and
    the gate skips it for want of a line. Both look green.
    """
    gate = (ROOT / "scripts" / "verify" / "browser.py").read_text(encoding="utf-8")
    listed = set(re.findall(r'"(test_[a-z0-9_]+\.py)"', gate))
    guarded = {
        path.name
        for path in sorted((ROOT / "tests" / "integration").glob("test_*.py"))
        if "INFRAGRAM_RUN_BROWSER_TESTS" in path.read_text(encoding="utf-8")
    }
    assert guarded - listed == set(), (
        f"browser suites the gate never runs: {sorted(guarded - listed)}"
    )
    missing = {name for name in listed if not (ROOT / "tests" / "integration" / name).is_file()}
    assert missing == set(), f"the gate names suites that do not exist: {sorted(missing)}"
