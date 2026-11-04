# Google Cloud library

Load only for Google Cloud content. The theme is [`gcp.json`](../../assets/themes/gcp.json)
(`theme="gcp"`); the component catalog is the official Google Cloud icon
library, 235 icons in `assets/icons/vendors/gcp/`. Coverage: **full**; the
icons fill 16 of the 21 categories, and one is still in `custom`.

## Frames

Starter stack: **Organization → folder → project → global VPC → region →
subnet**. The VPC is *global* and the subnet is *regional*, so region is a
location boundary drawn inside the VPC - never the VPC's parent.

| Frame id | Kind |
|---|---|
| `custom-boundary-gcp-organization` | organization |
| `custom-boundary-gcp-folder` | folder |
| `custom-boundary-gcp-project` | project |
| `custom-boundary-gcp-vpc` / `custom-boundary-gcp-shared-vpc` | vpc |
| `custom-boundary-gcp-region` / `custom-boundary-gcp-zone` | region / zone |
| `custom-boundary-gcp-subnet` | subnet-private |
| `custom-boundary-gcp-gke` | cluster (Kubernetes mark on the tab) |

Google Cloud frames use the Infragram Architect line glyphs on their tabs,
except the GKE cluster frame, which wears the Kubernetes mark; official frame
artwork is on the review backlog.

## Artwork

Preserve the bundled service icon colors; Google's product-icon terms forbid
altering the artwork. The Google Cloud mark stands once in each picture, in the lockup band below the drawing.

## Modelling rules

- Shared VPC: the host project owns the network frame; service projects
  attach as siblings with their workloads inside the shared subnets.
- Zonal resources (VM instances, zonal GKE) sit in a zone frame; regional
  resources sit directly in the region.
- Google Cloud service artwork. Google product-icon and trademark terms apply.
