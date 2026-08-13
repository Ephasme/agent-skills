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
//   Oh My Pi      ${NAME}          in env and headers          (verified, 17.2.9)
//   opencode      {env:NAME}       in env and headers
//   VS Code       ${env:NAME}      in env and headers
//   Codex         env_http_headers / bearer_token_env_var for headers; env is literal
//                 — a stdio server is launched through a shim instead, see below
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
// One slot has a third answer. When the agent cannot reference a variable but *does*
// let the manifest choose the program it spawns, the reference can be resolved one
// level down — by the launch itself rather than by the agent. That is `env: 'shim'`
// (Codex, stdio only); `envShimCommand` below is the whole mechanism.
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

import { readFile, writeFile, mkdir, rename, chmod, copyFile, stat, unlink, realpath } from 'node:fs/promises';
import { existsSync, realpathSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, dirname, relative, isAbsolute, resolve as resolvePath } from 'node:path';
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
  if (manifest === null || typeof manifest !== 'object' || Array.isArray(manifest)) {
    fail('manifest must be a JSON object');
    return;
  }
  if (manifest.version !== 1) fail(`unsupported manifest version ${manifest.version}`);
  if (manifest.servers !== undefined && (manifest.servers === null || typeof manifest.servers !== 'object' || Array.isArray(manifest.servers))) {
    fail('`servers` must be an object');
    return;
  }
  for (const [name, def] of Object.entries(manifest.servers ?? {})) {
    const at = (msg) => fail(`server \`${name}\`: ${msg}`);
    if (!/^[a-z0-9][a-z0-9-]*$/.test(name)) at('name must be lowercase kebab-case');
    // Every check below indexes into `def`. A null or scalar entry — a trailing-comma
    // cleanup, a half-finished paste — would otherwise throw a raw TypeError out of
    // both this script and validate.mjs, naming neither the file nor the server.
    if (def === null || typeof def !== 'object' || Array.isArray(def)) {
      at('must be an object');
      continue;
    }
    if (seen.has(name.toLowerCase())) at('duplicate name');
    seen.add(name.toLowerCase());
    // Absent means enabled. A disabled server keeps its full definition — it is
    // parked, not deleted — so the rest of the shape is still validated.
    if ('enabled' in def && typeof def.enabled !== 'boolean') at('`enabled` must be a boolean');
    if ('note' in def && typeof def.note !== 'string') at('`note` must be a string');
    // A parked server with no stated reason is the one that never gets switched
    // back on, because nobody left behind knows what would have to be true first.
    if (def.enabled === false && !def.note) at('a disabled server needs a `note` saying why');

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
// The stdio env shim (`env: 'shim'`)
// ---------------------------------------------------------------------------
//
// Codex spawns a stdio MCP server with a *scrubbed* environment. Verified on
// codex-cli 0.146.0 by pointing a probe server at `env`: the child sees exactly
// HOME, LANG, LOGNAME, PATH, PWD, SHELL, TERM, USER — plus whatever literal
// `[mcp_servers.x.env]` holds — and nothing else the launching shell exported.
// `shell_environment_policy.inherit = "all"` does not reach it either (probed
// separately; the child's env was byte-for-byte the same). So there is no way to
// hand Codex a *reference*: whatever value it passes, it passes literally.
//
// But the manifest chooses the program, and the program's own launch runs in a
// shell. So the reference is resolved one level down: `sh -c` sources the same
// ~/.config/secrets.zsh every other agent resolves its `${NAME}` against, then
// re-execs the real command through `env -i` carrying Codex's own core set plus
// *only* the variables this server's manifest entry names. Two properties matter —
// nothing secret is written to config.toml (the point of the whole reference
// model), and sourcing a file of 30-odd exports does not leak the other 27 into
// the server's environment.
//
// A variable that is unset at spawn time is simply not passed, rather than passed
// empty: BW_SESSION is minted per-shell by `bwunlock` and lives nowhere on disk, so
// for Codex it is usually absent — the Bitwarden server then starts locked and its
// own `unlock` tool establishes the session.
const SECRETS_FILE = process.env.AGENT_SECRETS_FILE ?? '$HOME/.config/secrets.zsh';

// Codex's own core set, minus PWD (which `env -i` re-derives and which no server
// should be told to trust anyway).
const SHIM_CORE_ENV = ['HOME', 'PATH', 'USER', 'LOGNAME', 'LANG', 'SHELL', 'TERM'];

const shQuote = (s) => `'${String(s).replace(/'/g, `'\\''`)}'`;

// `refs` is [[targetVariable, sourceVariable]] — the manifest may rename, so the
// left-hand side is what the server reads and the right-hand side is what the
// secrets file exports.
function envShimCommand(def, refs) {
  const script = [
    // `.` is a special builtin: a missing file would *exit* the shell in dash, so
    // the guard is what keeps a machine without the secrets file merely credential-
    // less rather than unable to start the server at all.
    `[ -r "${SECRETS_FILE}" ] && . "${SECRETS_FILE}"`,
    'set --',
    ...refs.map(([target, source]) =>
      `[ -n "\${${source}:-}" ] && set -- "$@" "${target}=\$${source}"`),
    `exec env -i ${SHIM_CORE_ENV.map((v) => `${v}="\$${v}"`).join(' ')} "$@" ` +
      [def.command, ...(def.args ?? [])].map(shQuote).join(' '),
  ].join('; ');
  return { command: '/bin/sh', args: ['-c', script] };
}

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

// VS Code and Gemini CLI both ship their config with a `// …` header and document
// comments as supported, so `JSON.parse` rejects a perfectly stock file. Strip
// comments for the read; the write cannot preserve them, which the caller reports.
function parseJsonc(text) {
  let out = '';
  let inString = false;
  let escaped = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inString) {
      out += c;
      if (escaped) escaped = false;
      else if (c === '\\') escaped = true;
      else if (c === '"') inString = false;
      continue;
    }
    if (c === '"') { inString = true; out += c; continue; }
    if (c === '/' && text[i + 1] === '/') {
      while (i < text.length && text[i] !== '\n') i++;
      out += '\n';
      continue;
    }
    if (c === '/' && text[i + 1] === '*') {
      const end = text.indexOf('*/', i + 2);
      i = end === -1 ? text.length : end + 1;
      out += ' ';
      continue;
    }
    out += c;
  }
  // Trailing commas are legal in both dialects and fatal to JSON.parse.
  return JSON.parse(out.replace(/,(\s*[}\]])/g, '$1'));
}

// Read-modify-write of a single top-level key, preserving everything else in the
// file. Claude Code's `.claude.json` is 60 KB of live session state that happens to
// also hold `mcpServers`, so touching anything else would be destructive.
async function writeJsonKey(file, key, entries, dropped, opts) {
  let doc = {};
  let hadComments = false;
  if (existsSync(file)) {
    const raw = await readFile(file, 'utf8');
    try {
      doc = JSON.parse(raw);
    } catch {
      try {
        doc = parseJsonc(raw);
        hadComments = true;
      } catch (e) {
        return { error: `${file} is not valid JSON or JSONC (${e.message}) — refusing to overwrite it` };
      }
    }
  }
  const before = JSON.stringify(doc[key] ?? {});
  const bucket = { ...(doc[key] ?? {}) };
  for (const name of dropped) delete bucket[name];
  // Overwriting an entry this script did not write loses a hand-written server
  // silently, and the lock would then claim it so `--prune` deletes it outright.
  // Adopting it is the lesser evil only if it is said out loud.
  const adopted = Object.keys(entries).filter((n) => n in bucket && !dropped.includes(n) && !opts.owned.has(n));
  Object.assign(bucket, entries);
  doc[key] = bucket;
  const after = JSON.stringify(doc[key]);
  const notes = [];
  if (adopted.length) notes.push(`overwrote hand-written entr(ies): ${adopted.join(', ')}`);
  if (hadComments && before !== after) notes.push('comments in this file were not preserved');
  if (before === after) return { changed: false, notes };
  if (!opts.dryRun) {
    const err = await atomicWrite(file, JSON.stringify(doc, null, 2) + '\n', opts);
    if (err) return { error: err };
  }
  return { changed: true, notes };
}

// Replace (or append) the delimited region this script owns, leaving hand-written
// TOML above and below it untouched.
async function writeTomlBlock(file, body, opts) {
  const existing = existsSync(file) ? await readFile(file, 'utf8') : '';
  const block = body.trim() ? `${BEGIN}\n${body.trim()}\n${END}\n` : '';
  const marked = new RegExp(`\\n*${escapeRe(BEGIN)}[\\s\\S]*?${escapeRe(END)}[^\\n]*\\n?`, 'g');
  // Only the seam left by the removed block is collapsed. A global
  // `\n{3,}` -> `\n\n` would reach inside hand-written multi-line basic strings and
  // silently change their value, which is exactly what this promises not to do.
  const base = existing.replace(marked, '\n\n');
  const next = block
    ? (base.trim() ? `${base.replace(/\n+$/, '')}\n\n${block}` : block)
    : (base.trim() ? `${base.replace(/\n+$/, '')}\n` : '');
  if (next === existing) return { changed: false };
  if (!opts.dryRun) {
    const err = await atomicWrite(file, next, opts);
    if (err) return { error: err };
  }
  return { changed: true };
}

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Returns an error string, or undefined on success.
async function atomicWrite(file, content, opts) {
  await mkdir(dirname(file), { recursive: true });

  // The target may be live session state that its agent is writing to right now
  // (Claude Code's `.claude.json`). There is no lock to take, so compare-and-swap:
  // if the file changed between the caller's read and this write, the merge was
  // computed against a stale document and renaming over it would discard whatever
  // the agent wrote in between.
  let before;
  if (existsSync(file)) {
    const s = await stat(file);
    before = `${s.mtimeMs}:${s.size}`;
    if (opts.readStamp && opts.readStamp.get(file) !== before) {
      return `${file} changed on disk while this ran (an agent has it open) — nothing written, re-run when it is idle`;
    }
  }

  // Preserve the target's permissions. Claude Code creates `.claude.json` 0600 and
  // it holds oauth state and the whole per-project history; taking the mode from the
  // umask instead would quietly publish it to every other local account.
  let mode = 0o600;
  if (existsSync(file)) mode = (await stat(file)).mode & 0o777;
  if (opts.materialize) mode &= 0o600;

  // The backup inherits the target's secrecy — after a `--materialize` run it holds
  // the same plaintext credentials the target does.
  if (existsSync(file)) {
    await copyFile(file, `${file}.bak`);
    await chmod(`${file}.bak`, mode);
  }
  const tmp = `${file}.agent-skills.tmp`;
  await writeFile(tmp, content);
  // Set before the rename so the file is never briefly readable at the umask.
  await chmod(tmp, mode);

  if (existsSync(file)) {
    const s = await stat(file);
    if (`${s.mtimeMs}:${s.size}` !== before) {
      await unlink(tmp);
      return `${file} changed on disk while this ran (an agent has it open) — nothing written, re-run when it is idle`;
    }
  }
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
    //
    // The default profile is NOT `~/.claude/.claude.json`. With CLAUDE_CONFIG_DIR
    // unset Claude Code reads `~/.claude.json` — verified against 2.1.220 — and
    // `~/.claude` exists here for unrelated reasons (rtk artefacts), so treating it
    // as a config dir writes 13 servers to a file nothing ever loads.
    targets() {
      const found = [];
      for (const name of ['.claude-work', '.claude-perso']) {
        const dir = join(HOME, name);
        if (existsSync(dir)) found.push({ id: `claude-code:${name.slice('.claude-'.length)}`, file: join(dir, '.claude.json') });
      }
      if (process.env.CLAUDE_CONFIG_DIR) {
        const dir = process.env.CLAUDE_CONFIG_DIR;
        const file = join(dir, '.claude.json');
        if (!found.some((t) => t.file === file)) {
          found.push({ id: `claude-code:${dir.replace(/.*\.claude-?/, '') || 'env'}`, file });
        }
      }
      // Only claim the profile-less config when it is actually in use; creating it
      // would hand a bare `claude` a config it never had.
      const bare = join(HOME, '.claude.json');
      if (existsSync(bare) && !found.some((t) => t.file === bare)) {
        found.push({ id: 'claude-code:default', file: bare });
      }
      return found;
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
    id: 'omp',
    label: 'Oh My Pi',
    // Same `${NAME}` dialect as Claude Code, and rather more thoroughly: omp maps
    // its expander over the entire parsed `mcpServers` object, so every string at
    // any depth is substituted — env values, header values, url, command, args.
    // It also understands `${NAME:-default}`, and leaves an unresolved reference
    // as the literal `${NAME}` rather than the empty string. Verified by reading
    // 17.2.9 (packages/coding-agent discovery: `K1(h.mcpServers)` over the file,
    // where K1 recurses and applies /\$\{([^}:]+)(?::-([^}]*))?\}/g against
    // Bun.env).
    caps: { env: 'template', headers: 'template' },
    ref: (n) => `\${${n}}`,
    // One target per profile, mirroring the Claude Code adapter — and for the
    // same reason: running this from inside an omp-perso session must still
    // configure the work profile, or the two drift. PI_CONFIG_DIR is therefore a
    // *candidate*, never an override.
    //
    // The user-scope file is <root>/agent/mcp.json, one level below the config
    // root (`omp config path` prints that agent dir). The profile-less
    // ~/.omp/agent/mcp.json is claimed only when it already exists: this machine
    // launches omp exclusively through omp-work / omp-perso, so creating it would
    // hand a bare `omp` a config it never had.
    targets() {
      const found = [];
      const add = (id, root) => {
        const file = join(root, 'agent', 'mcp.json');
        if (!found.some((t) => t.file === file)) found.push({ id: `omp:${id}`, file });
      };
      for (const name of ['.omp-work', '.omp-perso']) {
        const dir = join(HOME, name);
        if (existsSync(dir)) add(name.slice('.omp-'.length), dir);
      }
      // A bare name, not a path — omp resolves it against $HOME.
      if (process.env.PI_CONFIG_DIR) {
        const dir = join(HOME, process.env.PI_CONFIG_DIR);
        if (existsSync(dir)) add(process.env.PI_CONFIG_DIR.replace(/^\.omp-?/, '') || 'env', dir);
      }
      const bare = join(HOME, '.omp');
      if (existsSync(join(bare, 'agent', 'mcp.json'))) add('default', bare);
      return found;
    },
    // `type` is omp's transport discriminator, the same key Claude Code uses; a
    // stdio server omits it and is recognised by `command`.
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
    // #24401), so a stdio secret is resolved by the launch instead — see
    // `envShimCommand`.
    caps: { env: 'shim', headers: 'named' },
    targets: () => (existsSync(join(HOME, '.codex')) ? [{ id: 'codex', file: join(HOME, '.codex', 'config.toml') }] : []),
    server(def, r, name) {
      const lines = [`[mcp_servers.${tomlKey(name)}]`];
      if (def.transport === 'stdio') {
        // A shimmed server is spawned through `sh -c`; the manifest's command becomes
        // the tail of that script, so it is never both.
        const spawn = r.shim ? envShimCommand(def, r.shim) : { command: def.command, args: def.args };
        lines.push(`command = ${tomlString(spawn.command)}`);
        if (spawn.args?.length) lines.push(`args = [${spawn.args.map(tomlString).join(', ')}]`);
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
    // TOML forbids declaring the same table twice, and Codex refuses to load its
    // *entire* configuration on a duplicate — model, approval policy, profiles, not
    // just MCP. A hand-written `[mcp_servers.github]` outside the managed block would
    // collide with the rendered one, so those are dropped with a reason instead.
    async write(t, entries, _dropped, opts) {
      const existing = existsSync(t.file) ? await readFile(t.file, 'utf8') : '';
      const outside = existing.replace(
        new RegExp(`${escapeRe(BEGIN)}[\\s\\S]*?${escapeRe(END)}`, 'g'), '');
      const clash = Object.keys(entries).filter((name) =>
        new RegExp(`^\\s*\\[mcp_servers\\.(${escapeRe(name)}|"${escapeRe(name)}")\\]`, 'm').test(outside));
      for (const name of clash) delete entries[name];
      const result = await writeTomlBlock(t.file, Object.values(entries).join('\n\n'), opts);
      if (clash.length) {
        result.notes = [`hand-written [mcp_servers.${clash.join('], [mcp_servers.')}] already in ${t.file} — left alone, not rendered (a duplicate table stops Codex loading any config)`];
      }
      return result;
    },
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
        // `--materialize` deliberately outranks the shim: the whole point of that
        // flag is a config that stands alone, with no secrets file to read.
        if (isRef(v) && adapter.caps.env === 'shim' && !opts.materialize) {
          (r.shim ??= []).push([k, v.env]);
          continue;
        }
        const got = resolve(v, adapter.caps.env, adapter, SLOT.env, opts);
        if (!got.ok) return { skip: got.reason };
        out[k] = got.value;
      }
      if (Object.keys(out).length) r.env = out;
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

// Paths are stored relative to $HOME. The lock is yadm-tracked, and an absolute
// /home/debian/... in it makes every other machine's first health check report three
// targets "gone" when nothing is wrong.
const packPath = (p) => (isAbsolute(p) && !relative(HOME, p).startsWith('..') ? relative(HOME, p) : p);
const unpackPath = (p) => (isAbsolute(p) ? p : resolvePath(HOME, p));

async function readLock() {
  if (!existsSync(LOCK)) return { version: 1, targets: {} };
  let raw;
  try {
    raw = JSON.parse(await readFile(LOCK, 'utf8'));
  } catch (e) {
    // Returning an empty lock here would be silently catastrophic rather than
    // merely broken: `dropped` is computed from it, so every removal — a parked
    // server, a deleted one, `--prune` — becomes a no-op that still reports success.
    console.error(`✗ ${LOCK} does not parse (${e.message}).`);
    console.error('  It records what is installed where; without it nothing can be removed.');
    console.error('  Fix or delete it — deleting means the renderer forgets what it wrote and');
    console.error('  every already-installed server has to be removed by hand.');
    process.exit(1);
  }
  const targets = {};
  for (const [id, entry] of Object.entries(raw.targets ?? {})) {
    targets[id] = { ...entry, file: unpackPath(entry.file ?? '') };
  }
  return { version: 1, targets };
}

async function writeLock(lock, opts) {
  if (opts.dryRun) return;
  await mkdir(dirname(LOCK), { recursive: true });
  const packed = { version: 1, targets: {} };
  for (const [id, entry] of Object.entries(lock.targets)) {
    packed.targets[id] = { ...entry, file: packPath(entry.file) };
  }
  // Temp-and-rename: a partial write here is the corruption that readLock now has
  // to refuse, and an interrupted `writeFile` is exactly how it would happen.
  const tmp = `${LOCK}.tmp`;
  await writeFile(tmp, JSON.stringify(packed, null, 2) + '\n');
  await rename(tmp, LOCK);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const opts = {
    agents: [], dryRun: false, materialize: false, prune: false, list: false,
    // Populated per target: the mtime/size seen when the target was read, so the
    // write can refuse if its owning agent touched the file in between.
    readStamp: new Map(),
    // Server names this script wrote to the current target last time; anything else
    // already in the file is the user's, not ours to replace without saying so.
    owned: new Set(),
  };
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
  const disabled = new Map(all.filter(([, def]) => def.enabled === false).map(([name, def]) => [name, def.note]));
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
    console.log(`${servers.length} enabled, ${disabled.size} disabled`);
    for (const [name, note] of disabled) console.log(`  · ${name} — ${note}`);
    console.log();
    for (const adapter of ADAPTERS) {
      const targets = adapter.targets();
      const where = targets.length ? targets.map((t) => t.file).join(', ') : 'not installed';
      console.log(`${adapter.id.padEnd(12)} env:${adapter.caps.env.padEnd(12)} headers:${adapter.caps.headers.padEnd(12)} ${where}`);
    }
    return;
  }

  if (disabled.size && !opts.prune) {
    console.log(`  · disabled in the manifest, removed where installed: ${[...disabled.keys()].join(', ')}\n`);
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
    const unexpressible = [];
    for (const [name, def] of servers) {
      if (opts.prune) continue;
      const { entry, skip } = renderServer(adapter, name, def, opts);
      if (skip) {
        skipped.set(skip.text, [...(skipped.get(skip.text) ?? []), name]);
        unexpressible.push(name);
      } else entries[name] = entry;
    }
    for (const [text, names] of skipped) {
      console.log(`  ! ${adapter.id}: skipped ${names.length} — ${text}\n    ${names.join(', ')}`);
    }

    for (const target of targets) {
      const previous = lock.targets[target.id]?.servers ?? [];
      const dropped = previous.filter((n) => !(n in entries));
      // Stamp the target before the adapter reads it, so atomicWrite can tell
      // whether the agent that owns the file wrote to it in the meantime.
      if (existsSync(target.file)) {
        const s = await stat(target.file);
        opts.readStamp.set(target.file, `${s.mtimeMs}:${s.size}`);
      }
      opts.owned = new Set(previous);
      const result = await adapter.write(target, entries, dropped, opts);

      if (result.error) {
        console.error(`✗ ${target.id}: ${result.error}`);
        process.exitCode = 1;
        continue;
      }
      for (const note of result.notes ?? []) console.log(`  ! ${target.id}: ${note}`);

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

      // `unexpressible` is recorded so agents-doctor can tell the two reasons a
      // server is not installed apart: one is fixed by re-running the renderer, the
      // other never can be, because this agent structurally cannot carry it.
      if (count || unexpressible.length) {
        lock.targets[target.id] = {
          file: target.file,
          servers: Object.keys(entries),
          ...(unexpressible.length && { unexpressible }),
        };
      } else delete lock.targets[target.id];
      if (result.changed) wrote++;
    }
  }

  await writeLock(lock, opts);
  if (!wrote && !opts.dryRun) console.log('\nNothing changed.');
}

// Importable for scripts/validate.mjs; only runs the CLI when invoked directly.
// Compared through realpath: a checkout reached by a symlinked path (a symlinked
// ~/code, /tmp on macOS) makes the raw string comparison false, and main() would
// then silently never run — bootstrap printing "Done." having written nothing.
const invokedDirectly = process.argv[1]
  && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url));
if (invokedDirectly) await main();
