"""Terraform that calls modules from a registry, read by ``import:terraform``.

Held here:

- a module ``terraform init`` installed is read from the folder its manifest
  names, and one infragram's module cache holds at the newest version the
  call's constraint allows; any other is a note that says to run
  ``terraform init``; a constraint is read as Terraform reads one;
- an output that holds a module lets a caller reach an instance's outputs,
  and ``[i]`` or ``["key"]`` of an output that names a repeated resource is
  that instance (``[i]`` in key order, as the list an output makes holds it);
- a module called once gives what its outputs hold, so what a resource
  repeats over a utility module's map is known; what only a made resource
  gives is not, whatever ``try()`` falls back to (``try(aws_subnet.this[*].id,
  [])`` is no empty list); a dynamic block's iterator names what its
  ``for_each`` names;
- a Front Door's endpoints, origin groups, origins and routes fold into its
  profile (a part of a part too), and its WAF policy is drawn;
- a variable's type gives an object's optional attributes their defaults;
- an ``azapi_resource`` of an Azure type the table knows is drawn as the
  ``azurerm`` resource it is, and any other says its Azure type;
- over the public registry's own modules (AWS VPC, security group, EC2 and
  RDS; the Azure Verified Modules; the Google network module), when the
  module cache holds the versions pinned: every count known, each piece
  where it sits and the rules drawn as wires.
"""

from __future__ import annotations

import json
import shutil

import pytest

from infragram.estate import Box, draw
from infragram.paths import repo_root
from infragram.terraform.readconfig import _allows, _version, module_cache, read_configuration

FIXTURES = repo_root() / "tests" / "fixtures" / "estate" / "terraform"
#: A module in the shape of terraform-aws-modules/vpc, written to be one.
VPC = FIXTURES / "registry" / "modules" / "vpc"

NETWORK_CALL = """
provider "aws" {
  region = "eu-west-1"
}

module "network" {
  source  = "acme/network/aws"
  version = "%s"

  name               = "shop"
  cidr               = "10.0.0.0/16"
  azs                = ["eu-west-1a", "eu-west-1b"]
  public_subnets     = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets    = ["10.0.11.0/24", "10.0.12.0/24"]
  enable_nat_gateway = true
  single_nat_gateway = true
}

resource "aws_instance" "web" {
  ami           = "ami-0123456789abcdef0"
  instance_type = "t3.small"
  subnet_id     = module.network.private_subnets[1]
}
"""


def _parent(drawing, key: str) -> str | None:
    def visit(box: Box) -> str | None:
        for child in box.children:
            if child.key == key:
                return box.key
            if isinstance(child, Box) and (found := visit(child)):
                return found
        return None

    return next(
        (found for root in drawing.roots if isinstance(root, Box) and (found := visit(root))), None
    )


def _files(folder, files: dict[str, str]) -> None:
    for name, text in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- where a module is read from
def test_a_module_terraform_init_installed_is_read(tmp_path, monkeypatch):
    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path / "empty-cache"))
    root = tmp_path / "shop"
    _files(root, {"main.tf": NETWORK_CALL % "1.2.0"})
    shutil.copytree(VPC, root / ".terraform" / "modules" / "network")
    (root / ".terraform" / "modules" / "modules.json").write_text(
        json.dumps(
            {
                "Modules": [
                    {"Key": "", "Source": "", "Dir": "."},
                    {
                        "Key": "network",
                        "Source": "registry.terraform.io/acme/network/aws",
                        "Version": "1.2.0",
                        "Dir": ".terraform/modules/network",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    estate = read_configuration(root)
    assert "1 registry module from terraform init" in estate.origin
    assert estate.notes == []
    by = {found.address: found for found in estate.resources}
    assert by["aws_instance.web"].references["subnet_id"] == [
        "module.network.aws_subnet.private[1]"
    ]
    drawing = draw(estate)
    assert _parent(drawing, "aws_instance.web") == "module.network.aws_subnet.private[1]"
    assert (
        _parent(drawing, "module.network.aws_subnet.private[1]")
        == "zone:module.network.aws_vpc.this[0]:eu-west-1b"
    )


def test_a_module_in_the_cache_is_read_at_the_newest_version_its_constraint_allows(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path / "cache"))
    for version in ("1.2.0", "1.3.0", "2.0.0"):
        shutil.copytree(VPC, module_cache() / "acme" / "network" / "aws" / version)
    for constraint, read in (("~> 1.2", "1.3.0"), ("2.0.0", "2.0.0"), (">= 1.0, < 1.3", "1.2.0")):
        root = tmp_path / constraint.replace(" ", "").replace(">", "gt").replace("<", "lt").replace(
            ",", "_"
        )
        _files(root, {"main.tf": NETWORK_CALL % constraint})
        estate = read_configuration(root)
        assert "1 registry module from the module cache" in estate.origin
        vpc = next(found for found in estate.resources if found.type == "aws_vpc")
        assert f"/{read}/" in vpc.source, (constraint, vpc.source)
    # a version the cache does not hold is a note that says what to do
    root = tmp_path / "unheld"
    _files(root, {"main.tf": NETWORK_CALL % "~> 3.0"})
    estate = read_configuration(root)
    assert not [found for found in estate.resources if found.type == "aws_vpc"]
    assert any("acme/network/aws" in note and "terraform init" in note for note in estate.notes)


@pytest.mark.parametrize(
    ("constraint", "version", "allowed"),
    [
        ("6.7.3", "6.7.3", True),
        ("6.7.3", "6.7.4", False),
        ("= 6.7.3", "6.7.3", True),
        ("~> 6.0", "6.7.3", True),
        ("~> 6.0", "7.0.0", False),
        ("~> 6.7.3", "6.7.9", True),
        ("~> 6.7.3", "6.8.0", False),
        ("~> 6", "6.99.0", True),
        (">= 6.0, < 7.0", "6.9.1", True),
        (">= 6.0, < 7.0", "7.0.0", False),
        ("!= 6.1.0", "6.1.0", False),
        ("> 6.1", "6.1.0", False),
    ],
)
def test_a_version_constraint_is_read_as_terraform_reads_it(constraint, version, allowed):
    assert _allows(constraint, _version(version)) is allowed


# ---------------------------------------------------------------- what a module's outputs name
def test_an_output_holding_a_module_or_a_map_reaches_one_instance(tmp_path):
    _files(
        tmp_path,
        {
            "main.tf": """
module "net" {
  source = "./net"
}

resource "aws_instance" "web" {
  ami           = "ami-1"
  instance_type = "t3.small"
  subnet_id     = module.net.subnets["web"].subnet_id
}

resource "aws_instance" "worker" {
  ami           = "ami-1"
  instance_type = "t3.small"
  subnet_id     = module.net.extra_ids[1]
}

resource "aws_instance" "admin" {
  ami           = "ami-1"
  instance_type = "t3.small"
  subnet_id     = module.net.extra["a"].id
}
""",
            "net/main.tf": """
resource "aws_vpc" "this" {
  cidr_block = "10.0.0.0/16"
}

module "subnet" {
  source   = "./subnet"
  for_each = { web = "10.0.1.0/24", data = "10.0.2.0/24" }

  cidr   = each.value
  vpc_id = aws_vpc.this.id
}

resource "aws_subnet" "extra" {
  for_each   = { b = "10.0.4.0/24", a = "10.0.3.0/24" }
  vpc_id     = aws_vpc.this.id
  cidr_block = each.value
}

output "subnets" {
  value = module.subnet
}

output "extra" {
  value = aws_subnet.extra
}

output "extra_ids" {
  value = [for subnet in aws_subnet.extra : subnet.id]
}
""",
            "net/subnet/main.tf": """
variable "cidr" {
  type = string
}

variable "vpc_id" {
  type = string
}

resource "aws_subnet" "this" {
  vpc_id     = var.vpc_id
  cidr_block = var.cidr
}

output "subnet_id" {
  value = aws_subnet.this.id
}
""",
        },
    )
    by = {found.address: found for found in read_configuration(tmp_path).resources}
    # an instance of the module an output holds, then that instance's output
    assert by["aws_instance.web"].references["subnet_id"] == [
        'module.net.module.subnet["web"].aws_subnet.this'
    ]
    # [1] of a list made of a map's instances is the second in key order
    assert by["aws_instance.worker"].references["subnet_id"] == ["module.net.aws_subnet.extra[1]"]
    drawing = draw(read_configuration(tmp_path))
    assert _parent(drawing, "aws_instance.worker") == 'module.net.aws_subnet.extra["b"]'
    assert by["aws_instance.admin"].references["subnet_id"] == ['module.net.aws_subnet.extra["a"]']


def test_what_is_read_of_an_outputs_entry_is_that_instance(tmp_path):
    """The modules style's reads: an index after an attribute of an output's
    entry (``module.network.vpcs["a"].private_subnets[1]``), a chain one
    level deeper (``...virtual_networks["v"].subnets["web"].id``), and an
    output a ``for`` expression makes whose element is named like a resource
    type (``for key, security_group in module.security_group``)."""
    _files(
        tmp_path,
        {
            "main.tf": """
module "network" {
  source = "./network"
}

resource "aws_instance" "web" {
  ami           = "ami-1"
  instance_type = "t3.small"
  subnet_id     = module.network.vpcs["a"].private_subnets[1]
}

resource "aws_instance" "api" {
  ami                    = "ami-1"
  instance_type          = "t3.small"
  subnet_id              = module.network.virtual_networks["v"].subnets["web"].id
  vpc_security_group_ids = [module.network.security_groups["api"].id]
}
""",
            "network/main.tf": """
module "vpc" {
  source   = "./vpc"
  for_each = { a = "10.0.0.0/16" }

  cidr = each.value
}

module "virtual_network" {
  source   = "./vnet"
  for_each = { v = "10.1.0.0/16" }

  cidr = each.value
}

module "security_group" {
  source   = "./group"
  for_each = { web = "web", api = "api" }

  name = each.value
}

output "vpcs" {
  value = { for key, vpc in module.vpc : key => { private_subnets = vpc.private_subnets } }
}

output "virtual_networks" {
  value = { for key, virtual_network in module.virtual_network : key => { subnets = virtual_network.subnets } }
}

output "security_groups" {
  value = { for key, security_group in module.security_group : key => { id = security_group.id } }
}
""",
            "network/vpc/main.tf": """
variable "cidr" {
  type = string
}

resource "aws_vpc" "this" {
  cidr_block = var.cidr
}

resource "aws_subnet" "private" {
  count      = 2
  vpc_id     = aws_vpc.this.id
  cidr_block = cidrsubnet(var.cidr, 8, count.index)
}

output "private_subnets" {
  value = aws_subnet.private[*].id
}
""",
            "network/vnet/main.tf": """
variable "cidr" {
  type = string
}

resource "aws_vpc" "this" {
  cidr_block = var.cidr
}

module "subnet" {
  source   = "./subnet"
  for_each = { web = 1, data = 2 }

  vpc_id = aws_vpc.this.id
  cidr   = cidrsubnet(var.cidr, 8, each.value)
}

output "subnets" {
  value = module.subnet
}
""",
            "network/vnet/subnet/main.tf": """
variable "vpc_id" {
  type = string
}

variable "cidr" {
  type = string
}

resource "aws_subnet" "this" {
  vpc_id     = var.vpc_id
  cidr_block = var.cidr
}

output "id" {
  value = aws_subnet.this.id
}
""",
            "network/group/main.tf": """
variable "name" {
  type = string
}

resource "aws_security_group" "this" {
  name = var.name
}

output "id" {
  value = aws_security_group.this.id
}
""",
        },
    )
    by = {found.address: found for found in read_configuration(tmp_path).resources}
    assert by["aws_instance.web"].references["subnet_id"] == [
        'module.network.module.vpc["a"].aws_subnet.private[1]'
    ]
    assert by["aws_instance.api"].references["subnet_id"] == [
        'module.network.module.virtual_network["v"].module.subnet["web"].aws_subnet.this'
    ]
    # the element a for expression binds is no resource: one group, not every one
    assert by["aws_instance.api"].references["vpc_security_group_ids"] == [
        'module.network.module.security_group["api"].aws_security_group.this'
    ]


def test_a_modules_this_is_captioned_by_the_key_of_the_instance_it_is_in():
    from infragram.estate.draw import caption_of
    from infragram.estate.model import Found

    zone = Found(
        address='module.dns.module.route53_zone["route53"].aws_route53_zone.this[0]',
        type="aws_route53_zone",
        name="this",
        values={},
        references={},
    )
    assert caption_of(zone) == "route53"
    rule = Found(
        address='module.security.aws_vpc_security_group_ingress_rule.this["web_from_alb"]',
        type="aws_vpc_security_group_ingress_rule",
        name="this",
        values={},
        references={},
    )
    assert caption_of(rule) == "web_from_alb"
    plain = Found(
        address="aws_subnet.extra[1]", type="aws_subnet", name="extra", values={}, references={}
    )
    assert caption_of(plain) == "extra[1]"
    # its own index past the first tells two of one instance apart
    first, second = (
        Found(
            address=f'module.net["prod"].aws_subnet.this[{i}]',
            type="aws_subnet",
            name="this",
            values={},
            references={},
        )
        for i in (0, 1)
    )
    assert (caption_of(first), caption_of(second)) == ("prod", "prod[1]")


def test_what_a_utility_module_gives_is_known_and_what_a_resource_gives_is_not(tmp_path):
    """A module called once has its outputs evaluated where they name no
    resource, or make a map of none: a lock asked for by nobody is none, and
    a map of role assignments for each of none is empty. An output a
    resource gives is not known before it is made, whatever try() falls back
    to: the security group it names still wears its rule."""
    _files(
        tmp_path,
        {
            "main.tf": """
module "interfaces" {
  source = "./interfaces"
}

module "sg" {
  source = "./sg"
}

resource "azurerm_management_lock" "this" {
  for_each   = module.interfaces.lock != null ? { lock = module.interfaces.lock } : {}
  name       = each.value.name
  scope      = "x"
  lock_level = "CanNotDelete"
}

resource "azurerm_role_assignment" "this" {
  for_each             = module.interfaces.role_assignments
  scope                = "x"
  principal_id         = each.value.principal_id
  role_definition_name = "Reader"
}

resource "aws_instance" "web" {
  ami                    = "ami-1"
  instance_type          = "t3.small"
  vpc_security_group_ids = [module.sg.id]
}
""",
            "interfaces/main.tf": """
variable "lock" {
  type    = object({ kind = string, name = optional(string) })
  default = null
}

variable "role_assignments" {
  type    = map(object({ principal_id = string }))
  default = {}
}

resource "random_uuid" "name" {
  for_each = var.role_assignments
}

output "lock" {
  value = var.lock == null ? null : { name = coalesce(var.lock.name, "lock") }
}

output "role_assignments" {
  value = { for key, item in var.role_assignments : key => { principal_id = item.principal_id, name = random_uuid.name[key].result } }
}
""",
            "sg/main.tf": """
resource "aws_security_group" "this" {
  name = "web"
}

output "id" {
  value = try(aws_security_group.this.id, "")
}
""",
        },
    )
    by = {found.address: found for found in read_configuration(tmp_path).resources}
    assert not [
        address for address in by if "management_lock" in address or "role_assignment" in address
    ]
    web = by["aws_instance.web"]
    assert web.references["vpc_security_group_ids"] == ["module.sg.aws_security_group.this"]
    assert web.values.get("vpc_security_group_ids") != [""]


def test_what_only_a_made_resource_gives_is_no_empty_list(tmp_path):
    """``try(aws_subnet.this[*].id, [])`` in a module's output is the subnets'
    ids once made, not the empty list try() falls back to: a resource counted
    over it is drawn once, with a note, not left out."""
    _files(
        tmp_path,
        {
            "main.tf": """
module "net" {
  source = "./net"
}

resource "aws_instance" "web" {
  count         = length(module.net.subnet_ids)
  ami           = "ami-1"
  instance_type = "t3.small"
  subnet_id     = module.net.subnet_ids[count.index]
}
""",
            "net/main.tf": """
resource "aws_vpc" "this" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "this" {
  count      = 2
  vpc_id     = aws_vpc.this.id
  cidr_block = cidrsubnet("10.0.0.0/16", 8, count.index)
}

output "subnet_ids" {
  value = try(aws_subnet.this[*].id, [])
}
""",
        },
    )
    estate = read_configuration(tmp_path)
    assert "aws_instance.web" in {found.address for found in estate.resources}
    assert (
        "aws_instance.web: its count is not known without a plan, so it is drawn once"
        in estate.notes
    )


def test_a_front_doors_parts_fold_into_its_profile_and_its_waf_is_drawn(tmp_path):
    """A Front Door profile's endpoint, origin group, origin (a part of a
    part), route and rule set are the profile; its WAF policy is drawn as one."""
    _files(
        tmp_path,
        {
            "main.tf": """
resource "azurerm_resource_group" "edge" {
  name     = "rg-edge"
  location = "westeurope"
}

resource "azurerm_cdn_frontdoor_profile" "fd" {
  name                = "fd-shop"
  resource_group_name = azurerm_resource_group.edge.name
  sku_name            = "Premium_AzureFrontDoor"
}

resource "azurerm_cdn_frontdoor_origin" "web" {
  name                          = "web"
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.web.id
  host_name                     = "shop.example.com"
  certificate_name_check_enabled = true
}

resource "azurerm_cdn_frontdoor_origin_group" "web" {
  name                     = "web"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.fd.id
}

resource "azurerm_cdn_frontdoor_endpoint" "shop" {
  name                     = "shop"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.fd.id
}

resource "azurerm_cdn_frontdoor_route" "shop" {
  name                          = "shop"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.shop.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.web.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.web.id]
  supported_protocols           = ["Https"]
  patterns_to_match             = ["/*"]
}

resource "azurerm_cdn_frontdoor_firewall_policy" "waf" {
  name                = "wafshop"
  resource_group_name = azurerm_resource_group.edge.name
  sku_name            = "Premium_AzureFrontDoor"
  mode                = "Prevention"
}
"""
        },
    )
    drawing = draw(read_configuration(tmp_path))
    drawn = sorted(
        getattr(item, "service_id", "") for item in drawing.walk() if not isinstance(item, Box)
    )
    assert drawn == ["front-door-and-cdn-profiles", "web-application-firewall-policies-waf"], drawn
    for part in ("origin.web", "origin_group.web", "endpoint.shop", "route.shop"):
        assert drawing.folded[f"azurerm_cdn_frontdoor_{part}"].startswith("part of "), part


def test_a_dynamic_blocks_iterator_names_what_its_for_each_names(tmp_path):
    """``network_configuration.value.security_groups`` is no resource type
    but the dynamic block's iterator: it names what ``[local.network]``
    names, as the ECS service module writes its network."""
    _files(
        tmp_path,
        {
            "main.tf": """
resource "aws_security_group" "app" {
  name = "app"
}

locals {
  network = {
    security_groups = [aws_security_group.app.id]
    subnets         = ["subnet-1"]
  }
}

resource "aws_ecs_service" "web" {
  name = "web"

  dynamic "network_configuration" {
    for_each = var.enabled ? [local.network] : []

    content {
      security_groups = network_configuration.value.security_groups
      subnets         = network_configuration.value.subnets
    }
  }
}

variable "enabled" {
  type = bool
}
""",
        },
    )
    web = next(
        found
        for found in read_configuration(tmp_path).resources
        if found.address == "aws_ecs_service.web"
    )
    assert web.references["network_configuration.security_groups"] == ["aws_security_group.app"]
    assert not any(
        "network_configuration.value" in address
        for refs in web.references.values()
        for address in refs
    )


def test_a_variables_type_gives_optional_attributes_their_defaults(tmp_path):
    _files(
        tmp_path,
        {
            "main.tf": """
module "net" {
  source  = "./net"
  subnets = { web = { cidr = "10.0.1.0/24" }, data = { cidr = "10.0.2.0/24", count = 2 } }
}
""",
            "net/main.tf": """
variable "subnets" {
  type = map(object({
    cidr  = string
    count = optional(number, 1)
    zone  = optional(string)
  }))
}

resource "aws_vpc" "this" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "this" {
  for_each   = { for name, subnet in var.subnets : name => subnet if subnet.zone == null }
  vpc_id     = aws_vpc.this.id
  cidr_block = each.value.cidr
  tags       = { Name = "${each.key}-${each.value.count}" }
}
""",
        },
    )
    estate = read_configuration(tmp_path)
    assert estate.notes == []
    names = sorted(
        found.values["tags"]["Name"] for found in estate.resources if found.type == "aws_subnet"
    )
    assert names == ["data-2", "web-1"]


# ---------------------------------------------------------------- AzAPI
def test_azapi_resources_are_drawn_as_the_azurerm_resources_they_are(tmp_path):
    _files(
        tmp_path,
        {
            "main.tf": """
resource "azurerm_resource_group" "shop" {
  name     = "rg-shop"
  location = "westeurope"
}

resource "azapi_resource" "vnet" {
  type      = "Microsoft.Network/virtualNetworks@2024-07-01"
  name      = "vnet-shop"
  location  = "westeurope"
  parent_id = azurerm_resource_group.shop.id
  body = {
    properties = {
      addressSpace = { addressPrefixes = ["10.1.0.0/16"] }
    }
  }
}

resource "azapi_resource" "subnet" {
  type      = "Microsoft.Network/virtualNetworks/subnets@2024-07-01"
  name      = "snet-web"
  parent_id = azapi_resource.vnet.id
  body = {
    properties = {
      addressPrefixes = ["10.1.1.0/24"]
      defaultOutboundAccess = var.outbound
    }
  }
}

resource "azapi_resource" "lock" {
  type      = "Microsoft.Authorization/locks@2020-05-01"
  name      = "no-delete"
  parent_id = azurerm_resource_group.shop.id
}

variable "outbound" {
  type = bool
}
"""
        },
    )
    drawing = draw(read_configuration(tmp_path))
    boxes = {item.key: item for item in drawing.walk() if isinstance(item, Box)}
    assert boxes["azapi_resource.vnet"].kind == "network"
    assert boxes["azapi_resource.vnet"].caption == "vnet-shop · 10.1.0.0/16"
    # a value it cannot know leaves the others it can: the subnet's range
    assert boxes["azapi_resource.subnet"].caption == "snet-web · 10.1.1.0/24"
    assert _parent(drawing, "azapi_resource.subnet") == "azapi_resource.vnet"
    assert _parent(drawing, "azapi_resource.vnet") == "azurerm_resource_group.shop"
    assert (
        drawing.left_out["azapi_resource.lock"]
        == "an azapi resource of Microsoft.Authorization/locks, which the import does not draw"
    )


# ---------------------------------------------------------------- the registry's own modules
def _held(*modules: str) -> bool:
    return all((module_cache() / module).is_dir() for module in modules)


@pytest.mark.skipif(
    not _held(
        "terraform-aws-modules/vpc/aws/6.7.3",
        "terraform-aws-modules/security-group/aws/6.0.0",
        "terraform-aws-modules/ec2-instance/aws/6.4.1",
        "terraform-aws-modules/rds/aws/7.2.2",
    ),
    reason="the module cache does not hold the AWS modules (infragram verify:terraform --fetch)",
)
def test_the_aws_registry_modules_draw_where_their_resources_sit():
    estate = read_configuration(FIXTURES / "registry-modules" / "aws")
    assert "4 registry modules from the module cache" in estate.origin
    assert estate.notes == []
    drawing = draw(estate)
    kinds = {item.key: item.kind for item in drawing.walk() if isinstance(item, Box)}
    subnets = [key for key in kinds if key.startswith("module.vpc.aws_subnet.")]
    assert len(subnets) == 9 and kinds["module.vpc.aws_subnet.public[2]"] == "subnet-public"
    assert (
        _parent(drawing, "module.vpc.aws_nat_gateway.this[0]") == "module.vpc.aws_subnet.public[0]"
    )
    assert _parent(drawing, "module.web.aws_instance.this[0]") == "module.vpc.aws_subnet.public[0]"
    assert (
        _parent(drawing, "module.db.module.db_instance.aws_db_instance.this[0]")
        == "module.vpc.aws_subnet.database[0]"
    )
    assert {(w.source, w.target): w.label for w in drawing.wires} == {
        ("internet", "module.web.aws_instance.this[0]"): "HTTPS :443",
        (
            "module.web.aws_instance.this[0]",
            "module.db.module.db_instance.aws_db_instance.this[0]",
        ): "PostgreSQL :5432",
    }


@pytest.mark.skipif(
    not _held(
        "Azure/avm-res-network-virtualnetwork/azurerm/0.22.2",
        "Azure/avm-res-network-networksecuritygroup/azurerm/0.5.1",
    ),
    reason="the module cache does not hold the Azure Verified Modules (infragram verify:terraform --fetch)",
)
def test_the_azure_verified_modules_draw_where_their_resources_sit():
    estate = read_configuration(FIXTURES / "registry-modules" / "azure")
    drawing = draw(estate)
    assert drawing.notes == []
    vnet, web = (
        "module.vnet.azapi_resource.vnet",
        'module.vnet.module.subnet["web"].azapi_resource.subnet[0]',
    )
    assert _parent(drawing, vnet) == "azurerm_resource_group.shop"
    assert _parent(drawing, web) == vnet
    assert _parent(drawing, "azurerm_linux_virtual_machine.web") == web
    assert [(w.source, w.target, w.label) for w in drawing.wires] == [
        ("internet", "azurerm_linux_virtual_machine.web", "HTTPS :443")
    ]


@pytest.mark.skipif(
    not _held("terraform-google-modules/network/google/18.3.0"),
    reason="the module cache does not hold the Google network module (infragram verify:terraform --fetch)",
)
def test_the_google_network_module_draws_where_its_resources_sit():
    drawing = draw(read_configuration(FIXTURES / "registry-modules" / "gcp"))
    web = 'module.vpc.module.subnets.google_compute_subnetwork.subnetwork["europe-west1/web"]'
    assert _parent(drawing, "google_compute_instance.web") == web
    # subnets_self_links[1] is the second subnetwork in key order: web
    assert _parent(drawing, "google_compute_instance.db") == web
    assert {(w.source, w.target): w.label for w in drawing.wires} == {
        ("internet", "google_compute_instance.web"): "HTTPS :443",
        ("google_compute_instance.web", "google_compute_instance.db"): "PostgreSQL :5432",
    }
