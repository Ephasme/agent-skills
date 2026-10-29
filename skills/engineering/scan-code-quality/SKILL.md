---
name: scan-code-quality
description: >-
  Scans a codebase for structural quality issues (architecture incoherence,
  design-principle violations, dead code, excessive complexity, unclear naming, hidden
  state) and produces an evidence-backed, severity-ranked report with concrete,
  non-breaking refactor suggestions. Detects the stack and adds that stack's current,
  sourced rules as extra lenses where a stack pack exists (Swift/iOS, React). Each
  aspect gets its own reviewer on a capable model; a cheaper checker verifies and ranks
  every finding (--find-model, --check-model). Use whenever the user asks for a code
  review, code audit, code quality assessment, tech-debt analysis, refactoring
  preparation, code-smell detection, maintainability or architecture review — including
  casual phrasings like "look over my repo", "where's the worst code in this codebase",
  "is this code any good", "what should I clean up first", or "check this module before I
  ship it". Applies to any language or framework.
---

# Scan code quality

Act as the **orchestrator** of a senior code-review team. You don't read every file yourself — you scope the work, fan it out to specialist reviewers (one per quality aspect), then route their findings through a cheaper checker that verifies and ranks each one. You assemble the survivors into a single evidence-backed report.

Splitting the review this way keeps each reviewer focused on one lens (so it goes deep instead of skimming six concerns at once), runs the lenses in parallel, and spends the expensive model only on *finding* — the mechanical job of *verifying* a concrete claim and scoring its priority is well within a small, fast model's reach, so it runs there.

**Parallelism is an optimisation, not a requirement.** If this agent can dispatch sub-agents, give each reviewer and each checker its own; that is what makes the isolation real and the run fast. If it cannot, work the same list yourself — one category at a time, writing each category's findings to a file before starting the next, then a separate verification pass over the collected findings. Never drop a category, and never merge the find and check passes into one read: the check exists to be an independent look at the cited code.

## When to use

- Code review or quality audit
- Tech debt assessment or refactoring preparation
- Onboarding review to understand codebase health
- Code smell detection before a release

## Options

Read these from the invocation (e.g. `--find-model <mid-tier> --check-model <cheap> --depth thorough src/`). If absent, use the default and state the resolved value at the top of the report.

| Option | Default | Meaning |
| --- | --- | --- |
| `--find-model` | mid-tier: a strong general model, not the largest one available | Model for the per-aspect reviewers (the find phase). |
| `--check-model` | cheapest: the smallest, fastest model available | Model for the verification and ranking pass (the check phase). |
| `--depth` | `thorough` | `quick` = top findings only (each reviewer returns at most its 8 strongest), one checker batch; `thorough` = full catalog, per-finding verification. |
| `--focus` | all categories | Comma-separated subset of the categories, by the names in the [Detection Categories](#detection-categories) list or the lens ids (`swift-concurrency`, `react-core`, …) in the [Stack packs](#stack-packs) table, matched case-insensitively — only those reviewers run. A name that matches nothing is an error to report, not an empty scan. |
| `--stack` | auto-detected | Force (`--stack swift-ios`, `--stack react`, comma-separated) or disable (`--stack none`) the stack packs. |
| target paths | repo root | Positional args: directories/files to scan. |
| `--exclude` | vendor, generated, build outputs, lockfiles | Paths to skip. |

Model values pass through verbatim to whatever model selector this agent exposes — an alias or a full model id, whichever it accepts. If it exposes none, ignore both flags and say so in the report's config line; the phases still run, just on one model. The orchestrator itself always runs on the session model.

The tiers matter more than the names: **finding** structural problems needs reasoning, **checking** a concrete claim against cited code does not. Sending both to the same large model wastes most of the run's cost on the cheaper half of the work.

## Architecture

```
orchestrator (this session)
  │  1. scope + build a shared context brief
  ├──► find phase  (parallel, model = --find-model) ───────────────┐
  │      reviewer: architecture coherence                          │
  │      reviewer: design principle adherence                      │  one subagent
  │      reviewer: dead code & unused artifacts                    │  per in-scope
  │      reviewer: appropriate complexity                          │  category
  │      reviewer: code clarity                                    │
  │      reviewer: state management                                │
  │      reviewer: one per stack lens, if a pack matched           │
  │  2. collect raw findings, assign stable ids                ◄───┘
  ├──► check phase (parallel, model = --check-model) ──────────────┐
  │      checker: re-read cited code, confirm/refute,              │  verify + rank
  │               apply counter-signals, score priority           │  every finding
  │  3. keep confirmed findings, sort by priority              ◄───┘
  └──► 4. synthesize the report
```

## Workflow

1. **Scope.** Resolve target paths; identify languages, frameworks, layering, and project conventions from config files and directory layout. Apply exclusions. Capture this once as a short **context brief** (languages, frameworks, target paths, exclusions, notable layering) — you'll hand the same brief to every find subagent so none of them has to re-derive it.

   **Detect the stack** against the [Stack packs](#stack-packs) table. A pack applies when its detection signals hold for the target paths, not just somewhere in the repo. Record in the brief which packs matched and the toolchain facts their rules depend on, **per target** where they differ (language version and mode, default isolation, minimum OS, UI framework): rules apply per target, and a repo often mixes an app target with extensions and packages on different settings. No pack matched → generic categories only; say so in the config line.

2. **Find phase — dispatch one reviewer subagent per in-scope category, all in a single parallel batch**, each with `model = --find-model`. The categories are the six generic ones plus every lens of every matched pack. Give each subagent: the context brief, the name of its single category, the reference file and section to read (generic categories: their section of [references/generic.md](references/generic.md); a stack lens: its whole pack file), and the **find output contract** below. Use the prompt template in the next section. A reviewer that goes wide and shallow defeats the purpose — each one owns exactly one lens.

   Generic reviewers on a matched stack also apply the pack's idiom: a "god object" in SwiftUI is a screen-wide view model, not a 20-method class. Tell them which pack matched; they may read it but report only their own category.

   **Overlap.** One defect, one finding: lenses often see the same code — shared mutable state is both "Swift concurrency" and "state management"; server data copied into `useState` by an Effect is both `react-core` and `react-architecture`. A stack lens beats a generic category when one of its rules names the construct; between two stack lenses, the one whose rule is about the root cause wins (the cache, not the Effect that copies from it). At collect, merge findings whose location overlaps and whose pattern names the same mechanism, keep the owner's, and list the others under it.

3. **Collect.** Gather every reviewer's JSON output, concatenate, and assign each finding a stable `id` (e.g. `arch-1`, `complexity-3`). Drop exact duplicates (same location + pattern) and merge overlaps per the rule above.

4. **Check phase — verify and rank every finding** with `model = --check-model`. Dispatch checker subagents in parallel using the **check prompt template** below. Each checker independently re-reads the cited code and decides whether the finding is real, applies the counter-signals, adjusts severity, and assigns a 0–100 priority score. In `thorough` depth give each finding (or a small batch) its own checker for genuine independent verification; in `quick` depth batch all findings of a category into one checker. Discard `refuted` findings (surface them in "considered but not flagged"); keep `confirmed` and flag `uncertain`.

5. **Report.** Sort the surviving findings by `priority_score` descending (ties broken by severity). Emit the report structure below. Lead with the resolved config (target, depth, focus, find-model, check-model) so the run is reproducible.

## Find subagent — prompt template

Fill the placeholders and dispatch with `model = --find-model`, one per category:

> You are a senior code reviewer auditing code for **ONE** quality aspect: **{CATEGORY_NAME}**. Ignore every other aspect — other reviewers cover those.
>
> Context brief: {languages, frameworks, target paths, exclusions, layering notes}
>
> Read {the **{CATEGORY_NAME}** section of `{abs path to references/generic.md}` | the whole of `{abs path to the pack file}`} for the detection signals, thresholds, and refactor recipes for this aspect. Use them — don't rely on memory. Each pack rule's **Since** names the version it needs. If the project's version is older, the rule's fix may not exist there: report the defect when the problem itself exists on that version, give a refactor that works on that version, and mention the newer fix only as the upgrade path. Drop a rule entirely when its subject does not exist on that version (an API, a router, a compiler). Scan only the target paths.
>
> For every issue with **concrete evidence** (file path, symbol, a metric/count, or a specific construct), emit a finding. If you cannot point to evidence, do not emit it — unsubstantiated flags waste the reviewer's time. Respect the project's existing conventions; refactor directions must be non-breaking and behavior-preserving.
>
> Return **only** a JSON array (no prose), each element with these fields:
> `{ "category", "pattern", "location", "evidence", "impact", "refactor_direction", "severity" }`
> where `severity` ∈ `high|medium|low` per the rubric I gave you. Return `[]` if you find nothing.

## Check subagent — prompt template

Fill with the collected findings and dispatch with `model = --check-model`:

> You are an adversarial verifier and triager. For each candidate finding below, independently re-read the cited code and judge whether it is a **real** defect — do not trust the finding's own claims.
>
> Findings: {JSON array of findings, each including its `id`}
>
> For each finding decide:
> - **verdict**: `confirmed` (evidence holds and it's a genuine defect), `refuted` (evidence doesn't hold, the cited code differs, or a counter-signal applies), or `uncertain` (can't tell from the cited location). Default to `refuted` when evidence is thin and you can't substantiate it.
> - **confidence**: 0.0–1.0.
> - **adjusted_severity**: `high|medium|low` (you may overrule the reviewer's severity).
> - **priority_score**: 0–100 — rank by **severity × blast radius × fix-leverage**: how bad it is if left, how many files/consumers/paths it touches, and how much improvement a non-breaking fix buys per unit of effort. A high-severity issue confined to one dead file outranks nothing; a medium issue rippling across the hot path outranks an isolated high.
> - **rationale**: one or two sentences, citing what you saw in the code.
>
> Counter-signals that should push a finding to `refuted`: proven reuse across 3+ independent consumers; a compliance/regulatory mandate; an actively-used extension point; intentional AHA duplication (cheaper than the wrong abstraction); for a stack-lens finding, the rule's own **Counter-signals**, a subject that does not exist on the project's version, or a refactor that needs a newer version than the project runs with no alternative given.
>
> Return **only** a JSON array, each element: `{ "id", "verdict", "confidence", "adjusted_severity", "priority_score", "rationale" }`.

## Detection Categories

Listed in default priority order. Each describes what healthy code looks like; deviations are findings. Pass exactly one to each find subagent.

1. **Architecture coherence** — each module has a clear boundary and single purpose; dependencies flow in one direction; changes to one feature stay within its boundary.
2. **Design principle adherence** — code follows SOLID, DRY, YAGNI, KISS; abstractions exist only for proven, current needs; each class has one reason to change.
3. **Dead code and unused artifacts** — every exported symbol, file, branch, and parameter is reachable and exercised by current code paths.
4. **Appropriate complexity** — functions have low branching (CC ≤ 15), shallow nesting (≤ 3 levels), and few parameters (≤ 4); indirection layers are justified by reuse.
5. **Code clarity** — names reveal intent; constants replace magic values; control flow reads linearly; terminology is consistent across the codebase.
6. **State management** — dependencies are passed explicitly; mutable scope is as narrow as possible; side effects are visible in signatures.

Each find subagent reads only its matching section of [references/generic.md](references/generic.md) for the specific signals, thresholds, and refactor recipes — that file carries the per-category detail so reviewers don't work from memory.

## Stack packs

A pack adds lenses for one stack: rules that are specific to it or take a specific form there, each with detection signals, the version it applies from, severity, refactor, counter-signals and sources. Pack lenses run after the generic categories in priority order.

| Pack | Detect when | Lenses (one reviewer each) |
| --- | --- | --- |
| `swift-ios` | `*.swift` sources plus an `*.xcodeproj`, `project.yml` (XcodeGen), `Tuist/`, or a `Package.swift` with an `.iOS` platform | `swift-concurrency` — concurrency and data-race safety, [references/swift-concurrency.md](references/swift-concurrency.md); `swift-language` — language and API design, [references/swift-language.md](references/swift-language.md); `swiftui` — state and rendering, only when `import SwiftUI` appears, [references/swiftui.md](references/swiftui.md); `ios-platform` — platform correctness and App Store risk, [references/ios-platform.md](references/ios-platform.md) |
| `react` | `react` in a `package.json` `dependencies` that governs the target paths, plus `*.jsx`/`*.tsx` sources | `react-core` — components, hooks and rendering, [references/react-core.md](references/react-core.md); `react-architecture` — data, state and frameworks, [references/react-architecture.md](references/react-architecture.md); `react-tooling` — TypeScript, tests and build, [references/react-typescript-testing.md](references/react-typescript-testing.md); `web-platform` — performance, accessibility, security, i18n, [references/web-platform.md](references/web-platform.md) |

Each pack file ends with a **Tools** section: compiler flags and analysers that produce evidence. Run one when the environment has it and it settles a finding; a tool's output is evidence, the absence of a tool is not a finding.

**Upgrade debt.** A project several majors behind the pack's baseline loses whole rule families to `Since`. Report that once, as a single finding in the lens that owns the dependency: the versions in use, the pack baseline, and the rules it suppressed. It is a finding, not a rule per suppressed item.

Pack rules are dated. A pack's sources were current when written; before relying on a rule about a release newer than the project's toolchain, confirm it with the project's build settings. When a stack has no pack, the generic categories still cover it; adding a pack is adding a row here and a reference file in the same format.

## Severity Rubric

Both find and check subagents apply this. Pass it into their prompts.

| Level | Criteria |
| --- | --- |
| **High** | Causes or risks runtime failures (crash, data race, data loss), blocks testability, forces changes across 5+ files for a single feature, or — on a stack pack — risks store rejection, a security or privacy breach |
| **Medium** | Increases maintenance cost measurably: duplicated logic in 2+ places, functions with CC > 15, or classes mixing 2+ unrelated concerns |
| **Low** | Friction point that slows comprehension: unclear naming, minor style inconsistency, or single unused parameter |

## Report structure

Use this template:

```
# Code Quality Scan

**Config**: target=… · depth=… · focus=… · stack=… (packs matched, or none) · find-model=… · check-model=…
**Summary**: N findings confirmed (H high / M medium / L low), U uncertain, K refuted in verification.

## Ranked findings
<table: rank | priority | severity | category | location | pattern>

## Findings in detail
<for each confirmed finding, the 7-field template below, highest priority first>

## Needs a human
<uncertain findings: location, the claim, and what would settle it (a runtime check, a product decision, a test)>

## Considered but not flagged
<refuted findings + counter-signalled patterns: location, why it was dismissed>
```

Each detailed finding uses these 7 fields:

1. **Category** — which detection category
2. **Pattern** — specific pattern name (e.g. "god object", "feature envy", "dead export")
3. **Location** — file path + symbol or line range
4. **Evidence** — concrete metric or observation (LOC count, dependency count, CC value, call sites)
5. **Impact** — what this costs (testability, change cost, onboarding friction, runtime risk)
6. **Refactor direction** — one concrete, non-breaking improvement
7. **Severity & priority** — severity level + the checker's priority score and confidence

### Example detailed finding

> **Category**: Architecture coherence
> **Pattern**: God object
> **Location**: `src/core/app_manager.py` :: `AppManager`
> **Evidence**: 34 public methods, 12 injected dependencies, touches 4 distinct domains (auth, billing, notifications, reporting)
> **Impact**: any feature change requires reading 800+ LOC; unit tests need 12 mocked dependencies
> **Refactor direction**: extract domain-specific facades (AuthService, BillingService) that AppManager delegates to
> **Severity & priority**: High · priority 88 · confidence 0.9

## Counter-signals

A detected pattern is acceptable when any of these holds — the checker should refute it, and the orchestrator lists it under "considered but not flagged":

- Proven reuse across 3+ independent consumers
- Compliance or regulatory requirement that mandates the structure
- Extension point that is actively used (not speculative)
- Intentional duplication following the AHA principle (duplication is cheaper than the wrong abstraction)

## Constraints

- **Evidence required.** Findings without concrete evidence (file, symbol, metric, construct) are dropped — first by the reviewer, then again by the checker. Unsubstantiated flags erode trust.
- **Verification is independent.** The checker must re-read the cited code rather than trust the reviewer's claim; that second look is the whole point of the check phase and the reason it can run on a smaller model.
- **Respect existing conventions.** Match the project's naming, layering, and idioms in refactor suggestions — imposed style changes create friction.
- **Non-breaking refactors only.** Each refactor direction must preserve current behavior. Flag sweeping rewrites as a separate, explicit recommendation rather than embedding them as a "refactor direction".

## References

- Robert C. Martin, *Clean Code* (2008) and SOLID principles (2000)
- Martin Fowler, *Refactoring* 2nd ed. (2018) — code smell catalog
- Sandi Metz, "duplication is better than the wrong abstraction" (2016)
- Kent C. Dodds, AHA Programming (2020)
- McCabe cyclomatic complexity (1976); NIST Structured Testing guidance
