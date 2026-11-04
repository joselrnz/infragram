"""Self-hosted CI/CD with OIDC to a secrets vault, deploying to a DigitalOcean VPC.

A small team runs its own pipeline at home or in an office. AI agents push branches as a bot
account and a person merges. The merge runs CI on a runner VM: each job proves who it is with
the git server's per-job OIDC token, the vault answers with a five-minute token, and the job
reads only the bot's token for private packages and other repositories, so no secret is stored
in CI. A release runner builds one unsigned image candidate and holds no signing key or registry
login; the maintainer's workstation checks CI, pushes the image by digest, signs it and points the
deploy at that digest, and the deploy VM rolls the servers in the cloud over an overlay VPN.

The networks are drawn as built: every machine on one LAN, the runners and the deploy VM bridged
onto it through the hypervisor's external virtual switch, and the app and data droplets in a VPC
whose firewalls admit only the CDN on 443 and only the app on the data ports. The pipeline is the
main flow, numbered 1 to 14; the bot's own standing access to the vault is a second flow,
``Edge(..., step=1, flow="Agent access")``, listed under its name. A click on any step in the list
shows its wire in the editor.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/selfhosted_cicd_oidc.py \
        --formats template,html,svg,png --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import Group, infragram as shared
from infragram.nodes.digitalocean import compute as do_compute
from infragram.nodes.frames import digitalocean as do_frames, onprem
from infragram.nodes.infragram.hybrid_multicloud import BrandDigitalOcean

ai = shared.ai_machine_learning
compute = shared.compute
devops = shared.devops
identity = shared.identity
security = shared.security

with Diagram(
    "Self-hosted CI/CD with OIDC to a secrets vault",
    "Agents push as a bot account and a person merges. CI on a runner VM signs in to the vault with "
    "the git server's per-job OIDC token and reads the bot's token for packages and repositories; "
    "no secret is stored in CI. The maintainer's workstation pushes and signs the image, and the "
    "deploy VM rolls the app in a DigitalOcean VPC over an overlay VPN.",
    slug="selfhosted-cicd-oidc",
) as diagram:
    with onprem.Network("Office LAN 10.10.0.0/24").row().keep_order():
        with Group("Workstation .10").column().keep_order():
            agents = ai.AutomationAgent("AI agents", "coding agents - as bot")
            owner = identity.Administrator("Maintainer", "merge, dispatch, deploy")
            publisher = compute.DesktopClient("release script", "publish + cosign sign")

        with Group("Git server .20").column().keep_order():
            git = devops.GitBranch("Git server", "repos + CI")
            token = identity.OidcToken("OIDC ID token", "per job - aud vault")

        with Group("NAS .30").column():
            vault = security.SecretKey("Secrets vault", ":8200 TLS - kv/ci")

        with Group("Hypervisor .40").column():
            with onprem.Subnet("vSwitch - external, bridged").column().keep_order():
                ci = devops.CIRunner("ci-runner", ".41 - label docker")
                release = devops.CIRunner("release-runner", ".42 - label release")
                deployer = compute.VirtualMachine("deploy-vm", ".43 - deploy agent")

        candidate = devops.SignedArtifact("Image candidate", "OCI layout - unsigned")

    overlay = shared.networking.OverlayNetwork("Overlay VPN", "deploy-vm -> servers tcp:22 only")

    with do_frames.Region("DigitalOcean region").column().keep_order():
        registry = BrandDigitalOcean("Container registry", "signed images by digest")
        with do_frames.VPC("VPC app 10.20.0.0/24").column().keep_order():
            app = do_compute.Droplet("app droplet", "10.20.0.2 - 443 from the CDN only")
            data = do_compute.Droplet("data droplet", "10.20.0.3 - Postgres, Valkey")

    (
        agents
        >> Edge("push branch, PR", step=1, says="Agents push branches and open PRs as the bot")
        >> git
    )
    (
        owner
        >> Edge("merge to main", step=2, says="Only a person merges; the merge starts CI")
        >> git
    )
    git >> Edge("runs CI", step=3, says="Lint, tests and audits on the CI runner") >> ci
    ci >> Edge("asks for", step=4, says="The job asks the git server for an ID token") >> token
    git >> Edge("signs", dotted=True) >> token
    (
        token
        >> Edge(
            "login ci-pr",
            step=5,
            says="The vault checks the key, the repository and the runner's address",
        )
        >> vault
    )
    vault >> Edge("5-min token", step=6, says="Reads the bot's token, masked in the log") >> ci
    (
        ci
        >> Edge(
            "packages, repos",
            step=7,
            says="Installs private packages, fetches other repos; CI green",
        )
        >> git
    )
    owner >> Edge("dispatch build", step=8, says="Starts each app's image build on main") >> release
    git >> Edge("npm secret", dashed=True) >> release
    (
        release
        >> Edge(
            "builds",
            step=9,
            says="Builds and scans one unsigned candidate; no key, no registry login",
        )
        >> candidate
    )
    (
        publisher
        >> Edge("checks runs", step=10, says="CI green on the commit; downloads the candidate")
        >> git
    )
    (
        publisher
        >> Edge(
            "push + sign", step=11, says="Pushes by digest, signs and attests with the release key"
        )
        >> registry
    )
    (
        publisher
        >> Edge("set digest", step=12, says="Points the app's image at the digest")
        >> deployer
    )
    (
        deployer
        >> Edge(
            "SSH :22", step=13, says="The deploy VM opens SSH to the servers over the overlay VPN"
        )
        >> overlay
    )
    overlay >> Edge("redeploy", step=14, says="Rolls the app to the signed image") >> app
    overlay >> Edge("SSH", dashed=True) >> data
    app >> Edge("pulls", dotted=True) >> registry
    app >> Edge("5432, 6380", dotted=True) >> data
    (
        agents
        >> Edge("bot role", step=1, flow="Agent access", says="Bound to the workstation's address")
        >> vault
    )
    (
        vault
        >> Edge(
            "bot token",
            step=2,
            flow="Agent access",
            says="Used by git and the git server's API",
            leaves="top",
        )
        >> agents
    )


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
