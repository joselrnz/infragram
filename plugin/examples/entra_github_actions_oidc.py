"""GitHub Actions signing in to Microsoft Entra ID with OIDC: an app
registration's federated credential, no client secret.

The deploy job waits for the production environment's reviewers, then
azure/login asks GitHub for an OIDC token and hands it to Entra ID's token
endpoint as a client assertion. Entra ID checks the token's issuer, subject
(``repo:acme/web-app:environment:production``) and audience
(``api://AzureADTokenExchange``) against the app registration's federated
credential and issues an access token for the app's service principal, which
holds the roles: AcrPush on the registry, Website Contributor on the web app,
Storage Blob Data Contributor on the Terraform state. No secret lives in
GitHub.

The sign-in is the main flow, numbered in green; the one-time setup that
makes it possible is a second flow, in blue squares, as the Azure
Architecture Center draws an outbound flow. The Terraform export writes the
app registration, its federated credential and its service principal through
the azuread provider, and the role assignments through azurerm.

The same deploy with a user-assigned managed identity:
``azure_github_actions_oidc.py``.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/entra_github_actions_oidc.py \
        --formats template,html,svg,png,terraform --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import Group, infragram as shared
from infragram.nodes.azure import app_services, containers, identity, storage
from infragram.nodes.frames import azure

with Diagram(
    "GitHub Actions and Microsoft Entra ID with OIDC",
    "After the production environment's approval, azure/login trades GitHub's OIDC token at Microsoft "
    "Entra ID: the app registration's federated credential trusts only this repository's production "
    "environment, and the access token is for the app's service principal, which holds the deploy "
    "roles. No client secret is stored in GitHub.",
    slug="entra-github-actions-oidc",
) as diagram:
    with Group("GitHub").column().keep_order():
        repo = shared.devops.BrandGithub("Repository", "acme/web-app")
        workflow = shared.devops.BrandGithubActions(
            "Deploy workflow", "azure/login - id-token: write"
        )
        gate = shared.devops.ApprovalGate("Production approval", "environment: production")
        token = shared.identity.OidcToken("OIDC token", "aud: api://AzureADTokenExchange")

    issuer = shared.identity.IdentityProvider(
        "GitHub OIDC issuer", "token.actions.githubusercontent.com"
    )

    with azure.Tenant("Contoso - Microsoft Entra tenant"):
        with (
            Group("Workload identity federation", icon=identity.EntraWorkloadID).row().keep_order()
        ):
            entra = identity.EntraID(
                "Microsoft Entra ID", "token endpoint - login.microsoftonline.com"
            )
            app_reg = identity.AppRegistrations(
                "App registration", "github-deploy - federated credential"
            )
            principal = identity.EnterpriseApplications(
                "Service principal", "the app's identity - holds the roles"
            )
        admin = shared.identity.Administrator("Platform admin", "sets up the trust once")
        with azure.Subscription("Production subscription"), azure.Region("East US 2"):
            with azure.ResourceGroup("rg-web-prod").row():
                registry = containers.ContainerRegistries("Container Registry", "web-app images")
                app = app_services.AppServices("Web app", "P1v3 - container")
                state = storage.StorageAccounts("Terraform state", "tfstate container")

    # the sign-in, in order
    repo >> Edge("push", step=1, says="A push to main starts the deploy workflow") >> workflow
    (
        workflow
        >> Edge("deploy job", step=2, says="The deploy job waits for the production reviewers")
        >> gate
    )
    (
        gate
        >> Edge("then requests", step=3, says="Approved, azure/login asks GitHub for an OIDC token")
        >> token
    )
    issuer >> Edge("signs", dotted=True) >> token
    (
        token
        >> Edge("client assertion", step=4, says="It hands the token to Entra ID's token endpoint")
        >> entra
    )
    (
        entra
        >> Edge(
            "checks",
            step=5,
            says="Entra ID checks issuer, subject and audience against the federated credential",
        )
        >> app_reg
    )
    (
        entra
        >> Edge(
            "access token",
            step=6,
            says="and returns an access token for the service principal to the job",
        )
        >> workflow
    )
    (
        principal
        >> Edge(
            "deploy",
            step=7,
            leaves="bottom",
            arrives="top",
            says="Signed in as the service principal, the job deploys the new image",
        )
        >> app
    )
    issuer >> Edge("trusted issuer", dotted=True) >> app_reg
    app_reg >> Edge("service principal", dotted=True) >> principal
    principal >> Edge("AcrPush", leaves="bottom", arrives="top") >> registry
    principal >> Edge("state", dashed=True, leaves="bottom", arrives="top") >> state

    # the one-time setup that makes it possible
    (
        admin
        >> Edge(
            "registers",
            step=1,
            flow="One-time setup",
            says="An admin registers the app with a federated credential for production",
        )
        >> app_reg
    )
    (
        admin
        >> Edge(
            "assigns roles",
            step=2,
            flow="One-time setup",
            says="and gives its service principal the deploy roles, and no secret",
        )
        >> principal
    )


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
