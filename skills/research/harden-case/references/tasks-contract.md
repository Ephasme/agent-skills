# Structured task contract

Use one flat task list. Express grouping with `parent` and sequencing with `depends_on`. Validate the
parsed YAML data against `tasks.schema.json`; JSON Schema validates YAML after parsing because the
data model is the same.

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
10. Synchronize a prose task view only when local instructions define one. Otherwise `tasks.yaml` is
    the structured task authority.
