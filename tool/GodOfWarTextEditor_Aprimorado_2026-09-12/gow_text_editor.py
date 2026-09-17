#!python3.14
"""God of War WAD/TXT editor.

The editor follows the physical WAD rules used by god_of_war_browser:
0x20-byte little-endian tag headers, 0x10-byte tag alignment, and an
EntityCount tag with no body.  It edits text already stored inside the WAD.

The ELF analysis added two important runtime details:

* GoW2 Flash runtime messages are exposed as MSGS_COUNT, MSGS_LINES and
  MSGS_TXT.  MSGS_COUNT/MSGS_LINES are binary metadata; MSGS_TXT is the text
  payload.  The loader adds a four-byte length prefix in memory, not in the
  on-disk WAD payload.
* The runtime accepts message markers ending in *, *H or *T, splits pages on
  --, and the examined DoMsgPage path supports at most three lines per page.

The program intentionally keeps the browser's lossless behavior for text
files: structural blank lines and marker spelling are preserved, while a
runtime-accurate diagnostic is shown separately.  Untouched WAD segments,
including non-zero padding bytes, are emitted byte-for-byte unchanged.
"""
from __future__ import annotations

import os
import re
import shutil
import struct
import tempfile
import sys
from dataclasses import dataclass, field
from pathlib import Path

WAD_HEADER_SIZE = 0x20
WAD_ALIGNMENT = 0x10
GOW1_ZERO_TAG = 0x18
GOW2_ZERO_TAG = 0x00
GOW1_HEADER_TAG = 0x378
# GoW2 R_PERMA/R_PERM headers observed in the ELF-era WAD use tag 0x15.
GOW2_HEADER_TAGS = {0x15}

TEXT_CODECS = {
    "Windows-1252 (browser/legado)": "cp1252",
    "UTF-8 (runtime GoW2)": "gow2-runtime-utf8",
    "ISO-8859-1": "latin-1",
    "Windows-1251 (russo)": "cp1251",
    "UTF-8": "utf-8",
    "UTF-8 com BOM": "utf-8-sig",
    "Shift-JIS / CP932 (runtime)": "cp932",
}

# Keep the CP1252 table explicit instead of relying only on Python's codec.
# It documents the byte values used by the GoW2 font codeArray and is also the
# migration path for older one-byte MSGS_TXT files. The Text widget always
# shows the Unicode keys. The actual GoW2 runtime resource is saved as UTF-8;
# for example, visual "ã" -> bytes C3 A3 -> runtime codepoint U+00E3 -> font
# map index 0xE3. Legacy/browser mode can still emit the one-byte value E3.
GOW2_CP1252_DICTIONARY = {
    "\u00A9": 0xA9, "\u00AE": 0xAE,
    "\u00A1": 0xA1, "\u00B0": 0xB0, "\u00BF": 0xBF,
    "\u0152": 0x8C, "\u0153": 0x9C,
    "\u00C0": 0xC0, "\u00C1": 0xC1, "\u00C2": 0xC2, "\u00C3": 0xC3,
    "\u00C4": 0xC4, "\u00C7": 0xC7, "\u00C8": 0xC8, "\u00C9": 0xC9,
    "\u00CA": 0xCA, "\u00CB": 0xCB, "\u00CC": 0xCC, "\u00CD": 0xCD,
    "\u00CE": 0xCE, "\u00CF": 0xCF, "\u00D1": 0xD1, "\u00D2": 0xD2,
    "\u00D3": 0xD3, "\u00D4": 0xD4, "\u00D5": 0xD5, "\u00D6": 0xD6,
    "\u00D9": 0xD9, "\u00DA": 0xDA, "\u00DB": 0xDB, "\u00DC": 0xDC,
    "\u00DF": 0xDF,
    "\u00E0": 0xE0, "\u00E1": 0xE1, "\u00E2": 0xE2, "\u00E3": 0xE3,
    "\u00E4": 0xE4, "\u00E7": 0xE7, "\u00E8": 0xE8, "\u00E9": 0xE9,
    "\u00EA": 0xEA, "\u00EB": 0xEB, "\u00EC": 0xEC, "\u00ED": 0xED,
    "\u00EE": 0xEE, "\u00EF": 0xEF, "\u00F1": 0xF1, "\u00F2": 0xF2,
    "\u00F3": 0xF3, "\u00F4": 0xF4, "\u00F5": 0xF5, "\u00F6": 0xF6,
    "\u00F9": 0xF9, "\u00FA": 0xFA, "\u00FB": 0xFB, "\u00FC": 0xFC,
}
GOW2_CP1252_REVERSE_DICTIONARY = {value: key for key, value in GOW2_CP1252_DICTIONARY.items()}

# In the GoW2 Flash runtime used by the supplied game, Decode operates in
# encoding mode 1: bytes C0..DF and E0..EF are consumed as UTF-8 sequences.
# Therefore MSGS_TXT must be UTF-8 on disk even though the font codeArray uses
# the resulting Unicode/CP1252 values (for example U+00E3 -> glyph map 0xE3).
# Existing translated WADs may still contain the earlier one-byte CP1252 form;
# the runtime codec accepts that form as an input fallback and upgrades it to
# UTF-8 when the resource is saved.
GOW2_RUNTIME_UTF8_CODEC = "gow2-runtime-utf8"


def decode_gow2_runtime(data: bytes) -> str:
    """Decode GoW2 MSGS_TXT and accept legacy CP1252 input for migration."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return decode_cp1252_dictionary(data)


def encode_cp1252_dictionary(text: str) -> bytes:
    """Encode visual Unicode text using the GoW2 CP1252 character table.

    ASCII and other ordinary CP1252 characters still use Python's standard
    codec.  Accented characters go through the explicit table above, so the
    saved WAD is independent of any font/keyboard encoding assumptions.
    """
    out = bytearray()
    for position, character in enumerate(text):
        mapped = GOW2_CP1252_DICTIONARY.get(character)
        if mapped is not None:
            out.append(mapped)
            continue
        try:
            out.extend(character.encode("cp1252"))
        except UnicodeEncodeError as exc:
            raise ValueError(
                f"O caractere visual {character!r} na posição {position} "
                "não existe no dicionário CP1252 do GoW2."
            ) from exc
    return bytes(out)


def decode_cp1252_dictionary(data: bytes) -> str:
    """Decode CP1252 bytes back to the visual Unicode characters in the UI."""
    out: list[str] = []
    for value in data:
        character = GOW2_CP1252_REVERSE_DICTIONARY.get(value)
        if character is not None:
            out.append(character)
        else:
            try:
                out.append(bytes((value,)).decode("cp1252"))
            except UnicodeDecodeError as exc:
                raise ValueError(f"Byte CP1252 0x{value:02X} não possui caractere visual válido.") from exc
    return "".join(out)

# Native ParseMsgFile accepts *123*, *123*H and *123*T.  The complete line
# ending is consumed so body_raw begins exactly after the marker line.
MESSAGE_MARKER = re.compile(
    r"(?m)^\*(?P<id>[^*\r\n]+)\*(?P<tip>[HT]?)[ \t]*(?:\r\n|\n|\r|$)"
)
# Proven on UNSTRIPPED ParseMsgFile: a marker is a strtok("\r\n" @ 0x002EDCC0)
# token starting with '*' whose last byte is '*', or the byte before the last is
# '*' and the last is 'H'/'T'.  The ID is strtol(base 10) of token+1: digits
# followed by junk still parse; a zero id is swallowed (body merges backward).
MACRO_RE = re.compile(r"\[([^\]\r\n]*)\]")
MACRO_RE = re.compile(r"\[([^\]\r\n]*)\]")


def align16(value: int) -> int:
    return (value + WAD_ALIGNMENT - 1) // WAD_ALIGNMENT * WAD_ALIGNMENT


def decode_name(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("cp1252", errors="replace")


def native_tokens(text: str) -> list[str]:
    """Return non-empty line tokens before the native // filter."""
        # strtok collapses delimiters and therefore drops empty lines.  The
        # delimiter string is proven to be exactly "\r\n" (0x002EDCC0 in the
        # UNSTRIPPED demo) and a UTF-8 BOM preamble is skipped (memcmp, 0x002EDCB8).
    # line behavior supported by the observed resources.
    return [line for line in re.split(r"[\r\n]+", text) if line != ""]


def runtime_tokens(text: str) -> list[str]:
    """Return non-comment tokens, retaining -- page separators."""
    return [line for line in native_tokens(text) if not line.startswith("//")]


def clean_lines(text: str) -> list[str]:
    """Return effective message lines after comments/separators are removed."""
    return [line for line in runtime_tokens(text) if not line.startswith("--")]


def parse_native_id(raw: str) -> int | None:
    # strtol accepts a numeric prefix.  We are stricter in the editor because
    # silently converting a malformed marker is more dangerous than warning.
    value = raw.strip()
    if not re.fullmatch(r"[+-]?\d+", value):
        return None
    try:
        return int(value, 10)
    except ValueError:
        return None


def strtol_decimal(raw: str) -> int:
    """Simulate the C strtol(token + 1, &end, 10) inside ParseMsgFile.

    Returns the leading decimal value (with optional sign) or 0 when the
    token holds no digits, which is exactly what the runtime gets.
    """
    match = re.match(r"[+-]?\d+", raw.strip())
    return int(match.group(0), 10) if match else 0


def runtime_lead_conflicts(data: bytes) -> int:
    """Count sequences F_Font::Decode would consume as multi-byte leads.

    Decode (0x00156CF0) runs with the global encoding == 1 (0x002D79E0, set in
    .data and never written anywhere in the UNSTRIPPED export).  In that mode
    bytes C0..DF consume the following byte and E0..EF consume the following
    two, so a one-byte CP1252 accent saved into MSGS_TXT silently swallows its
    neighbours.  Well-formed UTF-8 continues (0x80..0xBF) are expected and do
    not count; a lead that grabs printable ASCII marks a real conflict.
    """
    count = 0
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if 0xC0 <= b <= 0xDF:
            if i + 1 < n:
                if 0x20 <= data[i + 1] <= 0x7E:
                    count += 1
                i += 2
            else:
                i += 1
        elif 0xE0 <= b <= 0xEF:
            if i + 2 < n:
                if 0x20 <= data[i + 1] <= 0x7E or 0x20 <= data[i + 2] <= 0x7E:
                    count += 1
                i += 3
            else:
                i += 1
        else:
            i += 1
    return count



@dataclass
@dataclass
class WadTag:
    index: int
    offset: int
    tag: int
    flags: int
    size_field: int
    name_raw: bytes
    data: bytes
    zero_sized: bool = False
    raw_segment: bytes = b""
    original_data: bytes = b""
    original_size_field: int = 0

    @property
    def name(self) -> str:
        return decode_name(self.name_raw)

    @property
    def upper_name(self) -> str:
        return self.name.upper()

    @property
    def resource_kind(self) -> str:
        name = self.upper_name
        if name == "MSGS_COUNT":
            return "MSGS_COUNT (contador binário)"
        if name == "MSGS_LINES":
            return "MSGS_LINES (contador binário)"
        if name == "MSGS_TXT":
            return "MSGS_TXT (TXT do runtime Flash)"
        if name.endswith(".TXT"):
            return "TXT (mensagens ou auxiliar)"
        if name in {"SANITY.TXT", "STRINGS.TXT"}:
            return "TXT"
        return "recurso"

    @property
    def is_runtime_counter(self) -> bool:
        return self.upper_name in {"MSGS_COUNT", "MSGS_LINES"}

    @property
    def is_text(self) -> bool:
        """Candidate text resource, excluding the two MSGS counters."""
        name = self.upper_name
        return bool(
            self.data
            and not self.is_runtime_counter
            and (
                name == "MSGS_TXT"
                or name.endswith(".TXT")
                or name in {"SANITY.TXT", "STRINGS.TXT"}
            )
        )

    def _canonical(self) -> bytes:
        if self.zero_sized:
            size = self.size_field
            body = b""
        else:
            size = len(self.data)
            body = self.data
        header = struct.pack("<HHI", self.tag, self.flags, size)
        header += self.name_raw[:24].ljust(24, b"\0")
        out = header + body
        padding_len = align16(len(out)) - len(out)
        # Reuse old padding first.  If a resized body needs more padding, the
        # remainder is zeroed, matching the browser's marshal behavior.
        old_pad = b""
        if self.raw_segment:
            old_body_end = WAD_HEADER_SIZE + len(self.original_data)
            old_pad = self.raw_segment[old_body_end:]
        padding = old_pad[:padding_len].ljust(padding_len, b"\0")
        return out + padding

    def serialize(self) -> bytes:
        # This is the key preservation guarantee: if neither the body nor the
        # zero-tag size changed, return the original header/body/padding block.
        if (
            self.raw_segment
            and self.data == self.original_data
            and self.size_field == self.original_size_field
        ):
            return self.raw_segment
        return self._canonical()


class WadFile:
    def __init__(self, raw: bytes):
        self.raw = bytes(raw)
        self.tags: list[WadTag] = []
        self.zero_tag: int | None = None
        self.variant = "unknown"
        self.first_tag = 0
        self._parse()

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "WadFile":
        return cls(Path(path).read_bytes())

    def _parse(self):
        if len(self.raw) < WAD_HEADER_SIZE:
            raise ValueError("Arquivo pequeno demais para ser um WAD.")
        self.first_tag = struct.unpack_from("<H", self.raw, 0)[0]
        if self.first_tag == GOW1_HEADER_TAG:
            self.zero_tag = GOW1_ZERO_TAG
            self.variant = "GoW1"
        elif self.first_tag == GOW2_ZERO_TAG or self.first_tag in GOW2_HEADER_TAGS:
            self.zero_tag = GOW2_ZERO_TAG
            self.variant = "GoW2/runtime"
        else:
            # Keep parsing useful for custom WADs.  This is the browser's
            # practical GoW2 fallback, but the UI labels it as heuristic.
            self.zero_tag = GOW2_ZERO_TAG
            self.variant = f"desconhecido (primeira tag 0x{self.first_tag:04x})"

        pos = 0
        index = 0
        raw_len = len(self.raw)
        while pos + WAD_HEADER_SIZE <= raw_len:
            tag, flags, size = struct.unpack_from("<HHI", self.raw, pos)
            name_raw = self.raw[pos + 8:pos + 32]
            zero_sized = tag == self.zero_tag
            body_size = 0 if zero_sized else size
            body_start = pos + WAD_HEADER_SIZE
            body_end = body_start + body_size
            segment_end = align16(body_end)
            if body_end > raw_len or segment_end > raw_len:
                raise ValueError(
                    f"Tag {index} ({decode_name(name_raw)}) ultrapassa o fim do WAD "
                    f"(offset 0x{pos:x}, tamanho 0x{size:x})."
                )
            data = bytes(self.raw[body_start:body_end])
            segment = bytes(self.raw[pos:segment_end])
            self.tags.append(
                WadTag(
                    index=index,
                    offset=pos,
                    tag=tag,
                    flags=flags,
                    size_field=size,
                    name_raw=bytes(name_raw),
                    data=data,
                    zero_sized=zero_sized,
                    raw_segment=segment,
                    original_data=data,
                    original_size_field=size,
                )
            )
            pos = segment_end
            index += 1
            if pos == raw_len:
                break

        if not self.tags:
            raise ValueError("Nenhuma tag encontrada no WAD.")
        if pos != raw_len:
            raise ValueError(
                f"WAD inválido ou truncado: parser terminou em 0x{pos:x}, "
                f"mas o arquivo tem 0x{raw_len:x} bytes."
            )

    def text_tags(self) -> list[WadTag]:
        return [tag for tag in self.tags if tag.is_text]

    def runtime_metadata(self) -> list[WadTag]:
        return [tag for tag in self.tags if tag.is_runtime_counter or tag.upper_name == "MSGS_TXT"]

    def serialize(self) -> bytes:
        return b"".join(tag.serialize() for tag in self.tags)

    def summary(self) -> str:
        counters = [f"{tag.name}={int.from_bytes(tag.data[:4], 'little')}" for tag in self.tags if tag.is_runtime_counter and len(tag.data) >= 4]
        counter_text = ", ".join(counters) if counters else "não encontrados"
        return (
            f"variante: {self.variant}\n"
            f"primeira tag: 0x{self.first_tag:04x}\n"
            f"tag EntityCount/zero: 0x{self.zero_tag:04x}\n"
            f"tamanho: {len(self.raw):,} bytes (0x{len(self.raw):x})\n"
            f"tags: {len(self.tags):,}\n"
            f"recursos editáveis candidatos: {len(self.text_tags())}\n"
            f"MSGS metadata: {counter_text}"
        )


@dataclass
class Message:
    key: str
    header_raw: str
    body_raw: str
    tip: str = ""

    @property
    def message_id(self) -> int | None:
        return parse_native_id(self.key)

    def flash_variable_line(self, suffix: str = "") -> str | None:
        """Resolve the line addressed by Flash's numeric variable convention.

        The analyzed GetVariable path treats names such as 123a and 123b as
        the ID 123 plus a line selector.  We expose that convention as a
        diagnostic/helper without changing the raw TXT representation.
        """
        if suffix == "":
            line_index = 0
        elif len(suffix) == 1 and suffix.isalpha():
            line_index = ord(suffix.lower()) - ord("a")
        else:
            return None
        lines = self.runtime_lines
        return lines[line_index] if 0 <= line_index < len(lines) else None

    @property
    def runtime_id(self) -> int:
        """ID that the native strtol-based ParseMsgFile would register."""
        return strtol_decimal(self.key)


    @property
    def tip_code(self) -> int:
        return {"H": 1, "T": 2}.get(self.tip.upper(), 0)

    @property
    def text(self) -> str:
        leading = len(self.body_raw) - len(self.body_raw.lstrip("\r\n"))
        trailing = len(self.body_raw) - len(self.body_raw.rstrip("\r\n"))
        end = len(self.body_raw) - trailing if trailing else len(self.body_raw)
        return self.body_raw[leading:end]

    @property
    def runtime_lines(self) -> list[str]:
        return clean_lines(self.text)

    @property
    def runtime_pages(self) -> list[list[str]]:
        pages: list[list[str]] = [[]]
        for line in runtime_tokens(self.text):
            if line.startswith("--"):
                pages.append([])
            else:
                pages[-1].append(line)
        return pages

    @property
    def macros(self) -> list[str]:
        return [m.group(1) for m in MACRO_RE.finditer(self.text)]

    def set_text(self, text: str):
        body = self.body_raw
        leading_len = len(body) - len(body.lstrip("\r\n"))
        trailing_len = len(body) - len(body.rstrip("\r\n"))
        leading = body[:leading_len]
        trailing = body[len(body) - trailing_len:] if trailing_len else ""
        crlf = body.count("\r\n")
        lf_only = body.count("\n") - crlf
        newline = "\r\n" if crlf > lf_only else "\n"
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = normalized.replace("\n", newline)
        self.body_raw = leading + normalized + trailing


class FLPMovie:
    """Filme Flash FLP (formato GoW2): leitura estrutural + reescrita de
    rótulos desenhados (StaticLabels) — texto gravado no filme como uma
    lista fixa de comandos de desenho (glifo + avanço), sem passar pelo
    MSGS. Ex.: "Total PlayTime" na tela STATUS do FLP_HUDA.

    Layout conforme god_of_war_browser (Mogaika), validado em jogo:
    header 0x5C com contagens (GH @0x38, refs @0x3C, fonts @0x40,
    statics @0x44, dynamics @0x48, d6 @0x4C, d7 @0x50, u16 transf/blend
    @0x54/56, strings_size u32 @0x58). Depois do header: GH (4B), refs
    (8B; materiais 8B), fontes (header 0x24 + corpo com widths e
    char_map), statics (header 0x1C com o tamanho do stream em +0x18;
    streams alinhados em 4), dynamics (0x20 cada) e o restante — que a
    reescrita preserva byte a byte (só desloca).

    Comando de desenho: op 0x80|flags {&8 gh u16 + escala i16/1024;
    &4 cor 4B; &2 x i16/16; &1 y i16/16} + u8 contagem + contagem x
    (glifo u16, avanço i16/16). O avanço NÃO é a largura natural da
    fonte: é o passo já na escala do filme (~0.32x da natural no
    "Total PlayTime", com kerning manual do autor).
    """

    @staticmethod
    def _u16(b, o):
        return struct.unpack_from("<H", b, o)[0]

    @staticmethod
    def _u16s(b, o):
        return struct.unpack_from("<h", b, o)[0]

    @staticmethod
    def _u32(b, o):
        return struct.unpack_from("<I", b, o)[0]

    def __init__(self, data: bytes):
        b = bytes(data)
        if len(b) < 0x5C:
            raise ValueError("FLP: tamanho inválido (não é FLP GoW2)")
        self.data = b
        self.gh_count = self._u32(b, 0x38)
        self.ref_count = self._u32(b, 0x3C)
        self.font_count = self._u32(b, 0x40)
        self.static_count = self._u32(b, 0x44)
        self.dynamic_count = self._u32(b, 0x48)
        self.strings_size = self._u32(b, 0x58)
        if self.strings_size > len(b) or self.static_count > 4096 or self.font_count > 64:
            raise ValueError("FLP: cabeçalho fora dos limites (não é FLP GoW2?)")
        pos = 0x5C
        self.gh = []
        for _ in range(self.gh_count):
            if pos + 4 > len(b):
                raise ValueError("FLP: tabela de handlers truncada")
            self.gh.append(struct.unpack_from("<HH", b, pos))
            pos += 4
        ref_mat_total = 0
        for _ in range(self.ref_count):
            if pos + 8 > len(b):
                raise ValueError("FLP: refs truncadas")
            ref_mat_total += self._u16(b, pos + 6)
            pos += 8
        pos += 8 * ref_mat_total
        self.fonts = []
        for _ in range(self.font_count):
            if pos + 0x24 > len(b):
                raise ValueError("FLP: fonte truncada")
            chars = self._u32(b, pos + 0x10)
            flags = self._u16(b, pos + 0x20)
            if not (0 < chars <= 4096):
                raise ValueError("FLP: fonte inválida")
            pos += 0x24
            if flags & (2 | 4):
                mats = 0
                for _ in range(chars):
                    if pos + 8 > len(b):
                        raise ValueError("FLP: refs da fonte truncadas")
                    mats += self._u16(b, pos + 6)
                    pos += 8
                pos += 8 * mats
            widths_pos = pos
            pos += 2 * chars
            pos = (pos + 3) & ~3
            cmap_pos = pos
            cmap_n = 0x100 if (flags & 1) else chars
            pos += 2 * cmap_n
            pos = (pos + 3) & ~3
            if pos > len(b):
                raise ValueError("FLP: corpo da fonte fora dos limites")
            self.fonts.append({"chars": chars, "flags": flags,
                               "widths_pos": widths_pos, "cmap_pos": cmap_pos,
                               "cmap_n": cmap_n})
        self.statics = []
        hdrs_start = pos
        pos += 0x1C * self.static_count
        for i in range(self.static_count):
            hdr = hdrs_start + 0x1C * i
            size = self._u32(b, hdr + 0x18)
            if size > len(b) or pos + size > len(b):
                raise ValueError("FLP: stream de rótulo fora dos limites")
            self.statics.append({"hdr": hdr, "stream": pos, "size": size})
            pos = (pos + size + 3) & ~3
        self.dynamics_pos = pos
        if pos + 0x20 * self.dynamic_count > len(b):
            raise ValueError("FLP: dynamics fora dos limites")

    # ---------------- fontes ----------------

    def font_index_of_gh(self, gh_index: int) -> int | None:
        """GlobalHandler -> índice na lista de fontes (array id 3)."""
        if not 0 <= gh_index < len(self.gh):
            return None
        arr_type, idx = self.gh[gh_index]
        if arr_type != 3 or not 0 <= idx < len(self.fonts):
            return None
        return idx

    def char_map(self, font_idx: int) -> list[int]:
        f = self.fonts[font_idx]
        return [struct.unpack_from("<h", self.data, f["cmap_pos"] + 2 * k)[0]
                for k in range(f["cmap_n"])]

    def symbol_widths(self, font_idx: int) -> list[int]:
        f = self.fonts[font_idx]
        return [struct.unpack_from("<h", self.data, f["widths_pos"] + 2 * k)[0]
                for k in range(f["chars"])]

    # ---------------- comandos de desenho ----------------

    def parse_commands(self, buf: bytes) -> list[dict]:
        blocks: list[dict] = []
        cur: dict | None = None
        i = 0
        first_run_pos = None
        while i < len(buf):
            op = buf[i]
            i += 1
            if op & 0x80:
                cur = {"flags": op & 0x7F, "glyphs": [], "gh": None, "scale": None,
                       "color": None, "x": None, "y": None, "start": i - 1}
                blocks.append(cur)
                if op & 8:
                    if i + 4 > len(buf):
                        raise ValueError("comando truncado (gh/escala)")
                    cur["gh"] = self._u16(buf, i)
                    cur["scale"] = self._u16s(buf, i + 2) / 1024.0
                    i += 4
                if op & 4:
                    if i + 4 > len(buf):
                        raise ValueError("comando truncado (cor)")
                    cur["color"] = bytes(buf[i:i + 4])
                    i += 4
                if op & 2:
                    if i + 2 > len(buf):
                        raise ValueError("comando truncado (x)")
                    cur["x"] = self._u16s(buf, i) / 16.0
                    i += 2
                if op & 1:
                    if i + 2 > len(buf):
                        raise ValueError("comando truncado (y)")
                    cur["y"] = self._u16s(buf, i) / 16.0
                    i += 2
                if first_run_pos is None:
                    first_run_pos = i
            else:
                if cur is None:
                    raise ValueError("comando de glifo sem bloco aberto")
                if first_run_pos is None:
                    first_run_pos = i - 1
                if i + 4 * op > len(buf):
                    raise ValueError("lista de glifos truncada")
                for _ in range(op):
                    cur["glyphs"].append((self._u16(buf, i), self._u16s(buf, i + 2) / 16.0))
                    i += 4
        return blocks

    def decode_ids(self, font_idx: int, ids) -> str:
        inv: dict[int, int] = {}
        for c, s in enumerate(self.char_map(font_idx)):
            if s >= 0:
                inv.setdefault(s, c)
        return "".join(chr(inv[g]) if g in inv and 32 <= inv[g] < 127 else "?" for g in ids)

    def label(self, index: int) -> dict:
        """Informações do rótulo: texto, editável?, detalhes."""
        if not 0 <= index < len(self.statics):
            raise ValueError("rótulo inexistente")
        st = self.statics[index]
        info = {"index": index, "size": st["size"], "text": "", "editable": False,
                "detail": "", "glyph_count": 0}
        try:
            blocks = self.parse_commands(self.data[st["stream"]:st["stream"] + st["size"]])
        except ValueError as exc:
            info["detail"] = f"comandos inválidos ({exc})"
            return info
        if len(blocks) != 1:
            info["detail"] = f"{len(blocks)} blocos de desenho (suporta apenas 1)"
            return info
        blk = blocks[0]
        info["glyph_count"] = len(blk["glyphs"])
        info["gh"] = blk["gh"]
        info["scale"] = blk["scale"]
        info["x"], info["y"] = blk["x"], blk["y"]
        font_idx = self.font_index_of_gh(blk["gh"]) if blk["gh"] is not None else None
        if font_idx is None:
            info["detail"] = f"bloco não aponta para uma fonte (gh={blk['gh']})"
            return info
        info["font_idx"] = font_idx
        info["text"] = self.decode_ids(font_idx, [g for g, _ in blk["glyphs"]])
        unknown = [g for g, _ in blk["glyphs"]
                   if g not in {s for s in self.char_map(font_idx) if s >= 0}]
        if unknown:
            info["detail"] = f"glifos fora do mapa da fonte: {unknown[:8]}"
            return info
        # posição onde começa a 1ª lista de glifos (após os campos do bloco)
        buf = self.data[st["stream"]:st["stream"] + st["size"]]
        j = 1
        op = buf[0]
        if op & 8: j += 4
        if op & 4: j += 4
        if op & 2: j += 2
        if op & 1: j += 2
        info["hdr_len"] = j  # bytes do bloco (a contagem u8 é reemitida no encode)
        info["editable"] = True
        info["detail"] = (f"fonte {font_idx} • escala {blk['scale']:.4f} • "
                          f"{len(blk['glyphs'])} glifos • largura "
                          f"{sum(w for _, w in blk['glyphs']):.1f}")
        return info

    def encode_label(self, index: int, new_text: str) -> bytes:
        """Recria o stream do rótulo com o novo texto (1 bloco). Devolve os
        bytes NOVOS da tag inteira; o restante do filme é preservado."""
        if not new_text:
            raise ValueError("Texto vazio (para apagar use outro recurso).")
        st = self.statics[index]
        info = self.label(index)
        if not info["editable"]:
            raise ValueError(f"Rótulo somente leitura: {info['detail']}")
        font_idx = info["font_idx"]
        cm = self.char_map(font_idx)
        widths = self.symbol_widths(font_idx)
        orig = self.parse_commands(self.data[st["stream"]:st["stream"] + st["size"]])[0]
        known = {g: w for g, w in orig["glyphs"]}
        so = sum(w for _, w in orig["glyphs"])
        sn = sum(widths[g] / 16.0 for g, _ in orig["glyphs"])
        factor = (so / sn) if sn else 1.0
        missing = []
        for ch in new_text:
            if ord(ch) < len(cm) and cm[ord(ch)] >= 0:
                continue
            if ch == " ":
                continue  # convenção: espaço pode usar o glifo 0
            missing.append(ch)
        if missing:
            raise ValueError("Caracteres sem glifo nesta fonte: " + " ".join(sorted(set(missing))))
        glyphs = []
        for ch in new_text:
            s = cm[ord(ch)] if ord(ch) < len(cm) else -1
            if s < 0 and ch == " ":
                s = 0  # convenção: glifo 0 é o espaço
            w = known.get(s)
            if w is None:
                w = widths[s] / 16.0 * factor
            glyphs.append((s, w))
        if len(glyphs) > 255:
            raise ValueError(f"Texto longo demais ({len(glyphs)} glifos; máximo 255).")
        hdr_bytes = bytes(self.data[st["stream"]:st["stream"] + info["hdr_len"]])
        run = bytearray([len(glyphs)])
        for g, w in glyphs:
            run += struct.pack("<Hh", g, int(round(w * 16)))
        new_stream = hdr_bytes + bytes(run)
        new_stream += b"\x00" * ((-len(new_stream)) % 4)
        return self._rebuild_statics(index, new_stream)

    def _rebuild_statics(self, changed_index: int, new_stream: bytes) -> bytes:
        b = self.data
        first = self.statics[0]["hdr"]
        end = self.statics[-1]["stream"] + ((self.statics[-1]["size"] + 3) & ~3)
        out = bytearray(b[:first])
        for i, stx in enumerate(self.statics):
            hb = bytearray(b[stx["hdr"]:stx["hdr"] + 0x1C])
            size = len(new_stream) if i == changed_index else stx["size"]
            struct.pack_into("<I", hb, 0x18, size)
            out += hb
        for i, stx in enumerate(self.statics):
            chunk = new_stream if i == changed_index else b[stx["stream"]:stx["stream"] + stx["size"]]
            out += chunk
            if i != changed_index:
                out += b"\x00" * ((-stx["size"]) % 4)
        out += b[end:]
        # revalidação completa antes de aceitar
        novo = FLPMovie(bytes(out))
        for i in range(novo.static_count):
            info = novo.label(i)
            if i == changed_index:
                if not info["editable"]:
                    raise ValueError("revalidação falhou no rótulo editado")
                continue
            antigo = self.label(i)
            if info["text"] != antigo["text"] or info["glyph_count"] != antigo["glyph_count"]:
                raise ValueError(f"revalidação falhou: rótulo [{i}] mudou junto")
        return bytes(out)


@dataclass
class ResourceDiagnostics:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        out: list[str] = []
        if self.errors:
            out.append("ERROS")
            out.extend(f"  • {x}" for x in self.errors)
        if self.warnings:
            if out:
                out.append("")
            out.append("AVISOS")
            out.extend(f"  • {x}" for x in self.warnings)
        if self.notes:
            if out:
                out.append("")
            out.append("INFORMAÇÕES")
            out.extend(f"  • {x}" for x in self.notes)
        return "\n".join(out) if out else "Nenhum problema encontrado."


class TextResource:
    def __init__(self, data: bytes, codec: str):
        self.codec = codec
        self.raw_data = bytes(data)
        # Some translated GoW1 resources contain a run of NUL bytes after the
        # last visible line (the attached Portuguese WAD has 815).  Only the
        # first NUL matters to the C string parser, but all of them are part of
        # the existing WAD payload and must survive a round-trip unchanged.
        trailing_nul_count = len(data) - len(data.rstrip(b"\0"))
        self.trailing_nuls = bytes(data[-trailing_nul_count:]) if trailing_nul_count else b""
        self.had_terminal_nul = bool(self.trailing_nuls)
        payload = data[:-trailing_nul_count] if trailing_nul_count else data
        self.raw_payload = bytes(payload)
        # Proven on UNSTRIPPED ParseMsgFile (0x001E6170): memcmp 3 against
        # 0x002EDCB8 == EF BB BF; a UTF-8 BOM preamble is skipped by the game.
        self.runtime_bom = b""
        if payload.startswith(b"\xef\xbb\xbf"):
            self.runtime_bom = payload[:3]
            payload = payload[3:]
        self.runtime_legacy_cp1252 = False
        try:
            if codec == "cp1252":
                # The editor always displays Unicode accents; the explicit
                # dictionary only controls the one-byte WAD representation.
                self.text = decode_cp1252_dictionary(payload)
            elif codec == GOW2_RUNTIME_UTF8_CODEC:
                # The runtime reads this resource with Decode(encoding=1),
                # i.e. UTF-8.  Fall back to one-byte CP1252 so an existing
                # WAD made by the previous editor can be opened and migrated.
                try:
                    self.text = payload.decode("utf-8")
                except UnicodeDecodeError:
                    self.runtime_legacy_cp1252 = True
                    self.text = decode_cp1252_dictionary(payload)
            else:
                self.text = payload.decode(codec)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError(f"Não foi possível decodificar o texto usando {codec}: {exc}") from exc
        self.messages: list[Message] = []
        self.is_plain_text = False
        self._parse()

    def _parse(self):
        matches = list(MESSAGE_MARKER.finditer(self.text))
        if not matches:
            # R_PERM can contain auxiliary TXT resources such as the
            # translator credit Curiosidade.txt.  Keep these editable instead
            # of confusing them with a malformed MSGS table.
            self.is_plain_text = True
            self.messages.append(Message(key="(texto)", header_raw="", body_raw=self.text))
            return
        for i, match in enumerate(matches):
            body_start = match.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(self.text)
            self.messages.append(
                Message(
                    key=match.group("id"),
                    tip=match.group("tip") or "",
                    header_raw=match.group(0),
                    body_raw=self.text[body_start:body_end],
                )
            )

    def rebuild(self) -> str:
        first = self.messages[0]
        first_pos = self.text.find(first.header_raw)
        preamble = self.text[:first_pos] if first_pos >= 0 else ""
        return preamble + "".join(m.header_raw + m.body_raw for m in self.messages)

    def to_bytes(self) -> bytes:
        visible_text = self.rebuild()
        try:
            if self.codec == "cp1252":
                # Legacy/browser mode: visual "á", "ã", "ç" etc. become
                # one-byte CP1252 values (E1, E3, E7, ...).
                encoded = encode_cp1252_dictionary(visible_text)
            elif self.codec == GOW2_RUNTIME_UTF8_CODEC:
                # GoW2's runtime Decode(encoding=1) must receive UTF-8.  The
                # resulting Unicode codepoints still index the same font map:
                # UTF-8 C3 A3 decodes to U+00E3, then codeArray[0xE3].
                encoded = visible_text.encode("utf-8")
            else:
                encoded = visible_text.encode(self.codec)
        except UnicodeEncodeError as exc:
            bad = exc.object[exc.start:exc.end]
            raise ValueError(
                f"A codificação {self.codec} não representa {bad!r} "
                f"na posição {exc.start}. Escolha outra codepage ou substitua o caractere."
            ) from exc
        if self.runtime_bom:
            # Preserve the exact preamble the runtime expects to skip; avoid
            # doubling it if the codec itself emitted a BOM (utf-8-sig).
            if encoded.startswith(b"\xef\xbb\xbf"):
                encoded = encoded[3:]
            encoded = self.runtime_bom + encoded
        return encoded + self.trailing_nuls


    def resolve_flash_variable(self, variable_name: str) -> str | None:
        """Return a line for a Flash variable like 123a, if it resolves.

        This is a convenience model of the observed native lookup.  It does
        not invent variables in the WAD and returns None for malformed or
        missing IDs.
        """
        match = re.fullmatch(r"(?P<id>\d+)(?P<suffix>[A-Za-z]?)", variable_name.strip())
        if not match:
            return None
        wanted = int(match.group("id"), 10)
        for message in self.messages:
            if message.message_id == wanted:
                return message.flash_variable_line(match.group("suffix"))
        return None

    def dominant_newline(self) -> str:
        """Estilo de quebra de linha predominante no recurso (preserva o original).

        Maioria, nao presenca: um punhado de CRLF solto num arquivo LF nao deve
        virar o estilo inteiro — era isso que, junto com a normalizacao do Qt,
        marcava o WAD como "editado" so de clicar numa mensagem.
        """
        crlf = self.text.count("\r\n")
        lf_only = self.text.count("\n") - crlf
        return "\r\n" if crlf > lf_only else "\n"

    def next_id(self) -> int:
        """Proximo ID sequencial livre (maximo atual + 1)."""
        ids = [m.message_id for m in self.messages if m.message_id is not None]
        return (max(ids) + 1) if ids else 1

    def insert_message(self, message_id: int, text: str = "", tip: str = "") -> Message:
        """Cria um marcador novo e insere na tabela mantendo IDs em ordem crescente.

        O runtime usa bsearch e exige a tabela ordenada; a insercao escolhe a
        posicao pelo ID e garante que o marcador anterior termine em quebra de
        linha para o novo marcador comecar em linha propria.
        """
        if any(m.message_id == message_id for m in self.messages):
            raise ValueError(f"O ID {message_id} ja existe neste recurso.")
        if tip and tip.upper() not in ("H", "T"):
            raise ValueError("Dica (tip) deve ser H, T ou vazio.")
        tip = tip.upper()
        nl = self.dominant_newline()
        header = f"*{message_id}*{tip}{nl}"
        new_message = Message(key=str(message_id), header_raw=header, body_raw="", tip=tip)
        position = len(self.messages)
        for i, existing in enumerate(self.messages):
            if existing.message_id is not None and existing.message_id > message_id:
                position = i
                break
        if position > 0:
            previous = self.messages[position - 1]
            if previous.body_raw and not previous.body_raw.endswith(("\n", "\r")):
                previous.body_raw += nl
        if text:
            new_message.set_text(text if text.endswith("\n") else text + "\n")
        self.messages.insert(position, new_message)
        return new_message

    def remove_message(self, index: int) -> Message:
        """Remove a mensagem (marcador + corpo) da tabela."""
        if index < 0 or index >= len(self.messages):
            raise ValueError("Indice de mensagem invalido.")
        return self.messages.pop(index)

    def diagnostics(self, max_lines_per_page: int = 3, gow2_runtime: bool = False) -> ResourceDiagnostics:
        d = ResourceDiagnostics()
        if self.runtime_bom:
            d.notes.append(
                "Payload começa com UTF-8 BOM (EF BB BF); o ParseMsgFile pula esses 3 bytes e o editor o preserva ao salvar."
            )
        if self.codec == "cp1252":
            d.notes.append(
                "Windows-1252 legado ativo: os acentos digitados na interface "
                "são gravados como bytes CP1252 (ã=E3, á=E1, ç=E7, etc.). "
                "Para MSGS_TXT do GoW2 use UTF-8 (runtime GoW2)."
            )
            if gow2_runtime and not self.is_plain_text:
                conflicts = runtime_lead_conflicts(encode_cp1252_dictionary(self.text))
                if conflicts:
                    d.warnings.append(
                        f"{conflicts} sequência(s) de bytes CP1252 seriam comidas como lead UTF-8 pelo Decode(encoding=1) do GoW2; para MSGS_TXT salve em UTF-8 (runtime GoW2)."
                    )
        elif self.codec == GOW2_RUNTIME_UTF8_CODEC:
            d.notes.append(
                "UTF-8 do runtime GoW2 ativo: Decode(encoding=1) transforma "
                "C3 A3 em U+00E3 e usa o glyph 0xE3 da fonte."
            )
        if self.had_terminal_nul:
            d.notes.append(f"O payload termina com {len(self.trailing_nuls)} NUL(s); o editor preservará toda essa cauda.")
        if self.is_plain_text:
            d.notes.append("TXT auxiliar sem marcadores runtime; será tratado como texto simples e preservado sem MSGS parsing.")
            d.notes.append(f"{len(self.text)} caracteres no recurso auxiliar.")
            return d
        ids = [m.message_id for m in self.messages]
        for message in self.messages:
            if message.message_id is None:
                if message.runtime_id:
                    d.warnings.append(
                        f"Marcador {message.key!r}: o editor recusa, mas o runtime registraria o ID {message.runtime_id} (strtol ignora o lixo após os dígitos)."
                    )
                else:
                    d.errors.append(
                        f"Marcador {message.key!r}: o strtol do runtime leria 0; o marcador some e o corpo é mesclado à mensagem anterior."
                    )
        numeric_ids = [value for value in ids if value is not None]
        duplicates = sorted({value for value in numeric_ids if numeric_ids.count(value) > 1})
        if duplicates:
            d.errors.append(f"IDs duplicados: {', '.join(map(str, duplicates[:20]))}.")
        if numeric_ids != sorted(numeric_ids):
            d.warnings.append("Os IDs não estão em ordem crescente; o runtime usa bsearch e normalmente exige a tabela ordenada.")
        if self.codec == "utf-8-sig":
            d.notes.append("UTF-8 com BOM selecionado; o BOM é tratado pelo codec e não é duplicado ao salvar.")

        if any(message.tip_code for message in self.messages):
            d.notes.append(
                "Dicas H/T: com ShowMsgTips desligado para o bit da dica (1=H, 2=T) o DoMsgPage pula a mensagem inteira."
            )
        total_runtime_lines = 0
        total_runtime_lines = 0
        for message in self.messages:
            if message.tip_code:
                d.notes.append(f"ID {message.key}: dica nativa {message.tip_code} ({message.tip}).")
            if any(line.startswith("//") for line in native_tokens(message.text)):
                d.notes.append(f"ID {message.key}: contém comentário // ignorado pelo parser nativo.")
            pages = message.runtime_pages
            total_runtime_lines += sum(len(page) for page in pages)
            for page_number, page in enumerate(pages, 1):
                if len(page) > max_lines_per_page:
                    d.warnings.append(
                        f"ID {message.key}, página {page_number}: {len(page)} linhas; DoMsgPage zera o template e a MENSAGEM INTEIRA fica oculta (máx. {max_lines_per_page} linhas por página)."
                    )
                elif len(pages) > 1 and len(page) == 0:
                    d.warnings.append(
                        f"ID {message.key}, página {page_number}: sem linhas de conteúdo; DoMsgPage cancela o template nesse caso."
                    )
            if message.message_id is not None and not any(pages):
                d.warnings.append(
                    f"ID {message.key}: marcador sem linhas efetivas; se exibida, o runtime mostra o fallback literal \"Msg {message.message_id}\"."
                )
            if len(message.macros) > 16:
                d.warnings.append(f"ID {message.key}: {len(message.macros)} macros; EditTextBuild limita a 16 macros por campo.")
            for macro in message.macros:
                if macro.startswith("*"):
                    if not re.fullmatch(r"\*\d?", macro):
                        d.warnings.append(f"ID {message.key}: macro de estilo [{macro}] pode não seguir [*] ou [*N].")
                elif not macro:
                    d.warnings.append(f"ID {message.key}: macro vazia [].")
        lines_by_id: dict[int, int] = {}
        for message in self.messages:
            if message.message_id is not None:
                lines_by_id.setdefault(message.message_id, sum(len(p) for p in message.runtime_pages))
        if any(1500 <= k < 1600 for k in lines_by_id):
            probe, total = 1500, 0
            while lines_by_id.get(probe, 0) > 1 and probe < 1600:
                total += 1
                probe += 1
            d.notes.append(
                f"Free Combat: ReadMsgText conta mensagens consecutivas com 2+ linhas a partir do ID 1500 (total atual = {total}; a contagem para no ID {probe}). Traduzir sem manter 2+ linhas nessa faixa altera o número de criaturas."
            )
        empty_lines = sum(1 for line in self.text.splitlines() if line == "")
        if empty_lines:
            d.notes.append(f"{empty_lines} linha(s) vazia(s) são preservadas no arquivo, mas strtok as descarta no runtime.")
        d.notes.append(f"{len(self.messages)} mensagens, {total_runtime_lines} linhas efetivas após a regra strtok.")
        return d


def sync_msgs_counters(wad: WadFile) -> bool:
    """Mantem MSGS_COUNT/MSGS_LINES coerentes com o MSGS_TXT (runtime Flash GoW2).

    ParseMsgFile aloca maxMsgs entradas MsgInfo e maxLines ponteiros de linha,
    entao os contadores precisam acompanhar a tabela quando mensagens sao
    adicionadas/removidas. So age quando os contadores existem no WAD; o corpo
    inalterado continua sendo preservado byte a byte pelo serialize().
    Retorna True quando algum contador foi atualizado.
    """
    txt_tag = next((t for t in wad.tags if t.upper_name == "MSGS_TXT"), None)
    if txt_tag is None:
        return False
    count_tag = next((t for t in wad.tags if t.upper_name == "MSGS_COUNT" and len(t.data) >= 4), None)
    lines_tag = next((t for t in wad.tags if t.upper_name == "MSGS_LINES" and len(t.data) >= 4), None)
    if count_tag is None and lines_tag is None:
        return False
    try:
        resource = TextResource(txt_tag.data, GOW2_RUNTIME_UTF8_CODEC)
    except ValueError:
        return False
    if resource.is_plain_text:
        return False
    wanted_count = len(resource.messages)
    wanted_lines = sum(len(runtime_tokens(m.text)) for m in resource.messages)
    changed = False
    if count_tag is not None and int.from_bytes(count_tag.data[:4], "little") != wanted_count:
        count_tag.data = struct.pack("<I", wanted_count) + count_tag.data[4:]
        changed = True
    if lines_tag is not None and int.from_bytes(lines_tag.data[:4], "little") != wanted_lines:
        lines_tag.data = struct.pack("<I", wanted_lines) + lines_tag.data[4:]
        changed = True
    return changed


import configparser

CONFIG_FILENAME = "GodOfWarTextEditor.ini"
CONFIG_ENV_VAR = "GOW2TE_INI"
DEFAULT_SCALE = 1.0


def config_file_path() -> "Path":
    """INI lives next to the .py (override with GOW2TE_INI=<path> for tests)."""
    from pathlib import Path as _P
    forced = os.environ.get(CONFIG_ENV_VAR)
    if forced:
        return _P(forced)
    return _P(__file__).resolve().parent / CONFIG_FILENAME


_CONFIG_KEYS = {
    "paths": ("last_open_dir", "last_save_dir"),
    "window": ("geometry", "fullscreen"),
    "ui": ("scale", "bg_image", "bg_dim"),
    "editor": ("codec",),
}


def read_config(path=None) -> dict:
    """Flat dict of every known key with sane defaults; a broken INI never kills the app."""
    from pathlib import Path as _P
    p = _P(path) if path is not None else config_file_path()
    cfg = {keys[0]: "" for keys in ()}  # placeholder removed below
    cfg = {}
    for section, keys in _CONFIG_KEYS.items():
        for key in keys:
            cfg[key] = ""
    cfg["scale"] = "1.0"
    cfg["bg_image"] = ""
    cfg["bg_dim"] = "110"
    if p.exists():
        parser = configparser.ConfigParser()
        try:
            parser.read(p, encoding="utf-8")
        except (configparser.Error, OSError, UnicodeDecodeError):
            return cfg
        for section, keys in _CONFIG_KEYS.items():
            if parser.has_section(section):
                for key in keys:
                    value = parser.get(section, key, fallback=None)
                    if value is not None:
                        cfg[key] = value
    return cfg


def write_config(values: dict, path=None) -> None:
    from pathlib import Path as _P
    p = _P(path) if path is not None else config_file_path()
    parser = configparser.ConfigParser()
    for section, keys in _CONFIG_KEYS.items():
        parser[section] = {key: str(values.get(key, "")) for key in keys}
    try:
        with open(p, "w", encoding="utf-8", newline="\r\n") as handle:
            parser.write(handle)
    except OSError:
        pass  # a read-only location must not break saving work


def clamp_ui_scale(value) -> float:
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return DEFAULT_SCALE
    return min(2.0, max(0.6, scale))


# ---- Pasta de imagens de fundo e fonte de titulo (ao lado da tool) ----
BG_FOLDERNAME = "imagens_de_fundo"
FONT_FILENAME = "GODOFWAR.TTF"
BG_NAME_ORDER = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
BG_FOLDER_README = (
    "COLOQUE AQUI A IMAGEM DE FUNDO DA TOOL\n"
    "=====================================\n\n"
    "- O arquivo deve se chamar BACKGROUND (ex.: background.png ou background.jpg).\n"
    "- Formatos aceitos: PNG, JPG, JPEG, BMP, GIF e WEBP.\n"
    "- A tool carrega essa imagem sozinha como fundo na proxima abertura\n"
    "  (ou use Visualizar > Imagem de fundo > Recarregar da pasta).\n"
    "- Arquivos com outros nomes sao ignorados.\n"
    "- Se existir mais de um (background.png e background.jpg), a ordem de\n"
    "  preferencia e: png, jpg, jpeg, bmp, gif, webp.\n"
    "- Para voltar ao fundo solido padrao, apague/renomeie o arquivo e use\n"
    "  Visualizar > Imagem de fundo > Remover imagem.\n"
)


def tool_base_dir() -> "Path":
    """Pasta da tool: funciona rodando do .py ou de um exe PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def background_folder() -> "Path":
    return tool_base_dir() / BG_FOLDERNAME


def tool_font_path() -> "Path":
    return tool_base_dir() / FONT_FILENAME


def ensure_background_folder() -> "Path":
    """Cria a pasta de fundos (com o aviso) se ela ainda nao existir."""
    folder = background_folder()
    try:
        folder.mkdir(exist_ok=True)
        readme = folder / "COLOQUE-A-IMAGEM-AQUI.txt"
        if not readme.exists():
            readme.write_text(BG_FOLDER_README, encoding="utf-8")
    except OSError:
        pass
    return folder


# ---- Pasta do icone da janela (mesmo esquema da imagem de fundo) ----
ICON_FOLDERNAME = "icone"
# .ico primeiro: e o formato nativo de icone do Windows
ICON_NAME_ORDER = (".ico", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
ICON_FOLDER_README = (
    "COLOQUE AQUI O ICONE DA JANELA DA TOOL\n"
    "======================================\n\n"
    "- O arquivo deve se chamar ICON (ex.: icon.png ou icon.ico).\n"
    "- Formatos aceitos: ICO, PNG, JPG, JPEG, BMP, GIF e WEBP\n"
    "  (de preferencia quadrado; 256x256 ou maior fica melhor).\n"
    "- O icone aparece na barra de titulo ao lado de 'God of War Text\n"
    "  Editor', na barra de tarefas e nos dialogs da tool.\n"
    "- Se houver mais de um (icon.png e icon.ico), a ordem e:\n"
    "  ico, png, jpg, jpeg, bmp, gif, webp.\n"
    "- Arquivos com outros nomes sao ignorados.\n"
    "- Para remover, use Visualizar > Icone da janela > Remover icone\n"
    "  (o arquivo vira icon.ext.off e pode ser renomeado de volta).\n"
)


def icon_folder() -> "Path":
    return tool_base_dir() / ICON_FOLDERNAME


def ensure_icon_folder() -> "Path":
    """Cria a pasta do icone (com o aviso) se ela ainda nao existir."""
    folder = icon_folder()
    try:
        folder.mkdir(exist_ok=True)
        readme = folder / "COLOQUE-AQUI-O-ICONE.txt"
        if not readme.exists():
            readme.write_text(ICON_FOLDER_README, encoding="utf-8")
    except OSError:
        pass
    return folder


def detect_window_icon_path() -> str:
    """Arquivo chamado icon.* dentro da pasta icone ('' se nenhuma)."""
    folder = icon_folder()
    for ext in ICON_NAME_ORDER:
        candidate = folder / ("icon" + ext)
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return ""


def detect_folder_background() -> str:
    """Imagem chamada background.* dentro de imagens_de_fundo ('' se nenhuma).

    Somente arquivos com o nome exato "background" sao aceitos; se houver
    mais de uma extensao, vale a ordem BG_NAME_ORDER (png primeiro).
    """
    folder = background_folder()
    for ext in BG_NAME_ORDER:
        candidate = folder / ("background" + ext)
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return ""


try:
    from PySide6.QtCore import Qt, QSignalBlocker, QPointF, QRectF, QByteArray, Signal, QTimer
    from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QIcon, QKeySequence, QPainter, QPen, QPixmap, QTextCursor, QTextDocument
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QSizePolicy,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    QT_AVAILABLE = True
except ImportError as exc:
    QT_AVAILABLE = False
    QT_IMPORT_ERROR = exc

if QT_AVAILABLE:
    WAD_BG, WAD_PANEL, WAD_PANEL_ALT = "#141417", "#1C1C20", "#242428"
    WAD_BORDER, WAD_BORDER_LT = "#35353C", "#45454F"
    WAD_FG, WAD_FG_DIM, WAD_FG_MID = "#E0E0E8", "#7A7A8A", "#ACACBE"
    # Acentos em VERMELHO (antes eram laranja: C8522A/E06030/6B2A10).
    WAD_ACCENT, WAD_ACCENT_HOV, WAD_ACCENT_DIM = "#C03030", "#E14B4B", "#5C1515"
    WAD_HEX_BG = "#0D0D10"

    # ---- Imagem de fundo personalizada da interface ----
    # O WAD permanece intacto: isso e apenas cosmética da janela.
    BG_DIM_DEFAULT = 110  # 50 (leve) .. 220 (forte); overlay preto sobre a imagem

    BG_STATE = {"path": "", "dim": BG_DIM_DEFAULT, "_orig": None, "_scaled": None, "_key": None}

    def _hex_rgba(color: str, alpha: int) -> str:
        c = QColor(color)
        return "rgba(%d,%d,%d,%d)" % (c.red(), c.green(), c.blue(), alpha)

    def clamp_bg_dim(value) -> int:
        try:
            dim = int(value)
        except (TypeError, ValueError):
            return BG_DIM_DEFAULT
        return min(220, max(50, dim))

    def _load_background_state(path: str, dim=BG_DIM_DEFAULT) -> None:
        """Define/limpa a imagem de fundo (caminho vazio limpa)."""
        path = (path or "").strip()
        BG_STATE["dim"] = clamp_bg_dim(dim)
        if path == BG_STATE["path"]:
            return
        BG_STATE["path"] = path
        BG_STATE["_orig"] = None
        BG_STATE["_scaled"] = None
        BG_STATE["_key"] = None
        if path:
            pix = QPixmap(path)
            if pix.isNull():  # arquivo invalido/sumido: ignora sem quebrar
                BG_STATE["path"] = ""
            else:
                BG_STATE["_orig"] = pix

    def get_background_pixmap(width: int, height: int):
        """Imagem ja escalada para cobrir width x height (aspecto preservado, corte central)."""
        if BG_STATE["_orig"] is None or width < 8 or height < 8:
            return None
        key = (BG_STATE["path"], width, height)
        if BG_STATE["_key"] != key:
            BG_STATE["_scaled"] = BG_STATE["_orig"].scaled(
                width, height,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            BG_STATE["_key"] = key
        return BG_STATE["_scaled"]

    def background_image_active() -> bool:
        return bool(BG_STATE["path"])

    _TOOL_FONT_FAMILY = ""

    def load_tool_font_family() -> str:
        """Carrega GODOFWAR.TTF da pasta da tool (uma unica vez por sessao)."""
        global _TOOL_FONT_FAMILY
        if _TOOL_FONT_FAMILY:
            return _TOOL_FONT_FAMILY
        font_path = tool_font_path()
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    _TOOL_FONT_FAMILY = families[0]
        return _TOOL_FONT_FAMILY

    def apply_dark_palette(app):
        """Same dark palette recipe as Wad Studio's main.py."""
        from PySide6.QtGui import QPalette, QColor
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(WAD_BG))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(WAD_FG))
        pal.setColor(QPalette.ColorRole.Base, QColor(WAD_HEX_BG))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(WAD_PANEL_ALT))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(WAD_PANEL))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(WAD_FG))
        pal.setColor(QPalette.ColorRole.Text, QColor(WAD_FG))
        pal.setColor(QPalette.ColorRole.Button, QColor(WAD_PANEL_ALT))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(WAD_FG))
        pal.setColor(QPalette.ColorRole.Link, QColor(WAD_ACCENT))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(WAD_ACCENT_DIM))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(WAD_ACCENT_HOV))
        app.setPalette(pal)

    def build_stylesheet(scale: float) -> str:
        """Wad Studio density: mono 11-12px, compact buttons, thin scrollbars."""
        def px(n: float) -> int:
            return int(round(n * scale))
        # Com imagem de fundo: canvas transparente (a imagem e pintada pela
        # janela principal) e paineis de vidro; menus/dialogos continuam
        # solidos porque sao janelas separadas, sem imagem atras.
        if background_image_active():
            win_bg = canvas = scroll_bg = "transparent"
            glass_panel = _hex_rgba(WAD_PANEL, 170)
            glass_panel_alt = _hex_rgba(WAD_PANEL_ALT, 180)
            glass_hex = _hex_rgba(WAD_HEX_BG, 188)
            glass_btn = _hex_rgba(WAD_PANEL_ALT, 205)
            glass_alt_row = _hex_rgba(WAD_PANEL_ALT, 140)
        else:
            win_bg = canvas = scroll_bg = WAD_BG
            glass_panel, glass_panel_alt = WAD_PANEL, WAD_PANEL_ALT
            glass_hex, glass_btn = WAD_HEX_BG, WAD_PANEL_ALT
            glass_alt_row = WAD_PANEL_ALT
        css = f"""
            QMainWindow {{ background: {win_bg}; }}
            QDialog {{ background: {WAD_BG}; }}
            QWidget {{ background: {canvas}; color: {WAD_FG};
                       font-family: 'Consolas', 'Courier New', monospace; font-size: {px(11)}px; }}
            #SidePanel {{ background: {glass_panel}; }}
            #PanelHeader {{ background: {glass_panel_alt}; border-bottom: 1px solid {WAD_BORDER}; }}
            #PanelHeaderText {{ color: {WAD_ACCENT}; font-size: {px(9)}px; letter-spacing: {px(2)}px;
                                font-weight: bold; background: transparent; }}
            #PanelTag {{ color: {WAD_FG_DIM}; font-size: {px(10)}px; background: transparent; }}
            #PanelMeta {{ color: {WAD_FG_DIM}; font-size: {px(10)}px; padding: {px(2)}px {px(8)}px;
                          border-top: 1px solid {WAD_BORDER}; background: {glass_panel}; }}
            #FilterField {{ background: {glass_hex}; border: none; border-bottom: 1px solid {WAD_BORDER};
                            border-radius: 0; padding: {px(4)}px {px(8)}px; font-size: {px(11)}px; }}
            #FilterField:focus {{ border-bottom: 1px solid {WAD_ACCENT}; }}
            QToolBar#MainToolbar {{ background: {glass_panel}; border-bottom: 1px solid {WAD_BORDER};
                                    spacing: {px(2)}px; padding: {px(2)}px {px(4)}px; }}
            QToolBar#MainToolbar QToolButton {{ background: transparent; color: {WAD_FG};
                                    border: 1px solid transparent; border-radius: {px(3)}px;
                                    padding: {px(3)}px {px(9)}px; font-size: {px(11)}px; }}
            QToolBar#MainToolbar QToolButton:hover {{ background: {WAD_PANEL_ALT};
                                    border-color: {WAD_ACCENT_DIM}; color: {WAD_ACCENT_HOV}; }}
            QToolBar#MainToolbar QToolButton:pressed,
            QToolBar#MainToolbar QToolButton:checked {{ background: {WAD_ACCENT_DIM}; color: {WAD_ACCENT_HOV}; }}
            QToolBar::separator {{ background: {WAD_BORDER}; width: 1px; margin: {px(3)}px {px(2)}px; }}
            QMenuBar {{ background: {WAD_PANEL}; color: {WAD_FG}; }}
            QMenuBar::item {{ padding: {px(3)}px {px(8)}px; background: transparent; }}
            QMenuBar::item:selected {{ background: {WAD_ACCENT_DIM}; color: {WAD_ACCENT_HOV}; }}
            QMenu {{ background: {WAD_PANEL}; color: {WAD_FG}; border: 1px solid {WAD_BORDER}; }}
            QMenu::item {{ padding: {px(3)}px {px(18)}px; }}
            QMenu::item:selected {{ background: {WAD_ACCENT_DIM}; color: {WAD_ACCENT_HOV}; }}
            QPushButton {{ background: {glass_btn}; color: {WAD_FG_MID}; border: 1px solid {WAD_BORDER};
                           border-radius: {px(3)}px; padding: {px(4)}px {px(12)}px; font-size: {px(11)}px; }}
            QPushButton:hover {{ background: #2E2E34; border-color: {WAD_ACCENT}; color: {WAD_FG}; }}
            QPushButton:pressed {{ background: {WAD_ACCENT_DIM}; border-color: {WAD_ACCENT}; color: {WAD_ACCENT_HOV}; }}
            QPushButton:disabled {{ color: {WAD_FG_DIM}; border-color: {WAD_PANEL_ALT}; background: {WAD_BG}; }}
            QPushButton#AccentButton {{ background: {WAD_ACCENT_DIM}; border: 1px solid {WAD_ACCENT};
                                        color: {WAD_ACCENT_HOV}; font-weight: bold; }}
            QPushButton#AccentButton:hover {{ background: {WAD_ACCENT}; color: white; }}
            QPushButton#MiniButton {{ padding: {px(2)}px {px(7)}px; font-size: {px(10)}px; }}
            QPushButton#MiniButton:checked {{ background: {WAD_ACCENT_DIM}; border-color: {WAD_ACCENT}; color: {WAD_ACCENT_HOV}; font-weight: bold; }}
            QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox {{ background: {glass_hex}; color: {WAD_FG};
                           border: 1px solid {WAD_BORDER}; border-radius: {px(2)}px;
                           padding: {px(3)}px {px(7)}px; font-size: {px(11)}px;
                           selection-background-color: #0078D7; selection-color: #FFFFFF; }}
            QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {WAD_ACCENT}; }}
            QComboBox::drop-down {{ border: none; width: {px(16)}px; }}
            QComboBox QAbstractItemView {{ background: {WAD_PANEL}; color: {WAD_FG};
                           selection-background-color: {WAD_ACCENT_DIM}; border: 1px solid {WAD_BORDER}; }}
            QComboBox:disabled {{ color: {WAD_ACCENT_HOV}; background: {WAD_PANEL_ALT}; }}
            QPlainTextEdit {{ font-family: 'Consolas', 'Courier New', monospace; font-size: {px(12)}px; }}
            QListWidget {{ background: {glass_panel}; color: {WAD_FG}; border: none; outline: none;
                           font-size: {px(11)}px; alternate-background-color: {glass_alt_row}; }}
            QListWidget::item {{ padding: {px(3)}px {px(8)}px; border-left: 2px solid transparent; }}
            QListWidget::item:hover {{ background: {WAD_PANEL_ALT}; }}
            QListWidget::item:selected {{ background: #3A0C0C; color: {WAD_ACCENT_HOV};
                           border-left: 2px solid {WAD_ACCENT}; }}
            QTableWidget {{ background: {glass_panel}; alternate-background-color: {glass_alt_row};
                           color: {WAD_FG}; gridline-color: transparent;
                           selection-background-color: #3A0C0C; selection-color: {WAD_ACCENT_HOV};
                           border: none; font-size: {px(11)}px; }}
            QTableWidget::item {{ padding: {px(3)}px {px(8)}px; border-left: 2px solid transparent; }}
            QTableWidget::item:hover {{ background: {WAD_PANEL_ALT}; }}
            QTableWidget::item:selected {{ background: #3A0C0C; color: {WAD_ACCENT_HOV};
                           border-left: 2px solid {WAD_ACCENT}; }}
            QHeaderView::section {{ background: {WAD_PANEL_ALT}; color: {WAD_FG_DIM}; border: none;
                           border-bottom: 1px solid {WAD_BORDER}; border-right: 1px solid {WAD_BORDER};
                           padding: {px(3)}px {px(5)}px; font-size: {px(10)}px; letter-spacing: 1px; }}
            QCheckBox {{ color: {WAD_FG}; background: transparent; font-size: {px(11)}px; spacing: {px(5)}px; }}
            QGroupBox {{ border: 1px solid {WAD_BORDER}; border-radius: {px(3)}px;
                         margin-top: {px(8)}px; padding-top: {px(6)}px; font-weight: bold; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: {px(10)}px; padding: 0 {px(4)}px;
                         color: {WAD_ACCENT}; font-size: {px(10)}px; letter-spacing: {px(1)}px; }}
            QLabel {{ color: {WAD_FG}; background: transparent; }}
            QLabel#MutedLabel {{ color: {WAD_FG_DIM}; font-size: {px(10)}px; }}
            QStatusBar {{ background: {glass_panel}; color: {WAD_FG_MID}; font-size: {px(11)}px;
                          border-top: 1px solid {WAD_BORDER}; }}
            QTabWidget::pane {{ border: 1px solid {WAD_BORDER}; background: {canvas}; border-top: none; }}
            QTabBar::tab {{ background: {glass_panel}; color: {WAD_FG_DIM}; border: 1px solid {WAD_BORDER};
                          border-bottom: none; padding: {px(4)}px {px(14)}px; margin-right: 1px; font-size: {px(11)}px; }}
            QTabBar::tab:selected {{ background: {WAD_BG}; color: {WAD_ACCENT_HOV}; border-top: 2px solid {WAD_ACCENT}; }}
            QScrollBar:vertical {{ background: {scroll_bg}; width: {px(8)}px; border: none; }}
            QScrollBar::handle:vertical {{ background: #444450; border-radius: {px(4)}px; min-height: {px(16)}px; margin: 1px; }}
            QScrollBar::handle:vertical:hover {{ background: {WAD_ACCENT}; }}
            QScrollBar:horizontal {{ background: {scroll_bg}; height: {px(8)}px; border: none; }}
            QScrollBar::handle:horizontal {{ background: #444450; border-radius: {px(4)}px; min-width: {px(16)}px; margin: 1px; }}
            QScrollBar::handle:horizontal:hover {{ background: {WAD_ACCENT}; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
            QSplitter::handle {{ background: {WAD_BORDER}; }}
        """
        return css


    def apply_ui_scale(app, scale: float):
        base = getattr(app, "_gow2_base_font", None)
        if base is None:
            base = app.font()
            app._gow2_base_font = base
        font = QFont(base)
        size = base.pointSizeF()
        font.setPointSizeF(max(6.0, (size if size > 0 else 9.0) * scale))
        app.setFont(font)
        app.setStyleSheet(build_stylesheet(scale))


    class PreviewWidget(QWidget):
        """Previa CRT na geometria REAL medida no FLP_HUD (s10).

        Numeros extraidos com o parser oficial do formato (port do
        god_of_war_browser/pack/wad/flp, Go) aplicado ao R_PERMA.WAD
        vanilla e ao do mod widescreen, chaveando os keyframes:
        - stage: cabecalho 12800x9600 em 16.16 => 800x600;
        - root coloca o container "MessageTemplates" em (400, 485);
        - Datas6[1..5] (Line1..5) la dentro em x=-397.5 (abs: 2.5) e
          y = -140.75, -103.25, -65.75, -28.25, 9.25 => passo 37.5,
          linha1 no topo; escala 1.0;
        - cada linha e um DynamicLabel com w1=440 (vanilla) e fontH=21;
          o mod 16:9 criou linhas novas com w1=480 => BOX_W por ratio;
        - ultima linha em y_abs 494.25 (600-494.25=105.75 do fundo).
        O usuario escolhe por NOME (esq/centro/dir, topo/meio/base).
        """

        STAGE_W = 800.0
        STAGE_H = 600.0            # medido no cabecalho do FLP (12800x9600 @16.16)
        X_LEFT = 2.5               # x absoluto da linha 1..5 (400 - 377.5? -> -397.5 rel.)
        BOTTOM_OFF = 105.75        # distancia da ultima linha ate a borda de baixo
        SAFE = 30.0
        LINE_H = 21.0              # fontHeight dos DynamicLabel
        GAPS = (31.25, 37.5, 43.75)  # normal = 37.5 exato, medido nos keyframes

        def _box_w(self):
            return 480.0 if self.ratio else 440.0  # w1 vanilla x mod 16:9 (medido)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.text = ""
            self.mode = "runtime"
            self.max_lines = 3
            self.align = 0
            self.anchor = 1
            self.gap = 1
            self.ratio = 0
            self.setMinimumHeight(190)
            self.setAutoFillBackground(False)

        def set_state(self, text: str, mode: str, max_lines: int, align: int, anchor: int, gap: int):
            self.text = text
            self.mode = mode
            self.max_lines = max_lines
            self.align = max(0, min(2, align))
            self.anchor = max(0, min(2, anchor))
            self.gap = max(0, min(2, gap))
            self.update()

        def set_placement(self, align: int, anchor: int, gap: int, ratio: int = 0):
            self.align = max(0, min(2, align))
            self.anchor = max(0, min(2, anchor))
            self.gap = max(0, min(2, gap))
            self.ratio = max(0, min(1, ratio))
            self.update()

        def _stage_lines(self, n: int):
            spacing = self.GAPS[self.gap]
            box = self._box_w()
            if self.align == 0:
                x = self.X_LEFT
            elif self.align == 2:
                x = self.STAGE_W - box - self.X_LEFT
            else:
                x = (self.STAGE_W - box) / 2.0
            if self.anchor == 0:
                y_last = self.BOTTOM_OFF + self.LINE_H + spacing * (n - 1)
            elif self.anchor == 1:
                y_last = self.STAGE_H / 2.0 + spacing * (n - 1) / 2.0 + self.LINE_H / 2.0
            else:
                y_last = self.STAGE_H - self.BOTTOM_OFF  # 494.25: posicao real do jogo
            return x, [y_last - (n - 1 - i) * spacing for i in range(n)]

        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), QColor("#141417"))
            area = self.rect().adjusted(8, 8, -8, -8)
            # 4:3 = TV original do PS2; 16:9 = mods widescreen (o stage 800x448
            # casa 1:1 com a tela). O mapeamento usa sx/sy SEPARADOS, porque o
            # pixel do stage nao e quadrado no 4:3 (e e quase quadrado no 16:9).
            aspect = 4.0 / 3.0 if self.ratio == 0 else 16.0 / 9.0
            tv_w = min(float(area.width()), float(area.height()) * aspect)
            tv_h = tv_w / aspect
            cx = area.x() + (area.width() - tv_w) / 2.0
            cy = area.y() + (area.height() - tv_h) / 2.0
            screen = QRectF(cx, cy, tv_w, tv_h)
            painter.setPen(QPen(QColor("#3a3a42"), 3))
            painter.drawRoundedRect(screen.adjusted(-4, -4, 4, 4), 12, 12)
            painter.fillRect(screen, QColor("#07120e"))
            painter.setPen(QPen(QColor("#0d241b"), 1))
            for y in range(int(screen.top()) + 2, int(screen.bottom()), 4):
                painter.drawLine(int(screen.left()) + 2, y, int(screen.right()) - 2, y)
            sx = tv_w / self.STAGE_W
            sy = tv_h / self.STAGE_H
            painter.setPen(QPen(QColor("#28453a"), 1, Qt.DashLine))
            painter.drawRect(QRectF(screen.left() + self.SAFE * sx, screen.top() + self.SAFE * sy,
                                    tv_w - 2 * self.SAFE * sx, tv_h - 2 * self.SAFE * sy))

            lines = self.text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            if self.text == "":
                lines = [""]
            if len(lines) > self.max_lines:
                painter.setPen(QColor("#e06a5f"))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(QRectF(screen.left() + 8, screen.top() + 4, tv_w - 16, 14),
                                 Qt.AlignRight, "aviso: %d linhas; limite %d" % (len(lines), self.max_lines))
            shown = lines[-self.max_lines:]
            x, ys = self._stage_lines(len(shown))
            font_size = max(8, int(self.LINE_H * 0.72 * min(sx, sy)))
            for line, yb in zip(shown, ys):
                box = QRectF(screen.left() + x * sx, screen.top() + (yb - self.LINE_H) * sy,
                             self._box_w() * sx, self.LINE_H * sy)
                painter.setPen(QPen(QColor("#426b4e"), 1, Qt.DashLine))
                painter.drawRect(box)
                painter.setPen(QColor("#c8ef75"))
                painter.setFont(QFont("Consolas", font_size))
                painter.drawText(QRectF(box.x() + 2, box.y() - 1, box.width() - 4, box.height()),
                                 Qt.AlignLeft | Qt.AlignVCenter, line)
            painter.setPen(QColor("#83ad8d"))
            painter.setFont(QFont("Segoe UI", 8))
            if self.ratio == 0:
                tag = "4:3 \u00b7 stage 800\u00d7600 medido no FLP \u00b7 5 linhas \u00b7 passo 37.5px \u00b7 caixa 440"
            else:
                tag = "16:9 \u00b7 mod widescreen \u00b7 mesmo stage 800\u00d7600 esticado \u00b7 caixa 480 (novas DYN)"
            painter.drawText(QRectF(screen.left() + 8, screen.bottom() - 16, tv_w - 16, 12),
                             Qt.AlignLeft, tag)


    class FlatListWidget(QListWidget):
        """Painel esquerdo estilo Wad Studio, mas com a API de QComboBox.

        currentIndex()/setCurrentIndex()/currentIndexChanged(int) espelham o
        QComboBox antigo, então os ~15 pontos de uso continuam funcionando.
        """

        currentIndexChanged = Signal(int)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAlternatingRowColors(True)
            self.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.setSelectionMode(QAbstractItemView.SingleSelection)
            self.setUniformItemSizes(True)
            self.setWordWrap(False)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            self.currentRowChanged.connect(self.currentIndexChanged.emit)

        def currentIndex(self) -> int:
            return self.currentRow()

        def setCurrentIndex(self, index: int):
            self.setCurrentRow(index)


    class App(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("God of War Text Editor")
            self.config = read_config()
            self._ui_scale = clamp_ui_scale(self.config.get("scale", 1.0))
            ensure_background_folder()
            ensure_icon_folder()
            self._apply_window_icon_from_folder()
            self._bg_from_folder = False
            _bg_auto = detect_folder_background()
            if _bg_auto:
                self._bg_from_folder = True
                _load_background_state(_bg_auto, self.config.get("bg_dim", BG_DIM_DEFAULT))
            else:
                _load_background_state(self.config.get("bg_image", ""), self.config.get("bg_dim", BG_DIM_DEFAULT))
            self.setMinimumSize(int(980 * self._ui_scale), int(640 * self._ui_scale))

            self.wad: WadFile | None = None
            self.wad_path: str | None = None
            self.text_resources: list[WadTag] = []
            self.active_tag: WadTag | None = None
            self.active_resource: TextResource | None = None
            self.resource_messages: list[Message] = []
            self.current_index: int | None = None
            self.dirty = False
            self._open_snapshot: dict = {}
            self._loading = False
            # s1: undo/redo global de edicoes aplicadas (texto por mensagem).
            # Entradas: (indice do recurso, indice da mensagem, texto anterior).
            self._undo_stack: list[tuple[int, int, str]] = []
            self._redo_stack: list[tuple[int, int, str]] = []

            self._build_ui()
            self._build_actions()
            self._sync_codec_ui(None)
            if background_image_active():
                # Reaplica o stylesheet agora com as cores translucidas do fundo.
                apply_ui_scale(QApplication.instance(), self._ui_scale)
            geom = (self.config.get("geometry") or "").strip()
            restored = False
            if geom:
                try:
                    restored = bool(self.restoreGeometry(QByteArray.fromHex(geom.encode())))
                except (TypeError, ValueError):
                    restored = False
            if not restored:
                self.resize(int(1440 * self._ui_scale), int(900 * self._ui_scale))
            saved_codec = self.config.get("codec") or ""
            if saved_codec in TEXT_CODECS:
                with QSignalBlocker(self.codec_box):
                    self.codec_box.setCurrentText(saved_codec)
            if getattr(self, "_bg_from_folder", False) and BG_STATE["path"]:
                self.status_label.setText(
                    f"Pronto. • Fundo detectado na pasta {BG_FOLDERNAME}: {os.path.basename(BG_STATE['path'])}"
                )
            else:
                self.status_label.setText("Pronto.")

        def _panel_header(self, title: str):
            """Linha de topo de painel (26px): rótulo CAIXA ALTA + controles à direita."""
            bar = QWidget(self)
            bar.setObjectName("PanelHeader")
            lay = QHBoxLayout(bar)
            lay.setContentsMargins(int(8 * self._ui_scale), 2, int(8 * self._ui_scale), 2)
            lay.setSpacing(int(4 * self._ui_scale))
            label = QLabel(title)
            label.setObjectName("PanelHeaderText")
            lay.addWidget(label)
            lay.addStretch(1)
            return bar, lay

        def _build_ui(self):
            # Layout estilo Wad Studio: painéis com header próprio, splitter 2px,
            # sem título/creditos/rodape; esquerda = apenas os recursos de texto.
            central = QWidget(self)
            self.setCentralWidget(central)
            root = QVBoxLayout(central)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            status_bar = self.statusBar()
            self.status_label = QLabel("Pronto.")
            self.status_label.setObjectName("MutedLabel")
            status_bar.addWidget(self.status_label, 1)
            self.info_label = QLabel("Abra um WAD para começar.")
            self.info_label.setStyleSheet(f"color: {WAD_ACCENT}; font-size: {int(10 * self._ui_scale)}px; padding: 0 6px;")
            status_bar.addPermanentWidget(self.info_label)

            splitter = QSplitter(Qt.Horizontal)
            splitter.setHandleWidth(2)
            splitter.setChildrenCollapsible(False)
            root.addWidget(splitter, 1)

            # esquerda: recursos de texto (nada de botões aqui)
            left = QWidget()
            left.setObjectName("SidePanel")
            left_v = QVBoxLayout(left)
            left_v.setContentsMargins(0, 0, 0, 0)
            left_v.setSpacing(0)
            left_header, _ = self._panel_header("RECURSOS DE TEXTO")
            left_v.addWidget(left_header)
            self.resource_box = FlatListWidget()
            self.resource_box.currentIndexChanged.connect(self.on_resource_change)
            left_v.addWidget(self.resource_box, 1)
            self.resource_meta_label = QLabel("")
            self.resource_meta_label.setObjectName("PanelMeta")
            self.resource_meta_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            left_v.addWidget(self.resource_meta_label)
            splitter.addWidget(left)

            # meio: tabela de mensagens com filtro e ações estruturais compactas
            mid = QWidget()
            mid.setObjectName("SidePanel")
            mid_v = QVBoxLayout(mid)
            mid_v.setContentsMargins(0, 0, 0, 0)
            mid_v.setSpacing(0)
            mid_header, mid_hl = self._panel_header("MENSAGENS")
            for text, slot in (("+ Nova", self.new_message), ("Duplicar", self.duplicate_message), ("Excluir", self.delete_message)):
                mini = QPushButton(text)
                mini.setObjectName("MiniButton")
                mini.clicked.connect(slot)
                mid_hl.addWidget(mini)
            mid_v.addWidget(mid_header)
            self.search_entry = QLineEdit()
            self.search_entry.setObjectName("FilterField")
            self.search_entry.setPlaceholderText("filtrar por ID ou conteúdo…")
            self.search_entry.setClearButtonEnabled(True)
            self.search_entry.textChanged.connect(self.refresh_message_list)
            mid_v.addWidget(self.search_entry)
            self.message_table = QTableWidget(0, 1)
            self.message_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.message_table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.message_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.message_table.setAlternatingRowColors(True)
            self.message_table.setShowGrid(False)
            self.message_table.setTextElideMode(Qt.ElideRight)
            self.message_table.verticalHeader().setVisible(False)
            self.message_table.verticalHeader().setDefaultSectionSize(int(23 * self._ui_scale))
            self.message_table.horizontalHeader().setVisible(False)
            self.message_table.horizontalHeader().setStretchLastSection(True)
            self.message_table.itemSelectionChanged.connect(self.on_message_select)
            mid_v.addWidget(self.message_table, 1)
            splitter.addWidget(mid)

            # direita: editor (com codificação no header) + prévia
            right = QSplitter(Qt.Vertical)
            right.setHandleWidth(2)
            right.setChildrenCollapsible(False)

            editor_panel = QWidget()
            editor_panel.setObjectName("SidePanel")
            editor_v = QVBoxLayout(editor_panel)
            editor_v.setContentsMargins(0, 0, 0, 0)
            editor_v.setSpacing(0)
            editor_header, editor_hl = self._panel_header("TEXTO DA MENSAGEM")
            codec_tag = QLabel("CODIF.")
            codec_tag.setObjectName("PanelTag")
            editor_hl.addWidget(codec_tag)
            self.codec_box = QComboBox()
            self.codec_box.addItems(list(TEXT_CODECS))
            self.codec_box.setMinimumContentsLength(10)
            self.codec_box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            self.codec_box.currentTextChanged.connect(self.on_codec_change)
            editor_hl.addWidget(self.codec_box)
            editor_hl.addStretch(1)
            apply_button = QPushButton("Aplicar texto")
            apply_button.setObjectName("AccentButton")
            apply_button.clicked.connect(self.apply_current)
            editor_hl.addWidget(apply_button)
            editor_v.addWidget(editor_header)
            self.editor = QPlainTextEdit()
            self.editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
            self.editor.setTabChangesFocus(False)
            self.editor.textChanged.connect(self.on_editor_changed)
            editor_v.addWidget(self.editor, 1)
            right.addWidget(editor_panel)

            preview_panel = QWidget()
            preview_panel.setObjectName("SidePanel")
            preview_v = QVBoxLayout(preview_panel)
            preview_v.setContentsMargins(0, 0, 0, 0)
            preview_v.setSpacing(0)
            self.preview_groups: dict[str, QButtonGroup] = {}
            preview_header, preview_hl = self._panel_header("PRÉVIA CRT / LAYOUT")
            self.preview_profile_box = QComboBox()
            self.preview_profile_box.addItems(["Automático", "GoW1 FLP_HUD (5 linhas)", "Runtime Flash (3 linhas)"])
            self.preview_profile_box.setMinimumContentsLength(12)
            self.preview_profile_box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            self.preview_profile_box.currentTextChanged.connect(self.update_preview)
            preview_hl.addWidget(self.preview_profile_box)
            ratio_tag = QLabel("TELA.")
            ratio_tag.setObjectName("PanelTag")
            preview_hl.addWidget(ratio_tag)
            ratio_group = QButtonGroup(self)
            ratio_group.setExclusive(True)
            for i, name in enumerate(("4:3", "16:9")):
                choice = QPushButton(name)
                choice.setObjectName("MiniButton")
                choice.setCheckable(True)
                choice.setToolTip("4:3 = TV original do PS2 (pixel amassado) \u00b7 16:9 = mods widescreen")
                ratio_group.addButton(choice, i)
                choice.clicked.connect(lambda _c=False, g=ratio_group: self._preview_choice("ratio", g))
                preview_hl.addWidget(choice)
            self.preview_groups["ratio"] = ratio_group
            try:
                start_ratio = int(self.config.get("preview_ratio", 0))
            except (TypeError, ValueError):
                start_ratio = 0
            first_ratio = ratio_group.button(max(0, min(1, start_ratio)))
            if first_ratio is not None:
                first_ratio.setChecked(True)
            preview_hl.addStretch(1)
            preview_v.addWidget(preview_header)
            # placement do texto: nomes que o usuario entende (sem X/Y/Z/zoom)
            geo_bar = QWidget()
            geo_bar.setObjectName("PanelHeader")
            geo_hl = QHBoxLayout(geo_bar)
            geo_hl.setContentsMargins(int(8 * self._ui_scale), 1, int(8 * self._ui_scale), 1)
            geo_hl.setSpacing(int(3 * self._ui_scale))
            real_tag = QLabel("ONDE")
            real_tag.setObjectName("PanelTag")
            geo_hl.addWidget(real_tag)
            self.preview_place_btn = QPushButton("REAL (jogo)")
            self.preview_place_btn.setObjectName("MiniButton")
            self.preview_place_btn.setCheckable(True)
            self.preview_place_btn.setToolTip(
                "Prévia na POSIÇÃO REAL medida no FLP_HUD (esq · base · passo 37,5px). "
                "Desmarque para ajustar os cantos na mão.")
            self.preview_place_btn.clicked.connect(self._toggle_preview_real)
            geo_hl.addWidget(self.preview_place_btn)
            for tag_text, key, names, default in (
                ("POS.", "align", ("ESQ", "CENTRO", "DIR"), 0),
                ("ALT.", "anchor", ("TOPO", "MEIO", "BASE"), 1),
                ("ESPAÇ.", "gap", ("FINO", "NORMAL", "LARGO"), 1),
            ):
                tag = QLabel(tag_text)
                tag.setObjectName("PanelTag")
                geo_hl.addWidget(tag)
                group = QButtonGroup(self)
                group.setExclusive(True)
                for i, name in enumerate(names):
                    choice = QPushButton(name)
                    choice.setObjectName("MiniButton")
                    choice.setCheckable(True)
                    choice.setToolTip({"align": "posição horizontal do texto na tela",
                                       "anchor": "onde o bloco de linhas encosta na vertical",
                                       "gap": "distância entre linhas do MessageTemplate"}[key])
                    group.addButton(choice, i)
                    choice.clicked.connect(lambda _c=False, k=key, g=group: self._preview_choice(k, g))
                    geo_hl.addWidget(choice)
                self.preview_groups[key] = group
                try:
                    start = int(self.config.get("preview_" + key, default))
                except (TypeError, ValueError):
                    start = default
                btn = group.button(max(0, min(len(names) - 1, start)))
                if btn is not None:
                    btn.setChecked(True)
            self._preview_real = str(self.config.get("preview_place_real", "1")) == "1"
            self._sync_preview_real_ui()
            self.preview_hint_label = QLabel("")
            self.preview_hint_label.setObjectName("PanelTag")
            self.preview_hint_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            geo_hl.addStretch(1)
            geo_hl.addWidget(self.preview_hint_label)
            preview_v.addWidget(geo_bar)
            self.preview = PreviewWidget()
            self._apply_preview_placement()
            preview_v.addWidget(self.preview, 1)
            right.addWidget(preview_panel)

            right.setStretchFactor(0, 2)
            right.setStretchFactor(1, 1)
            splitter.addWidget(right)
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 0)
            splitter.setStretchFactor(2, 1)
            self._split_initial = (int(250 * self._ui_scale), int(430 * self._ui_scale))
            self._splitter_main = splitter

        def showEvent(self, event):
            super().showEvent(event)
            # proporcoes iniciais so pegam depois que a fila de resize assentar
            if not getattr(self, "_split_done", False):
                self._split_done = True
                QTimer.singleShot(0, self._apply_split_sizes)

        def _apply_split_sizes(self):
            left, mid = self._split_initial
            avail = self._splitter_main.width()
            if avail > left + mid + int(320 * self._ui_scale):
                self._splitter_main.setSizes([left, mid, avail - left - mid])

        def _build_actions(self):
            self.action_open = QAction("Abrir WAD", self)
            self.action_open.setShortcut(QKeySequence("Ctrl+O"))
            self.action_open.triggered.connect(self.open_wad)
            self.addAction(self.action_open)

            self.action_save = QAction("Salvar WAD como...", self)
            self.action_save.setShortcut(QKeySequence("Ctrl+S"))
            self.action_save.triggered.connect(self.save_wad_as)
            self.addAction(self.action_save)

            self.action_undo = QAction("Desfazer", self)
            self.action_undo.setShortcut(QKeySequence("Ctrl+Z"))
            self.action_undo.triggered.connect(self.undo_action)
            self.addAction(self.action_undo)

            self.action_undo_global = QAction("Desfazer edição aplicada", self)
            self.action_undo_global.setShortcut(QKeySequence("Ctrl+Shift+Z"))
            self.action_undo_global.triggered.connect(self.undo_global)
            self.addAction(self.action_undo_global)

            self.action_redo_global = QAction("Refazer edição aplicada", self)
            self.action_redo_global.setShortcut(QKeySequence("Ctrl+Shift+Y"))
            self.action_redo_global.triggered.connect(self.redo_global)
            self.addAction(self.action_redo_global)

            self.action_find_replace = QAction("Localizar/Substituir", self)
            self.action_find_replace.setShortcut(QKeySequence("Ctrl+H"))
            self.action_find_replace.triggered.connect(self.show_find_replace)
            self.addAction(self.action_find_replace)

            self.action_find = QAction("Buscar", self)
            self.action_find.setShortcut(QKeySequence("Ctrl+F"))
            self.action_find.triggered.connect(lambda: self.search_entry.setFocus())
            self.addAction(self.action_find)

            self.action_export = QAction("Exportar recurso", self)
            self.action_export.triggered.connect(self.export_txt)
            self.action_import = QAction("Importar recurso", self)
            self.action_import.triggered.connect(self.import_txt)
            self.action_diagnostics = QAction("Diagnóstico", self)
            self.action_diagnostics.triggered.connect(self.show_diagnostics)
            self.action_static_labels = QAction("Rótulos desenhados do filme (FLP)...", self)
            self.action_static_labels.triggered.connect(self.show_static_labels)
            self.action_exit = QAction("Sair", self)
            self.action_exit.triggered.connect(self.close)
            self.action_about = QAction("Sobre", self)
            self.action_about.triggered.connect(self.show_about)

            self.action_fullscreen = QAction("Tela cheia", self)
            self.action_fullscreen.setShortcut(QKeySequence(Qt.Key_F11))
            self.action_fullscreen.triggered.connect(self.toggle_fullscreen)
            self.action_zoom_in = QAction("Aumentar fonte da interface", self)
            self.action_zoom_in.setShortcut(QKeySequence("Ctrl+="))
            self.action_zoom_in.triggered.connect(lambda: self.set_ui_scale(self._ui_scale + 0.05))
            self.action_zoom_out = QAction("Diminuir fonte da interface", self)
            self.action_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
            self.action_zoom_out.triggered.connect(lambda: self.set_ui_scale(self._ui_scale - 0.05))
            self.action_zoom_reset = QAction("Interface em 100%", self)
            self.action_zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
            self.action_zoom_reset.triggered.connect(lambda: self.set_ui_scale(1.0))
            self.action_changes = QAction("Alterações", self)
            self.action_changes.triggered.connect(self.show_changes)
            self.addAction(self.action_changes)

            # ---- Imagem de fundo personalizada ----
            self.action_bg_image = QAction("Definir imagem...", self)
            self.action_bg_image.triggered.connect(self.choose_background_image)
            self.action_bg_clear = QAction("Remover imagem", self)
            self.action_bg_clear.setEnabled(False)
            self.action_bg_clear.triggered.connect(self.clear_background_image)
            self.action_bg_reload = QAction("Recarregar da pasta", self)
            self.action_bg_reload.triggered.connect(self.reload_folder_background)
            self.action_icon_set = QAction("Definir ícone...", self)
            self.action_icon_set.triggered.connect(self.choose_window_icon)
            self.action_icon_reload = QAction("Recarregar da pasta", self)
            self.action_icon_reload.triggered.connect(self.reload_window_icon)
            self.action_icon_clear = QAction("Remover ícone", self)
            self.action_icon_clear.triggered.connect(self.clear_window_icon)
            self._bg_dim_actions = []
            for label, value in (("Leve", 70), ("Médio", 110), ("Forte", 160)):
                act = QAction(label, self)
                act.setCheckable(True)
                act._bg_dim_value = value
                act.triggered.connect(lambda _checked=False, v=value, a=act: self.set_background_dim(v, a))
                self._bg_dim_actions.append(act)

            file_menu = self.menuBar().addMenu("Arquivo")
            file_menu.addAction(self.action_open)
            file_menu.addAction(self.action_save)
            file_menu.addSeparator()
            file_menu.addAction(self.action_export)
            file_menu.addAction(self.action_import)
            file_menu.addSeparator()
            file_menu.addAction(self.action_exit)
            tools_menu = self.menuBar().addMenu("Ferramentas")
            tools_menu.addAction(self.action_diagnostics)
            tools_menu.addAction(self.action_static_labels)
            tools_menu.addAction(self.action_find_replace)
            tools_menu.addAction(self.action_changes)
            tools_menu.addAction(self.action_undo)
            tools_menu.addAction(self.action_undo_global)
            tools_menu.addAction(self.action_redo_global)
            view_menu = self.menuBar().addMenu("Visualizar")
            view_menu.addAction(self.action_find)
            view_menu.addSeparator()
            view_menu.addAction(self.action_fullscreen)
            view_menu.addAction(self.action_zoom_in)
            view_menu.addAction(self.action_zoom_out)
            view_menu.addAction(self.action_zoom_reset)
            bg_menu = view_menu.addMenu("Imagem de fundo")
            bg_menu.addAction(self.action_bg_image)
            bg_menu.addAction(self.action_bg_reload)
            bg_menu.addAction(self.action_bg_clear)
            bg_menu.addSeparator()
            dim_menu = bg_menu.addMenu("Escurecimento")
            for act in self._bg_dim_actions:
                dim_menu.addAction(act)
            icon_menu = view_menu.addMenu("Ícone da janela")
            icon_menu.addAction(self.action_icon_set)
            icon_menu.addAction(self.action_icon_reload)
            icon_menu.addAction(self.action_icon_clear)
            self._sync_bg_menu()
            help_menu = self.menuBar().addMenu("Ajuda")
            help_menu.addAction(self.action_about)

            self._build_toolbar()

        def _apply_title_style(self):
            """Titulo discreto 'GOW Text Editor' na fonte GodOfWar, em vermelho."""
            family = load_tool_font_family()
            px = max(12, int(16 * self._ui_scale))
            family_css = (family or "Consolas").replace("\\", "").replace("'", "")
            self.title_label.setStyleSheet(
                f"#AppTitle {{ color: {WAD_ACCENT_HOV}; font-family: \"{family_css}\";"
                f" font-size: {px}px; letter-spacing: {max(1, px // 14)}px;"
                f" padding-right: {int(10 * self._ui_scale)}px; }}"
            )

        def _build_toolbar(self):
            """Barra compacta estilo Wad Studio: botões de texto pequenos, separados por grupo."""
            toolbar = self.addToolBar("Ações")
            toolbar.setObjectName("MainToolbar")
            toolbar.setMovable(False)
            toolbar.setFloatable(False)
            toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
            toolbar.setContextMenuPolicy(Qt.PreventContextMenu)
            self.title_label = QLabel("GOW Text Editor")
            self.title_label.setObjectName("AppTitle")
            self._apply_title_style()
            toolbar.addWidget(self.title_label)
            toolbar.addSeparator()
            for action in (self.action_open, self.action_save):
                toolbar.addAction(action)
            toolbar.addSeparator()
            for action in (self.action_export, self.action_import):
                toolbar.addAction(action)
            toolbar.addSeparator()
            for action in (self.action_find_replace, self.action_changes, self.action_diagnostics):
                toolbar.addAction(action)

        def _codec(self) -> str:
            return TEXT_CODECS[self.codec_box.currentText()]

        @staticmethod
        def _is_gow2_runtime_tag(tag: WadTag | None) -> bool:
            return tag is not None and tag.upper_name == "MSGS_TXT"

        def _codec_for_tag(self, tag: WadTag | None = None) -> str:
            tag = tag if tag is not None else self.active_tag
            if self._is_gow2_runtime_tag(tag):
                return GOW2_RUNTIME_UTF8_CODEC
            return self._codec()

        def _sync_codec_ui(self, tag: WadTag | None = None):
            if self._is_gow2_runtime_tag(tag):
                with QSignalBlocker(self.codec_box):
                    self.codec_box.setCurrentText("UTF-8 (runtime GoW2)")
                self.codec_box.setEnabled(False)
            else:
                if self.codec_box.currentText() == "UTF-8 (runtime GoW2)":
                    with QSignalBlocker(self.codec_box):
                        self.codec_box.setCurrentText("Windows-1252 (browser/legado)")
                self.codec_box.setEnabled(True)

        def _set_status(self, text: str):
            self.status_label.setText(text)
            self.statusBar().showMessage(text)

        def open_wad(self):
            path, _ = QFileDialog.getOpenFileName(self, "Abrir WAD de God of War", self.config.get("last_open_dir") or "", "WAD (*.wad *.WAD *.txt);;Todos os arquivos (*)")
            if not path:
                return
            self._remember_dir("last_open_dir", path)
            try:
                wad = WadFile.load(path)
                resources = wad.text_tags()
                if not resources:
                    raise ValueError("Nenhum recurso .TXT ou MSGS_TXT foi encontrado neste WAD.")
                with QSignalBlocker(self.codec_box):
                    if wad.variant.startswith("GoW2") and any(tag.upper_name == "MSGS_TXT" for tag in resources):
                        self.codec_box.setCurrentText("UTF-8 (runtime GoW2)")
                    else:
                        self.codec_box.setCurrentText("Windows-1252 (browser/legado)")
                self.wad = wad
                self.wad_path = path
                self.text_resources = resources
                with QSignalBlocker(self.resource_box):
                    self.resource_box.clear()
                    for tag in resources:
                        self.resource_box.addItem(f"{tag.name} • {tag.resource_kind} • tag {tag.index} • {len(tag.data):,} bytes")
                    self.resource_box.setCurrentIndex(0)
                self.dirty = False
                self._open_snapshot = {}
                self.load_resource(0)
                self._take_open_snapshot()
                self.info_label.setText(f"{os.path.basename(path)} • {wad.variant} • {len(wad.tags):,} tags • {len(resources)} recurso(s) editável(is)")
                self._set_status("WAD carregado")
            except Exception as exc:
                QMessageBox.critical(self, "Erro ao abrir WAD", str(exc))

        def on_resource_change(self, index: int):
            if self.wad is None or self._loading or index < 0:
                return
            self.commit_current(update_list=False)
            self.load_resource(index)

        def on_codec_change(self, _text: str):
            if _text and self.config.get("codec") != _text:
                self.config["codec"] = _text
                write_config(self.config)
            if self.wad is None or self.active_tag is None or self._is_gow2_runtime_tag(self.active_tag):
                self._sync_codec_ui(self.active_tag)
                return
            try:
                self.commit_current(update_list=False)
                self.load_resource(self.resource_box.currentIndex())
            except Exception as exc:
                QMessageBox.critical(self, "Codificação", str(exc))

        def load_resource(self, resource_index: int):
            if resource_index < 0 or resource_index >= len(self.text_resources):
                return
            tag = self.text_resources[resource_index]
            codec = self._codec_for_tag(tag)
            self._sync_codec_ui(tag)
            try:
                resource = TextResource(tag.data, codec)
            except Exception as exc:
                QMessageBox.critical(self, "Recurso não reconhecido", f"{tag.name}:\n\n{exc}")
                return
            if codec == GOW2_RUNTIME_UTF8_CODEC and resource.runtime_legacy_cp1252:
                converted = resource.to_bytes()
                if converted != tag.data:
                    # migracao para UTF-8 e politica da tool (o runtime le UTF-8),
                    # nao edicao do usuario: converte em memoria SEM sujar o WAD.
                    # Quem salvar grava a migracao; quem fechar sem salvar mantem o
                    # arquivo legado intacto no disco.
                    tag.data = converted
                    self._set_status("MSGS_TXT legado migrado p/ UTF-8 em memoria (salve para gravar)")
            self.active_tag = tag
            self.active_resource = resource
            self.resource_messages = resource.messages
            self.current_index = None
            self.resource_box.setCurrentIndex(resource_index)
            self.resource_meta_label.setText(f"{tag.resource_kind} • offset 0x{tag.offset:x} • tag 0x{tag.tag:04x}")
            self.refresh_message_list()

        def refresh_message_list(self, *_args):
            if self._loading or self.active_resource is None:
                return
            keep_index = self.current_index
            query = self.search_entry.text().strip().casefold()
            visible: list[int] = []
            for index, message in enumerate(self.resource_messages):
                preview = " ".join(message.text.replace("\r", "").replace("\n", " ").split())
                if not query or query in message.key.casefold() or query in preview.casefold():
                    visible.append(index)

            _mode, max_lines = self._preview_mode()
            id_counts: dict[int, int] = {}
            for message in self.resource_messages:
                mid = message.message_id
                if mid is not None:
                    id_counts[mid] = id_counts.get(mid, 0) + 1

            self._loading = True
            try:
                with QSignalBlocker(self.message_table):
                    self.message_table.setRowCount(len(visible))
                    for row, index in enumerate(visible):
                        message = self.resource_messages[index]
                        preview = " ".join(message.text.replace("\r", "").replace("\n", " ").split())
                        pages = message.runtime_pages
                        overflow = any(len(page) > max_lines for page in pages)
                        duplicate = message.message_id is not None and id_counts.get(message.message_id, 0) > 1
                        item = QTableWidgetItem(preview[:240])
                        item.setData(Qt.UserRole, index)
                        note = message.key
                        if message.tip:
                            note += f" • tip {message.tip}"
                        note += f" • {len(message.text)} chars, {len(message.runtime_lines)} linhas"
                        if overflow:
                            note += " • página com mais linhas do que o runtime aceita"
                        if duplicate:
                            note += " • ID duplicado"
                        item.setToolTip(note)
                        if overflow or duplicate:
                            item.setForeground(QColor("#E15B5B"))
                        self.message_table.setItem(row, 0, item)
                    chosen_row = visible.index(keep_index) if keep_index in visible else (0 if visible else -1)
                    self.message_table.clearSelection()
                    if chosen_row >= 0:
                        self.message_table.selectRow(chosen_row)
            finally:
                self._loading = False
            if visible:
                chosen_index = keep_index if keep_index in visible else visible[0]
                self.load_message(chosen_index)

        def on_message_select(self):
            if self._loading:
                return
            rows = self.message_table.selectionModel().selectedRows()
            if not rows:
                return
            item = self.message_table.item(rows[0].row(), 0)
            if item is None:
                return
            index = int(item.data(Qt.UserRole))
            if self.current_index is not None and self.current_index != index:
                self.commit_current(update_list=False)
            self.load_message(index)

        def load_message(self, index: int):
            if index < 0 or index >= len(self.resource_messages):
                return
            self.current_index = index
            self._loading = True
            try:
                with QSignalBlocker(self.editor):
                    self.editor.setPlainText(self.resource_messages[index].text)
                    self.editor.document().clearUndoRedoStacks()
                    self.editor.document().setModified(False)
            finally:
                self._loading = False
            self.update_preview()
            message = self.resource_messages[index]
            self._set_status(f"Mensagem *{message.key}*{message.tip if message.tip else ''}")

        def on_editor_changed(self, *_args):
            if self._loading:
                return
            self.dirty = True
            self._set_status("Alterações pendentes")
            self.update_preview()

        def _take_open_snapshot(self):
            # s9: retrato dos bytes na ultima carga limpa (abertura/salvacao).
            # "dirty" passa a significar "bytes != snapshot", nao "historico":
            # editar e reescrever o texto original nao deixa aviso fantasma.
            if self.wad is not None:
                self._open_snapshot = {id(t): t.data for t in self.wad.tags}

        def _refresh_dirty(self):
            if self.wad is None or not self._open_snapshot:
                return
            changed = any(t.data != self._open_snapshot.get(id(t)) for t in self.wad.tags)
            if changed != self.dirty:
                self.dirty = changed
                self._set_status("Alteracoes pendentes" if self.dirty else "Sem alteracoes")

        def commit_current(self, update_list: bool = True):
            if self.current_index is None or not self.resource_messages or self.active_resource is None or self.active_tag is None:
                return
            message = self.resource_messages[self.current_index]
            new_text = self.editor.toPlainText()
            # Enter ja e a quebra real. Sequencias literais "\n"/"\r\n" coladas de
            # arquivos antigos viram quebra de linha na mesma — e e isso que o
            # strtok do runtime espera (delimitador 0x0D 0x0A, provado em
            # GOW2UNSTR.ELF @0x002EDCC0). set_text() normaliza p/ CRLF do recurso.
            new_text = new_text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
            old_text = message.text
            fold = lambda t: t.replace("\r\n", "\n").replace("\r", "\n")
            if fold(new_text) != fold(old_text):
                old_body = message.body_raw
                old_bytes = self.active_tag.data
                message.set_text(new_text)
                candidate = self.active_resource.to_bytes()
                if candidate == old_bytes:
                    # "edicao" que nao muda um byte so (Qt normalizando U+2028/
                    # U+0085 e cia): desfaz e nao marca nada.
                    message.body_raw = old_body
                    self._refresh_dirty()
                    return
                self.active_tag.data = candidate
                self.dirty = True
                resource_index = self.resource_box.currentIndex()
                self._undo_stack.append((resource_index, self.current_index, old_text))
                if len(self._undo_stack) > 400:
                    self._undo_stack.pop(0)
                self._redo_stack.clear()
                if update_list:
                    self.refresh_message_list()
            self._refresh_dirty()

        def apply_current(self):
            try:
                self.commit_current(update_list=False)
                self.refresh_message_list()
                self._set_status("Texto aplicado ao WAD em memória")
            except Exception as exc:
                QMessageBox.critical(self, "Erro ao aplicar texto", str(exc))

        def undo_action(self):
            if self.active_resource is None or self.current_index is None:
                self._set_status("Nada para desfazer")
                QApplication.beep()
                return
            if not self.editor.document().isUndoAvailable():
                self._set_status("Nada para desfazer")
                QApplication.beep()
                return
            self.editor.undo()
            self._set_status("Ação desfeita")

        # ---------------- undo/redo global (edicoes aplicadas) ----------------

        def _resource_parse(self, resource_index: int) -> tuple[WadTag, TextResource]:
            """Parse do recurso no indice pedido (usa o ja carregado quando e o ativo)."""
            tag = self.text_resources[resource_index]
            if resource_index == self.resource_box.currentIndex() and self.active_resource is not None:
                return tag, self.active_resource
            return tag, TextResource(tag.data, self._codec_for_tag(tag))

        def undo_global(self):
            if not self._undo_stack:
                self._set_status("Nenhuma edição aplicada para desfazer")
                QApplication.beep()
                return
            resource_index, message_index, old_text = self._undo_stack.pop()
            self._restore_edit(resource_index, message_index, old_text, self._redo_stack)
            self._set_status("Edição aplicada desfeita (Ctrl+Shift+Y refaz)")

        def redo_global(self):
            if not self._redo_stack:
                self._set_status("Nada para refazer")
                QApplication.beep()
                return
            resource_index, message_index, old_text = self._redo_stack.pop()
            self._restore_edit(resource_index, message_index, old_text, self._undo_stack)
            self._set_status("Edição refeita")

        def _restore_edit(self, resource_index: int, message_index: int, text: str, sibling_stack: list):
            if resource_index < 0 or resource_index >= len(self.text_resources):
                self._set_status("Recurso da edição não existe mais")
                return
            tag, resource = self._resource_parse(resource_index)
            if message_index < 0 or message_index >= len(resource.messages):
                self._set_status("A mensagem da edição mudou de posição (operação estrutural)")
                return
            message = resource.messages[message_index]
            previous_text = message.text
            message.set_text(text)
            tag.data = resource.to_bytes()
            self.dirty = True
            sibling_stack.append((resource_index, message_index, previous_text))
            self._refresh_dirty()
            if resource is self.active_resource:
                if self.current_index == message_index:
                    self.load_message(message_index)
                self.refresh_message_list()

        # ---------------- contadores MSGS_COUNT / MSGS_LINES ----------------

        def _sync_runtime_counters(self):
            """Mantem MSGS_COUNT/MSGS_LINES coerentes com o MSGS_TXT antes de salvar.

            Delega para sync_msgs_counters() no core (ver docstring la). So atua
            quando os contadores existem no WAD (runtime Flash do GoW2).
            """
            if self.wad is None:
                return
            if sync_msgs_counters(self.wad):
                self.dirty = True

        # ---------------- operacoes estruturais de mensagens ----------------

        def _require_msgs_resource(self) -> bool:
            if self.active_resource is None or self.active_tag is None:
                QMessageBox.information(self, "Mensagens", "Abra um WAD e selecione um recurso de mensagens.")
                return False
            if self.active_resource.is_plain_text:
                QMessageBox.information(self, "Mensagens", "Este recurso é texto simples (sem marcadores *ID*).")
                return False
            return True

        def new_message(self):
            if not self._require_msgs_resource():
                return
            self.commit_current(update_list=False)
            resource = self.active_resource
            suggested = resource.next_id()
            dialog = QDialog(self)
            dialog.setWindowTitle("Nova mensagem")
            layout = QVBoxLayout(dialog)
            form = QHBoxLayout()
            form.addWidget(QLabel("ID (inteiro, ordem crescente exigida pelo runtime):"))
            id_box = QDoubleSpinBox()
            id_box.setDecimals(0)
            id_box.setRange(0, 65535)
            id_box.setValue(suggested)
            id_box.setMinimumWidth(120)
            form.addWidget(id_box)
            tip_box = QComboBox()
            tip_box.addItems(["sem dica", "H (dica 1)", "T (dica 2)"])
            form.addWidget(tip_box)
            layout.addLayout(form)
            layout.addWidget(QLabel("Texto inicial (Enter quebra linha; deixe vazio para preencher depois):"))
            body = QPlainTextEdit()
            body.setFixedHeight(110)
            layout.addWidget(body)
            buttons = QHBoxLayout()
            ok = QPushButton("Criar")
            cancel = QPushButton("Cancelar")
            ok.clicked.connect(dialog.accept)
            cancel.clicked.connect(dialog.reject)
            buttons.addStretch(1)
            buttons.addWidget(ok)
            buttons.addWidget(cancel)
            layout.addLayout(buttons)
            if dialog.exec() != QDialog.Accepted:
                return
            tip = {"sem dica": "", "H (dica 1)": "H", "T (dica 2)": "T"}[tip_box.currentText()]
            try:
                message = resource.insert_message(int(id_box.value()), body.toPlainText(), tip)
            except ValueError as exc:
                QMessageBox.warning(self, "Nova mensagem", str(exc))
                return
            self.active_tag.data = resource.to_bytes()
            self.dirty = True
            self._sync_runtime_counters()
            self.refresh_message_list()
            index = resource.messages.index(message)
            self.current_index = index
            self.load_message(index)
            self._set_status(f"Mensagem *{message.key}* criada")

        def duplicate_message(self):
            if not self._require_msgs_resource():
                return
            self.commit_current(update_list=False)
            resource = self.active_resource
            if self.current_index is None or not resource.messages:
                self._set_status("Selecione uma mensagem para duplicar")
                return
            source = resource.messages[self.current_index]
            new_id = resource.next_id()
            message = resource.insert_message(new_id, source.text, source.tip)
            self.active_tag.data = resource.to_bytes()
            self.dirty = True
            self._sync_runtime_counters()
            self.refresh_message_list()
            index = resource.messages.index(message)
            self.current_index = index
            self.load_message(index)
            self._set_status(f"*{source.key}* duplicada como *{message.key}*")

        def delete_message(self):
            if not self._require_msgs_resource():
                return
            self.commit_current(update_list=False)
            resource = self.active_resource
            if self.current_index is None or not resource.messages:
                self._set_status("Selecione uma mensagem para excluir")
                return
            message = resource.messages[self.current_index]
            preview = " ".join(message.text.replace("\r", " ").replace("\n", " ").split())[:90]
            answer = QMessageBox.question(
                self,
                "Excluir mensagem",
                f"Excluir a mensagem *{message.key}*{message.tip}?\n\n{preview}\n\n"
                "Se o WAD tiver MSGS_COUNT/MSGS_LINES eles serão ressincronizados ao salvar.\n"
                "Não há desfazer para operações estruturais.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            resource.remove_message(self.current_index)
            self.active_tag.data = resource.to_bytes()
            self.dirty = True
            self.current_index = None
            self._sync_runtime_counters()
            self.refresh_message_list()
            self._set_status(f"Mensagem *{message.key}* excluída")

        # ---------------- localizar / substituir ----------------

        @staticmethod
        def _replace_in_text(text: str, query: str, replacement: str, case_sensitive: bool) -> tuple[str, int]:
            if not query:
                return text, 0
            if case_sensitive:
                return text.replace(query, replacement), text.count(query)
            pattern = re.escape(query)
            count = len(re.findall(pattern, text, flags=re.IGNORECASE))
            if not count:
                return text, 0
            return re.sub(pattern, lambda _match: replacement, text, flags=re.IGNORECASE), count

        def show_find_replace(self):
            if self.wad is None:
                QMessageBox.information(self, "Localizar/Substituir", "Abra um WAD primeiro.")
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("Localizar e substituir")
            dialog.resize(560, 260)
            layout = QVBoxLayout(dialog)
            form = QVBoxLayout()
            row_find = QHBoxLayout()
            row_find.addWidget(QLabel("Localizar:"))
            find_box = QLineEdit()
            row_find.addWidget(find_box, 1)
            form.addLayout(row_find)
            row_replace = QHBoxLayout()
            row_replace.addWidget(QLabel("Substituir por:"))
            replace_box = QLineEdit()
            row_replace.addWidget(replace_box, 1)
            form.addLayout(row_replace)
            row_options = QHBoxLayout()
            case_box = QCheckBox("Diferenciar maiúsculas/minúsculas")
            scope_box = QComboBox()
            scope_box.addItems(["Recurso ativo", "WAD inteiro"])
            row_options.addWidget(case_box)
            row_options.addWidget(scope_box)
            row_options.addStretch(1)
            form.addLayout(row_options)
            layout.addLayout(form)
            result_label = QLabel("")
            result_label.setObjectName("MutedLabel")
            result_label.setWordWrap(True)
            layout.addWidget(result_label)

            def find_next():
                query = find_box.text()
                if not query:
                    return
                self.commit_current(update_list=False)
                case = case_box.isChecked()
                whole_wad = scope_box.currentText() == "WAD inteiro"
                needle = query if case else query.casefold()
                n_res = len(self.text_resources)
                if n_res == 0:
                    return
                start_res = max(self.resource_box.currentIndex(), 0)
                if whole_wad:
                    order = [(start_res + step) % n_res for step in range(n_res)]
                else:
                    order = [start_res]
                start_msg = self.current_index if self.current_index is not None else -1
                for res_pos, res_index in enumerate(order):
                    try:
                        _, resource = self._resource_parse(res_index)
                    except ValueError:
                        continue
                    if not resource.messages:
                        continue
                    if res_pos == 0:
                        # comeca depois da mensagem atual e dá a volta (wrap)
                        sequence = list(range(start_msg + 1, len(resource.messages))) + list(range(0, start_msg + 1))
                    else:
                        sequence = list(range(len(resource.messages)))
                    for msg_index in sequence:
                        message = resource.messages[msg_index]
                        hay_key = message.key if case else message.key.casefold()
                        hay_text = message.text if case else message.text.casefold()
                        if needle in hay_key or needle in hay_text:
                            self._goto_message(res_index, msg_index)
                            self._highlight_in_editor(query, case)
                            result_label.setText(
                                f"Encontrado em {self.text_resources[res_index].name} • mensagem *{message.key}*"
                            )
                            return
                result_label.setText("Nenhuma ocorrência encontrada.")

            def replace_all():
                query = find_box.text()
                replacement = replace_box.text()
                if not query:
                    return
                self.commit_current(update_list=False)
                case = case_box.isChecked()
                whole_wad = scope_box.currentText() == "WAD inteiro"
                indices = range(len(self.text_resources)) if whole_wad else [max(self.resource_box.currentIndex(), 0)]
                total_occurrences = 0
                total_messages = 0
                changed_current = False
                for res_index in indices:
                    try:
                        tag, resource = self._resource_parse(res_index)
                    except ValueError:
                        continue
                    if resource.is_plain_text and not resource.messages:
                        continue
                    changed_here = False
                    for msg_index, message in enumerate(resource.messages):
                        old_text = message.text
                        new_text, count = self._replace_in_text(old_text, query, replacement, case)
                        if count:
                            message.set_text(new_text)
                            total_occurrences += count
                            total_messages += 1
                            changed_here = True
                            # registra undo global (Ctrl+Shift+Z desfaz a substituicao)
                            self._undo_stack.append((res_index, msg_index, old_text))
                            if len(self._undo_stack) > 400:
                                self._undo_stack.pop(0)
                    if changed_here:
                        tag.data = resource.to_bytes()
                        self.dirty = True
                        if res_index == self.resource_box.currentIndex():
                            changed_current = True
                if total_occurrences:
                    self._redo_stack.clear()
                if changed_current:
                    self.refresh_message_list()
                if total_occurrences:
                    self._set_status(f"Substituição aplicada: {total_occurrences} ocorrência(s) em {total_messages} mensagem(ns)")
                result_label.setText(
                    f"{total_occurrences} ocorrência(s) substituída(s) em {total_messages} mensagem(ns)."
                    if total_occurrences else "Nenhuma ocorrência para substituir."
                )

            row_buttons = QHBoxLayout()
            find_button = QPushButton("Localizar próxima")
            replace_button = QPushButton("Substituir tudo")
            close_button = QPushButton("Fechar")
            find_button.clicked.connect(find_next)
            replace_button.clicked.connect(replace_all)
            close_button.clicked.connect(dialog.accept)
            row_buttons.addWidget(find_button)
            row_buttons.addWidget(replace_button)
            row_buttons.addStretch(1)
            row_buttons.addWidget(close_button)
            layout.addLayout(row_buttons)
            dialog.exec()

        def _goto_message(self, resource_index: int, message_index: int):
            if self.resource_box.currentIndex() != resource_index:
                with QSignalBlocker(self.resource_box):
                    self.resource_box.setCurrentIndex(resource_index)
                self.load_resource(resource_index)
            self.current_index = message_index
            self.refresh_message_list()

        def _highlight_in_editor(self, query: str, case_sensitive: bool):
            text = self.editor.toPlainText()
            hay = text if case_sensitive else text.casefold()
            needle = query if case_sensitive else query.casefold()
            pos = hay.find(needle)
            if pos < 0:
                return
            cursor = self.editor.textCursor()
            cursor.setPosition(pos)
            cursor.setPosition(pos + len(query), QTextCursor.KeepAnchor)
            self.editor.setTextCursor(cursor)
            self.editor.setFocus()

        # ---------------- comparacao com o original ----------------

        def show_changes(self):
            if self.wad is None:
                QMessageBox.information(self, "Alterações", "Abra um WAD primeiro.")
                return
            self.commit_current(update_list=False)
            lines: list[str] = []
            changed_tags = [
                t for t in self.wad.tags
                if t.data != t.original_data or t.size_field != t.original_size_field
            ]
            lines.append(f"TAGS ALTERADAS NO WAD: {len(changed_tags)}")
            for tag in changed_tags:
                delta = len(tag.data) - len(tag.original_data)
                lines.append(f"  • {tag.name} • {len(tag.original_data):,} → {len(tag.data):,} bytes ({delta:+d})")
            if not changed_tags:
                lines.append("  (nenhuma — salvar agora gera um WAD idêntico ao original)")
            if self.active_tag is not None and self.active_resource is not None:
                lines.append("")
                lines.append(f"RECURSO ATIVO: {self.active_tag.name}")
                try:
                    original = TextResource(self.active_tag.original_data, self._codec_for_tag(self.active_tag))
                except ValueError as exc:
                    original = None
                    lines.append(f"  não foi possível decodificar o original: {exc}")
                if original is not None:
                    if original.is_plain_text or self.active_resource.is_plain_text:
                        before = original.text if not original.is_plain_text else (original.messages[0].text if original.messages else "")
                        after = self.active_resource.text if not self.active_resource.is_plain_text else (self.active_resource.messages[0].text if self.active_resource.messages else "")
                        if before == after:
                            lines.append("  texto simples sem alterações.")
                        else:
                            lines.append("  texto simples ALTERADO.")
                            lines.append(f"  antes: {before[:200]!r}")
                            lines.append(f"  agora: {after[:200]!r}")
                    else:
                        remaining = list(original.messages)
                        changed = 0
                        added: list[Message] = []
                        for message in self.active_resource.messages:
                            match = next((m for m in remaining if m.key == message.key and m.tip == message.tip), None)
                            if match is None:
                                added.append(message)
                                continue
                            remaining.remove(match)
                            if match.text != message.text:
                                changed += 1
                                old_preview = " ".join(match.text.replace("\r", " ").replace("\n", " ").split())[:70]
                                new_preview = " ".join(message.text.replace("\r", " ").replace("\n", " ").split())[:70]
                                lines.append(f"  • *{message.key}*{message.tip} alterada")
                                lines.append(f"      antes: {old_preview}")
                                lines.append(f"      agora: {new_preview}")
                        removed = remaining
                        lines.append("")
                        lines.append(f"  resumo: {changed} alterada(s), {len(added)} adicionada(s), {len(removed)} removida(s)")
                        for message in added[:50]:
                            lines.append(f"  + *{message.key}*{message.tip} (nova)")
                        for message in removed[:50]:
                            lines.append(f"  - *{message.key}*{message.tip} (removida)")
                        if len(added) > 50:
                            lines.append(f"  ... e mais {len(added) - 50} nova(s)")
                        if len(removed) > 50:
                            lines.append(f"  ... e mais {len(removed) - 50} removida(s)")
            dialog = QDialog(self)
            dialog.setWindowTitle("Alterações em relação ao WAD aberto")
            dialog.resize(920, 640)
            layout = QVBoxLayout(dialog)
            text = QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText("\n".join(lines) if lines else "Nenhuma alteração.")
            layout.addWidget(text)
            close_button = QPushButton("Fechar")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button, alignment=Qt.AlignRight)
            dialog.exec()

        def _preview_text(self) -> str:
            text = self.editor.toPlainText()
            text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
            return text.replace("\r\n", "\n").replace("\r", "\n")

        def _preview_mode(self) -> tuple[str, int]:
            selected = self.preview_profile_box.currentText()
            if selected == "GoW1 FLP_HUD (5 linhas)":
                return "gow1", 5
            if selected == "Runtime Flash (3 linhas)":
                return "runtime", 3
            if self.active_tag is not None and (self.active_tag.upper_name == "MSGS_TXT" or (self.wad and self.wad.variant.startswith("GoW2"))):
                return "runtime", 3
            return "gow1", 5

        def _apply_preview_placement(self):
            names = {"align": ("esq", "centro", "dir"),
                     "anchor": ("topo", "meio", "base"),
                     "gap": ("fino", "normal", "largo"),
                     "ratio": ("4:3", "16:9")}
            align, anchor, gap = self._placement_ids()
            ratio = self.preview_groups["ratio"].checkedId()
            self.preview.set_placement(align, anchor, gap, ratio)
            if self._preview_real:
                self.preview_hint_label.setText("REAL (medido no FLP) · " + names["ratio"][ratio])
            else:
                self.preview_hint_label.setText(" · ".join(
                    names[k][v] for k, v in (("align", align), ("anchor", anchor),
                                             ("gap", gap), ("ratio", ratio))))

        def _sync_preview_real_ui(self):
            try:
                self.preview_place_btn.setChecked(self._preview_real)
            except Exception:
                pass
            for key, group in self.preview_groups.items():
                if key == "ratio":
                    continue  # proporcao de tela nao e "canto": vale nos dois modos
                for b in group.buttons():
                    b.setEnabled(not self._preview_real)

        def _toggle_preview_real(self, checked: bool):
            self._preview_real = bool(checked)
            self.config["preview_place_real"] = "1" if self._preview_real else "0"
            self._save_config()
            self._sync_preview_real_ui()
            self._apply_preview_placement()
            if hasattr(self, "preview"):
                self.update_preview()

        def _placement_ids(self):
            # modo REAL = o que o jogo faz (medido no FLP: x=2,5, ultima linha em
            # y=494,25, passo 37,5) = o terno abaixo na nossa parametrizacao; os
            # botoes de canto so tem efeito no modo manual.
            if self._preview_real:
                return (0, 2, 1)
            return tuple(g.checkedId() for g in (self.preview_groups["align"],
                                                 self.preview_groups["anchor"],
                                                 self.preview_groups["gap"]))

        def _preview_choice(self, key: str, group: QButtonGroup):
            if self._preview_real and key != "ratio":
                # mexeu num canto -> sai do modo REAL sozinho, sem surpresa
                self._preview_real = False
                self.config["preview_place_real"] = "0"
                self._sync_preview_real_ui()
            self.config["preview_" + key] = str(group.checkedId())
            self._save_config()
            self._apply_preview_placement()

        def update_preview(self, *_args):
            if not hasattr(self, "preview"):
                return
            mode, max_lines = self._preview_mode()
            self.preview.set_state(self._preview_text(), mode, max_lines,
                                   *self._placement_ids())

        def export_txt(self):
            data = self._active_resource_bytes()
            if data is None:
                return
            default = self.active_tag.name if self.active_tag else "messages.txt"
            export_dir = self.config.get("last_save_dir") or ""
            initial = os.path.join(export_dir, default) if export_dir else default
            path, _ = QFileDialog.getSaveFileName(self, "Exportar recurso", initial, "Texto (*.txt);;Todos os arquivos (*)")
            if not path:
                return
            self._remember_dir("last_save_dir", path)
            try:
                Path(path).write_bytes(data)
                self._set_status(f"Recurso exportado: {os.path.basename(path)}")
            except OSError as exc:
                QMessageBox.critical(self, "Erro ao exportar", str(exc))

        def import_txt(self):
            if self.active_tag is None:
                return
            start_dir = self.config.get("last_save_dir") or self.config.get("last_open_dir") or ""
            path, _ = QFileDialog.getOpenFileName(self, "Importar recurso para o WAD", start_dir, "Texto (*.txt);;Todos os arquivos (*)")
            if not path:
                return
            self._remember_dir("last_save_dir", path)
            try:
                resource = TextResource(Path(path).read_bytes(), self._codec_for_tag(self.active_tag))
                self.active_resource = resource
                self.resource_messages = resource.messages
                self.active_tag.data = resource.to_bytes()
                self.current_index = None
                self.dirty = True
                self.refresh_message_list()
                self._set_status(f"{len(self.resource_messages)} mensagens importadas")
            except Exception as exc:
                QMessageBox.critical(self, "Erro ao importar recurso", str(exc))

        def _active_resource_bytes(self) -> bytes | None:
            self.commit_current(update_list=False)
            return self.active_tag.data if self.active_tag is not None else None

        def show_static_labels(self):
            """Editor de rótulos desenhados (StaticLabels) dos filmes FLP.

            Texto "assado" no filme (glifo + avanço, na fonte do próprio
            FLP) — não passa pelo MSGS. Ex.: "Total PlayTime" na STATUS.
            A reescrita troca apenas o stream do rótulo; o resto do filme
            é preservado (o header do bloco é copiado byte a byte e os
            avanços reutilizam os do rótulo original, com fallback
            largura_natural x fator_medido).
            """
            if self.wad is None:
                QMessageBox.information(self, "Rótulos desenhados", "Abra um WAD primeiro.")
                return
            parsed = []
            for tag in self.wad.tags:
                if tag.upper_name.startswith("FLP_") and tag.data and not tag.zero_sized:
                    try:
                        parsed.append((tag, FLPMovie(tag.data)))
                    except Exception:
                        continue
            if not parsed:
                QMessageBox.information(
                    self, "Rótulos desenhados",
                    "Nenhum FLP compatível (formato GoW2) neste WAD.\n"
                    "Rótulos desenhados ficam em recursos como FLP_HUDA/FLP_HUD.")
                return

            dlg = QDialog(self)
            dlg.setWindowTitle("Rótulos desenhados (texto gravado no filme FLP)")
            lay = QVBoxLayout(dlg)
            note = QLabel(
                "Este texto é DESENHO dentro do filme Flash (não passa pelo MSGS).\n"
                "Editar aqui recria os comandos de desenho com a fonte do próprio filme; "
                "o avanço das letras é herdado do rótulo original.")
            note.setWordWrap(True)
            lay.addWidget(note)
            flp_box = QComboBox()
            for tag, _movie in parsed:
                flp_box.addItem(f"{tag.name} • {len(tag.data):,} bytes")
            lay.addWidget(flp_box)
            label_list = QListWidget()
            lay.addWidget(label_list, 1)
            info = QLabel("")
            info.setWordWrap(True)
            lay.addWidget(info)
            row = QHBoxLayout()
            row.addWidget(QLabel("Texto:"))
            edit = QLineEdit()
            row.addWidget(edit, 1)
            lay.addLayout(row)
            btns = QHBoxLayout()
            apply_btn = QPushButton("Aplicar ao rótulo")
            restore_btn = QPushButton("Restaurar original")
            restore_btn.setEnabled(False)
            close_btn = QPushButton("Fechar")
            btns.addStretch(1)
            btns.addWidget(apply_btn)
            btns.addWidget(restore_btn)
            btns.addWidget(close_btn)
            lay.addLayout(btns)

            state = {"flp": -1, "label": -1}
            originals = {id(tag): bytes(tag.data) for tag, _movie in parsed}

            def refresh_labels():
                tag, movie = parsed[state["flp"]]
                label_list.clear()
                for i in range(movie.static_count):
                    try:
                        lbl = movie.label(i)
                    except Exception as exc:
                        label_list.addItem(f"[{i}] (erro: {exc})")
                        continue
                    txt = lbl["text"] if lbl["text"] else "(vazio)"
                    mark = "" if lbl["editable"] else "  [somente leitura]"
                    label_list.addItem(f"[{i}] {txt} • {lbl['glyph_count']} glifo(s){mark}")

            def on_flp_change(idx):
                if idx < 0:
                    return
                state["flp"] = idx
                state["label"] = -1
                refresh_labels()
                edit.clear()
                edit.setEnabled(False)
                apply_btn.setEnabled(False)
                restore_btn.setEnabled(False)
                info.setText("")

            def on_label_change(row):
                state["label"] = row
                if row < 0:
                    edit.clear()
                    edit.setEnabled(False)
                    apply_btn.setEnabled(False)
                    info.setText("")
                    return
                tag, movie = parsed[state["flp"]]
                lbl = movie.label(row)
                edit.setText(lbl["text"])
                edit.setEnabled(lbl["editable"])
                apply_btn.setEnabled(lbl["editable"])
                info.setText(lbl["detail"])
                restore_btn.setEnabled(bytes(tag.data) != originals[id(tag)])

            def do_apply():
                tag, movie = parsed[state["flp"]]
                row = state["label"]
                if row < 0:
                    return
                try:
                    new_data = movie.encode_label(row, edit.text().strip())
                except Exception as exc:
                    QMessageBox.critical(dlg, "Rótulo desenhado", str(exc))
                    return
                tag.data = new_data
                parsed[state["flp"]] = (tag, FLPMovie(new_data))
                self.dirty = True
                self._refresh_dirty()
                refresh_labels()
                label_list.setCurrentRow(row)
                restore_btn.setEnabled(True)
                self._set_status(f"Rótulo [{row}] atualizado em memória ({tag.name}) — salve o WAD para gravar")

            def do_restore():
                tag, _movie = parsed[state["flp"]]
                tag.data = originals[id(tag)]
                parsed[state["flp"]] = (tag, FLPMovie(tag.data))
                self.dirty = True
                self._refresh_dirty()
                refresh_labels()
                label_list.setCurrentRow(state["label"])
                restore_btn.setEnabled(False)
                self._set_status(f"FLP restaurado ao original da sessão ({tag.name})")

            flp_box.currentIndexChanged.connect(on_flp_change)
            label_list.currentRowChanged.connect(on_label_change)
            apply_btn.clicked.connect(do_apply)
            restore_btn.clicked.connect(do_restore)
            close_btn.clicked.connect(dlg.accept)
            dlg.resize(660, 540)
            on_flp_change(0)
            dlg.exec()

        def show_diagnostics(self):
            if self.wad is None:
                QMessageBox.information(self, "Diagnóstico", "Abra um WAD primeiro.")
                return
            self.commit_current(update_list=False)
            report = self.wad.summary() + "\n\n"
            if self.active_tag is not None and self.active_resource is not None:
                report += f"RECURSO ATIVO: {self.active_tag.name}\n"
                report += f"tipo: {self.active_tag.resource_kind}\n"
                report += f"tag: 0x{self.active_tag.tag:04x} • flags: 0x{self.active_tag.flags:04x}\n"
                report += f"payload: {len(self.active_tag.data):,} bytes\n\n"
                gow2 = bool(self.wad.runtime_metadata)
                report += self.active_resource.diagnostics(
                    max_lines_per_page=3 if gow2 else 5,
                    gow2_runtime=gow2,
                ).render()
                if self.active_tag.upper_name == "MSGS_TXT":
                    report += "\n\nNota: o runtime IFF acrescenta um prefixo de tamanho em memória; o editor mantém o payload TXT cru no WAD."
            dialog = QDialog(self)
            dialog.setWindowTitle("Diagnóstico WAD/TXT/runtime")
            dialog.resize(900, 650)
            layout = QVBoxLayout(dialog)
            text = QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText(report)
            layout.addWidget(text)
            close_button = QPushButton("Fechar")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button, alignment=Qt.AlignRight)
            dialog.exec()

        def show_about(self):
            QMessageBox.about(self, "Sobre", "God of War Text Editor\n\nTool By: Gus Hetfield\nSpecial Thanks: Mogaika\n\nEditor WAD/TXT com suporte ao runtime Flash do GoW2.")

        def save_wad(self):
            if self.wad is None:
                QMessageBox.information(self, "Nada aberto", "Abra um WAD primeiro.")
                return
            self.save_wad_as()

        def _write_wad_path(self, destination: Path, backup: bool = False):
            self.commit_current()
            self._sync_runtime_counters()
            destination = destination.resolve()
            if backup and destination.exists():
                shutil.copy2(destination, str(destination) + ".bak")
            payload = self.wad.serialize()
            destination.parent.mkdir(parents=True, exist_ok=True)
            tmp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(prefix=destination.name + ".", suffix=".tmp", dir=destination.parent, delete=False) as tmp:
                    tmp.write(payload)
                    tmp_path = Path(tmp.name)
                os.replace(tmp_path, destination)
            finally:
                if tmp_path is not None and tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
            self.wad_path = str(destination)
            self.dirty = False
            self._take_open_snapshot()
            self.info_label.setText(f"{destination.name} • {self.wad.variant} • WAD editado")
            self._set_status(f"Salvo com sucesso • {len(payload):,} bytes")

        def save_wad_as(self):
            if self.wad is None:
                QMessageBox.information(self, "Nada aberto", "Abra um WAD primeiro.")
                return
            initial_name = os.path.basename(self.wad_path) if self.wad_path else "R_PERM_EDITED.WAD"
            save_dir = self.config.get("last_save_dir") or ""
            initial = os.path.join(save_dir, initial_name) if save_dir else initial_name
            path, _ = QFileDialog.getSaveFileName(self, "Salvar WAD editado", initial, "WAD (*.wad *.WAD);;Todos os arquivos (*)")
            if not path:
                return
            self._remember_dir("last_save_dir", path)
            try:
                same_as_open = bool(self.wad_path and os.path.abspath(path) == os.path.abspath(self.wad_path))
                self._write_wad_path(Path(path), backup=same_as_open)
                QMessageBox.information(self, "WAD salvo", f"Arquivo salvo em:\n{Path(path).resolve()}\n\nOs segmentos não editados foram preservados.")
            except Exception as exc:
                QMessageBox.critical(self, "Erro ao salvar WAD", str(exc))

        def paintEvent(self, event):
            """Pinta a imagem de fundo personalizada atras de toda a interface."""
            super().paintEvent(event)
            if not background_image_active():
                return
            pix = get_background_pixmap(self.width(), self.height())
            if pix is None:
                return
            painter = QPainter(self)
            x = (self.width() - pix.width()) // 2
            y = (self.height() - pix.height()) // 2
            painter.drawPixmap(x, y, pix)
            # Overlay escuro para o texto continuar legivel sobre a imagem.
            painter.fillRect(self.rect(), QColor(5, 5, 7, BG_STATE["dim"]))

        def _apply_window_icon_from_folder(self) -> bool:
            """Aplica o icon.* da pasta icone na janela e nos dialogs. True se ok."""
            icon_path = detect_window_icon_path()
            if not icon_path:
                return False
            icon = QIcon(icon_path)
            if icon.isNull():
                return False
            self.setWindowIcon(icon)
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(icon)
            return True

        def choose_window_icon(self):
            """Escolhe uma imagem e guarda na pasta icone ja com o nome icon.*."""
            folder = ensure_icon_folder()
            start = str(folder) if folder.is_dir() else ""
            path, _ = QFileDialog.getOpenFileName(
                self, "Escolher ícone da janela", start,
                "Imagens (*.ico *.png *.jpg *.jpeg *.bmp *.gif *.webp);;Todos os arquivos (*.*)",
            )
            if not path:
                return
            try:
                chosen = Path(path)
                if chosen.exists():
                    for old in folder.glob("icon.*"):
                        if old.resolve() != chosen.resolve():
                            old.unlink()
                    target = folder / ("icon" + chosen.suffix.lower())
                    if chosen.resolve() != target.resolve():
                        shutil.copy(chosen, target)
            except (OSError, ValueError):
                pass
            if self._apply_window_icon_from_folder():
                applied = os.path.basename(detect_window_icon_path())
                self._set_status(f"Ícone da janela aplicado: {applied}  (pasta {ICON_FOLDERNAME})")
            else:
                self._set_status("Não foi possível carregar esse ícone.")

        def reload_window_icon(self):
            """Reaplica na hora o icon.* da pasta icone."""
            if not self._apply_window_icon_from_folder():
                self._set_status(f"Nenhum arquivo icon.(ico/png/...) encontrado em {ICON_FOLDERNAME}.")
            else:
                self._set_status(f"Ícone recarregado da pasta {ICON_FOLDERNAME}: {os.path.basename(detect_window_icon_path())}")

        def clear_window_icon(self):
            """Volta ao icone padrao; o arquivo vira icon.ext.off na pasta."""
            icon_path = detect_window_icon_path()
            if icon_path:
                try:
                    p = Path(icon_path)
                    p.rename(p.with_suffix(p.suffix + ".off"))
                except OSError:
                    pass
            self.setWindowIcon(QIcon())
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(QIcon())
            self._set_status("Ícone da janela removido (arquivo renomeado para .off na pasta icone).")

        def _reapply_background(self):
            apply_ui_scale(QApplication.instance(), self._ui_scale)
            self.update()
            self._sync_bg_menu()

        def choose_background_image(self):
            folder = ensure_background_folder()
            start = str(folder) if folder.is_dir() else (self.config.get("last_open_dir") or "")
            path, _ = QFileDialog.getOpenFileName(
                self, "Escolher imagem de fundo", start,
                "Imagens (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;Todos os arquivos (*.*)",
            )
            if not path:
                return
            # Guarda uma copia em imagens_de_fundo ja com o nome correto
            # (background.*) para a deteccao automatica continuar valendo;
            # outros background.* antigos sao removidos para nao competir.
            try:
                chosen = Path(path)
                if chosen.exists():
                    target = folder / ("background" + chosen.suffix.lower())
                    for old_bg in folder.glob("background.*"):
                        if old_bg.resolve() != chosen.resolve():
                            old_bg.unlink()
                    if chosen.resolve() != target.resolve():
                        shutil.copy(chosen, target)
            except (OSError, ValueError):
                pass
            # Carrega preferencialmente a copia padronizada da pasta.
            stable = detect_folder_background() or path
            _load_background_state(stable, self.config.get("bg_dim", BG_DIM_DEFAULT))
            self.config["bg_image"] = BG_STATE["path"]
            self._remember_dir("last_open_dir", path)
            write_config(self.config)
            self._reapply_background()
            if BG_STATE["path"]:
                self._set_status(f"Imagem de fundo aplicada: {os.path.basename(BG_STATE['path'])}  (Visualizar > Imagem de fundo para ajustar)")
            else:
                self._set_status("Não foi possível carregar essa imagem.")

        def clear_background_image(self):
            if not background_image_active():
                return
            bg_path = BG_STATE["path"]
            _load_background_state("", BG_STATE["dim"])
            # Renomeia background.* para *.off para a deteccao automatica
            # nao religar o fundo na proxima abertura (renomeie de volta
            # para reativar).
            renamed = ""
            try:
                p = Path(bg_path)
                if p.exists() and p.resolve().parent == background_folder().resolve():
                    p.rename(p.with_suffix(p.suffix + ".off"))
                    renamed = p.with_suffix(p.suffix + ".off").name
            except (OSError, ValueError):
                pass
            self.config["bg_image"] = ""
            write_config(self.config)
            self._reapply_background()
            extra = f" ({renamed} renomeado para .off)" if renamed else ""
            self._set_status(f"Imagem de fundo removida{extra}.")

        def set_background_dim(self, value: int, action):
            BG_STATE["dim"] = clamp_bg_dim(value)
            self.config["bg_dim"] = str(BG_STATE["dim"])
            write_config(self.config)
            self.update()
            self._sync_bg_menu()
            self._set_status(f"Escurecimento do fundo: {BG_STATE['dim']}/255")

        def reload_folder_background(self):
            """Reaplica na hora a imagem mais recente de imagens_de_fundo."""
            folder = ensure_background_folder()
            newest = detect_folder_background()
            if not newest:
                self._set_status(f"Nenhum arquivo background.(png/jpg/...) encontrado em {BG_FOLDERNAME}.")
                return
            _load_background_state(newest, self.config.get("bg_dim", BG_DIM_DEFAULT))
            self.config["bg_image"] = BG_STATE["path"]
            write_config(self.config)
            self._reapply_background()
            self._set_status(f"Fundo recarregado da pasta {BG_FOLDERNAME}: {os.path.basename(newest)}")

        def _sync_bg_menu(self):
            self.action_bg_clear.setEnabled(background_image_active())
            current = BG_STATE["dim"]
            for act in self._bg_dim_actions:
                act.setChecked(getattr(act, "_bg_dim_value", -1) == current)

        def toggle_fullscreen(self):
            if self.isFullScreen():
                self.showNormal()
                self.config["fullscreen"] = "false"
            else:
                self.showFullScreen()
                self.config["fullscreen"] = "true"
            write_config(self.config)

        def set_ui_scale(self, scale: float):
            self._ui_scale = clamp_ui_scale(scale)
            self.config["scale"] = str(self._ui_scale)
            write_config(self.config)
            apply_ui_scale(QApplication.instance(), self._ui_scale)
            self._apply_title_style()
            self.setMinimumSize(int(980 * self._ui_scale), int(640 * self._ui_scale))
            self._set_status(f"Escala da interface: {self._ui_scale * 100:.0f}% (Visualizar para ajustar)")

        def _remember_dir(self, key: str, file_path: str):
            try:
                folder = os.path.dirname(os.path.abspath(file_path))
            except (TypeError, ValueError):
                return
            if folder and self.config.get(key) != folder:
                self.config[key] = folder
                write_config(self.config)

        def _save_config(self):
            self.config["geometry"] = bytes(self.saveGeometry().toHex()).decode()
            self.config["fullscreen"] = "true" if self.isFullScreen() else "false"
            write_config(self.config)

        def closeEvent(self, event):
            self.commit_current(update_list=False)
            self._refresh_dirty()
            if self.dirty:
                answer = QMessageBox.question(self, "Sair", "Existem alterações não salvas. Sair mesmo assim?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer != QMessageBox.Yes:
                    event.ignore()
                    return
            self._save_config()
            event.accept()


    def main():
        app = QApplication(sys.argv)
        app.setApplicationName("God of War Text Editor")
        app.setStyle("Fusion")
        apply_dark_palette(app)
        apply_ui_scale(app, clamp_ui_scale(read_config().get("scale", 1.0)))
        _unused_legacy_stylesheet = """
            QMainWindow, QWidget { background: #111318; color: #eceff4; }
            QMenuBar { background: #151922; color: #eceff4; }
            QMenuBar::item:selected, QMenu::item:selected { background: #765817; }
            QMenu { background: #1b1f27; color: #eceff4; border: 1px solid #596273; }
            QLabel { color: #eceff4; }
            QLabel#TitleLabel { color: #e8bd4b; font-size: 20px; font-weight: bold; }
            QLabel#MutedLabel { color: #9aa4b2; }
            QGroupBox { border: 1px solid #596273; border-radius: 5px; margin-top: 9px; padding-top: 8px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #e8bd4b; }
            QPushButton { background: #292f39; color: #f2f5f8; border: 1px solid #596273; border-radius: 4px; padding: 7px 11px; }
            QPushButton:hover { background: #3a4350; }
            QPushButton#AccentButton { background: #765817; color: white; font-weight: bold; padding: 9px 18px; }
            QPushButton#AccentButton:hover { background: #a27a1e; }
            QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox { background: #1b1f27; color: #eef2f7; border: 1px solid #596273; border-radius: 3px; padding: 5px; selection-background-color: #765817; }
            QPlainTextEdit { font-family: Consolas, monospace; font-size: 12pt; }
            QComboBox:disabled { color: #e8bd4b; background: #252a34; }
            QTableWidget { background: #1b1f27; alternate-background-color: #202631; color: #e9edf2; gridline-color: #343c49; selection-background-color: #765817; selection-color: white; }
            QHeaderView::section { background: #292f39; color: white; padding: 5px; border: 0; }
            QCheckBox { color: #eceff4; }
            QStatusBar { background: #151922; color: #9aa4b2; }
            QSplitter::handle { background: #343c49; }
        """
        window = App()
        if (window.config.get("fullscreen") or "").strip().lower() in {"1", "true", "yes", "on"}:
            window.showFullScreen()
        else:
            window.show()
        sys.exit(app.exec())


else:
    def main():
        linhas = [
            "A interface Qt precisa do PySide6 e das bibliotecas Qt do sistema.",
            "Instale com: python -m pip install PySide6",
            f"Interpretador em uso: {sys.executable}",
        ]
        if globals().get("QT_IMPORT_ERROR") is not None:
            linhas.append(f"Erro real do import: {QT_IMPORT_ERROR}")
        raise SystemExit("\n".join(linhas))


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()