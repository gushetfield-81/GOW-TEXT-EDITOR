"""Optional Qt smoke regression for the R6 inline text-color panel.

The test is skipped when PySide6 or the private real WAD inputs are absent.
It never saves a WAD: the inline edit is checked only against bytes in memory.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path

# Must be defined before importing Qt in a CI/headless environment.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tool" / "GodOfWarTextEditor_Aprimorado_2026-09-24_R6" / "gow_text_editor.py"
INPUT_DIR = Path(os.environ.get("GOW_COLOR_TEST_INPUT_DIR", ROOT.parent / "uploads"))
PERMA = INPUT_DIR / "R_PERMA.WAD.txt"

try:
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication
except ImportError:
    QColor = None
    QApplication = None


def load_editor():
    spec = importlib.util.spec_from_file_location("gow_text_editor_inline_ui_r6", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EDITOR = load_editor()
CAN_SMOKE = bool(QApplication is not None and EDITOR.QT_AVAILABLE and PERMA.is_file())


@unittest.skipUnless(CAN_SMOKE, "PySide6/offscreen support and R_PERMA input are required")
class InlineColorsUiR6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_msgs_txt_panel_maps_template_and_edits_only_target_dynamic_field(self):
        original_digest = hashlib.sha256(PERMA.read_bytes()).hexdigest()
        window = EDITOR.App()
        # Do not allow an unexpected UI error to block a headless regression.
        class NoModalMessageBox:
            @staticmethod
            def critical(*args):
                raise AssertionError("Qt critical dialog: " + str(args[-1]))

            @staticmethod
            def warning(*args):
                raise AssertionError("Qt warning dialog: " + str(args[-1]))

            @staticmethod
            def information(*_args):
                return None

        original_box = EDITOR.QMessageBox
        original_dialog = EDITOR.QColorDialog
        EDITOR.QMessageBox = NoModalMessageBox
        try:
            self.assertTrue(window.load_wad_path(str(PERMA)))
            self.qt_app.processEvents()
            self.assertEqual(window.active_tag.upper_name, "MSGS_TXT")
            self.assertGreater(window.inline_colors_table.rowCount(), 0)
            self.assertTrue(any(item["field_kind"] == "dynamic"
                                for item in window._inline_color_entries.values()))
            self.assertTrue(any(item["field_kind"] == "blend"
                                for item in window._inline_color_entries.values()))

            # The cursor is part of the association: line 2 of a MSGS page is
            # sent by DoMsgPage to MessageTemplate_Line2, not Line1.
            original_editor_text = window.editor.toPlainText()
            window.editor.setPlainText("linha um\nlinha dois")
            cursor = window.editor.textCursor()
            cursor.setPosition(len("linha um\n"))
            window.editor.setTextCursor(cursor)
            self.qt_app.processEvents()
            line2_dynamic_ids = {
                item["field"]["dynamic_index"] for item in window._inline_color_entries.values()
                if item["field_kind"] == "dynamic"
            }
            self.assertEqual(line2_dynamic_ids, {2, 37})
            window.editor.setPlainText(original_editor_text)
            cursor = window.editor.textCursor()
            cursor.setPosition(0)
            window.editor.setTextCursor(cursor)
            self.qt_app.processEvents()

            record = next(item for item in window._inline_color_entries.values()
                          if item["field_kind"] == "dynamic")
            field, tag = record["field"], record["tag"]
            before = bytes(tag.data)

            class FixedColorDialog:
                ColorDialogOption = original_dialog.ColorDialogOption
                ShowAlphaChannel = original_dialog.ShowAlphaChannel

                @staticmethod
                def getColor(*_args, **_kwargs):
                    return QColor(0x12, 0x34, 0x56, 0x78)

            EDITOR.QColorDialog = FixedColorDialog
            window._inline_color_selected = record["token"]
            window._edit_inline_selected_color()
            changed = {i for i, (old, new) in enumerate(zip(before, tag.data)) if old != new}
            self.assertEqual(changed, set(range(field["offset"], field["offset"] + 4)))
            movie = next(movie for candidate, movie in window.main_flp_resources if candidate is tag)
            self.assertEqual(
                movie.dynamic_label_color_fields()[field["dynamic_index"]]["rgba"],
                (0x12, 0x34, 0x56, 0x78),
            )
            # Current MSGS text was never committed/replaced by the FLP patch.
            self.assertEqual(window.editor.toPlainText(), window.resource_messages[window.current_index].text)
        finally:
            EDITOR.QColorDialog = original_dialog
            # Do not invoke the real unsaved-changes question while closing the
            # offscreen window: the test deliberately changed only in-memory
            # FLP bytes. Reset its snapshot solely for orderly Qt teardown.
            if window.wad is not None:
                window._open_snapshot = {id(tag): tag.data for tag in window.wad.tags}
            window.dirty = False
            EDITOR.QMessageBox = original_box
            window.close()
            window.deleteLater()
        self.assertEqual(hashlib.sha256(PERMA.read_bytes()).hexdigest(), original_digest)


if __name__ == "__main__":
    unittest.main()
