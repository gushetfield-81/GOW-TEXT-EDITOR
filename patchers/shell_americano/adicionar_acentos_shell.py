"""Adiciona os acentos com til (Ã Õ ã õ) na fonte do menu (R_SHELLA.WAD).

Tecnica (espelha o que a fonte europeia do R_PERMA ja faz, validada em jogo):
  1. FLP_ShellA: 4 novos glifos (132..135) com larguras copiadas do PERMA e
     char_map[0xE3/0xC3/0xF5/0xD5] apontando para eles.
  2. MDL_ShellA_0: 4 novos parts (180..183), cada um clone do part da letra
     base (a, A, o, O) com o programa DMA (XY/UV) do glifo com til do PERMA;
     o dword da joint (raw+0x20) recebe a joint da letra base no SHELL.
  3. GFX_GodOfWarEurope: os desenhos completos (letra+til) vem da atlas do
     PERMA (mesmo tamanho/formato; as diferencas sao exatamente as celulas
     dos tiles com til — verificado antes de copiar).

O resultado e gravado como R_SHELLA_PTBR.WAD; o original nao e alterado.
"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gow_text_editor import WadFile  # noqa: E402

U16 = lambda b, o: struct.unpack_from("<H", b, o)[0]
U16S = lambda b, o: struct.unpack_from("<h", b, o)[0]
U32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
P4 = lambda n: (n + 3) & ~3

# (caractere, letra base) na mesma ordem do PERMA: ã, Ã, õ, Õ
TILDES = [(0xE3, 0x61), (0xC3, 0x41), (0xF5, 0x6F), (0xD5, 0x4F)]
WIDTHS_PERMA = {0xE3: 627, 0xC3: 759, 0xF5: 660, 0xD5: 792}
PERMA_GLYPH_PARTS = {0xE3: 410, 0xC3: 411, 0xF5: 412, 0xD5: 413}
GFX_NAME = "GFX_GodOfWarEurope"


def gfx_decode_indexes(buf):
    """Atlas da fonte e PSMT4 (4bpp) GUARDADA LINEAR (sem swizzle de GS).

    O browser (pack/wad/gfx) so aplica swizzle em PSMT8; para PSMT4 ele le
    data[(x+y*w)/2] direto — confirmado tambem empiricamente: a leitura
    linear reproduz os glifos perfeitamente.
    """
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


class MeshGow2:
    """Leitura/escrita por parts do MDL_*_0 (magic 0x0001000f)."""

    def __init__(self, buf):
        self.buf = bytes(buf)
        assert U32(self.buf, 0) == 0x0001000F
        self.comment_start = U32(self.buf, 4)
        self.parts_count = U16(self.buf, 8)
        self.offsets = [U32(self.buf, 0x18 + 4 * i) for i in range(self.parts_count)]
        self.header = bytearray(self.buf[:0x18])
        self.offset_table_region = self.buf[0x18:0x18 + self.parts_count * 4]
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
        gb = U32(block, 4)  # group[0], relativo ao inicio do part
        obj = gb + U32(block, gb + 8)  # tabela de offsets dos objetos @ gb+8
        obj_end = len(block) - U16(block, obj + 0xA) * 4
        raw = block[obj + 0x20:obj_end]
        return raw, joint_id

    def with_appended_parts(self, new_parts):
        """new_parts: lista de bytes de part (todas com o mesmo tamanho da 1a)."""
        sizes = {len(p) for p in new_parts}
        assert len(sizes) == 1, "parts novos devem ter o mesmo tamanho"
        step = sizes.pop()
        nparts = self.parts_count + len(new_parts)
        head = bytearray(self.header)
        struct.pack_into("<H", head, 8, nparts)
        base = 0x18 + nparts * 4
        table = bytearray()
        for i in range(self.parts_count):
            table += struct.pack("<I", base + sum(len(self.part_bytes(j)) for j in self._iter_parts()))
            break
        # offsets originais deslocados + 4*novos
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

    def _iter_parts(self):
        return range(self.parts_count)


def patch_flp(flp_data, perma_font):
    from flp_gow2 import FLP

    flp = FLP(flp_data)
    f = flp.fonts[0]
    assert f.flags & 1, "char_map de 256 entradas necessario"
    assert f.chars_count == 132
    part0 = f.mesh_refs[0][0]
    base_part_delta = part0 - 0  # glyph i -> part i + delta (medido do glyph 0)
    new_parts_start = 180
    glyph_ids = {}
    for k, (ch, _base) in enumerate(TILDES):
        gid = f.chars_count
        f.mesh_refs.append((new_parts_start + k, 1))
        f.mats.append((0xFFFFFFFF, 0))
        f.symbol_widths.append(WIDTHS_PERMA[ch])
        f.char_map[ch] = gid
        glyph_ids[ch] = gid
        f.chars_count += 1
    return flp.build(), glyph_ids, new_parts_start, base_part_delta


def main():
    aqui = Path(__file__).resolve().parent
    shell_path = aqui / "R_SHELLA.WAD"
    perma_path = aqui / "R_PERMA.WAD"
    saida = aqui / "R_SHELLA_PTBR.WAD"
    if not shell_path.exists():
        shell_path = Path("/home/user/uploads/R_SHELLA.WAD.txt")
    if not perma_path.exists():
        perma_path = Path("/home/user/uploads/R_PERMA.WAD.txt")

    print("== 1. carregando WADs ==")
    shell = WadFile.load(shell_path)
    perma = WadFile.load(perma_path)
    tag = lambda wad, name: next(t for t in wad.tags if t.name == name)

    print("== 2. FLP: novos glifos ==")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from flp_gow2 import FLP as FLPParser

    perma_flp = FLPParser(tag(perma, "FLP_HUDA").data)
    flp_novo, glyph_ids, parts_start, delta = patch_flp(tag(shell, "FLP_ShellA").data, perma_flp)
    print("   glyph ids:", {chr(k): v for k, v in glyph_ids.items()},
          "| parts novos:", parts_start, "..", parts_start + 3)

    print("== 3. MDL_ShellA_0: clones com UV dos tiles ==")
    mesh = MeshGow2(tag(shell, "MDL_ShellA_0").data)
    perma_mesh = MeshGow2(tag(perma, "MDL_HUDA_0").data)
    novos = []
    for (ch, base_ch), k in zip(TILDES, range(4)):
        base_glyph = perma_base = None
        shell_font = FLPParser(tag(shell, "FLP_ShellA").data).fonts[0]
        base_glyph_id = shell_font.char_map[base_ch]
        base_part = shell_font.mesh_refs[base_glyph_id][0]
        bloco = mesh.part_bytes(base_part)
        raw_tilde, _ = perma_mesh.part_raw(PERMA_GLYPH_PARTS[ch])
        _, shell_joint = mesh.part_raw(base_part)
        raw_novo = bytearray(raw_tilde)
        struct.pack_into("<I", raw_novo, 0x20, shell_joint)
        # localiza o raw dentro do bloco e substitui
        ng = U16(bloco, 2)
        gb = U32(bloco, 4)
        obj = gb + U32(bloco, gb + 8)
        obj_end = len(bloco) - U16(bloco, obj + 0xA) * 4
        assert len(raw_novo) == obj_end - (obj + 0x20), "tamanho de raw divergente"
        bloco[obj + 0x20:obj_end] = raw_novo
        novos.append(bytes(bloco))
        print(f"   {chr(ch)}: glyph {glyph_ids[ch]} <- part {parts_start + k} "
              f"(clone do part {base_part} da letra '{chr(base_ch)}', joint {shell_joint})")
    mdl_novo = mesh.with_appended_parts(novos)
    print(f"   MDL: {len(mesh.buf):,} -> {len(mdl_novo):,} bytes")

    print("== 4. GFX: transferindo os desenhos dos tiles ==")
    gfx_shell = tag(shell, GFX_NAME).data
    gfx_perma = tag(perma, GFX_NAME).data
    assert len(gfx_shell) == len(gfx_perma)
    w, rh, grid_s = gfx_decode_indexes(gfx_shell)
    _, _, grid_p = gfx_decode_indexes(gfx_perma)
    diferenças = [(x, y) for y in range(rh) for x in range(w) if grid_s[y][x] != grid_p[y][x]]

    # celulas (UV) dos 4 tiles novos + dos 132 glifos atuais do SHELL
    def uv_rects(font_parser, font):
        rects = []
        for gid in range(font.chars_count):
            mpi = font.mesh_refs[gid][0]
            raw, _ = (perma_mesh if font_parser is perma_flp else mesh).part_raw(mpi)
            us = [struct.unpack_from("<h", raw, 0x38 + i * 4)[0] for i in range(4)]
            vs = [struct.unpack_from("<h", raw, 0x3A + i * 4)[0] for i in range(4)]
            x0 = min(us) / 4096 * w; x1 = max(us) / 4096 * w
            y0 = min(vs) / 4096 * rh; y1 = max(vs) / 4096 * rh
            rects.append((gid, x0, y0, x1, y1))
        return rects

    shell_font = FLPParser(tag(shell, "FLP_ShellA").data).fonts[0]
    rects_shell = uv_rects(None, shell_font)
    rects_perma = uv_rects(perma_flp, perma_flp.fonts[0])

    dentro_tilde = 0
    fora = []
    for (x, y) in diferenças:
        ok = any(x0 - 2 <= x <= x1 + 2 and y0 - 2 <= y <= y1 + 2
                 for gid, x0, y0, x1, y1 in rects_perma if gid >= 132)
        if ok:
            dentro_tilde += 1
        else:
            fora.append((x, y))
    conflitos = []
    for (x, y) in fora:
        for gid, x0, y0, x1, y1 in rects_shell:
            if x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1:
                conflitos.append((gid, x, y))
                break
    print(f"   pixels diferentes: {len(diferenças)} | dentro dos tiles com til: {dentro_tilde} | fora: {len(fora)}")
    if conflitos:
        raise SystemExit(f"ABORTADO: diferencas da atlas dentro de glifos existentes: {conflitos[:10]}")
    gfx_novo = gfx_perma  # atlas inteira igual a do PERMA (comprovadamente seguro)

    print("== 5. montando o WAD ==")
    tag(shell, "FLP_ShellA").data = flp_novo
    tag(shell, "MDL_ShellA_0").data = mdl_novo
    tag(shell, GFX_NAME).data = gfx_novo
    wad_novo = shell.serialize()
    saida.write_bytes(wad_novo)
    print(f"   OK: {saida} ({len(wad_novo):,} bytes; original {len(shell.raw):,})")
    return saida


if __name__ == "__main__":
    main()
