# God of War Text Editor — Projeto de Tradução PT-BR (GoW I / GoW II)

Arquivo oficial de tudo que foi produzido nas sessões de trabalho com o agente
(Arena.ai): a **tool**, os **patchers** de dados do jogo, os **WADs traduzidos
entregues**, a **documentação viva de contexto** e as **prévias visuais**.

Além do fluxo de mensagens do GoW II, a tool reconhece textos de menu do
**GoW I** gravados como StaticLabels em filmes FLP, como `FLP_Shell` dentro de
`R_SHELL.WAD` e `FLP_HUD` em WADs que também carregam recursos TXT.

> **Tool By: Gus Hetfield** | **Special Thanks: Mogaika**

---

## 📁 Estrutura

```
god-of-war-text-editor/
├── CONTEXTO_MESTRE_GOW_TEXT_EDITOR.md   ← documentação viva (formatos binários,
│                                           decisões, regras, histórico — LEIA PRIMEIRO)
├── tool/
│   ├── GodOfWarTextEditor_Aprimorado_2026-09-12/   ← código-fonte da tool (PySide6)
│   │   ├── gow_text_editor.py                        editor WAD/MSGS + StaticLabels FLP (GoW1/GoW2)
│   │   ├── GodOfWarTextEditor.exe                    launcher (rodar com Python + PySide6)
│   │   ├── GODOFWAR.TTF, LEIA-ME.txt, icone/, imagens_de_fundo/
│   └── GodOfWarTextEditor_Aprimorado_2026-09-12_EXE.zip  ← pacote pronto p/ Windows
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
| **Código Python** (`gow_text_editor.py`) | [`tool/GodOfWarTextEditor_Aprimorado_2026-09-12/`](tool/GodOfWarTextEditor_Aprimorado_2026-09-12/gow_text_editor.py) — requer Python 3.10+ e `pip install PySide6` |
| **Pacote Windows atual — 2026-09-22 R3** | [`v2026.09.22-r3`](https://github.com/gushetfield-81/GOW-TEXT-EDITOR/releases/tag/v2026.09.22-r3) — ZIP portátil com Python+PySide6; baixar, extrair a pasta completa e rodar `GodOfWarTextEditor.exe` |
| **Pacote Windows v1.0 (histórico)** | [`tool/GodOfWarTextEditor_Aprimorado_2026-09-12_EXE.zip`](tool/GodOfWarTextEditor_Aprimorado_2026-09-12_EXE.zip) — anterior ao suporte GoW I/FLP direto |
| **Regra de publicação** | Toda mudança entregue na tool recebe ZIP versionado, commit na `main` e uma nova release pública no GitHub, sem sobrescrever releases anteriores. |

> **Nota de validação:** a R3 mantém os TXT usuais e acrescenta FLPs compatíveis
> como `FLP_HUD` à lista principal. Ela também incorpora `FLP_Shell`, labels
> multilinha seguros e o mapeamento correto ao alternar TXT → FLP → TXT. Antes
> de distribuir um **WAD editado**, ainda é recomendado testá-lo no PCSX2 ou console.

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
| `tool/GodOfWarTextEditor_Aprimorado_2026-09-22_R3_EXE.zip` | 33.749.916 | `b9b9d559ad927e3e04f7492478122c9df9bb31c7e0ee8619ea81db20dbc8add4` |
| `tool/GodOfWarTextEditor_Aprimorado_2026-09-22_R2_EXE.zip` (histórico) | 33.596.031 | `cdb7dd3d3f4d09ab913347528f5ba88d69e1e77ddda77655b2734ad513c674bd` |
| `tool/GodOfWarTextEditor_Aprimorado_2026-09-22_EXE.zip` (R1 histórico) | 33.593.905 | `429cc7c1542cea96078b3fe8604c4a0c4afda0e9abc7e4f285cb65831a2e907b` |
| `tool/GodOfWarTextEditor_Aprimorado_2026-09-12_EXE.zip` (histórico) | 33.587.311 | `281c50db6995012de98daa7da0284032a110d85902a65d35a3f554ca8c419920` |

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
