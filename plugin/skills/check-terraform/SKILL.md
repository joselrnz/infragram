---
name: check-terraform
description: Show that a diagram's Terraform works without deploying it - terraform fmt, init and validate offline, then a plan against mocked providers - for a document, a diagram file, an exported page or a Terraform folder. Run when the user invokes it.
argument-hint: <project.infragram.json | diagram.py | page.html | folder>... [--style resources|modules] [--var-file mine.tfvars] [--output-dir <dir>]
disable-model-invocation: true
allowed-tools: Read Glob Bash(python:*) Bash(python3:*)
---

# Check a diagram's Terraform

Show that the Terraform of the sources named in the arguments (`$ARGUMENTS`)
works, without deploying anything. This command belongs to the Infragram
Architect plugin: the `infragram-architect` skill sits beside this skill's
folder, and `<plugin>` below is the folder holding both:
`${CLAUDE_PLUGIN_ROOT}` in Claude Code, and in Codex or Pi the folder two
above this skill's own.

Read the `check:terraform` section of
`<plugin>/skills/infragram-architect/references/terraform.md` first. Run from
the user's directory:

```bash
python "<plugin>/skills/infragram-architect/scripts/infragram.py" check:terraform <the arguments>
```

Use `python3` where `python` is not Python 3. It needs the Terraform CLI on
the PATH. Terraform reads each skeleton in a copy, offline, and plans it
against mocked providers: nothing is created, no cloud is called and no
credentials are read. Never add `--fetch` (it downloads the pinned modules
and providers) unless the user asks for it, and never run a real
`terraform plan` or `apply` for them. When a configuration is skipped
because a module or provider is not cached, say which, and offer `--fetch`:
it downloads them once, from the Terraform registry into the cache, and is
the one step that reaches the network. Report each configuration's line
(`PASS` with what the plan would create, `FAIL` with Terraform's words, or
`SKIP` with what is missing), the plan files it wrote, and the variables it
made up values for, and say what a mocked plan cannot show (quotas, names
already taken, permissions): that is a real `terraform plan`, signed in,
which only the user runs.
