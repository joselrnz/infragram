"""A home's energy, from the pole to the plug, drawn with the 3D set.

The last mile of the grid on top -- the pad-mount, the pole, the service
drop and the meter; the panel wall beneath it with the breaker panel, the
sub-panel in the garage, the transfer switch and the portable generator it
takes; the roof's solar through its inverter into the home battery; and the
loads -- heat pump and thermostat, the EV charger, the lights, the plugs --
with the home hub and the smart meter reporting back. Draw it in the icon
look::

    python skills/infragram-architect/scripts/infragram.py compose examples/onprem_home_energy_3d.py --display icon
"""

from infragram.author import Diagram, Edge
from infragram.nodes.frames import generic
from infragram.nodes.onprem import (
    iso_energy as energy,
    iso_facility as facility,
    iso_industrial as industrial,
    iso_network as network,
)

with Diagram(
    "A home's energy, from the pole to the plug",
    "The grid's last mile, the panel wall, rooftop solar and a battery, and "
    "the loads they serve -- drawn with the rendered on-premises set.",
    slug="onprem-home-energy-3d",
    providers=("onprem",),
    direction="down",
) as diagram:
    with generic.Environment("The street").row():
        padmount = energy.IsoPadMountedTransformer("Pad-mount", "11 kV / 230 V")
        pole = energy.IsoUtilityPole("Utility pole", "230 V secondary")
        drop = energy.IsoServiceDrop("Service drop", "triplex · 100 A")
        meter = energy.IsoSmartMeter("Smart meter", "AMI · net metering")

    with generic.Environment("The panel wall").row():
        socket = energy.IsoMeterSocket("Meter socket", "100 A")
        panel = energy.IsoBreakerPanel("Breaker panel", "100 A · 24 ways")
        subpanel = energy.IsoSubPanel("Garage sub-panel", "40 A")
        transfer = energy.IsoHomeTransferSwitch("Transfer switch", "6 circuits")
        generator = facility.IsoMobileGenerator("Portable generator", "7 kW · petrol")

    with generic.Environment("Solar and storage").row():
        solar = industrial.IsoSolarArray("Rooftop solar", "6.4 kWp")
        inverter = industrial.IsoSolarInverter("Hybrid inverter", "5 kW")
        battery = energy.IsoHomeBattery("Home battery", "13.5 kWh")

    with generic.Environment("The loads").row():
        heatpump = energy.IsoHeatPump("Heat pump", "air source · 8 kW")
        thermostat = energy.IsoSmartThermostat("Thermostat", "schedules")
        charger = energy.IsoHomeEvCharger("EV charger", "7 kW wallbox")
        lights = industrial.IsoLightingController("Lighting", "smart switches")
        plugs = industrial.IsoPlugLoad("Appliances", "kitchen · laundry")
        hub = industrial.IsoIotGateway("Home hub", "Zigbee · Wi-Fi")
        wifi = network.IsoWirelessAccessPoint("Wi-Fi", "mesh")

    # the last mile
    padmount >> Edge("230 V") >> pole >> drop >> meter >> socket >> Edge("100 A") >> panel
    panel >> Edge("40 A") >> subpanel
    panel >> transfer
    generator >> Edge("standby", dashed=True) >> transfer

    # solar and storage
    solar >> Edge("DC") >> inverter
    inverter - Edge("charge/discharge") - battery
    inverter >> Edge("AC · backfeed") >> panel

    # the loads
    panel >> heatpump
    thermostat >> Edge("calls", dotted=True) >> heatpump
    subpanel >> Edge("32 A") >> charger
    panel >> lights
    panel >> plugs
    hub >> Edge("Zigbee", dotted=True) >> thermostat
    hub >> Edge("Zigbee", dotted=True) >> lights
    wifi >> Edge("Wi-Fi", dotted=True) >> hub
    meter >> Edge("reads", dotted=True) >> hub
