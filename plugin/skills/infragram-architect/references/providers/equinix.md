# Equinix library

Load only for Equinix content. The theme is [`equinix.json`](../../assets/themes/equinix.json)
(`theme="equinix"`). Coverage: **reviewed** - 27 service tiles drawn for this project (a white
glyph on the vendor's colour; they are this repository's own artwork, not the
vendor's icons), plus the frames and the theme. Four generic ids
(`entry-service`, `app-service`, `object-store-service`, `database-service`)
still resolve, for documents that use them; in a colocation they stand for
the customer's own equipment in the cage. Products with no tile yet take the
shared neutral primitives. Equinix Metal is not in the library: the service
reached end of life on 2026-06-30.

## Frames

Starter stack: **Metro → IBX → cage → cabinet**. Equinix Fabric is a network
frame that spans metros; draw it beside the metro frames, not inside one.

| Frame id | Kind |
|---|---|
| `custom-boundary-equinix-metro` | region |
| `custom-boundary-equinix-ibx` | site |
| `custom-boundary-equinix-cage` | location |
| `custom-boundary-equinix-cabinet` | server-group |
| `custom-boundary-equinix-fabric` | network |

## Modelling rules

- A metro holds one or more IBX data centers; a cage sits in one IBX and
  holds the customer's cabinets. Colocated servers, storage and databases go
  in a cabinet frame.
- A Fabric port is the physical port in the cage. Virtual connections run from
  a port (or a Network Edge device, or a Fabric Cloud Router) to a service
  profile: a cloud's on-ramp (AWS Direct Connect, Azure ExpressRoute, Google
  Cloud Partner Interconnect) or another Fabric customer. Draw the cloud side
  with that cloud's own components (`aws:direct-connect`,
  `azure:expressroute-circuits`, `gcp:partner-interconnect`).
- A cross connect is a physical cable inside an IBX, to a carrier or another
  customer's cage; Metro Connect joins two IBXs of one metro.
- Network Edge devices are virtual appliances hosted by Equinix, not in the
  customer's cage: draw them inside the metro frame, outside the cage.
- Equinix, Equinix Fabric, Network Edge and IBX are trademarks of Equinix, Inc.

## Components

| Component | Category | Id |
|---|---|---|
| Network Edge Load Balancer | networking | `equinix:entry-service` |
| Colocated Server | compute | `equinix:app-service` |
| Colocated Storage Array | storage | `equinix:object-store-service` |
| Colocated Database Server | databases | `equinix:database-service` |
| Fabric Port | networking | `equinix:fabric-port` |
| Fabric Virtual Connection | networking | `equinix:fabric-virtual-connection` |
| Fabric Cloud Router | networking | `equinix:fabric-cloud-router` |
| Fabric Cloud Connection | networking | `equinix:fabric-cloud-connection` |
| Fabric Service Profile | networking | `equinix:service-profile` |
| Fabric Service Token | security | `equinix:service-token` |
| Metro Connect | networking | `equinix:metro-connect` |
| Equinix Internet Exchange | networking | `equinix:internet-exchange` |
| Equinix Internet Access | networking | `equinix:internet-access` |
| Equinix Precision Time | networking | `equinix:precision-time` |
| Network Edge Virtual Device | networking | `equinix:network-edge-device` |
| Network Edge Router | networking | `equinix:network-edge-router` |
| Network Edge Firewall | security | `equinix:network-edge-firewall` |
| Network Edge SD-WAN | networking | `equinix:network-edge-sdwan` |
| Device Link Group | networking | `equinix:device-link-group` |
| ACL Template | security | `equinix:acl-template` |
| Identity and Access Management | identity | `equinix:iam` |
| IBX Data Center | colocation | `equinix:ibx-data-center` |
| Cage | colocation | `equinix:cage` |
| Cabinet | colocation | `equinix:cabinet` |
| Cross Connect | colocation | `equinix:cross-connect` |
| Power Circuit | colocation | `equinix:power-circuit` |
| Smart Hands | colocation | `equinix:smart-hands` |
