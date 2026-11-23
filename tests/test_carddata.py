import os
import struct
import unittest
from pathlib import Path

from ygo.carddata import (
    CARD_COUNT,
    PASSWORD_BASE,
    STATS_BASE,
    read_password,
    read_stats,
    validate_stats,
    write_password,
    write_stats,
)
from ygo.rom import Rom

ROOT = Path(__file__).resolve().parents[1]
JP = Path(os.environ.get("YGO_JP_ROM", ROOT / "Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba"))


class TestReadStats(unittest.TestCase):
    def setUp(self):
        self.rom = Rom(JP)
        self.stats = read_stats(self.rom)

    def test_reads_all_records(self):
        assert len(self.stats) == CARD_COUNT == 1115
        assert set(self.stats[0]) == {"atk", "def", "sub", "race", "level", "attr"}

    def test_decodes_dark_magician(self):
        assert self.stats[803] == {
            "atk": 2500,
            "def": 2100,
            "sub": 0,
            "race": 18,
            "level": 7,
            "attr": 2,
        }

    def test_decodes_blue_eyes_and_exodia(self):
        assert (self.stats[816]["atk"], self.stats[816]["def"]) == (3000, 2500)
        assert (self.stats[774]["atk"], self.stats[774]["def"]) == (1000, 1000)

    def test_decodes_pot_of_greed_as_spell(self):
        pot = self.stats[290]
        assert pot["attr"] == 0 and pot["race"] == 22


class TestPasswords(unittest.TestCase):
    def setUp(self):
        self.rom = Rom(JP)
        self.passwords = read_password(self.rom)

    def test_reads_all_passwords(self):
        assert len(self.passwords) == CARD_COUNT

    def test_decodes_known_passwords(self):
        assert self.passwords[803] == "46986414"
        assert self.passwords[816] == "89631139"
        assert self.passwords[774] == "33396948"

    def test_missing_password_is_none(self):
        assert self.passwords[1114] is None


class TestWriteStats(unittest.TestCase):
    def setUp(self):
        self.rom = Rom(JP)
        self.data = self.rom.data

    def test_write_recomposes_word(self):
        original = read_stats(self.rom)[803]
        edited = write_stats(self.data, 803, {**original, "atk": 2600})
        value = struct.unpack_from("<I", edited, STATS_BASE + 803 * 4)[0]
        assert ((value >> 9) & 0x1FF) * 10 == 2600
        assert read_stats(self.data) == read_stats(Rom(JP))

    def test_write_only_touches_index(self):
        before = read_stats(Rom(JP))
        edited = write_stats(self.data, 0, {**before[0], "level": 12})
        after = read_stats(_Bytes(edited))
        assert after[0]["level"] == 12
        assert after[1:] == before[1:]

    def test_roundtrip_is_byte_exact(self):
        edited = self.data
        for index, stats in enumerate(read_stats(self.rom)):
            edited = write_stats(edited, index, stats)
        assert edited == self.data

    def test_rejects_out_of_range_field(self):
        with self.assertRaises(ValueError):
            write_stats(self.data, 803, {**read_stats(self.rom)[803], "level": 16})

    def test_rejects_non_multiple_of_ten(self):
        with self.assertRaises(ValueError):
            write_stats(self.data, 803, {**read_stats(self.rom)[803], "atk": 2505})

    def test_rejects_bad_index(self):
        stats = read_stats(self.rom)[0]
        with self.assertRaises(IndexError):
            write_stats(self.data, CARD_COUNT, stats)

    def test_validation_lists_problems(self):
        problems = validate_stats({"atk": 2505, "def": 0, "sub": 4, "race": 32, "level": -1, "attr": 8})
        assert len(problems) == 5
        assert any("atk" in message for message in problems)
        assert any("10" in message for message in problems)

    def test_validation_accepts_real_stats(self):
        assert all(validate_stats(stats) == [] for stats in read_stats(self.rom))


class TestWritePassword(unittest.TestCase):
    def setUp(self):
        self.rom = Rom(JP)
        self.data = self.rom.data

    def test_write_password(self):
        edited = write_password(self.data, 803, "12345678")
        assert edited[PASSWORD_BASE + 803 * 4 : PASSWORD_BASE + 803 * 4 + 4] == b"\x12\x34\x56\x78"
        assert read_password(_Bytes(edited))[803] == "12345678"

    def test_write_none_uses_sentinel(self):
        edited = write_password(self.data, 803, None)
        assert edited[PASSWORD_BASE + 803 * 4 : PASSWORD_BASE + 803 * 4 + 4] == b"\xff" * 4

    def test_roundtrip_is_byte_exact(self):
        edited = self.data
        for index, password in enumerate(read_password(self.rom)):
            edited = write_password(edited, index, password)
        assert edited == self.data

    def test_rejects_bad_password(self):
        for bad in ("1234567", "123456789", "1234567a", " 12345678"):
            with self.assertRaises(ValueError):
                write_password(self.data, 0, bad)


class _Bytes:
    """Adaptador mínimo: leitores aceitam Rom ou bytes."""

    def __init__(self, data: bytes):
        self.data = data


if __name__ == "__main__":
    unittest.main()
