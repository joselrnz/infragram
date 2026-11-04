"""An OCI landing zone with a container platform, written as it would be described.

A tenancy divided into compartments, a VCN split into a public subnet for the
load balancer and private subnets for the cluster and the database, and a
FastConnect circuit back to the corporate datacenter. This is the shape an
enterprise landing zone takes on Oracle Cloud: the security zone is a real
boundary with policies attached, not decoration.

It is also the long tail of the library proving itself -- OCI is one of the
nineteen installed, drawn from the same catalogs and checked by the same
checker as the big three.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/oracle_oke_landing_zone.py \
        --formats template,html,svg,png --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.frames import oracle
from infragram.nodes.oracle import (
    compute,
    connectivity,
    database,
    monitoring,
    network,
    security,
    storage,
)

with Diagram(
    "OKE landing zone on Oracle Cloud",
    "Users reach a public load balancer behind the OCI WAF; OKE runs the "
    "application from a private subnet and talks to an Autonomous Database in "
    "its own. A service gateway keeps object storage traffic off the internet, "
    "a FastConnect circuit carries the corporate datacenter, and Vault, Cloud "
    "Guard and Telemetry cover secrets, posture and metrics.",
    slug="oracle-oke-landing-zone",
) as diagram:
    users = shared.identity.PublicUsers("Users", "browsers and partners")
    corporate = connectivity.CustomerDatacenter("Corporate datacenter", "10.0.0.0/8")

    with oracle.Tenancy("Oracle Cloud"), oracle.Region("eu-frankfurt-1"):
        with oracle.Compartment("workloads"), oracle.Vcn("VCN 10.30.0.0/16"):
            # The edge above the workloads, so its wire drops straight down
            # rather than crossing the private subnets.
            with oracle.Subnet("Public subnet").column():
                waf = security.WAF("WAF", "OWASP rulesets")
                balancer = network.LoadBalancer("Load balancer", "HTTPS :443")

            with oracle.Subnet("Private subnet - application"):
                with oracle.Oke("OKE"):
                    workloads = compute.OKE("Application", "3 node pools")

            with oracle.Subnet("Private subnet - data").row():
                autonomous = database.Autonomous("Autonomous Database", "ATP - auto-scaling")
                gateway = network.ServiceGateway("Service gateway", "no internet egress")

        with oracle.Compartment("platform"):
            with oracle.SecurityZone("Security zone").row():
                vault = security.Vault("Vault", "keys and secrets")
                guard = security.CloudGuard("Cloud Guard", "posture and detectors")
            buckets = storage.ObjectStorage("Object Storage", "artifacts and backups")
            telemetry = monitoring.Telemetry("Telemetry", "metrics - logs - alarms")
            circuit = connectivity.FastConnect("FastConnect", "private circuit - 1 Gbps")

    users >> Edge("HTTPS") >> balancer
    waf >> Edge("inspects", dotted=True) >> balancer
    balancer >> Edge("HTTPS :8443") >> workloads
    workloads >> Edge("SQL*Net") >> autonomous
    workloads >> Edge("objects", dashed=True) >> gateway
    gateway >> Edge("private endpoint", dashed=True) >> buckets
    workloads >> Edge("secrets", dotted=True) >> vault
    workloads >> Edge("telemetry", dotted=True) >> telemetry
    guard >> Edge("watches", dotted=True) >> workloads
    corporate >> Edge("BGP") >> circuit
    circuit >> Edge("private") >> workloads


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
