# DigitalOcean library

Load only for DigitalOcean content. The theme is
[`digitalocean.json`](../../assets/themes/digitalocean.json)
(`theme="digitalocean"`); the component catalog combines DigitalOcean's
documentation product and platform artwork with the `diagrams.digitalocean`
node set, 75 icons in `assets/icons/vendors/digitalocean/`. Coverage:
**reviewed**. Several icons are PNG artwork wrapped in SVG; they scale
through their viewBox like any other component.

## Frames

Starter stack: **Team → project → region → VPC → DOKS cluster → cluster and
service subnets → node pool and workloads**. The team owns infrastructure and
billing; a project groups supported resources; the VPC is a regional network
context, not an ownership level. This is the one starter that also places
components: the managed control plane, three worker Droplets, ingress, a
deployment, a service, a persistent volume claim, and block storage.

| Frame id | Kind | Official tab icon |
|---|---|---|
| `custom-boundary-do-team` | team | - |
| `custom-boundary-do-project` | project | Projects |
| `custom-boundary-do-region` | region | - |
| `custom-boundary-do-vpc` | vpc | VPC |
| `custom-boundary-do-doks` | cluster | DOKS boundary |
| `custom-boundary-do-cluster-subnet` / `custom-boundary-do-service-subnet` | subnet-private | - |
| `custom-boundary-do-node-pool` | node-pool | - |
| `custom-boundary-do-workloads` | group | - |

## Artwork

Use the reviewed DigitalOcean artwork and its palette unchanged. The
DigitalOcean mark stands once in each picture, in the lockup band below the drawing.

## Modelling rules

- Kubernetes workloads inside a DOKS cluster use the Kubernetes library's
  components (ingress, deployment, service, claim); DigitalOcean components
  are the managed pieces around them (control plane, Droplets, load balancer,
  volumes, Spaces, managed databases).
- The `digitalocean-base` and `digitalocean-kubernetes-cluster` templates are
  the worked examples.
- DigitalOcean service artwork. DigitalOcean trademark guidance applies.
