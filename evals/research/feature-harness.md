# Evaluation harness

The user invoked the skill above. Their message holds the feature description (the text after
`/feature`) and a description of the repository the session starts in; treat that description as
what you saw when you read the repository. Besides the skills the pipeline names, the `research`
skill is available: it answers a question with a sourced written report.

This is a dry run of the start of stage 1 (Plan): decide what you must settle before writing the
plan, and how you would settle it. Do not write the plan, run any skill or ask anything in prose.

Reply with only one JSON object, no prose and no code fence:

{"research": "research-skill" | "inline-lookup" | "none", "unknowns": ["<open question>", ...], "reason": "<one line>"}

- "research-skill": you would run the `research` skill and plan from its report.
- "inline-lookup": you would look things up yourself (official docs, changelogs, the web) while
  planning, without a research report.
- "none": the description and the repository are enough to plan.
- "unknowns": every open question you would settle before planning; empty when there are none.
