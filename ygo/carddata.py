"""Stats e senhas de carta da ROM JP em tabelas de passo 4."""

from __future__ import annotations

import struct

STATS_BASE = 0x979D24
PASSWORD_BASE = 0x97B74C
STRIDE = 4
CARD_COUNT = 1115
NO_PASSWORD = 0xFFFFFFFF

_RANGES = {
    "atk": (0, 5110),
    "def": (0, 5110),
    "sub": (0, 3),
    "race": (0, 31),
    "level": (0, 15),
    "attr": (0, 7),
}


def _data(rom) -> bytes:
    return rom.data if hasattr(rom, "data") else bytes(rom)


def _decode(value: int) -> dict:
    return {
        "atk": ((value >> 9) & 0x1FF) * 10,
        "def": (value & 0x1FF) * 10,
        "sub": (value >> 18) & 3,
        "race": (value >> 20) & 0x1F,
        "level": (value >> 25) & 0xF,
        "attr": (value >> 29) & 7,
    }


def _encode(stats: dict) -> int:
    return (
        (stats["atk"] // 10) << 9
        | (stats["def"] // 10)
        | (stats["sub"] << 18)
        | (stats["race"] << 20)
        | (stats["level"] << 25)
        | (stats["attr"] << 29)
    )


def read_stats(rom) -> list[dict]:
    """Decodifica os 1115 registros de stats; aceita `Rom` ou bytes."""
    data = _data(rom)
    return [
        _decode(struct.unpack_from("<I", data, STATS_BASE + index * STRIDE)[0])
        for index in range(CARD_COUNT)
    ]


def validate_stats(stats: dict) -> list[str]:
    """Mensagens dos campos ausentes, fora da faixa ou não múltiplos de 10."""
    problems = []
    for field, (low, high) in _RANGES.items():
        if field not in stats:
            problems.append(f"{field} ausente")
            continue
        value = stats[field]
        if field in ("atk", "def") and value % 10:
            problems.append(f"{field} deve ser múltiplo de 10: {value}")
        if not low <= value <= high:
            problems.append(f"{field} fora da faixa {low}..{high}: {value}")
    return problems


def write_stats(rom: bytes, index: int, stats: dict) -> bytes:
    """Devolve uma cópia da ROM com o u32 do registro recomposto."""
    if not 0 <= index < CARD_COUNT:
        raise IndexError(f"índice de carta inválido: {index}")
    problems = validate_stats(stats)
    if problems:
        raise ValueError("; ".join(problems))
    out = bytearray(rom)
    struct.pack_into("<I", out, STATS_BASE + index * STRIDE, _encode(stats))
    return bytes(out)


def read_password(rom) -> list[str | None]:
    """Senhas BCD de 8 dígitos; `None` onde a ROM guarda `FFFFFFFF`."""
    data = _data(rom)
    passwords: list[str | None] = []
    for index in range(CARD_COUNT):
        raw = data[PASSWORD_BASE + index * STRIDE : PASSWORD_BASE + (index + 1) * STRIDE]
        if int.from_bytes(raw, "big") == NO_PASSWORD:
            passwords.append(None)
            continue
        text = raw.hex()
        if not text.isdigit():
            raise ValueError(f"senha não-BCD no registro {index}: {text}")
        passwords.append(text)
    return passwords


def write_password(rom: bytes, index: int, password: str | None) -> bytes:
    """Grava a senha BCD; `None` grava o sentinela `FFFFFFFF`."""
    if not 0 <= index < CARD_COUNT:
        raise IndexError(f"índice de carta inválido: {index}")
    if password is None:
        payload = NO_PASSWORD.to_bytes(4, "big")
    else:
        if len(password) != 8 or not (password.isascii() and password.isdigit()):
            raise ValueError(f"senha deve ter 8 dígitos BCD: {password!r}")
        payload = bytes.fromhex(password)
    out = bytearray(rom)
    out[PASSWORD_BASE + index * STRIDE : PASSWORD_BASE + (index + 1) * STRIDE] = payload
    return bytes(out)
