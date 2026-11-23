# ygo-dm6e2-translation

English translation of **Yu-Gi-Oh! Duel Monsters 6 Expert 2** (GBA, Japanese release), using the text from *Worldwide Edition: Stairway to the Destined Duel* as the source. The Japanese ROM stays as the base so all 1115 cards from the original release are preserved.

ROMs are not included in this repository. Use only legal copies of the games.

## Build the translated ROM

Requirements: Python 3 and both ROMs in the project directory.

```bash
python3 tools/build.py \
  --jp 'Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba' \
  --us 'Yu-Gi-Oh! - Worldwide Edition - Stairway to the Destined Duel (USA) (En,Ja,Fr,De,Es,It).gba' \
  --out dm6-en.gba \
  --ips dm6-en.ips \
  --report translation-report.json
```

Outputs:

- `dm6-en.gba` — patched ROM (16 MiB).
- `dm6-en.ips` — IPS patch to apply to the original Japanese ROM.
- `translation-report.json` — hashes, counts and visual check.

## Translation editor

```bash
python3 tools/editor.py
```

Requirements: GTK 3 via PyGObject (`gi`). The editor has tabs for names, descriptions, dialogue, UI, overrides and **Card data**. The text tabs filter entries, validate control codes (`$...`, `@N`, `%s`) and cp932 byte size, and save with a `.bak` backup. The Card data tab edits ATK, DEF, level, attribute, race and passwords in the fixed 4-byte records at `0x979D24` and `0x97B74C`, keeping the original ROM untouched. A button runs the build.

Editable text lives in:

- `data/manual.json` — names, descriptions, script lines and UI strings without a match in the US ROM.
- `data/manual_descriptions.json` — short descriptions for cards whose English text does not fit the original slot.

## Structure

- `ygo/` — ROM reading, text tables, full-width conversion, card data and build.
- `tools/` — build CLI and desktop editor.
- `tests/` — `unittest` suite.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Known limitations

- The Japanese ROM renderer requires full-width characters; dialogue is split into pages with `$p` to fit the text box.
- Some long descriptions are shortened to fit the fixed 0x180-byte slot; the count is in the report.
- The drawn title/logo artwork remains Japanese.
- Manual translations use TCG terminology but still deserve human review.

## Version

See `CHANGELOG.md`.
