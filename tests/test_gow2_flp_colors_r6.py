"""Regression tests for R6's inline and surgical GoW2 FLP text-color editor.

The real WAD inputs are intentionally *not* part of the repository.  When
available in the maintainer workspace (or via GOW_COLOR_TEST_INPUT_DIR), this
test reads them only and performs all edits in memory.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tool" / "GodOfWarTextEditor_Aprimorado_2026-09-24_R6" / "gow_text_editor.py"
INPUT_DIR = Path(os.environ.get("GOW_COLOR_TEST_INPUT_DIR", ROOT.parent / "uploads"))
PERMA = INPUT_DIR / "R_PERMA.WAD.txt"
SHELLA = INPUT_DIR / "R_SHELLA.WAD.txt"
HAS_REAL_INPUTS = PERMA.is_file() and SHELLA.is_file()


def load_editor_module():
    spec = importlib.util.spec_from_file_location("gow_text_editor_colors_r6", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EDITOR = load_editor_module()


def changed_offsets(before: bytes, after: bytes) -> set[int]:
    assert len(before) == len(after)
    return {index for index, (old, new) in enumerate(zip(before, after)) if old != new}


def load_flp(path: Path, name: str):
    wad = EDITOR.WadFile.load(path)
    tag = next(tag for tag in wad.tags if tag.name == name)
    return wad, tag, EDITOR.open_flp_movie(tag.data)


@unittest.skipUnless(HAS_REAL_INPUTS, "real GoW2 input WADs are not present")
class GoW2TextColorR6Tests(unittest.TestCase):
    def test_huda_analysis_reaches_blendcolors_and_zone_report_title(self):
        _wad, _tag, movie = load_flp(PERMA, "FLP_HUDA")
        analysis = movie.analyze_text_colors()
        self.assertEqual(analysis["counts"], {
            "data6": 14,
            "data7": 480,
            "transformations": 5437,
            "blend_colors": 1171,
        })
        self.assertEqual(analysis["blend_colors_pos"], 0x59BA0)
        self.assertEqual(analysis["strings_pos"], 0x5C038)
        self.assertEqual(analysis["keyframe_count"], 10307)
        self.assertEqual(analysis["invalid_color_ids"], [])
        self.assertEqual(analysis["invalid_handlers"], [])
        self.assertEqual(analysis["dynamic_labels"][1]["name"], "PS2_MessageTemplate_Line1")
        # This proves the physical DynamicLabel field is decoded BGRA, not
        # mistakenly treated as the RGBA layout used by StaticLabel commands.
        self.assertEqual(analysis["dynamic_labels"][1]["raw"], bytes.fromhex("28 4b 64 ff"))
        self.assertEqual(analysis["dynamic_labels"][1]["rgba"], (0x64, 0x4B, 0x28, 0xFF))
        title_colors = [
            entry["color_index"]
            for entry in analysis["blend_colors"]
            if any(item["index"] == 19 and item["kind"] == "dynamic_label" for item in entry["labels"])
        ]
        # ColorId 0 is the root white multiplier and reaches nearly all labels;
        # the named ZoneReport tween itself is the consecutive 576..593 range.
        self.assertTrue(set(range(576, 594)).issubset(title_colors))
        self.assertEqual(analysis["blend_colors"][576]["native_rgba"], (166, 115, 90, 0))

    def test_inline_text_targets_expose_only_their_direct_and_animation_colors(self):
        _wad, _tag, movie = load_flp(PERMA, "FLP_HUDA")

        static = movie.colors_for_text_target("static_label", 0)
        self.assertEqual(static["target_kind"], "static_label")
        self.assertEqual(static["direct"][0]["rgba"], (255, 255, 255, 255))
        self.assertEqual(static["direct"][0]["block_text"], "/10")
        self.assertIn(0, {entry["color_index"] for entry in static["animations"]})

        title = movie.colors_for_text_target("dynamic", 19)
        self.assertEqual(title["direct"][0]["name"], "/:PS2_ZoneReport_Title")
        self.assertTrue(set(range(576, 594)).issubset(
            {entry["color_index"] for entry in title["animations"]}
        ))

        # MSGS_TXT is injected by DoMsgPage into these named Flash variables.
        # Keep both same-name instances: they represent distinct FLP states.
        templates = movie.message_template_color_targets()
        self.assertEqual(
            [(item["line"], item["dynamic_index"]) for item in templates],
            [(1, 1), (1, 36), (2, 2), (2, 37), (3, 3), (3, 38), (4, 4), (5, 5)],
        )
        self.assertTrue(all(item["colors"]["direct"] for item in templates))
        self.assertTrue(all(0 in {entry["color_index"] for entry in item["colors"]["animations"]}
                            for item in templates))
        with self.assertRaises(ValueError):
            movie.colors_for_text_target("dynamic_label", 99999)

    def test_shella_analysis_and_static_direct_color(self):
        original_digest = hashlib.sha256(SHELLA.read_bytes()).hexdigest()
        _wad, _tag, movie = load_flp(SHELLA, "FLP_ShellA")
        analysis = movie.analyze_text_colors()
        self.assertEqual(analysis["counts"], {
            "data6": 48,
            "data7": 134,
            "transformations": 1033,
            "blend_colors": 522,
        })
        self.assertEqual(analysis["blend_colors_pos"], 0x1CC38)
        self.assertEqual(analysis["keyframe_count"], 4083)
        self.assertEqual(analysis["dynamic_labels"][0]["name"], "PS2_GameVersion")
        static = movie.static_label_color_fields()
        self.assertEqual(len(static), 1)
        self.assertEqual(static[0]["block_text"], "/10")
        self.assertEqual(static[0]["rgba"], (255, 255, 255, 255))
        self.assertEqual(static[0]["offset"], 0x1569)
        red = analysis["blend_colors"][508]
        self.assertEqual(red["rgba"], (255, 26, 26, 255))
        self.assertEqual({item["index"] for item in red["labels"]}, {9, 10})
        # This input is inspection-only too; no test path is allowed to write it.
        self.assertEqual(hashlib.sha256(SHELLA.read_bytes()).hexdigest(), original_digest)

    def test_each_patch_changes_only_its_identified_flp_field(self):
        _wad, _tag, movie = load_flp(PERMA, "FLP_HUDA")
        before = movie.data

        dynamic = movie.dynamic_label_color_fields()[1]
        edited_dynamic = movie.with_dynamic_label_color(1, (0x12, 0x34, 0x56, 0x78))
        self.assertEqual(
            changed_offsets(before, edited_dynamic.data),
            set(range(dynamic["offset"], dynamic["offset"] + 4)),
        )
        self.assertEqual(edited_dynamic.data[dynamic["offset"]:dynamic["offset"] + 4], bytes.fromhex("56 34 12 78"))
        self.assertEqual(edited_dynamic.dynamic_label_color_fields()[1]["rgba"], (0x12, 0x34, 0x56, 0x78))

        static = movie.static_label_color_fields()[0]
        edited_static = movie.with_static_label_color(static["label_index"], static["block_index"], (1, 2, 3, 4))
        self.assertEqual(
            changed_offsets(before, edited_static.data),
            set(range(static["offset"], static["offset"] + 4)),
        )
        self.assertEqual(edited_static.static_label_color_fields()[0]["rgba"], (1, 2, 3, 4))

        blend = movie.blend_color_fields()[575]
        edited_blend = movie.with_blend_color(575, (0x12, 0x34, 0x56, 0x78))
        changed = changed_offsets(before, edited_blend.data)
        self.assertTrue(changed)
        self.assertTrue(changed <= set(range(blend["offset"], blend["offset"] + 8)))
        self.assertEqual(edited_blend.blend_color_fields()[575]["native_rgba"], (0x12, 0x34, 0x56, 0x78))

    def test_wad_round_trip_reopens_and_changes_only_dynamic_color_bytes(self):
        original_bytes = PERMA.read_bytes()
        original_digest = hashlib.sha256(original_bytes).hexdigest()
        wad, tag, movie = load_flp(PERMA, "FLP_HUDA")
        field = movie.dynamic_label_color_fields()[1]
        edited = movie.with_dynamic_label_color(1, (0x12, 0x34, 0x56, 0x78))
        tag.data = edited.data
        serialized = wad.serialize()
        self.assertEqual(len(serialized), len(original_bytes))
        expected = {
            tag.offset + EDITOR.WAD_HEADER_SIZE + field["offset"] + channel
            for channel in range(4)
        }
        self.assertEqual(changed_offsets(original_bytes, serialized), expected)
        reopened = EDITOR.WadFile(serialized)
        reopened_tag = next(item for item in reopened.tags if item.name == "FLP_HUDA")
        reopened_movie = EDITOR.open_flp_movie(reopened_tag.data)
        self.assertEqual(reopened_movie.dynamic_label_color_fields()[1]["rgba"], (0x12, 0x34, 0x56, 0x78))
        # The test never wrote the input; assert its hash after all in-memory work.
        self.assertEqual(hashlib.sha256(PERMA.read_bytes()).hexdigest(), original_digest)

    def test_wad_round_trip_static_and_animation_layers_stay_in_their_field(self):
        original_bytes = PERMA.read_bytes()
        original_digest = hashlib.sha256(original_bytes).hexdigest()

        # StaticLabel command: all four original white bytes become different.
        wad, tag, movie = load_flp(PERMA, "FLP_HUDA")
        static = movie.static_label_color_fields()[0]
        tag.data = movie.with_static_label_color(static["label_index"], static["block_index"], (1, 2, 3, 4)).data
        serialized = wad.serialize()
        expected_static = {
            tag.offset + EDITOR.WAD_HEADER_SIZE + static["offset"] + channel
            for channel in range(4)
        }
        self.assertEqual(changed_offsets(original_bytes, serialized), expected_static)
        reopened = EDITOR.open_flp_movie(next(item for item in EDITOR.WadFile(serialized).tags if item.name == "FLP_HUDA").data)
        self.assertEqual(reopened.static_label_color_fields()[0]["rgba"], (1, 2, 3, 4))

        # BlendColor stores four uint16s: only bytes belonging to its eight-byte
        # native RGBA field may differ, and the rebuilt WAD must reopen.
        wad, tag, movie = load_flp(PERMA, "FLP_HUDA")
        blend = movie.blend_color_fields()[575]
        tag.data = movie.with_blend_color(575, (0x12, 0x34, 0x56, 0x78)).data
        serialized = wad.serialize()
        changed = changed_offsets(original_bytes, serialized)
        expected_blend = {
            tag.offset + EDITOR.WAD_HEADER_SIZE + blend["offset"] + channel
            for channel in range(8)
        }
        self.assertTrue(changed)
        self.assertTrue(changed <= expected_blend)
        reopened = EDITOR.open_flp_movie(next(item for item in EDITOR.WadFile(serialized).tags if item.name == "FLP_HUDA").data)
        self.assertEqual(reopened.blend_color_fields()[575]["native_rgba"], (0x12, 0x34, 0x56, 0x78))
        self.assertEqual(hashlib.sha256(PERMA.read_bytes()).hexdigest(), original_digest)


if __name__ == "__main__":
    unittest.main()
