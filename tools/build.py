#!/usr/bin/env python3
"""Gera ROM traduzida e patch IPS a partir das ROMs JP e US."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ygo import Rom  # noqa: E402
from ygo.build import apply_table, build_table, verify  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jp", required=True, type=Path)
    parser.add_argument("--us", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--ips", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    jp, us = Rom(args.jp), Rom(args.us)
    table = build_table(jp, us)
    patched = apply_table(jp, table, args.out, args.ips)
    report = verify(jp, us, patched, table)
    report["ips_bytes"] = args.ips.stat().st_size
    report["jp_characters_remaining_scope"] = (
        "nomes + descrições de cartas + blocos de script com prefixo $... + "
        "UI sem prefixo na faixa 0xAFE44..0xB6ED0"
    )
    report["binary_false_positives_scope"] = (
        "strings japonesas sem prefixo fora da faixa de UI (ponteiros "
        "coincidentes em código/dados); excluídas da meta de tradução"
    )
    report["manual_schema"] = {
        "file": "data/manual.json",
        "names": "índice JP (string) -> {en, source}",
        "descriptions": "índice do slot JP (string) -> {en, source}",
        "script": "offset do bloco JP em hexadecimal (string) -> {en, source}",
        "ui": "offset do bloco de UI em hexadecimal (string) -> {en, source}",
        "note": (
            "UI sem prefixo é portada da ROM US por casamento do japonês e "
            "literais pareados; o que não casa usa data/manual.json['ui']."
        ),
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{args.out} ({patched.size} bytes), {args.ips} "
        f"({report['ips_bytes']} bytes), japonês restante: "
        f"{report['jp_characters_remaining']}"
    )
    return 0 if report["jp_characters_remaining"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
