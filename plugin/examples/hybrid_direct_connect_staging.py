"""Private staging landing zone fed from an on-premises DataStage estate.

Built from patterns so the shape is stated once: the on-premises edge and
the Direct Connect circuit come from :class:`DirectConnectUplink`, the two
Availability Zones from one :class:`MultiAZ` recipe, the detection services
from :class:`Guardrails`. What the drawing has to make legible:

* nothing in the VPC is reachable from the internet: no internet gateway,
  no NAT, no public subnet anywhere in it;
* the only path in is a dedicated Direct Connect circuit terminating on a
  Transit Gateway over a private virtual interface, MACsec on the wire;
* every AWS service the workload touches is reached through a VPC endpoint;
* every store is encrypted with a customer-managed KMS key;
* the database is Multi-AZ with a synchronous standby.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose \\
        examples/hybrid_direct_connect_staging.py --formats template,html,svg,png \\
        --display both --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared, onprem
from infragram.nodes.aws import (
    compute,
    databases,
    management_tools as mgmt,
    networking_content_delivery as net,
    security_identity as sec,
    storage,
)
from infragram.nodes.frames import aws, generic, onprem as dc
from infragram.patterns.aws import EndpointSubnet, Guardrails, MultiAZ, Zone
from infragram.patterns.hybrid import DirectConnectUplink

SLUG = "private-dx-staging-platform"
TITLE = "Private Direct Connect staging platform"
DESCRIPTION = (
    "IBM InfoSphere DataStage extracts from an on-premises SQL Server and "
    "lands into an AWS staging environment over a dedicated Direct Connect "
    "private virtual interface. The VPC has no internet gateway: S3, KMS and "
    "Secrets Manager are reached through VPC endpoints, the staging tier and "
    "the Multi-AZ RDS instance each sit in their own security group, and "
    "GuardDuty, CloudTrail, Security Hub, Macie and Config watch the account."
)

#: The interface endpoints every zone carries; each draws as the service it
#: fronts so the two are told apart at a glance.
ENDPOINTS = (
    (sec.KeyManagementService, "KMS endpoint", "interface · private DNS"),
    (sec.SecretsManager, "Secrets endpoint", "interface · private DNS"),
)


def private_tier(subnet, zone: Zone) -> None:
    """What every zone's private side holds: endpoints, the landing node in
    its own security group, and the database in another."""
    endpoints = EndpointSubnet(zone.letter, ENDPOINTS, name="Private subnet · endpoints")
    endpoints.attach(subnet)
    zone.part("kms-endpoint", endpoints["kms-endpoint"])
    zone.part("secrets-endpoint", endpoints["secrets-endpoint"])
    ingest = subnet >> aws.SecurityGroup("Security group · staging")
    zone.part("landing", ingest >> compute.EC2("DataStage landing node", "parallel writes"))
    data = subnet >> aws.SecurityGroup("Security group · database")
    primary = zone.letter == "A"
    zone.part(
        "rds",
        data
        >> databases.RDS(
            "RDS primary" if primary else "RDS standby",
            "SQL Server · encrypted" if primary else "synchronous · failover",
        ),
    )


with Diagram(TITLE, DESCRIPTION, slug=SLUG) as diagram:
    # --- on-premises --------------------------------------------------------
    uplink = DirectConnectUplink("Corporate data center")
    site = uplink["site"]
    with site, dc.SecurityZone("Source systems").row():
        sqlserver = onprem.database.Mssql("SQL Server 2022", "OLTP source · CDC enabled")
        datastage = shared.integration.SyncProcess(
            "IBM InfoSphere DataStage", "parallel ETL engine"
        )
        catalog = shared.databases.SearchIndex(
            "Information Governance Catalog", "lineage and glossary"
        )
    # The site's children were added after the frame: keep the sources above
    # the edge network by moving the edge to the end.
    site.children.remove(uplink["edge"])
    site.children.append(uplink["edge"])

    # --- AWS --------------------------------------------------------------
    with aws.Cloud("AWS Cloud").column().keep_order() as cloud:
        with generic.Environment("Environment · staging").column():
            with aws.Region("Region · us-east-1").column().keep_order():
                tgw = net.TransitGateway("Transit Gateway", "private VIF · no internet route")
                with aws.VPC("VPC · 10.40.0.0/16 · no internet gateway").row().keep_order() as vpc:
                    s3_endpoint = net.VPCEndpoints(
                        "S3 gateway endpoint", "route table · policy-scoped"
                    )
                    zones = MultiAZ(2, private=private_tier).attach(vpc)
                with generic.SecurityZone("Encrypted service tier").row():
                    bucket = storage.SimpleStorageService(
                        "S3 staging bucket", "SSE-KMS · versioned · block public access"
                    )
                    kms = sec.KeyManagementService("KMS", "customer-managed key")
                    secrets = sec.SecretsManager("Secrets Manager", "rotated credentials")
        audit = Guardrails(
            "Detection and audit",
            services=(
                (sec.Guardduty, "GuardDuty", "threat detection"),
                (mgmt.Cloudtrail, "CloudTrail", "org trail · immutable"),
                (sec.SecurityHub, "Security Hub", "posture findings"),
                (sec.Macie, "Macie", "PII discovery in S3"),
                (mgmt.Config, "Config", "drift and compliance"),
            ),
        ).attach(cloud)

    # --- what talks to what -----------------------------------------------
    sqlserver >> Edge("CDC extract") >> datastage
    datastage >> Edge("lineage", dotted=True) >> catalog
    datastage >> Edge("TLS 1.3") >> uplink["firewall"]
    uplink["circuit"] >> Edge("10 Gbps · transit VIF", dashed=True) >> tgw
    for landing in zones.each("landing"):
        tgw >> landing >> s3_endpoint
    s3_endpoint >> Edge("staged parquet") >> bucket
    zones.part_for("landing", "A") >> Edge("bulk load") >> zones.part_for("rds", "A")
    for letter in zones.letters:
        (
            zones.part_for("landing", letter)
            >> Edge("credentials", dotted=True)
            >> zones.part_for("secrets-endpoint", letter)
        )
    zones.part_for("secrets-endpoint", "A") >> Edge(dotted=True) >> secrets
    zones.part_for("kms-endpoint", "A") >> Edge(dotted=True) >> kms
    (
        zones.part_for("rds", "A")
        >> Edge("synchronous", dashed=True, both=True)
        >> zones.part_for("rds", "B")
    )
    kms >> Edge("CMK", dotted=True) >> [bucket, zones.part_for("rds", "A")]
    audit["macie"] >> Edge("scans", dotted=True) >> bucket
    audit["cloudtrail"] >> Edge("logs", dotted=True) >> bucket


if __name__ == "__main__":
    print(diagram.export(Path("dist"), display="both").html)
