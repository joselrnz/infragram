# Contributing to Infragram Architect

## Setup

Use Python 3.11 or later. From the repository root:

```bash
uv sync --all-extras
playwright install chromium
```

Activate `.venv` before running the commands below. See
[development setup](docs/maintainers/development.md) for verification and builds.

## Repository layout

- `README.md`: project overview and quickstart.
- `plugin/`: app source, agent plugins, skills, examples, icons and package metadata.
- `tests/`: unit, browser, integration and rendering checks.
- `scripts/`: build tools, importers and verification commands.
- `docs/`: user guides, component inventory and README media.
- `.claude-plugin/` and `.agents/`: repository marketplace manifests.
- `.forgejo/` and `.github/`: CI and contribution templates for Forgejo and GitHub.

## Checks

```bash
infragram verify:quick
infragram verify:browser       # after editor changes
infragram verify:terraform     # after Terraform export changes
infragram verify:install       # after packaging changes
```

Keep the Python package and plugin manifest versions synchronized. The current
version is 0.0.1. After changing package requirements or versions, run `uv lock`.

Keep the app's existing themes and default light appearance. Update generated
assets with their build tools, preserve vendor artwork and license notices, and
keep credentials and personal information out of source files and exports.

Review changed renderings before updating `tests/golden/pictures.lock.json`.
Use `infragram verify:pictures --update` only after checking the affected images.

Describe the resulting behavior and relevant validation in a pull request.
Report vulnerabilities through the private process in [SECURITY.md](SECURITY.md).
