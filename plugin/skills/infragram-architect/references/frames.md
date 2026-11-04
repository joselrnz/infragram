# Frames

Frames are Infragram-drawn containment components. They are not copied
stencil artwork, so they stay editable in exported HTML: move a frame and its
children move with it; connections recompute from world coordinates. Every
library has its own frames because ownership, location, and network are
*not* one universal hierarchy - an Azure resource group can hold resources
from several regions, a Google VPC is global while its subnets are regional,
and Kubernetes node pools are infrastructure, not parents of namespaces.

In a project document a frame is an element whose `component` is
`infragram:<frame id>`; its members are its `children`
(see [project-schema.md](project-schema.md)).

## Artwork

A frame draws as an outlined region with a solid, provider-colored tab holding
a small icon and the frame's name. The icon resolves in three tiers:

1. an official vendor icon named by the library's theme (31 frames: AWS,
   Azure, DigitalOcean and Databricks name several, Google Cloud, Oracle, IBM,
   Vultr and Akamai one each);
2. the Kubernetes mark for the Kubernetes cluster frame and the managed
   clusters that wear it (GKE, OKE, IBM, VKE, LKE; AKS and DOKS wear their
   vendor's own cluster artwork);
3. an Infragram-owned line glyph for the frame's kind.

Colors, dashes, widths, and fills come from the theme's `boundaries` block.

## Core frames

The generic group carries provider-neutral frames for the containment every
diagram needs regardless of vendor. Ownership: **Organization**, **Account**,
**Project**, **Environment** (production, staging, development). Location:
**Region**, **Availability zone**, **On-premises site**, **Campus /
building**, **Wiring closet** (IDF/MDF). Network: **Cloud boundary**,
**Network boundary**, **Hub network** and **Spoke network** for hub-and-spoke
topologies, **Management network** for the out-of-band plane, **Storage
fabric** for SAN zones, **Public subnet**, **Private subnet**, **DMZ**.
Workload: **Security zone**, **Cluster boundary**. Dashed outlines mark the
logical groupings (environment, management plane, DMZ, zones, clusters);
solid outlines mark physical or network containment.

## Starter stacks

The editor offers one nested starter stack per library. Frames stay
individually selectable, movable, and detachable after insertion.

| Library | Starter stack | Modelling rule |
|---|---|---|
| AWS | Cloud → Region → VPC → Availability Zone → public subnet | Organization and account are optional ownership frames. Use `subnet-public` / `subnet-private`; never a generic subnet - routability is the signal. |
| Azure | Tenant → management group → subscription → resource group → VNet → subnet | Region and zone are optional location frames; a resource group may span regions. |
| Google Cloud | Organization → folder → project → global VPC → region → subnet | The VPC is global and the subnet regional, so region is a location boundary inside the VPC, not its parent. |
| DigitalOcean | Team → project → region → VPC → DOKS cluster → cluster/service subnets → node pool and workloads | The team owns billing; a project groups resources; the VPC is a regional network. The stack also places the managed control plane, three workers, ingress, a deployment, a service, a claim, and block storage. |
| Oracle Cloud | Tenancy → compartment → region → VCN → subnet → OKE | Availability domains are optional because OCI supports regional subnets. |
| IBM Cloud | Enterprise → account → resource group → region → VPC → zone → subnet | Resource groups model ownership; the VPC is regional and subnets are zonal. |
| Alibaba Cloud | Resource directory → account → resource group → region → VPC → zone → vSwitch | The vSwitch is the zonal, subnet-level frame. |
| Cloudflare | Account → zone | A zone is one domain. The global network is a sibling frame holding Workers, Pages and Workers AI, which are account-scoped and serve every zone. |
| Kubernetes | Cluster → namespace → workload | Node pools are separate infrastructure frames. |
| Hetzner Cloud | Project → network → network zone → subnet | Networks own subnets; the zone constrains available locations. |
| Local & On-Premises | Datacenter → network → VLAN/subnet → compute cluster | Asserts nothing about a hypervisor or product; add those as components. |
| OVHcloud | Public Cloud project → region → vRack → subnet | The vRack is a private network that spans regions and product lines; dedicated servers and Public Cloud instances can share it. |
| Vultr | Account → region → VPC | VPCs are regional; firewall groups and VKE clusters are frames around instances. |
| Equinix | Metro → IBX → cage → cabinet | Colocated equipment sits in a cabinet; Fabric is a network frame beside the metros, and Network Edge devices sit in the metro outside the cage. |
| Akamai Cloud (Linode) | Account → region → VPC → subnet | VPCs and subnets are regional; Akamai's CDN edge is global and stays outside the region frames. |
| OpenStack | Region → project → network → subnet | Projects own resources; availability zones and host aggregates are placement frames for compute, not ownership. |
| VMware vSphere | vCenter → datacenter → cluster → ESXi host | Resource pools group workloads inside a cluster; distributed switches and port groups model the virtual network. Place the estate inside an on-prem site frame. |
| Proxmox VE | Datacenter → cluster → node → resource pool | Bridges and VLANs model the network; QEMU VMs and LXC containers sit in a pool or on a node. |

## How a frame looks

- **Colour** is the library's frame colour from its theme, at full strength
  at every depth. AWS frames follow the AWS Architecture Icons deck group box
  for group box (a dotted teal Region, a dashed teal Availability Zone, a
  purple VPC, green public and teal private subnets); Azure's are sampled from
  its own badge icons; every other library draws in its brand colour.
- **Line**: groupings a diagram invents (organization, folder, project,
  region, zone, cluster, namespace, node pool, security zone, environment,
  DMZ) are dashed, real perimeters solid, unless the theme says otherwise.
  Borders are 1.0 px, and 1.8 px for a cloud frame.
- **The tab** sits on the frame's corner and holds the frame's name and its
  badge: the vendor's own artwork for that boundary where the vendor ships one
  (31 frames), else the generic glyph for the kind (the other 115). A
  near-miss is never borrowed: Azure ships no Availability Zone mark, so its
  zone frame keeps the generic glyph rather than the Availability Sets mark.
- **The caption** is the frame's name in the sans face, in a readable
  darkening of the frame's colour.

Both renderers draw a frame from one description, so the editor, the SVG,
the PNG and the sidebar thumbnail agree; a document saved with an older look
is drawn with the theme's current one.

## The group glyph is not the frame

The deck also ships each of those boxes as a drawing, and the importer keeps
them, so thirteen AWS components are pictures of group boxes. Five are named
exactly like the frame that does the job:

| Glyph, which draws a card | Frame, which contains |
|---|---|
| `nodes.aws.architecture_group.Region` | `frames.aws.Region` |
| `nodes.aws.architecture_group.Cloud` | `frames.aws.Cloud` |
| `nodes.aws.architecture_group.Account` | `frames.aws.Account` |
| `nodes.aws.architecture_group.PrivateSubnet` | `frames.aws.PrivateSubnet` |
| `nodes.aws.architecture_group.PublicSubnet` | `frames.aws.PublicSubnet` |
| `nodes.aws.architecture_group.VirtualPrivateCloudVPC` | `frames.aws.VPC` |

Reach for the left column and the picture shows a card labelled "VPC" that
holds nothing: it reads as a boundary while modelling none, and the services
that belong inside it sit loose beside it. Each class docstring says it is
group artwork and names its frame, and `check` rejects a document that draws
one. Five of the thirteen have no frame counterpart at all -- the brand mark,
the two "contents" boxes, the Greengrass deployment and the Spot Fleet -- and
those say so rather than naming a near miss.

## Every other library: the icon and the frame

Only AWS files artwork as a group. The other vendors draw their containment
concepts as ordinary service icons, and thirty-eight of those, across
fourteen libraries, name something a frame also does. Among them:

| Library | Icon | Frame for containment |
|---|---|---|
| Azure | `networking.VirtualNetworks` | `frames.azure.VNet` |
| Azure | `networking.Subnet` | `frames.azure.Subnet` |
| Azure | `general.Subscriptions` | `frames.azure.Subscription` |
| Google Cloud | `legacy.VirtualPrivateCloud` | `frames.gcp.VPC` |
| IBM Cloud | `network.Vpc` | `frames.ibm.VPC` |
| Oracle Cloud | `network.Vcn` | `frames.oracle.Vcn` |
| Alibaba Cloud | `network.VirtualPrivateCloud` | `frames.alibaba.VPC` |
| DigitalOcean | `networking.VPC` | `frames.digitalocean.VPC` |

The difference from AWS group artwork matters. These are genuine service
icons, and placing one is not a mistake: an inventory diagram may want the
drawing of a VNet rather than a box holding things. So each class points at
its frame and `check` says nothing — a pointer, never a refusal. Only group
artwork is rejected.

## Building a framed diagram

34 templates ship as worked examples; `references/inventory.md`
lists them with their libraries and counts. The scenario templates show the
core frames in use: `campus-lan-wan` nests wiring closets in a campus,
`onprem-storage-fabric` pairs a storage fabric with a management network,
`zero-trust-identity` and `ot-iot-edge` place a DMZ between zones, and
`vdi-remote-work` and `onprem-dr-backup` span a site and a cloud frame.

Two shipped templates are complete worked examples. `aws-three-tier-web`:
users reach a load balancer in public subnets, web servers in private subnets
talk to a Multi-AZ database, every component inside the frame that owns it.
`onprem-datacenter`, built the same way with the Local & On-Premises library:
a branch office reaches a corporate datacenter through a firewall and VPN in a
perimeter security zone; DMZ, application and data VLANs carry HAProxy, Nginx
and PostgreSQL; a Proxmox cluster with Ceph and a backup appliance runs it;
Prometheus and Grafana watch from a management VLAN. Three more templates
follow the same recipe as lanes, so no wire crosses a card:
`onprem-data-platform` (a Hadoop lakehouse with Trino as the query layer and
SAS, RStudio, Superset and Tableau as consumers), `enterprise-data-integration`
(an Informatica-style ETL platform between source systems and a warehouse
with Power BI, Tableau, SAS and SPSS reporting) and `hybrid-bgp-edge` (two
edge routers with eBGP to two ISPs, iBGP, an OSPF core, a branch AS over
IPsec, and AWS Direct Connect plus a Site-to-Site VPN into a Transit Gateway;
on-premises and AWS frames in one hybrid project). Export any of them to see
the finished picture:

```text
python "<skill>/scripts/infragram.py" export:project "<skill>/assets/templates/cloud/aws-three-tier-web.infragram.json" --formats html,svg,png --output-dir dist
python "<skill>/scripts/infragram.py" export:project "<skill>/assets/templates/cloud/onprem-datacenter.infragram.json" --formats html,svg,png --output-dir dist
```

### In the exported HTML editor

1. Open the HTML. Add `?fresh=1` to the address to start from the file rather
   than a saved browser workspace.
2. Insert frames from the library's **Frames** gallery: a starter stack drops
   the whole nested hierarchy at once; single frames nest into whatever frame
   you drop them on. Resize with the corner handle; children move with their
   frame.
3. Drag a component from the library into a frame. The drop point decides the
   parent: a card dropped inside a public subnet belongs to that subnet, and
   the exported project records it as that frame's child.
4. Drag a card's terminal onto another card to wire them, then click the wire
   label to name it (`HTTPS`, `SQL`).
5. **Download** offers **Template** (the `.infragram.json`), **Editor page**
   (the `.html` with the current state) and **Diagram** (the clean `.svg`).
   PNG comes from the command-line export.

Scripts can do the same through `window.infragramEditor`: `addBoundary` and
`addNode` take the payload a sidebar drag carries (`id` is the service id,
plus `qualifiedId`, `provider`, `name`, `detail`, `iconUri`), `connect` wires
two ids, `setEdgeLabel` names a wire, and `exportProject()` returns the
document the Template button downloads.

### In the project document

A frame is an element whose `type` is its kind, whose `attributes` carry the
saved geometry and the frame group, and whose `children` are its members. A
component is a leaf with a `component` reference. Coordinates are editor
canvas units on a 4 px grid; sizes are the frame's own, so nest with room for
the 24 px padding.

```json
{
  "id": "public-a", "name": "Public subnet · 10.0.0.0/24", "type": "subnet-public",
  "attributes": {"editor_x": 456, "editor_y": 288, "editor_width": 432, "editor_height": 160,
                 "editor_frame_group": "aws"},
  "children": [
    {
      "id": "alb", "name": "Application Load Balancer", "type": "service",
      "component": {"provider": "aws", "service_id": "elastic-load-balancing",
                    "icon_ref": "aws:elastic-load-balancing"},
      "attributes": {"editor_x": 528, "editor_y": 332, "detail": "internet-facing",
                     "editor_card_size": {"width": 288, "height": 72}},
      "connections": [{"target": "web-a", "kind": "solid", "label": "HTTP"}]
    }
  ]
}
```

An empty frame (no `children`) stays a frame because of `editor_frame_group`;
the tab icon, colour and dash come from the library's theme for that kind. The
group is the frame's gallery, and its look goes with it: an AWS frame inside an
on-premises project is drawn in AWS's style by the editor and the exported
picture alike. The saved `editor_x`/`editor_y` (and a frame's size) are where
both renderers put the element, as long as they still describe the looks
being drawn; otherwise the layout places the document afresh.

## Frame ids

Kinds in parentheses drive the glyph and default styling. Use a library's own
frames when the provider is known; the core frames are for generic or
provider-neutral pictures.

### Core (shared)

| Id | Name |
|---|---|
| `custom-boundary-cloud` | Cloud boundary (cloud) |
| `custom-boundary-organization` | Organization (organization) |
| `custom-boundary-account` | Account (account) |
| `custom-boundary-project` | Project (project) |
| `custom-boundary-region-generic` | Region (region) |
| `custom-boundary-zone-generic` | Availability zone (zone) |
| `custom-boundary-network` | Network boundary (network) |
| `custom-boundary-public-subnet-generic` | Public subnet (subnet-public) |
| `custom-boundary-private-subnet-generic` | Private subnet (subnet-private) |
| `custom-boundary-security-zone` | Security zone (security-zone) |
| `custom-boundary-cluster` | Cluster boundary (cluster) |
| `custom-boundary-on-premises` | On-premises site (site) |
| `custom-boundary-environment` | Environment (environment) |
| `custom-boundary-campus` | Campus / building (campus) |
| `custom-boundary-wiring-closet` | Wiring closet (closet) |
| `custom-boundary-hub-network` | Hub network (hub) |
| `custom-boundary-spoke-network` | Spoke network (spoke) |
| `custom-boundary-management-network` | Management network (management) |
| `custom-boundary-storage-fabric` | Storage fabric (storage-fabric) |
| `custom-boundary-dmz` | DMZ (dmz) |
| `custom-section` | Section, a plain frame (group) |

### Local & On-Premises

| Id | Name |
|---|---|
| `custom-boundary-onprem-datacenter` | Datacenter (site) |
| `custom-boundary-onprem-site` | Office / branch site (location) |
| `custom-boundary-onprem-network` | Local network (network) |
| `custom-boundary-onprem-subnet` | VLAN / subnet (subnet-private) |
| `custom-boundary-onprem-security-zone` | Security zone (security-zone) |
| `custom-boundary-onprem-cluster` | Compute cluster (cluster) |
| `custom-boundary-onprem-rack` | Rack / server group (server-group) |
| `custom-boundary-onprem-row` | Rack row (server-group) |
| `custom-boundary-onprem-cage` | Cage / suite (location) |

### AWS

| Id | Name |
|---|---|
| `custom-boundary-aws-cloud` | AWS Cloud (cloud) |
| `custom-boundary-aws-organization` | AWS organization (organization) |
| `custom-boundary-aws-account` | AWS account (account) |
| `custom-boundary-region` | AWS Region (region) |
| `custom-boundary-availability-zone` | AWS Availability Zone (zone) |
| `custom-boundary-vpc` | Amazon VPC (vpc) |
| `custom-boundary-public-subnet` | AWS public subnet (subnet-public) |
| `custom-boundary-private-subnet` | AWS private subnet (subnet-private) |
| `custom-boundary-aws-security-group` | AWS security group (security-group) |
| `custom-boundary-aws-auto-scaling` | AWS Auto Scaling group (auto-scaling) |
| `custom-boundary-direct-connect-location` | Direct Connect location (location) |
| `custom-boundary-corporate-network` | Corporate network (site) |

### Azure

| Id | Name |
|---|---|
| `custom-boundary-azure-tenant` | Microsoft Entra tenant (organization) |
| `custom-boundary-azure-management-group` | Azure management group (management-group) |
| `custom-boundary-azure-subscription` | Azure subscription (subscription) |
| `custom-boundary-azure-resource-group` | Azure resource group (resource-group) |
| `custom-boundary-azure-region` | Azure region (region) |
| `custom-boundary-azure-zone` | Azure availability zone (zone) |
| `custom-boundary-azure-vnet` | Azure virtual network (network) |
| `custom-boundary-azure-subnet` | Azure subnet (subnet-private) |
| `custom-boundary-azure-aks` | Azure Kubernetes Service cluster (cluster) |

### Google Cloud

| Id | Name |
|---|---|
| `custom-boundary-gcp-organization` | Google Cloud organization (organization) |
| `custom-boundary-gcp-folder` | Google Cloud folder (folder) |
| `custom-boundary-gcp-project` | Google Cloud project (project) |
| `custom-boundary-gcp-region` | Google Cloud region (region) |
| `custom-boundary-gcp-zone` | Google Cloud zone (zone) |
| `custom-boundary-gcp-vpc` | Google Cloud VPC (vpc) |
| `custom-boundary-gcp-subnet` | Google Cloud subnet (subnet-private) |
| `custom-boundary-gcp-shared-vpc` | Google Cloud Shared VPC (vpc) |
| `custom-boundary-gcp-gke` | Google Kubernetes Engine cluster (cluster) |

### DigitalOcean

| Id | Name |
|---|---|
| `custom-boundary-do-team` | DigitalOcean team (team) |
| `custom-boundary-do-project` | DigitalOcean project (project) |
| `custom-boundary-do-region` | DigitalOcean region (region) |
| `custom-boundary-do-vpc` | DigitalOcean VPC (vpc) |
| `custom-boundary-do-doks` | DigitalOcean Kubernetes cluster (cluster) |
| `custom-boundary-do-cluster-subnet` | DOKS cluster subnet (subnet-private) |
| `custom-boundary-do-service-subnet` | DOKS service subnet (subnet-private) |
| `custom-boundary-do-node-pool` | DOKS node pool (node-pool) |
| `custom-boundary-do-workloads` | DOKS workloads (group) |

### Oracle Cloud

| Id | Name |
|---|---|
| `custom-boundary-oci-tenancy` | OCI tenancy (organization) |
| `custom-boundary-oci-compartment` | OCI compartment (compartment) |
| `custom-boundary-oci-region` | OCI region (region) |
| `custom-boundary-oci-domain` | OCI availability domain (zone) |
| `custom-boundary-oci-vcn` | OCI virtual cloud network (vpc) |
| `custom-boundary-oci-subnet` | OCI subnet (subnet-private) |
| `custom-boundary-oci-security-zone` | OCI security zone (security-zone) |
| `custom-boundary-oci-oke` | Oracle Kubernetes Engine cluster (cluster) |

### IBM Cloud

| Id | Name |
|---|---|
| `custom-boundary-ibm-enterprise` | IBM Cloud enterprise (organization) |
| `custom-boundary-ibm-account` | IBM Cloud account (account) |
| `custom-boundary-ibm-resource-group` | IBM Cloud resource group (resource-group) |
| `custom-boundary-ibm-region` | IBM Cloud region (region) |
| `custom-boundary-ibm-zone` | IBM Cloud availability zone (zone) |
| `custom-boundary-ibm-vpc` | IBM Cloud VPC (vpc) |
| `custom-boundary-ibm-subnet` | IBM Cloud subnet (subnet-private) |
| `custom-boundary-ibm-cluster` | IBM Kubernetes cluster (cluster) |

### Alibaba Cloud

| Id | Name |
|---|---|
| `custom-boundary-alibaba-directory` | Alibaba Cloud resource directory (organization) |
| `custom-boundary-alibaba-account` | Alibaba Cloud account (account) |
| `custom-boundary-alibaba-group` | Alibaba Cloud resource group (resource-group) |
| `custom-boundary-alibaba-region` | Alibaba Cloud region (region) |
| `custom-boundary-alibaba-zone` | Alibaba Cloud zone (zone) |
| `custom-boundary-alibaba-vpc` | Alibaba Cloud VPC (vpc) |
| `custom-boundary-alibaba-vswitch` | Alibaba Cloud vSwitch (subnet-private) |

### Kubernetes

| Id | Name |
|---|---|
| `custom-boundary-kubernetes-cluster` | Kubernetes cluster (cluster) |
| `custom-boundary-kubernetes-namespace` | Kubernetes namespace (namespace) |
| `custom-boundary-kubernetes-node-pool` | Kubernetes node pool (node-pool) |
| `custom-boundary-kubernetes-workload` | Kubernetes workload (group) |

### Hetzner Cloud

| Id | Name |
|---|---|
| `custom-boundary-hetzner-project` | Hetzner project (project) |
| `custom-boundary-hetzner-location` | Hetzner location (location) |
| `custom-boundary-hetzner-zone` | Hetzner network zone (zone) |
| `custom-boundary-hetzner-network` | Hetzner network (network) |
| `custom-boundary-hetzner-subnet` | Hetzner subnet (subnet-private) |
| `custom-boundary-hetzner-server-group` | Hetzner server group (server-group) |
| `custom-boundary-hetzner-firewall` | Hetzner firewall (security-group) |

### OVHcloud

| Id | Name |
|---|---|
| `custom-boundary-ovh-account` | OVHcloud account (account) |
| `custom-boundary-ovh-project` | Public Cloud project (project) |
| `custom-boundary-ovh-region` | OVHcloud region (region) |
| `custom-boundary-ovh-vrack` | vRack (network) |
| `custom-boundary-ovh-subnet` | OVHcloud subnet (subnet-private) |

### Vultr

| Id | Name |
|---|---|
| `custom-boundary-vultr-account` | Vultr account (account) |
| `custom-boundary-vultr-region` | Vultr region (region) |
| `custom-boundary-vultr-vpc` | Vultr VPC (vpc) |
| `custom-boundary-vultr-firewall-group` | Vultr firewall group (security-group) |
| `custom-boundary-vultr-vke` | Vultr Kubernetes Engine cluster (cluster) |

### Equinix

| Id | Name |
|---|---|
| `custom-boundary-equinix-metro` | Equinix metro (region) |
| `custom-boundary-equinix-ibx` | IBX data center (site) |
| `custom-boundary-equinix-cage` | Equinix cage (location) |
| `custom-boundary-equinix-cabinet` | Equinix cabinet (server-group) |
| `custom-boundary-equinix-fabric` | Equinix Fabric (network) |

### Akamai Cloud (Linode)

| Id | Name |
|---|---|
| `custom-boundary-akamai-account` | Akamai Cloud account (account) |
| `custom-boundary-akamai-region` | Akamai Cloud region (region) |
| `custom-boundary-akamai-vpc` | Akamai Cloud VPC (vpc) |
| `custom-boundary-akamai-subnet` | Akamai Cloud subnet (subnet-private) |
| `custom-boundary-akamai-firewall` | Cloud Firewall (security-group) |
| `custom-boundary-akamai-lke` | Linode Kubernetes Engine cluster (cluster) |

### OpenStack

| Id | Name |
|---|---|
| `custom-boundary-openstack-region` | OpenStack region (region) |
| `custom-boundary-openstack-availability-zone` | OpenStack availability zone (zone) |
| `custom-boundary-openstack-project` | OpenStack project (project) |
| `custom-boundary-openstack-network` | OpenStack network (network) |
| `custom-boundary-openstack-subnet` | OpenStack subnet (subnet-private) |
| `custom-boundary-openstack-host-aggregate` | OpenStack host aggregate (server-group) |

### VMware vSphere

| Id | Name |
|---|---|
| `custom-boundary-vmware-vcenter` | vCenter Server (organization) |
| `custom-boundary-vmware-datacenter` | vSphere datacenter (site) |
| `custom-boundary-vmware-cluster` | vSphere cluster (cluster) |
| `custom-boundary-vmware-host` | ESXi host (server-group) |
| `custom-boundary-vmware-resource-pool` | Resource pool (group) |
| `custom-boundary-vmware-distributed-switch` | Distributed switch (network) |
| `custom-boundary-vmware-port-group` | Port group (subnet-private) |

### Proxmox VE

| Id | Name |
|---|---|
| `custom-boundary-proxmox-datacenter` | Proxmox datacenter (site) |
| `custom-boundary-proxmox-cluster` | Proxmox cluster (cluster) |
| `custom-boundary-proxmox-node` | Proxmox node (server-group) |
| `custom-boundary-proxmox-pool` | Proxmox resource pool (group) |
| `custom-boundary-proxmox-bridge` | Linux bridge (network) |
| `custom-boundary-proxmox-vlan` | Proxmox VLAN (subnet-private) |

### Cloudflare

| Id | Name |
|---|---|
| `custom-boundary-cloudflare-account` | Cloudflare account (account) |
| `custom-boundary-cloudflare-zone` | Cloudflare zone, one domain (zone) |
| `custom-boundary-cloudflare-network` | Cloudflare global network (location) |

A Cloudflare zone is a domain, not a placement zone: it holds the DNS
records and rules for one hostname and belongs to the account. The global
network is a sibling of the zone rather than its parent, because the code
that runs at the edge is account-scoped and serves every zone.
