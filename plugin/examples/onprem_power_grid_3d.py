"""The power grid from the plant to the meter, drawn with the 3D set.

Generation on top -- the thermal plants with their step-up transformer and
generator breaker, the renewables and the grid battery; the 400 kV
transmission line with its towers, compensation and the HVDC interconnector;
the transmission substation in the order the current passes it: breaker,
disconnect, instrument transformers, arrester, the 400 / 132 kV transformer,
with the protection and its station battery beside; then distribution -- the
primary substation, kiosk and ring main unit feeding the large customers at
11 kV, and the overhead feeder with its poles, recloser, regulator, capacitor,
fault indicator and fuse cut-out down to the pad-mount and the 400 V
customers; the control centre underneath. Draw it in the icon look::

    python skills/infragram-architect/scripts/infragram.py compose examples/onprem_power_grid_3d.py --display icon
"""

from infragram.author import Diagram, Edge
from infragram.nodes.frames import generic
from infragram.nodes.onprem import (
    iso_energy as energy,
    iso_facility as facility,
    iso_industrial as industrial,
)

with Diagram(
    "The power grid, from the plant to the meter",
    "Generation, 400 kV transmission, the transmission substation, primary "
    "and feeder distribution and the customers at the end of the line, with "
    "the control centre that runs it -- drawn with the rendered on-premises set.",
    slug="onprem-power-grid-3d",
    providers=("onprem",),
    direction="down",
) as diagram:
    with generic.Environment("Generation").row():
        with generic.Zone("Thermal").row():
            nuclear = energy.IsoNuclearPowerPlant("Nuclear", "2 × 1,100 MW")
            coal = energy.IsoCoalPowerPlant("Coal", "600 MW")
            fgd = energy.IsoFlueGasDesulphurisation("FGD", "scrubber")
            ccgt = energy.IsoGasPowerPlant("CCGT", "400 MW")
            gsu = energy.IsoGeneratorStepUpTransformer("GSU transformer", "21 / 400 kV")
            gen_breaker = energy.IsoGeneratorBreaker("Generator breaker", "21 kV")

        with generic.Zone("Renewables").row():
            dam = energy.IsoHydroelectricDam("Hydro dam", "300 MW")
            pumped = energy.IsoPumpedStorage("Pumped storage", "1 GW · 8 h")
            wind = energy.IsoWindFarm("Wind farm", "60 × 4 MW")
            offshore = energy.IsoOffshoreWindTurbine("Offshore wind", "12 MW class")
            solar = energy.IsoSolarFarm("Solar farm", "150 MWp")
            bess = energy.IsoBessContainer("Grid battery", "100 MW · 400 MWh")

    with generic.Environment("Transmission · 400 kV").column():
        with generic.Zone("Lines").row():
            switchyard = energy.IsoSwitchyardBus("Switchyard", "400 kV bus")
            tower = energy.IsoTensionTower("Tension tower", "angle · dead-end")
            line = energy.IsoTransmissionLine("400 kV line", "twin bundle")
            shunt = energy.IsoShuntReactor("Shunt reactor", "150 MVAr")
            series_cap = energy.IsoSeriesCapacitor("Series capacitor", "compensation")
            line_trap = energy.IsoLineTrap("Line trap", "PLC coupling")
            hvdc = energy.IsoHvdcConverter("HVDC converter", "±320 kV")
            interconnector = energy.IsoGridInterconnection("Interconnector", "neighbouring grid")

        with generic.Zone("Transmission substation · 400 / 132 kV").row():
            relays = energy.IsoProtectionRelayPanel("Protection", "distance · differential")
            battery = energy.IsoSubstationBattery("Station battery", "110 V DC")
            breaker = energy.IsoHvCircuitBreaker("HV breaker", "SF6 · 400 kV")
            disconnect = energy.IsoDisconnectSwitch("Disconnect", "isolator")
            ct_vt = energy.IsoInstrumentTransformer("CT / VT", "metering · protection")
            arrester = energy.IsoSurgeArrester("Surge arrester", "ZnO")
            transformer = energy.IsoPowerTransformer("Power transformer", "400 / 132 kV · 500 MVA")
            statcom = energy.IsoStatcom("STATCOM", "±100 MVAr")

    with generic.Environment("Distribution").row():
        with generic.Zone("Primary substation · 132 / 33 / 11 kV").column():
            with generic.Zone("Substation").row():
                cap_bank = energy.IsoCapacitorBank("Capacitor bank", "power factor")
                primary = energy.IsoSubstation("Primary substation", "132 / 33 kV")
                kiosk = energy.IsoKioskSubstation("Kiosk substation", "33 / 11 kV")
                rmu = energy.IsoRingMainUnit("Ring main unit", "11 kV · 3-way")
                joint_bay = energy.IsoCableJointBay("Cable joint bay", "underground 11 kV")

            with generic.Zone("Large customers · 11 kV").row():
                datacentre = facility.IsoDatacenterBuilding("Datacentre", "2 × 11 kV feeds")
                factory = facility.IsoFactory("Factory", "own substation")
                hospital = facility.IsoHospital("Hospital", "priority load")

        with generic.Zone("Feeder · 11 kV").column():
            with generic.Zone("Overhead line").row():
                overhead = energy.IsoMvOverheadLine("Overhead line", "11 kV")
                pole = energy.IsoUtilityPole("Utility pole", "wood · 12 m")
                recloser = energy.IsoRecloser("Recloser", "auto-reclose")
                regulator = energy.IsoVoltageRegulator("Voltage regulator", "±10 %")
                pole_cap = energy.IsoPoleCapacitorBank("Pole capacitor", "switched")
                fault_ind = energy.IsoLineFaultIndicator("Fault indicator", "reports to SCADA")
                cutout = energy.IsoFuseCutout("Fuse cut-out", "drop-out")
                padmount = energy.IsoPadMountedTransformer("Pad-mount", "11 kV / 400 V")

            with generic.Zone("Customers · 400 V").row():
                ev = facility.IsoEvChargingPlaza("EV plaza", "12 × 150 kW")
                office = facility.IsoOfficeBuilding("Offices", "400 V")
                meter = energy.IsoSmartMeter("Smart meter", "AMI")
                homes = facility.IsoHomeOffice("Homes", "230 V")
                streetlight = facility.IsoStreetlight("Street lighting", "LED")

    with generic.Environment("Grid control").row():
        control = energy.IsoGridControlCentre("Control centre", "EMS · dispatch")
        scada = industrial.IsoScada("SCADA", "telemetry")
        historian = industrial.IsoHistorian("Historian", "PMU data")

    # generation
    nuclear >> Edge("21 kV") >> gsu
    coal >> gsu
    ccgt >> gsu
    coal >> Edge("flue gas", dotted=True) >> fgd
    gsu >> gen_breaker >> Edge("400 kV") >> switchyard
    pumped - Edge("pump / generate") - dam
    dam >> switchyard
    wind >> switchyard
    solar >> Edge("daytime") >> bess
    bess >> Edge("charge / discharge") >> switchyard
    offshore >> Edge("export cable", dashed=True) >> hvdc

    # transmission
    switchyard >> tower >> line >> shunt >> series_cap >> line_trap >> Edge("400 kV") >> breaker
    hvdc >> Edge("±320 kV DC", dashed=True) >> interconnector
    battery - Edge("110 V DC") - relays
    relays >> Edge("trip", dashed=True) >> breaker
    breaker >> disconnect >> ct_vt >> arrester >> transformer >> Edge("132 kV") >> primary
    transformer - statcom

    # distribution
    cap_bank - primary
    primary >> Edge("33 kV") >> kiosk >> Edge("11 kV") >> rmu >> Edge("underground") >> joint_bay
    primary >> Edge("11 kV · 2 feeds") >> factory
    kiosk >> hospital
    joint_bay >> datacentre
    rmu >> Edge("11 kV") >> overhead >> pole >> recloser >> regulator >> pole_cap
    pole_cap >> fault_ind >> cutout >> padmount
    padmount >> Edge("400 V") >> meter >> homes
    padmount >> ev
    padmount >> office
    padmount >> streetlight

    # control
    control >> scada >> historian
    meter >> Edge("AMI reads", dotted=True) >> scada
