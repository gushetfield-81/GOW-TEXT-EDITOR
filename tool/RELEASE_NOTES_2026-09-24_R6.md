# God of War Text Editor — 2026-09-24 R6

> **Status:** pacote e notas preparados localmente. A publicação no GitHub/Releases
> permanece pendente por decisão anterior (`publish_later`); esta nota não indica
> que uma release remota já exista.

## Asset preparado

- `GodOfWarTextEditor_Aprimorado_2026-09-24_R6_EXE.zip`
- Tamanho: **33.618.226 bytes**
- SHA-256: `ecf46f86c2c17c7aba22ed42c8bca3ad098d4f387ca15da2dbe4d2a6398aa5d1`

## Novo: cores durante a edição do texto

A tela principal agora possui o painel **CORES ASSOCIADAS AO TEXTO ATIVO**.
Ele aparece abaixo do editor e permite selecionar e editar a cor sem abrir outro
fluxo nem abandonar o texto atual.

### StaticLabels FLP GoW2

Ao editar um StaticLabel, o painel lista:

- cor(es) direta(s) de RenderCommand;
- blocos que herdam uma cor direta;
- apenas BlendColors/KeyFrames que alcançam aquele rótulo;
- quantidade de referências e outros textos atingidos por uma tinta compartilhada.

### MSGS_TXT GoW2

A R6 usa o vínculo real do runtime: `DoMsgPage` escreve cada linha da página
nas variáveis `PS2_MessageTemplate_Line1` a `Line5` do FLP. Com o cursor em uma
linha, o painel apresenta as instâncias de DynamicLabel e BlendColors ligadas a
`MessageTemplate_LineN`; mover o cursor atualiza o LineN. Em linhas vazias ou
no separador `--`, apresenta todos os campos do template potencialmente usados.

TXT que não seja `MSGS_TXT` permanece explicitamente sem uma associação
inventada, pois não há mapeamento físico confirmado entre seus IDs e um FLP.

## Segurança

- DynamicLabel: apenas 4 bytes BGRA.
- StaticLabel: apenas 4 bytes RGBA.
- BlendColor: apenas 8 bytes (`uint16` RGBA 0..256).
- O painel mostra o alcance antes da edição. Um BlendColor compartilhado pode
  alterar fades/estados de mais de um texto.
- Se houver edição de texto pendente, ela é preservada: o patch acontece no
  FLP de origem e o WAD só é escrito com **Salvar WAD como…**.

## Validação R6

- Suíte persistente: **16 testes**.
- Host sem PySide6: 14 aprovados e 2 smokes Qt ignorados.
- Qt/PySide6 offscreen: **16/16 aprovados**.
- O smoke visual abriu `R_PERMA`, validou o painel `MSGS_TXT → FLP_HUDA`,
  alternou o cursor da linha 1 à linha 2 (IDs 2/37), aplicou uma cor pelo botão
  inline e confirmou exatamente 4 bytes modificados, preservando o texto.
- O painel de StaticLabel também foi validado com cor direta e BlendColors.
- Nenhum WAD de entrada foi gravado; todos os patches foram feitos em memória.

## Créditos

Tool By: Gus Hetfield
Special Thanks: Mogaika
