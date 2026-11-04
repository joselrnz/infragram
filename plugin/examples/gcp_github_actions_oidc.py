"""GitHub Actions deploying to Google Cloud with Workload Identity Federation.

A push to main runs the workflow on a GitHub-hosted runner: it builds the
image, signs it and pushes it to Artifact Registry. The deploy job waits for
the production environment's reviewers, then trades GitHub's OIDC token at a
Workload Identity pool whose provider accepts only this repository's
production environment, and acts as the pool's service account: it may
write to the repository, deploy the Cloud Run service and keep the Terraform
state; no service-account key exists.

The pipeline is the main flow, numbered 1 to 8; what happens at runtime is a
second flow, ``Edge(..., step=1, flow="At runtime")``, marked the way the
cloud's own drawings mark a second flow and listed under its name.

The same pipeline for the other clouds: ``aws_github_actions_oidc.py`` and
``azure_github_actions_oidc.py``.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/gcp_github_actions_oidc.py \
        --formats template,html,svg,png,terraform --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import Group, infragram as shared
from infragram.nodes.frames import gcp
from infragram.nodes.gcp import core_products as core, legacy

with Diagram(
    "GitHub Actions to Google Cloud with OIDC",
    "A push to main builds, signs and pushes the image to Artifact Registry; after the production "
    "environment's approval the deploy job trades GitHub's OIDC token at a Workload Identity pool "
    "that accepts only this repository's production environment, and deploys Cloud Run as the "
    "pool's service account. No service-account key exists.",
    slug="gcp-github-actions-oidc",
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

    with gcp.Project("web-prod"), gcp.Region("us-central1").row():
        pool = legacy.WorkloadIdentityPool(
            "Workload Identity pool", "GitHub provider - deploy service account"
        )
        registry = legacy.ArtifactRegistry("Artifact Registry", "web-app images")
        service = core.CloudRun("Web service", "Cloud Run")
        state = core.CloudStorage("Terraform state", "versioned")

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
        >> Edge("token exchange", step=7, says="The pool trades it for the service account: no key")
        >> pool
    )
    (
        image
        >> Edge(
            "pushed to", dashed=True, step=4, says="The signed image is pushed to Artifact Registry"
        )
        >> registry
    )
    pool >> Edge("write images") >> registry
    pool >> Edge("deploy", step=8, says="The account deploys the new image to Cloud Run") >> service
    pool >> Edge("state", dashed=True) >> state
    (
        service
        >> Edge(
            "pulls",
            dotted=True,
            step=1,
            flow="At runtime",
            says="Cloud Run pulls the signed image from Artifact Registry",
        )
        >> registry
    )


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
