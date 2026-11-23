"""Desktop editor for the Yu-Gi-Oh! DM6 Expert 2 translation."""

import copy
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402


from tools.editor_core import (  # noqa: E402
    load_overrides,
    load_translations,
    save_translations,
    validate_entry,
)
from ygo.carddata import (  # noqa: E402
    read_password,
    read_stats,
    write_password,
    write_stats,
)
from ygo.rom import Rom, write_ips  # noqa: E402

MANUAL = Path("data/manual.json")
OVERRIDES = Path("data/manual_descriptions.json")
JP_ROM = Path("Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba")
US_ROM = Path(
    "Yu-Gi-Oh! - Worldwide Edition - Stairway to the Destined Duel (USA) "
    "(En,Ja,Fr,De,Es,It).gba"
)
OUT_ROM = Path("dm6-en.gba")
OUT_IPS = Path("dm6-en.ips")
SECTIONS = {
    "names": "Names",
    "descriptions": "Descriptions",
    "script": "Dialogue",
    "ui": "UI",
    "overrides": "Overrides",
}
LIMITS = {"names": 63, "descriptions": 383, "overrides": 383}

CARD_FIELDS = ("atk", "def", "level", "attr", "race", "sub", "password")
CARD_COLUMNS = {"atk": 2, "def": 3, "level": 4, "attr": 5, "race": 6, "sub": 7, "password": 8}
IPS_MAX = 0xFFFF


def combine_data(manual: dict, overrides: dict) -> dict:
    data = copy.deepcopy(manual)
    data["overrides"] = copy.deepcopy(overrides)
    return data


def _text_of(value) -> str:
    if isinstance(value, dict):
        return value.get("en", "")
    return str(value)


def _sort_key(key: str):
    try:
        return (0, int(key))
    except ValueError:
        return (1, key.lower())


def filter_rows(data: dict, section: str, query: str) -> list[tuple[str, str]]:
    rows = [
        (str(key), _text_of(value))
        for key, value in data.get(section, {}).items()
    ]
    needle = query.strip().lower()
    if needle:
        rows = [
            (key, text)
            for key, text in rows
            if needle in key.lower() or needle in text.lower()
        ]
    return sorted(rows, key=lambda row: _sort_key(row[0]))


def validation_for(section: str, original: str, edited: str) -> list[str]:
    """Validate any section; dialogue/UI use a high informational limit."""
    return validate_entry(original, edited, limit=LIMITS.get(section, 10_000))


def apply_edit(data: dict, section: str, key: str, text: str) -> dict:
    updated = copy.deepcopy(data)
    if section == "overrides":
        updated[section][key] = text
    else:
        entry = dict(updated[section][key])
        entry["en"] = text
        updated[section][key] = entry
    return updated


def stats_rows(rom, names: dict | None = None) -> list[tuple[str, str]]:
    """Uma linha por carta: índice e descrição curta com o nome, se houver."""
    names = names or {}
    passwords = read_password(rom)
    rows = []
    for index, stats in enumerate(read_stats(rom)):
        name = _text_of(names.get(str(index), ""))
        description = (
            f"ATK {stats['atk']} DEF {stats['def']} Lv {stats['level']} "
            f"Attr {stats['attr']} Race {stats['race']}"
        )
        if name:
            description = f"{name} - {description}"
        if passwords[index]:
            description += f" Pwd {passwords[index]}"
        rows.append((str(index), description))
    return rows


def apply_stats_edit(rom: bytes, index: int, field: str, value) -> bytes:
    """Aplica um campo de stats ou a senha sobre uma cópia da ROM."""
    if field == "password":
        return write_password(rom, index, None if value in (None, "") else str(value))
    if field not in CARD_COLUMNS:
        raise ValueError(f"campo desconhecido: {field}")
    stats = dict(read_stats(rom)[index])
    try:
        stats[field] = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} deve ser inteiro: {value!r}") from None
    return write_stats(rom, index, stats)


def _diff_records(original: bytes, patched: bytes) -> list[tuple[int, bytes]]:
    """Registros IPS (offset, bytes) das diferenças, em blocos de 0xFFFF."""
    if len(original) != len(patched):
        raise ValueError("ROMs de tamanhos diferentes")
    runs: list[tuple[int, bytes]] = []
    chunk_size = 0x10000
    for base in range(0, len(patched), chunk_size):
        old_chunk = original[base : base + chunk_size]
        new_chunk = patched[base : base + chunk_size]
        if old_chunk == new_chunk:
            continue
        start = None
        for offset, (old, new) in enumerate(zip(old_chunk, new_chunk)):
            if old != new and start is None:
                start = offset
            elif old == new and start is not None:
                runs.append((base + start, new_chunk[start:offset]))
                start = None
        if start is not None:
            runs.append((base + start, new_chunk[start:]))

    records: list[tuple[int, bytes]] = []
    for offset, payload in runs:
        while payload:
            piece = payload[:IPS_MAX]
            records.append((offset, piece))
            offset += len(piece)
            payload = payload[len(piece):]
    return records


class EditorWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Translation Editor - DM6 Expert 2")
        self.set_default_size(1000, 700)
        self.data = combine_data(load_translations(MANUAL), load_overrides(OVERRIDES))
        self.current_section = "names"
        self.current_key = None
        self.current_card = None
        self.card_edits: dict[int, dict[str, str]] = {}
        self.jp_data = None
        self.rom_error = ""
        try:
            self.jp_data = Rom(JP_ROM).data
        except OSError as exc:
            self.rom_error = str(exc)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(main_box)
        self.notebook = Gtk.Notebook()
        main_box.pack_start(self.notebook, True, True, 0)

        self.views = {}
        for section, label in SECTIONS.items():
            page = self._build_page(section)
            self.notebook.append_page(page, Gtk.Label(label=label))
            self.views[section] = page
        card_page = self._build_card_page()
        self.notebook.append_page(card_page, Gtk.Label(label="Card data"))
        self.views["carddata"] = card_page

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.status = Gtk.Label(label="")
        bottom.pack_start(self.status, True, True, 0)
        build_button = Gtk.Button(label="Build ROM/IPS")
        build_button.connect("clicked", self.on_build)
        bottom.pack_start(build_button, False, False, 0)
        main_box.pack_start(bottom, False, False, 0)

        self.notebook.connect("switch-page", self.on_switch_page)
        self._refresh("names")
        self._refresh_cards()

    def _build_page(self, section: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        search = Gtk.Entry()
        search.set_placeholder_text("Search (index, offset or text)")
        search.connect("changed", self.on_search)
        box.pack_start(search, False, False, 0)

        store = Gtk.ListStore(str, str)
        tree = Gtk.TreeView(model=store)
        for column_index, title in enumerate(("Key", "Text")):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=column_index)
            tree.append_column(column)
        selection = tree.get_selection()
        selection.connect("changed", self.on_select)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(tree)
        box.pack_start(scrolled, True, True, 0)

        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        text_scrolled = Gtk.ScrolledWindow()
        text_scrolled.add(text_view)
        box.pack_start(text_scrolled, True, True, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        save = Gtk.Button(label="Save entry")
        save.connect("clicked", self.on_save_entry)
        reload = Gtk.Button(label="Reload files")
        reload.connect("clicked", self.on_reload)
        buttons.pack_start(save, False, False, 0)
        buttons.pack_start(reload, False, False, 0)
        box.pack_start(buttons, False, False, 0)

        page_data = {
            "search": search,
            "store": store,
            "tree": tree,
            "text_view": text_view,
            "section": section,
        }
        box._editor = page_data  # type: ignore[attr-defined]
        return box

    def _page(self, section: str) -> dict:
        return self.views[section]._editor  # type: ignore[attr-defined]

    def _build_card_page(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        warning = Gtk.Label(label="")
        box.pack_start(warning, False, False, 0)

        store = Gtk.ListStore(*([str] * 9))
        tree = Gtk.TreeView(model=store)
        titles = ("Index", "Name", "ATK", "DEF", "Level", "Attr", "Race", "Sub", "Password")
        for column_index, title in enumerate(titles):
            renderer = Gtk.CellRendererText()
            tree.append_column(Gtk.TreeViewColumn(title, renderer, text=column_index))
        tree.set_search_column(1)
        tree.get_selection().connect("changed", self.on_card_select)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(tree)
        box.pack_start(scrolled, True, True, 0)

        grid = Gtk.Grid(column_spacing=6, row_spacing=6)
        entries = {}
        for column, field in enumerate(CARD_FIELDS):
            grid.attach(Gtk.Label(label=field.upper()), column, 0, 1, 1)
            entries[field] = Gtk.Entry()
            grid.attach(entries[field], column, 1, 1, 1)
        box.pack_start(grid, False, False, 0)

        save = Gtk.Button(label="Save card")
        save.connect("clicked", self.on_save_card)
        box.pack_start(save, False, False, 0)

        self._card_page = {
            "store": store,
            "tree": tree,
            "entries": entries,
            "warning": warning,
        }
        return box

    def _card_output(self) -> bytes:
        try:
            return OUT_ROM.read_bytes()
        except OSError:
            return self.jp_data

    def _refresh_cards(self) -> None:
        page = self._card_page
        page["store"].clear()
        self.current_card = None
        if self.jp_data is None:
            page["warning"].set_text(f"JP ROM unavailable: {self.rom_error}")
            return
        page["warning"].set_text("")
        data = self._card_output()
        stats = read_stats(data)
        passwords = read_password(data)
        names = self.data.get("names", {})
        for key, _description in stats_rows(data, names):
            index = int(key)
            entry = stats[index]
            page["store"].append(
                [
                    key,
                    _text_of(names.get(key, "")),
                    str(entry["atk"]),
                    str(entry["def"]),
                    str(entry["level"]),
                    str(entry["attr"]),
                    str(entry["race"]),
                    str(entry["sub"]),
                    passwords[index] or "",
                ]
            )

    def on_card_select(self, selection):
        model, iterator = selection.get_selected()
        if iterator is None:
            return
        values = list(model[iterator])
        self.current_card = int(values[0])
        for field, entry in self._card_page["entries"].items():
            entry.set_text(values[CARD_COLUMNS[field]])

    def on_save_card(self, button):
        if self.jp_data is None:
            self.status.set_text("JP ROM unavailable")
            return
        if self.current_card is None:
            self.status.set_text("select a card")
            return
        index = self.current_card
        data = self._card_output()
        try:
            for field, entry in self._card_page["entries"].items():
                data = apply_stats_edit(data, index, field, entry.get_text())
        except (IndexError, ValueError) as exc:
            self.status.set_text(str(exc))
            return
        if OUT_ROM.resolve() == JP_ROM.resolve():
            self.status.set_text("refusing to overwrite the JP ROM")
            return
        for path in (OUT_ROM, OUT_IPS):
            if path.exists():
                shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        OUT_ROM.write_bytes(data)
        write_ips(OUT_IPS, _diff_records(self.jp_data, data))
        self.card_edits[index] = {
            field: entry.get_text()
            for field, entry in self._card_page["entries"].items()
        }
        self._refresh_cards()
        self.status.set_text(f"saved card {index}")

    def _refresh(self, section: str, query: str = "") -> None:
        page = self._page(section)
        page["store"].clear()
        for key, text in filter_rows(self.data, section, query):
            page["store"].append([key, text])

    def _current_text(self, section: str) -> str:
        view = self._page(section)["text_view"]
        buffer = view.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def on_switch_page(self, notebook, page, index):
        if index >= len(SECTIONS):
            self.current_section = "carddata"
            self.current_key = None
            return
        section = list(SECTIONS)[index]
        self.current_section = section
        self.current_key = None
        self._refresh(section, self._page(section)["search"].get_text())

    def on_search(self, entry):
        section = self.current_section
        self._refresh(section, entry.get_text())

    def on_select(self, selection):
        model, iterator = selection.get_selected()
        if iterator is None:
            return
        section = self.current_section
        key = model[iterator][0]
        self.current_key = key
        text = self._text_of(self.data[section][key])
        view = self._page(section)["text_view"]
        buffer = view.get_buffer()
        buffer.set_text(text)
        self._validate_current()

    def _text_of(self, value) -> str:
        return _text_of(value)

    def _validate_current(self) -> list[str]:
        if self.current_key is None:
            self.status.set_text("")
            return []
        original = self._text_of(self.data[self.current_section][self.current_key])
        problems = validation_for(
            self.current_section, original, self._current_text(self.current_section)
        )
        self.status.set_text(" | ".join(problems))
        return problems

    def on_save_entry(self, button):
        if self.current_key is None:
            self.status.set_text("select an entry")
            return
        if self._validate_current():
            return
        self.data = apply_edit(
            self.data,
            self.current_section,
            self.current_key,
            self._current_text(self.current_section),
        )
        self._save_files()
        self._refresh(self.current_section)
        self.status.set_text("saved")

    def _save_files(self):
        manual = {key: value for key, value in self.data.items() if key != "overrides"}
        save_translations(manual, MANUAL)
        save_translations(self.data["overrides"], OVERRIDES)

    def on_reload(self, button):
        self.data = combine_data(load_translations(MANUAL), load_overrides(OVERRIDES))
        if self.current_section in SECTIONS:
            self._refresh(self.current_section)
        self._refresh_cards()
        self.status.set_text("reloaded")

    def _apply_card_edits(self) -> None:
        """Reaplica as edições da sessão, que o rebuild apaga da ROM de saída."""
        if not self.card_edits or self.jp_data is None:
            return
        try:
            data = OUT_ROM.read_bytes()
            for index, fields in self.card_edits.items():
                for field, value in fields.items():
                    data = apply_stats_edit(data, index, field, value)
        except (OSError, IndexError, ValueError) as exc:
            self.status.set_text(f"card edits not applied: {exc}")
            return
        OUT_ROM.write_bytes(data)
        write_ips(OUT_IPS, _diff_records(self.jp_data, data))

    def on_build(self, button):
        result = subprocess.run(
            [
                sys.executable,
                "tools/build.py",
                "--jp",
                str(JP_ROM),
                "--us",
                str(US_ROM),
                "--out",
                str(OUT_ROM),
                "--ips",
                str(OUT_IPS),
                "--report",
                "translation-report.json",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self._apply_card_edits()
        self._refresh_cards()
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=f"exit code {result.returncode}\n"
            + ((result.stdout + result.stderr).strip() or "build finished"),
        )
        dialog.run()
        dialog.destroy()


def main() -> None:
    window = EditorWindow()
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
