"""Items rendered by spec, beside the shipped set.

None of these exist in the table: a 3U server with twelve bays in the storage
colour with a database badge, a 48-port switch in a colour of its own, a
five-node cluster of 2U machines, a six-cell MV switchgear lineup, a small
modular reactor carrying the power mark, a plain 1U with no badge at all.
Each is rendered once when the node is made, measured, cached by its spec
hash, and carried in the document beside the ordinary icons::

    python skills/infragram-architect/scripts/infragram.py compose examples/onprem_custom_3d.py
"""

from infragram.author import Diagram, Edge
from infragram.nodes.frames import onprem as frames
from infragram.nodes.iso import Iso
from infragram.nodes.onprem import iso_energy as energy, iso_network as net

with Diagram(
    "Rendered by spec",
    "Six items no table has, rendered from their recipes at compose time, wired to shipped ones.",
    slug="onprem-custom-3d",
    providers=("onprem",),
) as diagram:
    feed = energy.IsoGridInterconnection("Utility feed", "11 kV")
    smr = Iso(
        "Unit 2", "SMR · 300 MW", recipe="reactor", family="energy", glyph="power", kind="smr"
    )

    with frames.Datacenter("Datacentre").column():
        with frames.Row("Power room").row():
            mv = Iso(
                "MV switchgear",
                "6 cells",
                recipe="switchgear",
                family="facility",
                cells=6,
                kind="mv",
            )

        with frames.Row("Compute row").row():
            core = Iso(
                "Core switch",
                "48 ports",
                recipe="switch",
                colour="#0f766e",
                glyph="arrows",
                count=48,
            )
            cluster = Iso(
                "Hypervisors", "5 × 2U", recipe="cluster", family="compute", count=5, unit="gpu"
            )
            db = Iso(
                "DB-01",
                "PostgreSQL 16",
                recipe="server",
                family="storage",
                glyph="database",
                units=3,
                drivesN=12,
            )
            plain = Iso(
                "Node 7",
                "1U · no badge",
                recipe="server",
                colour="#5b21b6",
                badge=False,
                units=1,
                drivesN=0,
            )

    smr >> Edge("132 kV") >> feed >> Edge("11 kV") >> mv
    mv >> Edge("400 V") >> cluster
    core >> Edge("25G") >> cluster
    core >> Edge("25G") >> db
    core >> plain
    edge = net.IsoEdgeRouter("Edge router", "BGP")
    edge >> Edge("uplink") >> core
