import os
import struct
import unittest
from pathlib import Path

from ygo.palette import (
    CARD_COUNT,
    PALETTE_BASE,
    PALETTE_COLORS,
    PALETTE_STRIDE,
    bgr555_to_rgb,
    read_palette,
    rgb_to_bgr555,
    write_palette,
)
from ygo.rom import Rom

ROOT = Path(__file__).resolve().parents[1]
JP = Path(os.environ.get("YGO_JP_ROM", ROOT / "Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba"))


class TestConversion(unittest.TestCase):
    def test_black_and_white(self):
        assert bgr555_to_rgb(0) == (0, 0, 0)
        assert bgr555_to_rgb(0x7FFF) == (255, 255, 255)
        assert rgb_to_bgr555(0, 0, 0) == 0
        assert rgb_to_bgr555(255, 255, 255) == 0x7FFF

    def test_primary_channels(self):
        assert bgr555_to_rgb(0x001F) == (255, 0, 0)
        assert bgr555_to_rgb(0x03E0) == (0, 255, 0)
        assert bgr555_to_rgb(0x7C00) == (0, 0, 255)

    def test_value_roundtrip_is_exact(self):
        for value in range(1 << 15):
            assert rgb_to_bgr555(*bgr555_to_rgb(value)) == value


class TestReadPalette(unittest.TestCase):
    def setUp(self):
        self.rom = Rom(JP)

    def test_reads_all_records(self):
        palettes = read_palette(self.rom)
        assert len(palettes) == CARD_COUNT == 1115
        assert all(len(palette) == PALETTE_COLORS == 64 for palette in palettes)
        assert all(all(0 <= color <= 0xFFFF for color in palette) for palette in palettes)

    def test_reads_dark_magician(self):
        palette = read_palette(self.rom)[803]
        assert palette[:8:2] == [0x5A00, 0x5C00, 0x5F00, 0x6100]

    def test_accepts_bytes(self):
        assert read_palette(self.rom.data) == read_palette(self.rom)


class TestWritePalette(unittest.TestCase):
    def setUp(self):
        self.rom = Rom(JP)
        self.data = self.rom.data

    def test_roundtrip_is_byte_exact(self):
        edited = self.data
        for index, palette in enumerate(read_palette(self.rom)):
            edited = write_palette(edited, index, palette)
        assert edited == self.data

    def test_write_only_touches_expected_word(self):
        palette = read_palette(self.rom)[803]
        edited = write_palette(self.data, 803, [0x001F, *palette[1:]])
        offset = PALETTE_BASE + 803 * PALETTE_STRIDE
        changed = [i for i in range(len(self.data)) if edited[i] != self.data[i]]
        assert changed == [offset, offset + 1]
        assert struct.unpack_from("<H", edited, offset)[0] == 0x001F

    def test_refuses_bad_input(self):
        palette = read_palette(self.rom)[0]
        with self.assertRaises(IndexError):
            write_palette(self.data, CARD_COUNT, palette)
        with self.assertRaises(IndexError):
            write_palette(self.data, -1, palette)
        with self.assertRaises(ValueError):
            write_palette(self.data, 0, palette[:63])
        with self.assertRaises(ValueError):
            write_palette(self.data, 0, [0x10000, *palette[1:]])


if __name__ == "__main__":
    unittest.main()
