"""``discover:azure --source resource-graph``: the estate read in one query.

Resource Graph returns every resource with its ARM properties nested under
``properties`` at each level; the CLI's list calls print the same resources
flattened. What is held here is that the rows, flattened, give the ``az``
reader exactly what its list calls give it, so the Terraform types, values,
drawing and report are the same whichever way the estate was read:

- two ``az rest`` calls replace the reader's list calls, and nothing else
  reaches the CLI but ``az account show``;
- peerings and SQL databases, which the reader asks for per network and per
  server, are answered from the same rows;
- the CLI's and Resource Graph's spellings of an AKS pool's subnet agree;
- a refused query is a ``DiscoveryError`` naming the role it needs;
- the command and the MCP tool pass ``--source`` through.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from infragram.estate import draw
from infragram.estate.discover import CallError, DiscoveryError
from infragram.estate.discover.azure_graph import GraphRunner, discover_azure_graph, flatten

SUB = "11111111-2222-3333-4444-555555555555"
RG = f"/subscriptions/{SUB}/resourceGroups"
VNET = f"{RG}/rg-net/providers/Microsoft.Network/virtualNetworks/vnet-app"
SNET = f"{VNET}/subnets/snet-app"
NIC = f"{RG}/rg-app/providers/Microsoft.Network/networkInterfaces/vm1-nic"
HUB = f"{RG}/rg-hub/providers/Microsoft.Network/virtualNetworks/vnet-hub"
SQL = f"{RG}/rg-app/providers/Microsoft.Sql/servers/sql1"


def arm(
    group: str, arm_type: str, name: str, props: dict[str, Any] | None = None, **extra: Any
) -> dict[str, Any]:
    provider, _, path = arm_type.partition("/")
    return {
        "id": f"{RG}/{group}/providers/{provider}/{path}/{name}",
        "name": name,
        "type": arm_type.lower(),
        "kind": "",
        "location": "eastus2",
        "resourceGroup": group,
        "subscriptionId": SUB,
        "sku": None,
        "tags": {"env": "prod"},
        "properties": props or {},
        **extra,
    }


ROWS = [
    arm(
        "rg-net",
        "Microsoft.Network/virtualNetworks",
        "vnet-app",
        {
            "addressSpace": {"addressPrefixes": ["10.1.0.0/16"]},
            "subnets": [
                {"id": SNET, "name": "snet-app", "properties": {"addressPrefix": "10.1.1.0/24"}}
            ],
            "virtualNetworkPeerings": [
                {
                    "id": f"{VNET}/virtualNetworkPeerings/to-hub",
                    "name": "to-hub",
                    "properties": {"remoteVirtualNetwork": {"id": HUB}},
                }
            ],
        },
    ),
    arm(
        "rg-app",
        "Microsoft.Network/networkInterfaces",
        "vm1-nic",
        {
            "ipConfigurations": [
                {
                    "name": "ipconfig1",
                    "properties": {"subnet": {"id": SNET}, "privateIPAddress": "10.1.1.4"},
                }
            ],
        },
    ),
    arm(
        "rg-app",
        "Microsoft.Compute/virtualMachines",
        "vm1",
        {
            "hardwareProfile": {"vmSize": "Standard_D2s_v5"},
            "storageProfile": {"osDisk": {"osType": "Linux"}},
            "networkProfile": {"networkInterfaces": [{"id": NIC}]},
        },
    ),
    arm(
        "rg-app",
        "Microsoft.ContainerService/managedClusters",
        "aks1",
        {
            "agentPoolProfiles": [
                {"name": "system", "vmSize": "D4s", "vnetSubnetID": SNET},
                {"name": "user", "vmSize": "D8s", "vnetSubnetID": SNET},
            ],
        },
    ),
    arm(
        "rg-net",
        "Microsoft.Network/networkSecurityGroups",
        "nsg-app",
        {
            "securityRules": [
                {
                    "name": "allow-https",
                    "properties": {
                        "priority": 100,
                        "direction": "Inbound",
                        "access": "Allow",
                        "protocol": "Tcp",
                        "destinationPortRange": "443",
                    },
                }
            ],
            "subnets": [{"id": SNET}],
        },
    ),
    arm(
        "rg-app", "Microsoft.Web/sites", "app1", {"virtualNetworkSubnetId": SNET}, kind="app,linux"
    ),
    arm("rg-app", "Microsoft.Web/sites", "func1", {}, kind="functionapp,linux"),
    arm("rg-app", "Microsoft.Sql/servers", "sql1"),
    {
        **arm("rg-app", "Microsoft.Sql/servers", "sql1"),
        "id": f"{SQL}/databases/orders",
        "name": "orders",
        "type": "microsoft.sql/servers/databases",
        "sku": {"name": "GP_Gen5_2"},
    },
    {
        **arm("rg-app", "Microsoft.Sql/servers", "sql1"),
        "id": f"{SQL}/databases/master",
        "name": "master",
        "type": "microsoft.sql/servers/databases",
    },
]
GROUPS = [
    {"id": f"{RG}/{g}", "name": g, "location": "eastus2", "subscriptionId": SUB}
    for g in ("rg-net", "rg-app")
]


class FakeAz:
    """``az account show`` and ``az rest``; any other call fails the test."""

    def __init__(self, pages: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.bodies: list[dict[str, Any]] = []
        self.pages = pages

    def __call__(self, args: list[str]) -> Any:
        self.calls.append(args)
        if args[:2] == ["account", "show"]:
            return {"id": SUB, "name": "Production"}
        if args[0] == "rest":
            body = json.loads(Path(args[args.index("--body") + 1][1:]).read_text("utf-8"))
            self.bodies.append(body)
            if body["query"].startswith("resourcecontainers"):
                return {"data": GROUPS}
            if self.pages is not None:
                return self.pages.pop(0)
            return {"data": ROWS}
        raise AssertionError(f"unexpected az call {args}")


def test_the_rows_reach_the_reader_as_its_list_calls_would() -> None:
    fake = FakeAz()
    estate = discover_azure_graph(runner=fake)
    by = {found.address: found for found in estate.resources}
    types = {found.type for found in estate.resources}
    assert [call[0] for call in fake.calls].count("rest") == 2
    assert {call[0] for call in fake.calls} == {"account", "rest"}
    assert by["azurerm_subnet.snet-app"].values["address_prefixes"] == ["10.1.1.0/24"]
    assert by["azurerm_virtual_network_peering.to-hub"].values["remote_virtual_network_id"] == HUB
    assert (
        by["azurerm_network_interface.vm1-nic"].values["ip_configuration"][0]["subnet_id"] == SNET
    )
    assert by["azurerm_linux_virtual_machine.vm1"].values["network_interface_ids"] == [NIC]
    pool = by["azurerm_kubernetes_cluster.aks1"].values["default_node_pool"][0]
    assert pool["vnet_subnet_id"] == SNET
    assert "azurerm_kubernetes_cluster_node_pool" in types
    rule = by["azurerm_network_security_group.nsg-app"].values["security_rule"][0]
    assert rule["destination_port_range"] == "443"
    assert "azurerm_subnet_network_security_group_association" in types
    assert {"azurerm_linux_web_app", "azurerm_linux_function_app"} <= types
    assert "azurerm_mssql_database.orders" in by
    assert "azurerm_mssql_database.master" not in by
    assert "azurerm_resource_group.rg-net" in by
    assert any("Resource Graph" in note for note in estate.notes)


def test_what_it_reads_draws_like_a_list_read() -> None:
    drawing = draw(discover_azure_graph(runner=FakeAz()))
    assert drawing is not None


def test_the_query_is_read_page_by_page() -> None:
    fake = FakeAz(pages=[{"data": ROWS[:3], "$skipToken": "next"}, {"data": ROWS[3:]}])
    runner = GraphRunner(fake, SUB)
    assert sum(len(rows) for rows in runner.by_type.values()) == len(ROWS)
    bodies = [body for body in fake.bodies if not body["query"].startswith("resourcecontainers")]
    assert bodies[1]["options"]["$skipToken"] == "next"


def test_flatten_merges_every_level_of_properties() -> None:
    row = flatten({"id": "x", "properties": {"subnets": [{"id": "s", "properties": {"a": 1}}]}})
    assert row == {"id": "x", "subnets": [{"id": "s", "a": 1}]}


def test_a_refused_query_names_the_role_it_needs() -> None:
    def refuse(args: list[str]) -> Any:
        if args[0] == "rest":
            raise CallError("az rest", "Forbidden: AccessDenied")
        return {"id": SUB}

    with pytest.raises(DiscoveryError, match="Reader role"):
        discover_azure_graph(runner=refuse)


def test_the_command_and_the_mcp_tool_pass_the_source_through() -> None:
    from infragram.mcp import TOOLS

    tool = next(tool for tool in TOOLS if tool.name == "discover")
    argv = tool.argv({"cloud": "azure", "source": "resource-graph"})
    assert argv[:1] == ["discover:azure"] and "--source" in argv
    assert argv[argv.index("--source") + 1] == "resource-graph"
