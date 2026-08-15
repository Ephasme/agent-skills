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
// Usage: node scripts/validate.mjs [--quiet] [--home DIR] [--no-registry]

import { readdir, readFile, stat } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { ADAPTERS, validateManifest } from './install-mcp.mjs';
import { RegistryError, harnesses, identities, load, selection } from './registry.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SKILLS = join(ROOT, 'skills');
const MCP = join(ROOT, 'mcp', 'servers.json');
const QUIET = process.argv.includes('--quiet');
// The harness registry is a machine fact, not repo content: ~/.agents/harnesses.json
// is yadm content and no checkout carries it. Two flags follow from that.
//   --home DIR      lint a fixture tree instead of this machine. There is no test
//                   runner here, so this is how checkRegistry() is tested at all.
//   --no-registry   there is no registry to lint. CI is the only such place, and
//                   .github/workflows/validate.yml passes it for that reason and no
//                   other: locally a missing registry is a hard failure, because a
//                   consumer that degrades to an empty harness list reports success
//                   having checked nothing. The standing registry check is
//                   agents-doctor, which runs where the registry actually lives.
const homeArg = process.argv.indexOf('--home');
if (homeArg !== -1 && !process.argv[homeArg + 1]) {
  console.error('validate.mjs: --home needs a directory');
  process.exit(2);
}
const HOME = homeArg === -1 ? homedir() : process.argv[homeArg + 1];
const NO_REGISTRY = process.argv.includes('--no-registry');

// Categories organise this repo only; installed skills are flat. The set is
// deliberate — a new one is a decision, not a side effect of `mkdir`.
const CATEGORIES = [
  'engineering',
  'finance',
  'health',
  'legal',
  'meta',
  'research',
  'setup',
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
  [/(^|[^.\w])~\/\.claude/, 'hard-coded Claude Code config directory'],
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
    if (e.code === 'ENOENT') return { total: 0, off: 0 }; // the manifest is optional
    fail(MCP, `is not valid JSON (${e.message})`);
    return { total: 0, off: 0 };
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
  const defs = Object.values(manifest.servers ?? {});
  return { total: defs.length, off: defs.filter((d) => d.enabled === false).length };
}

// One harness list, in ~/.agents/harnesses.json, read by five tools that each used
// to carry a list of their own. None of them can check it — they consume it — so it
// is checked here. Two of these rules are not shape validation and carry more weight
// than the rest:
//   * an adapter named by no entry renders nothing (design decision 4). Without this
//     check ADAPTERS drifts back into being a second harness list, which is the
//     duplication the registry exists to remove.
//   * mcp.key is required for exactly the adapters whose writer is writeJsonKey and
//     forbidden for the others (§3.1.6), so codex's omission — it owns a delimited
//     TOML block, not a JSON key — is verified rather than merely tolerated.
// Errors are pushed with a fixed prefix rather than through fail(), whose
// relative(ROOT, file) would render a $HOME path as ../../../.agents/harnesses.json.
const MODES = new Set(['each', 'single']);
const IDENTIFIER = /^[a-z][a-z0-9-]*$/;
// Not imported from registry.mjs: that module's own isObject is a private helper,
// unexported by design (§7's boundary — checkRegistry owns shape validation, the
// reader owns only the envelope), so the same one-liner is declared again here.
const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

async function checkRegistry() {
  const bad = (msg) => errors.push(`harnesses.json: ${msg}`);
  const badSelection = (msg) => errors.push(`selection.json: ${msg}`);

  let reg;
  try {
    reg = await load(HOME);
  } catch (e) {
    if (!(e instanceof RegistryError)) throw e;
    errors.push(e.message); // already names the file and the reason
    return null;
  }

  const ids = identities(reg);
  const declared = Object.keys(ids).join(', ');
  const known = new Map(ADAPTERS.map((a) => [a.id, a]));
  const claimed = new Set();
  const hs = harnesses(reg);

  // ---- identities: shared labels for account selection and tab rendering ----
  for (const [identity, spec] of Object.entries(ids)) {
    if (!IDENTIFIER.test(identity)) {
      bad(`identity \`${identity}\`: name must match ^[a-z][a-z0-9-]*$`);
    }
    if (!isObject(spec)) {
      bad(`identity \`${identity}\`: must be an object`);
      continue;
    }
    for (const field of ['gh', 'glyph']) {
      if (typeof spec[field] !== 'string' || !spec[field]) {
        bad(`identity \`${identity}\`: ${field} must be a non-empty string`);
      }
    }
  }

  for (const [name, h] of Object.entries(hs)) {
    if (!IDENTIFIER.test(name)) {
      bad(`harness \`${name}\`: name must match ^[a-z][a-z0-9-]*$`);
    }
    if (typeof h.label !== 'string' || !h.label) {
      bad(`harness \`${name}\`: label must be a non-empty string`);
    }
    if (typeof h.root !== 'string' || !h.root) {
      bad(`harness \`${name}\`: root must be a non-empty string`);
    }

    // ---- identities: the mode, and the owner a single-configuration harness names --
    const mode = h.identities?.mode;
    if (!MODES.has(mode)) {
      bad(`harness \`${name}\`: identities.mode \`${mode}\` is neither \`each\` nor \`single\``);
    } else if (mode === 'single') {
      const owner = h.identities.owner;
      if (!owner) bad(`harness \`${name}\`: identities.mode \`single\` needs an \`owner\``);
      else if (!(owner in ids)) {
        bad(`harness \`${name}\`: owner \`${owner}\` is not a declared identity (declared: ${declared})`);
      }
    }
    // ---- process self-report: either both fields make sense, or the capability is absent ----
    if (h.identity !== undefined) {
      if (!isObject(h.identity)
          || !['value', 'root'].includes(h.identity.from)
          || typeof h.identity.env !== 'string'
          || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(h.identity.env)) {
        bad(`harness \`${name}\`: identity.from must be \`value\` or \`root\` and identity.env must name an environment variable`);
      }
    }

    // ---- probe: presence is exclusive, and the selected value has a usable type ----
    const probe = isObject(h.probe) ? h.probe : {};
    const file = probe.file;
    const bin = probe.bin;
    const hasFile = Object.hasOwn(probe, 'file');
    const hasBin = Object.hasOwn(probe, 'bin');
    const chosen = hasFile ? file : bin;
    if (hasFile === hasBin || typeof chosen !== 'string' || !chosen) {
      bad(`harness \`${name}\`: probe needs exactly one non-empty string \`file\` or \`bin\``);
    }

    // ---- declared capabilities: presence means one real, usable shape ----
    for (const leaf of ['skills', 'agents']) {
      const cap = h[leaf];
      if (cap === undefined) continue;
      if (!isObject(cap)) {
        bad(`harness \`${name}\`: ${leaf} must be an object`);
        continue;
      }
      const native = cap.native === true;
      const hasDir = typeof cap.dir === 'string' && cap.dir.length > 0;
      if (leaf === 'agents' && native) {
        bad(`harness \`${name}\`: agents cannot be native`);
      } else if (native === hasDir) {
        bad(`harness \`${name}\`: ${leaf} needs exactly one of native: true or a non-empty dir`);
      }
      if (cap.native !== undefined && cap.native !== true) {
        bad(`harness \`${name}\`: ${leaf}.native, when present, must be true`);
      }
    }

    if (h.sessions !== undefined) {
      if (!isObject(h.sessions)) {
        bad(`harness \`${name}\`: sessions must be an object`);
      } else {
        for (const field of ['launcher', 'comm']) {
          if (typeof h.sessions[field] !== 'string' || !h.sessions[field]) {
            bad(`harness \`${name}\`: sessions.${field} must be a non-empty string`);
          }
        }
        // events is one of the two optional fields, and null is the only accepted
        // absence — a harness may hold a tmux pane and speak no event vocabulary, which
        // is what the tabs-only shape declares. Both readers stop on a dropped key, so
        // this stops too: "no vocabulary" is a fact worth writing, and a typo is not
        // that fact.
        if (!('events' in h.sessions)) {
          bad(`harness \`${name}\`: sessions.events is missing — declare null for no event vocabulary`);
        } else if (h.sessions.events !== null
                   && (typeof h.sessions.events !== 'string' || !h.sessions.events)) {
          bad(`harness \`${name}\`: sessions.events must be a non-empty string or null`);
        }
        // producer is the other one: the file that actually calls agent-notify — omp's
        // extension, opencode's plugin — or null where the harness has no file to
        // install. Same rule, same reason. It is what catches the quietest failure in
        // this setup: a harness declaring a vocabulary whose producer was never
        // installed launches, draws its pane, and reads 💤 forever.
        if (!('producer' in h.sessions)) {
          bad(`harness \`${name}\`: sessions.producer is missing — declare null for no producer file`);
        } else if (h.sessions.producer !== null
                   && (typeof h.sessions.producer !== 'string' || !h.sessions.producer)) {
          bad(`harness \`${name}\`: sessions.producer must be a non-empty string or null`);
        } else if (h.sessions.producer !== null
                   && (h.sessions.events === null || !('events' in h.sessions))) {
          // Coherence between the two, checked here and in neither reader: a producer
          // reports INTO a vocabulary, so a file declared with no vocabulary to report
          // into is read by nothing. The reverse is legal and live — claude-code
          // declares events `claude` with a null producer, because its hook entries
          // lived inside settings.json and there was never a second file to look for.
          bad(`harness \`${name}\`: sessions.producer \`${h.sessions.producer}\` reports into no event vocabulary (sessions.events is null) — a producer nothing listens for is dead code`);
        }
      }
    }

    // ---- templates: ~ at position 0, {identity}, {root}, nothing else (§3.2) ----
    // A surviving `{` is fatal at resolution time in both readers, so it is a lint
    // failure here. `omp-{profile}` — tmux-agent's spelling before the port — is the
    // collision this catches first.
    for (const [where, template] of [
      ['root', h.root],
      ['probe.file', file],
      ['skills.dir', h.skills?.dir],
      ['agents.dir', h.agents?.dir],
      ['mcp.file', h.mcp?.file],
      ['sessions.launcher', h.sessions?.launcher],
      ['sessions.comm', h.sessions?.comm],
      ['sessions.events', h.sessions?.events],
      ['sessions.producer', h.sessions?.producer],
    ]) {
      if (typeof template !== 'string') continue;
      const stray = template.replaceAll('{identity}', '').replaceAll('{root}', '').match(/\{[^}]*\}?/);
      if (stray) {
        bad(`harness \`${name}\`: ${where} \`${template}\` contains \`${stray[0]}\` — the only substitutions are \`~\` at position 0, \`{identity}\` and \`{root}\``);
      }
      if (template.lastIndexOf('~') > 0) {
        bad(`harness \`${name}\`: ${where} \`${template}\` has a \`~\` past position 0, where it does not expand`);
      }
      if (where === 'root' && template.includes('{root}')) {
        bad(`harness \`${name}\`: root \`${template}\` uses {root} — substitution is never recursive`);
      }
    }

    // ---- mcp: a real adapter, and a key exactly when the adapter writes one ----
    if (h.mcp !== undefined) {
      if (!isObject(h.mcp)) {
        bad(`harness \`${name}\`: mcp must be an object`);
        continue;
      }
      if (typeof h.mcp.file !== 'string' || !h.mcp.file) {
        bad(`harness \`${name}\`: mcp.file must be a non-empty string`);
      }
      if (typeof h.mcp.adapter !== 'string' || !h.mcp.adapter) {
        bad(`harness \`${name}\`: mcp.adapter must be a non-empty string`);
        continue;
      }
      const adapter = known.get(h.mcp.adapter);
      if (!adapter) {
        bad(`harness \`${name}\`: mcp.adapter \`${h.mcp.adapter}\` names no adapter in install-mcp.mjs (known: ${[...known.keys()].join(', ')})`);
      } else {
        claimed.add(adapter.id);
        if (adapter.keyed && (typeof h.mcp.key !== 'string' || !h.mcp.key)) {
          bad(`harness \`${name}\`: adapter \`${adapter.id}\` writes a keyed JSON object — mcp.key is required`);
        }
        if (!adapter.keyed && h.mcp.key !== undefined) {
          bad(`harness \`${name}\`: adapter \`${adapter.id}\` writes no keyed JSON object — mcp.key \`${h.mcp.key}\` would be ignored`);
        }
      }
    }
  }

  for (const a of ADAPTERS) {
    if (!claimed.has(a.id)) {
      bad(`adapter \`${a.id}\` is named by no harness — an adapter with no registry entry renders nothing; declare the harness or delete the adapter from install-mcp.mjs`);
    }
  }

  // ---- selection: every name resolves to something that exists ----
  // selection() itself raises RegistryError for a non-object entry — the same rule
  // load() applies to harnesses, and the same class both readers agree on (parity
  // with agent_registry.py). Caught here rather than left to crash the process, so
  // one malformed identity is a lint line, not the whole run.
  let sel;
  try {
    sel = await selection(HOME);
  } catch (e) {
    if (!(e instanceof RegistryError)) throw e;
    const m = /: (\S+) is not an object$/.exec(e.message);
    badSelection(m ? `${m[1]}: must be an object` : e.message);
    sel = {};
  }
  const store = join(HOME, '.agents', 'skills');
  let stored = new Set();
  try {
    stored = new Set(
      (await readdir(store, { withFileTypes: true }))
        .filter((e) => e.isDirectory() || e.isSymbolicLink())
        .map((e) => e.name),
    );
  } catch {
    // No store at all: every selected name is reported below, which is the right
    // answer — bootstrap.sh builds the store before replaying selection into links.
  }

  for (const [identity, want] of Object.entries(sel)) {
    if (!(identity in ids)) {
      badSelection(`\`${identity}\` is not a declared identity (declared: ${declared})`);
      continue;
    }
    if (!isObject(want)) {
      badSelection(`${identity}: must be an object`);
      continue;
    }
    for (const [leaf, source, kind] of [
      ['skills', want.skills, 'skill'],
      ['agents', want.agents, 'agent'],
    ]) {
      if (!Array.isArray(source)
          || new Set(source).size !== source.length
          || source.some((name) => typeof name !== 'string' || !IDENTIFIER.test(name))) {
        badSelection(`${identity}: ${leaf} must be an array of unique identifiers`);
        continue;
      }
      for (const name of source) {
        if (leaf === 'skills') {
          if (!stored.has(name)) {
            badSelection(`${identity}: skill \`${name}\` is not in the store (${join(store, name)})`);
          }
          continue;
        }
        // Agents are this repo's files rather than store entries, and the linter is the
        // one consumer that can see them.
        const file = join(ROOT, 'agents', `${name}.md`);
        try {
          const info = await stat(file);
          if (!info.isFile()) throw new Error('not a file');
        } catch {
          badSelection(`${identity}: ${kind} \`${name}\` has no file in this repo (${relative(ROOT, file)})`);
        }
      }
    }
  }

  return { harnesses: Object.keys(hs).length, identities: Object.keys(ids).length };
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

  const mcp = await checkMcpManifest();
  const reg = NO_REGISTRY ? null : await checkRegistry();

  for (const w of warnings) console.warn(`  ! ${w}`);
  if (errors.length) {
    console.error(`\n✗ ${errors.length} problem(s):\n`);
    for (const e of errors) console.error(`  ${e}`);
    process.exit(1);
  }
  if (!QUIET) {
    const off = mcp.off ? ` (${mcp.off} disabled)` : '';
    const registry = NO_REGISTRY
      ? ', registry lint skipped (--no-registry)'
      : `, ${reg.harnesses} harnesses × ${reg.identities} identities`;
    console.log(`✓ ${found.size} skills across ${categories.length} categories, ${mcp.total} MCP servers${off}${registry}, no problems`);
  }
}

await main();
