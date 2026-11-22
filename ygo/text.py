"""Texto cp932 com códigos de controle ASCII `$...` preservados."""

from __future__ import annotations

import re

ENCODING = "cp932"

# `$` + código: `$t2`/`$r1`, nomes de 3 letras conhecidos, letra com args, letra solta.
_TOKEN = r"\$(?:(?:[tTrR]\d)|(?:fot|fib|fit|fob)|[A-Za-z]\([^)]*\)|[A-Za-z]\d?)"
_CONTROL_PREFIX = re.compile(rf"^(?:{_TOKEN})+")
_TOKEN_RE = re.compile(_TOKEN)
_MARKUP_RE = re.compile(rf"{_TOKEN}|%[-+ 0-9.#]*[diouxXcsfg]|@[0-9]")
# ASCII full-width (U+FF01..U+FF60) é o texto traduzido, não japonês restante.
_JAPANESE = re.compile(
    r"[\u3001-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f]"
)
_BREAKS = re.compile(r"\$[ncp]\d?|[ \u3000\u00a0\r\n\t]")


def decode(raw: bytes) -> str:
    return raw.decode(ENCODING)


def encode(text: str) -> bytes:
    return text.encode(ENCODING)


def cp932_len(text: str) -> int:
    return len(encode(text))


# A fonte da ROM JP não tem glifos para ASCII de 1 byte: o renderizador de
# diálogo/carta só desenha os códigos full-width (JIS X 0208, linha 3).
_ASCII = {chr(code): chr(0xFF00 + code - 0x20) for code in range(0x21, 0x7F)}
_ASCII[" "] = "\u3000"
_FULLWIDTH = str.maketrans(_ASCII)


def fullwidth(text: str) -> str:
    """Troca ASCII imprimível pelas formas full-width aceitas pela fonte do jogo."""
    return text.translate(_FULLWIDTH)


def fullwidth_script(text: str) -> str:
    """Como `fullwidth`, preservando `$...`, `%s`/`%d` e marcadores `@N`."""
    out: list[str] = []
    pos = 0
    for match in _MARKUP_RE.finditer(text):
        out.append(fullwidth(text[pos : match.start()]))
        out.append(match.group(0))
        pos = match.end()
    out.append(fullwidth(text[pos:]))
    return "".join(out)


def fit_fullwidth(text: str, limit: int) -> str:
    """Encurta `text` (já full-width) para caber em `limit` bytes cp932."""
    if cp932_len(text) <= limit:
        return text
    cut = text
    while cut and cp932_len(cut + "…") > limit:
        space = cut.rfind("\u3000")
        cut = cut[:space] if space > 0 else cut[:-1]
    return cut.rstrip("\u3000") + "…" if cut else ""


def contains_japanese(text: str) -> bool:
    return _JAPANESE.search(text) is not None


def control_prefix(text: str) -> str:
    """Sequência inicial de tokens `$...`, sem o corpo."""
    match = _CONTROL_PREFIX.match(text)
    return match.group(0) if match else ""


def strip_breaks(text: str) -> str:
    """Normaliza para casamento: tira `$n`/`$c`/`$p`, espaços; `．．．` → `…`."""
    return _BREAKS.sub("", text.replace("．．．", "…"))


def _units(text: str) -> list[tuple[str, str]]:
    atoms: list[tuple[str, str]] = []
    pos = 0
    for match in _MARKUP_RE.finditer(text):
        atoms.extend(("c", char) for char in text[pos : match.start()])
        atoms.append(("t", match.group(0)))
        pos = match.end()
    atoms.extend(("c", char) for char in text[pos:])
    return atoms


PAGE_CHARS = 18
PAGE_LINES = 3


def paginate_script(
    text: str, chars: int = PAGE_CHARS, lines: int = PAGE_LINES
) -> str:
    """Quebra o texto em linhas e páginas que caibam na caixa de diálogo.

    A fonte do diálogo tem ~18 glifos full-width por linha; o texto portado do
    US usa linhas de 34 caracteres da fonte estreita e transborda a caixa.
    `$n`/`$c$p` explícitos (formato do próprio US) paginam na largura da fonte.
    """
    atoms = _units(text)
    tail: list[str] = []
    while atoms and atoms[-1][0] == "t" and atoms[-1][1] in ("$c", "$p", "$fot"):
        tail.insert(0, atoms.pop()[1])
    words: list[list[str]] = [[]]
    for kind, value in atoms:
        if kind == "t":
            if value == "$n":  # quebra do texto US: sai, o espaço já está no texto
                continue
            if value in ("$c", "$p"):  # fim de página: vira separador de palavras
                if words[-1]:
                    words.append([])
                continue
            words[-1].append(value)
        elif value in (" ", "\u3000"):
            if words[-1]:
                words.append([])
        else:
            words[-1].append(value)
    merged: list[list[str]] = []
    for word in words:
        if merged and all(len(atom) > 1 for atom in word):
            merged[-1].extend(word)
        elif word:
            merged.append(word)
    out: list[str] = []
    used = line = 0
    for word in merged:
        just_broke = False
        width = sum(1 for atom in word if len(atom) == 1)
        if used and used + 1 + width > chars:
            used = 0
            line += 1
            if line >= lines:
                out.append("$c$p\u3000")
                line = 0
                used = 1
                just_broke = True
            else:
                out.append("$n")
        if used and not just_broke:
            out.append("\u3000")
            used += 1
        for atom in word:
            if len(atom) > 1:
                out.append(atom)
                continue
            if used >= chars:
                used = 0
                line += 1
                if line >= lines:
                    out.append("$c$p\u3000")
                    line = 0
                    used = 1
                else:
                    out.append("$n")
            out.append(atom)
            used += 1
    out.extend(tail)
    return "".join(out)
