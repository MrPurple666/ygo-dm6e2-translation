"""Tabelas de nomes de cartas das ROMs JP e US."""

from __future__ import annotations

from .rom import Rom
from .text import cp932_len, decode

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
