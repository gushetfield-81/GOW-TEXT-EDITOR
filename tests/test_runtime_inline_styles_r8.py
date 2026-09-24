"""Core regression for R8 Flash inline MSGS_TXT styles (no Qt required)."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tool" / "GodOfWarTextEditor_Aprimorado_2026-09-24_R8" / "gow_text_editor.py"
PERMA = ROOT.parent / "uploads" / "R_PERMA.WAD.txt"
SHELLA = ROOT.parent / "uploads" / "R_SHELLA.WAD.txt"


def load_editor():
    spec = importlib.util.spec_from_file_location("gow_r8_core", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EDITOR = load_editor()


def message(resource, key):
    return next(item for item in resource.messages if item.key == key)


def style_at(plan, block, position):
    for start, length, rgba in plan.spans.get(block, []):
        if start <= position < start + length:
            return rgba
    return None


@unittest.skipUnless(PERMA.is_file() and SHELLA.is_file(), "WAD inputs required")
class RuntimeInlineStylesR8Tests(unittest.TestCase):
    def setUp(self):
        self.perma_digest = hashlib.sha256(PERMA.read_bytes()).hexdigest()
        self.shell_digest = hashlib.sha256(SHELLA.read_bytes()).hexdigest()

    def tearDown(self):
        self.assertEqual(hashlib.sha256(PERMA.read_bytes()).hexdigest(), self.perma_digest)
        self.assertEqual(hashlib.sha256(SHELLA.read_bytes()).hexdigest(), self.shell_digest)

    def perma(self):
        wad = EDITOR.WadFile.load(PERMA)
        palette = EDITOR.find_runtime_inline_palette(wad)
        self.assertIsNotNone(palette)
        tag = next(tag for tag in wad.tags if tag.name == "MSGS_TXT")
        resource = EDITOR.TextResource(tag.data, EDITOR.GOW2_RUNTIME_UTF8_CODEC)
        return wad, palette, tag, resource

    def test_palette_is_read_from_exported_gbl_global(self):
        _wad, palette, _tag, _resource = self.perma()
        self.assertTrue(palette.editable)
        self.assertEqual(palette.source, "DC_WAD_R_Perm → GBL_Global")
        self.assertEqual(palette.global_offset, 0x6BE0)
        self.assertEqual(palette.field_offset(1), 0x6FF0)
        self.assertEqual(palette.colors, {
            1: (127, 40, 5, 255), 2: (170, 89, 20, 255),
            3: (102, 102, 102, 255), 4: (102, 153, 204, 255),
            5: (127, 140, 96, 255), 6: (178, 191, 122, 255),
        })

    def test_laminas_and_reset_follow_same_line_runtime_scope(self):
        _wad, palette, _tag, resource = self.perma()
        blades = message(resource, "701")
        self.assertTrue(blades.text.startswith("[*1] [IconBlade] LÂMINAS DE ATENA"))
        plan = EDITOR.build_inline_style_render_plan(blades.text, palette)
        self.assertEqual(style_at(plan, 0, blades.text.index("LÂMINAS")), palette.colors[1])
        # A description line without a marker begins a new EditTextBuild/style=0.
        self.assertNotIn(3, plan.spans)
        self.assertEqual(plan.controls[0][0].raw, "[*1]")

        mid = message(resource, "270")
        mid_plan = EDITOR.build_inline_style_render_plan(mid.text, palette)
        self.assertEqual(style_at(mid_plan, 0, mid.text.index("Investida")), palette.colors[1])
        self.assertIsNone(style_at(mid_plan, 0, mid.text.index("[*0]") + 4))
        self.assertEqual([control.style for control in mid_plan.controls[0]], [1, 0])

    def test_observed_styles_and_raw_wrap_roundtrip(self):
        wad, palette, tag, resource = self.perma()
        mixed = message(resource, "799")
        plan = EDITOR.build_inline_style_render_plan(mixed.text, palette)
        self.assertEqual(style_at(plan, 0, mixed.text.index("?")), palette.colors[1])
        self.assertEqual(style_at(plan, 2, 5), palette.colors[2])
        challenge = message(resource, "6110")
        self.assertEqual(style_at(EDITOR.build_inline_style_render_plan(challenge.text, palette), 0,
                                  challenge.text.index("Fúria")), palette.colors[4])

        self.assertEqual(EDITOR.replace_inline_style_at("[*1]Lâmina", 1, 4), "[*4]Lâmina")
        self.assertEqual(EDITOR.wrap_inline_style_selection("A[IconBlade]B[*2]C", 1, 13, 1),
                         "A[*1][IconBlade]B[*0][*2]C")
        self.assertEqual(EDITOR.wrap_inline_style_selection("Aone\ntwo\nthreeB", 1, 12, 4),
                         "A[*4]one[*0]\n[*4]two[*0]\n[*4]thr[*0]eeB")

        item = message(resource, "270")
        raw = item.text
        item.set_text(EDITOR.wrap_inline_style_selection(raw, 4, raw.index("[*0]"), 4))
        self.assertIn("[*4]", item.text)
        tag.data = resource.to_bytes()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "roundtrip.wad"
            output.write_bytes(wad.serialize())
            reopened = EDITOR.WadFile.load(output)
        reopened_tag = next(candidate for candidate in reopened.tags if candidate.name == "MSGS_TXT")
        reopened_resource = EDITOR.TextResource(reopened_tag.data, EDITOR.GOW2_RUNTIME_UTF8_CODEC)
        result = message(reopened_resource, "270").text
        self.assertEqual(result, item.text)
        self.assertNotIn("<span", result.lower())

    def test_rgb_patch_is_limited_to_three_float_components(self):
        wad, palette, _tag, _resource = self.perma()
        target = palette.data_tag
        self.assertIsNotNone(target)
        before_tag = target.data
        before_wad = wad.serialize()
        offset = palette.field_offset(1)
        target.data = EDITOR.patched_runtime_inline_palette_rgb(palette, 1, (1, 2, 3))
        self.assertEqual(target.data[:offset], before_tag[:offset])
        self.assertEqual(target.data[offset + 12:], before_tag[offset + 12:])
        reparsed = EDITOR.find_runtime_inline_palette(wad)
        self.assertEqual(reparsed.colors[1], (1, 2, 3, 255))
        after_wad = wad.serialize()
        changed = {i for i, (old, new) in enumerate(zip(before_wad, after_wad)) if old != new}
        absolute = target.offset + EDITOR.WAD_HEADER_SIZE + offset
        self.assertTrue(changed)
        self.assertTrue(changed <= set(range(absolute, absolute + 12)))
        self.assertEqual(len(before_wad), len(after_wad))

    def test_shell_has_no_fake_editable_global(self):
        shell = EDITOR.WadFile.load(SHELLA)
        self.assertIsNone(EDITOR.find_runtime_inline_palette(shell))
        palette = EDITOR.runtime_inline_palette_for_wad(shell)
        self.assertFalse(palette.editable)
        self.assertEqual(palette.colors[1], (127, 40, 5, 255))
        with self.assertRaises(ValueError):
            EDITOR.patched_runtime_inline_palette_rgb(palette, 1, (10, 20, 30))


if __name__ == "__main__":
    unittest.main()
