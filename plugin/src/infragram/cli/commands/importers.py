"""Bringing reviewed vendor artwork in from its source."""

from __future__ import annotations

__all__ = ["COMMANDS"]

#: command -> (script path relative to scripts/, help text)
COMMANDS: dict[str, tuple[str, str]] = {
    "import:brand-icons": (
        "importers/brand-icons.py",
        "import reviewed brand icons from the source vault",
    ),
    "import:official-icons": (
        "importers/official-icons.py",
        "import reviewed official icons from the source vault",
    ),
    "import:diagrams-icons": (
        "importers/diagrams-provider-icons.py",
        "vendor a provider node set from mingrammer/diagrams (alibaba, oracle, openstack)",
    ),
    "import:ibm-icons": (
        "importers/carbon-ibm-icons.py",
        "rebuild the IBM Cloud library from IBM's Carbon icons by the reviewed service table",
    ),
    "import:onprem-icons": (
        "importers/onprem-diagrams-icons.py",
        "import the reviewed Local & On-Premises icon set",
    ),
    "import:digitalocean-icons": (
        "importers/digitalocean-diagrams-icons.py",
        "import the reviewed DigitalOcean diagrams icon set",
    ),
    "import:digitalocean-platform-icons": (
        "importers/digitalocean-platform-icons.py",
        "import the reviewed DigitalOcean platform artwork",
    ),
}
