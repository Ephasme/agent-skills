---
name: tcc
description: >-
  Sourced, adversarially verified research corpus on TCC (thérapie
  cognitivo-comportementale / cognitive behavioural therapy), compiled 2026-07-28 from
  ~210 cited primary sources. Use for any question about CBT or TCC — what it is,
  whether it works for a given disorder and how well, effect sizes and why headline
  numbers are inflated, techniques and session doses, exposure and ERP, behavioural
  activation, third-wave therapies (ACT, DBT, MBCT, schema therapy, MCT), EMDR versus
  trauma-focused CBT, the guideline landscape (NICE, HAS, APA, WHO mhGAP, VA/DoD),
  internet CBT, mental-health apps and AI therapy chatbots, and the French practical
  reality (who may legally practise, "Mon soutien psy", ALD, access). Also when asked
  whether a CBT claim is still current, or to extend or re-verify the corpus. Triggers:
  "TCC", "CBT", "psychothérapie", "Mon soutien psy", a named CBT technique or third-wave
  therapy, and phrasings like "does CBT actually work", "combien de séances".
---

# TCC research corpus

A standing evidence base on TCC (*thérapie cognitivo-comportementale* = cognitive behavioural therapy), compiled **2026-07-28** from a nine-angle research effort, adversarially re-verified against primary sources. It is your starting point for every TCC question. It is **not** automatically current — see [Decay](#decay--check-this-before-quoting).

## Files

**`$SKILL_DIR` is notation, not a variable that is already set** — it stands for this skill's own directory, the absolute path printed when the skill is loaded, or the directory holding this `SKILL.md`. Build every read and shell path from that, or export it once (`SKILL_DIR=<that path>`) before running any command below.

| File | What it is | When to open it |
|---|---|---|
| [`references/handbook.md`](references/handbook.md) | The operating manual — source registry, decay schedule, trap list, contested register, work queue, method | **Before any substantive research.** Always for a trap, source-admissibility or currency question |
| [`references/dossier.md`](references/dossier.md) | The findings. 12 sections, ~210 sources, every claim cited inline. 1,340 lines with very long lines | For the answer itself. Read the section the domain map names, in ranges — never the whole file |
| [`references/source-ledger.md`](references/source-ledger.md) | Every source used, with its type, date and **why it was acceptable** — 526 rows grouped by research angle | To judge whether a new source class is admissible, or to check whether a claim was read at source or only via an abstract |

Below, a bare `handbook.md` / `dossier.md` / `source-ledger.md` means that file under `$SKILL_DIR/references/`.

The corpus was condensed from a thirteen-file raw research layer that has since been **deleted**, though its 526 ledger rows are preserved verbatim in `source-ledger.md`; `dossier.md` §12 records what each deleted file covered and how to recover it from git. Because the dossier was written by an editor reading those files rather than the primary sources, a load-bearing claim deserves one fetch of its cited source — check `source-ledger.md` first, since it often records whether that source was read in full.

## Operating rules

1. **Never answer from memory.** The corpus exists because memory is stale here: guideline versions, French reimbursement rules and digital-product status all changed inside the last 24 months.
2. **Route before researching.** Use the domain map below. Do not re-research what the corpus establishes; cite it and move on.
3. **`?` means unverified.** Do not promote a `?` claim to a plain assertion without fetching the source yourself, and never silently drop the prefix when quoting.
4. **Read the primary source, never a summary of it.** Automated summarisers fabricated content at least four times while this corpus was built, once inverting a paper's conclusion. A search snippet is a pointer, not a citation.
5. **Never date a guideline from its bracket tag or landing page.** NICE tags are evidence-review dates: NG222 rec 1.5.3 is tagged `[2022]` and was rewritten October 2025; CG113's panic-dose block is `[2004]` on a guideline stamped "last reviewed 2024". The APA depression page prints a 2025 suggested citation for a February-2019 document. State the document date **and** its evidence vintage.
6. **Cite inline** — URL, the specific finding or quotation, the date or version. No URL dump at the end.
7. **Refuse rather than guess.** No acceptable source → say what you searched, why it was rejected, where a human should look next.

## Domain map

| Question about… | `dossier.md` § |
|---|---|
| What CBT is; definitions; three waves; Beck's model | §1 |
| Is cognitive change the active ingredient; process-based therapy; network models | §1.4–1.5 |
| Exposure, ERP, habituation vs inhibitory learning | §2.1 |
| Which components carry the effect; behavioural activation; behavioural experiments | §2.2–2.4 |
| **How many sessions**; dose; stepped vs matched care; frequency | §2.5, §7.8 |
| Relapse prevention; MBCT as maintenance; stopping antidepressants | §2.6 |
| Transdiagnostic / Unified Protocol; modular vs manualised | §2.7–2.8 |
| **Does CBT work for X** — any of 16 disorders | §3.1–3.16 |
| Cross-disorder effect sizes and first-line status | §3.0 |
| ACT, DBT, MBCT, schema therapy, MCT, CFT; mindfulness harms | §4 |
| EMDR vs trauma-focused CBT | §4.3 |
| **Is CBT overrated** — decline effect, publication bias, waitlists, dodo bird | §5 |
| Dropout, harms, deterioration, durability, who it fails | §5.8–5.12 |
| iCBT, apps, chatbots, AI therapy, digital therapeutics, DiGA | §6 |
| **France: who may practise, what it costs, "Mon soutien psy"** | §7 |
| French guidelines, ALD, psychiatrist tariffs, access, controversies | §7.4–7.7 |
| What changed 2024–2026; psychedelics, VR, precision therapy | §8 |
| **Is this claim still current** | §9 (122 items) |
| Guideline status and versions | §9 D |
| Where the corpus contradicts itself | §10 |
| What is missing or unsourced | §11 (20 coverage gaps + 105 unresolved) |

## Decay — check this before quoting

Re-verify against a primary source, however recently the corpus was compiled:

1. **French reimbursement rules, tariffs, session caps, remote-delivery ceilings, tiers payant** — changed six times between June 2024 and June 2026. Two corpus files stamped "unchanged, re-verified" were wrong on two counts. Read Légifrance first, then ameli / service-public.
2. **Digital product existence and market status** — Pear Chapter 11, Woebot shut down, Ash withdrawn from the UK, two of three NICE-recommended depression products removed. Rejoyn, Big Health, SilverCloud, Koa Health, Iona Mind, Wysa, Cerina are all unverified for 2026. Never assume a named product still trades.
3. **AI-therapy legislation** — the 2025 wave was superseded inside a year.
4. **Métapsy / Cuijpers pooled estimates** — a living database; the corpus's two cross-disorder anchors rest on searches 2.5 and 3.5 years old.

`handbook.md` §5 has the full schedule; §6 has the citation, fetch and reading traps.

## What the corpus does not cover

Six areas were identified as missing and deliberately never researched. Say so, then research from scratch under cite-or-refuse rules:

1. Therapist competence, treatment fidelity, drift, supervision.
2. Health economics and cost-effectiveness.
3. Cultural adaptation, LMIC and task-shifted delivery.
4. Older adults.
5. CBT in physical illness — including the entire PACE / ME-CFS controversy.
6. Homework, therapeutic alliance, patient experience, reasons for dropout.

## Two things the corpus itself got wrong at first

1. **Relaxation is contested, not superseded** — a negative component in specific packages, and simultaneously a live AASM conditional recommendation for insomnia and a live co-equal NICE option for GAD.
2. **"Group CBT is downgraded" is scope-limited** — true for OCD, PTSD and social anxiety; **false for depression**, where NICE ranks group CBT and group BA *above* individual CBT.

`handbook.md` §7 lists all 17 decision-relevant disagreements, marked resolved or open.

## Standing prohibition

Not clinical advice. State evidence and guideline positions; do not recommend a treatment for a specific person, diagnose, or advise on medication. When the real question is "what should I do about my own care", give the evidence and say it belongs with a practitioner.

## Extending the corpus

Only on explicit request. Then follow `handbook.md` §10.3:

1. Write findings straight into `dossier.md`, in the section the domain map points at. There is no raw layer to stage them in — a claim that is not in the dossier is not in the corpus.
2. Append a dated verification note to the section you touched: what you checked, corrected and removed. That note is the corpus's only provenance record.
3. Update two places when a fact changes: `dossier.md` (the claim, and §9 if something became superseded), and `handbook.md` §5 or §9 if the decay schedule or work queue moves.
4. Log rejected sources — "only marketing pages assert this" is a finding worth keeping.
5. English prose; French clinical and institutional terms verbatim with a gloss on first use (TCC, HAS, RBP, ALD, EDC, « Mon soutien psy », AFTCC). File names stay English.
