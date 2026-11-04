"""RStudio and Shiny on AWS across two Availability Zones, from patterns.

Redrawn from a reference architecture. Shiny runs serverless on Fargate,
RStudio on EC2 in an Auto Scaling group, both in private subnets in both
zones behind their own load balancers. Data arrives by SFTP through Transfer
Family or straight into S3, is queried through Athena over JDBC, and every
compute tier mounts the same EFS file system, which is what makes the zones
interchangeable. One :class:`MultiAZ` recipe draws both zones; the
account-wide row is a :class:`Guardrails`.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose \\
        examples/aws_rstudio_shiny.py --formats template,html,svg,png \\
        --display icon --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.aws import (
    analytics,
    compute,
    containers,
    management_tools as mgmt,
    migration_modernization as migration,
    networking_content_delivery as net,
    security_identity as sec,
    storage,
)
from infragram.nodes.frames import aws, generic
from infragram.patterns.aws import Guardrails, MultiAZ, Zone

SLUG = "rstudio-shiny-analytics-platform"
TITLE = "RStudio and Shiny analytics platform"
DESCRIPTION = (
    "Shiny on Fargate and RStudio on EC2, each behind its own load balancer "
    "and spread across two Availability Zones. Data arrives by SFTP through "
    "Transfer Family or straight into S3, is queried through Athena over "
    "JDBC, and every compute tier mounts the same EFS file system."
)


def public_tier(subnet, zone: Zone) -> None:
    zone.part("nat", subnet >> net.VPCNATGateway("NAT Gateway", "outbound only"))


def private_tier(subnet, zone: Zone) -> None:
    zone.part(
        "ecs", subnet >> containers.ElasticContainerService("Amazon ECS", "Shiny task definitions")
    )
    zone.part("shiny", subnet >> containers.Fargate("AWS Fargate Shiny", "serverless task"))
    zone.part("shiny-2", subnet >> containers.Fargate("AWS Fargate Shiny", "serverless task"))
    group = subnet >> aws.AutoScaling("Auto Scaling group").row()
    zone.part("ec2", group >> compute.EC2("EC2 Server", "RStudio host"))
    zone.part(
        "rstudio",
        group >> containers.ElasticContainerRegistry("RStudio Containers", "pulled from ECR"),
    )
    zone.part("egress", subnet >> shared.security.Firewall("Egress Filtering", "allow-list only"))


# Cards: this drawing shows its gateways as bare marks and its services
# carded, and that distinction only exists in a document whose default is
# cards. Every other example follows the document default.
with Diagram(TITLE, DESCRIPTION, slug=SLUG, display="card") as diagram:
    devices = shared.compute.DesktopClient("devices", "analyst workstations")
    users = shared.identity.PublicUsers("users", "researchers")

    with aws.Cloud("AWS Cloud").column().keep_order():
        with aws.Region("Region").column().keep_order() as region:
            account = Guardrails(
                "Account-wide services",
                services=(
                    (net.Privatelink, "AWS PrivateLink", "private service access"),
                    (mgmt.Cloudtrail, "Amazon CloudTrail", "API audit trail"),
                    (sec.KeyManagementService, "AWS Key Management Service", "CMKs"),
                    (sec.Shield, "AWS Shield", "DDoS protection"),
                    (net.Route53, "Amazon Route 53", "public DNS"),
                    (sec.CertificateManager, "Amazon Certificate Manager", "TLS certs"),
                    (sec.Guardduty, "Amazon GuardDuty", "threat detection"),
                    (mgmt.Cloudwatch, "Amazon CloudWatch", "logs and metrics"),
                    (containers.ElasticContainerRegistry, "Amazon ECR", "container images"),
                ),
            ).attach(region)

            with aws.VPC("VPC").row().keep_order() as vpc:
                zones = MultiAZ(2, public=public_tier, private=private_tier).attach(vpc)
                # The reference stacks the ingress chain and the data services
                # down the middle of the VPC, between the two zones. Both zones
                # reach all of it.
                with generic.Network("Shared ingress and data").column().keep_order() as middle:
                    igw = net.VPCInternetGateway("Internet Gateway", "VPC ingress")
                    waf = sec.NetworkFirewall("AWS WAF", "managed rule groups")
                    elb_shiny = net.ElasticLoadBalancing("Amazon ELB Shiny", "HTTPS")
                    elb_rstudio = net.ElasticLoadBalancing("Amazon ELB RStudio", "HTTPS")
                    transfer = migration.TransferFamily("AWS Transfer Family", "managed SFTP")
                    bucket = storage.SimpleStorageService("Amazon S3", "landing and results")
                    datasync = migration.Datasync("AWS DataSync", "S3 to EFS")
                    athena = analytics.Athena("Amazon Athena", "SQL over S3")
                    efs = storage.EFS("Amazon EFS", "shared home directories")
                vpc.children.remove(middle)
                vpc.children.insert(1, middle)

    # --- ingestion and ingress ------------------------------------------
    devices >> Edge("SFTP File Ingestion") >> transfer
    users >> Edge("S3 File Ingestion") >> bucket
    account["amazon-route-53"] >> igw >> waf >> [elb_shiny, elb_rstudio]
    for letter in zones.letters:
        elb_shiny >> Edge("Shiny traffic") >> zones.part_for("shiny", letter)
        elb_rstudio >> Edge("RStudio traffic") >> zones.part_for("ec2", letter)
        (
            zones.part_for("ecs", letter)
            >> Edge(dotted=True)
            >> [zones.part_for("shiny", letter), zones.part_for("shiny-2", letter)]
        )
        zones.part_for("egress", letter) >> zones.part_for("nat", letter)
        zones.part_for("nat", letter) >> Edge(dashed=True) >> igw

    # --- data -------------------------------------------------------------
    transfer >> bucket >> [datasync, athena]
    datasync >> efs
    for letter in zones.letters:
        athena >> Edge("JDBC", dotted=True) >> zones.part_for("rstudio", letter)
        efs >> Edge("NFS Mount", dashed=True) >> zones.part_for("rstudio", letter)
        efs >> Edge(dashed=True) >> zones.part_for("shiny-2", letter)


if __name__ == "__main__":
    print(diagram.export(Path("dist"), display="both").html)
