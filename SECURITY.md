# Security policy

## Reporting a vulnerability

Use the repository host's private vulnerability-reporting feature when it
is enabled. If no private reporting channel is available, contact the
maintainer privately through the host before sending vulnerability details.
Do not include those details in a public issue, pull request or discussion.

Say what you found and how to reproduce it: the version (`infragram
--version`), how it was installed (a checkout, the wheel, the npm package or
an agent's marketplace), the command or tool call, and the smallest file that
shows the problem. If you know what an attacker gains, say that too. Responses
use the same private channel.

## Supported versions

| Version | Security fixes |
|---|---|
| 0.0.2 | yes |

An exported page carries the editor of the version that wrote it, so a fix
in the editor reaches an existing page only when it is exported again.

## Threat model

What Infragram runs, reads and reaches, as the code does it.

### What runs code

- **A diagram file is a Python program.** `infragram compose file.py` runs
  it, and `compose -` runs what arrives on standard input. So does
  `export:set` (every `*.py` in the folder it is given), and so do `diff`,
  `views`, `costs`, `check:policy` and `check:terraform` when they are handed
  a `.py` file. Treat a diagram file like any script: read one you did not
  write before you run it.
- **The MCP server runs diagram files too.** Its `compose` tool runs a
  diagram file, and `compose_source` writes the Python source the client
  sends and then runs it. An agent given the server can run Python as you, in
  the folder the server started in; approve those calls as you would a shell
  command.
- **Tools from your PATH, only when a command needs them:** the cloud CLIs
  (`aws`, `az`, `gcloud`, `kubectl`) for discovery, `terraform` for
  `check:terraform`, Checkov or Trivy for `check:policy` on a Terraform
  folder when they are installed, the agents' CLIs for `plugin:install`, and
  Chromium, through Playwright, to draw a page. Each is called with an
  argument list, not a shell command line. On Windows `az` and `gcloud` are
  batch files that run through cmd.exe: there every argument is quoted for
  cmd.exe, and one holding `%` or a line break is refused.
- **`check:terraform` runs Terraform** (`fmt`, `init`, `validate`, then a
  plan against mocked providers) offline, on the skeleton a diagram exports or
  on a Terraform folder you name. Before you name a folder you did not write,
  treat it as you would before running `terraform` in it.

### What is read as data

- **A `.infragram.json` document** is data. A colour it stores for a card,
  frame or wire is written into the picture only when it is a colour (a hex,
  a CSS name, or `rgb()`/`hsl()`); anything else is dropped, and
  `infragram check` fails the document.
- **A comments file** (`<slug>.comments.json`, ADR 0009) is data, read by
  the same rules as a document: a fixed format, checked by `infragram check`,
  carried into the page in a JSON script that cannot close itself, and shown
  as text. Comments written in a page stay in that browser's local storage
  until the reader downloads them; the page sends them nowhere, and no SVG,
  PNG or draw.io carries one. A page opened from a file shares the browser's
  storage with every other page opened from a file, keyed by the diagram's
  slug: a page someone sends with the same slug as one of yours opens your
  saved workspace and comments for that diagram. Nothing leaves the browser
  unless you download it, but open pages from people you trust, or use
  `?fresh=` for a separate workspace. A comment's author is whatever name was
  typed; nothing verifies it.
- **draw.io and Visio XML** goes through `infragram.convert.xmlsafe`, which
  refuses any `ENTITY` declaration and any `DOCTYPE` with an internal subset
  before the standard library parses the file, and checks with expat in the
  document's own encoding as well as with a text search. A compressed page
  or a `.vsdx` member is expanded only up to a limit
  (`infragram.convert.bounded`), so a small file cannot claim gigabytes.
- **Terraform HCL** (`*.tf`, `*.tf.json`, variable files), **plans and
  states** (as `terraform show -json` writes them, or a `terraform.tfstate`
  file), **Mermaid**, **PlantUML** and
  **Excalidraw** are parsed as data. Nothing in them is executed, and
  `import:terraform` does not run Terraform.
- **The plugin's check hook** (`infragram hook:check`, which Claude Code and
  Codex run after the agent writes a file) checks a `.infragram.json` with the
  shipped checker and reads a diagram `.py` with Python's `ast` module. It
  never runs the file: the only modules it imports are Infragram's own, never
  its command-line `__main__`, to confirm that a class the file names exists. It always exits 0, so it never
  fails the tool call it follows.

### What reaches the network

- **Discovery is read-only.** `discover:aws`, `discover:azure`,
  `discover:gcp` and `discover:kubernetes` call the providers' own CLIs with
  list, describe, get and show calls only (each reader's calls are spelt out
  in `plugin/src/infragram/estate/discover/`), as the CLI is already signed
  in. Infragram never signs in or out and holds no credentials of its own.
  `discover:azure --source resource-graph` sends one paged query to Azure
  Resource Graph through `az rest`, a read that needs only the Reader role.
- **Prices** (`--prices`) are fetched while exporting, never when a page is
  opened, from AWS's published price files, over https only
  (`infragram.pricing.fetch` refuses any other scheme), and kept for a day in
  Infragram's cache.
- **Drawing never reaches another machine.** A page carries its libraries,
  its fonts (inline, under the OFL) and its editor, and works from `file://`.
  When Chromium draws a PNG or SVG, every request that is not the page, what
  it carries, or this machine is refused, so a shared document cannot make
  the render call out. Links in a card's details are ordinary links; nothing
  is fetched unless you follow one. `compose --watch` serves its page on
  127.0.0.1 only.
- **The checker holds pages and artwork to this.** `infragram check` (and
  `--verify` on an export) fails a page that loads a remote script or
  resource (other than the Google Fonts hosts that pages from older versions
  used), and a document, page or picture whose markup carries a script, an
  event handler, an embedded document or a reference to another server. Icon artwork is checked for
  active content when a library's catalog is loaded and again before the
  static renderer inlines it; an unsafe icon stops the export.

### The MCP server

`infragram mcp` (the plugin's MCP server) speaks JSON-RPC over stdio. Each
tool that runs a command runs `python -m infragram <command>` in the folder
the client started the server in, with its arguments held to the tool's
schema, the command line built by the server, standard input closed, and
Python's `-P` flag so a file in that folder cannot stand in for a module. The
one file the server writes itself, `compose_source`'s diagram file, must
resolve inside that folder. Other path arguments reach the command as you
would type them, so a client can name files elsewhere that your account can
read or write. Its resources are a fixed list of files the plugin ships, plus
a generated listing of each library's node classes.

### What the output holds

A diagram drawn from a Terraform plan or state, or from a live estate,
records what it drew from: names, IDs, addresses, tags and rules, and its
report says what was read. Treat those files, and the pages and pictures
exported from them, as you would the source, and review them before sharing.
By default an SVG and a PNG carry their whole document, so that
`export:project picture.png` can redraw it; export with `--no-embed` to leave
a picture bare.
