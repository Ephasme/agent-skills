#!/usr/bin/env node
// Render mcp/servers.json into every installed agent's own MCP configuration.
//
// Skills are portable because they are inert files: one store plus a symlink serves
// any agent. MCP configuration is not — it is structured state each agent keeps in
// its own file, under its own key, in its own dialect. There is nothing to symlink,
// so the only way to stay agent-neutral is to keep one manifest and *write* the
// dialects. That is all this script is.
//
// The hard constraint is credentials. Fifteen of the seventeen servers are HTTP with
// a secret in a request header, and the agents disagree sharply about whether a
// header value may reference an environment variable:
//
//   Claude Code   ${NAME}          in env and headers          (verified, 2.1.220)
//   opencode      {env:NAME}       in env and headers
//   VS Code       ${env:NAME}      in env and headers
//   Codex         env_http_headers / bearer_token_env_var for headers; env is literal
//   Cursor        ${env:NAME}      in env only — unresolved for remote servers
//   Gemini CLI    $NAME            in env only — headers are literal strings
//
// So each adapter declares, per slot, whether it can express "this value comes from
// environment variable NAME". A server whose secret cannot be expressed is skipped
// with a printed reason rather than written insecurely. `--materialize` overrides
// that and inlines the real values, which is why it is opt-in, chmods the file to
// 0600, and says so loudly: it turns a committed-safe reference into a secret at
// rest, and rotating a credential then means re-running this script.
//
// A server carrying `"enabled": false` is parked: not rendered anywhere, and removed
// from every agent that has it on the next run. Its definition stays in the manifest,
// which is the point — deleting the entry uninstalls it too, but throws the
// definition away, and most reasons to turn a server off are temporary.
//
// Usage:
//   node scripts/install-mcp.mjs                 write every detected target
//   node scripts/install-mcp.mjs --list          show targets and what each supports
//   node scripts/install-mcp.mjs --dry-run       print the diff, write nothing
//   node scripts/install-mcp.mjs -a codex        limit to one agent (repeatable)
//   node scripts/install-mcp.mjs --prune         remove everything this script wrote
//   node scripts/install-mcp.mjs --materialize   inline real secrets (see above)

import { readFile, writeFile, mkdir, rename, chmod, copyFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const HOME = homedir();
const LOCK = join(HOME, '.agents', '.mcp-lock.json');

// Markers around the region this script owns inside a TOML file. TOML cannot be
// merged structurally without a parser dependency, and the point of this repo is to
// stay dependency-free, so the Codex adapter owns a delimited block instead.
const BEGIN = '# >>> agent-skills mcp — generated, do not edit >>>';
const END = '# <<< agent-skills mcp <<<';

// ---------------------------------------------------------------------------
// Manifest
// ---------------------------------------------------------------------------

// A manifest value is either a literal string or {env: "NAME"}. One level of
// indirection, no string templating — every adapter can therefore render it
// natively instead of pattern-matching `${...}` out of a string.
const isRef = (v) => v !== null && typeof v === 'object' && typeof v.env === 'string';

export function validateManifest(manifest, fail) {
  const seen = new Set();
  if (manifest.version !== 1) fail(`unsupported manifest version ${manifest.version}`);
  for (const [name, def] of Object.entries(manifest.servers ?? {})) {
    const at = (msg) => fail(`server \`${name}\`: ${msg}`);
    if (!/^[a-z0-9][a-z0-9-]*$/.test(name)) at('name must be lowercase kebab-case');
    if (seen.has(name.toLowerCase())) at('duplicate name');
    seen.add(name.toLowerCase());
    // Absent means enabled. A disabled server keeps its full definition — it is
    // parked, not deleted — so the rest of the shape is still validated.
    if ('enabled' in def && typeof def.enabled !== 'boolean') at('`enabled` must be a boolean');

    if (def.transport === 'http') {
      if (!def.url) at('http transport needs `url`');
      if (def.command || def.args || def.env) at('http transport cannot take command/args/env');
      for (const [h, v] of Object.entries(def.headers ?? {})) {
        if (typeof v !== 'string' && !isRef(v)) at(`header \`${h}\` must be a string or {env}`);
      }
      if (def.auth && def.auth.type !== 'bearer') at(`unknown auth type \`${def.auth.type}\``);
      if (def.auth && !isRef(def.auth.token)) at('bearer auth needs `token: {env}`');
    } else if (def.transport === 'stdio') {
      if (!def.command) at('stdio transport needs `command`');
      if (def.url || def.headers || def.auth) at('stdio transport cannot take url/headers/auth');
      if (def.args && !Array.isArray(def.args)) at('`args` must be an array');
      for (const [k, v] of Object.entries(def.env ?? {})) {
        if (typeof v !== 'string' && !isRef(v)) at(`env \`${k}\` must be a string or {env}`);
      }
    } else {
      at(`unknown transport \`${def.transport}\``);
    }
  }
}

async function loadManifest(path) {
  const manifest = JSON.parse(await readFile(path, 'utf8'));
  const problems = [];
  validateManifest(manifest, (m) => problems.push(m));
  if (problems.length) {
    console.error(`✗ ${path} is invalid:\n`);
    for (const p of problems) console.error(`  ${p}`);
    process.exit(1);
  }
  return manifest;
}

// ---------------------------------------------------------------------------
// Rendering helpers
// ---------------------------------------------------------------------------

// Resolve one manifest value for an adapter whose slot capability is `cap`.
// Returns {ok: true, value} or {ok: false, reason} — never a partially rendered
// value, so a caller that cannot express a secret drops the whole server. `reason`
// carries a `code` so the reporter can collapse fifteen identical skips into a line.
function resolve(value, cap, adapter, slot, opts) {
  if (!isRef(value)) return { ok: true, value };
  if (cap === 'template') return { ok: true, value: adapter.ref(value.env) };
  if (opts.materialize) {
    const actual = process.env[value.env];
    if (actual === undefined) {
      return { ok: false, reason: { code: 'unset', text: `$${value.env} is not set in this shell` } };
    }
    return { ok: true, value: actual };
  }
  return { ok: false, reason: { text: `${adapter.label} cannot reference environment variables in ${slot}` } };
}

// Deliberately coarse: the reason a server is skipped is the *slot*, not the
// particular variable, so every server that fails the same way collapses to one line.
const SLOT = { env: 'a stdio server\'s env', headers: 'request headers' };

// ---------------------------------------------------------------------------
// TOML emission (Codex only)
// ---------------------------------------------------------------------------

const tomlString = (s) =>
  '"' + String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n') + '"';
const tomlKey = (k) => (/^[A-Za-z0-9_-]+$/.test(k) ? k : tomlString(k));
const tomlInline = (obj) =>
  '{ ' + Object.entries(obj).map(([k, v]) => `${tomlKey(k)} = ${tomlString(v)}`).join(', ') + ' }';

// ---------------------------------------------------------------------------
// File writers
// ---------------------------------------------------------------------------

// Read-modify-write of a single top-level key, preserving everything else in the
// file. Claude Code's `.claude.json` is 60 KB of live session state that happens to
// also hold `mcpServers`, so touching anything else would be destructive.
async function writeJsonKey(file, key, entries, dropped, opts) {
  let doc = {};
  if (existsSync(file)) {
    try {
      doc = JSON.parse(await readFile(file, 'utf8'));
    } catch (e) {
      return { error: `${file} is not valid JSON (${e.message}) — refusing to overwrite it` };
    }
  }
  const before = JSON.stringify(doc[key] ?? {});
  const bucket = { ...(doc[key] ?? {}) };
  for (const name of dropped) delete bucket[name];
  Object.assign(bucket, entries);
  doc[key] = bucket;
  const after = JSON.stringify(doc[key]);
  if (before === after) return { changed: false };
  if (!opts.dryRun) await atomicWrite(file, JSON.stringify(doc, null, 2) + '\n', opts);
  return { changed: true };
}

// Replace (or append) the delimited region this script owns, leaving hand-written
// TOML above and below it untouched.
async function writeTomlBlock(file, body, opts) {
  const existing = existsSync(file) ? await readFile(file, 'utf8') : '';
  const block = body.trim() ? `${BEGIN}\n${body.trim()}\n${END}\n` : '';
  const marked = new RegExp(`\\n?${escapeRe(BEGIN)}[\\s\\S]*?${escapeRe(END)}\\n?`, 'g');
  const base = existing.replace(marked, '\n').replace(/\n{3,}/g, '\n\n');
  const next = block ? `${base.trimEnd()}\n\n${block}`.replace(/^\n+/, '') : base.trimEnd() + '\n';
  if (next === existing) return { changed: false };
  if (!opts.dryRun) await atomicWrite(file, next, opts);
  return { changed: true };
}

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

async function atomicWrite(file, content, opts) {
  await mkdir(dirname(file), { recursive: true });
  if (existsSync(file)) await copyFile(file, `${file}.bak`);
  const tmp = `${file}.agent-skills.tmp`;
  await writeFile(tmp, content);
  // Written before the rename so the secret is never briefly world-readable.
  if (opts.materialize) await chmod(tmp, 0o600);
  await rename(tmp, file);
}

// ---------------------------------------------------------------------------
// Adapters
// ---------------------------------------------------------------------------
//
// `caps` says, per slot, how this agent can reference an environment variable:
//   template     — a placeholder inside the value string; `ref()` builds it
//   named        — a dedicated field that takes the variable's *name*
//   unsupported  — no indirection; the value would have to be the literal secret
//
// Every capability below is either verified on this machine or cited to the agent's
// own docs. When in doubt the honest answer is `unsupported`: that skips a server
// with a visible reason, where a wrong `template` would ship a config that silently
// sends the literal string `${TOKEN}` as a credential.

const ADAPTERS = [
  {
    id: 'claude-code',
    label: 'Claude Code',
    // Verified on 2.1.220: user-scope `.claude.json` expands ${VAR} in both stdio
    // `env` values and HTTP `headers` values.
    caps: { env: 'template', headers: 'template' },
    ref: (n) => `\${${n}}`,
    // One target per profile, and every profile gets the same set. CLAUDE_CONFIG_DIR
    // is a *candidate*, never an override: running this from inside a claude-perso
    // session must still configure the work profile, or the two would drift.
    targets() {
      const dirs = new Set(['.claude-work', '.claude-perso', '.claude'].map((d) => join(HOME, d)).filter(existsSync));
      if (process.env.CLAUDE_CONFIG_DIR) dirs.add(process.env.CLAUDE_CONFIG_DIR);
      return [...dirs].map((dir) => ({
        id: `claude-code:${dir.replace(/.*\.claude-?/, '') || 'default'}`,
        file: join(dir, '.claude.json'),
      }));
    },
    server(def, r) {
      if (def.transport === 'stdio') {
        return { command: def.command, ...(def.args && { args: def.args }), ...(r.env && { env: r.env }) };
      }
      return { type: 'http', url: def.url, ...(r.headers && { headers: r.headers }) };
    },
    write: (t, entries, dropped, opts) => writeJsonKey(t.file, 'mcpServers', entries, dropped, opts),
  },

  {
    id: 'codex',
    label: 'Codex',
    // `env_http_headers` maps a header name to an environment variable name, and
    // `bearer_token_env_var` does the same for bearer auth — so headers are fully
    // expressible. `[mcp_servers.x.env]` takes literal values only (openai/codex
    // #24401), so stdio secrets are not.
    caps: { env: 'unsupported', headers: 'named' },
    targets: () => (existsSync(join(HOME, '.codex')) ? [{ id: 'codex', file: join(HOME, '.codex', 'config.toml') }] : []),
    server(def, r, name) {
      const lines = [`[mcp_servers.${tomlKey(name)}]`];
      if (def.transport === 'stdio') {
        lines.push(`command = ${tomlString(def.command)}`);
        if (def.args?.length) lines.push(`args = [${def.args.map(tomlString).join(', ')}]`);
        if (r.env && Object.keys(r.env).length) lines.push(`env = ${tomlInline(r.env)}`);
      } else {
        lines.push(`url = ${tomlString(def.url)}`);
        if (r.bearerEnv) lines.push(`bearer_token_env_var = ${tomlString(r.bearerEnv)}`);
        if (r.staticHeaders && Object.keys(r.staticHeaders).length) {
          lines.push(`http_headers = ${tomlInline(r.staticHeaders)}`);
        }
        if (r.envHeaders && Object.keys(r.envHeaders).length) {
          lines.push(`env_http_headers = ${tomlInline(r.envHeaders)}`);
        }
      }
      return lines.join('\n');
    },
    write: (t, entries, _dropped, opts) => writeTomlBlock(t.file, Object.values(entries).join('\n\n'), opts),
  },

  {
    id: 'opencode',
    label: 'opencode',
    // https://opencode.ai/docs/mcp-servers — `{env:NAME}` is substituted while the
    // config loads, in every string value including headers.
    caps: { env: 'template', headers: 'template' },
    ref: (n) => `{env:${n}}`,
    targets: () =>
      existsSync(join(HOME, '.config', 'opencode'))
        ? [{ id: 'opencode', file: join(HOME, '.config', 'opencode', 'opencode.json') }]
        : [],
    server(def, r) {
      if (def.transport === 'stdio') {
        return { type: 'local', command: [def.command, ...(def.args ?? [])], enabled: true, ...(r.env && { environment: r.env }) };
      }
      // oauth:false is required for a server that authenticates by header alone;
      // otherwise opencode attempts an OAuth handshake the endpoint will refuse.
      return { type: 'remote', url: def.url, enabled: true, oauth: false, ...(r.headers && { headers: r.headers }) };
    },
    write: (t, entries, dropped, opts) => writeJsonKey(t.file, 'mcp', entries, dropped, opts),
  },

  {
    id: 'vscode',
    label: 'VS Code',
    caps: { env: 'template', headers: 'template' },
    ref: (n) => `\${env:${n}}`,
    targets: () =>
      existsSync(join(HOME, '.config', 'Code', 'User'))
        ? [{ id: 'vscode', file: join(HOME, '.config', 'Code', 'User', 'mcp.json') }]
        : [],
    server(def, r) {
      if (def.transport === 'stdio') {
        return { type: 'stdio', command: def.command, ...(def.args && { args: def.args }), ...(r.env && { env: r.env }) };
      }
      return { type: 'http', url: def.url, ...(r.headers && { headers: r.headers }) };
    },
    write: (t, entries, dropped, opts) => writeJsonKey(t.file, 'servers', entries, dropped, opts),
  },

  {
    id: 'cursor',
    label: 'Cursor',
    // `${env:NAME}` resolves for stdio servers but is sent literally in the headers
    // of remote servers — a reported bug, so headers are treated as unsupported.
    caps: { env: 'template', headers: 'unsupported' },
    ref: (n) => `\${env:${n}}`,
    targets: () => (existsSync(join(HOME, '.cursor')) ? [{ id: 'cursor', file: join(HOME, '.cursor', 'mcp.json') }] : []),
    server(def, r) {
      if (def.transport === 'stdio') {
        return { command: def.command, ...(def.args && { args: def.args }), ...(r.env && { env: r.env }) };
      }
      return { url: def.url, ...(r.headers && { headers: r.headers }) };
    },
    write: (t, entries, dropped, opts) => writeJsonKey(t.file, 'mcpServers', entries, dropped, opts),
  },

  {
    id: 'gemini-cli',
    label: 'Gemini CLI',
    // `$NAME` / `${NAME}` expand in `env`; header values are documented as literal
    // strings (google-gemini/gemini-cli #5282).
    caps: { env: 'template', headers: 'unsupported' },
    ref: (n) => `$${n}`,
    targets: () => (existsSync(join(HOME, '.gemini')) ? [{ id: 'gemini-cli', file: join(HOME, '.gemini', 'settings.json') }] : []),
    server(def, r) {
      if (def.transport === 'stdio') {
        return { command: def.command, ...(def.args && { args: def.args }), ...(r.env && { env: r.env }) };
      }
      return { httpUrl: def.url, ...(r.headers && { headers: r.headers }) };
    },
    write: (t, entries, dropped, opts) => writeJsonKey(t.file, 'mcpServers', entries, dropped, opts),
  },
];

// ---------------------------------------------------------------------------
// Per-server rendering
// ---------------------------------------------------------------------------

// Produce the adapter-native entry for one server, or a reason it was skipped.
function renderServer(adapter, name, def, opts) {
  const r = {};

  if (def.transport === 'stdio') {
    if (def.env) {
      const out = {};
      for (const [k, v] of Object.entries(def.env)) {
        const got = resolve(v, adapter.caps.env, adapter, SLOT.env, opts);
        if (!got.ok) return { skip: got.reason };
        out[k] = got.value;
      }
      r.env = out;
    }
    return { entry: adapter.server(def, r, name) };
  }

  // Bearer auth is modelled separately from plain headers because Codex has a
  // dedicated field for it, and because it is the one case where the credential is
  // a substring ("Bearer <token>") rather than the whole value.
  if (def.auth?.type === 'bearer') {
    const envName = def.auth.token.env;
    if (adapter.caps.headers === 'named') {
      r.bearerEnv = envName;
    } else {
      const got = resolve(def.auth.token, adapter.caps.headers, adapter, SLOT.headers, opts);
      if (!got.ok) return { skip: got.reason };
      r.headers = { ...r.headers, Authorization: `Bearer ${got.value}` };
    }
  }

  for (const [h, v] of Object.entries(def.headers ?? {})) {
    if (adapter.caps.headers === 'named') {
      // Codex splits the two cases across two fields rather than one map.
      if (isRef(v)) (r.envHeaders ??= {})[h] = v.env;
      else (r.staticHeaders ??= {})[h] = v;
      continue;
    }
    const got = resolve(v, adapter.caps.headers, adapter, SLOT.headers, opts);
    if (!got.ok) return { skip: got.reason };
    (r.headers ??= {})[h] = got.value;
  }

  return { entry: adapter.server(def, r, name) };
}

// ---------------------------------------------------------------------------
// Lock file
// ---------------------------------------------------------------------------
//
// Records what was written where, so a server removed from the manifest is also
// removed from the agents. Mirrors ~/.agents/.skill-lock.json, which yadm tracks for
// the same reason: the installed artefacts are disposable, the record of them is not.

async function readLock() {
  if (!existsSync(LOCK)) return { version: 1, targets: {} };
  try {
    return JSON.parse(await readFile(LOCK, 'utf8'));
  } catch {
    return { version: 1, targets: {} };
  }
}

async function writeLock(lock, opts) {
  if (opts.dryRun) return;
  await mkdir(dirname(LOCK), { recursive: true });
  await writeFile(LOCK, JSON.stringify(lock, null, 2) + '\n');
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const opts = { agents: [], dryRun: false, materialize: false, prune: false, list: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--dry-run' || a === '-n') opts.dryRun = true;
    else if (a === '--materialize') opts.materialize = true;
    else if (a === '--prune') opts.prune = true;
    else if (a === '--list' || a === '-l') opts.list = true;
    else if (a === '--agent' || a === '-a') opts.agents.push(argv[++i]);
    else if (a === '--manifest') opts.manifest = argv[++i];
    else if (a === '--help' || a === '-h') opts.help = true;
    else {
      console.error(`unknown argument: ${a}`);
      process.exit(2);
    }
  }
  return opts;
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) {
    const source = await readFile(fileURLToPath(import.meta.url), 'utf8');
    const header = source.split('\n').slice(1); // drop the shebang
    const doc = header.slice(0, header.findIndex((l) => !l.startsWith('//')));
    console.log(doc.map((l) => l.replace(/^\/\/ ?/, '')).join('\n'));
    return;
  }

  const manifestPath = opts.manifest ?? join(ROOT, 'mcp', 'servers.json');
  const manifest = await loadManifest(manifestPath);

  // `"enabled": false` parks a server: it keeps its full definition in the
  // manifest, is not rendered anywhere, and — because the lock records what was
  // written last time — is removed from every agent on the next run. Deleting the
  // entry outright would remove it too, but loses the definition, which is the
  // wrong trade for a server that is only down, or only temporarily unwanted.
  const all = Object.entries(manifest.servers);
  const servers = all.filter(([, def]) => def.enabled !== false);
  const disabled = new Set(all.filter(([, def]) => def.enabled === false).map(([name]) => name));
  const known = new Set(all.map(([name]) => name));

  let adapters = ADAPTERS;
  if (opts.agents.length) {
    const unknown = opts.agents.filter((a) => !ADAPTERS.some((x) => x.id === a));
    if (unknown.length) {
      console.error(`unknown agent(s): ${unknown.join(', ')}`);
      console.error(`known: ${ADAPTERS.map((a) => a.id).join(', ')}`);
      process.exit(2);
    }
    adapters = ADAPTERS.filter((a) => opts.agents.includes(a.id));
  }

  if (opts.list) {
    console.log(`${servers.length} enabled, ${disabled.size} disabled${disabled.size ? `: ${[...disabled].join(', ')}` : ''}\n`);
    for (const adapter of ADAPTERS) {
      const targets = adapter.targets();
      const where = targets.length ? targets.map((t) => t.file).join(', ') : 'not installed';
      console.log(`${adapter.id.padEnd(12)} env:${adapter.caps.env.padEnd(12)} headers:${adapter.caps.headers.padEnd(12)} ${where}`);
    }
    return;
  }

  if (disabled.size && !opts.prune) {
    console.log(`  · disabled in the manifest, will be removed where installed: ${[...disabled].join(', ')}\n`);
  }

  if (opts.materialize) {
    console.warn('! --materialize writes real credentials into agent config files (mode 0600).');
    console.warn('! Those files are secrets at rest, and rotating a credential means re-running this.\n');
  }

  const lock = await readLock();
  let wrote = 0;

  for (const adapter of adapters) {
    const detected = adapter.targets();
    // Pruning has to reach targets that are no longer detected — an agent can be
    // uninstalled after this script wrote to it, and the lock is the only record.
    const stale = opts.prune
      ? Object.entries(lock.targets)
          .filter(([id]) => id === adapter.id || id.startsWith(`${adapter.id}:`))
          .filter(([id]) => !detected.some((t) => t.id === id))
          .map(([id, v]) => ({ id, file: v.file }))
      : [];
    const targets = [...detected, ...stale];

    if (!targets.length) {
      if (opts.agents.includes(adapter.id)) console.log(`- ${adapter.label}: not installed, nothing to do`);
      continue;
    }

    const entries = {};
    // Skips are grouped by reason rather than listed per server: an agent that
    // cannot do secret headers fails the same way fifteen times, and fifteen
    // identical lines bury the two that are actually different.
    const skipped = new Map();
    for (const [name, def] of servers) {
      if (opts.prune) continue;
      const { entry, skip } = renderServer(adapter, name, def, opts);
      if (skip) skipped.set(skip.text, [...(skipped.get(skip.text) ?? []), name]);
      else entries[name] = entry;
    }
    for (const [text, names] of skipped) {
      console.log(`  ! ${adapter.id}: skipped ${names.length} — ${text}\n    ${names.join(', ')}`);
    }

    for (const target of targets) {
      const previous = lock.targets[target.id]?.servers ?? [];
      const dropped = previous.filter((n) => !(n in entries));
      const result = await adapter.write(target, entries, dropped, opts);

      if (result.error) {
        console.error(`✗ ${target.id}: ${result.error}`);
        process.exitCode = 1;
        continue;
      }

      const count = Object.keys(entries).length;
      const mark = result.changed || opts.dryRun ? '✓' : '·';
      const what = opts.prune
        ? `${opts.dryRun ? 'would remove' : 'removed'} ${dropped.length} server(s)`
        : result.changed || opts.dryRun
          ? `${opts.dryRun ? 'would write' : 'wrote'} ${count}/${servers.length} servers`
          : `unchanged — ${count}/${servers.length} servers`;
      console.log(`${mark} ${target.id.padEnd(20)} ${what} → ${target.file}`);
      // Three different things land in `dropped`, and they are not interchangeable
      // to someone deciding whether something broke: a server parked on purpose, a
      // server deleted from the manifest, and a server this agent stopped being able
      // to express. Say which.
      if (dropped.length && !opts.prune) {
        const why = (n) =>
          disabled.has(n) ? 'disabled in the manifest'
          : known.has(n) ? 'no longer expressible by this agent'
          : 'removed from the manifest';
        const groups = new Map();
        for (const n of dropped) groups.set(why(n), [...(groups.get(why(n)) ?? []), n]);
        for (const [reason, names] of groups) console.log(`    dropped ${names.join(', ')} — ${reason}`);
      }

      if (count) lock.targets[target.id] = { file: target.file, servers: Object.keys(entries) };
      else delete lock.targets[target.id];
      if (result.changed) wrote++;
    }
  }

  await writeLock(lock, opts);
  if (!wrote && !opts.dryRun) console.log('\nNothing changed.');
}

// Importable for scripts/validate.mjs; only runs the CLI when invoked directly.
if (process.argv[1] === fileURLToPath(import.meta.url)) await main();
