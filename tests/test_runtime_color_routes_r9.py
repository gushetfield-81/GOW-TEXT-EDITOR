"""R9 regression: effective runtime color routes and safe inline overrides."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tool" / "GodOfWarTextEditor_Aprimorado_2026-09-24_R9" / "gow_text_editor.py"
PERMA = Path("/home/user/uploads/R_PERMA.WAD.txt")


def load_editor():
    spec = importlib.util.spec_from_file_location("gow_r9_core", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EDITOR = load_editor()


def message(resource, key):
    return next(item for item in resource.messages if item.key == key)


@unittest.skipUnless(PERMA.is_file(), "R_PERMA input required")
class RuntimeColorRoutesR9Tests(unittest.TestCase):
    def setUp(self):
        self.digest = hashlib.sha256(PERMA.read_bytes()).hexdigest()
        self.wad = EDITOR.WadFile.load(PERMA)
        self.palette = EDITOR.find_runtime_inline_palette(self.wad)
        self.tag = next(tag for tag in self.wad.tags if tag.upper_name == "MSGS_TXT")
        self.resource = EDITOR.TextResource(self.tag.data, EDITOR.GOW2_RUNTIME_UTF8_CODEC)

    def tearDown(self):
        self.assertEqual(hashlib.sha256(PERMA.read_bytes()).hexdigest(), self.digest)

    def test_msg701_flashmsg1_is_the_title_route(self):
        blades = message(self.resource, "701")
        position = blades.text.index("LÂMINAS")
        self.assertEqual(EDITOR.inline_style_at_position(blades.text, position), 1)
        self.assertEqual(EDITOR.inline_styles_in_range(blades.text, position, position + 7), {1})
        plan = EDITOR.build_inline_style_render_plan(blades.text, self.palette)
        span = next(item for item in plan.spans[0] if item[0] <= position < item[0] + item[1])
        self.assertEqual(span[2], (127, 40, 5, 255))
        self.assertEqual(EDITOR.inline_style_at_position(blades.text, blades.text.index("Lâminas poderosas")), 0)

    def test_duplicate_template_instances_have_distinct_verified_paths(self):
        huda = next(tag for tag in self.wad.tags if tag.name == "FLP_HUDA")
        movie = EDITOR.FLPMovie(huda.data)
        targets = movie.message_template_color_targets()
        line1 = {item["dynamic_index"]: item for item in targets if item["line"] == 1}
        self.assertEqual(line1[1]["colors"]["runtime_paths"], ("MessageTemplates",))
        self.assertEqual(line1[36]["colors"]["runtime_paths"], ("PickUpInfoMenu → InfoTextMovieClips",))
        self.assertEqual(line1[1]["colors"]["direct"][0]["rgba"], (100, 75, 40, 255))
        self.assertEqual(line1[36]["colors"]["direct"][0]["rgba"], (255, 255, 255, 255))

    def test_selection_override_restores_following_route_and_round_trips(self):
        original = "[*1]aBC def"
        rewritten = EDITOR.wrap_inline_style_selection(original, original.index("B"), original.index(" def"), 3)
        self.assertEqual(rewritten, "[*1]a[*3]BC[*1] def")
        self.assertEqual(EDITOR.inline_style_at_position(rewritten, rewritten.index("def")), 1)

        blades = message(self.resource, "701")
        other_before = message(self.resource, "270").text
        old_context = bytes(self.palette.data_tag.data)
        offset = self.palette.field_offset(3)
        self.palette.data_tag.data = EDITOR.patched_runtime_inline_palette_rgb(self.palette, 3, (19, 37, 71))
        start = blades.text.index("LÂMINAS")
        blades.set_text(EDITOR.wrap_inline_style_selection(blades.text, start, start + len("LÂMINAS"), 3))
        self.tag.data = self.resource.to_bytes()
        self.assertIn("[*3]LÂMINAS[*1] DE ATENA", blades.text)
        self.assertEqual(message(self.resource, "270").text, other_before)
        self.assertEqual(self.palette.data_tag.data[:offset], old_context[:offset])
        self.assertEqual(self.palette.data_tag.data[offset + 12:], old_context[offset + 12:])
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "r9.wad"
            out.write_bytes(self.wad.serialize())
            reopened = EDITOR.WadFile.load(out)
        fresh = EDITOR.find_runtime_inline_palette(reopened)
        self.assertEqual(fresh.color(3), (19, 37, 71, 255))
        reopened_resource = EDITOR.TextResource(
            next(tag for tag in reopened.tags if tag.upper_name == "MSGS_TXT").data,
            EDITOR.GOW2_RUNTIME_UTF8_CODEC,
        )
        self.assertIn("[*3]LÂMINAS[*1] DE ATENA", message(reopened_resource, "701").text)


if __name__ == "__main__":
    unittest.main()
