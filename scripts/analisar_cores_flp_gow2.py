#!/usr/bin/env python3
"""Relatório somente-leitura das cores de texto de FLPs GoW2.

Uso:
    python scripts/analisar_cores_flp_gow2.py /caminho/R_PERMA.WAD /caminho/R_SHELLA.WAD

O script não escreve nos WADs. Ele usa o mesmo parser lossless da R7 para
validar Data6/Data7/Data8, DynamicLabels, StaticLabel RenderCommands e a
tabela global BlendColors.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import struct
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDITOR_SOURCE = ROOT / "tool" / "GodOfWarTextEditor_Aprimorado_2026-09-24_R7" / "gow_text_editor.py"


def load_editor():
    spec = importlib.util.spec_from_file_location("gow_text_editor_r7_analysis", EDITOR_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Não foi possível carregar {EDITOR_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def short_list(values: list[str], limit: int = 6) -> str:
    if not values:
        return "—"
    prefix = "; ".join(values[:limit])
    return prefix + (f"; … +{len(values) - limit}" if len(values) > limit else "")


def report_wad(editor, wad_path: Path, show_all_animation_text: bool) -> None:
    raw = wad_path.read_bytes()  # leitura somente
    wad = editor.WadFile(raw)
    print(f"\n## {wad_path.name}")
    print(f"- SHA-256 de entrada: `{hashlib.sha256(raw).hexdigest()}`")
    print(f"- Tamanho: {len(raw):,} bytes; variante detectada: {wad.variant}")

    for tag in wad.tags:
        if len(tag.data) < 4 or struct.unpack_from("<I", tag.data, 0)[0] != 0x1B:
            continue
        try:
            movie = editor.open_flp_movie(tag.data)
            analysis = movie.analyze_text_colors()
        except Exception as exc:
            print(f"\n### {tag.name}\n- FLP GoW2 não analisado: `{exc}`")
            continue

        counts = analysis["counts"]
        dynamics = analysis["dynamic_labels"]
        static_fields = movie.static_label_color_fields()
        blends = analysis["blend_colors"]
        text_blends = [entry for entry in blends if entry["text_label_count"]]
        colors = Counter(movie.rgba_hex(entry["rgba"]) for entry in dynamics)

        print(f"\n### {tag.name}")
        print(f"- Payload: {len(tag.data):,} bytes; SHA-256 `{hashlib.sha256(tag.data).hexdigest()}`")
        print(
            "- Animação: "
            f"Data6={counts['data6']}, Data7={counts['data7']}, "
            f"Transformations={counts['transformations']}, BlendColors={counts['blend_colors']}; "
            f"{analysis['keyframe_count']:,} KeyFrames."
        )
        print(
            f"- Tabela BlendColors em `0x{analysis['blend_colors_pos']:X}`; "
            f"strings em `0x{analysis['strings_pos']:X}`; "
            f"{len(text_blends)} tintas alcançam pelo menos um rótulo de texto."
        )
        print(f"- DynamicLabels: {len(dynamics)}; cores base RGBA: " + ", ".join(
            f"`{color}` × {amount}" for color, amount in colors.most_common()
        ))

        print("- StaticLabel RenderCommands com BlendColor próprio:")
        if static_fields:
            for field in static_fields:
                inherited = ", ".join(str(index + 1) for index in field["affected_blocks"])
                print(
                    f"  - StaticLabel [{field['label_index']}], bloco {field['block_index'] + 1}: "
                    f"`{movie.rgba_hex(field['rgba'])}` em `0x{field['offset']:X}`; "
                    f"afeta bloco(s) {inherited}; texto `{field['block_text']}`."
                )
        else:
            print("  - Nenhum.")

        named_animation = []
        for blend in text_blends:
            labels = [item["display"] for item in blend["labels"]]
            if any("Title" in label or "ZoneReport" in label or "PS2_4021" in label for label in labels):
                named_animation.append(blend)
        if named_animation:
            print("- Exemplos de tintas de animação que alcançam títulos/rótulos nomeados:")
            for blend in named_animation[:40]:
                print(
                    f"  - ColorId {blend['color_index']}: `{movie.rgba_hex(blend['rgba'])}` "
                    f"(nativo {blend['native_rgba']}, refs {blend['reference_count']}) → "
                    f"{short_list([item['display'] for item in blend['labels']], 3)}"
                )
            if len(named_animation) > 40:
                print(f"  - … +{len(named_animation) - 40} entradas relacionadas.")

        if show_all_animation_text:
            print("- Todas as BlendColors que chegam a texto:")
            for blend in text_blends:
                print(
                    f"  - ColorId {blend['color_index']}: `{movie.rgba_hex(blend['rgba'])}`; "
                    f"{blend['text_label_count']} rótulo(s); "
                    f"{short_list([item['display'] for item in blend['labels']], 5)}"
                )

        if analysis["invalid_color_ids"] or analysis["invalid_handlers"]:
            print(
                "- Avisos estruturais: "
                f"ColorIds inválidos={analysis['invalid_color_ids']}; "
                f"handlers inválidos={analysis['invalid_handlers']}."
            )
        else:
            print("- Validação estrutural: nenhum ColorId/handler inválido encontrado.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analisa cores FLP GoW2 sem alterar os WADs.")
    parser.add_argument("wads", nargs="+", type=Path, help="WAD(s) de entrada, somente para leitura")
    parser.add_argument(
        "--all-animation-text",
        action="store_true",
        help="lista todas as BlendColors que alcançam pelo menos um texto",
    )
    args = parser.parse_args()
    if not EDITOR_SOURCE.is_file():
        parser.error(f"Fonte da R7 não encontrada: {EDITOR_SOURCE}")
    editor = load_editor()
    print("# Análise de cores FLP GoW2 (somente leitura)")
    print("Nenhum WAD de entrada é gravado por este script.")
    for wad_path in args.wads:
        if not wad_path.is_file():
            print(f"\n## {wad_path}\n- Arquivo não encontrado.")
            continue
        report_wad(editor, wad_path, args.all_animation_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
