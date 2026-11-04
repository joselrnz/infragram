# Local & On-Premises library

Load this reference for datacenter, office, branch, lab, edge, and other
provider-neutral infrastructure. The theme is [`onprem.json`](../../assets/themes/onprem.json)
(`theme="onprem"`). Coverage: **reviewed**.

The library combines **241 product icons** from three mingrammer/diagrams
v0.25.1 node sets with **24 neutral operational components** (bare-metal
server, hypervisor host, virtual machine, application server, database
server, file server, object-storage appliance, backup appliance, directory
service, local users, network switch, router / gateway, perimeter firewall,
VPN gateway, load balancer, DNS server, workstation, laptop, mobile device,
container host, Kubernetes cluster, message broker, monitoring server,
administration terminal):

- the complete `diagrams.onprem` catalog (172 icons) across 31 source
  categories: compute, Proxmox, clients, networking, DNS, containers,
  databases, in-memory services, storage, registries, queues, messaging,
  CI/CD, GitOps, infrastructure as code, monitoring, logging, tracing,
  analytics, ETL, MLOps, security, identity, certificates, authentication,
  groupware, search, version control, workflow, and aggregation;
- the vendor-neutral `diagrams.generic` set (25 icons): firewall, router,
  switch, subnet and VPN; rack, storage and database hardware; datacenter;
  mobile and tablet devices; ten operating systems; QEMU, VirtualBox, VMware
  and Xen virtualization (catalog categories `generic-*`);
- the self-hosted `diagrams.elastic` set (44 icons): Elasticsearch, Kibana,
  Logstash, Beats, Agent, Observability, Security, Enterprise Search and
  Elastic Cloud (catalog categories `elastic-*`).

Self-hosted platform marks that mingrammer does not carry (Pi-hole, WireGuard,
Portainer, Forgejo, TrueNAS, Home Assistant, Uptime Kuma, and more) ship as
shared primitives available in every library. The artwork is PNG wrapped in
SVG and is embedded in exports, so interactive HTML stays offline.

## Isometric (3D) set

**845 rendered 3D models** of on-premises equipment ship in the same
collection under the `iso-*` categories, so a diagram can be drawn in the
"3D" style of cloud-diagram tools: rack, tower, blade and micro servers, a
24-bay storage server, blade chassis, racks, rack rows and cages, storage
arrays, disk shelves, NAS, SAN switches, tape libraries, switches, a
chassis switch, a spine-leaf fabric, routers, firewalls, access points,
patch panels, UPS, PDU, cooling, generators, laptops (and one that is
broken), an iPhone-style and an Android phone, a tablet, PLCs, sensors,
the cables between them (Cat6 copper, LC fibre, DAC/twinax, console, IEC
power), and the systems they form -- hypervisor, HPC, GPU and
hyperconverged clusters, a Kubernetes control plane and worker pool,
storage and database clusters, HA, load-balancer, DNS and firewall pairs
-- each painted by family (compute blue, storage teal, network violet,
security red, facility amber, client slate, platform indigo, operations
cyan, industrial green, energy fuchsia).

The **energy** family follows electricity from the plant to the rack:
coal, gas, nuclear, biomass and geothermal plants, reactors, a dam and a
pumped-storage station, wind and solar farms, turbines, boilers, gen-sets,
a battery storage container; then the grid -- pylons and lines, a
substation, transformers, breakers, disconnects, arresters, capacitor
banks, poles, pad-mounts, ring main units, HVDC. Inside the building the
facility family carries the chain on: MV feeder and switchgear, LV
switchboard, paralleling gear, ATS, UPS and batteries, DC plant and
rectifiers, floor PDU and remote power panels, busway and tap-offs, rack
PDUs, the server's own PSUs, whips and cords, earthing, SPDs, load banks;
and the cooling plant that takes the heat back out -- towers, dry coolers,
CDUs, immersion tanks, manifolds, pump skids, economisers, ducts, fire
suppression. `examples/onprem_power_chain_3d.py` draws that chain end to
end; `examples/onprem_power_grid_3d.py` draws the grid itself from the
plants to the meter, tier under tier, and `examples/onprem_microgrid_3d.py`
a campus microgrid behind one switchboard, and
`examples/onprem_home_energy_3d.py` a home from the pole to the plug.

Beyond the machine room the set reaches the outside plant (cell towers and
small cells, satellite dishes, OLT and ONT, street cabinets, splice closures
and trays, cable reels, central office, point of presence), the sites a
network joins (office, headquarters, warehouse, factory, hospital, store,
home office, gatehouse, datacentre building, container datacentre, fence,
barrier, bollards, floodlights, water tower), physical security and safety
(turnstiles, speed gates, intercoms, key cabinets, safes, first aid, AED,
fire panels, exit signs, hose reels), the vehicles on site (fuel truck,
vans and trucks, generator trailer, fleet car, forklift, drone, inspection
robot), the test bench (oscilloscope, spectrum analyser, bench supply,
network tester, certifier, OTDR, multimeter), the office (meeting room,
video bar, conference phone, headset, shredder, payment terminal, ATM),
media, virtual constructs (virtual switch and router, overlay, pod,
ingress, namespace, tenant), process plant (reactor, column, pipeline,
crane, weighbridge, silo, water treatment) and the people in it -- and
the plant's internals (steam generator, pressuriser, coolant
pump, fuel assembly, spent fuel pool, dry casks), renewables in detail
(heliostat tower, trackers, offshore foundations and platform, submarine
cable and the ship that lays it, tidal, flow battery, molten salt,
compressed air, flywheel), the grid's last mile down to the meter socket
and the breaker panel behind it, building services (HVAC, fire, elevator,
loading dock, mantrap), outside plant and radio (manhole, duct bank,
pedestal, strand, DWDM, microwave, sector antenna, GPS, PTP), process
machines (pump, blower, kiln, furnace, press, CNC, pumpjack, flare, LPG
sphere, clarifier, desalination), more roles and vehicles; and
the world the plant sits in: transport (traffic light, railway
signal, locomotive, tram, railway station, bus stop, fuel station, road
and suspension bridges), marine (container ship, ferry, oil tanker,
ship-to-shore crane, lighthouse), air and space (airliner, helicopter,
control tower, helipad, satellite, radome), the town (school, apartment
block, bank, hotel, parking garage, mall, fire station, stadium,
greenhouse, lockers, vending machine), the site (drilling rig, mine
headframe, ambulance, police car, tractor, dump truck, excavator, mixer
and refuse trucks, outside-broadcast van) and the home (siren, smart
lock, video doorbell, panic button, smart speaker, robot vacuum, set-top
box).

Every kind of data store is a drum of its own: relational, document,
key-value, time-series, graph, search index, vector, ledger, columnar,
OLAP cube, in-memory; distributed SQL, sharded, primary and replica,
multi-master; data lake, lakehouse and object store (the wide drums);
message queue, event stream, cache cluster, log and metrics stores. Down
to the parts -- bare HDD, SSD and NVMe drives, RAID and HBA and network
cards, SFP and QSFP transceivers -- and out to the building: raised-floor
tiles, aisle containment, fire and leak and airflow sensors, extinguisher,
fuel tank, transformer, switchgear, busway, crash cart, water pump, EV
charger, solar array, battery storage; security keys, smart cards,
biometric readers, a secure door; a monitor, projector, wall display,
docking station, POS terminal, rugged handheld; valves, motors, drives, a
robot arm, a conveyor, an AGV; and the platform and operations services
between them (registry, config, feature flags, event bus, scheduler,
functions, notebooks, ETL, stream processing, runbooks, status page, NOC
wall).

When none of the 845 is the thing, **render one by spec**: any of the
builders behind the set, with its own knobs, any colour, any glyph or none
-- `Iso("DB-01", recipe="server", family="storage", glyph="database",
units=3, drivesN=12)` renders once, is measured, cached and carried in the
document (see "Items rendered by spec" in [compose.md](../compose.md)).

A **custom server** is picked by shape rather than name: 1U, 2U or 4U,
blank or with 4, 8, 12 or 24 bays, in any family colour, no badge:

```python
from infragram.nodes.custom import custom_server

build = custom_server("Build server", "custom 2U · 8 bays", units=2, bays=8, family="platform")
```

They are real renders, not drawings: each item is built procedurally in
three.js -- chassis with rack ears, hot-swap sleds with their lights, port
rows, perforated fronts, glass doors, lit screens, people with arms and
what they carry, software concepts as objects and virtual constructs in
glass -- lit and shadowed from
one fixed three-quarter camera and rendered in headless Chromium to a 192 px
256-colour transparent PNG, shipped inside an SVG like the imported artwork.
The set is one table, rendered once and installed with the rest of the
artwork, so a new shipped item is one more line in it -- maintainer work in
a checkout; a diagram that needs a shape the set lacks renders it by spec,
as above. In code they are the `iso_*` categories of the on-prem package:

```python
from infragram.nodes.onprem import iso_compute, iso_network, iso_storage

core = iso_network.IsoCoreSwitch("Core switch", "stacked pair")
san = iso_storage.IsoStorageArray("SAN", "all-flash")
```

Draw such a diagram in the icon look (`display="icon"`) so the objects stand
on the page with their captions beneath; every side of every icon seats a
link on the drawing (ADR 0006).

## Frames

Starter stack: **Datacenter → network → VLAN/subnet → compute cluster**. The
starter asserts nothing about a hypervisor, private-cloud product, or
topology; add those as components.

| Frame id | Kind |
|---|---|
| `custom-boundary-onprem-datacenter` | site |
| `custom-boundary-onprem-site` | location (office, branch, lab, edge) |
| `custom-boundary-onprem-network` | network |
| `custom-boundary-onprem-subnet` | subnet-private (VLAN / subnet) |
| `custom-boundary-onprem-security-zone` | security-zone |
| `custom-boundary-onprem-cluster` | cluster |
| `custom-boundary-onprem-rack` | server-group (rack, chassis, server group) |
| `custom-boundary-onprem-row` | server-group (a row of racks in a hall or pod) |
| `custom-boundary-onprem-cage` | location (colocation cage or private suite) |

For hybrid pictures, a site frame is the on-premises end of `vpn`
or `vif` links into a cloud library's frames.

## Modelling rules

- Keep product marks on product components and keep the neutral operational
  components vendor-agnostic. A product's presence in the library is a drawing
  capability, not a claim that it is deployed.
- Segment with network and VLAN frames plus firewall and gateway components;
  L2/L3 detail (IP plans, VLAN tables, cabling) is out of scope.
- On-premises, generic and Elastic product artwork from mingrammer/diagrams
  v0.25.1 (MIT); neutral primitives derived from Tabler Icons (MIT);
  self-hosted platform marks from Simple Icons (CC0). Depicted products'
  marks remain their owners' trademarks.
