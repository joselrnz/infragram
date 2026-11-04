# Artwork provenance and licenses

Provider artwork is bundled under each provider's own terms and recorded per
file with source, release, terms URL, and SHA-256 in every pack's
`catalog.json`. Neutral primitives derive from MIT/CC0 icon sets. See
[`THIRD_PARTY_LICENSES.md`](../plugin/THIRD_PARTY_LICENSES.md). The project code is
MIT-licensed under [`LICENSE`](../LICENSE).

Every library records *how* we came by its artwork, in `license_basis`, and
each icon carries it through to the index as `license_status`:

| Basis | Libraries | What it means |
|---|---|---|
| `upstream-permissive` | Local & On-Premises, Oracle, IBM, Alibaba, OpenStack, Kubernetes, Databricks | an OSS licence (MIT, Apache-2.0, CC0) grants redistribution |
| `provider-terms` | AWS, Azure, Google Cloud | the vendor publishes an asset pack whose terms permit architecture-diagram use |
| `vendor-unverified` | DigitalOcean, Hetzner | a conservative library-wide label; check the per-file provenance described below |
| `original-artwork` | Cloudflare, OVHcloud, Vultr, Akamai, VMware, Proxmox, Equinix | service tiles drawn for this project (a Tabler glyph, MIT, on the vendor's colour); MIT with the repository, and **not the vendor's icons** |
| `permissive` | the 17 logos in `icons/logos/` (Cloudflare's four product marks among them) | a CC0 or MIT logo set |

The index labels 101 distinct icons `vendor-unverified` (DigitalOcean 75,
Hetzner 26), with 170 entries because themes repeat 69 icons. Per-file
provenance is more specific: 28 DigitalOcean icons come from the MIT-licensed
`mingrammer/diagrams` collection. The remaining 47 DigitalOcean icons and all
26 Hetzner icons come from vendor web pages; no redistribution grant was
established for those 73 files. Their inclusion does not establish permission
or relicense them under this project's MIT licence. See
[`THIRD_PARTY_LICENSES.md`](../plugin/THIRD_PARTY_LICENSES.md) and each pack's
`catalog.json`. A test pins the index count so the set cannot grow unnoticed.

These icons are used by the component catalog and provider diagram templates,
including DigitalOcean application delivery and Kubernetes, Hetzner application
delivery, and multicloud diagrams. Removing them would change rendered diagrams.

**Trademarks.** AWS, Azure, Google Cloud and the other cloud, platform and
product names and logos in the libraries are trademarks of their owners.
Infragram Architect is not affiliated with, sponsored by or endorsed by any of
them; a name or logo is there so a diagram can say what it shows. See the
Trademarks section of [`THIRD_PARTY_LICENSES.md`](../plugin/THIRD_PARTY_LICENSES.md).

[Documentation](README.md) · [Project README](../README.md)
