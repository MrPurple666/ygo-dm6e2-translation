import os
import tempfile
import unittest
from pathlib import Path

from ygo import (
    Rom,
    contains_japanese,
    control_prefix,
    decode,
    encode,
    write_ips,
)
from ygo.tables import OFFSETS, extract_names, match_names

ROOT = Path(__file__).resolve().parent.parent
JP = Path(os.environ.get("YGO_JP_ROM", ROOT / "Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba"))
US = Path(
    os.environ.get(
        "YGO_US_ROM",
        ROOT
        / "Yu-Gi-Oh! - Worldwide Edition - Stairway to the Destined Duel (USA) (En,Ja,Fr,De,Es,It).gba",
    )
)


class TestPrimitives(unittest.TestCase):
    def test_slot_le_nome_japones(self):
        rom = Rom(JP)
        assert rom.read_slot(0x2AA160, 0x40).split(b"\x00")[0].decode("cp932") == "地縛霊"

    def test_strings_do_bloco_ingles(self):
        rom = Rom(US)
        first = rom.strings(0x89C47E, 3, ascii_only=True)
        assert first[0][0] == 0x89C47E
        assert first[0][1].startswith(b"A vengeful creature")

    def test_escrita_reflete_em_data(self):
        rom = Rom(JP)
        before = rom.data
        rom.write(0x2AA160, b"TEST")
        assert rom.data[0x2AA160 : 0x2AA164] == b"TEST"
        assert before[0x2AA160 : 0x2AA164] == b"\x92n\x94\x9b"

    def test_texto_roundtrip_e_controles(self):
        s = "$g(1,L,1)$fit$iグールズが立ち去った後$nカバン"
        assert decode(encode(s)) == s
        assert control_prefix(s) == "$g(1,L,1)$fit$i"
        assert contains_japanese(s) and not contains_japanese("After the Ghouls departed")

    def test_ips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir) / "patch.ips"
            write_ips(tmp, [(0x123, b"ABC")])
            raw = tmp.read_bytes()
            assert raw[:5] == b"PATCH"
            assert raw[5:8] == (0x123).to_bytes(3, "big")
            assert raw[8:10] == (3).to_bytes(2, "big")
            assert raw[10:13] == b"ABC" and raw[-3:] == b"EEE"


class TestNameTables(unittest.TestCase):
    def test_nomes_jp_e_us(self):
        jp = extract_names(Rom(JP), OFFSETS["JP_NAME"], 1115)
        us = extract_names(Rom(US), OFFSETS["US_NAME"], 1086)
        assert len(jp) == 1115 and len(us) == 1086
        assert jp[0] == "地縛霊" and us[0] == "Earthbound Spirit"
        assert jp[-1] == "スライムモンスタートークン"

    def test_casamento_de_nomes(self):
        jp = extract_names(Rom(JP), OFFSETS["JP_NAME"], 1115)
        us_jp = extract_names(Rom(US), OFFSETS["US_JPNAME"], 1086)
        m = match_names(jp, us_jp)
        assert len(m) == 1083
        assert m[0] == 0 and m[1] == 1


if __name__ == "__main__":
    unittest.main()
