"""GitHub Actions deploying to AWS with OIDC, no stored keys.

A push to main runs the workflow on a GitHub-hosted runner: it builds the
image, signs it and pushes it to ECR. The deploy job waits for the production
environment's reviewers, then asks GitHub for an OIDC token and trades it at
AWS STS for the deploy role, whose trust names only this repository's
production environment. The role may push to the repository, roll the ECS
service and keep the Terraform state; nothing else, and no key lives in
GitHub.

The pipeline is the main flow, numbered 1 to 8; what happens at runtime is a
second flow, ``Edge(..., step=1, flow="At runtime")``, marked the way the
cloud's own drawings mark a second flow and listed under its name.

The same pipeline for the other clouds: ``azure_github_actions_oidc.py`` and
``gcp_github_actions_oidc.py``.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/aws_github_actions_oidc.py \
        --formats template,html,svg,png,terraform --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import Group, infragram as shared
from infragram.nodes.aws import containers, security_identity as security, storage
from infragram.nodes.frames import aws

with Diagram(
    "GitHub Actions to AWS with OIDC",
    "A push to main builds, signs and pushes the image to ECR; after the production environment's "
    "approval the deploy job signs in with GitHub's OIDC token as a role that trusts only this "
    "repository's production environment, rolls the ECS service on Fargate and keeps the Terraform "
    "state in S3. No access key is stored in GitHub.",
    slug="aws-github-actions-oidc",
) as diagram:
    with Group("GitHub").column().keep_order():
        repo = shared.devops.BrandGithub("Repository", "acme/web-app")
        workflow = shared.devops.BrandGithubActions("Deploy workflow", "on: push to main")
        runner = shared.devops.CIRunner("Runner", "ubuntu-latest - GitHub-hosted")
        gate = shared.devops.ApprovalGate("Production approval", "environment: production")
        token = shared.identity.OidcToken("OIDC token", "id-token: write")

    issuer = shared.identity.IdentityProvider(
        "GitHub OIDC issuer", "token.actions.githubusercontent.com"
    )
    image = shared.devops.SignedArtifact("Container image", "cosign signature - SLSA provenance")

    with aws.Cloud("AWS Cloud"), aws.Region("us-east-1").column().keep_order():
        with Group("Deploy access").row():
            role = security.IdentityAccessManagementRole(
                "Deploy role", "OIDC trust - production only"
            )
            registry = containers.ElasticContainerRegistry("ECR", "web-app images - scan on push")
            state = storage.SimpleStorageService("Terraform state", "versioned")
        with aws.VPC("VPC 10.0.0.0/16"), aws.PrivateSubnet("Private subnets").row():
            cluster = containers.ElasticContainerService("ECS cluster", "web")
            service = containers.Fargate("Web service", "Fargate - 3 tasks")

    repo >> Edge("push", step=1, says="A push to main starts the deploy workflow") >> workflow
    workflow >> Edge("runs on", step=2, says="Its jobs run on a GitHub-hosted runner") >> runner
    (
        runner
        >> Edge("build + sign", step=3, says="The build job builds the image and signs it")
        >> image
    )
    (
        runner
        >> Edge("deploy job", step=5, says="The deploy job waits for the production reviewers")
        >> gate
    )
    (
        gate
        >> Edge("then requests", step=6, says="Approved, it asks GitHub for an OIDC token")
        >> token
    )
    issuer >> Edge("signs", dotted=True) >> token
    (
        token
        >> Edge(
            "AssumeRoleWithWebIdentity",
            step=7,
            says="STS trades the token for the deploy role: no key",
        )
        >> role
    )
    (
        image
        >> Edge("pushed to", dashed=True, step=4, says="The signed image is pushed to ECR")
        >> registry
    )
    role >> Edge("push") >> registry
    (
        role
        >> Edge("update service", step=8, says="The role rolls the ECS service to the new image")
        >> service
    )
    role >> Edge("state", dashed=True) >> state
    service >> Edge("runs in", dotted=True) >> cluster
    (
        service
        >> Edge(
            "pulls",
            dotted=True,
            step=1,
            flow="At runtime",
            says="The tasks pull the signed image from ECR",
        )
        >> registry
    )


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
