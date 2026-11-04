# Akamai Cloud library

Load only for Akamai Cloud (formerly Linode) content. The theme is
[`akamai.json`](../../assets/themes/akamai.json) (`theme="akamai"`).
Coverage: **reviewed** - 24 service tiles drawn for this project (a white
glyph on the vendor's colour; they are this repository's own artwork, not the
vendor's icons), plus the frames and the theme. Four generic ids
(`entry-service`, `app-service`, `object-store-service`, `database-service`)
still resolve, for documents that use them. Products
with no tile yet take the shared neutral primitives.

## Frames

Starter stack: **Account → region → VPC → subnet**. Cloud Firewalls are
security frames; Linode Kubernetes Engine clusters are cluster frames.

| Frame id | Kind |
|---|---|
| `custom-boundary-akamai-account` | account |
| `custom-boundary-akamai-region` | region |
| `custom-boundary-akamai-vpc` | vpc |
| `custom-boundary-akamai-subnet` | subnet-private |
| `custom-boundary-akamai-firewall` | security-group |
| `custom-boundary-akamai-lke` | cluster (Kubernetes mark on the tab) |

## Modelling rules

- VPCs and their subnets are regional; NodeBalancers, instances, and managed
  databases live in the region and attach to a subnet.
- Akamai's CDN and security edge is a separate, global capability: draw it
  outside the region frames, like Cloudflare.
- Akamai and Linode marks remain the property of Akamai Technologies, Inc.

## Components

| Component | Category | Id |
|---|---|---|
| NodeBalancer | networking | `akamai:entry-service` |
| Linode Compute Instance | compute | `akamai:app-service` |
| Object Storage | storage | `akamai:object-store-service` |
| Managed Database | databases | `akamai:database-service` |
| Dedicated CPU Instance | compute | `akamai:dedicated-cpu` |
| GPU Instance | compute | `akamai:gpu-instance` |
| Bare Metal | compute | `akamai:bare-metal` |
| Linode Kubernetes Engine | containers | `akamai:lke` |
| Block Storage | storage | `akamai:block-storage` |
| Images | storage | `akamai:images` |
| Backups | storage | `akamai:backups` |
| VPC | networking | `akamai:vpc` |
| Cloud Firewall | security | `akamai:cloud-firewall` |
| DNS Manager | networking | `akamai:dns-manager` |
| Akamai Edge DNS | networking | `akamai:edge-dns` |
| Akamai CDN | networking | `akamai:cdn` |
| App and API Protector | security | `akamai:app-api-protector` |
| Bot Manager | security | `akamai:bot-manager` |
| Prolexic DDoS Protection | security | `akamai:prolexic` |
| Guardicore Segmentation | security | `akamai:guardicore` |
| Enterprise Application Access | security | `akamai:enterprise-application-access` |
| EdgeWorkers | compute | `akamai:edgeworkers` |
| EdgeKV | databases | `akamai:edgekv` |
| DataStream | analytics | `akamai:datastream` |
