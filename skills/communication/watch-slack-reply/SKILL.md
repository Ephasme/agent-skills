---
name: watch-slack-reply
description: >-
  Waits in the background for someone to answer a Slack message, DM or thread, then pushes a phone
  notification with the answer and a link to it. Use when the user says "tell me when X replies",
  "watch this thread", "ping me when someone answers", "surveille la réponse", "préviens-moi
  quand il répond", or after the agent posts a question in Slack and the user wants to be told of
  the answer instead of polling. Read-only on Slack; never posts, reacts or marks anything read.
compatibility: >-
  Slack and ntfy. Needs bash, curl and jq, a Slack user token (channels:history, groups:history,
  im:history, users:read) and a write-scoped ntfy token. A 1Password CLI session is only needed at
  start when the Slack token is read through an `op://` reference.
---

# Watch a Slack reply

`$SKILL_DIR` is notation for this skill's directory. `$SKILL_DIR/scripts/watch-slack-reply.sh` polls one conversation and exits on the first message
written by someone other than the token's owner. It then sends one ntfy message to topic `answers`
(title "Slack: <name> answered", body the text, click target the Slack permalink) and prints the
messages. Exit 0 = answered, 2 = nothing within `--hours`, 1 = setup error.

## Run it

Start it as a background process with the harness's no-deadline option, never as a foreground call:
the watcher outlives any command timeout and its output wakes the session when it ends.

```bash
# a thread in a channel
$SKILL_DIR/scripts/watch-slack-reply.sh C09EJ3GRGJU --thread 1794490120.350439 --since 1794492448.429169
# a whole DM
$SKILL_DIR/scripts/watch-slack-reply.sh D09MPE4V4HM --since 1794486896.151249
```

| Flag | Meaning | Default |
|---|---|---|
| `<channel-id>` | channel, group or DM id | required |
| `--thread <ts>` | thread root; replies in that thread count | none |
| `--since <ts>` | only messages after this ts count; set it to the ts of the message just sent | thread root, else now |
| `--scope thread\|conversation` | `thread` ignores the rest of the channel | `thread` for a channel thread, `conversation` for a DM or no `--thread` |
| `--hours N`, `--interval S`, `--settle S` | give up after N h; poll every S s; wait S s after the first hit so a burst of messages arrives in one push | 4, 60, 90 |
| `--topic T` | ntfy topic | `answers` |
| `--no-notify` | print only | off |

Without `--since` a thread watcher reports replies already in the thread. Pass the ts of your own
last message there, otherwise old answers fire the push at once.

Slack ts: the digits after `p` in a permalink, with a dot before the last six
(`p1794490120350439` → `1794490120.350439`).

## Setup, once per machine

Config lives outside any repo, in `${XDG_CONFIG_HOME:-$HOME/.config}/watch-slack-reply/env`, mode
600, directory mode 700:

```
NTFY_URL=<ntfy server base URL>
NTFY_TOKEN=<write token for the topic>        # or NTFY_TOKEN_OP_REF=op://vault/item/field
SLACK_USER_TOKEN=<xoxp-...>                   # or SLACK_TOKEN_OP_REF=op://vault/item/field
OP_ACCOUNT=<optional 1Password account for op read>
```

The user token, not a bot token, because a bot only sees conversations it was invited to and the
watched DM or private channel usually is not one of them.

Tokens are read once at start into a private temp directory that a trap deletes on every exit
(reply, timeout, error, INT/TERM/HUP), so a long run no longer depends on the password manager
session. Nothing secret is printed or put on a command line.

## Checks before trusting a run

- `--since` is the ts of your last message, not of the thread root, unless old replies should count.
- The channel id is the id (`C…`, `G…`, `D…`), not the name.
- A silent failure shows as `last error: slack: <code>` in the timeout line: `missing_scope` or
  `channel_not_found` means the token cannot see that conversation.
- Test the push path with `--no-notify` off against a thread that already has a reply and
  `--since` at its root: it must fire within one poll.
