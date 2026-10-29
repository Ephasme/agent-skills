---
name: call-french-insurance-law-agent
description: Hands any French-law insurance question to the dedicated `french-insurance-law-expert` sub-agent and relays its sourced answer. Covers refusal of cover, nullity for false declaration, forfeiture (déchéance), exclusion clauses, the two-year limitation period, proportional rule, termination and the Hamon / Chatel / Lemoine laws, motor claims and the Badinter law, dommages-ouvrage and ten-year liability (décennale), natural disasters, life insurance and beneficiary clauses, borrower insurance, group contracts, duty of advice and distribution (DDA), the victim's direct action, expert appraisal, time limits and litigation strategy. Use when the user mentions "assureur", "sinistre", "garantie refusée", "police d'assurance", "L. 113-…", "déchéance", "dommages-ouvrage", "courtier", "mutuelle", or says their insurer refuses to pay or asks whether they can still bring a claim.
---

# Call the French insurance law agent

French insurance-law answers must rest on the current text of the Code des assurances and on case law, and a sub-agent named `french-insurance-law-expert` has a primary-source corpus and method preloaded. Your job is to hand the question over and relay the answer, not to answer.

1. Pass the user's full question to the sub-agent named `french-insurance-law-expert`, verbatim, with all context they gave: policy wording, dates (loss, notice, refusal), the insurer's letter, the parties involved.
2. Do not answer from memory, and do not pre-research the question yourself.
3. Relay the agent's answer as it came back, with its source citations and its stated uncertainties. Do not turn an open point into a firm conclusion.

The agent is read-heavy and slow by design. For a one-line factual question it is acceptable to skip it and use the fallback below.

## Serial fallback

If you cannot start a sub-agent, or the question is a quick factual one, load the `french-insurance-law` skill in the current session and follow it.
