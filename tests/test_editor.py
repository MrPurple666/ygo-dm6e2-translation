import json
import tempfile
import unittest
from pathlib import Path

from tools.editor_core import (
    load_overrides,
    load_translations,
    save_translations,
    validate_entry,
)


class TestEditorCore(unittest.TestCase):
    def test_validate_preserves_tokens(self):
        assert validate_entry("$t1Olá $nMundo", "$t1Hello $nWorld", limit=63) == []

    def test_validate_rejects_lost_token(self):
        problems = validate_entry("$t1Olá $nMundo", "Hello World", limit=63)
        assert any("token" in p for p in problems)

    def test_validate_rejects_overflow(self):
        problems = validate_entry("x", "Ａ" * 40, limit=63)
        assert any("63" in p for p in problems)

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
