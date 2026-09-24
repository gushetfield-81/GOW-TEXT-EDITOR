# God of War Text Editor — 2026-09-24 R8

> **Status:** publicado no GitHub em 2026-09-24 como
> [`v2026.09.24-r8`](https://github.com/gushetfield-81/GOW-TEXT-EDITOR/releases/tag/v2026.09.24-r8).
> Nenhum WAD de entrada faz parte do asset.

## O que a R8 corrige

A R7 já mostrava as cores físicas base de DynamicLabels/StaticLabels no próprio
texto. Ela ainda não interpretava a camada de estilo do runtime Flash expressa
no `MSGS_TXT` por controles como `[*1]`.

A R8 completa essa camada para o `R_PERMA`/`MSGS_TXT` analisado:

- `[*]` e `[*0]` retornam à cor física base da linha;
- `[*1]`…`[*4]` aplicam as cores reais `FlashMsg1Color`…`FlashMsg4Color` de
  `GBL_Global` aos glifos posteriores **na mesma linha**;
- o controle continua literal, visível e editável no campo **TEXTO DA
  MENSAGEM**; não há HTML/rich text no WAD;
- o caso da mensagem 701, `[*1] [IconBlade] LÂMINAS DE ATENA`, passa a mostrar
  o título com o RGB runtime `#7F2805`, em vez de branco;
- a prévia CRT projeta a mesma camada e esconde somente o token de controle;
  macros de ícone continuam referência textual, sem sprite inventado.

## Fluxo de edição novo

No cabeçalho do próprio editor há a barra **COR INLINE**:

1. escolha a cor base (`[*0] / [*]`) ou `[*1]` a `[*4]`;
2. sem seleção, **Inserir [*N]** coloca o token no cursor;
3. com cursor dentro de um token, o botão troca apenas aquele token;
4. com seleção, envolve o conteúdo e preserva `[Icon…]`/outros controles;
   uma seleção com várias linhas recebe um par por linha, porque o runtime
   reinicia `style = 0` em cada `MessageTemplate_LineN`;
5. **Editar RGB runtime…** altera a cor escolhida sem abandonar a mensagem.

O seletor mostra a cor extraída do WAD atual. Para `R_PERMA.WAD.txt`, a tabela
validada é:

| Token | Campo | RGB |
|---|---|---|
| `[*1]` | `FlashMsg1Color` | `#7F2805` |
| `[*2]` | `FlashMsg2Color` | `#AA5914` |
| `[*3]` | `FlashMsg3Color` | `#666666` |
| `[*4]` | `FlashMsg4Color` | `#6699CC` |

A edição altera somente os três floats RGB do campo selecionado dentro de
`GBL_Global`; alfa, tamanho do Data Context, Export table, TXT e outras tags
permanecem intactos. Estilos 5–6 são apenas lidos para diagnóstico: o renderer
comprovado constrói os estilos 1–4, portanto a R8 não oferece controles sem
base de runtime.

## Segurança e limites

- Os WADs anexados foram usados apenas para leitura/teste.
- O WAD só é gravado por **Salvar WAD como…**. Use uma cópia e teste-a no jogo.
- `R_SHELLA.WAD.txt` não contém `MSGS_TXT`, Data Context ou `GBL_Global`:
  continua com as cores FLP físicas da R7, mas não recebe uma edição inline
  fictícia.
- `[*N]` é uma camada de texto Flash; não substitui as cores físicas de
  `DynamicLabel`, `StaticLabel` ou animações `BlendColor` que a R7 mantém.
- A mini-prévia não simula sprites de tokens `[Icon…]`.

## Fundamentação

A implementação foi confrontada com o código fornecido do `god_of_war_browser`
para as estruturas FLP e com o runtime descompilado:

- `FlashInterface::DoMsgPage` atribui cada linha às variáveis
  `MessageTemplate_LineN`;
- `EditTextBuild` inicia estilo 0 por chamada, interpreta `[*N]` sem criar
  glifo e entrega o estilo a cada `TextItem`;
- `EditTextRender` usa as matrizes de mensagem;
- `renFlashServer::SetMsgParameters` converte os floats RGB de `GBL_Global`
  para bytes de cor;
- a tabela Export/Data IFF localiza `GBL_Global` sem uma busca frágil por
  string.

Veja [`RELATORIO_CORES_INLINE_RUNTIME_R8.md`](../RELATORIO_CORES_INLINE_RUNTIME_R8.md)
para offsets, semântica de linha e evidência detalhada.

## Validação

- `python3 -m py_compile` da fonte R8: aprovado.
- Regressão de entrega: **24/24 testes aprovados** (núcleo GoW1/GoW2,
  preservação de FLP/R6 e as regressões R8), com Qt/PySide6 `offscreen`.
- Regressão de núcleo R8: extração de paleta, `[*0]`, limites por linha,
  `[*1]`/`[*2]`/`[*4]`, preservação de macros, seleção multilinha, round-trip
  raw de `MSGS_TXT` e patch RGB de 12 bytes: aprovado.
- Smoke Qt/PySide6 `offscreen`: abriu `R_PERMA`, validou formatos efetivos de
  glifo em `QPlainTextEdit`, a prévia CRT, cursor/troca/inserção/wrap e o
  diálogo RGB; também confirmou que a camada física R7 de `MSGS_TXT` e
  `StaticLabel` continua ativa.
- `R_PERMA.WAD.txt` e `R_SHELLA.WAD.txt`: hashes preservados após os testes.
- O ZIP final é testado com `unzip -t`; não contém `.ini`, logs, backups ou
  `__pycache__`.

## Asset

- `GodOfWarTextEditor_Aprimorado_2026-09-24_R8_EXE.zip`
- Tamanho: **33.621.831 bytes**
- SHA-256: `532e58486d233bffd8df0bfb595166d74aa3a933abac63367798e7fa4b4bb8c9`
- `unzip -t` e `py_compile` da fonte extraída: aprovados. O asset traz o
  launcher Windows, `app\\` portátil com Python/PySide6 e não contém `.ini`,
  logs, backups ou `__pycache__`.

## Créditos

Tool By: Gus Hetfield  
Special Thanks: Mogaika
