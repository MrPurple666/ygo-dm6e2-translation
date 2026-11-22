# Changelog

## [0.1.0] - 2026-11-22

### Added

- Tradução para inglês da ROM japonesa de Duel Monsters 6 Expert 2, preservando as 1115 cartas.
- Pipeline Python para extrair nomes, descrições, diálogos e UI das duas ROMs e gerar ROM, IPS e relatório.
- Tabela de traduções manuais e descrições curtas em `data/`.
- Editor desktop GTK 3 com busca, validação, backup e botão de rebuild.
- README e changelog.

### Changed

- Texto de diálogo e cartas gravado em full-width cp932 e dividido em páginas para o renderizador da ROM japonesa.
- Nomes e descrições portados da Worldwide Edition quando casam pelo texto japonês; o restante usa traduções manuais.

### Fixed

- Códigos de controle preservados nas traduções.
- Espaços e dígitos preservados nas quebras de linha e páginas.
- Ponteiros que caíam no meio de caracteres de 2 bytes.
