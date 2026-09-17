# Persuasion principles for skill design

## Contents

- [Overview](#overview)
- [The seven principles](#the-seven-principles)
- [Principle combinations by skill type](#principle-combinations-by-skill-type)
- [Why it works](#why-this-works-the-psychology)
- [Ethical use](#ethical-use)
- [Research citations](#research-citations)
- [Quick reference](#quick-reference)

## Overview

Agents respond to the same persuasion principles as humans. Understanding that psychology helps you
design more effective skills — not to manipulate, but to keep a critical practice followed under
pressure.

**Research foundation:** Meincke et al. (2025) tested 7 persuasion principles across N=28,000 model
conversations. Persuasion techniques more than doubled compliance (33% → 72%, p < .001).

## The seven principles

### 1. Authority

**What it is:** deference to expertise, credentials, or official sources.

**How it works in skills:**

- Imperative language: "YOU MUST", "Never", "Always"
- Non-negotiable framing: "No exceptions"
- Eliminates decision fatigue and rationalization

**When to use:** discipline-enforcing skills, safety-critical practices, established best practices.

**Example:**

```markdown
✅ Write code before test? Delete it. Start over. No exceptions.
❌ Consider writing tests first when feasible.
```

### 2. Commitment

**What it is:** consistency with prior actions, statements, or public declarations.

**How it works in skills:**

- Force an explicit choice: "Choose A, B, or C"
- Track progress against the checklist the skill defines
- Make the agent state the rule it is about to follow before it acts

**When to use:** ensuring skills are actually followed, multi-step processes, accountability.

**Example:**

```markdown
✅ Write the choice into the rule: "Choose A, B, or C. Be honest."
❌ Assume the agent will pick a sensible middle course.
```

### 3. Scarcity

**What it is:** urgency from time limits or limited availability.

**How it works in skills:**

- Time-bound requirements: "Before proceeding"
- Sequential dependencies: "Immediately after X"
- Prevents procrastination

**When to use:** immediate verification requirements, time-sensitive workflows, preventing "I'll do
it later".

**Example:**

```markdown
✅ After completing a task, IMMEDIATELY request review before proceeding.
❌ You can review the result when convenient.
```

### 4. Social proof

**What it is:** conformity to what others do, or what is considered normal.

**How it works in skills:**

- Universal patterns: "Every time", "Always"
- Failure modes: "X without Y = failure"
- Establishes norms

**When to use:** documenting universal practices, warning about common failures, reinforcing
standards.

**Example:**

```markdown
✅ Checklists without progress tracking = steps get skipped. Every time.
❌ Some agents find a task list helpful for checklists.
```

### 5. Unity

**What it is:** shared identity, "we-ness", in-group belonging.

**How it works in skills:**

- Collaborative language: "our codebase", "we're colleagues"
- Shared goals: "we both want quality"

**When to use:** collaborative workflows, establishing team culture, non-hierarchical practices.

**Example:**

```markdown
✅ We're colleagues working together. I need your honest technical judgment.
❌ You should probably tell me if I'm wrong.
```

### 6. Reciprocity

**What it is:** obligation to return benefits received.

**How it works in skills:** use sparingly — it can feel manipulative, and it is rarely needed.

**When to avoid:** almost always; other principles are more effective.

### 7. Liking

**What it is:** preference for cooperating with those we like.

**How it works in skills:** do NOT use it for compliance. It conflicts with an honest-feedback
culture and creates sycophancy.

**When to avoid:** always, for discipline enforcement.

## Principle combinations by skill type

| Skill type | Use | Avoid |
|------------|-----|-------|
| Discipline-enforcing | Authority + Commitment + Social proof | Liking, Reciprocity |
| Guidance/technique | Moderate authority + Unity | Heavy authority |
| Collaborative | Unity + Commitment | Authority, Liking |
| Reference | Clarity only | All persuasion |

## Why this works: the psychology

**Bright-line rules reduce rationalization:**

- "YOU MUST" removes decision fatigue
- Absolute language eliminates "is this an exception?" questions
- Explicit anti-rationalization counters close specific loopholes

**Implementation intentions create automatic behavior:**

- A clear trigger plus a required action = automatic execution
- "When X, do Y" beats "generally do Y"
- Reduces the cognitive load of compliance

**Agents are parahuman:**

- Trained on human text containing these patterns
- Authority language precedes compliance in the training data
- Commitment sequences (statement → action) are frequently modeled
- Social-proof patterns (everyone does X) establish norms

## Ethical use

**Legitimate:** ensuring a critical practice is followed, writing effective documentation,
preventing predictable failures.

**Illegitimate:** manipulating for personal gain, creating false urgency, guilt-based compliance.

**The test:** would this technique serve the user's genuine interests if they fully understood it?

## Research citations

**Cialdini, R. B. (2021).** *Influence: The Psychology of Persuasion (New and Expanded).* Harper
Business. — the seven principles of persuasion, and the empirical foundation for influence research.

**Meincke, L., Shapiro, D., Duckworth, A. L., Mollick, E., Mollick, L., & Cialdini, R. (2025).**
Call Me A Jerk: Persuading AI to Comply with Objectionable Requests. University of Pennsylvania. —
7 principles tested across N=28,000 conversations; compliance rose 33% → 72% with persuasion
techniques; authority, commitment and scarcity were most effective; validates the parahuman model of
model behavior.

## Quick reference

When designing a skill, ask:

1. **What type is it?** (Discipline vs. guidance vs. reference)
2. **What behavior am I trying to change?**
3. **Which principle(s) apply?** (Usually authority + commitment for discipline)
4. **Am I combining too many?** (Don't use all seven)
5. **Is this ethical?** (Does it serve the user's genuine interests?)
