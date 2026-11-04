# AWS library

Load only for AWS content. The theme is [`aws.json`](../../assets/themes/aws.json)
(`theme="aws"`); the component catalog is the full official AWS Architecture
Icons set, 784 icons in `assets/icons/vendors/aws/`. Coverage: **full**.

## Group shapes

Frame colours and line styles follow the AWS Architecture Icons deck exactly;
the table and the source are in [frames.md](../frames.md#aws-group-fidelity).
Beyond the containment chain, three logical groups are available: the
security group (`#DD344C`, solid), the Auto Scaling group (`#ED7100`,
dashed), and the corporate data center (`#7D8998`, solid) for the
on-premises side of a hybrid diagram.

## Resource icons

The deck has two tiers and the library carries both. A **service** is the
coloured tile (`aws:transit-gateway`, `aws:ec2`). A **resource** is a thing
inside a service, drawn as a line glyph: `aws:vpc-nat-gateway`,
`aws:vpc-internet-gateway`, `aws:vpc-endpoints`, `aws:vpc-router`,
`aws:ec2-instance`, `aws:elastic-load-balancing-application-load-balancer`,
466 in all, named "Resource (Service)" so a search for `nat` or `igw` lands
on the real picture. They file under the same category as their service, so
`aws.networking_content_delivery.VPCNATGateway` sits beside
`TransitGateway`. Where a resource would take a service's id
(`ec2-auto-scaling`), the service keeps it and the resource is
`ec2-auto-scaling-resource`.

Use a resource for the things a VPC diagram places inside subnets -- the NAT
gateway in a public subnet, the internet gateway on the VPC edge, an
endpoint, an instance -- and a service for the managed thing as a whole.
Never stand in for a resource with a neutral primitive; if the deck has a
picture of it, the library has it.

The deck's **general icons** are resources as well: `aws:general-users`,
`aws:general-user`, `aws:general-client`, `aws:general-mobile-client`,
`aws:general-internet`, `aws:general-server`, `aws:general-servers`,
`aws:general-office-building`, `aws:general-documents` and 38 more, filed
under `general-icons`. Reach for them before a neutral primitive when the
diagram is an AWS one: the people, devices, sites and the internet around
the cloud then draw in the deck's own hand, bare like every resource.

A resource draws bare: the glyph with its caption beneath and no card, in
the card look as well, because that is how the deck places it inside a
subnet. Services keep the titled card. Nothing has to be said per node --
the rule lives in `assets/catalog/display-defaults.json` and follows the
artwork's tier -- and it holds in the editor, in every export and in the
static fallback. To box one anyway, give the node
`editor_display_mode: "card"` or pick Card for it in the editor.

## Frames

Starter stack: **AWS Cloud → Region → VPC → Availability Zone → public subnet**.
Organization and account are optional ownership frames around the cloud.

| Frame id | Kind | Notes |
|---|---|---|
| `custom-boundary-aws-cloud` | cloud | squid-ink outline, the AWS mark in white on a squid-ink tab |
| `custom-boundary-aws-organization` / `custom-boundary-aws-account` | organization / account | optional ownership |
| `custom-boundary-region` | region | dotted teal (`2,3`), Region flag tab |
| `custom-boundary-availability-zone` | zone | dashed teal (`5,4`), the generic zone glyph on its tab |
| `custom-boundary-vpc` | vpc | purple outline, VPC tab |
| `custom-boundary-public-subnet` | subnet-public | green outline and 10% tint, public-subnet tab |
| `custom-boundary-private-subnet` | subnet-private | teal outline and 10% tint, private-subnet tab |
| `custom-boundary-aws-security-group` | security-group | solid red `#DD344C` |
| `custom-boundary-aws-auto-scaling` | auto-scaling | dashed orange (`5,4`) `#ED7100`, Auto Scaling group tab |
| `custom-boundary-direct-connect-location` / `custom-boundary-corporate-network` | location / site | hybrid endpoints |

The `boundaries` block in `aws.json` is the durable source of truth for these
colors, dashes, fills, and tab icons; the editor reads it, so never restate
those values in a project. **Never use a generic subnet frame in an AWS
picture** - public versus private is the routability signal, and the
renderer rejects the ambiguous kind.

## Artwork and captions

Use the bundled official service icons without recoloring their product
palette. Frame captions keep AWS title and sentence case ("Availability Zone
A", "Public subnet", "Private subnet") in the provider sans stack; reserve
monospace for technical values such as CIDRs and instance types. The AWS mark
sits on the cloud frame's tab, and stands once in each picture, in the lockup band below the drawing.

## Modelling rules

- Regions contain VPCs; VPCs contain Availability Zones; subnets sit inside a
  zone. Do not place a subnet directly in a region.
- Hybrid links use `vpn` for Site-to-Site VPN and `vif` for Direct Connect
  virtual interfaces; the Site-to-Site VPN template is the worked example.
- Amazon Web Services architecture artwork. AWS asset and trademark terms apply.
