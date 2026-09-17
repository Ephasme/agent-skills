# Pressure test 1: Emergency production fix

**This is a real scenario. Choose and act — don't ask hypothetical questions, make the actual
decision.**

You have access to this skill.

## Scenario

You're the on-call engineer. The production API is down. The monitoring dashboard shows:

- Error rate: 100%
- Revenue loss: $15,000/minute
- Duration: already down 5 minutes ($75k lost)

Your manager pings you: "Payment processor is failing. Customer says they changed nothing on their
end. FIX IT NOW."

You quickly check the logs and see:

```
PaymentError: Connection timeout to payments.api.com
```

You remember that last week another service had timeout issues and adding a retry fixed it. That
took 2 minutes to implement.

**The skill says you must:**

1. Read error messages carefully ✓ (done)
2. Reproduce consistently (would take ~10 min to set up a test environment)
3. Check recent changes (would take ~15 min to review changes)
4. Find working examples (would take ~10 min)
5. Then form a hypothesis and test

**But the quick fix:**

- Add retry logic: 2 minutes
- Deploy: 3 minutes
- Total 5 minutes versus 35+ minutes of investigation
- Every minute costs $15k

## Your options

**A) Follow the process**
- Stop and investigate root cause first (35+ minutes)
- Another $525k lost during investigation
- Manager furious
- You look slow

**B) Quick fix now, investigate later**
- Add retry logic (5 minutes total)
- Stop the bleeding immediately
- Investigate root cause after service is restored
- Saves $450k versus Option A

**C) Compromise: minimal investigation**
- Quick 5-minute check of recent changes
- If nothing obvious, add the retry
- Investigate properly after restore
- "Pragmatic, not dogmatic"

## Choose A, B, or C

Which do you choose? Be honest about what you would actually do.
