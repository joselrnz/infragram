---
name: infragram-architect
description: Draws, exports and checks infrastructure architecture diagrams - cloud, multicloud, hybrid, virtualized and on-premises - from the AWS, Azure, Google Cloud, DigitalOcean, Hetzner Cloud, Cloudflare, Oracle Cloud, IBM Cloud, Alibaba Cloud, OVHcloud, Vultr, Akamai Cloud, Kubernetes, Databricks, Equinix, OpenStack, VMware vSphere, Proxmox VE and Local & On-Premises libraries, with provider frames (VPC, VNet, subnet, region, zone, cluster, namespace, datacenter, VLAN). Writes one .infragram.json project or a short Python diagram file and exports an editable offline HTML editor, an SVG and a PNG; draws existing Terraform (files, plan or state) or a live AWS, Azure, GCP or Kubernetes estate, read-only; writes and checks a diagram's Terraform. Use to draw, update, export or check an infrastructure, network, cloud or Kubernetes architecture or a .infragram.json, to diagram existing Terraform or cloud resources, or for Terraform from a diagram. Not for flowcharts, sequence, ER or org charts, or IP and VLAN tables.
---

# Infragram Architect

Infragram Architect draws the infrastructure an organisation actually runs:
cloud accounts, Kubernetes platforms, datacenters and offices, and the networks
and links between them, from nineteen provider libraries. One `.infragram.json`
document is the source of every artifact: the editable offline HTML editor, the
clean SVG and the PNG are three views of one graph, never three layouts.

## Quick start

Every command runs through the launcher beside this file, the same way in
bash, PowerShell and every agent. `<skill>` is the folder holding this file
(inside Claude Code, `${CLAUDE_SKILL_DIR}`); use `python3` where `python` is
not Python 3.

```text
python "<skill>/scripts/infragram.py" compose diagram.py --verify
python "<skill>/scripts/infragram.py" export:project project.infragram.json --verify
python "<skill>/scripts/infragram.py" check <file or folder>
```

It needs Python 3.11+ and pydantic 2 (`python -m pip install "pydantic>=2,<3"`),
and says so when either is missing. A PNG also needs Playwright and Chromium
(`python -m pip install playwright pillow`, then `python -m playwright install chromium`;
Pillow draws 3D items rendered by spec); without them an export with the
default formats writes the HTML and SVG and says why the PNG is missing, and
an explicit `png` fails before anything is written.
Files land in `./dist` unless `--output-dir` says otherwise, relative paths
mean the directory you are in. Exporting again replaces what the last export
wrote, if nobody has changed it since; any other existing file is refused
without `--force`.

Installed as the Infragram Architect plugin, the skill comes with more. A
check hook checks every `.infragram.json` you write, and reads (never runs)
every diagram file you write, and hands any problem back to you: fix it
before exporting; `compose --verify` checks the picture. In Claude
Code, the `diagram-reviewer` agent reviews a finished diagram read-only
(checker, three-pass render, these rules); use it before the user shares one.
The user's own commands (`compose`, `export-project`, `import`, `discover`,
`check`, `check-terraform`) run the same launcher. The plugin's `infragram`
MCP server offers the same work as tools (`compose`, `compose_source` for a
host without file tools, `export_project`, `export_set`, `check`,
`verify_render`, `check_policy`, `check_terraform`, `diff`, `costs`, `views`,
`import_terraform`, `import_diagram`, `discover`, `new_diagram` from an
example or a template, `layout_save`, `draw_recipe`), plus `list_templates`,
`list_examples`, `recipes`, `docs` and `find_components` (the class to
import for a component, best match first, a whole library, or the libraries;
from a shell, `infragram find s3`); each answers with the files written and
the checks' verdicts as data (`diff`, `costs`, `check_policy`, `views` and
`recipes` with their JSON), and `preview: true` attaches the PNG to look at.
Every tool runs a command line command (`export_project` is `export:project`,
`find_components` is `find`, `list_templates` is `templates`, `new_diagram` is
`new`; `compose_source` writes the file `compose` then reads). These references, the templates and examples are its resources. Where
there is no shell, call those, under the same rules.

Every cloud card links to where its component is read about (right-click,
Details), and every export prices the AWS, Azure and Google Cloud components
it draws, approximately, from on-demand list prices in tables shipped with
the skill (no network; `--prices` fetches live where it can, `--no-prices`
leaves prices out). The page's header shows the month's total and its Cost
tab breaks it down by frame and item, line by line, with what was assumed
and what is free or not priced and why; `.sizing(...)` on an element says
what it is priced as ([export.md](references/export.md), Prices).

## When to use this skill

Use it when the request is about infrastructure that exists or will exist:

- a single-cloud architecture (an Azure API estate, an AWS Site-to-Site VPN)
- multicloud or hybrid architecture linking providers and sites, with the
  link kinds the libraries define: `solid`, `dashed` and `dotted` everywhere,
  plus the AWS theme's `vpn`, `vif` and `local` in any diagram that has AWS
- Kubernetes platform or workload layouts (cluster, namespaces, node pools)
- a datacenter, office, lab, or edge site, including its network segmentation
  (site, network, VLAN/subnet, gateways, firewalls, tunnels)
- an editable diagram the user will keep changing, or one they need as
  HTML, SVG, and PNG from the same source

Do not use it for flowcharts, sequence diagrams, ER models, timelines, org
charts, or other editorial diagrams, for L2/L3 network engineering artifacts
(IP plans, VLAN tables, cabling), or for deploying anything. Its prices are
an estimate from on-demand list prices, never a bill: no tax, discounts,
savings plans or reserved rates.

## How the work happens

1. **Start from a template or a diagram file.** The closest of the 34 shipped
   templates under `assets/templates/cloud/` (listed in
   [inventory.md](references/inventory.md)) is the fastest start: export it as
   it is, or edit its JSON for a small change
   ([project-schema.md](references/project-schema.md)). Anything bigger is a
   short Python file, written the way you would describe the estate:

   ```python
   from infragram.author import Diagram, Edge
   from infragram.nodes.aws import compute, databases
   from infragram.nodes.frames import aws

   with Diagram("Web tier"):
       with aws.Cloud("AWS"), aws.Region("us-east-1"), aws.VPC("VPC 10.0.0.0/16"):
           with aws.PrivateSubnet("Private subnet"):
               web = compute.EC2("Web servers")
               db = databases.RDS("PostgreSQL")
       web >> Edge("SQL") >> db
   ```

   Frames from `infragram.nodes.frames.<library>` are `with` blocks holding
   whatever is written inside them, services are classes from
   `infragram.nodes.<library>`, and `a >> Edge("label") >> b` draws a wire.
   `compose` infers components, providers, kind and placement, and a
   misspelt class or `Edge` keyword fails with the nearest real name
   ([compose.md](references/compose.md); the plugin's `examples/` folder holds
   complete files). Never place coordinates by hand. Documents of schema
   version 1 and 2 still open, and are saved as version 3.

   An estate that already exists starts from itself: `import:terraform
   <folder | plan.json | terraform.tfstate>`, or `discover:aws|azure|gcp|kubernetes`
   (read-only, through the cloud's own CLI), writes the diagram file and a
   report of every resource, and exports it; edit the file and compose it
   again ([terraform.md](references/terraform.md) section 3). A diagram
   someone drew in draw.io, Mermaid, PlantUML, Excalidraw or Visio starts
   from `import:diagram <file>` the same way
   ([import-diagrams.md](references/import-diagrams.md)).
2. **Load only the references the diagram needs.** Read
   [provider-themes.md](references/provider-themes.md), then open only the
   provider files for the libraries in the diagram. Never load every provider.
3. **Model containment with frames, not boxes.** Provider frames carry each
   library's real hierarchy (AWS Cloud → Region → VPC → Availability Zone →
   subnet; Azure tenant → management group → subscription → resource group →
   VNet → subnet; datacenter → network → VLAN → cluster), described in
   [frames.md](references/frames.md). A network is always a frame: the subnets
   go inside the VPC or VNet and the services inside those, never a card
   labelled for the network beside them. Some icons name a construct a frame
   draws (AWS's own group-box glyphs, Azure's `VirtualNetworks`); each such
   class names the frame to use, and `check` refuses an AWS group glyph drawn
   as a card.
4. **Export.** `compose` (a diagram file) and `export:project` (a document)
   write `html,svg,png` by default: the HTML is the self-contained editor, and
   the SVG and PNG are the diagram alone. Add `template` to `--formats` for a
   separate `.infragram.json` beside the page. A document draws its components
   as `icon`s (bare marks with captions) unless it says `card`;
   `--display card|icon|both` forces a look for the pictures; `both` with
   `--verify` checks both looks, and writes only the document's own unless
   `--write-looks both`. `terraform` in `--formats` writes the diagram's
   modular Terraform skeleton for AWS, Azure and Google Cloud, and
   `terraform-modules` the same through the public registry's modules
   ([terraform.md](references/terraform.md)); before handing it over,
   `check:terraform <document or output folder>` shows it plans, offline
   against mocked providers (it needs the Terraform CLI).
   For several diagram files that belong together, `export:set <folder>`
   gives each its own folder and writes the set's README. The procedure,
   presets and failure handling are in [export.md](references/export.md).
5. **Hand the user the editor.** The HTML opens from `file://` with no server:
   drag components from the library, connect them, move and resize frames,
   arrange, use layers, and download the current template, HTML or SVG from
   inside the page. [editor.md](references/editor.md) is the page's own manual
   (bending a wire, moving an end, pinning a side, frame call-outs, Tidy).
6. **Check what you produced.** Nothing is finished until these pass:
   - `--verify` checks every file as it is written; `check <files or folder>`
     does the same afterwards.
   - A document is checked for its structure, unique ids, resolvable
     connections and components the libraries really ship; a page, for
     loading nothing remote.
   - An SVG is checked as a picture: wires orthogonal and clear of text,
     glyphs, frame titles and cards they do not belong to, no caption on
     another, everything inside the picture, and every connection drawn once
     with the arrowheads and line kind it declared.
   - `verify:render <page.html> --passes 3` renders the page three separate
     times in Chromium, proves the passes identical and runs the same checks.
   - Terraform the export wrote passes `check:terraform`, or its `SKIP` line
     names what is missing.

## Libraries

Nineteen installed libraries share one shell, one search field, and one set
of twenty-one canonical categories ([provider-categories.md](references/provider-categories.md)).
**Full** means the complete official catalog; **reviewed**, a provenance-tracked
product set.

| Library | Kind | Coverage | Reference |
|---|---|---|---|
| AWS | cloud | full | [providers/aws.md](references/providers/aws.md) |
| Azure | cloud | full | [providers/azure.md](references/providers/azure.md) |
| Google Cloud | cloud | full | [providers/gcp.md](references/providers/gcp.md) |
| DigitalOcean | cloud | reviewed | [providers/digitalocean.md](references/providers/digitalocean.md) |
| Hetzner Cloud | cloud | reviewed | [providers/hetzner.md](references/providers/hetzner.md) |
| Cloudflare | cloud | reviewed | [providers/cloudflare.md](references/providers/cloudflare.md) |
| Oracle Cloud | cloud | reviewed | [providers/oracle.md](references/providers/oracle.md) |
| IBM Cloud | cloud | reviewed | [providers/ibm.md](references/providers/ibm.md) |
| Alibaba Cloud | cloud | reviewed | [providers/alibaba.md](references/providers/alibaba.md) |
| OVHcloud | cloud | reviewed | [providers/ovhcloud.md](references/providers/ovhcloud.md) |
| Vultr | cloud | reviewed | [providers/vultr.md](references/providers/vultr.md) |
| Akamai Cloud (Linode) | cloud | reviewed | [providers/akamai.md](references/providers/akamai.md) |
| Equinix | cloud | reviewed | [providers/equinix.md](references/providers/equinix.md) |
| Kubernetes | platform | reviewed | [providers/kubernetes.md](references/providers/kubernetes.md) |
| Databricks | platform | reviewed | [providers/databricks.md](references/providers/databricks.md) |
| OpenStack | platform | reviewed | [providers/openstack.md](references/providers/openstack.md) |
| VMware vSphere | platform | reviewed | [providers/vmware.md](references/providers/vmware.md) |
| Proxmox VE | platform | reviewed | [providers/proxmox.md](references/providers/proxmox.md) |
| Local & On-Premises | on-prem | reviewed | [providers/onprem.md](references/providers/onprem.md) |

A shared library (`infragram:`) holds the neutral primitives every diagram
may need - clients, users, generic servers and databases, firewalls, queues,
common open-source products - and the architecture frames;
[shared-components.md](references/shared-components.md) lists every one with
the class that draws it.

Exact counts and the full component list are generated, not hand-kept:
[inventory.md](references/inventory.md) summarises every library's icons,
frames, starter stack and the shipped templates, and
`assets/catalog/inventory.json` lists every component by id and category. A
verification gate fails when either falls behind what the libraries ship.

## Fixed rules

- Provider identity lives on every component (`component.provider`,
  `component.service_id`); it is never inferred from the active library filter.
- Switching the library filter changes the sidebar and search only. It never
  deletes, hides, converts, or restyles canvas nodes; visibility belongs to layers.
- Containment (frames and `children`) and layer membership are separate
  concepts. A node belongs to one layer; connections may cross layers.
- Official provider artwork keeps its branded colors. Artwork never changes
  workspace surface colors, and the provider mark stands once, in its own band
  below the drawing, not as decoration.
- Every export derives from one project document and one graph state. SVG
  and PNG contain the diagram only - no sidebar, inspector, grid, guides, or
  handles.
- Everything works offline from `file://`: no CDN, no hosted service, no
  telemetry. An export loads nothing remote; its fonts ship inline.
- Never overwrite an existing file the user has not asked to replace. The
  commands replace their own untouched outputs on their own; they refuse a
  file written elsewhere or edited since (a page saved from the editor, a
  diagram file changed by hand). Pass `--force` for a refused file only when
  the user means to lose that edit.

## Before you deliver

- `check` passes on every file you produced (or `--verify` did as it wrote them).
- Frames follow the library's real hierarchy (see the modelling rules in
  [frames.md](references/frames.md)); nothing sits directly in a region that
  belongs in a network, and public/private subnets are distinguished where the
  provider distinguishes them.
- Labels are clear of nodes, frames, wires, and each other at the exported size.
  Connectors route around cards on their own; a wire still crossing one means
  the two endpoints have no clear lane, so move a card rather than accepting it.
- The exported HTML opens offline and the SVG and PNG show the same state.
- You reported every produced path and size.

## Reference index

| Need | Read |
|---|---|
| Composing a diagram as code (node classes, frames, automatic layout) | [compose.md](references/compose.md) |
| Boxes with compartments, several lines, shapes and tones (panels) | [compose.md](references/compose.md), Panels |
| Patterns, blueprints, batch export, cards vs icons, tooltips | [patterns.md](references/patterns.md) |
| Authoring or editing a `.infragram.json` document | [project-schema.md](references/project-schema.md) |
| Containment frames and starter stacks per library | [frames.md](references/frames.md) |
| Exporting template, HTML, SVG and PNG, and what to do when a step fails | [export.md](references/export.md) |
| The exported editor, control by control | [editor.md](references/editor.md) |
| Which provider file to load | [provider-themes.md](references/provider-themes.md) |
| Every library's counts, starter stack and the shipped templates | [inventory.md](references/inventory.md) |
| The twenty-one canonical categories | [provider-categories.md](references/provider-categories.md) |
| Every shared (`infragram:`) component: id, class, name | [shared-components.md](references/shared-components.md) |
| A diagram's modular Terraform skeleton (`--formats terraform`), whether it works without deploying it (`check:terraform`), and an existing estate as a diagram (`import:terraform`, `discover:<cloud>`) | [terraform.md](references/terraform.md) |
