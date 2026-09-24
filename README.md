# God of War Text Editor — Projeto de Tradução PT-BR (GoW I / GoW II)

Arquivo oficial de tudo que foi produzido nas sessões de trabalho com o agente
(Arena.ai): a **tool**, os **patchers** de dados do jogo, os **WADs traduzidos
entregues**, a **documentação viva de contexto** e as **prévias visuais**.

Além do fluxo de mensagens do GoW II, a tool reconhece textos de menu do
**GoW I** gravados como StaticLabels em filmes FLP, como `FLP_Shell` dentro de
`R_SHELL.WAD` e `FLP_HUD` em WADs que também carregam recursos TXT. Ela também
exporta/importa o payload binário bruto de um FLP selecionado, com validação
estrutural e bloqueio de troca entre formatos GoW1 e GoW2. Na R5, FLPs GoW2
recebem edição cirúrgica das três camadas de cor de texto: DynamicLabel,
RenderCommand de StaticLabel e BlendColors/KeyFrames. Na R7, as cores base
fisicamente associadas são pintadas nos próprios glifos do editor, inclusive
no vínculo real `MSGS_TXT → MessageTemplate_LineN`. A R8 acrescenta a camada
real de estilo do runtime Flash: controles `[*1]`…`[*4]` de `MSGS_TXT` são
renderizados no próprio texto e editam os RGB físicos `FlashMsgNColor` de
`GBL_Global`, sem transformar o recurso em HTML.

> **Tool By: Gus Hetfield** | **Special Thanks: Mogaika**

---

## 📁 Estrutura

```
god-of-war-text-editor/
├── CONTEXTO_MESTRE_GOW_TEXT_EDITOR.md   ← documentação viva (formatos binários,
│                                           decisões, regras, histórico — LEIA PRIMEIRO)
├── tool/
│   ├── GodOfWarTextEditor_Aprimorado_2026-09-24_R8/ ← código-fonte da tool (PySide6)
│   │   ├── gow_text_editor.py                        editor WAD/MSGS/FLP + cores WYSIWYG/runtime inline
│   │   ├── GodOfWarTextEditor.exe                    launcher Windows
│   │   └── GODOFWAR.TTF, LEIA-ME.txt, icone/, imagens_de_fundo/
│   ├── GodOfWarTextEditor_Aprimorado_2026-09-24_R8_EXE.zip ← pacote portátil atual
│   └── GodOfWarTextEditor_Aprimorado_2026-09-22_R2_EXE.zip ← histórico preservado
│       (os ZIPs locais R3/R4/R5 foram removidos para liberar espaço; R3 segue
│        disponível na release GitHub e R8 substitui localmente as revisões anteriores)
├── patchers/                            ← scripts que alteram dados do jogo
│   ├── shell_americano/adicionar_acentos_shell.py    (ã Ã õ Õ no R_SHELLA — EUA)
│   ├── shell_europeu/adicionar_acentos_shellu.py     (ã Ã õ Õ no R_SHELLU — Europa)
│   └── playtime/patch_total_playtime.py              (patch de playtime do R_PERMA)
├── entregas/                            ← LEIA-MEs + prévias de cada entrega
│                                           (os WADs ficam em cópia privada)
│   ├── shell_americano/  LEIA-ME_SHELL.txt                        (✔ testado em jogo)
│   ├── shell_europeu/    LEIA-ME_SHELLU.txt                       (⏳ aguarda teste)
│   ├── plocu/            LEIA-ME_PLOCU.txt                        (✔ testado em jogo)
│   └── playtime/         LEIA-ME_PLAYTIME.txt
└── previews/                            ← renders de conferência das fontes
```

## ⬇️ Downloads da tool

| O quê | Onde |
|---|---|
| **Código Python R8** (`gow_text_editor.py`) | [`tool/GodOfWarTextEditor_Aprimorado_2026-09-24_R8/`](tool/GodOfWarTextEditor_Aprimorado_2026-09-24_R8/gow_text_editor.py) — requer Python 3.10+ e `pip install PySide6` |
| **Pacote R8 publicado — 2026-09-24** | [`tool/GodOfWarTextEditor_Aprimorado_2026-09-24_R8_EXE.zip`](tool/GodOfWarTextEditor_Aprimorado_2026-09-24_R8_EXE.zip) — ZIP portátil com cores WYSIWYG físicas e controles inline reais `[*N]` de MSGS_TXT |
| **Release R8 publicada — 2026-09-24** | [`v2026.09.24-r8`](https://github.com/gushetfield-81/GOW-TEXT-EDITOR/releases/tag/v2026.09.24-r8) — fonte, testes, documentação e ZIP portátil publicados; nenhum WAD de entrada foi enviado. R7 continua como referência histórica. |
| **Release R7 publicada — 2026-09-24** | [`v2026.09.24-r7`](https://github.com/gushetfield-81/GOW-TEXT-EDITOR/releases/tag/v2026.09.24-r7) — cores físicas WYSIWYG de StaticLabel/MSGS_TXT. |

> **Nota de validação:** a R8 preserva os fluxos TXT/FLP, `FLP_Shell`, labels
> multilinha, transferência de FLP bruto e a camada física WYSIWYG da R7. Em
> `MSGS_TXT`, ela também interpreta `[*]`, `[*0]` e `[*1]`…`[*4]` com os RGB
> reais de `GBL_Global`, limitados à mesma `MessageTemplate_LineN` que o runtime
> constrói. O texto continua puro/serializável e BlendColors continuam animações,
> não uma aparência inventada. Antes de distribuir um **WAD editado**, ainda é
> recomendado testá-lo no PCSX2 ou console.

## 🚀 Instalação rápida (cada patch)

1. **Backup** do WAD original na pasta do jogo.
2. Renomeie o WAD da entrega (ex.: `R_SHELLU_PTBR.WAD` → `R_SHELLU.WAD`).
3. Copie por cima do original. Para os slots europeus, selecione
   **inglês britânico** no menu de idiomas do jogo.
4. Detalhes e SHA-256 completos no `LEIA-ME` de cada pasta de entrega.

## 🧬 Integridade

O launcher e o código versionados aqui:

| Arquivo | Tamanho (B) | SHA-256 |
|---|---|---|
| `tool/…/GodOfWarTextEditor.exe` (launcher x64) | 179.712 | `7c43368fd54d101fa0d3400d63dc8ac122782f2702f2e2248156497858dde950` |
| `tool/…/R8/gow_text_editor.py` | 314.897 | `177bdcd16437a7c4649cd26ad52dc9e898822cbe9518ed0568e92395fa1173fb` |
| `tool/…/R8/LEIA-ME.txt` | 22.006 | `1ca6086a20191843b1a0aca78815b66da475854ef1140c595cce136e39b8db95` |
| `tool/GodOfWarTextEditor_Aprimorado_2026-09-24_R8_EXE.zip` | 33.621.831 | `532e58486d233bffd8df0bfb595166d74aa3a933abac63367798e7fa4b4bb8c9` |
| `tool/GodOfWarTextEditor_Aprimorado_2026-09-24_R7_EXE.zip` (histórico) | 33.615.425 | `88c1ef57acda7b5bd013e03581d179deaa09f9468e04663ac3726a794edce7aa` |
| `tool/GodOfWarTextEditor_Aprimorado_2026-09-22_R2_EXE.zip` (histórico) | 33.596.031 | `cdb7dd3d3f4d09ab913347528f5ba88d69e1e77ddda77655b2734ad513c674bd` |

**Não incluídos neste repositório** (por direitos autorais do jogo e/ou limite
de 25 MB/arquivo do upload web do GitHub):

- os 4 WADs traduzidos (`R_SHELLA_PTBR`, `R_SHELLU_PTBR`, `R_PLOCU_PTBR`,
  `R_PERMA_TTJ`) — tamanho e SHA-256 completos de cada um estão nos LEIA-MEs
  de `entregas/`, para conferência das cópias privadas;
- *(o pacote .EXE passou a ser distribuído no próprio repositório e na aba Releases)*

## 📜 Histórico de versões

| Data | Marco | Resultado |
|---|---|---|
| 2026-09-12 | Tool "Aprimorado" | editor Qt completo: WAD round-trip byte-exato, MSGS_TXT em UTF-8 (runtime GoW2), FLP GoW2 de rótulos estáticos, Mesh/GFX p/ fontes |
| Sessões 1–5 | Playtime + legendas | R_PERMA_TTJ.WAD (playtime) e legendas do PERMA — ✔ confirmados em jogo |
| Sessão 6 | Acentos do shell EUA | ã Ã õ Õ no R_SHELLA via tiles do PERMA — ✔ confirmado em jogo |
| Sessão 7 | Editor de rótulos FLP | larguras derivadas do rótulo original; entrega via ZIP reconstruído |
| Sessão 8 | PLOCU europeu | merge por ID (ordem/conjunto do EU + corpos traduzidos) — ✔ "Funcionou perfeitamente" |
| Sessão 9 | Acentos do shell EUROPA | ã Ã õ Õ no R_SHELLU por **células-vítima** (ñ/Ä/ö/Ö cedem espaço) — ⏳ aguarda teste no PCSX2 |
| Sessão 10 (2026-09-22) | Shell do GoW I | leitura/edição inicial de rótulos estáticos `FLP_Shell` do `R_SHELL.WAD` (não há TXT nesse shell); multilinha foi ampliado na Sessão 13 |
| Sessão 11 (2026-09-22) | FLP direto na tela principal | WADs sem TXT exibem `FLP_Shell` e seus rótulos na lista principal, sem exigir o menu Ferramentas |
| Sessão 12 (2026-09-22) | Pacote Windows atualizado | ZIP portátil x64 com EXE launcher, Python/PySide6 embutidos e a versão de tela principal para `FLP_Shell` |
| Sessão 13 (2026-09-22) | Labels multilinha editáveis | Cada bloco/linha mantém sua âncora; a UI exige preservar o número original de linhas e deixa os 120 labels do `R_SHELL` editáveis |
| Sessão 14 (2026-09-22) | TXT + FLP na mesma lista | `R_PERM`/`R_PERMA` passam a exibir TXT e `FLP_HUD` juntos na tela principal; alternar TXT → FLP → TXT preserva os índices reais e a edição segura |
| Sessão 17 (2026-09-23) | FLP bruto selecionado | `Exportar FLP…` grava o payload cru; `Importar FLP…` valida e troca apenas a tag ativa, preservando nome/flags e bloqueando GoW1 ↔ GoW2 |
| Sessão 18 (2026-09-24) | Cores de texto FLP GoW2 — R5 | `Ferramentas → Cores de texto do FLP…` separa cor base DynamicLabel, cor direta StaticLabel e tintas BlendColors/KeyFrames; mostra escopo/rótulos atingidos e atualiza apenas 4/8 bytes do campo escolhido |
| Sessão 19 (2026-09-24) | Cores durante a edição — R6 | Painel inline relaciona StaticLabel ao seu RenderCommand/BlendColors e `MSGS_TXT` ao `MessageTemplate_LineN` sob o cursor; cores editáveis sem abandonar o texto ativo |
| Sessão 20 (2026-09-24) | Cores WYSIWYG durante a edição — R7 | Substitui a interação de tabela: glifos do editor recebem a cor base física; seletor/botão ficam no cabeçalho da própria caixa; preserva campos diretos e trata BlendColors apenas como animações |
| Sessão 21 (2026-09-24) | Cores inline reais `MSGS_TXT` — R8 | `[*]`/`[*0]` e `[*1]`…`[*4]` passam a renderizar no editor/prévia com `FlashMsgNColor` extraído de `GBL_Global`; inserção/troca/wrap e patch RGB de 12 bytes respeitam o reset por `MessageTemplate_LineN` |

## ⚠️ Nota importante

Os `.WAD` do jogo (originais e traduzidos) contêm **assets com direitos
autorais** (Sony/Santa Monica) e por isso **não são distribuídos aqui** —
ficam apenas em cópia privada com o autor do projeto. Os patchers desta
ferramenta precisam dos WADs originais do usuário para regenerar as entregas.

## 🔧 Requisitos da tool

- Python 3.10+ com **PySide6** (`pip install PySide6`)
- Rodar: `python gow_text_editor.py` (ou o `.exe` da pasta)
- Encoding de `MSGS_TXT`: **UTF-8 (runtime GoW2)** — já padrão da tool

## 🏛️ GoW I — textos do `R_SHELL.WAD`

O shell do GoW I **não possui arquivos `.TXT`** para os menus. Conforme o
formato lido pelo `god_of_war_browser`, os textos estão desenhados dentro de
`FLP_Shell` como listas de glifos (StaticLabels). Basta abrir o WAD: quando
não houver TXT, a tela principal passa a mostrar **FLP_Shell** no painel da
esquerda e seus rótulos diretamente na coluna central. A tool identifica
`FLP_Shell • GoW1`, exibe os rótulos PT-BR com acentos CP1252 e permite editar
rótulos de uma **ou várias linhas** pelo botão **Aplicar rótulo**. Em labels
multilinha, mantenha exatamente o mesmo número de linhas indicado na lista:
cada linha é escrita no seu próprio bloco, conservando posição, escala, cor e
âncora originais.

## 🧩 TXT + FLP em `R_PERM` / `R_PERMA`

Alguns WADs carregam mensagens convencionais e rótulos desenhados ao mesmo
tempo. Na R3, os TXT permanecem no topo do painel esquerdo e cada FLP
compatível — por exemplo **`FLP_HUD`** — é acrescentado abaixo deles. Ao
selecionar um FLP, a coluna **Mensagens** passa a listar seus StaticLabels e o
editor à direita aplica a mesma proteção de fontes, glifos e linhas. Ao voltar
para um TXT, o fluxo normal de mensagens retorna sem perder o mapeamento do
recurso. O menu **Ferramentas → Rótulos desenhados** continua disponível como
acesso avançado, mas não é necessário para abrir esses FLPs.

A substituição em lote é mantida deliberadamente só para TXT: um FLP exige a
validação individual de glifos e da quantidade de blocos para não romper o
layout do jogo.

## 💾 Importar e exportar `.flp` bruto

Com um filme FLP selecionado no painel esquerdo, as ações **Arquivo → Exportar
FLP…** e **Importar FLP…** trabalham sobre o filme binário completo:

- A exportação cria um `.flp` cujo primeiro dword é o magic do filme; ela não
  inclui o header de 0x20 bytes da tag WAD.
- A importação aponta **somente para o FLP que está selecionado**. Ela preserva
  nome, tipo e flags da tag no WAD; apenas substitui o corpo e atualiza o tamanho
  quando o WAD for salvo.
- O arquivo é analisado antes da confirmação. GoW I (`magic 0x21`, header `0x60`)
  só aceita outro FLP GoW I; GoW II (`magic 0x1B`, header `0x5C`) só aceita GoW II.
- Filmes sem StaticLabels também podem ser listados para esse fluxo binário.
  A tool não transfere junto os `MDL_*`, materiais, fontes ou texturas dos quais
  o FLP importado possa depender.

A validação segue os handlers e layouts de `pack/wad/flp/flp.go` e `parser.go`
do **god_of_war_browser** fornecido pelo usuário. Sempre salve em uma cópia do
WAD e teste no jogo antes de distribuir.


## 🎨 Cores de texto de FLP GoW2 — R5

No FLP GoW2, a aparência de um texto pode resultar de camadas diferentes. A R5
não tenta alterar uma “cor global” genérica: com um FLP GoW2 selecionado,
**Ferramentas → Cores de texto do FLP…** oferece três listas explícitas:

- **DynamicLabels:** a cor base do campo `F_EditText` usado pelo runtime; a UI
  identifica o nome/variável do jogo e converte o layout físico BGRA para RGBA.
- **StaticLabels:** o `BlendColor` RGB+A de cada RenderCommand que contém cor
  própria, indicando bloco/texto que a herda.
- **BlendColors/KeyFrames:** tintas RGBA 16-bit na escala 0..256; cada entrada
  informa o número de referências e os labels de texto alcançáveis na árvore de
  animação. É importante para títulos, fades e efeitos de seleção.

A janela mostra cor atual, nova cor e alfa antes de aplicar. O patch é de
comprimento fixo, reabre o FLP para validação e modifica somente o campo
selecionado — nunca reserializa fontes, modelos, materiais ou outros recursos.
A alteração permanece em memória até **Salvar WAD como…**. Veja o inventário e
a evidência de formato em [`RELATORIO_ANALISE_CORES_FLP_GOW2.md`](RELATORIO_ANALISE_CORES_FLP_GOW2.md).


## 🖍️ Cores WYSIWYG dentro do texto em edição — R7

A R7 substitui a tabela externa R6 como fluxo principal: a caixa **TEXTO DA
MENSAGEM** pinta os próprios glifos na cor base física associada, sem transformar
o conteúdo em rich text. O texto permanece editável normalmente e a
serialização ainda recebe somente `toPlainText()`.

- **StaticLabels FLP GoW2:** cada bloco recebe exclusivamente a cor direta do
  seu `RenderCommand`. No cabeçalho do editor, **COR BASE** e o botão RGBA
  permitem editar o campo daquele bloco sem sair do rótulo.
- **`MSGS_TXT`:** a linha/página sob o cursor é ligada ao
  `PS2_MessageTemplate_LineN` comprovado pelo runtime. Todas as instâncias
  físicas/estados de DynamicLabel permanecem selecionáveis; trocar a instância
  redesenha a linha ativa e editar altera somente os seus quatro bytes BGRA.
  Linhas vazias, `--` e TXT sem vínculo comprovado não recebem uma cor falsa.
- **BlendColors:** são animações/KeyFrames. A interface exibe a cor base e a
  quantidade de animações associadas, mas não inventa uma aparência estática.
  A inspeção avançada continua em **Ferramentas → Cores de texto do FLP…**.
- **Segurança:** `QSyntaxHighlighter` faz apenas a pintura visual e bloqueia o
  sinal de formatação que poderia recursar por `textChanged`. Patch de
  DynamicLabel/StaticLabel continua limitado a 4 bytes; o WAD só é escrito em
  **Salvar WAD como…**.

A regressão R7 validou cor efetivamente aplicada aos formatos de glifo,
reinício de página em `--`, `Line1 → Line2`, instâncias `{2, 37}`, patch
cirúrgico de DynamicLabel e StaticLabel, texto preservado e hashes das entradas
imutáveis. A suíte completa com Qt offscreen passou **18/18** testes. Consulte
[`tool/RELEASE_NOTES_2026-09-24_R7.md`](tool/RELEASE_NOTES_2026-09-24_R7.md)
e [`RELATORIO_INTERACAO_CORES_TEXTO_R7.md`](RELATORIO_INTERACAO_CORES_TEXTO_R7.md).

## 🎨 Cores inline reais de `MSGS_TXT` — R8

A R8 resolve a camada que a R7 não podia mostrar só pelas cores físicas do
FLP: comandos Flash literais `[*N]` dentro do próprio `MSGS_TXT`.

- **`[*]` e `[*0]`:** retornam à cor base física da linha.
- **`[*1]`…`[*4]`:** aplicam os RGB reais de
  `GBL_Global.FlashMsg1Color`…`FlashMsg4Color` aos glifos posteriores da
  **mesma** linha. No `R_PERMA` validado, são `#7F2805`, `#AA5914`,
  `#666666` e `#6699CC`.
- **Linha é uma fronteira real:** `DoMsgPage` entrega texto a
  `MessageTemplate_LineN`, e cada chamada de `EditTextBuild` reinicia o estilo
  em zero. A R8 não deixa a cor atravessar Enter/`--`; seleção multilinha
  recebe um par de marcadores por linha.
- **WYSIWYG sem rich text:** o `QSyntaxHighlighter` colore somente os formatos
  visuais. `[*N]`, `[Icon…]` e o texto continuam bytes serializáveis; a
  mensagem 701 passa a exibir `LÂMINAS DE ATENA` na cor `#7F2805`.
- **Edição no mesmo painel:** a barra **COR INLINE** insere, troca ou envolve
  controles; **Editar RGB runtime…** toca exclusivamente os três `float`s RGB
  do `FlashMsgNColor` selecionado no Data Context (`GBL_Global`). Alfa e todos
  os bytes fora da janela de 12 bytes são preservados.
- **R_SHELLA:** sem `MSGS_TXT`/`GBL_Global`, não recebe paleta fictícia; a
  edição de cores FLP existente permanece disponível.

A regressão R8 valida o Data/Export IFF, os estilos observados, reset por
linha, serialização raw, round-trip, localização binária do patch e Qt
`offscreen` (editor + prévia + cursor + RGB). Consulte
[`RELATORIO_CORES_INLINE_RUNTIME_R8.md`](RELATORIO_CORES_INLINE_RUNTIME_R8.md)
e [`tool/RELEASE_NOTES_2026-09-24_R8.md`](tool/RELEASE_NOTES_2026-09-24_R8.md).
