# Análise validada de cores de texto — FLP GoW2

**Data:** 2026-09-24
**Entradas analisadas somente em leitura:** `uploads/R_PERMA.WAD.txt` e `uploads/R_SHELLA.WAD.txt`
**Resultado:** as cores de texto estão em **três camadas independentes** no FLP. A R5 passa a exibir e editar cada camada separadamente, sem reserializar o filme inteiro.

> Nenhum WAD em `uploads/` foi alterado durante esta análise.

---

## Evidência de formato e semântica

A implementação foi validada antes da edição contra o código fornecido do **God of War Browser** e o decompile do runtime GoW2:

| Camada | Evidência | Layout físico confirmado | Efeito no render |
|---|---|---|---|
| `DynamicLabel` / `F_EditText.color` | `pack/wad/flp/parser.go`, `DynamicLabel.FromBuf`: `BlendColor` em `+0x08`; decompile `F_EditText` + `EditTextRender` | registro de `0x20`; os 4 bytes são **BGRA** no disco | cor base do campo de texto do runtime |
| `StaticLabelRenderCommand.BlendColor` | `pack/wad/flp/staticlabel.go` e `BrowserWadFlp.js` | 4 bytes **RGBA** quando o bit `0x04` do comando está presente | cor direta do comando; os comandos seguintes podem herdá-la |
| `BlendColors[ColorId]` | `flp.go` define `Color [4]uint16 // rgba`; `parser.go` lê quatro `uint16`; `BrowserWadFlp.js` usa `KeyFrame.ColorId` | 4 words little-endian, **RGBA**, escala nativa `0..256` | multiplicador/tinta de animação aplicado antes de renderizar o elemento e seus descendentes |

### Por que DynamicLabel é BGRA?

O Browser identifica o campo como o `uint32` `DynamicLabel.BlendColor`, mas não expande seus canais. O decompile fornecido fecha essa lacuna:

- `F_EditText.color` é o `uint32` na posição equivalente a `DynamicLabel + 0x08`;
- em `EditTextRender`, o runtime calcula `R = color >> 16`, `G = color >> 8`, `B = color`, `A = color >> 24`;
- como o FLP é little-endian, os bytes gravados são `B, G, R, A`.

Exemplo real: os bytes `28 4B 64 FF` do `PS2_MessageTemplate_Line1` significam **RGBA `#644B28FF`**, não `#284B64FF`.

---

## Inventário: `R_PERMA.WAD.txt` → `FLP_HUDA`

- WAD de entrada: **3.507.296 bytes**, SHA-256 `fcbecae40d0dcc7ef677f7de37458ea5f1a9a1b0305945e0d38a70ad00f7c42d`.
- FLP: **409.918 bytes**, SHA-256 `3ece91c988f8be491e9aa6035e33719bf569c29d690533afd1b0773c2a5ee28f`.
- `DynamicLabels`: **556**.
- `StaticLabels`: **4**.
- Estrutura de animação validada: Data6=14, Data7=480, Transformations=5.437, BlendColors=1.171, KeyFrames=10.307.
- Tabela global `BlendColors`: offset relativo `0x59BA0`; setor de strings: `0x5C038`.
- **373** tintas globais alcançam pelo menos um rótulo de texto.
- Nenhum `ColorId` nem handler inválido foi encontrado.

### Cores base de DynamicLabels (exibidas em RGBA)

| RGBA | Ocorrências |
|---|---:|
| `#CCCCCCFF` | 286 |
| `#FFFFFFFF` | 208 |
| `#4F3931FF` | 39 |
| `#644B28FF` | 5 |
| `#B7A38DFF` | 4 |
| `#B78C6DFF` | 3 |
| outras | 11 |

Exemplos correlacionados:

- `DynamicLabel[1..5]` — `PS2_MessageTemplate_Line1` até `Line5`: `#644B28FF` (campo físico BGRA `28 4B 64 FF`).
- `DynamicLabel[19]` — `/:PS2_ZoneReport_Title`: cor base `#CCCCCCFF`, mas recebe uma sequência de tintas de animação (ColorIds **576–593**).
- `DynamicLabel[543]` — `/:PS2_4021`: é alcançado por ColorId **575** (`#CC0000FF`) e por uma sequência posterior de tintas relacionadas.

### Cores diretas de StaticLabels

| StaticLabel | Texto | RGBA | Offset no FLP |
|---:|---|---|---:|
| 0 | `/10` | `#FFFFFFFF` | `0x3619` |
| 1 | `Tempo Jogado` | `#FFFFFFFF` | `0x3631` |
| 2 | `3` | `#CCCCCCFF` | `0x3671` |
| 3 | `R` | `#CCCCCCFF` | `0x3681` |

### Título animado: `PS2_ZoneReport_Title`

A cor do título não é apenas a cor base do DynamicLabel. A animação `ZoneReport` referencia a cadeia abaixo, todas mapeadas ao `DynamicLabel[19]`:

- ColorId 576: `#A5735A00` (nativo `[166, 115, 90, 0]`)
- ColorId 577: `#AC796020`
- ColorId 578: `#B2806740`
- …
- ColorId 584: `#D9A58CFF`
- …
- ColorId 593: `#BF8C73FF`

Isto confirma que editar somente `DynamicLabel.BlendColor` não cobriria necessariamente a aparência final de títulos/efeitos. A R5 expõe também a tabela de tintas e mostra os rótulos alcançáveis por cada entrada.

---

## Inventário: `R_SHELLA.WAD.txt` → `FLP_ShellA`

- WAD de entrada: **4.974.320 bytes**, SHA-256 `d97b35d25a834565a1001df8236e45202ff38bf2e89f1d6b2980c23b16435e76`.
- FLP: **133.071 bytes**, SHA-256 `783370d87312bd34e8f30f8d443a7404c5b5e352f14ca915044ceb0451b700ff`.
- `DynamicLabels`: **120**.
- `StaticLabels`: **1**.
- Estrutura de animação validada: Data6=48, Data7=134, Transformations=1.033, BlendColors=522, KeyFrames=4.083.
- Tabela global `BlendColors`: offset relativo `0x1CC38`; setor de strings: `0x1DC88`.
- **156** tintas globais alcançam pelo menos um rótulo de texto.
- Nenhum `ColorId` nem handler inválido foi encontrado.

### Cores base de DynamicLabels (RGBA)

| RGBA | Ocorrências |
|---|---:|
| `#FFFFFFFF` | 82 |
| `#CCCCCCFF` | 35 |
| `#999999FF` | 2 |
| `#870000FF` | 1 |

`DynamicLabel[0]` foi identificado como `PS2_GameVersion` (`#CCCCCCFF`).

### Cor direta de StaticLabel

| StaticLabel | Texto | RGBA | Offset no FLP |
|---:|---|---|---:|
| 0 | `/10` | `#FFFFFFFF` | `0x1569` |

### Exemplo de animação correlacionada

A ColorId **508** é `#FF1A1AFF` (nativo `[256, 26, 26, 256]`) e alcança os DynamicLabels `/:PS2_4004` e `/:PS2_4003` pela raiz `Data8`.

---

## Implementação R5

A R5 acrescenta **Ferramentas → Cores de texto do FLP…** para o FLP GoW2 ativo e separa claramente:

1. **DynamicLabels — cor base:** mostra nome/variável do runtime, cor RGBA atual, alfa e o layout físico BGRA que será atualizado.
2. **StaticLabels — RenderCommand:** lista apenas os comandos que possuem campo de cor próprio, texto/bloco e os blocos que herdam aquela cor.
3. **Animações — BlendColors:** mostra ColorId, cor RGBA, escala nativa 0..256, número de referências e os rótulos de texto alcançáveis.

A seleção de cor usa diálogo RGBA com alfa. Antes de aplicar, a UI exibe **Atual** e **Nova**; ao aplicar, altera exclusivamente:

- 4 bytes no `DynamicLabel` selecionado;
- 4 bytes no `StaticLabelRenderCommand` selecionado; ou
- 8 bytes (quatro `uint16`) no `BlendColor` selecionado.

Depois do patch, a tool reabre e revalida o FLP. O tamanho do FLP não pode mudar. A alteração fica somente em memória até **Salvar WAD como…**.

---

## Validação automatizada R5

`tests/test_gow2_flp_colors_r5.py` usa os dois WADs somente em leitura e validou:

- caminhamento integral Data6/Data7/Data8 e offsets reais das tabelas;
- ordem BGRA de DynamicLabel e RGBA das outras duas camadas;
- patch de DynamicLabel, StaticLabel e BlendColor limitado ao campo identificado;
- reabertura/round-trip do WAD para as três camadas, com diferença limitada
  ao campo de cor identificado (4 bytes DynamicLabel, 4 StaticLabel e até os
  8 bytes do BlendColor);
- hash do WAD de entrada inalterado após o teste.

Também foi executada a regressão de GoW1/StaticLabels/transferência FLP bruto: **14 testes aprovados**, 1 smoke de Qt ignorado no ambiente Linux por ausência de PySide6.

> **Extensão R6:** o inventário desta análise passou a alimentar o painel inline
> de texto. A associação conservadora de StaticLabels e de `MSGS_TXT` com
> `PS2_MessageTemplate_LineN` está documentada em
> `RELATORIO_ASSOCIACAO_CORES_TEXTO_R6.md`; ela não cria vínculo para TXT sem
> evidência física/runtime.
