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
  research -.->|review| refine-document
  research -.->|review| fact-check-document
  execute-autonomously -->|re-hardens a plan with| harden-plan
  feature -->|stage 1| write-plan
  feature -.->|open requirements| brainstorm-design
  feature -->|stage 2| harden-plan
  feature -->|stage 3| execute-plan
  campaign -->|stage 5, per feature| feature
  bugfix -->|stages 1-3| debug-systematically
  do -->|routes to| research
  do -->|routes to| bugfix
  do -->|routes to| feature
  do -->|routes to| campaign
```

Every skill here installs on its own: none requires a skill outside this catalog.
