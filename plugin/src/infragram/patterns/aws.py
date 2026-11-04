"""AWS patterns: the shapes that recur in every AWS reference architecture.

Each one is a :class:`~infragram.patterns.base.Pattern`: it builds from the
generated frame and service classes, registers the parts a caller wires up,
and knows nothing about the diagram around it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeAlias

from ..models.topology import TopologyElement
from ..nodes import Element
from ..nodes.aws import management_tools as mgmt, security_identity as sec
from ..nodes.frames import aws as frames, generic
from ..utils.text import slugify as _slug
from .base import Pattern, PatternError

__all__ = ["EndpointSubnet", "Guardrails", "MultiAZ", "ServiceSpec", "Zone"]

#: A service to place: the node class, its name, and its detail line.
ServiceSpec: TypeAlias = tuple[type[Element], str, str]

#: How a subnet is filled: given the subnet frame and the zone that owns it,
#: place nodes and register the ones worth connecting with ``zone.part``.
SubnetBuilder: TypeAlias = Callable[[TopologyElement, "Zone"], None]


class Guardrails(Pattern):
    """Account-wide services drawn as one row outside the VPC.

    Detection, audit, keys, certificates: the things a reader checks are
    present before reading anything else. The default set is the usual four;
    pass ``services`` to draw exactly what the estate runs.
    """

    DEFAULT: tuple[ServiceSpec, ...] = (
        (sec.Guardduty, "Amazon GuardDuty", "threat detection"),
        (mgmt.Cloudtrail, "AWS CloudTrail", "API audit trail"),
        (sec.SecurityHub, "AWS Security Hub", "posture findings"),
        (mgmt.Config, "AWS Config", "drift and compliance"),
    )

    def __init__(
        self, name: str = "Account-wide services", services: Sequence[ServiceSpec] | None = None
    ) -> None:
        super().__init__(name)
        self._services: tuple[ServiceSpec, ...] = self.DEFAULT
        if services is not None:
            self.services = services

    @property
    def services(self) -> tuple[ServiceSpec, ...]:
        return self._services

    @services.setter
    def services(self, value: Sequence[ServiceSpec]) -> None:
        self._guard_unbuilt("services")
        if not value:
            raise PatternError("Guardrails needs at least one service")
        self._services = tuple(value)

    def build(self) -> TopologyElement:
        zone = generic.SecurityZone(self.name, flow="row")
        for cls, name, detail in self._services:
            self.part(_slug(name), zone >> cls(name, detail))
        return zone


class Zone(Pattern):
    """One Availability Zone: an optional public subnet and a private one.

    The subnets are filled by callables so the pattern stays generic: it
    draws the zone and the subnets, the caller says what lives in them.
    """

    def __init__(
        self,
        letter: str,
        *,
        public: SubnetBuilder | None = None,
        private: SubnetBuilder | None = None,
        name: str | None = None,
        private_name: str | None = None,
        public_name: str | None = None,
    ) -> None:
        letter = str(letter).strip().upper()
        if len(letter) != 1 or not letter.isalpha():
            raise PatternError(f"a zone letter is one letter, not {letter!r}")
        super().__init__(name or f"Availability Zone {letter}")
        self.letter = letter
        self._public = public
        self._private = private
        self._public_name = public_name or f"Public subnet {letter}"
        self._private_name = private_name or f"Private subnet {letter}"

    def build(self) -> TopologyElement:
        zone = frames.AvailabilityZone(self.name, flow="column", arrange="manual")
        if self._public is not None:
            public = self.part("public", zone >> frames.PublicSubnet(self._public_name, flow="row"))
            self._public(public, self)
        if self._private is not None:
            private = self.part(
                "private",
                zone >> frames.PrivateSubnet(self._private_name, flow="column", arrange="manual"),
            )
            self._private(private, self)
        return zone


class MultiAZ(Pattern):
    """Identical Availability Zones side by side, built from one recipe.

    ``count`` zones are made, lettered A, B, C ... and each is a :class:`Zone`
    filled by the same ``public`` and ``private`` builders, which is what
    "the zones are interchangeable" means in a drawing. Parts are reached
    per zone, ``multi.part_for("landing", "B")``, or across all zones,
    ``multi.each("landing")``.
    """

    LETTERS = "ABCDEF"

    def __init__(
        self,
        count: int = 2,
        *,
        public: SubnetBuilder | None = None,
        private: SubnetBuilder | None = None,
        name: str = "Availability Zones",
    ) -> None:
        super().__init__(name)
        self._count = 0
        self.count = count
        self._public = public
        self._private = private
        self._zones: tuple[Zone, ...] = ()

    @property
    def count(self) -> int:
        return self._count

    @count.setter
    def count(self, value: int) -> None:
        self._guard_unbuilt("count")
        if not 1 <= int(value) <= len(self.LETTERS):
            raise PatternError(f"MultiAZ draws 1 to {len(self.LETTERS)} zones, not {value}")
        self._count = int(value)

    @property
    def zones(self) -> tuple[Zone, ...]:
        self.realise()
        return self._zones

    @property
    def letters(self) -> tuple[str, ...]:
        return tuple(self.LETTERS[: self._count])

    def build(self) -> Sequence[TopologyElement]:
        zones = tuple(
            Zone(letter, public=self._public, private=self._private) for letter in self.letters
        )
        for zone in zones:
            frame = zone.realise()[0]
            for key, element in zone.parts.items():
                self.part(f"{key}:{zone.letter}", element)
            self.part(f"zone:{zone.letter}", frame)
        self._zones = zones
        return [zone.elements[0] for zone in zones]

    def part_for(self, key: str, letter: str) -> Any:
        """The part ``key`` registered in zone ``letter``."""
        return self[f"{key}:{str(letter).upper()}"]

    def each(self, key: str) -> list[Any]:
        """The part ``key`` from every zone, in zone order."""
        return [self.part_for(key, letter) for letter in self.letters]


class EndpointSubnet(Pattern):
    """A private subnet holding the interface endpoints a zone needs.

    Interface endpoints are per zone, so a Multi-AZ estate that reaches KMS
    and Secrets Manager privately draws this once per zone, with the icon of
    the service each endpoint fronts.
    """

    def __init__(
        self, letter: str, services: Sequence[ServiceSpec], *, name: str | None = None
    ) -> None:
        super().__init__(name or f"Private subnet · endpoints {str(letter).upper()}")
        if not services:
            raise PatternError("EndpointSubnet needs at least one service")
        self._services = tuple(services)

    def build(self) -> TopologyElement:
        subnet = frames.PrivateSubnet(self.name, flow="row")
        for cls, name, detail in self._services:
            self.part(_slug(name), subnet >> cls(name, detail))
        return subnet
