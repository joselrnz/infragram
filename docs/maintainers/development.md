# Development

## Setup

Use Python 3.11 or later. The repository is a uv workspace containing `plugin/`.

```bash
uv sync --all-extras
playwright install chromium
```

Activate `.venv` before running the CLI. The test tools are pinned in `uv.lock`.
Node is needed for JavaScript syntax checks; Terraform and agent CLIs are needed
for their respective verification commands.

## Verification

```bash
infragram verify:quick
infragram verify:types
infragram verify:browser
infragram verify:terraform
infragram verify:install --strict
infragram verify:all
```

`verify:quick` checks lint, types, repository consistency and unit tests without
slow cases. Browser checks use Chromium. `verify:all` also checks rendering,
installation and dependencies; its dependency audit needs network access.

## Packages and generated assets

```bash
infragram build:packages
infragram inventory
infragram inventory --images
python scripts/docs/regenerate-media.py
```

Packages are written to `dist/packages`; building does not publish them. Keep
package and plugin versions synchronized and run `uv lock` after a version or
requirement change. The starting version is 0.0.1.

## Price tables

The shipped price tables live in
`plugin/skills/infragram-architect/assets/prices/`. Rebuild them with:

```bash
python scripts/build/price-tables.py aws
python scripts/build/price-tables.py azure
python scripts/build/price-tables.py gcp
```

Google Cloud's table builder needs `INFRAGRAM_GCP_PRICING_KEY` in the shell.
Keep that key outside the repository. Viewing shipped estimates requires no key.

[Contributing](../../CONTRIBUTING.md) · [Documentation](../README.md)
