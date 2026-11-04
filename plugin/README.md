# Infragram Architect

A plugin that draws infrastructure architecture diagrams -- cloud, multicloud,
hybrid, Kubernetes, virtualization and on-premises -- from nineteen provider
libraries (AWS, Azure, Google Cloud, DigitalOcean, Hetzner Cloud, Cloudflare,
Oracle Cloud, IBM Cloud, Alibaba Cloud, OVHcloud, Vultr, Akamai Cloud,
Kubernetes, Databricks, Equinix, OpenStack, VMware vSphere, Proxmox VE, Local &
On-Premises), with provider frames and typed links. One `.infragram.json` document, or a short
Python diagram file, exports to an editable offline HTML editor, an SVG and a
PNG. It also draws what already exists, from Terraform or read-only from a
live AWS, Azure or Google Cloud account, writes a diagram's Terraform, and
shows that Terraform works without deploying it.

It installs into Claude Code, Codex and Pi, and its skill works in any agent
that reads [Agent Skills](https://agentskills.io).

## What it adds

| Part | What it does | Claude Code | Codex | Pi |
|---|---|---|---|---|
| `infragram-architect` skill | the agent draws, exports and checks diagrams when you ask for one | yes | yes | yes |
| `compose`, `export-project`, `import`, `discover`, `check`, `check-terraform` | commands you run yourself | `/infragram-architect:compose` | `$compose` | `/skill:compose` |
| check hook | after the agent writes a `.infragram.json` the checker runs, and a diagram `.py` is read (never run); any problem goes back to it | yes | yes | -- |
| `infragram` MCP server | the commands as tools answering with data and an optional PNG preview, template, example and component lookup, the references as resources, and prompts, for any MCP client | yes | yes | -- |
| `diagram-reviewer` agent | reviews a diagram read-only: checker, three-pass render, the skill's rules | yes | -- | -- |
| `infragram` command | everything above from a terminal | with pip or uv | | |

## Install

Below, `<repository>` is the repository's git URL or a checkout of it, and
`<plugin folder>` is the plugin itself: the `plugin/` folder of a checkout,
an unpacked npm package, or the folder `infragram plugin:path` prints. The
plugin folder is its own marketplace.

**Claude Code**, from the npm package (`--registry <url>` for a private
registry):

```bash
claude plugin install infragram-architect@npm
```

or from the repository or a plugin folder, as a marketplace:

```bash
claude plugin marketplace add <repository>
claude plugin install infragram-architect@infragram-architect
```

**Codex**:

```bash
codex plugin marketplace add <repository>
codex plugin add infragram-architect@infragram-architect
```

**Pi**: `pi install npm:infragram-architect`, `pi install git:<repository>`
or `pi install <plugin folder>`.

**pip or uv**: the Python package `infragram` carries this whole plugin.
Install the command, then register the plugin it carries with an agent:

```bash
uv tool install "infragram[png]"
infragram plugin:install claude
```

From a checkout of the repository, install the folder instead:
`uv tool install "./plugin[png]"`. `pipx install` and `python -m pip install`
take the same arguments; `[png]` adds what a PNG needs and can be left out.
`infragram plugin:install codex` and `infragram plugin:install pi` register
it with the others, and `--dry-run` prints the commands.

**Any other agent** that reads a skills folder: copy
`skills/infragram-architect` from the plugin folder there, and install the
Python package once, so the skill's launcher finds it.

## Requirements

- Python 3.11 or later with pydantic 2. The launcher every command goes
  through (`skills/infragram-architect/scripts/infragram.py`) says how to
  install whatever is missing; with [uv](https://docs.astral.sh/uv/) on the
  PATH it runs the package through `uvx` instead.
- A PNG also needs Playwright and Chromium: the `png` extra
  (`python -m pip install "infragram[png]"`, or `"./plugin[png]"` from a
  checkout), then `python -m playwright install chromium`. Without them an
  export writes the HTML and SVG and says why.
- The MCP server runs through `uvx`, so it needs uv; its first start downloads
  the package's dependencies, Playwright among them, and for PNGs Chromium once:
  `uvx --from "<plugin folder>[png]" playwright install chromium`, with the
  folder the agent installed the plugin into.
- `check-terraform` needs the Terraform CLI, 1.7 or later for the plan.

## Use

Ask for a diagram ("draw our AWS three-tier web app with the database in
private subnets"), or run a command on your own files, from your project's
folder:

```text
/infragram-architect:compose my_diagram.py
/infragram-architect:export-project dist/my-diagram.infragram.json
/infragram-architect:import ./terraform
/infragram-architect:check-terraform dist/my-diagram.infragram.json
```

A command's paths are read from your folder, not the plugin's. To start from
one of the plugin's diagram files or templates, ask the agent for it by name
("compose the AWS three-tier example"), or, with the `infragram` command
installed, copy one with `infragram new` (`infragram new --list` names them),
or find the plugin folder with `infragram plugin:path`:

```bash
infragram compose "$(infragram plugin:path)/examples/aws_three_tier.py"
```

Every export prices its AWS, Azure and Google Cloud components,
approximately, from on-demand list prices shipped with the plugin: the page's
header shows the month's total and its Cost tab breaks it down by frame and
item, line by line. Every cloud card links to where its component is read
about (right-click, Details).

From a terminal, `infragram --help` lists every command. `skills/infragram-architect/SKILL.md`
and its `references/` are the full guide; `examples/` holds complete diagram
files.

## License

MIT (`LICENSE`); the provider artwork is its owners', under the terms in
`THIRD_PARTY_LICENSES.md`. Cloud, platform and product names and logos are
their owners' trademarks; Infragram Architect is not affiliated with,
sponsored by or endorsed by any of them.
