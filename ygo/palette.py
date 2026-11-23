"""Paletas BGR555 das 1115 cartas da ROM JP em tabelas de passo 0x80."""

from __future__ import annotations

import struct

PALETTE_BASE = 0x156F20
PALETTE_STRIDE = 0x80
PALETTE_COLORS = 64
CARD_COUNT = 1115
MAX_COLOR = 0xFFFF  # bit 15 aparece em 831 registros; preservar garante roundtrip


def _data(rom) -> bytes:
    return rom.data if hasattr(rom, "data") else bytes(rom)


def _to8(value: int) -> int:
    return (value * 255 + 15) // 31


def _to5(value: int) -> int:
    return (value * 31 + 127) // 255


def bgr555_to_rgb(value: int) -> tuple[int, int, int]:
    """Canais de 5 bits (bits 0-4 R, 5-9 G, 10-14 B) para 0..255."""
    return (
        _to8(value & 0x1F),
        _to8((value >> 5) & 0x1F),
        _to8((value >> 10) & 0x1F),
    )


def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    """Canais 0..255 para BGR555; arredonda para o 5 bits mais próximo."""
    return _to5(r) | _to5(g) << 5 | _to5(b) << 10


def read_palette(rom) -> list[list[int]]:
    """Lê as 1115 paletas de 64 cores; aceita `Rom` ou bytes."""
    data = _data(rom)
    return [
        list(struct.unpack_from("<64H", data, PALETTE_BASE + index * PALETTE_STRIDE))
        for index in range(CARD_COUNT)
    ]


def write_palette(rom: bytes, index: int, colors: list[int]) -> bytes:
    """Devolve uma cópia da ROM com os 64 u16 da paleta da carta."""
    if not 0 <= index < CARD_COUNT:
        raise IndexError(f"índice de carta inválido: {index}")
    colors = list(colors)
    if len(colors) != PALETTE_COLORS:
        raise ValueError(f"paleta precisa de {PALETTE_COLORS} cores: {len(colors)}")
    invalid = [color for color in colors if not 0 <= color <= MAX_COLOR]
    if invalid:
        raise ValueError(f"cor fora de 0..{MAX_COLOR:#x}: {invalid[0]}")
    out = bytearray(rom)
    struct.pack_into("<64H", out, PALETTE_BASE + index * PALETTE_STRIDE, *colors)
    return bytes(out)
