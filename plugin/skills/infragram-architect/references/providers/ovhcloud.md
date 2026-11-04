# OVHcloud library

Load only for OVHcloud content. The theme is [`ovhcloud.json`](../../assets/themes/ovhcloud.json)
(`theme="ovhcloud"`). Coverage: **reviewed** - 26 service tiles drawn for this project (a white
glyph on the vendor's colour; they are this repository's own artwork, not the
vendor's icons), plus the frames and the theme. Four generic ids
(`entry-service`, `app-service`, `object-store-service`, `database-service`)
still resolve, for documents that use them. Products
with no tile yet take the shared neutral primitives.

## Frames

Starter stack: **Public Cloud project → region → vRack → subnet**. The
account owns projects; the vRack is OVHcloud's private network spanning
regions and product lines.

| Frame id | Kind |
|---|---|
| `custom-boundary-ovh-account` | account |
| `custom-boundary-ovh-project` | project (Public Cloud project) |
| `custom-boundary-ovh-region` | region |
| `custom-boundary-ovh-vrack` | network (vRack) |
| `custom-boundary-ovh-subnet` | subnet-private |

## Modelling rules

- Dedicated servers and Public Cloud instances can share one vRack; draw the
  vRack as the network frame and place both kinds of compute inside it.
- Managed Kubernetes, databases, and object storage are regional services in
  the project.
- OVHcloud marks remain the property of OVH SAS.

## Components

| Component | Category | Id |
|---|---|---|
| OVHcloud Load Balancer | networking | `ovhcloud:entry-service` |
| Public Cloud Instance | compute | `ovhcloud:app-service` |
| Object Storage | storage | `ovhcloud:object-store-service` |
| Managed Database | databases | `ovhcloud:database-service` |
| Bare Metal Server | compute | `ovhcloud:bare-metal` |
| VPS | compute | `ovhcloud:vps` |
| GPU Instance | compute | `ovhcloud:gpu-instance` |
| Hosted Private Cloud | compute | `ovhcloud:hosted-private-cloud` |
| Managed Kubernetes Service | containers | `ovhcloud:managed-kubernetes` |
| Managed Private Registry | containers | `ovhcloud:managed-registry` |
| Block Storage | storage | `ovhcloud:block-storage` |
| Cold Archive | storage | `ovhcloud:cold-archive` |
| Backup and Snapshot | storage | `ovhcloud:backup` |
| NAS-HA | storage | `ovhcloud:nas-ha` |
| vRack | networking | `ovhcloud:vrack` |
| Public Network | networking | `ovhcloud:public-network` |
| Domains and DNS | networking | `ovhcloud:domains-dns` |
| Anti-DDoS | security | `ovhcloud:anti-ddos` |
| Network Firewall | security | `ovhcloud:network-firewall` |
| Identity and Access Management | identity | `ovhcloud:iam` |
| Key Management Service | security | `ovhcloud:kms` |
| Web Hosting | web | `ovhcloud:web-hosting` |
| Data Processing | analytics | `ovhcloud:data-processing` |
| Logs Data Platform | analytics | `ovhcloud:logs-data-platform` |
| AI Notebooks and Training | ai-machine-learning | `ovhcloud:ai-notebooks` |
| AI Deploy | ai-machine-learning | `ovhcloud:ai-deploy` |
