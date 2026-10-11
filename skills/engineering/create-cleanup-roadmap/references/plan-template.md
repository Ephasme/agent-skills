# Plan template

One file per plan: `docs/plans/<cleanup-name>/<nn>-<slug>.md`. The skeleton below is the shape that
survives hardening — header, global constraints, one task per finding, plan-done checklist.

````markdown
# <nn> — <Title> Implementation Plan

> **For the implementing agent:** Execute one task at a time. Tick each checkbox
> (`- [ ]` → `- [x]`) as you finish a step, and stop to ask if any step is unclear —
> never guess.

**Goal:** <the workstream's outcome in one sentence.>

**Architecture:** <the shape of the change: extract method, move a module, narrow a mutable scope,
extract a collaborator. State the pattern once; the tasks do not re-argue it.>

**Tech Stack:** <only what these tasks touch.>

**Spec:** [README](README.md) — findings `<id>`, `<id>`, `<id>`. <Any finding owned by another plan,
or subsumed by one, is named with the plan that owns it.>

## Global Constraints

- <The repo commands that apply here, copied from the roadmap's Global Constraints, plus anything
  specific to this workstream.>
- One commit per task, Conventional Commits.
- **Non-breaking:** <what must not change for this workstream — signatures, procedure names, status
  codes, persisted keys.>

---

### Task <n.m>: <what it does> (<finding id>)

**Files:**
- Modify: `<path>:<line-range>`
- Create: `<path>`
- Test: `<path>` (existing, or create if absent)

**Interfaces:**
- Consumes: <exact signature or symbol this task uses from earlier work.>
- Produces: <exact names, parameters and return types later tasks rely on. A task is read on its own,
  so this block is how an implementer learns the neighbouring names.>

**Behaviour change:** <required line when the task is not behaviour-preserving: what changes, and for
whom. Omit the line entirely when behaviour is preserved.>

- [ ] **Step 1: <one action>**

```<lang>
<the actual content: the failing test, the command, the code to add. No prose describing it.>
```

- [ ] **Step 2: Run it and confirm the expected failure / result**

Run: `<exact command>`
Expected: <FAIL with X | PASS>

- [ ] **Step 3: <one action — the minimal change>**

- [ ] **Step 4: Verify**

```bash
<lint + focused test + suite>
```

- [ ] **Step 5: Commit**

```bash
git add <paths> && git commit -m "<type>(<scope>): <message>"
```

---

## Plan done

- [ ] All <n> tasks committed.
- [ ] Lint, unit tests and type-check green.
- [ ] <The plan's own measurable end state: line counts, duplication counts, grep results — whatever
      proves the workstream finished.>
````

## Notes on filling it

- **Steps are one action each** and each code step carries its actual content — a test, a command, a
  signature. "Add appropriate handling" is a plan failure; write what to add.
- **Verification commands come from the repo.** Read the manifests and configs; never write a test
  command from memory, and never promise a suite the repo does not have.
- **An extraction task states its target symbols and line ranges**, not the rewritten body: the
  implementer reads the code, and a plan that inlines a 2000-line function is not a plan.
- **A task that cannot be made non-breaking** keeps the current behaviour and adds a named constant,
  a doc comment and a decision row in the roadmap — instead of quietly changing the wire contract.
- **A task that depends on another plan** says so in its Interfaces block and in the plan header, and
  the roadmap's wave diagram carries the same edge.
