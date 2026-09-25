---
name: set-filevault-recovery-key
description: >-
  Records a Mac's FileVault personal recovery key in Flock (Les Sherpas' MDM
  control plane) for a named person or machine, through Flock's API — for a
  Mac whose own escrow never reached Flock (`key_predates_profile`,
  `enabled_not_escrowed`) when someone holds the key from elsewhere. Resolves
  the person to exactly one Mac, calls `PUT /api/devices/{serial}/recovery-key`,
  and reads the result back. Use whenever the user wants to store, set, insert,
  import, escrow or "put in Flock" a FileVault / recovery / escrow key for
  someone — "add Sebastien's FileVault key", "here's the recovery key for
  C02XYZ001", "mets la clé FileVault de Camille dans Flock", "la clé de
  récupération de Hugo est XXXX-…" — even when they say "in the db" or
  "in prod". Not for revealing a stored key or rotating one.
compatibility: >-
  Needs curl, jq and bash, network access to the Flock instance (default
  https://flock.sherpas.com, override with FLOCK_URL), and an administrator's
  Flock API key in FLOCK_API_KEY — exported, or in the secrets file named by
  FLOCK_SECRETS_FILE (default ~/.config/secrets/common.zsh).
---

# Set a FileVault recovery key in Flock

A Mac escrows its FileVault key to Flock by itself when it enables FileVault
under Flock's profile. When that never happened — FileVault was turned on
before the profile arrived (`key_predates_profile`), or the Mac never sent an
envelope (`enabled_not_escrowed`) — Flock holds nothing, and the only way in is
an administrator typing the key someone recovered elsewhere. Flock's API does
that: it encrypts the key to the active escrow certificate, stores it exactly
where a Mac-sent envelope lands, moves the escrow state to
`enabled_escrowed_manually`, and writes an audit row.

Everything goes through the API. Never write to Flock's database directly,
never reach for cloud credentials or a cluster tunnel: the API owns the
encryption, the state change and the audit row in one transaction, and a
hand-written row gets at least one of those wrong.

`$SKILL_DIR` below is **notation, not a variable that is already set** — it
stands for this skill's own directory (the one holding this `SKILL.md`).

## Why getting the Mac right matters more than anything else

Flock refuses to overwrite a key it already holds (409), because the stored one
may be the only copy that opens that disk. So a key recorded on the **wrong**
Mac cannot be corrected by typing again. It stays there until that Mac escrows
its own key or someone rotates it, and a Mac whose real key is missing stays
unrecoverable in the meantime. Nothing over MDM can check the key against the
disk either — Flock stores what it is given. A wrong target is the one mistake
this workflow cannot undo, so resolving the Mac is the step that deserves care.

## 1. Resolve the Mac

```bash
"$SKILL_DIR/scripts/flock-recovery-key.sh" find "<name, email, serial, UDID or device name>"
```

Case-insensitive substring match over owner name, owner email, serial, UDID
and device name. Prints one tab-separated row per match: UDID, serial, owner,
device name, enrolled, escrow state, key held.

Proceed only when exactly one Mac is plainly the right one:

- **Several people match** (a first name shared by two people): ask which one,
  listing names and emails. Do not guess.
- **One person owns several Macs**: ask which serial, unless exactly one of
  them is in a state that can take a key (below) — then name the one you
  picked and why.
- **No match**: try the email, the surname alone, or ask for the serial. A Mac
  with no owner assigned is found only by serial, UDID or device name.
- **UDID reads `(none: never enrolled)`**: the Mac has never checked in, so
  nothing can be recorded against it. Say so and stop.

## 2. Check the state before sending

| Escrow state | Key held | What to do |
|---|---|---|
| `key_predates_profile`, `enabled_not_escrowed` | false | The case this exists for. Send it. |
| `escrow_key_mismatch`, `user_never_enabled`, `infrastructure_error`, `(no capture)` | false | Accepted by the API. Send it if the user holds the key. |
| `profile_pending`, `awaiting_user_enablement` | false | The API answers 409: Flock is still waiting for the Mac's own escrow. Tell the user; the Mac's own key will arrive once FileVault is on. |
| any | true | The API answers 409: Flock already holds a key. Stop — see below. |

Do not call the API just to see the 409; the table already tells you.

## 3. Send the key

Validate the shape first: six groups of four letters or digits,
`XXXX-XXXX-XXXX-XXXX-XXXX-XXXX` (case and surrounding spaces are normalised).
Anything else — five groups, a stray `O`/`0` the user flagged as uncertain, a
key that looks like a 16-byte hex string — ask rather than send.

Pass the key on **stdin**, never as an argument: an argument is visible to
every local user through the process list.

```bash
printf '%s\n' 'XXXX-XXXX-XXXX-XXXX-XXXX-XXXX' \
  | "$SKILL_DIR/scripts/flock-recovery-key.sh" set <serial>
```

Success prints the `escrowedAt` timestamp, then a read-back of the device:
`escrowState=enabled_escrowed_manually keyHeld=true`. That read-back is the
proof; report it. It deliberately does not call the reveal endpoint, which
would add a second audit row saying someone read the key.

## 4. When it refuses

- **409 "already holds a recovery key"** — do not try to work around it. If
  the user believes the stored key is wrong, the repair is a rotation (the
  "Rotate" action on the device's Security & compliance card, or
  `POST /api/devices/{serial}/recovery-key/rotate`), which makes the Mac escrow a
  fresh key. It needs a FileVault user to sign in, so it is not instant. Tell
  the user; don't rotate on your own initiative.
- **409 "still waiting for this Mac to escrow its own key"** — nothing to do
  from here. Once FileVault is on and the Mac checks in, its own key arrives.
- **401** — the API key is missing, revoked or mistyped. **403** — the key's
  owner is not an administrator. Either way, say which and stop.
- **404** — the serial is unknown to Flock. Re-run `find`.

## 5. Report

Name the person, serial and UDID, the resulting state, and the timestamp.
Add the two caveats that stay true after a success:

- Nothing checked the key against the disk. A typo is stored as-is, and
  cannot be corrected by typing again (see above).
- The key has now appeared in this conversation in plain text. If that
  matters, the Mac's key should be rotated.

Never echo the key back in the report beyond what the user already wrote, and
never print `FLOCK_API_KEY`.
