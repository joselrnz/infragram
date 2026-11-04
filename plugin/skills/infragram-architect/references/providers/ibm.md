# IBM Cloud library

Load only for IBM Cloud content. The theme is [`ibm.json`](../../assets/themes/ibm.json)
(`theme="ibm"`); the component catalog is 168 IBM Cloud services across
analytics, applications, blockchain, compute, data, DevOps, general,
infrastructure, management, network, security, social, storage, and user in
`assets/icons/vendors/ibm/`, each drawn with an icon from IBM's Carbon set
(`@carbon/icons` 11.89.0, Apache-2.0). Coverage: **reviewed** - a reviewed
table (`scripts/importers/ibm-carbon-map.json`) names each service's Carbon
icon and why; where Carbon has the product's own icon it is used, otherwise
the nearest generic one. Nine services with no honest icon are left out.

## Frames

Starter stack: **Enterprise → account → resource group → region → VPC → zone
→ subnet**. Resource groups model IAM and resource ownership; the VPC is
regional and subnets are zonal.

| Frame id | Kind |
|---|---|
| `custom-boundary-ibm-enterprise` | organization |
| `custom-boundary-ibm-account` | account |
| `custom-boundary-ibm-resource-group` | resource-group |
| `custom-boundary-ibm-region` | region |
| `custom-boundary-ibm-zone` | zone |
| `custom-boundary-ibm-vpc` | vpc |
| `custom-boundary-ibm-subnet` | subnet-private |
| `custom-boundary-ibm-cluster` | cluster (Kubernetes mark on the tab) |

IBM frames use the Infragram Architect line glyphs on their tabs, except the
cluster frame, which wears the Kubernetes mark; official frame artwork is on
the review backlog.

## Modelling rules

- Subnets are zonal: place each in a zone frame inside the regional VPC.
- The `general` upstream category holds diagram-neutral symbols; prefer a
  specific service icon when one exists.
- IBM Cloud icons from IBM Carbon (`@carbon/icons` 11.89.0, Apache-2.0,
  Copyright 2015 IBM Corp.). IBM names and marks remain with IBM.
