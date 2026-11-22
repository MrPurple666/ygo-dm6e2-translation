"""Tabelas de nomes de cartas e strings de script das ROMs JP e US."""

from __future__ import annotations

import re
import struct
import unicodedata
from dataclasses import dataclass

from .rom import Rom
from .text import contains_japanese, control_prefix, cp932_len, decode, strip_breaks

SCRIPT_MAX_BYTES = 2000
_ENGLISH_WINDOW = 0x1000
_CONTROL = re.compile(r"\$[A-Za-z]+(?:\([^)]*\))?")

OFFSETS = {
    "JP_NAME": 0x2AA160,
    "JP_DESC": 0x2CD0A0,
    "NAME_STRIDE": 0x40,
    "DESC_STRIDE": 0x180,
    "CARD_COUNT_JP": 1115,
    "US_NAME": 0x385564,
    "US_JPNAME": 0x8475FC,
    "CARD_COUNT_US": 1086,
    "US_EN_DESC": 0x89C47E,
    "US_JP_DESC": 0x8B8FAA,
    "DESC_COUNT_US": 1082,
    "DESC_MAX_BYTES": 383,
}


def extract_names(rom: Rom, base: int, count: int) -> list[str]:
    """Lê `count` slots de `NAME_STRIDE` bytes, parando no NUL de cada um."""
    return [
        decode(rom.read_slot(base + i * OFFSETS["NAME_STRIDE"], OFFSETS["NAME_STRIDE"]).split(b"\x00")[0])
        for i in range(count)
    ]


def match_names(jp_names: list[str], us_jp_names: list[str]) -> dict[int, int]:
    """Índice JP → índice US pelo nome japonês exato.

    Nomes repetidos casam com a primeira ocorrência US ainda não usada.
    """
    available: dict[str, list[int]] = {}
    for index, name in enumerate(us_jp_names):
        available.setdefault(name, []).append(index)
    matched: dict[int, int] = {}
    for index, name in enumerate(jp_names):
        candidates = available.get(name)
        if candidates:
            matched[index] = candidates.pop(0)
    return matched


def extract_jp_descriptions(rom: Rom) -> list[str]:
    """Lê os 1115 slots de descrição japonesa, parando no NUL de cada um."""
    return [
        decode(rom.read_slot(OFFSETS["JP_DESC"] + i * OFFSETS["DESC_STRIDE"], OFFSETS["DESC_STRIDE"]).split(b"\x00")[0])
        for i in range(OFFSETS["CARD_COUNT_JP"])
    ]


def extract_us_language_block(
    rom: Rom, start: int, *, ascii_only: bool, jp_only: bool
) -> list[str]:
    """Strings não vazias do bloco de 1082 descrições, pulando padding."""
    pairs = rom.strings(
        start, OFFSETS["DESC_COUNT_US"], ascii_only=ascii_only, jp_only=jp_only
    )
    return [decode(raw) for _, raw in pairs]


def match_descriptions(jp_desc: list[str], us_jp_desc: list[str]) -> dict[int, int]:
    """Índice do slot JP → posição no bloco inglês pelo texto japonês exato."""
    return match_names(jp_desc, us_jp_desc)


def find_overflows(english: list[str], limit: int = OFFSETS["DESC_MAX_BYTES"]) -> list[int]:
    """Posições cujo texto não cabe no slot de descrição em cp932."""
    return [index for index, text in enumerate(english) if cp932_len(text) > limit]


@dataclass(frozen=True)
class ScriptString:
    """String de script apontada por um ponteiro u32 da ROM."""

    offset: int
    prefix: str
    body: str


def _script_text(rom: Rom, offset: int) -> tuple[str, str] | None:
    data = rom.data
    end = data.find(b"\x00", offset, min(offset + SCRIPT_MAX_BYTES, rom.size))
    if end < 0 or end - offset < 2:
        return None
    try:
        text = decode(data[offset:end])
    except UnicodeDecodeError:
        return None
    if any(not (char.isprintable() or char.isspace()) for char in text):
        return None
    prefix = control_prefix(text)
    body = text[len(prefix) :]
    # Ponteiro para o meio de uma string só é texto se começa em código `$...`.
    if not body or (offset > 0 and data[offset - 1] != 0 and not prefix):
        return None
    return prefix, body


def extract_script(rom: Rom) -> list[ScriptString]:
    """Strings de script apontadas por u32 little-endian em toda a ROM."""
    targets = {
        value - 0x08000000
        for (value,) in struct.iter_unpack("<I", rom.data)
        if 0 <= value - 0x08000000 < rom.size - 1
    }
    found = []
    for offset in sorted(targets):
        parsed = _script_text(rom, offset)
        if parsed:
            found.append(ScriptString(offset, *parsed))
    return found


def _script_key(text: str) -> str:
    """Normaliza corpo japonês: sem tokens, quebras, pontuação ou largura."""
    text = _CONTROL.sub("", strip_breaks(text))
    return re.sub(r"[\W_]", "", unicodedata.normalize("NFKC", text))


def _english_before(us: list[ScriptString], index: int, jp_string: ScriptString):
    for candidate in reversed(us[:index]):
        if jp_string.offset - candidate.offset > _ENGLISH_WINDOW:
            break
        if (
            candidate.prefix == jp_string.prefix
            and candidate.body.isascii()
            and any(char.isalpha() for char in candidate.body)
        ):
            return candidate
    return None


def match_script(jp: list[ScriptString], us: list[ScriptString]) -> dict[int, int]:
    """Offset da string JP → offset da variante inglesa na ROM US."""
    us = sorted(us, key=lambda string: string.offset)
    available: dict[tuple[str, str], list[ScriptString]] = {}
    for string in us:
        if string.prefix and contains_japanese(string.body):
            available.setdefault((string.prefix, _script_key(string.body)), []).append(string)
    positions = {string.offset: index for index, string in enumerate(us)}
    matched: dict[int, int] = {}
    for string in jp:
        # Sem prefixo não há como distinguir a variante inglesa no bloco US.
        if not string.prefix or not contains_japanese(string.body):
            continue
        candidates = available.get((string.prefix, _script_key(string.body)))
        if not candidates:
            continue
        us_jp = candidates.pop(0)
        english = _english_before(us, positions[us_jp.offset], us_jp)
        if english is not None:
            matched[string.offset] = english.offset
    return matched
