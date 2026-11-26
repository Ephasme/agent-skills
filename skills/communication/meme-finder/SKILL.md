---
name: "meme-finder"
description: "Find up to 5 meme templates matching a mood, sentence or Slack message, with official imgflip names and working imgflip links, verified through Exa. Use for any 'what meme fits this' ask."
---

# Meme finder

Given a mood, a sentence, or a pasted Slack message (French or English), return up to 5 meme templates that fit, each with its **official imgflip name** and a **working imgflip link**.

**All web lookups in this skill go through Exa.** Do not use any other search or fetch tool, curl included, even as a fallback.

## 0. Make sure Exa is available

The Exa tools are `mcp__Exa__web_fetch_exa` and `mcp__Exa__web_search_exa`. If your agent loads tools on demand, load both before starting.

If they are not available at all, stop. Tell the user in one line that this skill needs the Exa MCP connector. Do not fall back to other tools.

## 1. Read the situation, not just the words

Memes match the *shape* of a situation more than its keywords. Before picking anything, name to yourself:
- **Emotion**: smug, panicked, betrayed, resigned, petty, overwhelmed, quietly proud, fake-calm, relieved...
- **Structure**: a choice between two things, a preference (this not that), escalation, a plan that backfires, a hypocrisy, a reveal, an obvious truth nobody wants to hear, being ignored, agreeing across a divide, before/after, a close call.
- **Context**: work/Slack banter, dev/IT life, deadline, meeting, prod incident, Monday...

If the input is a Slack message, find the beat that's funny (the irony, the pain point, the plot twist) and match that.

## 2. Get the official names and IDs from imgflip via Exa

Fetch the live top-100 template list with Exa:

- `mcp__Exa__web_fetch_exa` with `urls: ["https://api.imgflip.com/get_memes"]` and `maxCharacters: 40000` (the default 3000 truncates the list).
- Read every template's `id`, `name` and `box_count` from the JSON.

The `name` field is the official name. Use it **verbatim** (capitalization, punctuation and all). `box_count` tells you how many text panels the template has.

If the best fit isn't in the top 100, use `mcp__Exa__web_search_exa` to find its imgflip template page, e.g. query `imgflip meme template page for "<template name>"` with an objective asking for imgflip.com/meme/ or imgflip.com/memegenerator/ pages first. If highlights don't confirm the name and URL, `mcp__Exa__web_fetch_exa` the best imgflip URL (an imgflip.com/i/ page also names its template and links to it). **Never invent a name, ID or URL.** If you can't verify a template through Exa, drop it.

## 3. Pick up to 5

- Rank best fit first.
- Make them **genuinely different angles** (e.g. one panic, one irony, one resigned acceptance), not five variants of the same joke.
- Fewer than 5 is fine if only 2-3 really fit. Don't pad.
- Default to workplace-safe. If a pick is edgy, say so in a few words.

Rough mood-to-template cheat sheet (names only; always confirm against the API):
- Preference / this not that → Drake Hotline Bling, Buff Doge vs. Cheems
- Hard choice → Two Buttons, Left Exit 12 Off Ramp
- Temptation / distraction → Distracted Boyfriend
- Everything's on fire, pretending it's fine → This Is Fine, Panik Kalm Panik
- Close call / lucky escape → Panik Kalm Panik, Left Exit 12 Off Ramp, Success Kid (not in top 100, verify via Exa search)
- Refusing the obvious fix → UNO Draw 25 Cards
- Plan that backfires → Gru's Plan
- Escalating cleverness / galaxy brain → Expanding Brain
- Awkward silence / pretending not to see → Monkey Puppet
- Smug or obvious truth → Roll Safe Think About It, Change My Mind, Always Has Been
- Waiting forever → Waiting Skeleton
- Mocking a statement → Mocking Spongebob
- Shut down an idea → Batman Slapping Robin
- Two groups agreeing → Epic Handshake
- Hidden pain behind a smile → Hide the Pain Harold
- Asking again → Bernie I Am Once Again Asking For Your Support
- Exchange / deal → Trade Offer
- Misidentifying something → Is This A Pigeon
- Unexpected consequence → Surprised Pikachu
- Missing something / lonely → Sad Pablo Escobar

## 4. Build the links

Use the meme generator link, which lets the user caption it right away:

`https://imgflip.com/memegenerator/{id}/{Slug}`

- `{id}` comes from the API (this is what routes the page).
- `{Slug}` = the official name with punctuation removed and spaces replaced by hyphens (e.g. `Drake Hotline Bling` → `Drake-Hotline-Bling`).
- If a template came from an Exa search or fetch instead of the API, use the imgflip URL found there as-is.

## 5. Output

Reply in the language of the input. Keep it compact and Slack-friendly, no preamble:

```
1. **<Official Name>** — <link>
   Why: <one short line on why it fits>
   Caption: <panel 1> / <panel 2> (match box_count)
```

- The caption is a ready-to-use suggestion tied to the user's actual situation, short and punchy.
- Don't embed or reproduce the images; the links are enough.
- End with nothing, or at most one line offering to tweak captions or find a different vibe.