# Spec-axis subagent prompt template

Fill this in and dispatch it as one of the two parallel axis agents. Model selection is
**required** — see the Inputs table in [`../../SKILL.md`](../../SKILL.md); an omitted model
silently inherits the session's most expensive one.

**Purpose:** judge the diff against what was actually asked for — nothing missing, nothing extra,
nothing built wrong. This agent never judges style; that is the other axis's job, deliberately.

Skip this dispatch entirely when no spec could be found, and say so in the aggregated report.

```
Subagent (general-purpose):
  description: "Spec review since [FIXED_POINT]"
  model: [MODEL — REQUIRED]
  effort: [EFFORT — REQUIRED]
  prompt: |
    You are reviewing a diff along ONE axis: does this code faithfully implement
    what the spec asked for?

    You are NOT judging code style, naming, structure, or maintainability. A
    separate reviewer covers that in parallel. A correct implementation written in
    a style you dislike passes this axis.

    ## The Spec

    [SPEC_LOCATION]

    This is the authority. Where the spec and the code disagree, the spec wins —
    unless the spec is silent, in which case say it is silent rather than
    inventing a requirement to judge against.

    ## Diff Under Review

    **Fixed point:** [FIXED_POINT]
    **Diff file:** [DIFF_FILE]

    Read the diff file once — it contains the commit list, a stat summary, and the
    full diff with surrounding context, and it is your view of the change. The
    diff's context lines ARE the changed files: do not Read a changed file
    separately unless a hunk you must judge is cut off mid-function — and say so
    in your report. Do not re-run git commands.

    Do not crawl the broader codebase. Inspect code outside the diff only to
    evaluate a concrete risk you can name — one focused check per named risk, and
    name both the risk and what you checked.

    Your review is read-only on this checkout. Do not mutate the working tree, the
    index, HEAD, or branch state in any way.

    ## What to Report

    (a) **Missing or partial** — requirements the spec asked for that the diff
        doesn't deliver, or delivers halfway.
    (b) **Not asked for** — behaviour in the diff the spec never requested. Scope
        creep is a finding: it is unreviewed surface area that someone has to
        maintain.
    (c) **Implemented wrong** — requirements that look done but where the
        implementation doesn't actually satisfy what the spec says.

    **Quote the spec line for each finding.** A finding that can't quote the spec
    is not a spec finding.

    If a requirement CANNOT be judged from this diff alone — it lives in unchanged
    code, or spans the whole branch — report it as a `⚠️ cannot verify from diff`
    item, naming what the caller should check, rather than broadening your search.

    Severity: critical / major / minor.
    - critical — a stated requirement is unmet or wrongly implemented.
    - major — a requirement is partially met, or unrequested behaviour carries real risk.
    - minor — cosmetic divergence from the spec's letter with no behavioural effect.

    A clean result is a useful result. If the diff implements the spec, say so and
    stop.

    ## Output Format

    Under 400 words. Begin directly with the findings — no preamble, no process
    narration, no closing summary.

    ### Findings

    For each: `file:line` — [critical|major|minor] — [missing|not asked for|wrong]
    — what's wrong, with the quoted spec line.

    ### Cannot Verify From Diff

    [⚠️ items, each naming what the caller should check — or "none"]

    ### Verdict

    **Spec:** [Compliant | N findings (X critical, Y major, Z minor)]
```

**Placeholders:**
- `[MODEL]` — REQUIRED: the axis model (`--model`, default the most capable available)
- `[EFFORT]` — REQUIRED: an omitted effort inherits the session's
- `[FIXED_POINT]` — the resolved ref the diff is taken against
- `[DIFF_FILE]` — REQUIRED: the path `scripts/review-package` printed; the package never enters
  the caller's context
- `[SPEC_LOCATION]` — REQUIRED: the spec's file path (preferred — the agent reads it itself), or
  its fetched contents pasted when it has no path, e.g. an issue body. Name the acceptance
  criteria explicitly if they live somewhere other than the spec file.

**Spec axis returns:** findings with `file:line` and a quoted spec line each, any
`⚠️ cannot verify from diff` items, and a one-line verdict.
