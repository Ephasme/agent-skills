// Promptfoo provider that runs one decision of a skill as a dry run and returns the model's JSON.
//
// The system prompt is the skill's SKILL.md (`config.skill`, repo-relative) at a git ref
// (`config.ref`), or the working tree when the ref is `WORKTREE`, followed by a harness
// (`config.harness`, repo-relative, always read from the working tree) that limits the run to one
// decision and fixes the JSON reply. The model runs through `omp -p` with tools, skills, context
// files and extensions disabled, so only the skill text, the harness and the test case reach it.

import { execFileSync, spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const TIMEOUT_MS = 300_000;

const fileText = new Map();

function load(path, ref) {
  const key = `${ref}:${path}`;
  if (!fileText.has(key)) {
    const text =
      ref === 'WORKTREE'
        ? readFileSync(join(ROOT, path), 'utf-8')
        : execFileSync('git', ['-C', ROOT, 'show', `${ref}:${path}`], { encoding: 'utf-8' });
    fileText.set(key, text);
  }
  return fileText.get(key);
}

function runOmp(args) {
  return new Promise((resolve) => {
    const child = spawn('omp', args, { cwd: tmpdir(), stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => (stdout += d));
    child.stderr.on('data', (d) => (stderr += d));
    const timer = setTimeout(() => child.kill('SIGKILL'), TIMEOUT_MS);
    child.on('error', (err) => {
      clearTimeout(timer);
      resolve({ code: -1, stdout, stderr: String(err) });
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      resolve({ code, stdout, stderr });
    });
  });
}

// The last assistant `message_end` event of `omp --mode json` carries the reply and its usage.
function lastAssistantMessage(stdout) {
  let message;
  for (const line of stdout.split('\n')) {
    if (!line.startsWith('{')) continue;
    try {
      const event = JSON.parse(line);
      if (event.type === 'message_end' && event.message?.role === 'assistant') message = event.message;
    } catch {
      // Not an event line.
    }
  }
  return message;
}

export default class SkillDryRunProvider {
  constructor(options) {
    this.providerId = options.id;
    this.config = options.config ?? {};
    for (const key of ['skill', 'harness', 'ref']) {
      if (!this.config[key]) throw new Error(`provider config needs \`${key}\``);
    }
  }

  id() {
    return `skill-dry-run:${this.config.skill}@${this.config.ref}`;
  }

  async callApi(prompt) {
    const args = [
      '-p',
      '--mode', 'json',
      '--no-session',
      '--no-tools',
      '--no-skills',
      '--no-context-files',
      '--no-rules',
      '--no-extensions',
      '--no-lsp',
      '--system-prompt',
      `${load(this.config.skill, this.config.ref)}\n${load(this.config.harness, 'WORKTREE')}`,
    ];
    if (this.config.model) args.push('--model', this.config.model);
    if (this.config.thinking) args.push('--thinking', this.config.thinking);
    args.push(prompt);

    const { code, stdout, stderr } = await runOmp(args);
    const message = lastAssistantMessage(stdout);
    if (code !== 0 || !message) {
      return { error: `omp exited ${code}: ${stderr.trim().slice(-2000) || 'no assistant message'}` };
    }
    const output = message.content
      .filter((part) => part.type === 'text')
      .map((part) => part.text)
      .join('');
    const usage = message.usage ?? {};
    return {
      output,
      cost: usage.cost?.total,
      tokenUsage: {
        total: usage.totalTokens,
        prompt: (usage.input ?? 0) + (usage.cacheRead ?? 0) + (usage.cacheWrite ?? 0),
        completion: usage.output,
      },
      metadata: { model: `${message.provider}/${message.model}` },
    };
  }
}
