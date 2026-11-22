"""Editor desktop das traduções de Yu-Gi-Oh! DM6 Expert 2."""

import copy
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

MANUAL = Path("data/manual.json")
OVERRIDES = Path("data/manual_descriptions.json")
JP_ROM = Path("Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba")
US_ROM = Path(
    "Yu-Gi-Oh! - Worldwide Edition - Stairway to the Destined Duel (USA) "
    "(En,Ja,Fr,De,Es,It).gba"
)
SECTIONS = {
    "names": "Nomes",
    "descriptions": "Descrições",
    "script": "Falas",
    "ui": "UI",
    "overrides": "Overrides",
}
LIMITS = {"names": 63, "descriptions": 383, "overrides": 383}


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


def apply_edit(data: dict, section: str, key: str, text: str) -> dict:
    updated = copy.deepcopy(data)
    if section == "overrides":
        updated[section][key] = text
    else:
        updated[section][key] = {"en": text, "source": "edited in editor"}
    return updated


class EditorWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Editor de Traduções — DM6 Expert 2")
        self.set_default_size(1000, 700)
        self.data = combine_data(load_translations(MANUAL), load_overrides(OVERRIDES))
        self.current_section = "names"
        self.current_key = None

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(main_box)
        self.notebook = Gtk.Notebook()
        main_box.pack_start(self.notebook, True, True, 0)

        self.views = {}
        for section, label in SECTIONS.items():
            page = self._build_page(section)
            self.notebook.append_page(page, Gtk.Label(label=label))
            self.views[section] = page

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.status = Gtk.Label(label="")
        bottom.pack_start(self.status, True, True, 0)
        build_button = Gtk.Button(label="Gerar ROM/IPS")
        build_button.connect("clicked", self.on_build)
        bottom.pack_start(build_button, False, False, 0)
        main_box.pack_start(bottom, False, False, 0)

        self.notebook.connect("switch-page", self.on_switch_page)
        self._refresh("names")

    def _build_page(self, section: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        search = Gtk.Entry()
        search.set_placeholder_text("Buscar (índice, offset ou texto)")
        search.connect("changed", self.on_search)
        box.pack_start(search, False, False, 0)

        store = Gtk.ListStore(str, str)
        tree = Gtk.TreeView(model=store)
        for column_index, title in enumerate(("Chave", "Texto")):
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
        save = Gtk.Button(label="Salvar entrada")
        save.connect("clicked", self.on_save_entry)
        reload = Gtk.Button(label="Recarregar arquivos")
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
        limit = LIMITS.get(self.current_section, 0)
        problems = [] if limit == 0 else validate_entry(
            original, self._current_text(self.current_section), limit=limit
        )
        self.status.set_text(" | ".join(problems))
        return problems

    def on_save_entry(self, button):
        if self.current_key is None:
            self.status.set_text("selecione uma entrada")
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
        self.status.set_text("salvo")

    def _save_files(self):
        manual = {key: value for key, value in self.data.items() if key != "overrides"}
        save_translations(manual, MANUAL)
        save_translations(self.data["overrides"], OVERRIDES)

    def on_reload(self, button):
        self.data = combine_data(load_translations(MANUAL), load_overrides(OVERRIDES))
        self._refresh(self.current_section)
        self.status.set_text("recarregado")

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
                "dm6-en.gba",
                "--ips",
                "dm6-en.ips",
                "--report",
                "translation-report.json",
            ],
            capture_output=True,
            text=True,
        )
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=(result.stdout + result.stderr).strip() or "build concluído",
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
