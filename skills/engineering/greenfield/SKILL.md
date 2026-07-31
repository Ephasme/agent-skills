---
name: greenfield
description: >-
  Converts one or more documents into a "greenfield" version describing only the
  current state — as if the system were freshly designed with no past — by stripping
  every kind of legacy content: history and evolution narratives, decision records and
  ADRs, deprecation and migration notes, embedded changelogs and release notes,
  rejected alternatives, back-compat sections, and dated commentary. Nothing is deleted
  by default: each removed passage is preserved verbatim, with its original location,
  in a sibling {name}.changelog.md; --no-changelog makes the trim destructive instead.
  Use whenever the user says "greenfield this", "make this doc read fresh", "strip the
  history / legacy / ADRs / decision records", "remove the migration and deprecation
  notes", "clean this up for handoff", or "I want only the current state, no baggage".
  Handles one document directly and many documents — a list, a glob, or a directory —
  one at a time, in parallel where possible.
---

# Greenfield

Take a document that has accumulated cruft over time — design docs, specs, READMEs,
architecture notes carrying history, decisions, deprecations, migrations — and
produce a **greenfield** version that reads as if written today by someone who never
knew the old system, describing only how things currently work.

**The core invariant: nothing is lost.** This is not deletion. It is *separation*.
Every passage that doesn't belong in a fresh document is moved, verbatim, into a
changelog file. The greenfield doc holds the present; the changelog holds everything
that was trimmed.

## Mode: `--no-changelog`

Everything below this section is written in the **default** mode's voice. The
`--no-changelog` flag changes exactly one variable — **the fate of the trimmed spans** —
and this section is the only place that variable is defined. Classification, the keep/trim
test, excise-don't-rewrite, and seam-healing are identical in both modes.

|  | **Default** | **`--no-changelog`** |
|---|---|---|
| Trimmed spans | moved verbatim into `{name}.changelog.md` | **discarded** — written nowhere |
| Outputs per document | greenfield doc + changelog | greenfield doc only |
| Flags (dangling refs, ambiguous calls) | the changelog's `### Flags` section | the final report — the only record that survives |
| Report closes with | trimmed content lives in the `.changelog.md` files; originals reconstructable | trimmed content was discarded; this run cannot reconstruct it |
| Recoverable | yes, from the changelog | only from version control |

**Under `--no-changelog`, every changelog instruction below is void.** The
Preserve-verbatim principle, step 7 of the per-document procedure, and the Output
contract's changelog rules simply do not execute. Those sections are **not** re-qualified
at each site — this section is the override, and the table above is what they resolve to.

Two things the flag adds rather than removes:

- **Bias harder toward keeping.** "When unsure, keep and flag" is merely tidy when the
  changelog can hand the content back; under the flag it is the only thing standing
  between an over-trim and a permanently wrong document.
- **Announce, then check, before writing.** Open the run with "running with
  `--no-changelog`: trimmed content will not be saved". Since the in-place default leaves
  version control as the only recovery path, confirm the targets are tracked and clean in
  git first; if they aren't, say so and get an explicit go-ahead. (`--no-changelog`
  writing to `{name}.greenfield.md` is the milder pairing — the source survives intact.)

The mode applies to the whole run: every document, every sub-agent, the same mode.

## Operating principles (these are the whole point)

- **Two outputs, never destruction.** Each input yields a greenfield document
  (current state only) **and** a `{name}.changelog.md` (everything removed, verbatim,
  located). If you would delete something, you move it instead.
- **Excise, don't rewrite.** Produce the greenfield doc by *deleting the legacy
  spans* from the original — not by regenerating it from understanding. Surviving
  prose must stay byte-for-byte identical. Rewriting risks paraphrasing away correct
  current content and silently altering meaning; excision cannot.
- **Preserve verbatim.** Removed passages are copied into the changelog exactly as
  written, with enough location context to put them back. The pair (greenfield +
  changelog) should let a reader reconstruct the original.
- **Present tense is the test.** A greenfield doc states what *is* and how things
  *currently* work (including present-tense rationale: "uses event sourcing to
  enable audit replay"). Anything that only makes sense as a reference to the *past*,
  a *removed* thing, a *future removal*, or a *comparison to what came before* is
  legacy and gets trimmed.
- **Correctness beats thoroughness.** The greenfield doc must remain a complete and
  correct description of the current system. When unsure whether a passage is "legacy
  framing" or "load-bearing current detail," keep it in the greenfield doc and add a
  flag — under-trimming leaves mild cruft, over-trimming makes the doc wrong. (By default
  the trimmed content is recoverable from the changelog regardless.)
- **One sub-agent per document.** Multiple documents are processed in parallel, one
  agent each, isolated to its single file.

## Inputs & resolution

Resolve the set of documents to process:

- Accept **explicit paths**, a **glob** (`docs/**/*.md`), or a **directory** (process
  the text documents in it).
- **Exclude `*.changelog.md`** from the input set, always — never re-ingest this
  skill's own prior output. This is what makes re-runs idempotent.
- **Exclude binary / non-text** files. This skill operates on text/markdown documents.
- If the input was a glob or directory (not an explicit list), **list the resolved
  files and confirm the set with the user** before processing — a wrong glob is the
  easy way to mangle the wrong files.

Then branch on the count: **1 → run the per-document procedure directly. N → fan out**
(see Orchestration).

## What counts as legacy (trim these)

| Category | Signals | Trim |
|---|---|---|
| **History / evolution** | "originally", "previously", "used to", "in the past", "formerly known as", version-evolution narratives | the historical narrative; keep only the resulting present-tense fact |
| **Decision records / ADRs** | "Decision:", Context/Decision/Consequences blocks, "we chose X over Y", "options considered", "trade-off analysis" framed as a past choice | the whole record; if it carries rationale still true today, restate that rationale in present tense and keep *that* one line |
| **Deprecation** | "deprecated", "do not use", "will be removed", "use X instead" | the deprecated item itself and its notice — in a greenfield system it simply doesn't exist (watch for surviving references to it) |
| **Migration / upgrade** | "upgrading from", "migration guide", "breaking changes", "if you're on v1" | entirely |
| **Embedded changelog / release notes** | "## Changelog", "## Release Notes", version-dated entries | entirely |
| **Legacy / back-compat** | "legacy", "backwards compatibility", "for compatibility with older", "transitional" | entirely |
| **Rejected / abandoned alternatives** | "we considered but decided against", "this was tried and didn't work", "rejected because" | entirely |
| **Dated / temporal commentary** | "as of 2022", dated author notes, "currently being phased out", stale historical TODO/FIXME with dates | entirely; if a stale TODO describes a real current gap, keep it but strip the dated framing |
| **Superseded sections** | "old approach", "previous design", "v1 architecture" | entirely |

## What to keep (do not trim)

- Current architecture, behavior, data models, APIs, contracts, constraints, invariants.
- **Present-tense rationale** for the current design ("X is used to achieve Y").
- Setup, usage, configuration, and operational instructions for the current system.
- **Current** limitations and known issues that still apply — these are present-state,
  not history. Strip only the version-historical framing around them ("known issue:
  in versions before 2.3…" → keep the issue, drop the version clause if no longer true).

## The keep/trim test

Apply to every passage:

> Would this sentence appear in a document written **today** by someone who never knew
> the old system, describing only how things **currently** work?
>
> - **Yes** → keep it (untouched).
> - **No — it only makes sense as a reference to the past, a removed thing, a future
>   removal, or a comparison to what was** → trim it to the changelog.
> - **Unsure** → keep it in the greenfield doc and add a flag for review.

## Per-document procedure

Run this for **exactly one** document. (Sub-agents run this; for a single input you run
it directly.)

1. **Read the whole document** first. Classification needs full context — the same
   sentence can be current fact or historical aside depending on its section.
2. **Classify every passage** as keep or trim, tagging each trim with a category from
   the taxonomy.
3. **Excise the trim-spans** from a working copy of the file. Do not touch surviving
   content. The greenfield doc is the original *minus* the legacy spans — not a rewrite.
4. **Heal the seams.** Only these edits are permitted beyond deletion:
   - remove a heading/section left empty by its content's removal;
   - **fix or flag** cross-references now dangling (e.g. "see the migration section"
     pointing at removed text) — repoint if a valid present-tense target exists,
     otherwise remove the pointer and flag it;
   - collapse runs of >1 consecutive blank line introduced by deletions;
   - repair list numbering / markdown structure broken by a removal.
   No rewriting, condensing, or "improving" of surviving prose.
5. **Stand-alone pass.** Confirm the greenfield doc reads as a fresh document: no
   orphaned "as mentioned above", "as we'll see", or "unlike the old…" pointing at
   content that's no longer there.
6. **Write the greenfield doc to the original path** (in place — see Output contract for
   the non-destructive option).
7. **Write / append the changelog** (format below).
8. **If nothing was trimmed:** leave the source file unchanged, do **not** create a
   changelog, and report `already greenfield`.

## Output contract

**Greenfield document** — written to the original path, in place. Preserve the original
format and heading style. Put **no** editorial annotations inside it (flags go in the
changelog, not the doc).

**Changelog path** — same directory, the file's final extension replaced with
`.changelog.md` (append `.changelog.md` if there is no extension):

```
docs/architecture.md   →  docs/architecture.changelog.md
notes.v2.md            →  notes.v2.changelog.md
README                 →  README.changelog.md
```

**Changelog format** — a record of removed content, append-only across runs:

```markdown
# {name} — trimmed legacy content

Content removed from `{original path}` during greenfielding. The greenfield document
holds the current state; this file holds everything trimmed from it, verbatim, so the
original can be reconstructed.

## Greenfielded YYYY-MM-DD

### History / evolution

**From:** `<nearest heading>` — <brief locator: the line it followed / its position>
> <removed text, verbatim>

_Why:_ <one line, optional>

### Decision records / ADRs

**From:** `<nearest heading>` — <locator>
> <removed text, verbatim>

…(one subsection per category that had removals)…

### Flags

- <dangling reference removed at `<heading>`: "<text>">
- <ambiguous keep/trim kept in greenfield at `<heading>`: "<text>">
```

Rules for the changelog:

- **Group by category**, verbatim text in blockquotes (or fenced blocks if the content
  is itself markdown/code), each with its **original location** (nearest heading plus a
  short locator) so re-insertion is possible.
- **Append, never overwrite.** On a re-run that trims new content, add a new
  `## Greenfielded <date>` section above or below prior ones — do not rewrite history.
- End each run section with **Flags**: dangling references that were removed, and any
  ambiguous calls left in the greenfield doc for review.

## Orchestration: single vs many

- **One document** → run the **Per-document procedure** directly and report.
- **Many documents** → spawn **one sub-agent per document, in parallel**; where
  sub-agents aren't available, process the documents one at a time in this context,
  finishing and writing out each before opening the next. The isolation is what
  matters, not the concurrency. Each
  sub-agent owns exactly one file and must not read or write any other input file
  (isolation keeps runs independent and prevents cross-contamination). **Pass the run's
  mode to every sub-agent** — a sub-agent cannot infer it, and one that assumes the
  default either writes a changelog the user asked not to have or, the other way, discards
  content irrecoverably. Each returns a **structured result** so you can aggregate:
  - greenfield path,
  - changelog path (or `none`),
  - count of items trimmed **by category**,
  - flags (dangling refs, ambiguous calls),
  - `already greenfield` if applicable.

  If a sub-agent fails or reports an oversized/ambiguous document, re-dispatch or
  surface it — do not let one failure silently drop a document from the batch.

### Sub-agent prompt (one per document; fill `<FILE>`, `<SKILL_PATH>`, `<MODE>`)

Fill `<MODE>` with `default` or `--no-changelog`, matching the run. Every sub-agent in a
batch gets the same one.

```
You are converting ONE document to a greenfield version as part of a batch.

Read the skill at <SKILL_PATH> and follow its "Mode", "Per-document procedure" and
"Output contract" sections for EXACTLY this one file — do not touch any other file:

  <FILE>

Run mode: <MODE>

Non-negotiables (restated so you don't need to re-derive them):
- The greenfield doc holds the current state only. What happens to the spans you trim is
  decided solely by the run mode above, as defined in the skill's "Mode" section — read
  it and follow it exactly. Never substitute the default for a mode that says otherwise.
- EXCISE, don't rewrite: the greenfield doc is the original minus the legacy spans;
  surviving prose stays byte-for-byte. The only edits beyond deletion are healing
  seams (drop emptied headings, fix/flag dangling refs, collapse blank lines, repair
  broken lists).
- Trim: history/evolution, decision records & ADRs, deprecation, migration/upgrade,
  embedded changelogs/release notes, legacy/back-compat, rejected alternatives, dated
  commentary, superseded sections. Keep: current architecture/behavior/APIs/data
  models/constraints, present-tense rationale, current usage/ops, still-valid
  limitations. When unsure, KEEP in the greenfield doc and flag it.
- Write the greenfield doc in place at <FILE>.
- If nothing was trimmed: leave <FILE> unchanged, create no changelog.

Report back ONLY this structured result:
- greenfield_path
- changelog_path (or "none")
- trimmed_by_category: {category: count, ...}
- flags: [ ... ]
- status: "done" | "already_greenfield"
```

## Final report

After the single run or the fan-out, report to the user, per document:
- greenfield path and changelog path,
- items trimmed by category,
- any flags,
- documents that were `already greenfield`.

Close with a one-line batch summary and the mode's closing line (see Mode).

## Guardrails & edge cases

- **In-place is the default; offer the non-destructive variant.** By default the
  greenfield doc replaces the original (the changelog naming is symmetric to it, and
  excision-not-rewrite plus the verbatim changelog make the edit recoverable). If the
  user wants originals untouched, write the greenfield version to `{name}.greenfield.md`
  instead and leave the source alone — keep the same changelog rules.
- **Idempotent.** Re-running the skill on an already-greenfield doc trims nothing,
  changes nothing, and reports `already greenfield`. `*.changelog.md` files are always
  excluded from inputs.
- **Don't process binary/non-text** files; skip and note them.
- **Large documents** still get exactly one sub-agent — that agent owns the whole file
  end to end rather than splitting it (splitting a single doc across agents fractures
  classification context).
- **Watch surviving references to removed things.** Removing a deprecated API or a
  superseded section can orphan references elsewhere; the heal/stand-alone passes exist
  to catch these — repoint or flag, never leave a dangling pointer in the greenfield doc.
