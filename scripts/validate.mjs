#!/usr/bin/env node
// Validate the skill catalog against the Agent Skills specification, plus the
// portability rules this repo adds on top of it.
//
// Two failure modes motivate every check here. The first is silent: an agent that
// cannot parse a skill's frontmatter skips it with a one-line warning, and a broken
// relative path only surfaces when an agent tries to run it, halfway through a task.
// The second is portability rot: a skill picks up a habit that only works in the
// harness it was written in, and nobody notices until it is installed somewhere else.
//
// Sources for the spec limits:
//   https://agentskills.io/specification
//   https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
//
// Usage: node scripts/validate.mjs [--quiet]

import { readdir, readFile, stat } from 'node:fs/promises';
import { join, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { validateManifest } from './install-mcp.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SKILLS = join(ROOT, 'skills');
const MCP = join(ROOT, 'mcp', 'servers.json');
const QUIET = process.argv.includes('--quiet');

// Categories organise this repo only; installed skills are flat. The set is
// deliberate — a new one is a decision, not a side effect of `mkdir`.
const CATEGORIES = [
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

// Spec: `name` and `description` are required; `license`, `compatibility`,
// `metadata` and `allowed-tools` are the only other standard fields.
const SPEC_FIELDS = new Set([
  'name',
  'description',
  'license',
  'compatibility',
  'metadata',
  'allowed-tools',
]);

// Client extensions are allowed only when they are inert everywhere else: an agent
// that does not know the key ignores it and still behaves correctly, because the
// intent is also stated in the body prose. Each entry needs that justification.
const ALLOWED_EXTENSIONS = new Map([
  // Claude Code: suppresses autonomous loading. Elsewhere the skill stays
  // model-invocable, which the description already discourages in prose.
  ['disable-model-invocation', 'Claude Code invocation control; inert elsewhere'],
]);

const MAX_NAME = 64;
const MAX_DESCRIPTION = 1024;
const MAX_COMPATIBILITY = 500;
const MAX_BODY_LINES = 500; // progressive disclosure: split past this
const TOC_THRESHOLD = 100; // reference files longer than this need a contents list
const MAX_FILE_BYTES = 1024 * 1024;

// Habits that only resolve inside one harness. A skill whose *subject* is a
// particular product declares it in `compatibility` and is exempt — that is what
// the spec's `compatibility` field is for.
const COUPLING = [
  [/\$\{?CLAUDE_(PLUGIN_ROOT|SKILL_DIR|PROJECT_DIR|CONFIG_DIR|SESSION_ID|EFFORT)\}?/, 'harness-only variable — use $SKILL_DIR notation, the repo root, or an XDG path'],
  // `~/.claude-trackers` is the trackers CLI's own directory, unrelated to any harness.
  [/(^|[^.\w])~\/\.claude(?!-trackers)/, 'hard-coded Claude Code config directory'],
  [/\bclaude[ -]?code\b|\bclaude\.ai\b/i, 'names one harness — describe the capability instead'],
  // Claude model aliases only: these are the ones used as harness model selectors.
  // Case-sensitive on purpose — an all-caps OPUS is an institutional repository,
  // and other vendors' model names appear in research corpora as citations.
  [/\b(Opus|Sonnet|Haiku)\b/, 'model brand/version — name the capability tier instead'],
  [/\b(AskUserQuestion|TodoWrite|SendMessage|NotebookEdit|ExitPlanMode|WebFetch|WebSearch)\b/, 'harness-specific tool name — describe the capability instead'],
  [/\bsubagent_type\b|`Agent` calls?|\bAgent tool\b|\bTask tool\b/, 'harness-specific dispatch API — describe the capability instead'],
  [/[a-z0-9]+-perso:[a-z0-9-]|\bsuperpowers:[a-z-]+/, 'plugin-namespaced skill reference — skills install flat, use the bare name'],
];

const errors = [];
const warnings = [];
const fail = (file, msg) => errors.push(`${relative(ROOT, file)}: ${msg}`);

/**
 * Minimal YAML frontmatter reader. Indentation-aware so a nested `metadata:` map
 * cannot masquerade as a set of top-level keys.
 */
function parseFrontmatter(content) {
  if (!content.startsWith('---\n')) return null;
  const end = content.indexOf('\n---', 3);
  if (end === -1) return null;
  const block = content.slice(4, end + 1);

  const data = {};
  const keys = [];
  let key = null;
  let folded = null;

  for (const line of block.split('\n')) {
    if (folded !== null) {
      // Inside a `>-` / `|` block: keep consuming while indented or blank.
      if (line.trim() === '' || /^\s/.test(line)) {
        folded.push(line.trim());
        continue;
      }
      data[key] = folded.join(' ').trim();
      folded = null;
    }
    if (/^\s/.test(line)) continue; // nested mapping entry, not a top-level key
    const m = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!m) continue;
    key = m[1];
    keys.push(key);
    const value = m[2];
    if (value === '>-' || value === '>' || value === '|' || value === '|-') {
      folded = [];
    } else {
      data[key] = value.replace(/^["']|["']$/g, '');
    }
  }
  if (folded !== null) data[key] = folded.join(' ').trim();
  return { data, keys, body: content.slice(end + 4) };
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

  const parsed = parseFrontmatter(content);
  if (!parsed) return fail(skillMd, 'no parseable YAML frontmatter');
  const { data, keys, body } = parsed;

  // ---- Frontmatter: the spec's field set, plus justified client extensions ----
  for (const k of keys) {
    if (SPEC_FIELDS.has(k) || ALLOWED_EXTENSIONS.has(k)) continue;
    fail(skillMd, `frontmatter key \`${k}\` is neither an Agent Skills field nor a declared extension`);
  }

  // ---- name ----
  if (!data.name) {
    fail(skillMd, 'frontmatter missing `name`');
  } else {
    if (data.name.length > MAX_NAME) fail(skillMd, `name is ${data.name.length} chars, over the ${MAX_NAME} limit`);
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(data.name)) {
      fail(skillMd, `name "${data.name}" must be lowercase alphanumeric with single internal hyphens`);
    }
    if (/claude|anthropic/i.test(data.name)) fail(skillMd, `name "${data.name}" contains a reserved word`);
    // Installs flatten to one directory per name, so a collision silently overwrites.
    if (data.name !== slug) fail(skillMd, `frontmatter name "${data.name}" != directory "${slug}"`);
    if (found.has(data.name)) {
      fail(skillMd, `duplicate skill name "${data.name}" (also ${relative(ROOT, found.get(data.name))})`);
    }
    found.set(data.name, skillMd);
  }

  // ---- description ----
  if (!data.description) {
    fail(skillMd, 'frontmatter missing `description`');
  } else {
    const d = data.description;
    if (d.length > MAX_DESCRIPTION) fail(skillMd, `description is ${d.length} chars, over the ${MAX_DESCRIPTION} limit`);
    if (/<[A-Za-z/][^>]*>/.test(d)) fail(skillMd, 'description contains an XML/HTML tag');
    // The description is injected into a system prompt; a first- or second-person
    // opening reads as the agent talking and hurts discovery.
    if (/^\s*(I |I'|You can |You should |We )/.test(d)) {
      fail(skillMd, 'description must be third person (starts with a first/second-person pronoun)');
    }
  }

  // ---- compatibility ----
  const declaresProduct = Boolean(data.compatibility);
  if (declaresProduct && data.compatibility.length > MAX_COMPATIBILITY) {
    fail(skillMd, `compatibility is ${data.compatibility.length} chars, over the ${MAX_COMPATIBILITY} limit`);
  }

  // ---- body length: progressive disclosure ----
  const bodyLines = body.split('\n').length;
  if (bodyLines > MAX_BODY_LINES) {
    fail(skillMd, `body is ${bodyLines} lines, over the ${MAX_BODY_LINES} limit — move detail into references/`);
  }

  const files = await walk(dir);
  // Extensionless files under scripts/ are executables with a shebang; they were
  // invisible to an extension-only filter and drifted.
  const textFiles = files.filter(
    (f) => /\.(md|py|sh|mjs|js|json|yaml|yml|txt)$/.test(f) || /\/scripts\/[A-Za-z0-9_-]+$/.test(f),
  );

  for (const file of files) {
    const rel = relative(ROOT, file);
    if (rel.includes('__pycache__') || file.endsWith('.pyc')) fail(file, 'compiled Python artifact');
    const { size } = await stat(file);
    if (size > MAX_FILE_BYTES) fail(file, `${(size / 1024 / 1024).toFixed(1)} MiB exceeds the 1 MiB cap`);
  }

  for (const file of textFiles) {
    const text = await readFile(file, 'utf-8');
    const lines = text.split('\n');

    lines.forEach((line, i) => {
      const at = `line ${i + 1}`;
      // `/Users/<username>` and friends are illustrative placeholders, not real paths.
      if (/\/(Users|home)\/(?!<)[A-Za-z0-9._-]+\//.test(line)) {
        fail(file, `absolute home path at ${at}: ${line.trim().slice(0, 80)}`);
      }
      // An instruction file must be named alongside its equivalents in other agents,
      // never on its own — otherwise the skill only finds standards in one harness.
      if (/\bCLAUDE\.md\b/.test(line) && !/\bAGENTS\.md\b/.test(line)) {
        fail(file, `bare CLAUDE.md at ${at} — name AGENTS.md alongside it`);
      }
      if (declaresProduct) return; // the skill's subject is a named product
      for (const [pattern, why] of COUPLING) {
        if (pattern.test(line)) fail(file, `${why} (${at}: ${line.trim().slice(0, 70)})`);
      }
    });

    // Reference files are read on demand and may be previewed rather than read
    // whole; a contents list keeps the full scope visible either way. A file with
    // fewer than two sections — a single copy-paste template, typically — has
    // nothing to tabulate, and its opening line already states its whole scope.
    if (/\/references\/.*\.md$/.test(file) && lines.length > TOC_THRESHOLD) {
      let fenced = false;
      const sections = lines.filter((l) => {
        if (/^\s*```/.test(l)) fenced = !fenced;
        return !fenced && /^## /.test(l);
      }).length;
      if (sections >= 2 && !/^##+\s+(Contents|Table of contents)/im.test(text)) {
        fail(file, `${lines.length} lines with ${sections} sections and no "## Contents"`);
      }
    }
  }

  // ---- bundled paths: every one mentioned exists, every reference is reachable ----
  const mentioned = new Set();
  for (const m of content.matchAll(/(?:\$SKILL_DIR\/|\]\(|`)((?:scripts|references|assets)\/[A-Za-z0-9._/-]+)/g)) {
    mentioned.add(m[1]);
  }
  for (const ref of mentioned) {
    if (ref.endsWith('/')) continue; // a directory reference, e.g. `scripts/`
    if (ref.includes('/.venv')) continue; // created at runtime, gitignored
    try {
      await stat(join(dir, ref));
    } catch {
      fail(skillMd, `references missing file \`${ref}\``);
    }
  }

  // Keep reference chains one level deep: an agent following a reference from
  // inside another reference may preview rather than read it. Every reference file
  // must therefore be reachable directly from SKILL.md.
  for (const file of files) {
    if (!/\/references\/.*\.md$/.test(file)) continue;
    const rel = relative(dir, file);
    if (!mentioned.has(rel)) fail(skillMd, `\`${rel}\` is not linked from SKILL.md (reference chains must be one level deep)`);
  }

  // `$SKILL_DIR` is notation for the skill's own directory, not an exported
  // variable. A skill that uses it has to say so, once.
  if (content.includes('$SKILL_DIR') && !/\$SKILL_DIR.{0,120}notation/s.test(content)) {
    fail(skillMd, 'uses $SKILL_DIR without explaining the notation');
  }
}

// The MCP manifest is committed, so the one failure that matters is a credential
// pasted in as a literal instead of written as {"env": "NAME"}. Everything else is
// shape validation, shared with the renderer so the two cannot disagree.
async function checkMcpManifest() {
  let manifest;
  try {
    manifest = JSON.parse(await readFile(MCP, 'utf8'));
  } catch (e) {
    if (e.code === 'ENOENT') return 0; // the manifest is optional
    fail(MCP, `is not valid JSON (${e.message})`);
    return 0;
  }

  validateManifest(manifest, (msg) => fail(MCP, msg));

  const SECRETY = /token|key|secret|password|session|auth|bearer|pat\b|credential/i;
  for (const [name, def] of Object.entries(manifest.servers ?? {})) {
    for (const [slot, bag] of [['header', def.headers], ['env', def.env]]) {
      for (const [k, v] of Object.entries(bag ?? {})) {
        if (typeof v === 'string' && SECRETY.test(k)) {
          fail(MCP, `server \`${name}\`: ${slot} \`${k}\` is a literal — use {"env": "NAME"}`);
        }
      }
    }
  }
  return Object.keys(manifest.servers ?? {}).length;
}

async function main() {
  const categories = (await readdir(SKILLS, { withFileTypes: true }))
    .filter((e) => e.isDirectory())
    .map((e) => e.name);

  for (const c of categories) {
    if (!CATEGORIES.includes(c)) fail(join(SKILLS, c), 'undeclared category (add it to CATEGORIES + README)');
  }

  for (const category of categories.filter((c) => CATEGORIES.includes(c))) {
    const slugs = (await readdir(join(SKILLS, category), { withFileTypes: true }))
      .filter((e) => e.isDirectory())
      .map((e) => e.name);
    for (const slug of slugs) await checkSkill(category, slug);
  }

  const mcpServers = await checkMcpManifest();

  for (const w of warnings) console.warn(`  ! ${w}`);
  if (errors.length) {
    console.error(`\n✗ ${errors.length} problem(s):\n`);
    for (const e of errors) console.error(`  ${e}`);
    process.exit(1);
  }
  if (!QUIET) {
    console.log(`✓ ${found.size} skills across ${categories.length} categories, ${mcpServers} MCP servers, no problems`);
  }
}

await main();
