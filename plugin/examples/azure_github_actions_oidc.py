"""GitHub Actions deploying to Azure with OIDC, no client secret.

A push to main runs the workflow on a GitHub-hosted runner: it builds the
image, signs it and pushes it to Azure Container Registry. The deploy job
waits for the production environment's reviewers, then signs in with
GitHub's OIDC token as a user-assigned managed identity whose federated
credential names only this repository's production environment. Its roles
reach the registry (AcrPush), the web app (Website Contributor) and the
Terraform state (Storage Blob Data Contributor); no secret lives in GitHub.

The pipeline is the main flow, numbered 1 to 8; what happens at runtime is a
second flow, ``Edge(..., step=1, flow="At runtime")``, marked the way the
cloud's own drawings mark a second flow and listed under its name.

The same pipeline for the other clouds: ``aws_github_actions_oidc.py`` and
``gcp_github_actions_oidc.py``.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/azure_github_actions_oidc.py \
        --formats template,html,svg,png,terraform --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import Group, infragram as shared
from infragram.nodes.azure import app_services, containers, identity, storage
from infragram.nodes.frames import azure

with Diagram(
    "GitHub Actions to Azure with OIDC",
    "A push to main builds, signs and pushes the image to Azure Container Registry; after the "
    "production environment's approval the deploy job signs in with GitHub's OIDC token as a "
    "managed identity whose federated credential trusts only this repository's production "
    "environment, and deploys the web app. No client secret is stored in GitHub.",
    slug="azure-github-actions-oidc",
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

    with azure.Subscription("Production subscription"), azure.Region("East US 2"):
        with azure.ResourceGroup("rg-web-prod").row():
            deployer = identity.ManagedIdentities(
                "Deploy identity", "federated credential - no secret"
            )
            registry = containers.ContainerRegistries("Container Registry", "web-app images")
            app = app_services.AppServices("Web app", "P1v3 - container")
            state = storage.StorageAccounts("Terraform state", "tfstate container")

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
            "federated sign-in",
            step=7,
            says="Entra ID accepts it for the managed identity: no secret",
        )
        >> deployer
    )
    (
        image
        >> Edge(
            "pushed to",
            dashed=True,
            step=4,
            says="The signed image is pushed to Container Registry",
        )
        >> registry
    )
    deployer >> Edge("AcrPush") >> registry
    (
        deployer
        >> Edge("deploy", step=8, says="The identity deploys the new image to the web app")
        >> app
    )
    deployer >> Edge("state", dashed=True, leaves="bottom", arrives="bottom") >> state
    (
        app
        >> Edge(
            "pulls",
            dotted=True,
            step=1,
            flow="At runtime",
            says="The web app pulls the signed image from Container Registry",
        )
        >> registry
    )


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
