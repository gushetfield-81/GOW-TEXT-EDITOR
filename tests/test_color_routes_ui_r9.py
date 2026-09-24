"""Qt/offscreen R9 regression for effective color-route disclosure."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GOW2TE_INI", "/tmp/gow-r9-ui-tests.ini")
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tool" / "GodOfWarTextEditor_Aprimorado_2026-09-24_R9" / "gow_text_editor.py"
PERMA = Path("/home/user/uploads/R_PERMA.WAD.txt")

try:
    from PySide6.QtGui import QColor, QTextCursor
    from PySide6.QtWidgets import QApplication
except ImportError:
    QColor = QTextCursor = QApplication = None


def load_editor():
    spec = importlib.util.spec_from_file_location("gow_r9_ui", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EDITOR = load_editor()
CAN_RUN = bool(QApplication is not None and EDITOR.QT_AVAILABLE and PERMA.is_file())


@unittest.skipUnless(CAN_RUN, "PySide6/offscreen plus R_PERMA required")
class ColorRoutesUiR9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.digest = hashlib.sha256(PERMA.read_bytes()).hexdigest()
        self.window = EDITOR.App()
        self.original_box = EDITOR.QMessageBox
        self.assertTrue(self.window.load_wad_path(str(PERMA)))
        resource = next(i for i, tag in enumerate(self.window.text_resources) if tag.upper_name == "MSGS_TXT")
        self.window.load_resource(resource)
        self.window.load_message(next(i for i, item in enumerate(self.window.resource_messages) if item.key == "701"))
        self.app.processEvents()

    def tearDown(self):
        try:
            self.window._open_snapshot = {id(tag): tag.data for tag in self.window.wad.tags}
            self.window.dirty = False
            self.window.close()
            self.window.deleteLater()
        finally:
            EDITOR.QMessageBox = self.original_box
        self.assertEqual(hashlib.sha256(PERMA.read_bytes()).hexdigest(), self.digest)

    def move_to(self, text):
        cursor = self.window.editor.textCursor()
        cursor.setPosition(self.window.editor.toPlainText().index(text))
        self.window.editor.setTextCursor(cursor)
        self.window._on_editor_cursor_changed()
        self.app.processEvents()

    def test_title_routes_to_flashmsg_not_base_and_line3_lists_branches(self):
        self.move_to("LÂMINAS")
        self.assertIn("FlashMsg1Color #7F2805", self.window.inline_style_hint.text())
        self.assertIn("125 marcador(es)", self.window.inline_style_hint.text())
        self.assertEqual(self.window.editor_color_tag.text(), "BASE NÃO PINTA [*N]")
        self.assertFalse(self.window.editor_color_button.isEnabled())
        self.assertEqual(self.window.inline_style_selector.currentData(), 1)

        self.move_to("B1H")
        hint = self.window.inline_style_hint.text()
        self.assertIn("MessageTemplates", hint)
        self.assertIn("PickUpInfoMenu → InfoTextMovieClips", hint)
        options = [self.window.editor_color_selector.itemText(i)
                   for i in range(self.window.editor_color_selector.count())]
        self.assertEqual(len(options), 2)
        self.assertTrue(any("#644B28FF" in item for item in options))
        self.assertTrue(any("#FFFFFFFF" in item for item in options))

    def test_exclusive_color_reserves_free_slot_for_only_selection(self):
        text = self.window.editor.toPlainText()
        start = text.index("LÂMINAS")
        cursor = self.window.editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + len("LÂMINAS"), QTextCursor.KeepAnchor)
        self.window.editor.setTextCursor(cursor)
        self.window._on_editor_cursor_changed()
        self.assertTrue(self.window.inline_style_exclusive_button.isEnabled())

        class Box:
            Yes = self.original_box.Yes
            No = self.original_box.No
            @staticmethod
            def question(*_args):
                return Box.Yes
            @staticmethod
            def information(*_args):
                raise AssertionError("unexpected information dialog")
            @staticmethod
            def warning(*_args):
                raise AssertionError("unexpected warning dialog")
            @staticmethod
            def critical(*args):
                raise AssertionError(str(args[-1]))
        class Dialog:
            @staticmethod
            def getColor(*_args, **_kwargs):
                return QColor(19, 37, 71)

        EDITOR.QMessageBox = Box
        old_dialog = EDITOR.QColorDialog
        EDITOR.QColorDialog = Dialog
        try:
            self.window._apply_exclusive_inline_selection_color()
        finally:
            EDITOR.QColorDialog = old_dialog
        self.app.processEvents()
        self.assertIn("[*3]LÂMINAS[*1] DE ATENA", self.window.editor.toPlainText())
        self.assertEqual(self.window.runtime_inline_palette.color(3), (19, 37, 71, 255))
        self.assertEqual(self.window._inline_style_usage(3)["controls"], 1)


if __name__ == "__main__":
    unittest.main()
