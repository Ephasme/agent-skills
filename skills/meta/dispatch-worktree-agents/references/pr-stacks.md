# Pull requests as GitHub stacks

GitHub's stacked pull requests (public preview) chain PRs so that each one targets the
branch of the PR below it and the bottom one targets the trunk. Each layer shows only its own
diff, is reviewed on its own, and CI and branch protection run on every layer as if it
targeted the trunk. Merging a layer merges everything below it; the rest re-target the trunk
automatically. The dependency graph this skill builds is already that shape, so with
`"pr": "stack"` the run maps it onto stacks for you.

## Contents

- When to stack
- Shaping the graph
- What `herd.py` does
- Maintaining a stack
- Prerequisites and failure modes

## When to stack

Stack when the user wants reviewable PRs out of the run and a task builds on another's
unmerged branch. Keep `"pr": "none"` (the default) when the run is exploratory, when the user
reviews branches locally, or when every task is independent — independent tasks are plain PRs
on the trunk either way, and `"pr": "stack"` still opens those for you.

## Shaping the graph

GitHub requires a **fully linear history** in a stack and a PR belongs to exactly one stack.
Two consequences for step 1:

- **No joins across branches.** A task depending on two siblings that ran in parallel would
  need a merge commit, which a stack refuses. `herd.py check` rejects it and names the fix:
  serialise the siblings (make one depend on the other), then the joining task sits on the
  top one. When the siblings touch separable parts of the same files, serialising costs one
  rebase and buys a mergeable stack — usually the right trade. Otherwise keep them parallel
  and let the joining task wait until they have **merged** to the trunk (base it on the trunk,
  in a later run).
- **Fans split into stacks.** When several tasks depend on the same parent, the first in
  manifest order continues the parent's stack; each other one starts a new stack on top of
  the parent's branch. Order the manifest so the longest or most important line comes first.

`check` prints the resulting stacks, bottom first:

```
stack: main <- tanstack-table <- column-resize <- column-reorder <- view-permalinks
stack: tanstack-table <- docs-update
```

A task's PR base is always the branch it was cut from; `"base"` on a task overrides both.
`"merge"` is rejected in stack mode for the same linearity reason.

## What `herd.py` does

On every scheduler tick where a new done marker appeared (and on demand with
`herd.py stack <manifest>`), for each finished task in manifest order:

1. push the branch if the agent left it local — never force a branch origin holds at another
   commit;
2. open a **draft** PR on its base if none is open (title from the task `summary`, body from
   its first commit), or retarget an open PR whose base is wrong;
3. link each chain with `gh stack link --base <trunk> <pr> <pr> …`, bottom first. A chain is
   linked only as far as its layers are finished, since a stack must be contiguous from the
   bottom; linking is additive, so a later tick extends the same stack.

`herd.py status` prints each chain with its PR numbers and bases and the GitHub stack number
once linked. Drafts are deliberate: marking ready for review stays the user's call.

Agents are told in their prompt and in their system prompt (which survives plan approval)
that PRs are managed for them: never open, retarget or merge PRs, never rebase a branch below
their own, never merge a branch in.

## Maintaining a stack

- **A lower layer changed** (review fixes, a rebase): each layer above moves only its own
  commits onto the new parent — `git rebase --onto origin/<parent> <previous parent tip>
  <branch>`, then `git push --force-with-lease` — bottom-up, one agent per layer. Record the
  tips before the lowest rebase; after it, the previous tip is gone from the branch. On the
  website, **Rebase stack** in the merge box does the same server-side.
- **The trunk moved**: rebase the bottom layer onto the trunk first, then cascade as above.
  The scheduler re-links nothing it does not need to; run `herd.py stack` afterwards to
  confirm bases and membership.
- **Merging**: bottom-up only. `gh stack merge <pr>` merges everything up to that PR in one
  atomic operation; the layers above re-target the trunk automatically.

`gh stack rebase` / `gh stack sync` automate the cascade but need the stack adopted locally
with `gh stack init`, in one working tree — they do not fit a run where every layer lives in
its own worktree, which is why the per-layer `rebase --onto` above is the default here.

## Prerequisites and failure modes

`check` verifies them when `"pr": "stack"` is set:

- `gh` authenticated, and the `gh-stack` extension: `gh extension install github/gh-stack`.
- Stacked PRs enabled on the repository (`GET /repos/{owner}/{repo}/stacks` answers).
- All branches in the same repository — cross-fork stacks are not supported.

`herd.py` passes `GH_REPO` to every `gh` call: `gh-stack` resolves the repository from the
remote URL alone and fails on an SSH host alias such as `git@github.com-work:org/repo.git`
("none of the git remotes … point to a known GitHub host"), which `gh` itself resolves.

A sync failure is logged and notified once and retried on the next tick; the scheduler does
not exit while a finished task is still unsynced.
