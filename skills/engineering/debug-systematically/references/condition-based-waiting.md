# Condition-based waiting

## Contents

- [When to use](#when-to-use)
- [Core pattern](#core-pattern)
- [Quick patterns](#quick-patterns)
- [Implementation](#implementation)
- [Common mistakes](#common-mistakes)
- [When an arbitrary timeout is correct](#when-an-arbitrary-timeout-is-correct)

## Overview

Flaky tests often guess at timing with arbitrary delays, creating race conditions where tests pass
on a fast machine but fail under load or in CI.

**Core principle:** Wait for the actual condition you care about, not a guess about how long it
takes.

## When to use

```dot
digraph when_to_use {
    "Test uses setTimeout/sleep?" [shape=diamond];
    "Testing timing behavior?" [shape=diamond];
    "Document WHY timeout needed" [shape=box];
    "Use condition-based waiting" [shape=box];

    "Test uses setTimeout/sleep?" -> "Testing timing behavior?" [label="yes"];
    "Testing timing behavior?" -> "Document WHY timeout needed" [label="yes"];
    "Testing timing behavior?" -> "Use condition-based waiting" [label="no"];
}
```

Use when:
- Tests have arbitrary delays (`setTimeout`, `sleep`, `time.sleep()`)
- Tests are flaky — pass sometimes, fail under load
- Tests time out when run in parallel
- Waiting for async operations to complete

Don't use when:
- Testing actual timing behaviour (debounce, throttle intervals)
- Always document WHY when an arbitrary timeout is genuinely needed

## Core pattern

```typescript
// ❌ BEFORE: guessing at timing
await new Promise(r => setTimeout(r, 50));
const result = getResult();
expect(result).toBeDefined();

// ✅ AFTER: waiting for the condition
await waitFor(() => getResult() !== undefined);
const result = getResult();
expect(result).toBeDefined();
```

## Quick patterns

| Scenario | Pattern |
|----------|---------|
| Wait for an event | `waitFor(() => events.find(e => e.type === 'DONE'))` |
| Wait for state | `waitFor(() => machine.state === 'ready')` |
| Wait for a count | `waitFor(() => items.length >= 5)` |
| Wait for a file | `waitFor(() => fs.existsSync(path))` |
| Complex condition | `waitFor(() => obj.ready && obj.value > 10)` |

## Implementation

Generic polling function:

```typescript
async function waitFor<T>(
  condition: () => T | undefined | null | false,
  description: string,
  timeoutMs = 5000
): Promise<T> {
  const startTime = Date.now();

  while (true) {
    const result = condition();
    if (result) return result;

    if (Date.now() - startTime > timeoutMs) {
      throw new Error(`Timeout waiting for ${description} after ${timeoutMs}ms`);
    }

    await new Promise(r => setTimeout(r, 10)); // Poll every 10ms
  }
}
```

A complete implementation with domain-specific helpers (`waitForEvent`, `waitForEventCount`,
`waitForEventMatch`) is in
`$SKILL_DIR/references/condition-based-waiting-example.ts`.

## Common mistakes

- **Polling too fast** — `setTimeout(check, 1)` wastes CPU. Poll every 10ms.
- **No timeout** — the loop runs forever if the condition is never met. Always include a timeout
  with a clear error.
- **Stale data** — caching state before the loop. Call the getter inside the loop for fresh data.

## When an arbitrary timeout is correct

```typescript
// The tool ticks every 100ms — two ticks are needed to observe partial output
await waitForEvent(manager, 'TOOL_STARTED'); // First: wait for the condition
await new Promise(r => setTimeout(r, 200));  // Then: wait for timed behaviour
// 200ms = 2 ticks at 100ms intervals — documented and justified
```

Requirements:

1. First wait for the triggering condition
2. Base the delay on known timing, not a guess
3. Comment explaining WHY
