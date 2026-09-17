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

# AWS admin session (1h, MFA)

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
prompt:

```bash
[ -f /tmp/.admin.env ] && . /tmp/.admin.env && aws sts get-caller-identity --query Arn --output text
```

Prints `.../AdminAccessRole/...` → already admin, stop here, do the work.
Fails or prints the plain IAM user → continue.

## 2. Mint the session

Only now ask for the code, then run with `MFA` set to what the user gave:

```bash
MFA=123456
cd /tmp && read -r AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN < <(
  AWS_PROFILE=loup-iam aws sts assume-role \
    --role-arn arn:aws:iam::226016658082:role/AdminAccessRole \
    --role-session-name agent-session \
    --serial-number arn:aws:iam::226016658082:mfa/1password \
    --token-code "$MFA" --duration-seconds 3600 \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' --output text
) && export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN \
  && printf 'export AWS_ACCESS_KEY_ID=%s\nexport AWS_SECRET_ACCESS_KEY=%s\nexport AWS_SESSION_TOKEN=%s\n' \
     "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" "$AWS_SESSION_TOKEN" > /tmp/.admin.env \
  && chmod 600 /tmp/.admin.env && aws sts get-caller-identity --query Arn --output text
```

Success = the printed ARN contains `assumed-role/AdminAccessRole`. Anything else,
treat as failure.

`cd /tmp` avoids `read` from a process substitution in a directory the shell
can't handle; the exports land in the persistent shell, so subsequent `bash`
calls in this session are already admin.

## 3. Use it elsewhere

A fresh shell, a subagent, or a shell that lost its environment picks the
session up with:

```bash
. /tmp/.admin.env
```

Never `cat` the file or echo the variables into the transcript — they are live
credentials until they expire.

## Failures

- `MultiFactorAuthentication failed ... invalid MFA one time pass code` — the
  code expired between the ask and the run, or was mistyped. Ask again,
  immediately, and run in the same turn.
- `AccessDenied` on the AssumeRole itself — the `loup-iam` key, not the code.
  Check with `aws sts get-caller-identity --profile loup-iam`.
- `ExpiredToken` on a later command — the hour is up. Delete `/tmp/.admin.env`
  and redo step 2.
