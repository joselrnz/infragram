# Third-party licenses

The infragram code is MIT-licensed (see [`LICENSE`](LICENSE)). It bundles
artwork, fonts and code from the following third-party sources, redistributed
under their respective licenses. Every provider icon pack records source, release, terms
URL, and SHA-256 per file in its `catalog.json`; read an icon's own fields
first and fall back to the collection's `source` block.

The licence texts and copyright notices these terms require ship in
[`licenses/`](licenses/): the MIT notice of each MIT project below by its name
(`licenses/tabler-icons.txt` and so on) and the Apache License 2.0 text
(`licenses/Apache-2.0.txt`). The fonts' OFL texts and the Databricks set's
licence sit beside those files.

## Tabler Icons

- **License:** MIT
- **Upstream:** https://github.com/tabler/tabler-icons
- **Used in:** stroked neutral primitives in `skills/infragram-architect/references/primitive-icons.md` (compute, people, network, data, Kubernetes, action, and DevOps symbols, the datacenter and network infrastructure concepts such as mainframe, SAN fabric switch, storage array, NAS, tape library, wireless access point, WAN link, core and access switches, UPS, PDU, IDS/IPS and WAF, the operations, security, facilities and OT concepts (console server, IPAM, PKI, HSM, DLP, mail server and relay, ESB, CDC, ITSM, CMDB, PLC, SCADA, HMI, generator, cooling, fire suppression, and more), plus the stroked brand outlines for Docker, Terraform, AWS, Azure, GitHub, Windows, Slack, Microsoft Teams and Microsoft 365), the semantic sidebar glyphs, and the Local & On-Premises neutral operational components.

The MIT notice ships as [`licenses/tabler-icons.txt`](licenses/tabler-icons.txt) (upstream: https://github.com/tabler/tabler-icons/blob/main/LICENSE).

## GitHub Primer Octicons

- **License:** MIT
- **Upstream:** https://github.com/primer/octicons
- **Used in:** the Containers category glyph in the library sidebar.

The MIT notice ships as [`licenses/octicons.txt`](licenses/octicons.txt) (upstream: https://github.com/primer/octicons/blob/main/LICENSE).

## Simple Icons

- **License:** CC0 1.0 Universal (Public Domain Dedication)
- **Upstream:** https://github.com/simple-icons/simple-icons
- **Used in:** filled brand silhouettes in `skills/infragram-architect/references/primitive-icons.md` (DigitalOcean, Kubernetes, Google Cloud, PostgreSQL, Nginx, Gitea, Keycloak, MinIO, Apache NiFi, Apache Airflow, Trino, Apache Superset, Jupyter, Python, R, and the self-hosted platform marks listed under "Self-hosted platforms" in the same gallery: Pi-hole, AdGuard Home, WireGuard, OpenVPN, Authelia, authentik, Vaultwarden, Portainer, Rancher, Longhorn, Forgejo, Salt, Rundeck, TrueNAS, Home Assistant, Mattermost, Rocket.Chat, Matrix, Jitsi, Coder, Syncthing, Paperless-ngx, BookStack, Wiki.js, GitBook, Elasticsearch, Kibana, Logstash, OpenSearch, Icinga, Checkmk, Uptime Kuma, Netdata, Nginx Proxy Manager, QEMU, VirtualBox, Nutanix, Veeam, BorgBackup, Talend, Apache Hadoop, Apache Spark, Snowflake, Cloudera, Teradata, MicroStrategy, Qlik, SAP, and the network and hardware vendor marks Cisco, Juniper Networks, Fortinet, Palo Alto Networks, Ubiquiti, F5, SonicWall, NETGEAR, TP-Link, Huawei, Dell, Supermicro, and the enterprise platform marks Red Hat, Red Hat OpenShift, SUSE, openSUSE, Rocky Linux, AlmaLinux, FreeBSD, Fedora, Citrix, NetApp, Hitachi, Veritas, Okta, Auth0, Qualys, Fastly, Atlassian, Jira, Confluence, Bitbucket, Zoom, Asterisk, HashiCorp, Vagrant, Packer, Chef, Octopus Deploy, Sonatype, Podman, Helm, ownCloud, Seafile, openmediavault, Unraid, Synology, QNAP, Timescale, MQTT, PagerDuty, Opsgenie, Wireshark, Kali Linux, Snort, Apache CloudStack, OpenNebula, HP, Intel, Roundcube, and the second platform batch 1Password, Airbyte, Alpine Linux, AnyDesk, Apache Guacamole, Apache Parquet, Apache Pulsar, ArangoDB, Arch Linux, Arduino, Backstage, BigBlueButton, Burp Suite, Camunda, Dependabot, Dovecot, Drupal, ERPNext, ESPHome, Falco, Fluent Bit, Frigate, Gitpod, GraphQL, HubSpot, Jellyfin, KeePassXC, LangChain, Lenovo, Meilisearch, Metasploit, Milvus, n8n, NixOS, Node-RED, NVIDIA, Odoo, Ollama, OpenBSD, openHAB, OpenWrt, Parrot Security, Raspberry Pi, rclone, Renovate, Rook, RustDesk, ScyllaDB, Shopify, Snyk, SonarQube Server, strongSwan, Sumo Logic, Tailscale, Talos Linux, TeamViewer, Thunderbird, TiDB, VictoriaMetrics, VirusTotal, Vitess, WebAssembly, WooCommerce, Yubico, Zapier, Zendesk, ZeroTier, Zigbee, macOS), and the Hetzner identity mark in `skills/infragram-architect/assets/themes/marks/hetzner.svg`. Each mark remains its owner's trademark; its presence is a drawing capability, not an endorsement.

The CC0 dedication is reproduced in full at https://github.com/simple-icons/simple-icons/blob/develop/LICENSE.md.

## log-z/logos

- **License:** MIT
- **Upstream:** https://github.com/log-z/logos/tree/main/website-logos
- **Used in:** filled brand silhouettes that aren't carried by Simple Icons or Tabler: MySQL, Redis, and StarRocks. Source SVGs are 100×100 with embedded `<style>` + class-based fills; the build script strips the style block and rewrites class refs to `currentColor` for monochrome consistency.

The MIT notice ships as [`licenses/log-z-logos.txt`](licenses/log-z-logos.txt) (upstream: https://github.com/log-z/logos/blob/main/LICENSE).

## Devicon

- **License:** MIT
- **Upstream:** https://github.com/devicons/devicon
- **Used in:** the RStudio and SPSS glyphs in `skills/infragram-architect/references/primitive-icons.md` (the repository keeps their sources in `scripts/vendor/icons/devicon/`).

The MIT notice ships as [`licenses/devicon.txt`](licenses/devicon.txt) (upstream: https://github.com/devicons/devicon/blob/master/LICENSE).

## thesvg brand logos

- **License:** per entry; the 17 retained entries are all `permissive` (CC0-1.0 or MIT), recorded in `license` and `license_status` in `skills/infragram-architect/assets/icons/logos/catalog.json`
- **Upstream:** https://github.com/glincker/thesvg (pinned commit recorded in the catalog's `source` block)
- **Used in:** the theme marks for AWS, Azure, Cloudflare, OpenStack, OVHcloud, Vultr, Akamai Cloud, VMware vSphere, Proxmox VE, and Equinix (thesvg files Equinix's "E" symbol under its retired Metal product, slug `equinix-metal`), the Kubernetes mark on managed-cluster frames, the four Cloudflare product components, and the brand components every slug offers as a node class (`infragram.nodes.logos`, such as `logos.software.IBM` and the nginx example in the node-class tests). Only these 17 slugs ship: `aws`, `microsoft`, `microsoft-azure`, `kubernetes`, `cloudflare`, `cloudflare-workers`, `cloudflare-pages`, `workersai-cloudflare`, `ibm`, `nginx`, `openstack`, `ovh`, `vultr`, `akamai`, `vmware`, `proxmox`, `equinix-metal`.

## mingrammer/diagrams provider node sets

- **License:** MIT (Copyright 2020 MinJae Kwon); the notice ships as [`licenses/mingrammer-diagrams.txt`](licenses/mingrammer-diagrams.txt)
- **Upstream:** https://github.com/mingrammer/diagrams (pinned to v0.25.1, commit `dd0763d939f377c99898951a489e813c0360cd4a`)
- **Used in:** the Oracle Cloud (`diagrams.oci`, 70 icons), Alibaba Cloud (`diagrams.alibabacloud`, 94), and OpenStack (`diagrams.openstack`, 50) libraries under `skills/infragram-architect/assets/icons/vendors/`. Each upstream PNG is embedded byte-for-byte in a self-contained SVG wrapper; source and wrapper SHA-256 digests are recorded per icon in each pack's `catalog.json`. OCI's white-on-transparent variants are not imported.

The MIT license covers the diagrams project's files; it does not by itself
establish redistribution rights for every provider artwork file. Oracle,
Alibaba Cloud, and OpenInfra Foundation marks remain subject to their
owners' trademark terms, which the provider registry records per library.

## IBM Carbon icons

- **License:** Apache-2.0 (Copyright 2015 IBM Corp.); the text ships as [`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt)
- **Upstream:** https://github.com/carbon-design-system/carbon/tree/main/packages/icons (`@carbon/icons` 11.89.0 on npm)
- **Used in:** the IBM Cloud library (168 icons) under `skills/infragram-architect/assets/icons/vendors/ibm/`. Each service's icon is a Carbon 32 px icon chosen in a reviewed table (`scripts/importers/ibm-carbon-map.json`, written by `scripts/importers/carbon-ibm-icons.py`); its paths are unaltered and carried in this library's SVG wrapper, and the catalog records the source and wrapper SHA-256 digests, the Carbon icon and why it was chosen. IBM's names and marks remain IBM's.

## mingrammer/diagrams DigitalOcean resources

- **License:** MIT (Copyright 2020 MinJae Kwon)
- **Upstream:** https://github.com/mingrammer/diagrams
- **Used in:** the complete 25-node `diagrams.digitalocean` compute, database,
  network, and storage vocabulary, pinned to commit
  `364c61d47884bc0718d07f932f7c1772e82c42b1`. Each upstream PNG is embedded
  byte-for-byte in a self-contained SVG wrapper; source and wrapper SHA-256
  digests are recorded in the DigitalOcean catalog. Earlier compact symbols
  for Spaces and Managed Database remain available for compatibility.

The MIT license is reproduced in full in the upstream repository's `LICENSE`
file. That software license does not by itself establish separate redistribution
rights for every provider artwork file; DigitalOcean marks remain subject to
DigitalOcean's trademark and asset terms.

## mingrammer/diagrams on-premises resources

- **License:** MIT (Copyright 2020 MinJae Kwon)
- **Upstream:** https://github.com/mingrammer/diagrams/tree/v0.25.1/resources
  (`onprem`, `generic` and `elastic`)
- **Used in:** the complete `diagrams.onprem` product catalog, the
  vendor-neutral `diagrams.generic` set (network devices, operating systems,
  virtualization, storage, datacenter, devices) and the `diagrams.elastic`
  set (Elastic stack, Beats, Agent, Observability, Security, Enterprise
  Search, Cloud) that together form the Local & On-Premises library
  (`skills/infragram-architect/assets/icons/vendors/onprem/`). Each upstream PNG is
  embedded byte-for-byte in a self-contained SVG wrapper; source and wrapper
  SHA-256 digests are recorded in the on-prem catalog.

The node set depicts third-party products (Proxmox, Kubernetes distributions,
databases, message brokers, observability and CI tools, and more). The MIT
license covers the diagrams project's files; each depicted product's marks
remain subject to their owner's trademark terms, and their presence in the
library is a drawing capability, not a claim about any deployment.

## Hetzner website product icons

- **Source:** https://www.hetzner.com (product-icon SVGs served from cdn.hetzner.com; per-icon source URL and SHA-256 recorded in `skills/infragram-architect/assets/icons/vendors/hetzner/catalog.json`)
- **Fetched:** 2026-08-18 (26 vector icons)
- **Rights status:** Hetzner publishes no icon package with explicit redistribution terms. These files are Hetzner artwork bundled at the maintainer's direction for architecture-diagram and documentation use only; they are **not** relicensed under Infragram Architect's MIT license, and Hetzner's trademark and asset terms apply. If Hetzner objects or clarifies terms that exclude this use, remove this subset.

## DigitalOcean documentation product and platform icons

- **Source:** https://docs.digitalocean.com/products/ and https://docs.digitalocean.com/platform/ (documentation SVGs; per-icon hashed source path and SHA-256 recorded in `skills/infragram-architect/assets/icons/vendors/digitalocean/catalog.json`)
- **Fetched:** 2026-08-18 and 2026-08-22 (51 unique SVG assets; repeated artwork is cataloged once, and the Teams SVG retains DigitalOcean's embedded image)
- **Rights status:** DigitalOcean publishes no architecture-icon package with explicit redistribution terms. These files are DigitalOcean artwork bundled at the maintainer's direction for architecture-diagram and documentation use only; they are **not** relicensed under Infragram Architect's MIT license, and DigitalOcean's trademark and asset terms apply. If DigitalOcean objects or clarifies terms that exclude this use, remove this subset.

## Official cloud architecture icon packages

- **AWS:** reviewed service icons copied from the AWS Architecture Icons 2026-Q3 package. Source and usage guidance: https://aws.amazon.com/architecture/icons/
- **Microsoft Azure:** reviewed service icons copied without geometric or color modification from Azure Public Service Icons V24. Source and permitted-use restrictions: https://learn.microsoft.com/en-us/azure/architecture/icons/
- **Google Cloud:** reviewed service icons copied from the official 2025 Google Cloud icon library. Source and usage guidance: https://cloud.google.com/icons
- **Kubernetes:** project artwork from the Kubernetes community repository (Apache-2.0, text in [`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt)); CNCF and Linux Foundation trademark policies apply to the marks.
- **Databricks:** architecture icons built from Databricks' official SVGs (https://brand.databricks.com/), vendored in `assets/icons/vendors/databricks/`. That set is Copyright (c) 2026 Eduardo Rabelo under the MIT License, whose full notice ships beside the icons as `assets/icons/vendors/databricks/LICENSE`; nothing is fetched from its repository. The license grants no trademark rights: Databricks, the Databricks logo and the product names are trademarks of Databricks, Inc., which does not sponsor or endorse the set. The theme mark (`assets/themes/marks/databricks.svg`) is the same logo redrawn in one colour.

These files are provider artwork, not relicensed under Infragram Architect's MIT license. They are bundled only for architecture-diagram and documentation use under the linked provider terms. Their per-file source path, release, terms URL, and SHA-256 digest are recorded in each pack's `catalog.json`.

## Project logos

Two brand marks no icon library carries are taken from the project's own
repository, pinned to a commit, and kept unmodified in
`scripts/vendor/icons/official/` (the table is `OFFICIAL` in
`scripts/build/icons.py`). The gallery draws each in one colour; Redpanda's
white panda becomes a cut-out of its disc.

- **Valkey** — `static/img/Valkey-logo.svg` from
  https://github.com/valkey-io/valkey-io.github.io at commit
  `c2a4d37b33afc4cd879d29857d6c6bf3ae952f97`. BSD-3-Clause (Copyright 2024
  Linux Foundation or its affiliates); the notice ships as
  [`licenses/valkey.txt`](licenses/valkey.txt). Valkey is a trademark of the
  Linux Foundation; the licence grants no trademark rights.
- **Redpanda** — `docs/icon-redpanda.svg` from
  https://github.com/redpanda-data/redpanda at commit
  `10932ba73d4c98eeda85ee55d80f2d6a8e01901c`.
  - **Rights status:** Redpanda publishes the mark in its repository and in
    its press media kit, with no explicit redistribution terms. It is bundled
    at the maintainer's direction for architecture-diagram and documentation
    use only; it is **not** relicensed under Infragram Architect's MIT
    license, and Redpanda Data's trademark terms apply. If Redpanda objects
    or clarifies terms that exclude this use, remove it.

## One-off sourced icons

None besides the two project logos above. Apache Hop, Pentaho, Dagster, SAS
and Stata have no licence-clean brand mark, so each draws a generic Tabler
glyph that says what the tool does. `tests/unit/test_artwork_licensing.py`
fails if a glyph is fetched from a vendor page again, and holds every project
logo to its entry here.

## Drawn vendor service tiles

OVHcloud, Vultr, Akamai Cloud (Linode), VMware vSphere, Proxmox VE and Equinix publish no
service-icon pack with a redistribution grant, and Cloudflare publishes only its
product marks. Their libraries are therefore drawn here: each tile is a Tabler
Icons glyph (MIT, see above) in white on a rounded square of the vendor's colour,
produced by `scripts/build/vendor-tiles.py` from a table in that script. The tiles
are this repository's own artwork under its MIT licence and are not the vendor's
icons; the vendor's name and colour say which product a card stands for, and the
vendor's marks remain its trademarks (see below). The library registry
(`license_basis` in `assets/catalog/providers.json`) records them as
`original-artwork`, and the icon index carries that to every tile. Cloudflare's
four product marks are logos from the shared set (`permissive`, above).

## three.js

- **License:** MIT (Copyright 2010-2024 three.js authors); the notice ships as [`licenses/three.js.txt`](licenses/three.js.txt), and `RoomEnvironment.js`, adapted from Google's model-viewer, is also under the Apache License 2.0 ([`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt))
- **Upstream:** https://github.com/mrdoob/three.js (r161)
- **Used in:** `src/infragram/iso3d/lib/three.module.js` (its MIT notice kept at the top) and `src/infragram/iso3d/lib/RoomEnvironment.js` (the three.js example environment, which three.js adapted from Google's model-viewer, Apache-2.0), which draw the on-premises 3D set: the build scripts render each item with them, and an exported page that can use the in-editor 3D builder carries them.

## draw.io stencil names

- **License:** Apache License 2.0 (Copyright JGraph Ltd); the text ships as [`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt)
- **Upstream:** https://github.com/jgraph/drawio-mcp, `shape-search/search-index.json` at the commit `skills/infragram-architect/assets/catalog/drawio-stencils.json` records
- **Used in:** the `.drawio` export. `scripts/build/drawio-stencils.py` matches Infragram's AWS, Azure and Kubernetes components to the draw.io style strings that index lists, by exact name, and keeps the matching style strings in `drawio-stencils.json`; the export writes them so draw.io draws its own stencils. No draw.io artwork is copied: draw.io draws the stencils it names.

## Fonts

- **License:** SIL Open Font License 1.1
- **Upstream:** google/fonts, fetched as subsetted woff2 through the Google Fonts CSS API; each face's source URL and sha256 are recorded in `skills/infragram-architect/assets/fonts/catalog.json`
- **Used in:** every editor page, static page and standalone SVG, which carry the faces inline: Inter (the editor itself and every label in a diagram) and Geist Mono (the monospaced face the Text panel offers, and monospaced frame titles). The notices are the `OFL-*.txt` files beside the fonts in `skills/infragram-architect/assets/fonts/`.

## Trademarks

Brand logos remain the trademarks of their respective owners. Their inclusion in this icon set is for documentation and illustrative use only. The presence of a brand mark in this repository does not imply endorsement, sponsorship, or affiliation: Infragram Architect is an independent project, not affiliated with or endorsed by Amazon Web Services, Microsoft, Google, DigitalOcean, Hetzner, Cloudflare, Oracle, IBM, Alibaba Cloud, OVHcloud, Vultr, Akamai, Databricks, Equinix, Broadcom (VMware), Proxmox, the OpenInfra Foundation or the Cloud Native Computing Foundation.
