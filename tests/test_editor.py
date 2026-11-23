import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.editor import (
    EditorWindow,
    SECTIONS,
    _diff_records,
    apply_edit,
    apply_palette_edit,
    apply_stats_edit,
    combine_data,
    filter_rows,
    palette_rows,
    stats_rows,
    validation_for,
)
from tools.editor_core import (
    load_overrides,
    load_translations,
    save_translations,
    validate_entry,
)
from ygo.carddata import read_password, read_stats
from ygo.palette import read_palette
from ygo.rom import Rom

ROOT = Path(__file__).resolve().parents[1]
JP_ROM = ROOT / "Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba"


class TestEditorView(unittest.TestCase):
    def test_filter_rows_by_query(self):
        data = {"names": {"0": {"en": "Aqua Snake"}, "1": {"en": "Dark Magician"}}}
        assert filter_rows(data, "names", "aqua") == [("0", "Aqua Snake")]

    def test_apply_edit_updates_entry(self):
        data = {"names": {"0": {"en": "Old", "source": "Manual translation"}}}
        updated = apply_edit(data, "names", "0", "New")
        assert updated["names"]["0"] == {"en": "New", "source": "Manual translation"}

    def test_combine_data_adds_overrides_section(self):
        manual = {"names": {}}
        overrides = {"5": {"en": "Short"}}
        assert combine_data(manual, overrides)["overrides"] == overrides

    def test_validation_for_script_detects_lost_token(self):
        problems = validation_for("script", "$t1Olá $nMundo", "Olá Mundo")
        assert any("token" in p for p in problems)

    def test_validation_for_ui_detects_lost_token(self):
        problems = validation_for("ui", "Use @3 this card", "Use this card")
        assert any("token" in p for p in problems)

    @unittest.skipUnless(os.environ.get("DISPLAY"), "requires X11")
    def test_window_loads_real_data(self):
        window = EditorWindow()
        assert set(SECTIONS) == {"names", "descriptions", "script", "ui", "overrides"}
        assert len(window._page("names")["store"]) > 0
        window.destroy()


class TestEditorCore(unittest.TestCase):
    def test_validate_preserves_tokens(self):
        assert validate_entry("$t1Olá $nMundo", "$t1Hello $nWorld", limit=63) == []

    def test_validate_rejects_lost_token(self):
        problems = validate_entry("$t1Olá $nMundo", "Hello World", limit=63)
        assert any("token" in p for p in problems)

    def test_validate_rejects_overflow(self):
        problems = validate_entry("x", "Ａ" * 40, limit=63)
        assert any("63" in p for p in problems)

    def test_validate_measures_fullwidth_bytes(self):
        problems = validate_entry("x", "A" * 40, limit=63)
        assert any("63" in p for p in problems)

    def test_validate_reports_non_cp932_character(self):
        problems = validate_entry("x", "OK 😀", limit=63)
        assert any("cp932" in p for p in problems)

    def test_save_roundtrip_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual.json"
            path.write_text(json.dumps({"names": {"0": {"en": "Old"}}}), encoding="utf-8")
            data = {"names": {"0": {"en": "New"}}}
            save_translations(data, path)
            assert load_translations(path) == data
            assert (path.parent / "manual.json.bak").exists()

    def test_load_overrides(self):
        data = load_overrides(Path("data/manual_descriptions.json"))
        assert isinstance(data, dict) and data


@unittest.skipUnless(JP_ROM.exists(), "JP ROM ausente")
class TestCardData(unittest.TestCase):
    def setUp(self):
        self.data = Rom(JP_ROM).data

    def test_stats_rows_lists_every_card_with_name(self):
        rows = stats_rows(self.data, {"803": {"en": "Dark Magician"}})
        assert len(rows) == 1115
        assert rows[803][0] == "803"
        assert "Dark Magician" in rows[803][1]

    def test_stats_rows_describes_stats_without_names(self):
        rows = stats_rows(self.data)
        assert "ATK 2500" in rows[803][1]
        assert "DEF 2100" in rows[803][1]
        assert "Lv 7" in rows[803][1]

    def test_apply_stats_edit_updates_only_that_field(self):
        before = read_stats(self.data)
        edited = apply_stats_edit(self.data, 803, "atk", "2600")
        after = read_stats(edited)
        assert after[803]["atk"] == 2600
        assert after[803]["def"] == before[803]["def"]
        assert after[:803] == before[:803]
        assert after[804:] == before[804:]

    def test_apply_stats_edit_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            apply_stats_edit(self.data, 803, "atk", "2605")
        with self.assertRaises(ValueError):
            apply_stats_edit(self.data, 803, "level", "16")

    def test_apply_stats_edit_password_roundtrip(self):
        edited = apply_stats_edit(self.data, 1114, "password", "12345678")
        assert read_password(edited)[1114] == "12345678"
        cleared = apply_stats_edit(edited, 1114, "password", "")
        assert read_password(cleared)[1114] is None

    def test_diff_records_groups_contiguous_changes(self):
        assert _diff_records(b"abcdef", b"abXdeY") == [(2, b"X"), (5, b"Y")]


@unittest.skipUnless(os.environ.get("DISPLAY"), "requires X11")
@unittest.skipUnless(JP_ROM.exists(), "JP ROM ausente")
class TestCardDataWindow(unittest.TestCase):
    def test_window_has_card_data_tab(self):
        window = EditorWindow()
        try:
            assert window.notebook.get_n_pages() == len(SECTIONS) + 2
            assert "carddata" in window.views
            page = window._card_page
            assert len(page["store"]) == 1115
            assert set(page["entries"]) == {
                "atk",
                "def",
                "level",
                "attr",
                "race",
                "sub",
                "password",
            }
        finally:
            window.destroy()

    def test_save_writes_output_rom_and_ips_only(self):
        from gi.repository import Gtk

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dm6-en.gba"
            ips = Path(tmp) / "dm6-en.ips"
            with mock.patch("tools.editor.OUT_ROM", out), mock.patch(
                "tools.editor.OUT_IPS", ips
            ):
                window = EditorWindow()
                try:
                    page = window._card_page
                    selection = page["tree"].get_selection()
                    selection.select_iter(
                        page["store"].get_iter(Gtk.TreePath.new_from_string("803"))
                    )
                    page["entries"]["atk"].set_text("2600")
                    window.on_save_card(None)
                    assert window.card_edits[803]["atk"] == "2600"
                finally:
                    window.destroy()
            assert read_stats(Rom(out).data)[803]["atk"] == 2600
            assert read_stats(Rom(JP_ROM).data)[803]["atk"] == 2500
            raw = ips.read_bytes()
            assert raw[:5] == b"PATCH" and raw[-3:] == b"EEE"

    def test_save_creates_backups_of_output_rom_and_ips(self):
        from gi.repository import Gtk

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dm6-en.gba"
            ips = Path(tmp) / "dm6-en.ips"
            out.write_bytes(JP_ROM.read_bytes())
            ips.write_bytes(b"PATCH" + b"\x00" * 32 + b"EEE")
            original_ips = ips.read_bytes()
            with mock.patch("tools.editor.OUT_ROM", out), mock.patch(
                "tools.editor.OUT_IPS", ips
            ):
                window = EditorWindow()
                try:
                    page = window._card_page
                    selection = page["tree"].get_selection()
                    selection.select_iter(
                        page["store"].get_iter(Gtk.TreePath.new_from_string("803"))
                    )
                    page["entries"]["sub"].set_text("1")
                    window.on_save_card(None)
                finally:
                    window.destroy()
            assert out.with_suffix(".gba.bak").read_bytes() == JP_ROM.read_bytes()
            assert ips.with_suffix(".ips.bak").read_bytes() == original_ips

    def test_save_keeps_existing_output_bytes_and_patches_them(self):
        from gi.repository import Gtk

        jp = Rom(JP_ROM).data
        offset = 0xC00000
        marker = b"EN-MARKER"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dm6-en.gba"
            ips = Path(tmp) / "dm6-en.ips"
            out.write_bytes(jp[:offset] + marker + jp[offset + len(marker):])
            with mock.patch("tools.editor.OUT_ROM", out), mock.patch(
                "tools.editor.OUT_IPS", ips
            ):
                window = EditorWindow()
                try:
                    page = window._card_page
                    selection = page["tree"].get_selection()
                    selection.select_iter(
                        page["store"].get_iter(Gtk.TreePath.new_from_string("803"))
                    )
                    page["entries"]["atk"].set_text("2600")
                    window.on_save_card(None)
                finally:
                    window.destroy()
            assert out.read_bytes()[offset:offset + len(marker)] == marker
            assert read_stats(Rom(out).data)[803]["atk"] == 2600
            record = offset.to_bytes(3, "big") + len(marker).to_bytes(2, "big") + marker
            assert record in ips.read_bytes()

    def test_session_card_edits_survive_a_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dm6-en.gba"
            ips = Path(tmp) / "dm6-en.ips"
            out.write_bytes(Rom(JP_ROM).data)
            with mock.patch("tools.editor.OUT_ROM", out), mock.patch(
                "tools.editor.OUT_IPS", ips
            ):
                window = EditorWindow()
                try:
                    window.card_edits[803] = {"atk": "2600"}
                    window._apply_card_edits()
                finally:
                    window.destroy()
            assert read_stats(Rom(out).data)[803]["atk"] == 2600
            patched = bytearray(Rom(JP_ROM).data)
            raw = ips.read_bytes()
            pos = 5
            while raw[pos:pos + 3] != b"EEE":
                offset = int.from_bytes(raw[pos:pos + 3], "big")
                size = int.from_bytes(raw[pos + 3:pos + 5], "big")
                patched[offset:offset + size] = raw[pos + 5:pos + 5 + size]
                pos += 5 + size
            assert bytes(patched) == out.read_bytes()


@unittest.skipUnless(JP_ROM.exists(), "JP ROM ausente")
class TestPaletteData(unittest.TestCase):
    def setUp(self):
        self.data = Rom(JP_ROM).data

    def test_palette_rows_lists_every_card_with_name(self):
        rows = palette_rows(self.data, {"803": {"en": "Dark Magician"}})
        assert len(rows) == 1115
        assert rows[803] == ("803", "Dark Magician")
        assert palette_rows(self.data)[803] == ("803", "Card 803")

    def test_apply_palette_edit_updates_only_that_color(self):
        before = read_palette(self.data)
        edited = apply_palette_edit(self.data, 803, 0, 0x001F)
        after = read_palette(edited)
        assert after[803][0] == 0x001F
        assert after[803][1:] == before[803][1:]
        assert after[:803] == before[:803]
        assert after[804:] == before[804:]

    def test_apply_palette_edit_rejects_invalid_values(self):
        with self.assertRaises(IndexError):
            apply_palette_edit(self.data, 1115, 0, 0)
        with self.assertRaises(ValueError):
            apply_palette_edit(self.data, 0, 64, 0)
        with self.assertRaises(ValueError):
            apply_palette_edit(self.data, 0, 0, 0x10000)


@unittest.skipUnless(os.environ.get("DISPLAY"), "requires X11")
@unittest.skipUnless(JP_ROM.exists(), "JP ROM ausente")
class TestPaletteWindow(unittest.TestCase):
    def _select(self, window, card=803, color=0):
        from gi.repository import Gtk

        page = window._palette_page
        page["tree"].get_selection().select_iter(
            page["store"].get_iter(Gtk.TreePath.new_from_string(str(card)))
        )
        page["swatches"][color].emit("clicked")

    def test_window_has_palette_tab(self):
        window = EditorWindow()
        try:
            assert window.notebook.get_n_pages() == len(SECTIONS) + 2
            assert "palette" in window.views
            page = window._palette_page
            assert len(page["store"]) == 1115
            assert len(page["swatches"]) == 64
            assert set(page["entries"]) == {"r", "g", "b", "hex"}
            sample = page["store"][803][2]
            assert sample.startswith("#") and len(sample) == 7
        finally:
            window.destroy()

    def test_color_fields_stay_in_sync(self):
        window = EditorWindow()
        try:
            self._select(window)
            entries = window._palette_page["entries"]
            entries["hex"].set_text("001F")
            assert [entries[key].get_text() for key in ("r", "g", "b")] == ["31", "0", "0"]
            for key, value in (("r", "31"), ("g", "0"), ("b", "0")):
                entries[key].set_text(value)
            assert entries["hex"].get_text() == "001F"
        finally:
            window.destroy()

    def test_save_writes_output_rom_and_ips_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dm6-en.gba"
            ips = Path(tmp) / "dm6-en.ips"
            with mock.patch("tools.editor.OUT_ROM", out), mock.patch(
                "tools.editor.OUT_IPS", ips
            ):
                window = EditorWindow()
                try:
                    self._select(window)
                    window._palette_page["entries"]["hex"].set_text("001F")
                    window.on_save_palette(None)
                    assert window.palette_edits[803][0] == 0x001F
                finally:
                    window.destroy()
            assert read_palette(Rom(out).data)[803][0] == 0x001F
            assert read_palette(Rom(JP_ROM).data)[803][0] == 0x5A00
            raw = ips.read_bytes()
            assert raw[:5] == b"PATCH" and raw[-3:] == b"EEE"

    def test_save_creates_backups_of_output_rom_and_ips(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dm6-en.gba"
            ips = Path(tmp) / "dm6-en.ips"
            out.write_bytes(JP_ROM.read_bytes())
            ips.write_bytes(b"PATCH" + b"\x00" * 32 + b"EEE")
            original_ips = ips.read_bytes()
            with mock.patch("tools.editor.OUT_ROM", out), mock.patch(
                "tools.editor.OUT_IPS", ips
            ):
                window = EditorWindow()
                try:
                    self._select(window, color=1)
                    window._palette_page["entries"]["hex"].set_text("0000")
                    window.on_save_palette(None)
                finally:
                    window.destroy()
            assert out.with_suffix(".gba.bak").read_bytes() == JP_ROM.read_bytes()
            assert ips.with_suffix(".ips.bak").read_bytes() == original_ips

    def test_session_palette_edits_survive_a_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dm6-en.gba"
            ips = Path(tmp) / "dm6-en.ips"
            out.write_bytes(Rom(JP_ROM).data)
            colors = read_palette(Rom(JP_ROM).data)[803]
            colors[0] = 0x001F
            with mock.patch("tools.editor.OUT_ROM", out), mock.patch(
                "tools.editor.OUT_IPS", ips
            ):
                window = EditorWindow()
                try:
                    window.palette_edits[803] = colors
                    window._apply_palette_edits()
                finally:
                    window.destroy()
            assert read_palette(Rom(out).data)[803][0] == 0x001F
            patched = bytearray(Rom(JP_ROM).data)
            raw = ips.read_bytes()
            pos = 5
            while raw[pos:pos + 3] != b"EEE":
                offset = int.from_bytes(raw[pos:pos + 3], "big")
                size = int.from_bytes(raw[pos + 3:pos + 5], "big")
                patched[offset:offset + size] = raw[pos + 5:pos + 5 + size]
                pos += 5 + size
            assert bytes(patched) == out.read_bytes()
