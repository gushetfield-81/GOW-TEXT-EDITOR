"""Headless regression for R7's WYSIWYG text-color interaction.

R7 deliberately paints the glyphs in the editable QPlainTextEdit rather than
showing a detached table underneath it.  These tests never save a WAD: they
only exercise the in-memory, field-sized FLP patches and assert that the input
WAD remains byte-identical.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path

# Must precede Qt import in CI/headless execution.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tool" / "GodOfWarTextEditor_Aprimorado_2026-09-24_R7" / "gow_text_editor.py"
INPUT_DIR = Path(os.environ.get("GOW_COLOR_TEST_INPUT_DIR", ROOT.parent / "uploads"))
PERMA = INPUT_DIR / "R_PERMA.WAD.txt"

try:
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication
except ImportError:
    QColor = None
    QApplication = None


def load_editor():
    spec = importlib.util.spec_from_file_location("gow_text_editor_inline_ui_r7", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EDITOR = load_editor()
CAN_SMOKE = bool(QApplication is not None and EDITOR.QT_AVAILABLE and PERMA.is_file())


def changed_offsets(before: bytes, after: bytes) -> set[int]:
    assert len(before) == len(after)
    return {index for index, (old, new) in enumerate(zip(before, after)) if old != new}


def block_foreground_rgba(editor, block_number: int) -> tuple[int, int, int, int] | None:
    """Read the actual syntax-highlighter format applied to one editor line."""
    block = editor.document().findBlockByNumber(block_number)
    if not block.isValid() or block.layout() is None:
        return None
    for item in block.layout().formats():
        if item.length:
            color = item.format.foreground().color()
            return color.red(), color.green(), color.blue(), color.alpha()
    return None


@unittest.skipUnless(CAN_SMOKE, "PySide6/offscreen support and R_PERMA input are required")
class InlineColorsUiR7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.input_digest = hashlib.sha256(PERMA.read_bytes()).hexdigest()
        self.window = EDITOR.App()
        self.original_box = EDITOR.QMessageBox

        class NoModalMessageBox:
            Yes = self.original_box.Yes
            No = self.original_box.No

            @staticmethod
            def critical(*args):
                raise AssertionError("Qt critical dialog: " + str(args[-1]))

            @staticmethod
            def warning(*args):
                raise AssertionError("Qt warning dialog: " + str(args[-1]))

            @staticmethod
            def information(*_args):
                return None

            @staticmethod
            def question(*_args):
                # The test has already reset its in-memory snapshot in
                # tearDown; returning Yes is a defensive headless fallback.
                return self.original_box.Yes

        EDITOR.QMessageBox = NoModalMessageBox
        self.assertTrue(self.window.load_wad_path(str(PERMA)))
        self.qt_app.processEvents()

    def tearDown(self):
        try:
            # Tests intentionally alter only memory. Avoid an unsaved-work
            # prompt while tearing the offscreen QWidget down.
            if self.window.wad is not None:
                self.window._open_snapshot = {id(tag): tag.data for tag in self.window.wad.tags}
            self.window.dirty = False
            self.window.close()
            self.window.deleteLater()
        finally:
            EDITOR.QMessageBox = self.original_box
        self.assertEqual(hashlib.sha256(PERMA.read_bytes()).hexdigest(), self.input_digest)

    def test_msgs_txt_glyphs_follow_cursor_template_and_selected_physical_instance(self):
        window = self.window
        self.assertEqual(window.active_tag.upper_name, "MSGS_TXT")
        # The former R6 table is no longer a visual control. The direct editor
        # owns both rendering and color selection in R7.
        self.assertFalse(hasattr(window, "inline_colors_table"))
        self.assertTrue(window.editor_color_selector.isEnabled())
        self.assertTrue(window.editor_color_button.isEnabled())

        # First loaded MSGS line is template Line1 / DynamicLabel 1.
        self.assertEqual(window.editor_color_highlighter._line_colors, {0: (100, 75, 40, 255)})
        self.assertEqual(block_foreground_rgba(window.editor, 0), (100, 75, 40, 255))
        self.assertEqual(
            {item["field"]["dynamic_index"] for item in window._editor_color_fields}, {1, 36}
        )

        # Page separators reset the runtime template count. The separator is
        # deliberately unpainted and the first line after it returns to Line1.
        paged_text = "primeira\nsegunda\n--\nnova página"
        window.editor.setPlainText(paged_text)
        cursor = window.editor.textCursor()
        cursor.setPosition(paged_text.index("nova página"))
        window.editor.setTextCursor(cursor)
        self.qt_app.processEvents()
        self.assertEqual(window.editor_color_highlighter._line_colors, {
            0: (100, 75, 40, 255),
            1: (100, 75, 40, 255),
            3: (100, 75, 40, 255),
        })
        self.assertEqual(
            {item["field"]["dynamic_index"] for item in window._editor_color_fields}, {1, 36}
        )

        # The cursor's second page-line must resolve to Line2 and paint both
        # visible lines. This also covers the no-recursion behavior when a
        # highlighter refresh follows a normal text edit.
        visible_text = "linha um\nlinha dois"
        window.editor.setPlainText(visible_text)
        cursor = window.editor.textCursor()
        cursor.setPosition(len("linha um\n"))
        window.editor.setTextCursor(cursor)
        self.qt_app.processEvents()
        self.assertEqual(window.editor.toPlainText(), visible_text)
        self.assertEqual(window.editor_color_highlighter._line_colors, {
            0: (100, 75, 40, 255),
            1: (100, 75, 40, 255),
        })
        self.assertEqual(block_foreground_rgba(window.editor, 0), (100, 75, 40, 255))
        self.assertEqual(block_foreground_rgba(window.editor, 1), (100, 75, 40, 255))
        self.assertEqual(
            {item["field"]["dynamic_index"] for item in window._editor_color_fields}, {2, 37}
        )

        # DynamicLabel 37 is a distinct physical state of Line2. Selecting it
        # changes the glyph paint in-place, not via an external color table.
        selected_index = next(
            index for index, choice in enumerate(window._editor_color_fields)
            if choice["field"]["dynamic_index"] == 37
        )
        window.editor_color_selector.setCurrentIndex(selected_index)
        self.qt_app.processEvents()
        selected = window._choice_for_editor_token(window._editor_color_active_token)
        self.assertIsNotNone(selected)
        self.assertEqual(selected["field"]["dynamic_index"], 37)
        self.assertEqual(block_foreground_rgba(window.editor, 1), (255, 255, 255, 255))
        self.assertEqual(window.editor.toPlainText(), visible_text)

        # Editing through the color button changes exactly that DynamicLabel's
        # BGRA field and leaves the current message text as plain text.
        field, tag = selected["field"], selected["tag"]
        before = bytes(tag.data)
        original_dialog = EDITOR.QColorDialog

        class FixedColorDialog:
            ColorDialogOption = original_dialog.ColorDialogOption
            ShowAlphaChannel = original_dialog.ShowAlphaChannel

            @staticmethod
            def getColor(*_args, **_kwargs):
                return QColor(0x12, 0x34, 0x56, 0x78)

        EDITOR.QColorDialog = FixedColorDialog
        try:
            window._edit_editor_color_field()
        finally:
            EDITOR.QColorDialog = original_dialog
        self.assertEqual(
            changed_offsets(before, tag.data), set(range(field["offset"], field["offset"] + 4))
        )
        self.assertEqual(block_foreground_rgba(window.editor, 1), (0x12, 0x34, 0x56, 0x78))
        self.assertEqual(window.editor.toPlainText(), visible_text)

    def test_gow2_staticlabel_uses_its_direct_rendercommand_in_the_same_editor(self):
        window = self.window
        flp_index = next(
            index for index, (tag, _movie) in enumerate(window.main_flp_resources)
            if tag.name == "FLP_HUDA"
        )
        window.load_flp_resource(flp_index)
        self.qt_app.processEvents()

        self.assertEqual(window.active_tag.name, "FLP_HUDA")
        self.assertTrue(window._is_main_flp_mode())
        self.assertEqual(window.editor.toPlainText(), "/10")
        self.assertEqual(window.editor_color_highlighter._line_colors, {0: (255, 255, 255, 255)})
        self.assertEqual(block_foreground_rgba(window.editor, 0), (255, 255, 255, 255))
        self.assertEqual(len(window._editor_color_fields), 1)
        selected = window._editor_color_fields[0]
        self.assertEqual(selected["field_kind"], "static")
        self.assertEqual(selected["field"]["block_index"], 0)

        field, tag = selected["field"], selected["tag"]
        before = bytes(tag.data)
        original_text = window.editor.toPlainText()
        original_dialog = EDITOR.QColorDialog

        class FixedColorDialog:
            ColorDialogOption = original_dialog.ColorDialogOption
            ShowAlphaChannel = original_dialog.ShowAlphaChannel

            @staticmethod
            def getColor(*_args, **_kwargs):
                return QColor(1, 2, 3, 4)

        EDITOR.QColorDialog = FixedColorDialog
        try:
            window._edit_editor_color_field()
        finally:
            EDITOR.QColorDialog = original_dialog
        self.assertEqual(
            changed_offsets(before, tag.data), set(range(field["offset"], field["offset"] + 4))
        )
        self.assertEqual(block_foreground_rgba(window.editor, 0), (1, 2, 3, 4))
        self.assertEqual(window.editor.toPlainText(), original_text)


if __name__ == "__main__":
    unittest.main()
