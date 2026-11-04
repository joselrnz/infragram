---
name: import
description: Draw existing infrastructure or an existing diagram as an editable infragram diagram file and a report, exported to HTML, SVG and PNG - from Terraform (a configuration folder, a plan or a state), or from a diagram drawn in draw.io, Mermaid, PlantUML, Excalidraw, Visio/Lucidchart or a Markdown page's diagram blocks. Run when the user invokes it with Terraform or a diagram file to draw.
argument-hint: <terraform-folder | plan.json | terraform.tfstate | file.drawio | file.mmd | file.puml | file.excalidraw | file.vsdx | page.md> [--page NAME|N] [--var-file prod.tfvars] [--output-dir <dir>] [--force]
disable-model-invocation: true
allowed-tools: Read Write Glob Bash(python:*) Bash(python3:*)
---

# Draw existing Terraform or an existing diagram

Draw what the file or folder named in the arguments (`$ARGUMENTS`) holds.
This command belongs to the Infragram Architect plugin: the
`infragram-architect` skill sits beside this skill's folder, and `<plugin>`
below is the folder holding both: `${CLAUDE_PLUGIN_ROOT}` in Claude Code, and
in Codex or Pi the folder two above this skill's own.

Use `python3` where `python` is not Python 3. Never add `--force` unless the
user explicitly intends to replace the named files.

## Terraform

When the first argument is a folder of Terraform, a plan as `terraform show
-json` writes it, or a `terraform.tfstate`, read
`<plugin>/skills/infragram-architect/references/terraform.md` section 3
first: it says what is drawn, what is folded or left out, and why. Run from
the user's directory:

```bash
python "<plugin>/skills/infragram-architect/scripts/infragram.py" import:terraform <the arguments> --verify
```

A live account instead of files is the `discover` command. Never run a
Terraform or cloud command that creates, changes or deletes anything.

## A diagram from another tool

When the first argument is a draw.io file (`.drawio`, `.drawio.png`,
`.drawio.svg`), Mermaid (`.mmd`), PlantUML (`.puml`), Excalidraw
(`.excalidraw`, `.excalidraw.md`), Visio or Lucidchart (`.vsdx`), or a
Markdown page with ```` ```mermaid ```` or ```` ```plantuml ```` blocks, read
`<plugin>/skills/infragram-architect/references/import-diagrams.md` first.
When the file may hold several diagrams, list them, then import:

```bash
python "<plugin>/skills/infragram-architect/scripts/infragram.py" import:diagram <file> --list
python "<plugin>/skills/infragram-architect/scripts/infragram.py" import:diagram <the arguments> --verify
```

Each diagram (a page, a block) becomes its own diagram file and report;
`--page` picks some.

## Report back

Report the `READ`, `SPEC` and `REPORT` lines, every produced path and byte
size, the verification verdict, and the notes about what could not be read.
For a diagram import, also name the shapes the report lists under "Guessed
from words or shape". The diagram file is the starting point: offer to
regroup, recaption or reclass it, then compose it again.
