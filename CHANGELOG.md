# Changelog

## [0.1.0] - 2026-11-22

### Added

- English translation of the Japanese ROM of Duel Monsters 6 Expert 2, preserving all 1115 cards.
- Python pipeline to extract names, descriptions, dialogue and UI text from both ROMs and generate a ROM, IPS patch and report.
- Card data tab for editing ATK, DEF, level, attribute, race and passwords, with fixed-slot validation and IPS regeneration.
- GTK 3 desktop editor with search, validation, backup and rebuild button.
- README and changelog.

### Changed

- Dialogue and card text is written in full-width cp932 and split into pages for the Japanese ROM renderer.
- Names and descriptions are ported from Worldwide Edition when they match by Japanese text; the rest use manual translations.

### Fixed

- Control codes are preserved in all translations.
- Spaces and digits are preserved across line breaks and page breaks.
- Pointers that landed in the middle of 2-byte characters.
