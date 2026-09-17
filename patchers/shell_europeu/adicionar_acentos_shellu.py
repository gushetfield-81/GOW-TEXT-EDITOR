"""
Adiciona os acentos com til (Ã Õ ã õ) na fonte do menu do R_SHELLU.WAD
(GoW2 europeu — slot inglês britânico), mesma técnica validada do R_SHELLA:

  1. FLP_ShellU: 4 novos glifos (132..135 = ã Ã õ Õ), widths do PERMA
     (627/759/660/792 — iguais às letras base), char_map atualizado.
  2. MDL_ShellU_0: 4 novos parts (180..183) = clones dos parts das letras
     base (a=59, A=33, o=73, O=47) com o raw (UV+XY) dos tiles de til do
     PERMA (parts 410..413), joint da letra base no SHELLU (60/34/74/48)
     e UVs REALOCADOS para as células-vítimas (a atlas europeia tem
     empacotamento diferente da americana!).
  3. GFX_GodOfWarEurope: os desenhos completos (letra+til) do PERMA são
     pintados nas células-vítimas do atlas do SHELLU.

  VÍTIMAS (acentos que PT-BR de menus nunca usa — encaixe exato):
     ã (20x21) <- ñ  (sym 123, célula 123,83)   char_map[0xF1] = -1
     Ã (25x25) <- Ä  (sym  90, célula   1,30)   char_map[0xC4] = -1
     õ (21x20) <- ö  (sym 127, célula  70,109)  char_map[0xF6] = -1
     Õ (26x25) <- Ö  (sym 104, célula 158,  1)  char_map[0xD6] = -1

Saida: R_SHELLU_PTBR.WAD (o original nao e alterado).
Requisitos na mesma pasta: flp_gow2.py, gow_text_editor.py e o
R_PERMA.WAD (fonte dos tiles com til) + R_SHELLU.WAD (alvo).
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gow_text_editor import WadFile  # noqa: E402

U16 = lambda b, o: struct.unpack_from("<H", b, o)[0]
U16S = lambda b, o: struct.unpack_from("<h", b, o)[0]
U32 = lambda b, o: struct.unpack_from("<I", b, o)[0]

TILDES = [(0xE3, 0x61), (0xC3, 0x41), (0xF5, 0x6F), (0xD5, 0x4F)]
WIDTHS_PERMA = {0xE3: 627, 0xC3: 759, 0xF5: 660, 0xD5: 792}
PERMA_GLYPH_PARTS = {0xE3: 410, 0xC3: 411, 0xF5: 412, 0xD5: 413}
GFX_NAME = "GFX_GodOfWarEurope"

# vitimas: char -> (simbolo, celula (x0,y0,x1,y1))
VITIMAS = {0xF1: (123, (123, 83, 142, 103)),   # ñ
           0xC4: (90,  (1, 30, 25, 54)),       # Ä
           0xF6: (127, (70, 109, 90, 128)),    # ö
           0xD6: (104, (158, 1, 183, 25))}     # Ö

# til -> char vitima que cede a celula
VITIMA_DE = {0xE3: 0xF1, 0xC3: 0xC4, 0xF5: 0xF6, 0xD5: 0xD6}

# celulas dos tiles no atlas do PERMA (medidas dos parts 410-413)
PERMA_CELLS = {0xE3: (149, 84, 168, 104), 0xC3: (28, 30, 52, 54),
               0xF5: (93, 110, 113, 129), 0xD5: (186, 1, 211, 25)}


def gfx_decode_indexes(buf):
    w, h, enc, bpi, n = struct.unpack_from("<IIIII", buf, 4)
    rh = h // n
    assert bpi == 4, "atlas esperada em 4bpp"
    data = buf[24:24 + w * rh * bpi // 8]
    grid = [[0] * w for _ in range(rh)]
    for y in range(rh):
        base = y * w
        for x in range(w):
            v = data[(base + x) // 2]
            grid[y][x] = (v & 0xF) if (x & 1) == 0 else (v >> 4)
    return w, rh, grid


def gfx_encode_indexes(w, rh, grid):
    out = bytearray(w * rh // 2)
    for y in range(rh):
        base = y * w
        for x in range(w):
            v = grid[y][x] & 0xF
            if (x & 1) == 0:
                out[(base + x) // 2] |= v
            else:
                out[(base + x) // 2] |= v << 4
    return bytes(out)


class MeshGow2:
    def __init__(self, buf):
        self.buf = bytes(buf)
        assert U32(self.buf, 0) == 0x0001000F
        self.comment_start = U32(self.buf, 4)
        self.parts_count = U16(self.buf, 8)
        self.offsets = [U32(self.buf, 0x18 + 4 * i) for i in range(self.parts_count)]
        self.header = bytearray(self.buf[:0x18])
        self.parts_data = self.buf[self.offsets[0]:self.comment_start]
        self.tail = self.buf[self.comment_start:]

    def part_bytes(self, idx):
        start = self.offsets[idx]
        end = self.offsets[idx + 1] if idx + 1 < self.parts_count else self.comment_start
        return bytearray(self.buf[start:end])

    def part_raw(self, idx):
        block = self.part_bytes(idx)
        ng = U16(block, 2)
        joint_id = U16(block, 4 + ng * 4)
        gb = U32(block, 4)
        obj = gb + U32(block, gb + 8)
        obj_end = len(block) - U16(block, obj + 0xA) * 4
        raw = block[obj + 0x20:obj_end]
        return raw, joint_id

    def with_appended_parts(self, new_parts):
        sizes = {len(p) for p in new_parts}
        assert len(sizes) == 1, "parts novos devem ter o mesmo tamanho"
        nparts = self.parts_count + len(new_parts)
        head = bytearray(self.header)
        struct.pack_into("<H", head, 8, nparts)
        base = 0x18 + nparts * 4
        table = bytearray()
        for i in range(self.parts_count):
            table += struct.pack("<I", self.offsets[i] + 4 * len(new_parts))
        cursor = base + len(self.parts_data)
        for p in new_parts:
            table += struct.pack("<I", cursor)
            cursor += len(p)
        new_comment = self.comment_start + 4 * len(new_parts) + sum(len(p) for p in new_parts)
        struct.pack_into("<I", head, 4, new_comment)
        return bytes(head) + bytes(table) + self.parts_data + b"".join(new_parts) + self.tail


def main():
    aqui = Path(__file__).resolve().parent
    shell_path = aqui / "R_SHELLU.WAD"
    perma_path = aqui / "R_PERMA.WAD"
    saida = aqui / "R_SHELLU_PTBR.WAD"
    if not shell_path.exists():
        shell_path = Path("/home/user/uploads/R_SHELLU.WAD.txt")
    if not perma_path.exists():
        perma_path = Path("/home/user/uploads/R_PERMA.WAD.txt")

    print("== 1. carregando WADs ==")
    shell = WadFile.load(shell_path)
    perma = WadFile.load(perma_path)
    tag = lambda wad, name: next(t for t in wad.tags if t.name == name)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from flp_gow2 import FLP

    flp_shell = FLP(bytes(tag(shell, "FLP_ShellU").data))
    flp_perma = FLP(bytes(tag(perma, "FLP_HUDA").data))
    mesh = MeshGow2(bytes(tag(shell, "MDL_ShellU_0").data))
    perma_mesh = MeshGow2(bytes(tag(perma, "MDL_HUDA_0").data))
    f = flp_shell.fonts[0]
    assert f.flags & 1, "char_map de 256 entradas necessario"
    assert f.chars_count == 132 and mesh.parts_count == 180

    print("== 2. conferindo vitimas (células exclusivas?) ==")
    def uv_rect(mesh_obj, part_idx):
        raw, _ = mesh_obj.part_raw(part_idx)
        us = [struct.unpack_from("<h", raw, 0x38 + i * 4)[0] for i in range(4)]
        vs = [struct.unpack_from("<h", raw, 0x3A + i * 4)[0] for i in range(4)]
        return (min(us) // 16, min(vs) // 16, max(us) // 16, max(vs) // 16)
    rects = [uv_rect(mesh, f.mesh_refs[s][0]) for s in range(132)]
    for ch, (sym, (vx0, vy0, vx1, vy1)) in VITIMAS.items():
        real = rects[sym]
        assert real == (vx0, vy0, vx1, vy1), f"celula da vitima {ch:#x} mudou: {real}"
        for s2, r2 in enumerate(rects):
            if s2 == sym:
                continue
            assert r2[2] < vx0 or r2[0] > vx1 or r2[3] < vy0 or r2[1] > vy1, \
                f"vitima {ch:#x} compartilha pixels com o glifo {s2}"
    print("   ok: 4 vitimas exclusivas e nas posicoes esperadas")

    print("== 3. FLP_ShellU: novos glifos e char_map ==")
    glyph_ids = {}
    for k, (ch, _base) in enumerate(TILDES):
        gid = f.chars_count
        f.mesh_refs.append((180 + k, 1))
        f.mats.append((0xFFFFFFFF, 0))
        f.symbol_widths.append(WIDTHS_PERMA[ch])
        f.char_map[ch] = gid
        f.chars_count += 1
        glyph_ids[ch] = gid
    # vitimas saem do mapa (seus chars nao podem renderizar os tiles emprestados)
    for ch, (sym, _cell) in VITIMAS.items():
        assert f.char_map[ch] == sym
        f.char_map[ch] = -1
    flp_novo = flp_shell.build()
    print(f"   glifos: 132 -> {f.chars_count} | ã=132 Ã=133 õ=134 Õ=135 | ñ Ä ö Ö -> -1")

    print("== 4. MDL_ShellU_0: clones com raw do PERMA + UV realocado ==")
    novos = []
    for (ch, base_ch), k in zip(TILDES, range(4)):
        base_glyph_id = 56 if ch == 0xE3 else 30 if ch == 0xC3 else 70 if ch == 0xF5 else 44
        base_part = flp_u_part = f.mesh_refs[base_glyph_id][0]
        bloco = mesh.part_bytes(base_part)
        raw_tilde, _ = perma_mesh.part_raw(PERMA_GLYPH_PARTS[ch])
        _, shell_joint = mesh.part_raw(base_part)
        raw_novo = bytearray(raw_tilde)
        struct.pack_into("<I", raw_novo, 0x20, shell_joint)
        # UV realocado: delta = celula da vitima - celula original no PERMA
        px0, py0, px1, py1 = PERMA_CELLS[ch]
        vx0, vy0, vx1, vy1 = VITIMAS[VITIMA_DE[ch]][1]
        dx, dy = vx0 - px0, vy0 - py0
        for i in range(4):
            u = U16S(raw_novo, 0x38 + i * 4)
            v = U16S(raw_novo, 0x3A + i * 4)
            struct.pack_into("<hh", raw_novo, 0x38 + i * 4, u + dx * 16, v + dy * 16)
        ng = U16(bloco, 2)
        gb = U32(bloco, 4)
        obj = gb + U32(bloco, gb + 8)
        obj_end = len(bloco) - U16(bloco, obj + 0xA) * 4
        assert len(raw_novo) == obj_end - (obj + 0x20), "tamanho de raw divergente"
        bloco[obj + 0x20:obj_end] = raw_novo
        novos.append(bytes(bloco))
        print(f"   {chr(ch)}: glyph {glyph_ids[ch]} <- part {180 + k} "
              f"(clone do part {base_part}, joint {shell_joint}, UV delta {dx},{dy})")
    mdl_novo = mesh.with_appended_parts(novos)
    print(f"   MDL: {len(mesh.buf):,} -> {len(mdl_novo):,} bytes")

    print("== 5. GFX: pintando os tiles nas células-vítimas ==")
    gfx_shell = bytes(tag(shell, GFX_NAME).data)
    gfx_perma = bytes(tag(perma, GFX_NAME).data)
    w, rh, grid_s = gfx_decode_indexes(gfx_shell)
    _, _, grid_p = gfx_decode_indexes(gfx_perma)
    for (ch, _base) in TILDES:
        sx0, sy0, sx1, sy1 = PERMA_CELLS[ch]
        dx0, dy0, dx1, dy1 = VITIMAS[VITIMA_DE[ch]][1]
        tw, th = sx1 - sx0 + 1, sy1 - sy0 + 1
        dw, dh = dx1 - dx0 + 1, dy1 - dy0 + 1
        assert (tw, th) == (dw, dh), f"tile {ch:#x}: dims {tw}x{th} vs celula {dw}x{dh}"
        for j in range(th):
            for i in range(tw):
                grid_s[dy0 + j][dx0 + i] = grid_p[sy0 + j][sx0 + i]
        print(f"   {chr(ch)}: tile PERMA ({sx0},{sy0}) {tw}x{th} -> celula ({dx0},{dy0})")
    gfx_novo = gfx_shell[:24] + gfx_encode_indexes(w, rh, grid_s)

    print("== 6. montando o WAD ==")
    tag(shell, "FLP_ShellU").data = flp_novo
    tag(shell, "MDL_ShellU_0").data = mdl_novo
    tag(shell, GFX_NAME).data = gfx_novo
    saida.write_bytes(shell.serialize())
    import hashlib
    print(f"OK: {saida.name} ({saida.stat().st_size:,} bytes)")
    print("SHA-256:", hashlib.sha256(saida.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
