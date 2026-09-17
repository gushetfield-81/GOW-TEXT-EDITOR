# God of War Text Editor — Projeto de Tradução PT-BR (GoW II)

Arquivo oficial de tudo que foi produzido nas sessões de trabalho com o agente
(Arena.ai): a **tool**, os **patchers** de dados do jogo, os **WADs traduzidos
entregues**, a **documentação viva de contexto** e as **prévias visuais**.

> **Tool By: Gus Hetfield** | **Special Thanks: Mogaika**

---

## 📁 Estrutura

```
god-of-war-text-editor/
├── CONTEXTO_MESTRE_GOW_TEXT_EDITOR.md   ← documentação viva (formatos binários,
│                                           decisões, regras, histórico — LEIA PRIMEIRO)
├── tool/
│   ├── GodOfWarTextEditor_Aprimorado_2026-09-12/   ← código-fonte da tool (PySide6)
│   │   ├── gow_text_editor.py                        editor WAD/FLP/MSGS (UTF-8 runtime GoW2)
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
| **Pacote Windows (.EXE standalone)** | [`tool/GodOfWarTextEditor_Aprimorado_2026-09-12_EXE.zip`](tool/GodOfWarTextEditor_Aprimorado_2026-09-12_EXE.zip) (33,6 MB — Python+PySide6 embutidos; extrair e rodar `GodOfWarTextEditor.exe`, sem instalar nada) |
| **Release oficial** | aba **Releases** do repositório (mesmos arquivos, download em 1 clique) |

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
| `tool/…/GodOfWarTextEditor.exe` | 179.712 | `7c43368fd54d101f…` |
| `tool/…_EXE.zip` (pacote Windows) | 33.587.311 | `281c50db6995012d…` |

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

## ⚠️ Nota importante

Os `.WAD` do jogo (originais e traduzidos) contêm **assets com direitos
autorais** (Sony/Santa Monica) e por isso **não são distribuídos aqui** —
ficam apenas em cópia privada com o autor do projeto. Os patchers desta
ferramenta precisam dos WADs originais do usuário para regenerar as entregas.

## 🔧 Requisitos da tool

- Python 3.10+ com **PySide6** (`pip install PySide6`)
- Rodar: `python gow_text_editor.py` (ou o `.exe` da pasta)
- Encoding de `MSGS_TXT`: **UTF-8 (runtime GoW2)** — já padrão da tool
