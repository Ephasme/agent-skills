"""The com.loup.realm LaunchAgent that runs `realm.py tick`."""

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from .daemon import TICK_SECONDS
from .state import HOME, LOG_FILE, log

LABEL = "com.loup.realm"
PLIST = HOME / "Library/LaunchAgents" / f"{LABEL}.plist"
# The entry point launchd runs: realm.py beside this package.
ENTRY = Path(__file__).resolve().parent.parent / "realm.py"


def cmd_install(_a):
    herdr = shutil.which("herdr")
    if not herdr:
        sys.exit("realm install: herdr not on PATH")
    # Unresolved on purpose: the Homebrew symlink survives Python upgrades, the Cellar path does not.
    python = shutil.which("python3") or sys.executable
    script = str(ENTRY)
    # PATH covers the shell commands mcp.json headers run (sops, …): launchd starts with a bare PATH.
    path_dirs = [os.path.dirname(herdr), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    env = {
        "PATH": ":".join(dict.fromkeys(path_dirs)),
        "HOME": str(HOME),
        "REALM_HERDR": herdr,
        "REALM_LAUNCHD": "1",
    }
    if os.environ.get("HERDR_SOCKET_PATH"):
        env["HERDR_SOCKET_PATH"] = os.environ["HERDR_SOCKET_PATH"]
    plist = {
        "Label": LABEL,
        "ProgramArguments": [python, script, "tick"],
        "StartInterval": TICK_SECONDS,
        "RunAtLoad": True,
        "EnvironmentVariables": env,
        "StandardOutPath": str(LOG_FILE),
        "StandardErrorPath": str(LOG_FILE),
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)
    with PLIST.open("wb") as f:
        plistlib.dump(plist, f)
    subprocess.run(["launchctl", "bootstrap", domain, str(PLIST)], check=True)
    log(f"installed {PLIST} (python={python}, herdr={herdr})")


def cmd_uninstall(_a):
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
    PLIST.unlink(missing_ok=True)
    log(f"uninstalled {PLIST}")
