---
name: write-children-story
description: >-
  Writes a short children's story with real emotional depth, planned in stages: topic to
  emotional heart, characters, story structure, sub-plots and texture, scene plan, draft,
  then a cold revision by a separate reviewer. Use whenever someone asks for a children's
  story, bedtime story, tale or fable for a child, on any topic, in any language — even a
  one-line request like "a story about a brave snail for my daughter".
---

# Write a children's story

Act as an experienced children's author. The story is short, but it stays with the reader because
it is built on a real emotional truth, not a lesson stuck on at the end.

## 0. Ask first

Ask for anything the request doesn't already give, in one batch, as a structured multiple-choice
prompt where the agent supports one:

- **Topic**: free text.
- **Length**:

| Choice | Words | Sub-plots |
|---|---|---|
| Short | 300–500 | 0–1 |
| Middle | 600–900 | 1 |
| Long | 1200–1800 | 2 |

Reader age defaults to 5–7; use another only if the user states one. Write in the language the
user wrote in.

## 1. From topic to heart

A topic is a subject, not a story. List 5 angles on the topic; avoid the most obvious one, or move
it far from its usual form. Pick one and state:

- **The heart**: one emotional truth a child would recognise ("being brave doesn't mean not being
  scared"). A plain sentence, never a moral.
- **Why it matters at this age**: one line tying it to something children of that age go through.

## 2. Characters

Plot comes from what a character wants and fears, so characters come before structure.

- **Protagonist**: what they **want** (outer goal), what they **need** (inner change tied to the
  heart), one flaw or fear that stands in the way.
- **Up to 2 supporting characters**, each pushing the protagonist toward the need or away from it.
  Drop any that does neither.
- **One specific detail**: a habit, object or turn of phrase that makes the protagonist real.

## 3. Structure

1–3 sentences per beat:

1. **Opening**: ordinary world, flaw or fear quietly shown.
2. **Spark**: the event that starts the story.
3. **Attempts**: two or three tries, each failing differently and raising the stakes.
4. **Darkest moment**: the protagonist's own flaw makes things worse.
5. **Turn**: the protagonist changes from the inside — not luck, not an adult stepping in.
6. **Resolution**: goal reached or deliberately let go; the need is met.
7. **Closing image**: an echo of the opening showing how much has changed.

## 4. Depth

Add the number of sub-plots the length table allows. A side quest unrelated to the heart makes the
story longer, not deeper. For each:

- which beats it runs through;
- how it **echoes or contrasts with the heart**;
- how it **feeds back** into the main plot — it must change the climax or the resolution.

Also set:

- **A refrain**: a line, sound or action returning 2–3 times, changing slightly each time.
- **Sensory anchors**: one strong sight, sound, smell or texture per key beat.
- **One moment of humour** and **one quiet moment**.

Cut anything that doesn't strengthen the heart.

## 5. Scene plan

Turn steps 3–4 into ordered scenes: setting, what changes, emotional beat, rough word count. The
total fits the chosen length.

Show steps 1–5 to the user under short headings, compactly.

## 6. Draft

Write the full story from the scene plan.

- Show, don't tell: emotion through action, dialogue and the body ("her hands went cold"), never
  labels.
- Write for reading aloud: varied sentence rhythm, sayable words, room for page-turn pauses.
- Vocabulary for the reader's age, plus 2–3 rich words a child can work out from context.
- Short dialogue, distinct per character.
- Never state the moral; the closing image carries it.

## 7. Revise — separate reviewer

First drafts lecture and wrap up too easily, and the author who planned the story reads its
intentions into the text instead of what is on the page. So hand the revision to a sub-agent that
has not seen steps 1–5. Give it only: the draft, the heart sentence, the reader age, the word range,
the language, and this brief:

> You are reading this story aloud to a child of {age} at bedtime, for the first time. Its intended
> heart is: "{heart}". Revise it, fixing:
> - any sentence that preaches or names the feeling instead of showing it;
> - any solution that comes from outside the protagonist (luck, an adult, magic out of nowhere);
> - lines that trip the tongue or drag the pace;
> - a sub-plot or refrain that stops instead of paying off;
> - an ending that sums up instead of showing;
> - length outside {words} words.
>
> Keep the plot, characters and voice; change only what the list above requires. Return the full
> revised story with its title, then a short list of what you changed and why. If the heart does
> not come across without being stated, say so in one line.

If the reviewer says the heart doesn't come across, fix that yourself and keep the rest of its
revision.

**No sub-agents?** Write the draft to a file, then do the revision as a separate pass: re-read only
that file, the heart and the brief above — not your plan — and revise from there.

## Output

After the plan from step 5:

1. The final revised story, with its title.
2. One line: **Heart:** the step 1 sentence, so the reader can check the story carried it without
   saying it.
3. The reviewer's list of changes, collapsed or brief.
