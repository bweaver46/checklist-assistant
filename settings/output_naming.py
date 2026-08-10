"""
Output naming

Turns the user-provided export name (e.g. "2026 Topps Chrome Baseball")
into safe, unique filenames for the raw and final CSV exports.

Added because the app used to always write to the same hardcoded
raw_export.csv / checklist_export.csv, silently overwriting a previous
set's work if Brandon started a new extraction before saving/renaming
those files elsewhere.

Exports also used to default to directory="." (the app's own current
working directory), which meant they landed wherever the process
happened to be launched from - in practice, straight into the source
code folder itself, mixed in with app/exporter/scraper/settings.
Fixed (Brandon, 2026-08-07) to always write to one predictable folder
instead: DEFAULT_EXPORT_DIR below.
"""

from __future__ import annotations

import os
import re

RAW_SUFFIX = "_raw_export.csv"
FINAL_SUFFIX = "_checklist_export.csv"
DEFAULT_NAME = "checklist"

# Fixed export location so files always land somewhere predictable and
# easy to find/attach from any other app, instead of wherever the
# process's working directory happened to be.
DEFAULT_EXPORT_DIR = os.path.expanduser("~/Collock/checklist")


def _ensure_export_dir(directory: str) -> str:
    os.makedirs(directory, exist_ok=True)
    return directory

_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|]')
_WHITESPACE = re.compile(r"\s+")


def sanitize_output_name(name: str) -> str:
    """Strip characters that are illegal in filenames on macOS/Windows,
    collapse whitespace, and fall back to a generic name if nothing
    usable is left. Never returns an empty string."""
    name = name.strip()
    name = _ILLEGAL_CHARS.sub(" ", name)
    name = _WHITESPACE.sub(" ", name).strip()
    if not name:
        name = DEFAULT_NAME
    return name[:80]


def resolve_unique_output_name(name: str, directory: str = DEFAULT_EXPORT_DIR) -> str:
    """Sanitize the given name, then, if either output file for that
    name already exists in `directory`, append ' (2)', ' (3)', etc.
    until both the raw and final filenames are free.

    This is resolved ONCE per new set (when the name is first entered)
    and the resolved name is then persisted/reused for every subsequent
    page-range chunk of that same set, so continuing a set correctly
    keeps rebuilding the same two files rather than creating a new pair
    every chunk.
    """
    directory = _ensure_export_dir(directory)
    base = sanitize_output_name(name)
    candidate = base
    i = 2
    while (
        os.path.exists(os.path.join(directory, candidate + RAW_SUFFIX))
        or os.path.exists(os.path.join(directory, candidate + FINAL_SUFFIX))
    ):
        candidate = f"{base} ({i})"
        i += 1
    return candidate


def raw_export_path(name: str, directory: str = DEFAULT_EXPORT_DIR) -> str:
    directory = _ensure_export_dir(directory)
    return os.path.abspath(os.path.join(directory, name + RAW_SUFFIX))


def final_export_path(name: str, directory: str = DEFAULT_EXPORT_DIR) -> str:
    directory = _ensure_export_dir(directory)
    return os.path.abspath(os.path.join(directory, name + FINAL_SUFFIX))
