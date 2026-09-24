# Relatório técnico — interação de cores dentro do editor (R7)

**Data:** 2026-09-24
**Escopo:** substituir a tabela externa R6 pela visualização/edição de cor no
próprio campo `TEXTO DA MENSAGEM`, sem modificar os WADs de entrada.

## Decisão de UI

A implementação usa `QSyntaxHighlighter` (`TextColorHighlighter`) ligado ao
`QPlainTextEdit`. Cada bloco de texto recebe somente um `QTextCharFormat` de
primeiro plano RGBA para exibição. Não há HTML, código de controle ou rich text:

- `editor.toPlainText()` continua retornando os mesmos caracteres;
- rotinas de MSGS e StaticLabel continuam serializando texto puro;
- colorir/recolorir não altera a tag WAD;
- o mapa `linha → RGBA` é normalizado e comparado antes de redesenhar;
- `QSignalBlocker(document)` envolve `rehighlight()`, pois uma mudança de
  formato pode emitir `textChanged` mesmo sem mudança de caracteres. Isso evita
  recursão durante uma edição normal.

O cabeçalho da própria caixa contém **COR BASE**, combo de campo físico,
amostra/botão RGBA e uma dica sobre BlendColors. Assim, escolher uma instância
ou editar sua cor não exige abrir uma tabela inferior nem abandonar o texto.

## Associação usada para StaticLabel GoW2

Para um `StaticLabel` ativo, a R7 percorre
`FLPMovie.static_label_color_fields()` e usa exclusivamente os
`RenderCommand` diretos cujo `label_index` é o rótulo aberto. Os
`affected_blocks` determinam quais blocos/linhas do editor são pintados.

O combo sob o cursor lista somente esses campos diretos. Ao editar, o fluxo
re-resolve o campo no filme atual, consolida primeiro um texto pendente do
StaticLabel e chama `with_static_label_color()`: o diff é limitado aos quatro
bytes RGBA do campo identificado.

## Associação usada para `MSGS_TXT`

A associação não é feita por ID de mensagem. A evidência do runtime permanece:
`DoMsgPage` escreve as linhas da página em `PS2_MessageTemplate_Line1` até
`Line5`.

`_runtime_template_lines_in_editor()` conta linhas não vazias por página,
reiniciando em `--`. Para cada bloco visual, a R7 resolve
`message_template_color_targets()` do FLP GoW2 e pinta a cor direta da primeira
instância disponível como base. A linha sob o cursor preenche o combo com
**todas** as instâncias físicas de `DynamicLabel` daquele `LineN`; escolher uma
instância alternativa redesenha a linha ativa e permite editar somente os seus
quatro bytes BGRA.

Cursor sobre linha vazia/separador retorna `None`; não é criada uma associação
falsa. TXT diferente de `MSGS_TXT` também não recebe vínculo heurístico.

## BlendColors

BlendColors representam valores de animação usados por KeyFrames. Eles não têm
uma aparência estática única que possa ser desenhada honestamente no editor.
Por isso o campo mostra a cor base editável e informa quantas animações chegam
ao texto. O diálogo avançado de cores FLP continua disponível para inspeção e
edição de BlendColors compartilhadas, com seus cuidados próprios.

## Regressão e integridade

`tests/test_inline_colors_ui_r7.py` valida em Qt offscreen:

1. formato de glifo aplicado de fato ao `QPlainTextEdit`;
2. reinício de página em `--`, mudança `Line1 → Line2` e campos físicos
   `{2, 37}`;
3. seleção da instância alternativa e mudança visual na linha ativa;
4. patch de DynamicLabel limitado aos quatro bytes do offset identificado,
   preservando texto puro;
5. StaticLabel `FLP_HUDA` com RenderCommand direto, cor visual e patch de
   quatro bytes;
6. ausência do painel `inline_colors_table` na UI R7.

A suíte completa executada com PySide6/Qt offscreen passou **18/18**. Um smoke
adicional abriu `R_SHELLA.WAD.txt`: `FLP_ShellA` GoW2 exibiu sua cor direta e a
dica de 22 animações associadas. Os hashes das entradas somente-leitura
permaneceram:

- `R_PERMA.WAD.txt`: `fcbecae40d0dcc7ef677f7de37458ea5f1a9a1b0305945e0d38a70ad00f7c42d`
- `R_SHELLA.WAD.txt`: `d97b35d25a834565a1001df8236e45202ff38bf2e89f1d6b2980c23b16435e76`

## Entrega local

- ZIP: `tool/GodOfWarTextEditor_Aprimorado_2026-09-24_R7_EXE.zip`
- Tamanho: 33.615.425 bytes
- SHA-256: `88c1ef57acda7b5bd013e03581d179deaa09f9468e04663ac3726a794edce7aa`
- Publicação remota: [`v2026.09.24-r7`](https://github.com/gushetfield-81/GOW-TEXT-EDITOR/releases/tag/v2026.09.24-r7) publicada em 2026-09-24.
