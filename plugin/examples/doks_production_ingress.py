"""Production ingress on DigitalOcean Kubernetes, drawn with panels.

Shows panels (compose.md, Panels): boxes that carry their own facts as
compartments side by side and stacked, several detail lines, an ellipse for
the customer, a hexagon for the managed control plane, notes for a contract
and a caveat, and tones that mean something, which the legend names. The
load balancer's public front end stands beside its back ends, with what must
never happen under both; each worker carries its pod.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/doks_production_ingress.py \\
        --formats template,html,svg,png --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import Box
from infragram.nodes.frames import digitalocean as do

SLUG = "doks-production-ingress"
TITLE = "Production ingress, load balancing, nodes and pods"
DESCRIPTION = (
    "One public application front end through a proxied edge and a regional "
    "load balancer to a managed gateway, private DOKS networks, isolated "
    "workers without public addresses, and egress through a NAT gateway."
)
#: The request path, the control and egress paths.
REQUEST = "#cc7631"
CONTROL = "#4a77ad"
EGRESS = "#7a5cb0"

with Diagram(
    TITLE,
    DESCRIPTION,
    slug=SLUG,
    display="card",
    legend=(("solid", "customer request"), ("dashed", "control, egress or overflow")),
    tones={
        "edge": "public edge / ingress",
        "private": "private VPC / Kubernetes",
        "internal": "cluster-internal service / managed data",
        "correction": "target correction required",
        "blocker": "launch blocker",
    },
) as diagram:
    customer = (
        Box("1 · Customer", "HTTPS 443\npayments only when billing is enabled")
        .shape("ellipse")
        .tone("internal")
    )
    edge = (
        Box(
            "2 · Proxied edge",
            "public DNS answers with the edge's anycast\nWAF · CDN · DDoS · rate controls",
        )
        .tone("edge")
        .section(
            "Configured origin = regional load balancer",
            "a DNS-only record is forbidden",
            tone="edge",
        )
    )
    with do.Region("DigitalOcean region"):
        balancer = (
            Box(
                "3 · Public regional HTTP load balancer",
                "one Gateway-owned resource · two size units",
            )
            .tone("edge")
            .section(
                "Public frontend",
                "HTTPS 443 · Full (strict)",
                "TLS passed through to the gateway",
                tone="edge",
            )
            .section(
                "DOKS gateway backends",
                "controller-managed health-checked targets",
                "node interface placement must be inspected",
                tone="private",
                beside=True,
            )
            .section(
                "Direct origin access must fail",
                "origin restriction still needs proof",
                tone="blocker",
            )
        )
        control = (
            Box(
                "Managed DOKS control plane",
                "separate managed API · HA\nOIDC · RBAC · API firewall",
            )
            .shape("hexagon")
            .tone("managed")
        )
        with do.VPC("Private regional VPC · VPC-native DOKS").column().keep_order():
            gateway = (
                Box(
                    "4 · Managed Cilium gateway",
                    "TLS termination + origin certificate · one HTTPS listener\nlive placement must be verified",
                )
                .tone("private")
                .section(
                    "5 · HTTPRoute",
                    "exact hostname + path + backendRef",
                    "unknown route = denied",
                    tone="private",
                )
            )
            service = Box(
                "6 · Service / web · ClusterIP :80",
                "cluster-internal VIP / ready-endpoint distribution\nnever customer-addressed\ntargetPort :3000",
            ).tone("internal")
            with do.NodePool("App pool · autoscale 2→4"):
                workers = [
                    Box(f"App worker {letter}", "2 vCPU · 4 GiB · pod CIDR slice")
                    .tone("private")
                    .section(
                        "Isolated · VPC address only",
                        "no public IP · no routine SSH",
                        tone="private",
                    )
                    .section(f"Pod · web #{number} · :3000", note, tone="private")
                    for letter, number, note in (
                        ("A", 1, "ready endpoint"),
                        ("B", 2, "separate failure domain"),
                    )
                ]
                elastic = (
                    Box("Elastic app workers", "same isolated-worker contract")
                    .tone("neutral")
                    .section("HPA / reschedule / overflow", "no permanent pod assumption")
                )
            with do.NodePool("Jobs pool · autoscale 2→4 · tainted for jobs"):
                jobs = (
                    Box(
                        "Jobs worker A · 4 vCPU / 8 GiB",
                        "isolated · VPC address only · no public IP",
                    )
                    .tone("private")
                    .section("Inference proxy · :8443 TLS", "absent unless enabled", tone="blocker")
                    .section("Search ingest · hourly", "absent unless enabled", tone="blocker")
                    .section(
                        "Database export · daily",
                        "required before production data",
                        tone="correction",
                    )
                )
                Box(
                    "Jobs worker B · minimum + elastic",
                    "replacement target / bounded overflow\nsingleton behaviour is per workload",
                ).tone("private")
            nat = Box(
                "VPC NAT gateway",
                "outbound static IP only\negress bypasses the ClusterIP · never inbound",
            ).tone("managed")
            Box(
                "Network contract",
                "gateway-only backend ingress · default deny\nno public NodePort",
            ).shape("note").tone("correction")
    data = Box(
        "Managed data + external providers",
        "PostgreSQL: primary + standby · private verify-full TLS\n"
        "Valkey: primary + standby · private VPC\n"
        "outbound mail through the NAT's approved source IP",
    ).tone("neutral")
    Box(
        "Current implementation: NO-GO",
        "1. networking, NAT and the Gateway exist only in source\n"
        "2. origin certificate and direct-origin denial are unproven\n"
        "3. database restore and wrong-tenant tests are incomplete\n"
        "4. control-plane firewall and recovery drills are unresolved",
    ).tone("blocker")

    customer >> Edge("HTTPS", color=REQUEST, width=2) >> edge
    edge >> Edge("HTTPS 443 · Full (strict)", color=REQUEST, width=2) >> balancer
    balancer >> Edge("controller-managed backend", color=REQUEST, width=2) >> gateway
    gateway >> Edge("approved backendRef", color=REQUEST, width=2) >> service
    for worker in workers:
        service >> Edge(color=REQUEST, width=2) >> worker
    service >> Edge("overflow", dashed=True, color=CONTROL) >> elastic
    jobs >> Edge("pod egress", dashed=True, color=EGRESS) >> nat
    nat >> Edge("SNAT · TLS", dashed=True, color=EGRESS) >> data
    gateway - Edge(dotted=True, color=EGRESS) - control


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
