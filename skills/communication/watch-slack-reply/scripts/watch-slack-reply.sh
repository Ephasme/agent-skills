#!/usr/bin/env bash
# Watches a Slack conversation and pushes an ntfy message when someone other than the token owner
# answers. Read-only on Slack. See SKILL.md for setup and usage.
#
#   watch-slack-reply.sh <channel-id> [--thread <ts>] [--since <ts>] [--scope thread|conversation]
#                        [--hours N] [--interval S] [--settle S] [--topic T] [--no-notify]
#
# Exit: 0 reply found, 1 setup error, 2 nothing arrived before --hours elapsed.
set -u

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

CH=""; THREAD=""; SINCE=""; SCOPE=""; HOURS=4; INTERVAL=60; SETTLE=90; TOPIC=answers; NOTIFY=1
[ $# -ge 1 ] || usage
CH=$1; shift
while [ $# -gt 0 ]; do
  case $1 in
    --thread)    THREAD=${2:?}; shift 2 ;;
    --since)     SINCE=${2:?}; shift 2 ;;
    --scope)     SCOPE=${2:?}; shift 2 ;;
    --hours)     HOURS=${2:?}; shift 2 ;;
    --interval)  INTERVAL=${2:?}; shift 2 ;;
    --settle)    SETTLE=${2:?}; shift 2 ;;
    --topic)     TOPIC=${2:?}; shift 2 ;;
    --no-notify) NOTIFY=0; shift ;;
    *) usage ;;
  esac
done

CONF="${XDG_CONFIG_HOME:-$HOME/.config}/watch-slack-reply/env"
[ -f "$CONF" ] && . "$CONF"

# A DM has no meaningful "other threads": watch all of it. A channel is watched through one thread.
if [ -z "$SCOPE" ]; then
  if [ -n "$THREAD" ] && [ "${CH#D}" = "$CH" ]; then SCOPE=thread; else SCOPE=conversation; fi
fi
[ "$SCOPE" = thread ] && [ -z "$THREAD" ] && { echo "ERROR: --scope thread needs --thread" >&2; exit 1; }
[ -n "$SINCE" ] || SINCE=${THREAD:-$(date +%s).000000}

# secret <ENV_NAME> <ENV_NAME_HOLDING_AN_OP_REFERENCE>
secret() {
  local v="${!1:-}"
  if [ -z "$v" ] && [ -n "${!2:-}" ]; then v=$(op read ${OP_ACCOUNT:+--account "$OP_ACCOUNT"} "${!2}" 2>/dev/null); fi
  printf %s "$v"
}

# Tokens are read once, kept in a private directory, and removed on any exit: the watcher then runs
# for hours without depending on the password manager session that started it.
DIR=$(umask 077; mktemp -d "${TMPDIR:-/tmp}/watch-slack-reply.XXXXXX") || exit 1
trap 'rm -rf "$DIR"' EXIT
trap 'exit 130' INT TERM HUP
SLACK_HDR="$DIR/slack"; NTFY_HDR="$DIR/ntfy"

ST=$(secret SLACK_USER_TOKEN SLACK_TOKEN_OP_REF)
[ -n "$ST" ] || { echo "ERROR: no Slack token (set SLACK_USER_TOKEN or SLACK_TOKEN_OP_REF in $CONF)" >&2; exit 1; }
( umask 077; printf 'Authorization: Bearer %s\n' "$ST" > "$SLACK_HDR" ); unset ST

if [ "$NOTIFY" = 1 ]; then
  [ -n "${NTFY_URL:-}" ] || { echo "ERROR: NTFY_URL not set in $CONF" >&2; exit 1; }
  NT=$(secret NTFY_TOKEN NTFY_TOKEN_OP_REF)
  [ -n "$NT" ] || { echo "ERROR: no ntfy token (set NTFY_TOKEN or NTFY_TOKEN_OP_REF in $CONF)" >&2; exit 1; }
  ( umask 077; printf 'Authorization: Bearer %s\n' "$NT" > "$NTFY_HDR" ); unset NT
fi

SLACK=https://slack.com/api
sapi() { curl -s -m 20 -H "@$SLACK_HDR" "$@"; }

AUTH=$(sapi "$SLACK/auth.test")
ME=$(jq -r 'select(.ok==true)|.user_id' <<<"$AUTH")
[ -n "$ME" ] || { echo "ERROR: Slack token rejected: $(jq -r .error <<<"$AUTH")" >&2; exit 1; }

RESULT='[]'; lasterr=""
# collect: sets RESULT to the new messages from someone else, oldest first; returns 1 on Slack error.
collect() {
  local out='[]' r
  if [ "$SCOPE" = conversation ]; then
    r=$(sapi "$SLACK/conversations.history?channel=$CH&oldest=$SINCE&inclusive=false&limit=100")
    [ "$(jq -r .ok <<<"$r" 2>/dev/null)" = true ] || { lasterr="slack: $(jq -r .error <<<"$r" 2>/dev/null)"; return 1; }
    out=$(jq -c --arg me "$ME" --arg s "$SINCE" \
      '[.messages[]?|select(.user!=$me and ((.subtype//"")|test("^(channel|group)_")|not) and (.ts|tonumber)>($s|tonumber))]' <<<"$r")
  fi
  if [ -n "$THREAD" ]; then
    r=$(sapi "$SLACK/conversations.replies?channel=$CH&ts=$THREAD&oldest=$SINCE&limit=200")
    [ "$(jq -r .ok <<<"$r" 2>/dev/null)" = true ] || { lasterr="slack: $(jq -r .error <<<"$r" 2>/dev/null)"; return 1; }
    out=$(jq -c --argjson prev "$out" --arg me "$ME" --arg s "$SINCE" --arg t "$THREAD" \
      '$prev+[.messages[]?|select(.user!=$me and .ts!=$t and (.ts|tonumber)>($s|tonumber))]' <<<"$r")
  fi
  RESULT=$(jq -c 'unique_by(.ts)|sort_by(.ts|tonumber)' <<<"$out")
}

name_of() {
  local n; n=$(sapi "$SLACK/users.info?user=$1" | jq -r '.user.real_name // empty' 2>/dev/null)
  printf %s "${n:-$1}"
}

notify() { # <title> <message> <click-url>
  local body code
  body=$(jq -nc --arg t "$TOPIC" --arg ti "$1" --arg m "$2" --arg c "$3" \
    '{topic:$t,title:$ti,message:$m,click:$c,tags:["speech_balloon"],priority:3}')
  code=$(curl -s -m 20 -o /dev/null -w '%{http_code}' -H "@$NTFY_HDR" -H 'Content-Type: application/json' \
    -d "$body" "${NTFY_URL%/}/")
  [ "$code" = 200 ] && echo "ntfy: sent to topic $TOPIC" || echo "ntfy: FAILED (HTTP $code)" >&2
}

END=$(( $(date +%s) + HOURS * 3600 )); polls=0
while [ "$(date +%s)" -lt "$END" ]; do
  polls=$((polls+1))
  if collect && [ "$(jq length <<<"$RESULT")" -gt 0 ]; then
    sleep "$SETTLE"            # let a burst of messages finish
    collect                    # on failure RESULT still holds the first read
    N=$(jq length <<<"$RESULT")
    echo "REPLY after $polls polls ($N message(s)):"
    jq -r '.[]|"[\(.ts|tonumber|localtime|strftime("%H:%M:%S"))] \(.user // .bot_id // "?"): \(.text)"' <<<"$RESULT"
    if [ "$NOTIFY" = 1 ]; then
      first=$(jq -c '.[0]' <<<"$RESULT")
      who=$(name_of "$(jq -r '.user // empty' <<<"$first")")
      text=$(jq -r '.text' <<<"$first" | tr '\n' ' ' | cut -c1-280)
      [ "$N" -gt 1 ] && text="$text (+$((N-1)) more)"
      link=$(sapi "$SLACK/chat.getPermalink?channel=$CH&message_ts=$(jq -r .ts <<<"$first")" | jq -r '.permalink // empty')
      notify "Slack: $who answered" "$text" "$link"
    else
      echo "ntfy: skipped (--no-notify)"
    fi
    exit 0
  fi
  sleep "$INTERVAL"
done
echo "NO REPLY after ${HOURS} h ($polls reads, last error: ${lasterr:-none})"
exit 2
