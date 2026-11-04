# infragram

The library and CLI inside the Infragram Architect plugin. The *product* it
builds and verifies is the plugin this package sits in (`plugin/`), whose skill
is [`skills/infragram-architect/`](../../skills/infragram-architect/);
the wire format keeps the short name (`.infragram.json`, the `infragram`
package, the `infragram:` shared library id).

| Module | Owns |
|---|---|
| `author/` | how a diagram is written: `edge` (the wire: label, line, style), `diagram` (the `with` block and what it exports) |
| `compose/` | a topology tree into a project document: `errors`, `ids` (qualification against the installed catalogs), `inference` (the libraries and kind read off what a document holds), `document` (the assembly) |
| `exports/` | the exporter, split along its seams: `errors`, `presets` (named sizes and the style each asks for), `svg` (finishing one document: namespace, viewBox, fonts, ground), `render` (drawing without a browser), `palette` (the dark and darker canvases), `browser` (the Playwright renderers and the content crop), `project` (writing the artifacts asked for) |
| `projects/` | the project document: `names` (the closed vocabularies), `parts` (provider selection, layer, presentation, the `View` it declares), `document` (`CloudProject` and its migrations), `views` (drawing one part of a document on its own: a frame, a rule, a declared view) |
| `models/` | domain models: the topology tree (`TopologyElement`, `Connection`), providers and icons, and `changes` (the marks a plan and a diff draw: add, change, replace, destroy, drift) |
| `nodes/` | generated node and frame classes per library; `_base.py` (Element, Group, Frame), `_scope.py` (open `with` scopes) |
| `patterns/` | `Pattern` and `Blueprint`: repetition and the low-level assembly layer for generators |
| `builders/` | the Python renderer and its rules: `architecture` (a topology into a placed scene), `scene`, `saved_geometry`, `render`, `routing`, `captions`, `frame_style`, `metrics`, `arrowheads`, `ink`, `index` (the icon index) |
| `editor/` | the exported page: `shell` (data in, page out), `state`, `sidebar`, `artwork`, `bundle` (the runtime assembled from its numbered modules in the order they evaluate, and the stylesheet from its files in cascade order), `runtime/` -- 35 modules, the browser side -- and `ui/` (components/, styles/ and views/: the chrome's markup builders and stylesheets) |
| `catalog/` | catalog contracts: component specs, aliases, tiers and container artwork |
| `registries/` | the provider skin catalog, icon collections, class naming, plugin manifests ([README](registries/README.md)) |
| `themes/` | `Theme`, the theme files (`theme_manifest`), and `colour` (hex channels, WCAG luminance and contrast) |
| `verification/` | SVG safety screen, viewBox and body extraction, presentation attributes |
| `utils/` | small cross-cutting helpers |
| `paths/` | where the plugin (its skills and assets) and the checkout around it are -- found by what they hold, never by counting directories |
| `mcp/` | `infragram mcp`: the user commands served to an MCP client over stdio, on the standard library: `tools` (each tool's schema and the command it runs), `run` (running one, reading what it printed), `resources` (resources and prompts), `protocol` (the JSON-RPC loop) |
| `review/` | what a reviewer reads: `diff` (what changed between two versions, `infragram diff`) and `policy` (the rules `infragram check:policy` applies, and Checkov or Trivy on a folder) |
| `terraform/` | a diagram to Terraform (`emit`, `dynamic`, `render_modules`), Terraform read back (`hclread`, `readconfig`, `readstate`), and `check` (Terraform itself on a skeleton, offline) |
| `estate/` | what an import or discovery found, drawn as a diagram file |
| `convert/` | another tool's diagram read as a sketch and drawn (`import:diagram`): `drawio`, `mermaid`, `plantuml`, `c4`, `excalidraw`, `visio`, `xmlsafe` (XML without its declarations), `model`, `match` (a shape to a component), `nesting`, `draw`, `report` |
| `iso3d/` | the 3D items drawn by spec: `vocabulary` (the recipes, knobs, families and glyphs `scene.js` defines), `api` (a spec built and rendered), `render` and `bundle` (three.js in headless Chromium, and in the page), `measure`, `seat`, `cache`, `recipes` |
| `pricing/` | what a diagram costs a month: `ask` and `tables` (the pricer's request and the shipped price tables), `aws`, `azure`, `gcp` (each cloud's pricers and what it covers), `build/` (the tables read from each cloud's price source), `fetch` (live prices, https only), `infracost` (a breakdown joined by Terraform address), `rollup` (added up by frame) |
| `cli/` | the `infragram` command: `user/` (the user commands, run in-process from any copy), `commands/` (one module per group, merged by an `__init__` that refuses a name claimed twice), `scripts` (finding the maintainer script a command names, in a checkout), `runner` (running one, or a gate list in order), `version`, `cli` (parsing and dispatch); `user/hook_check` is the plugin's check hook, `user/plugin_install` registers the plugin with an agent |

## Layering

```
author ──► compose ──► projects ──► exports ──► editor + builders
nodes  ──► models                             builders ──► catalog, registries, themes, verification
```

Dependencies point one way. `models/`, `themes/` and `verification/` import
nothing above them; `nodes/` builds on `models/`; `builders/` reads the
catalogs and themes and draws; `editor/` writes the page from a placed scene;
`exports/` runs the browser. The numbers both renderers share live in
`skills/infragram-architect/assets/catalog/render-metrics.json` and are read
through `builders/metrics.py`; every JSON asset loads through a pydantic model.

## Using it

```python
from infragram.author import Diagram, Edge
from infragram.nodes.frames import azure as az
from infragram.nodes.azure import compute

with Diagram("Azure: subscription to VM") as diagram:
    with az.Subscription("Production"), az.ResourceGroup("rg-prod"):
        with az.VNet("vnet-prod").row(), az.Subnet("snet-web"):
            web = compute.VirtualMachine("Web tier", "VM scale set")
diagram.export("dist", formats=("html", "svg", "png"))
```

```bash
uv run infragram compose spec.py --formats html,svg,png --output-dir dist
uv run infragram verify:quick
```
