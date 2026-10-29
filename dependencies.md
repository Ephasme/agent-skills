# Skill dependencies

Which skill reaches for which other one. Solid arrow: required. Dotted: recommended, or a pointer the
skill still runs without.

```mermaid
flowchart LR
  cbt-expert -.->|loads| cbt
  french-insurance-law-expert -.->|loads| french-insurance-law
  quality-scout -.->|loads| assess-true-quality
  call-cbt-agent -->|dispatches| cbt-expert
  call-french-insurance-law-agent -->|dispatches| french-insurance-law-expert

  assess-true-quality -.->|routes to| call-cbt-agent
  assess-true-quality -.->|routes to| cite-or-refuse
  assess-true-quality -.->|routes to| fact-check-document
  assess-true-quality -.->|routes to| call-french-insurance-law-agent
  cbt -.->|sourcing discipline| cite-or-refuse

  refine-document -->|pass 1| strip-legacy-content
  refine-document -.->|pass 2| cite-or-refuse
  refine-document -.->|pass 2| fact-check-document
  execute-autonomously -->|re-hardens a plan with| harden-plan
```

Every skill here installs on its own: none requires a skill outside this catalog.
