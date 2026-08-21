---
name: refine-document
description: >-
  Rewrites one document — README, AGENTS.md, design note, runbook, spec — so it is
  greenfield (no history, no legacy), factual (every claim verified against a primary source
  or marked, nothing invented), concise (one fact in one place), organized (critical
  information first), and tuned to a declared reader. Takes --target=agent (default), for an
  LLM that reads the document as context, or --target=human; the two produce deliberately
  different documents, each following the measured readability evidence for that reader.
  Everything removed is preserved in a sibling record file. Use when the user asks to clean
  up, tighten, de-cruft, de-fluff, compress, restructure, factualise or "make this readable"
  for a document; when a README has drifted into marketing and history; when an AGENTS.md is
  long, repetitive and ignored; or when a doc must be handed to a reader who was not in the
  room. Rewrites the user's file, so run it on an explicit request about a named document,
  never as unprompted tidying.
---

# Refine Document

Take one document and produce a version that a reader who has no history with the project
can act on: **greenfield, factual, concise, organized, and shaped for the declared reader.**

Four passes, fixed order, then a verification gate. Everything removed is written to a
record file, so a wrong call is recoverable.

## Invocation

```
refine-document <path> [--target=agent|human] [--no-record]
```

| Flag | Default | Effect |
|---|---|---|
| `--target` | `agent` | Which reader the last pass optimizes for. Changes the document, not just the tone — see [Pass 4](#pass-4--organize-for-the-declared-reader). |
| `--no-record` | off | Skip the record file. Removals become unrecoverable except from version control. |

**Before touching the file:**

1. **Confirm the request names this document.** This rewrites the user's file in place.
2. **Confirm the file is tracked and clean in version control.** If it is not, say so and get
   an explicit go-ahead — under `--no-record` that is the only recovery path left.
3. **State the target you are running with** in your first message, including when it is the
   default. A silent default is how a document gets shaped for the wrong reader.
4. **Many documents:** run this procedure once per document, one sub-agent each where
   sub-agents are available, passing the same target and flags to every one. A sub-agent
   owns exactly one file.

## Outputs

| Output | Path | Contents |
|---|---|---|
| Refined document | the original path, in place | current state only, target-shaped |
| Record | `{name}.changelog.md`, same directory | everything removed, verbatim, located — append-only across runs |
| Report | your reply | see [Report](#report) |

## Pass order

Run the passes in this order, as four separate reads of the document. Each one shrinks the
input to the next, and out of order they undo each other — compressing prose that pass 1
was going to delete wastes the work, and organizing before compressing organizes filler.

1. **Greenfield** — remove everything that only makes sense as a reference to the past.
2. **Factual** — every surviving claim is verified, cited, or marked.
3. **Concise** — one fact, one place, shortest form that keeps the fact.
4. **Organize** — critical first, then the target's shape.

## Pass 1 — greenfield

**REQUIRED SUB-SKILL:** use `greenfield` for this pass. It owns the legacy taxonomy, the
excise-don't-rewrite rule, and the `{name}.changelog.md` format this skill also writes into.
Map `--no-record` to its `--no-changelog`.

Where that skill is unavailable, remove: history and evolution narratives, decision records
and ADRs, deprecation notices, migration and upgrade guides, embedded changelogs and release
notes, back-compat sections, rejected alternatives, dated commentary, superseded sections.
Excise the spans; do not rewrite the surviving prose — passes 2-4 will.

**The deprecated-feature rule.** A feature marked deprecated is not automatically legacy.
Apply this test, and record which branch you took:

> Does the feature have a use that is not "supporting the old system"?
>
> - **No** — it exists only for back-compat. Remove the feature and its notice.
> - **Yes** — it is current behaviour. Keep it, drop the removal timeline and the
>   "since v1" framing, and flag it in the record.

## Pass 2 — factual

Every assertion the document makes is a claim, including the ones it inherited. Classify
each one and take the matching action. There is no fifth option.

| Class | Signal | Action |
|---|---|---|
| **Checkable, artifact reachable** | behaviour, flags, defaults, paths, commands, config keys, and you can read the code, the config, or the `--help` | Check it. True: keep. False: correct it. |
| **Checkable, artifact out of reach** | the same claims, with no repo, no binary, and no documentation to check against | Keep the claim exactly as the source states it, **unmarked**, and list it in the report as unchecked. |
| **Externally sourceable** | standards, protocol behaviour, third-party product behaviour, version support | Cite the primary source inline with its date or version. No acceptable source: cut the claim. |
| **Comparative or promotional** | "10x faster", "best-in-class", "blazing", "elegant", "most engineers agree", and any comparison whose other term is not part of the current system ("lighter than Kafka") | Cut it, unless a citable measurement exists — then state the measurement and its source. Keep the surviving fact: "queues jobs with Redis Streams". |
| **Unverifiable and hazardous** | an unchecked claim a reader could act on irrecoverably: data loss, spend, credentials, a destructive command, a security boundary | Keep it, mark it `[unverified]` in the document, and list it in the report. |

**The marker is for hazards, not for provenance.** A document about an artifact you cannot
reach is mostly unchecked claims, and marking each one teaches the reader to skip the marker.
Unchecked provenance belongs in the report and the record; `[unverified]` in the document is
reserved for the claims whose failure the reader cannot undo. If more than a handful of
markers survive into the document, you have classified provenance as hazard — reclassify.

**Never invent a fact the source document did not have.** Not a config location, not a
default, not a file format, not a prerequisite — not even one that is almost certainly true.
An inferred fact stated flatly is indistinguishable from a verified one, and this pass is
the only thing standing between the reader and a confident wrong answer. If the source is
silent, the refined document is silent.

**Never soften an unsourced claim into a vaguer one.** "Roughly 10x faster" rewritten as
"very fast" is the same opinion with less precision. Cite it or cut it.

**Never delete an operational instruction for lack of a source.** Marking beats deleting:
a marked instruction can be checked by someone who knows, a deleted one is gone.

For a document whose claims are mostly external, run `cite-or-refuse` for the sourcing and
`fact-check-document` for a full claim audit before continuing.

## Pass 3 — concise

**One fact, one place.** For each fact, pick the single section where a reader looking for
it will arrive first. State it there, in full. Everywhere else, either delete the restatement
or replace it with a pointer naming that section exactly.

Delete outright:

- Filler openers: "It is worth noting that", "Simply", "Basically", "As you can see".
- Instructions to do what the reader is already doing: "To install, run the install command".
- Restated section titles as first sentences.
- Defensive caveats that change no action.
- Examples that demonstrate the same thing as an earlier example.

Compress:

- More than three items compared across more than two attributes → a table.
- A paragraph that lists parallel things → a list.
- A sentence whose subject is a nominalisation → the verb ("make a determination" → "decide").

**The compression floor.** Stop when removing the next word removes a fact. A shorter
document that lost a fact is a regression, not a win. Word count is a symptom of the work,
never its target.

**The one sanctioned duplication** is the agent target's head-and-tail restatement of the
critical block (pass 4). Every other repetition goes.

## Pass 4 — organize for the declared reader

### Shared: the ordering law

Order by what blocks the reader, not by the history of the subject:

1. **What this is** — one sentence, no preamble.
2. **Prerequisites that block everything else** — the env var without which nothing starts,
   the credential, the required version.
3. **Destructive and irreversible operations** — anything that deletes, overwrites, spends
   money, or cannot be undone. This is placement by consequence, not by topic: it goes near
   the top even when the command is obscure, and it is marked, not merely mentioned.
4. **The main path** — the thing most readers came to do, end to end.
5. **Everything else**, most-used first.
6. **Edge cases, troubleshooting, and reference tables** last.

A summary block belongs at the top when the document has more than about five sections; it
lists the facts a reader needs before they can do anything, not a précis of the prose.

### `--target=agent`

The reader is a model that loads the document as context, often after grepping for one term
and reading only the matched slice. Produce a document with this shape:

1. **A critical block first, and the same block verbatim last.** Prerequisites, destructive
   operations, and hard constraints. Attention to a long context is strongest at its two
   ends and weakest in the middle (Liu et al., TACL 2024) — the middle is where a rule goes
   to be ignored. Head the first copy `## Critical constraints` and the last
   `## Critical constraints (repeat)`: two unique anchors, one identical body. This pair is
   the only near-duplicate heading the document may contain.
2. **Positive phrasing.** State the action to take. Where a prohibition is genuinely needed,
   put the positive alternative in the same sentence: "write to `state/`, not to `/tmp`".
   Models handle negated statements measurably worse than affirmative ones.
3. **One heading, one retrievable unit.** Every heading is unique within the document,
   literal, and made of the words an agent would grep for — apart from the critical-block
   pair above. Its section stands alone: no "as described above", no pronoun whose referent
   is in another section.
4. **Literal identifiers at the point of use.** Full paths, exact command lines, exact
   environment variable names, exact file names — every time, not once with references
   after.
5. **Checkable statements over narrative.** A command, a path, a value, an exit condition. If
   a sentence cannot be checked, it is probably rationale — keep it only where it changes
   what the agent does.
6. **Markdown structure only** — headings, lists, fenced code, small tables. Do not add an
   XML tagging scheme to a Markdown document; reserve JSON or YAML blocks for content that
   is genuinely machine-read data.
7. **Shortest form that keeps every fact.** Input length degrades retrieval on its own, and
   topically adjacent content that answers nothing acts as a distractor — near-miss prose is
   worse than absence.
8. **No contradictions.** Two statements that disagree are worse than neither. Resolve them
   before writing.
9. **A contents list only past ~100 lines**, since the agent may read a slice rather than the
   whole file and otherwise cannot see the scope.

**Acceptance:** an agent that greps one heading and reads only that section acts correctly.

### `--target=human`

The reader scans before reading and reads a minority of the words. Where formatting offers no
cues, that scan degrades into an F-shaped sweep down the left edge — structure is what
prevents it, not what imitates it. Produce a document with this shape:

1. **The point in the first sentence** of the document and of every section. Most important
   content in the first two paragraphs; a reader who stops there has what they came for.
2. **Front-loaded lines.** Every heading, bullet, and paragraph starts with its
   information-carrying words — the first two words of a line get read, the rest get scanned.
3. **Descriptive headings**: "Configure the state directory", never "Overview", "Notes",
   "Details", or "Section 3".
4. **One idea per paragraph**, roughly four sentences at most.
5. **Objective language.** Neutral wording measurably outperforms promotional wording for
   usability; this is a comprehension result, not a style preference.
6. **Tables for comparison, prose for reasoning.** More than three items across more than two
   attributes → table. Connected, causal, or nuanced explanation stays prose — fragmenting
   an argument into bullets loses the links.
7. **Domain vocabulary stays.** Define a term once, inline, at first use. Do not simplify
   technical precision away, and do not rewrite toward a readability-formula score — those
   scores cannot see organization and penalise correct terminology.
8. **A contents list past about two screens or five sections.**

**Acceptance:** a reader can complete the task the document describes using only the
document.

### What must differ between targets

| Decision | `--target=human` | `--target=agent` |
|---|---|---|
| Critical constraints | once, on the first screen, marked | first **and** repeated verbatim last |
| Section independence | sections may build on earlier ones | every section self-contained |
| Cross-references | "see above" is fine | name the exact heading |
| Headings | descriptive and readable | unique, literal, grep-shaped |
| Prohibitions | "don't do X" is fine | "do Y" carries the prohibition |
| Identifiers | introduce once, then shorten | full and literal every time |
| Reasoning | prose keeps the causal links | keep only where it changes an action |
| Contents list | past ~2 screens | past ~100 lines |
| Length | about half the original words | shortest form keeping every fact |

**Divergence check — REQUIRED.** Before writing the file, name at least three decisions this
run made differently *because of the declared target*, and put them in the report. Fewer than
three means pass 4 did not run: the ordering law alone is not a target. Both targets producing
the same document is the failure this check exists to catch.

## Verification gate

Re-read the file you wrote. Not the draft, not your intent — the bytes on disk. Confirm:

1. Every fact in the original survives, was recorded as removed, or was corrected with a
   source. Diff the original against the refined document plus the record.
2. Every claim of the report is true of the written file. A summary you meant to add and did
   not is a false report.
3. Every marked `[unverified]` claim appears in the report, and every marker in the document
   sits on a claim whose failure the reader cannot undo.
4. No heading is duplicated. Under `--target=agent` no heading is a near-duplicate either,
   except the `## Critical constraints` / `## Critical constraints (repeat)` pair.
5. Every internal pointer resolves to a heading that still exists.
6. The critical block is where the target requires, and its two copies match verbatim
   (`--target=agent`).
7. Nothing in the document asserts something you did not find in the source or verify
   yourself.

## Report

1. Document path, target used, record path (or "no record kept").
2. Removed by pass: legacy spans, unsourced claims, duplicated facts, filler — with counts.
3. **Three or more decisions driven by the target** (the divergence check).
4. Unchecked claims: which artifact was out of reach, and the claims left standing on the
   source document's authority alone. Group them; do not list every table cell.
5. Claims marked `[unverified]` in the document, each with the harm a reader risks if it is
   wrong.
6. Deprecated features kept, with the branch of the deprecated-feature rule that applies.
7. Lines and words, before → after.

## Failure modes

| Rationalization | Reality |
|---|---|
| "It's deprecated, so it's legacy" | Only if its sole use is supporting the old system. Otherwise it is current behaviour with a removal date attached — keep the behaviour, drop the date. |
| "The source doesn't say, but it's obviously the working directory" | You just invented a fact. Unstated is unstated: leave the document silent and say so in the report. |
| "The claim is unsourced, so I'll soften it" | "10x faster" → "very fast" is the same opinion with less precision. Cite it or cut it. |
| "I can't verify this instruction, so it goes" | Marking beats deleting. A marked instruction gets checked; a deleted one is gone. |
| "I can't reach the source, so everything gets marked" | Then the marker means "this document exists" and the reader stops seeing it. Mark what a reader cannot undo; report the rest. |
| "Both targets want a clean document" | Then the flag did nothing. Name three decisions that differ, or pass 4 did not run. |
| "I'll note in the report that I added a summary" | The report is checked against the file, not against your intent. Re-read what you wrote. |
| "Compression means shorter" | Compression means fewer words for the same facts. A lost fact is a regression. |
| "The record is bureaucracy, the diff is in git" | The record says what was removed and why, grouped, verbatim. A diff of a full rewrite says nothing. |

## Red flags — stop and re-read the pass

- A sentence in the refined document that you cannot point at a source for.
- A "roughly", "generally", or "should be fine" that replaced a specific claim you could not verify.
- The word count dropped a lot and you cannot name which facts moved where.
- The report and the file disagree.
- The target block produced no visible difference.

## Evidence

Every readability rule in pass 4 traces to a source in
[references/readability-evidence.md](references/readability-evidence.md), with its date and
whether it is measured or recommended. Read it when a rule is contested, when adapting a rule
to a document type it does not fit, or before adding a rule of your own — the file also lists
the popular readability claims the evidence does not support.
