#!/usr/bin/env node
// Read ~/.agents/harnesses.json — the one place this machine declares which coding
// harnesses exist, where each one lives, and which identities each one carries.
//
// This is the Node half of a pair. ~/.local/bin/agent_registry.py is the Python half,
// and the two are held together by `dump()`: both print the same canonical text for the
// same $HOME, so a divergence between them is a failing `diff` rather than two tools
// quietly resolving the same harness to two different directories. Neither reader is
// allowed to answer a question `dump()` cannot show the answer to.
//
// Synchronous, unlike the rest of this repo's I/O, and on purpose: every consumer needs
// the registry before it can decide anything, `stateOf()` is a stat and a $PATH walk
// rather than real I/O, and a sync reader spells the same contract as the Python one —
// both are `load(home)`, not one of them `await load(home)`. install-mcp.mjs already
// imports existsSync/realpathSync (:48) for the same reason.
//
// Nothing here writes. ~/.agents/selection.json is written by `skills` alone; this module
// only reads it. mkdtempSync/mkdirSync/writeFileSync/chmodSync below belong to the
// selftest's fixture and are used nowhere else.
//
// Usage:
//   node scripts/registry.mjs dump       print the canonical registry text
//   node scripts/registry.mjs selftest   assert the contract against a fixture $HOME

import {
  existsSync, readFileSync, statSync, accessSync, constants, realpathSync,
  mkdtempSync, mkdirSync, writeFileSync, chmodSync,
} from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const registryPath = (home) => join(home ?? homedir(), '.agents', 'harnesses.json');
export const selectionPath = (home) => join(home ?? homedir(), '.agents', 'selection.json');

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

// The $HOME a registry was read from, carried on the object itself so that every
// resolver expands `~` against it without a `home` parameter on nine signatures — and so
// that a reg loaded from a fixture cannot resolve half its paths against the real home.
// Symbol-keyed and non-enumerable: JSON.stringify and Object.keys never see it, so a reg
// is still exactly the file's shape to validate.mjs's lint.
const HOME_OF = Symbol('home');
const homeOf = (reg) => reg[HOME_OF] ?? homedir();

// Message texts are terse and pinned, because validate.mjs's fixtures assert them
// byte-for-byte. The loud shape belongs to whoever prints — `✗ ${e.message}` and two
// indented remedy lines, then exit 1, which is readLock's shape at
// install-mcp.mjs:642-646. The registry is the same class of file: one that nothing
// downstream can proceed without, and that must never degrade to an empty answer.
export class RegistryError extends Error {
  constructor(message) {
    super(message);
    this.name = 'RegistryError';
  }
}

const at = (reg, msg) => new RegistryError(`${registryPath(homeOf(reg))}: ${msg}`);

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------

export function load(home) {
  const file = registryPath(home);
  if (!existsSync(file)) throw new RegistryError(`${file}: not found`);
  let reg;
  try {
    reg = JSON.parse(readFileSync(file, 'utf8'));
  } catch (e) {
    throw new RegistryError(`${file}: not valid JSON (${e.message})`);
  }
  // The envelope, and nothing else. `mode`, `owner`, `probe`, `adapter`, `key` and every
  // template are checked by checkRegistry() in validate.mjs — a file with a bad `mode`
  // has to load in order to be linted. What is checked here is only what has to hold for
  // an index three calls further down not to throw a raw TypeError naming nothing.
  // Every message below is spelled exactly as agent_registry.py spells it, and the emptiness
  // test is there for the same reason: a registry that loads on one reader and refuses on the
  // other makes the Step 11 parity diff report an empty side instead of the real cause.
  if (!isObject(reg)) throw new RegistryError(`${file}: not an object`);
  if (reg.version !== 1) {
    throw new RegistryError(`${file}: unsupported version ${String(reg.version)} (expected 1)`);
  }
  for (const key of ['identities', 'harnesses']) {
    if (!isObject(reg[key]) || Object.keys(reg[key]).length === 0) {
      throw new RegistryError(`${file}: ${key} is not a non-empty object`);
    }
  }
  for (const [name, h] of Object.entries(reg.harnesses)) {
    if (!isObject(h)) throw new RegistryError(`${file}: harnesses.${name} is not an object`);
  }
  Object.defineProperty(reg, HOME_OF, { value: home ?? homedir(), enumerable: false });
  return reg;
}

// Absent is not an error: a machine that has activated nothing yet has no selection, and
// `skills` writes the file the first time something is activated. Unreadable *is* an
// error — it is the only record of what each identity activates, so degrading to an empty
// selection would mean "unlink everything", silently and successfully.
export function selection(home) {
  const file = selectionPath(home);
  if (!existsSync(file)) return {};
  let sel;
  try {
    sel = JSON.parse(readFileSync(file, 'utf8'));
  } catch (e) {
    throw new RegistryError(`${file}: not valid JSON (${e.message})`);
  }
  if (!isObject(sel)) throw new RegistryError(`${file}: not an object`);
  if (sel.version !== 1) {
    throw new RegistryError(`${file}: unsupported version ${String(sel.version)} (expected 1)`);
  }
  // `version` is envelope, not data. Both readers strip it, so every consumer can iterate the
  // result as identities without a skip — agent_registry.save_selection() writes the envelope
  // back on its own, and a `version` key that survives into the data is what made the first
  // draft of Task 4 hand the integer 1 to a function expecting {skills, agents}.
  const out = {};
  for (const [name, spec] of Object.entries(sel)) {
    if (name === 'version') continue;
    if (!isObject(spec)) throw new RegistryError(`${file}: ${name} is not an object`);
    out[name] = spec;
  }
  return out;
}

// No caching. Every function takes an optional `reg`, so a consumer loads once and passes
// it down; a cache inside load() would make a fixture-driven selftest depend on call
// order, and would hide a registry edited between two runs of a long-lived process.
export const identities = (reg) => (reg ?? load()).identities;
export const harnesses = (reg) => (reg ?? load()).harnesses;

const harnessOf = (name, reg) => {
  const h = reg.harnesses[name];
  if (!h) throw at(reg, `no harness named \`${name}\``);
  return h;
};

export function identitiesOf(name, reg) {
  const r = reg ?? load();
  const h = harnessOf(name, r);
  const mode = h.identities?.mode;
  if (mode === 'each') return Object.keys(r.identities);
  if (mode === 'single') {
    const owner = h.identities.owner;
    if (!(owner in r.identities)) {
      throw at(r, `harness \`${name}\`: identities.owner \`${owner}\` is not a declared identity`);
    }
    return [owner];
  }
  // Refusing to answer, rather than refusing to load: the envelope rule sends a malformed
  // entry to the lint, and every question about that entry then fails loudly instead of
  // returning an empty identity list.
  throw at(r, `harness \`${name}\`: identities.mode must be "each" or "single", not ${JSON.stringify(mode)}`);
}

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------
//
// Exactly three substitutions, in this order (design §3.2):
//   1. `~`          at position 0 only, expands to the registry's $HOME
//   2. `{identity}` the identity being resolved
//   3. `{root}`     the harness's own resolved root
// `root` is itself resolved by steps 1-2 only, so `{root}` is never recursive and a root
// template mentioning `{root}` is fatal rather than circular.
//
// A `{` surviving resolution is fatal, never a literal path component. This is the one
// place the two readers could silently disagree, and a tool that writes into
// `~/.omp/profiles/{identity}/agent` leaves bytes the next tool cannot find.

function substitute(template, { root, identity, home, where }) {
  if (typeof template !== 'string') {
    throw new RegistryError(`${where}: must be a string, not ${JSON.stringify(template)}`);
  }
  let out = template.startsWith('~') ? home + template.slice(1) : template;
  // Falsy means "not supplied", exactly as `if identity:` / `if harness and …` do on the
  // Python side. An empty-string identity therefore leaves `{identity}` standing and the
  // unresolved-template check below fires, instead of quietly producing `~/.claude-`.
  if (identity) out = out.split('{identity}').join(identity);
  if (root) out = out.split('{root}').join(root);
  if (out.includes('{')) {
    throw new RegistryError(`${where}: unresolved template \`${template}\` → \`${out}\``);
  }
  return out;
}

// The one normalisation both readers can prove they share. Python prints str(Path(s))
// here, which collapses duplicate slashes, `.` segments and a trailing slash — and,
// unlike node's path.resolve(), never collapses `..` and never absolutises a relative
// result. Rather than reimplement PurePosixPath, this refuses exactly what the two
// spellings could disagree about, so every value it returns is byte-for-byte the Python
// one. Nothing legal is refused: `root` is always `~`-rooted and every other path is
// `{root}`-rooted, and Task 8's template lint says so independently.
function pathish(value, where) {
  if (!value.startsWith('/')) {
    throw new RegistryError(`${where}: must resolve to an absolute path, got \`${value}\``);
  }
  if (value.startsWith('//')) {
    throw new RegistryError(`${where}: leading \`//\` in \`${value}\` — POSIX reserves it`);
  }
  const parts = [];
  for (const part of value.split('/')) {
    if (part === '' || part === '.') continue;
    if (part === '..') {
      throw new RegistryError(`${where}: \`..\` in \`${value}\` — name the directory instead`);
    }
    parts.push(part);
  }
  return `/${parts.join('/')}`;
}

const resolvedPath = (template, ctx) => pathish(substitute(template, ctx), ctx.where);

export function resolve(template, { harness, identity, reg } = {}) {
  const r = reg ?? load();
  const home = homeOf(r);
  const root = harness ? rootOf(harness, identity, r) : null;   // falsy = not supplied, as Python
  const where = `${registryPath(home)}: ${harness ?? '?'}${identity ? `:${identity}` : ''}`;
  return substitute(template, { root, identity, home, where });
}

export function rootOf(name, identity, reg) {
  const r = reg ?? load();
  const h = harnessOf(name, r);
  const home = homeOf(r);
  return resolvedPath(h.root, {
    root: null, identity, home, where: `${registryPath(home)}: ${name}:${identity} root`,
  });
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const isDir = (p) => {
  try {
    return statSync(p).isDirectory();
  } catch {
    return false;
  }
};

// `probe.bin` is looked up exactly the way python's shutil.which does it, because the
// Python reader calls it: this is a mirror, not a design. access(2) with X_OK (not a
// st_mode bitmask — an execute bit belonging to another user is not a binary this machine
// can run), directories rejected, symlinks followed (~/.local/bin/claude is one), $PATH
// read at call time and split on ':'. Two of its behaviours are mirrored deliberately
// rather than improved on: PATH="" finds nothing at all (bpo-35755), while an empty entry
// in PATH=":" searches the current directory. A `probe.bin` should therefore be a bare
// name, which is Task 8's lint to require — a name carrying a slash is resolved against
// the cwd here too, exactly as shutil.which resolves it.
function accessible(p) {
  try {
    if (statSync(p).isDirectory()) return false;
    accessSync(p, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function onPath(bin) {
  if (typeof bin !== 'string' || !bin) return false;
  if (bin.includes('/')) return accessible(bin);
  // shutil.which distinguishes PATH unset from PATH empty: unset falls back to
  // os.confstr('CS_PATH') — measured `/usr/bin:/bin:/usr/sbin:/sbin` on this machine, and
  // only if confstr is unavailable does it fall back to os.defpath (`/bin:/usr/bin`) — while
  // empty finds nothing. Mirror the confstr value, or a probe.bin under /sbin reads installed
  // on one reader and residue on the other in any environment that strips PATH.
  const raw = process.env.PATH;
  const path = raw === undefined ? '/usr/bin:/bin:/usr/sbin:/sbin' : raw;  // os.confstr('CS_PATH')
  if (!path) return false;
  return path.split(':').some((dir) => accessible(join(dir, bin)));
}

export function stateOf(name, identity, reg) {
  const r = reg ?? load();
  const h = harnessOf(name, r);
  const root = rootOf(name, identity, r);
  if (!isDir(root)) return 'absent';
  const probe = h.probe;
  const hasFile = isObject(probe) && typeof probe.file === 'string';
  const hasBin = isObject(probe) && typeof probe.bin === 'string';
  // Installed is measured every run and stored nowhere (design decision 9), so a harness
  // with no usable probe has no answer at all — not a default of "installed", which is
  // exactly how a residue tree gets written into.
  if (hasFile === hasBin) {
    throw at(r, `harness \`${name}\`: probe needs exactly one of \`file\` or \`bin\``);
  }
  const home = homeOf(r);
  const hit = hasFile
    ? existsSync(resolvedPath(probe.file, {
        root, identity, home, where: `${registryPath(home)}: ${name}:${identity} probe.file`,
      }))
    : onPath(probe.bin);
  return hit ? 'installed' : 'residue';
}

// ---------------------------------------------------------------------------
// Instances
// ---------------------------------------------------------------------------

// Capability is presence, not a list (design §3.1.1): `vscode` declares only `mcp`, so it
// is never offered a skills link and never appears in a sessions list.
const CAPS = new Set(['skills', 'agents', 'mcp', 'sessions']);
const STATES = new Set(['installed', 'residue', 'absent']);

export function instances({ cap, state = 'installed', reg } = {}) {
  const r = reg ?? load();
  // A typo'd cap or state is a caller bug, and the failure it would otherwise produce —
  // an empty list, reported as success — is the one this registry exists to prevent.
  if (cap !== undefined && cap !== null && !CAPS.has(cap)) {
    throw new TypeError(`unknown capability \`${cap}\``);
  }
  if (state !== null && !STATES.has(state)) throw new TypeError(`unknown state \`${state}\``);
  const out = [];
  for (const [name, h] of Object.entries(r.harnesses)) {
    // By value, not by key: `"mcp": null` must not survive a cap filter that promises
    // mcpFile() is non-null, which is what Task 7 destructures without a guard. Matches
    // agent_registry.instances()'s isinstance(spec.get(cap), dict).
    if (cap && !isObject(h[cap])) continue;
    for (const identity of identitiesOf(name, r)) {
      if (state !== null && stateOf(name, identity, r) !== state) continue;
      // A missing label raises rather than falling back to the harness name — but only for
      // an instance that survives the state filter, which is where agent_registry checks it
      // (inside the append, past its own `continue`). Checking earlier would make
      // `instances()` stop on an unlabelled harness that is absent or residue, so `skills`
      // would link happily while `install-mcp.mjs` hard-stopped on the same file.
      if (typeof h.label !== 'string' || !h.label) {
        throw at(r, `harnesses.${name}.label is missing or not a string`);
      }
      out.push({
        id: `${name}:${identity}`,
        harness: name,
        identity,
        root: rootOf(name, identity, r),
        label: h.label,
      });
    }
  }
  return out;
}

export function mcpFile(inst, reg) {
  const r = reg ?? load();
  const mcp = r.harnesses[inst.harness]?.mcp;
  if (!isObject(mcp)) return null;                 // no MCP capability at all — dump() skips it
  // An `mcp` section that exists and carries no usable `file` is a broken declaration, not an
  // absence: refuse and name it, exactly as agent_registry.mcp_file()'s _field() does.
  if (typeof mcp.file !== 'string') throw at(r, `harnesses.${inst.harness}.mcp.file is missing or not a string`);
  const home = homeOf(r);
  return resolvedPath(mcp.file, {
    root: inst.root, identity: inst.identity, home,
    where: `${registryPath(home)}: ${inst.id} mcp.file`,
  });
}

// Not exported: `skills` and `agents-doctor` do the linking and both are Python, so dump()
// is the only JS caller. `native` and "no such capability" both answer null — the caller
// that needs to tell them apart reads the entry, which is what dump() does.
function capDir(inst, leaf, reg) {
  const cap = reg.harnesses[inst.harness]?.[leaf];
  if (!isObject(cap)) return null;                 // no such capability — dump() prints `-`
  if (cap.native === true) return null;            // reads ~/.agents/skills directly
  // Same rule as mcpFile: a declared section with no usable `dir` is refused, not silently
  // rendered as `-`, so both readers stop on the same registries.
  if (typeof cap.dir !== 'string') throw at(reg, `harnesses.${inst.harness}.${leaf}.dir is missing or not a string`);
  const home = homeOf(reg);
  return resolvedPath(cap.dir, {
    root: inst.root, identity: inst.identity, home,
    where: `${registryPath(home)}: ${inst.id} ${leaf}.dir`,
  });
}

// ---------------------------------------------------------------------------
// Canonical text
// ---------------------------------------------------------------------------
//
// The one function whose output is a contract with another language. For the same
// **lint-clean** registry and $HOME, agent_registry.py's dump() prints these same bytes, and
// Task 3's parity step diffs them — so a reader that resolves `{root}` differently, walks
// $PATH differently, or disagrees about what `residue` means fails as one visible line instead
// of as a mystery two months later.
//
// Capability lines are declaration-only: `state` is a field on the `instance` line, never
// a filter on the rest, so the two readers are compared on the whole declaration rather
// than on whatever happens to be installed on the machine running the diff.

export function dump(home) {
  const reg = load(home);
  const sel = selection(home);
  const lines = [];

  // `or '-'` on Python and the non-empty-string contract enforced by checkRegistry(): a
  // lint-clean identity renders the same text on both readers. An identity whose value is not
  // an object is refused rather than rendered, on both readers.
  for (const [id, v] of Object.entries(reg.identities)) {
    if (!isObject(v)) throw at(reg, `identities.${id} is not an object`);
    lines.push(`identity ${id} gh=${v.gh ?? '-'} glyph=${v.glyph ?? '-'}`);
  }

  for (const inst of instances({ state: null, reg })) {
    const h = reg.harnesses[inst.harness];
    lines.push(`instance ${inst.id} harness=${inst.harness} identity=${inst.identity}`
      + ` state=${stateOf(inst.harness, inst.identity, reg)} root=${inst.root}`);
    // Presence is `leaf in h`, matching agent_registry's `leaf not in spec` — so a declared
    // `"skills": null` prints `skills <id> -` on both readers instead of vanishing on one.
    for (const leaf of ['skills', 'agents']) {
      if (!(leaf in h)) continue;
      const cap = h[leaf];
      lines.push(`${leaf} ${inst.id} ${isObject(cap) && cap.native === true ? 'native' : (capDir(inst, leaf, reg) ?? '-')}`);
    }
    if (isObject(h.mcp)) {
      lines.push(`mcp ${inst.id} ${mcpFile(inst, reg)}`
        + ` key=${h.mcp.key ?? '-'} adapter=${h.mcp.adapter ?? '-'}`);
    }
    if (isObject(h.sessions)) {
      // Refuse a declared-but-incomplete sessions section, as agent_registry's _field()
      // does — the sibling fixes above already refuse an mcp.file and a <leaf>.dir, and a
      // `-` here would be the one place left where one reader answers and the other stops.
      const s = (k) => {
        const v = h.sessions[k];
        if (typeof v !== 'string' || !v) {
          throw at(reg, `harnesses.${inst.harness}.sessions.${k} is missing or not a string`);
        }
        return resolve(v, { harness: inst.harness, identity: inst.identity, reg });
      };
      // events is the one optional field of the three, and `null` is the only accepted
      // absence — agent_registry._optional(), with both wordings pinned there too. A
      // harness may hold a pane and speak no event vocabulary; a dropped key says
      // nothing at all, and the two are different facts.
      const spoken = () => {
        if (!('events' in h.sessions)) {
          throw at(reg, `harnesses.${inst.harness}.sessions.events is missing (declare null for none)`);
        }
        const v = h.sessions.events;
        if (v === null) return '-';
        if (typeof v !== 'string' || !v) {
          throw at(reg, `harnesses.${inst.harness}.sessions.events is not a non-empty string or null`);
        }
        return resolve(v, { harness: inst.harness, identity: inst.identity, reg });
      };
      lines.push(`sessions ${inst.id} launcher=${s('launcher')} comm=${s('comm')} events=${spoken()}`);
    }
  }

  // selection() has already stripped `version` and refused a non-object identity, so this
  // loop sees only data. A missing, empty or non-list value renders `-` on both readers.
  for (const [identity, v] of Object.entries(sel)) {
    const list = (k) => (Array.isArray(v[k]) && v[k].length ? v[k].join(',') : '-');
    lines.push(`selection ${identity} skills=${list('skills')} agents=${list('agents')}`);
  }

  // Sort the finished line strings, not the structures behind them: the sort key is then
  // literally the printed byte sequence, so python's `sorted()` and this `.sort()` cannot
  // order the file differently. They agree because every line begins `<kind> <id> `, that
  // prefix is unique per line and pure ASCII, and no comparison therefore ever reaches a
  // glyph — the only place UTF-16 code-unit order could diverge from code-point order.
  // One LF after every line, including the last: `join` then a trailing `"\n"`, which is the
  // same bytes as python's `"".join(line + "\n" for line in sorted(lines))` for every
  // non-empty dump. The empty case cannot arise on either side now that load() refuses an
  // empty `identities`/`harnesses`.
  lines.sort();
  return lines.join('\n') + '\n';
}

// ---------------------------------------------------------------------------
// Selftest
// ---------------------------------------------------------------------------
//
// No framework, and no package.json to hang one on, so the suite is a fixture $HOME under
// os.tmpdir() plus a table of assertions — the same shape agent_registry.py's selftest
// uses, case for case, so that a divergence between the two readers surfaces as one named
// failing case instead of a mystery diff.
//
// The fixture is synthetic on purpose: alpha/beta/gamma cover both `identities.mode`s, a
// file probe and a bin probe, installed/residue/absent, a `native` skills harness and an
// mcp entry with no `key`. Asserting against this machine's real registry would test
// today's machine rather than the contract.

const FIXTURE = {
  version: 1,
  identities: {
    perso: { gh: 'gh-perso', glyph: 'P' },
    work: { gh: 'gh-work', glyph: 'W' },
  },
  harnesses: {
    alpha: {
      label: 'Alpha',
      root: '~/.alpha-{identity}',
      probe: { file: '{root}/settings.json' },
      identities: { mode: 'each' },
      identity: { env: 'ALPHA_DIR', from: 'root' },
      skills: { dir: '{root}/skills' },
      agents: { dir: '{root}/agents' },
      mcp: { file: '{root}/mcp.json', key: 'mcpServers', adapter: 'alpha' },
      sessions: { launcher: 'alpha-{identity}', comm: 'alpha', events: 'alpha' },
    },
    beta: {
      label: 'Beta',
      root: '~/.beta',
      probe: { bin: 'beta-bin' },
      identities: { mode: 'single', owner: 'work' },
      skills: { native: true },
      mcp: { file: '{root}/config.toml', adapter: 'beta' },
    },
    gamma: {
      label: 'Gamma',
      root: '~/.gamma',
      probe: { file: '{root}/settings.json' },
      identities: { mode: 'single', owner: 'perso' },
      mcp: { file: '{root}/mcp.json', key: 'servers', adapter: 'gamma' },
    },
  },
};

const FIXTURE_SELECTION = {
  version: 1,
  perso: { skills: ['one', 'two'], agents: ['solo'] },
  work: { skills: ['one'], agents: [] },
};

// Written with the same 2-space JSON everything else in this repo writes, so the fixture
// is a file a human could have hand-edited. `registry` may be a raw string, which is how
// the unparseable case is built.
function writeHome(registry, selectionDoc) {
  const home = mkdtempSync(join(tmpdir(), 'registry-'));
  mkdirSync(join(home, '.agents'), { recursive: true });
  if (registry !== null) {
    writeFileSync(registryPath(home),
      typeof registry === 'string' ? registry : JSON.stringify(registry, null, 2) + '\n');
  }
  if (selectionDoc !== null) {
    writeFileSync(selectionPath(home), JSON.stringify(selectionDoc, null, 2) + '\n');
  }
  return home;
}

// Every variant gets the same disk shape as the good fixture, or a probe case would be
// decided by a missing root before the probe was ever read.
function fixture(mutate) {
  const copy = JSON.parse(JSON.stringify(FIXTURE));
  if (mutate) mutate(copy);
  const home = writeHome(copy, FIXTURE_SELECTION);
  mkdirSync(join(home, '.alpha-perso'));                                  // root + probe
  writeFileSync(join(home, '.alpha-perso', 'settings.json'), '{}\n');     // → installed
  mkdirSync(join(home, '.alpha-work'));               // root, no probe → residue
  mkdirSync(join(home, '.beta'));                     // root + a bin on PATH → installed
  mkdirSync(join(home, 'bin'));
  writeFileSync(join(home, 'bin', 'beta-bin'), '#!/bin/sh\nexit 0\n');
  chmodSync(join(home, 'bin', 'beta-bin'), 0o755);
  // ~/.gamma is deliberately never created: absent.
  return home;
}

function selftest() {
  const home = fixture();
  const savedPath = process.env.PATH;
  process.env.PATH = `${join(home, 'bin')}:${savedPath}`;
  let cases = 0;
  let failures = 0;
  const check = (label, got, want) => {
    cases++;
    if (got !== want) {
      failures++;
      console.log(`FAIL ${label}\n  want ${JSON.stringify(want)}\n  got  ${JSON.stringify(got)}`);
    }
  };
  const refuses = (label, fn) => {
    cases++;
    try {
      fn();
    } catch (e) {
      if (e instanceof RegistryError) return;
      failures++;
      console.log(`FAIL ${label}: ${e.name}: ${e.message}`);
      return;
    }
    failures++;
    console.log(`FAIL ${label}: no RegistryError`);
  };

  try {
    const reg = load(home);
    const text = dump(home);
    const line = (kind, id) => text.split('\n').find((l) => l.startsWith(`${kind} ${id} `)) ?? '';

    // The parity contract itself: sorted lines, LF-terminated, absolute paths, `-` for an
    // optional value the entry does not carry, capability lines for every declared
    // instance regardless of state. agent_registry.py's selftest asserts this same text
    // for its own fixture; Step 10 diffs the two CLIs over one shared fixture $HOME.
    check('dump', text, [
      `agents alpha:perso ${home}/.alpha-perso/agents`,
      `agents alpha:work ${home}/.alpha-work/agents`,
      'identity perso gh=gh-perso glyph=P',
      'identity work gh=gh-work glyph=W',
      `instance alpha:perso harness=alpha identity=perso state=installed root=${home}/.alpha-perso`,
      `instance alpha:work harness=alpha identity=work state=residue root=${home}/.alpha-work`,
      `instance beta:work harness=beta identity=work state=installed root=${home}/.beta`,
      `instance gamma:perso harness=gamma identity=perso state=absent root=${home}/.gamma`,
      `mcp alpha:perso ${home}/.alpha-perso/mcp.json key=mcpServers adapter=alpha`,
      `mcp alpha:work ${home}/.alpha-work/mcp.json key=mcpServers adapter=alpha`,
      `mcp beta:work ${home}/.beta/config.toml key=- adapter=beta`,
      `mcp gamma:perso ${home}/.gamma/mcp.json key=servers adapter=gamma`,
      'selection perso skills=one,two agents=solo',
      'selection work skills=one agents=-',
      'sessions alpha:perso launcher=alpha-perso comm=alpha events=alpha',
      'sessions alpha:work launcher=alpha-work comm=alpha events=alpha',
      `skills alpha:perso ${home}/.alpha-perso/skills`,
      `skills alpha:work ${home}/.alpha-work/skills`,
      'skills beta:work native',
    ].join('\n') + '\n');
    check('dump is LF-terminated exactly once', text.endsWith('\n') && !text.endsWith('\n\n'), true);
    check('native skills declare no directory', line('skills', 'beta:work'), 'skills beta:work native');
    check('mcp without a key renders key=-', line('mcp', 'beta:work'),
      `mcp beta:work ${home}/.beta/config.toml key=- adapter=beta`);
    check('sessions substitutes {identity}', line('sessions', 'alpha:work'),
      'sessions alpha:work launcher=alpha-work comm=alpha events=alpha');
    // `events: null` is the explicit "no producer": a harness that holds a pane and
    // reports nothing from it, which agent_registry._optional() accepts and prints as the
    // same `-` every absent optional value gets. The other two absences are faults, with
    // the wordings its selftest pins.
    check('sessions with no vocabulary renders events=-',
      dump(fixture((r) => { r.harnesses.alpha.sessions.events = null; }))
        .split('\n').find((l) => l.startsWith('sessions alpha:perso ')),
      'sessions alpha:perso launcher=alpha-perso comm=alpha events=-');
    refuses('sessions.events dropped entirely',
      () => dump(fixture((r) => { delete r.harnesses.alpha.sessions.events; })));
    refuses('sessions.events as an empty string',
      () => dump(fixture((r) => { r.harnesses.alpha.sessions.events = ''; })));
    check('an empty selection list renders -', line('selection', 'work'),
      'selection work skills=one agents=-');

    check('{identity} inside root', rootOf('alpha', 'perso', reg), `${home}/.alpha-perso`);
    check('root with no {identity}', rootOf('beta', 'work', reg), `${home}/.beta`);
    // Substitution order is decidable exactly here: `~` is step 1 and applies to the
    // template, so a `~` arriving later — inside a `{root}` expansion, or after one —
    // stays literal. A reader that expanded `~` last answers `${home}/.beta${home}/x`.
    check('~ only at position 0', resolve('{root}/~/x', { harness: 'beta', identity: 'work', reg }),
      `${home}/.beta/~/x`);
    check('{identity} in the outer template',
      resolve('{root}/{identity}.log', { harness: 'alpha', identity: 'work', reg }),
      `${home}/.alpha-work/work.log`);

    check('installed: root and probe.file', stateOf('alpha', 'perso', reg), 'installed');
    check('residue: root, no probe.file', stateOf('alpha', 'work', reg), 'residue');
    check('installed: probe.bin on PATH', stateOf('beta', 'work', reg), 'installed');
    check('absent: no root', stateOf('gamma', 'perso', reg), 'absent');
    process.env.PATH = '/nonexistent-bin';
    check('residue: probe.bin off PATH', stateOf('beta', 'work', reg), 'residue');
    // shutil.which returns None for PATH="" instead of falling back to os.defpath
    // (bpo-35755); this reader mirrors it, so an empty PATH finds nothing at all.
    process.env.PATH = '';
    check('residue: PATH is empty', stateOf('beta', 'work', reg), 'residue');
    process.env.PATH = join(home, 'bin');
    check('probe.bin is found through PATH alone', stateOf('beta', 'work', reg), 'installed');
    // access(2) with X_OK, not a mode bitmask: a file whose execute bit belongs to
    // somebody else is not a binary this machine can run, and shutil.which agrees.
    chmodSync(join(home, 'bin', 'beta-bin'), 0o644);
    check('residue: probe.bin has no execute bit', stateOf('beta', 'work', reg), 'residue');
    chmodSync(join(home, 'bin', 'beta-bin'), 0o755);
    process.env.PATH = `${join(home, 'bin')}:${savedPath}`;

    check('mode each spans every identity', identitiesOf('alpha', reg).join(','), 'perso,work');
    check('mode single carries its owner', identitiesOf('beta', reg).join(','), 'work');
    check('instance ids are <harness>:<identity>',
      instances({ state: null, reg }).map((i) => i.id).join(' '),
      'alpha:perso alpha:work beta:work gamma:perso');
    check('instances default to installed',
      instances({ reg }).map((i) => i.id).join(' '), 'alpha:perso beta:work');
    check('cap selects by declaration',
      instances({ cap: 'sessions', state: null, reg }).map((i) => i.id).join(' '),
      'alpha:perso alpha:work');
    check('cap and state together',
      instances({ cap: 'mcp', reg }).map((i) => i.id).join(' '), 'alpha:perso beta:work');
    // A declared-but-unusable section must not survive the cap filter, or Task 7's
    // `const { mcp } = harnesses(reg)[inst.harness]` destructures null and throws a raw
    // TypeError past the hard stop written to catch a RegistryError.
    check('cap ignores a non-object section',
      instances({ cap: 'mcp', state: null, reg: load(fixture((r) => { r.harnesses.gamma.mcp = null; })) })
        .map((i) => i.id).join(' '),
      'alpha:perso alpha:work beta:work');
    check('label comes from the entry', instances({ reg })[0].label, 'Alpha');
    const beta = instances({ reg }).find((i) => i.harness === 'beta');
    check('mcpFile resolves {root}', mcpFile(beta, reg), `${home}/.beta/config.toml`);
    check('mcpFile is null for an undeclared harness', mcpFile({ ...beta, harness: 'delta' }, reg), null);
    check('selection reads the file', selection(home).perso.skills.join(','), 'one,two');
    check('selection is {} when absent', Object.keys(selection(join(home, 'nowhere'))).length, 0);

    // The parity rows: every one of these raises on the Python side too, and each was a
    // silent divergence before hardening. A reader that answers where the other refuses is
    // how the Step 10/11 dump diff turns into an empty side rather than a named cause.
    refuses('an empty identities object', () => load(fixture((r) => { r.identities = {}; })));
    refuses('an empty harnesses object', () => load(fixture((r) => { r.harnesses = {}; })));
    // beta is installed in the fixture, so it survives the default state filter too — which
    // is the point: the check must fire for an instance that is returned, not for one that
    // was filtered out, or the two readers disagree on a residue harness with no label.
    refuses('a harness with no label', () =>
      instances({ reg: load(fixture((r) => { delete r.harnesses.beta.label; })) }));
    check('an unlabelled absent harness is filtered out before the label check',
      instances({ reg: load(fixture((r) => { delete r.harnesses.gamma.label; })) })
        .map((i) => i.id).join(' '),
      'alpha:perso beta:work');
    refuses('an mcp section with no file', () =>
      mcpFile(beta, load(fixture((r) => { r.harnesses.beta.mcp = { adapter: 'codex' }; }))));
    refuses('a skills section with no dir', () =>
      dump(fixture((r) => { r.harnesses.alpha.skills = { adapter: 'x' }; })));
    refuses('an identity whose value is not an object', () =>
      dump(fixture((r) => { r.identities.work = 'yes'; })));

    refuses('a missing registry', () => load(join(home, 'nowhere')));
    refuses('an unparseable registry', () => load(writeHome('{ "version": 1,', null)));
    refuses('an unsupported version', () => load(fixture((r) => { r.version = 2; })));
    refuses('harnesses that is not an object', () => load(fixture((r) => { r.harnesses = []; })));
    // `mode` and `owner` are the lint's business (Main's decision 4), so they must load —
    // and then refuse to answer. An empty identity list here would activate a harness
    // into nothing and report success, which is the failure this registry exists to stop.
    const badMode = load(fixture((r) => { r.harnesses.beta.identities = { mode: 'both' }; }));
    check('a bad mode still loads, for the lint to report',
      badMode.harnesses.beta.identities.mode, 'both');
    refuses('a bad mode has no identities', () => identitiesOf('beta', badMode));
    refuses('an owner that is not an identity',
      () => identitiesOf('beta', load(fixture((r) => { r.harnesses.beta.identities.owner = 'ghost'; }))));
    refuses('a probe with neither file nor bin',
      () => stateOf('beta', 'work', load(fixture((r) => { r.harnesses.beta.probe = {}; }))));
    refuses('a probe with both file and bin',
      () => stateOf('beta', 'work', load(fixture((r) => {
        r.harnesses.beta.probe = { file: '{root}/x', bin: 'beta-bin' };
      }))));
    refuses('a root that mentions {root}',
      () => rootOf('beta', 'work', load(fixture((r) => { r.harnesses.beta.root = '~/.beta/{root}'; }))));
    // pathish() is the whole normalisation contract: what it accepts, python's
    // str(Path(s)) prints identically; what it refuses is what the two spellings would
    // disagree about, since node's path.resolve() collapses `..` and absolutises a
    // relative result where PurePosixPath does neither.
    const dotty = fixture((r) => { r.harnesses.beta.root = '~/.beta//x/./y/'; });
    check('duplicate, trailing and single-dot segments collapse',
      rootOf('beta', 'work', load(dotty)), `${dotty}/.beta/x/y`);
    refuses('a `..` segment in a resolved path',
      () => rootOf('beta', 'work', load(fixture((r) => { r.harnesses.beta.root = '~/.beta/../elsewhere'; }))));
    refuses('a root that is not absolute',
      () => rootOf('beta', 'work', load(fixture((r) => { r.harnesses.beta.root = '.beta'; }))));
    refuses('a surviving brace', () => resolve('{root}/{oops}', { harness: 'beta', identity: 'work', reg }));
    refuses('{root} with no harness', () => resolve('{root}/x', { reg }));
    refuses('an unknown harness', () => identitiesOf('delta', reg));
  } finally {
    process.env.PATH = savedPath;
  }

  // The fixture is left where it is on purpose: Step 10's parity diff runs both readers
  // against it, and os.tmpdir() is not $HOME, so nothing accumulates in the yadm tree.
  console.log(`fixture: ${home}`);
  console.log(`${cases} cases, ${failures} failure(s)`);
  return failures ? 1 : 0;
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function main(argv) {
  const cmd = argv[0] ?? 'dump';
  if (cmd === 'dump') {
    process.stdout.write(dump());
    return 0;
  }
  if (cmd === 'selftest') return selftest();
  console.error(`unknown argument: ${cmd}`);
  console.error('usage: node scripts/registry.mjs [dump|selftest]');
  return 2;
}

// Importable by scripts/validate.mjs exactly the way install-mcp.mjs is (validate.mjs:21),
// so the CLI runs only when this file is the entry point. Compared through realpath for
// the reason install-mcp.mjs:853-855 gives: a checkout reached through a symlinked path
// makes the raw string comparison false, and main() would then silently never run.
const invokedDirectly = process.argv[1]
  && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url));
if (invokedDirectly) {
  try {
    // process.exitCode, never process.exit(): stdout is a pipe under Step 10's
    // `diff <(…) <(…)`, writes to a pipe are asynchronous, and exiting hard can drop the
    // tail of the dump — which would look exactly like a parity failure.
    process.exitCode = main(process.argv.slice(2));
  } catch (e) {
    if (!(e instanceof RegistryError)) throw e;
    console.error(`✗ ${e.message}`);
    console.error('  The registry declares which harnesses exist and where each one lives;');
    console.error('  nothing can be resolved without it. Fix it, or restore it with');
    console.error('  yadm checkout -- .agents/harnesses.json');
    process.exitCode = 1;
  }
}
