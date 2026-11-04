"""Campus LAN with two buildings and a branch office, written as described.

An on-premises estate built entirely from generic and on-premises frames, the
shared primitive library and the on-premises library's plain network-switch
glyph: no vendor icons, no coordinates. The campus
frame lays its closets side by side (``.row()``); the MDF keeps the order
traffic enters (``.keep_order()``) instead of letting the layout pull the
edge router towards the uplinks.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/campus_lan.py \
        --formats template,html,svg,png --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared, onprem as lan
from infragram.nodes.frames import generic, onprem

net = shared.networking
sec = shared.security
ident = shared.identity


def switch(name: str, detail: str):
    """An access switch drawn with the plain network-switch glyph."""
    return lan.generic_network.Switch(name, detail, icon="network-switch")


with Diagram(
    "Campus LAN with two buildings and a branch",
    "Two ISP uplinks reach the edge router in the MDF; the firewall and core "
    "switches feed the IDF closets in two buildings and a services VLAN with "
    "DHCP, DNS, the domain controller, RADIUS and NTP; a branch office joins "
    "over an SD-WAN tunnel.",
    slug="campus-lan-composed",
    direction="right",
) as diagram:
    # Everything that reaches the campus from outside sits in one WAN column
    # on the left, so every uplink and the branch tunnel run rightwards into
    # the MDF without crossing each other.
    with generic.Network("WAN - Internet"):
        isp_a = net.ISPUplink("ISP A uplink", "1 Gbps fibre")
        isp_b = net.ISPUplink("ISP B uplink", "500 Mbps")
        with onprem.Site("Branch office"):
            br_router = net.EdgeRouter("Branch router", "SD-WAN")
            br_switch = switch("Branch switch", "PoE")
            br_ap = net.WirelessAccessPoint("Branch access point")

    with generic.Campus("Campus - HQ").row():
        with generic.WiringCloset("MDF - Building A ground floor").keep_order():
            edge = net.EdgeRouter("Edge router", "dual-homed")
            firewall = sec.Firewall("Firewall", "north-south")
            core = net.CoreSwitch("Core switches", "stacked pair - L3")
            wlc = net.WLANController("WLAN controller", "SSIDs - roaming")
            shared.compute.PDU("UPS + PDU", "rack power")
        with generic.WiringCloset("IDF-1 - Building A floor 2"):
            sw1 = switch("Access switches", "PoE - 48 ports")
            ap1 = net.WirelessAccessPoint("Access points", "Wi-Fi 6E")
            patch = net.PatchPanel("Patch panel", "Cat6A")
        with generic.WiringCloset("IDF-2 - Building B"):
            sw2 = switch("Access switches", "PoE - 48 ports")
            ap2 = net.WirelessAccessPoint("Access points", "Wi-Fi 6E")
            phones = net.PBX("IP phones", "SIP - voice VLAN")
        with onprem.Subnet("VLAN 20 - Network services"):
            net.DHCPServer("DHCP server", "scopes per VLAN")
            net.DNSService("DNS", "internal zones")
            dc = ident.DomainController("Domain controller", "AD - Kerberos")
            radius = ident.RadiusServer("RADIUS / NAC", "802.1X")
            net.NTPServer("NTP server", "stratum 2")

    isp_a >> Edge("BGP") >> edge
    isp_b >> Edge("BGP") >> edge
    br_router >> Edge("WAN - IPsec", dashed=True) >> edge
    br_switch >> Edge("PoE") >> br_ap
    edge >> Edge("L3") >> firewall >> Edge("L3") >> core
    core >> Edge("10G fibre") >> [sw1, sw2]
    core >> Edge("CAPWAP") >> wlc
    sw1 >> Edge("PoE") >> ap1
    sw1 >> Edge("patched", dotted=True) >> patch
    sw2 >> Edge("PoE") >> [ap2, phones]
    dc >> Edge("LDAP", dotted=True) >> radius
    radius >> Edge("802.1X", dotted=True) >> ap2


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
