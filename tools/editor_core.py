"""Núcleo do editor de traduções: carregar, validar e salvar os JSONs."""

import json
import shutil
from pathlib import Path

from ygo.text import _MARKUP_RE as TOKEN_RE
from ygo.text import contains_japanese, cp932_len


def load_translations(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_overrides(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_translations(data: dict, path: Path) -> None:
    path = Path(path)
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def validate_entry(original: str, edited: str, *, limit: int) -> list[str]:
    problems: list[str] = []
    if not edited.strip():
        problems.append("texto vazio")
    original_tokens = TOKEN_RE.findall(original)
    edited_tokens = TOKEN_RE.findall(edited)
    if original_tokens != edited_tokens:
        problems.append(
            f"tokens de controle alterados: {original_tokens} != {edited_tokens}"
        )
    if contains_japanese(edited):
        problems.append("ainda há texto japonês")
    size = cp932_len(edited)
    if size > limit:
        problems.append(f"texto tem {size} bytes; limite é {limit}")
    return problems
