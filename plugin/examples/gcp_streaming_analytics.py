"""A streaming analytics platform on Google Cloud, written as it would be described.

Events arrive at a global load balancer, are served by Cloud Run and GKE,
published to Pub/Sub, shaped by Dataflow, landed in BigQuery, and read in
Looker. The operational store is Cloud SQL; Cloud Composer schedules the
batch side.

Frames are ``with`` blocks and whatever is written inside one belongs to it;
an arrow between two nodes is a wire. Frames come from
``infragram.nodes.frames.gcp``, services from ``infragram.nodes.gcp``, the
users from the shared library, and the document is inferred: components,
providers, kind and placement.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/gcp_streaming_analytics.py \
        --formats template,html,svg,png --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.frames import gcp
from infragram.nodes.gcp import core_products as core, legacy

with Diagram(
    "Streaming analytics on Google Cloud",
    "Events reach a global HTTPS load balancer behind Cloud Armor and Cloud CDN; "
    "Cloud Run serves the API and GKE runs the stream processors. Pub/Sub carries "
    "the events, Dataflow shapes them, BigQuery stores them and Looker reads them. "
    "Cloud SQL holds operational state, Cloud Composer schedules the batch jobs, "
    "and Secret Manager and Cloud Monitoring cover credentials and telemetry.",
    slug="gcp-streaming-analytics",
) as diagram:
    users = shared.identity.PublicUsers("Users", "browsers, apps and devices")

    with gcp.Organization("Google Cloud"), gcp.Project("analytics-prod"):
        with gcp.Region("us-central1"):
            # The edge stacked above the workloads, so its wire drops straight
            # onto the services underneath rather than crossing the frame.
            with gcp.Subnet("Edge").column():
                armor = legacy.CloudArmor("Cloud Armor", "WAF and DDoS policies")
                cdn = legacy.CloudCDN("Cloud CDN", "cached static responses")
                balancer = legacy.CloudLoadBalancing("Global load balancer", "HTTPS :443")

            with gcp.Subnet("Serving").row():
                api = core.CloudRun("API service", "scale to zero")
                with gcp.GKE("GKE Autopilot"):
                    processors = core.GKE("Stream processors", "3 workloads")

            with gcp.Subnet("Data").row():
                events = legacy.Pubsub("Pub/Sub", "events topic - 7 days")
                pipeline = legacy.Dataflow("Dataflow", "streaming pipeline")
                warehouse = core.Bigquery("BigQuery", "partitioned tables")

            with gcp.Subnet("Platform").row():
                operational = core.CloudSQL("Cloud SQL", "PostgreSQL - HA")
                schedule = legacy.CloudComposer("Cloud Composer", "nightly batch DAGs")
                looker = core.Looker("Looker", "dashboards and explores")

        bucket = core.CloudStorage("Cloud Storage", "raw event archive")
        secrets = legacy.SecretManager("Secret Manager", "service credentials")
        watch = legacy.CloudMonitoring("Cloud Monitoring", "metrics - logs - alerts")

    users >> Edge("HTTPS") >> balancer
    armor >> Edge("inspects", dotted=True) >> balancer
    cdn >> Edge("caches", dashed=True) >> balancer
    balancer >> Edge("HTTPS") >> api
    balancer >> Edge("HTTPS") >> processors
    api >> Edge("publish") >> events
    processors >> Edge("publish") >> events
    events >> Edge("subscribe") >> pipeline
    pipeline >> Edge("load") >> warehouse
    warehouse >> Edge("query") >> looker
    api >> Edge("SQL") >> operational
    schedule >> Edge("triggers", dotted=True) >> pipeline
    pipeline >> Edge("archive", dashed=True) >> bucket
    api >> Edge("credentials", dotted=True) >> secrets
    processors >> Edge("telemetry", dotted=True) >> watch


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
