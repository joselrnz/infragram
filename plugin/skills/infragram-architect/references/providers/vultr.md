# Vultr library

Load only for Vultr content. The theme is [`vultr.json`](../../assets/themes/vultr.json)
(`theme="vultr"`). Coverage: **reviewed** - 21 service tiles drawn for this project (a white
glyph on the vendor's colour; they are this repository's own artwork, not the
vendor's icons), plus the frames and the theme. Four generic ids
(`entry-service`, `app-service`, `object-store-service`, `database-service`)
still resolve, for documents that use them. Products
with no tile yet take the shared neutral primitives.

## Frames

Starter stack: **Account → region → VPC**. Firewall groups are security frames
around instances; Vultr Kubernetes Engine clusters are cluster frames.

| Frame id | Kind |
|---|---|
| `custom-boundary-vultr-account` | account |
| `custom-boundary-vultr-region` | region |
| `custom-boundary-vultr-vpc` | vpc |
| `custom-boundary-vultr-firewall-group` | security-group |
| `custom-boundary-vultr-vke` | cluster (Kubernetes mark on the tab) |

## Modelling rules

- A VPC is regional; instances, load balancers, and managed databases attach
  to it inside the region frame.
- Vultr marks remain the property of The Constant Company, LLC.

## Components

| Component | Category | Id |
|---|---|---|
| Vultr Load Balancer | networking | `vultr:entry-service` |
| Cloud Compute Instance | compute | `vultr:app-service` |
| Vultr Object Storage | storage | `vultr:object-store-service` |
| Managed Database | databases | `vultr:database-service` |
| Bare Metal | compute | `vultr:bare-metal` |
| Cloud GPU | compute | `vultr:cloud-gpu` |
| Optimized Cloud Compute | compute | `vultr:optimized-cloud-compute` |
| Vultr Kubernetes Engine | containers | `vultr:kubernetes-engine` |
| Container Registry | containers | `vultr:container-registry` |
| Block Storage | storage | `vultr:block-storage` |
| Vultr File System | storage | `vultr:file-system` |
| Snapshots | storage | `vultr:snapshots` |
| Automatic Backups | storage | `vultr:backups` |
| VPC | networking | `vultr:vpc` |
| Reserved IP | networking | `vultr:reserved-ip` |
| Vultr DNS | networking | `vultr:dns` |
| Direct Connect | networking | `vultr:direct-connect` |
| Vultr Firewall | security | `vultr:firewall` |
| DDoS Protection | security | `vultr:ddos-protection` |
| Serverless Inference | ai-machine-learning | `vultr:serverless-inference` |
| Marketplace App | web | `vultr:marketplace-app` |
