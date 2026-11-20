#!/usr/bin/env python3
"""realm: wake subscribed herdr panes that have unread Agent Mail. Code lives in realmlib/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from realmlib.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
