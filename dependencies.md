# Skill dependencies

Which skill reaches for which other one. Solid arrow: required. Dotted: recommended, or a pointer that
degrade without it.

```mermaid
flowchart LR
  cbt-expert -.->|loads| cbt
  french-insurance-law-expert -.->|loads| french-insurance-law
  quality-scout -.->|loads| assess-true-quality

  assess-true-quality -.->|routes to| cbt
  assess-true-quality -.->|routes to| cite-or-refuse
  assess-true-quality -.->|routes to| fact-check-document
  assess-true-quality -.->|routes to| french-insurance-law
  cbt -.->|sourcing discipline| cite-or-refuse
  harden-case -.->|README contract| sync-case

  create-cleanup-roadmap -->|scans with| scan-code-quality:::external
  create-cleanup-roadmap -->|hardens each plan with| harden-plan:::external
  classDef external stroke-dasharray: 4 3,stroke-width: 1px
```

The two dotted `create-cleanup-roadmap` edges point into the other catalog:

| Skill here | Needs | Lives in |
| --- | --- | --- |
| `create-cleanup-roadmap` | `scan-code-quality`, `harden-plan` | `Les-Sherpas/agent-skills` |

Both catalogs install side by side (`~/.config/skills/sources` names them), and the store is flat, so
those two edges resolve whenever both are installed — the graph is drawn with them marked as external
because a machine with only this catalog will not have them.

Everything else is self-contained: no skill here requires a skill outside this catalog.
