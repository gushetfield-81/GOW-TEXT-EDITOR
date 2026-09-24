# Relatório técnico — rotas efetivas de cor R9

## Resultado para a MSG 701

A mensagem contém `[*1] [IconBlade] LÂMINAS DE ATENA`. O token é consumido por
`EditTextBuild` e não produz glifo; o título seguinte usa o estilo runtime 1.
A rota correta é `[*1] → GBL_Global.FlashMsg1Color = #7F2805`, não a primeira
cor base `#644B28` de `MessageTemplate_Line1`.

## Camadas físicas verificadas

- `EditTextBuild` reinicia o estilo em cada linha e interpreta `[*N]`.
- `EditTextRender` comprovadamente desenha os estilos 1–4.
- `SetMsgParameters` quantiza `FlashMsgNColor` por `int(float * 255)`; a R9
  altera apenas os três floats RGB (12 bytes) do campo exportado de
  `GBL_Global`.
- Em `FLP_HUDA`, a reversão de GlobalHandlers/KeyFrames até `Data8` distinguiu
  instâncias de mesmo nome:

| Linha | DynamicLabel | RGBA | ramo até a raiz |
|---|---:|---|---|
| 1–5 | 1–5 | `#644B28FF` | `MessageTemplates` |
| 1–3 | 36–38 | `#FFFFFFFF` | `PickUpInfoMenu → InfoTextMovieClips` |

O caminho não é deduzido pela posição da lista. `MessageTemplate_Style` é
selecionado pelo chamador em runtime; o WAD não registra um histórico por ID.
A R9 expõe as alternativas físicas e não escolhe uma por palpite.

## Escopo e caminho seguro

`[*N]` é local à mensagem/linha, mas `FlashMsgNColor` é global. No R_PERMA de
referência, `[*1]` ocorre 125 vezes em 91 mensagens e `[*3]` não ocorre.
Assim, **Editar associada…** confirma o escopo compartilhado, enquanto
**Nova cor exclusiva…** só reserva um slot 1–4 sem uso e aplica tokens apenas
à seleção.

Ao envolver uma seleção, a R9 restaura por linha o estilo que estava ativo logo
depois dela. Isso impede que um novo `[*3]` transforme em base o restante de
um trecho que já pertencia a `[*1]`.

Não há promessa de RGB ilimitado por seleção: se os quatro slots runtime já
estiverem em uso, a alteração exigiria mudar o runtime/ELF, não somente o
`MSGS_TXT`.
