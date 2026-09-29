# Structured task contract

Use one flat task list. Express grouping with `parent` and sequencing with `depends_on`.

## Where the list lives — ask the case, do not assume

This contract defines the **task model**, not the storage. Before writing anything, read the
repository's and the case's own instructions for a declared **task authority**:

- **An external tracker is declared** (a Notion task database, or a Jira project, reached through
  its MCP server): it is the authority. One row per task. Carry the fields below into the
  tracker's own concepts — `title` → name, `status` → state, `priority` → priority, `due` →
  target date, `parent` → parent item, `depends_on` → the tracker's relations — and put whatever
  has no native field (`id`, `due_source`, `evidence`, `file`, `waiting_on`, `notes`) in the item
  description, each on its own labelled line. **Never mirror the tracker into a repo file**: a
  second list is a second truth, and the copy is the one that goes stale.
- **Nothing is declared**: you have no storage, so **create none**. Report the proposed tasks in
  the run output, state that the case declares no task authority, and ask where they should live.
  Writing `tasks.yaml` — or any other task file — on your own initiative is how a repository ends
  up with two task lists and one of them silently rotting. A repo that wants that file says so.

The invariants further down hold either way. Only the storage changes.

## The task model

Rendered as YAML for readability. When a case declares a file store, this is also its literal
shape, and `tasks.schema.json` validates the parsed data — JSON Schema validates YAML after
parsing, because the data model is the same.

```yaml
version: 1
case: <case-slug>
generated: YYYY-MM-DD
horizon: YYYY-MM-DD # or null

tasks:
  - id: stable-kebab-id
    title: "Actionable title"
    status: todo # todo | in_progress | blocked | done | cancelled
    priority: P0 # P0 deadline/money risk; P1 required; P2 normal; P3 optional
    due: YYYY-MM-DD # or null
    due_source: "Primary source and derivation" # or null
    owner: loup # person/role or null
    waiting_on: null # non-empty when blocked
    depends_on: []
    parent: null
    file: "cases/<slug>/<file>#section"
    evidence: "documents/<source>:clause/page/message-id"
    notes: null

analysis:
  cycles: []
  date_conflicts: []
  overdue: []
  unowned_deadlines: []
  external_blocks: []
  critical_path: []
```

## Invariants beyond the schema

1. `case` equals the case directory slug. `generated` is the last successfully verified hardening
   date in the case's declared timezone; it is not an arbitrary regeneration timestamp.
2. Preserve existing task IDs across title/status changes. Never recycle an ID. New IDs are unique
   kebab-case slugs.
3. Every `depends_on` and non-null `parent` references an existing ID; no self-reference exists.
   Detect dependency cycles and parent cycles. Never remove a real edge to clear a cycle.
4. Dependencies may reference done/cancelled tasks to preserve history. Explain a cancelled
   prerequisite's impact in `notes` or `date_conflicts`.
5. Every P0 has a non-null `due` and `due_source`. If money is at risk without a literal deadline,
   derive a defensible action date and explain the derivation; otherwise classify P1.
6. Contractual/dated tasks cite primary evidence and clause/page/message. Store pointers, not copied
   sensitive content. Keep evidence inside established tracked scope.
7. A blocked task has `waiting_on`; other statuses normally set it null.
8. `horizon` comes from a source-backed case deadline or is null. Dates use `YYYY-MM-DD`; interpret
   them in the case timezone unless the source states another zone. Validate real calendar dates
   semantically even when a JSON Schema implementation does not enforce the `date` format.
9. `analysis.cycles`, `overdue`, `unowned_deadlines`, and `critical_path` contain task IDs.
   `date_conflicts` and `external_blocks` use the object shapes enforced by the schema.
10. Synchronize a prose task view only when local instructions define one. The declared task
    authority is the only structured list; where none is declared there is no structured list to
    write. Where a prose view exists, it restates the same items and never adds a parallel
    deadline table of its own.
