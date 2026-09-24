"""Offscreen Qt regression for R8 editor/preview integration."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tool" / "GodOfWarTextEditor_Aprimorado_2026-09-24_R8" / "gow_text_editor.py"
PERMA = ROOT.parent / "uploads" / "R_PERMA.WAD.txt"

try:
    from PySide6.QtGui import QColor, QTextCursor
    from PySide6.QtWidgets import QApplication
except ImportError:
    QColor = QTextCursor = QApplication = None


def load_editor():
    spec = importlib.util.spec_from_file_location("gow_r8_ui", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EDITOR = load_editor()
CAN_RUN = bool(QApplication is not None and EDITOR.QT_AVAILABLE and PERMA.is_file())


def color_at(editor, block_no, position):
    block = editor.document().findBlockByNumber(block_no)
    for item in block.layout().formats():
        if item.start <= position < item.start + item.length:
            color = item.format.foreground().color()
            return color.red(), color.green(), color.blue(), color.alpha()
    return None


@unittest.skipUnless(CAN_RUN, "PySide6/offscreen plus R_PERMA required")
class InlineStylesUiR8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.digest = hashlib.sha256(PERMA.read_bytes()).hexdigest()
        self.window = EDITOR.App()
        self.original_message_box = EDITOR.QMessageBox

        class Box:
            Yes = self.original_message_box.Yes
            No = self.original_message_box.No
            @staticmethod
            def critical(*args):
                raise AssertionError(str(args[-1]))
            @staticmethod
            def warning(*args):
                raise AssertionError(str(args[-1]))
            @staticmethod
            def information(*args):
                return None
            @staticmethod
            def question(*args):
                return Box.Yes
        EDITOR.QMessageBox = Box
        self.assertTrue(self.window.load_wad_path(str(PERMA)))
        self.app.processEvents()

    def tearDown(self):
        try:
            if self.window.current_index is not None:
                self.window.load_message(self.window.current_index)
            if self.window.wad is not None:
                self.window._open_snapshot = {id(tag): tag.data for tag in self.window.wad.tags}
            self.window.dirty = False
            self.window.close()
            self.window.deleteLater()
        finally:
            EDITOR.QMessageBox = self.original_message_box
        self.assertEqual(hashlib.sha256(PERMA.read_bytes()).hexdigest(), self.digest)

    def load_message(self, key):
        index = next(i for i, item in enumerate(self.window.resource_messages) if item.key == key)
        self.window.load_message(index)
        self.app.processEvents()
        return index

    def choose(self, style):
        row = next(i for i in range(self.window.inline_style_selector.count())
                   if self.window.inline_style_selector.itemData(i) == style)
        self.window.inline_style_selector.setCurrentIndex(row)
        self.app.processEvents()

    def test_laminas_wysiwyg_and_preview_keep_raw_marker(self):
        self.load_message("701")
        window = self.window
        line = window.editor.toPlainText().split("\n")[0]
        self.assertEqual(line, "[*1] [IconBlade] LÂMINAS DE ATENA")
        self.assertTrue(window.inline_style_selector.isEnabled())
        self.assertTrue(window.inline_style_palette_button.isEnabled())
        self.assertEqual(window.runtime_inline_palette.colors[1], (127, 40, 5, 255))
        self.assertNotEqual(color_at(window.editor, 0, 0), (127, 40, 5, 255))
        self.assertEqual(color_at(window.editor, 0, line.index("LÂMINAS")), (127, 40, 5, 255))
        self.assertEqual(color_at(window.editor, 3, 0), (100, 75, 40, 255))
        segments = window.preview._runtime_segments_for_line(0, line)
        self.assertEqual("".join(piece for piece, _ in segments), " [IconBlade] LÂMINAS DE ATENA")
        self.assertTrue(all(rgba == (127, 40, 5, 255) for _piece, rgba in segments))

    def test_control_edit_multiline_wrap_and_rgb_patch(self):
        index = self.load_message("701")
        window = self.window
        window.editor.setPlainText("A[IconBlade]B[*2]C")
        cursor = window.editor.textCursor()
        cursor.setPosition(1)
        cursor.setPosition(len("A[IconBlade]B"), QTextCursor.KeepAnchor)
        window.editor.setTextCursor(cursor)
        self.choose(1)
        window._apply_inline_style_control()
        self.assertEqual(window.editor.toPlainText(), "A[*1][IconBlade]B[*0][*2]C")
        cursor = window.editor.textCursor()
        cursor.setPosition(2)
        window.editor.setTextCursor(cursor)
        self.choose(4)
        window._apply_inline_style_control()
        self.assertEqual(window.editor.toPlainText(), "A[*4][IconBlade]B[*0][*2]C")

        window.editor.setPlainText("Aone\ntwo\nthreeB")
        cursor = window.editor.textCursor()
        cursor.setPosition(1)
        cursor.setPosition(12, QTextCursor.KeepAnchor)
        window.editor.setTextCursor(cursor)
        self.choose(4)
        window._apply_inline_style_control()
        self.assertEqual(window.editor.toPlainText(), "A[*4]one[*0]\n[*4]two[*0]\n[*4]thr[*0]eeB")

        window.load_message(index)
        self.choose(1)
        palette = window.runtime_inline_palette
        tag = palette.data_tag
        before = bytes(tag.data)
        offset = palette.field_offset(1)
        original_dialog = EDITOR.QColorDialog
        class Dialog:
            @staticmethod
            def getColor(*args, **kwargs):
                return QColor(0x12, 0x34, 0x56)
        EDITOR.QColorDialog = Dialog
        try:
            window._edit_inline_runtime_palette()
        finally:
            EDITOR.QColorDialog = original_dialog
        self.app.processEvents()
        changed = {i for i, (old, new) in enumerate(zip(before, tag.data)) if old != new}
        self.assertTrue(changed and changed <= set(range(offset, offset + 12)))
        self.assertEqual(window.runtime_inline_palette.colors[1], (0x12, 0x34, 0x56, 255))
        pos = window.editor.toPlainText().split("\n")[0].index("LÂMINAS")
        self.assertEqual(color_at(window.editor, 0, pos), (0x12, 0x34, 0x56, 255))

    def test_r7_base_layers_remain_for_msgs_and_flp(self):
        window = self.window
        self.assertEqual(window.editor_color_highlighter._line_colors, {0: (100, 75, 40, 255)})
        self.assertEqual(color_at(window.editor, 0, 0), (100, 75, 40, 255))
        flp_index = next(i for i, (tag, _movie) in enumerate(window.main_flp_resources) if tag.name == "FLP_HUDA")
        window.load_flp_resource(flp_index)
        self.app.processEvents()
        self.assertEqual(window.editor.toPlainText(), "/10")
        self.assertEqual(color_at(window.editor, 0, 0), (255, 255, 255, 255))
        self.assertFalse(window.inline_style_selector.isEnabled())


if __name__ == "__main__":
    unittest.main()
