# Editor de Traduções DM6 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** entregar um editor desktop local para editar/validar as traduções e gerar ROM/IPS, e deixar o repositório limpo para envio ao GitHub sem artefatos de IA.

**Architecture:** módulo de núcleo com funções puras para carregar, validar e salvar os JSONs de tradução; interface GTK 3 fina sobre esse núcleo; limpeza do repositório remove documentos de IA do índice e adiciona README.

**Tech Stack:** Python 3 (stdlib + `gi`/GTK 3 já instalado), `unittest`, pipeline existente `tools/build.py`.

**Spec:** `docs/editor-design.md`

## Global Constraints

- Não modificar as ROMs originais; saída sempre via `tools/build.py`.
- Nenhum artefato de IA no repositório final: `.superpowers/` e `docs/superpowers/` fora do índice.
- Sem dependências novas fora as já presentes (`gi`/GTK 3).
- Testes com `python3 -m unittest discover -s tests -v`.
- Idioma da interface: português.

## Review Focus

- Tokens de controle (`$...`, `@N`, `%s`) não podem ser perdidos ao editar → teste no núcleo.
- Nomes/descrições não podem estourar o slot (63/383 bytes cp932) → teste no núcleo.
- Salvar não pode corromper JSON nem apagar entradas existentes → teste de roundtrip.
- Repo final não pode conter `superpowers` em nenhum caminho rastreado → verificação com `git ls-files`.

---

### Task 1: Núcleo do editor

**Files:**
- Create: `tools/editor_core.py`
- Test: `tests/test_editor.py`

**Interfaces:**
- `load_translations(path: Path) -> dict` — carrega `data/manual.json`.
- `load_overrides(path: Path) -> dict` — carrega `data/manual_descriptions.json`.
- `save_translations(data: dict, path: Path) -> None` — grava com `ensure_ascii=False`, indent 2 e backup `.bak`.
- `validate_entry(original: str, edited: str, *, limit: int) -> list[str]` — retorna lista de problemas (strings vazias descritivas).
- `TOKEN_RE` — regex compartilhada com `ygo.text._MARKUP_RE`.

- [ ] **Step 1: escrever testes que falham**

```python
def test_validate_preserves_tokens():
    assert validate_entry("$t1Olá $nMundo", "$t1Hello $nWorld", limit=63) == []

def test_validate_rejects_lost_token():
    problems = validate_entry("$t1Olá $nMundo", "Hello World", limit=63)
    assert any("token" in p for p in problems)

def test_validate_rejects_overflow():
    problems = validate_entry("x", "Ａ" * 40, limit=63)
    assert any("63" in p for p in problems)
```

- [ ] **Step 2: rodar e confirmar falha por módulo ausente**

Run: `python3 -m unittest tests.test_editor -v`
Expected: FAIL com `ModuleNotFoundError: tools.editor_core`.

- [ ] **Step 3: implementar `tools/editor_core.py`**

- [ ] **Step 4: rodar testes e confirmar passagem**

Run: `python3 -m unittest tests.test_editor -v`
Expected: PASS.

- [ ] **Step 5: commit**

### Task 2: Interface GTK 3

**Files:**
- Create: `tools/editor.py`
- Modify: `tools/editor_core.py` (se necessário)

**Interfaces:**
- Consumes: funções do Task 1 e `tools/build.py`.
- Produces: comando `python3 tools/editor.py` abre a janela.

- [ ] **Step 1: implementar janela com abas Nomes/Descrições/Falas/UI/Overrides**

Cada aba: `Gtk.TreeView` com índice + texto atual, campo de busca, `Gtk.TextView` para edição e botões Salvar/Recarregar.

- [ ] **Step 2: validar antes de salvar**

Ao editar, chamar `validate_entry`; mostrar problemas numa barra de status e bloquear salvamento se houver erro.

- [ ] **Step 3: botão "Gerar ROM/IPS"**

Chamar `subprocess.run([sys.executable, "tools/build.py", ...])` com caminhos configuráveis (padrão: ROMs no diretório atual); mostrar saída numa janela de log.

- [ ] **Step 4: verificação visual**

Run: `DISPLAY=:1 python3 tools/editor.py`
Expected: janela abre, abas carregam dados reais, edição de teste salva e recarrega.

- [ ] **Step 5: commit**

### Task 3: Limpeza e documentação do repositório

**Files:**
- Remove: `docs/superpowers/plans/2026-11-22-dm6-english-translation.md`
- Remove: `docs/superpowers/specs/2026-11-22-dm6-english-translation-design.md`
- Modify: `.gitignore`
- Create: `README.md`
- Modify: `CHANGELOG.md` (criar se ausente)

- [ ] **Step 1: remover documentos de IA do índice**

Run: `git rm --cached docs/superpowers/plans/... docs/superpowers/specs/...`
Expected: arquivos deixam de ser rastreados; `.superpowers/` já ignorado.

- [ ] **Step 2: escrever README curto**

Conteúdo: o que é o projeto, como gerar ROM/IPS (`python3 tools/build.py ...`), como usar o editor, estrutura de `data/`, aviso de uso pessoal das ROMs.

- [ ] **Step 3: escrever CHANGELOG inicial**

`## [0.1.0]` com Added/Changed/Fixed resumindo a tradução e o editor.

- [ ] **Step 4: verificar repo limpo**

Run: `git ls-files | grep -i superpowers`
Expected: nenhuma saída.

- [ ] **Step 5: commit**

### Task 4: Verificação final

- [ ] **Step 1: suíte completa**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 2: build final**

Run: `python3 tools/build.py ...`
Expected: ROM 16 MiB, IPS com `PATCH`, japonês 0.

- [ ] **Step 3: inspeção do editor**

Run: `DISPLAY=:1 python3 tools/editor.py`
Expected: abre, edita, salva, gera ROM/IPS.
