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

`<repository>` is a path to this checkout or its git URL: the marketplace at
the root names `./plugin`, so an agent copies that folder and nothing else.
The npm package and the wheel carry the same folder; `infragram
build:packages` builds both into `dist/packages`, and nothing is published
yet.

[Documentation](README.md) · [Project README](../README.md)
