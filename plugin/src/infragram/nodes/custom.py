"""Parameterised picks from the generated 3D on-premises set.

The set ships a grid of plain servers -- no badge, every family colour,
seven shapes -- so a diagram can ask for the server it means instead of
the nearest named one::

    from infragram.nodes.custom import custom_server

    db = custom_server("DB-01", "PostgreSQL 16", units=2, bays=8, family="storage")
    gpu = custom_server("GPU-03", "8 × H100", units=4, bays=12)

``units`` and ``bays`` name one of the shapes in ``CUSTOM_SERVER_SHAPES``;
``family`` is the colour: compute (blue, the default), storage (teal),
network (violet), security (red), facility (amber), client (slate),
platform (indigo), operations (cyan), industrial (green), energy (fuchsia). Anything else --
a badge, a different front -- is a line in the table of
``scripts/build/iso-icons.py`` and an install.
"""

from __future__ import annotations

import importlib
from typing import Any

#: (rack units, drive bays) the custom grid is rendered in.
CUSTOM_SERVER_SHAPES: tuple[tuple[int, int], ...] = (
    (1, 0),
    (1, 4),
    (2, 0),
    (2, 8),
    (4, 0),
    (4, 12),
    (4, 24),
)
FAMILIES = (
    "compute",
    "storage",
    "network",
    "security",
    "facility",
    "client",
    "platform",
    "operations",
    "industrial",
    "energy",
)


def custom_server(
    name: str,
    subtitle: str = "",
    *,
    units: int = 2,
    bays: int = 8,
    family: str = "compute",
    **kwargs: Any,
):
    """The plain server of that shape and colour, as a node in the diagram."""
    if (units, bays) not in CUSTOM_SERVER_SHAPES:
        raise ValueError(
            f"no custom server of {units}U with {bays} bays; one of "
            + ", ".join(f"{u}U/{b}" for u, b in CUSTOM_SERVER_SHAPES)
        )
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}; one of {', '.join(FAMILIES)}")
    module = importlib.import_module(f"infragram.nodes.onprem.iso_{family}")
    return getattr(module, f"IsoCustomServer{family.capitalize()}{units}u{bays}")(
        name, subtitle, **kwargs
    )
