---
name: research
description: Answers a research question through a fixed seven-step pipeline (clarify, research, draft, review, verify, fix, publish) and delivers a written report in which every claim carries its citation, every uncitable claim is marked refused and every claim that could not be run is marked unverified. Use whenever the user invokes /research, or asks to research, investigate, dig into, survey, compare options for, or write up a sourced report on a technical, legal, scientific or product question whose answer deserves a document rather than a chat reply. Prefer cite-or-refuse for a single sourced answer in chat, fact-check-document for auditing claims in a document the user already has, and assess-true-quality for whether a product or vendor is actually good.
---

# Research

A research question gets one pipeline, always in this order:

**CLARIFYING → RESEARCHING → DRAFTING → REVIEWING → VERIFYING → FIXING → PUBLISHING**

Each step has an exit condition. Do not move to the next step until the current one's is met, and when you
move on, say so in one line with its evidence (`RESEARCHING done: 14 sources kept, 6 rejected, notes in …`).
Skipping a step is how a confident wrong report gets written: the order exists because each step catches what
the previous one let through.

This skill researches and reports. It pushes nothing, opens no pull request, merges nothing and deploys nothing,
unless the question itself was to change code and the user asked for that change.

## Setup

- **Slug**: a short kebab-case name for the question (`sqlite-wal-on-nfs`).
- **Report path**: the one the user named; otherwise `research/<slug>.md` under the working directory. Say which
  path you chose before RESEARCHING.
- **Notes**: keep working notes (sources taken, what each supports, version and date) as you go, in the
  conversation or a scratch file beside the report. They are what DRAFTING builds from and what PUBLISHING's
  source list comes from.

## 1. CLARIFYING

Restate the question in your own words, then list its ambiguities: scope, versions, platform, jurisdiction, what
"better" means, what decision the answer feeds.

Settle each one yourself from the brief, the code, the docs or a source. Ask the user only what none of those can
settle: two to four questions per round, each with its options and your recommended answer. If the user told you
not to ask, take your recommendation and record it as an assumption in the report.

**Exit**: a restated question with every ambiguity either settled (and how) or recorded as an assumption. Never
start researching on a guess: an ambiguity papered over now is a wrong conclusion later.

## 2. RESEARCHING

Gather sources and evidence under cite-or-refuse rules. Search before concluding; conclude from sources only,
never from memory, even when the topic feels familiar.

**Acceptable** (can support a conclusion):

- Official documentation from the project, vendor or standards body
- Source code from the project's canonical repository
- Peer-reviewed papers
- Primary legal or regulatory texts, and the texts of laws and standards themselves
- A maintainer's or recognised authority's writing on a verifiable channel (release notes, design docs, the
  maintainer's own blog)

**Not acceptable** (a pointer to a trustworthy source at most, never evidence):

- General blog posts, tutorials, SEO content
- Forum posts (Stack Overflow, Reddit, Hacker News, Discord)
- AI-generated summaries
- Marketing standing in for technical documentation
- Outdated sources: anything predating a relevant major version, deprecation or spec change

Record the **version and date** of every source as you take it, next to what it supports. For anything that
changes over time, a source older than the relevant change cannot support a claim about current behaviour.
Record rejected leads too, with why: they go in the report.

When two acceptable sources disagree, keep both and cite both. Prefer the more recent or more authoritative one
(source code over docs, a current spec over an older one); with no clear winner, say so.

Independent sub-questions can go to parallel sub-agents, each given the same source rules and asked to return
claims with citations, versions, dates and rejected leads. Without sub-agents, take the sub-questions one after
another.

**Exit**: notes that cover every part of the restated question, or say which part found no acceptable source.

## 3. DRAFTING

Write the report at the report path, built only on the notes. Use the structure in [Report](#report).

Every claim sits next to its citation: a direct link plus the section, quoted passage or line that supports it,
so claim maps to source at a glance. No citation dump at the bottom standing in for inline citations. What cannot
be cited is marked **refused**, with exactly what was searched and why what was found was rejected ("only Stack
Overflow hits", "docs do not cover this edge", "the only source predates v3"). Never fabricate a URL, section
title or quote: a citation you are not certain of does not go in.

**Exit**: the draft file exists at the report path.

## 4. REVIEWING

Review the draft for consistency and clarity: does the answer follow from the findings, do two sections
contradict each other, is anything claimed in the summary that the body does not support.

Hand the draft to a reviewer sub-agent when one is available, briefed only with the question and the draft path,
so it reads without your assumptions. Where they apply, the `refine-document` skill tightens prose and the
`fact-check-document` skill audits claims. Then check every citation yourself: it resolves, and it says what the
claim uses it for.

**Exit**: a list of findings (possibly empty) to fix.

## 5. VERIFYING

Run whatever can be run: reproduce code claims, commands, measurements and API calls. Stay read-only, use none of
the user's credentials, and spend nothing (paid APIs, cloud resources) without the user's OK.

A claim that cannot be run is marked **unverified**, not dropped. A claim the run contradicts goes back to the
findings list.

**Exit**: each runnable claim marked verified (with what was run and its result) or contradicted; the rest marked
unverified.

## 6. FIXING

Correct what REVIEWING and VERIFYING found. Re-check only what you changed: its citation resolves and supports it,
and any rerun still passes.

**Exit**: every finding fixed or explicitly kept with a reason.

## 7. PUBLISHING

The Markdown file at the report path is the canonical text. Then reply to the user with:

- the answer in a few lines and your recommendation, if the question feeds a decision;
- what was refused or left unverified, if anything changes the decision;
- the report path.

The report may also be rendered as an HTML page, provided the rendering carries every source: each claim keeps
its inline citation (link plus section or quote, with version and date), plus the full source list with the
rejected leads.

## Report

Use this structure:

```markdown
# <Question, restated>

## Answer
<The conclusion in a few lines, with its citations. Recommendation here when the question feeds a decision.>

## Findings
<One subsection per sub-question. Each claim with its inline citation: [title](link), §section or "quote",
version, date. Verified claims say what was run. Unverified and refused claims are marked as such.>

## Refused
<Each claim that found no acceptable source: what was searched, why what was found was rejected, where to look next.>

## Assumptions
<Every ambiguity settled by assumption in CLARIFYING, with the alternative it rules out.>

## Sources
### Used
<Every source cited: link, version, date, what it supports.>
### Rejected
<Every lead not used: link, and why (forum post, outdated, marketing, does not cover the case).>
```

Drop a section only when it would be empty, never to save space.
