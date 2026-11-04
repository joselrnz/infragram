"""Terraform to a diagram: ``import:terraform``.

Held here with fixtures under ``tests/fixtures/estate/``:

- a configuration is read the way Terraform resolves it: variables from their
  defaults and ``terraform.tfvars``, locals, ``count`` and ``for_each``
  instances, references followed through module inputs and outputs (an
  indexed output reaches that one instance), a registry module named in the
  notes; and one written in the registry's own style (conditional counts,
  ``for`` expressions, ``regexall()``, ``element()`` through a local, dynamic
  blocks, a module per ``for_each`` key, the blocks a reader passes over)
  resolves every count and draws each piece where it sits;
- a plan reads its configuration's references (the most specific of each)
  and its provider's region; a state reads its ids into references, never
  a name into one;
- the drawing puts each resource in the deepest frame it names, public
  subnets by their own say, wires from security group rules, load balancer
  targets and event sources, folds helpers into what they belong to and says
  where every resource went;
- Azure network security groups and Google Cloud firewall rules draw the
  traffic they allow, from the internet, a range, an application security
  group, a tag or a service account, and nothing for a deny, an outbound
  rule, a ping, a service tag or a range that holds its own targets;
- the diagram file is the composer's form and draws a picture the checker
  passes; the command writes it with its report, refuses to overwrite, and
  exports through the usual options;
- a diagram's Terraform export, imported, draws the same components.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from infragram.estate import draw, write_spec
from infragram.estate.report import write_report
from infragram.estate.tables import component_class, frame_class, type_table
from infragram.paths import repo_root
from infragram.projects import CloudProject
from infragram.terraform import terraform_files
from infragram.terraform.mapping import PROVIDERS, load_mapping
from infragram.terraform.readconfig import ConfigurationError, read_configuration
from infragram.terraform.readstate import StateError, read_show_json

ROOT = repo_root()
FIXTURES = ROOT / "tests" / "fixtures" / "estate"
SHOP = FIXTURES / "terraform" / "shop"
REGISTRY = FIXTURES / "terraform" / "registry"
RULES_AZURE = FIXTURES / "terraform" / "rules-azure"
RULES_GCP = FIXTURES / "terraform" / "rules-gcp"
TEMPLATES = ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "templates" / "cloud"


def _pinned_modules_cached() -> bool:
    from infragram.terraform.mapping import load_modules
    from infragram.terraform.readconfig import module_cache

    return all(
        (module_cache() / module.package / module.version).is_dir()
        for module in load_modules().modules.values()
    )


_MODULES = pytest.mark.skipif(
    not _pinned_modules_cached(),
    reason="the module cache does not hold the pinned "
    "registry modules (infragram verify:terraform --fetch)",
)


def _cards(drawing):
    from infragram.estate import Card

    return {item.key: item for item in drawing.walk() if isinstance(item, Card)}


def _parent_of(drawing, key: str) -> str | None:
    from infragram.estate import Box

    def visit(box, parent):
        for child in box.children:
            if child.key == key:
                return box.key
            if isinstance(child, Box):
                found = visit(child, box)
                if found:
                    return found
        return None

    for root in drawing.roots:
        if isinstance(root, Box):
            found = visit(root, None)
            if found:
                return found
    return None


# ---------------------------------------------------------------- the tables
#: The frames the import makes up around what it reads, per library.
_PLACES = {
    "aws": {"cloud", "region", "zone"},
    "azure": {"subscription", "region"},
    "gcp": {"project"},
}


@pytest.mark.parametrize("library", PROVIDERS)
def test_every_import_entry_draws_with_a_class_the_library_has(library):
    table = type_table(library)
    services = (
        {s for s in table.components.values() if s}
        | set(table.collapse.values())
        | {table.fallback}
    )
    assert sorted(s for s in services if component_class(library, s) is None) == []
    kinds = set(table.frames.values()) | {"subnet-public", "subnet-private"} | _PLACES[library]
    assert sorted(k for k in kinds if frame_class(library, k) is None) == []


# ---------------------------------------------------------------- a configuration
def test_a_configuration_resolves_as_terraform_would():
    estate = read_configuration(SHOP)
    by = {found.address: found for found in estate.resources}
    # terraform.tfvars over the defaults, locals built from them
    assert by["aws_sqs_queue.jobs"].values["name"] == "shop-prod-jobs"
    # count and for_each expand, cidrsubnet evaluates
    assert {a for a in by if "aws_subnet" in a} == {
        'module.network.aws_subnet.public["a"]',
        'module.network.aws_subnet.public["b"]',
        "module.network.aws_subnet.private[0]",
        "module.network.aws_subnet.private[1]",
    }
    assert by["module.network.aws_subnet.private[1]"].values["cidr_block"] == "10.40.11.0/24"
    # an indexed module output reaches that one instance
    assert by["aws_instance.web[1]"].references["subnet_id"] == [
        "module.network.aws_subnet.private[1]"
    ]
    # a whole output reaches every instance, a module input the resource behind it
    assert by["aws_lb.public"].references["subnets"] == ["module.network.aws_subnet.public"]
    assert by["module.network.aws_nat_gateway.this"].references["subnet_id"] == [
        'module.network.aws_subnet.public["a"]'
    ]
    assert by["aws_security_group.web"].references["vpc_id"] == ["module.network.aws_vpc.this"]
    line = (SHOP / "main.tf").read_text(encoding="utf-8").splitlines().index(
        'resource "aws_instance" "web" {'
    ) + 1
    assert by["aws_instance.web[0]"].source == f"main.tf:{line}"
    assert any("module.labels" in note and "cloudposse/label/null" in note for note in estate.notes)
    # the origin names the variable file it read, not "no variable file"
    assert (
        estate.origin
        == "the Terraform in shop/ (terraform.tfvars; variables otherwise their defaults)"
    )


def test_the_registrys_own_style_resolves_as_terraform_would():
    estate = read_configuration(REGISTRY)
    # every count and for_each is known: for expressions build the subnets'
    # ranges and the services' maps, regexall() picks the zone
    assert estate.notes == []
    by = {found.address: found for found in estate.resources}
    subnets = [a for a in by if a.startswith("module.vpc.aws_subnet.")]
    assert subnets == [
        f"module.vpc.aws_subnet.{kind}[{i}]" for kind in ("public", "private") for i in range(3)
    ]
    assert by["module.vpc.aws_subnet.private[2]"].values["availability_zone"] == "eu-west-1c"
    assert by["module.vpc.aws_subnet.private[1]"].values["cidr_block"] == "10.60.16.0/20"
    assert by["module.vpc.aws_subnet.public[0]"].values["cidr_block"] == "10.60.48.0/24"
    assert [a for a in by if a.startswith("aws_lb")] == [
        "aws_lb.public[0]",
        'aws_lb_target_group.service["api"]',
        'aws_lb_target_group_attachment.service["api"]',
        "aws_lb_listener.https[0]",
    ]
    # a module instance's output by its key; element() through a local and
    # through a module output; each.value names what its for_each names
    assert by['aws_instance.service["worker"]'].references["vpc_security_group_ids"] == [
        'module.service_sg["worker"].aws_security_group.this'
    ]
    assert by['aws_instance.service["worker"]'].references["subnet_id"] == [
        "module.vpc.aws_subnet.private[1]"
    ]
    assert by["module.vpc.aws_nat_gateway.this[2]"].references == {
        "allocation_id": ["module.vpc.aws_eip.nat[2]"],
        "subnet_id": ["module.vpc.aws_subnet.public[2]"],
        "depends_on": ["module.vpc.aws_internet_gateway.this"],
    }
    assert by[
        'module.service_sg["api"].aws_vpc_security_group_ingress_rule.this["8080"]'
    ].references == {
        "security_group_id": ['module.service_sg["api"].aws_security_group.this'],
        "referenced_security_group_id": ["aws_security_group.alb"],
    }
    # a dynamic block is one block per element, in the set's order
    assert [
        (b["from_port"], b["cidr_blocks"]) for b in by["aws_security_group.alb"].values["ingress"]
    ] == [(80, ["0.0.0.0/0"]), (443, ["0.0.0.0/0"])]
    # a provider alias, a JSON file; a check's data source is not the configuration's
    assert by["aws_s3_bucket.logs"].region == "us-east-1"
    assert by["aws_sqs_queue.jobs"].source == "queue.tf.json"
    assert "data.http.api" not in by

    drawing = draw(estate)
    kinds = {item.key: item.kind for item in drawing.walk() if hasattr(item, "kind")}
    assert [kinds[f"module.vpc.aws_subnet.public[{i}]"] for i in range(3)] == ["subnet-public"] * 3
    for i, zone in enumerate("abc"):
        # a NAT gateway per zone, each in its zone's public subnet
        assert (
            _parent_of(drawing, f"module.vpc.aws_nat_gateway.this[{i}]")
            == f"module.vpc.aws_subnet.public[{i}]"
        )
        assert (
            _parent_of(drawing, f"module.vpc.aws_subnet.private[{i}]")
            == f"zone:module.vpc.aws_vpc.this[0]:eu-west-1{zone}"
        )
    assert (
        _parent_of(drawing, 'aws_instance.service["worker"]') == "module.vpc.aws_subnet.private[1]"
    )
    assert {(w.source, w.target): w.label for w in drawing.wires} == {
        ("internet", "aws_lb.public[0]"): "HTTP :80 · HTTPS :443",
        ("aws_lb.public[0]", 'aws_instance.service["api"]'): "HTTP :8080",
        # the worker's group lets the load balancer's in, though no target group sends
        ("aws_lb.public[0]", 'aws_instance.service["worker"]'): "TCP :9000",
    }
    assert (
        drawing.folded["module.vpc.aws_eip.nat[1]"] == "used by module.vpc.aws_nat_gateway.this[1]"
    )
    assert not drawing.unmapped


def test_variables_given_win_and_a_broken_file_is_refused(tmp_path):
    estate = read_configuration(SHOP, values={"environment": "stage", "web_count": 3})
    names = sorted(f.values["tags"]["Name"] for f in estate.resources if f.type == "aws_instance")
    assert names == ["shop-stage-web-1", "shop-stage-web-2", "shop-stage-web-3"]
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "main.tf").write_text(
        'resource "aws_vpc" "x" {\n  cidr_block = "10.0.0.0/16"\n', encoding="utf-8"
    )
    with pytest.raises(ConfigurationError, match="never closed"):
        read_configuration(broken)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ConfigurationError, match="holds no"):
        read_configuration(empty)


def test_the_drawing_puts_each_resource_where_it_sits_and_wires_the_traffic():
    drawing = draw(read_configuration(SHOP))
    cards = _cards(drawing)
    assert _parent_of(drawing, "aws_instance.web[0]") == "module.network.aws_subnet.private[0]"
    assert _parent_of(drawing, "aws_instance.web[1]") == "module.network.aws_subnet.private[1]"
    assert (
        _parent_of(drawing, "module.network.aws_nat_gateway.this")
        == 'module.network.aws_subnet.public["a"]'
    )
    assert (
        _parent_of(drawing, "module.network.aws_internet_gateway.this")
        == "module.network.aws_vpc.this"
    )
    kinds = {item.key: item.kind for item in drawing.walk() if hasattr(item, "kind")}
    assert kinds['module.network.aws_subnet.public["a"]'] == "subnet-public"
    assert kinds["module.network.aws_subnet.private[0]"] == "subnet-private"
    wires = {(w.source, w.target): w.label for w in drawing.wires}
    assert wires == {
        ("internet", "aws_lb.public"): "HTTPS :443",
        ("aws_lb.public", "aws_instance.web[0]"): "HTTP :8080",
        ("aws_lb.public", "aws_instance.web[1]"): "HTTP :8080",
        ("aws_sqs_queue.jobs", "aws_lambda_function.worker"): "events",
    }
    # names shed the prefix they share; a module's "this" says what it is
    assert cards["aws_instance.web[0]"].caption == "web-1"
    assert cards["module.network.aws_internet_gateway.this"].caption == "internet gateway"
    # every resource is accounted for
    assert set(drawing.drawn) | set(drawing.folded) | set(drawing.left_out) == {
        f.address for f in read_configuration(SHOP).resources
    }
    assert drawing.left_out["aws_iam_role.worker"].startswith("not architecture")
    assert drawing.left_out["random_password.db"].startswith("not architecture")
    assert drawing.folded["aws_lb_listener.https"] == "part of aws_lb.public"


# ---------------------------------------------------------------- a plan and a state
def test_a_plan_reads_its_configuration_and_its_region():
    estate = read_show_json(FIXTURES / "plan.json")
    by = {found.address: found for found in estate.resources}
    assert by["aws_instance.web[0]"].references["subnet_id"] == ["module.vpc.aws_subnet.private[0]"]
    assert by["aws_security_group.web"].references["vpc_id"] == ["module.vpc.aws_vpc.this[0]"]
    drawing = draw(estate)
    boxes = {item.key: item for item in drawing.walk() if hasattr(item, "kind")}
    assert "region:aws:us-west-2" in boxes
    # the registry module sets its subnets' VPC through a local the plan does
    # not expand: the one VPC of that module holds them, and its gateway
    assert (
        _parent_of(drawing, "module.vpc.aws_subnet.private[1]")
        == "zone:module.vpc.aws_vpc.this[0]:us-west-2b"
    )
    assert (
        _parent_of(drawing, "module.vpc.aws_internet_gateway.this[0]")
        == "module.vpc.aws_vpc.this[0]"
    )
    assert _parent_of(drawing, "aws_instance.web[0]") == "module.vpc.aws_subnet.private[0]"


def test_a_state_reads_its_ids_into_references_and_never_a_name():
    estate = read_show_json(FIXTURES / "terraform.tfstate")
    by = {found.address: found for found in estate.resources}
    assert by["module.api.aws_instance.this"].references == {
        "subnet_id": ["aws_subnet.app[0]"],
        "vpc_security_group_ids": ["aws_security_group.api"],
    }
    assert by["aws_db_instance.db"].references == {
        "db_subnet_group_name": ["aws_db_subnet_group.db"],
        "vpc_security_group_ids": ["aws_security_group.db"],
    }
    drawing = draw(estate)
    assert [(w.source, w.target, w.label) for w in drawing.wires] == [
        ("module.api.aws_instance.this", "aws_db_instance.db", "MySQL :3306")
    ]
    assert _parent_of(drawing, "aws_db_instance.db") == "aws_subnet.app[0]"


# ---------------------------------------------------------------- Azure and Google Cloud rules
def test_azure_network_security_groups_draw_the_traffic_they_allow():
    estate = read_configuration(RULES_AZURE)
    drawing = draw(estate)
    vm = "azurerm_linux_virtual_machine."
    assert {(w.source, w.target): w.label for w in drawing.wires} == {
        # inline rules on the web subnet's group: from the internet, and from
        # a range of one address, the jump box's own
        ("internet", f"{vm}web[0]"): "HTTPS :443",
        ("internet", f"{vm}web[1]"): "HTTPS :443",
        (f"{vm}jump", f"{vm}web[0]"): "SSH :22",
        (f"{vm}jump", f"{vm}web[1]"): "SSH :22",
        # rule resources on the group of the database's interface: from an
        # application security group, and from a subnet's range on two ports
        (f"{vm}web[0]", f"{vm}db"): "PostgreSQL :5432",
        (f"{vm}web[1]", f"{vm}db"): "PostgreSQL :5432",
        (f"{vm}jump", f"{vm}db"): "SSH :22 · TCP 8000-8080",
    }
    # the web subnet's group is a badge on its corner too; the group on the
    # database's interface is no card, the way the export writes a
    # machine's rules back (on its interface's group)
    assert (
        drawing.folded["azurerm_network_security_group.web"]
        == "drawn as a badge on its subnet and the wires it allows"
    )
    badged = {
        item.key: [(badge.service_id, badge.label) for badge in item.badges]
        for item in drawing.walk()
        if getattr(item, "badges", None)
    }
    assert badged == {"azurerm_subnet.web": [("network-security-groups", "nsg-web")]}
    assert (
        drawing.folded["azurerm_network_security_rule.postgres"] == "drawn as the wires it allows"
    )
    # a range that holds the guarded subnet says anything inside may pass
    assert drawing.left_out["azurerm_network_security_rule.inside"].startswith("not architecture")
    # the groups, rules and associations are no cards
    assert not drawing.unmapped
    assert set(drawing.drawn) | set(drawing.folded) | set(drawing.left_out) == {
        f.address for f in estate.resources
    }


def test_google_cloud_firewall_rules_draw_the_traffic_they_allow():
    estate = read_configuration(RULES_GCP)
    drawing = draw(estate)
    vm = "google_compute_instance."
    assert {(w.source, w.target): w.label for w in drawing.wires} == {
        ("internet", f"{vm}web[0]"): "HTTPS :443",
        ("internet", f"{vm}web[1]"): "HTTPS :443",
        # a source tag to a target tag
        (f"{vm}bastion", f"{vm}web[0]"): "SSH :22",
        (f"{vm}bastion", f"{vm}web[1]"): "SSH :22",
        # a service account to a service account, then a subnetwork's range
        # to a tag: one wire per pair, the ports together
        (f"{vm}web[0]", f"{vm}db"): "PostgreSQL :5432 · TCP :9100 · TCP :9187",
        (f"{vm}web[1]", f"{vm}db"): "PostgreSQL :5432 · TCP :9100 · TCP :9187",
        (f"{vm}bastion", f"{vm}db"): "TCP :9100 · TCP :9187",
        # a managed instance group wears its template's tag; a protocol by number
        (f"{vm}web[0]", "google_compute_region_instance_group_manager.api"): "TCP :8080",
        (f"{vm}web[1]", "google_compute_region_instance_group_manager.api"): "TCP :8080",
    }
    assert (
        _parent_of(drawing, "google_compute_region_instance_group_manager.api")
        == "google_compute_subnetwork.app"
    )
    # Google's own ranges reach nothing drawn, the internal range holds every
    # subnetwork, a ping is no flow, a disabled or outbound rule allows nothing
    for rule in ("health", "iap", "internal", "ping", "legacy", "egress"):
        assert drawing.left_out[f"google_compute_firewall.{rule}"].startswith("not architecture")
    assert drawing.folded["google_compute_firewall.postgres"] == "drawn as the wires it allows"


def _wires_by_caption(drawing) -> dict[tuple[str, str], str]:
    captions = {item.key: item.caption for item in drawing.walk()}
    return {(captions[w.source], captions[w.target]): w.label for w in drawing.wires}


@pytest.mark.parametrize(
    ("folder", "style"),
    [
        pytest.param(folder, style, marks=[_MODULES] if style == "modules" else [])
        for folder in ("rules-azure", "rules-gcp")
        for style in ("resources", "modules")
    ],
)
def test_the_rule_fixtures_round_trip_through_both_styles(folder, style, tmp_path):
    """Each rule fixture drawn, exported in either style, and read again: the
    same wires, through the registry's modules as through plain resources."""
    from infragram.cli.user.compose import project_from_spec
    from infragram.terraform import write_terraform

    first = draw(read_configuration(FIXTURES / "terraform" / folder))
    spec = tmp_path / f"{folder}.py"
    spec.write_text(
        write_spec(
            first, command=f"import:terraform {folder}", date="2026-09-23", filename=spec.name
        ),
        encoding="utf-8",
    )
    written = write_terraform(project_from_spec(spec), tmp_path / "out", style=style)
    again = draw(read_configuration(written.directory))
    assert _wires_by_caption(again) == _wires_by_caption(first)


def test_google_cloud_firewall_wires_round_trip_through_the_export(tmp_path):
    """The rules fixture drawn, exported as Terraform, and read again: the
    instances wear their network tags, the internet reaches the two it wires
    to through an external address, and every wire comes back as it went."""
    from infragram.cli.user.compose import project_from_spec

    first = draw(read_configuration(RULES_GCP))
    spec = tmp_path / "rules-gcp.py"
    spec.write_text(
        write_spec(
            first, command="import:terraform rules-gcp", date="2026-09-23", filename="rules-gcp.py"
        ),
        encoding="utf-8",
    )
    project = project_from_spec(spec)
    _plan, files = terraform_files(project)
    folder = tmp_path / "skeleton"
    for name, text in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text, encoding="utf-8")
    module = files["modules/security/main.tf"]
    rule = module.split('resource "google_compute_firewall" "db_from_web_0" {', 1)[1].split(
        "\n}\n", 1
    )[0]
    assert re.search(r'source_tags\s*=\s*\["web-0"\]', rule) and re.search(
        r'target_tags\s*=\s*\["db"\]', rule
    )
    assert re.search(r'ports\s*=\s*\["5432", "9100", "9187"\]', rule)
    assert len(re.findall(r'source_ranges\s*=\s*\["0\.0\.0\.0/0"\]', module)) == 2
    compute = files["modules/compute/main.tf"]
    # the internet reaches web-0 and web-1: they alone have an external address
    assert compute.count("access_config {}") == 2
    assert '"${var.gcp_region}-b"' in compute
    again = draw(read_configuration(folder))
    assert _wires_by_caption(again) == _wires_by_caption(first)


def test_azure_security_group_wires_round_trip_through_the_export(tmp_path):
    """The Azure rules fixture drawn, exported and read again: each machine
    wears a network security group on its interface and an application
    security group, and every wire comes back as it went, a port range as a
    range."""
    from infragram.cli.user.compose import project_from_spec

    first = draw(read_configuration(RULES_AZURE))
    spec = tmp_path / "rules-azure.py"
    spec.write_text(
        write_spec(
            first,
            command="import:terraform rules-azure",
            date="2026-09-23",
            filename="rules-azure.py",
        ),
        encoding="utf-8",
    )
    _plan, files = terraform_files(project_from_spec(spec))
    folder = tmp_path / "skeleton"
    for name, text in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text, encoding="utf-8")
    security = files["modules/security/main.tf"]
    rule = security.split('resource "azurerm_network_security_rule" "vm_db_from_vm_jump" {', 1)[1]
    rule = rule.split("\n}\n", 1)[0]
    assert re.search(r'destination_port_ranges\s*=\s*\["22", "8000-8080"\]', rule)
    # the machines' groups are the compute module's, handed in
    assert re.search(
        r"source_application_security_group_ids\s*=\s*\[var\.vm_jump_application_security_group_id\]",
        rule,
    )
    # each rule takes the next priority of its own group
    database = [
        re.search(r"priority\s*=\s*(\d+)", body).group(1)
        for body in re.findall(
            r'resource "azurerm_network_security_rule" "\w+" \{(.*?)\n\}', security, re.S
        )
        if "var.vm_db_network_security_group_name" in body
    ]
    assert database == ["100", "110", "120"]
    assert len(re.findall(r'source_address_prefix\s*=\s*"Internet"', security)) == 2
    again = draw(read_configuration(folder))
    assert _wires_by_caption(again) == _wires_by_caption(first)


def test_a_range_reserved_for_peering_is_plumbing_not_a_load_balancer(tmp_path):
    """The export reserves a global address for Cloud SQL's private services
    connection; read back, it is the network's plumbing, while the load
    balancer's global address stays the load balancer."""
    from infragram.cli.user.compose import project_from_spec
    from infragram.paths import plugin_root
    from infragram.terraform import write_terraform

    written = write_terraform(
        project_from_spec(plugin_root() / "examples" / "gcp_three_tier.py"), tmp_path / "out"
    )
    drawing = draw(read_configuration(written.directory))
    captions = [getattr(item, "caption", "") for item in drawing.walk()]
    assert "lb" in captions
    assert not [caption for caption in captions if "private-services" in caption], captions
    assert "module.network.google_compute_global_address.private_services" in drawing.left_out


def test_a_rule_from_googles_front_ends_comes_back_as_the_load_balancers_wire(tmp_path):
    """A firewall rule from Google's load balancer and health check ranges is
    the load balancer reaching the servers: read back, it is a wire from the
    load balancer drawn in the diagram."""
    from infragram.cli.user.compose import project_from_spec
    from infragram.paths import plugin_root
    from infragram.terraform import write_terraform

    written = write_terraform(
        project_from_spec(plugin_root() / "examples" / "gcp_three_tier.py"), tmp_path / "out"
    )
    drawing = draw(read_configuration(written.directory))
    captions = {item.key: item.caption for item in drawing.walk()}
    wires = {(captions[wire.source], captions[wire.target]) for wire in drawing.wires}
    assert ("lb", "web") in wires, wires


def test_a_private_endpoint_comes_back_wired_to_the_database_it_connects(tmp_path):
    """Read back, a private endpoint is wired to the database whose server it
    connects (the server folds into its database, not into the endpoint that
    names it), and the privatelink zone is plumbing, not a DNS card."""
    from infragram.cli.user.compose import project_from_spec
    from infragram.paths import plugin_root
    from infragram.terraform import write_terraform

    written = write_terraform(
        project_from_spec(plugin_root() / "examples" / "azure_three_tier.py"), tmp_path / "out"
    )
    drawing = draw(read_configuration(written.directory))
    captions = {item.key: item.caption for item in drawing.walk()}
    wires = {(captions[wire.source], captions[wire.target]) for wire in drawing.wires}
    assert ("private-endpoint-mssql-database", "mssql-database") in wires, wires
    assert not [caption for caption in captions.values() if caption.startswith("privatelink.")], (
        captions
    )


def test_a_state_draws_a_rule_that_names_its_group_by_name(tmp_path):
    import json

    group = "/subscriptions/0000/resourceGroups/rg-shop"
    network = f"{group}/providers/Microsoft.Network"
    nic, nsg = f"{network}/networkInterfaces/nic-db", f"{network}/networkSecurityGroups/nsg-data"
    rule = {
        "name": "https-in",
        "direction": "Inbound",
        "access": "Allow",
        "protocol": "Tcp",
        "source_address_prefix": "Internet",
        "source_address_prefixes": [],
        "destination_port_range": "443",
        "destination_port_ranges": [],
        "destination_address_prefix": "*",
        "source_application_security_group_ids": [],
        "destination_application_security_group_ids": [],
    }

    def resource(kind: str, name: str, attributes: dict) -> dict:
        return {
            "mode": "managed",
            "type": kind,
            "name": name,
            "provider": 'provider["registry.terraform.io/hashicorp/azurerm"]',
            "instances": [{"schema_version": 0, "attributes": attributes}],
        }

    state = {
        "version": 4,
        "terraform_version": "1.14.7",
        "serial": 1,
        "lineage": "0",
        "outputs": {},
        "resources": [
            resource(
                "azurerm_resource_group",
                "shop",
                {"id": group, "name": "rg-shop", "location": "westeurope"},
            ),
            resource(
                "azurerm_virtual_network",
                "shop",
                {
                    "id": f"{network}/virtualNetworks/vnet-shop",
                    "name": "vnet-shop",
                    "resource_group_name": "rg-shop",
                    "location": "westeurope",
                    "address_space": ["10.1.0.0/16"],
                },
            ),
            resource(
                "azurerm_subnet",
                "data",
                {
                    "id": f"{network}/virtualNetworks/vnet-shop/subnets/snet-data",
                    "name": "snet-data",
                    "resource_group_name": "rg-shop",
                    "virtual_network_name": "vnet-shop",
                    "address_prefixes": ["10.1.2.0/24"],
                },
            ),
            resource(
                "azurerm_network_interface",
                "db",
                {
                    "id": nic,
                    "name": "nic-db",
                    "resource_group_name": "rg-shop",
                    "location": "westeurope",
                    "ip_configuration": [
                        {
                            "name": "internal",
                            "private_ip_address": "10.1.2.10",
                            "subnet_id": f"{network}/virtualNetworks/vnet-shop/subnets/snet-data",
                        }
                    ],
                },
            ),
            resource(
                "azurerm_linux_virtual_machine",
                "db",
                {
                    "id": f"{group}/providers/Microsoft.Compute/virtualMachines/vm-db",
                    "name": "vm-db",
                    "resource_group_name": "rg-shop",
                    "location": "westeurope",
                    "network_interface_ids": [nic],
                },
            ),
            # the provider reads a group's rules back into it, rule resources too
            resource(
                "azurerm_network_security_group",
                "data",
                {
                    "id": nsg,
                    "name": "nsg-data",
                    "resource_group_name": "rg-shop",
                    "location": "westeurope",
                    "security_rule": [rule],
                },
            ),
            resource(
                "azurerm_network_security_rule",
                "https",
                {
                    **rule,
                    "id": f"{nsg}/securityRules/https-in",
                    "resource_group_name": "rg-shop",
                    "network_security_group_name": "nsg-data",
                },
            ),
            resource(
                "azurerm_network_interface_security_group_association",
                "db",
                {
                    "id": f"{nic}|{nsg}",
                    "network_interface_id": nic,
                    "network_security_group_id": nsg,
                },
            ),
        ],
    }
    path = tmp_path / "terraform.tfstate"
    path.write_text(json.dumps(state), encoding="utf-8")
    estate = read_show_json(path)
    by = {found.address: found for found in estate.resources}
    assert by["azurerm_network_security_rule.https"].references["network_security_group_name"] == [
        "azurerm_network_security_group.data"
    ]
    drawing = draw(estate)
    assert [(w.source, w.target, w.label) for w in drawing.wires] == [
        ("internet", "azurerm_linux_virtual_machine.db", "HTTPS :443")
    ]
    assert drawing.folded["azurerm_network_security_rule.https"] == "drawn as the wires it allows"


def test_what_is_neither_a_plan_nor_a_state_is_refused(tmp_path):
    other = tmp_path / "other.json"
    other.write_text('{"hello": "world"}', encoding="utf-8")
    with pytest.raises(StateError, match="terraform show -json"):
        read_show_json(other)


# ---------------------------------------------------------------- the diagram file
def test_the_diagram_file_composes_and_the_picture_passes_the_checker(tmp_path):
    from infragram.cli.user.checker import checker
    from infragram.cli.user.compose import project_from_spec
    from infragram.exports import render_project_svg

    drawing = draw(read_configuration(SHOP))
    text = write_spec(
        drawing, command="import:terraform shop", date="2026-09-23", filename="shop.py"
    )
    assert "from infragram.nodes.frames import aws as aws_frames" in text
    assert re.search(r"with aws_frames\.VPC\('shop-prod · 10\.40\.0\.0/16'\)\.row\(\):", text)
    assert "internet >> Edge('HTTPS :443') >> alb" in text
    spec = tmp_path / "shop.py"
    spec.write_text(text, encoding="utf-8")
    project = project_from_spec(spec)
    assert tuple(project.provider_ids) == ("aws",)
    project.save(tmp_path / f"{project.slug}.infragram.json")
    svg = tmp_path / f"{project.slug}.svg"
    svg.write_text(render_project_svg(project), encoding="utf-8")
    ok, message = checker().check_path(svg)
    assert ok, message


@pytest.mark.parametrize(
    "folder", [RULES_AZURE, RULES_GCP, REGISTRY], ids=["azure", "gcp", "registry"]
)
def test_the_rules_draw_a_picture_the_checker_passes(folder, tmp_path):
    from infragram.cli.user.checker import checker
    from infragram.cli.user.compose import project_from_spec
    from infragram.exports import render_project_svg

    drawing = draw(read_configuration(folder))
    text = write_spec(
        drawing,
        command=f"import:terraform {folder.name}",
        date="2026-09-23",
        filename=f"{folder.name}.py",
    )
    assert re.search(r"internet >> Edge\('[^']*HTTPS :443[^']*'\) >> ", text)
    spec = tmp_path / f"{folder.name}.py"
    spec.write_text(text, encoding="utf-8")
    project = project_from_spec(spec)
    svg = tmp_path / f"{project.slug}.svg"
    svg.write_text(render_project_svg(project), encoding="utf-8")
    ok, message = checker().check_path(svg)
    assert ok, message


def test_the_report_says_where_every_resource_went():
    estate = read_configuration(SHOP)
    drawing = draw(estate)
    report = write_report(
        estate, drawing, command="import:terraform shop", date="2026-09-23", spec="shop.py"
    )
    assert f"| Resources read | {len(estate.resources)} |" in report
    for address in ("aws_instance.web[1]", "aws_iam_role.worker", "aws_lb_listener.https"):
        assert f"`{address}`" in report
    assert "cloudposse/label/null" in report


# ---------------------------------------------------------------- the command
def test_import_terraform_writes_the_file_and_report_and_exports(tmp_path, capsys):
    from infragram.cli.user.import_estate import import_terraform

    code = import_terraform(
        [str(SHOP), "--title", "Shop", "--formats", "template", "--output-dir", str(tmp_path)]
    )
    printed = capsys.readouterr()
    assert code == 0, printed.err
    assert (tmp_path / "shop.py").is_file() and (tmp_path / "shop.import.md").is_file()
    assert (tmp_path / "shop.infragram.json").is_file()
    assert re.search(
        r"^SPEC     .*shop\.py \(12 resources drawn, 4 wires\)$", printed.out, re.MULTILINE
    )
    # importing again replaces what the last import wrote; a hand edit is kept
    assert (
        import_terraform(
            [str(SHOP), "--title", "Shop", "--no-export", "--output-dir", str(tmp_path)]
        )
        == 0
    )
    capsys.readouterr()
    spec = tmp_path / "shop.py"
    spec.write_text(spec.read_text(encoding="utf-8") + "# mine\n", encoding="utf-8")
    assert (
        import_terraform(
            [str(SHOP), "--title", "Shop", "--no-export", "--output-dir", str(tmp_path)]
        )
        == 2
    )
    assert "refusing to overwrite" in capsys.readouterr().err
    # a plan called plan.json is titled after its folder, and the command the
    # diagram file records carries no absolute path, however it was given
    assert (
        import_terraform(
            [str((FIXTURES / "plan.json").resolve()), "--no-export", "--output-dir", str(tmp_path)]
        )
        == 0
    )
    written = (tmp_path / f"{FIXTURES.name}.py").read_text(encoding="utf-8")
    assert (
        f"import:terraform {(FIXTURES / 'plan.json').resolve().name}" in written
        or "import:terraform tests/fixtures/" in written
    )
    assert str(FIXTURES.resolve().parent.parent) not in written
    assert FIXTURES.resolve().as_posix() not in written


def test_import_terraform_refuses_what_it_cannot_read(tmp_path, capsys):
    from infragram.cli.user.import_estate import import_terraform

    assert import_terraform([str(tmp_path / "missing"), "--no-export"]) == 2
    (tmp_path / "only.tf").write_text('resource "random_pet" "x" {}\n', encoding="utf-8")
    assert (
        import_terraform([str(tmp_path), "--no-export", "--output-dir", str(tmp_path / "out")]) == 2
    )
    assert "nothing on AWS, Azure or Google Cloud" in capsys.readouterr().err


# ---------------------------------------------------------------- the round trip
@pytest.mark.parametrize(
    "slug", ["aws-three-tier-web", "azure-web-app-front-door", "gcp-three-tier-web"]
)
def test_a_diagrams_terraform_imported_draws_its_components(slug, tmp_path):
    """Export writes each component's resources; import reads them back. Every
    component the export wrote comes back as the same component."""
    from infragram.terraform import write_files

    project = CloudProject.load(TEMPLATES / f"{slug}.infragram.json")
    plan, files = terraform_files(project)
    write_files(files, tmp_path)
    drawing = draw(read_configuration(tmp_path))
    drawn = {card.service_id for card in _cards(drawing).values()}
    written = set()
    for element in project.topology.walk():
        component = element.component
        if component is None or component.provider not in PROVIDERS or element.is_frame:
            continue
        rule = load_mapping(component.provider).component(component.service_id)
        if (
            rule is not None
            and any(spec.key == "main" for spec in rule.resources)
            and element.name not in dict(plan.not_written)
        ):
            written.add(component.service_id)
    assert written and written <= drawn, sorted(written - drawn)


def _rule_wires(written, drawing, style: str = "resources") -> tuple[int, list[str]]:
    """How many wires the export wrote as rules, and those the drawing lost:
    each must be a wire again between the same two elements. In the modules
    style a rule from a subnet's range the diagram leaves to fill names the
    range by its value, which a configuration alone does not know, where the
    plain style names the subnet itself."""
    captions = {item.key: item.caption for item in drawing.walk()}
    pairs = {(captions[w.source], captions[w.target]) for w in drawing.wires}
    # a wire both ways is drawn once, from either end
    pairs |= {(captions[w.target], captions[w.source]) for w in drawing.wires if w.both}
    rules, lost = 0, []
    for wire in written.wires:
        if (
            not wire.written_as
            or wire.written_as.startswith("not written")
            or not re.search(r"(security group|firewall) rule", wire.written_as)
        ):
            continue
        if style == "modules" and "a value to fill" in wire.written_as:
            continue
        rules += 1
        # a card is captioned by the name the skeleton gives its element
        target = written.nouns[wire.target.id].replace("_", "-")
        source = (
            "Internet"
            if "from the internet" in wire.written_as
            else written.nouns[wire.source.id].replace("_", "-")
        )
        if not any(t.endswith(target) and (s == source or s.endswith(source)) for s, t in pairs):
            lost.append(f"{wire.source.name} -> {wire.target.name} ({wire.written_as})")
    return rules, lost


@pytest.mark.parametrize("style", ["resources", pytest.param("modules", marks=_MODULES)])
def test_every_wire_a_skeleton_writes_as_a_rule_comes_back_as_a_wire(style, tmp_path):
    """Every shipped template's skeleton, in both styles, imported: each wire
    the export wrote as a rule (a security group rule, an Azure network
    security rule, a Google Cloud firewall rule, or an entry of a registry
    module's rule map) is a wire again between the same two elements, an EFS
    file system's through the mount target that wears its group."""
    from infragram.terraform import TerraformError, write_terraform

    rules = 0
    missing: list[str] = []
    for path in sorted(TEMPLATES.glob("*.infragram.json")):
        project = CloudProject.load(path)
        try:
            written = write_terraform(project, tmp_path, overwrite=True, style=style)
        except TerraformError:
            continue
        drawing = draw(read_configuration(written.directory))
        found, lost = _rule_wires(written, drawing, style)
        rules += found
        missing += [f"{project.slug}: {wire}" for wire in lost]
    # Not vacuous: the templates' rules on AWS, the only cloud whose shipped
    # templates wire components that wear a boundary
    assert rules >= 15, rules
    assert not missing, "\n".join(missing)


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("style", ["resources", pytest.param("modules", marks=_MODULES)])
def test_every_component_the_tables_write_comes_back_through_the_import(provider, style, tmp_path):
    """The coverage diagram -- one of each component a table writes -- in
    both styles, imported: every component comes back as what the import
    draws its main resource type as (a PrivateLink endpoint is a VPC
    endpoint), through a registry module or not; nothing is a generic card;
    every wire written as a rule is a wire again."""
    from infragram.terraform import write_terraform
    from infragram.terraform.coverage import coverage_project

    project = coverage_project(provider)
    written = write_terraform(project, tmp_path, style=style)
    drawing = draw(read_configuration(written.directory))
    drawn = {card.service_id for card in _cards(drawing).values()}
    table, types = load_mapping(provider), type_table(provider)
    expected = set()
    for element in project.topology.walk():
        component = element.component
        if (
            component is None
            or component.provider != provider
            or element.name in dict(written.not_written)
        ):
            continue
        main = next(
            (
                spec
                for spec in table.components[component.service_id].resources
                if spec.key == "main"
            ),
            None,
        )
        # a type the import leaves out on purpose (an IAM role) is not drawn back
        if main is not None and main.type not in table.imports.not_drawn:
            role = types.role(main.type)
            expected.add(role.value if role.kind == "component" else component.service_id)
    assert expected and expected <= drawn, sorted(expected - drawn)
    assert types.fallback not in drawn and not drawing.unmapped
    rules, lost = _rule_wires(written, drawing)
    assert rules >= 2 and not lost, lost


def test_every_shipped_skeleton_imports_without_a_generic_card():
    """The import's tables cover every resource type the export writes."""
    from infragram.terraform import TerraformError

    for path in sorted(TEMPLATES.glob("*.infragram.json")):
        try:
            _, files = terraform_files(CloudProject.load(path))
        except TerraformError:
            continue
        types = set(
            re.findall(r'^resource "([a-z0-9_]+)"', "\n".join(files.values()), re.MULTILINE)
        )
        for resource_type in types:
            role = type_table(
                {"aws": "aws", "azurerm": "azure", "google": "gcp"}[resource_type.split("_")[0]]
            ).role(resource_type)
            assert role.kind != "unmapped", f"{path.name}: {resource_type}"


def test_the_import_command_is_listed(capsys):
    from infragram import cli

    with pytest.raises(SystemExit):
        cli.main(["--help"])
    listing = capsys.readouterr().out
    for command in ("import:terraform", "discover:aws", "discover:azure", "discover:gcp"):
        assert command in listing


def test_an_imported_file_says_how_to_draw_it(tmp_path: Path) -> None:
    from infragram.cli.user.import_estate import import_terraform

    plan = ROOT / "tests/fixtures/estate/plan-changes.json"
    assert import_terraform([str(plan), "--no-export", "--output-dir", str(tmp_path)]) == 0
    text = next(tmp_path.glob("*.py")).read_text(encoding="utf-8")
    assert "    infragram compose plan-changes.py" in text


SECURITY_GROUPS = FIXTURES / "terraform" / "security-groups"


def _configuration(tmp_path: Path) -> Path:
    folder = tmp_path / "tf"
    folder.mkdir()
    (folder / "main.tf").write_text(
        (SECURITY_GROUPS / "main.tf").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return folder


def test_each_ingress_block_of_a_configuration_draws_its_own_groups(tmp_path):
    drawing = draw(read_configuration(_configuration(tmp_path)))
    wires = {(w.source, w.target, w.label) for w in drawing.wires}
    for web in ("aws_instance.web[0]", "aws_instance.web[1]"):
        assert (web, "aws_db_instance.db", "PostgreSQL :5432") in wires
    # the second block names the load balancer's group, not the app's
    assert ("aws_lb.alb", "aws_db_instance.db", "SSH :22") in wires
    assert not any(
        w.label == "SSH :22" and w.source.startswith("aws_instance") for w in drawing.wires
    )
    assert not any(
        w.label == "PostgreSQL :5432" and w.source == "aws_lb.alb" for w in drawing.wires
    )
