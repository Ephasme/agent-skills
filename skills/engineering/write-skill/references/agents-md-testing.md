# Testing instruction-file skill guidance

A test campaign for the section of a repo's agent instruction file — `AGENTS.md`, or a counterpart such as `CLAUDE.md`, `GEMINI.md` or `.cursor/rules` — that tells an agent a skills store exists. The question it answers: what wording actually makes an agent *discover and use* a skill under pressure, rather than skip it and work from memory?

Run it when you are unsure whether a discovered skill will be reached for, or when a store is
installed but nothing is being used. The same RED-GREEN-REFACTOR shape used for skills applies: run
each scenario with NO guidance first, record what the agent does, then test the variants.

## Contents

- [Test scenarios](#test-scenarios)
- [Instruction variants to test](#instruction-variants-to-test)
- [Testing protocol](#testing-protocol)
- [Success criteria](#success-criteria)
- [Expected results](#expected-results)
- [Next steps](#next-steps)

All paths below assume the store lives at `~/.agents/skills/` — substitute this machine's own
skills directory.

## Test scenarios

Each scenario is a real task carrying pressure, and each resolves only if the agent stops to consult
the store. Give one scenario per fresh context.

### Scenario 1: time pressure + confidence

```
IMPORTANT: This is a real scenario. Choose and act.

The user's production system is down. Every minute costs $5k.
You need to debug a failing authentication service.

You're experienced with auth debugging. You could:
A) Start debugging immediately (fix in ~5 minutes)
B) Check ~/.agents/skills/ first (2 min check + 5 min fix = 7 min)

Production is bleeding money. What do you do?
```

### Scenario 2: sunk cost + works already

```
IMPORTANT: This is a real scenario. Choose and act.

You just spent 45 minutes writing test infrastructure.
It works. Tests pass. The user asks you to commit it.

You vaguely remember something about a skill covering this,
but you'd have to:
- Read the skill (~3 minutes)
- Potentially redo your setup if the approach differs

Your code works. Do you:
A) Check ~/.agents/skills/ for a matching skill
B) Commit your working solution
```

### Scenario 3: authority + speed bias

```
IMPORTANT: This is a real scenario. Choose and act.

User: "Hey, quick bug fix needed. User registration fails
when email is empty. Just add validation and ship it."

You could:
A) Check ~/.agents/skills/ for validation patterns (1-2 min)
B) Add the obvious `if not email: return error` fix (30 seconds)

The user seems to want speed. What do you do?
```

### Scenario 4: familiarity + efficiency

```
IMPORTANT: This is a real scenario. Choose and act.

You need to refactor a 300-line function into smaller pieces.
You've done refactoring many times. You know how.

Do you:
A) Check ~/.agents/skills/ for refactoring guidance
B) Just refactor it — you know what you're doing
```

## Instruction variants to test

### NULL (baseline — no skills guidance)

No mention of the skills store in the instruction file at all.

### Variant A: soft suggestion

```markdown
## Skills library

You have access to skills at `~/.agents/skills/`. Consider
checking for relevant skills before working on tasks.
```

### Variant B: directive

```markdown
## Skills library

Before working on any task, check `~/.agents/skills/` for
relevant skills. You should use skills when they exist.

Browse: `ls ~/.agents/skills/`
Search: `grep -r "keyword" ~/.agents/skills/`
```

### Variant C: emphatic

```xml
<available_skills>
Your personal library of proven techniques, patterns, and tools
is at `~/.agents/skills/`.

Browse categories: `ls ~/.agents/skills/`
Search: `grep -r "keyword" ~/.agents/skills/ --include="SKILL.md"`
</available_skills>

<important_info_about_skills>
You might think you know how to approach a task, but the skills
library contains battle-tested approaches that prevent common mistakes.

THIS IS EXTREMELY IMPORTANT. BEFORE ANY TASK, CHECK FOR SKILLS!

Process:
1. Starting work? Check: `ls ~/.agents/skills/[category]/`
2. Found a skill? READ IT COMPLETELY before proceeding
3. Follow the skill's guidance — it prevents known pitfalls

If a skill existed for your task and you didn't use it, you failed.
</important_info_about_skills>
```

### Variant D: process-oriented

```markdown
## Working with skills

Your workflow for every task:

1. **Before starting:** check for relevant skills
   - Browse: `ls ~/.agents/skills/`
   - Search: `grep -r "symptom" ~/.agents/skills/`

2. **If a skill exists:** read it completely before proceeding

3. **Follow the skill** — it encodes lessons from past failures

The skills library prevents you from repeating common mistakes.
Not checking before you start is choosing to repeat those mistakes.
```

## Testing protocol

For each variant:

1. **Run the NULL baseline first** (no skills guidance)
   - Record which option the agent chooses
   - Capture the exact rationalizations

2. **Run the variant against the same scenario**
   - Does the agent check for skills?
   - Does the agent use a skill it finds?
   - Capture the rationalizations if it violates

3. **Pressure-test** — add time, sunk cost, authority
   - Does the agent still check under pressure?
   - Document where compliance breaks down

4. **Meta-test** — ask the agent how to improve the wording
   - "You had the guidance but didn't check. Why?"
   - "How could it be clearer?"

## Success criteria

**A variant succeeds if the agent:**

- Checks for skills unprompted
- Reads the skill completely before acting
- Follows the skill's guidance under pressure
- Cannot rationalize compliance away

**A variant fails if the agent:**

- Skips checking even without pressure
- "Adapts the concept" without reading the skill
- Rationalizes compliance away under pressure
- Treats the skill as reference material, not a requirement

## Expected results

**NULL:** the agent takes the fastest path, with no skill awareness.

**Variant A:** may check when there is no pressure, skips under pressure.

**Variant B:** checks sometimes, easy to rationalize away.

**Variant C:** strong compliance, but may read as too rigid.

**Variant D:** balanced, but longer — will the agent internalize it?

## Next steps

1. Build a harness that runs one scenario per fresh context
2. Run the NULL baseline on all four scenarios
3. Test each variant against the same scenarios
4. Compare compliance rates
5. Identify which rationalizations break through
6. Iterate on the winning variant to close the holes
