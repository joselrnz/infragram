"""Zone-redundant web application behind Azure Front Door, with a warm standby.

Redrawn from the reliable web app pattern. Front Door Premium terminates TLS
at the edge with WAF and reaches the App Service origin over Private Link,
so the origin has no public endpoint. Inside the region every tier is zone
redundant and every data service is reached over private endpoints; a second
region holds a warm standby and the SQL failover group's secondary. What the
drawing has to make legible:

* the only public surface is Front Door; DNS points at it and DDoS Protection
  covers the public IPs;
* App Service, SQL, Redis and Storage are zone redundant in the primary
  region and reached over private endpoints from the integration subnet;
* a failover group replicates SQL to the standby region, where a second App
  Service waits as origin priority 2;
* managed identity, Key Vault, Application Insights and Log Analytics
  complete the picture.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose \\
        examples/azure_web_app_front_door.py --formats template,html,svg,png \\
        --display both --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.azure import (
    app_services,
    databases,
    general,
    identity,
    monitor,
    networking as net,
    other,
    security,
    storage,
)
from infragram.nodes.frames import azure

SLUG = "azure-web-app-front-door"
TITLE = "Zone-redundant web app behind Front Door"
DESCRIPTION = (
    "Front Door Premium is the only public surface: WAF and TLS at the edge, "
    "Private Link to an App Service origin with no public endpoint. In the "
    "primary region App Service, Azure SQL, Cache for Redis and Storage are "
    "zone redundant and reached over private endpoints from the integration "
    "subnet; a failover group replicates SQL to a second region where a warm "
    "standby App Service waits as origin priority 2. Managed identity, Key "
    "Vault, Application Insights and Log Analytics complete the picture."
)

with Diagram(TITLE, DESCRIPTION, slug=SLUG) as diagram:
    users = shared.identity.PublicUsers("Users", "browsers · worldwide")
    mobile = general.Mobile("Mobile clients", "iOS · Android")

    with azure.Subscription("Production subscription").column().keep_order():
        # --- the global edge --------------------------------------------
        with azure.ResourceGroup("rg-global-edge").row():
            dns = net.DNSZones("Azure DNS", "contoso.com · CNAME to Front Door")
            front_door = net.FrontDoorAndCDNProfiles(
                "Azure Front Door Premium", "WAF · TLS · caching · Private Link origins"
            )
            ddos = net.DdosProtectionPlans("DDoS Protection", "network protection · public IPs")

        # --- the primary region -----------------------------------------
        with azure.Region("East US 2 · primary").row():
            with azure.ResourceGroup("rg-web-prod").column():
                with azure.VNet("VNet · 10.20.0.0/16").row():
                    with azure.Subnet("snet-appservice-integration"):
                        app = app_services.AppServices(
                            "App Service", "P1v3 ×3 · zone redundant · VNet integration"
                        ).sizing(sku="P1v3", count=3)
                    with azure.Subnet("snet-private-endpoints"):
                        endpoints = other.PrivateEndpoints(
                            "Private endpoints", "SQL · Redis · Storage · Key Vault"
                        )
            with azure.ResourceGroup("rg-data-prod").column().keep_order():
                sql = databases.SQLDatabase(
                    "Azure SQL Database", "Business Critical · zone redundant · failover group"
                ).sizing(tier="Business Critical", zone_redundant="yes")
                redis = databases.CacheRedis(
                    "Cache for Redis", "Premium · zone redundant · session state"
                ).sizing(tier="Premium")
                blobs = storage.StorageAccounts(
                    "Storage account", "ZRS · static assets · uploads"
                ).sizing(redundancy="ZRS")
                vault = security.KeyVaults("Key Vault", "connection strings · certificates")
            with azure.ResourceGroup("rg-ops-prod").column().keep_order():
                app_identity = identity.ManagedIdentities(
                    "Managed identity", "App Service · no secrets in config"
                )
                app_insights = monitor.ApplicationInsightsMonitor(
                    "Application Insights", "requests · dependencies · availability tests"
                )
                logs = monitor.LogAnalyticsWorkspacesMonitor(
                    "Log Analytics", "diagnostics · alerts"
                )

        # --- the standby region -----------------------------------------
        with (
            azure.Region("Central US · standby").row(),
            azure.ResourceGroup("rg-web-standby").row(),
        ):
            standby_app = app_services.AppServices(
                "App Service · warm standby", "P1v3 ×1 · origin priority 2"
            ).sizing(sku="P1v3", count=1)
            standby_sql = databases.SQLDatabase(
                "Azure SQL · geo-secondary", "readable · failover group"
            ).sizing(tier="Business Critical")

    # --- what talks to what ---------------------------------------------
    users >> Edge("HTTPS 443") >> front_door
    mobile >> Edge("HTTPS 443 · API") >> front_door
    dns >> Edge("CNAME · TXT validation", dotted=True) >> front_door
    ddos >> Edge("covers public IPs", dotted=True) >> front_door
    front_door >> Edge("Private Link origin · priority 1") >> app
    front_door >> Edge("origin priority 2 · health probes", dashed=True) >> standby_app
    app >> Edge("VNet integration · private DNS") >> endpoints
    endpoints >> Edge("TDS 1433", dotted=True) >> sql
    endpoints >> Edge("TLS 6380", dotted=True) >> redis
    endpoints >> Edge("blob · HTTPS", dotted=True) >> blobs
    endpoints >> Edge("secrets", dotted=True) >> vault
    app >> Edge("token", dotted=True) >> app_identity
    app_identity >> Edge("RBAC · Key Vault Secrets User", dotted=True) >> vault
    sql >> Edge("failover group · async replication", dashed=True) >> standby_sql
    standby_app >> Edge("read-only until failover", dotted=True) >> standby_sql
    app >> Edge("telemetry", dotted=True) >> app_insights
    app_insights >> Edge("workspace-based", dotted=True) >> logs
    front_door >> Edge("access + WAF logs", dotted=True) >> logs


if __name__ == "__main__":
    print(diagram.export(Path("dist"), display="both").html)
