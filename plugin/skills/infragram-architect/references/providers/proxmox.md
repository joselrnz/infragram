# Proxmox VE library (platform)

Load only for Proxmox content. The theme is [`proxmox.json`](../../assets/themes/proxmox.json)
(`theme="proxmox"`). Coverage: **reviewed** - 23 service tiles drawn for this project (a white
glyph on the vendor's colour; they are this repository's own artwork, not the
vendor's icons), plus the frames and the theme. Four generic ids
(`entry-service`, `app-service`, `object-store-service`, `database-service`)
still resolve, for documents that use them. The Proxmox
VE product icon itself ships in the Local & On-Premises library
(`onprem:proxmox-pve`).

## Frames

Starter stack: **Datacenter → cluster → node → resource pool**. Linux bridges
and VLANs model the virtual network.

| Frame id | Kind |
|---|---|
| `custom-boundary-proxmox-datacenter` | site |
| `custom-boundary-proxmox-cluster` | cluster |
| `custom-boundary-proxmox-node` | server-group (PVE node) |
| `custom-boundary-proxmox-pool` | group (resource pool) |
| `custom-boundary-proxmox-bridge` | network (vmbr) |
| `custom-boundary-proxmox-vlan` | subnet-private |

## Modelling rules

- A Proxmox cluster is on-premises infrastructure: place its datacenter frame
  inside a Local & On-Premises site frame when the picture has more than one
  location.
- QEMU virtual machines and LXC containers sit in a pool or directly on a
  node; Ceph, ZFS, and NFS storage attach at the cluster or node level.
- Proxmox marks remain the property of Proxmox Server Solutions GmbH.

## Components

| Component | Category | Id |
|---|---|---|
| Reverse Proxy VM | networking | `proxmox:entry-service` |
| QEMU Virtual Machine | compute | `proxmox:app-service` |
| Ceph Storage | storage | `proxmox:object-store-service` |
| Database Container | databases | `proxmox:database-service` |
| PVE Node | compute | `proxmox:pve-node` |
| PVE Cluster | compute | `proxmox:pve-cluster` |
| Datacenter | compute | `proxmox:datacenter` |
| LXC Container | containers | `proxmox:lxc-container` |
| VM and CT Template | compute | `proxmox:vm-template` |
| HA Group | compute | `proxmox:ha-group` |
| Corosync Quorum Device | compute | `proxmox:quorum-device` |
| ZFS Pool | storage | `proxmox:zfs-pool` |
| Local and LVM Storage | storage | `proxmox:local-storage` |
| NFS and SMB Storage | storage | `proxmox:nfs-storage` |
| ISO Images and Templates | storage | `proxmox:iso-images` |
| Proxmox Backup Server | storage | `proxmox:backup-server` |
| Proxmox Mail Gateway | security | `proxmox:mail-gateway` |
| Linux Bridge | networking | `proxmox:linux-bridge` |
| SDN Zone | networking | `proxmox:sdn-zone` |
| Network Bond | networking | `proxmox:bond` |
| PVE Firewall | security | `proxmox:firewall` |
| Two-Factor Authentication | identity | `proxmox:two-factor` |
| API Token | identity | `proxmox:api-token` |
