import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.editor import EditorWindow, SECTIONS, apply_edit, combine_data, filter_rows, validation_for
from tools.editor_core import (
    load_overrides,
    load_translations,
    save_translations,
    validate_entry,
)


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
