# Editor de traduções DM6 Expert 2 — design curto

## Objetivo

Ferramenta local para editar as traduções do projeto sem mexer diretamente em JSON, validar o texto antes de salvar e gerar ROM/IPS atualizados. Depois, preparar o repositório para envio ao GitHub sem artefatos de IA.

## Abordagens

- **A — Editor desktop local (escolhida).** Abre `data/manual.json` e `data/manual_descriptions.json`, permite filtrar/editar entradas, valida limites e códigos de controle, salva e dispara o build. Funciona offline e reaproveita o pipeline Python atual.
- **B — Editor web.** Melhor colaboração remota, mas exige frontend, hospedagem e bem mais código; não é necessário agora.
- **C — Script CLI.** Barato, mas não resolve a edição confortável pedida.

Tkinter não está utilizável nesta máquina (`libtk8.6.so` ausente). GTK 3 via PyGObject (`gi`) está disponível, então a implementação será GTK 3 local — continua sendo desktop, sem dependências novas a instalar.

## O que a ferramenta faz

- Abas: nomes, descrições, falas de script, UI, overrides de descrição.
- Busca pelo original japonês, pelo índice/offset ou pelo texto em inglês.
- Edição do texto mantendo os códigos de controle (`$...`, `@N`, `%s`/`%d`).
- Validação antes de salvar: sem japonês solto, tokens preservados em relação ao original, tamanho em bytes cp932 dentro do limite do slot (nomes 63, descrições 383; falas/UI têm limite informativo).
- Botões: salvar JSON (com backup), recarregar, e "gerar ROM/IPS" chamando `tools/build.py` com os caminhos das duas ROMs.
- Nenhum artefato de IA é lido ou escrito pela ferramenta.

## Não-objetivos

- Traduzir automaticamente; a ferramenta só edita e valida.
- Publicar no GitHub automaticamente (sem `gh`/credencial configurada, e o link retorna 404).
- Incluir `docs/superpowers/`, `.superpowers/` ou qualquer documento de IA no commit final.

## Preparação do repositório

- Remover do índice `docs/superpowers/plans/*` e `docs/superpowers/specs/*`.
- Manter `.gitignore` com `.superpowers/`, ROMs, IPS e artefatos gerados.
- Adicionar `README.md` explicando build, editor e o uso do IPS.
- Deixar commits limpos e prontos; o push depende de o usuário criar o repositório remoto e configurar credencial.

## Verificação

- Testes unitários para as funções de validação e carregamento/salvamento dos JSON.
- Abrir a janela no ambiente X11 disponível (`DISPLAY=:1`) e conferir que carrega as abas e salva uma edição de teste.
