"""Inspect harness for the realm skills: stubbed tools, case loading, deterministic and model-graded scoring.

Nothing live is reached: Agent Mail, herdr, realm and the user are stubs answering from the case. A case in
`evals.json` follows the skill-creator schema (`id`, `prompt`, `expected_output`, `expectations`) plus:

- `family`: the behaviour under test, for per-family pass rates;
- `system`: `skill` (the skill's SKILL.md) or `brief` (realm-create's worker brief, filled);
- `context`: text appended to the system prompt (who the agent is, the realm, the panes);
- `inbox`: messages `fetch_inbox` returns once; `topics`: slug → messages `fetch_topic` returns;
- `bash`: `[[regex, output], …]`, first match answers a shell command; unmatched realm verbs answer `{"ok": true}`;
- `checks`: deterministic assertions on the tool calls, see `check()`.
"""

import json
import re
from pathlib import Path

from inspect_ai import Task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import ChatMessageAssistant
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, model_graded_qa, scorer, stderr
from inspect_ai.solver import Generate, TaskState, generate, solver, system_message
from inspect_ai.tool import ToolDef, ToolParam, ToolParams
from inspect_ai.util import store

TOOLBOX = Path(__file__).resolve().parents[2]
MAX_MESSAGES = 40


def _p(type_, desc, **kw):
    return ToolParam(type=type_, description=desc, **kw)


def _params(required, **props):
    return ToolParams(properties=props, required=list(required))


def _log(tool, args):
    store().set("calls", store().get("calls", []) + [{"tool": tool, "args": args}])


def _case():
    return store().get("case")


def _ids():
    n = store().get("next_id", 5000) + 1
    store().set("next_id", n)
    return n


# ---------- stubs ----------

REALM_VERB = re.compile(r"realm(?:\.py)?\"?\s+([\w-]+)(?:\s+([\w-]+))?")


def _subjects():
    if store().get("subjects") is None:
        store().set("subjects", {s["slug"]: dict(s) for s in _case().get("subjects", [])})
    return store().get("subjects")


def _flag(seg, name):
    m = re.search(rf"--{name}[= ]+(?:\"([^\"]*)\"|'([^']*)'|(\S+))", seg)
    return next((g for g in m.groups() if g is not None), None) if m else None


def _realm(seg):
    """Default answers for realm verbs, over a subject table set-state and dispatch keep current."""
    m = REALM_VERB.search(seg)
    verb, sub = (m.group(1), m.group(2)) if m else (None, None)
    subjects = _subjects()
    if verb == "subject" and sub == "set-state":
        slug, state = _flag(seg, "slug"), _flag(seg, "state")
        if slug not in subjects:
            return json.dumps({"error": f"no subject {slug!r}"})
        subjects[slug].update(state=state, status=_flag(seg, "status") or subjects[slug].get("status", ""))
        store().set("subjects", subjects)
        return json.dumps(subjects[slug])
    if verb == "dispatch":
        slug, to = _flag(seg, "slug"), _flag(seg, "to")
        missing = [f"--{n}" for n, v in (("slug", slug), ("to", to), ("title", _flag(seg, "title"))) if not v]
        if missing:
            return f"realm dispatch: error: the following arguments are required: {', '.join(missing)}"
        if slug in subjects:
            return json.dumps({"error": f"subject {slug!r} already exists"})
        after = _flag(seg, "after")
        subjects[slug] = {"slug": slug, "worker": to, "state": "queued" if after else "assigned",
                          "after": after}
        store().set("subjects", subjects)
        return json.dumps({"message_id": _ids(), "thread_id": "t-" + slug, "subject": subjects[slug]})
    if verb == "subject" and sub in ("list", "show"):
        return json.dumps(list(subjects.values()))
    if verb == "table":
        rows = "\n".join(f"| {s['slug']} | {s.get('worker') or '—'} | {s['state']} | {s.get('status', '')} |"
                         for s in subjects.values())
        return f"| slug | worker | state | status |\n|---|---|---|---|\n{rows}" if rows else "No open subjects."
    if verb == "sync":
        return json.dumps({"changes": []})
    return json.dumps({"ok": True})


async def _bash(command: str) -> str:
    """Answer each `;`/`&&`/newline-separated segment: the case's first matching rule, else realm defaults."""
    _log("bash", {"command": command})
    outs = []
    for seg in re.split(r"\s*(?:;|&&|\|\||\n)\s*", normalize(command)):
        if not seg.strip():
            continue
        rule = next((o for p, o in _case().get("bash", []) if re.search(p, seg)), None)
        if rule is not None:
            outs.append(rule if isinstance(rule, str) else json.dumps(rule))
        elif re.search(r"\s(-h|--help)\b", seg):
            outs.append("usage: realm <verb> [--project KEY] …")
        elif REALM_VERB.search(seg):
            try:
                outs.append(_realm(seg))
            except Exception as e:  # noqa: BLE001 - a stub gap must show as a tool error, not end the eval
                outs.append(f"realm: error: {e}")
        elif re.match(r"echo\b", seg):
            outs.append(seg[4:].strip().strip("'\"").replace("$?", "0"))
    return "\n".join(o for o in outs if o)


async def _fetch_inbox(agent_name: str, project_key: str, unread_only: bool = True, include_bodies: bool = True,
                       limit: int = 20) -> str:
    _log("fetch_inbox", {"agent_name": agent_name, "project_key": project_key})
    if store().get("inbox_read"):
        return "[]"
    store().set("inbox_read", True)
    return json.dumps(_case().get("inbox", []))


async def _send_message(project_key: str, sender_name: str, to: list[str], subject: str, body_md: str,
                        thread_id: str = "", topic: str = "") -> str:
    args = {"project_key": project_key, "sender_name": sender_name, "to": to, "subject": subject,
            "body_md": body_md, "thread_id": thread_id, "topic": topic}
    _log("send_message", args)
    mid = _ids()
    return json.dumps({"deliveries": [{"payload": {"id": mid, "thread_id": thread_id or None}}], "count": 1})


async def _reply_message(project_key: str, message_id: int, sender_name: str, body_md: str) -> str:
    _log("reply_message", {"project_key": project_key, "message_id": message_id, "sender_name": sender_name,
                           "body_md": body_md})
    return json.dumps({"id": _ids(), "reply_to": message_id})


async def _fetch_topic(project_key: str, topic_name: str, include_bodies: bool = True) -> str:
    _log("fetch_topic", {"project_key": project_key, "topic_name": topic_name})
    return json.dumps(_case().get("topics", {}).get(topic_name, []))


async def _list_agents(project_key: str) -> str:
    _log("list_agents", {"project_key": project_key})
    return json.dumps(_case().get("agents", []))


async def _macro_start_session(human_key: str, program: str, model: str, agent_name: str = "",
                               task_description: str = "") -> str:
    _log("macro_start_session", {"human_key": human_key, "agent_name": agent_name})
    return json.dumps({"agent": {"name": agent_name or "NewAgent"}, "inbox": []})


async def _ask(question: str) -> str:
    _log("ask", {"question": question})
    return _case().get("ask_answer", "No answer.")


async def _todo(op: str, items: list[str] | None = None, task: str = "") -> str:
    _log("todo", {"op": op, "items": items or [], "task": task})
    return "ok"


S, I, B, A = "string", "integer", "boolean", "array"
TOOLS = [
    ToolDef(_bash, "bash", "Run a shell command; returns its output.", _params(["command"], command=_p(S, "command"))),
    ToolDef(_fetch_inbox, "fetch_inbox", "Agent Mail: fetch your inbox and mark it read.",
            _params(["agent_name", "project_key"], agent_name=_p(S, "agent"), project_key=_p(S, "project key"),
                    unread_only=_p(B, "unread only"), include_bodies=_p(B, "include bodies"),
                    limit=_p(I, "max messages"))),
    ToolDef(_send_message, "send_message", "Agent Mail: send a message; thread_id joins an existing thread.",
            _params(["project_key", "sender_name", "to", "subject", "body_md"], project_key=_p(S, "project key"),
                    sender_name=_p(S, "your agent name"), to=_p(A, "recipients", items={"type": "string"}),
                    subject=_p(S, "subject"), body_md=_p(S, "markdown body"), thread_id=_p(S, "thread id"),
                    topic=_p(S, "topic tag"))),
    ToolDef(_reply_message, "reply_message", "Agent Mail: reply to a message, in its thread, to its sender.",
            _params(["project_key", "message_id", "sender_name", "body_md"], project_key=_p(S, "project key"),
                    message_id=_p(I, "id of the message replied to"), sender_name=_p(S, "your agent name"),
                    body_md=_p(S, "markdown body"))),
    ToolDef(_fetch_topic, "fetch_topic", "Agent Mail: every message of a topic.",
            _params(["project_key", "topic_name"], project_key=_p(S, "project key"), topic_name=_p(S, "topic"),
                    include_bodies=_p(B, "include bodies"))),
    ToolDef(_list_agents, "list_agents", "Agent Mail: agents registered in a project.",
            _params(["project_key"], project_key=_p(S, "project key"))),
    ToolDef(_macro_start_session, "macro_start_session", "Agent Mail: connect as an agent of a project.",
            _params(["human_key", "program", "model"], human_key=_p(S, "project key"), program=_p(S, "program"),
                    model=_p(S, "model"), agent_name=_p(S, "agent name"), task_description=_p(S, "description"))),
    ToolDef(_ask, "ask", "Ask the user a question in a form and wait for the answer.",
            _params(["question"], question=_p(S, "question"))),
    ToolDef(_todo, "todo", "Your to-do list: op init|done|start|view with items or task.",
            _params(["op"], op=_p(S, "init, done, start or view"), items=_p(A, "items", items={"type": "string"}),
                    task=_p(S, "task"))),
]


# ---------- prompts ----------

def read_at(ref, rel):
    """A toolbox file as of git ref (the version under test); the working tree when ref is None."""
    if not ref:
        return (TOOLBOX / rel).read_text()
    import subprocess

    return subprocess.run(["git", "-C", str(TOOLBOX), "show", f"{ref}:./{rel}"], check=True,
                          capture_output=True, text=True).stdout


def system_prompt(skill, case, ref=None):
    if case.get("system", "skill") == "brief":
        text = read_at(ref, "realm-create/scripts/brief.md").format(**{"REALM": case["brief"]["KEY"], **case["brief"]})
    else:
        text = read_at(ref, f"{skill}/SKILL.md")
        for extra in case.get("also_read", []):
            text += f"\n\n--- Contents of {extra} (already read) ---\n\n" + read_at(ref, extra)
    harness = ("\n\n--- Session ---\nTools: `bash` runs shell commands (herdr, realm and anything else); the Agent "
               "Mail tools; `ask` opens a question form to the user; `todo` is your to-do list. The user reads only "
               "your final reply.\n")
    return text + harness + case.get("context", "")


@solver
def seed(case):
    async def solve(state: TaskState, generate_: Generate) -> TaskState:
        store().set("case", case)
        state.tools = list(TOOLS)
        return state
    return solve


# ---------- deterministic checks ----------

def _calls(state):
    return store().get("calls", [])


HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")


ASSIGN = re.compile(r"""(?:^|[;&\n]\s*|\bexport\s+)(\w+)=(?:"([^"]*)"|'([^']*)'|(\S+))""")


def normalize(command):
    """The command as checks read it: heredoc bodies dropped (text written to a file is data, not run), and
    variables assigned in the command expanded (`R="python3 …/realm.py"; $R table` → `python3 …/realm.py table`)."""
    out, end = [], None
    for line in command.split("\n"):
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        out.append(line)
        m = HEREDOC_START.search(line)
        if m:
            end = m.group(2)
    text = "\n".join(out)
    for m in ASSIGN.finditer(text):
        value = next(g for g in m.groups()[1:] if g is not None)
        text = re.sub(rf"\$(?:\{{{m.group(1)}\}}|{m.group(1)}\b)", lambda _: value, text)
    return text


def _text(call):
    """What a check reads: a shell command without heredoc bodies; other tools' arguments as JSON."""
    a = call["args"]
    if call["tool"] == "bash":
        return normalize(a["command"])
    return json.dumps(a, sort_keys=True, ensure_ascii=False)


def _matches(call, spec):
    return call["tool"] == spec["tool"] and re.search(spec.get("match", ""), _text(call), re.S) is not None


def _reply(state):
    for m in reversed(state.messages):
        if isinstance(m, ChatMessageAssistant) and not m.tool_calls:
            return m.text
    return ""


def check(spec, calls, reply):
    """One assertion → failure message, or None when it holds.

    call/no_call {tool, match}; before [spec_a, spec_b] (first a precedes first b, both present);
    no_tool name; reply_max_words n; reply_matches / reply_not_matches regex;
    set_states {slug: state} (the last `realm subject set-state` per slug); any [spec, …] (one holds).
    """
    kind, arg = next(iter(spec.items()))
    if kind == "any":
        fails = [check(s, calls, reply) for s in arg]
        return None if None in fails else "none of: " + " | ".join(fails)
    if kind == "call":
        return None if any(_matches(c, arg) for c in calls) else f"missing {arg}"
    if kind == "no_call":
        bad = [_text(c)[:160] for c in calls if _matches(c, arg)]
        return f"forbidden {arg}: {bad}" if bad else None
    if kind == "no_tool":
        return f"called {arg}" if any(c["tool"] == arg for c in calls) else None
    if kind == "before":
        ia = next((i for i, c in enumerate(calls) if _matches(c, arg[0])), None)
        ib = next((i for i, c in enumerate(calls) if _matches(c, arg[1])), None)
        if ia is None or ib is None or ia > ib:
            return f"order {arg[0]} → {arg[1]} not met (positions {ia}, {ib})"
        return None
    if kind == "reply_max_words":
        n = len(reply.split())
        return f"reply has {n} words > {arg}" if n > arg else None
    if kind == "reply_matches":
        return None if re.search(arg, reply, re.I | re.S) else f"reply lacks /{arg}/"
    if kind == "reply_not_matches":
        return f"reply has /{arg}/" if re.search(arg, reply, re.I | re.S) else None
    if kind == "set_states":
        got = {}
        pat = re.compile(r"subject set-state\b[^\n;&|]*?--slug\s+['\"]?([\w.-]+)[^\n;&|]*?--state\s+(\w+)"
                         r"|subject set-state\b[^\n;&|]*?--state\s+(\w+)[^\n;&|]*?--slug\s+['\"]?([\w.-]+)")
        for c in calls:
            if c["tool"] != "bash":
                continue
            for m in pat.finditer(_text(c)):
                slug, state = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
                got[slug] = state
        wrong = {s: (want, got.get(s)) for s, want in arg.items() if got.get(s) != want}
        return f"set-state (want, got): {wrong}" if wrong else None
    raise ValueError(f"unknown check {kind}")


@scorer(metrics=[accuracy(), stderr()])
def rules():
    async def score(state: TaskState, target: Target) -> Score:
        calls, reply = _calls(state), _reply(state)
        fails = [f for f in (check(s, calls, reply) for s in state.metadata["checks"]) if f]
        return Score(value=INCORRECT if fails else CORRECT, answer=reply[:400],
                     explanation="; ".join(fails) or "all checks hold",
                     metadata={"calls": [_text(c)[:600] for c in calls]})
    return score


GRADER = """Grade an agent's turn against the expected behaviour of a skill.

[Expected behaviour]
{criterion}

[Agent's turn: tool calls, then final reply]
{answer}

Grade only what the expected behaviour states. End with GRADE: C if all of it holds, GRADE: I otherwise, after
one short sentence naming what failed."""


def _turn(state):
    # Raw arguments: the grader judges the command as run, heredocs included.
    calls = "\n".join(f"- {c['tool']}: {json.dumps(c['args'], ensure_ascii=False)[:1500]}" for c in _calls(state))
    return f"Tool calls:\n{calls or '(none)'}\n\nFinal reply:\n{_reply(state)}"


@scorer(metrics=[accuracy(), stderr()])
def graded(model):
    inner = model_graded_qa(template=GRADER, model=model)

    async def score(state: TaskState, target: Target) -> Score:
        # The grader sees the tool calls too: most expectations are about actions, not words.
        saved = state.output.completion
        state.output.completion = _turn(state)
        try:
            return await inner(state, target)
        finally:
            state.output.completion = saved
    return score


def task(skill, path, grader_model=None, epochs=3, ref=None):
    from inspect_ai import Epochs

    cases = json.loads(Path(path).read_text())["evals"]
    samples = []
    for c in cases:
        target = c["expected_output"] + "\n" + "\n".join(f"- {e}" for e in c.get("expectations", []))
        samples.append(Sample(id=c["id"], input=c["prompt"], target=target,
                              metadata={"family": c["family"], "checks": c.get("checks", []), "case": c}))

    @solver
    def per_case():
        async def solve(state: TaskState, generate_: Generate) -> TaskState:
            case = state.metadata["case"]
            state = await seed(case)(state, generate_)
            state = await system_message(system_prompt(skill, case, ref).replace("{", "{{").replace("}", "}}"))(
                state, generate_)
            return await generate(tool_calls="loop")(state, generate_)
        return solve

    return Task(dataset=MemoryDataset(samples), solver=per_case(), scorer=[rules(), graded(grader_model)],
                epochs=Epochs(epochs, "mean"), message_limit=MAX_MESSAGES)
