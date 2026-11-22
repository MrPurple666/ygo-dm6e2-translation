"""Tabelas de nomes de cartas das ROMs JP e US."""

from __future__ import annotations

from .rom import Rom
from .text import decode

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
