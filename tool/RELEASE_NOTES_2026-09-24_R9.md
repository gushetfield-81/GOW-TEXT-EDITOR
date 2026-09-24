# God of War Text Editor — R9

**Data:** 2026-09-24
**Tag:** `v2026.09.24-r9`
**Pacote:** `GodOfWarTextEditor_Aprimorado_2026-09-24_R9_EXE.zip`

## Entregue

- Barra **ROTA DA SELEÇÃO** dentro de `TEXTO DA MENSAGEM`:
  - trecho `[*N]`: `FlashMsgNColor`, RGB final e escopo compartilhado;
  - trecho base: `MessageTemplate_LineN`, DynamicLabels físicos, ramos FLP e
    BlendColors/KeyFrames relevantes;
  - seleção mista: aviso explícito, sem uma cor inventada.
- Para a MSG 701, `LÂMINAS DE ATENA` é identificado como
  `[*1] → FlashMsg1Color #7F2805`; a base fica bloqueada nesse trecho para
  evitar editar um template compartilhado por engano.
- Instâncias duplicadas de `MessageTemplate_LineN` são rastreadas por
  GlobalHandlers/KeyFrames: `MessageTemplates` e
  `PickUpInfoMenu → InfoTextMovieClips` ficam distintos na interface.
- **Aplicar à seleção** restaura o estilo ativo depois do trecho, em vez de
  sempre fechar com `[*0]`.
- **Nova cor exclusiva…** só usa um FlashMsg1..4Color que não possui marcador
  existente; grava os 12 bytes RGB e envolve somente a seleção. Sem slot livre,
  a tool recusa prometer independência que o renderer não oferece.

## Limite confirmado

O runtime analisado desenha somente `[*1]`…`[*4]`; `FlashMsgNColor` é global.
`MessageTemplate_Style` é definido pelo chamador em runtime, logo a tool mostra
os ramos físicos comprovados, mas não finge conhecer o contexto quando o WAD
não o codifica.

## Validação

- py_compile da fonte e dos testes R9;
- testes de núcleo: MSG 701, caminhos físicos, restauração de estilo, patch RGB
  de 12 bytes e round-trip;
- Qt offscreen: base bloqueada no título, ramos marrom/branco em `B1H` e reserva
  de `[*3]` aplicada somente à seleção;
- WADs de entrada permaneceram somente leitura.

Nenhum WAD, `.ini`, cache, log ou credencial acompanha a release. Teste WADs
salvos no PCSX2/console antes de distribuir.
