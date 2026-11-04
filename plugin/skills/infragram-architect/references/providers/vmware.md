# VMware vSphere library (platform)

Load only for VMware content. The theme is [`vmware.json`](../../assets/themes/vmware.json)
(`theme="vmware"`). Coverage: **reviewed** - 23 service tiles drawn for this project (a white
glyph on the vendor's colour; they are this repository's own artwork, not the
vendor's icons), plus the frames and the theme. Four generic ids
(`entry-service`, `app-service`, `object-store-service`, `database-service`)
still resolve, for documents that use them. Products
with no tile yet take the shared neutral primitives.

## Frames

Starter stack: **vCenter → datacenter → cluster → ESXi host**. Resource pools
group workloads inside a cluster; distributed switches and port groups model
the virtual network.

| Frame id | Kind |
|---|---|
| `custom-boundary-vmware-vcenter` | organization (vCenter Server) |
| `custom-boundary-vmware-datacenter` | site |
| `custom-boundary-vmware-cluster` | cluster |
| `custom-boundary-vmware-host` | server-group (ESXi host) |
| `custom-boundary-vmware-resource-pool` | group |
| `custom-boundary-vmware-distributed-switch` | network |
| `custom-boundary-vmware-port-group` | subnet-private |

## Modelling rules

- A vSphere estate is on-premises infrastructure: place the vCenter frame
  inside a Local & On-Premises datacenter or site frame.
- Virtual machines sit in a resource pool or directly in a cluster; storage
  (vSAN, NFS, iSCSI datastores) attaches at the cluster level.
- VMware marks remain the property of Broadcom Inc.

## Components

| Component | Category | Id |
|---|---|---|
| NSX Load Balancer | networking | `vmware:entry-service` |
| vSphere Virtual Machine | compute | `vmware:app-service` |
| vSAN Datastore | storage | `vmware:object-store-service` |
| Database Virtual Machine | databases | `vmware:database-service` |
| ESXi Host | compute | `vmware:esxi-host` |
| vCenter Server | devops | `vmware:vcenter` |
| vSphere Cluster | compute | `vmware:vsphere-cluster` |
| Resource Pool | compute | `vmware:resource-pool` |
| VM Template | compute | `vmware:vm-template` |
| vMotion | compute | `vmware:vmotion` |
| HA and DRS | compute | `vmware:ha-drs` |
| VMFS Datastore | storage | `vmware:datastore` |
| Storage Policy | storage | `vmware:storage-policy` |
| NSX Manager | networking | `vmware:nsx-manager` |
| NSX Edge Gateway | networking | `vmware:nsx-edge` |
| vSphere Distributed Switch | networking | `vmware:distributed-switch` |
| NSX Distributed Firewall | security | `vmware:distributed-firewall` |
| Tanzu Kubernetes Grid | containers | `vmware:tanzu` |
| Horizon Desktop | compute | `vmware:horizon` |
| Aria Operations | analytics | `vmware:aria-operations` |
| Aria Automation | devops | `vmware:aria-automation` |
| Site Recovery Manager | storage | `vmware:site-recovery` |
| Cloud Foundation | compute | `vmware:cloud-foundation` |
