"""Three-tier web application on AWS, written as it would be described.

Frames are ``with`` blocks and whatever is written inside one belongs to it;
an arrow between two nodes is a wire. Frames come from
``infragram.nodes.frames.aws``, services from ``infragram.nodes.aws``, the
users from the shared library, and the document is inferred: components,
providers, kind and placement.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/aws_three_tier.py \
        --formats template,html,svg,png --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.aws import (
    compute,
    databases,
    management_tools,
    networking_content_delivery as net,
    security_identity as security,
    storage,
)
from infragram.nodes.frames import aws

with Diagram(
    "Three-tier web application on AWS",
    "Users reach an Application Load Balancer behind AWS WAF in the public subnets; "
    "an EC2 Auto Scaling group serves the application from the private subnets and "
    "talks to a Multi-AZ PostgreSQL on RDS; assets live in S3, secrets in Secrets "
    "Manager, and CloudWatch watches the estate.",
    slug="aws-three-tier-composed",
) as diagram:
    users = shared.identity.PublicUsers("Users", "browsers and apps")

    with aws.Cloud("AWS Cloud"), aws.Region("us-east-1"):
        with aws.VPC("VPC 10.0.0.0/16"):
            # WAF over the load balancer, so the balancer sits directly above
            # the web servers and its wire drops straight onto them.
            with aws.PublicSubnet("Public subnets").column():
                waf = security.WAF("AWS WAF", "managed rule groups")
                alb = net.ElasticLoadBalancing("Application Load Balancer", "HTTPS :443")
            with aws.PrivateSubnet("Private subnets").row():
                # what --prices prices it as; the region is the frame's
                web = compute.EC2("Web servers", "Auto Scaling - 3 x m6i.large").sizing(
                    instance_type="m6i.large", count=3
                )
                db = databases.RDS("PostgreSQL", "Multi-AZ - db.r6g.large")

        bucket = storage.SimpleStorageService("Assets", "static content - versioned")
        secrets = security.SecretsManager("Secrets Manager", "database credentials")
        watch = management_tools.Cloudwatch("CloudWatch", "metrics - logs - alarms")

    users >> Edge("HTTPS") >> alb
    waf >> Edge("inspects", dotted=True) >> alb
    alb >> Edge("HTTP :8080") >> web
    web >> Edge("SQL") >> db
    web >> Edge("objects", dashed=True) >> bucket
    web >> Edge("credentials", dotted=True) >> secrets
    web >> Edge("telemetry", dotted=True) >> watch


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
