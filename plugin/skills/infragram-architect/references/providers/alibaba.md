# Alibaba Cloud library

Load only for Alibaba Cloud content. The theme is [`alibaba.json`](../../assets/themes/alibaba.json)
(`theme="alibaba"`); the component catalog is the `diagrams.alibabacloud`
node set, 94 icons across analytics, application, communication, compute,
database, IoT, network, security, storage, and web in
`assets/icons/vendors/alibaba/`. Coverage: **reviewed** - the artwork is
embedded unmodified with per-file provenance; Alibaba Cloud's trademark and
brand guidelines apply to the marks.

## Frames

Starter stack: **Resource directory → account → resource group → region → VPC
→ zone → vSwitch**. The vSwitch is the zonal, subnet-level frame.

| Frame id | Kind |
|---|---|
| `custom-boundary-alibaba-directory` | organization |
| `custom-boundary-alibaba-account` | account |
| `custom-boundary-alibaba-group` | resource-group |
| `custom-boundary-alibaba-region` | region |
| `custom-boundary-alibaba-zone` | zone |
| `custom-boundary-alibaba-vpc` | vpc |
| `custom-boundary-alibaba-vswitch` | subnet-private |

Alibaba Cloud frames use the Infragram Architect line glyphs on their tabs; official
frame artwork is on the review backlog.

## Modelling rules

- A VPC spans a region; vSwitches are zonal. ECS instances sit in a vSwitch.
- Alibaba Cloud artwork via mingrammer/diagrams v0.25.1 (MIT). Alibaba Cloud
  trademarks remain with their owner.
