#!/bin/sh
# One MCP header value for omp, read from the SOPS store next to this script:
#
#   secret.sh 'Bearer ' APIFY_API_TOKEN
#
# omp runs a `!`-prefixed header value through /bin/sh -c and drops the header whenever
# the command prints nothing (packages/coding-agent/src/mcp/manager.ts, together with
# config/resolve-config-value.ts). That is why this exits 1 on a missing key: a plain
# "${APIFY_API_TOKEN}" reference would be sent to the server as that literal text.
set -eu

[ "$#" -eq 2 ] || { echo "usage: $(basename "$0") PREFIX NAME" >&2; exit 2; }

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
value=$(sops exec-env "$here/secrets.sops.yaml" "printf '%s' \"\$$2\"") || exit 1
[ -n "$value" ] || exit 1
printf '%s%s' "$1" "$value"
