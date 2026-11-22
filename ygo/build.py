"""Monta e aplica a tabela de tradução JP → EN e verifica o resultado."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .rom import Rom, write_ips
from .tables import (
    OFFSETS,
    ScriptString,
    extract_jp_descriptions,
    extract_names,
    extract_script,
    extract_us_language_block,
    find_overflows,
    match_descriptions,
    match_names,
    match_script,
)
from .text import contains_japanese, cp932_len, decode, encode

EXPECTED_JP_SHA = "6b75a36a9da1d1575c976dc6954222061fed15c6cdd4b8081832b810b0b82b02"
EXPECTED_US_SHA = "c4c3ef5c8980996be049a3b6efd1c99b165e565405e040ea428801a14b8c8aa9"
ROM_SIZE = 16 * 1024 * 1024
FREE_START = 0xC32CF4
FREE_END = 0xFFFFFF
NAME_MAX = OFFSETS["NAME_STRIDE"] - 1
DESC_MAX = OFFSETS["DESC_MAX_BYTES"]
IPS_MAX = 0xFFFF

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "manual.json"
MANUAL_DESCRIPTIONS = ROOT / "data" / "manual_descriptions.json"

_TOKEN = re.compile(
    r"\$(?:(?:[tTrR][0-9])|(?:fot|fib|fit|fob)|[A-Za-z]\([^)]*\)|[A-Za-z][0-9]?)"
)


@dataclass(frozen=True)
class Entry:
    offset: int
    size: int
    original: bytes
    replacement: bytes
    source: str
    note: str


@dataclass
class TranslationTable:
    entries: list[Entry] = field(default_factory=list)
    pointer_updates: dict[int, int] = field(default_factory=dict)
    report: dict = field(default_factory=dict)


def _load_manual(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _text_entry(offset: int, text: str, source: str, note: str, original: bytes) -> Entry:
    replacement = encode(text) + b"\x00"
    return Entry(offset, len(replacement), original[: len(replacement)], replacement, source, note)


def _entry(offset: int, replacement: bytes, source: str, note: str, original: bytes) -> Entry:
    return Entry(offset, len(replacement), original[: len(replacement)], replacement, source, note)


def _find_pointers(data: bytes) -> dict[int, list[int]]:
    pointers: dict[int, list[int]] = {}
    for pos in range(0, len(data) - 3, 4):
        value = int.from_bytes(data[pos : pos + 4], "little")
        target = value - 0x08000000
        if 0 <= target < len(data):
            pointers.setdefault(target, []).append(pos)
    return pointers


def _byte_to_char(text: str, byte_offset: int) -> int | None:
    total = 0
    for index, char in enumerate(text):
        if total == byte_offset:
            return index
        total += cp932_len(char)
        if total > byte_offset:
            return None
    return len(text) if total == byte_offset else None


def _map_pointer_target(
    target: int, old_start: int, text: str, english: str, new_start: int
) -> int:
    rel = target - old_start
    if rel == 0:
        return new_start
    jp_tokens = [match.start() for match in _TOKEN.finditer(text)]
    char = _byte_to_char(text, rel)
    if char in jp_tokens and english:
        index = jp_tokens.index(char)
        en_tokens = [match.start() for match in _TOKEN.finditer(english)]
        if index < len(en_tokens):
            return new_start + cp932_len(english[: en_tokens[index]])
    return min(new_start + rel, new_start + cp932_len(english))


def _blocks(script: list[ScriptString]) -> list[tuple[int, int, str]]:
    """Faixas (offset, fim, texto) dos blocos contíguos de script."""
    ranges: list[list[int]] = []
    end = -1
    for string in sorted(script, key=lambda item: item.offset):
        size = cp932_len(string.prefix + string.body) + 1
        if string.offset >= end:
            ranges.append([string.offset, string.offset + size])
        else:
            ranges[-1][1] = max(ranges[-1][1], string.offset + size)
        end = max(end, string.offset + size)
    texts = {string.offset: string.prefix + string.body for string in script}
    return [(start, stop, texts[start]) for start, stop in ranges]


def _us_text_at(rom: Rom, offset: int) -> str:
    """Texto do bloco US que contém `offset` (a variante inglesa)."""
    start = rom.data.rfind(b"\x00", 0, offset) + 1
    end = rom.data.find(b"\x00", start)
    return decode(rom.data[start:end])


def build_table(jp: Rom, us: Rom) -> TranslationTable:
    manual = _load_manual(MANUAL)
    overrides = _load_manual(MANUAL_DESCRIPTIONS)
    table = TranslationTable()

    jp_names = extract_names(jp, OFFSETS["JP_NAME"], OFFSETS["CARD_COUNT_JP"])
    us_jp_names = extract_names(us, OFFSETS["US_JPNAME"], OFFSETS["CARD_COUNT_US"])
    us_names = extract_names(us, OFFSETS["US_NAME"], OFFSETS["CARD_COUNT_US"])
    name_match = match_names(jp_names, us_jp_names)
    manual_names = manual.get("names", {})

    names_ported = names_manual = 0
    for index in range(len(jp_names)):
        override = manual_names.get(str(index))
        if override is not None:
            text, source = override["en"], override["source"]
            names_manual += 1
        elif index in name_match:
            text, source = us_names[name_match[index]], "portado: Worldwide Edition"
            names_ported += 1
        else:
            raise ValueError(f"nome sem tradução manual: {index} {jp_names[index]}")
        if cp932_len(text) > NAME_MAX:
            raise ValueError(f"nome longo demais no slot {index}: {text!r}")
        slot = OFFSETS["JP_NAME"] + index * OFFSETS["NAME_STRIDE"]
        original = jp.read_slot(slot, NAME_MAX + 1).split(b"\x00")[0] + b"\x00"
        table.entries.append(
            _text_entry(slot, text, source, "name", original)
        )

    jp_desc = extract_jp_descriptions(jp)
    us_jp_desc = extract_us_language_block(
        us, OFFSETS["US_JP_DESC"], ascii_only=False, jp_only=True
    )
    en_desc = extract_us_language_block(
        us, OFFSETS["US_EN_DESC"], ascii_only=True, jp_only=False
    )
    desc_match = match_descriptions(jp_desc, us_jp_desc)
    overflows = set(find_overflows(en_desc))
    manual_desc = manual.get("descriptions", {})

    desc_ported = desc_manual = desc_overridden = 0
    for index in range(len(jp_desc)):
        override = manual_desc.get(str(index))
        if override is not None:
            text, source = override["en"], override["source"]
            desc_manual += 1
        elif index in desc_match:
            position = desc_match[index]
            if str(position) in overrides:
                text, source = overrides[str(position)], "override curto"
                desc_overridden += 1
            else:
                text, source = en_desc[position], "portado: Worldwide Edition"
                desc_ported += 1
        else:
            raise ValueError(f"descrição sem tradução manual: {index} {jp_names[index]}")
        if cp932_len(text) > DESC_MAX:
            raise ValueError(f"descrição longa demais no slot {index}: {cp932_len(text)}")
        slot = OFFSETS["JP_DESC"] + index * OFFSETS["DESC_STRIDE"]
        original = jp.read_slot(slot, OFFSETS["DESC_STRIDE"]).split(b"\x00")[0] + b"\x00"
        if text:
            table.entries.append(
                _text_entry(slot, text, source, "description", original)
            )

    if overflows:
        missing = sorted(i for i in overflows if str(i) not in overrides)
        if missing:
            raise ValueError(f"overrides ausentes: {missing}")

    jp_script = extract_script(jp)
    us_script = extract_script(us)
    script_match = match_script(jp_script, us_script)
    manual_script = manual.get("script", {})
    pointers = _find_pointers(jp.data)
    free = FREE_START

    script_ported = script_manual = script_relocated = 0
    for start, stop, text in _blocks(jp_script):
        if not contains_japanese(text) or not text.startswith("$"):
            continue
        manual_entry = manual_script.get(f"{start:#X}") or manual_script.get(f"{start:X}")
        if start in script_match:
            english = _us_text_at(us, script_match[start])
            source = "portado: Worldwide Edition"
            script_ported += 1
        elif manual_entry is not None:
            english, source = manual_entry["en"], manual_entry["source"]
            script_manual += 1
        else:
            raise ValueError(f"script sem tradução manual em {start:#X}: {text[:60]!r}")
        if contains_japanese(english):
            raise ValueError(f"tradução com japonês em {start:#X}")

        old_len = stop - start
        replacement = encode(english) + b"\x00"
        original = jp.read_slot(start, old_len)
        if len(replacement) <= old_len:
            new_start = start
            note = "script"
            table.entries.append(
                _entry(start, replacement, source, note, original)
            )
            if len(replacement) < old_len:
                table.entries.append(
                    _entry(
                        start + len(replacement),
                        b"\x00" * (old_len - len(replacement)),
                        source,
                        "script-tail",
                        original[len(replacement) :],
                    )
                )
        else:
            free = (free + 3) & ~3
            if free + len(replacement) > FREE_END:
                raise ValueError("espaço livre esgotado")
            if any(jp.data[free : free + len(replacement)]):
                raise ValueError(f"região livre não está zerada em {free:#X}")
            new_start = free
            script_relocated += 1
            table.entries.append(
                _entry(free, replacement, source, "script-relocated", jp.read_slot(free, len(replacement)))
            )
            table.entries.append(
                _entry(start, b"\x00" * old_len, source, "script-moved", original)
            )
            free += len(replacement)

        for target, positions in pointers.items():
            if not start <= target < stop:
                continue
            new_target = _map_pointer_target(target, start, text, english, new_start)
            value = 0x08000000 + new_target
            for position in positions:
                current = int.from_bytes(jp.data[position : position + 4], "little")
                if current != value:
                    table.pointer_updates[position] = value

    table.report = {
        "names_total": len(jp_names),
        "names_ported": names_ported,
        "names_manual": names_manual,
        "descriptions_total": len(jp_desc),
        "descriptions_ported": desc_ported,
        "descriptions_manual": desc_manual,
        "descriptions_overridden": desc_overridden,
        "script_blocks": script_ported + script_manual,
        "script_ported": script_ported,
        "script_manual": script_manual,
        "script_relocated": script_relocated,
        "pointer_updates": len(table.pointer_updates),
        "manual_keys": {
            "names": sorted(manual_names),
            "descriptions": sorted(manual_desc),
            "script": sorted(manual_script),
        },
    }
    return table


def _ips_records(table: TranslationTable) -> list[tuple[int, bytes]]:
    records = [(entry.offset, entry.replacement) for entry in table.entries]
    for position, value in table.pointer_updates.items():
        records.append((position, value.to_bytes(4, "little")))
    records.sort()
    split: list[tuple[int, bytes]] = []
    for offset, payload in records:
        for start in range(0, len(payload), IPS_MAX):
            split.append((offset + start, payload[start : start + IPS_MAX]))
    return split


def apply_table(jp: Rom, table: TranslationTable, out_path: Path, ips_path: Path) -> Rom:
    patched = Rom(jp.path)
    for entry in table.entries:
        patched.write(entry.offset, entry.replacement)
    for position, value in table.pointer_updates.items():
        patched.write(position, value.to_bytes(4, "little"))
    patched.save(out_path)
    write_ips(ips_path, _ips_records(table))
    return patched


def verify(jp: Rom, us: Rom, patched: Rom, table: TranslationTable) -> dict:
    names = extract_names(patched, OFFSETS["JP_NAME"], OFFSETS["CARD_COUNT_JP"])
    descriptions = extract_jp_descriptions(patched)
    script = extract_script(patched)
    prefixed = [item for item in script if item.prefix]
    remaining = sum(contains_japanese(item.body) for item in prefixed)
    unprefixed = sum(
        contains_japanese(item.body) for item in script if not item.prefix
    )

    pointer_valid = True
    for position, value in table.pointer_updates.items():
        if int.from_bytes(patched.data[position : position + 4], "little") != value:
            pointer_valid = False
            break
        target = value - 0x08000000
        if not 0 <= target < patched.size:
            pointer_valid = False
            break
        end = patched.data.find(b"\x00", target)
        if end < 0:
            pointer_valid = False
            break
        try:
            text = decode(patched.data[target:end])
        except UnicodeDecodeError:
            pointer_valid = False
            break
        if any(not (char.isprintable() or char.isspace()) for char in text):
            pointer_valid = False
            break

    return {
        "jp_sha256": jp.sha256(),
        "us_sha256": us.sha256(),
        "patched_sha256": patched.sha256(),
        "jp_hash_ok": jp.sha256() == EXPECTED_JP_SHA,
        "us_hash_ok": us.sha256() == EXPECTED_US_SHA,
        "size": patched.size,
        "size_ok": patched.size == ROM_SIZE,
        "jp_characters_remaining": remaining,
        "unprefixed_japanese_remaining": unprefixed,
        "pointer_updates_valid": pointer_valid,
        "pointer_updates": len(table.pointer_updates),
        "card_count": len(names),
        "cards_ok": len(names) == OFFSETS["CARD_COUNT_JP"],
        "manual_entries": {
            "names": table.report.get("names_manual", 0),
            "descriptions": table.report.get("descriptions_manual", 0),
            "script": table.report.get("script_manual", 0),
        },
        "build": table.report,
        "ips_bytes": None,
    }
