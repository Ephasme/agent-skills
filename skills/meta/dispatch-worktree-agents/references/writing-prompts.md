# Writing a task prompt

The agent receiving this prompt runs a fast model in a fresh session, in a worktree, with
nothing but the prompt and the repository. It will spend its first turns finding what you
already found. Give it the map; keep the decisions that are genuinely open as questions it must
put to the user in plan mode.

## Contents

- Layout of `<id>.md`
- What makes a prompt good
- The shared `context.md`
- Mistakes that cost a relaunch

## Layout of `<id>.md`

```markdown
# Task: <imperative title>

<One paragraph: what to build and why, in the user's terms. Quote the user's own words when
they state a requirement precisely — "columns do not stretch" is a spec, not a style.>

## Scope
- In scope: <files, directories, screens, endpoints — by path>
- Out of scope: <what a sibling owns, what must stay untouched>

## Current state
<What exists today that this task changes: the functions, schemas, routes and their files.
Enough that the agent reads them instead of searching for them.>

## Decisions to make in the plan
<The real design choices, each with the options you see. The ones only the user can make
say so: "ask the user".>

## Requirements
<Observable behaviour, edge cases, limits. Precise over complete.>

## Invariants
<What must keep working, and the existing tests that guard it.>

## Acceptance
<The scenarios that prove it, runnable: pages to drive, requests to send, commands to run.>
```

Drop a section that has nothing in it. `herd.py` adds the sibling list, worktree and mode,
plan requirements, shared context and done protocol after this body — never restate them.

## What makes a prompt good

- **Paths and symbols, not descriptions.** `useFilteredList` in
  `apps/web/src/components/filters/use-filtered-list.ts` beats "the list hook". Verify every
  path you name exists; a wrong path costs more than none.
- **The why behind each constraint.** "Keep sizes in the same state object as visibility — the
  permalink task after you serializes that object" lets the agent make the right call in cases
  you did not foresee. A bare MUST does not.
- **Boundaries with siblings, stated from both sides.** When two tasks run in parallel over
  the same area, each prompt says what the other owns: "a sibling adds resizing on
  `column-resize`; keep your diff to ordering and do not restyle header cells".
- **Seams for later tasks, not their work.** Tell a foundation task what its successors will
  need ("design the column state so ordering and sizing drop in") and that it must not build
  them.
- **Version-sensitive APIs flagged.** When a library's current major differs from what a model
  likely remembers, say so and point at the docs or `npm view <pkg> dist-tags`.
- **Open questions routed to the user.** Anything that changes a product contract (privacy,
  sharing, URL compatibility, data migration) is a plan-mode question, not the agent's call.

## The shared `context.md`

For rules every agent in the run needs and the repository does not already state in its own
agent-instructions file. Typical content, when it applies:

- **Isolation on a shared machine.** Several agents run the project's dev servers and tests at
  once: give each its own database (`{{SLUG}}` in a name), tell them how to move ports, and
  that a port or process they did not start belongs to a sibling and must not be killed.
- **Destructive commands to avoid** — anything that resets a shared volume or database.
- **How to verify** — the project's check command, how to run the app, test credentials.

Read the repository's own `AGENTS.md`/`CLAUDE.md` first and point to it rather than copying
it; the agent loads it anyway.

## Mistakes that cost a relaunch

- A task id that collides with an existing branch prefix (`lists` blocks `lists/x`) — the
  worktree cannot be created. `herd.py check` catches it.
- A prompt that assumes a sibling's work exists when the sibling runs in parallel.
- Acceptance that cannot be exercised ("works well") — the agent then claims done on a
  typecheck.
- Asking for the done marker before the commit — dependants start from an unfinished branch.
  The appended protocol already orders this; do not contradict it.
