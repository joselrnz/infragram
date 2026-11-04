"""AWS enterprise application: global, event-driven, active/active in two Regions.

Route 53 latency records send each user to the nearest healthy Region's API
Gateway, which reaches the EKS services through a VPC link and an internal
ALB. An order is written to a DynamoDB global table and announced on
EventBridge through a global endpoint; a rule buffers it in SQS for the
Lambda handlers, which publish the result back to EventBridge, and an API
destination delivers it to partners. EKS streams the clickstream to MSK, and
Data Firehose lands it in the S3 lake for Athena. Platform accounts hold
security, observability and the delivery pipeline.

Each service keeps its own recovery behaviour, and the captions say which:
DynamoDB global tables and MSK (with MSK Replicator both ways) are active in
both Regions; the EventBridge global endpoint replicates events and fails the
bus over on a Route 53 health check; SQS queues are regional, so messages left
in a failed Region wait there; Aurora Global Database has one writer; the
Cognito replica serves sign-in only.

Checked against AWS documentation on 2026-11-05: EventBridge global endpoints
(asynchronous event replication; RTO and RPO 360 s, at most 420 s, with the
prescribed alarm), MSK Replicator active-active (asynchronous, at least once:
consumers must tolerate duplicates), Cognito multi-Region replication
(one-way; the replica serves sign-in, not sign-up or password reset), DynamoDB
global tables, Aurora Global Database failover, S3 Replication Time Control.
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import Box, Group, infragram as shared
from infragram.nodes.aws import (
    analytics,
    application_integration as integration,
    compute,
    containers,
    databases,
    developer_tools,
    management_tools as management,
    networking_content_delivery as net,
    security_identity as security,
    storage,
)
from infragram.nodes.frames import aws


def region(name: str, cidr: str, role: str):
    """One application Region: the VPC, messaging and data."""
    primary = role == "primary"
    with aws.Region(name).column().keep_order():
        with Group(f"Edge · {name.split(' ')[0]}", "group").row().keep_order():
            api = net.APIGateway("API Gateway", "regional · custom domain")
            cognito = security.Cognito(
                "Cognito user pool", "primary" if primary else "replica · sign-in only"
            )
        with aws.VPC(f"VPC {cidr}").row().keep_order():
            with aws.PrivateSubnet("Private subnets · app"):
                alb = net.ElasticLoadBalancingApplicationLoadBalancer(
                    "Internal ALB", "VPC link target"
                )
                eks = containers.ElasticKubernetesService(
                    "EKS", "orders · catalog · payments\n6 × m6i.xlarge"
                ).sizing(nodes=6, instance_type="m6i.xlarge")
            with aws.PrivateSubnet("Private subnets · data"):
                cache = databases.ElasticacheElasticacheForValkey(
                    "ElastiCache for Valkey",
                    "Global Datastore · " + ("primary" if primary else "secondary"),
                ).sizing(node_type="cache.r7g.large", nodes=2)
                aurora = databases.Aurora(
                    "Aurora PostgreSQL", "ledger · " + ("writer" if primary else "global secondary")
                ).sizing(instance_class="db.r6g.xlarge", instances=2 if primary else 1)
                msk = analytics.ManagedStreamingForApacheKafka(
                    "Amazon MSK", "clickstream · 3 brokers"
                ).sizing(broker_type="kafka.m7g.large", brokers=3)
        with Group("Serverless", "group").row().keep_order():
            bus = integration.EventbridgeCustomEventBus(
                "EventBridge bus", "orders · global endpoint"
            )
            queue = integration.SimpleQueueServiceQueue("SQS queue", "orders · this Region only")
            handlers = compute.Lambda("Lambda handlers", "payment · stock · fulfilment")
            table = databases.Dynamodb("DynamoDB", "global table · orders · MREC")
            secrets = security.SecretsManager(
                "Secrets Manager", "primary" if primary else "replica secrets"
            )
    return {
        "api": api,
        "cognito": cognito,
        "alb": alb,
        "eks": eks,
        "cache": cache,
        "aurora": aurora,
        "msk": msk,
        "bus": bus,
        "queue": queue,
        "handlers": handlers,
        "table": table,
        "secrets": secrets,
    }


with Diagram(
    "AWS enterprise application · global, event-driven, active/active",
    "Route 53 latency records send users to the nearest healthy Region's API Gateway "
    "and EKS services in us-east-1 and us-west-2. Orders go to a DynamoDB global "
    "table and onto EventBridge through a global endpoint; SQS buffers them for "
    "Lambda handlers, and an API destination tells partners. MSK streams the "
    "clickstream to the S3 lake. DynamoDB and MSK are active in both Regions; "
    "EventBridge fails over on a health check in about 6 min; Aurora has one writer.",
    slug="aws-enterprise-global-app",
    direction="down",
) as diagram:
    with Group("People and partners", "group").row().keep_order():
        users = shared.identity.PublicUsers("Customers", "web · mobile")
        partners = shared.identity.PublicUsers("Partner systems", "REST · webhooks")
        sre = shared.identity.Administrator("SRE on call", "runs the Aurora failover")
        Box(
            "Recovery targets",
            "Tier 0 · customer-facing\nRTO: API < 1 min, events ≈ 6 min, ledger minutes\n"
            "RPO: DynamoDB ≈ 1 s · Aurora seconds · SQS backlog waits",
        ).shape("note")

    with aws.Account("Production account").row().keep_order():
        east = region("us-east-1 · active", "10.10.0.0/16", "primary")

        with Group("Global services", "group").column().keep_order():
            dns = net.Route53("Route 53", "latency records · health checks")
            cdn = net.Cloudfront("CloudFront", "web app · WAF")
            shield = security.ShieldAWSShieldAdvanced("Shield Advanced", "DDoS response")
            kms = security.KeyManagementService("KMS", "multi-Region keys")

        west = region("us-west-2 · active", "10.20.0.0/16", "secondary")

    with Group("Platform accounts", "group").row().keep_order():
        with aws.Account("Security account").column().keep_order():
            sso = security.IAMIdentityCenter("IAM Identity Center", "workforce sign-in")
            guardduty = security.Guardduty("GuardDuty", "threat detection · all accounts")
            hub = security.SecurityHub("Security Hub", "findings · standards")
        with aws.Account("Observability account").column().keep_order():
            alarms = management.CloudwatchAlarm("CloudWatch alarms", "Region health · SLOs")
            watch = management.Cloudwatch("CloudWatch", "cross-account logs · metrics")
            xray = developer_tools.XRay("X-Ray", "traces")
        with aws.Account("Data account").column().keep_order():
            firehose = analytics.DataFirehose("Data Firehose", "MSK source · Parquet")
            lake = storage.SimpleStorageService("S3 data lake", "raw · curated · CRR").sizing(
                storage_gb=10000
            )
            athena = analytics.Athena("Athena", "SQL on the lake")
        with aws.Account("Delivery account").column().keep_order():
            pipeline = developer_tools.Codepipeline(
                "CodePipeline", "build · scan · deploy both Regions"
            )
            ecr = containers.ElasticContainerRegistry("ECR", "replicated to us-west-2")

    # The order journey: the main flow
    (
        users
        >> Edge(
            "HTTPS 443",
            step=1,
            says="A customer places an order; Route 53 answers with the nearest healthy Region",
        )
        >> dns
    )
    users >> Edge("HTTPS 443") >> cdn
    partners >> Edge("HTTPS 443") >> dns
    shield >> Edge("protects", dotted=True) >> cdn
    (
        dns
        >> Edge("latency record", step=2, says="The request reaches API Gateway in us-east-1")
        >> east["api"]
    )
    dns >> Edge("latency record") >> west["api"]
    for side in (east, west):
        side["api"] >> Edge("JWT authorizer", dotted=True) >> side["cognito"]
        side["eks"] >> Edge("TLS 6379", dotted=True) >> side["cache"]
        side["eks"] >> Edge("TLS 9098 · IAM", dotted=True) >> side["msk"]
        side["eks"] >> Edge("GetSecretValue", dotted=True) >> side["secrets"]
    west["api"] >> Edge("VPC link") >> west["alb"]
    west["alb"] >> Edge("HTTP 8080") >> west["eks"]
    (
        east["api"]
        >> Edge(
            "VPC link",
            step=3,
            says="API Gateway checks the Cognito token and calls the internal ALB through a VPC link",
        )
        >> east["alb"]
    )
    (
        east["alb"]
        >> Edge("HTTP 8080", step=4, says="The orders service on EKS takes the request")
        >> east["eks"]
    )
    (
        east["eks"]
        >> Edge("PutItem", step=5, says="It writes the order to the DynamoDB global table")
        >> east["table"]
    )
    (
        east["eks"]
        >> Edge(
            "PutEvents",
            step=6,
            says="and publishes OrderPlaced through the EventBridge global endpoint",
        )
        >> east["bus"]
    )
    (
        east["bus"]
        >> Edge("rule", step=7, says="A rule buffers it in the Region's SQS queue")
        >> east["queue"]
    )
    (
        east["queue"]
        >> Edge(
            "poll",
            step=8,
            says="Lambda handlers take it (payment, stock, fulfilment, each idempotent) and publish OrderShipped back to the bus",
        )
        >> east["handlers"]
    )
    east["handlers"] >> Edge() >> east["bus"]
    (
        east["bus"]
        >> Edge(
            "API destination · HTTPS",
            step=9,
            says="An API destination pushes the event to partners' webhooks",
        )
        >> partners
    )
    east["eks"] >> Edge("TCP 5432", dotted=True) >> east["aurora"]
    (
        east["msk"]
        >> Edge(
            "Kafka · IAM",
            step=10,
            says="Data Firehose reads the clickstream from MSK and lands it in the S3 lake",
        )
        >> firehose
    )
    firehose >> Edge("Parquet") >> lake
    athena >> Edge("queries", dotted=True) >> lake

    # Running all the time: dashed, no steps
    east["table"] >> Edge("global table", dashed=True, both=True) >> west["table"]
    east["bus"] >> Edge("event replication", dashed=True) >> west["bus"]
    east["msk"] >> Edge("MSK Replicator", dashed=True, both=True) >> west["msk"]
    east["aurora"] >> Edge("global database", dashed=True) >> west["aurora"]
    east["cache"] >> Edge("Global Datastore", dashed=True) >> west["cache"]
    east["cognito"] >> Edge("user pool replica", dashed=True) >> west["cognito"]
    pipeline >> Edge("push · both Regions") >> ecr
    guardduty >> Edge("findings", dotted=True) >> hub
    xray >> Edge("traces", dotted=True) >> watch

    # us-east-1 fails
    failover = "Region failover"
    (
        alarms
        >> Edge(
            "health check",
            step=1,
            flow=failover,
            says="CloudWatch alarms on us-east-1 trip the Route 53 health checks",
        )
        >> dns
    )
    (
        dns
        >> Edge(
            "all traffic",
            dashed=True,
            step=2,
            flow=failover,
            says="Route 53 sends every request to us-west-2; the Cognito domain fails over too",
        )
        >> west["api"]
    )
    (
        dns
        >> Edge(
            "endpoint failover",
            dashed=True,
            step=3,
            flow=failover,
            says="The EventBridge global endpoint moves publishing to the us-west-2 bus",
        )
        >> west["bus"]
    )
    (
        alarms
        >> Edge("page", step=4, flow=failover, says="The same alarms page the SRE on call")
        >> sre
    )
    (
        sre
        >> Edge(
            "failover-global-cluster",
            step=5,
            flow=failover,
            says="The SRE fails Aurora Global Database over to us-west-2",
        )
        >> west["aurora"]
    )
    (
        west["queue"]
        >> Edge(
            "poll",
            step=6,
            flow=failover,
            says="us-west-2 handlers carry on; messages already in the us-east-1 queue wait for it to return",
        )
        >> west["handlers"]
    )

if __name__ == "__main__":
    print(diagram.export(Path("dist"), display="both").html)
