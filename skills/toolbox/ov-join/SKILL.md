---
name: ov-join
description: >-
  Registers the directory of the pane running this agent as an overlord target, so the overlord
  daemon drives that agent through plan, harden, build, review, fix, merge and cleanup by typing the
  next instruction at each phase boundary. Use when the user types `/ov-join` or asks to join,
  enrol, register or hand this pane over to overlord, e.g. "join overlord", "put this pane under
  overlord", "let overlord drive this one", or in French "rejoins overlord". Not the same as
  summon-the-overlord, which runs the daemon itself.
compatibility: >-
  Requires the `overlord` and `herdr` binaries on PATH, and a herdr pane: overlord matches a target
  to a pane by exact cwd equality, so a registration made outside herdr is never driven.
disable-model-invocation: true
---

# Join overlord

**Explicit invocation only.** Registering hands the workspace label and the prompts typed into this
pane to the overlord daemon until the work is merged and pruned. Where `disable-model-invocation` is
ignored, this paragraph is the rule.

Overlord is a separate daemon (`overlord run`) sweeping registered targets every 60 s. Joining is
`overlord add`: one row in `~/.overlord/state.db`. Nothing else about the agent changes — same pane,
same checkout, same branch.

## The path is the identity

A target is a pane whose `cwd` equals the registered path **exactly**: string equality, no walking
up, no discovery. So register the pane's own cwd, absolute and canonicalised. A shell's `pwd` inside a
subdirectory, or a `cd` done in this turn, is not it.

```bash
herdr pane list | jq -r --arg p "$HERDR_PANE_ID" '.result.panes[] | select(.pane_id==$p) | .cwd'
```

Fall back to `pwd -P` only when `herdr pane list` is unreachable, and say so in the report: with no
matching pane nothing will ever prompt this agent. `add` also refuses a relative path (exit 2, "path
must be absolute").

## Check before adding

```bash
overlord list
```

One tab-separated row per target: machine, path, PR gate, base, deploy command, phase, last decision.

`add` is an upsert on (machine, path): it rewrites `pr_capable`, `base` and `deploy_cmd`, and an
omitted `--deploy-cmd` stores an empty one. A path already listed is therefore not re-added to
"refresh" it — that silently drops its deploy command. Re-add only when the user asked for a change,
repeating every flag the row should keep.

## Add

```bash
overlord add <pane cwd>
overlord add <pane cwd> --base <branch>       # PR target when origin/HEAD is not it
overlord add <pane cwd> --deploy-cmd "<cmd>"  # run in the target once its PR is MERGED
```

Never `--machine`: that registers a path on a saved herdr machine, for another host. This agent's own
pane is local.

## Report

`overlord list` again. The row must carry this path, the expected PR gate (`yes` when the checkout has
a GitHub remote, `no` otherwise — no remote means deploy then `DONE`, with no review loop), the base
and the deploy command. Name anything missing rather than assuming it.

Then `pgrep -f 'overlord run'`. A registration with no pass running is inert: nothing sweeps it. Do not
start `overlord run` here — it drives every target on the host and holds a single-instance lock — say
it is missing and stop.

## Once joined

- The workspace label is overlord's phase storage (`HRDN?`, `BUILD?`, `REV?`, `FIX?`, `MRG?`,
  `HELP?`, `DONE`). Never rename this workspace or pane, and never relabel it to "tidy": the label is
  read back as the phase, so a rename is a phase change.
- Overlord types the next instruction at each boundary and never edits files or merges from here.
  Follow the prompt, keep the PR's checks green, push the fix instead of asking what to do.
- `HELP?` means a cause hit its retry cap and a person decides. Report it; do not fight the cap.
