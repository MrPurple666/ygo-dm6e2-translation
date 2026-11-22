# DM6 Expert 2 English Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gerar uma ROM patched de `Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba` em inglês, usando a Worldwide Edition como fonte de texto e preservando as 1115 cartas da versão japonesa.

**Architecture:** Pipeline Python puro lê as duas ROMs, extrai tabelas de nomes/descrições e o script de diálogo, casa o texto japonês presente nas duas ROMs, escolhe a variante inglesa e aplica as substituições numa cópia da ROM japonesa. Textos que não cabem no slot original são realocados para a região livre e têm seus ponteiros atualizados. Um script de verificação valida a ROM resultante.

**Tech Stack:** Python 3 (somente biblioteca padrão: `pathlib`, `struct`, `json`, `hashlib`, `unittest`), `mgba-qt` para inspeção visual.

**Spec:** `docs/superpowers/specs/2026-11-22-dm6-english-translation-design.md`

## Global Constraints

- ROMs de entrada: `Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba` (SHA-256 `6b75a36a9da1d1575c976dc6954222061fed15c6cdd4b8081832b810b0b82b02`) e `Yu-Gi-Oh! - Worldwide Edition - Stairway to the Destined Duel (USA) (En,Ja,Fr,De,Es,It).gba` (SHA-256 `c4c3ef5c8980996be049a3b6efd1c99b165e565405e040ea428801a14b8c8aa9`). Nunca modificar os originais.
- ROM de saída: exatamente `16777216` bytes; patch IPS clássico (`PATCH` + offsets de 24 bits + `EEE`).
- Texto: Shift-JIS (cp932) com códigos de controle ASCII (`$n`, `$c`, `$fot`, `$a(...)`, `$g(...)`, `$i`, `$o(...)`, `$t...`). Códigos de controle devem ser preservados literalmente.
- Constantes: `JP_NAME=0x2AA160`, `JP_DESC=0x2CD0A0`, `NAME_STRIDE=0x40`, `DESC_STRIDE=0x180`, `CARD_COUNT_JP=1115`, `US_NAME=0x385564`, `US_JPNAME=0x8475FC`, `CARD_COUNT_US=1086`, `US_EN_DESC=0x89C47E`, `US_JP_DESC=0x8B8FAA`.
- Blocos de idioma da ROM americana têm 1082 descrições não vazias cada; o bloco inglês começa em `0x89C47E` e o japonês em `0x8B8FAA`.
- Espaço livre da ROM japonesa: `0xC32CF4` a `0xFFFFFF` (zeros).
- Casamento exato de nomes japoneses: 1083 de 1115. Oito descrições inglesas excedem 383 bytes e exigem versões manuais mais curtas, sem perda de sentido.
- Sem dependências externas, sem `git add`/commit (diretório não é repositório). Checkpoint = rodar a suíte de testes.

## Review Focus

- Diálogos exclusivos do JP sem equivalente na Worldwide: o build deve listá-los em `data/manual.json` e a verificação deve acusar nenhum caractere japonês não documentado → teste end-to-end varre todas as strings patched.
- Códigos de controle corrompidos ao trocar idioma: cada string portada deve manter exatamente a mesma sequência de tokens `$...` do original → teste de prefixo no Task 4.
- Descrição maior que o slot de 0x180: nenhuma descrição final pode passar de 383 bytes → teste de overflow no Task 3.
- Ponteiro de script realocado apontando para lixo: todo ponteiro alterado deve apontar para string terminada em NUL e decodificável → teste no Task 5.
- Originais sobrescritos ou ROM final com tamanho errado: hashes dos originais e tamanho 16 MiB são assertados no Task 5.

---

### Task 1: Primitivas de ROM e texto

**Files:**
- Create: `ygo/__init__.py`
- Create: `ygo/rom.py`
- Create: `ygo/text.py`
- Test: `tests/test_ygo.py`

**Interfaces:**
- Consumes: caminhos das ROMs via `Path`; variáveis de ambiente `YGO_JP_ROM` / `YGO_US_ROM` com fallback para os nomes no diretório atual.
- Produces: `Rom(path: Path)` com `.data: bytes`, `.size: int`, `.read_slot(offset: int, size: int) -> bytes`, `.strings(start: int, count: int, *, jp_only: bool = False, ascii_only: bool = False) -> list[tuple[int, bytes]]` (strings terminadas em NUL, pulando padding de zeros), `.write(offset: int, payload: bytes) -> None`, `.save(path: Path) -> None`, `.sha256() -> str`.
- Produces: `write_ips(path: Path, records: Iterable[tuple[int, bytes]]) -> None`.
- Produces: `decode(raw: bytes) -> str`, `encode(text: str) -> bytes`, `cp932_len(text: str) -> int`, `contains_japanese(text: str) -> bool`, `control_prefix(text: str) -> str`, `strip_breaks(text: str) -> str`.

- [ ] **Step 1: Escrever testes que falham**

```python
def test_slot_le_nome_japones():
    rom = Rom(JP)
    assert rom.read_slot(0x2AA160, 0x40).split(b"\x00")[0].decode("cp932") == "地縛霊"

def test_strings_do_bloco_ingles():
    rom = Rom(US)
    first = rom.strings(0x89C47E, 3, ascii_only=True)
    assert first[0][0] == 0x89C47E
    assert first[0][1].startswith(b"A vengeful creature")

def test_texto_roundtrip_e_controles():
    s = "$g(1,L,1)$fit$iグールズが立ち去った後$nカバン"
    assert decode(encode(s)) == s
    assert control_prefix(s) == "$g(1,L,1)$fit$i"
    assert contains_japanese(s) and not contains_japanese("After the Ghouls departed")

def test_ips():
    write_ips(tmp, [(0x123, b"ABC")])
    raw = tmp.read_bytes()
    assert raw[:5] == b"PATCH"
    assert raw[5:8] == (0x123).to_bytes(3, "big")
    assert raw[8:10] == (3).to_bytes(2, "big")
    assert raw[10:13] == b"ABC" and raw[-3:] == b"EEE"
```

- [ ] **Step 2: Rodar os testes e conferir que falham**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL com `ModuleNotFoundError: ygo` ou `Rom is not defined`.

- [ ] **Step 3: Implementar `ygo/rom.py` e `ygo/text.py` com as assinaturas acima**

`strings()` deve parar quando encontrar byte de controle fora de tabulação/nova linha ou quando o tamanho passar de 700 bytes; `write_ips()` usa big-endian para offset e tamanho.

- [ ] **Step 4: Rodar os testes e conferir que passam**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS (4 testes novos).

- [ ] **Step 5: Checkpoint**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS.

---

### Task 2: Tabelas de nomes de cartas

**Files:**
- Modify: `ygo/tables.py` (criar)
- Test: `tests/test_ygo.py`

**Interfaces:**
- Consumes: `Rom`, `decode` do Task 1.
- Produces: `OFFSETS: dict[str, int]` com todas as constantes de `Global Constraints`.
- Produces: `extract_names(rom: Rom, base: int, count: int) -> list[str]` — lê `count` slots de `NAME_STRIDE` bytes.
- Produces: `match_names(jp_names: list[str], us_jp_names: list[str]) -> dict[int, int]` — índice JP → índice US por nome japonês exato; nomes JP repetidos usam a primeira ocorrência US ainda não usada.

- [ ] **Step 1: Escrever testes que falham**

```python
def test_nomes_jp_e_us():
    jp = extract_names(Rom(JP), OFFSETS["JP_NAME"], 1115)
    us = extract_names(Rom(US), OFFSETS["US_NAME"], 1086)
    assert len(jp) == 1115 and len(us) == 1086
    assert jp[0] == "地縛霊" and us[0] == "Earthbound Spirit"
    assert jp[-1] == "スライムモンスタートークン"

def test_casamento_de_nomes():
    jp = extract_names(Rom(JP), OFFSETS["JP_NAME"], 1115)
    us_jp = extract_names(Rom(US), OFFSETS["US_JPNAME"], 1086)
    m = match_names(jp, us_jp)
    assert len(m) == 1083
    assert m[0] == 0 and m[1] == 1
```

- [ ] **Step 2: Rodar os testes e conferir que falham**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL com `ImportError: cannot import name 'extract_names'`.

- [ ] **Step 3: Implementar `extract_names()` e `match_names()` em `ygo/tables.py`**

- [ ] **Step 4: Rodar os testes e conferir que passam**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 5: Checkpoint**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS.

---

### Task 3: Descrições de cartas e overrides curtos

**Files:**
- Modify: `ygo/tables.py`
- Create: `data/manual_descriptions.json`
- Test: `tests/test_ygo.py`

**Interfaces:**
- Consumes: `Rom`, `decode`, `OFFSETS` do Task 2.
- Produces: `extract_jp_descriptions(rom: Rom) -> list[str]` — 1115 slots de `DESC_STRIDE` em `JP_DESC`.
- Produces: `extract_us_language_block(rom: Rom, start: int, *, ascii_only: bool, jp_only: bool) -> list[str]` — 1082 strings não vazias, pulando padding.
- Produces: `match_descriptions(jp_desc: list[str], us_jp_desc: list[str]) -> dict[int, int]` — índice do slot JP → posição no bloco inglês, casando pelo texto japonês exato.
- Produces: `find_overflows(english: list[str], limit: int = 383) -> list[int]`.
- `data/manual_descriptions.json`: objeto `{ "<posição no bloco inglês>": "<texto curto em inglês>" }` com uma entrada para cada uma das 8 posições de overflow.

- [ ] **Step 1: Escrever testes que falham**

```python
def test_descricoes_jp():
    d = extract_jp_descriptions(Rom(JP))
    assert len(d) == 1115
    assert d[0].startswith("闘いに敗れた兵士たちの魂が一つになった怨霊")
    assert d[-1] == ""

def test_blocos_ingles_e_japones():
    us = Rom(US)
    en = extract_us_language_block(us, OFFSETS["US_EN_DESC"], ascii_only=True, jp_only=False)
    jp = extract_us_language_block(us, OFFSETS["US_JP_DESC"], ascii_only=False, jp_only=True)
    assert len(en) == len(jp) == 1082
    assert en[0].startswith("A vengeful creature")
    assert jp[0].startswith("闘いに敗れた兵士たち")

def test_overflow_tem_override():
    us = Rom(US)
    en = extract_us_language_block(us, OFFSETS["US_EN_DESC"], ascii_only=True, jp_only=False)
    over = find_overflows(en)
    assert len(over) == 8
    manual = json.loads(MANUAL_DESCRIPTIONS.read_text())
    assert all(str(i) in manual for i in over)
    assert all(cp932_len(manual[str(i)]) <= 383 for i in over)
```

- [ ] **Step 2: Rodar os testes e conferir que falham**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL com `ImportError: cannot import name 'extract_jp_descriptions'`.

- [ ] **Step 3: Implementar as três funções em `ygo/tables.py`**

`extract_jp_descriptions()` lê slots fixos de 0x180; `extract_us_language_block()` usa `Rom.strings()` e filtra por presença/ausência de bytes >= 0x80; `find_overflows()` usa `cp932_len()`.

- [ ] **Step 4: Escrever as 8 descrições manuais em `data/manual_descriptions.json`**

Usar a regra oficial da carta em inglês, reduzida a uma redação completa que caiba em 383 bytes. Preservar todos os efeitos, condições e "once per turn". Registrar a posição e o texto.

- [ ] **Step 5: Rodar os testes e conferir que passam**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 6: Checkpoint**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS.

---

### Task 4: Portabilidade do script de diálogo

**Files:**
- Modify: `ygo/tables.py`
- Test: `tests/test_ygo.py`

**Interfaces:**
- Consumes: `Rom`, `decode`, `control_prefix`, `strip_breaks`.
- Produces: `@dataclass(frozen=True) ScriptString(offset: int, prefix: str, body: str)`.
- Produces: `extract_script(rom: Rom) -> list[ScriptString]` — varredura de u32 little-endian em toda a ROM que apontam para `0x08000000 + off`, mantendo apenas alvos que decodificam como texto com tokens `$...` ou japonês/ASCII; ordenar por offset; cada string é dividida em prefixo de tokens `$...` e corpo. Isso cobre diálogos, menus, nomes de booster, senhas e ajuda — não apenas a faixa de diálogo.
- Produces: `match_script(jp: list[ScriptString], us: list[ScriptString]) -> dict[int, int]` — offset da string JP → offset da string inglesa na ROM US. Casar por prefixo idêntico e corpo japonês normalizado (`strip_breaks()` remove `$n`, `$c`, `$p...` e espaços; `．．．` equivale a `…`).

- [ ] **Step 1: Escrever testes que falham**

```python
def test_extract_script_encontra_ponteiro_e_string():
    jp = extract_script(Rom(JP))
    s = next(x for x in jp if x.offset == 0x8CDBC)
    assert s.prefix == "$g(1,L,1)$fit$i"
    assert s.body.startswith("グールズが立ち去った後")
    assert any(  # ponteiro existe na ROM JP
        int.from_bytes(Rom(JP).data[i:i+4], "little") == 0x0808CDBC
        for i in range(0, 0x200000, 4)
    )

def test_match_script_ancora():
    jp = extract_script(Rom(JP))
    us = extract_script(Rom(US))
    m = match_script(jp, us)
    assert m[0x8CDBC] == 0x96838
    assert us[[x.offset for x in us].index(m[0x8CDBC])].body.startswith("After the Ghouls departed")
```

- [ ] **Step 2: Rodar os testes e conferir que falham**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL com `ImportError: cannot import name 'extract_script'`.

- [ ] **Step 3: Implementar `ScriptString`, `extract_script()` e `match_script()` em `ygo/tables.py`**

- [ ] **Step 4: Rodar os testes e conferir que passam**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 5: Checkpoint**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS.

---

### Task 5: Build, aplicação do patch e verificação

**Files:**
- Create: `ygo/build.py`
- Create: `tools/build.py`
- Create: `data/manual.json`
- Test: `tests/test_ygo.py`

**Interfaces:**
- Consumes: todas as funções dos Tasks 1–4; `data/manual_descriptions.json`.
- Produces: `@dataclass(frozen=True) Entry(offset: int, size: int, original: bytes, replacement: bytes, source: str, note: str)` e `@dataclass TranslationTable(entries: list[Entry], pointer_updates: dict[int, int], report: dict)`.
- Produces: `build_table(jp: Rom, us: Rom) -> TranslationTable` — monta entradas para nomes, descrições e script; nomes/descrições sem fonte usam `data/manual.json`; quando uma string de script não cabe no slot original, grava em `FREE_START`, registra `pointer_updates[pointer_offset] = novo_endereco`.
- Produces: `apply_table(jp: Rom, table: TranslationTable, out_path: Path, ips_path: Path) -> Rom` — grava em cópia, aplica ponteiros, escreve ROM e IPS.
- Produces: `verify(jp: Rom, us: Rom, patched: Rom, table: TranslationTable) -> dict` — checa hashes dos dois originais, tamanho, ponteiros, ausência de japonês nas strings patched e contagem de cartas; retorna relatório serializável.
- CLI: `python3 tools/build.py --jp <rom> --us <rom> --out <patched.gba> --ips <patch.ips> --report <report.json>`.

- [ ] **Step 1: Escrever testes que falham**

```python
def test_end_to_end():
    jp, us = Rom(JP), Rom(US)
    table = build_table(jp, us)
    patched = apply_table(jp, table, OUT, IPS)
    rpt = verify(jp, us, patched, table)
    assert jp.sha256() == EXPECTED_JP_SHA
    assert patched.size == 16777216
    assert rpt["jp_characters_remaining"] == 0
    assert rpt["pointer_updates_valid"] is True
    assert IPS.read_bytes()[:5] == b"PATCH"
    assert len(extract_names(patched, OFFSETS["JP_NAME"], 1115)) == 1115
```

- [ ] **Step 2: Rodar os testes e conferir que falham**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL com `ImportError: cannot import name 'build_table'`.

- [ ] **Step 3: Implementar `ygo/build.py`, `tools/build.py` e `data/manual.json`**

`data/manual.json` começa com as entradas necessárias para cartas e falas sem par na ROM americana; cada entrada registra `{"en": "...", "source": "..."}`.

- [ ] **Step 4: Rodar os testes e conferir que passam**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 5: Rodar o build completo e inspecionar o relatório**

Run: `python3 tools/build.py --jp 'Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba' --us 'Yu-Gi-Oh! - Worldwide Edition - Stairway to the Destined Duel (USA) (En,Ja,Fr,De,Es,It).gba' --out dm6-en.gba --ips dm6-en.ips --report translation-report.json`
Expected: saída `dm6-en.gba` com 16777216 bytes, `dm6-en.ips` começando com `PATCH`, e `translation-report.json` com `jp_characters_remaining: 0` e `pointer_updates_valid: true`.

- [ ] **Step 6: Checkpoint**

Run: `python3 -m unittest discover -s tests -v && sha256sum 'Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba'`
Expected: PASS; hash do original igual a `6b75a36a...`.

---

### Task 6: Inspeção visual no emulador

**Files:** nenhum (artefatos: `dm6-en.gba`, `dm6-en.ips`, `translation-report.json`)

**Interfaces:**
- Consumes: `dm6-en.gba` do Task 5.
- Produces: confirmação observada de que menu, pelo menos um diálogo de campanha e pelo menos uma tela de carta aparecem em inglês; limitações registradas no relatório.

- [ ] **Step 1: Abrir a ROM patched no mGBA**

Run: `mgba-qt dm6-en.gba`
Expected: emulador abre sem erro.

- [ ] **Step 2: Observar três telas**

Observar: menu principal, primeiro diálogo com o texto "After the Ghouls departed...", e tela de detalhe da carta `Earthbound Spirit` com nome e descrição em inglês. Anotar qualquer glifo faltante ou texto cortado.

- [ ] **Step 3: Registrar limitações**

Atualizar `translation-report.json` com `visual_check` (observações e telas verificadas). Se a interface gráfica não permitir automação, registrar explicitamente o limite em vez de afirmar verificação automática.
