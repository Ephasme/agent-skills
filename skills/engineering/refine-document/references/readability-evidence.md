# Readability evidence, by target

Every rule in pass 4 of the skill traces to a row below. Each row states whether it is
**measured** (numbers from a study) or **guidance** (a standard or vendor recommendation with
no published measurement), and carries its date. Citations were re-verified against the
primary source on 2026-08-21; where the source disagreed with the popular version of a claim,
the source won and the discrepancy is noted.

## Contents

- [How to use this file](#how-to-use-this-file)
- [Agent target — measured](#agent-target--measured)
- [Agent target — vendor guidance](#agent-target--vendor-guidance)
- [Human target — measured](#human-target--measured)
- [Human target — standards and guidance](#human-target--standards-and-guidance)
- [Where the vendors disagree](#where-the-vendors-disagree)
- [Claims the evidence does not support](#claims-the-evidence-does-not-support)

## How to use this file

Read a row before bending the rule it supports. A **measured** row transfers to documents
that resemble the study's material; a **guidance** row is one vendor's advice about their own
models, and generalises less. Both beat a rule with no row at all: a new rule in the skill
needs a source here first.

The two targets diverge because the readers diverge. A human scans, reads a fraction of the
words, and stops when satisfied. A model ingests every token, weights the ends of its context
more than the middle, and frequently sees only the slice a search returned. Rules that help
one can cost the other, which is why the skill makes you name the decisions the target drove.

## Agent target — measured

| # | Finding | Numbers | Source | Date | URL |
|---|---|---|---|---|---|
| A1 | Accuracy on multi-document QA follows a U-shaped curve against the position of the relevant document: best at the very beginning, next best at the end, worst in the middle | GPT-3.5-Turbo drops more than 20 points from best to worst position; in 20- and 30-document settings the mid-context result falls below the closed-book baseline of 56.1% | Liu, Lin, Hewitt, Paranjape, Bevilacqua, Petroni, Liang, "Lost in the Middle: How Language Models Use Long Contexts", TACL vol. 12, pp. 157–173 | 2024-02 (preprint 2023-07-06) | https://doi.org/10.1162/tacl_a_00638 |
| A2 | Accuracy declines with input length on tasks that are trivial at short length — length alone, not difficulty | 18 models including GPT-4.1, Claude 4, Gemini 2.5, Qwen3; "performance consistently degrades across all models" on a repeated-words task | Hong, Troynikov, Huber, "Context Rot: How Increasing Input Tokens Impacts LLM Performance", Chroma technical report | 2025-07-14 | https://www.trychroma.com/research/context-rot |
| A3 | Topically related content that does not answer the question degrades extraction, and the damage compounds | "Even a single distractor reduces performance relative to the baseline… adding four distractors compounds this degradation further" | Same report | 2025-07-14 | https://www.trychroma.com/research/context-rot |
| A4 | The further the wording of the target content is from the wording of the question, the faster accuracy decays with length | "as needle-question similarity decreases, model performance degrades more significantly with increasing input length" | Same report | 2025-07-14 | https://www.trychroma.com/research/context-rot |
| A5 | Degradation is severe well inside the advertised window once literal keyword overlap is removed | 11 of 13 models claiming 128K+ fall below half their short-context baseline at 32K tokens; GPT-4o 99.3% → 69.7% | Modarressi et al., "NoLiMa: Long-Context Evaluation Beyond Literal Matching", ICML 2025, arXiv:2502.05167 | 2025-02-07 | https://arxiv.org/abs/2502.05167 |
| A6 | Length hurts even when retrieval is perfect and the irrelevant tokens are masked out entirely | 13.9%–85% degradation across models, within their claimed lengths | Du et al., "Context Length Alone Hurts LLM Performance Despite Perfect Retrieval", arXiv:2510.05381 | 2025-10-06 | https://arxiv.org/abs/2510.05381 |
| A7 | Prompt format changes task accuracy, and smaller models are far more sensitive to it | GPT-3.5-turbo varies by up to 40% **on a code-translation task**; GPT-4 is markedly more robust | He, Rungta, Koleczek, Sekhon, Wang, Hasan, "Does Prompt Formatting Have Any Impact on LLM Performance?", arXiv:2411.10541 | 2024-11-15 | https://arxiv.org/abs/2411.10541 |
| A8 | Models classify affirmative statements well and negated ones poorly, leaning on surface cues; fine-tuning narrows but does not close the gap | ~400K-sentence benchmark | García-Ferrero, Altuna, Álvez, Gonzalez-Dios, Rigau, "This is not a Dataset: A Large Negation Benchmark to Challenge Large Language Models", EMNLP 2023, arXiv:2310.15941 | 2023-10-24 | https://arxiv.org/abs/2310.15941 |

The 40% figure in A7 is scoped to one task. Cite it as evidence that format matters and that
the effect is model-dependent — not as a general spread across all work.

## Agent target — vendor guidance

| # | Guidance | Source | Date | URL |
|---|---|---|---|---|
| A9 | Place instructions at both the beginning and the end of a long context: "we found this to perform better than only above or below. If you'd prefer to only have your instructions once, then above the provided context works better than below." | OpenAI, "GPT-4.1 Prompting Guide", OpenAI Cookbook | 2025 | https://cookbook.openai.com/examples/gpt4-1_prompting_guide |
| A10 | Markdown is the recommended starting delimiter; an XML delimiter scheme is less effective when the content already contains XML | Same guide | 2025 | https://cookbook.openai.com/examples/gpt4-1_prompting_guide |
| A11 | "Good context engineering means finding the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome"; organise context into distinct labelled sections | Anthropic, "Effective context engineering for AI agents" | 2025-09-29 | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents |
| A12 | Agents navigate by stable identifiers and names: "the presence of a file named test_utils.py in a tests folder implies a different purpose than a file with the same name located in src/core_logic/" — file paths and naming conventions are load-bearing signals, and just-in-time loading beats pre-loading everything | Same post | 2025-09-29 | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents |
| A13 | "Put longform data at the top: Place your long documents and inputs near the top of your prompt, above your query, instructions, and examples", and ask for relevant quotes before the task | Anthropic, "Prompting best practices", long-context section | current | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#long-context-prompting |
| A14 | "In most cases, especially if the total context is long, the model's performance will be better if you put your query / question at the end of the prompt (after all the other context)" | Google, "Long context", Gemini API documentation | updated 2026-06-22 | https://ai.google.dev/gemini-api/docs/long-context |
| A15 | State what to do rather than what not to do: "Instead of just saying what not to do, say what to do instead" | OpenAI, "Best practices for prompt engineering with the OpenAI API" | current | https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-the-openai-api |
| A16 | AGENTS.md is plain Markdown with no required fields; the nearest file up the directory tree wins, so subprojects ship their own; README.md is for humans and AGENTS.md carries the detail agents need | AGENTS.md open specification, stewarded by the Agentic AI Foundation (Linux Foundation) | current | https://agents.md/ |

## Human target — measured

| # | Finding | Numbers | Source | Date | URL |
|---|---|---|---|---|---|
| H1 | Rewriting for the web improves measured usability against a promotional control, and the three edits compound | concise text +58%, scannable layout +47%, objective language +27%, all three +124% | Jakob Nielsen, "How Users Read on the Web", Nielsen Norman Group; underlying study Morkes & Nielsen, "Concise, SCANNABLE, and Objective: How to Write for the Web", CHI'98 | 1997-09-30 | https://www.nngroup.com/articles/how-users-read-on-the-web/ |
| H2 | Readers consume a minority of the words on a page | time to read at most 28% of the words; ~20% realistic | Jakob Nielsen, "How Little Do Users Read?", NN/g, over Weinreich et al., ACM TWEB 2(1) | 2008-05-05 | https://www.nngroup.com/articles/how-little-do-users-read/ |
| H3 | Unformatted text is scanned in an F-shaped path — two horizontal sweeps and a vertical run down the left — so line beginnings carry the reading | 232 users eyetracked across thousands of pages | Jakob Nielsen, "F-Shaped Pattern For Reading Web Content (Original Study)", NN/g | 2006-04-16 | https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content-discovered/ |
| H4 | The F-pattern is what happens when formatting gives the reader no cues: "The F-pattern is the default pattern when there are no strong cues" — good structure prevents it rather than exploiting it | eyetracking replication 11 years later, desktop and mobile | Kara Pernice, "F-Shaped Pattern of Reading on the Web: Misunderstood, But Still Relevant", NN/g | 2017-11-12 | https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/ |
| H5 | The same facts in a small table beat the same facts in text, for comprehension and modestly for recall six weeks later | comprehension d = 0.39, recall d = 0.12, n = 2305, registered report, census-matched UK sample | Brick, McDowell, Freeman, "Risk communication in tables versus text: a registered report randomized trial on 'fact boxes'", Royal Society Open Science 7(3):190876 | 2020-03-01 | https://doi.org/10.1098/rsos.190876 |
| H6 | Connected narrative is understood and recalled better than expository text — the reason connected reasoning should not be shredded into bullets | 75+ samples, >33,000 participants, robust to single-study removal | Mar, Li, Nguyen, Ta, "Memory and comprehension of narrative versus expository texts: A meta-analysis", Psychonomic Bulletin & Review 28(3):732–749 | 2021 | https://doi.org/10.3758/s13423-020-01853-1 |
| H7 | Signalling — headings, outlines, verbal cues that expose structure — has a small-to-medium positive effect on comprehension and transfer, largest for readers new to the material | r = .17, 95% CI [0.11, 0.22] | Richter, Scheiter, Eitel, "Signaling text–picture relations in multimedia learning: A comprehensive meta-analysis", Educational Research Review 17:19–36 | 2016 | https://doi.org/10.1016/j.edurev.2015.12.003 |

## Human target — standards and guidance

| # | Guidance | Source | Date | URL |
|---|---|---|---|---|
| H8 | Plain language has four governing principles: readers get what they need (**relevant**), can find what they need (**findable**), understand what they find (**understandable**), and can act on it (**actionable**). The fourth principle's official term is *actionable*; "usable" is a secondary paraphrase | ISO 24495-1:2023, "Plain language — Part 1: Governing principles and guidelines" | 2023-06 | https://www.iso.org/standard/78907.html |
| H9 | Write for the audience, use active voice and topic sentences, organise and summarise up front, use tables and lists. Statutory basis: the Plain Writing Act of 2010 | Digital.gov (GSA), "Plain language guide series". plainlanguage.gov is archived, not maintained — this is the live source | current | https://digital.gov/guides/plain-language/principles |
| H10 | Descriptive headings and labels help readers identify content; technique G130 is "Providing descriptive headings" | W3C WAI, "Understanding Success Criterion 2.4.6: Headings and Labels (Level AA)" | WCAG 2.1 | https://www.w3.org/WAI/WCAG21/Understanding/headings-and-labels.html |
| H11 | Readability formulas score word and sentence length only: "The formulas do not measure comprehension or reading ease", and scores for one text "differ by several grade levels, depending on which formula is used". Use one as a trigger to re-read, never as the rewrite target | AHRQ, "Tip 6. Use Caution With Readability Formulas for Quality Reports" | reviewed 2015-05 | https://www.ahrq.gov/talkingquality/resources/writing/tip6.html |

## Where the vendors disagree

Their advice on instruction placement looks contradictory and is not. Anthropic puts long
documents above the query (A13); Google puts the query after the context (A14); OpenAI puts
instructions at both ends and, failing that, before (A9). All three say the same thing about
a document: **bulk content in the middle, the things that must be obeyed at an edge.** That
convergence, plus the U-shaped curve in A1, is what the head-and-tail critical block
implements.

They differ on delimiters, and there the honest answer is that no universal ranking exists:
the format effect is real but model- and content-dependent (A7, A10). Markdown is the
default because two vendors recommend it for prose and because a Markdown document does not
need a second syntax layered on top.

## Claims the evidence does not support

Do not put these in a document, or in a justification for a rewrite.

1. **"Long context windows solved this."** Refuted for current frontier models by A2, A5 and
   A6 — degradation is measurable well inside the advertised window, on trivial tasks and
   with perfect retrieval.
2. **"A high needle-in-a-haystack score means long documents are safe."** That benchmark
   measures literal keyword retrieval; A4 and A5 show performance collapses once the wording
   stops matching.
3. **"Shuffled text beats coherent text, so structure doesn't help agents."** The Chroma
   report does find shuffled haystacks outperform coherent ones, but that is about narrative
   padding in a retrieval benchmark. No study measured heading structure or scannable
   organisation under that label, and every vendor recommendation (A9–A13) points the other
   way. Do not generalise it into a document-authoring rule.
4. **"XML beats Markdown"** (or the reverse), stated universally. A7 and A10: the effect
   exists, its direction depends on the model and on what the content already contains.
5. **"Markdown is N% more token-efficient than JSON."** Only practitioner blog measurements
   support this; the one peer-reviewed comparison in this area does not include Markdown.
   Token counts are easy to measure yourself for the document at hand — do not cite a
   percentage.
6. **"Repeat instructions everywhere to be safe."** The measured guidance is narrower: both
   ends of a long context, or once before it (A9). Arbitrary repetition costs tokens (A6)
   and risks contradictions, which are worse than a single statement.
7. **"Active voice is 23% faster to process"** and **"bullets are scanned 70% more
   efficiently"**. Both figures circulate widely; neither traces to a primary study. Active
   voice is sound default guidance (H9), without a number attached.
8. **"Write everything at a ninth-grade reading level."** A general-public plain-language
   target misapplied to practitioner documentation. Forcing the score down strips accurate
   terminology, and the score cannot see the organisation that actually carries
   comprehension (H11).
9. **"Design the layout to produce an F shape."** Backwards: the F-pattern is what readers
   fall back on when formatting gives them nothing (H4).
10. **"Bullets always beat prose."** True for discrete, parallel, comparable items (H5).
    False for connected reasoning, where narrative is understood and recalled better (H6).
