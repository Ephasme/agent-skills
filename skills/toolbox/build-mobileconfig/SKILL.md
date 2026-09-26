---
name: build-mobileconfig
description: >-
  Builds, reviews and fixes macOS configuration profiles (.mobileconfig) against
  Apple's own device-management schema, with stable payload UUIDs, correct scope,
  same-profile certificate references, per-machine variable placeholders and no
  committed secrets. Use whenever the user wants to create, write, generate,
  edit, lint, validate, debug or explain a .mobileconfig / configuration profile
  / MDM profile / payload for a Mac — Wi-Fi, VPN, certificates, FileVault
  escrow, firewall, Gatekeeper, passcode, PPPC/TCC, system or kernel extensions,
  restrictions, login window, screen saver, managed app preferences (e.g. a
  vendor's bundle ID) — or asks for a value filled per machine at install time
  (a dynamic profile: `{{name}}` variables the MDM resolves, an SSH key list, a
  per-machine name or endpoint), or asks "why won't this profile install",
  "which payload does X", "is this key still supported", even when they never say
  "mobileconfig". Not for iOS-only profiles or DDM declarations.
compatibility: >-
  macOS with git, plutil, openssl and uv (the helper is a uv inline script that
  pulls pyyaml). Network once, to clone github.com/apple/device-management.
---

# Build a macOS configuration profile

A `.mobileconfig` fails quietly more often than loudly: macOS accepts a profile
whose Wi-Fi password is a placeholder, whose firewall payload sits in a
User-scoped profile, or whose certificate reference points at nothing, and
reports success. The schema catches most of this before a Mac ever sees it, so
every profile goes through Apple's schema, never through memory of it.

`$SKILL_DIR` is notation for this skill's directory, not a set variable.

## Sources, in the order they win

1. **Apple's schema** — `github.com/apple/device-management`, branch `release`.
   The helper clones it to `~/.cache/apple-device-management` on first use;
   `schema --update` pulls. Payload keys, types, ranges, `supportedOS`
   (introduced / deprecated / removed, channels, supervision, UAMDM, manual
   install), and `docs/errata.md`, which retroactively corrects it.
2. **Apple's prose** — developer.apple.com/documentation/devicemanagement
   (same content, plus worked examples) and support.apple.com/guide/deployment
   (behaviour: merge rules, duplicates, what a user sees). When prose and schema
   disagree, report both; do not pick silently.
3. **Learnings measured in this workspace** — `references/learnings.md`. Things
   the schema does not say and that cost a real Mac to find out.
4. **The vendor's own MDM docs**, for a third-party preference domain only
   (e.g. Tailscale's `io.tailscale.ipn.macsys`). Apple has no schema for those.

Not sources: blog posts, other MDMs' UIs, ProfileCreator/iMazing manifests,
LLM memory. They may hint where to look; they never justify a key. Say
"no primary source found" rather than fill a gap.

## The helper

```bash
M="$SKILL_DIR/scripts/mobileconfig.py"
"$M" schema --search wifi                 # which PayloadType
"$M" schema com.apple.wifi.managed        # every key, type, default, range, macOS gate
"$M" uuid com.example.wifi.corp           # stable PayloadUUID for an identifier
"$M" build spec.json -o corp-wifi.mobileconfig [--keep-uuids-from deployed.mobileconfig]
"$M" lint *.mobileconfig                  # XML or CMS-signed
"$M" --min-macos 15.0 lint …              # warn on keys newer than the fleet floor (default 14.0)
```

`lint` exits non-zero on any ERROR. Read every WARN aloud in the answer; each
one is a decision the user should know was made.

## Workflow

### 1. Pin down the intent

What should change on the Mac, for whom (every user → System scope; one user →
User scope), how it is delivered (MDM, or double-click install), and the oldest
macOS in the fleet. Ask only for what the code, the existing profiles and the
schema cannot tell you. If the repository already has profiles, read two of
them first and match their identifier prefix, organization and layout.

### 2. Find the payload and read its schema

`schema --search`, then `schema <PayloadType>`. Read the **Notes** section as
carefully as the keys: scope requirements, merge rules ("most restrictive
union"), and side effects on removal live there. Check, for the payload and for
each key you plan to set:

- `introduced` against the fleet floor; `deprecated`/`removed` — a
  `Deprecated: use …` line names the replacement (often a DDM declaration).
- `userapprovedmdm`, `allowmanualinstall: false`, `requiresdep`, `supervised` —
  each one is a way the profile installs on one Mac and fails on another.
- `multiple: false` — one such payload **per Mac**, across every profile, not
  per file.
- `presence: required`, `rangelist`, `range`, `format`, `default`.

Set only keys that change something. A key equal to its default is noise, and a
restriction nobody asked for is a surprise. Keep a short "deliberately absent"
list — keys you considered and left out, with the reason — because the next
person will otherwise add them.

### 3. Build it

Write a spec and let `build` assemble the container, so identifiers, UUIDs,
scope and `TargetDeviceType` are never hand-typed:

```json
{
  "identifier": "com.example.corp-wifi",
  "display_name": "Corporate Wi-Fi",
  "description": "Joins CorpNet with the device certificate.",
  "organization": "Example",
  "scope": "System",
  "payloads": [
    {"id": "ca",   "type": "com.apple.security.root",
     "settings": {"PayloadContent": {"$data_file": "ca.der"}, "PayloadCertificateFileName": "ca.cer"}},
    {"id": "wifi", "type": "com.apple.wifi.managed",
     "settings": {"SSID_STR": "CorpNet", "EncryptionType": "WPA2", "AutoJoin": true,
                  "EAPClientConfiguration": {"AcceptEAPTypes": [13],
                                             "PayloadCertificateAnchorUUID": [{"$uuid": "ca"}]}}}
  ]
}
```

- Payload identifier = `<identifier>.<id>`; its `PayloadUUID` =
  `uuid5(NAMESPACE_DNS, PayloadIdentifier)`, uppercased. Same input, same file.
- `{"$uuid": "<id>"}` inserts another payload's `PayloadUUID` — the only safe way
  to write `PayloadCertificateUUID`, `EncryptCertPayloadUUID`,
  `PayloadCertificateAnchorUUID` and friends.
- `{"$data": "<base64>"}`, `{"$data_file": "path"}` → `<data>`;
  `{"$date": "2027-01-01T00:00:00Z"}` → `<date>`; `{"$real": 1}` → `<real>`.
- `removal_disallowed`, `extra_top_level` for anything else at the top.
- `--keep-uuids-from <file>` when changing a profile **already on Macs** whose
  UUIDs were not derived: the deployed UUIDs win, so the update is in place.
- A value that differs per machine — an SSH key list, a per-site endpoint, a
  per-user name — is a `{{name}}` placeholder left in a `<string>` for the MDM to
  fill at install, not a `REPLACE-…` you fill before upload. The two are not
  interchangeable; see **A per-machine value is a placeholder the MDM fills**
  below.

Hand-writing XML is fine for a trivial edit to an existing profile; lint it
afterwards all the same.

### 4. Lint, then explain

Run `lint`. Fix every ERROR. For each WARN, either fix it or state why it
stands (e.g. "requires user-approved MDM — fine, these Macs are ADE-enrolled";
`[INFERENCE]` if that is a reading rather than a quote). `plutil -lint` alone
proves only that the XML parses. Lint reports a dynamic profile's variables in
its INFO rows — treat that list as work for the operator, not as noise.

Then tell the user what the profile does **not** prove: `ProfileList` returns
payload metadata, never values, so an installed profile is evidence the payload
is present, not that it works — and for a dynamic one, not that the machine got
the value it should have. Name the read-back that does prove it — the artifact
the value produces on the Mac, a `SecurityInfo` field, a `profiles show`, the
app's own status — or say none exists. The MDM's own queue view is where the
rendered values are checked, and reading it there is handling a secret.

### 5. Deliver

- **Unsigned XML plist.** MDM `InstallProfile` does not require a signature;
  Apple exempts MDM from the same-signer replacement rule. Never emit a binary
  plist: Apple documents profiles as XML only.
- **Sign only for manual distribution** (email, web download), and then keep
  signing every later version with the same identity, or a manually installed
  copy cannot be replaced:
  `openssl smime -sign -signer cert.pem -inkey key.pem -certfile chain.pem -nodetach -outform der -in p.mobileconfig -out p.signed.mobileconfig`.
- **Manual install on macOS 11+**: `profiles install` no longer works; the user
  opens the file, then System Settings → General → Device Management →
  Downloaded, double-click, Install. Payloads with `allowmanualinstall: false`
  (PPPC, system/kernel extensions, service management) cannot go this way at all.

## Rules that are easy to break

**Payload UUIDs are stable forever.** macOS replaces a profile when the
top-level `PayloadIdentifier` matches, and updates a payload in place only when
both its `PayloadIdentifier` and `PayloadUUID` match the installed one. A new
UUID turns every edit into remove-and-add — for a certificate, VPN or FileVault
payload that means reprovisioning. Never call `uuidgen` or `crypto.randomUUID()`
at render time; never change the UUID of a payload that is already deployed.
(Apple: `TopLevel.yaml` and `CommonPayloadKeys.yaml`, `PayloadIdentifier`/`PayloadUUID`.)

**A certificate reference resolves inside one file.** Every `*CertificateUUID`
key names a `PayloadUUID` in the same `.mobileconfig`; a payload and the
certificate or identity it uses cannot be split across two profiles. Check the
user's plan against this, not only your file: "the identity comes from our other
SCEP profile" for an EAP-TLS network, VPN or SSO payload is exactly that split,
and the right answer is to challenge it, not to build around it.

**Scope is explicit.** Emit `PayloadScope` every time: the current schema
states no default (only the 2019 PDF says `User`). Firewall, FileVault escrow,
system extensions and most security payloads require `System`.

**A credential in a profile is plaintext.** `Password`, `SharedSecret`, a
PKCS #12, a removal password — anyone with the file reads it, and profile
encryption needs a certificate already on that one Mac, so it is not a fix.
Commit a template with a `REPLACE-…` placeholder and fill it at render time from
the secret store. A placeholder installs cleanly and does nothing, so it must
never be the thing uploaded. Where the value differs per machine, the next rule
is the mechanism instead.

**A per-machine value is a placeholder the MDM fills, not one you fill.** Two
mechanisms look alike and are not. `REPLACE-…`, substituted before upload,
produces one file for every Mac. `{{name}}`, left in the file, is substituted by
the MDM per machine at the install — so the file is a template at rest and only
ever becomes concrete on the way to one device. Reach for it when the value
genuinely differs per machine (an SSH key list, a per-machine endpoint, a
per-user name) and the MDM supports it; otherwise prefer the fixed value, because
a variable the MDM cannot resolve **fails that install** rather than falling back
to a default. The rules the mechanism imposes:

- Inside `<string>` values only. A placeholder in a `<key>`, a `<data>` or a
  number is not a placeholder — it is literal text that reaches the Mac.
- Never in `PayloadIdentifier`, `PayloadUUID`, `PayloadType` or any
  `*CertificateUUID`. The first three have to stay identical on every machine or
  the update stops being in place; a certificate reference has to name a payload
  in this same file.
- A `<string>` holding **nothing but** one placeholder may be replaced by an
  `<array>` when that variable holds a list — the plist type in the installed
  payload is then not the one in the file. Nothing on the Mac side can be
  surprised by that (the payload is validated after substitution), but a
  placeholder meant as one string does not survive being typed as a list.
- The values are sealed in the MDM's store: not in its API responses, not in its
  event log. The profile it *sends* carries them in clear, so the operator's
  stdout, a command log or a `curl` of the device queue is a leak even though the
  API looks clean.
- Syntax, the catalog the variables must be defined in, and the precedence
  between a value typed at assignment and one a group carries are all the MDM's,
  not Apple's. This skill writes `{{name}}` — lowercase, digits and underscores,
  starting with a letter — because that is what the MDM here accepts; confirm
  against the MDM's own docs before shipping a template somewhere else. Name
  every variable the profile references, so the operator can define each one
  before the upload is refused or the install fails.

**Top-level keys that bite:** `RemovalDate`, `DurationUntilRemoval` (silently
drop enforcement), `PayloadExpirationDate` (prompts the user), `ConsentText`
(forces a dialog), `PayloadRemovalDisallowed` (on macOS 10.15+ it guards only a
manually installed copy; MDM profiles are unremovable by users anyway). Set them
only on purpose. `TargetDeviceType: 5` is a free wrong-platform guard.

**Custom preference domains are unchecked.** A payload whose `PayloadType` is
an app's bundle ID carries the app's own keys flat beside `PayloadType`; the
helper cannot validate them. Cite the vendor's documentation for every key, and
prefer the vendor's current key name over whatever an old template used.

## Per-payload learnings

`references/learnings.md` — read the section for the payload you are touching
before writing it: FileVault + escrow, certificates, Wi-Fi, VPN / network
extensions, PPPC, system and kernel extensions, firewall, Gatekeeper, passcode,
restrictions and Activation Lock, managed preferences, dynamic per-machine
placeholders.

## Answer shape

The profile (path), the lint result, then:

- keys set, one line each with the reason;
- deliberately absent keys that someone would plausibly add, with the reason;
- for a dynamic profile, every `{{variable}}` the file now references, and what
  the operator has to define before it installs at all;
- gates (UAMDM, supervision, ADE, manual-install refused, macOS floor);
- how to verify on a real Mac, or that nothing can;
- anything with no primary source, said as such.
