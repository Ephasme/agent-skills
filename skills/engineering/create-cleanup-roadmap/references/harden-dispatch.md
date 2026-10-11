# Hardening dispatch

One sub-agent per plan. Not one per finding, not one per wave — a plan is the unit that gets a single
owner, and the hardening read has to see the whole document.

## Prompt template

Fill every placeholder and dispatch with the plan file's path. Keep the prompt self-contained: the
sub-agent cannot see the conversation that produced the plan, and it cannot see its siblings.

> You are hardening one implementation plan against the codebase it describes. Read-only on the code:
> verify by reading, grepping and running read-only queries — never write or execute code to settle a
> claim, and never edit anything except the plan file named below.
>
> - **Plan to harden:** `<docs/plans/<cleanup-name>/<nn>-<slug>.md>`
> - **Roadmap (the spec the plan argues from):** `<docs/plans/<cleanup-name>/README.md>`
> - **Repo root:** `<absolute path to the repo>`
> - **Mode:** fix (default) — apply the fixes to the plan file and re-review until a round produces
>   none. Use report mode only if the caller passed `--no-fix`.
>
> Run the `harden-plan` skill against the plan path above. Verify every claim the plan makes — file
> paths, symbols, line ranges, metrics, ordering assumptions — and check the collateral damage it does
> not mention: callers the plan forgets, tests it would break, decisions it silently makes. Then run
> its closing structural sweep for ambiguity and missing contracts.
>
> Two constraints specific to this run:
>
> 1. The plan's tasks cite finding ids from the scan. Do not renumber or drop an id: the roadmap's
>    index and the report cite them.
> 2. If a fix needs a product decision the code cannot settle, do not invent one. Leave the
>    conservative default in place, state the decision and its flip condition in the plan, and list it
>    in your result so it can be raised with the user.
>
> Return: the mode you ran, how many issues you fixed, what you left unresolved, any decision that
> needs a human, and the plan's own end-state check (line counts, duplication counts, grep results)
> if the plan defines one.

## Collecting results

One result per plan, recorded in the roadmap's plan table and in the final report:

| plan | mode | fixed | unresolved | needs a decision |
|---|---|---|---|---|
| `01-<slug>.md` | fix | <n> | <n> | <one line, or —> |

Route every "needs a decision" row to the user with the default that is currently in force. A
hardening sub-agent that reports an unresolved *blocking* issue (a plan step that cannot be executed
as written) is a reason to re-dispatch that one plan after the fix, not to harden it again by hand.

## Concurrency

- Dispatch all plans that do not depend on each other in one batch, then the dependent ones as their
  prerequisites' results arrive.
- Plans that rewrite the same file may still be hardened concurrently: hardening edits plan files,
  not source. The same-file ordering constraint belongs in the roadmap's waves.
- If the agent cannot dispatch sub-agents, harden the plans inline, one at a time: finish a plan,
  write its row into the roadmap table, then start the next. Do not interleave two plans — the
  ordering plus the written result is what replaces the isolation a sub-agent would have given.
