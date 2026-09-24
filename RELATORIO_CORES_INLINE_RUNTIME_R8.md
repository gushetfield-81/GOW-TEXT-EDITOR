# Cores inline reais de `MSGS_TXT` — R8

**Data:** 2026-09-24  
**Escopo:** mensagens `MSGS_TXT`/Flash do `R_PERMA.WAD.txt` fornecido. Este
relatório não modifica os WADs de entrada.

## Conclusão

Os controles literais `[*N]` não são HTML, nem referências a uma tabela
inventada pelo editor. Eles são comandos consumidos pelo renderer Flash do
runtime PS2. A R8 os mantém como texto bruto no `MSGS_TXT`, pinta os glifos
correspondentes dentro de **TEXTO DA MENSAGEM** e permite alterar, no mesmo
fluxo, os RGB das cores reais que o runtime lê de `GBL_Global`.

O exemplo pedido aparece na mensagem **701**:

```text
[*1] [IconBlade] LÂMINAS DE ATENA
```

`[*1]` não é desenhado pelo jogo; o título posterior é renderizado com
`FlashMsg1Color`, extraída do WAD como **#7F2805**. Assim o título deixa de
parecer branco no editor.

## Evidência de código e comportamento do runtime

### 1. `god_of_war_browser` fornecido

O parser FLP do Browser (`pack/wad/flp/parser.go` e `pack/wad/flp/flp.go`,
commit fornecido `1bfc55c0172e67c48c8e941c495333f583c721a0`) foi usado para
manter o caminho já validado de cores físicas de `DynamicLabel`,
`StaticLabel`, `RenderCommand` e `BlendColor`. Em particular, confirma o
`ColorId` de `Data6` subtype 1 e evita tratar o texto como HTML.

O Browser não decodifica os controles de texto `[*N]`; por isso a R8 não
inferiu uma paleta a partir do FLP. A semântica abaixo vem do código de runtime
descompilado que acompanha o projeto.

### 2. Construção de texto pelo runtime

Em `gow2europedemo_europe_decompiled_named.c`:

- `FlashInterface::DoMsgPage` (`297201+`) entrega cada linha efetiva às
  variáveis `MessageTemplate_Line1`…`MessageTemplate_Line5`;
- a atualização de cada `F_EditText` chama `EditTextBuild` (`146365`);
- `EditTextBuild` (`147167+`) inicia `style = 0`, reconhece `[*N]`, não cria
  glifo para o controle e passa o estilo de cada item a
  `F_EditTextInstance::Add`;
- `[*]` e `[*0]` retornam ao estilo base;
- o construtor é chamado separadamente para cada `MessageTemplate_LineN`.
  Logo, **o estilo persiste até outro controle ou até o fim da mesma linha**;
  ele não vaza através de Enter nem de `--`.

A R8 aceita de forma segura apenas `[*]` e `[*0]`…`[*9]` como tokens; para
inserção/edição ela expõe somente os estilos comprovados pelo renderer
`[*1]`…`[*4]`. Sequências inválidas continuam texto literal no editor.

### 3. Paleta real

`renFlashServer::SetMsgParameters` (`145968+`) converte os componentes com o
equivalente a `uint8(int(float * 255))`. `EditTextRender` usa as matrizes de
mensagem construídas para os estilos 1–4; o alfa de `m_FlashMsgNColor` não é a
opacidade final desses glifos, que continua dependente do `cxform` pai.

O loader IFF (`dc::Loader::IFFProcessData`, `89852+`, e
`IFFProcessExportTable`, `89898+`) resolve o objeto exportado `GBL_Global` sem
supor que uma string encontrada no WAD seja um endereço. Na entrada fornecida:

- tag Data `DC_WAD_R_Perm`, índice **3348**;
- `GBL_Global` no offset Data **0x6BE0**;
- `m_FlashMsg1Color` no offset Data **0x6FF0**.

| Estilo | Campo físico | RGB do runtime | Hex exibido |
|---:|---|---:|---|
| `[*1]` | `FlashMsg1Color` | `(127, 40, 5)` | `#7F2805` |
| `[*2]` | `FlashMsg2Color` | `(170, 89, 20)` | `#AA5914` |
| `[*3]` | `FlashMsg3Color` | `(102, 102, 102)` | `#666666` |
| `[*4]` | `FlashMsg4Color` | `(102, 153, 204)` | `#6699CC` |

Os campos 5–6 também são lidos para diagnóstico da estrutura, mas a UI não os
oferece como `[*N]`: a rota de renderização comprovada cria os estilos 1–4.

## Implementação R8

### Dentro do editor

- `QSyntaxHighlighter` preserva a cor física base FLP da linha e aplica o span
  `[*N]` por cima dela; o marcador recebe somente uma formatação discreta e
  continua visível/editável como texto cru.
- A barra **COR INLINE** fica no próprio painel de edição:
  - escolhe `[*0] / [*]` ou `[*1]`…`[*4]`;
  - insere um token no cursor;
  - substitui apenas um token sob o cursor;
  - envolve seleção sem apagar ícones `[Icon…]` ou controles existentes;
  - se a seleção atravessa Enter, insere um par por linha, respeitando o
    reinício real de estilo do runtime.
- **Editar RGB runtime…** abre a escolha RGB apenas se o WAD aberto possui o
  `GBL_Global` físico editável. O patch toca exatamente os três `float`s RGB
  de `FlashMsg1Color`…`FlashMsg4Color`; alfa e os demais bytes do Data Context
  são preservados.

### Prévia CRT

A prévia recebe o mesmo plano de estilos: remove visualmente apenas `[*N]`/
`[*]`, mantém macros de ícone como referência textual e usa a cor física FLP
como fallback. Ela não tenta inventar sprites de macro. Como o perfil Flash
da prévia limita a página a três linhas, uma mensagem com cinco linhas pode
mostrar apenas o trecho que o perfil já mostrava antes; a cor de cada trecho
visível é a mesma do editor.

### WADs sem o contexto

`R_SHELLA.WAD.txt` não contém `MSGS_TXT`, `GBL_Global` ou o Data Context
necessário. A R8 preserva a edição de cores FLP já existente, não inventa um
campo RGB para esse WAD e deixa a edição da paleta inline desabilitada. Uma
referência de visualização compartilhada só é usada onde o runtime já teria
carregado o `R_PERMA`; ela nunca habilita gravação em um WAD sem o objeto.

## Validação R8

A suíte adicionada cobre a entrada real em modo somente leitura e o smoke Qt
`offscreen`:

1. localiza `GBL_Global` pelo Export/Data e extrai a tabela acima;
2. confirma que MSG 701 pinta **LÂMINAS DE ATENA** com `#7F2805` e conserva
   `[*1]` no texto;
3. confirma reset `[*0]` na mesma linha e reset automático ao mudar de linha;
4. testa estilos observados 1, 2 e 4, troca de token, ícone preservado e
   seleção multilinha;
5. confirma que o RGB altera somente a janela de 12 bytes dos três floats e
   que o WAD reabre com a nova cor;
6. confirma round-trip de controles como texto puro, sem `<span>` ou HTML;
7. confirma no Qt os formatos de glifo, a sincronização da prévia e a
   manutenção das cores físicas R7 em `MSGS_TXT` e `StaticLabel`.

Os hashes de `R_PERMA.WAD.txt` e `R_SHELLA.WAD.txt` são verificados após os
testes. Nenhum WAD de entrada é sobrescrito; o usuário deve usar **Salvar WAD
como…** para criar uma cópia e testá-la no jogo/PCSX2.
