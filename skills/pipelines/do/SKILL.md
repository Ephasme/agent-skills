---
name: do
description: >-
  Routes a request to the pipeline skills that carry it to the end: reads it just enough to tell a
  question from a bug, a feature or a product-scale endeavour, announces a route made of research,
  bugfix, feature and campaign, alone or chained (research then feature, bugfix then feature,
  research then campaign), and runs each skill in turn, handing each one what the previous one
  produced. Use when the user invokes /do followed by a request and leaves the choice of pipeline
  to the agent.
disable-model-invocation: true
---

# Do

Explicit invocation only: the text after `/do` is the request. Route it to the pipeline skills that
carry it to the end, then run them in turn without handing control back between them; the user
asked for the whole thing.

Empty request → ask for it, then start.

## Track the route

Before any work, create this todo list, each item verbatim, and keep it current. Mark an item done
only when the outcome after its colon holds. Routing appends the rest.

```text
0. Route: request read, route announced
```

Once the route is announced, append one item per skill run, in route order, numbered from 1:

```text
N. Research: report published
N. Bugfix: fix merged
N. Feature: pull requests merged
N. Campaign: stack merged
```

Each skill creates its own todo list, which would replace this one and drop the rest of the route.
When a skill starts, insert its items right after its route item instead, flattening any groups and
prefixing each item's number with `N.` (`2.1 Plan: plan written`, `3.5.01 <feature-slug>:
integrated, pull request opened`), and remove them once the skill reports.

## Route the request

Understand the request only as far as routing needs: what the user wants to end up with, and
whether it is a question, a defect, one change or many. Read the request and anything it points to
(a link, a file, an error); glance at the repository only to place it. The routed skills do the
deep reading in their own first stage; reading more here duplicates it.

| Skill | Route to it when the request |
|---|---|
| `research` | asks a question whose answer deserves a sourced document, or depends on an unknown that only outside sources settle: a library or vendor choice, a protocol's or a law's behaviour |
| `bugfix` | reports existing behaviour that contradicts what it should do: an error, a failing test, a regression, an issue describing a defect |
| `feature` | asks for one capability that does not exist yet (a new endpoint, a screen, an integration), or for a few huge but simple tasks (a refactor, a rewrite, a framework or language migration, an upgrade), within one repository or coordinated across two or three. Size alone never rules it out: thousands of lines are still a feature when the work is one task, or a few, applied across the code |
| `campaign` | asks for many distinct pieces of work: lots of tasks in one repository, an epic whose features land in different and almost unrelated parts of the codebase, or a whole application or product, often across several repositories (`build me an app that manages my invoices`, `build a billing platform with an API, a dashboard and a mobile client`) |

Breadth earns `campaign`, size does not: count the distinct pieces of work and how unrelated the
parts of the codebase they touch are, not the lines they change. `campaign` is the rare route: it
costs an epic interview, a stacked-PR chain and hours of runtime. Default to `feature` and pick
`campaign` only when the request clearly holds many distinct pieces of work. Vagueness is not
breadth: a vague request for one capability is a `feature`, which plans it itself. Between these
two, decide without asking.

Chain skills when the request needs more than one, in this order: `research` first, since its answer
shapes everything after it; then `bugfix`, since new work should build on fixed code; then
`feature` or `campaign`. Never chain `feature` and `campaign` on the same scope: a campaign runs
`feature` once per feature itself. The same skill may appear twice for independent parts, such as
two unrelated bugs.

An unknown the code can answer is not research: `feature` and `bugfix` read the code themselves.
A request that only asks a question gets `research` alone, even when the answer suggests a change.

When two routes would do substantially different work and the request does not settle which, ask
one question with the routes you see and the one you recommend; use a structured multiple-choice
prompt where the agent has one. Otherwise announce the route in one line with its reason
(`Route: research → feature. Which queue library to use is open; the feature depends on it.`) and
start.

## Run the route

Run each skill of the route in order, with its own invocation text: the part of the request it
carries, plus what earlier skills produced. Where the agent cannot load a skill reserved for
explicit invocation on its own, read that skill's `SKILL.md` and follow it.

Between two skills, hand over:

- **After `research`.** Pass the report's answer and path to the next skill. If the answer removes
  the reason for what comes next (the thing already exists, the premise is false, the recommended
  option is to do nothing), stop and report instead of building on it.
- **After `bugfix`.** The next skill starts from the default branch once the fix has merged, so it
  builds on fixed code.
- **After `feature` or `campaign`.** Nothing follows them in a route; they are its last step.

Each skill keeps its own stop conditions and user gates, such as `campaign`'s epic approval. A skill
that stops on a blocker stops the route: skills after it depend on its result.

## Stop conditions

Stop and report only when a routed skill stops on a blocker, or when a `research` answer removes the
reason for the rest of the route. Report what the skills before it produced.

## Report

- The route taken and why, in one line.
- Per skill run: its report, condensed to what the user acts on, with its links.
- Anything left unverified, and the skills of the route that did not run, with why.
