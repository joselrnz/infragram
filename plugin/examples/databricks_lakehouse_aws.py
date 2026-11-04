"""A Databricks lakehouse on AWS, written as it would be described.

The workspace runs in the customer's AWS account: Auto Loader and a
Lakeflow pipeline land raw files from S3 into Delta tables (bronze, silver,
gold), Lakeflow Jobs schedules them on serverless compute, a SQL warehouse
serves AI/BI dashboards, and Unity Catalog governs every table and shares
the gold ones with a partner through Delta Sharing.

Databricks frames come from ``infragram.nodes.frames.databricks``, its
products from ``infragram.nodes.databricks``; the storage stays AWS's.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/databricks_lakehouse_aws.py \
        --formats template,html,svg,png --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.aws import storage
from infragram.nodes.databricks import analytics, engineering, governance, sharing
from infragram.nodes.frames import aws, databricks

with Diagram(
    "Databricks lakehouse on AWS",
    "Auto Loader and a Lakeflow pipeline land raw files from S3 into Delta tables; Lakeflow Jobs "
    "runs them on serverless compute; a SQL warehouse serves AI/BI dashboards; Unity Catalog "
    "governs every table and shares the gold ones through Delta Sharing.",
    slug="databricks-lakehouse-aws",
) as diagram:
    analysts = shared.identity.PublicUsers("Analysts", "dashboards and SQL")
    partner = shared.identity.PublicUser("Partner", "Delta Sharing recipient")

    with aws.Cloud("AWS Cloud"), aws.Region("us-east-1").row():
        raw = storage.SimpleStorageService("Raw landing", "S3 - JSON and CSV drops")
        lake = storage.SimpleStorageService("Lakehouse storage", "S3 - Delta tables")

        with databricks.Account("Databricks account").column().keep_order():
            with databricks.Workspace("Workspace - prod").row():
                with databricks.Compute("Serverless compute").column():
                    loader = engineering.AutoLoader("Auto Loader", "incremental ingest")
                    pipeline = engineering.SparkDeclarativePipelines(
                        "Lakeflow pipeline", "bronze - silver - gold"
                    )
                    jobs = engineering.LakeflowJobs("Lakeflow Jobs", "hourly schedule")
                warehouse = analytics.SQLWarehouse("SQL warehouse", "serverless - Photon")
                dashboards = analytics.AIBIDashboards("AI/BI dashboards", "sales and ops")
            with databricks.UnityCatalog("Unity Catalog").row():
                catalog = governance.UnityCatalog("Catalog: prod", "bronze - silver - gold schemas")
                lineage = governance.DataLineage("Lineage", "table and column")
                share = sharing.DeltaSharing("Delta Sharing", "gold tables")

    raw >> Edge("new files") >> loader
    loader >> Edge("bronze") >> pipeline
    jobs >> Edge("runs", dotted=True) >> pipeline
    pipeline >> Edge("Delta tables") >> lake
    warehouse >> Edge("queries") >> lake
    dashboards >> Edge("SQL") >> warehouse
    analysts >> Edge("HTTPS") >> dashboards
    catalog >> Edge("governs", dotted=True) >> lake
    catalog >> Edge("records", dotted=True) >> lineage
    share >> Edge("shares") >> partner


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
