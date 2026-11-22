"""Texto cp932 com códigos de controle ASCII `$...` preservados."""

from __future__ import annotations

import re

ENCODING = "cp932"

# `$` + nome; args entre parênteses; `$t`/`$r` levam um dígito solto.
_TOKEN = r"\$(?:[tTrR]\d|[A-Za-z]+(?:\([^)]*\))?)"
_CONTROL_PREFIX = re.compile(rf"^(?:{_TOKEN})+")
_JAPANESE = re.compile(
    r"[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff01-\uff60\uff66-\uff9f]"
)
_BREAKS = re.compile(r"\$[ncp]\d?|[ \u3000\u00a0\r\n\t]")


def decode(raw: bytes) -> str:
    return raw.decode(ENCODING)


def encode(text: str) -> bytes:
    return text.encode(ENCODING)


def cp932_len(text: str) -> int:
    return len(encode(text))


def contains_japanese(text: str) -> bool:
    return _JAPANESE.search(text) is not None


def control_prefix(text: str) -> str:
    """Sequência inicial de tokens `$...`, sem o corpo."""
    match = _CONTROL_PREFIX.match(text)
    return match.group(0) if match else ""


def strip_breaks(text: str) -> str:
    """Normaliza para casamento: tira `$n`/`$c`/`$p`, espaços; `．．．` → `…`."""
    return _BREAKS.sub("", text.replace("．．．", "…"))
