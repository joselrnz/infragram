"""Whether a diagram's Terraform works, without deploying it: ``check:terraform``.

Held here:

- a variable nobody gave a value gets one of the shape its name, then its
  type, asks for; a value the configuration's own tfvars files, the user's
  files, ``--var`` or a ``TF_VAR_`` variable gives is never made up;
- every module call is pointed at a folder inside the copy: a registry module
  at the cached module, a local module beside the configuration at a copy of
  it, and what cannot be read offline is named;
- the plan mocks every provider that could reach a cloud, the ones only a
  module uses declared in the root's one ``required_providers`` block, and
  runs none of the configuration's own tests;
- the plugin folder is found where Terraform itself is told of it;
- the command writes a diagram's skeletons (a document, a diagram file, an
  exported page's diagram) or copies a Terraform folder, refuses what it
  cannot read, and with Terraform and the providers at hand plans them:
  a valid one passes, a broken one fails with Terraform's words, the user's
  values are the plan's, and the folder checked is left as it was.
"""

from __future__ import annotations

import ipaddress
import json
import re
import shutil
from pathlib import Path

import pytest

from infragram.paths import repo_root
from infragram.terraform import check
from infragram.terraform.hclread import parse, type_of

TEMPLATES = (
    repo_root() / "plugin" / "skills" / "infragram-architect" / "assets" / "templates" / "cloud"
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------------ values
def test_a_made_up_value_follows_the_name_then_the_type():
    assert check.made_up("db_password", type_of("string")) == "Demo-Passw0rd-123!"
    assert check.made_up("vpc_cidr", type_of("string")) == "10.9.0.0/16"
    assert check.made_up("admin_ssh_public_key").startswith("ssh-rsa ")
    assert check.made_up("name") == "demo"
    assert check.made_up("count_of", type_of("number")) == 1
    assert check.made_up("enabled", type_of("bool")) is False
    assert check.made_up("ports", type_of("list(number)")) == [1]
    assert check.made_up("zones", type_of("set(string)")) == ["demo"]
    assert check.made_up("tags", type_of("map(string)")) == {}
    assert check.made_up("pair", type_of("tuple([string, number])")) == ["demo", 1]
    # the name decides only where the type allows it
    assert check.made_up("enable_secret_rotation", type_of("bool")) is False
    assert check.made_up("password_length", type_of("number")) == 1
    assert check.made_up("secrets", type_of("map(string)")) == {}
    assert check.made_up("ssh_keys", type_of("list(string)")) == [
        check.made_up("ssh_key", type_of("string"))
    ]
    assert check.made_up("subresource_names", type_of("list(string)")) == ["blob"]
    assert check.made_up("subresource_names", type_of("string")) == "demo"
    # an object gets its required attributes, never its optional ones
    assert check.made_up(
        "site", type_of("object({ name = string, size = optional(number, 2) })")
    ) == {"name": "demo"}


def test_a_value_something_gave_is_never_made_up(tmp_path, monkeypatch):
    _write(tmp_path / "terraform.tfvars", 'region = "eu-west-1"\n')
    _write(tmp_path / "terraform.tfvars.json", json.dumps({"zone": "a"}))
    _write(tmp_path / "prod.auto.tfvars", "size = 2\n")
    mine = _write(tmp_path.parent / f"{tmp_path.name}-mine.tfvars", 'owner = "me"\n')
    given = check._given(tmp_path, [mine], ["tier=web"])
    assert given == {"region", "zone", "size", "owner", "tier"}
    # a TF_VAR_ variable is passed on by the name the configuration writes
    # (Windows hands the environment on in capitals), and only where nothing
    # else gives the value, which would take precedence over it
    monkeypatch.setenv("TF_VAR_team", "platform")
    monkeypatch.setenv("TF_VAR_region", "us-east-2")
    assert check._from_environment(["team", "region", "size"], given) == ["team=platform"]


# ------------------------------------------------------------------ modules
def test_every_module_call_points_inside_the_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path / "cache"))
    cached = tmp_path / "cache" / "terraform" / "modules" / "acme" / "thing" / "aws"
    _write(
        cached / "1.2.0" / "main.tf",
        'module "inner" {\n  source = "./modules/inner"\n}\n\n'
        'module "other" {\n  source  = "acme/other/aws"\n  version = "3.0.0"\n}\n',
    )
    _write(cached / "1.2.0" / "modules" / "inner" / "main.tf", "")
    _write(cached / "2.0.0" / "main.tf", "")
    root = tmp_path / "root"
    _write(
        root / "main.tf",
        'module "app" {\n  source = "./modules/app"\n}\n\n'
        'module "thing" {\n  source  = "acme/thing/aws"\n  version = "~> 1.0" # the 1.x line\n}\n\n'
        'module "far" {\n  source = "git::https://example.com/far.git"\n}\n',
    )
    _write(root / "modules" / "app" / "main.tf", "")

    found = check.vendor(root)

    text = (root / "main.tf").read_text(encoding="utf-8")
    assert 'source  = "./.vendor/acme/thing/aws/1.2.0"' in text and "version" not in text
    assert 'source = "./modules/app"' in text
    names = [folder.relative_to(root.resolve()).as_posix() for folder in found.folders]
    assert names == [
        ".",
        "modules/app",
        ".vendor/acme/thing/aws/1.2.0",
        ".vendor/acme/thing/aws/1.2.0/modules/inner",
    ]
    assert found.missing == [
        "the module git::https://example.com/far.git (not from the public registry)",
        "the module acme/other/aws 3.0.0",
    ]


def test_a_local_module_beside_the_configuration_is_copied_in(tmp_path):
    original = tmp_path / "project" / "live"
    _write(original / "main.tf", 'module "net" {\n  source = "../shared/net"\n}\n')
    _write(tmp_path / "project" / "shared" / "net" / "main.tf", 'resource "aws_vpc" "this" {}\n')
    work = check.copy_configuration(original, tmp_path / "work" / "live")

    found = check.vendor(work, original)

    assert 'source = "./.vendor/local/1-net"' in (work / "main.tf").read_text(encoding="utf-8")
    assert (work / ".vendor" / "local" / "1-net" / "main.tf").is_file()
    assert found.missing == [] and len(found.folders) == 2
    # the original is read, never written
    assert '"../shared/net"' in (original / "main.tf").read_text(encoding="utf-8")


def test_a_missing_local_module_is_left_for_init_to_name(tmp_path):
    """terraform init says a module is missing, as it would anywhere; the
    check does not crash copying what is not there."""
    root = tmp_path / "root"
    _write(root / "main.tf", 'module "gone" {\n  source = "../does-not-exist"\n}\n')
    found = check.vendor(root)
    assert '"../does-not-exist"' in (root / "main.tf").read_text(encoding="utf-8")
    assert found.missing == [] and len(found.folders) == 1


def test_the_command_names_a_folder_of_diagrams_and_checks_dot_by_its_name(
    tmp_path, monkeypatch
) -> None:
    from infragram.cli.user.check_terraform import _gather, _Refused

    pages = tmp_path / "dist"
    _write(pages / "shop.html", "")
    _write(pages / "shop.infragram.json", "{}")
    with pytest.raises(_Refused, match=r"it holds diagrams \(shop.html, shop.infragram.json\)"):
        _gather([pages], "both", tmp_path / "work")
    project = tmp_path / "my-terraform"
    _write(project / "main.tf", "")
    monkeypatch.chdir(project)
    ((copy, original, name),) = _gather([Path(".")], "both", tmp_path / "work2")
    assert (
        copy == tmp_path / "work2" / "my-terraform"
        and original == Path(".")
        and name == "my-terraform"
    )


def test_a_copy_leaves_out_state_locks_and_the_configurations_own_tests(tmp_path):
    source = tmp_path / "source"
    for name in (
        "main.tf",
        ".terraform.lock.hcl",
        "terraform.tfstate",
        "terraform.tfstate.backup",
        "tests/apply.tftest.hcl",
        ".terraform/modules/modules.json",
        "terraform.tfvars",
    ):
        _write(source / name, "")
    copy = check.copy_configuration(source, tmp_path / "copy")
    assert sorted(
        path.relative_to(copy).as_posix() for path in copy.rglob("*") if path.is_file()
    ) == ["main.tf", "terraform.tfvars"]


# ---------------------------------------------------------------- providers
def test_the_plan_mocks_every_provider_that_could_reach_a_cloud(tmp_path):
    _write(
        tmp_path / "root" / "versions.tf",
        "terraform {\n  required_providers {\n"
        '    aws = {\n      source  = "hashicorp/aws"\n      version = "~> 6.0"\n    }\n'
        '    random = {\n      source = "hashicorp/random"\n    }\n  }\n}\n',
    )
    _write(
        tmp_path / "root" / "main.tf",
        'resource "terraform_data" "marker" {}\n\n'
        'provider "aws" {\n  alias  = "west"\n  region = "us-west-2"\n}\n',
    )
    _write(
        tmp_path / "module" / "main.tf",
        "terraform {\n  required_providers {\n"
        '    modtm = {\n      source = "Azure/modtm"\n    }\n  }\n}\n\n'
        'data "azuread_client_config" "me" {}\nresource "time_sleep" "wait" {}\n',
    )
    root, module = check._uses(tmp_path / "root"), check._uses(tmp_path / "module")
    assert root == {"aws": "hashicorp/aws", "random": "hashicorp/random"}
    assert module == {
        "modtm": "azure/modtm",
        "azuread": "hashicorp/azuread",
        "time": "hashicorp/time",
    }

    mocked, declare, clash = check._mocks(root, [module])
    # random and time work on the machine; everything else is mocked, external
    # (a program) and tls (a URL) among it
    assert (
        "hashicorp/external" not in check.LOCAL_PROVIDERS
        and "hashicorp/tls" not in check.LOCAL_PROVIDERS
    )
    assert mocked == {
        "aws": "hashicorp/aws",
        "modtm": "azure/modtm",
        "azuread": "hashicorp/azuread",
    }
    assert declare == {"modtm": "azure/modtm", "azuread": "hashicorp/azuread"} and clash == []
    # a module's name for a provider the root names otherwise cannot be mocked
    assert check._mocks(root, [{"aws": "someone/aws"}])[2] == ["someone/aws"]

    test = check._test_file(mocked, check._aliases(tmp_path / "root"))
    assert 'mock_provider "aws" {\n  alias = "west"' in test
    assert test.count('mock_provider "aws" {') == 2 and 'mock_data "aws_availability_zones"' in test
    assert 'mock_provider "random"' not in test and 'run "plan" {\n  command = plan\n}' in test


def test_another_configurations_state_is_never_read(tmp_path):
    """No mock answers terraform_remote_state: a plan would read it from its
    backend, so a configuration that reads one is validated, not planned."""
    _write(
        tmp_path / "root" / "main.tf",
        'data "terraform_remote_state" "network" {\n  backend = "s3"\n}\n',
    )
    _write(tmp_path / "module" / "main.tf", 'data "aws_vpc" "this" {}\n')
    assert check._remote_states([tmp_path / "root", tmp_path / "module"]) == [
        "data.terraform_remote_state.network"
    ]
    assert check._uses(tmp_path / "root") == {}


def test_a_provider_only_modules_use_is_declared_in_the_roots_one_block(tmp_path):
    versions = _write(
        tmp_path / "declared" / "versions.tf",
        'terraform {\n  required_providers {\n    aws = {\n      source = "hashicorp/aws"\n    }\n  }\n}\n',
    )
    check._declare(tmp_path / "declared", {"modtm": "azure/modtm"})
    body = parse(versions.read_text(encoding="utf-8"))
    (block,) = body.blocks_of("terraform")[0].body.blocks_of("required_providers")
    assert set(block.body.attributes) == {"aws", "modtm"}
    assert not (tmp_path / "declared" / check.PROVIDERS_FILE).exists()

    _write(tmp_path / "bare" / "main.tf", 'resource "aws_vpc" "this" {}\n')
    check._declare(tmp_path / "bare", {"modtm": "azure/modtm"})
    assert 'modtm = { source = "azure/modtm" }' in (
        tmp_path / "bare" / check.PROVIDERS_FILE
    ).read_text(encoding="utf-8")


def test_the_plugin_folder_is_where_terraform_is_told_of_it(tmp_path, monkeypatch):
    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("TF_PLUGIN_CACHE_DIR", str(tmp_path / "from-env"))
    assert check.plugin_folder() == tmp_path / "from-env"
    monkeypatch.delenv("TF_PLUGIN_CACHE_DIR")
    config = _write(
        tmp_path / "terraform.rc", f'plugin_cache_dir = "{(tmp_path / "configured").as_posix()}"\n'
    )
    monkeypatch.setenv("TF_CLI_CONFIG_FILE", str(config))
    assert check.plugin_folder() == tmp_path / "configured"
    monkeypatch.setenv("TF_CLI_CONFIG_FILE", str(tmp_path / "none.rc"))
    assert check.plugin_folder() is None
    (tmp_path / "cache" / "terraform" / "plugins").mkdir(parents=True)
    assert check.plugin_folder() == tmp_path / "cache" / "terraform" / "plugins"
    assert check.provider_source("registry.terraform.io/Azure/azapi") == "azure/azapi"
    assert check.provider_source("aws") == "hashicorp/aws"


# ------------------------------------------------------------------ command
def test_the_command_is_listed(capsys):
    from infragram import cli

    with pytest.raises(SystemExit):
        cli.main(["--help"])
    assert "check:terraform" in capsys.readouterr().out


def test_the_command_refuses_what_it_cannot_read(tmp_path, capsys):
    from infragram.cli.user.check_terraform import main

    full = _write(tmp_path / "kept" / "something.txt", "").parent
    document = TEMPLATES / "gcp-three-tier-web.infragram.json"
    assert main([str(document), "--keep", str(full)]) == 2
    assert main([str(tmp_path), "--keep", str(tmp_path / "inside")]) == 2
    assert main([str(document), "--var", "no-equals-sign"]) == 2
    assert main([str(document), "--var-file", str(tmp_path / "missing.tfvars")]) == 2
    errors = capsys.readouterr().err
    assert "not a new or empty folder" in errors and "is inside" in errors
    assert "NAME=VALUE" in errors and "is not a file" in errors


def test_the_command_reads_a_document_a_page_or_terraform_folders(tmp_path):
    from infragram.cli.user.check_terraform import _gather, _Refused
    from infragram.exports.render import render_project_html
    from infragram.projects import CloudProject

    project = CloudProject.load(TEMPLATES / "gcp-three-tier-web.infragram.json")
    page = _write(tmp_path / "page.html", render_project_html(project))
    found = _gather(
        [TEMPLATES / "gcp-three-tier-web.infragram.json", page], "both", tmp_path / "work"
    )
    # a skeleton written here is checked in its prod environment, which carries the diagram's values
    assert [name for _folder, _original, name in found] == [
        "gcp-three-tier-web-terraform/prod",
        "gcp-three-tier-web-terraform-modules/prod",
        "gcp-three-tier-web-terraform-2/prod",
        "gcp-three-tier-web-terraform-modules-2/prod",
    ]
    assert all(
        original is None and (folder / "main.tf").is_file() for folder, original, _name in found
    )

    # a skeleton given as a folder is each of its environments
    exported = tmp_path / "dist"
    shutil.copytree(found[0][0].parent.parent, exported / "a-terraform")
    _write(exported / "page.html", "")
    copied = _gather([exported], "modules", tmp_path / "work2")
    assert [(name, original) for _folder, original, name in copied] == [
        ("a-terraform/dev", exported / "a-terraform" / "environments" / "dev"),
        ("a-terraform/prod", exported / "a-terraform" / "environments" / "prod"),
    ]

    with pytest.raises(_Refused, match="holds no Terraform"):
        _gather([_write(tmp_path / "empty" / "notes.txt", "").parent], "both", tmp_path / "work3")
    with pytest.raises(_Refused, match="draws nothing"):
        _gather([TEMPLATES / "campus-lan-wan.infragram.json"], "both", tmp_path / "work4")


def _terraform_ready(*sources: str) -> bool:
    folder = check.plugin_folder()
    return (
        shutil.which("terraform") is not None
        and folder is not None
        and all((folder / "registry.terraform.io" / source).is_dir() for source in sources)
    )


@pytest.mark.slow
@pytest.mark.skipif(
    not _terraform_ready("hashicorp/google"),
    reason="needs the Terraform CLI and the google provider in a plugin folder",
)
def test_the_command_plans_a_folder_and_says_what_fails(tmp_path, capsys):
    from infragram.cli.user.check_terraform import main
    from infragram.projects import CloudProject
    from infragram.terraform import write_terraform

    project = CloudProject.load(TEMPLATES / "gcp-three-tier-web.infragram.json")
    mine = tmp_path / "mine"
    edited = write_terraform(project, mine).directory
    _write(edited / "environments" / "prod" / "terraform.tfvars", 'gcp_region = "europe-west1"\n')
    broken = shutil.copytree(edited, mine / "broken-terraform")
    # a module both environments call, broken: each of them fails
    with open(broken / "modules" / "storage" / "main.tf", "a", encoding="utf-8") as file:
        file.write(
            '\nresource "google_storage_bucket" "oops" {\n  name            = "x"\n  not_an_argument = true\n}\n'
        )
    before = sorted(path.relative_to(mine).as_posix() for path in mine.rglob("*"))

    status = main([str(mine), "--output-dir", str(tmp_path / "plans")])

    out = capsys.readouterr().out
    assert status == 1, out
    passed = re.search(
        r"^PASS     gcp-three-tier-web-terraform/prod: fmt ok, init ok, validate ok, plan ok "
        r"\((\d+) to create\)$",
        out,
        re.MULTILINE,
    )
    assert passed, out
    assert "PASS     gcp-three-tier-web-terraform/dev:" in out
    assert "FAIL     broken-terraform/prod: fmt ok, init ok, validate FAIL" in out
    assert 'An argument named "not_an_argument" is not expected here.' in out
    plan = (tmp_path / "plans" / "gcp-three-tier-web-terraform-prod.plan.txt").read_text(
        encoding="utf-8"
    )
    assert (
        f"Plan: {passed.group(1)} to add, 0 to change, 0 to destroy." in plan
        and '"europe-west1"' in plan
    )
    assert "gcp_region" not in plan.split("# Made-up values:")[1].splitlines()[0]
    # the folders checked are as they were: the check ran on copies
    assert sorted(path.relative_to(mine).as_posix() for path in mine.rglob("*")) == before
    # a configuration Terraform refuses before the plan has no plan to write
    assert not (tmp_path / "plans" / "broken-terraform-prod.plan.txt").exists()


def test_a_made_up_list_of_subnet_ranges_is_real_distinct_ranges():
    lists = {}
    for name in ("public_subnet_cidrs", "private_subnet_cidrs", "allowed_cidr_blocks"):
        for kind in (type_of("list(string)"), ("any",)):
            value = check.made_up(name, kind)
            assert isinstance(value, list) and len(value) >= 3, (name, value)
            networks = [ipaddress.ip_network(cidr) for cidr in value]  # raises on "demo"
            assert len(set(networks)) == len(networks), value
            assert all(16 <= n.prefixlen <= 28 for n in networks), value
            lists[name] = networks
    public, private = lists["public_subnet_cidrs"], lists["private_subnet_cidrs"]
    assert not any(a.overlaps(b) for a in public for b in private), (public, private)
    # one range where the variable holds one
    assert check.made_up("vpc_cidr", type_of("string")) == "10.9.0.0/16"
    assert ipaddress.ip_network(check.made_up("public_subnet_cidrs", type_of("string")))
