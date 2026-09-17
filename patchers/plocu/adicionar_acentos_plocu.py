"""
PLOCU v2 — acentos (ã Ã õ Õ) na fonte de GAMEPLAY/HUD (FLP_HUDU) + mensagens 36-45.

O R_PLOCU europeu carrega a fonte que o jogo usa em GAMEPLAY (legendas, HUD,
banners de pausa como "Opções"/"Status", status das urnas). Ela não tinha os
4 glifos com til — mesma doença que o shell tinha. Aplica o MESMO esquema de
células-vítima validado no SHELLU (ñ/Ä/ö/Ö cedem as células, encaixe exato).

Além da fonte, recoloca as mensagens *36*..*45* (únicos IDs do set americano
ausentes do europeu) com os textos do usuário — se a exec européia consultar
esses IDs (ex.: status das urnas), agora encontra texto.

Entrada : uploads/R_PLOCU.WAD.txt (merge S8 do usuario) + uploads/R_PERMA.WAD.txt
Saída   : saida_plocu/R_PLOCU_PTBR.WAD (v2)
"""
import struct, sys, re, hashlib
from pathlib import Path

sys.path.insert(0, "/home/user/work/tool/GodOfWarTextEditor_Aprimorado_2026-09-12")
sys.path.insert(0, "/home/user/saida_shellu")
from gow_text_editor import WadFile
from flp_gow2 import FLP
from adicionar_acentos_shellu import MeshGow2, gfx_decode_indexes, gfx_encode_indexes

U16 = lambda b, o: struct.unpack_from("<H", b, o)[0]
U16S = lambda b, o: struct.unpack_from("<h", b, o)[0]
U32 = lambda b, o: struct.unpack_from("<I", b, o)[0]

TILDES = [(0xE3, 0x61), (0xC3, 0x41), (0xF5, 0x6F), (0xD5, 0x4F)]  # (char, letra base)
WIDTHS = {0xE3: 627, 0xC3: 759, 0xF5: 660, 0xD5: 792}
PERMA_PARTS = {0xE3: 410, 0xC3: 411, 0xF5: 412, 0xD5: 413}   # tiles no PERMA
PERMA_CELLS = {0xE3: (149, 84, 168, 104), 0xC3: (28, 30, 52, 54),
               0xF5: (93, 110, 113, 129), 0xD5: (186, 1, 211, 25)}
# vitimas no HUDU (mesmas celulas do shell — mesma atlas EU), indexadas pelo TIL:
# valor = (simbolo da vitima, celula) ; a vitima que cede a celula do til X:
VITIMA_DE = {0xE3: 0xF1, 0xC3: 0xC4, 0xF5: 0xF6, 0xD5: 0xD6}  # ã<-ñ Ã<-Ä õ<-ö Õ<-Ö
VITIMAS = {0xE3: (123, (123, 83, 142, 103)), 0xC3: (90, (1, 30, 25, 54)),
           0xF5: (127, (70, 109, 90, 128)), 0xD5: (104, (158, 1, 183, 25))}
GFX_NAME = "GFX_GodOfWarEurope"


def main():
    perma = WadFile.load("/home/user/uploads/R_PERMA.WAD.txt")
    plocu = WadFile.load("/home/user/uploads/R_PLOCU.WAD.txt")
    tg = lambda w, n: bytes(next(t for t in w.tags if t.name == n).data)

    print("== 1. conferindo vitimas no HUDU ==")
    flp = FLP(tg(plocu, "FLP_HUDU"))
    f = flp.fonts[0]
    mdl = MeshGow2(tg(plocu, "MDL_HUDU_0"))
    perma_mdl = MeshGow2(tg(perma, "MDL_HUDA_0"))
    assert f.chars_count == 132 and mdl.parts_count == 410

    def uv_rect(mesh, part_idx):
        raw, _ = mesh.part_raw(part_idx)
        us = [U16S(raw, 0x38 + i * 4) // 16 for i in range(4)]
        vs = [U16S(raw, 0x3A + i * 4) // 16 for i in range(4)]
        return (min(us), min(vs), max(us), max(vs))

    rects = [uv_rect(mdl, f.mesh_refs[s][0]) for s in range(132)]
    for ch, (sym, cell) in VITIMAS.items():
        assert rects[sym] == cell, f"celula da vitima {ch:#x} mudou: {rects[sym]}"
        for s2, r2 in enumerate(rects):
            if s2 != sym:
                assert r2[2] < cell[0] or r2[0] > cell[2] or r2[3] < cell[1] or r2[1] > cell[3], \
                    f"vitima {ch:#x} colide com glifo {s2}"
    print("   ok: ñ Ä ö Ö exclusivos e nas posições esperadas")

    print("== 2. FLP_HUDU: glifos 132-135 ==")
    for k, (ch, _base) in enumerate(TILDES):
        gid = f.chars_count
        f.mesh_refs.append((410 + k, 1))
        f.mats.append((0xFFFFFFFF, 0))
        f.symbol_widths.append(WIDTHS[ch])
        f.char_map[ch] = gid
        f.chars_count += 1
    for til, vit in VITIMA_DE.items():
        assert f.char_map[vit] == VITIMAS[til][0]
        f.char_map[vit] = -1
    flp_novo = flp.build()
    print(f"   glifos 132->136 | ã=132 Ã=133 õ=134 Õ=135 | ñ Ä ö Ö -> -1")

    print("== 3. MDL_HUDU_0: parts 410-413 (clone da letra + raw PERMA + UV realocado) ==")
    novos = []
    for (ch, base_ch), k in zip(TILDES, range(4)):
        base_glyph = f.char_map[base_ch] if f.char_map[base_ch] >= 0 else {0x61: 56, 0x41: 30, 0x6F: 70, 0x4F: 44}[base_ch]
        base_part = {0x61: 61, 0x41: 35, 0x6F: 75, 0x4F: 49}[base_ch]
        bloco = mdl.part_bytes(base_part)
        raw_tilde, _ = perma_mdl.part_raw(PERMA_PARTS[ch])
        _, joint = mdl.part_raw(base_part)
        raw_novo = bytearray(raw_tilde)
        struct.pack_into("<I", raw_novo, 0x20, joint)
        px0, py0, _, _ = PERMA_CELLS[ch]
        vx0, vy0, _, _ = VITIMAS[ch][1]
        dx, dy = vx0 - px0, vy0 - py0
        for i in range(4):
            u, v = U16S(raw_novo, 0x38 + i * 4), U16S(raw_novo, 0x3A + i * 4)
            struct.pack_into("<hh", raw_novo, 0x38 + i * 4, u + dx * 16, v + dy * 16)
        ng = U16(bloco, 2)
        gb = U32(bloco, 4)
        obj = gb + U32(bloco, gb + 8)
        obj_end = len(bloco) - U16(bloco, obj + 0xA) * 4
        assert len(raw_novo) == obj_end - (obj + 0x20), f"raw divergente em {ch:#x}"
        bloco[obj + 0x20:obj_end] = raw_novo
        novos.append(bytes(bloco))
        print(f"   {chr(ch)}: part {410+k} <- clone do part {base_part}, joint {joint}, UV Δ {dx},{dy}")
    mdl_novo = mdl.with_appended_parts(novos)
    print(f"   MDL: {len(mdl.buf):,} -> {len(mdl_novo):,} B (parts 410 -> 414)")

    print("== 4. GFX: pintando tiles nas células-vítimas ==")
    w, rh, grid = gfx_decode_indexes(tg(plocu, GFX_NAME))
    _, _, grid_p = gfx_decode_indexes(tg(perma, GFX_NAME))
    for ch, _b in TILDES:
        sx0, sy0, sx1, sy1 = PERMA_CELLS[ch]
        dx0, dy0, dx1, dy1 = VITIMAS[ch][1]
        for j in range(sy1 - sy0 + 1):
            for i in range(sx1 - sx0 + 1):
                grid[dy0 + j][dx0 + i] = grid_p[sy0 + j][sx0 + i]
    gfx_novo = tg(plocu, GFX_NAME)[:24] + gfx_encode_indexes(w, rh, grid)
    print("   4 tiles pintados (ñ Ä ö Ö)")

    print("== 5. MSGS_TXT: recolocando *36*..*45* ==")
    raw_perma = tg(perma, "MSGS_TXT").decode("utf-8")
    raw_plocu = tg(plocu, "MSGS_TXT").decode("utf-8")
    todas = [(m.start(), int(m.group(1))) for m in re.finditer(r'\*(\d+)\*', raw_perma)]
    segmentos = []
    for idx, (s, i) in enumerate(todas):
        fim = todas[idx + 1][0] if idx + 1 < len(todas) else len(raw_perma)
        if 36 <= i <= 45:
            segmentos.append((i, raw_perma[s:fim]))
    assert len(segmentos) == 10, segmentos
    m_fim = re.search(r'[\x00]+$', raw_plocu)
    cauda = m_fim.group(0) if m_fim else ""
    corpo = raw_plocu[:len(raw_plocu) - len(cauda)]
    assert all(ord(c) == 0 for c in cauda)
    msgs_novo = corpo + "".join(s for _i, s in sorted(segmentos)) + cauda
    msgs_novo_b = msgs_novo.encode("utf-8")
    print(f"   MSGS: {len(raw_plocu.encode('utf-8')):,} -> {len(msgs_novo_b):,} B (+10 mensagens)")

    print("== 6. montando WAD ==")
    tag = lambda n: next(t for t in plocu.tags if t.name == n)
    tag("FLP_HUDU").data = flp_novo
    tag("MDL_HUDU_0").data = mdl_novo
    tag(GFX_NAME).data = gfx_novo
    tag("MSGS_TXT").data = msgs_novo_b
    saida = Path("/home/user/saida_plocu/R_PLOCU_PTBR.WAD")
    saida.write_bytes(plocu.serialize())
    print(f"OK: {saida} ({saida.stat().st_size:,} B)")
    print("SHA-256:", hashlib.sha256(saida.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
