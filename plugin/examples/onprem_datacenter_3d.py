"""An on-premises datacentre drawn with the 3D set.

Internet and staff on the outside; a perimeter of edge routers, a firewall
cluster and a spine-leaf fabric; in the hall, a compute row (a hypervisor
cluster, a Kubernetes control plane and worker pool, a GPU cluster, a custom
build server) and a storage row (SAN, all-flash array, a Ceph-style storage
cluster, a database cluster, backup and tape); the facilities behind them;
and a campus with switches, Wi-Fi, laptops (one out of service), an
iPhone-style and an Android phone. Every container is one of the on-prem
frames -- datacenter, security zone, cage, rack row, cluster, site. Draw it
in the icon look, so the equipment stands on the page with its captions::

    python skills/infragram-architect/scripts/infragram.py compose examples/onprem_datacenter_3d.py --display icon
"""

from infragram.author import Diagram, Edge
from infragram.nodes.custom import custom_server
from infragram.nodes.frames import generic, onprem as frames
from infragram.nodes.onprem import (
    iso_client as client,
    iso_compute as compute,
    iso_facility as facility,
    iso_network as net,
    iso_platform as platform,
    iso_security as sec,
    iso_storage as storage,
)

with Diagram(
    "On-premises datacentre, 3D",
    "A perimeter, a hall with a compute row and a storage row, the power and "
    "cooling behind them, and a campus of users -- drawn with the rendered "
    "on-premises set inside the on-prem frames.",
    slug="onprem-datacenter-3d",
    providers=("onprem",),
) as diagram:
    internet = net.IsoInternet("Internet", "two ISPs")
    staff = client.IsoUsers("Staff", "head office")

    with frames.Datacenter("Datacentre DC-1").column():
        with frames.SecurityZone("Perimeter").row():
            edge = net.IsoEdgeRouter("Edge routers", "BGP · dual-homed")
            firewall = sec.IsoFirewallCluster("Firewall cluster", "active/active · IDS")
            fabric = net.IsoSpineLeafFabric("Spine-leaf fabric", "EVPN · 100G spines")

        with frames.Cage("Hall A").column():
            with frames.Row("Compute row").row():
                with frames.Cluster("Hypervisor cluster").row():
                    hosts = compute.IsoHypervisorCluster("Hypervisor hosts", "3 × 2U · HA")
                with frames.Cluster("Kubernetes").row():
                    control = platform.IsoKubernetesControlPlane("Control plane", "3 nodes · etcd")
                    workers = platform.IsoKubernetesWorkerPool("Worker pool", "4 nodes")
                gpu = compute.IsoGpuCluster("GPU cluster", "2 × 4U · 8 GPUs each")
                build = custom_server(
                    "Build server", "custom 2U · 8 bays", units=2, bays=8, family="platform"
                )

            with frames.Row("Storage row").row():
                san_switch = storage.IsoSanSwitch("SAN switches", "FC · 32G")
                array = storage.IsoStorageArray("Storage array", "all-flash")
                ceph = storage.IsoStorageCluster("Storage cluster", "Ceph · 3 nodes")
                dbc = storage.IsoDatabaseCluster("Database cluster", "primary + 2 replicas")
                backup = storage.IsoBackupServer("Backup server", "nightly")
                tape = storage.IsoTapeLibrary("Tape library", "LTO-9 · offsite")

        with generic.Environment("Facilities").row():
            ups = facility.IsoUps("UPS", "2N")
            pdu = facility.IsoPdu("PDU", "A + B feeds")
            cooling = facility.IsoFanCoilUnit("Cooling", "CRAC · N+1")
            racks = facility.IsoRackRow("Rack row", "12 × 42U")

    with frames.Site("Campus").row():
        access = net.IsoAccessSwitch("Access switches", "PoE · 48 ports")
        ap = net.IsoWirelessAccessPoint("Wi-Fi", "Wi-Fi 6E")
        laptops = client.IsoLaptop("Laptops", "staff")
        broken = client.IsoLaptopBroken("Laptop", "out of service")
        iphone = client.IsoPhoneIos("iPhone", "iOS · MDM enrolled")
        android = client.IsoPhoneAndroid("Galaxy", "Android · MDM enrolled")

    internet >> Edge("uplinks") >> edge >> firewall >> fabric
    fabric >> Edge("100G") >> hosts
    hosts >> Edge("VMs", dotted=True) >> control
    control >> Edge("API") >> workers
    fabric >> Edge("25G") >> gpu
    fabric >> build
    hosts >> Edge("FC") >> san_switch >> array
    workers >> Edge("RBD", dotted=True) >> ceph
    dbc >> Edge("WAL", dashed=True) >> backup
    backup >> Edge("stream", dotted=True) >> tape
    fabric >> Edge("trunk") >> access
    access >> ap >> laptops
    ap >> iphone
    ap >> android
    access - Edge("no link", dotted=True) - broken
    staff >> Edge("VPN", dashed=True) >> firewall
    ups >> pdu >> racks
