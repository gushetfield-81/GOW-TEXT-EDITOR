"""
Patch "Total PlayTime" -> PT-BR no R_PERMA.WAD (God of War 1, tela STATUS).

MISTERIO RESOLVIDO (2026-09-16):
  "Total PlayTime" NAO e texto do jogo (nao esta no MSGS_TXT). E um
  StaticLabel (texto "assado") do filme Flash FLP_HUDA: uma lista de
  comandos que desenham glifos FIXOS (id+largura) da fonte Europeia.
  Por isso editar o *4601* ("Tempo Total Jogado") do MSGS nunca surtiu
  efeito: essa entrada nao e usada neste rotulo.

  O patch substitui, DENTRO do FLP_HUDA, a lista de glifos do rotulo
  [1] pela nova palavra (mesma fonte, mesmas larguras naturais).
  Todas as letras necessarias existem na fonte (inclusive cedilha e til,
  caso queira "Duracao do Jogo" com acentos).

USO:
  python patch_total_playtime.py                     -> "Tempo de Jogo"
  python patch_total_playtime.py "Duracao do Jogo"   -> texto livre

Requisitos na mesma pasta: flp_gow2.py e gow_text_editor.py
Saida: R_PERMA_TTJ.WAD (o original nao e alterado).
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flp_gow2 import FLP, u16, u16s, u32  # noqa: E402
from gow_text_editor import WadFile  # noqa: E402

LABEL_INDEX = 1  # [0]="/10"  [1]="Total PlayTime"  [2]=triangulo  [3]=R1


def parse_commands(buf):
    cmds, cur, i = [], None, 0
    while i < len(buf):
        op = buf[i]; i += 1
        if op & 0x80:
            cur = {"flags": op & 0x7F, "font": None, "scale": None, "color": None,
                   "x": None, "y": None, "glyphs": []}
            cmds.append(cur)
            if op & 8:
                cur["font"] = u16(buf, i); cur["scale"] = u16s(buf, i + 2) / 1024.0; i += 4
            if op & 4:
                cur["color"] = bytes(buf[i:i + 4]); i += 4
            if op & 2:
                cur["x"] = u16s(buf, i) / 16.0; i += 2
            if op & 1:
                cur["y"] = u16s(buf, i) / 16.0; i += 2
        else:
            for _ in range(op):
                cur["glyphs"].append([u16(buf, i), u16s(buf, i + 2) / 16.0]); i += 4
    return cmds


def decode(data, flp, ids):
    inv = {}
    for c, s in enumerate(flp.fonts[0].char_map):
        if s >= 0:
            inv.setdefault(s, c)
    return "".join(chr(inv[g]) if g in inv and 32 <= inv[g] < 127 else f"<{g}>" for g in ids)


def static_streams(flp, total):
    pos = flp.after_fonts_pos
    hdrs, streams = [], []
    for _ in range(flp.static_count):
        hdrs.append(pos); pos += 0x1C
    for h in hdrs:
        size = u32(total, h + 0x18)
        streams.append((h, pos, size))
        pos = (pos + size + 3) & ~3
    return hdrs, streams, pos  # pos = fim do bloco statics


def patch_flp(flp_data: bytes, novo_texto: str) -> bytes:
    flp = FLP(flp_data)
    font = flp.fonts[0]
    cm = font.char_map
    widths = font.symbol_widths

    hdrs, streams, end_all = static_streams(flp, flp_data)
    hdr, s1, size1 = streams[LABEL_INDEX]
    cmds = parse_commands(flp_data[s1:s1 + size1])
    velho_ids = [g for c in cmds for g, w in c["glyphs"]]
    print(f"  rotulo atual: {decode(flp_data, flp, velho_ids)!r}")

    # LARGURAS: a width do comando NAO e a largura natural da fonte; e o avanco
    # ja na escala do filme (~1/3 da natural neste rotulo). Derivar do original:
    old_pairs = [(g, w) for c in cmds for g, w in c["glyphs"]]
    known = {}
    so = sn = 0.0
    for g, w in old_pairs:
        known[g] = w
        so += w
        sn += widths[g] / 16.0
    fator = (so / sn) if sn else 1.0
    print(f"  fator de escala do rotulo original: {fator:.5f} (largura original {so:.1f})")

    novos = []
    for ch in novo_texto:
        s = cm[ord(ch)]
        if ch == " ":
            s = 0
        if s < 0:
            raise SystemExit(f"  ERRO: o caractere {ch!r} nao existe na fonte do rotulo.")
        w = known.get(s)
        if w is None:
            w = widths[s] / 16.0 * fator
        novos.append((s, w))
    nova_largura = sum(w for _, w in novos)
    print(f"  novo rotulo : {decode(flp_data, flp, [g for g, w in novos])!r} ({len(novos)} glifos, largura {nova_largura:.1f} vs {so:.1f} do original)")

    hdr0 = cmds[0]
    f = hdr0["flags"]
    b = bytearray([0x80 | f])
    if f & 8:
        b += struct.pack("<Hh", hdr0["font"], int(round(hdr0["scale"] * 1024)))
    if f & 4:
        b += hdr0["color"]
    if f & 2:
        b += struct.pack("<h", int(round(hdr0["x"] * 16)))
    if f & 1:
        b += struct.pack("<h", int(round(hdr0["y"] * 16)))
    while len(novos) > 255:
        b.append(255)
        for g, w in novos[:255]:
            b += struct.pack("<Hh", g, int(round(w * 16)))
        novos = novos[255:]
    b.append(len(novos))
    for g, w in novos:
        b += struct.pack("<Hh", g, int(round(w * 16)))
    novo_stream = bytes(b)
    novo_stream += b"\x00" * ((-len(novo_stream)) % 4)

    old_sizes = [u32(flp_data, h + 0x18) for h in hdrs]
    new_sizes = [sz + (len(novo_stream) - size1 if i == LABEL_INDEX else 0)
                 for i, sz in enumerate(old_sizes)]

    bloco = bytearray()
    for i, h in enumerate(hdrs):
        hb = bytearray(flp_data[h:h + 0x1C])
        struct.pack_into("<I", hb, 0x18, new_sizes[i])
        bloco += hb
    for i, (h, s, sz) in enumerate(streams):
        raw = novo_stream if i == LABEL_INDEX else flp_data[s:s + sz]
        bloco += raw
        if i != LABEL_INDEX:
            bloco += b"\x00" * ((-sz) % 4)

    out = bytearray(flp_data)
    out[hdrs[0]:end_all] = bloco

    # validacao: reparse
    flp2 = FLP(bytes(out))
    hdrs2, streams2, _ = static_streams(flp2, bytes(out))
    for i, (h, s, sz) in enumerate(streams2):
        cs = parse_commands(bytes(out[s:s + sz]))
        ids = [g for c in cs for g, w in c["glyphs"]]
        print(f"  reparse [{i}]: {decode(bytes(out), flp2, ids)!r}")
    return bytes(out)


def main():
    aqui = Path(__file__).resolve().parent
    texto = sys.argv[1] if len(sys.argv) > 1 else "Tempo de Jogo"

    wad_path = aqui / "R_PERMA.WAD"
    if not wad_path.exists():
        alt = Path("/home/user/uploads/R_PERMA.WAD.txt")
        wad_path = alt if alt.exists() else None
    if wad_path is None:
        raise SystemExit("Coloque o R_PERMA.WAD na mesma pasta deste script.")

    print("== patch Total PlayTime ==")
    print("== 1. carregando", wad_path.name, "==")
    wad = WadFile.load(wad_path)
    tag = next(t for t in wad.tags if t.name == "FLP_HUDA")

    print("== 2. patch do rotulo estatico [1] ==")
    tag.data = patch_flp(bytes(tag.data), texto)

    saida = aqui / "R_PERMA_TTJ.WAD"
    print("== 3. gravando", saida.name, "==")
    saida.write_bytes(wad.serialize())
    import hashlib
    h = hashlib.sha256(saida.read_bytes()).hexdigest()
    print(f"OK: {saida.name} ({saida.stat().st_size:,} bytes)")
    print(f"SHA-256: {h}")


if __name__ == "__main__":
    main()
