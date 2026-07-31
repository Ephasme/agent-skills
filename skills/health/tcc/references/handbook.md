# TCC research handbook

**An operating manual for the next agent who researches TCC (*thérapie cognitivo-comportementale* / cognitive behavioural therapy).**

This is not a summary of the dossier. `dossier.md` holds the findings and their inline citations. This file holds everything you need in order to *work with* that corpus without repeating its mistakes: where each kind of question is already answered, which sources are admissible, which citations are booby-trapped, which claims rot fastest, what is still open, and how to extend the corpus so the next agent after you inherits something coherent.

Corpus compiled **2026-07-28**. Read [§5 Decay schedule](#5-decay-schedule--what-rots-and-when) before you quote anything time-sensitive; several classes of claim in here have a shelf life measured in months.

---

## Contents

1. [Mission brief — what this corpus is and how to behave](#1-mission-brief--what-this-corpus-is-and-how-to-behave)
2. [Domain map — where your question is already answered](#2-domain-map--where-your-question-is-already-answered)
3. [The spine — twelve load-bearing facts](#3-the-spine--twelve-load-bearing-facts)
4. [Source registry — what counts as evidence here](#4-source-registry--what-counts-as-evidence-here)
5. [Decay schedule — what rots and when](#5-decay-schedule--what-rots-and-when)
6. [Trap list — how this corpus nearly got things wrong](#6-trap-list--how-this-corpus-nearly-got-things-wrong)
7. [Contested register — what to say when the sources disagree](#7-contested-register--what-to-say-when-the-sources-disagree)
8. [Do-not-repeat register — the superseded material](#8-do-not-repeat-register--the-superseded-material)
9. [Work queue — 125 open items, prioritised](#9-work-queue--125-open-items-prioritised)
10. [Method — how this corpus was built and how to extend it](#10-method--how-this-corpus-was-built-and-how-to-extend-it)

---

## 1. Mission brief — what this corpus is and how to behave

### 1.1 What exists

The corpus is the `tcc` skill, in the `health` category of the `agent-skills` repo. Its home is `$SKILL_DIR/` — this skill's own directory, whose absolute path the skill preamble prints — and every path below is relative to `$SKILL_DIR/references/`.

| File | Role | Size |
|---|---|---|
| `../SKILL.md` | Entry point. Operating rules, domain map, decay summary, what the corpus does not cover | 101 lines |
| `dossier.md` | **The findings.** 12 sections, ~210 distinct sources, every claim cited inline | 1,340 lines |
| `handbook.md` | **This file.** How to work with the corpus | 334 lines |
| `source-ledger.md` | **Every source, with why it was acceptable.** 526 rows grouped by research angle, restored verbatim from the deleted raw layer | 678 lines |

**The raw evidence layer has been deleted**, but its ledgers were restored. The corpus was condensed from thirteen research files — nine angle files and four gap-closure files — each carrying *Current state of knowledge*, *Superseded*, *Unresolved*, *Source ledger* and *Verification log* sections. Those files are gone. What survives: the findings in `dossier.md`, the superseded register in `dossier.md` §9, the contradictions in §10, the gaps in §11, the traps and contested register in §§6–7 here, and **all 526 ledger rows verbatim in `source-ledger.md`**.

Still only in git: the thirteen verification logs, which recorded what each adversarial pass corrected. Recover from the `me` repository at commit `15e599a` under `reference/health/tcc/raw/` — e.g. `git show 15e599a:reference/health/tcc/raw/guidelines.md`.

**One consequence worth carrying:** the dossier was written by an editor reading the raw files, not the primary sources. A load-bearing claim deserves one fetch of its cited source — and `source-ledger.md` will often tell you whether that source was read in full or only through an abstract.

### 1.2 The five operating rules

1. **Search before concluding. Cite or refuse.** Never answer from memory on this topic. The corpus exists because memory is stale here: guideline versions, French reimbursement rules and digital-product status all changed inside the last 24 months.
2. **`?` means unverified.** Every claim prefixed `?` in any file appears in the corpus but was not confirmed at the primary source. Do not promote a `?` claim to plain assertion without fetching the source yourself, and do not silently drop the prefix when quoting.
3. **Read the primary source, never a summary of it.** Automated page summarisers fabricated content **at least four times** while this corpus was being built, including inverting a paper's conclusion (§6.1). A search snippet is a pointer, not a citation.
4. **Never date a guideline from its year tag.** NICE bracket tags are *evidence-review* dates, not text dates. NG222 rec 1.5.3 is tagged `[2022]` and was rewritten in October 2025. This trap caught the corpus once and would have caught it more often (§6.2).
5. **A source's date and its evidence vintage are different numbers.** State both. ISTSS 2018/2019 rests on RCT searches ending 31 March 2018; NICE CG113's panic dosing is 2004 evidence on a guideline stamped "last reviewed 2024"; APA's depression guideline prints a 2025 suggested citation for a February-2019 document.

### 1.3 What this corpus is *not*

It is a **snapshot**, not a maintained document, and it is **not clinical advice**. Six named content areas were identified as missing and deliberately not researched — therapist competence and fidelity, health economics, cultural adaptation and non-Western evidence, older adults, CBT in physical illness (including the entire PACE / ME-CFS controversy), and the patient's own experience of treatment. See [§9 Tier 1](#tier-1--changes-what-a-reader-would-do). Do not present the dossier as complete; it says so itself in `dossier.md` §11.

---

## 2. Domain map — where your question is already answered

Find your question's row, go straight to the named section, and only then decide whether new searching is needed.

| If you are asked about… | Dossier section |
|---|---|
| What CBT *is*; definitions; the "three waves"; Beck's model | §1 |
| Whether cognitive change is the active ingredient; process-based therapy; network models | §1.4–1.5 |
| Exposure, ERP, the habituation-vs-inhibitory-learning story | §2.1 |
| Which components carry the effect; behavioural activation; behavioural experiments | §2.2–2.4 |
| **How many sessions**; dose; stepped vs matched care; frequency and spacing | §2.5, §7.8 |
| Relapse prevention; MBCT as maintenance; stopping antidepressants | §2.6 |
| Transdiagnostic / Unified Protocol; modular vs manualised | §2.7–2.8 |
| **"Does CBT work for X?"** — any of 16 disorders | §3.1–3.16 |
| Effect sizes, cross-disorder comparison, first-line status | §3.0 |
| ACT, DBT, MBCT, schema therapy, MCT, CFT; mindfulness harms | §4 |
| EMDR vs trauma-focused CBT | §4.3 |
| **"Is CBT overrated?"** — decline effect, publication bias, waitlists, dodo bird | §5 |
| Dropout, harms, deterioration, durability, who it fails | §5.8–5.12 |
| iCBT, apps, chatbots, AI therapy, digital therapeutics, DiGA | §6 |
| **France: who may practise, what it costs, "Mon soutien psy"** | §7 |
| French guidelines, ALD, psychiatrist tariffs, access, controversies | §7.4–7.7 |
| What changed in 2024–2026; psychedelics, VR, precision therapy, SSIs | §8 |
| **"Is this claim still current?"** | §9 (122 items) |
| Guideline status, versions, what replaced what | §9 D |
| Where the corpus contradicts itself | §10 |
| What is missing or unsourced | §11 (20 coverage gaps + 105 unresolved) |

**Questions the corpus cannot answer at all** — do not improvise, start fresh research: therapist competence and fidelity; cost-effectiveness and QALYs; cultural adaptation and LMIC delivery; older adults; CBT in cancer / diabetes / IBS / ME-CFS; homework and alliance as processes; the patient's lived experience of treatment; bibliotherapy.

---

## 3. The spine — twelve load-bearing facts

These carry most of the dossier's weight. Every one is sourced inline in `dossier.md`; the section reference is given so you can pull the citation. If a new source contradicts one of these, that is a corpus-level event — record it in `dossier.md` §9, not just in your answer.

1. **CBT works, modestly, and the headline numbers are inflated by trial design.** Depression g = 0.79 unadjusted → 0.60 in low-risk-of-bias trials → **0.47** corrected for publication bias. (§5.0, §5.2)
2. **Absolute response ≈ 41%, of which ≈ 16–17% would have responded anyway** — CBT is the reason roughly one patient in four gets better. Every relative effect size must be read against this denominator. (§5.8)
3. **Against a pill placebo, psychotherapy for depression does not survive publication-bias correction** (NNT 6.7 → 14.3, no longer significant). (§5.2)
4. **Choice of control group is worth as much effect size as an antidepressant.** Waitlist g = 0.95 vs care-as-usual g = 0.63. 62% of trials across eight disorders used waitlist. Any pre-2015 anxiety/OCD/PTSD/eating-disorder headline effect is "vs no treatment", not efficacy. (§5.3)
5. **Cognitive change is a robust correlate and a plausible common pathway, not a CBT-specific active ingredient.** Removing cognitive restructuring does not reliably reduce outcome; removing behavioural activation does. (§1.4, §2.2)
6. **The habituation rationale for exposure is dead as theory and alive as practice.** The inhibitory-learning model won the argument; its superiority trial — from Craske's own lab — was null. (§2.1)
7. **No current guideline recommends CBT to the exclusion of other structured psychotherapies for depression.** WHO, NICE, CANMAT and HAS all bundle it with alternatives. "CBT is the gold standard" is not a guideline position. (§9 D, §3.1)
8. **CBT-I has the cleanest first-line status of any indication**, and beats drugs on long-term remission at high certainty — on only 13 trials / 823 participants. (§3.8)
9. **The guided/unguided iCBT binary was retired in May 2026 by the same authors who built it.** Human contact *before* treatment matters more than guidance *during* it; in low-risk-of-bias trials automated support ranks first. (§6.1)
10. **The digital-therapeutics category's headline story is commercial failure, not efficacy failure** — Pear Chapter 11, Woebot shut down, Ash withdrawn from the UK, two of three NICE-recommended depression products removed for withdrawal from market. (§6.5, §9 F)
11. **France does not give TCC privileged status.** HAS: *"ces psychothérapies peuvent toutes être mises en œuvre"*; TCC merely has the most data. The state reimburses a professional and a session count, not a protocol. (§7.5)
12. **"Mon soutien psy" in 2026:** 12 sessions/calendar year at €50, no referral since 15 June 2024, one statutory exception (no cap for minors in ALD), a 20% ceiling on remote conventioned activity, tiers payant generalising 1 October 2026. **This is the fastest-decaying block in the corpus.** (§7.3, §9 E)

---

## 4. Source registry — what counts as evidence here

### 4.1 Tier A — cite directly

| Body / source | What it is authoritative for | Current documents & status |
|---|---|---|
| **NICE** (UK) | Dose, first-line status, do-not-do statements | NG222 depression (2022, **reviewed 30 Jan 2026, will not update**); NG116 PTSD (2018); CG113 anxiety/panic (**panic content `[2004]`, never updated**); CG159 social anxiety (2013); CG31 OCD (2005, **replacement GID-NG10435 due 16 Feb 2027**); CG178 psychosis (2014); HTG624/675/676 digital |
| **HAS** (France) | French clinical position, ALD scope, reimbursement doctrine | EDC adulte RBP (Oct 2017, current); ALD n°23 actes-et-prestations (Jan 2025); ALD-23 guide médecin (2007, historical — **the only French dose anchor in existence**); autism RBP (Jan 2026). **No HAS recommendation exists for anxiety, OCD, PTSD, insomnia-CBT-I, eating disorders or adult ADHD** |
| **WHO** | Global recommendation strength and certainty | **mhGAP 3rd edition, 20 Nov 2023** — supersedes 2010/2015. DEP3 strong/moderate (bundled, not CBT-privileged); ANX2 strong/moderate (the strongest CBT-specific WHO statement); STR1 conditional, STR2 strong. ⚠ mhGAP **Intervention Guide** is still v2.0 (2016) |
| **APA** (US) | US psychotherapy grading | PTSD guideline **2025 edition** (approved 22 Feb 2025) — supersedes 2017. Depression guideline substantively **February 2019** despite a 2025 suggested citation |
| **VA/DoD** | Recommendation-level GRADE for PTSD and MDD | PTSD/ASD **v4.0 (2023)**, evidence to 4 May 2022; MDD v4.0 (2022), evidence to Jan 2021 |
| **Cochrane** | Systematic-review baselines | CD013305 behavioural activation (2020); CD000560 debriefing; CD006869.pub3 multi-session prevention (2019). ⚠ **No current Cochrane review of CBT for adult depression exists** |
| **Métapsy / Cuijpers group** | The only identically-methodised cross-disorder series | *JAMA Psychiatry* 2025 (searches to 2024-01-01); *World Psychiatry* 2024 (to 2023-01-01). **A living database — re-check for a refreshed series** |
| **Légifrance / JO / ameli / service-public** | Every French statutory or tariff claim | Décret 2025-424; arrêtés 24 juin 2024, 13 mai 2025, 17 juin 2026; LOI 2026-492; LOI 2025-1403; décret 2026-163 |
| **ClinicalTrials.gov / registries** | Trial existence, status and dates | Distinguish *first-posted* from *study start* — conflating them produced one of the corpus's contradictions |
| **ISTSS, Phoenix Australia, AASM, CANMAT, AWMF/NVL** | Secondary guideline authorities | ISTSS 2018/2019 — **evidence cut-off 31 Mar 2018**, replacement announced with no date. German S3 anxiety guideline **expired 5 April 2026** |

### 4.2 Tier B — pointers only, never a basis

Search-engine summaries, AI-written aggregator pages, Wikipedia, therapist directories, teleconsultation and clinic marketing, insurer pages, law-firm client alerts, advocacy trackers, press coverage where a primary source exists, conference-report sites. **Several of these were the *only* hits for French clinical claims and were all rejected** — that rejection is itself a finding (§9 Tier 3).

### 4.3 Tier C — actively rejected in this corpus, with reasons

- Third-party mirrors of the APA 2017 PTSD guideline (`gonetowar.com`, `naasca.org`).
- An unattributed AI-style aggregator asserting Rejoyn's continued availability, a "$99/month relaunch" and a De Novo number that conflicts with the sponsor's own "cleared" language.
- A "6,200+ participating psychologists" figure appearing only in secondary press.
- The remission figures ("60 à 80 %") quoted by French therapist-directory pages claiming HAS endorsement without citing any HAS document.

### 4.4 The full ledger — `source-ledger.md`

`references/source-ledger.md` carries **526 rows**: every source the corpus used, with its type, its date or version, and **why it was judged acceptable**, grouped by the research angle that compiled it. Reproduced verbatim from the thirteen deleted raw files, not merged or deduplicated — a source two angles both reached appears twice, and that duplication is itself evidence of how well attested it is.

Two questions it answers that `dossier.md` cannot:

1. **Is this class of source admissible here?** Read the "Why acceptable" column of comparable rows before admitting a new one. The tiers above are the rule; the ledger is 526 worked examples of it.
2. **Was this claim read at source, or only through an abstract?** Many rows say so explicitly — "abstract read via ACBS", "full PDF read page by page", "403; figures from a secondary transcription". A row admitting second-hand retrieval is exactly the kind of claim that carries a `?` in the dossier, and the first thing to re-fetch if it turns load-bearing.

Row counts by angle: france-practice 63, techniques-protocols 63, frontier 60, third-wave 56, evidence-by-disorder 53, digital-delivery 50, foundations-models 49, efficacy-controversies 48, guidelines 36, gap-3 16, gap-4 16, gap-1 10, gap-2 6.

---

## 5. Decay schedule — what rots and when

Ordered by how fast a claim becomes wrong. **Re-verify anything in the first two bands before using it, regardless of how recently the corpus was compiled.**

| Band | Claim class | Why it moves | Re-check trigger |
|---|---|---|---|
| **Months** | French reimbursement rules, tariffs, session caps, remote-delivery ceilings, tiers payant | Changed **six times** between June 2024 and June 2026 by décret/arrêté/LOI. Two corpus files stamped "unchanged, re-verified" and were **wrong on two counts** | Always. Read Légifrance + ameli + service-public before answering |
| **Months** | Digital product existence and market status | Pear Chapter 11, Woebot shut, Ash withdrawn, Beating the Blues and Deprexis removed. Rejoyn, Big Health, SilverCloud/Amwell, Koa Health, Iona Mind, Wysa, Cerina **all unverified for 2026** | Always. Never assume a named product still trades |
| **Months** | AI-therapy legislation (US states, EU) | 2025 wave superseded by 2026 wave within a year; a "three states ban AI therapy" snapshot went stale in months | Always |
| **6–18 months** | Métapsy / Cuijpers pooled estimates | Living database, continuous output; the corpus's two anchors are calibrated on 2.5- and 3.5-year-old searches | Before quoting any cross-disorder effect size |
| **6–18 months** | NHS Talking Therapies statistics | The Internet-Enabled-Therapy series **broke on a definition change in January 2026** — a level shift, not a trend | Before quoting any volume or recovery figure |
| **1–3 years** | Guideline revision status | NICE CG31 replacement due 16 Feb 2027; HTG675 review due by May 2027; German S3 anxiety expired 5 Apr 2026; APA depression update panel appointed 2025 with no published date | Check the guidance page's own "last reviewed" line every time |
| **3–5 years** | Meta-analytic effect sizes for a specific disorder | New NMAs displace old ones; adult OCD's synthesis is already a decade old | When precision matters |
| **Slow / stable** | Theory and mechanism; the superseded register; methodological critiques (waitlist inflation, publication bias, dodo bird) | These move on the scale of a research programme | Annually, or on a named new publication |

---

## 6. Trap list — how this corpus nearly got things wrong

Each of these actually caught a researcher during construction. Treat them as pre-loaded failure modes.

### 6.1 Summarisers fabricate

Automated page summaries invented, at minimum: an Angelakis 2022 headline that does not exist in the paper and pointed the **opposite** way to the real finding; a Jover Martínez 2026 "verbatim" passage; a Cambridge Core effect range absent from the article; and a Carona 2023 conclusion that **inverts** the paper's actual position. A fifth summariser fabricated a subgroup range in the Tong 2026 NMA. **Six fabricated "verbatim" quotes were removed corpus-wide.** If a quotation is load-bearing, you must have opened the document.

### 6.2 Citation traps

| Trap | What goes wrong |
|---|---|
| **NICE bracket tags** | `[2022]` on NG222 rec 1.5.3 conceals an October 2025 rewrite. `[2004]` on CG113's entire panic-dose block sits on a guideline stamped "Last reviewed: 7 May 2024" |
| **`apa.org/ptsd-guideline/ptsd.pdf`** | Now serves the **2025** guideline. A reference reading "APA (2017), apa.org/ptsd-guideline/ptsd.pdf" is broken on both counts |
| **APA depression landing page** | Prints its suggested citation as "(2025)" for a February-2019 document — wrong about evidence vintage by six years |
| **NG222 recommendation numbers** | The May 2024 "presentational" simplification shifted them. **Cite NG222 by text, not number** |
| **NICE HTE8/HTE9/MTG70** | Renumbered to HTG675/HTG676/HTG624. HTE8 → HTG675 in **December 2025** |
| **"IAPT"** | Renamed **NHS Talking Therapies** in 2023; the dataset is still versioned "IAPT 2.1" |
| **WHO** | Citing the 2013 stress guidelines or mhGAP-IG 2.0 as WHO's current position. The current word is **mhGAP 3rd ed., 20 Nov 2023** |
| **ISTSS** | Never cite the 2009/2012 sets. Prefer the dated filename `ISTSS_PreventionTreatmentGuidelines_FNL-March-19-2019.pdf` |
| **Registry dates** | *First-posted* ≠ *study start*. Conflating them generated a false contradiction about NCT06517589 |
| **CG113 patient page** | Still advertises "structured problem solving" for panic — an option NICE formally withdrew as an error in July 2019 |

### 6.3 Fetch traps

- `nice.org.uk` returns **HTTP 403** to some fetchers. The corpus's NICE text was retrieved through a different fetcher. If yours 403s, switch tools; do not fall back to a summary.
- URL casing changed the answer once: `/guidance/ng116` and `/Guidance/Ng116` returned **different "last reviewed" dates** on the same day (§7 item 8). Unresolved.
- ScienceDirect, Taylor & Francis and several publishers return 403; PMC sometimes serves a reCAPTCHA. Route to PMC, institutional repositories, or the author's own copy.
- HAS PDFs sometimes return undecodable streams; the TDAH argumentaire defeated extraction entirely.
- The VA/DoD full CPG PDF failed **TLS certificate validation** — its recommendation strengths are quoted via the ECRI Guidelines Trust profile, which is why the EMDR Strong/Weak question is still open.

### 6.4 Reading traps

- **"95% of responders improve within 7 sessions" is not "7 sessions is enough."** The denominator is responders only — 25–27% of low-intensity cases. This is the single most-misread statistic in the field.
- **A large effect size vs waitlist and a modest response rate are the same finding stated twice.** Treat them as compatible.
- **"Insufficient evidence to recommend"** means absence of evidence of effectiveness *or ineffectiveness* — ISTSS's own definition, covering 62% of its recommendations. It is not a negative finding.
- **Superseded theory ≠ superseded practice.** Habituation-rationale exposure still works; the rationale is what fell.
- **Publication date ≠ evidence date.** Always state which anchor you mean; the corpus itself slipped on ISTSS's "7 years old" (7 from the amendment, 8+ from the search cut-off).

---

## 7. Contested register — what to say when the sources disagree

The dossier's §10 documents 22 internal disagreements. These are the ones where an answer depends on which side you take. **Resolved** rows give the settled position and why; **open** rows must be presented as open.

| # | Question | Position to take |
|---|---|---|
| 1 | NG222 rec 1.5.3 wording | **Resolved.** Live text is the October 2025 wording; the addition of *"informed"* raises the bar — never describe it as a softening. Quote both sentences |
| 3, 5 | Mon soutien psy: session cap and remote delivery | **Resolved against "unchanged".** LOI 2026-492 removes the cap for minors in ALD; arrêté du 17 juin 2026 imposes the 20% remote ceiling and in-person bilan. Statutory text wins over a portal page |
| 4 | Tiers payant from 1 Oct 2026 | **Resolved, with caveat.** Three primary artefacts support it; the application décret is still pending and the LFSS article number is unverified |
| 7 | WHO's position on PTSD therapy | **Resolved.** mhGAP 3rd ed. (2023). One corpus file's 2013 entry is a decade stale |
| 8 | HAS 2007 ALD-23 guide | **Resolved.** The document is accessible and its GAD/panic/OCD quotations are verbatim-verified. ⚠ The separate claim that it names "TCC and EMDR as treatments of choice" for psychotrauma remains **unsourced** |
| 9 | **Status of relaxation** | **Open — and one corpus file overstates it.** Correct statement: a negative component in specific packages *and simultaneously* a live AASM conditional recommendation for insomnia and a live co-equal NICE option for GAD. **Contested, not superseded** |
| 11 | INSERM 2004 | **Resolved.** Never formally superseded or scientifically retracted; withdrawn in 2005 by ministerial decision — political, not scientific. Both of the usual rhetorical uses are wrong |
| 13 | Guided vs unguided iCBT | **Resolved against both older framings** by Tong 2026 |
| 15 | "Group CBT is downgraded" | **Overstated.** True for OCD, PTSD and social anxiety; **false for depression**, where NICE ranks group CBT and group BA *above* individual CBT |
| 16 | Dodo bird | **Mostly upheld, newly cracked.** Brands converge while components diverge; do not state equivalence at the flatness the corpus's own within-CBT differentiation contradicts |
| 17 | "CBT works less well in young people" | **Scope it.** True for youth *depression*; paediatric anxiety shows OR 5.45 vs waitlist, NNTB 3 |
| 2 | NHS IPT recovery rate (44.8% vs 48.7%) | **Open — one is wrong.** Same source, same year. Experimental statistics; unadjusted and confounded either way |
| 12 | Authorship of the transdiagnostic meta-analysis | **Open.** Jiménez-Orenga vs Díaz-García for the same DOI. **Cite by DOI and title** |
| 19 | Mon soutien psy uptake | **Open, and must stay open.** Two French ministry documents from the same week give 1 M vs 1.8 M patients. **Do not pick one** |
| 22 | NG116 "last reviewed" date | **Open.** Two URL casings returned different dates. Dossier states 8 April 2025. Rec 1.6.5 stands either way |
| 34 | VA/DoD 2023 grade for EMDR | **Open.** Strong / Weak / Strong-For across three secondary renderings. Unresolvable without the CPG's own table |
| 20 | Session dose for a French patient | **No resolution exists anywhere.** HAS 2007 says ≥25 for OCD; NICE frames panic and OCD in therapist *hours*; English data give 14 sessions for 95% of high-intensity responders; Mon soutien psy caps at 12. Present the conflict, not a number |

---

## 8. Do-not-repeat register — the superseded material

`dossier.md` §9 catalogues **122 superseded, abandoned or contested items** in six groups. Do not duplicate it here — consult it before quoting anything. Its shape:

| Group | Count | Highest-value entries |
|---|---|---|
| **A. Theory and mechanism** | 14 | Habituation as exposure's mechanism; Beck's 1967/1979 triad; cognitive restructuring as the necessary ingredient; network centrality as a treatment target |
| **B. Techniques** | 14 | Thought stopping; psychological debriefing (**with evidence of harm**); "safety behaviours must always be eliminated"; SIT as Strong-for in PTSD |
| **C. Effect sizes and evidence practices** | 27 | Waitlist as an acceptable control; pre-post effect sizes; "CBT beats other psychotherapies for depression"; the common-factors variance partition; Ruiz 2012 on ACT; Normann 2014 on MCT |
| **D. Guidelines and official documents** | 34 | CG90, CG26, CG22/CG123, TA97, CG82; WHO 2010/2015; APA PTSD 2017; VA/DoD 2017; ISTSS 2009/2012; the whole "stepped care" vocabulary |
| **E. France — reimbursement** | 14 | 8 sessions → 12; €40/€30 → €50; mandatory referral → direct access; ADELI → RPPS; the 20% remote ceiling |
| **F. Digital / AI** | 19 | Karyotaki 2021 as the guided-vs-unguided reference; the binary itself; app effect sizes before bias correction; Pear, Woebot, Ash; the 2025 AI-law snapshot |

**Two entries deserve special care because the corpus itself got them wrong at first:** relaxation is **contested, not superseded** (§7 row 9), and "group CBT is downgraded" is **scope-limited, not general** (§7 row 15).

---

## 9. Work queue — 125 open items, prioritised

`dossier.md` §11 lists all 125 with their full context. This is the triage: what to do first, and why.

**Two number series, and they overlap — read the citation form.** §11.1 holds **20 coverage gaps** in its own series 1–20, cited here as **`11.1-N`**. §11.2 through §11.10 hold **105 unresolved items** in a single shared series 1–105, cited here as a **bare number**. A bare "14" in Tier 3 or Tier 4 below means §11 item 14, not §11.1 item 14.

### Tier 1 — changes what a reader would do

Six content areas were identified as missing and never researched. Any one of them is a full research angle.

| # | Gap | Why it is first |
|---|---|---|
| 11.1-1 | **Therapist competence, fidelity, drift, supervision** | The bridge between the efficacy literature and the therapist a patient actually sits in front of. `CTS-R` returns **0 hits** across the corpus; exposure under-use — the best-documented drift phenomenon in the field — does not appear at all |
| 11.1-2 | **Health economics and cost-effectiveness** | The criterion guidelines actually optimise. `QALY` = 0 hits. Without it the dossier cannot explain why the recommended option is often the cheap one |
| 11.1-5 | **CBT in physical illness, and the PACE / ME-CFS controversy** | The highest-profile public controversy about CBT in fifteen years, which produced a guideline-level downgrade (NICE NG206, 2021), is **absent** next to 114 KB on publication bias |
| 11.1-3 | **Cultural adaptation, LMIC and task-shifted delivery** | Country of origin swings effect sizes by up to **0.61 SD — larger than the whole treatment effect in low-RoB trials** — and the corpus dismisses it in one line. Its own largest unexplained moderator |
| 11.1-6 | **Homework, alliance, patient experience, dropout reasons** | Homework — TCC's defining behavioural demand — appears **once in 8,385 lines**. Determines whether a given person completes a course |
| 11.1-4 | **Older adults** | `late-life`, `geriatr`, `personnes âgées` all return 0. The population where the pharmacological alternative is most hazardous |

### Tier 2 — corrections that would change a stated conclusion

| # | Item | Action |
|---|---|---|
| 11.1-9 | The "concertation after 12 sessions before a further cycle" claim for Mon soutien psy | **Probably a survival of the 2022 MonPsy design.** No primary source supports it. If stale it is materially misleading about how many sessions a patient can get. Audit against the arrêté du 13 mai 2025 |
| 11.1-13 | Both cross-disorder anchors rest on searches 2.5 and 3.5 years old | Check Métapsy for a refreshed unified series. **Every disorder-level claim hangs off these** |
| 11.1-12, 58 | Rejoyn, Big Health and three NICE-listed products assumed still trading | Query the FDA 510(k) database on product code **PWE**; check Otsuka IR. The section's own headline is commercial failure — an unverified "still marketed" is its weakest link |
| 11.1-10, 63 | App retention benchmarked on 2017–18 pre-LLM panel data (30-day retention 3.3%) | Find a post-2020 replication. This number is the main counterweight to the app efficacy literature |
| 11.1-19 | VA/DoD "update in progress" markers not mapped | Establish which CPGs are under update. Two heavily used sources rest on evidence reviewed 4–5 years ago |
| 11.1-18 | Cochrane currency not formally checked | Determine whether CD003388, CD008704, CD008705 are flagged "no longer current". CD003388 is "the base layer under several current guidelines" |
| 11.1-20 | German S3 anxiety guideline quoted as in force **in the same file that records its expiry** | Past its *Gültigkeitsdatum*, revision unregistered. It is the corpus's only guideline-level VR positioning |
| 33, 34 | VA/DoD recommendation table | Obtain the CPG PDF (TLS failure blocked it). Resolves the EMDR Strong/Weak conflict |

### Tier 3 — sourcing holes that constrain what can be claimed

Bare numbers are §11 items (the 1–105 series), not §11.1 coverage gaps.

- **French institutional anchors (1, 25, 31, 49, 87, 88).** No HAS document defining TCC; **no HAS RBP for anxiety, OCD, PTSD, insomnia, eating disorders or adult ADHD**; no HAS psychotrauma recommendation despite a 2020 note de cadrage targeting 2021; no count of French TCC therapists or of the modality share within Mon soutien psy. **State "no published recommendation found after a targeted search" — never "HAS recommends X".**
- **No European training standard (16, 81).** The only EABCT document is titled `Training-and-Accreditation-2002-2013` — the filename is the deprecation signal.
- **Genuine literature holes, not retrieval failures (26, 40, 55, 66).** No meta-analysis of CBT-attributable deterioration exists; no systematic harms literature for ACT/DBT/schema/MCT; **no current Cochrane review of CBT for adult depression**; **no head-to-head chatbot-CBT vs guided-iCBT trial** — the single most decision-relevant missing comparison in the digital section.
- **Paywalled or blocked primaries worth one more attempt (19, 20, 44, 67, 75).** Cuijpers 2025 Table 2 + GRADE table; Cuijpers 2024 Results; **de Vries 2018 on cumulative reporting and citation bias — likely the strongest single "how inflated is the literature" source**; Tong 2026's Figure 3 / Table 2 league values and CINeMA ratings (without which **no "moderate-certainty evidence that…" statement can be made about any contrast in that NMA**); the HAS TDAH argumentaire §3.3.2.
- **Statutory texts read only through trackers (61, 105).** Maine, Colorado, Tennessee and Rhode Island AI-therapy laws — the largest remaining sourcing weakness in the AI-regulation material.

### Tier 4 — completeness, low decision impact

Bare numbers are §11 items (the 1–105 series), not §11.1 coverage gaps.

Items 2, 7, 9–10, 14, 17–18, 21, 23–24, 27–30, 32, 35–39, 41–43, 45–48, 50–54, 56–57, 59–60, 62, 64–65, 68–74, 76–80, 82–86, 89–104. Mostly single unfetched figures, unverified author lists, and status checks on secondary guidelines.

---

## 10. Method — how this corpus was built and how to extend it

### 10.1 What produced it

A 25-agent workflow, run 2026-07-28: nine parallel angle researchers → one adversarial verifier per angle (editing files in place) → a deprecation auditor plus a completeness critic → four gap-fill researchers → one editor. Script preserved at `~/.claude-perso/projects/-Users-loup-code-perso-me/<session>/workflows/scripts/tcc-deep-research-*.js`.

**All nine angles came back `CORRECTED`, none clean.** That is the base rate to expect: a first-pass researcher under cite-or-refuse rules still fabricates quotes and cites superseded guidance. **The verification pass is not optional.**

### 10.2 Search patterns that worked

1. **Search for the *newer* version first, not the claim.** The highest-yield query shape was "`<guideline> update 2026`" / "`<guideline> last reviewed`", run *before* reading the guideline itself.
2. **Go to the issuing body's own update-information page**, not the guidance page. NICE's `/chapter/Update-information` is where amendments hidden behind year tags are recorded.
3. **For French rules, start at Légifrance and work outward.** Portal pages (ameli, service-public) lag the JO by weeks and were wrong twice.
4. **Chain-verify a claim to the instrument that changed it** — décret, arrêté, LOI, with JO number and date. A portal sentence is not a source for a statutory rule.
5. **When a publisher 403s, try PMC → institutional repository → author copy → society site.** In that order.
6. **Check whether a paper's own authors have superseded it.** The single largest correction in this corpus came from noticing that Karyotaki 2021's senior authors published its replacement.
7. **Search for the *absence*.** "No HAS recommendation exists for X" required exhausting has-sante.fr's search, then stating the negative explicitly. That negative is itself a finding.

### 10.3 If you add to the corpus

Preserve the structure — the next agent depends on it:

1. **Write findings straight into `dossier.md`**, in the section the domain map points at. There is no raw layer to stage them in any more — a claim that is not in the dossier is not in the corpus.
2. **Append a dated verification note** to the section you touched, recording what you checked, what you corrected and what you removed. That note is now the only provenance record the corpus keeps.
3. **Every substantive claim carries its citation inline** — URL, the specific finding or quote, and the date or version. No URL dumps.
4. **Prefix `?` on anything you did not confirm at source.** Do not remove someone else's `?` without fetching the source.
5. **Update two places when a fact changes:** `dossier.md` (the claim *and* §9 if something became superseded), and this handbook's §5 or §9 if the change alters the decay schedule or closes a queue item.
6. **Log rejected sources.** "Only marketing pages assert this" is a finding worth keeping; it stops the next agent re-running the same search.
7. **Re-verify before reusing.** Anything in §5's first two bands is presumed stale until re-checked, however recently the corpus was compiled.

### 10.4 Language convention

Repo convention is English (see the repo `CLAUDE.md`). French clinical and institutional terms stay verbatim with a gloss on first use: **TCC**, **HAS**, **RBP**, **ALD**, **EDC**, **"Mon soutien psy"**, **AFTCC**. Folder and file names stay English.
