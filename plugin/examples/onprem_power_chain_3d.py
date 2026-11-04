"""How electricity reaches a server, drawn with the 3D set.

The grid on the left -- a gas plant, the transmission line, the substation,
the utility feed at the fence; then the building's power chain in the order
the current takes it: MV switchgear, the transformer, the LV switchboard,
the ATS with its generators and fuel, the UPS with its batteries, the floor
PDU, the busway and its tap-off, the rack PDU, the server's two PSUs, the
server. Beside it the cooling that carries the heat back out. Draw it in the
icon look::

    python skills/infragram-architect/scripts/infragram.py compose examples/onprem_power_chain_3d.py --display icon
"""

from infragram.author import Diagram, Edge
from infragram.nodes.frames import generic, onprem as frames
from infragram.nodes.onprem import (
    iso_compute as compute,
    iso_energy as energy,
    iso_facility as facility,
)

with Diagram(
    "How power reaches a server",
    "From a gas plant through the grid and the building's power chain to a "
    "server's power supplies, with the cooling plant beside it -- drawn with "
    "the rendered on-premises set.",
    slug="onprem-power-chain-3d",
    providers=("onprem",),
) as diagram:
    with generic.Environment("Grid").row():
        plant = energy.IsoGasPowerPlant("Power plant", "CCGT · 400 MW")
        line = energy.IsoTransmissionLine("Transmission", "132 kV")
        substation = energy.IsoSubstation("Substation", "132 / 11 kV")
        feed = energy.IsoGridInterconnection("Utility feed", "2 × 11 kV")

    with frames.Datacenter("Datacentre DC-1").column():
        with frames.Row("Power room").row():
            mv = facility.IsoMvSwitchgear("MV switchgear", "11 kV · 4 cells")
            transformer = facility.IsoTransformer("Transformer", "11 kV / 400 V · 2 MVA")
            lv = facility.IsoLvSwitchboard("LV switchboard", "400 V · 4000 A")
            ats = facility.IsoChangeoverPanel("ATS", "utility / generator")
            generators = energy.IsoDieselGenset("Generators", "2 × 2 MVA · N+1")
            fuel = facility.IsoFuelTank("Fuel", "48 h")

        with frames.Row("UPS room").row():
            ups = facility.IsoUps("UPS", "2N · 1 MVA")
            batteries = facility.IsoLithiumBatteryCabinet("Batteries", "10 min")
            pdu = facility.IsoFloorPdu("Floor PDU", "A + B")

        with frames.Row("Hall A").row():
            busway = facility.IsoBusway("Busway", "A + B feeds")
            tap = facility.IsoBuswayTapOff("Tap-off", "63 A")
            rack_pdu = facility.IsoPdu("Rack PDU", "metered")
            psus = facility.IsoRedundantPsuPair("Server PSUs", "1 + 1 · 800 W")
            server = compute.IsoRackServer("Server", "2U")

        with frames.Row("Cooling").row():
            chillers = facility.IsoDryCooler("Chillers", "N+1")
            pumps = facility.IsoPumpSkid("Pumps", "duty / standby")
            crah = facility.IsoFanCoilUnit("CRAH", "N+1")
            aisle = facility.IsoAisleContainment("Cold aisle", "containment")

    plant >> Edge("132 kV") >> line >> substation >> Edge("11 kV") >> feed >> mv
    mv >> transformer >> Edge("400 V") >> lv >> ats >> ups >> pdu
    generators >> Edge("standby", dashed=True) >> ats
    fuel >> generators
    batteries - Edge("DC bus") - ups
    pdu >> busway >> tap >> rack_pdu >> psus >> server
    chillers >> pumps >> crah >> Edge("cold air", dotted=True) >> aisle >> server
