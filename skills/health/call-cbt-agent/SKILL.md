---
name: call-cbt-agent
description: Hands any question about CBT / TCC (thérapie cognitivo-comportementale) to the dedicated `cbt-expert` sub-agent and relays its cited answer. Covers whether CBT works for a given disorder and how well, effect sizes and their limits, techniques and session doses, exposure and ERP, behavioural activation, third-wave therapies (ACT, DBT, MBCT, schema therapy, MCT), EMDR versus trauma-focused CBT, the guideline landscape (NICE, HAS, APA, WHO mhGAP, VA/DoD), internet CBT, mental-health apps and AI therapy chatbots, and the French practical reality (who may legally practise, "Mon soutien psy", ALD, access). Use when the user asks about CBT or TCC, "does CBT actually work", "combien de séances", a named CBT technique or third-wave therapy, whether a CBT claim is still current, or wants the underlying corpus extended or re-verified.
---

# Call the CBT agent

CBT questions are answered from a sourced, adversarially verified corpus, and a sub-agent named `cbt-expert` has it preloaded. Your job is to hand the question over and relay the answer, not to answer.

1. Pass the user's full question to the sub-agent named `cbt-expert`, verbatim, with any context they gave (their situation, the claim or document under discussion, the language they wrote in).
2. Do not answer from memory, and do not pre-research the topic yourself.
3. Relay the agent's answer as it came back. Keep every citation and every `?` marker (`?` means unverified); do not promote a `?` claim to a plain assertion, and do not summarise away the agent's stated uncertainty or coverage gaps.

## Serial fallback

If you cannot start a sub-agent, load the `cbt` skill in the current session and follow its operating rules; they replace your own instincts about how to research this topic.
