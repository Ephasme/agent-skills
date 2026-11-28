// Promptfoo provider that asks a model to route a request the way the `do` skill would.
//
// The system prompt is the do skill's SKILL.md at a git ref (`config.ref`), or the working tree
// when the ref is `WORKTREE`, followed by a harness that limits the run to the routing stage and
// asks for JSON. The model runs through `omp -p` with tools, skills, context files and extensions
// disabled, so only the skill text and the test case reach it.

import { execFileSync, spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SKILL = 'skills/pipelines/do/SKILL.md';
const TIMEOUT_MS = 300_000;

const HARNESS = `
# Evaluation harness

The user invoked the skill above. Their message holds the request (the text after \`/do\`) and a
description of the repository the session starts in; treat that description as what you saw when
you glanced at the repository. This is a routing dry run: perform only the routing step. Do not
run any skill, create todos or ask anything in prose.

Reply with only one JSON object, no prose and no code fence:

{"action": "route" | "ask", "route": ["research" | "bugfix" | "feature" | "campaign", ...], "reason": "<one line>"}

- "route": you would announce the route and start. "route" lists the skills in run order.
- "ask": the skill tells you to ask the user which route to take before starting. "route" is the
  one you would recommend in that question.
`;

const skillText = new Map();

function loadSkill(ref) {
  if (!skillText.has(ref)) {
    const text =
      ref === 'WORKTREE'
        ? readFileSync(join(ROOT, SKILL), 'utf-8')
        : execFileSync('git', ['-C', ROOT, 'show', `${ref}:${SKILL}`], { encoding: 'utf-8' });
    skillText.set(ref, text);
  }
  return skillText.get(ref);
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

export default class DoRouteProvider {
  constructor(options) {
    this.providerId = options.id;
    this.config = options.config ?? {};
    if (!this.config.ref) throw new Error('provider config needs a `ref` (git ref or WORKTREE)');
  }

  id() {
    return `do-route:${this.config.ref}`;
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
      '--system-prompt', loadSkill(this.config.ref) + HARNESS,
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
