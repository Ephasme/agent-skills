#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Build, check and look up macOS configuration profiles against Apple's own schema.

  mobileconfig.py schema <PayloadType>         what Apple's schema says about a payload, macOS view
  mobileconfig.py schema --search <text>       payload types whose type/title/description match
  mobileconfig.py uuid <PayloadIdentifier>...  the stable PayloadUUID for an identifier
  mobileconfig.py build <spec.json> -o <out>   assemble a profile from a JSON spec, then lint it
  mobileconfig.py lint <file.mobileconfig>...  check a profile (XML or CMS-signed) against the schema

The schema is github.com/apple/device-management, branch `release`, cloned to
$APPLE_DM_SCHEMA (default ~/.cache/apple-device-management). `schema --update` pulls it.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import plistlib
import re
import subprocess
import sys
import uuid
from pathlib import Path

import yaml

SCHEMA_REPO = "https://github.com/apple/device-management"
SCHEMA_DIR = Path(os.environ.get("APPLE_DM_SCHEMA", "~/.cache/apple-device-management")).expanduser()
UUID_RE = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")
# Keys that point at another payload's PayloadUUID; Apple resolves them within one profile.
CERT_REF_RE = re.compile(r"(?i)(cert|identity)\w*uuids?$")
SECRET_KEYS = {
    "Password", "AuthPassword", "SharedSecret", "RemovalPassword", "AuthKey", "Challenge",
    "AutologinPassword", "PIN", "Secret", "UserPassword", "AccountPassword",
}
TYPES = {
    "<string>": (str,), "<integer>": (int,), "<real>": (float, int), "<boolean>": (bool,),
    "<data>": (bytes,), "<date>": (dt.datetime,), "<array>": (list,), "<dictionary>": (dict,),
}


def stable_uuid(identifier: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, identifier)).upper()


# ---------------------------------------------------------------- schema


def ensure_schema(update: bool = False) -> Path:
    if not (SCHEMA_DIR / "mdm" / "profiles").is_dir():
        SCHEMA_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", "--branch", "release", SCHEMA_REPO, str(SCHEMA_DIR)],
            check=True,
        )
    elif update:
        subprocess.run(["git", "-C", str(SCHEMA_DIR), "pull", "--quiet", "--ff-only"], check=True)
    return SCHEMA_DIR


def schema_revision() -> str:
    out = subprocess.run(
        ["git", "-C", str(SCHEMA_DIR), "log", "-1", "--format=%h %s"], capture_output=True, text=True
    )
    return out.stdout.strip() or "unknown"


_index: dict[str, list[Path]] | None = None
# Apple's own note on the App-Layer VPN payload: "The fields in this payload are the same as the
# VPN payload, with the addition of the fields shown below."
EXTENDS = {"com.apple.vpn.managed.applayer": "com.apple.vpn.managed"}


def schema_index() -> dict[str, list[Path]]:
    """PayloadType -> YAML files. Keyed on `payload.payloadtype`, never the filename:
    `com.apple.preferences.users.yaml` declares `com.apple.preference.users`. One type can have
    several files — `com.apple.MCX` has six variants, `com.apple.extensiblesso` two."""
    global _index
    if _index is None:
        _index = {}
        for f in sorted((ensure_schema() / "mdm" / "profiles").glob("*.yaml")):
            doc = yaml.safe_load(f.read_text())
            ptype = (doc.get("payload") or {}).get("payloadtype")
            if ptype and f.stem not in ("TopLevel", "CommonPayloadKeys"):
                _index.setdefault(ptype, []).append(f)
    return _index


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def macos(block: dict | None, parent: dict | None = None) -> dict:
    """Apple's inheritance rule: a key inherits the payload's supportedOS, then its own overrides."""
    merged = dict(parent or {})
    merged.update(((block or {}).get("supportedOS") or {}).get("macOS") or {})
    return merged


def is_na(os_block: dict) -> bool:
    return str(os_block.get("introduced", "")).lower() == "n/a"


def schema_notes(doc: dict) -> str:
    parts = [(doc.get("payload") or {}).get("content") or ""]
    parts += [n.get("content") or "" for n in doc.get("notes") or []]
    return "\n".join(p for p in parts if p)


def payload_schemas(ptype: str) -> list[dict]:
    docs = [load(f) for f in schema_index().get(ptype, [])]
    base = EXTENDS.get(ptype)
    if base and docs:
        extra = [k for d in payload_schemas(base) for k in d.get("payloadkeys") or []]
        for d in docs:
            d["payloadkeys"] = (d.get("payloadkeys") or []) + extra
    return docs


# ---------------------------------------------------------------- schema command


def fmt_os(o: dict) -> str:
    keep = ["introduced", "deprecated", "removed", "multiple", "devicechannel", "userchannel",
            "supervised", "requiresdep", "userapprovedmdm", "allowmanualinstall"]
    bits = [f"{k}={o[k]}" for k in keep if k in o]
    ue = (o.get("userenrollment") or {}).get("mode")
    if ue:
        bits.append(f"userenrollment={ue}")
    return " ".join(bits)


def print_keys(keys: list[dict], parent_os: dict, depth: int = 0, root_os: dict | None = None) -> None:
    pad = "  " * depth
    for k in keys:
        kos = macos(k, parent_os)
        line = f"{pad}- {k['key']} {k.get('type', '?')} {k.get('presence', '')}"
        if "default" in k:
            line += f" default={k['default']!r}"
        if "rangelist" in k:
            line += f" one-of={k['rangelist']}"
        if "range" in k:
            line += f" range={k['range']}"
        if "format" in k:
            line += f" format={k['format']}"
        own = ((k.get("supportedOS") or {}).get("macOS")) or {}
        if own:
            line += f"  [macOS {fmt_os(own)}]"
        if is_na(kos):
            line += "  ** NOT ON macOS **"
        print(line)
        content = (k.get("content") or "").strip().replace("\n", " ")
        if content:
            print(f"{pad}    {content[:400]}{'…' if len(content) > 400 else ''}")
        if k.get("subkeys"):
            print_keys(k["subkeys"], kos, depth + 1)


def cmd_schema(args: argparse.Namespace) -> int:
    ensure_schema(update=args.update)
    if args.search:
        needle = args.search.lower()
        for ptype, files in sorted(schema_index().items()):
            for f in files:
                doc = load(f)
                hay = " ".join([ptype, f.stem, doc.get("title") or "", doc.get("description") or ""]).lower()
                if needle in hay:
                    o = macos(doc.get("payload"))
                    tag = "" if not is_na(o) else "  (not on macOS)"
                    print(f"{ptype}\t{doc.get('title')}{tag}")
        return 0
    if not args.payload_type:
        print("give a PayloadType, or --search <text>", file=sys.stderr)
        return 2
    if args.payload_type in ("TopLevel", "CommonPayloadKeys"):
        files = [SCHEMA_DIR / "mdm" / "profiles" / f"{args.payload_type}.yaml"]
    else:
        files = schema_index().get(args.payload_type, [])
    if not files:
        print(f"no Apple schema for PayloadType {args.payload_type!r} at {schema_revision()}.")
        print("A custom preference domain (an app's bundle ID) has no Apple schema: the vendor's own")
        print("documentation is the source. Try `schema --search <word>` for Apple payloads.")
        return 1
    for f in files:
        doc = load(f)
        pos = macos(doc.get("payload"))
        print(f"# {doc.get('title')} — {args.payload_type}")
        print(f"schema: {f.relative_to(SCHEMA_DIR)} @ {schema_revision()}")
        print(f"macOS: {fmt_os(pos)}")
        if args.payload_type in EXTENDS:
            print(f"Also carries every key of {EXTENDS[args.payload_type]} (Apple's note); run `schema {EXTENDS[args.payload_type]}`.")
        notes = schema_notes(doc)
        if notes:
            print("\nNotes:\n" + notes.strip())
        print("\nKeys (CommonPayloadKeys also apply: PayloadIdentifier, PayloadUUID, PayloadType, PayloadVersion, …):")
        print_keys(doc.get("payloadkeys") or [], pos)
        print()
    return 0


# ---------------------------------------------------------------- build


def resolve_value(value, uuids: dict[str, str], base: Path):
    if isinstance(value, dict):
        if set(value) == {"$data"}:
            return base64.b64decode(value["$data"])
        if set(value) == {"$data_file"}:
            return (base / value["$data_file"]).read_bytes()
        if set(value) == {"$date"}:
            return dt.datetime.fromisoformat(value["$date"].replace("Z", "+00:00")).replace(tzinfo=None)
        if set(value) == {"$real"}:
            return float(value["$real"])
        if set(value) == {"$uuid"}:
            if value["$uuid"] not in uuids:
                raise SystemExit(f"$uuid refers to unknown payload id {value['$uuid']!r}")
            return uuids[value["$uuid"]]
        return {k: resolve_value(v, uuids, base) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_value(v, uuids, base) for v in value]
    return value


def installed_uuids(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    prof = read_profile(path)
    found = {prof.get("PayloadIdentifier"): prof.get("PayloadUUID")}
    for p in prof.get("PayloadContent") or []:
        found[p.get("PayloadIdentifier")] = p.get("PayloadUUID")
    return {k: v for k, v in found.items() if k and v}


def cmd_build(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text())
    base = spec_path.parent
    keep = installed_uuids(Path(args.keep_uuids_from) if args.keep_uuids_from else None)

    def uuid_for(identifier: str) -> str:
        return keep.get(identifier) or stable_uuid(identifier)

    ident = spec["identifier"]
    payload_ids: dict[str, str] = {}
    uuids: dict[str, str] = {}
    for p in spec["payloads"]:
        pid = p.get("id") or p["type"].split(".")[-1]
        if pid in payload_ids:
            raise SystemExit(f"two payloads share id {pid!r}; give each an explicit distinct `id`")
        payload_ids[pid] = f"{ident}.{pid}"
        uuids[pid] = uuid_for(payload_ids[pid])

    content = []
    for p in spec["payloads"]:
        pid = p.get("id") or p["type"].split(".")[-1]
        d = resolve_value(p.get("settings") or {}, uuids, base)
        d.update({
            "PayloadType": p["type"],
            "PayloadIdentifier": payload_ids[pid],
            "PayloadUUID": uuids[pid],
            "PayloadVersion": 1,
        })
        if p.get("display_name"):
            d["PayloadDisplayName"] = p["display_name"]
        content.append(d)

    profile = {
        "PayloadContent": content,
        "PayloadDisplayName": spec["display_name"],
        "PayloadIdentifier": ident,
        "PayloadScope": spec.get("scope", "System"),
        "PayloadType": "Configuration",
        "PayloadUUID": uuid_for(ident),
        "PayloadVersion": 1,
        "TargetDeviceType": 5,
    }
    for src, dst in (("description", "PayloadDescription"), ("organization", "PayloadOrganization")):
        if spec.get(src):
            profile[dst] = spec[src]
    if "removal_disallowed" in spec:
        profile["PayloadRemovalDisallowed"] = bool(spec["removal_disallowed"])
    for k, v in (spec.get("extra_top_level") or {}).items():
        profile[k] = resolve_value(v, uuids, base)

    out = Path(args.output)
    out.write_bytes(plistlib.dumps(profile, fmt=plistlib.FMT_XML, sort_keys=True))
    print(f"wrote {out}")
    return lint_file(out)


# ---------------------------------------------------------------- lint


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, level: str, where: str, msg: str) -> None:
        self.rows.append((level, where, msg))

    def error(self, where: str, msg: str) -> None:
        self.add("ERROR", where, msg)

    def warn(self, where: str, msg: str) -> None:
        self.add("WARN", where, msg)

    def info(self, where: str, msg: str) -> None:
        self.add("INFO", where, msg)


def read_profile(path: Path) -> dict:
    raw = path.read_bytes()
    if not raw.lstrip().startswith(b"<?xml") and not raw.startswith(b"bplist"):
        # `-noverify` skips chain trust only; the signature over the content is still checked.
        # security(1) cms -D would try to import the signer into a keychain and fail unprivileged.
        out = subprocess.run(
            ["openssl", "cms", "-verify", "-noverify", "-inform", "DER", "-in", str(path)], capture_output=True
        )
        if out.returncode != 0:
            raise ValueError(f"neither an XML plist nor a CMS SignedData openssl can verify: {out.stderr.decode().strip()}")
        raw = out.stdout
    return plistlib.loads(raw)


def type_ok(value, stype: str) -> bool:
    if stype in ("<any>", None):
        return True
    want = TYPES.get(stype)
    if not want:
        return True
    if stype in ("<integer>", "<real>") and isinstance(value, bool):
        return False
    return isinstance(value, want)


def looks_placeholder(value) -> bool:
    return isinstance(value, str) and "REPLACE" in value.upper()


def version_tuple(v) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (0,)


MIN_MACOS = "14.0"


def check_value(value, spec: dict, where: str, os_ctx: dict, r: Report) -> None:
    kos = macos(spec, os_ctx)
    own = ((spec.get("supportedOS") or {}).get("macOS") or {})
    name = spec["key"]
    if is_na(kos):
        # Reported once, where it starts; a payload that is n/a is reported on the payload.
        if not is_na(os_ctx):
            r.error(where, f"`{name}` is not available on macOS (introduced: n/a)")
        return
    # Deprecation inherited from the payload is reported once, on the payload.
    if own.get("removed"):
        r.error(where, f"`{name}` was removed in macOS {own['removed']}")
    elif own.get("deprecated"):
        r.warn(where, f"`{name}` is deprecated since macOS {own['deprecated']}")
    if own.get("introduced") and not is_na(own) and version_tuple(own["introduced"]) > version_tuple(MIN_MACOS):
        r.warn(where, f"`{name}` needs macOS {own['introduced']}+; ignored on older Macs (fleet floor assumed {MIN_MACOS}, see --min-macos)")
    if own.get("requiresdep"):
        r.warn(where, f"`{name}` works only on ADE (DEP) enrolled Macs")
    if own.get("allowmanualinstall") is False:
        r.warn(where, f"`{name}` is refused in a manually installed profile")
    if own.get("userapprovedmdm"):
        r.warn(where, f"`{name}` needs user-approved MDM")
    stype = spec.get("type")
    if not type_ok(value, stype):
        r.error(where, f"`{name}` must be {stype}, got {type(value).__name__}")
        return
    if "rangelist" in spec and not isinstance(value, (list, dict)) and value not in spec["rangelist"]:
        r.error(where, f"`{name}` = {value!r} is not one of {spec['rangelist']}")
    rng = spec.get("range") or {}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "min" in rng and value < rng["min"]:
            r.error(where, f"`{name}` = {value} is below the schema minimum {rng['min']}")
        if "max" in rng and value > rng["max"]:
            r.warn(where, f"`{name}` = {value} is above the schema maximum {rng['max']} (check the key's prose; Apple is sometimes inconsistent)")
    if isinstance(value, str) and spec.get("format"):
        try:
            if not re.fullmatch(spec["format"], value) and not looks_placeholder(value):
                r.error(where, f"`{name}` = {value!r} does not match format {spec['format']}")
        except re.error:
            pass
    subkeys = spec.get("subkeys") or []
    if isinstance(value, dict) and subkeys:
        check_dict(value, subkeys, where + "." + name, kos, r)
    elif isinstance(value, list) and subkeys:
        item = subkeys[0]
        for i, v in enumerate(value):
            check_value(v, item, f"{where}.{name}[{i}]", kos, r)


def check_dict(d: dict, keyspecs: list[dict], where: str, os_ctx: dict, r: Report, extra_known: set[str] = frozenset()) -> None:
    by_name = {k["key"]: k for k in keyspecs}
    any_spec = by_name.get("ANY")
    for k in keyspecs:
        if k["key"] == "ANY" or k.get("presence") != "required" or k["key"] in d:
            continue
        if is_na(macos(k, os_ctx)):
            continue
        r.error(where, f"required key `{k['key']}` is missing")
    for key, value in d.items():
        if key in extra_known:
            continue
        spec = by_name.get(key) or any_spec
        if spec is None:
            r.warn(where, f"`{key}` is not in Apple's schema for this payload (typo, or an undocumented key)")
            continue
        check_value(value, spec if spec is not any_spec else {**spec, "key": key}, where, os_ctx, r)


def walk_strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]")
    else:
        yield path, obj


def lint_profile(prof: dict, r: Report) -> None:
    ensure_schema()
    root = SCHEMA_DIR / "mdm" / "profiles"
    top = load(root / "TopLevel.yaml")
    common = load(root / "CommonPayloadKeys.yaml")
    common_names = {k["key"] for k in common["payloadkeys"]}

    top_keys = [k for k in top["payloadkeys"] if k["key"] != "PayloadContent"]
    check_dict({k: v for k, v in prof.items() if k != "PayloadContent"}, top_keys, "profile", macos(top.get("payload")), r)
    if "PayloadContent" not in prof and "EncryptedPayloadContent" not in prof:
        r.error("profile", "required key `PayloadContent` is missing")
    if not isinstance(prof.get("PayloadContent", []), list):
        r.error("profile", "`PayloadContent` must be an array of payload dictionaries")
        return
    if prof.get("PayloadType") != "Configuration":
        r.error("profile", "top-level `PayloadType` must be `Configuration`")
    scope = prof.get("PayloadScope")
    if scope is None:
        r.warn("profile", "`PayloadScope` is absent; the current schema states no default (legacy docs say `User`). Emit it explicitly")
    if prof.get("TargetDeviceType") not in (5, None):
        r.warn("profile", f"`TargetDeviceType` = {prof.get('TargetDeviceType')}; 5 is Mac")
    elif prof.get("TargetDeviceType") is None:
        r.info("profile", "no `TargetDeviceType`; 5 (Mac) guards against installation on the wrong platform")
    for key, why in (
        ("ConsentText", "forces an agreement dialog before installation"),
        ("RemovalDate", "the profile removes itself on that date, silently dropping enforcement"),
        ("DurationUntilRemoval", "the profile removes itself after that many seconds"),
        ("PayloadExpirationDate", "the system shows an update prompt after that date"),
    ):
        if key in prof:
            r.warn("profile", f"`{key}` is set: {why}")

    top_id = prof.get("PayloadIdentifier", "")
    all_uuids: dict[str, str] = {}
    seen_ids: set[str] = set()
    if isinstance(prof.get("PayloadUUID"), str):
        all_uuids[prof["PayloadUUID"].upper()] = "profile"
        if UUID_RE.match(prof["PayloadUUID"]) and prof["PayloadUUID"].upper() != stable_uuid(top_id):
            r.info("profile", "top-level PayloadUUID is not uuid5(DNS, PayloadIdentifier); harmless (Apple: content unimportant)")

    single_seen: dict[str, int] = {}
    payloads = prof.get("PayloadContent") or []
    for i, p in enumerate(payloads):
        if not isinstance(p, dict):
            r.error(f"payload[{i}]", "each PayloadContent item must be a dictionary")
            continue
        ptype = p.get("PayloadType", "?")
        where = f"payload[{i}] {ptype}"
        pid, puuid = p.get("PayloadIdentifier"), p.get("PayloadUUID")
        for key in ("PayloadIdentifier", "PayloadUUID", "PayloadType", "PayloadVersion"):
            if key not in p:
                r.error(where, f"required key `{key}` is missing")
        if pid:
            if pid in seen_ids:
                r.error(where, f"PayloadIdentifier {pid!r} repeats; it must be unique within the profile")
            if pid == top_id:
                r.error(where, "payload PayloadIdentifier equals the profile's; append a component")
            seen_ids.add(pid)
        if isinstance(puuid, str):
            if not UUID_RE.match(puuid):
                r.error(where, f"PayloadUUID {puuid!r} is not a UUID")
            elif puuid.upper() in all_uuids:
                r.error(where, f"PayloadUUID {puuid} repeats ({all_uuids[puuid.upper()]}); it must be globally unique")
            else:
                all_uuids[puuid.upper()] = where
                if pid and puuid.upper() != stable_uuid(pid):
                    r.info(where, "PayloadUUID is not uuid5(DNS, PayloadIdentifier). Fine if it is the UUID already installed on Macs — never change it then; otherwise derive it with `uuid`")
        if p.get("PayloadVersion") not in (1, None):
            r.error(where, "PayloadVersion must be 1")

        docs = payload_schemas(ptype)
        if not docs:
            r.warn(where, "no Apple schema for this PayloadType: a custom preference domain whose keys come from the vendor's docs only; no key is checked")
            continue
        doc = docs[0]
        if len(docs) > 1:
            # Several schema variants share this PayloadType; judge against the one that fits best.
            def score(d: dict) -> int:
                trial = Report()
                check_dict({k: v for k, v in p.items() if k not in common_names}, d.get("payloadkeys") or [], where, macos(d.get("payload")), trial)
                return sum(1 for lvl, *_ in trial.rows if lvl in ("ERROR", "WARN"))
            doc = min(docs, key=score)
            r.info(where, f"{len(docs)} schema variants share this PayloadType; checked against “{doc.get('title')}”")
        pos = macos(doc.get("payload"))
        if is_na(pos):
            r.error(where, "this payload is not available on macOS")
        if pos.get("removed"):
            r.error(where, f"payload removed in macOS {pos['removed']}")
        elif pos.get("deprecated"):
            r.warn(where, f"payload deprecated since macOS {pos['deprecated']}")
        if pos.get("multiple") is False:
            single_seen[ptype] = single_seen.get(ptype, 0) + 1
            if single_seen[ptype] == 2:
                r.error(where, "`multiple: false`: at most one such payload per device; this profile has two")
            elif single_seen[ptype] == 1:
                r.info(where, "`multiple: false`: no other profile on the same Mac may carry this payload type")
        gates = []
        if pos.get("userapprovedmdm"):
            gates.append("user-approved MDM")
        if pos.get("supervised"):
            gates.append("supervision")
        if pos.get("requiresdep"):
            gates.append("ADE (DEP) enrollment")
        if pos.get("allowmanualinstall") is False:
            gates.append("MDM delivery (manual install refused)")
        if gates:
            r.warn(where, "requires " + ", ".join(gates))
        if pos.get("devicechannel") is False and scope == "System":
            r.warn(where, "user channel only, but the profile is System-scoped")
        if pos.get("userchannel") is False and scope == "User":
            r.warn(where, "device channel only, but the profile is User-scoped")
        notes = schema_notes(doc).lower()
        if re.search(r"system[- ]scoped", notes):
            if scope == "User":
                r.error(where, "Apple: this payload must be in a System-scoped profile, and PayloadScope is User")
            elif scope is None:
                r.warn(where, "Apple: this payload must be in a System-scoped profile; set PayloadScope: System")

        own_names = {k["key"] for k in doc.get("payloadkeys") or []}
        check_dict(
            {k: v for k, v in p.items() if k not in common_names or k in own_names},
            doc.get("payloadkeys") or [], where, pos, r,
        )

    # cross-references and credentials, once every PayloadUUID is known
    for i, p in enumerate(payloads):
        if not isinstance(p, dict):
            continue
        where = f"payload[{i}] {p.get('PayloadType', '?')}"
        for path, value in walk_strings({k: v for k, v in p.items() if k != "PayloadUUID"}):
            leaf = re.sub(r"\[\d+\]$", "", path).split(".")[-1]
            if CERT_REF_RE.search(leaf) and isinstance(value, str) and UUID_RE.match(value):
                if value.upper() not in all_uuids:
                    r.error(where, f"`{path}` = {value} names no PayloadUUID in this profile; certificate references resolve within one profile only")
            if leaf in SECRET_KEYS and isinstance(value, str) and value:
                if looks_placeholder(value):
                    r.info(where, f"`{path}` holds a placeholder: fill it at render time, never commit the real value")
                else:
                    r.warn(where, f"`{path}` holds a credential in plaintext; anyone with the file reads it")
            elif looks_placeholder(value):
                r.info(where, f"`{path}` holds a placeholder; the profile installs but does nothing useful until it is filled")
        if p.get("PayloadType") == "com.apple.security.pkcs12" and p.get("PayloadContent"):
            r.warn(where, "PKCS #12 carries a private key; the file is a secret")
        eap = p.get("EAPClientConfiguration")
        if isinstance(eap, dict) and 13 in (eap.get("AcceptEAPTypes") or []) and not p.get("PayloadCertificateUUID"):
            r.warn(where, "EAP-TLS with no PayloadCertificateUUID: the client identity must be a payload in this same profile (Apple: 'within the same profile'); an identity from another profile is undocumented")


def lint_file(path: Path) -> int:
    r = Report()
    lint_out = subprocess.run(["plutil", "-lint", str(path)], capture_output=True, text=True)
    raw = path.read_bytes()
    if raw.lstrip().startswith(b"<?xml") and lint_out.returncode != 0:
        print(lint_out.stdout.strip() or lint_out.stderr.strip())
        return 1
    try:
        prof = read_profile(path)
    except Exception as e:  # noqa: BLE001 — report any parse failure as the lint result
        print(f"{path}: ERROR cannot read: {e}")
        return 1
    if raw.startswith(b"bplist"):
        r.warn("file", "binary plist: Apple documents profiles only as XML plists; MicroMDM's store refuses them")
    elif not raw.lstrip().startswith(b"<?xml"):
        r.warn("file", "CMS-signed profile (signature over content verified, signer trust not checked). MDM InstallProfile does not need a signature; a server that reads PayloadIdentifier from the XML cannot read it here")
    lint_profile(prof, r)
    errors = sum(1 for lvl, *_ in r.rows if lvl == "ERROR")
    warns = sum(1 for lvl, *_ in r.rows if lvl == "WARN")
    print(f"{path}  (schema {schema_revision()})")
    for lvl, where, msg in sorted(r.rows, key=lambda x: ("ERROR", "WARN", "INFO").index(x[0])):
        print(f"  {lvl:5} {where}: {msg}")
    print(f"  => {errors} error(s), {warns} warning(s)")
    return 1 if errors else 0


def cmd_lint(args: argparse.Namespace) -> int:
    return max(lint_file(Path(f)) for f in args.files)


def cmd_uuid(args: argparse.Namespace) -> int:
    for ident in args.identifiers:
        print(f"{stable_uuid(ident)}\t{ident}")
    return 0


def main() -> int:
    global MIN_MACOS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-macos", default=MIN_MACOS, help=f"oldest macOS the fleet runs (default {MIN_MACOS})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("schema")
    s.add_argument("payload_type", nargs="?")
    s.add_argument("--search")
    s.add_argument("--update", action="store_true", help="git pull the schema clone first")
    s.set_defaults(fn=cmd_schema)
    u = sub.add_parser("uuid")
    u.add_argument("identifiers", nargs="+")
    u.set_defaults(fn=cmd_uuid)
    b = sub.add_parser("build")
    b.add_argument("spec")
    b.add_argument("-o", "--output", required=True)
    b.add_argument("--keep-uuids-from", help="an already-deployed version; its UUIDs win for matching identifiers")
    b.set_defaults(fn=cmd_build)
    li = sub.add_parser("lint")
    li.add_argument("files", nargs="+")
    li.set_defaults(fn=cmd_lint)
    args = ap.parse_args()
    MIN_MACOS = args.min_macos
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
