"""Hybrid patterns: the on-premises side of a cloud diagram and the circuit
that joins the two."""

from __future__ import annotations

from collections.abc import Sequence

from ..models.topology import TopologyElement
from ..nodes import infragram as shared
from ..nodes.aws import networking_content_delivery as net
from ..nodes.frames import aws as aws_frames, onprem as dc
from .base import Pattern, PatternError

__all__ = ["DirectConnectUplink"]


class DirectConnectUplink(Pattern):
    """A corporate site's edge and the AWS Direct Connect location it lands in.

    Draws the site (a datacenter frame holding an edge network with a
    perimeter firewall and a BGP router), the Direct Connect location with
    the circuit, and the dashed MACsec/BGP link between them. The site's
    frame is a part, so a caller adds its own source systems to it::

        uplink = DirectConnectUplink("Corporate data center")
        sources = uplink["site"] >> dc.SecurityZone("Source systems", flow="row")

    On the cloud side the circuit terminates on a gateway, never on an
    instance; connect ``uplink["circuit"]`` to a Transit Gateway.
    """

    def __init__(
        self,
        site: str = "Corporate data center",
        *,
        location: str = "Direct Connect location",
        bandwidth: str = "10 Gbps dedicated · MACsec",
        asn: str = "AS 65000",
        egress_policy: str = "egress allow-list only",
    ) -> None:
        super().__init__(site)
        self._location = location
        self._bandwidth = bandwidth
        self._asn = asn
        self._egress_policy = egress_policy

    @property
    def bandwidth(self) -> str:
        return self._bandwidth

    @bandwidth.setter
    def bandwidth(self, value: str) -> None:
        self._guard_unbuilt("bandwidth")
        if not str(value).strip():
            raise PatternError("bandwidth needs a value such as '1 Gbps dedicated'")
        self._bandwidth = str(value)

    @property
    def asn(self) -> str:
        return self._asn

    @asn.setter
    def asn(self, value: str) -> None:
        self._guard_unbuilt("asn")
        self._asn = str(value)

    def build(self) -> Sequence[TopologyElement]:
        site = self.part("site", dc.Datacenter(self.name, flow="column"))
        edge = self.part("edge", site >> dc.Network("Edge network", flow="row"))
        firewall = self.part(
            "firewall", edge >> shared.security.Firewall("Perimeter firewall", self._egress_policy)
        )
        router = self.part(
            "router", edge >> shared.networking.EdgeRouter("Edge router", f"BGP · {self._asn}")
        )
        location = self.part("location", aws_frames.DirectConnectLocation(self._location))
        circuit = self.part(
            "circuit", location >> net.DirectConnect("Direct Connect", self._bandwidth)
        )
        firewall.to(router, label="")
        router.to(circuit, kind="dashed", label="MACsec · BGP")
        return [site, location]
