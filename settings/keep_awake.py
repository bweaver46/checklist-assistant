"""
Keeps the Mac awake for the duration of an extraction run, so a long
multi-hundred-page pull doesn't get interrupted by the machine going
to sleep partway through (Brandon, 2026-08-07).

This file was referenced by app/extraction_worker.py's import but
never actually committed - it only worked because a local, untracked
copy happened to still be sitting on disk. Reconstructed here from
that usage (start_keep_awake() with no args, returning a handle;
stop_keep_awake(handle) in a finally block) - confirmed 2026-08-10
after Brandon's git status showed it as untracked post-pull.

Uses macOS's built-in `caffeinate` command-line tool rather than a
third-party package - no extra dependency, and it's already on every
Mac. Silently does nothing on any other OS (`caffeinate` doesn't
exist there) rather than failing the whole extraction over a
nice-to-have.
"""

from __future__ import annotations

import subprocess
import sys


def start_keep_awake() -> subprocess.Popen | None:
    """Starts `caffeinate -i` (prevent idle sleep) for as long as the
    returned process stays alive. Returns None on non-macOS platforms,
    or if caffeinate isn't available for any reason - callers should
    treat None as "nothing to clean up" and pass it straight through
    to stop_keep_awake() without checking."""
    if sys.platform != "darwin":
        return None
    try:
        return subprocess.Popen(
            ["caffeinate", "-i"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, FileNotFoundError):
        return None


def stop_keep_awake(process: subprocess.Popen | None) -> None:
    """Stops a process started by start_keep_awake(). Safe to call with
    None (nothing was started, e.g. non-macOS)."""
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
