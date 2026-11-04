# Importing diagrams from other tools

`infragram import:diagram <file>` reads a diagram someone drew in another
tool and writes it as an infragram diagram file (`<slug>.py`, the `with
Diagram` form) beside a report (`<slug>.import.md`), then composes and
exports it like any other (`--formats`, `--verify`, `--output-dir`, `--force`).
`import:drawio` and `import:mermaid` are the same command with the format
fixed. The diagram file is where the diagram starts: regroup, recaption or
change a class, then `compose` it again.

## What it reads

| Format | Files | One diagram per |
|---|---|---|
| draw.io / diagrams.net | `.drawio`, `.dio`, `.xml`, `.drawio.png`, `.drawio.svg` (plain or compressed pages) | page |
| Mermaid | `.mmd`, `.mermaid`: `flowchart`/`graph`, `architecture-beta`, `C4Context`, `C4Container`, `C4Component`, `C4Dynamic`, `C4Deployment` | file |
| PlantUML | `.puml`, `.plantuml`, `.pu`, `.iuml`, `.wsd`: deployment and component diagrams, C4-PlantUML, AWS/Azure/Kubernetes libraries, tupadr3 icon macros | `@startuml` block |
| Excalidraw | `.excalidraw`, `.excalidraw.json`, Obsidian `.excalidraw.md` (plain or compressed) | file |
| Visio / Lucidchart | `.vsdx` (Lucidchart exports Visio); an old `.vsd` is refused with "save it as .vsdx" | foreground page |
| Markdown | `.md`: every ```` ```mermaid ```` and ```` ```plantuml ```` block, titled by the heading above it | block |

A file with another name is told by its contents; `--format` names it
outright. `--list` prints the diagrams a file holds, `--page NAME|N` picks
some (repeatable); `--title` and `--spec` need exactly one. Sequence, class,
state, Gantt and other kinds that draw no architecture are refused by name
(in Markdown, passed over with a note).

## What becomes what

- **Frames.** A shape the source nests others in (a draw.io container or
  swimlane, a Mermaid `subgraph` or architecture `group`, a PlantUML block
  `{`, a C4 boundary or deployment node, an Excalidraw frame, a Visio
  container), and any shape drawn wholly around others, holds them. Its
  library and kind come from its stencil (a draw.io AWS VPC group is
  `frames.aws.VPC`, the green and blue subnet groups `PublicSubnet` and
  `PrivateSubnet`; `VPCGroup(...)` in AWS-PlantUML) or its label (`Public
  subnet`, `rg-prod`, `us-east-1`, `team namespace`, `On-prem datacenter`,
  `Production`), in the library most of its contents come from, then the
  generic frames. A label that names no kind is a plain `Group`. A container
  without a label gives its shapes to its parent.
- **Components.** In order: the stencil or icon in its own library
  (`mxgraph.aws4.lambda_function`, `resIcon=mxgraph.aws4.rds`,
  `img/lib/azure2/.../Function_Apps.svg`, `logos:aws-lambda`,
  `@{ icon: "aws:lambda" }`, `AzureFunction(...)`, a `<$Lambda>` sprite, a
  Visio master named `Amazon EC2`); a technology or generic icon (a C4
  `"PostgreSQL"`, `logos:redis`) or the label, matched exactly in the
  diagram's own libraries and the shared one, and in any library only when
  the name is a product's own (`Cosmos DB`, `BigQuery`; never `Browser`);
  a name the label holds (`Orders DB (RDS)`); a cloud the label names
  (`Amazon S3`); what the words say (`users`, `queue`, `api`, `cache`,
  `web server`); what the shape is (a cylinder is a database, a stick figure
  a person, a cloud a cloud); else a generic container. Every guess from
  words or shape is listed in the report under "Guessed from words or
  shape". The 3D isometric set is never guessed.
- **Labels.** The first line is the caption, the rest the detail; HTML,
  Markdown and icon codes are stripped. A text shape inside an unlabelled
  one is its label; a text shape on its own is an annotation and is left
  out. draw.io `<object>` data, C4 descriptions and technologies, Mermaid
  `click` links and PlantUML macro names land in the element's popup table
  with where the shape was read and what the match rested on.
- **Mermaid panels.** A flowchart's look comes along as a panel (compose.md,
  Panels): each `<br>` line under the caption stays a line of the detail;
  `((circle))` and v11 `circle` draw an ellipse, `{{hexagon}}` and `hex` a
  hexagon, v11 `doc` a note; a fill from `classDef` with `class` or
  `:::name`, or from `style`, becomes the tone nearest its hue (a class
  named for a tone, `blocker` or `privateNet`, is that tone; white is
  none). The class names say what each tone means in the legend:
  `classDef publicEdge` writes `Diagram(tones={"edge": "public edge"})`.
  A panel the matcher could only guess at is written as a plain `Box`,
  with no guessed vendor icon in its corner.
- **Wires.** A line joins two drawn shapes; a draw.io, Excalidraw or Visio
  line with a loose end is joined to the shape under it or reported. The
  label, a dashed or dotted line and the arrowheads come along: one head is
  `>>`, two `both=True`, none `a - Edge() - b`; a line drawn backwards is
  turned around. Mermaid junctions fold into the lines they join; invisible
  (`~~~`) and hidden (`-[hidden]-`) links are dropped. Two lines saying the
  same thing are one wire.
- **Layout.** Nothing is placed: the composer lays the picture out. A
  Mermaid `flowchart LR` or PlantUML `left to right direction` sets
  `Diagram(direction="right")`; a subgraph's `direction` sets its frame's
  `.row()` or `.column()`.

## After the import

Read the report first: the guesses, the shapes left out and the lines that
joined nothing. Fix a wrong class in the diagram file (the popup's "Matched
by" row says why it was chosen), then compose it again. Nothing the readers
do touches the network or runs the source's tool.
