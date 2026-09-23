# CONTEXTO MESTRE — God of War Text Editor (GOW Text Editor)

> **Documento de continuidade vivo.** Este arquivo reúne TODO o contexto técnico,
> decisões e estado atual da tool. Regra da sessão (definida pelo usuário em
> 2026-09-13): **sempre atualizar/gerar este arquivo após qualquer alteração na tool.**
> Em um chat novo, anexe este arquivo (+ os arquivos relevantes) para retomar de onde parou.

Última atualização: **2026-09-22** (Sessão 13 — StaticLabels multilinha editáveis)
Versão do documento: **2.9** (substitui o antigo `CONTEXTO_GOW_TEXT_EDITOR_HANDOFF.md/.txt`)

---

## 1. VISÃO GERAL DO PROJETO

- **Ferramenta:** editor de textos direto em WADs de God of War (PS2), com foco no
  GoW2 (`R_PERM.WAD` / `R_PERMA.WAD` das mensagens, `R_SHELLA.WAD` dos menus).
- **Usuário:** Gus Hetfield — tradutor/modder PT-BR. **Não precisa de .exe**; roda a tool
  em Python no Windows. Créditos fixos da tool: `Tool By: Gus Hetfield` /
  `Special Thanks: Mogaika`.
- **Stack:** Python + PySide6 (Qt). Interface tema escuro estilo "Wad Studio".
- **Regras de ouro do núcleo (JÁ VALIDADAS EM JOGO — NÃO MEXER):**
  - headers de tag de 0x20 bytes; alinhamento/padding de 0x10 bytes;
  - recursos binários não editados permanecem byte a byte idênticos;
  - marcadores de mensagens (`*ID*`, `*ID*H`, `*ID*T`), IDs, quebras e dados preservados;
  - `MSGS_TXT` do GoW2 é gravado SEMPRE em UTF-8 (runtime Flash) — ver seção 3.

---

## 2. ESTADO ATUAL DA TOOL (funcionalidades)

### 2.1 Núcleo WAD/texto (validado em jogo, não alterar sem necessidade)
- Parser WAD lossless (variantes GoW1 e `GoW2/runtime`), serialização byte-exata;
  recursos inalterados voltam idênticos (inclusive padding não-zero).
- Codificações: `Windows-1252 (browser/legado)`, `UTF-8 (runtime GoW2)` — **travado e
  obrigatório quando o recurso é `MSGS_TXT`** —, `ISO-8859-1`, `Windows-1251`,
  `UTF-8`, `UTF-8 com BOM`, `Shift-JIS/CP932`.
- Dicionário CP1252 explícito do GoW2 (`GOW2_CP1252_DICTIONARY`) para migração de
  WADs legados; editor visual sempre em Unicode.
- Diagnóstico runtime (IDs duplicados, dicas H/T, páginas `--`, limite de linhas do
  DoMsgPage, macros), localizar/substituir, undo/redo, importar/exportar recurso.
- Prévia CRT/Layout com `QPainter` (geometria real medida no FLP_HUD; 4:3/16:9,
  alinhamento, âncora, espaçamento).
- Editor de StaticLabels agora cobre **GoW2 e GoW1**: `FLP_HUDA`/filmes GoW2 e
  `FLP_Shell` do GoW1. O shell GoW1 abre mesmo sem recursos `.TXT` e, nesse
  caso, seus rótulos aparecem diretamente nos painéis principais (lista
  central + editor à direita), sem exigir o menu Ferramentas. Rótulos de um
  ou vários blocos são editáveis: em multilinha, a UI exige preservar o mesmo
  número de linhas e reemite cada uma no bloco/âncora original.

### 2.2 Interface (estado atual)
- **Acento visual VERMELHO** (era laranja): paleta
  `WAD_ACCENT #C03030 / WAD_ACCENT_HOV #E14B4B / WAD_ACCENT_DIM #5C1515`;
  seleção de listas/tabela `#3A0C0C`; avisos de overflow/ID duplicado `#E15B5B`.
- **Shell GoW1 sem TXT:** se o WAD só traz `FLP_Shell`, o painel esquerdo muda
  para **FILMES / RÓTULOS**, a lista central para **RÓTULOS DESENHADOS** e o
  editor para **TEXTO DO RÓTULO**. A lista marca multilinhas com `• N linhas`
  e o status lembra manter N linhas. Os botões estruturais (+Nova/Duplicar/
  Excluir), codec, importar/exportar e localizar/substituir ficam desativados;
  **Aplicar rótulo** grava somente o StaticLabel selecionado em memória.
- **Imagem de fundo personalizada** — menu `Visualizar > Imagem de fundo`:
  - `Definir imagem...` (PNG/JPG/JPEG/BMP/GIF/WEBP): copia a escolha para
    `imagens_de_fundo/` já com o nome `background.*` e aplica na hora;
  - `Recarregar da pasta` — reaplica o `background.*` atual;
  - `Remover imagem` — volta ao tema sólido e renomeia o arquivo para `*.off`;
  - `Escurecimento`: Leve 70 / Médio 110 (padrão) / Forte 160 (overlay preto sobre a imagem);
  - com imagem ativa, painéis/fundos viram "vidro" translúcido (alpha ~170–205),
    menus e diálogos continuam sólidos; sem imagem, tema sólido normal;
  - persistência no INI (`[ui] bg_image`, `bg_dim`), restaurada ao reabrir.
- **Pasta `imagens_de_fundo/`** (ao lado da tool, criada automaticamente com o aviso
  `COLOQUE-A-IMAGEM-AQUI.txt`): a detecção automática é **pelo NOME** — só carrega um
  arquivo chamado `background` (`background.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`,
  `.webp`); outros nomes são ignorados; preferência png > jpg > jpeg > bmp > gif > webp.
- **Pasta `icone/`** (mesmo esquema): aplica o ícone da janela (barra de título,
  taskbar, diálogos) a partir de um arquivo chamado **`icon`**
  (`icon.ico/png/jpg/jpeg/bmp/gif/webp`); preferência **ico > png > jpg > jpeg > bmp >
  gif > webp**; menu `Visualizar > Ícone da janela` (Definir ícone... / Recarregar da
  pasta / Remover ícone — remover renomeia para `icon.*.off`); já vem com um
  `icon.png` de exemplo (ômega vermelho).
- **Título "GOW Text Editor"** discreto no canto esquerdo da toolbar, em VERMELHO,
  usando a fonte `GODOFWAR.TTF` (família "GodOfWar") carregada da pasta da tool
  (`QFontDatabase.addApplicationFont`); tamanho acompanha a escala da UI
  (Ctrl+= / Ctrl+- / Ctrl+0); sem o .ttf, usa fonte comum sem quebrar.
- Atalhos: `Ctrl+O` abrir, `Ctrl+S` salvar como, `Ctrl+Z` desfazer campo,
  `Ctrl+Shift+Z`/`Ctrl+Shift+Y` undo/redo global, `Ctrl+F` busca, `Ctrl+H` substituir,
  `F11` tela cheia, `Ctrl+0` escala 100%.
- Configuração em `GodOfWarTextEditor.ini` ao lado do .py (override de testes:
  env `GOW2TE_INI`); seções: `[paths]`, `[window]`, `[ui]` (scale, bg_image, bg_dim),
  `[editor]` (codec).

### 2.3 Arquivos da tool (pasta `GodOfWarTextEditor_Aprimorado_2026-09-12/`)
| Arquivo | Papel |
|---|---|
| `gow_text_editor.py` | Fonte única da tool (núcleo + UI Qt), incluindo parsers FLP GoW2 e GoW1 |
| `tests/test_gow1_flp.py` | Testes sintéticos de StaticLabels GoW1/GoW2 (sem WADs proprietários) |
| `flp_gow2.py` | Parser/marshal FLP GoW2 (Sessão 4; usado pelo patcher do Shell) |
| `adicionar_acentos_shell.py` | Gera `R_SHELLA_PTBR.WAD` a partir dos WADs originais |
| `GODOFWAR.TTF` | Fonte do título |
| `imagens_de_fundo/` | `background.png` (exemplo) + aviso |
| `icone/` | `icon.png` (exemplo ômega) + aviso |
| `LEIA-ME.txt` | Documentação do usuário (atualizada a cada revisão) |
| `GodOfWarTextEditor.exe` | **ANTIGO** (laranja, sem fundo/ícone/título) — ignorar |
| `R_PERMA.WAD.txt`, `R_SHELLA.WAD.txt` | WADs de referência/trabalho |

---

## 3. DESCOBERTA-CHAVE: ENCODING DO RUNTIME GOW2 (validada em jogo)

O runtime Flash do GoW2 usa `Decode(encoding=1)`, que consome **UTF-8**. A fonte usa
codepoints equivalentes aos índices CP1252/Unicode:

```
ã  -> UTF-8 C3 A3 -> codepoint U+00E3 -> índice de fonte 0xE3
í  -> UTF-8 C3 AD -> codepoint U+00ED -> índice de fonte 0xED
```

Gravar CP1252 de 1 byte (`E3`) fazia o runtime engolir o byte seguinte
("Titã" virava "TitMuito Difi..."). O WAD corrigido em UTF-8 foi confirmado em jogo.
WADs legados em CP1252 são migrados automaticamente ao carregar e gravados em UTF-8.

---

## 4. HISTÓRICO DE SESSÕES / CHANGELOG

### Sessão 0 (chat anterior — resumo do handoff original)
- Tool criada e evoluída até a versão Qt; descoberta do UTF-8 runtime (seção 3);
  `R_PERMA_GOW2_RUNTIME_UTF8.WAD` testado com sucesso no jogo
  (`Titã (Muito Difícil)` correto).

### Sessão 1 (2026-09-13) — Vermelho + Imagem de fundo
- Laranja → **vermelho** em toda a UI (paleta, seleções, avisos).
- Recurso de **imagem de fundo** (menu, efeito vidro, escurecimento, INI).
- Corrigidos problemas herdados do pacote: linha final corrompida do
  `gow_text_editor.py` (`main()it(...)`) e literal quebrado do
  `test_gow2_visual_accent_dictionary_roundtrip` (string do teste tinha espaços
  espurios — o núcleo estava certo).
- Bundle enviado: `GodOfWarTextEditor_Vermelho_Fundo_2026-09-13.zip`.

### Sessão 2 (2026-09-13) — Pasta de fundos + Título
- `imagens_de_fundo/` com detecção automática (primeiro por "mais recente",
  logo depois alterado para **detecção pelo nome `background.*`** — decisão do usuário).
- Título **"GOW Text Editor"** na toolbar com a fonte `GODOFWAR.TTF` em vermelho
  (usuário enviou a fonte; família "GodOfWar"); escala acompanha a UI.
- Itens de menu `Recarregar da pasta`; cópia padronizada em `Definir imagem...`;
  status informa a detecção. Bundle: `GodOfWarTextEditor_Background_2026-09-13.zip`.

### Sessão 3 (2026-09-13) — Ícone da janela
- Pasta `icone/` + detecção pelo nome `icon.*` (mesmo esquema do fundo).
- Menu `Visualizar > Ícone da janela` (Definir/Recarregar/Remover com `.off`).
- `Remover imagem` do fundo também passou a renomear `background.*` → `*.off`
  (consistência: o fundo não "volta sozinho").
- Ícone exemplo gerado (ômega vermelho estilo GoW).
- Bundle: `GodOfWarTextEditor_Icone_2026-09-13.zip`.

### Sessão 4 (2026-09-13) — Acentos com til na fonte do menu (R_SHELLA)
Pedido: "reunir contexto" + (sessão anterior) adicionar acentos PT na fonte do Shell.
- **Análise:** o `R_SHELLA.WAD` tem fonte própria em `FLP_ShellA` (132 glifos, mapa
  256 entradas, flags 0x5). TINHA todos os acentos PT **exceto til**: faltavam
  `Ã(0xC3) Õ(0xD5) ã(0xE3) õ(0xF5)`.
- **Prova do método:** o mod europeu do `R_PERMA` (`FLP_HUDA`) já tinha resolvido o
  mesmo problema do mesmo jeito: glifos 132-135 clonando a/A/o/O
  (widths 627/759/660/792 = mesmos das letras base), parts 410-413 no `MDL_HUDA_0`,
  e tiles com til desenhados nas células que antes eram de Ñ/Ä/Ö da atlas
  `GFX_GodOfWarEurope`.
- **Executado no Shell (idêntico ao mod):**
  1. `FLP_ShellA`: +4 glifos (132=ã, 133=Ã, 134=õ, 135=Õ), `char_map` atualizado,
     widths do PERMA, refs para parts 180-183;
  2. `MDL_ShellA_0`: +4 parts (180-183) = clones dos parts de a/A/o/O
     (59/33/73/47) com o programa DMA (XY+UV) dos glifos de til do PERMA e a
     joint da letra base (raw+0x20); parts 180→184; 85.488 → 86.400 bytes;
  3. `GFX_GodOfWarEurope`: copiados **somente os pixels das 4 células**
     (150,84)-(168,104) ã, (28,30)-(52,54) Ã, (94,110)-(114,130) õ,
     (186,2)-(212,26) Õ. Prova: as atlas diferem em 353 px, 100% dentro dessas
     células (ö/ä/ü/ñ e todo o resto intactos). Paleta idêntica, intocada.
- **Resultado:** `saida_shell/R_SHELLA_PTBR.WAD` (4.974.320 bytes; SHA-256
  `0e7505a739f02fc3578fd52a4811a901e4fab8bb4cdfb75a60287509345d3ac0`).
  Só 3 tags mudam (FLP/MDL/GFX); as outras 2.539 permanecem byte a byte.
- **Validação visual:** render em software usando os quads/UVs do próprio WAD —
  `Titã (Muito Difícil)`, `feijão`, `não`, `pão`, `amanhã`, `mãe`, `ÃÕãõ` perfeitos
  (`saida_shell/previa_definitiva.png`, `zoom_final_tiles.png` antes/depois).

### Sessão 5 (2026-09-13) — Pasta enxuta + GodOfWarTextEditor.exe com ícone
Pedido: "analisar a pasta da tool, remover arquivos desnecessários e criar um
.EXE com aquele mesmo ícone (ômega), dentro da pasta da tool".
- **Limpeza** (`work/tool/arquivados/` guarda os arquivos fora da tool):
  a pasta da tool ficou com APENAS: `GodOfWarTextEditor.exe`, `gow_text_editor.py`,
  `GODOFWAR.TTF`, `LEIA-ME.txt`, `icone/` (icon.png), `imagens_de_fundo/`
  (background.png). Removidos da tool: WADs de teste, `GodOfWarTextEditor.ini`
  (artefato de teste; a tool recria sozinha), `__pycache__`, fontes/tests/spec antigos.
- **EXE (launcher nativo, sem PyInstaller):** `launcher.c` compilado com
  `zig cc -target x86_64-windows-gnu -municode -O2` (zig 0.16 via pip `ziglang`)
  → subsystem GUI (sem console), ~190 KB. Não embute Python: ele resolve o
  próprio diretório e executa `app\pythonw.exe -X utf8 gow_text_editor.py`
  (CreateProcess sem janela); se `app\pythonw.exe` não existir, usa `pythonw.exe`
  do PATH (exige `pip install PySide6`); erros mostram MessageBox em PT-BR.
- **Ícone no PE — MÉTODO FINAL (canônico, validado):** `lld-link` do zig **ignora
  `.res` solto silenciosamente** (aceita linkar mas não cria `.rsrc`) e **injeção
  manual de seção `.rsrc` é DEAD END** — mesmo com SizeOfImage corrigido o
  Windows do usuário rejeitou o exe duas vezes ("Este aplicativo não pode ser
  executado em seu PC"). NÃO RETENTAR. O que funciona:
  1) gerar a árvore de recursos (RT_ICON 16→256 px + RT_GROUP_ICON, Python puro)
     como **objeto COFF** (`res2.obj`: 1 seção `.rsrc`, chars 0x40000040);
  2) **data entrys com RVA FINAL = VA da .rsrc no exe pronto + offset na árvore**
     (o lld copia a seção verbatim e NÃO reajusta offsets estilo windres — com
     offset relativo ou base errada os ícones saem corrompidos);
  3) linkar com a linha EXATA que o `zig cc` usa (obter com `zig cc -v`) +
     `/SUBSYSTEM:WINDOWS` + o objeto. Assim SizeOfImage/defaults ficam 100% por
     conta do linker (canônico). A VA da .rsrc é determinística (0xA000 p/ estes
     inputs); se mudar, relinkar e reajustar a base do objeto.
  - .ico de 7 tamanhos gerado de `icone/icon.png` com PIL (256 px fica como PNG).
  - **Validação dupla:** pefile (zero warnings, 7 ícones byte-exatos vs icon.ico,
    grupo com ids 1-7) **+ WINE 11.17 como loader real** (AppImage mmtrt/
    WINE_AppImage, `--appimage-extract`, WINEPREFIX em /home/user — /tmp ele
    recusa): test42_plain → exit 42; test42_com_recursos → exit 42; launcher
    real → carregou e retornou 1 (código rodou, pythonw ausente no sandbox).
  - Exe final: 179.200 B, SHA-256 `df8d892b…`, subsystem GUI, SizeOfImage
    0x32000, `.rsrc` @ 0xA000. Fontes: `arquivados/launcher.c` + builder do
    objeto em `arquivados/` (ver Sessão 5 changelog).
- **Runtime portátil:** montado em /tmp (NÃO persiste entre sessões!) —
  `python-3.13.1-embed-amd64.zip` + wheels `PySide6-Essentials/shiboken6 6.11.2
  cp310-abi3 win_amd64` (/tmp/wheels). Strip por whitelist → só
  QtCore/QtGui/QtWidgets (+DLLs Qt6Core/Gui/Widgets, plugins
  `platforms/styles/imageformats/iconengines`, CRTs do shiboken);
  `app/python313._pth` = `python313.zip`, `.`, `Lib\site-packages`.
  232 MB → **65 MB** extraídos; ZIP final **~33,5 MB**.
- **Entrega:** `GodOfWarTextEditor_Aprimorado_2026-09-12_EXE.zip` em `/home/user/`
  (raiz: exe, py, TTF, LEIA-ME, icone/, imagens_de_fundo/, app/). O exe também
  está na pasta da tool no workspace. `gow_text_editor.py` não mudou (core
  intocado). Fontes do launcher (`launcher.c`, `build_res_obj.py`, `icon.ico`)
  guardadas em `work/tool/arquivados/`. LEIA-ME ganhou a seção
  "EXECUTÁVEL .EXE (2026-09-13)" (e perdeu o aviso obsoleto de "build anterior").
- **⚠ ROOT CAUSE do "abre e não aparece nada" (corrigido na Sessão 5):** o strip
  da PySide6 apagou **`pyside6.abi3.dll`** (DLL de suporte que TODOS os .pyd
  linkam; não estava na whitelist) → `ImportError: DLL load failed while
  importing QtWidgets` morrendo em silêncio no pythonw (sem console). LIÇÃO:
  após qualquer strip, testar `import` de QtCore/QtGui/QtWidgets no runtime alvo.
  A DLL foi restaurada do wheel (`unzip pyside6_essentials...whl PySide6/pyside6.abi3.dll`).
  (opengl32sw.dll segue fora de propósito — fallback de GL por software, 20 MB.)
- **⚠ LAUNCHER v2 (logging):** após este bug invisível, o launcher passou a rodar
  `app\python.exe` (console) com `CREATE_NO_WINDOW` + stderr/stdout →
  `erro_python.log` na pasta da tool (truncate por execução). Fallbacks:
  app\pythonw.exe / pythonw.exe do PATH. Fonte: `arquivados/launcher.c`.
- **VALIDAÇÃO FINAL NO WINE (loader PE real), aprovada em cadeia:**
  `python.exe -c "from PySide6 import QtWidgets..."` OK → boot do editor real
  (`QT_QPA_PLATFORM=offscreen`, vivo 12 s = loop rodando, sem traceback) →
  launcher completo via `C:` virtual (exit 0, python vivo 10 s+, log criado
  vazio, sem .ini). **QUIRK do Wine AppImage:** `GetModuleFileNameW` retorna
  caminho `unix\tmp\...` quando o exe roda do Z: → FileExists falha; testar
  SEMPRE copiando o bundle para `$WINEPREFIX/drive_c/` e rodando via `C:\...`
  (no Windows real não acontece). `wineserver -k` para limpar processos.

### Sessão 6 (2026-09-16) — Mistério do "Total PlayTime" (R_PERMA)
Pedido: "consegui alterar todos os textos, exceto 'Total PlayTime' — por quê?"
- **RESPOSTA (validada):** não é texto do jogo. É um **StaticLabel** do filme
  Flash **FLP_HUDA** (tela STATUS): lista de comandos que desenham glifos fixos
  (id+largura) da fonte europeia. Nunca passa pelo MSGS → a edição do *4601*
  ("Tempo Total Jogado", já traduzida pelo usuário) não o afeta.
- **Formato FLP GoW2 filme** (fonte: god_of_war_browser do Mogaika,
  `pack/wad/flp`): header 0x5C com CONTAGENS @0x38 GH, @0x3C refs, @0x40
  fonts, @0x44 statics, @0x48 dynamics, @0x4C d6, @0x50 d7, @0x54/56 u16
  transf/blend, @0x58 u32 strings_size. Stream: GH(4B) → refHeaders(8B;
  matsPart s16@+4, cnt u16@+6) → refMats(8B) → font headers 0x24 → font
  bodies → **statics**: headers 0x1C (transformation + u32 streamSize @0x18)
  seguidos dos streams alinhados em 4. Stream = blocos {op 0x80|flags; &8:
  gh u16 + scale i16/1024; &4: cor 4B; &2: x i16/16; &1: y i16/16} + u8
  count + count×(glyph u16, width i16/16). Depois: dynamics 0x20B (value_off
  u16@0, placeholder_off u16@2, gh u16@4, limit u16@0xC; offsets relativos ao
  setor de strings no FIM do arquivo). UVs dos glifos na mesh HUDA: **2×i16
  por vértice @part+0x78** (na FLP_HUD era @raw+0x38 c/ contagem no +2; aqui
  esse campo vale 1 — não reusar a receita da HUD sem checar).
- **Rótulos estáticos do FLP_HUDA:** [0]"/10" [1]"Total PlayTime" [2]"3"
  (ícone triângulo) [3]"R" (R1). Decodificação por char_map invertido
  (flags&1 → 256 entradas símbolo→char); glifo 0 = espaço; as larguras
  naturais conferem byte a byte com o original → identificação exata.
- **Textura da fonte do STATUS:** material indexado (soff=3) → 3º objeto
  após MDL_HUDA na sub-árvore = **TXR_GodOfWarEurope** (é a atlas Europe!).
  Cuidado: teste "empírico de alpha" enganou (fumaça/SFX são opacos 100%).
- **Patch entregue:** `saida_playtime/` — `patch_total_playtime.py`
  (troca o stream do rótulo [1]; revalida com reparse; aceita texto livre
  via argv; ç=114 e ã=132 EXISTEM na fonte) + `R_PERMA_TTJ.WAD`
  (regenerado em 2026-09-16 sobre a versão NOVA que o usuário mandou com
  mais edições de texto: 3.507.264 B; SHA-256 `6ae45372…1431da`;
  **só FLP_HUDA difere, 3.352 tags byte-exatas** — edições do usuário
  preservadas). Texto padrão
  "Tempo de Jogo" (13 glifos, largura 157 < 168 do original).
  ⚠ LIÇÃO v2 (causou "T E M P O E J O G O" espalhado sobre o cronômetro):
  a width em cada glifo do stream NÃO é a largura natural da fonte — é o
  AVANÇO já na escala do filme (~0.325× a natural neste rótulo; razões
  variam 0.317–0.333 = kerning manual). O patcher agora deriva
  fator = Σ(w originais)/Σ(naturais) do PRÓPRIO rótulo e reusa a width
  exata do original quando o glifo já existe nele; fallback = natural×fator.
  "Tempo de Jogo" (13 glifos ≈188px < 202px do original na escala 0.390625
  — não encosta no cronômetro). Na mesma pasta: `flp_gow2.py` e
  `gow_text_editor.py` (requisitos do patcher) + LEIA-ME_PLAYTIME.txt.
- PENDENTE: teste em jogo (tela STATUS). As traduções do usuário continuam
  íntegras (o patch foi feito sobre o arquivo dele).

---

### Sessão 7 (2026-09-16) — A TOOL AGORA EDITA os rótulos desenhados (FLP)
Depois do patch validado em jogo ("Tempo de Jogo" na STATUS, print do usuário),
o usuário pediu: "fazer com que a tool consiga editar corretamente esse texto".
- **Implementado em `gow_text_editor.py`** (tool folder; single-file preservado):
  1. **`FLPMovie`** (núcleo, nível de módulo, SEM Qt): parser do filme GoW2
     (gh/refs/fonts/statics/dynamics) com validação de limites; `label(i)`
     (texto decodificado via char_map invertido, editável?, detalhe);
     `encode_label(i, texto)` — reescreve o stream do rótulo com o novo texto:
     header do bloco copiado BYTE A BYTE do original (evita drift de float de
     escala), avanços reutilizados do original quando o glifo já existe nele,
     fallback `natural × fator` (fator = Σw_orig/Σw_natural), glifo 0 =
     espaço; `_rebuild_statics` realinha tudo e REVALIDA reparseando (texto
     do rótulo novo + rótulos vizinhos inalterados) ANTES de devolver.
  2. **UI**: menu `Ferramentas > "Rótulos desenhados do filme (FLP)..."` →
     diálogo (QComboBox de FLPs parseáveis + QListWidget de rótulos + QLineEdit
     + Aplicar/Restaurar/Fechar). Read-only para: multi-bloco, sem fonte
     (gh≠array3), glifos fora do mapa. `Restaurar original` = bytes de quando
     o diálogo abriu. Apply → `tag.data` + `self.dirty` (salva via fluxo normal).
  3. Pipeline de TEXTO (TextResource/apply_current/MSGS) **intocado**.
- **VALIDAÇÃO**:
  - **TESTE DE OURO**: `FLPMovie.encode_label(1, "Tempo de Jogo")` sobre o
    R_PERMA do usuário gera FLP_HUDA **BYTE-IDÊNTICO** ao `R_PERMA_TTJ.WAD`
    do patcher validado em jogo ✓
  - UI offscreen (QFileDialog simulado + QDialog.exec interceptado): abre WAD,
    diálogo lista 4 rótulos, carrega "Total PlayTime", aplica "Tempo de Jogo",
    lista atualiza, tag == golden, dirty=True ✓
  - Regressão do núcleo: round-trip R_PERMA/R_SHELLA byte-exato, dicionário
    CP1252, MSGS_TXT to_bytes idempotente ✓
  - Guardas: "~" sem glifo recusado com mensagem; vazio recusado; ç/ã aceitos;
    editar [0] p/ "7/10" e voltar p/ "/10" = byte-exato ✓
- **BUGS de implementação corrigidos no caminho (não repetir):**
  1. `len(b) % 4` no __init__ — o CORPO da tag FLP não é alinhado (só a tag);
  2. helpers u16/u32 não existem no módulo da tool → métodos estáticos
     `_u16/_u16s/_u32` na classe (o replace global quebrou os `def` — cuidado);
  3. loop de statics: `hdr` calculado com `pos` MUTÁVEL (avança nos streams) —
     drift → "stream fora dos limites"; fix: `hdrs_start` fixo;
  4. `parse_commands` virou método de instância (usa self._u16) — sem
     @staticmethod;
  5. `hdr_len = j + 1` incluía o u8 de contagem antigo no header copiado →
     contagem duplicada no stream novo (revalidação pegou!) → `hdr_len = j`.
- **Entrega atualizada**: ZIP do EXE (33,6 MB) regenerado com o py novo
  (exe NÃO mudou — launcher roda o .py da pasta); LEIA-ME com seção
  "RÓTULOS DESENHADOS DO FILME — FLP"; `saida_playtime/gow_text_editor.py`
  sincronizado (patcher segue funcionando).
- **Limitações conscientes**: só FLP GoW2 (GoW1 tem header 0x60/statics 0x24 —
  parser recusa); rótulos multi-bloco read-only; max 255 glifos; strings/
  dynamic labels não editáveis aqui (placeholder do DynamicLabel fica no setor
  de strings — tarefa futura, se o usuário quiser).

---

### Sessão 8 (2026-09-17) — Tradução do usuário no R_PLOCU europeu (GoW2)
Pedido: aplicar o MSGS_TXT traduzido (do R_PERMA) no R_PLOCU.WAD da versão
europeia (slot inglês britânico); a tentativa do usuário "não rodou".
- **R_PLOCU**: 360 tags; variant "desconhecido" p/ a tool (primeira tag
  MC_DATA 0x0007) mas parse/serialize BYTE-EXATO (round-trip ok); tem
  FLP_HUDU (filme de HUD da localização), MDL_HUDU (185KB), a MESMA
  GFX/PAL/TXR_GodOfWarEurope, e MSGS_TXT (50.328 B, UTF-8 VÁLIDO — mesmo
  runtime) + MSGS_COUNT/MSGS_LINES com 0 BYTES (vazios — igual R_PERMA;
  o runtime conta sozinho, os contadores não existem fisicamente).
- **Diferenças de conteúdo EU vs tradução do usuário (R_PERMA)**:
  EU=799 msgs; usuário=808. Usuário TEM a mais: 36-45 (textos de combo
  "Continue!" etc.). EU TEM a mais: *4034* = "\nL\nR\n" (rótulos de
  botão, exclusiva do EU). Ordem diferente (EU pula 35→100).
  Marcador-template com colchetes existe nos DOIS (EU: *1]Forward Dash
  Slam[* / usuário: *1]Investida pra frente[* — é dica de combo com o
  nome do golpe DENTRO do marcador; corpo começa com "0] ...").
  Sufixos H/T idênticos em todos os IDs comuns (0 diferenças).
- **CAUSAS prováveis do "não rodou"**: conjunto/ordem de IDs incompatível
  (FindMsg de mensagem inexistente, ex. 4034) e/ou troca binária direta
  (arquivo 5KB maior → estrutura corrompida → nem abre). Contadores NÃO
  foram a causa (vazios nos dois).
- **SOLUÇÃO entregue (`saida_plocu/R_PLOCU_PTBR.WAD`)**: merge por ID —
  ordem/conjunto EXATOS do EU (799), corpo traduzido do usuário em 798,
  *4034* mantida em inglês (L/R universal), template trocada pela
  traduzida (casamento por prefixo "N]"), extras 36-45 descartados.
  Só MSGS_TXT difere (359 tags byte-exatas); cauda do EU preservada;
  re-serialize estável; TextResource vê a MESMA quantidade de entradas
  nos dois (798 — o parser da tool funde o template com o anterior,
  igual no original); UTF-8 válido; SHA-256 ddca73c5…; LEIA-ME_PLOCU.txt.
- **NOTA de como-rodar**: substituir o R_PLOCU.WAD do jogo e escolher
  INGLÊS (britânico) na língua — é esse slot.
- **Para o futuro**: um "merge de idiomas" como este é candidato a virar
  função da tool (Ferramentas > Aplicar tradução em outro WAD), seguindo
  exatamente este algoritmo (ordem/conjunto do DESTINO, corpos da ORIGEM,
  templates casadas por prefixo "N]", IDs ausentes mantidos em inglês).

---

### Sessão 9 (2026-09-16) — Acentos ã Ã õ Õ no R_SHELLU europeu (GoW2)
Pedido: repetir o esquema de acentos validado no shell AMERICANO (R_SHELLA,
Sessão anterior ao PLOCU) no shell EUROPEU (R_SHELLU.WAD, 2533 tags, slot
inglês britânico). Fonte dos tiles: o mesmo R_PERMA traduzido do usuário.
- **Por que não deu para copiar da atlas (ataalho do EUA)**: a atlas
  (GFX_GodOfWarEurope) do SHELLU tem desenhos DIFERENTES dos do PERMA
  (30.606 px) e as posições dos tiles ã/Ã/õ/Õ do PERMA estão OCUPADAS por
  glifos vivos: '?'(145,83), '¿'(161,83), 'Y'(28,30 — célula INTEIRA),
  'g'(93,109), 'G'(186,1 — célula INTEIRA). Relocar tiles é impossível:
  retângulos dos 132 glifos cobrem 74% da atlas 256×256 (único buraco
  20×21 em (236,196)).
- **SOLUÇÃO (validada): células-VÍTIMA.** A fonte europeia tem 4 acentos
  que PT-BR de menus NUNCA usa, com medidas EXATAS dos tiles de til:
  ñ sym123 (123,83) 20×21 → ã | Ä sym90 (1,30) 25×25 → Ã |
  ö sym127 (70,109) 21×20 → õ | Ö sym104 (158,1) 26×25 → Õ.
  (Espelha o americano, que sacrificou Ñ/Ä/Ö.) char_map[ñ/Ä/ö/Ö] = -1.
- **Alterações (3 tags de 2533; patcher `saida_shellu/adicionar_acentos_shellu.py`)**:
  FLP_ShellU (125.215→125.519 B): glifos 132-135 = ã Ã õ Õ, widths PERMA
  627/759/660/792, mesh_refs (180+k,1), mats (0xFFFFFFFF,0);
  MDL_ShellU_0 (85.392→86.304 B): parts 180-183, clones dos parts das
  letras base (a=59/joint60, A=33/34, o=73/74, O=47/48) com raw do tile
  PERMA (parts 410-413), joint da letra base no u32@raw+0x20 e UVs
  REALOCADOS em s16 1/16px para a célula-vítima (delta = célula-vítima −
  célula-PERMA); GFX_GodOfWarEurope: tiles PINTADOS pixel a pixel nas 4
  células-vítimas (nada mais muda — 0 px fora).
- **Validação**: só FLP_ShellU/MDL_ShellU_0/GFX diferen; FLP re-parse
  (136 glifos, cmap ã=132 Ã=133 õ=134 Õ=135, ñ/Ä/ö/Ö=-1, todos os demais
  campos intactos, round-trip build ok); MDL re-parse (184 parts, UVs/
  joints/XY conferidos; XY dos novos = XY do PERMA); GFX pixel-exato
  (origem PERMA → destino-vítima 0 divergências; fora das células 0
  mudanças). Preview renderizado `work/shell/preview_shellu_ptbr.png`.
- **Entrega**: `saida_shellu/R_SHELLU_PTBR.WAD` (4.965.744 B; SHA-256
  c275e2399522d131a3eb7e085f4ed4bd860aad9ba7f1bea1a36efb396d7f757c) +
  LEIA-ME_SHELLU.txt. Instalar: renomear para R_SHELLU.WAD (backup antes).
- **TESTE PCSX2 (2026-09-17)**: menus OK com acentos; MAS banner dourado
  continuou "OPÇES" e status das urnas não apareceu. CAUSA RAIZ achada:
  o banner e os textos de GAMEPLAY usam a FLP_HUDU (dentro do R_PLOCU!),
  que não tinha os 4 glifos. Comparação com o FLP_HUDA do PERMA US
  (funcionando) mostrou o mesmo esquema 136 glifos/ã=132… e que os únicos
  IDs de msg do set US ausentes do EU eram 36-45.
- **PLOCU v2 entregue (`saida_plocu/R_PLOCU_PTBR.WAD`, 1.053.552 B,
  SHA-256 35f7d247b9db7f4c…)**: mesmo esquema de células-vítima aplicado à
  FLP_HUDU/MDL_HUDU_0 (parts 410-413, clones das letras 61/35/75/49,
  joints 62/36/76/50 — estrutura idêntica ao shell, blocos 224B/raw 156B)
  + GFX pintada + msgs 36-45 RECOLOCADAS no MSGS_TXT (antes do padding
   final; 798 corpos intactos). Banner *4006*="Opções"/*4600*="Status"
  renderizam pela HUDU → consertam-se sozinhos. AGUARDA TESTE.
  ARMADILHA: no patcher do PLOCU, VITIMAS deve ser consultado via
  VITIMA_DE (til->vitima); indexar pelo char do til zera ã/Ã/õ/Õ em vez
  das vítimas (bug pego na validação, corrigido).
  Se o status das urnas AINDA faltar após a v2: aí é consulta de ID em
  registrador (engenharia reversa de código, muito mais difícil).
- **TRAVAMENTO no boot (2026-09-17, CORRIGIDO)**: a 1ª build da PLOCU v2
  (SHA 35f7d247…) CONGELAVA o jogo na tela "SCE Europe presents". Causa:
  mats dos 4 glifos novos com (0xFFFFFFFF, 0) — a FLP_HUDU usa
  (0xFFFFFFFF, 3) para TODOS os glifos (e o patch US também); soff=0 é
  dereferenciado no boot e derruba o jogo. A FLP_ShellU usa soff=0 (por
  isso o shell nunca travou). REGRA: mats de glifo novo = copiar o soff
  do último glyph existente da fonte, NUNCA valor fixo. v2 correta:
  SHA-256 4b83800097943185f7f799e9102521d88a6e69ac9bc7644d84cdd0776563a2ad
  (1.053.552 B). Validada contra a FLP_HUDA US campo a campo (chars/
  mesh_refs/mats/widths/cmap dos glifos 132-135 idênticos). MESMO COM
  ISSO AINDA TRAVOU → 2ª suspeita: MSGS 36-45 APPENDADAS no FIM do
  arquivo (ordem física ...7100,36,37... quebra a ordem crescente de
  IDs; o set US que funciona é totalmente ordenado). V3 entregue
  (SHA 0e2e91b8…): 36-45 inseridas ENTRE *35* e *100* (ordenadas,
  espelhando o US) + fonte; e TESTE-DIAG_PLOCU.WAD (SHA 247724be…,
  1.053.264 B) = só FLP/MDL/GFX patchados, MSGS v1 original — para
  isolar a causa se a v3 travar (diag liga → culpa é das msgs;
  diag trava → culpa é da fonte/mesh → bisecar FLP vs MDL).
  Lições: (1) inserir mensagens SEMPRE em posição ordenada por ID;
  (2) mats de glifo novo = herdar soff da fonte; (3) diff cirúrgica
  byte a byte (regiões esperadas) exonerou FLP/MDL estruturalmente.

---

### Sessão 10 (2026-09-22) — suporte ao R_SHELL do GoW I / `FLP_Shell`
Pedido: analisar o shell GoW1 já traduzido e fazer a tool ler seus textos, que
não apareciam na lista de recursos.

- **Descoberta (confirmada no `LOCALIZATION.md` do god_of_war_browser):** o
  `R_SHELL.WAD` do GoW I não tem `msgs_*.txt`/`MSGS_TXT`. Todo texto do menu
  principal é StaticLabel dentro de `FLP_Shell`, isto é, uma lista de comandos
  de desenho com `glyph id + avanço`. Não era falha de encoding nem TXT oculto.
- **Amostra real analisada:** `R_SHELL.WAD` PT-BR fornecido pelo usuário:
  3.034.480 B, 1.010 tags, zero recursos TXT candidatos; `FLP_Shell` na tag
  138, 175.788 B, magic `0x21`, 1 fonte, 120 StaticLabels. Leitura conferida
  para `= Selecionar`, `Opções`, `Vibração:`, `Exército de Hades`,
  `Espartano (Difícil)` e avisos multilinha.
- **Implementado no núcleo:** `FLPMovieGoW1`, baseado no parser do browser:
  header de 0x60 B; GH count @0x0C, refs @0x14, fonts @0x1C, statics @0x24;
  referência de mesh/material em +0/+2; font `chars/flags` em +0/+0x0C;
  StaticLabel header de 0x24 B, tamanho do stream em +0x14. A factory
  `open_flp_movie()` escolhe GoW1 (magic 0x21) ou GoW2 (0x1B).
- **Acentos:** `decode_ids()` deixou de restringir o char_map a ASCII. Índices
  CP1252 são mostrados como Unicode visual, portanto 0xE3/0xE9/0xE7 viram
  `ã`/`é`/`ç` na UI. A conversão inversa para o char_map também aceita CP1252.
- **UI inicial (substituída pelo fluxo direto da Sessão 11):** WADs sem TXT
  passaram a abrir normalmente e o diálogo `Ferramentas > Rótulos desenhados
  do filme (FLP)...` mostrava `FLP_Shell • GoW1`. Labels de vários blocos são
  legíveis (separadas por `↵`) mas continuam somente leitura. Um bloco continua
  editável e preserva cabeçalho, avanços conhecidos e o resto do FLP bruto.
- **Validação feita:** `Opções -> Menu` aplicado em memória pela UI offscreen,
  reparseado como GoW1 e reembutido no WAD; todas as outras tags serializadas
  permaneceram byte-idênticas. O no-op `Opções -> Opções` mantém o FLP inteiro
  byte-idêntico. `tests/test_gow1_flp.py` usa FLPs sintéticos sem assets do
  jogo e cobre despacho GoW1/GoW2, acentos, no-op e edição/reparse. Teste em
  PCSX2/hardware do WAD salvo ainda é pendente.

### Sessão 11 (2026-09-22) — `FLP_Shell` direto na tela principal
Pedido do usuário após validar a primeira UI: eliminar o passo complexo
`Ferramentas > Rótulos desenhados...` e abrir os textos do shell diretamente
na área **Mensagens**.

- **Fluxo novo:** se o WAD não tiver TXT e tiver FLP com StaticLabels, a lista
  esquerda passa a conter `FLP_Shell • GoW1 • 120 rótulos`; a coluna central
  mostra `[índice] texto`, aceita filtro por índice/conteúdo e a direita abre o
  texto selecionado. Para `R_SHELL.WAD`, a seleção inicial é `[0] = Selecionar`.
- **Edição segura no mesmo fluxo:** títulos de painel mudam para **FILMES /
  RÓTULOS**, **RÓTULOS DESENHADOS** e **TEXTO DO RÓTULO**. O botão vira
  **Aplicar rótulo**; ele usa `encode_label()` e reabre o FLP. Na versão
  inicial da Sessão 11, multi-blocos ficavam somente leitura; isso foi
  substituído pela edição por linha da Sessão 13.
- **Controles TXT que não fazem sentido no FLP** são desativados (+Nova,
  Duplicar, Excluir, codificação, importar/exportar, localizar/substituir e
  undo/redo global). O Ctrl+Z do campo ainda serve antes de aplicar; salvar é
  sempre pelo WAD inteiro/Salvar como.
- **Compatibilidade:** WADs com TXT continuam no modo normal; FLPs desses
  WADs seguem acessíveis no diálogo avançado de Ferramentas. Ao acioná-lo em
  um shell já no modo principal, o foco retorna para a lista em vez de abrir
  um diálogo redundante.
- **Validação UI:** smoke test offscreen no R_SHELL real confirmou 1 recurso
  `FLP_Shell`, 120 linhas, `Opções -> Menu` pela tela principal e label [9]
  multilinha bloqueado. Regressão offscreen com WAD GoW1 sintético contendo
  `TEST.TXT` confirmou 2 mensagens e todos os controles TXT no modo normal.
  O WAD real fornecido não foi gravado.

### Sessão 12 (2026-09-22) — pacote Windows/EXE atualizado
Pedido do usuário: compilar/entregar a tool atualizada como executável Windows.

- **Entrega criada:** `tool/GodOfWarTextEditor_Aprimorado_2026-09-22_EXE.zip`
  (33.593.905 B; SHA-256
  `429cc7c1542cea96078b3fe8604c4a0c4afda0e9abc7e4f285cb65831a2e907b`).
  O ZIP contém a pasta `GodOfWarTextEditor_Aprimorado_2026-09-22/`, o launcher
  `GodOfWarTextEditor.exe` x64, `gow_text_editor.py` da Sessão 11,
  `LEIA-ME.txt`, ícone/fundo e `app\\` com Python 3.13.1 + PySide6 6.11.2.
- **Launcher:** o binário PE continua com SHA-256
  `7c43368fd54d101fa0d3400d63dc8ac122782f2702f2e2248156497858dde950`.
  Ele já procura `app\\python.exe` e `gow_text_editor.py` ao lado; não precisava
  mudar só porque a lógica Python mudou. A distribuição foi reconstruída com
  a fonte atual e o runtime portátil completo, pronta para duplo clique após
  extrair a pasta inteira.
- **Validação de pacote:** `unzip -t` passou; hashes da fonte dentro/fora do
  ZIP coincidem (`gow_text_editor.py`:
  `621db615f50e18857cdd1e0a4d673c7267bca0f87f03e7f251864f4a15296c4a`);
  scan confirmou ausência de WAD, `.bak`, `.ini` ou log no pacote. O WAD real
  de referência não foi incluído nem escrito.
- **Limite conhecido:** executável/ZIP foi validado estruturalmente; o teste
  de um WAD editado salvo no PCSX2/hardware ainda continua pendente antes de
  distribuir qualquer WAD resultante.

### Sessão 13 (2026-09-22) — StaticLabels multilinha editáveis
Problema reportado pelo usuário após abrir o EXE: avisos do shell, como
`Modo Progressivo\nfoi alterado.`, apareciam como **somente leitura** porque
possuem 2+ RenderCommands/linhas dentro do mesmo StaticLabel.

- **Verificação de formato antes de alterar:** `staticlabel.go` do
  `god_of_war_browser` confirma que `MarshalRenderCommandList()` escreve um
  cabeçalho de comando e uma lista de glifos para **cada** RenderCommand;
  `MarshalStruct/MarshalData` conserva o tamanho cru GoW1 e pad4 externo.
  No R_SHELL real, label [93] tem dois cabeçalhos `0x8F`/`0x8B`, ambos com
  GH=12/fonte 0 e X/Y próprios; label [91] tem cinco. Portanto é seguro
  reemitir cada linha no bloco correspondente, sem fundi-las.
- **Implementação:** `parse_commands()` agora guarda `header_end`. `label()`
  expõe `line_count` e torna editáveis blocos com fonte/glifos resolvidos.
  `encode_label()` normaliza LF, exige exatamente a mesma quantidade de
  linhas, copia o cabeçalho de cada bloco byte a byte e reconstrói somente sua
  contagem/lista de `(glyph, advance)`. Avanços existentes são preservados e
  glyphs novos recebem largura natural multiplicada pelo fator daquele bloco.
  Linha extra/removida, linha vazia, glifo ausente ou >255 glyphs é recusado.
- **UI:** todos os 120 labels do `FLP_Shell` real ficaram editáveis. Multilinha
  aparece como `• N linhas`, abre em `QPlainTextEdit` e mostra no status
  `mantenha N linhas (uma por bloco)`. O diálogo FLP avançado também migrou de
  `QLineEdit` para `QPlainTextEdit`, portanto não colapsa quebras de linha.
- **Validação:** novo teste sintético cobre no-op, edição de duas linhas,
  preservação de flags/GH/escala/X/Y e recusa de contagem diferente. No WAD
  real: no-op dos 120 labels foi byte-exato; label [93] editou/reparseou;
  label [9] de 3 linhas editou/reparseou e uma serialização/reabertura do WAD
  preservou todas as tags não-`FLP_Shell`. UI offscreen confirmou [93] e [91]
  editáveis; modal avançado sintético confirmou multilinha. O WAD fornecido
  nunca foi salvo/modificado.
- **Entrega R2:** `tool/GodOfWarTextEditor_Aprimorado_2026-09-22_R2_EXE.zip`
  (33.596.031 B; SHA-256
  `cdb7dd3d3f4d09ab913347528f5ba88d69e1e77ddda77655b2734ad513c674bd`).
  Contém o launcher x64 + runtime portátil da Sessão 12 e a fonte da Sessão
  13 (`gow_text_editor.py` SHA-256
  `774104bdef33628bc89e6f199203a0f4b92333eb7de082e18e9e492bea605b0f`).
  `unzip -t` passou; não há WAD, `.bak`, `.ini` ou log no ZIP.

### Sessão 14 (2026-09-22) — TXT + StaticLabels FLP juntos na tela principal (R3)
Pedido do usuário: em WADs GoW1 como `R_PERM`/`R_PERMA`, `Curiosidade.txt` e
`MSGS_en.txt` continuavam visíveis na tela principal, mas `FLP_HUD` só aparecia
no diálogo avançado porque a UI anterior só montava `main_flp_resources` quando
**não** havia TXT. O pedido foi manter os TXT e acrescentar os FLPs navegáveis
na mesma lista de recursos.

- **Implementação:** `load_wad_path()` agora coleta todos os FLPs parseáveis com
  StaticLabels independentemente de haver TXT. A nova lista virtual
  `main_resource_entries` guarda pares `("txt", índice em text_resources)` ou
  `("flp", índice em main_flp_resources)`. O painel esquerdo lista primeiro os
  TXT normais e depois itens como `FLP_HUD • StaticLabels • GoW1 • N rótulos`.
- **Troca segura de contexto:** `on_resource_change()` resolve a entrada virtual
  antes de carregar. `load_resource()`/`load_flp_resource()` fazem a conversão
  inversa para selecionar a linha visual certa. Codec, commit, undo global TXT,
  parse interno, localizar/substituir e `_goto_message()` deixaram de assumir
  que `resource_box.currentIndex()` era um índice direto de `text_resources`.
- **Fluxo visível:** ao clicar em `FLP_HUD`, a lista central vira
  **RÓTULOS DESENHADOS** e a direita usa o mesmo `QPlainTextEdit`/Aplicar rótulo
  seguro da Sessão 13. Ao voltar a `Curiosidade.txt`/`MSGS_en.txt`, voltam as
  mensagens TXT e seus controles. O título do painel passa a
  **RECURSOS / RÓTULOS** quando o WAD possui ambos os tipos.
- **Segurança:** a substituição em lote continua propositalmente limitada a TXT.
  Fazer uma troca cega em vários StaticLabels exigiria validar por rótulo os
  glifos da fonte e a contagem de blocos; no FLP, o usuário usa o filtro e edita
  um rótulo por vez. A regra multilinha permanece: não adicionar/remover/reordenar
  linhas e preservar RenderCommands, âncoras, escala, cor, flags e fontes.
- **R_SHELL somente leitura:** a captura do usuário com a frase “edição ainda é
  suportada apenas para 1 bloco” foi identificada como o pacote R1 antigo. A R2
  e esta R3 mantêm `[93] Modo Progressivo / foi alterado.` editável quando os
  glifos/fonte são resolvidos; não foi atribuída uma causa em bytes ao R_PERMA,
  pois o WAD correspondente não foi disponibilizado nesta sessão.
- **Regressão:** `tests/test_gow1_flp.py` ganhou um WAD sintético GoW1 com
  `Curiosidade.txt` + `FLP_HUD`; o teste Qt carrega a janela, edita TXT, troca
  para FLP, edita o label, desfaz o TXT enquanto o FLP está ativo e volta ao TXT.
  Resultado com runtime Qt offscreen: **6/6 OK**. O smoke no `R_SHELL.WAD` real
  confirmou 1 FLP/120 labels, `[93]` editável e no-op byte-exato; SHA-256 do WAD
  de referência permaneceu `f7aa847414922256c501b00bd682e6ea11223be3448d9a2aad41cfc76633488c`.
- **Entrega R3:** `tool/GodOfWarTextEditor_Aprimorado_2026-09-22_R3_EXE.zip`
  (33.749.916 B; SHA-256
  `b9b9d559ad927e3e04f7492478122c9df9bb31c7e0ee8619ea81db20dbc8add4`).
  Fonte incorporada `gow_text_editor.py` SHA-256
  `d4cbac8c3831e652c9a5042448b8f71cc03b4f3b2a493246ed8ec52d17612d57`.
  `unzip -t` passou e a inspeção confirmou ausência de `.wad`, `.bak`, `.ini`
  e `.log`. Nenhum WAD do usuário foi gravado ou incluído.

### Sessão 15 (2026-09-22) — sincronização do contexto e acesso de escrita ao GitHub
O usuário autorizou o acesso de escrita ao repositório oficial e pediu que o
contexto do GitHub recebesse as informações novas da R3.

- **Repositório/branch confirmados:** `gushetfield-81/GOW-TEXT-EDITOR`, branch
  `main`. O acesso HTTPS de escrita foi validado antes de publicar; nenhuma
  credencial foi adicionada ao repositório, à URL remota ou à documentação.
- **Primeiro push da R3:** commit
  [`ff0461bd78b32c1f49e868727f87e790d6dde439`](https://github.com/gushetfield-81/GOW-TEXT-EDITOR/commit/ff0461bd78b32c1f49e868727f87e790d6dde439),
  mensagem `feat: exibe TXT e StaticLabels FLP juntos na tela principal`.
  Ele adicionou/atualizou a fonte da R3, o ZIP portátil, `tests/test_gow1_flp.py`,
  README, este contexto, LEIA-ME e regras de `.gitignore` que impedem WADs,
  backups, INIs e logs de serem versionados.
- **Integridade atual da entrega publicada:**
  `GodOfWarTextEditor_Aprimorado_2026-09-22_R3_EXE.zip` tem 33.749.116 B e
  SHA-256 `b9b9d559ad927e3e04f7492478122c9df9bb31c7e0ee8619ea81db20dbc8add4`.
  A fonte embutida tem SHA-256
  `d4cbac8c3831e652c9a5042448b8f71cc03b4f3b2a493246ed8ec52d17612d57`.
- **Validação repetida antes desta atualização:** `py_compile` passou; a suíte
  sintética teve 5 testes de núcleo OK e 1 smoke Qt condicional ignorado neste
  ambiente sem PySide6. O teste central real, somente leitura, reabriu o
  `R_SHELL.WAD` fornecido: GoW1, `FLP_Shell`, 120 rótulos, `[93]` multilinha
  editável e no-op byte-exato. O SHA-256 do WAD continuou
  `f7aa847414922256c501b00bd682e6ea11223be3448d9a2aad41cfc76633488c`.
- **Espaço de trabalho/local:** para manter a R3 portátil disponível no Arena,
  o usuário autorizou remover apenas cópias técnicas/históricas locais: ZIP R1
  obsoleto, clone/bare repo temporário e espelho local do browser. R2, R3,
  código-fonte, testes, documentação e todos os WADs do usuário foram mantidos.
  Isso não remove conteúdo já publicado no GitHub.
- **Estado naquela data:** a aba **GitHub Releases** ainda não tinha sido
  alterada; a Sessão 16 abaixo resolve essa pendência sem tocar na release
  rascunho/legada criada pelo usuário.

### Sessão 16 (2026-09-22) — release pública obrigatória a cada entrega da tool
O usuário determinou que a versão mais recente da tool deve ficar na aba
**Releases** e que, de agora em diante, toda mudança entregue na tool deve ser
publicada ali automaticamente.

- **Release atual publicada e verificada:** [`v2026.09.22-r3`](https://github.com/gushetfield-81/GOW-TEXT-EDITOR/releases/tag/v2026.09.22-r3),
  título **God of War Text Editor — 2026-09-22 R3**, pública (`draft=false`,
  `prerelease=false`), criada sobre o commit
  `7d398f74ef8e2820ffbc83ee01390a82a1c37596`. Ela anexa exatamente
  [`GodOfWarTextEditor_Aprimorado_2026-09-22_R3_EXE.zip`](https://github.com/gushetfield-81/GOW-TEXT-EDITOR/releases/download/v2026.09.22-r3/GodOfWarTextEditor_Aprimorado_2026-09-22_R3_EXE.zip)
  (33.749.116 B; SHA-256
  `b9b9d559ad927e3e04f7492478122c9df9bb31c7e0ee8619ea81db20dbc8add4`).
  A release rascunho/sem tag **GOW TEXT EDITOR** e a release `v1.0` são
  preservadas, sem sobrescrita ou remoção.
- **Regra obrigatória para o futuro:** depois de cada alteração que gere uma
  entrega da tool: (1) rodar validações; (2) gerar ZIP versionado contendo a
  pasta portátil completa e LEIA-ME; (3) calcular/registrar hashes; (4) fazer
  commit e push para `main`; (5) criar uma **nova release pública, não draft**
  com tag única no formato `vAAAA.MM.DD-rN`, anexando o ZIP; (6) atualizar
  README e este contexto com link, tag, hash e resultado. Nunca substituir um
  asset de release anterior, nem incluir WADs, `.bak`, `.ini`, logs ou tokens.
- **Escopo de uma release:** ela só é criada quando uma mudança afeta a tool,
  seu pacote, seu comportamento ou sua documentação de uso. Alterações sem
  relação com a tool exigem confirmação do usuário antes de criar uma versão.

---

## 5. FORMATOS BINÁRIOS (conhecimento consolidado nas sessões)

### 5.1 WAD (núcleo da tool, já documentado no código)
Tag header 0x20 (`<HHI` tag/flags/size + nome 24B), alinhamento 0x10, `EntityCount`
sem corpo, GoW2 header tag 0x15; `serialize()` devolve o segmento original se nada
mudou (garantia byte-exata).

### 5.2 FLP GoW2 (portado em `flp_gow2.py`; base: god_of_war_browser/pack/wad/flp)
- Header 0x5C; magic inicial = FileFormatId dword (0x1B no Shell);
- counts: 0x38 globalHandlers, 0x3C meshPartRefs, 0x40 fonts, 0x44 staticLabels,
  0x48 dynamicLabels, 0x4C datas6, 0x50 datas7, 0x54(word) transformations,
  0x56(word) blendColors, 0x58 dword stringsSize;
- **ordem física:** globalHandlers(4B cada) → refs: TODOS os headers 8B primeiro
  (meshPartIndex int16 @+4, matCount u16 @+6), DEPOIS todos os materiais 8B
  (color u32 + stringOffset u32) → font headers 0x24
  (charsCount u32 @+0x10, float @+0x14, size i16 @+0x1A, flags u16 @+0x20) →
  por fonte: refs headers 8B + materiais 8B + symbolWidths i16×N + pad4 +
  charMap i16×(256 se flags&1, senão N) + pad4 → static (0x1C + renderBuffer) →
  dynamic (0x20) → datas6/datas7/data8 → transformations/blendColors → strings;
- strings section começa em `len - stringsSize`; material stringOffset indexa nela;
- **round-trip exato confirmado** (FLP_ShellA e FLP_HUDA reconstruem byte a byte).
- Fonte flags 0x5 = mapa 256 entradas + refs com material por glifo.

### 5.3 FLP GoW1 / `FLP_Shell` (Sessão 10; base: god_of_war_browser)
- Magic `0x21`, header físico de **0x60 B** (GoW2 usa `0x1B`/0x5C).
- Counts usados pelo editor: globalHandlers @0x0C, meshPartRefs @0x14,
  fonts @0x1C, staticLabels @0x24, dynamicLabels @0x2C e stringsSize @0x58.
- Cada MeshPartReference continua com 8 B, mas no GoW1 o `meshPartIndex` está
  em +0 e `matCount` em +2 (no GoW2 eles ficam em +4/+6).
- Font header continua 0x24 B; no GoW1 `charsCount` fica em +0 e `flags` em
  +0x0C. As larguras e o char_map seguem o mesmo alinhamento de 4 B.
- StaticLabel: header de **0x24 B**; transformação em +0 e tamanho cru do
  render-command stream em +0x14. O stream é alinhado externamente em 4 B;
  ao editar, o editor mantém o tamanho cru no header e só então acrescenta
  padding. Isso espelha `StaticLabel.MarshalStruct/MarshalData` do browser.
- Comando de desenho é o mesmo: `0x80|flags`, campos opcionais e depois
  contagem u8 + pares `(glyph u16, advance i16/16)`. Vários comandos são
  linhas/blocos distintos. O editor os reemite um a um, preservando os
  cabeçalhos/âncoras, e exige que a edição tenha o mesmo número de linhas.

### 5.4 Mesh GoW2 (`MDL_*_0`, magic 0x0001000F)
- Header 0x18: magic, mdlCommentStart u32@4, partsCount u16@8, offsets u32@0x18+N*4;
- sem vetores nos meshes de fonte (offsets dos parts começam logo após a tabela);
- tail após `mdlCommentStart`: nome "isAnimated" + KeepJoint (80 bytes no Shell);
- **Part:** `[unk00 u16][ngroups u16][groupOffsets u32×N][jointId u16]` — nos glyphs
  do Shell: jointId = idx+1;
- **Group (8B header):** hideDistance f32 (=-34359738368.0 nos glyphs), objectsCount
  u16@+4, hasBbox u32@+8, tabela de offsets u32 dos objetos;
- **Object (header 0x20 + raw + jointmaps):** type u16 (0xE nos glyphs), dmatpp u32@4
  (=2), materialId u16@8 (=partIdx nos glyphs do Shell), jointMapElementsCount u16@0xA
  (=1), instances u32@0xC, flags u32@0x10 (=0), flagsMask u32@0x14 (=0xFFFFFF35),
  textureLayers u8@0x18 (=1), dmaPrograms u8@0x19 (=1), nextFreeVUBufferId u16@0x1A
  (=1), unk1c u16@0x1C, sourceVerticesCount u16@0x1E (=4);
- **Raw DMA do glyph = template fixo de 156 bytes** (ver `preparedMeshDmaPacketData`
  no bmfileimport.go do browser): UVs i16 @0x38 (u@+0, v@+2, por vértice ×4,
  **escala ×4096**), XYs i16 @0x4C (x@+0, y@+2, stride 8, **escala ×16**), dword da
  joint @0x20; vértices em ordem: (1,1),(0,1),(1,0),(0,0);
- clonar um part = copiar o bloco do part inteiro (224 bytes no Shell) e trocar
  UVs/joint no raw; `with_appended_parts()` em `adicionar_acentos_shell.py` refaz
  header/tabela de offsets/mdlCommentStart.

### 5.5 GFX/PAL/TXR (textura PS2)
- GFX (magic 0xC): w u32@4, h u32@8, encoding u32@0xC, bpi u32@0x10, blocks u32@0x14,
  dados a partir de 0x18 (RealHeight = h/blocks);
- **atlas da fonte: 256×256 PSMT4 (4bpp)** — PALETA de 16 cores em RGBA8888
  (alpha 0-128 → 0-255: `a*255//128`);
- **AVISO (dor de cabeça resolvida):** o decode da atlas da fonte que funciona é o
  com **swizzle do GS** (`IndexUnswizzleTexture` do browser — mesmo código para
  PSMT8/PSMT8H). Leitura linear produz ruído. NÃO trocar de novo (houve idas e
  vindas na Sessão 4; o patcher final usa swizzle + cópia cirúrgica por célula);
- TXR (88B, magic 7): nomes GFX/PAL @4/@28 (24B cada), flags @84 (0x510000 na fonte);
- PAL (magic 0xC): 256×2 (altura 2 = 16 cores swizzladas com remap [0,2,1,3]).

---

## 6. VALIDAÇÃO (roteiro padrão após qualquer mudança)

```bash
# 1) compilação
python3 -m py_compile \
  tool/GodOfWarTextEditor_Aprimorado_2026-09-12/gow_text_editor.py \
  tests/test_gow1_flp.py

# 2) testes sintéticos versionados (não exigem WAD proprietário)
python3 -m unittest discover -s tests -v
# Inclui despacho FLP GoW1/GoW2, acentos CP1252, no-op byte-exato, edição/
# reparse, preservação de cabeçalhos/âncoras multilinha e WAD sintético com
# TXT + FLP_HUD coexistindo. Com PySide6 disponível, também executa o smoke
# Qt TXT -> FLP -> TXT e a verificação de undo/mapeamento de índices.

# 3) validação real, somente em cópia privada de WAD
# - abrir R_SHELL.WAD; confirmar 120 labels no FLP_Shell;
# - editar um rótulo de 1 bloco e um multilinha (mantendo N linhas),
#   Salvar como..., reabrir e testar em PCSX2;
# - diff: só a tag FLP editada pode mudar.

# 4) UI offscreen (sandbox: PySide6 + libxkbcommon +
#    QT_QPA_PLATFORM=offscreen + GOW2TE_INI=/tmp/gow_test.ini)
# - abrir por load_wad_path() um WAD sem TXT e conferir FLP_Shell/120 rótulos;
# - abrir WAD sintético ou cópia privada com TXT + FLP_HUD, alternar TXT -> FLP
#   -> TXT e confirmar que aplicar/undo/navegação usam o recurso correto;
# - editar um bloco e um rótulo multilinha mantendo a mesma contagem de linhas.
```

No Windows do usuário: `python -m pip install PySide6` + `python gow_text_editor.py`.

---

## 7. LIMITAÇÕES / PENDÊNCIAS CONHECIDAS

- Sandbox Linux: sem root p/ `libxkbcommon.so.0` (contorna-se com a lib embutida do
  opencv via LD_LIBRARY_PATH; no Windows não é problema).
- O `GodOfWarTextEditor.exe` atual (Sessão 5, método canônico) é um **launcher** —
  precisa da pasta `app\` (runtime) ao lado, ou de Python+PySide6 no sistema.
  Reconstruir o exe (só se mudar o C): `arquivados/launcher.c` + builder do
  objeto `.rsrc` + `lld-link` (receita completa no changelog da Sessão 5).
  Mudanças no editor NÃO exigem recompilar: o exe sempre roda o
  `gow_text_editor.py` da pasta. Validar sempre no Wine antes de entregar.
- `R_SHELLA_PTBR.WAD` aguarda **teste em jogo** pelo usuário (menus com ã/Ã/õ/Õ);
  o .EXE também aguarda teste em Windows real (ícone + duplo clique).
- StaticLabels multilinha agora preservam os blocos existentes, mas não
  suportam **adicionar/remover/reordenar** linhas automaticamente: mantenha a
  contagem original. Labels com fonte/glifos não resolvidos continuam somente
  leitura até existir uma estratégia específica para eles.
- O suporte ao `R_SHELL.WAD` foi validado estruturalmente e pela UI offscreen;
  falta o teste de um WAD salvo no PCSX2/hardware antes de distribuir a saída.

---

## 8. REGRAS PARA SESSÕES FUTURAS (acordo com o usuário)

- **GitHub do projeto (desde 2026-09-16):** `github.com/gushetfield-81/GOW-TEXT-EDITOR`,
  branch `main`. **Regra explícita do usuário desde a Sessão 16:** toda mudança
  entregue na tool deve, na mesma rodada, ser validada, commitada, enviada e
  publicada como uma nova **release pública não draft** com o ZIP portátil
  atual anexado. Usar tag única `vAAAA.MM.DD-rN`; nunca sobrescrever releases
  ou assets anteriores. Registrar URL, tag, tamanho e SHA-256 no README e neste
  contexto. A release rascunho sem tag `GOW TEXT EDITOR` e a `v1.0` pertencem
  ao usuário e devem ser preservadas. Token fine-grained pode ficar somente em
  `/home/user/.github_token`: nunca versionar, colocar em URL remota ou expor
  em documentação/chat. WADs, `.bak`, `.ini` e logs NUNCA vão ao repositório.

1. **SEMPRE** atualizar este arquivo (ou gerar `CONTEXTO_MESTRE_YYYY-MM-DD.md` novo)
   ao final de qualquer alteração na tool, com changelog + estado atual.
2. NÃO alterar o núcleo WAD/encoding validado em jogo sem necessidade explícita;
   mudanças de UI/cosmética ficam isoladas (paleta/stylesheet/menus/config).
3. Toda validação passa pelos testes da seção 6 antes de entregar.
4. Novos recursos "de pasta" (como fundo e ícone) seguem o mesmo padrão:
   pasta ao lado da tool + nome fixo do arquivo + menu em `Visualizar` +
   `Definir/Recarregar/Remover(.off)` + persistência no INI.
5. Entregas empacotadas em `.zip` com a pasta completa + `LEIA-ME.txt` atualizado.
6. Créditos sempre preservados: `Tool By: Gus Hetfield` / `Special Thanks: Mogaika`.

---

## 9. MAPA DO WORKSPACE DESTA SESSÃO

```
/home/user/
├── CONTEXTO_MESTRE_GOW_TEXT_EDITOR.md                    <- ESTE arquivo (v3.0)
├── GOW-TEXT-EDITOR/
│   ├── README.md, tests/test_gow1_flp.py, patchers/, entregas/, previews/
│   └── tool/
│       ├── GodOfWarTextEditor_Aprimorado_2026-09-22_R3_EXE.zip <- ENTREGA atual
│       ├── GodOfWarTextEditor_Aprimorado_2026-09-22_R2_EXE.zip <- histórico multilinha
│       ├── GodOfWarTextEditor_Aprimorado_2026-09-12_EXE.zip    <- histórico / v1.0
│       └── GodOfWarTextEditor_Aprimorado_2026-09-12/           <- FONTE ATUAL
│           (gow_text_editor.py, launcher EXE, TTF, LEIA-ME, ícone e fundo)
├── uploads/  <- R_SHELL.WAD.txt original de referência + capturas do usuário
└── RELATORIO_AUDITORIA_GOW_TEXT_EDITOR_2026-09-22.md

Arquivos removidos localmente com autorização do usuário para caber a entrega
R3 no workspace: ZIP R1 obsoleto, clone/bare repo técnico e espelho local do
`god_of_war_browser`. O código relevante do browser já está documentado neste
contexto; a cópia original pode ser clonada novamente quando necessária.
```

Observação: o conteúdo de `app\` (Python+PySide6 strip) NÃO persiste no
workspace — fica só dentro do ZIP de entrega. Refazer via Sessão 5 (changelog)
se precisar regerar o pacote.

*Fim do documento — manter este formato nas próximas revisões.*

## Lição adicional — FLP das skins / limite de linhas (2026-09-21)
- No MSGS_TXT do R_PERMA, IDs 5101–5107 usam exatamente duas linhas: linha 0 = nome da skin; linha 1 = habilidade.
- A tela de skins usa DynamicLabels do FLP para esses dois campos. Uma terceira linha da mesma mensagem não aparece porque o código do jogo só solicita/atribui os dois campos; serializar o FLP permite editar layout, labels e scripts de apresentação, mas não altera a rotina nativa que separa a mensagem nem cria automaticamente um terceiro valor.
- O limite de ~64 caracteres é do campo/label da habilidade. Para exibir duas habilidades seria necessário alterar também a lógica no ELF (ou encontrar um campo já existente que a rotina preencha), não apenas o FLP/MSGS_TXT.
- O browser do Mogaika suporta parse/serialize do FLP e decompilação/recompilação de scripts de apresentação; isso não equivale a recompilar as funções nativas do ELF.
