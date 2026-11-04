"""The Terraform export: a diagram becomes a skeleton laid out as modules and environments.

Held here without the Terraform CLI (``verify:terraform --plan`` runs it on
every template and coverage diagram, in both styles):

- the tables: every placeholder is one the emitter fills, every ``$self`` and
  output names a resource of the same entry, every component is in its
  library, and every frame the library offers has a rule;
- the layout HashiCorp's standard module structure asks for: a module a
  concern under ``modules/`` (README, main, variables, outputs, versions),
  configuring no provider, and ``environments/dev`` and ``environments/prod``
  calling each once, each with its own backend and values;
- the style guide: names from the diagram, never repeating the resource
  type (``aws_subnet.public``, ``aws_security_group.web``); variables and
  outputs in alphabetical order, a variable's type first;
- apply-ready: a tier drawn in no zone frame is a subnet a zone across two,
  a server the card counts several of is an Auto Scaling group, and the
  instance class, Multi-AZ and a bucket's versions come from the card;
- every skeleton is whole: a module reads another only through the
  environment, every variable a module reads it declares and every one the
  environment must pass it does, every output the environment reads exists;
- the modules style calls the public registry's modules from each concern
  (the VPC module, a security group module a component, RDS, ALB, the Azure
  Verified Modules, Google's network module) and writes the wires as rules;
- the same document writes the same bytes; diagram text stays text; AWS
  descriptions are what AWS accepts; every README says what the code has.
"""

from __future__ import annotations

import importlib
import inspect
import re

import pytest

from infragram.catalog import load_provider_component_catalog
from infragram.exports import ExportError, export_project
from infragram.paths import plugin_root, repo_root
from infragram.projects import CloudProject
from infragram.terraform import (
    TerraformError,
    plan_terraform,
    render_plan,
    terraform_files,
    write_terraform,
)
from infragram.terraform.emit import PLACEHOLDERS
from infragram.terraform.mapping import PROVIDERS, load_mapping, load_modules

ROOT = repo_root()
TEMPLATES = ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "templates" / "cloud"
ENVIRONMENT_FILES = [
    "backend.tf",
    "locals.tf",
    "main.tf",
    "outputs.tf",
    "providers.tf",
    "terraform.tfvars.example",
    "variables.tf",
    "versions.tf",
]


def template(slug: str) -> CloudProject:
    return CloudProject.load(TEMPLATES / f"{slug}.infragram.json")


def three_tier() -> CloudProject:
    """The plugin's example: a VPC with public and private tiers, an ALB, three
    web servers, a Multi-AZ PostgreSQL, a versioned bucket."""
    from infragram.cli.user.compose import project_from_spec

    return project_from_spec(plugin_root() / "examples" / "aws_three_tier.py")


def example(name: str) -> CloudProject:
    """One of the plugin's examples: ``azure_three_tier``, ``gcp_three_tier``."""
    from infragram.cli.user.compose import project_from_spec

    return project_from_spec(plugin_root() / "examples" / f"{name}.py")


def _block(text: str, kind: str, *labels: str) -> str:
    """One top-level block of a file, as written."""
    head = f"{kind} " + " ".join(f'"{label}"' for label in labels) + " {"
    start = text.index(head)
    return text[start : text.index("\n}\n", start) + 2]


def _code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _variables(text: str) -> dict[str, str]:
    """variable name -> its block's body."""
    return dict(re.findall(r'^variable "([^"]+)" \{\n(.*?)^\}', text, re.MULTILINE | re.DOTALL))


def _outputs(text: str) -> list[str]:
    return re.findall(r'^output "([^"]+)"', text, re.MULTILINE)


#: A name cut to a length and not trimmed after: AWS and Google refuse a name
#: that ends on a hyphen, and the cut can leave one. A cut of letters and
#: digits alone (``replace(..., "/[^a-z0-9]/", "")``) has none to leave.
_UNTRIMMED_CUT = re.compile(r"(?<!trim\()substr\((?!lower\(replace\(|replace\()[^\n]*")


def _folders(files: dict[str, str]) -> list[str]:
    return sorted({name.rsplit("/", 1)[0] for name in files if name.startswith("modules/")})


# ---------------------------------------------------------------- the tables
def _placeholders(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _placeholders(item)
    elif isinstance(value, list):
        for item in value:
            yield from _placeholders(item)
    elif isinstance(value, str) and value.startswith("$"):
        yield value.removesuffix("?")[1:]


def _entries(provider: str):
    table = load_mapping(provider)
    yield from (("frame", kind, rule) for kind, rule in table.frames.items())
    yield from (("component", service_id, rule) for service_id, rule in table.components.items())


@pytest.mark.parametrize("provider", PROVIDERS)
def test_the_coverage_diagram_draws_every_component_its_table_writes(provider):
    """``verify:terraform`` and the import's round trip hold every row of a
    table to Terraform through this diagram, so it must draw them all."""
    from infragram.terraform.coverage import coverage_project

    project = coverage_project(provider)
    drawn = {
        element.component.service_id
        for element in project.topology.walk()
        if element.component is not None and element.component.provider == provider
    }
    assert drawn == set(load_mapping(provider).components), sorted(
        drawn ^ set(load_mapping(provider).components)
    )
    for style in ("resources", "modules"):
        assert terraform_files(project, style)[1]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_placeholder_is_one_the_emitter_fills(provider):
    problems = []
    for what, key, rule in _entries(provider):
        keys: list[str] = []
        for spec in rule.resources:
            # the registry module's arguments are filled the same way
            for token in [*_placeholders(spec.args), *_placeholders(spec.module_args or {})]:
                head, _, rest = token.partition(":")
                base, _, attribute = head.partition(".")
                if base not in PLACEHOLDERS:
                    problems.append(f"{what} {key}: ${token} is no placeholder")
                if base == "self" and attribute.partition(".")[0] not in keys:
                    problems.append(f"{what} {key}: ${token} names no resource written before it")
                if base == "name" and not re.fullmatch(
                    r"(lower|alnum|max)?(\d+)?(\+[a-z][a-z0-9-]*)?", rest
                ):
                    problems.append(f"{what} {key}: ${token} is no name transform")
            keys.append(spec.key)
            if spec.module is not None:
                assert spec.module in load_modules().modules, (what, key, spec.module)
        output = getattr(rule, "output", None)
        if output and (output.rpartition(".")[0] or "main") not in keys:
            problems.append(f"{what} {key}: its output {output} names no resource of it")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_component_is_in_its_library_and_every_frame_it_offers_has_a_rule(provider):
    table = load_mapping(provider)
    catalog = {
        component.service_id for component in load_provider_component_catalog(provider).components
    }
    assert sorted(set(table.components) - catalog) == []
    module = importlib.import_module(f"infragram.nodes.frames.{provider}")
    kinds = {
        cls.KIND
        for cls in vars(module).values()
        if inspect.isclass(cls)
        and cls.__module__ == module.__name__
        and isinstance(getattr(cls, "KIND", None), str)
    }
    assert sorted(kinds - set(table.frames)) == []


# ---------------------------------------------------------------- the layout
@pytest.mark.parametrize("style", ["resources", "modules"])
def test_a_skeleton_is_modules_a_concern_and_two_environments(style):
    """HashiCorp's standard module structure: every module a README, main,
    variables, outputs and versions, and no provider block; each environment
    the same composition with its own backend and values; nothing at the top
    but the README and .gitignore."""
    _plan, files = terraform_files(three_tier(), style)
    assert [name for name in files if "/" not in name] == [".gitignore", "README.md"]
    assert _folders(files) == [
        f"modules/{name}"
        for name in sorted(
            (
                "network",
                "security",
                "secrets",
                "compute",
                "database",
                "storage",
                "loadbalancer",
                "monitoring",
            )
        )
    ]
    for folder in _folders(files):
        assert {name.rsplit("/", 1)[1] for name in files if name.startswith(f"{folder}/")} == {
            "README.md",
            "main.tf",
            "outputs.tf",
            "variables.tf",
            "versions.tf",
        } - (set() if f"{folder}/outputs.tf" in files else {"outputs.tf"}), folder
        assert not re.search(
            r'^provider "',
            "".join(files[f"{folder}/{n}"] for n in ("main.tf", "versions.tf")),
            re.MULTILINE,
        ), folder
    for environment in ("dev", "prod"):
        assert (
            sorted(
                name.rsplit("/", 1)[1]
                for name in files
                if name.startswith(f"environments/{environment}/")
            )
            == ENVIRONMENT_FILES
        )
    main = files["environments/prod/main.tf"]
    calls = re.findall(
        r'^module "(\w+)" \{\n  source = "\.\./\.\./modules/(\w+)"', main, re.MULTILINE
    )
    assert calls == [
        (name, name)
        for name in (
            "network",
            "security",
            "secrets",
            "compute",
            "database",
            "storage",
            "loadbalancer",
            "monitoring",
        )
    ]
    # dev and prod are one composition: their own environment name and state key
    dev = {
        name.rsplit("/", 1)[1]: text
        for name, text in files.items()
        if name.startswith("environments/dev/")
    }
    prod = {
        name.rsplit("/", 1)[1]: text
        for name, text in files.items()
        if name.startswith("environments/prod/")
    }
    for name in ENVIRONMENT_FILES:
        assert dev[name].replace("dev", "prod") == prod[name].replace("dev", "prod"), name
    assert re.search(
        r'variable "environment" \{\n  type        = string\n.*\n  default     = "prod"',
        prod["variables.tf"],
    )
    assert "aws-three-tier-composed/prod/terraform.tfstate" in prod["backend.tf"]
    assert ".tfvars" in files[".gitignore"] and "!*.tfvars.example" in files[".gitignore"]


def test_the_names_are_the_diagrams_as_the_style_guide_asks():
    """Every block named after what the diagram calls it, never its type
    again: the VPC is ``main``, the tiers ``public`` and ``private``, a
    security group its component's; variables and outputs in alphabetical
    order, a variable's type first."""
    _plan, files = terraform_files(three_tier())
    code = "".join(text for name, text in files.items() if name.endswith(".tf"))
    addresses = set(re.findall(r'^resource "(\w+)" "(\w+)"', code, re.MULTILINE))
    assert {
        ("aws_vpc", "main"),
        ("aws_subnet", "public"),
        ("aws_subnet", "private"),
        ("aws_internet_gateway", "main"),
        ("aws_route_table", "public"),
        ("aws_security_group", "alb"),
        ("aws_security_group", "web"),
        ("aws_security_group", "postgresql"),
        ("aws_vpc_security_group_ingress_rule", "web_from_alb"),
        ("aws_vpc_security_group_ingress_rule", "alb_from_internet"),
        ("aws_lb", "main"),
        ("aws_lb_listener", "https"),
        ("aws_lb_target_group", "web"),
        ("aws_launch_template", "web"),
        ("aws_autoscaling_group", "web"),
        ("aws_db_instance", "postgresql"),
        ("aws_s3_bucket", "assets"),
        ("aws_cloudwatch_log_group", "main"),
    } <= addresses
    for kind, name in addresses:
        assert not re.search(r"\d+_\d+_\d+", name), (kind, name)
        assert not name.endswith(("_sg", "_subnets")), (kind, name)
    for name, text in files.items():
        if name.endswith("variables.tf"):
            names = list(_variables(text))
            assert names == sorted(names), name
            assert all(body.startswith("  type ") for body in _variables(text).values()), name
        if name.endswith("outputs.tf"):
            assert _outputs(text) == sorted(_outputs(text)), name
    assert set(_outputs(files["environments/prod/outputs.tf"])) >= {
        "alb_dns_name",
        "assets_bucket",
        "postgresql_address",
        "private_subnet_ids",
        "public_subnet_ids",
        "vpc_id",
    }


def test_the_skeleton_applies_as_the_card_says():
    """A tier in no zone frame is a subnet a zone across two, which the load
    balancer and the database subnet group need; three web servers are an
    Auto Scaling group behind the target group; the database's class and
    Multi-AZ are the card's; the bucket keeps its versions."""
    _plan, files = terraform_files(three_tier())
    network = files["modules/network/main.tf"]
    for tier in ("public", "private"):
        assert re.search(
            rf'resource "aws_subnet" "{tier}" \{{\n  count = length\(var\.azs\)\n\n'
            rf"  availability_zone += var\.azs\[count\.index\]\n"
            rf"  cidr_block += var\.{tier}_subnet_cidrs\[count\.index\]",
            network,
        ), tier
    variables = files["environments/prod/variables.tf"]
    assert '["10.0.0.0/24", "10.0.1.0/24"]' in _variables(variables)["public_subnet_cidrs"]
    assert '["10.0.2.0/24", "10.0.3.0/24"]' in _variables(variables)["private_subnet_cidrs"]
    assert re.search(
        r"azs\s+= slice\(data\.aws_availability_zones\.available\.names, 0, 2\)",
        files["environments/prod/locals.tf"],
    )
    assert "subnets            = var.public_subnet_ids" in files["modules/loadbalancer/main.tf"]
    assert "vpc_zone_identifier = var.private_subnet_ids" in files["modules/compute/main.tf"]
    assert (
        "autoscaling_group_name = var.web_autoscaling_group_name"
        in files["modules/loadbalancer/main.tf"]
    )
    defaults = {
        name: re.search(r"default\s+= (.+)", body).group(1)
        for name, body in _variables(variables).items()
        if "default" in body
    }
    assert (
        defaults["web_desired_capacity"] == "3" and defaults["web_instance_type"] == '"m6i.large"'
    )
    assert (
        defaults["postgresql_instance_class"] == '"db.r6g.large"'
        and defaults["postgresql_multi_az"] == "true"
    )
    assert re.search(
        r'resource "aws_s3_bucket_versioning" "assets" \{\n(?:.*\n)*?\s+status = "Enabled"',
        files["modules/storage/main.tf"],
    )
    # the dev environment's name is one letter shorter: "aws-three-tier-composed-dev-web-" is 32
    assert (
        'name     = trim(substr("${var.name}-web-8080", 0, 32), "-")'
        in files["modules/loadbalancer/main.tf"]
    )


@pytest.mark.parametrize("style", ["resources", "modules"])
def test_a_subnet_azure_reserves_for_a_service_is_named_as_azure_asks(style):
    """Azure Bastion deploys only into a subnet named AzureBastionSubnet, a
    firewall into AzureFirewallSubnet: the subnet holding one is named so
    whatever its caption says, a caption that says the name keeps it, and the
    block is named after what the subnet is for."""
    from infragram.author import Diagram
    from infragram.nodes.azure import networking as net
    from infragram.nodes.frames import azure

    with Diagram("Reserved subnets", slug="tf-reserved") as diagram:
        with azure.ResourceGroup("rg-hub"), azure.VNet("VNet 10.0.0.0/16"):
            with azure.Subnet("snet-admin 10.0.9.0/26"):
                net.Bastions("Bastion")
            with azure.Subnet("AzureFirewallSubnet 10.0.1.0/26"):
                net.Firewalls("Firewall")
    for project in (diagram.to_project(), example("azure_three_tier")):
        _plan, files = terraform_files(project, style)
        names = re.findall(r'^\s+name\s+= "(\w+)"', files["modules/network/main.tf"], re.MULTILINE)
        assert "AzureBastionSubnet" in names, (style, names)
    assert "AzureFirewallSubnet" in re.findall(
        r'^\s+name\s+= "(\w+)"',
        terraform_files(diagram.to_project(), style)[1]["modules/network/main.tf"],
        re.MULTILINE,
    )
    if style == "resources":
        assert (
            'resource "azurerm_subnet" "bastion"'
            in terraform_files(example("azure_three_tier"))[1]["modules/network/main.tf"]
        )


@pytest.mark.parametrize("style", ["resources", "modules"])
def test_a_database_on_a_private_ip_is_peered_before_it_is_made(style):
    """Cloud SQL on a private IP needs its network's private services
    connection first: one reserved range and one peering a network, the
    database reads its network through the peering so Terraform peers
    before it creates, the API is on, and "HA" on the card is REGIONAL."""
    _plan, files = terraform_files(example("gcp_three_tier"), style)
    network = files["modules/network/main.tf"]
    assert network.count('resource "google_service_networking_connection"') == 1
    assert re.search(
        r'resource "google_compute_global_address" "private_services" \{\n(?:.*\n)*?'
        r'  purpose\s+= "VPC_PEERING"\n  address_type\s+= "INTERNAL"\n  prefix_length = 16\n',
        network,
    )
    assert re.search(
        r'  service\s+= "servicenetworking.googleapis.com"\n'
        r"  reserved_peering_ranges = \[google_compute_global_address\.private_services\.name\]",
        network,
    )
    assert "private_network = var.private_services_network" in files["modules/database/main.tf"]
    assert re.search(
        r"private_services_network\s+= module\.network\.private_services_network",
        _block(files["environments/prod/main.tf"], "module", "database"),
    )
    assert (
        'resource "google_project_service" "servicenetworking"'
        in files["modules/foundation/main.tf"]
    )
    assert (
        '"REGIONAL"'
        in _variables(files["environments/prod/variables.tf"])["postgresql_availability_type"]
    )


@pytest.mark.parametrize("style", ["resources", "modules"])
def test_a_private_endpoint_connects_what_it_is_wired_to(style):
    """A private endpoint wired to a service connects to it: the service's
    resource (an SQL server, not its database), its subresource, and the
    private DNS zone it resolves in, written once and linked to the network;
    one endpoint a service, named after it; with no wire, what it connects is
    a variable to fill, as before."""
    from infragram.author import Diagram
    from infragram.nodes.azure import other
    from infragram.nodes.frames import azure

    _plan, files = terraform_files(example("azure_three_tier"), style)
    network = files["modules/network/main.tf"]
    assert re.search(
        r'resource "azurerm_private_dns_zone" "database" \{\n  name\s+= "privatelink\.database\.windows\.net"',
        network,
    )
    assert "virtual_network_id    = " in _block(
        network, "resource", "azurerm_private_dns_zone_virtual_network_link", "database"
    )
    assert "subresource_names" in network and '["sqlServer"]' in network
    assert "[azurerm_private_dns_zone.database.id]" in network
    assert re.search(r"private_connection_resource_id\s+= var\.mssql_database_\w+", network)
    env = _block(files["environments/prod/main.tf"], "module", "network")
    assert re.search(r"mssql_database_\w+\s+= module\.database\.mssql_database_\w+", env)
    fill = files["environments/prod/terraform.tfvars.example"]
    assert "target_resource_id" not in fill and "subresource_names" not in fill
    # the Front Door template reaches four services from one endpoint element: four endpoints
    code = "".join(
        text
        for name, text in terraform_files(template("azure-web-app-front-door"), style)[1].items()
        if name.endswith(".tf")
    )
    assert sorted(re.findall(r"subresource_names\s+= \[\"(\w+)\"\]", code)) == [
        "blob",
        "redisCache",
        "sqlServer",
        "vault",
    ]
    assert len(set(re.findall(r'"\$\{var\.name\}-private-endpoints?-([\w-]+)"', code))) == 4
    if style == "modules":
        assert {"mssql_database_private_endpoint", "redis_cache_private_endpoint"} <= set(
            re.findall(r'^module "(\w+)"', code, re.MULTILINE)
        )
    # an endpoint wired to nothing still says what to fill
    with Diagram("Unwired endpoint", slug="tf-unwired") as diagram:
        with (
            azure.ResourceGroup("rg-app"),
            azure.VNet("VNet 10.0.0.0/16"),
            azure.Subnet("snet-pe 10.0.1.0/24"),
        ):
            other.PrivateEndpoints("Private endpoint")
    plan, files = terraform_files(diagram.to_project(), style)
    assert (
        "private_endpoint_target_resource_id" in files["environments/prod/terraform.tfvars.example"]
    )
    assert any("a wire from it" in note for note in plan.notes)


@pytest.mark.parametrize("style", ["resources", "modules"])
def test_an_application_gateway_serves_what_its_card_and_wires_say(style):
    """An Application Gateway listens on HTTPS 443 when a wire into it says
    HTTPS (its certificate from Key Vault, a value to fill), forwards on the
    port of the wire out of it, and is WAF_v2 with its own OWASP policy when
    the card says WAF; the scale set it is wired to sits in its backend pool
    and wears a network security group whose rules are the wires into it.
    Said nothing of the kind, it listens on HTTP 80 as Standard_v2."""
    from infragram.author import Diagram, Edge
    from infragram.nodes import infragram as shared
    from infragram.nodes.azure import compute, networking as net
    from infragram.nodes.frames import azure

    _plan, files = terraform_files(example("azure_three_tier"), style)
    balancer = files["modules/loadbalancer/main.tf"]
    gateway = _block(balancer, "resource", "azurerm_application_gateway", "main")
    assert re.search(r'sku \{\n\s+name\s+= "WAF_v2"\n\s+tier\s+= "WAF_v2"', gateway)
    assert re.search(
        r"firewall_policy_id\s+= azurerm_web_application_firewall_policy\.application_gateway\.id",
        gateway,
    )
    assert re.search(r'managed_rule_set \{\n\s+type\s+= "OWASP"\n\s+version = "3\.2"', balancer)
    assert re.search(r'frontend_port \{\n\s+name = "https"\n\s+port = 443', gateway)
    assert re.search(r"backend_http_settings \{\n(?:.*\n)*?\s+port\s+= 8080\n", gateway)
    assert re.search(r'ssl_certificate_name\s+= "tls"', gateway) and "identity {" in gateway
    compute_code = files["modules/compute/main.tf"]
    assert '["${var.application_gateway_id}/backendAddressPools/backend"]' in compute_code
    assert re.search(
        r"network_security_group_id = (module|azurerm_network_security_group)\.", compute_code
    )
    ports = re.findall(r'destination_port_range\s+= "(\d+)"', files["modules/security/main.tf"])
    assert sorted(ports) == ["22", "8080"], ports
    assert (
        "application_gateway_certificate_secret_id"
        in files["environments/prod/terraform.tfvars.example"]
    )
    # a subnet's ranges cross modules as the list they are, or validate refuses the rule
    for name, body in _variables(files["modules/security/variables.tf"]).items():
        if name.endswith("address_prefixes"):
            assert body.startswith("  type        = list(string)"), (name, body)

    with Diagram("Plain gateway", slug="tf-plain-gateway") as diagram:
        users = shared.identity.PublicUsers("Users")
        with azure.ResourceGroup("rg-web"), azure.VNet("VNet 10.0.0.0/16"):
            with azure.Subnet("snet-gateway 10.0.1.0/24"):
                gateway_node = net.ApplicationGateways("Gateway")
            with azure.Subnet("snet-app 10.0.2.0/24"):
                servers = compute.VMScaleSets("Servers")
        users >> Edge("HTTP") >> gateway_node
        gateway_node >> Edge("HTTP") >> servers
    plain = _block(
        terraform_files(diagram.to_project(), style)[1]["modules/loadbalancer/main.tf"],
        "resource",
        "azurerm_application_gateway",
        "main",
    )
    assert '"Standard_v2"' in plain and "firewall_policy_id" not in plain
    assert re.search(r'frontend_port \{\n\s+name = "http"\n\s+port = 80', plain)
    assert "ssl_certificate" not in plain and "identity {" not in plain


@pytest.mark.parametrize("style", ["resources", "modules"])
def test_a_google_load_balancer_reaches_the_backends_it_is_wired_to(style):
    """Three web servers are a managed instance group from an instance
    template, its named port the wire's; the load balancer wired to them is
    a health check and backend service each (Cloud Armor's policy on it when
    Armor is wired to the balancer, Cloud CDN switched on when CDN is), a URL
    map, an HTTPS proxy with a Google-managed certificate when a wire reaches
    it on 443, and the forwarding rule on its address; a firewall rule lets
    Google's front ends reach the servers' port. A Cloud Run backend is a
    serverless network endpoint group."""
    _plan, files = terraform_files(example("gcp_three_tier"), style)
    compute_code = files["modules/compute/main.tf"]
    assert 'resource "google_compute_instance_template" "web"' in compute_code
    group = _block(compute_code, "resource", "google_compute_region_instance_group_manager", "web")
    assert "instance_template = google_compute_instance_template.web.self_link_unique" in group
    assert re.search(r'named_port \{\n\s+name = "http"\n\s+port = 8080', group)
    assert (
        "default     = 3" in _variables(files["environments/prod/variables.tf"])["web_target_size"]
    )
    edge = files["modules/edge/main.tf"]
    assert re.search(r"http_health_check \{\n\s+port = 8080", edge)
    service = _block(edge, "resource", "google_compute_backend_service", "web")
    assert re.search(r"security_policy\s+= var\.armor_\w+", service)
    assert (
        "group = var.web_instance_group" in service and 'port_name             = "http"' in service
    )
    assert 'resource "google_compute_managed_ssl_certificate" "main"' in edge
    assert "ssl_certificates = [google_compute_managed_ssl_certificate.main.id]" in edge
    rule = _block(edge, "resource", "google_compute_global_forwarding_rule", "https")
    assert (
        'port_range            = "443"' in rule
        and "target                = google_compute_target_https_proxy.main.id" in rule
    )
    firewall = "".join(text for name, text in files.items() if name.endswith(".tf"))
    assert re.search(r'"35\.191\.0\.0/16", "130\.211\.0\.0/22"', firewall)
    assert "lb_domains" in files["environments/prod/terraform.tfvars.example"]

    code = "".join(
        text
        for name, text in terraform_files(template("gcp-three-tier-web"), style)[1].items()
        if name.endswith(".tf")
    )
    assert 'network_endpoint_type = "SERVERLESS"' in code and "enable_cdn            = true" in code
    # a bucket keeps its versions, as an S3 bucket does
    storage = files["modules/storage/main.tf"]
    pattern = (
        r"versioning \{\n\s+enabled = true" if style == "resources" else r"versioning\s+= true"
    )
    assert re.search(pattern, storage)


@pytest.mark.parametrize("style", ["resources", "modules"])
def test_aws_waf_is_a_web_acl_of_managed_rules_on_what_it_is_wired_to(style):
    """AWS WAF is a regional web ACL of AWS's managed rule groups, allowing
    what they pass, associated with the load balancer its wire points at."""
    plan, files = terraform_files(three_tier(), style)
    security = files["modules/security/main.tf"]
    acl = _block(security, "resource", "aws_wafv2_web_acl", "main")
    assert re.search(r'scope\s+= "REGIONAL"', acl)
    assert re.findall(r'name\s+= "(AWSManagedRules\w+)"', acl) == [
        "AWSManagedRulesCommonRuleSet",
        "AWSManagedRulesKnownBadInputsRuleSet",
    ]
    association = _block(security, "resource", "aws_wafv2_web_acl_association", "alb")
    assert (
        re.search(r"resource_arn = var\.alb_\w*arn", association)
        and "aws_wafv2_web_acl.main.arn" in association
    )
    assert any(w.written_as == "the web ACL's association with it" for w in plan.wires)
    assert not [name for name, _why in plan.not_written if name == "AWS WAF"]


@pytest.mark.parametrize("style", ["resources", "modules"])
def test_a_github_workflow_signs_in_with_oidc_and_reaches_only_what_it_is_wired_to(style):
    """A GitHub workflow wired to a cloud identity signs in to it with its
    OIDC token, no secret: the trust names the diagram's repository and the
    approval gate's environment, and the identity may do what its wires
    reach and no more (an AWS policy on those ARNs, Azure roles on those
    resources, Google roles for the pool's service account)."""
    subject = "repo:${var.github_repository}:environment:${var.github_environment}"

    _plan, files = terraform_files(example("aws_github_actions_oidc"), style)
    security = files["modules/security/main.tf"]
    assert 'url            = "https://token.actions.githubusercontent.com"' in security
    trust = _block(security, "data", "aws_iam_policy_document", "deploy_trust")
    assert '"sts:AssumeRoleWithWebIdentity"' in trust and f'values   = ["{subject}"]' in trust
    assert "assume_role_policy   = data.aws_iam_policy_document.deploy_trust.json" in security
    access = _block(security, "data", "aws_iam_policy_document", "deploy_access")
    assert (
        '"ecr:PutImage"' in access
        and '"ecs:UpdateService"' in access
        and '"s3:PutObject"' in access
    )
    assert '/*"]' in access  # the bucket's objects, not every bucket
    variables = _variables(files["environments/prod/variables.tf"])
    assert (
        '"acme/web-app"' in variables["github_repository"]
        and '"production"' in variables["github_environment"]
    )

    _plan, files = terraform_files(example("azure_github_actions_oidc"), style)
    security = files["modules/security/main.tf"]
    credential = _block(security, "resource", "azurerm_federated_identity_credential", "deploy")
    assert f'subject                   = "{subject}"' in credential
    assert 'audience                  = ["api://AzureADTokenExchange"]' in credential
    assert sorted(re.findall(r'role_definition_name = "([^"]+)"', security)) == [
        "AcrPush",
        "Storage Blob Data Contributor",
        "Website Contributor",
    ]
    assert 'output "azure_tenant_id"' in files["environments/prod/outputs.tf"]

    _plan, files = terraform_files(example("gcp_github_actions_oidc"), style)
    security = files["modules/security/main.tf"]
    assert (
        "assertion.repository == '${var.github_repository}' && assertion.environment == "
        "'${var.github_environment}'" in security
    )
    assert (
        '"principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.main.name}'
        '/attribute.repository/${var.github_repository}"' in security
    )
    assert sorted(re.findall(r'role    = "(roles/[^"]+)"', security)) == [
        "roles/artifactregistry.writer",
        "roles/iam.serviceAccountUser",
        "roles/run.developer",
        "roles/storage.objectAdmin",
    ]
    assert (
        'resource "google_project_service" "iamcredentials"' in files["modules/foundation/main.tf"]
    )


@pytest.mark.parametrize("style", ["resources", "modules"])
def test_a_workflow_signs_in_to_entra_id_as_an_app_registrations_service_principal(style):
    """The Entra ID way: the app registration carries the federated
    credential GitHub's token is checked against, its service principal
    (the Enterprise application wired from it) holds the roles, and azuread
    is declared only where its resources are written."""
    subject = "repo:${var.github_repository}:environment:${var.github_environment}"
    _plan, files = terraform_files(example("entra_github_actions_oidc"), style)
    security = files["modules/security/main.tf"]
    credential = _block(
        security, "resource", "azuread_application_federated_identity_credential", "registration"
    )
    assert "application_id = azuread_application.registration.id" in credential
    assert f'subject        = "{subject}"' in credential
    assert 'audiences      = ["api://AzureADTokenExchange"]' in credential
    principal = _block(security, "resource", "azuread_service_principal", "main")
    assert "client_id = azuread_application.registration.client_id" in principal
    assert sorted(re.findall(r'role_definition_name = "([^"]+)"', security)) == [
        "AcrPush",
        "Storage Blob Data Contributor",
        "Website Contributor",
    ]
    assert set(re.findall(r"principal_id\s+= (\S+)", security)) == {
        "azuread_service_principal.main.object_id"
    }
    assert 'source  = "hashicorp/azuread"' in files["modules/security/versions.tf"]
    assert "azuread" not in files["modules/compute/versions.tf"]
    assert 'provider "azuread" {}' in files["environments/prod/providers.tf"]
    # what azure/login asks for: the client id is an output, and so is the tenant's id
    outputs = files["environments/prod/outputs.tf"]
    assert 'output "registration_client_id"' in outputs and 'output "azure_tenant_id"' in outputs
    assert "value       = data.azurerm_client_config.current.tenant_id" in outputs
    assert 'data "azurerm_client_config" "current" {}' in files["environments/prod/main.tf"]
    # only the app registration's wire is its service principal; the admin's and
    # Entra ID's wires to it are the story
    readme = files["README.md"]
    assert (
        "| App registration | Service principal | service principal | its service principal"
        in readme
    )
    assert (
        "| Platform admin | Service principal | assigns roles | not written: the service principal's roles"
        in readme
    )


def test_an_app_registration_holds_no_roles_and_a_lone_service_principal_is_not_written():
    """Roles go to a service principal: wired from the app registration itself
    they are not written, and a service principal wired from no app
    registration has no client id to name."""
    from infragram.author import Diagram, Edge
    from infragram.nodes.azure import containers, identity as entra
    from infragram.nodes.frames import azure

    with Diagram("Entra roles", slug="tf-entra-roles") as diagram:
        with azure.Tenant("Tenant"):
            app = entra.AppRegistrations("Deploy app")
            entra.EnterpriseApplications("Lone principal")
            with azure.Subscription("Sub"), azure.Region("East US 2"), azure.ResourceGroup("rg"):
                registry = containers.ContainerRegistries("Registry")
        app >> Edge("AcrPush") >> registry
    plan, files = terraform_files(diagram.to_project())
    code = "".join(text for name, text in files.items() if name.endswith(".tf"))
    assert "azurerm_role_assignment" not in code and "azuread_service_principal" not in code
    reasons = dict(plan.not_written)
    assert "wired to no app-registrations" in reasons["Lone principal"]
    assert 'resource "azuread_application"' in code


def test_an_identity_no_workflow_signs_in_to_keeps_its_own_trust():
    """An IAM role nothing from GitHub is wired to is a role whose trust is a
    value to fill; the GitHub provider is not written."""
    from infragram.author import Diagram
    from infragram.nodes.aws import security_identity as security
    from infragram.nodes.frames import aws

    with Diagram("Plain role", slug="tf-plain-role") as diagram:
        with aws.Cloud("AWS Cloud"), aws.Region("us-east-1"):
            security.IdentityAccessManagementRole("Batch role")
    _plan, files = terraform_files(diagram.to_project())
    code = "".join(text for name, text in files.items() if name.endswith(".tf"))
    assert "aws_iam_openid_connect_provider" not in code
    assert "batch_assume_role_policy" in files["environments/prod/terraform.tfvars.example"]


# ---------------------------------------------------------------- every template
@pytest.mark.parametrize("style", ["resources", "modules"])
def test_every_skeleton_is_whole(style):
    """What ``terraform validate`` would catch first, read without it: a
    module reads another only through its variables, declares each variable
    it reads and reads each it declares; the environment passes a module
    exactly its variables and reads only outputs it has; every value to fill
    is listed."""
    problems: list[str] = []
    written = calls = reads = 0
    for path in sorted(TEMPLATES.glob("*.infragram.json")):
        project = CloudProject.load(path)
        try:
            plan, files = terraform_files(project, style)
        except TerraformError:
            continue
        written += 1
        slug = project.slug
        folders = _folders(files)
        defined = {}
        for folder in folders:
            code = _code(files[f"{folder}/main.tf"])
            for kind, name in re.findall(r'^resource "(\w+)" "(\w+)"', code, re.MULTILINE):
                defined[f"{kind}.{name}"] = folder
            for name in re.findall(r'^module "(\w+)"', code, re.MULTILINE):
                defined[f"module.{name}"] = folder
        for folder in folders:
            code = "\n".join(
                _code(files[f"{folder}/{name}"])
                for name in ("main.tf", "outputs.tf")
                if f"{folder}/{name}" in files
            )
            declared = set(_variables(files[f"{folder}/variables.tf"]))
            used = set(re.findall(r"\bvar\.(\w+)", code))
            reads += len(used)
            problems += [f"{slug} {folder}: var.{name} is not declared" for name in used - declared]
            problems += [
                f"{slug} {folder}: var.{name} is declared and never read"
                for name in declared - used
            ]
            problems += [
                f"{slug} {folder}: reads {address} of {owner}"
                for address, owner in defined.items()
                if owner != folder and re.search(rf"(?<![\w.]){re.escape(address)}\b", code)
            ]
            assert "local." not in code, (slug, folder)
        env = files["environments/prod/main.tf"]
        for name, source, body in re.findall(
            r'^module "(\w+)" \{\n  source = "\.\./\.\./(modules/[\w/]+)"\n(.*?)^\}',
            env,
            re.MULTILINE | re.DOTALL,
        ):
            calls += 1
            wanted = set(_variables(files[f"{source}/variables.tf"]))
            passed = set(re.findall(r"^  (\w+)\s+=", body, re.MULTILINE)) - {
                "providers",
                "depends_on",
            }
            problems += [
                f"{slug} {name}: {arg} is passed and no variable of it" for arg in passed - wanted
            ]
            problems += [f"{slug} {name}: {arg} is not passed" for arg in wanted - passed]
            reads_of = body + files.get("environments/prod/outputs.tf", "")
            for called, output in re.findall(r"module\.(\w+)\.(\w+)", reads_of):
                target = re.search(
                    rf'^module "{called}" \{{\n  source = "\.\./\.\./(modules/[\w/]+)"',
                    env,
                    re.MULTILINE,
                )
                assert target is not None, (slug, called)
                if output not in _outputs(files.get(f"{target.group(1)}/outputs.tf", "")):
                    problems.append(f"{slug}: module.{called}.{output} is no output of it")
        declared = set(_variables(files["environments/prod/variables.tf"]))
        used = set(
            re.findall(
                r"\bvar\.(\w+)",
                "".join(
                    _code(files[f"environments/prod/{name}"])
                    for name in ("main.tf", "locals.tf", "providers.tf")
                ),
            )
        )
        problems += [f"{slug} prod: var.{name} is not declared" for name in used - declared]
        problems += [
            f"{slug} prod: var.{name} is declared and never read" for name in declared - used
        ]
        for variable in plan.root.variables.values():
            if (
                variable.todo
                and variable.name in declared
                and f"\n{variable.name} = "
                not in files["environments/prod/terraform.tfvars.example"]
            ):
                problems.append(f"{slug}: {variable.name} is not in terraform.tfvars.example")
        for name, text in files.items():
            if not text.endswith("\n") or "\r" in text:
                problems.append(f"{slug} {name}: not LF-terminated text")
            problems += [
                f"{slug} {name}: a name cut to a length can end on a hyphen: {cut.group(0)}"
                for cut in _UNTRIMMED_CUT.finditer(text)
            ]
    assert (written, calls > 60, reads > 300) == (15, True, True), (written, calls, reads)
    assert not problems, "\n".join(problems)


def test_the_same_document_writes_the_same_bytes():
    project = template("azure-hub-spoke-landing-zone")
    for style in ("resources", "modules"):
        assert render_plan(plan_terraform(project, style)) == render_plan(
            plan_terraform(project, style)
        )


def test_a_gateway_the_diagram_draws_is_the_one_its_public_subnets_use():
    _, files = terraform_files(template("rstudio-shiny-analytics-platform"))
    text = "\n".join(text for name, text in files.items() if name.endswith(".tf"))
    assert text.count('resource "aws_internet_gateway"') == 1
    assert "the diagram draws none" not in text


def test_the_google_skeleton_turns_on_the_apis_its_resources_need_first():
    for style in ("resources", "modules"):
        _, files = terraform_files(template("gcp-three-tier-web"), style)
        assert 'resource "google_project_service" "compute"' in files["modules/foundation/main.tf"]
        main = files["environments/prod/main.tf"]
        for call in re.findall(r'^module "(\w+)"', main, re.MULTILINE):
            if call != "foundation":
                assert "depends_on = [module.foundation]" in _block(main, "module", call), (
                    style,
                    call,
                )


# ---------------------------------------------------------------- diagram text
def _diagram(caption: str, label: str) -> CloudProject:
    from infragram.author import Diagram, Edge
    from infragram.nodes import infragram as shared
    from infragram.nodes.aws import compute, networking_content_delivery as net
    from infragram.nodes.frames import aws

    with Diagram(
        "Text stays text", "a caption that looks like a template", slug="tf-text"
    ) as diagram:
        users = shared.identity.PublicUsers("Users")
        with aws.Cloud("AWS Cloud"), aws.Region("us-east-1"), aws.VPC("VPC 10.0.0.0/16"):
            with aws.PublicSubnet("Public 10.0.0.0/24"):
                balancer = net.ElasticLoadBalancing("Balancer ${x}")
            with aws.PrivateSubnet("Private 10.0.1.0/24"):
                web = compute.EC2(caption)
        users >> Edge(label) >> balancer
        balancer >> Edge("HTTP") >> web
    return diagram.to_project()


def test_diagram_text_stays_text_and_aws_descriptions_are_what_aws_accepts():
    _, files = terraform_files(_diagram("Wéb · tier ${x}", "HTTPS · public"))
    code = {name: _code(text) for name, text in files.items() if name.endswith(".tf")}
    for name, text in code.items():
        assert not re.search(r"(?<!\$)\$\{x\}", text), f"{name} interpolates diagram text"
    assert any("$${x}" in text for text in code.values())
    descriptions = re.findall(r'description\s+= "([^"]*)"', code["modules/security/main.tf"])
    assert "HTTPS / public" in descriptions
    assert "Web / tier $${x}" in descriptions
    assert all(description.isascii() for description in descriptions)


# ---------------------------------------------------------------- the export
def test_the_export_writes_the_folder_beside_the_pictures(tmp_path):
    project = template("aws-three-tier-web")
    result = export_project(project, tmp_path, formats=("terraform",))
    assert result.terraform == tmp_path / "aws-three-tier-web-terraform"
    assert (result.terraform / "modules" / "network" / "main.tf").is_file()
    assert (result.terraform / "environments" / "prod" / "main.tf").is_file()
    assert result.html is None and result.svg is None
    assert any("variables to fill" in note for note in result.notes)
    # Untouched since it was written, the folder is simply replaced; a file
    # added to it is an edit, and an edit needs --force.
    export_project(project, tmp_path, formats=("terraform",))
    (result.terraform / "stale.tf").write_text("", encoding="utf-8")
    with pytest.raises(ExportError, match="--force"):
        export_project(project, tmp_path, formats=("terraform",))
    export_project(project, tmp_path, formats=("terraform",), overwrite=True)
    assert not (result.terraform / "stale.tf").exists()
    assert [path.name for path in tmp_path.iterdir()] == ["aws-three-tier-web-terraform"]


def test_a_diagram_with_nothing_to_write_is_refused_before_anything_is_written(tmp_path):
    with pytest.raises(TerraformError, match="draws nothing on AWS, Azure or Google Cloud"):
        export_project(template("campus-lan-wan"), tmp_path, formats=("svg", "terraform"))
    assert list(tmp_path.iterdir()) == []


def test_write_terraform_refuses_a_folder_that_exists_unless_asked(tmp_path):
    project = template("gcp-three-tier-web")
    first = write_terraform(project, tmp_path)
    assert first.directory.name == "gcp-three-tier-web-terraform"
    assert first.directory / "README.md" in first.files
    with pytest.raises(TerraformError, match="exists"):
        write_terraform(project, tmp_path)
    again = write_terraform(project, tmp_path, overwrite=True)
    assert [path.name for path in tmp_path.iterdir()] == ["gcp-three-tier-web-terraform"]
    assert [variable.name for variable in again.todos] == [
        variable.name for variable in first.todos
    ]


def test_export_project_prints_the_folder(tmp_path, capsys):
    from infragram.cli.user.export_project import main

    code = main(
        [
            str(TEMPLATES / "aws-three-tier-web.infragram.json"),
            "--formats",
            "terraform",
            "--output-dir",
            str(tmp_path),
        ]
    )
    printed = capsys.readouterr()
    assert code == 0
    found = re.search(
        r"^TERRAFORM .*aws-three-tier-web-terraform \((\d+) files\)$", printed.out, re.MULTILINE
    )
    assert found and int(found.group(1)) == sum(
        1 for p in (tmp_path / "aws-three-tier-web-terraform").rglob("*") if p.is_file()
    )
    assert "variables to fill" in printed.err


def test_the_export_writes_the_modules_folder_beside_the_other(tmp_path):
    result = export_project(
        template("aws-three-tier-web"), tmp_path, formats=("terraform", "terraform-modules")
    )
    assert result.terraform == tmp_path / "aws-three-tier-web-terraform"
    assert result.terraform_modules == tmp_path / "aws-three-tier-web-terraform-modules"
    assert (result.terraform_modules / "modules" / "network" / "main.tf").is_file()
    assert any(note.startswith("aws-three-tier-web-terraform-modules:") for note in result.notes)


# ---------------------------------------------------------------- the modules style
def _imported(folder: str) -> CloudProject:
    """A diagram of one of the import's rule fixtures."""
    import tempfile
    from pathlib import Path

    from infragram.cli.user.compose import project_from_spec
    from infragram.estate import draw, write_spec
    from infragram.terraform.readconfig import read_configuration

    source = ROOT / "tests" / "fixtures" / "estate" / "terraform" / folder
    spec = Path(tempfile.mkdtemp()) / f"{folder}.py"
    spec.write_text(
        write_spec(
            draw(read_configuration(source)), command="t", date="2026-09-23", filename=spec.name
        ),
        encoding="utf-8",
    )
    return project_from_spec(spec)


def test_the_modules_style_calls_the_registrys_modules_from_each_concern():
    """Each concern's module calls the public registry's module for what it
    holds, pinned, one call an element -- no map repeated with ``for_each``;
    the wires are ingress rules beside the security group modules; the RDS
    module writes its subnet group; the listener reads the ALB module."""
    pinned = load_modules().modules
    plan, files = terraform_files(three_tier(), "modules")
    assert plan.style == "modules"
    code = "".join(text for name, text in files.items() if name.endswith(".tf"))
    assert "for_each = var." not in code
    for folder, label, key in (
        ("network", "vpc", "aws-vpc"),
        ("security", "web_sg", "aws-security-group"),
        ("compute", "web", "aws-autoscaling"),
        ("database", "postgresql", "aws-rds"),
        ("loadbalancer", "alb", "aws-alb"),
        ("storage", "assets", "aws-s3-bucket"),
    ):
        block = _block(files[f"modules/{folder}/main.tf"], "module", label)
        assert (
            f'source  = "{pinned[key].source}"' in block
            and f'version = "{pinned[key].version}"' in block
        ), label
    assert "aws_db_subnet_group" not in code and "aws_launch_template" not in code
    network = _block(files["modules/network/main.tf"], "module", "vpc")
    assert (
        "public_subnets  = var.public_subnet_cidrs" in network
        and "azs             = var.azs" in network
    )
    security = files["modules/security/main.tf"]
    assert re.search(
        r'resource "aws_vpc_security_group_ingress_rule" "web_from_alb" \{\n'
        r"  security_group_id += module\.web_sg\.id",
        security,
    )
    assert "referenced_security_group_id = module.alb_sg.id" in security
    assert "enable_exclusive_rules = false" in security
    assert "load_balancer_arn = module.alb.arn" in files["modules/loadbalancer/main.tf"]
    assert "versioning = {\n    enabled = true\n  }" in files["modules/storage/main.tf"]
    readme = files["README.md"]
    assert f"| {pinned['aws-rds'].version} |" in readme and "## Architecture" in readme


def test_the_modules_style_writes_azure_and_google_networks_through_the_registrys_modules():
    pinned = load_modules().modules
    _plan, files = terraform_files(_imported("rules-azure"), "modules")
    network = files["modules/network/main.tf"]
    assert f'source  = "{pinned["azure-virtual-network"].source}"' in network
    assert "enable_telemetry = false" in network
    compute = files["modules/compute/main.tf"]
    assert f'source  = "{pinned["azure-network-security-group"].source}"' in compute
    # a wire to a machine is a rule on its group, the machine's resource group its own
    security = files["modules/security/main.tf"]
    rule = security[security.index('resource "azurerm_network_security_rule"') :]
    rule = rule[: rule.index("\n}\n")]
    assert re.search(r"network_security_group_name += var\.\w+_nsg_name", rule), rule
    _plan, files = terraform_files(_imported("rules-gcp"), "modules")
    network = files["modules/network/main.tf"]
    assert f'source  = "{pinned["gcp-network"].source}"' in network
    assert "ingress_rules = [" in network and 'target_tags = ["db"]' in network
    assert "google_compute_firewall" not in "".join(files.values())


def test_a_sensitive_endpoint_is_a_sensitive_output_in_both_styles():
    """Application Insights' connection string is sensitive to the provider:
    an output that gives it unmarked fails the plan, the module's and the
    environment's."""
    from infragram.terraform.coverage import coverage_project

    for style in ("resources", "modules"):
        _plan, files = terraform_files(coverage_project("azure"), style)
        for path in ("environments/prod/outputs.tf", "modules/monitoring/outputs.tf"):
            assert re.search(
                r'output "\w*connection_string" \{\n(?:.*\n)*?\s+sensitive\s+= true', files[path]
            ), (style, path)


def test_a_clouds_second_provider_is_configured_as_its_own_is():
    """google-beta and azapi, which the registry modules call beside google
    and azurerm, are configured in each environment as those are (the
    project and region; the subscription), required by the modules that call
    them, and handed to a module with the cloud's own."""
    from infragram.terraform.coverage import coverage_project

    _plan, files = terraform_files(coverage_project("gcp"), "modules")
    providers = files["environments/prod/providers.tf"]
    assert re.search(
        r'provider "google-beta" \{\n\s+project = var\.gcp_project_id\n\s+region\s+= var\.gcp_region',
        providers,
    )
    assert '"hashicorp/google-beta"' in files["environments/prod/versions.tf"]
    assert '"hashicorp/google-beta"' in files["modules/network/versions.tf"]
    _plan, files = terraform_files(template("azure-hub-spoke-landing-zone"), "modules")
    assert re.search(
        r'provider "azapi" \{\n\s+alias\s+= "landing_zone_production"\n\s+subscription_id = ',
        files["environments/prod/providers.tf"],
    )
    main = files["environments/prod/main.tf"]
    assert "azurerm.landing_zone_production = azurerm.landing_zone_production" in main
    assert re.search(
        r"configuration_aliases = \[azurerm\.landing_zone_production\]",
        "".join(text for name, text in files.items() if name.endswith("/versions.tf")),
    )
    _plan, files = terraform_files(template("aws-three-tier-web"), "modules")
    versions = files["environments/prod/versions.tf"]
    assert "google-beta" not in versions and "azapi" not in versions


def test_a_registry_module_does_only_what_the_plain_resources_do_where_it_counts():
    """The rule on the three clouds, from comparing what each style plans:
    the security group module leaves the wires' rules beside it be; the
    modules name no availability zone the plain resources do not, keep one
    App Service worker, an EKS cluster's public endpoint and a log group it
    manages, Cosmos DB's session consistency, and no Network Firewall delete
    protection; a database keeps its last snapshot under a name, so it
    destroys, in both styles; the skeleton needs the Terraform its modules need."""
    from infragram.terraform.coverage import coverage_project

    _plan, files = terraform_files(template("aws-three-tier-web"), "modules")
    assert re.search(r"enable_exclusive_rules\s+= false", files["modules/security/main.tf"])
    # the RDS module needs Terraform 1.11.1, and the environment and the module say so
    assert 'required_version = ">= 1.11.1"' in files["environments/prod/versions.tf"]
    assert re.search(r'required_version = ">= 1.11.1"', files["modules/database/versions.tf"])
    _plan, files = terraform_files(template("aws-three-tier-web"))
    assert 'required_version = ">= 1.5"' in files["environments/prod/versions.tf"]
    _plan, files = terraform_files(coverage_project("aws"), "modules")
    assert re.search(r"endpoint_public_access\s+= true", files["modules/containers/main.tf"])
    assert re.search(r"delete_protection\s+= false", files["modules/security/main.tf"])
    assert re.search(r"final_snapshot_identifier\s+= ", files["modules/database/main.tf"])
    _plan, files = terraform_files(coverage_project("azure"), "modules")
    code = "".join(
        text
        for name, text in files.items()
        if name.startswith("modules/") and name.endswith("main.tf")
    )
    assert re.search(r"zone_redundant\s+= false", code)
    assert re.search(r"worker_count\s+= 1\n\s+zone_balancing_enabled = false", code)
    assert re.search(r'consistency_policy = \{\n\s+consistency_level = "Session"', code)


@pytest.mark.parametrize("style", ["resources", "modules"])
def test_a_network_in_a_second_region_takes_that_regions_zones(style):
    """Each AWS provider configuration has its own availability zones: the
    network of another region reads its region's, not the default's."""
    region = [
        {
            "id": f"region-{n}",
            "name": name,
            "type": "region",
            "attributes": {},
            "connections": [],
            "children": [
                {
                    "id": f"vpc-{n}",
                    "name": f"VPC {n} · 10.{n}.0.0/16",
                    "type": "vpc",
                    "attributes": {},
                    "connections": [],
                    "children": [
                        {
                            "id": f"private-{n}",
                            "name": f"Private · 10.{n}.1.0/24",
                            "type": "subnet-private",
                            "attributes": {},
                            "connections": [],
                            "children": [
                                {
                                    "id": f"web-{n}",
                                    "name": f"web-{n}",
                                    "type": "service",
                                    "attributes": {},
                                    "component": {
                                        "provider": "aws",
                                        "service_id": "ec2",
                                        "icon_ref": "aws:ec2",
                                    },
                                    "connections": [],
                                    "children": [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        for n, name in ((0, "us-east-1"), (1, "eu-west-1"))
    ]
    project = CloudProject.model_validate(
        {
            "schema_version": 2,
            "kind": "single-cloud",
            "slug": "two-regions",
            "title": "Two regions",
            "description": "Two regions, one VPC each.",
            "providers": [{"id": "aws", "enabled": True}],
            "default_library": "aws",
            "topology": {
                "id": "root",
                "name": "two",
                "type": "group",
                "children": [
                    {
                        "id": "cloud",
                        "name": "AWS Cloud",
                        "type": "cloud",
                        "attributes": {},
                        "connections": [],
                        "children": region,
                    }
                ],
            },
        }
    )
    _plan, files = terraform_files(project, style)
    main = files["environments/prod/main.tf"]
    assert re.search(
        r'data "aws_availability_zones" "available_eu_west_1" \{\n\s+provider = aws\.eu_west_1',
        main,
    )
    locals_ = files["environments/prod/locals.tf"]
    assert (
        "eu_west_1_azs = slice(data.aws_availability_zones.available_eu_west_1.names, 0, 2)"
        in locals_
    )
    assert "slice(data.aws_availability_zones.available.names, 0, 2)" in locals_
    assert "aws.eu_west_1 = aws.eu_west_1" in _block(main, "module", "network")


def test_subnets_two_a_zone_still_fit_the_vpc_module():
    """private-dx-staging-platform draws two private subnets in each of two
    zones: in turn by zone, they are the VPC module's four. ``azs`` names each
    zone once and the module wraps round it, so the subnets still land a, b, a,
    b (a list with repeats made the module drop public subnets on three zones)."""
    plan, files = terraform_files(template("private-dx-staging-platform"), "modules")
    network = files["modules/network/main.tf"]
    assert re.search(r'azs\s+= \["\$\{var\.aws_region\}a", "\$\{var\.aws_region\}b"\]', network)
    assert len(re.findall(r"var\.\w+_subnet_cidr\b", network)) == 4, "its four subnets"
    assert re.search(r"cidr\s+= var\.vpc_cidr", network)
    assert not any("cannot be so placed" in note for note in plan.notes)


def test_every_readme_says_what_the_code_has():
    """Each module has a README whose inputs and outputs are the code's, and
    the skeleton's README has the environment's, and the layout drawn."""
    for style in ("resources", "modules"):
        _plan, files = terraform_files(template("aws-three-tier-web"), style)
        for folder in [*_folders(files), "environments/prod"]:
            readme = files[f"{folder}/README.md" if folder.startswith("modules/") else "README.md"]
            text = "".join(
                t
                for name, t in files.items()
                if name.endswith(".tf") and name.rsplit("/", 1)[0] == folder
            )
            for kind in ("variable", "output"):
                for name in re.findall(rf'^{kind} "(\w+)"', text, re.MULTILINE):
                    assert f"| `{name}` |" in readme, (style, folder, kind, name)
        assert "## Layout" in files["README.md"] and "└── environments/" in files["README.md"]
        for folder in _folders(files):
            readme = files[f"{folder}/README.md"]
            assert "## Usage" in readme and f'source = "../../{folder}"' in readme, folder


# ------------------------------------------------- the VPC module's zones (modules style)


def _network(project) -> tuple[str, list[str]]:
    plan, files = terraform_files(project, "modules")
    return files["modules/network/main.tf"], list(plan.notes)


def _list(text: str, name: str) -> list[str]:
    match = re.search(rf"^\s+{name}\s+= \[(.*)\]$", text, re.MULTILINE)
    assert match, (name, text)
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def _flag(text: str, name: str) -> bool:
    match = re.search(rf"^\s+{name}\s+= (true|false)$", text, re.MULTILINE)
    assert match, (name, text)
    return match.group(1) == "true"


def _three_zones_three_tiers():
    from infragram.author import Diagram
    from infragram.nodes import aws
    from infragram.nodes.frames import aws as aws_frames

    with Diagram("az3", "three zones", slug="tf-review-az3") as diagram:
        with aws_frames.Cloud("AWS Cloud"), aws_frames.Region("eu-west-1"):
            with aws_frames.VPC("vpc · 10.0.0.0/16").row():
                for i, z in enumerate("abc"):
                    with aws_frames.AvailabilityZone(f"eu-west-1{z}").column():
                        with aws_frames.PublicSubnet(f"public-{z} · 10.0.{i}.0/24"):
                            aws.VPCNATGateway(f"nat-{z}")
                        with aws_frames.PrivateSubnet(f"app-{z} · 10.0.{10 + i}.0/24"):
                            aws.EC2(f"app-{z}", "t3.micro")
                        with aws_frames.PrivateSubnet(f"data-{z} · 10.0.{20 + i}.0/24"):
                            aws.RDS(f"db-{z}", "db.t3.micro")
    return diagram.to_project()


def test_three_zones_of_three_tiers_name_each_zone_once_in_the_vpc_module():
    network, notes = _network(_three_zones_three_tiers())
    azs = _list(network, "azs")
    public = _list(network, "public_subnets")
    private = _list(network, "private_subnets")
    assert len(azs) == len(set(azs)) == 3, azs
    assert len(public) == 3 and len(private) == 6, (public, private)
    # a side's i-th subnet sits in azs[i % 3]: zones a, b, c, then the data
    # tier wraps round to a, b, c again
    assert [zone.strip('"')[-1] for zone in azs] == ["a", "b", "c"], azs
    assert [c.split("_")[0].removeprefix("var.") for c in private] == ["app"] * 3 + ["data"] * 3
    # one NAT gateway a zone: the module writes the public subnets only when
    # there are at least as many as azs names zones
    assert _flag(network, "one_nat_gateway_per_az")
    assert len(public) >= len(azs)
    assert not any("cannot be so placed" in note for note in notes)


def test_subnets_partly_outside_zone_frames_never_slice_past_the_zones_held():
    from infragram.author import Diagram
    from infragram.nodes import aws
    from infragram.nodes.frames import aws as aws_frames

    with Diagram("mixed", "one subnet in a zone frame", slug="tf-review-mixed") as diagram:
        with aws_frames.Cloud("AWS Cloud"), aws_frames.Region("us-east-1"):
            with aws_frames.VPC("vpc · 10.0.0.0/16"):
                with aws_frames.AvailabilityZone("us-east-1a"):
                    with aws_frames.PrivateSubnet("app-a · 10.0.1.0/24"):
                        aws.EC2("a", "t3.micro")
                with aws_frames.PrivateSubnet("app-b · 10.0.2.0/24"):
                    aws.EC2("b", "t3.micro")
                with aws_frames.PrivateSubnet("app-c · 10.0.3.0/24"):
                    aws.EC2("c", "t3.micro")
    _plan, files = terraform_files(diagram.to_project(), "modules")
    held = 2  # local.azs = slice(data.aws_availability_zones...names, 0, 2)
    for name, text in files.items():
        for end in re.findall(r"slice\((?:var|local)\.\w*azs, 0, (\d+)\)", text):
            assert int(end) <= held, (name, end)
    assert len(_list(files["modules/network/main.tf"], "private_subnets")) == 3


def test_uneven_zones_never_ask_for_a_nat_gateway_a_zone_without_the_public_subnets():
    """Three private subnets in one zone and one in the other cannot wrap
    over two zones, so ``azs`` names a zone again; one NAT gateway a zone
    would then be more zones than public subnets, and the module would write
    none of them."""
    from infragram.author import Diagram
    from infragram.nodes import aws
    from infragram.nodes.frames import aws as aws_frames

    with Diagram("uneven", "uneven zones", slug="tf-review-uneven") as diagram:
        with aws_frames.Cloud("AWS Cloud"), aws_frames.Region("us-east-1"):
            with aws_frames.VPC("vpc · 10.0.0.0/16"):
                with aws_frames.AvailabilityZone("us-east-1a"):
                    with aws_frames.PublicSubnet("public-a · 10.0.0.0/24"):
                        aws.VPCNATGateway("nat-a")
                    for i in range(3):
                        with aws_frames.PrivateSubnet(f"app-a{i} · 10.0.{10 + i}.0/24"):
                            aws.EC2(f"a{i}", "t3.micro")
                with aws_frames.AvailabilityZone("us-east-1b"):
                    with aws_frames.PublicSubnet("public-b · 10.0.1.0/24"):
                        aws.VPCNATGateway("nat-b")
                    with aws_frames.PrivateSubnet("app-b · 10.0.20.0/24"):
                        aws.EC2("b", "t3.micro")
    network, _notes = _network(diagram.to_project())
    azs = _list(network, "azs")
    public = _list(network, "public_subnets")
    if _flag(network, "one_nat_gateway_per_az"):
        assert len(public) >= len(azs), (azs, public)
