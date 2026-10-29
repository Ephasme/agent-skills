#!/usr/bin/env python3
"""slack-reaction.py — add or remove a Slack reaction via the Web API.

The Slack MCP server exposes add and get reactions only; removal exists at the
API but not as an MCP tool. This script closes that gap with the user token of
the user's own Slack app, read from SLACK_USER_TOKEN (xoxp-…, needs
`reactions:write`).

Usage:
  slack-reaction.py add    <channel> <ts> <emoji>     e.g. emoji "white_check_mark"
  slack-reaction.py remove <channel> <ts> <emoji>
  slack-reaction.py test                              auth.test with the token

Exit codes: 0 ok, 1 Slack error, 2 usage, 3 SLACK_USER_TOKEN unset.
"""
import json
import os
import sys
import urllib.request

API = "https://slack.com/api/"


def load_token():
    token = os.environ.get("SLACK_USER_TOKEN")
    if not token:
        print("SLACK_USER_TOKEN unset", file=sys.stderr)
        sys.exit(3)
    return token


def call(method, token, params):
    body = json.dumps(params).encode()
    req = urllib.request.Request(
        API + method,
        data=body,
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            out = json.loads(res.read().decode())
    except Exception as exc:  # network/HTTP failure
        print(f"{method}: {exc}", file=sys.stderr)
        sys.exit(1)
    if not out.get("ok"):
        print(f"{method}: error {out.get('error')}", file=sys.stderr)
        sys.exit(1)
    return out


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    cmd = args[0]
    token = load_token()
    if cmd == "test":
        me = call("auth.test", token, {})
        print("user:", me.get("user_id"), "team:", me.get("team_id"))
        return
    if cmd in ("add", "remove") and len(args) == 4:
        _, channel, ts, emoji = args
        method = "reactions.add" if cmd == "add" else "reactions.remove"
        call(method, token, {"channel": channel, "timestamp": ts, "name": emoji})
        print(f"{cmd} :{emoji}: on {channel} {ts}")
        return
    print(__doc__)
    sys.exit(2)


if __name__ == "__main__":
    main()
