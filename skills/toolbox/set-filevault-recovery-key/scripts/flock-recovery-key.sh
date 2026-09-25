#!/usr/bin/env bash
# Resolve a Mac in Flock and record its FileVault personal recovery key through
# PUT /api/devices/{serial}/recovery-key.
#
#   flock-recovery-key.sh find <query>        # owner name/email, serial, UDID or device name
#   flock-recovery-key.sh set <serial> < keyfile # key on stdin, never in argv
#
# FLOCK_URL      base URL, default https://flock.sherpas.com
# FLOCK_API_KEY  an administrator's `flk_…` key; when unset, read from
#                FLOCK_SECRETS_FILE (default ~/.config/secrets/common.zsh)
set -euo pipefail

FLOCK_URL="${FLOCK_URL:-https://flock.sherpas.com}"
FLOCK_URL="${FLOCK_URL%/}"
KEY_PATTERN='^[A-Z0-9]{4}(-[A-Z0-9]{4}){5}$'

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

for bin in curl jq; do command -v "$bin" >/dev/null || die "$bin is required"; done

api_key() {
  if [ -n "${FLOCK_API_KEY:-}" ]; then printf %s "$FLOCK_API_KEY"; return; fi
  local file="${FLOCK_SECRETS_FILE:-$HOME/.config/secrets/common.zsh}"
  [ -r "$file" ] || die "FLOCK_API_KEY is unset and $file is not readable"
  # A subshell, so the rest of that file's exports never reach this process.
  local key
  key=$(bash -c '. "$1" >/dev/null 2>&1; printf %s "${FLOCK_API_KEY:-}"' _ "$file")
  [ -n "$key" ] || die "FLOCK_API_KEY is not exported by $file"
  printf %s "$key"
}

# The bearer token goes through a curl config on stdin: in argv it would be
# readable by every local user through `ps`.
request() {
  local method=$1 path=$2 body=${3:-}
  local auth
  auth=$(printf 'header = "Authorization: Bearer %s"\n' "$(api_key)")
  if [ -n "$body" ]; then
    printf '%s\n' "$auth" | curl -sS -m 30 -K - -X "$method" \
      -H 'Content-Type: application/json' --data-binary @"$body" \
      -w '\n%{http_code}' "$FLOCK_URL$path"
  else
    printf '%s\n' "$auth" | curl -sS -m 30 -K - -X "$method" -w '\n%{http_code}' "$FLOCK_URL$path"
  fi
}

split_status() { STATUS=${1##*$'\n'}; BODY=${1%$'\n'*}; }

cmd_find() {
  local query=${1:-}
  [ -n "$query" ] || die "usage: find <owner name|email|serial|udid|device name>"
  split_status "$(request GET /api/devices)"
  [ "$STATUS" = 200 ] || die "GET /api/devices answered $STATUS: $BODY"
  printf '%s' "$BODY" | jq -r --arg q "$query" '
    ($q | ascii_downcase) as $q
    | [ .devices[]
        | select([.owner.fullName, .owner.email, .serialNumber, .udid, .inventory.deviceName]
                 | map(select(. != null) | ascii_downcase | contains($q)) | any) ]
    | if length == 0 then "no device matches"
      else (["UDID", "SERIAL", "OWNER", "DEVICE NAME", "ENROLLED", "ESCROW STATE", "KEY HELD"] | @tsv),
           (.[] | [ (.udid // "(none: never enrolled)"), .serialNumber,
                    (if .owner then "\(.owner.fullName) <\(.owner.email)>" else "(unassigned)" end),
                    (.inventory.deviceName // "-"), (.enrolled | tostring),
                    (.fileVaultEscrowCapture.state // "(no capture)"),
                    (.fileVaultRecoveryKeyEscrowed | tostring) ] | @tsv)
      end'
}

cmd_set() {
  local serial=${1:-}
  [ -n "$serial" ] || die "usage: set <serial>   (recovery key on stdin)"
  local key
  IFS= read -r key || [ -n "$key" ] || die "no recovery key on stdin"
  key=$(printf %s "$key" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')
  [[ $key =~ $KEY_PATTERN ]] || die "recovery key must be six groups of four letters or digits (XXXX-XXXX-XXXX-XXXX-XXXX-XXXX)"

  # Global, not local: the EXIT trap fires after this function's scope is gone.
  BODY_FILE=$(mktemp)
  trap 'rm -f "${BODY_FILE:-}"' EXIT
  chmod 600 "$BODY_FILE"
  jq -n --arg k "$key" '{recoveryKey: $k}' > "$BODY_FILE"
  split_status "$(request PUT "/api/devices/$serial/recovery-key" "$BODY_FILE")"
  rm -f "$BODY_FILE"

  case "$STATUS" in
    200) ;;
    409) die "409 $(printf '%s' "$BODY" | jq -r '.error // .')" ;;
    *) die "PUT answered $STATUS: $BODY" ;;
  esac
  printf 'stored: escrowedAt=%s\n' "$(printf '%s' "$BODY" | jq -r .escrowedAt)"

  # Read back what the fleet page will show, without the audited reveal.
  split_status "$(request GET "/api/devices/$serial")"
  [ "$STATUS" = 200 ] || die "stored, but GET /api/devices/$serial answered $STATUS"
  printf '%s' "$BODY" | jq -r '.device | "serial=\(.serialNumber) owner=\(.owner.email // "(unassigned)") escrowState=\(.fileVaultEscrowCapture.state) keyHeld=\(.fileVaultRecoveryKeyEscrowed)"'
}

case "${1:-}" in
  find) shift; cmd_find "$@" ;;
  set) shift; cmd_set "$@" ;;
  *) die "usage: $0 find <query> | set <serial> (recovery key on stdin)" ;;
esac
