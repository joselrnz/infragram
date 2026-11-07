# Installation

Everything that installs is the [`plugin/`](../plugin/README.md) folder: the
manifests, the skills, the hook, the agent, the MCP server's configuration,
the Python package, the examples and the licences. The repository around it
(tests, docs, maintainer scripts) never reaches an agent.
[`plugin/README.md`](../plugin/README.md) is the guide: what each agent gets,
every install route, and the requirements (Python 3.11 or later with
pydantic 2; Playwright and Chromium for a PNG; uv for the MCP server).

From this repository:

| Route | Command |
|---|---|
| Claude Code | `claude plugin marketplace add <repository>` then `claude plugin install infragram-architect@infragram-architect` |
| Codex | `codex plugin marketplace add <repository>` then `codex plugin add infragram-architect@infragram-architect` |
| Pi | `pi install git:<repository>`, or `pi install <repository>/plugin` |
| uv or pip, then any agent | `uv tool install ./plugin` (or `pip install ./plugin`), then `infragram plugin:install claude\|codex\|pi` |
| any agent that reads skills | copy `plugin/skills/infragram-architect` there, and install the package once |
| GitHub Copilot, Cursor, other MCP clients | the MCP server and the skill: see below |

`<repository>` is a path to this checkout or its git URL: the marketplace at
the root names `./plugin`, so an agent copies that folder and nothing else.
The npm package and the wheel carry the same folder; `infragram
build:packages` builds both into `dist/packages`, and nothing is published
yet.

## GitHub Copilot, Cursor and other MCP clients

Copilot in VS Code and Cursor use Infragram through two pieces, both tested
from this repository on GitHub: the **MCP server**, whose tools draw, check,
price and export, and the **skill**, which tells the agent how. The server
needs [uv](https://docs.astral.sh/uv/); it runs in the folder the editor opens,
so diagrams land in your project.

**GitHub Copilot in VS Code.** Add the server to your profile:

```bash
code --add-mcp '{"name":"infragram","command":"uvx","args":["--from","git+https://github.com/joselrnz/infragram#subdirectory=plugin","infragram","mcp"]}'
```

or to one project, in `.vscode/mcp.json`:

```json
{"servers": {"infragram": {"command": "uvx", "args": ["--from", "git+https://github.com/joselrnz/infragram#subdirectory=plugin", "infragram", "mcp"]}}}
```

Then the skill: copy `plugin/skills/infragram-architect` into the project's
`.github/skills/`, where Copilot's agent mode reads skills.

**Cursor.** Put the server in `.cursor/mcp.json` (the project) or
`~/.cursor/mcp.json` (every project):

```json
{"mcpServers": {"infragram": {"command": "uvx", "args": ["--from", "git+https://github.com/joselrnz/infragram#subdirectory=plugin", "infragram", "mcp"]}}}
```

and copy the skill folder into `.cursor/skills/`.

**Codex.** The plugin route above installs the skill, which runs everything
through its launcher, so Codex needs nothing more. For the MCP tools as well:

```bash
codex mcp add infragram -- uvx --from "git+https://github.com/joselrnz/infragram#subdirectory=plugin" infragram mcp
```

A skill copied out of the repository on its own runs through the package
installed once: `uv tool install "git+https://github.com/joselrnz/infragram#subdirectory=plugin[png]"`.
Any other MCP client takes the same command: `uvx --from <that source> infragram mcp`.

[Documentation](README.md) · [Project README](../README.md)
