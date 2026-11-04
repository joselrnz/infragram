# README media

Infragram's mascot is a cream-and-charcoal engraved pangolin drawing a diagram
on a light mint tile. The editor embeds small WebP exports in its header and
welcome screen, and a PNG favicon, so it works offline. The README and brand kit use exports
of this same selected design.

The retained assets are:

- `../images/infragram-mascot.png`: full-resolution selected mascot artwork.
- `../images/infragram-engineer-icon.png`, `infragram-mascot-128.png` and
  `infragram-mascot-32.png`: mint tiles with transparent rounded corners
  at 512, 128 and 32 pixels.
- `../images/infragram-engineer-header.svg`: SVG header with an embedded PNG mascot and a dark charcoal
  background with warm cream serif lettering in both README themes,
  and the slogan "Picture it. Watch it take shape."
  Matching PNGs end in `-light.png` and `-dark.png`.
- `../images/infragram-engineer.gif`: four-second mascot tile animation with transparent corners.
- `infragram-brand-kit.zip`: the eight mascot, icon, banner and animation files
  above, with a short usage note; built by the script below and attached to a
  release, not kept in git.
- `../images/infragram-editor.gif` and `infragram-editor.mp4`: recordings of the
  editor drawing the shipped `enterprise-data-integration` template, with no
  live account data.
- `infragram-tour.mp4`: the longer flow tour across four examples from
  `plugin/examples` (AWS three-tier, GitHub Actions to AWS with numbered
  steps, the AKS baseline on Azure, streaming analytics on Google Cloud), each
  recorded on its own and cut together; `../images/infragram-tour-aws.gif`,
  `-aws-pipeline.gif`, `-azure.gif` and `-gcp.gif` are its four parts, each a
  few MB, since one GIF of the whole tour is past what Markdown viewers show.
- `../images/agent-example.png`: the agent workflow example used in the README.

The demo shows component search; the flow, stage by stage: a source, the ETL
hub, data quality, the warehouse, the marts and Power BI, then a frame, a
caption, and the lens that lights everything Power BI depends on; then label
editing, dragging, layout tidying, card/icon display modes, light/dark themes
and the export menu.
The template gallery is in `../images/gallery/`; the provider inventory
sheets are in `../inventory/`.

Regenerate the selected brand assets and editor recordings from the repository
root with:

```bash
python scripts/docs/regenerate-media.py
```

The palette uses mint `#C9EFDF`, cream `#FFF8EB`, blue `#008AD8` and charcoal
`#191E27`. The master is `plugin/src/infragram/editor/ui/assets/mascot.png`.
The banner uses charcoal `#141B24` and cream `#F2E7D3` for its wordmark.
The engraving is raster artwork, not editable SVG paths. Replace this selected
master and regenerate to update the published copies and small offline app icons.

The script needs Python with the project's `docs` extra, Playwright Chromium
and FFmpeg on PATH. It captures the real editor, renders the artwork at each
icon size, and animates the mascot export. The banner's text and decorations
are vector shapes; its mascot is an embedded PNG.
