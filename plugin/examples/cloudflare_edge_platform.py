"""Cloudflare edge platform in front of an on-premises origin, composed as code.

Shows the Cloudflare frames: an account holds the zone for one domain, and
the global network is a sibling frame holding the code that runs at the
edge. Traffic reaches the origin only through the edge.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/cloudflare_edge_platform.py \\
        --formats template,html,svg,png --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import cloudflare, infragram as shared, onprem
from infragram.nodes.frames import cloudflare as cf, onprem as dc

SLUG = "cloudflare-edge-platform"
TITLE = "Cloudflare edge platform with an on-premises origin"
DESCRIPTION = (
    "Visitors reach a Cloudflare zone where DNS, the WAF and the CDN sit in "
    "front of everything; Pages serves the front end, Workers the API and "
    "Workers AI the inference calls, all on the global network; cache misses "
    "and writes reach an origin in the corporate datacenter through a tunnel."
)

with Diagram(TITLE, DESCRIPTION, slug=SLUG) as diagram:
    visitors = shared.identity.PublicUsers("Visitors", "browsers and apps")

    with cf.Account("Cloudflare account"), cf.Zone("Zone · shop.example.com"):
        entry = cloudflare.Cloudflare("DNS, WAF and CDN", "proxied records")
    with cf.Network("Cloudflare global network"):
        pages = cloudflare.Pages("Pages", "storefront front end")
        workers = cloudflare.Workers("Workers", "API and routing")
        inference = cloudflare.WorkersAI("Workers AI", "product search")

    with dc.Datacenter("Corporate datacenter"), dc.SecurityZone("Origin zone"):
        tunnel = shared.networking.VPNTunnel("Cloudflare tunnel", "outbound only")
        origin = onprem.network.Nginx("Origin", "product catalogue")
        database = onprem.database.Postgresql("PostgreSQL", "orders")

    visitors >> Edge("HTTPS") >> entry
    entry >> Edge("static") >> pages
    entry >> Edge("/api/*") >> workers
    workers >> Edge("embeddings") >> inference
    workers >> Edge("cache miss", dashed=True) >> tunnel
    tunnel >> Edge("HTTP") >> origin
    origin >> Edge("SQL") >> database


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
