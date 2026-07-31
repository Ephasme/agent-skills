#!/usr/bin/env node
// Validate the skill catalog before it reaches an agent.
//
// The `skills` CLI is forgiving: a skill with unparseable frontmatter is silently
// skipped with a one-line warning, and a broken relative path only surfaces when an
// agent tries to run it, halfway through a task. Everything here is a failure mode
// that would otherwise be discovered at use time.
//
// Usage: node scripts/validate.mjs [--quiet]

import { readdir, readFile, stat } from 'node:fs/promises';
import { join, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SKILLS = join(ROOT, 'skills');
const QUIET = process.argv.includes('--quiet');

const CATEGORIES = [
  'claude-tools',
  'engineering',
  'finance',
  'health',
  'meta',
  'ops',
  'research',
  'security',
  'setup',
  'trackers',
];

// `skills` refuses archives over 10 MiB / 1000 files; a single reference file that
// large is also a sign something unintended got committed.
const MAX_FILE_BYTES = 1024 * 1024;

const errors = [];
const fail = (file, msg) => errors.push(`${relative(ROOT, file)}: ${msg}`);

/** Minimal YAML frontmatter reader — only the scalar keys we care about. */
function parseFrontmatter(content) {
  if (!content.startsWith('---\n')) return null;
  const end = content.indexOf('\n---', 3);
  if (end === -1) return null;
  const block = content.slice(4, end + 1);

  const data = {};
  let key = null;
  let folded = null;

  for (const line of block.split('\n')) {
    if (folded !== null) {
      // Inside a `>-` / `|` block: keep consuming while indented or blank.
      if (line.trim() === '' || /^\s+/.test(line)) {
        folded.push(line.trim());
        continue;
      }
      data[key] = folded.join(' ').trim();
      folded = null;
    }
    const m = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!m) continue;
    key = m[1];
    const value = m[2];
    if (value === '>-' || value === '>' || value === '|' || value === '|-') {
      folded = [];
    } else {
      data[key] = value.replace(/^["']|["']$/g, '');
    }
  }
  if (folded !== null) data[key] = folded.join(' ').trim();
  return data;
}

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(path)));
    else out.push(path);
  }
  return out;
}

const found = new Map(); // skill name -> path, for the uniqueness check

async function checkSkill(category, slug) {
  const dir = join(SKILLS, category, slug);
  const skillMd = join(dir, 'SKILL.md');

  let content;
  try {
    content = await readFile(skillMd, 'utf-8');
  } catch {
    fail(dir, 'no SKILL.md');
    return;
  }

  // 1. frontmatter parses and carries the two fields `skills` requires
  const data = parseFrontmatter(content);
  if (!data) return fail(skillMd, 'no parseable YAML frontmatter');
  if (!data.name) fail(skillMd, 'frontmatter missing `name`');
  if (!data.description) fail(skillMd, 'frontmatter missing `description`');

  // 2. name matches the directory, and is unique across the catalog — installs
  //    flatten to ~/.agents/skills/<name>, so a collision silently overwrites.
  if (data.name && data.name !== slug) {
    fail(skillMd, `frontmatter name "${data.name}" != directory "${slug}"`);
  }
  if (data.name) {
    if (found.has(data.name)) {
      fail(skillMd, `duplicate skill name "${data.name}" (also ${relative(ROOT, found.get(data.name))})`);
    }
    found.set(data.name, skillMd);
  }

  const files = await walk(dir);

  for (const file of files) {
    const rel = relative(ROOT, file);

    // 5. nothing that shouldn't be committed, nothing oversized
    if (rel.includes('__pycache__') || file.endsWith('.pyc')) fail(file, 'compiled Python artifact');
    const { size } = await stat(file);
    if (size > MAX_FILE_BYTES) fail(file, `${(size / 1024 / 1024).toFixed(1)} MiB exceeds the 1 MiB cap`);

    if (!/\.(md|py|sh|mjs|js|json|yaml|yml|txt)$/.test(file)) continue;
    const text = await readFile(file, 'utf-8');

    // 3. nothing that only resolves inside a Claude Code plugin, or on one machine
    if (text.includes('CLAUDE_PLUGIN_ROOT')) {
      fail(file, 'references ${CLAUDE_PLUGIN_ROOT} — empty once installed as a plain skill');
    }
    for (const [line, i] of text.split('\n').map((l, i) => [l, i])) {
      // `/Users/<username>` and friends are illustrative placeholders, not real paths.
      if (/\/(Users|home)\/(?!<)[A-Za-z0-9._-]+\//.test(line)) {
        fail(file, `absolute home path at line ${i + 1}: ${line.trim().slice(0, 80)}`);
      }
    }
  }

  // 4. every skill-relative path the SKILL.md points at actually ships
  const referenced = new Set();
  for (const m of content.matchAll(/(?:\$SKILL_DIR\/|\]\(|`)((?:scripts|references)\/[A-Za-z0-9._/-]+)/g)) {
    referenced.add(m[1]);
  }
  for (const ref of referenced) {
    if (ref.endsWith('/')) continue; // a directory reference, e.g. `scripts/`
    if (ref.includes('/.venv')) continue; // created at runtime, gitignored
    try {
      await stat(join(dir, ref));
    } catch {
      fail(skillMd, `references missing file \`${ref}\``);
    }
  }
}

async function main() {
  const categories = (await readdir(SKILLS, { withFileTypes: true }))
    .filter((e) => e.isDirectory())
    .map((e) => e.name);

  // 6. no category invented on the side — the set is deliberate and documented
  for (const c of categories) {
    if (!CATEGORIES.includes(c)) fail(join(SKILLS, c), `undeclared category (add it to CATEGORIES + README)`);
  }

  for (const category of categories.filter((c) => CATEGORIES.includes(c))) {
    const slugs = (await readdir(join(SKILLS, category), { withFileTypes: true }))
      .filter((e) => e.isDirectory())
      .map((e) => e.name);
    for (const slug of slugs) await checkSkill(category, slug);
  }

  if (errors.length) {
    console.error(`\n✗ ${errors.length} problem(s):\n`);
    for (const e of errors) console.error(`  ${e}`);
    process.exit(1);
  }
  if (!QUIET) console.log(`✓ ${found.size} skills across ${categories.length} categories, no problems`);
}

await main();
