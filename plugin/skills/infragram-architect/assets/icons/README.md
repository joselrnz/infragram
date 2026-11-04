# icons/

Icon libraries: provenance-tracked artwork, never hand-edited. Icons exist
exactly once — themes and the index reference them, nothing copies them.
Collections are named by **artwork kind**, and each has exactly one owner
(one importer), so regeneration can never destroy curated work.

```text
icons/
├── index.json          GENERATED lookup over everything (id, family, tags, path, rights)
├── vendors/            per-vendor icon packs — drawn as nodes INSIDE diagrams
│   ├── sources.json    official pack manifest — add vendors HERE, not in code
│   └── <vendor>/       catalog.json + <category>/<id>.svg
└── logos/              company identity artwork the editor references — 17 slugs
    ├── catalog.json    pruned to the referenced slugs, per-variant sha256 (see logos/README.md)
    ├── families.json   curated grouping overlay (never regenerated)
    └── <slug>/<variant>.svg
```

Which collection does something belong to? Three questions:
node drawn *inside* a diagram → `vendors/`; a company's identity as published
→ `logos/`; the badge a theme stamps on examples → `../themes/marks/`.

## Regeneration (one owner per collection)

- `vendors/azure`, `aws`, `gcp`, `kubernetes` — `infragram import:official-icons
  [vendor ...]`, from the checksum-verified official downloads that
  `vendors/sources.json` lists, kept in the separate
  `scripts/cloud-diagram-sources` vault.
- `vendors/oracle`, `ibm`, `alibaba`, `openstack` — `infragram
  import:diagrams-icons`, from the mingrammer/diagrams node sets.
- `vendors/digitalocean` — `infragram import:digitalocean-icons` (the
  diagrams-repository set) and `infragram import:digitalocean-platform-icons`
  (the platform pages' artwork).
- `vendors/onprem` — `infragram import:onprem-icons`; the rendered 3D items
  (`iso-*`) come from `scripts/build/iso-render.py --install`.
- `vendors/cloudflare`, `ovhcloud`, `vultr`, `akamai`, `vmware`, `proxmox`, `equinix` —
  drawn service tiles, from `scripts/build/vendor-tiles.py` (`--check` holds
  the shipped sets to its table). Cloudflare's four product marks are `logos/`
  slugs.
- `vendors/hetzner` — fetched from hetzner.com's product pages and curated by
  hand; no importer rebuilds it.
- `logos/*` — `infragram import:brand-icons` wipes and rebuilds every slug
  folder from thesvg; afterwards prune back to the referenced slugs listed in
  `logos/README.md`. `families.json` is the one file the importer must never
  touch.
- `index.json` — `infragram build:index`.

A catalog's `source` block describes where the collection as a whole came
from. An individual icon that came from somewhere else overrides it with its
own `source_url`, `source_release`, and `terms_url`, as many icons in
`digitalocean/` do. Read an icon's own fields first, then fall back to the
collection block; never assume the collection terms cover every file.

## families.json

Groups related logo slugs (google-*, microsoft-*, ...) without moving
folders, so grouping survives regeneration. `official.vendors` names the
pack that supersedes those logos in lookup (tier 1 beats tier 2);
`official.url` records where to download the official pack later.

## Reuse rule

The license covering repository code is not necessarily the license covering
the icons. Provider names, product marks, logos, and architecture artwork
often retain separate terms even when distributed under MIT or Apache
wrappers. Check `license_status` in the index before altering any artwork;
most vendor terms permit use in diagrams but forbid modification.
