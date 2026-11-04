# Cloud provider theme index

Use this lightweight router for provider-branded architecture diagrams.

## Load one provider only

Identify the provider, then read exactly one linked provider reference. Do not
open the other provider files unless the diagram genuinely contains multiple
providers; for a multicloud diagram, read only the providers that appear.

| Provider | Theme slug | Provider-specific reference |
|---|---|---|
| Azure | `azure` | [Azure](providers/azure.md) |
| AWS | `aws` | [AWS](providers/aws.md) |
| Google Cloud | `gcp` | [Google Cloud](providers/gcp.md) |
| Cloudflare | `cloudflare` | [Cloudflare](providers/cloudflare.md) |
| DigitalOcean | `digitalocean` | [DigitalOcean](providers/digitalocean.md) |
| Oracle Cloud | `oracle` | [Oracle Cloud](providers/oracle.md) |
| IBM Cloud | `ibm` | [IBM Cloud](providers/ibm.md) |
| Alibaba Cloud | `alibaba` | [Alibaba Cloud](providers/alibaba.md) |
| Kubernetes | `kubernetes` | [Kubernetes](providers/kubernetes.md) |
| Databricks | `databricks` | [Databricks](providers/databricks.md) |
| Hetzner Cloud | `hetzner` | [Hetzner Cloud](providers/hetzner.md) |
| Local & On-Premises | `onprem` | [Local & On-Premises](providers/onprem.md) |
| OVHcloud | `ovhcloud` | [OVHcloud](providers/ovhcloud.md) |
| Vultr | `vultr` | [Vultr](providers/vultr.md) |
| Equinix | `equinix` | [Equinix](providers/equinix.md) |
| Akamai Cloud (Linode) | `akamai` | [Akamai Cloud](providers/akamai.md) |
| OpenStack | `openstack` | [OpenStack](providers/openstack.md) |
| VMware vSphere | `vmware` | [VMware vSphere](providers/vmware.md) |
| Proxmox VE | `proxmox` | [Proxmox VE](providers/proxmox.md) |

The machine-readable provider index is
[`../assets/themes/catalog.json`](../assets/themes/catalog.json); the
library registry with kind, coverage, and terms is
[`../assets/catalog/providers.json`](../assets/catalog/providers.json).
Exported HTML, SVG, and PNG are output, never configuration.

## Shared rules

The renderers apply a theme; nothing in it is drawn by hand. A theme colours
the diagram itself -- paper, frames, connectors, text -- and never the
editor's chrome. Service artwork keeps its reviewed colours, which identify
services and never become a border palette. The provider mark stands once in
each picture, in the lockup band below the drawing: decorative, in its own
proportions, and implying no endorsement.

To add or update a provider, follow
[`../assets/themes/README.md`](../assets/themes/README.md). Provider-specific
guidance belongs in its one file under `references/providers/`.

## Connection kinds

A theme may extend the connection kinds under `style.links`. Every provider
starts from the same three -- `solid`, `dotted` (dash `2 3`) and `dashed`
(dash `5 4`, `link_dashes` in `render-metrics.json`) -- and a theme adds or
overrides entries with `color`, `width`,
`dash` and `role`:

```json
"style": {
  "links": {
    "vif":   { "color": "#147eba", "width": 1.4, "dash": "7,4" },
    "vpn":   { "color": "#c7254e", "width": 1.4, "dash": "8,3,2,3" },
    "local": { "role": "soft", "width": 1.1 }
  }
}
```

The kind a connection names selects one entry, so `kind="vpn"` on an AWS
diagram draws the red dash-dot wire and `kind="local"` a soft solid one. The
editor, the static renderer and the shipped picture checker all read this
table: a connector is dashed exactly when its kind has a `dash` here, and the
checker reports any export where the picture disagrees with the document.

## Frame style: the `boundaries` block

Every field a theme may set for its frames. Both renderers read them through
one derivation (`builders/frame_style.py`); see *One description of a frame*
in `frames.md` for how the picture follows.

| Field | Meaning | Default |
| --- | --- | --- |
| `color` | Frame colour for every kind `colors` does not name: a theme role or hex. Every shipped theme declares it. | `""` (falls to `border_role`, faded by depth) |
| `colors` | Frame colour per kind, e.g. AWS `vpc: #8c4fff`. | `{}` |
| `fills` | Fill per kind: a role, a hex (tinted by `fill_tint`), or `none`. | `{}` (no fill) |
| `fill_tint` | Alpha applied to a declared fill. | `0.10` |
| `dashes` | Dash per kind; `null` means solid. Unlisted kinds: invented groupings `5,4`, perimeters solid. | `{}` |
| `dash` | Dash for a kind in neither table; `null` is solid. | `null` |
| `widths` | Line weight per kind. | `{}` (cloud 1.8, else 1.0) |
| `radii` | Corner radius per kind. | `{}` (square) |
| `icons` | Badge per kind, `collection:slug`; a kind without one gets the generic glyph. | `{}` |
| `tab_fill` | `frame`: tab in the frame colour, paper glyph. `paper`: paper tab, glyph in the frame colour. | `frame` |
| `label_font`, `label_case`, `label_weight`, `label_tracking`, `label_size` | Caption face and setting. | `sans`, `preserve`, `500`, `0`, `10` |
| `pad` | Frame edge to its children. | `24` |
| `tab`, `label_icon`, `label_icon_gap` | Tab geometry; taken from `render-metrics.json` `frame`, not meant to be set per theme. | `20`, `16`, `5` |
