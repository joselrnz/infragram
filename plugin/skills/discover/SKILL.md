---
name: discover
description: Draw a live AWS, Azure or Google Cloud estate, or a Kubernetes cluster, read-only through the cloud's own CLI or kubectl as the user is signed in, as an editable diagram file and a report, exported to HTML, SVG and PNG. Run when the user invokes it with a cloud or kubernetes.
argument-hint: <aws | azure | gcp | kubernetes> [--region R] [--profile P] [--subscription S] [--source resource-graph] [--project P] [--context C] [--namespace N] [--output-dir <dir>] [--force]
disable-model-invocation: true
allowed-tools: Read Write Glob Bash(python:*) Bash(python3:*)
---

# Draw a live cloud account

Draw the estate of the cloud named first in the arguments (`$ARGUMENTS`):
`aws`, `azure` or `gcp`, or the Kubernetes cluster for `kubernetes`. This command belongs to the Infragram Architect
plugin: the `infragram-architect` skill sits beside this skill's folder, and
`<plugin>` below is the folder holding both: `${CLAUDE_PLUGIN_ROOT}` in Claude
Code, and in Codex or Pi the folder two above this skill's own.

Read `<plugin>/skills/infragram-architect/references/terraform.md` section 3
first: it says what is drawn, what is folded or left out, and why. The estate
is read through that cloud's own CLI (`aws`, `az`, `gcloud`), or `kubectl` for
a cluster, as the user is already signed in, with list and describe (or get)
calls only. Pass the rest of the arguments on: `--region` and `--profile` for
AWS, `--subscription` and `--resource-group` for Azure, `--project` and
`--region` for Google Cloud, `--context` and `--namespace` (repeatable) for
Kubernetes. Run
from the user's directory, for example:

```bash
python "<plugin>/skills/infragram-architect/scripts/infragram.py" discover:aws --region eu-west-1 --verify
```

Use `python3` where `python` is not Python 3. Never run a cloud command that
creates, changes or deletes anything, and never sign the user in or out.
A second discovery replaces what the first wrote; never add `--force` for a
file it refuses (edited since) unless the user explicitly intends to lose
that edit. Report the `READ`, `SPEC` and `REPORT` lines, every produced path and
byte size, the verification verdict, and the notes about what could not be
read. The diagram file is the starting point: offer to regroup or recaption
it, then compose it again.
