"""A live estate to a diagram: ``discover:aws``, ``discover:azure``, ``discover:gcp``.

The CLIs are replayed from ``tests/fixtures/estate/discover/<cloud>.json``, the
answers each would give a small estate, so what is held here is:

- every call a reader makes only reads: describe, get, list, show;
- a call the account may not make is a note, and the rest is still drawn;
- each reader writes what it reads in Terraform's terms, and the drawing
  places it: an AWS default VPC nobody uses is left out, an Azure VM sits in
  its network interface's subnet and an AKS pool in its cluster, a Google
  NAT sits in its router's network;
- network security groups, application security groups and firewall rules
  are read with the rest and draw the traffic they allow;
- the commands write the diagram file and report from the same readers, and
  say plainly when the CLI is missing or nothing is named to read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from infragram.estate import Box, Card, draw, write_spec
from infragram.estate.discover import CallError, DiscoveryError, cli_runner
from infragram.estate.discover.aws import discover_aws
from infragram.estate.discover.azure import discover_azure
from infragram.estate.discover.gcp import discover_gcp
from infragram.paths import repo_root

FIXTURES = repo_root() / "tests" / "fixtures" / "estate" / "discover"
#: Flags the recorded keys leave out, and how many values each takes.
_FLAGS = {
    "--output": 1,
    "--profile": 1,
    "--subscription": 1,
    "--project": 1,
    "--format": 1,
    "--only-show-errors": 0,
    "--quiet": 0,
}
#: The verbs a read-only call starts with.
_READS = ("describe", "get", "list", "show")


class Replay:
    """A CLI that answers from the recording, and remembers what it was asked."""

    def __init__(self, cloud: str) -> None:
        self.answers = json.loads((FIXTURES / f"{cloud}.json").read_text(encoding="utf-8"))["calls"]
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]):
        self.calls.append(list(args))
        key, i = [], 0
        while i < len(args):
            if args[i] in _FLAGS:
                i += 1 + _FLAGS[args[i]]
                continue
            key.append(args[i])
            i += 1
        answer = self.answers.get(" ".join(key))
        if isinstance(answer, dict) and "__error__" in answer:
            raise CallError(" ".join(key), answer["__error__"])
        return answer

    def verbs(self) -> set[str]:
        """The verb of every call: the first word that is not a group name."""
        out = set()
        for call in self.calls:
            words = [w for w in call if not w.startswith("-")]
            verb = next((w for w in words if w.split("-")[0] in _READS), None)
            out.add(verb.split("-")[0] if verb else " ".join(words))
        return out


def _where(drawing) -> dict[str, str]:
    """element key -> the key of the frame it is in."""
    out: dict[str, str] = {}

    def visit(box: Box) -> None:
        for child in box.children:
            out[child.key] = box.key
            if isinstance(child, Box):
                visit(child)

    for root in drawing.roots:
        if isinstance(root, Box):
            visit(root)
    return out


# ---------------------------------------------------------------- AWS
def test_aws_is_read_with_reads_only_and_drawn_where_it_runs():
    replay = Replay("aws")
    estate = discover_aws(regions=["eu-west-1"], runner=replay)
    assert replay.verbs() <= set(_READS)
    assert estate.title == "AWS account 111122223333"
    assert any("lambda list-functions" in note and "AccessDenied" in note for note in estate.notes)
    drawing = draw(estate)
    where = _where(drawing)
    # the default VPC nobody uses is left out; the terminated instance is not read
    keys = {item.key for item in drawing.walk()}
    assert "aws_vpc.vpc-0de" not in keys and "aws_instance.i-old" not in keys
    assert where["aws_instance.i-web1"] == "aws_subnet.subnet-app-a"
    assert where["aws_db_instance.shop-prod-db"] == "aws_subnet.subnet-app-a"
    assert where["aws_lb.shop-alb"] == "aws_subnet.subnet-pub-a"
    kinds = {item.key: item.kind for item in drawing.walk() if isinstance(item, Box)}
    # public by its route to the internet gateway, though it maps no public address
    assert kinds["aws_subnet.subnet-pub-b"] == "subnet-public"
    assert kinds["aws_subnet.subnet-app-b"] == "subnet-private"
    wires = {(w.source, w.target): w.label for w in drawing.wires}
    assert wires == {
        ("internet", "aws_lb.shop-alb"): "HTTPS :443",
        ("aws_lb.shop-alb", "aws_instance.i-web1"): "HTTP :8080",
        ("aws_lb.shop-alb", "aws_instance.i-web2"): "HTTP :8080",
        ("aws_instance.i-web1", "aws_db_instance.shop-prod-db"): "PostgreSQL :5432",
        ("aws_instance.i-web2", "aws_db_instance.shop-prod-db"): "PostgreSQL :5432",
    }


def test_aws_needs_a_region_and_a_cli_that_signs_in(monkeypatch):
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    with pytest.raises(DiscoveryError, match="--region"):
        discover_aws(regions=[], runner=Replay("aws"))

    def refuses(args):
        raise CallError("aws sts get-caller-identity", "Unable to locate credentials")

    with pytest.raises(DiscoveryError, match="cannot sign in"):
        discover_aws(regions=["eu-west-1"], runner=refuses)
    with pytest.raises(DiscoveryError, match="not on the PATH"):
        cli_runner("infragram-no-such-cli")


# ---------------------------------------------------------------- Azure
def test_azure_is_read_with_lists_only_and_drawn_by_group_and_network():
    replay = Replay("azure")
    estate = discover_azure(runner=replay)
    assert replay.verbs() <= set(_READS)
    assert estate.title == "Contoso Production"
    assert any("redis" in note and "AuthorizationFailed" in note for note in estate.notes)
    drawing = draw(estate)
    where = _where(drawing)
    ids = {item.key: item for item in drawing.walk()}
    assert ids["top:azure"].caption == "Contoso Production"
    # through its network interface, whose subnet id differs in case
    assert where["azurerm_linux_virtual_machine.vm-jump"] == "azurerm_subnet.snet-shared"
    # the pools inside their cluster, the cluster inside its subnet
    cluster = "azurerm_kubernetes_cluster.aks-app"
    assert where[f"{cluster}#default_node_pool"] == cluster
    assert where["azurerm_kubernetes_cluster_node_pool.user"] == cluster
    assert where[cluster] == "azurerm_subnet.snet-aks"
    assert ids[f"{cluster}#default_node_pool"].caption == "system"
    pools = (f"{cluster}#default_node_pool", "azurerm_kubernetes_cluster_node_pool.user")
    assert {(w.source, w.target): w.label for w in drawing.wires} == {
        # the endpoint reaches the database on the server it names
        (
            "azurerm_private_endpoint.pe-sql",
            "azurerm_mssql_database.shop",
        ): "private service connection",
        # the hub subnet's group lets the internet in on SSH; the cluster
        # subnet's lets anyone in on HTTPS, and the jump box's application
        # security group (named in another case by its interface) on SSH
        ("internet", "azurerm_linux_virtual_machine.vm-jump"): "SSH :22",
        **{("internet", pool): "HTTPS :443" for pool in pools},
        **{("azurerm_linux_virtual_machine.vm-jump", pool): "SSH :22" for pool in pools},
    }
    assert (
        drawing.folded["azurerm_network_security_group.nsg-aks"]
        == "drawn as a badge on its subnet and the wires it allows"
    )
    # what applies to a subnet is a badge on its corner: the NSG first, the
    # route table beside it; one route table on two subnets is on each
    badges = {
        item.key: [(badge.service_id, badge.label) for badge in item.badges]
        for item in drawing.walk()
        if isinstance(item, Box) and item.badges
    }
    assert badges == {
        "azurerm_subnet.snet-aks": [
            ("network-security-groups", "nsg-aks"),
            ("route-tables", "rt-app-egress"),
        ],
        "azurerm_subnet.snet-web": [("route-tables", "rt-app-egress")],
        "azurerm_subnet.snet-shared": [("network-security-groups", "nsg-shared")],
    }
    assert (
        drawing.folded["azurerm_route_table.rt-app-egress"]
        == "drawn as a badge on each of its 2 subnets"
    )
    # the peering is a card
    peering = [
        item for item in drawing.walk() if isinstance(item, Card) and item.service_id == "peerings"
    ]
    assert [(p.caption, where[p.key]) for p in peering] == [
        ("peering to vnet-app", "azurerm_virtual_network.vnet-hub")
    ]


# ---------------------------------------------------------------- Google Cloud
def test_gcp_is_read_with_lists_only_and_drawn_in_its_networks():
    replay = Replay("gcp")
    estate = discover_gcp(runner=replay)
    assert replay.verbs() <= set(_READS)
    assert estate.title == "Google Cloud project shop-prod-1234"
    # Memorystore is asked in the regions the subnets are in
    assert replay.calls[-1][:5] == ["redis", "instances", "list", "--region", "europe-west1"]
    drawing = draw(estate)
    where = _where(drawing)
    assert where["google_compute_instance.bastion"] == "google_compute_subnetwork.web"
    assert where["google_container_cluster.shop-gke"] == "google_compute_subnetwork.gke"
    assert where["google_sql_database_instance.shop-db"] == "google_compute_network.shop-vpc"
    # the NAT is in the network its router is in
    assert where["google_compute_router_nat.shop-nat"] == "google_compute_network.shop-vpc"
    assert where["google_cloud_run_v2_service.shop-api"] == "project:shop-prod-1234"
    # the firewall: HTTPS from the internet to the web tag, SSH from the
    # bastion's tag; Identity-Aware Proxy's range reaches nothing drawn, the
    # internal range holds every subnetwork, and a deny allows nothing
    assert {(w.source, w.target): w.label for w in drawing.wires} == {
        ("internet", "google_compute_instance.web-1"): "HTTPS :443",
        ("google_compute_instance.bastion", "google_compute_instance.web-1"): "SSH :22",
    }
    for rule in ("allow-iap-ssh", "allow-internal", "deny-telnet"):
        assert drawing.left_out[f"google_compute_firewall.{rule}"].startswith("not architecture")


# ---------------------------------------------------------------- the commands
@pytest.mark.parametrize(
    ("cloud", "argv"),
    [
        ("aws", ["--region", "eu-west-1"]),
        ("azure", []),
        ("gcp", []),
    ],
)
def test_the_discover_commands_write_the_file_and_report(
    cloud, argv, tmp_path, monkeypatch, capsys
):
    import importlib

    from infragram.cli.user import import_estate

    module = importlib.import_module(f"infragram.estate.discover.{cloud}")
    monkeypatch.setattr(module, "cli_runner", lambda program: Replay(cloud))
    command = getattr(import_estate, f"discover_{cloud}")
    assert command([*argv, "--no-export", "--output-dir", str(tmp_path)]) == 0, (
        capsys.readouterr().err
    )
    specs = list(tmp_path.glob("*.py"))
    assert len(specs) == 1
    assert (tmp_path / f"{specs[0].stem}.import.md").is_file()
    text = specs[0].read_text(encoding="utf-8")
    assert f"infragram discover:{cloud}" in text and "read-only" in text


def test_a_drawing_of_a_live_estate_composes(tmp_path):
    from infragram.cli.user.checker import checker
    from infragram.cli.user.compose import project_from_spec
    from infragram.exports import render_project_svg

    for cloud, read in (
        ("aws", lambda r: discover_aws(regions=["eu-west-1"], runner=r)),
        ("azure", lambda r: discover_azure(runner=r)),
        ("gcp", lambda r: discover_gcp(runner=r)),
    ):
        drawing = draw(read(Replay(cloud)))
        spec = Path(tmp_path, f"{cloud}.py")
        spec.write_text(
            write_spec(drawing, command=f"discover:{cloud}", date="2026-09-23", filename=spec.name),
            encoding="utf-8",
        )
        project = project_from_spec(spec)
        project.save(tmp_path / f"{project.slug}.infragram.json")
        picture = tmp_path / f"{project.slug}.svg"
        picture.write_text(render_project_svg(project), encoding="utf-8")
        ok, message = checker().check_path(picture)
        assert ok, f"{cloud}: {message}"
        if cloud == "azure":
            # the diagram file writes each subnet's badges, and they draw
            assert (
                ".badge(azure.NetworkSecurityGroups, label='nsg-aks')"
                ".badge(azure.RouteTables, label='rt-app-egress')"
                in spec.read_text(encoding="utf-8")
            )
            badged = {
                e.name.split(" · ")[0]: [b.label for b in e.badges]
                for e in project.topology.walk()
                if e.badges
            }
            assert badged == {
                "snet-shared": ["nsg-shared"],
                "snet-aks": ["nsg-aks", "rt-app-egress"],
                "snet-web": ["rt-app-egress"],
            }
            assert picture.read_text(encoding="utf-8").count('data-frame-badge=""') == 4


def _two_of_each(args: list[str]) -> Any:
    service, operation = args[0], args[1]
    region = args[args.index("--region") + 1] if "--region" in args else None
    if (service, operation) == ("sts", "get-caller-identity"):
        return {"Account": "1"}
    if (service, operation) == ("ecs", "list-clusters"):
        if region != "us-east-1":
            return {}
        return {
            "clusterArns": [
                "arn:aws:ecs:us-east-1:1:cluster/prod",
                "arn:aws:ecs:us-east-1:1:cluster/staging",
            ]
        }
    if (service, operation) == ("ecs", "list-services"):
        cluster = args[args.index("--cluster") + 1]
        return {"serviceArns": [f"{cluster}/api"]}
    if (service, operation) == ("ecs", "describe-services"):
        cluster = args[args.index("--cluster") + 1]
        arn = cluster.replace("cluster", "service") + "/api"
        return {"services": [{"serviceName": "api", "serviceArn": arn}]}
    if (service, operation) == ("lambda", "list-functions"):
        arn = f"arn:aws:lambda:{region}:1:function:handler"
        return {"Functions": [{"FunctionName": "handler", "FunctionArn": arn}]}
    return {}


def test_aws_keeps_every_resource_that_shares_a_name():
    estate = discover_aws(regions=["us-east-1", "eu-west-1"], runner=_two_of_each)
    services = estate.of_type("aws_ecs_service")
    functions = estate.of_type("aws_lambda_function")
    assert len(services) == 2
    assert len(functions) == 2
    assert {f.region for f in functions} == {"us-east-1", "eu-west-1"}
    addresses = [f.address for f in estate.resources]
    assert len(addresses) == len(set(addresses))
    assert "aws_ecs_service.api_2" in addresses
    assert "aws_lambda_function.handler_2" in addresses


def test_aws_reads_one_resource_reached_twice_once():
    def twice(args: list[str]) -> Any:
        if args[:2] == ["sts", "get-caller-identity"]:
            return {"Account": "1"}
        if args[:2] == ["s3api", "list-buckets"]:
            return {"Buckets": [{"Name": "logs"}, {"Name": "logs"}]}
        return {}

    estate = discover_aws(regions=["us-east-1"], runner=twice)
    assert [f.address for f in estate.of_type("aws_s3_bucket")] == ["aws_s3_bucket.logs"]
