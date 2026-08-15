"""
Keep-awake (Brandon, 2026-08-07): a full extraction can run long enough
that macOS puts the Mac to sleep partway through, which pauses (or can
outright break) a live Playwright browser session mid-scrape.

Wraps macOS's built-in `caffeinate` command-line tool for the duration
of an extraction run - no extra dependencies, it ships with every Mac.
`-d` keeps the display awake, `-i` prevents idle sleep, `-s` prevents
system sleep while on AC power. Started right before scraping begins,
always stopped in a `finally` block (see app/extraction_worker.py) so
a crash or early return never leaves the Mac stuck awake afterward.

No-ops safely (returns None, stop_keep_awake does nothing) on any
non-macOS system, or if `caffeinate` isn't found - this is a nice-to-
have, not something that should ever break the actual extraction.

(This file was briefly missing from the committed repo - it only
worked because a local, untracked copy stayed on Brandon's machine
from when it was first written. Restored here, 2026-08-10, matching
that original working version - not the interim placeholder guess.)
"""

from __future__ import annotations

import platform
import subprocess


def start_keep_awake() -> subprocess.Popen | None:
    if platform.system() != "Darwin":
        return None
    try:
        return subprocess.Popen(
            ["caffeinate", "-d", "-i", "-s"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, FileNotFoundError):
        return None


def stop_keep_awake(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    try:
        process.terminate()
        process.wait(timeout=3)
    except Exception:
        pass
