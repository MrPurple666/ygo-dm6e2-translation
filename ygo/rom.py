"""Primitivas de leitura/escrita das ROMs de GBA."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

MAX_STRING = 700


class Rom:
    """ROM em memória; leituras devolvem bytes e escritas alteram só a cópia."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._buf = bytearray(self.path.read_bytes())
        self._snapshot: bytes | None = None

    @property
    def data(self) -> bytes:
        if self._snapshot is None:
            self._snapshot = bytes(self._buf)
        return self._snapshot

    @property
    def size(self) -> int:
        return len(self._buf)

    def read_slot(self, offset: int, size: int) -> bytes:
        return bytes(self._buf[offset : offset + size])

    def strings(
        self,
        start: int,
        count: int,
        *,
        jp_only: bool = False,
        ascii_only: bool = False,
    ) -> list[tuple[int, bytes]]:
        """Strings NUL-terminadas a partir de `start`, pulando padding de zeros.

        Para na primeira string com byte de controle (fora de tab/nova linha) ou
        com mais de MAX_STRING bytes: dali em diante a região não é texto.
        """
        found: list[tuple[int, bytes]] = []
        pos, size = start, self.size
        while pos < size and len(found) < count:
            if self._buf[pos] == 0:
                pos += 1
                continue
            end = pos
            while end < size and self._buf[end] != 0:
                b = self._buf[end]
                if (b < 0x20 and b not in (0x09, 0x0A)) or end - pos > MAX_STRING:
                    return found
                end += 1
            raw = bytes(self._buf[pos:end])
            has_high = any(b >= 0x80 for b in raw)
            if not (jp_only and not has_high) and not (ascii_only and has_high):
                found.append((pos, raw))
            pos = end + 1
        return found

    def write(self, offset: int, payload: bytes) -> None:
        if offset < 0 or offset + len(payload) > self.size:
            raise ValueError(f"escrita fora da ROM: {offset:#x}+{len(payload)}")
        self._buf[offset : offset + len(payload)] = payload
        self._snapshot = None

    def save(self, path: Path) -> None:
        target = Path(path)
        if target.resolve() == self.path.resolve():
            raise ValueError("recusando sobrescrever a ROM de origem")
        target.write_bytes(self._buf)

    def sha256(self) -> str:
        return hashlib.sha256(self._buf).hexdigest()


def write_ips(path: Path, records: Iterable[tuple[int, bytes]]) -> None:
    """Grava patch IPS clássico (offset/tamanho big-endian, fim `EEE`)."""
    out = bytearray(b"PATCH")
    for offset, payload in records:
        if not payload:  # tamanho 0 vira RLE no IPS clássico
            continue
        out += offset.to_bytes(3, "big")
        out += len(payload).to_bytes(2, "big")
        out += payload
    out += b"EEE"
    Path(path).write_bytes(out)
