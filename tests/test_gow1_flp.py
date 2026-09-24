"""Regression tests for GoW1 FLP StaticLabels.

These tests use a synthetic FLP only. No game WAD/assets are stored in the
repository; the real R_SHELL.WAD is checked manually by the maintainer.
"""
from __future__ import annotations

import importlib.util
import os
import struct
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
# R5 is the maintained source; the synthetic GoW1 suite also guards that its
# parser and raw-FLP transfer behavior remained compatible while adding GoW2
# text-color editing.
SOURCE = ROOT / "tool" / "GodOfWarTextEditor_Aprimorado_2026-09-24_R6" / "gow_text_editor.py"


def load_editor_module():
    spec = importlib.util.spec_from_file_location("gow_text_editor_gow1_test", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves postponed annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EDITOR = load_editor_module()


def align4(value: int) -> int:
    return (value + 3) & ~3


def synthetic_gow1_flp(lines: tuple[str, ...] = ("Opções",)) -> bytes:
    """Build a minimal GoW1 FLP with a PT-BR StaticLabel.

    ``lines`` become separate render commands, exactly like the multiline
    warnings in R_SHELL: each line owns its font handler and X/Y anchor.

    Layout mirrors god_of_war_browser's GoW1 parser: magic 0x21, 0x60-byte
    header, a GlobalHandler pointing to font 0, one 0x24-byte font header and
    one 0x24-byte StaticLabel header whose stream size lives at +0x14.
    """
    header = bytearray(0x60)
    struct.pack_into("<I", header, 0x00, 0x21)  # GoW1 FLP magic
    struct.pack_into("<I", header, 0x0C, 1)     # global handlers
    struct.pack_into("<I", header, 0x1C, 1)     # fonts
    struct.pack_into("<I", header, 0x24, 1)     # static labels

    # GlobalHandler[0] = type 3 (fonts), font index 0.
    body = bytearray(struct.pack("<HH", 3, 0))

    # Glyph 0 is space; the remaining glyphs spell Opções.
    chars = " Opçõesão"  # inclui ã/o para testar uma edição PT-BR válida
    glyph_for = {character: index for index, character in enumerate(chars)}
    font_header = bytearray(0x24)
    struct.pack_into("<I", font_header, 0x00, len(chars))
    struct.pack_into("<H", font_header, 0x0C, 0x0001)  # 256-entry char map
    body += font_header
    body += struct.pack("<%dh" % len(chars), *([160] * len(chars)))
    body += b"\0" * (align4(len(body)) - len(body))
    char_map = [-1] * 0x100
    for character, glyph in glyph_for.items():
        char_map[ord(character)] = glyph
    body += struct.pack("<256h", *char_map)
    body += b"\0" * (align4(len(body)) - len(body))

    stream = bytearray()
    for line_index, line in enumerate(lines):
        glyphs = [glyph_for[character] for character in line]
        # GH + scale + X/Y: the headers differ per line and must survive an
        # edit exactly, just as they do in the real multiline shell labels.
        stream.append(0x8B)
        stream += struct.pack("<Hhhh", 0, 1024, 16 * line_index, 32 * line_index)
        stream.append(len(glyphs))
        for glyph in glyphs:
            stream += struct.pack("<Hh", glyph, 80)

    static_header = bytearray(0x24)
    struct.pack_into("<I", static_header, 0x14, len(stream))
    body += static_header
    body += stream
    body += b"\0" * (align4(len(body)) - len(body))
    return bytes(header + body)


def synthetic_wad_tag(tag: int, name: str, data: bytes, flags: int = 0) -> bytes:
    """Build one canonical 0x20-byte WAD tag segment for a loader regression."""
    header = struct.pack("<HHI", tag, flags, len(data))
    header += name.encode("cp1252").ljust(24, b"\0")
    segment = header + data
    return segment + b"\0" * ((-len(segment)) % 0x10)


def synthetic_mixed_txt_flp_wad() -> bytes:
    """Minimal GoW1 WAD shaped like R_PERM/R_PERMA: TXT plus FLP_HUD."""
    return b"".join((
        # First tag 0x378 identifies a GoW1 container to WadFile.
        synthetic_wad_tag(0x378, "R_PERMA", b"\0\0\0\0"),
        synthetic_wad_tag(0x101, "Curiosidade.txt", b"*1*\r\nTexto original\r\n"),
        synthetic_wad_tag(0x102, "FLP_HUD", synthetic_gow1_flp()),
    ))


def synthetic_gow2_flp() -> bytes:
    """Minimal GoW2 counterpart used to guard the existing FLP path."""
    header = bytearray(0x5C)
    struct.pack_into("<I", header, 0x00, 0x1B)  # GoW2 FLP magic
    struct.pack_into("<I", header, 0x38, 1)     # global handlers
    struct.pack_into("<I", header, 0x40, 1)     # fonts
    struct.pack_into("<I", header, 0x44, 1)     # static labels
    body = bytearray(struct.pack("<HH", 3, 0))

    chars = " Opçõesão"
    glyph_for = {character: index for index, character in enumerate(chars)}
    font_header = bytearray(0x24)
    struct.pack_into("<I", font_header, 0x10, len(chars))
    struct.pack_into("<H", font_header, 0x20, 0x0001)
    body += font_header
    body += struct.pack("<%dh" % len(chars), *([160] * len(chars)))
    body += b"\0" * (align4(len(body)) - len(body))
    char_map = [-1] * 0x100
    for character, glyph in glyph_for.items():
        char_map[ord(character)] = glyph
    body += struct.pack("<256h", *char_map)
    body += b"\0" * (align4(len(body)) - len(body))

    glyphs = [glyph_for[character] for character in "Opções"]
    stream = bytearray([0x88]) + struct.pack("<Hh", 0, 1024) + bytes([len(glyphs)])
    for glyph in glyphs:
        stream += struct.pack("<Hh", glyph, 80)
    static_header = bytearray(0x1C)
    struct.pack_into("<I", static_header, 0x18, len(stream))
    body += static_header + stream
    body += b"\0" * (align4(len(body)) - len(body))
    return bytes(header + body)


class GoW1StaticLabelTests(unittest.TestCase):
    def test_reads_cp1252_accents_and_selects_gow1_parser(self):
        movie = EDITOR.open_flp_movie(synthetic_gow1_flp())
        self.assertEqual(movie.format_name, "GoW1")
        self.assertEqual(movie.static_count, 1)
        label = movie.label(0)
        self.assertTrue(label["editable"])
        self.assertEqual(label["text"], "Opções")

    def test_noop_is_byte_exact_and_edit_reparses(self):
        raw = synthetic_gow1_flp()
        movie = EDITOR.open_flp_movie(raw)
        self.assertEqual(movie.encode_label(0, "Opções"), raw)

        edited = movie.encode_label(0, "Opção")
        self.assertNotEqual(edited, raw)
        rebuilt = EDITOR.open_flp_movie(edited)
        self.assertEqual(rebuilt.label(0)["text"], "Opção")
        # GoW1 convention: stream size excludes its 4-byte alignment padding.
        self.assertNotEqual(
            rebuilt.statics[0]["size"] % 4,
            0,
            "The GoW1 StaticLabel header must keep the raw, unpadded stream length.",
        )

    def test_multiline_label_preserves_blocks_and_requires_same_line_count(self):
        raw = synthetic_gow1_flp(("Opções", "Opção"))
        movie = EDITOR.open_flp_movie(raw)
        label = movie.label(0)
        self.assertTrue(label["editable"])
        self.assertEqual(label["line_count"], 2)
        self.assertEqual(label["text"], "Opções\nOpção")
        self.assertEqual(movie.encode_label(0, label["text"]), raw)

        edited = movie.encode_label(0, "Opção\nOpções")
        rebuilt = EDITOR.open_flp_movie(edited)
        self.assertEqual(rebuilt.label(0)["text"], "Opção\nOpções")
        self.assertEqual(rebuilt.label(0)["line_count"], 2)
        before_static = movie.statics[0]
        after_static = rebuilt.statics[0]
        before_blocks = movie.parse_commands(raw[before_static["stream"]:before_static["stream"] + before_static["size"]])
        after_blocks = rebuilt.parse_commands(edited[after_static["stream"]:after_static["stream"] + after_static["size"]])
        self.assertEqual(
            [(b["flags"], b["gh"], b["scale"], b["x"], b["y"]) for b in after_blocks],
            [(b["flags"], b["gh"], b["scale"], b["x"], b["y"]) for b in before_blocks],
        )
        with self.assertRaisesRegex(ValueError, "2 linhas"):
            movie.encode_label(0, "Opções")

    def test_gow2_path_still_dispatches_and_reparses(self):
        raw = synthetic_gow2_flp()
        movie = EDITOR.open_flp_movie(raw)
        self.assertEqual(movie.format_name, "GoW2")
        self.assertEqual(movie.label(0)["text"], "Opções")
        self.assertEqual(movie.encode_label(0, "Opções"), raw)
        self.assertEqual(EDITOR.open_flp_movie(movie.encode_label(0, "Opção")).label(0)["text"], "Opção")

    def test_synthetic_r_perma_has_both_txt_and_flp_hud(self):
        wad = EDITOR.WadFile(synthetic_mixed_txt_flp_wad())
        self.assertEqual(wad.variant, "GoW1")
        self.assertEqual([tag.name for tag in wad.text_tags()], ["Curiosidade.txt"])
        flp_tags = [tag for tag in wad.tags if tag.upper_name.startswith("FLP_")]
        self.assertEqual([tag.name for tag in flp_tags], ["FLP_HUD"])
        movie = EDITOR.open_flp_movie(flp_tags[0].data)
        self.assertEqual(movie.label(0)["text"], "Opções")

    @unittest.skipUnless(EDITOR.QT_AVAILABLE, "PySide6 is needed for the main-window regression")
    def test_main_window_mixes_txt_and_flp_without_index_confusion(self):
        """TXT -> FLP -> TXT must use source indices, not left-panel rows."""
        app = EDITOR.QApplication.instance() or EDITOR.QApplication([])
        old_ini = os.environ.get("GOW2TE_INI")
        window = None
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                wad_path = temp_path / "R_PERMA.WAD"
                ini_path = temp_path / "test.ini"
                wad_path.write_bytes(synthetic_mixed_txt_flp_wad())
                os.environ["GOW2TE_INI"] = str(ini_path)
                window = EDITOR.App()
                self.assertTrue(window.load_wad_path(str(wad_path)))
                self.assertEqual(window.main_resource_entries, [("txt", 0), ("flp", 0)])
                self.assertEqual(window.resource_box.count(), 2)
                self.assertIn("Curiosidade.txt", window.resource_box.item(0).text())
                self.assertIn("FLP_HUD", window.resource_box.item(1).text())

                # Edit and apply TXT first: undo must retain text-resource index 0.
                self.assertFalse(window._is_main_flp_mode())
                window.editor.setPlainText("Texto alterado")
                window.apply_current()
                self.assertEqual(window._undo_stack[-1][0], 0)

                # UI row 1 is FLP, but source index 0 in main_flp_resources.
                window.resource_box.setCurrentIndex(1)
                app.processEvents()
                self.assertTrue(window._is_main_flp_mode())
                self.assertEqual(window.active_tag.name, "FLP_HUD")
                self.assertEqual(window.editor.toPlainText(), "Opções")
                # No modo FLP, as mesmas ações de Arquivo viram transferência
                # binária selecionada, em vez de ficarem bloqueadas como na R3.
                self.assertTrue(window.action_export.isEnabled())
                self.assertTrue(window.action_import.isEnabled())
                self.assertEqual(window.action_export.text(), "Exportar FLP…")
                self.assertEqual(window.action_import.text(), "Importar FLP…")
                window.editor.setPlainText("Opção")
                window.apply_current()
                self.assertEqual(window.active_flp_movie.label(0)["text"], "Opção")

                # O helper de UI recebe somente o FLP selecionado e mantém a
                # tag/nome no WAD; a caixa de diálogo de arquivos só o chama
                # depois da validação e confirmação do usuário.
                replacement = synthetic_gow1_flp(("Opções",))
                replacement_movie = EDITOR.validate_flp_replacement(window.active_tag.data, replacement)
                window._update_active_flp_after_import(replacement, replacement_movie)
                self.assertEqual(window.active_tag.name, "FLP_HUD")
                self.assertEqual(window.active_tag.data, replacement)
                self.assertEqual(window.active_flp_movie.label(0)["text"], "Opções")
                self.assertIn("FLP_HUD", window.resource_box.item(1).text())

                # Undoing the prior TXT edit while FLP is selected must not treat
                # visual row 1 as text resource 1. _goto_message maps back to row 0.
                window.undo_global()
                window._goto_message(0, 0)
                app.processEvents()
                self.assertFalse(window._is_main_flp_mode())
                self.assertEqual(window.resource_box.currentIndex(), 0)
                self.assertEqual(window.editor.toPlainText(), "Texto original")
        finally:
            if old_ini is None:
                os.environ.pop("GOW2TE_INI", None)
            else:
                os.environ["GOW2TE_INI"] = old_ini
            if window is not None:
                window.hide()
                window.deleteLater()
                app.processEvents()


class FLPBinaryTransferTests(unittest.TestCase):
    """Raw .flp export/import contract, independent of the Qt file dialogs."""

    def test_export_filename_is_safe_and_uses_flp_extension(self):
        self.assertEqual(EDITOR.flp_export_filename("FLP_Shell"), "FLP_Shell.flp")
        self.assertEqual(EDITOR.flp_export_filename("FLP_HUD.FLP"), "FLP_HUD.FLP")
        self.assertEqual(EDITOR.flp_export_filename("  pasta/FLP_Menu\\teste  "), "pasta_FLP_Menu_teste.flp")
        self.assertEqual(EDITOR.flp_export_filename(""), "movie.flp")

    def test_replacement_accepts_same_game_and_rejects_cross_game(self):
        target = synthetic_gow1_flp(("Opções",))
        imported = synthetic_gow1_flp(("Opção",))
        movie = EDITOR.validate_flp_replacement(target, imported)
        self.assertEqual(movie.format_name, "GoW1")
        self.assertEqual(movie.label(0)["text"], "Opção")

        with self.assertRaisesRegex(ValueError, "incompatível"):
            EDITOR.validate_flp_replacement(target, synthetic_gow2_flp())
        with self.assertRaisesRegex(ValueError, "magic|pequeno"):
            EDITOR.validate_flp_replacement(target, b"not a FLP")

    def test_imported_raw_flp_reserializes_only_target_tag(self):
        raw_wad = synthetic_mixed_txt_flp_wad()
        wad = EDITOR.WadFile(raw_wad)
        text_segment_before = wad.tags[1].raw_segment
        target = next(tag for tag in wad.tags if tag.name == "FLP_HUD")
        target_name = target.name_raw
        target_flags = target.flags
        target_original = target.data
        imported = synthetic_gow1_flp(("Opção",))
        self.assertNotEqual(imported, target_original)

        movie = EDITOR.validate_flp_replacement(target_original, imported)
        target.data = imported
        serialized = wad.serialize()
        rebuilt = EDITOR.WadFile(serialized)
        rebuilt_target = next(tag for tag in rebuilt.tags if tag.name == "FLP_HUD")

        self.assertEqual(rebuilt.tags[1].raw_segment, text_segment_before)
        self.assertEqual(rebuilt_target.name_raw, target_name)
        self.assertEqual(rebuilt_target.flags, target_flags)
        self.assertEqual(rebuilt_target.size_field, len(imported))
        self.assertEqual(rebuilt_target.data, imported)
        self.assertEqual(EDITOR.open_flp_movie(rebuilt_target.data).label(0)["text"], "Opção")
        self.assertEqual(movie.format_name, "GoW1")


if __name__ == "__main__":
    unittest.main()
