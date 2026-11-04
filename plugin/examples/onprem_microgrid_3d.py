"""A campus microgrid, drawn with the 3D set.

The utility connection and the site's own generation along the top -- solar
field and floating solar into a DC switchboard and central inverters, a wind
turbine, a gas CHP, a battery on its power conversion system, an
electrolyser making hydrogen for the fuel cell; the campus switchboard that
joins them, with the microgrid controller, SCADA and the IoT gateway beside
it; then the loads -- a ground-source heat pump on the district heating loop,
offices, a warehouse, an edge datacentre, the EV plaza, the site lighting and
the meters that report back. Draw it in the icon look::

    python skills/infragram-architect/scripts/infragram.py compose examples/onprem_microgrid_3d.py --display icon
"""

from infragram.author import Diagram, Edge
from infragram.nodes.frames import generic
from infragram.nodes.onprem import (
    iso_energy as energy,
    iso_facility as facility,
    iso_industrial as industrial,
)

with Diagram(
    "Campus microgrid",
    "A grid connection and on-site solar, wind, CHP, battery and hydrogen "
    "behind one campus switchboard, the controller that islands it, and the "
    "buildings, heat loop and chargers it serves -- drawn with the rendered "
    "on-premises set.",
    slug="onprem-microgrid-3d",
    providers=("onprem",),
    direction="down",
) as diagram:
    with generic.Environment("Sources").row():
        with generic.Zone("Utility").row():
            grid = energy.IsoGridInterconnection("Grid connection", "33 kV · import / export")
            padmount = energy.IsoPadMountedTransformer("Pad-mount", "33 kV / 400 V")

        with generic.Zone("On-site generation").row():
            solar = energy.IsoSolarFarm("Solar field", "5 MWp")
            floating = energy.IsoFloatingSolar("Floating solar", "1 MWp · reservoir")
            wind = energy.IsoWindTurbine("Wind turbine", "3 MW")
            chp = energy.IsoChpUnit("CHP", "2 MW · gas")
            bess = energy.IsoBessContainer("Battery", "4 MW · 16 MWh")
            electrolyser = energy.IsoHydrogenElectrolyser("Electrolyser", "1 MW PEM")
            h2 = energy.IsoHydrogenStorage("H2 storage", "500 kg")
            fuelcell = energy.IsoFuelCell("Fuel cell", "500 kW")

    with generic.Environment("Conversion and control").row():
        dc = energy.IsoDcSwitchboard("DC switchboard", "1,500 V")
        inverter = industrial.IsoSolarInverter("Inverters", "4 × 1.25 MW")
        pcs = energy.IsoPowerConversionSystem("PCS", "bidirectional")
        lv = facility.IsoLvSwitchboard("Campus switchboard", "400 V · 6,300 A")
        controller = facility.IsoMicrogridController("Microgrid controller", "islanding · dispatch")
        scada = industrial.IsoScada("SCADA", "site telemetry")
        gateway = industrial.IsoIotGateway("IoT gateway", "meters · sensors")

    with generic.Environment("Loads").row():
        heatpump = energy.IsoHeatPump("Heat pump", "ground source")
        district = energy.IsoDistrictHeating("District heating", "campus loop")
        office = facility.IsoOfficeBuilding("Offices", "1.2 MW")
        warehouse = facility.IsoWarehouse("Warehouse", "400 kW")
        edge_dc = facility.IsoContainerDatacenter("Edge datacentre", "600 kW")
        ev = facility.IsoEvChargingPlaza("EV plaza", "20 × 150 kW")
        lights = facility.IsoStreetlight("Site lighting", "LED")
        meter = industrial.IsoEnergyMeter("Energy meters", "per building")

    # sources
    grid >> Edge("33 kV") >> padmount >> Edge("400 V · import / export") >> lv
    solar >> Edge("1,500 V DC") >> dc
    floating >> dc
    dc >> inverter >> lv
    wind >> Edge("690 V") >> lv
    chp >> lv
    bess - Edge("DC") - pcs
    pcs - Edge("charge / discharge") - lv
    lv >> Edge("surplus", dashed=True) >> electrolyser
    electrolyser >> Edge("H2") >> h2 >> Edge("H2", dotted=True) >> fuelcell
    fuelcell >> lv

    # control
    controller >> Edge("dispatch", dotted=True) >> lv
    scada - controller
    gateway >> Edge("telemetry", dotted=True) >> scada
    meter >> Edge("reads", dotted=True) >> gateway

    # loads
    lv >> Edge("400 V") >> heatpump
    heatpump >> Edge("heat", dotted=True) >> district >> Edge("heat", dotted=True) >> office
    lv >> office
    lv >> warehouse
    lv >> edge_dc
    lv >> ev
    lv >> lights
