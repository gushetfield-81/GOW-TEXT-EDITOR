"""Parser/marshal FLP (GoW2) portado de god_of_war_browser/pack/wad/flp.

Layout validado contra FLP_ShellA de R_SHELLA.WAD:
  header 0x5c; counts @ 0x38..0x56;
  ordem: globalHandlers(4B) -> refs headers(8B) -> refs materiais(8B)
         -> font headers(0x24) -> [font refs headers(8B) + font refs materiais(8B)
         + symbol widths(2B) pad4 + char map(2B) pad4] -> static -> dynamic
         -> datas6 -> datas7 -> data8 -> transformations -> blendColors
         -> strings
"""
import struct

HDR = 0x5C
DATA1, DATA2, DATA2MAT, DATA3, DATA4, DATA5, DATA6 = 4, 8, 8, 0x24, 0x1C, 0x20, 0xC

u16 = lambda b, o: struct.unpack_from("<H", b, o)[0]
u16s = lambda b, o: struct.unpack_from("<h", b, o)[0]
u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
p4 = lambda n: (n + 3) & ~3


class Font:
    def __init__(self):
        self.chars_count = 0
        self.float020 = 0.0
        self.unk04 = self.size = self.unk08 = self.unk0a = self.flags = 0
        self.header_raw = bytearray(0x24)
        self.mesh_refs = []   # [(meshPartIndex, matCount)]
        self.mats = []        # [(color, stringOffset)] achatado na ordem
        self.symbol_widths = []
        self.char_map = []


class FLP:
    def __init__(self, buf):
        self.buf = bytes(buf)
        b = self.buf
        self.unk04 = u32(b, 0x30)
        self.unk08 = u32(b, 0x34)
        self.gh_count = u32(b, 0x38)
        self.ref_count = u32(b, 0x3C)
        self.static_count = u32(b, 0x44)
        self.dynamic_count = u32(b, 0x48)
        self.d6_count = u32(b, 0x4C)
        self.d7_count = u32(b, 0x50)
        self.trans_count = u16(b, 0x54)
        self.blend_count = u16(b, 0x56)
        self.strings_size = u32(b, 0x58)

        pos = HDR
        self.gh = [b[pos + i*4: pos + i*4 + 4] for i in range(self.gh_count)]
        pos += self.gh_count * DATA1
        # refs: headers juntos, depois materiais juntos
        self.refs = []
        for i in range(self.ref_count):
            self.refs.append((u16s(b, pos + 4), u16(b, pos + 6)))
            pos += DATA2
        self.ref_mats = []
        for i in range(sum(mc for _, mc in self.refs)):
            self.ref_mats.append(struct.unpack_from("<II", b, pos))
            pos += DATA2MAT
        self.after_refs_pos = pos

        # fontes
        self.fonts = []
        for i in range(u32(b, 0x40)):
            f = Font()
            f.header_raw = bytearray(b[pos:pos + DATA3])
            f.chars_count = u32(b, pos + 0x10)
            f.float020 = struct.unpack_from("<f", b, pos + 0x14)[0]
            f.unk04 = u16(b, pos + 0x18)
            f.size = u16s(b, pos + 0x1A)
            f.unk08 = u16(b, pos + 0x1C)
            f.unk0a = u16(b, pos + 0x1E)
            f.flags = u16(b, pos + 0x20)
            pos += DATA3
            if f.flags & (2 | 4):
                for j in range(f.chars_count):
                    f.mesh_refs.append((u16s(b, pos + 4), u16(b, pos + 6)))
                    pos += DATA2
                for j in range(sum(mc for _, mc in f.mesh_refs)):
                    f.mats.append(struct.unpack_from("<II", b, pos))
                    pos += DATA2MAT
            f.symbol_widths = list(struct.unpack_from("<%dh" % f.chars_count, b, pos))
            pos += 2 * f.chars_count
            pos = p4(pos)
            mlen = 0x100 if (f.flags & 1) else f.chars_count
            f.char_map = list(struct.unpack_from("<%dh" % mlen, b, pos))
            pos += 2 * mlen
            pos = p4(pos)
            self.fonts.append(f)
        self.after_fonts_pos = pos
        self.font_blob_start = self.after_refs_pos
        self.tail = b[self.after_fonts_pos:]  # static..blend (strings viram à parte)

    # ---------- marshal ----------
    def font_bytes(self, f):
        out = bytearray(f.header_raw)
        struct.pack_into("<I", out, 0x10, f.chars_count)
        struct.pack_into("<f", out, 0x14, f.float020)
        struct.pack_into("<H", out, 0x18, f.unk04)
        struct.pack_into("<h", out, 0x1A, f.size)
        struct.pack_into("<H", out, 0x1C, f.unk08)
        struct.pack_into("<H", out, 0x1E, f.unk0a)
        struct.pack_into("<H", out, 0x20, f.flags)
        if f.flags & (2 | 4):
            for mpi, mc in f.mesh_refs:
                out += b"\x00" * 4 + struct.pack("<hH", mpi, mc)
            for color, soff in f.mats:
                out += struct.pack("<II", color, soff)
        out += struct.pack("<%dh" % len(f.symbol_widths), *f.symbol_widths)
        out += b"\x00" * ((-len(out)) % 4)
        out += struct.pack("<%dh" % len(f.char_map), *f.char_map)
        out += b"\x00" * ((-len(out)) % 4)
        return bytes(out)

    def build(self, fonts=None):
        fonts = fonts if fonts is not None else self.fonts
        out = bytearray(self.buf[:HDR])
        struct.pack_into("<I", out, 0x38, len(self.gh))
        struct.pack_into("<I", out, 0x3C, len(self.refs))
        struct.pack_into("<I", out, 0x40, len(fonts))
        for gh in self.gh:
            out += gh
        for mpi, mc in self.refs:
            out += b"\x00" * 4 + struct.pack("<hH", mpi, mc)
        for color, soff in self.ref_mats:
            out += struct.pack("<II", color, soff)
        for f in fonts:
            out += self.font_bytes(f)
        out += self.tail
        return bytes(out)


def add_glyphs(flp, flp_index, new_glyphs):
    """new_glyphs: lista de dicts {width:int, mesh_part:int, tex_string_off:int}.

    Adiciona glyphs no fim e devolve lista de novos glyph ids.
    Pressupoe char_map de 256 entradas (flags & 1).
    """
    f = flp.fonts[flp_index]
    assert f.flags & 1, "char map de 256 entradas obrigatorio"
    ids = []
    for g in new_glyphs:
        gid = f.chars_count
        f.mesh_refs.append((g["mesh_part"], 1))
        f.mats.append((0xFFFFFFFF, g["tex_string_off"]))
        f.symbol_widths.append(g["width"])
        f.char_map[g["char"]] = gid
        f.chars_count += 1
        ids.append(gid)
    return ids
