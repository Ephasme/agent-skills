#!/usr/bin/env node
// Install the servers in servers.json into every agent that reads a JSON config:
// omp's ~/.omp/agent/mcp.json and Claude Code's ~/.claude.json (user scope).
//
// No credential is written to either file. omp gets a `!` indirection to mcp/secret.sh
// and Claude Code a headersHelper pointing at mcp/headers.mjs, both of which read
// mcp/secrets.sops.yaml at connection time — a static "Bearer ${VAR}" header would have
// the agent send that literal text as the credential, because neither expands an unset
// variable.
//
// Usage: node mcp/install.mjs [--dry-run] [--only omp|claude] [--manifest <path>]… [--skip <name>]…
//
// `--manifest` adds another catalog's server list — each server keeps that catalog's own
// helpers, so a second repo's servers read that repo's secrets. Repeat it for each one; the
// default is this repo's own servers.json. `--skip` leaves out a server an added manifest lists
// (never this repo's own), and removes it from the targets if an earlier run wrote it from there.

import { closeSync, copyFileSync, mkdirSync, openSync, readFileSync, renameSync, statSync, writeFileSync } from 'node:fs';
import childProcess from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const HOME = process.env.HOME;
const REF = /^(.*?)\$\{([A-Z0-9_]+)\}$/;

const argv = process.argv.slice(2);
const dryRun = argv.includes('--dry-run');
const only = argv.includes('--only') ? argv[argv.indexOf('--only') + 1] : null;
const valuesOf = (flag) => argv.flatMap((a, i) => (a === flag && argv[i + 1] ? [argv[i + 1]] : []));
const extra = valuesOf('--manifest').map((p) => resolve(p));
const skip = new Set(valuesOf('--skip'));

const manifests = [join(HERE, 'servers.json'), ...extra].map((path, i) => ({
  dir: dirname(path),
  servers: Object.fromEntries(
    Object.entries(JSON.parse(readFileSync(path, 'utf8'))).filter(([name]) => i === 0 || !skip.has(name)),
  ),
}));
const servers = Object.assign({}, ...manifests.map((m) => m.servers));
// The last catalog declaring a name wins the merge above, so it is also the one whose helpers
// must serve it — anything else pairs one catalog's server with another catalog's secrets.
const catalogOf = (name) => manifests.findLast((m) => name in m.servers).dir;

/** omp runs a `!`-prefixed header value through /bin/sh -c and drops the header if it prints
 * nothing — config/resolve-config-value.ts and mcp/manager.ts in can1357/oh-my-pi. */
const ompHeader = (value, dir) => {
  const ref = REF.exec(value);
  return ref ? `!sh ${join(dir, 'secret.sh')} '${ref[1]}' ${ref[2]}` : value;
};

// omp and Claude Code expand no ${VAR} inside `oauth`/`auth` (only env/headers get
// resolution), so placeholders there must be resolved at install time — via the same
// secret.sh indirection omp headers use. A `${VAR}` the secrets file does not define
// yields an empty string and aborts the install: a literal "${SLACK_CLIENT_ID}" sent as
// a client id produces Slack's "Invalid client_id parameter" screen, which is how the
// bug surfaced the first time.
const resolveOauthPlaceholders = (oauth, dir) =>
  Object.fromEntries(
    Object.entries(oauth).map(([k, v]) => {
      if (typeof v !== 'string') return [k, v];
      const ref = REF.exec(v);
      if (!ref) return [k, v];
      const { execFileSync } = childProcess;
      const value = execFileSync('/bin/sh', [join(dir, 'secret.sh'), '', ref[2]], { encoding: 'utf8' }).trim();
      if (!value) throw new Error(`${ref[2]} missing from ${join(dir, 'secrets.sops.yaml')} — run node mcp/keys.mjs`);
      return [k, value];
    }),
  );

const targets = {
  omp: {
    path: join(HOME, '.omp/agent/mcp.json'),
    render: () => ({
      $schema:
        'https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/src/config/mcp-schema.json',
      mcpServers: Object.fromEntries(
        Object.entries(servers).map(([name, s]) => {
          const out = { type: s.type, url: s.url };
          if (s.headers)
            out.headers = Object.fromEntries(
              Object.entries(s.headers).map(([h, v]) => [h, ompHeader(v, catalogOf(name))]),
            );
          if (s.oauth) out.oauth = resolveOauthPlaceholders(s.oauth, catalogOf(name));
          if (s.auth) out.auth = resolveOauthPlaceholders(s.auth, catalogOf(name));
          return [name, out];
        }),
      ),
    }),
  },
  claude: {
    path: join(HOME, '.claude.json'),
    render: () => ({
      mcpServers: Object.fromEntries(
        Object.entries(servers).map(([name, s]) => {
          const out = { type: 'http', url: s.url };
          if (s.oauth) out.oauth = resolveOauthPlaceholders(s.oauth, catalogOf(name));
          if (s.headers) out.headersHelper = join(catalogOf(name), 'headers.mjs');
          return [name, out];
        }),
      ),
    }),
  },
};

const readTarget = (path) => {
  const stat = statSync(path, { throwIfNoEntry: false });
  if (!stat) return { previous: {}, text: null, mode: 0o600 };
  const text = readFileSync(path, 'utf8');
  return { previous: JSON.parse(text), text, mode: stat.mode & 0o777 };
};

/** Compact when the file is, pretty when it is — ~/.claude.json is one long line. */
const serialise = (doc, text) =>
  (text === null || text.includes('\n') ? JSON.stringify(doc, null, 2) : JSON.stringify(doc)) + '\n';

const lines = [];
let failed = false;

for (const [name, target] of Object.entries(targets)) {
  if (only && only !== name) continue;

  const { previous, text, mode } = readTarget(target.path);
  // The manifest owns `mcpServers` outright; every other key in the target is left alone.
  const doc = { ...previous, ...target.render() };
  const next = serialise(doc, text);

  const was = previous.mcpServers ?? {};
  const added = Object.keys(doc.mcpServers).filter((s) => !(s in was));
  const changed = Object.keys(doc.mcpServers).filter(
    (s) => s in was && JSON.stringify(was[s]) !== JSON.stringify(doc.mcpServers[s]),
  );
  const removed = Object.keys(was).filter((s) => !(s in doc.mcpServers));
  const summary = `+${added.length} ~${changed.length} -${removed.length}`;
  const detail = [
    added.length && `    added:   ${added.join(', ')}`,
    changed.length && `    changed: ${changed.join(', ')}`,
    removed.length && `    removed: ${removed.join(', ')}`,
  ].filter(Boolean);

  if (text !== null && next === text) {
    lines.push(`${name}: unchanged (${Object.keys(doc.mcpServers).length} servers)`);
    continue;
  }

  if (dryRun) {
    lines.push(`${name}: would write ${target.path} (${summary})`, ...detail);
    continue;
  }

  if (text !== null) {
    // Refuse the write when the agent rewrote the file since we read it — Claude Code
    // rewrites ~/.claude.json while it runs.
    if (readFileSync(target.path, 'utf8') !== text) {
      lines.push(`${name}: ${target.path} changed under us — nothing written`);
      failed = true;
      continue;
    }
    copyFileSync(target.path, `${target.path}.bak`);
  }

  // A machine with Claude Code and no omp has no ~/.omp/agent/ yet — readTarget treats the
  // missing file as an empty one, so the directory has to be there before we write into it.
  mkdirSync(dirname(target.path), { recursive: true });

  const tmp = `${target.path}.tmp-${process.pid}`;
  closeSync(openSync(tmp, 'w', mode));
  writeFileSync(tmp, next, { mode });
  renameSync(tmp, target.path);
  lines.push(`${name}: wrote ${target.path} (${summary})`, ...detail);
}

console.log(lines.join('\n'));

process.exit(failed ? 1 : 0);
