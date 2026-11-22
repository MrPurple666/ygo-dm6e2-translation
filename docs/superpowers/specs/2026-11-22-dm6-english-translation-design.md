# DM6 Expert 2 (JP) — tradução para inglês via Worldwide Edition

Data: 2026-11-22

## Intenção

Produzir uma ROM jogável em inglês a partir de `Yu-Gi-Oh! Duel Monsters 6 Expert 2 (Japan).gba`, mantendo a base japonesa e, portanto, o elenco completo de cartas. A Konami nunca localizou este título; a `Worldwide Edition` americana usa o mesmo motor e quase todo o mesmo texto, mas com menos cartas. O usuário escolheu inglês como idioma final e a abordagem A (patch da ROM japonesa).

## Objetivos

- Traduzir para inglês todo o texto visível ao jogador: menus, diálogos da campanha, nomes e descrições de cartas, nomes de boosters, senhas e textos de ajuda. Meta: nenhum caractere japonês restante em texto de jogo; sobras, se houver, são listadas como limitação.
- Manter as 1115 entradas de cartas da ROM japonesa, com seus dados, artes e conteúdo exclusivo.
- Entregar uma ROM patched sem sobrescrever os originais, mais um script reproduzível e uma tabela de tradução revisável (JSON/CSV) com origem de cada string.
- Comprovar o resultado com verificações automáticas de codificação/ponteiros e um teste visual em emulador, quando disponível.

## Não-objetivos

- Tradução para português.
- Portar cartas japonesas para dentro da ROM americana.
- Melhorias de jogabilidade de terceiros (senhas infinitas, remoção de mãos injustas, deslocalização de nomes etc.) do projeto do GBAtemp/pixelstories.
- Alterar arte de cartas, estatísticas, efeitos de jogo ou balanço. Ajustes na fonte (tiles de caracteres latinos) são permitidos se necessários para exibir o inglês.

## Restrições observadas

- As duas ROMs têm 16 MiB e usam o mesmo formato de texto: Shift-JIS (cp932) com códigos de controle ASCII como `$n`, `$c`, `$fot`, `$a(...)`, `$g(...)`.
- Tabela de nomes de cartas: 1115 registros de 0x40 bytes na ROM JP a partir de 0x2AA160; 1086 registros de 0x40 bytes na ROM US a partir de 0x385564.
- A ROM americana também contém os nomes em japonês (tabela a partir de 0x8475FC, 1086 registros). Casando o nome japonês, 997 dos 1115 nomes JP encontram correspondência exata; os demais incluem cartas realmente exclusivas e variantes de escrita que precisam de normalização ou tradução manual.
- Texto em inglês é mais longo que o japonês. Registros fixos podem não comportar a versão inglesa; é obrigatório realocar e repontear ou, se necessário, criar tabela indireta/patchar código. Texto de efeito é regra do jogo: não pode ser abreviado com perda de sentido.
- A ROM americana contém vários idiomas; é obrigatório selecionar as variantes em inglês, não as de japonês/francês/espanhol/italiano/alemão.
- ROMs são material protegido; uso pessoal dos arquivos fornecidos. Não publicar ROMs, apenas ferramentas/patch quando aplicável.
- A ROM final continua com exatamente 16 MiB para manter compatibilidade com IPS clássico (offset de 24 bits).

## Abordagens consideradas

- **A — Patch da ROM japonesa (escolhida).** Substituir texto na base JP, usando o nome japonês como chave para copiar nomes/descrições em inglês da Worldwide, e portar diálogos/menus. Preserva todas as cartas e o conteúdo exclusivo; exige tratar strings maiores e traduzir o que não existe na ROM americana.
- **B — ROM americana como base.** Trazer as cartas exclusivas do JP para a ROM US. O texto inglês já existe, mas seria necessário realocar registros de cartas, sprites, efeitos e tabelas de deck, com risco alto de quebrar ponteiros e saves; contraria o pedido de traduzir o jogo japonês.
- **C — Aproveitar patch de terceiros.** Projeto ativo no GBAtemp/pixelstories faz DM6 em inglês, mas até 05/11/2026 estava "em progresso", sem patch publicado; depende de outra pessoa.

## Como será feito (decisões já tomadas)

- Ferramentas em Python puro (biblioteca padrão), neste diretório de trabalho; nenhuma dependência nova.
- Nunca modificar os dois `.gba` originais: ler deles e gravar uma cópia patched.
- Pipeline: extrair strings JP → casar com as strings JP da ROM US → escolher a variante em inglês → gravar tabela de tradução com offset, bytes originais, bytes finais e origem ("portado" ou "manual") → aplicar na cópia da ROM → gerar também um patch IPS.
- Preservar códigos de controle e terminação nula; toda string resultante deve decodificar em cp932/ASCII.
- Se uma string não couber no registro original: realocar para espaço livre e atualizar o ponteiro; se não houver ponteiro identificável, criar indireção ou patchar o código de leitura. Nunca truncar descrição de efeito; nomes só podem ser abreviados se a abreviação preservar a identidade da carta e for registrada na tabela.
- Verificação: asserts sobre tamanho da ROM, integridade dos originais, decodificação de todas as strings alteradas, contagem de cartas inalterada e inspeção visual no mGBA (`mgba-qt` instalado) de pelo menos menu, diálogo e tela de carta.

## Decisões do builder check

- Fidelidade de efeitos: sem perda semântica; overflow resolve com realocação/repontueiro ou patch de código, não com abreviação.
- Definição de pronto: varredura de texto jogável sem caracteres japoneses; resíduos em texto são listados como limitação, não aceitos silenciosamente.
- Formato: ROM de 16 MiB e patch IPS clássico.
- Traduções manuais (sem fonte na ROM americana): usar terminologia oficial TCG/Konami consultada em fontes públicas como Yugipedia, registrar cada escolha na tabela para revisão posterior.
- Texto desenhado em arte (logo/título, rótulos em tiles decorativos) fica fora do escopo e será declarado como limitação; tiles da fonte podem ser ajustados para cobrir caracteres latinos.
- Se o conjunto de glifos da ROM JP não cobrir letras/pontuação do inglês portado, importar os glifos latinos da Worldwide Edition.

## Deixado para o planejamento/implementação

- Estrutura exata das tabelas de descrição de cartas e dos ponteiros de texto (a ser determinada no código, com testes sobre as ROMs fornecidas).
- Normalização dos nomes japoneses que não casaram exatamente.
- Lista final de strings sem fonte em inglês e suas traduções manuais.
- Localização de espaço livre suficiente e estratégia de reponteiro por bloco de texto.
