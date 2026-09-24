# God of War Text Editor — 2026-09-24 R7

> **Status:** publicado no GitHub em 2026-09-24 como
> [`v2026.09.24-r7`](https://github.com/gushetfield-81/GOW-TEXT-EDITOR/releases/tag/v2026.09.24-r7). O ZIP anexado é o mesmo asset
> validado localmente; nenhum WAD de entrada foi publicado.

## Asset preparado

- `GodOfWarTextEditor_Aprimorado_2026-09-24_R7_EXE.zip`
- Tamanho: **33.615.425 bytes**
- SHA-256: `88c1ef57acda7b5bd013e03581d179deaa09f9468e04663ac3726a794edce7aa`

## Correção de interação: cores WYSIWYG no próprio texto

A R7 substitui a tabela externa abaixo do editor como fluxo principal. Ao abrir
ou circular por um texto, os próprios glifos da caixa **TEXTO DA MENSAGEM**
recebem a cor base física associada e continuam sendo texto puro/editável.

No cabeçalho da mesma caixa há agora:

- **COR BASE:** seletor das instâncias/campos físicos que podem pintar a linha
  sob o cursor;
- botão RGBA com amostra da cor: abre a edição do campo sem abandonar a
  mensagem/rótulo atual;
- indicação das animações BlendColor que também alcançam o texto.

A pintura é feita por `QSyntaxHighlighter`; portanto não insere tags, rich text
ou bytes extras no `MSGS_TXT`/StaticLabel. A atualização bloqueia sinais de
formatação do documento, evitando a recursão de `textChanged` durante a
recoloração.

### StaticLabels FLP GoW2

- Cada bloco recebe somente a cor direta do `RenderCommand` realmente associado
  a esse bloco.
- O campo selecionado edita exatamente seus 4 bytes RGBA.
- Caso haja texto pendente no StaticLabel, ele é consolidado antes do patch;
  os caracteres abertos no editor permanecem intactos.

### `MSGS_TXT` GoW2

- O vínculo continua sendo o comprovado pelo runtime: linha/página sob o cursor
  → `PS2_MessageTemplate_Line1..Line5`.
- Todas as instâncias físicas/estados de `DynamicLabel` de cada `LineN` ficam
  selecionáveis. Trocar a instância redesenha a linha ativa na cor daquela
  instância e a edição toca somente seus 4 bytes BGRA.
- Linhas vazias e o separador `--` não recebem uma associação inventada.
- TXT sem ser `MSGS_TXT` permanece explicitamente sem vínculo FLP não provado.

### BlendColors

`BlendColor` representa animação por KeyFrame, não uma única tinta estática.
A R7 mostra a cor base editável nos glifos e a quantidade de BlendColors que
também alcançam o texto; não simula uma aparência física inventada. A inspeção
avançada de animações segue disponível em **Ferramentas → Cores de texto do
FLP…**.

## Segurança

- DynamicLabel: somente 4 bytes BGRA.
- StaticLabel: somente 4 bytes RGBA.
- A recoloração da UI não altera texto nem WAD.
- O WAD só é persistido por **Salvar WAD como…**; os WADs de entrada foram
  tratados somente em leitura.

## Validação R7

- `py_compile` da fonte R7 aprovado.
- Suíte completa com PySide6/Qt offscreen: **18/18 testes aprovados**.
- O novo smoke R7 confirmou formatos de glifo efetivamente aplicados dentro do
  `QPlainTextEdit`, reinício de página em `--`, cursor `Line1 → Line2`, estados
  físicos `DynamicLabel` `{2, 37}`, seleção visual da instância alternativa,
  edição cirúrgica e texto puro preservado.
- Também confirmou `FLP_HUDA` StaticLabel com cor direta de `RenderCommand`,
  patch limitado a quatro bytes e texto preservado.
- Smoke adicional abriu `R_SHELLA`: `FLP_ShellA` GoW2 mostrou sua cor direta e
  informou 22 animações associadas sem tentar desenhá-las como cor fixa.
- `R_PERMA.WAD.txt` e `R_SHELLA.WAD.txt` mantiveram seus hashes de entrada.
- `unzip -t` aprovado; o ZIP contém o runtime portátil `app/python.exe`, não
  contém `.ini`, `.log`, `.bak` ou `__pycache__`, e a fonte extraída compila.

## Integridade da fonte no pacote

| Arquivo | SHA-256 |
|---|---|
| `gow_text_editor.py` | `fce152f0b8e1abd5998d139d5afeb91e6c77efec64d5ed765128fbd3a4d6ea0a` |
| `LEIA-ME.txt` | `a756b1a3ece813965e325622733847ed77c7a7ce15ff6ea2d5b019aaaedbfe12` |
| `GodOfWarTextEditor.exe` | `7c43368fd54d101fa0d3400d63dc8ac122782f2702f2e2248156497858dde950` |

## Créditos

Tool By: Gus Hetfield
Special Thanks: Mogaika
