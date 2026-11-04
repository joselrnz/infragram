# Oracle Cloud library

Load only for Oracle Cloud Infrastructure content. The theme is
[`oracle.json`](../../assets/themes/oracle.json) (`theme="oracle"`); the
component catalog is the `diagrams.oci` node set, 70 icons across compute,
connectivity, database, DevOps, governance, monitoring, network, security,
and storage in `assets/icons/vendors/oracle/`. Coverage: **reviewed** - the
artwork is embedded unmodified with per-file provenance; Oracle's trademark
terms apply to the marks.

## Frames

Starter stack: **Tenancy → compartment → region → VCN → subnet → OKE**.
Availability domains are optional because OCI supports regional subnets.

| Frame id | Kind |
|---|---|
| `custom-boundary-oci-tenancy` | organization |
| `custom-boundary-oci-compartment` | compartment |
| `custom-boundary-oci-region` | region |
| `custom-boundary-oci-domain` | zone (availability domain) |
| `custom-boundary-oci-vcn` | vpc |
| `custom-boundary-oci-subnet` | subnet-private |
| `custom-boundary-oci-security-zone` | security-zone |
| `custom-boundary-oci-oke` | cluster (Kubernetes mark on the tab) |

OCI frames use the Infragram Architect line glyphs on their tabs, except the
OKE cluster frame, which wears the Kubernetes mark; official frame artwork is
on the review backlog.

## Modelling rules

- Compartments are ownership, not location: one compartment can hold
  resources in several regions.
- Regional subnets are the default; use an availability-domain frame only
  when placement matters to the picture.
- Oracle Cloud Infrastructure artwork via mingrammer/diagrams v0.25.1 (MIT).
  Oracle trademarks remain property of Oracle and its affiliates.
