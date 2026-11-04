# OpenStack library (platform)

Load only for OpenStack content. The theme is [`openstack.json`](../../assets/themes/openstack.json)
(`theme="openstack"`); the component catalog is the `diagrams.openstack` node
set in `assets/icons/vendors/openstack/`. Coverage: **reviewed**. OpenStack is a
*platform* library: a private cloud that runs on the operator's own hardware,
so it usually sits inside a Local & On-Premises datacenter frame.

## Frames

Starter stack: **Region → project → network → subnet**. Availability zones
are optional location frames for compute placement; host aggregates group
hypervisors.

| Frame id | Kind |
|---|---|
| `custom-boundary-openstack-region` | region |
| `custom-boundary-openstack-availability-zone` | zone |
| `custom-boundary-openstack-project` | project (tenant) |
| `custom-boundary-openstack-network` | network (Neutron network) |
| `custom-boundary-openstack-subnet` | subnet-private |
| `custom-boundary-openstack-host-aggregate` | server-group |

OpenStack frames use the Infragram Architect line glyphs on their tabs.

## Artwork

Use the registered OpenStack service icons (Nova, Neutron, Cinder, Swift,
Keystone, Glance, Octavia, Magnum, Heat, Ironic, ...) in their upstream
colors. The OpenStack mark stands once in each picture, in the lockup band below the drawing.

## Modelling rules

- A project owns instances, networks, volumes, and load balancers; Keystone,
  Horizon, and shared services belong to the region, not to a project.
- Bare-metal (Ironic) nodes and hypervisor hosts are infrastructure inside a
  host aggregate or the datacenter frame, not tenants.
- OpenStack project artwork via mingrammer/diagrams v0.25.1 (MIT). OpenStack
  and the OpenStack logo are trademarks of the OpenInfra Foundation.
