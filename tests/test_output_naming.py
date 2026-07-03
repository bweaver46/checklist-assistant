"""
Tests for settings/output_naming.py.

Added alongside the fix for: starting a new extraction used to always
overwrite the previous set's raw_export.csv / checklist_export.csv
because both filenames were hardcoded. Now the user names each export,
and that name is resolved to something that can never collide with an
existing file pair.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from settings.output_naming import (
    sanitize_output_name,
    resolve_unique_output_name,
    raw_export_path,
    final_export_path,
    RAW_SUFFIX,
    FINAL_SUFFIX,
    DEFAULT_NAME,
)


class TestSanitizeOutputName(unittest.TestCase):
    def test_strips_illegal_filename_characters(self):
        self.assertEqual(sanitize_output_name('2026 Topps: Chrome/Prizm?'), "2026 Topps Chrome Prizm")

    def test_collapses_whitespace(self):
        self.assertEqual(sanitize_output_name("2026   Topps    Chrome"), "2026 Topps Chrome")

    def test_blank_input_falls_back_to_default(self):
        self.assertEqual(sanitize_output_name(""), DEFAULT_NAME)
        self.assertEqual(sanitize_output_name("   "), DEFAULT_NAME)

    def test_normal_name_passes_through_unchanged(self):
        self.assertEqual(sanitize_output_name("2026 Bowman Chrome Baseball"), "2026 Bowman Chrome Baseball")


class TestResolveUniqueOutputName(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _touch(self, name: str) -> None:
        open(os.path.join(self.tmpdir, name), "w").close()

    def test_returns_sanitized_name_when_no_collision(self):
        result = resolve_unique_output_name("2026 Topps Chrome", self.tmpdir)
        self.assertEqual(result, "2026 Topps Chrome")

    def test_appends_counter_when_final_export_already_exists(self):
        self._touch("2026 Topps Chrome" + FINAL_SUFFIX)
        result = resolve_unique_output_name("2026 Topps Chrome", self.tmpdir)
        self.assertEqual(result, "2026 Topps Chrome (2)")

    def test_appends_counter_when_raw_export_already_exists(self):
        self._touch("2026 Topps Chrome" + RAW_SUFFIX)
        result = resolve_unique_output_name("2026 Topps Chrome", self.tmpdir)
        self.assertEqual(result, "2026 Topps Chrome (2)")

    def test_keeps_incrementing_past_multiple_collisions(self):
        self._touch("Set A" + FINAL_SUFFIX)
        self._touch("Set A (2)" + FINAL_SUFFIX)
        self._touch("Set A (3)" + RAW_SUFFIX)
        result = resolve_unique_output_name("Set A", self.tmpdir)
        self.assertEqual(result, "Set A (4)")

    def test_blank_name_still_resolves_and_avoids_collision(self):
        self._touch(DEFAULT_NAME + FINAL_SUFFIX)
        result = resolve_unique_output_name("", self.tmpdir)
        self.assertEqual(result, f"{DEFAULT_NAME} (2)")


class TestExportPathHelpers(unittest.TestCase):
    def test_raw_and_final_paths_use_the_same_base_name(self):
        raw = raw_export_path("My Set", "/some/dir")
        final = final_export_path("My Set", "/some/dir")
        self.assertTrue(raw.endswith("My Set" + RAW_SUFFIX))
        self.assertTrue(final.endswith("My Set" + FINAL_SUFFIX))
        self.assertTrue(os.path.isabs(raw))
        self.assertTrue(os.path.isabs(final))


if __name__ == "__main__":
    unittest.main()
