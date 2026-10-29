#!/usr/bin/env node
// Claude Code `headersHelper`: prints the JSON headers for the server it names in
// $CLAUDE_CODE_MCP_SERVER_NAME, with every credential read at connection time from the
// SOPS store next to this script — or from the environment when that store is absent.
//
// Claude Code runs a helper fresh on each connection, which a static "Bearer ${VAR}"
// header cannot do — and an unset ${VAR} is exactly what it would send literally.

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const name = process.env.CLAUDE_CODE_MCP_SERVER_NAME ?? '';
const servers = JSON.parse(readFileSync(join(here, 'servers.json'), 'utf8'));

const server = servers[name];
if (!server) {
  console.error(`headers.mjs: no server named "${name}" in servers.json`);
  process.exit(1);
}

const out = {};
for (const [header, template] of Object.entries(server.headers ?? {})) {
  const ref = /^(.*?)\$\{([A-Z0-9_]+)\}$/.exec(template);
  if (!ref) {
    out[header] = template;
    continue;
  }
  const [, prefix, key] = ref;
  try {
    const store = join(here, 'secrets.sops.yaml');
    const value = existsSync(store)
      ? execFileSync('sops', ['exec-env', store, `printf '%s' "$${key}"`], { encoding: 'utf8' }).trim()
      : (process.env[key] ?? '').trim();
    if (!value) throw new Error('empty');
    out[header] = prefix + value;
  } catch {
    console.error(`headers.mjs: ${name}: ${key} is missing from secrets.sops.yaml and the environment`);
    process.exit(1);
  }
}

process.stdout.write(JSON.stringify(out));
