"""Swarm verbs against fake herdr and fake Agent Mail: `python3 -m unittest test_swarm`. No network, no sleeps."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from realmlib import daemon, db, herdr as herdr_mod, state, swarm

KEY = "/test/swarm"
OTHER = "/test/other"


class FakeHerdr:
    """Workspaces hold tabs, tabs hold panes. The queen starts alone in workspace `w`, tab `w:t0`, pane `w:p0`."""

    def __init__(self):
        self.workspaces = {"w": {"label": "home"}}
        self.tabs = {"w:t0": {"label": "shell", "ws": "w", "panes": ["w:p0"]}}
        self.panes = {"w:p0": {"tab_id": "w:t0", "workspace_id": "w", "agent": "omp", "agent_status": "idle"}}
        self.alias = {}  # old pane id → new one, as herdr keeps after `pane move`
        self.typed = []
        self.ran = []
        self.n = 0

    def add_tab(self, ws, label):
        """A tab with one pane in an existing workspace, the way realm opened workers before workspaces."""
        self.n += 1
        tab, p = f"{ws}:t{self.n}", f"{ws}:p{self.n}"
        self.tabs[tab] = {"label": label, "ws": ws, "panes": [p]}
        self.panes[p] = {"tab_id": tab, "workspace_id": ws, "agent": None, "agent_status": "unknown"}
        return tab, p

    def _close_tab(self, tab):
        for p in self.tabs.pop(tab)["panes"]:
            self.panes.pop(p, None)

    def __call__(self, *args):
        cmd = args[:2]
        if cmd == ("tab", "rename"):
            self.tabs[args[2]]["label"] = args[3]
            return {}
        if cmd == ("workspace", "create"):
            assert "--no-focus" in args and "--workspace" not in args
            ws = f"x{self.n + 1}"
            self.workspaces[ws] = {"label": args[args.index("--label") + 1]}
            tab, p = self.add_tab(ws, "1")
            return {"result": {"workspace": {"workspace_id": ws}, "tab": {"tab_id": tab}, "root_pane": {"pane_id": p}}}
        if cmd == ("workspace", "list"):
            return {"result": {"workspaces": [{"workspace_id": w, "label": v["label"]}
                                              for w, v in self.workspaces.items()]}}
        if cmd == ("workspace", "get"):
            w = self.workspaces.get(args[2])
            return {"result": {"workspace": {"label": w["label"]}}} if w else {"error": {"code": "workspace_not_found"}}
        if cmd == ("workspace", "rename"):
            self.workspaces[args[2]]["label"] = args[3]
            return {}
        if cmd == ("workspace", "close"):
            assert self.workspaces.pop(args[2])
            for t in [t for t, v in self.tabs.items() if v["ws"] == args[2]]:
                self._close_tab(t)
            return {}
        if cmd == ("tab", "list"):
            return {"result": {"tabs": [{"tab_id": t, "label": v["label"]} for t, v in self.tabs.items()]}}
        if cmd == ("tab", "get"):
            t = self.tabs.get(args[2])
            return {"result": {"tab": {"label": t["label"]}}} if t else {"error": {"code": "tab_not_found"}}
        if cmd == ("tab", "close"):
            self._close_tab(args[2])
            return {}
        if cmd == ("pane", "get"):
            pid = self.alias.get(args[2], args[2])
            p = self.panes.get(pid)
            return {"result": {"pane": {"pane_id": pid, **p}}} if p else {"error": {"code": "pane_not_found"}}
        if cmd == ("pane", "move"):
            assert "--new-workspace" in args and "--no-focus" in args
            old = self.alias.get(args[2], args[2])
            p = self.panes.pop(old)
            self.tabs[p["tab_id"]]["panes"].remove(old)
            closed = p["tab_id"] if not self.tabs[p["tab_id"]]["panes"] else None
            if closed:
                del self.tabs[closed]
            self.n += 1
            ws, tab, new = f"x{self.n}", f"x{self.n}:t1", f"x{self.n}:p1"
            self.workspaces[ws] = {"label": args[args.index("--label") + 1]}
            self.tabs[tab] = {"label": "1", "ws": ws, "panes": [new]}
            self.panes[new] = {**p, "tab_id": tab, "workspace_id": ws}
            self.alias.update({k: new for k, v in self.alias.items() if v == old}, **{old: new})
            return {"result": {"move_result": {"pane": {"pane_id": new, "workspace_id": ws},
                                               "closed_tab_id": closed}}}
        if cmd == ("pane", "run"):
            self.ran.append((args[2], args[3]))
            self.panes[args[2]].update(agent="omp", agent_status="idle")
            return {}
        if cmd == ("pane", "send-text"):
            self.typed.append((args[2], args[3]))
            return {}
        if cmd == ("pane", "send-keys"):
            return {}
        raise AssertionError(args)


class FakeMail:
    def __init__(self):
        self.agents = {}
        self.sent = []
        self.retired = []
        self.unread = {}  # agent → ids of mail it has not read
        self.n = 0
        self.clock = None

    def __call__(self, tool, args):
        if tool == "create_agent_identity":
            self.n += 1
            name = f"Worker{chr(64 + self.n)}ox"
            self.agents[name] = {"name": name, "task_description": args["task_description"],
                                 "inception_ts": db.iso(self.clock()), "last_active_ts": db.iso(self.clock())}
            return {"name": name}
        if tool == "macro_start_session":
            name = args.get("agent_name") or "QueenBee"
            self.agents.setdefault(name, {"name": name, "task_description": args.get("task_description", ""),
                                          "inception_ts": db.iso(self.clock()), "last_active_ts": None})
            return {"agent": {"name": name, "registration_token": "SECRET-" + name}, "inbox": []}
        if tool == "list_agents":
            return list(self.agents.values())
        if tool == "retire_agent":
            assert args["registration_token"] == "SECRET-" + args["agent_name"]
            self.retired.append(args["agent_name"])
            return {"ok": True}
        if tool == "send_message":
            self.n += 1
            mid = 1000 + self.n
            self.sent.append({**args, "id": mid})
            for to in args["to"]:
                self.unread.setdefault(to, set()).add(mid)
            return {"deliveries": [{"payload": {"id": mid, "thread_id": None}}]}
        if tool == "fetch_topic":
            return []
        if tool == "fetch_inbox_events":
            assert args.get("position_now")
            return {"tail_cursor": 500 + len(self.sent)}
        raise AssertionError(tool)

    def join(self, name, at):
        """The worker's first `macro_start_session`: it returns the inbox and marks it read."""
        if self.agents[name]["last_active_ts"] == self.agents[name]["inception_ts"]:
            self.unread.pop(name, None)
        self.agents[name]["last_active_ts"] = db.iso(at)


class SwarmTest(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.t = 1_800_000_000.0
        self.h = FakeHerdr()
        self.m = FakeMail()
        self.m.clock = lambda: self.t
        patches = [
            (state, "STATE_DIR", tmp), (state, "STATE_FILE", tmp / "state.json"),
            (state, "LOCK_FILE", tmp / "state.lock"), (state, "LOG_FILE", tmp / "realm.log"),
            (swarm, "herdr", self.h), (swarm, "call", self.m), (swarm, "now", lambda: self.t),
            (swarm, "sleep", self.advance), (swarm, "launchd_loaded", lambda: True),
            (herdr_mod, "herdr", self.h), (daemon, "herdr", self.h),
        ]
        for module, target, value in patches:
            p = mock.patch.object(module, target, value)
            p.start()
            self.addCleanup(p.stop)
        env = mock.patch.dict(os.environ, {"REALM_DB": str(tmp / "realm.db"), "TMPDIR": str(tmp)})
        env.start()
        self.addCleanup(env.stop)
        self.conn = db.connect()
        self.addCleanup(self.conn.close)

    def advance(self, seconds):
        self.t += seconds
        for name in self.m.agents:
            if name.startswith("Worker") and name not in getattr(self, "never_join", ()):
                self.m.join(name, self.t)

    def subs(self):
        with state.locked_state() as s:
            return dict(s["subscriptions"])

    def create(self, size=2, key=KEY):
        return swarm.create(self.conn, key, size, "m1", "w", "/cwd", "w:p0", "w:t0")

    def test_create_with_name_labels_tab_brief_and_table(self):
        out = swarm.create(self.conn, KEY, 1, "m1", "w", "/cwd", "w:p0", "w:t0", name="secret garden")
        self.assertEqual(self.h.tabs["w:t0"]["label"], "👑 queen · secret garden")
        self.assertEqual(self.h.workspaces["x1"]["label"], "🛠️ secret garden · worker-aox")
        text = Path(out["workers"][0]["brief"]).read_text()
        self.assertIn("worker of realm `secret garden`", text)
        self.assertIn('herdr workspace rename x1 "🛠️ secret garden · worker-aox"', text)
        self.assertEqual(swarm.status(self.conn, KEY)["realm"], "secret garden")
        self.assertIn("Realm `secret garden`", db.render_table(self.conn, KEY, False, self.t))

    def test_create_refuses_taken_name_before_any_side_effect(self):
        db.init_realm(self.conn, OTHER, "Q", None, self.t, name="garden")
        with self.assertRaises(db.Refused):
            swarm.create(self.conn, KEY, 1, "m1", "w", "/cwd", "w:p0", "w:t0", name="garden")
        self.assertEqual(self.h.tabs["w:t0"]["label"], "shell")
        self.assertEqual(self.h.workspaces, {"w": {"label": "home"}})
        self.assertEqual(self.m.agents, {})

    def test_create_bootstraps_queen_and_workers_each_in_its_own_workspace(self):
        out = self.create()
        self.assertEqual(out["queen"], "QueenBee")
        self.assertEqual(self.h.tabs["w:t0"]["label"], "👑 queen")
        self.assertEqual(self.h.workspaces["w"]["label"], "👑 home")  # the user's label kept, marked
        self.assertEqual(out["queen_workspace"], "ok")
        self.assertEqual([w["name"] for w in out["workers"]], ["WorkerAox", "WorkerBox"])
        self.assertEqual([w["workspace"] for w in out["workers"]], ["x1", "x2"])
        self.assertEqual(out["not_joined"], [])
        self.assertEqual([t for t, v in self.h.tabs.items() if v["ws"] == "w"], ["w:t0"])  # no worker tab beside her
        subs = self.subs()
        self.assertEqual(subs["w:p0"]["mode"], "aside")
        self.assertEqual({p: v["mode"] for p, v in subs.items() if p != "w:p0"},
                         {"x1:p1": "prompt", "x2:p2": "prompt"})
        brief = Path(out["workers"][0]["brief"])
        self.assertEqual(brief.parent, swarm.brief_dir(KEY))
        text = brief.read_text()
        self.assertIn("You are WorkerAox", text)
        self.assertIn("ABSOLUTE RULE: never ask the user", text)
        self.assertNotIn("HERDR_TAB_ID", text)
        self.assertEqual(self.h.ran[0], ("x1:p1", f"omp @{brief}"))
        self.assertEqual(self.h.workspaces["x1"]["label"], "🛠️ /test/swarm · worker-aox")
        self.assertEqual([w["workspace"] for w in db.list_workers(self.conn, KEY, self.t)], ["x1", "x2"])
        self.assertTrue(all(w["joined"] for w in db.list_workers(self.conn, KEY, self.t)))

    def test_wait_joined_reports_laggards_without_real_sleep(self):
        self.never_join = {"WorkerBox"}
        out = self.create()
        self.assertEqual(out["joined"], ["WorkerAox"])
        self.assertEqual(out["not_joined"], [{"name": "WorkerBox", "pane": "x2:p2"}])

    def test_create_refuses_bad_size_and_missing_pane(self):
        with self.assertRaises(db.Refused):
            self.create(size=0)
        with self.assertRaises(db.Refused):
            swarm.create(self.conn, KEY, 1, "m1", "w", "/cwd", None, None)

    def test_dispatch_and_queue(self):
        self.create(size=1)
        out = swarm.dispatch(self.conn, KEY, "WorkerAox", "s1", "Do it", "body")
        self.assertEqual(out["subject"]["state"], "assigned")
        self.assertEqual(self.m.sent[0]["subject"], "[s1] Do it")
        self.assertEqual(self.m.sent[0]["topic"], "s1")
        self.assertEqual(self.m.sent[0]["sender_name"], "QueenBee")
        q = swarm.dispatch(self.conn, KEY, "WorkerAox", "s2", "Next", "body", after="s1")
        self.assertEqual(q["subject"]["state"], "queued")
        self.assertTrue(self.m.sent[1]["body_md"].startswith("queued: start after s1\n"))
        self.assertEqual(self.h.typed, [])  # dispatch never types: the daemon wakes
        for slug, after in (("s1", None), ("s3", "missing")):
            with self.assertRaises(db.Refused):
                swarm.dispatch(self.conn, KEY, "WorkerAox", slug, "Again", "body", after=after)
        self.assertEqual(len(self.m.sent), 2)  # refused before any mail went out

    def test_dispatch_to_a_fresh_worker_waits_for_its_connect(self):
        """The race: a subject sent before the worker connects is marked read by that connect, and the daemon,
        which wakes only on unread mail, never wakes it."""
        self.create(size=1)
        name = swarm.spawn(self.conn, KEY)["name"]  # not joined: spawn does not wait
        self.assertIsNone(db.worker_row(self.conn, KEY, name, self.t)["joined"])
        out = swarm.dispatch(self.conn, KEY, name, "s1", "First", "body")
        self.m.join(name, self.t + 1)  # its connect, if it had not happened yet
        self.assertEqual(self.m.unread.get(name), {out["message_id"]})

    def test_dispatch_to_a_worker_that_never_joins_sends_nothing(self):
        self.create(size=1)
        self.never_join = {"WorkerBox"}
        swarm.spawn(self.conn, KEY)
        with self.assertRaises(db.Refused):
            swarm.dispatch(self.conn, KEY, "WorkerBox", "s1", "First", "body")
        self.assertEqual(self.m.sent, [])
        self.assertEqual(db.list_subjects(self.conn, KEY), [])

    def test_retire_scales_in(self):
        out = self.create(size=1)
        brief = Path(out["workers"][0]["brief"])
        res = swarm.retire(self.conn, KEY, "WorkerAox")
        self.assertEqual(res["steps"]["workspace_close"], "ok")
        self.assertNotIn("x1", self.h.workspaces)
        self.assertIn("w", self.h.workspaces)
        self.assertNotIn("x1:p1", self.subs())
        self.assertEqual(self.m.retired, ["WorkerAox"])
        self.assertFalse(brief.exists())
        self.assertNotIn("SECRET", repr(res))
        self.assertEqual(db.list_workers(self.conn, KEY, self.t), [])

    def test_retire_never_closes_a_queen_workspace_a_row_names(self):
        self.create(size=1)
        self.conn.execute("UPDATE workers SET workspace='x1', tab=NULL")
        self.h.workspaces["x1"]["label"] = "👑 someone else's realm"
        res = swarm.retire(self.conn, KEY, "WorkerAox")
        self.assertEqual(res["steps"]["workspace_close"], "refused: queen workspace")
        self.assertIn("x1", self.h.workspaces)

    def test_tab_era_worker_retires_and_stops_by_its_tab(self):
        """Rows written before workers got workspaces: a tab in the queen's workspace, no workspace id."""
        self.create(size=1)
        tab, p = self.h.add_tab("w", "🛠️ subject-old")
        db.add_worker(self.conn, KEY, "Old", p, tab, None, self.t)
        swarm.subscribe(p, "Old", KEY, aside=False)
        brief = swarm.rebrief(self.conn, KEY)
        old_text = (swarm.brief_dir(KEY) / "old.md").read_text()
        self.assertIn('herdr tab rename "$HERDR_TAB_ID" "🛠️ subject-old"', old_text)
        self.assertNotIn("HERDR_WORKSPACE_ID", old_text)  # in its pane that is the queen's workspace
        self.assertEqual(sorted(brief["started"]), ["Old"])
        res = swarm.retire(self.conn, KEY, "Old")
        self.assertEqual(res["steps"]["tab_close"], "ok")
        self.assertNotIn(tab, self.h.tabs)
        tab2, p2 = self.h.add_tab("w", "🛠️ subject-old2")
        db.add_worker(self.conn, KEY, "Old2", p2, tab2, None, self.t)
        swarm.subscribe(p2, "Old2", KEY, aside=False)
        out = swarm.stop(self.conn, KEY, "w:t0")
        self.assertEqual(sorted(map(str, out["closed"])),
                         sorted(map(str, [{"agent": "WorkerAox", "workspace": "x1"}, {"agent": "Old2", "tab": tab2}])))
        self.assertIn("w", self.h.workspaces)
        self.assertIn("w:t0", self.h.tabs)

    def test_move_takes_a_tab_era_worker_into_its_own_workspace(self):
        self.create(size=1)
        tab, p = self.h.add_tab("w", "🛠️ subject-old")
        self.h.panes[p].update(agent="omp", agent_status="idle")
        db.add_worker(self.conn, KEY, "Old", p, tab, None, self.t)
        swarm.subscribe(p, "Old", KEY, aside=False)
        ran = list(self.h.ran)
        out = swarm.move(self.conn, KEY, "Old")
        new, ws = out["pane"], out["workspace"]
        self.assertEqual(out["closed_tab"], tab)
        self.assertNotIn(tab, self.h.tabs)
        self.assertEqual(self.h.workspaces[ws]["label"], "🛠️ /test/swarm · old")
        self.assertEqual(self.h.ran, ran)  # nothing restarted: the agent moved live
        self.assertNotIn(p, self.subs())
        self.assertEqual(self.subs()[new]["agent"], "Old")
        w = db.worker_row(self.conn, KEY, "Old", self.t)
        self.assertEqual((w["pane"], w["workspace"], w["tab"]), (new, ws, None))
        self.assertIn(f'herdr workspace rename {ws} "', Path(w["brief"]).read_text())
        self.assertEqual(out["queen_workspace"], "already marked")
        # The agent keeps its old $HERDR_PANE_ID: verbs run from it still find its realm.
        self.assertEqual(db.resolve_key(None, p, state.STATE_FILE), KEY)
        bound, copy = swarm.bind.read(p), swarm.bind.read(new)  # the extension reads the old id, realm the new
        self.assertEqual({k: bound[k] for k in ("agent", "project", "cursor")}, {"agent": "Old", "project": KEY,
                                                                               "cursor": copy["cursor"]})
        self.assertEqual((copy["agent"], copy["project"]), ("Old", KEY))
        with self.assertRaises(db.Refused):
            swarm.move(self.conn, KEY, "Old")  # already out of the queen's workspace

    def test_move_takes_a_busy_worker_but_never_the_queen(self):
        self.create(size=1)
        tab, p = self.h.add_tab("w", "🛠️ subject-busy")
        self.h.panes[p].update(agent="omp", agent_status="working")
        db.add_worker(self.conn, KEY, "Busy", p, tab, None, self.t)
        db.add_subject(self.conn, KEY, "s1", "T", "Busy", None, None, None, self.t)
        out = swarm.move(self.conn, KEY, "Busy")
        self.assertNotIn(tab, self.h.tabs)
        s = db.subject_row(self.conn, KEY, "s1")
        self.assertEqual((s["state"], s["worker"], s["pane"]), ("assigned", "Busy", out["pane"]))
        db.add_worker(self.conn, KEY, "Fake", "w:p0", "w:t0", None, self.t)
        with self.assertRaises(db.Refused):
            swarm.move(self.conn, KEY, "Fake")
        self.assertIn("w:p0", self.h.panes)
        # A realm older than the db's workspace column: the queen's pane gives her workspace.
        self.conn.execute("UPDATE realms SET workspace=NULL WHERE key=?", (KEY,))
        self.conn.commit()
        tab2, p2 = self.h.add_tab("w", "🛠️ subject-legacy")
        db.add_worker(self.conn, KEY, "Legacy", p2, tab2, None, self.t)
        self.assertEqual(swarm.move(self.conn, KEY, "Legacy")["queen_workspace"], "already marked")
        self.assertNotIn(tab2, self.h.tabs)

    def test_move_takes_a_tab_era_scout_and_rewrites_its_brief(self):
        self.create(size=1)
        tab, p = self.h.add_tab("w", "🔭 scout")
        self.conn.execute("INSERT INTO scouts (realm, agent, pane, tab, brief, created_ts) VALUES (?,?,?,?,?,?)",
                          (KEY, "Peek", p, tab, None, self.t))
        self.conn.commit()
        with state.locked_state() as s:
            s["subscriptions"][p] = {"agent": "Peek", "project": KEY, "mode": "prompt", "kind": "scout",
                                     "cursor": None, "pending": []}
        out = swarm.move(self.conn, KEY, "Peek")
        self.assertEqual(self.h.workspaces[out["workspace"]]["label"], "🔭 /test/swarm · scout")
        self.assertEqual(self.subs()[out["pane"]]["kind"], "scout")
        row = self.conn.execute("SELECT pane, workspace, tab, brief FROM scouts WHERE realm=?", (KEY,)).fetchone()
        self.assertEqual((row["pane"], row["workspace"], row["tab"]), (out["pane"], out["workspace"], None))
        self.assertIn(f'herdr workspace rename {out["workspace"]} "🔭', Path(row["brief"]).read_text())

    def test_queen_workspace_left_unmarked_while_tab_era_workers_live_in_it(self):
        tab, p = self.h.add_tab("w", "🛠️ subject-old")
        swarm.subscribe(p, "Old", OTHER, aside=False)
        out = self.create(size=1)
        self.assertEqual(out["queen_workspace"], "left alone: worker tabs still in it")
        self.assertEqual(self.h.workspaces["w"]["label"], "home")
        db.init_realm(self.conn, OTHER, "Q2", "w:p0", self.t, model="m1", workspace="w", cwd="/cwd")
        db.add_worker(self.conn, OTHER, "Old", p, tab, None, self.t)
        self.assertEqual(swarm.move(self.conn, OTHER, "Old")["queen_workspace"], "ok")  # last tab out: 👑
        self.assertEqual(self.h.workspaces["w"]["label"], "👑 home")

    def test_retire_refuses_busy_worker(self):
        self.create(size=1)
        swarm.dispatch(self.conn, KEY, "WorkerAox", "s1", "t", "b")
        with self.assertRaises(db.Refused):
            swarm.retire(self.conn, KEY, "WorkerAox")
        self.assertIn("x1", self.h.workspaces)

    def test_retire_only_once_every_subject_is_done(self):
        """Loup: retire done workers only. A paused subject keeps its worker alive; there is no override."""
        self.create(size=1)
        swarm.dispatch(self.conn, KEY, "WorkerAox", "s1", "t", "b")
        db.set_state(self.conn, KEY, "s1", "paused", "waits on the user", None, self.t)
        self.assertFalse(db.worker_row(self.conn, KEY, "WorkerAox", self.t + 7200)["scale_in"])
        with self.assertRaisesRegex(db.Refused, "s1:paused"):
            swarm.retire(self.conn, KEY, "WorkerAox")
        self.assertEqual((self.m.retired, "x1" in self.h.workspaces), ([], True))
        db.set_state(self.conn, KEY, "s1", "done", None, None, self.t)
        self.assertTrue(db.worker_row(self.conn, KEY, "WorkerAox", self.t + 30 * 60)["scale_in"])
        swarm.retire(self.conn, KEY, "WorkerAox")
        self.assertEqual(self.m.retired, ["WorkerAox"])

    def test_stop_is_scoped_to_the_key(self):
        self.create(size=1)
        swarm.create(self.conn, OTHER, 1, "m1", "w", "/cwd", "w:p0", "w:t0")  # same queen pane, other realm
        other_brief = swarm.brief_dir(OTHER)
        swarm.dispatch(self.conn, KEY, "WorkerAox", "s1", "t", "b")
        self.h.panes["x1:p1"]["agent_status"] = "working"
        with self.assertRaises(db.NeedsHuman):
            swarm.stop(self.conn, KEY, "w:t0")
        self.assertIn("x1", self.h.workspaces)
        out = swarm.stop(self.conn, KEY, "w:t0", close_working=True)
        self.assertEqual(out["closed"], [{"agent": "WorkerAox", "workspace": "x1"}])
        self.assertIn("x2", self.h.workspaces)  # the other realm's worker
        self.assertIn("w", self.h.workspaces)  # the queen's own
        self.assertIn("w:t0", self.h.tabs)
        self.assertTrue(other_brief.exists())
        self.assertFalse(swarm.brief_dir(KEY).exists())
        self.assertEqual({v["project"] for v in self.subs().values()}, {OTHER})
        self.assertEqual(db.subject_row(self.conn, KEY, "s1")["state"], "paused")

    def test_restart_resumes_queen_and_delivers_brief_on_idle_tick(self):
        self.create(size=2)
        self.h.tabs["w:t9"] = {"label": "new", "ws": "w", "panes": ["w:p9"]}
        self.h.panes["w:p9"] = {"tab_id": "w:t9", "workspace_id": "w", "agent": "omp", "agent_status": "idle"}
        self.h.tabs["w:t0"]["label"] = "dead"  # old queen tab no longer marked
        self.t += 3600
        self.h.panes["x2:p2"]["agent_status"] = "working"
        out = swarm.restart(self.conn, KEY, "m1", "w:p9", "w:t9", "w", "/cwd")
        self.assertEqual(out["queen"], "QueenBee")
        self.assertEqual(sorted(out["brief_pending"]), ["WorkerAox", "WorkerBox"])
        subs = self.subs()
        self.assertNotIn("w:p0", subs)
        self.assertEqual(subs["w:p9"]["mode"], "aside")
        self.assertEqual(db.realm_row(self.conn, KEY)["queen_pane"], "w:p9")
        # Tick hook: idle pane gets the re-read prompt once; the working one waits.
        typed = []
        wake = lambda p, mode, text: typed.append((p, text))  # noqa: E731
        self.assertTrue(swarm.deliver_brief("x1:p1", self.h.panes["x1:p1"], wake))
        self.assertFalse(swarm.deliver_brief("x1:p1", self.h.panes["x1:p1"], wake))
        self.assertFalse(swarm.deliver_brief("x2:p2", self.h.panes["x2:p2"], wake))
        self.assertEqual(len(typed), 1)
        self.assertTrue(typed[0][1].startswith("Re-read @"))
        self.h.panes["x2:p2"]["agent_status"] = "done"
        self.assertTrue(swarm.deliver_brief("x2:p2", self.h.panes["x2:p2"], wake))

    def test_restart_adopts_a_subscribed_pane_in_its_own_worker_workspace(self):
        self.create(size=1)
        self.conn.execute("DELETE FROM workers")
        self.h.tabs["w:t9"] = {"label": "new", "ws": "w", "panes": ["w:p9"]}
        self.h.panes["w:p9"] = {"tab_id": "w:t9", "workspace_id": "w", "agent": "omp", "agent_status": "idle"}
        self.h.tabs["w:t0"]["label"] = "dead"
        self.t += 3600
        swarm.restart(self.conn, KEY, "m1", "w:p9", "w:t9", "w", "/cwd")
        (w,) = db.list_workers(self.conn, KEY, self.t)
        self.assertEqual((w["workspace"], w["tab"]), ("x1", None))

    def test_restart_refuses_while_old_queen_alive(self):
        self.create(size=1)
        self.h.tabs["w:t9"] = {"label": "new", "ws": "w", "panes": ["w:p9"]}
        self.h.panes["w:p9"] = {"tab_id": "w:t9", "workspace_id": "w", "agent": "omp", "agent_status": "idle"}
        with self.assertRaises(db.NeedsHuman) as e:
            swarm.restart(self.conn, KEY, "m1", "w:p9", "w:t9", "w", "/cwd")
        self.assertEqual(e.exception.detail["queen_tabs"], ["w:t0"])
        self.assertIn("w:p0", self.subs())

    def test_restart_without_db_asks_which_queen(self):
        self.m.agents = {n: {"name": n, "task_description": "Swarm queen", "last_active_ts": None}
                         for n in ("Q1", "Q2")}
        self.h.tabs["w:t9"] = {"label": "new", "ws": "w", "panes": ["w:p9"]}
        with self.assertRaises(db.NeedsHuman) as e:
            swarm.restart(self.conn, KEY, "m1", "w:p9", "w:t9", "w", "/cwd")
        self.assertEqual([c["name"] for c in e.exception.detail["candidates"]], ["Q1", "Q2"])

    def test_daemon_tick_delivers_brief_through_guarded_wake(self):
        self.create(size=1)
        db.set_brief_pending(self.conn, KEY, "WorkerAox", True)
        info = {"pane_id": "x1:p1", **self.h.panes["x1:p1"]}
        self.assertTrue(swarm.deliver_brief("x1:p1", info, daemon.wake))
        self.assertEqual(len(self.h.typed), 1)
        self.assertTrue(self.h.typed[0][1].startswith("Re-read @"))
        # The queen's pane is never typed into, even with a pending flag forced on a worker row there.
        db.add_worker(self.conn, KEY, "Fake", "w:p0", "w:t0", "/x", self.t)
        db.set_brief_pending(self.conn, KEY, "Fake", True)
        with self.assertRaises(RuntimeError):
            swarm.deliver_brief("w:p0", {"pane_id": "w:p0", **self.h.panes["w:p0"]}, daemon.wake)
        self.assertEqual(len(self.h.typed), 1)

    def test_every_woken_pane_is_bound_from_its_tail_and_unbound_when_dropped(self):
        """realm-wake reads these files: a worker bound before omp starts, from the tail taken then."""
        self.create(size=2)
        queen, a = swarm.bind.read("w:p0"), swarm.bind.read("x1:p1")
        self.assertEqual((queen["agent"], queen["project"]), ("QueenBee", KEY))
        self.assertEqual((a["agent"], a["cursor"]), ("WorkerAox", 500))
        self.assertNotEqual(a["id"], swarm.bind.read("x2:p2")["id"])
        swarm.retire(self.conn, KEY, "WorkerAox")
        self.assertIsNone(swarm.bind.read("x1:p1"))
        swarm.stop(self.conn, KEY, "w:t0")
        self.assertEqual(list(swarm.bind.bind_dir().glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
