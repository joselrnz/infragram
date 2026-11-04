# Hetzner Cloud library

Load only for Hetzner Cloud content. The theme is [`hetzner.json`](../../assets/themes/hetzner.json)
(`theme="hetzner"`); the component catalog is Hetzner's website product
artwork, 26 icons in `assets/icons/vendors/hetzner/`. Coverage: **reviewed**.

## Frames

Starter stack: **Project → network → network zone → subnet**. Networks own
subnets; a network zone constrains which locations those subnets can use.

| Frame id | Kind |
|---|---|
| `custom-boundary-hetzner-project` | project |
| `custom-boundary-hetzner-location` | location |
| `custom-boundary-hetzner-network` | network |
| `custom-boundary-hetzner-zone` | zone |
| `custom-boundary-hetzner-subnet` | subnet-private |
| `custom-boundary-hetzner-server-group` | server-group |
| `custom-boundary-hetzner-firewall` | security-group |

Hetzner frames use the Infragram Architect line glyphs on their tabs.

## Artwork

Preserve the manifest palette and the registered product artwork. The Hetzner
mark stands once in each picture, in the lockup band below the drawing.

## Modelling rules

- Cloud servers, dedicated servers, load balancers, and volumes sit in a
  location inside a network; Storage Box and Object Storage are regional
  services outside the private network.
- The `hetzner-application-delivery` template is the worked example.
- Hetzner service artwork. Hetzner terms and trademark rights apply; the
  files are bundled for architecture-diagram and documentation use only.
