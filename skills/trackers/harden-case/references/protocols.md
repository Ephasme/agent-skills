# Role protocols

Return valid YAML. Include every key; use `null`, `[]`, or `""` when empty. Checkers, adversaries,
and the tasker never write files. A writer may change only its authorized worklist and returns the
writer report afterward.

## Checker

```yaml
role: facts # facts | consistency | conventions | blindspots | maths | language | greenfield | tasker
status: completed # completed | failed
coverage:
  files_read: []
  sources_opened: []
  omitted_scope: []
findings:
  - id: facts-001
    severity: critical # critical | high | medium | low
    claim: ""
    location: ""
    evidence: ""
    source_path: ""
    calculation: null
    proposed_fix: ""
    question: null
    untouchable: false
    unverifiable: false
failures: []
tasks_yaml: null # tasker only: complete YAML document as a block string; add tasker-* findings
```

## Adversary

```yaml
reviewed_role: facts
status: completed # completed | failed
verdicts:
  - id: facts-001
    verdict: confirmed # confirmed | refuted | unjudged
    source_reopened: true
    severity_adjusted: null
    counterevidence: null
    missing_evidence: null
    fix_correction: null
unjudged: [] # IDs not actually judged; never treat as confirmed
failures: []
```

## Decision packet for non-interactive hosts

```yaml
status: needs_user_decision
case: ""
decisions:
  - id: decision-001
    finding: ""
    options:
      - choice: ""
        consequence: ""
    safe_default: stop_without_editing
completed_read_only_work: []
proposed_next_step: ""
```

## Blocked run

Use this for missing paths, unreadable sources, absent required capabilities, or repository state
that prevents safe progress. It is not a decision packet.

```yaml
status: blocked
case: ""
blockers:
  - code: missing-case-path
    detail: ""
    needed: ""
completed_read_only_work: []
safe_to_resume: true
```

## Writer report

```yaml
status: completed # completed | failed | partial
files_touched: []
sources_reopened: []
generators_run: []
tasks_validation: ""
escalations: []
recoverable_baseline: ""
```
