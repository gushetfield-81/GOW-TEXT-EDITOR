# Associação de cores ao texto em edição — R6

## Objetivo

A R6 acrescenta um painel inline de cores à tela de edição. A regra de projeto
é conservadora: uma cor só é apresentada como associada a um texto quando o
vínculo é demonstrável pelo FLP ou pelo runtime; nunca por semelhança de nome,
ID numérico ou uma suposição visual.

## Dois vínculos implementados

### 1. StaticLabel de FLP GoW2

Quando o usuário seleciona um rótulo desenhado na tela principal, o alvo é o
índice físico `StaticLabel[n]` do FLP ativo.

O painel obtém:

- os campos RGBA próprios de cada RenderCommand do rótulo, inclusive os blocos
  posteriores que herdam a mesma cor;
- somente os `BlendColors[ColorId]` cujos KeyFrames alcançam o mesmo
  `StaticLabel[n]` pela árvore Data6/Data7/Data8;
- o número de referências de KeyFrame e a quantidade de outros textos que uma
  tinta compartilhada também atinge.

Assim, alterar uma cor direta afeta apenas seus 4 bytes RGBA. Alterar uma
BlendColor pode atingir mais de um texto — o painel mostra isso antes do botão
de edição ser usado.

### 2. `MSGS_TXT` do runtime Flash GoW2

Uma mensagem de `MSGS_TXT` não possui uma cor individual no próprio TXT. A
associação correta vem do runtime:

- o decompile registra `MessageTemplate_Line1` até `MessageTemplate_Line5` no
  `FlashInterface`;
- `DoMsgPage` preenche essas variáveis com as linhas da página;
- o código monta os nomes Flash `PS2_MessageTemplate_Line%d`;
- o `FLP_HUDA` contém DynamicLabels com esses mesmos nomes.

Por isso, para `MSGS_TXT`, a R6 usa a linha sob o cursor dentro da página:

| Cursor no editor | Campo FLP exibido |
|---|---|
| primeira linha de uma página | `PS2_MessageTemplate_Line1` |
| segunda linha | `PS2_MessageTemplate_Line2` |
| terceira linha | `PS2_MessageTemplate_Line3` |
| linha 4/5, quando existir estado correspondente | `PS2_MessageTemplate_Line4/Line5` |
| linha vazia ou `--` | todos os campos MessageTemplate potencialmente usados |

O `DoMsgPage` analisado limita a página normal a três linhas. Os campos 4/5
continuam expostos por serem DynamicLabels físicos existentes no FLP, não uma
previsão da UI.

## Resultado real em `FLP_HUDA`

O inventário confirmou instâncias distintas para o mesmo nome de variável:

- Linha 1: DynamicLabels **1** e **36**;
- Linha 2: **2** e **37**;
- Linha 3: **3** e **38**;
- Linha 4: **4**;
- Linha 5: **5**.

A R6 mostra todas: não esconde o estado branco/alternativo atrás do estado
marrom padrão. Para cada instância, lista a cor base BGRA e apenas as
BlendColors que chegam àquela instância. Por exemplo, o ColorId 0 é um
multiplicador-raiz compartilhado e o painel informa seu alcance amplo, em vez
de fazê-lo parecer uma cor exclusiva da mensagem.

## Limites deliberados

- Um TXT que não seja `MSGS_TXT` não é ligado a uma cor sem uma prova de
  runtime/FLP. O painel informa a ausência de vínculo seguro.
- A associação por cursor identifica a linha lógica da página; ela não tenta
  inferir cor a partir de palavras selecionadas dentro da mesma linha.
- Ainda é necessário testar o WAD salvo no PCSX2/hardware, principalmente ao
  editar BlendColors de fades/estados compartilhados.

## Validação R6

O smoke Qt offscreen carregou `R_PERMA.WAD.txt`, selecionou `MSGS_TXT`,
confirmou o painel MessageTemplate, moveu o cursor da linha 1 à 2 e verificou
a troca para DynamicLabels 2/37. Em seguida aplicou uma nova cor pelo botão
inline: o diff no `FLP_HUDA` ficou limitado aos quatro bytes BGRA do
DynamicLabel selecionado, enquanto o texto ainda aberto no editor permaneceu
inalterado. O mesmo smoke selecionou um StaticLabel e confirmou cores diretas
e animações no painel.

Os WADs de entrada foram sempre abertos somente em leitura; nenhum foi salvo
ou substituído durante a validação.
