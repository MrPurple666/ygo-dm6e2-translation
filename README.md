# ygo-dm6e2-translation

Tradução para inglês de **Yu-Gi-Oh! Duel Monsters 6 Expert 2** (GBA, versão japonesa), usando o texto da *Worldwide Edition: Stairway to the Destined Duel* como fonte. A ROM japonesa é mantida como base para preservar as 1115 cartas do lançamento original.

As ROMs não são incluídas neste repositório. Use apenas cópias legais dos jogos.

## Gerar a ROM traduzida

Requisitos: Python 3 e as duas ROMs no diretório do projeto.

```bash
python3 tools/build.py \
  --jp 'Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba' \
  --us 'Yu-Gi-Oh! - Worldwide Edition - Stairway to the Destined Duel (USA) (En,Ja,Fr,De,Es,It).gba' \
  --out dm6-en.gba \
  --ips dm6-en.ips \
  --report translation-report.json
```

Saídas:

- `dm6-en.gba` — ROM patched (16 MiB).
- `dm6-en.ips` — patch IPS para aplicar sobre a ROM japonesa original.
- `translation-report.json` — hashes, contagens e verificação visual.

## Editor de traduções

```bash
python3 tools/editor.py
```

Requisitos: GTK 3 via PyGObject (`gi`). O editor abre abas para nomes, descrições, falas, UI e overrides; filtra entradas; valida códigos de controle (`$...`, `@N`, `%s`) e tamanho em bytes cp932; salva com backup `.bak` e tem botão para rodar o build.

Os textos editáveis ficam em:

- `data/manual.json` — nomes, descrições, falas de script e UI sem par na ROM americana.
- `data/manual_descriptions.json` — descrições curtas para cartas cujo texto inglês não cabe no slot original.

## Estrutura

- `ygo/` — leitura de ROM, tabelas de texto, conversão full-width e build.
- `tools/` — CLI de build e editor desktop.
- `tests/` — suíte `unittest`.

## Testes

```bash
python3 -m unittest discover -s tests -v
```

## Limitações conhecidas

- O renderizador da ROM japonesa exige caracteres full-width; os diálogos são paginados com `$p` para caber na caixa.
- Algumas descrições longas são abreviadas para caber no slot fixo de 0x180 bytes; a quantidade aparece no relatório.
- O logo/título desenhado em arte permanece japonês.
- Traduções manuais foram feitas com terminologia TCG, mas merecem revisão humana.

## Versão

Ver `CHANGELOG.md`.
