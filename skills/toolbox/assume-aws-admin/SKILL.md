---
name: assume-aws-admin
description: >-
  Mints a 1-hour AWS admin session (AdminAccessRole on account 226016658082) by
  assuming the role with an MFA code the user types in. Use whenever an AWS call
  needs privileges the current credentials lack — AccessDenied,
  ExpiredToken/"security token included in the request is expired", "credentials
  missing", an interactive MFA prompt blocking a non-interactive command — or
  when the user asks to "go admin", "elevate", "assume the admin role", "get AWS
  creds", "passe en admin AWS", "élève-toi sur AWS". The MFA code is valid for
  ~30 seconds, so the skill's core rule is: ask for it only at the instant you
  are ready to fire the command.
---

# Assume AWS admin (1h, MFA)

Target: `arn:aws:iam::226016658082:role/AdminAccessRole`, assumed from the
`loup-iam` profile, MFA serial `arn:aws:iam::226016658082:mfa/1password`
(1Password entry). Duration 3600s.

## Rule zero — ask for the code last

A TOTP code lives ~30 seconds. Do everything else first: reads, planning, the
credential reuse check below, any tool call you were going to make anyway. Ask
for the six digits **only when the very next action is running the command**,
and run it in the same turn the user answers. Never ask "before we start" and
never batch the MFA question with other questions.

Ask exactly one thing: the current 6-digit code from the 1Password AWS MFA entry.

## 1. Reuse before asking

An unexpired session may already be on disk. Costs one call, saves the user a
prompt. Probe it in a **subshell** — an expired file sourced into the persistent
shell exports stale `AWS_*` variables that outrank `~/.aws/config` and poison
every later command, including step 2:

```bash
( . "$TMPDIR/admin.env" && aws sts get-caller-identity --query Arn --output text ) 2>/dev/null
```

Prints `.../AdminAccessRole/...` → the file is good. Run `. "$TMPDIR/admin.env"`
in the persistent shell and do the work.
Fails or prints the plain IAM user → `rm -f "$TMPDIR/admin.env"` and continue.

## 2. Mint the session

Only now ask for the code, then run with `MFA` set to what the user gave:

```bash
MFA=123456
read -r AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN < <(
  env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN \
    aws --profile loup-iam sts assume-role \
      --role-arn arn:aws:iam::226016658082:role/AdminAccessRole \
      --role-session-name agent-session \
      --serial-number arn:aws:iam::226016658082:mfa/1password \
      --token-code "$MFA" --duration-seconds 3600 \
      --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' --output text
) && [ -n "$AWS_SESSION_TOKEN" ] \
  && export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN \
  && (umask 077; printf 'export AWS_ACCESS_KEY_ID=%s\nexport AWS_SECRET_ACCESS_KEY=%s\nexport AWS_SESSION_TOKEN=%s\n' \
       "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" "$AWS_SESSION_TOKEN" > "$TMPDIR/admin.env.$$") \
  && mv -f "$TMPDIR/admin.env.$$" "$TMPDIR/admin.env" \
  && aws sts get-caller-identity --query Arn --output text
```

Success = the printed ARN contains `assumed-role/AdminAccessRole`. Anything else,
treat as failure.

Three details carry weight, none of them cosmetic:

- **`--profile`, never `AWS_PROFILE`.** Only the CLI flag removes the environment
  credential provider from the chain (`botocore/credentials.py`: `disable_env_vars
  = session.instance_variables().get('profile') is not None`, and
  `instance_variables()` is populated by the flag alone). With `AWS_PROFILE` and
  stale `AWS_*` exported, the AssumeRole authenticates as those dead credentials
  and never reads the `loup-iam` key — a valid MFA code then fails, misleadingly.
  `env -u` strips them regardless, for that one call.
- **`umask 077` before the write, not `chmod` after.** A plain `>` creates the
  file at 0644 under the default umask, leaving live admin credentials
  world-readable until the `chmod` lands.
- **Write to `$TMPDIR`, not `/tmp`.** `$TMPDIR` is per-user, mode 700. `/tmp` is
  shared and world-writable: anyone can pre-create `.admin.env` there, and the
  redirection would then write real credentials into their file. Writing to
  `admin.env.$$` and renaming keeps a good session intact if the mint fails.

The exports land in the persistent shell, so subsequent `bash` calls in this
session are already admin.

## 3. Use it elsewhere

A fresh shell, a subagent, or a shell that lost its environment picks the
session up with:

```bash
. "$TMPDIR/admin.env"
```

Never `cat` the file or echo the variables into the transcript — they are live
credentials until they expire.

## Failures

- `MultiFactorAuthentication failed ... invalid MFA one time pass code` — the
  code expired between the ask and the run, or was mistyped. Ask again,
  immediately, and run in the same turn.
- `AccessDenied` on the AssumeRole itself — the `loup-iam` key or the role trust
  policy, not the code. Check with `aws --profile loup-iam sts get-caller-identity`.
- `ExpiredToken` on a later command — the hour is up. Delete `"$TMPDIR/admin.env"`
  and redo step 2.
