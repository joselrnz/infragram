# Usage guide

## Names

The product is **Infragram Architect**; the code and the file format use the
short name. The Python package and command are `infragram`, documents end in
`.infragram.json`, and the shared component library inside a document is
`infragram:`.

## First diagram

*`plugin/examples/aws_three_tier.py`: one Python file, one command.*

```python
from infragram.author import Diagram, Edge
from infragram.nodes.aws.compute import EC2
from infragram.nodes.aws.databases import RDS
from infragram.nodes.aws.networking_content_delivery import ElasticLoadBalancing
from infragram.nodes.frames import aws

with Diagram("Shop"):
    with aws.Cloud("AWS Cloud"), aws.Region("us-east-1"), aws.VPC("VPC 10.0.0.0/16"):
        with aws.PublicSubnet("Public"):
            lb = ElasticLoadBalancing("Load balancer")
        with aws.PrivateSubnet("Private"):
            web = EC2("Web servers")
            db = RDS("PostgreSQL")
    lb >> Edge("HTTPS") >> web >> Edge("SQL") >> db
```

## Scope

*Infrastructure* is the product. Inside it are three library kinds:

| Kind | Libraries | Coverage |
|---|---|---|
| **cloud** | AWS (784 icons), Azure (715), Google Cloud (235) | full official catalogs |
| | DigitalOcean (75), Hetzner Cloud (26), Cloudflare (37: 33 drawn service tiles and 4 product marks, 3 frames), Oracle Cloud (70), IBM Cloud (168), Alibaba Cloud (94) | reviewed, provenance-tracked product sets |
| | OVHcloud (26), Vultr (21), Akamai Cloud (Linode) (24), Equinix (27) | reviewed - service tiles drawn for this project (original artwork), frames and theme |
| **platform** | Kubernetes (34), OpenStack (50) | reviewed |
| | Databricks (78) | reviewed - the Databricks architecture icon set (MIT, from Databricks' official SVGs), frames and theme |
| | VMware vSphere (23), Proxmox VE (23) | reviewed - service tiles drawn for this project (original artwork), frames and theme |
| **on-prem** | Local & On-Premises: 1,110 components covering servers, network, storage, monitoring, CI and the rendered 3D estate | reviewed |

A shared `infragram:` library adds neutral primitives (clients, users, generic
servers and databases, firewalls, queues, common open-source products) and the
architecture frames.

Diagrams it produces: single-cloud architecture, multicloud and hybrid
architecture, Kubernetes platform and workload layouts, datacenter and site
topologies, and architecture-level network segmentation (sites, networks,
VLANs/subnets, gateways, firewalls, tunnels). Not this project: editorial
diagrams such as flowcharts or sequences, L2/L3 network engineering artifacts,
deployment or detailed network configuration. A diagram on AWS, Azure or Google Cloud exports as a
modular Terraform skeleton to review (`--formats terraform`, or
`terraform-modules` to call the public registry's modules), which
`check:terraform` shows works without deploying it (Terraform offline and a
plan against mocked providers), and what already
exists draws as a diagram: `import:terraform` reads a configuration, a plan or
a state, `discover:aws`, `discover:azure` and `discover:gcp` read a live
account through its CLI, and `discover:kubernetes` a cluster through kubectl,
all read-only
([`terraform.md`](../plugin/skills/infragram-architect/references/terraform.md)).

## Frames

Frames are Infragram-drawn containment components, so they stay editable in
exported HTML instead of being copied stencil artwork. 151 frames in
20 groups, with a one-click starter stack per library:

| Library | Starter stack |
|---|---|
| AWS | Cloud → Region → VPC → Availability Zone → public subnet |
| Azure | Tenant → management group → subscription → resource group → VNet → subnet |
| Google Cloud | Organization → folder → project → global VPC → region → subnet |
| Cloudflare | Account → zone (the global network as a frame of its own) |
| DigitalOcean | Team → project → region → VPC → DOKS cluster → subnets → node pool and workloads |
| Oracle Cloud | Tenancy → compartment → region → VCN → subnet → OKE |
| IBM Cloud | Enterprise → account → resource group → region → VPC → zone → subnet |
| Alibaba Cloud | Resource directory → account → resource group → region → VPC → zone → vSwitch |
| Kubernetes | Cluster → namespace → workload (node pools stay separate) |
| Databricks | Account → workspace → compute (Unity Catalog beside the workspaces it governs) |
| Hetzner Cloud | Project → network → network zone → subnet |
| OVHcloud | Public Cloud project → region → vRack → subnet |
| Vultr | Account → region → VPC (firewall groups and VKE clusters as frames) |
| Equinix | Metro → IBX → cage → cabinet (Equinix Fabric as a network frame beside the metros) |
| Akamai Cloud (Linode) | Account → region → VPC → subnet (Cloud Firewall and LKE as frames) |
| OpenStack | Region → project → network → subnet (availability zones and host aggregates as frames) |
| VMware vSphere | vCenter → datacenter → cluster → ESXi host (resource pools, distributed switches, port groups) |
| Proxmox VE | Datacenter → cluster → node → resource pool (bridges and VLANs) |
| Local & On-Premises | Datacenter → network → VLAN/subnet → compute cluster |

Frame artwork resolves in three tiers: an official vendor icon named by the
library's theme (31 frames: AWS, Azure, DigitalOcean and Databricks name
several, Google Cloud, Oracle, IBM, Vultr and Akamai one each), the Kubernetes mark
for managed-cluster frames, then an Infragram-owned line glyph. See
[`plugin/skills/infragram-architect/references/frames.md`](../plugin/skills/infragram-architect/references/frames.md).

## Compose as code

Write the diagram the way you would describe it: nesting is containment,
an arrow is a wire, and nothing in the file says how anything is drawn.

```python
from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.aws import compute, databases, networking_content_delivery as net
from infragram.nodes.frames import aws

with Diagram("Three-tier web"):
    users = shared.identity.PublicUsers("Users")
    with aws.Cloud("AWS Cloud"), aws.Region("us-east-1"), aws.VPC("VPC 10.0.0.0/16"):
        with aws.PublicSubnet("Public subnet"):
            alb = net.ElasticLoadBalancing("ALB")
        with aws.PrivateSubnet("Private subnet"):
            web = compute.EC2("Web servers")
            db = databases.RDS("PostgreSQL")
    users >> Edge("HTTPS") >> alb >> Edge("HTTP") >> web >> Edge("SQL") >> db
```

One class per shipped icon (`infragram.nodes.<library>.<category>`), one per
shared primitive (`infragram.nodes.infragram`), one per containment frame of
every gallery (`infragram.nodes.frames.<library>`), all generated from the
catalogs by `infragram gen:nodes`. A frame is a `with` block; every frame
draws with its library's colour and line from the theme, and the vendor's own
badge where the theme names one, identically in the editor and the export. The document -- provider-qualified components,
providers, kind, placement -- is inferred.
`infragram compose spec.py --formats template,html,svg,png` runs a file and
exports it; complete specs live under `plugin/examples/`. The guide is
[compose.md](../plugin/skills/infragram-architect/references/compose.md).

What there is to start from and to draw with is listed from the command line
as well: `infragram new --list` (the examples, then the templates), `infragram
templates` (the 34 shipped documents; `new --template NAME` copies one),
`infragram find s3` (the class to import, and the patterns), `infragram find
--library aws` (a whole library) and `find --libraries`, `infragram recipes`
(the 3D items drawn by spec, and `--svg` to draw one), and `infragram docs
compose` (the references, printed). `diff`, `check:policy`, `costs` and
`views` print `--json` for a script or a CI job, and `diff --exit-code` and
`--comment` fit a pull request.

A diagram file type-checks as written. Each generated module ships a type
stub that declares, on every class, the `__init__` that runs, so an editor
completes `compute.EC2(` with `name` and `detail` and mypy or pyright accept
it (a checker otherwise builds a pydantic class an `__init__` of its model
fields and reads `EC2("web")` as an error). The shipped examples are held to
it by the type gate.

Repetition is a pattern (`infragram.patterns`): `MultiAZ(2, private=tier)`
draws two identical Availability Zones from one recipe, `Guardrails()` the
account-wide row, `DirectConnectUplink()` a site and its circuit, and each
attaches inside the frame that holds it (`MultiAZ(...).attach(vpc)`).
Generators that draw many pictures from one file assemble them with
`Blueprint`, which validates as it goes and exports deterministically, alone
or many at once; a file that lists them as `PROJECTS = [...]` is exported by
`infragram compose` like any other.
Components draw as bare vendor icons with captions unless a document says
`card` for titled boxes (`--display both --write-looks both` writes each
look), and every exported page explains a component, wire or frame on hover. The guide is
[patterns.md](../plugin/skills/infragram-architect/references/patterns.md).

## Export

```text
project.infragram.json → validate → scene → editor HTML
                                              ├── template  <slug>.infragram.json
                                              ├── svg       diagram only
                                              └── png       diagram only, Chromium, 1-4×
```

```powershell
uv tool install ./plugin         # the infragram command, from this checkout (pip install -e ./plugin works too)
uv tool install "./plugin[png]" --with-executables-from playwright   # with Playwright, for PNG and browser-drawn SVG
playwright install chromium
infragram export:project plugin/skills/infragram-architect/assets/templates/cloud/aws-site-to-site-vpn.infragram.json --formats template,html,svg,png --output-dir dist
infragram check dist/aws-site-to-site-vpn.html
```

Without installing anything but pydantic, run the same commands through the
skill's launcher, `python <repo>/plugin/skills/infragram-architect/scripts/infragram.py
export:project ...`, from any directory; project and output paths resolve
where you are. The HTML embeds
the project's libraries (two to three megabytes for a cloud project); `--libraries all` embeds every
installed library so the editor can add any of them later. Open the HTML from
`file://`: drag components, connect terminals, move frames with their
children, arrange, use layers, and download the current template, HTML, or
SVG from inside the page. Exporting again replaces the last export's own
files; a file written elsewhere or edited since is refused without
`--force`.

Every export estimates what the diagram's AWS, Azure and Google Cloud
components cost a month, from price tables shipped with Infragram: no key
and no network. The page's header shows the total, and its Cost tab the
detail by frame and item; `--no-prices` leaves prices out, and `--prices`
fetches live where it can. Rebuilding the tables is a maintainer's job; only
Google's source needs a key ([Price tables and keys](maintainers/development.md#price-tables-and-keys)).

Everything the page's Download menu and the Python API can produce, the
command line produces too, with the same options on `compose`,
`export:project`, `diff` and the imports (`export:set` takes them all but
`--title`, and draws whole diagrams, so it refuses `--view`): `--size slide-16x9`
(or `social-og`, `print-a4-landscape`, ...) puts the SVG and PNG on that
canvas, the drawing centred; `--renderer static` draws them without the
editor; `--routing direct` draws the wires straight; `--terraform-zip` writes
the Terraform skeleton as the zip the page downloads; `--title` changes the
title and `--status` saves document metadata; `--offline` and `--timeout` set how
the browser draws. Details:
[`plugin/skills/infragram-architect/references/export.md`](../plugin/skills/infragram-architect/references/export.md).

[Documentation](README.md) · [Project README](../README.md)
