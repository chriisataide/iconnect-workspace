# EXEC 25 · Gráficos com biblioteca

> Três ondas: abrir `style-src` com contrapartidas (9.5), montar os gráficos
> (10) e ligar a interação (11). Este documento começa pela primeira, que é a
> única que mexe em segurança.

---

## 25.1 A onda 9.5 em uma frase

`style-src` passou a ter `unsafe-inline`. `script-src` não. E a regra "nenhum
`style=` em template nosso" saiu do navegador e virou lint.

---

## 25.2 O que a CSP era, e o que ela é

```diff
  default-src 'self';
- script-src  'self';
+ script-src  'self' 'nonce-…';
- style-src   'self';
+ style-src   'self' 'unsafe-inline';
  img-src     'self' data:;
  font-src    'self';
  connect-src 'self';
  form-action 'self';
+ frame-src   'none';
  frame-ancestors 'none';
  base-uri    'self';
  object-src  'none'
```

Três mudanças. Duas delas abrem alguma coisa; a terceira fecha.

### O que o prompt supunha e não era verdade aqui

O prompt mandava **tirar o nonce de `style-src`**. Não havia nonce em lugar
nenhum: `SEGURANCA_CSP` era uma string estática, sem nonce em diretiva alguma. A
armadilha que ele descrevia — nonce anulando `unsafe-inline` — não podia
acontecer neste repositório.

E **seis das oito contrapartidas já estavam em vigor** desde o primeiro dia:
`img-src 'self' data:`, `font-src`, `connect-src`, `base-uri`, `form-action` e
`object-src`. Só `frame-src 'none'` faltava — `default-src 'self'` a cobria, e
`default-src 'self'` **permite** iframe de mesma origem.

---

## 25.3 Por que o nonce entrou em `script-src`

A onda 10 leva os números do servidor para o gráfico num bloco de dados:

```html
<script type="application/json" nonce="…" id="grafico-ebitda">{"series": […]}</script>
```

Um bloco `type="application/json"` não é executado, e por isso quase certamente
não seria bloqueado por `script-src 'self'`. **"Quase certamente" não é base para
uma decisão de segurança**, e a alternativa custa pouco: nonce em `script-src`
não enfraquece nada — ele só anularia um `unsafe-inline` que não está lá — e
torna o bloco inequivocamente permitido.

O preço é real e vale registrar: a CSP deixou de ser uma constante e passou a ser
montada por requisição, em `iconnect_workspace.seguranca`. `SEGURANCA_CSP` virou
`SEGURANCA_CSP_MOLDE`, com `{nonce}` no lugar.

O nonce vive em `request.csp_nonce`, e não num `threading.local`: o segundo
sobrevive à requisição num servidor com pool de threads, e nonce que vaza de uma
requisição para a seguinte é nonce reutilizável.

---

## 25.4 O detalhe mecânico que não pode ser errado

Navegador moderno **ignora `unsafe-inline` quando há nonce na mesma diretiva**.

Manter os dois não é meio-termo: é manter o comportamento antigo achando que
abriu. E o sintoma seria o pior possível — o gráfico não quebra, ele **sai
errado**: sem tooltip posicionado, sem redimensionamento, com a legenda no lugar
errado. Nada no log do servidor, nada no console além de avisos que ninguém lê.

Por isso `test_a_csp_abriu_style_e_nao_abriu_script` afirma os quatro fatos ao
mesmo tempo, e não um de cada vez:

| | tem que ser |
|---|---|
| `script-src` | **sem** `'unsafe-inline'` |
| `script-src` | **com** nonce |
| `style-src` | **com** `'unsafe-inline'` |
| `style-src` | **sem** nonce |

Qualquer um deles sozinho passa despercebido numa revisão. É o tipo de linha que
alguém "arruma" numa faxina de configuração.

---

## 25.5 A disciplina que a CSP não cobra mais

`style=` em template **nosso** continua proibido. O que a biblioteca injeta é
aceito; o que nós escrevemos, não.

**Dois testes cobram, pelos dois lados:**

- `test_nenhum_template_nosso_escreve_style` varre os **templates**, como
  arquivo — o repositório inteiro, e não quatro rotas. A versão anterior cobria
  quatro telas de trinta e cinco, e cobria porque o navegador fazia o resto do
  trabalho;
- `test_nenhuma_tela_usa_atributo_style` varre o **HTML renderizado** — e pega o
  `style=` que não está em template nenhum: o que um serviço monta em string, o
  que vem de um campo do banco, o que um filtro produz.

Eles se sobrepõem de propósito. Quando a cobrança sai do browser, é melhor que
ela sobre em dois lugares do que caia em nenhum.

**E a entrada também fecha:** `test_nenhum_template_interpola_dentro_de_style`
recusa `{{ }}` dentro de `<style>`. Com `style-src` aberta, isso é injeção de
CSS direta — e injeção de CSS não é enfeite: um seletor de atributo com
`background-image: url(…)` lê o valor de um campo e o manda para fora,
caractere por caractere. `img-src 'self' data:` fecha a saída; essa regra fecha
a entrada.

A barra tripla da bandeja **continua em SVG**, onde `width` é atributo. Não
porque precise mais, mas porque desenhar assim sobrevive a `style-src` fechada —
e fechar de novo não deveria custar uma reescrita.

---

## 25.6 Onda 10 — a biblioteca

### A escolha, e a versão

**Apache ECharts 6.1.0**, licença Apache-2.0, com renderizador **SVG**.

ECharts e não Chart.js porque o benchmark precisa de medidor (Score PEC), mapa de
calor em tabela e eixo duplo com barra + linha (1.1.02): os três vêm de fábrica,
enquanto o Chart.js exige plugin para dois deles e só desenha em canvas.

Canvas não dá texto selecionável, não tem árvore de acessibilidade e piora o PDF.
E — medido — ele é **7 KB menor**. A escolha pelo SVG custa alguma coisa, e vale
dizer que custa.

### O tamanho, medido e não estimado

| Build | minificado | gzip |
|---|---|---|
| só barra + linha | 558 KB | 190 KB |
| catálogo (6 tipos de série) | 639 KB | **217 KB** |
| pacote completo — proibido | 1.095 KB | 360 KB |

O tree-shaking corta **40%**, e não 80%: o núcleo do ECharts é a maior parte, e
190 KB é o piso mesmo com um gráfico só.

Por isso o bundle **só carrega nas telas que declaram gráfico**, pelo bloco
`{% templatetag openblock %} scripts {% templatetag closeblock %}`. A home, o
catálogo e as reservas não pagam nada.

### Os números vêm do servidor — inclusive a vírgula

O ECharts formata em en-US por padrão. O caminho óbvio seria um `formatter` em JS
com `Intl.NumberFormat('pt-BR')` — e aí a mesma regra existiria em dois lugares,
o gráfico e a **tabela irmã**, que mostra exatamente os mesmos números.

`formatter` aceita um **template em string** com `{@dimensão}`, resolvido contra o
dado bruto — conferido no fonte da 6.1.0, `lib/model/mixin/dataFormat.js`. Então o
Python manda o texto pronto como uma dimensão a mais do `dataset`, e o formatador
é a string `"{@rotulo}"`.

**Zero função em JavaScript.** `workspace/graficos/formato.py` é a fonte única.

As faixas da escala, com o motivo de cada corte:

    abaixo de 10 mil     1.234       abreviar não encurta nada
    até 999 mil          840 Mil     sem casa decimal: `840,3 Mil` é ruído
    de 1 milhão          1,23 Mi     duas casas, porque a primeira decide

O arredondamento é conferido **depois** de aplicado: 999.999 vira `1,00 Mi`, e não
`1.000 Mil` — o segundo está certo na conta e errado na tela.

### A tabela irmã é FALLBACK, e não acessibilidade

No desenho anterior — SVG calculado em Python — o gráfico existia sem JavaScript.
Aqui não existe: sem JS, o `<div>` fica vazio.

Por isso o `<details>` nasce **`open` no HTML**, e o JS o fecha depois de
desenhar. Escrevê-lo condicionalmente deixaria a tabela fechada para quem não tem
JavaScript — que é exatamente quem depende dela.

E não há como pedir metade: `{% templatetag openblock %} grafico {% templatetag closeblock %}`
renderiza os dois, do mesmo objeto `Bloco`, com os mesmos textos formatados.

### O rótulo é girado — e é assim que treze meses cabem

A primeira versão pôs o valor em cima de cada barra, na horizontal. Com treze
meses, `R$ 1,19 Mi` mede mais que a largura de uma barra, e os rótulos viraram
uma mancha ilegível.

O Portal GPS resolve girando o texto em 90° e pondo-o **dentro** da barra —
girado, o rótulo ocupa a altura, que sobra, em vez da largura, que falta. É o que
`_rotulo()` faz em todo tipo do catálogo.

`labelLayout.hideOverlap` deixa o ECharts esconder o que ainda não couber. O
número continua na tabela irmã, que é onde se confere.

**O percentual não gira.** Ele é curto e é a leitura principal do bloco — no
benchmark ele aparece numa etiqueta escura sobre a linha, e aqui também.

### A faixa do dinheiro: realizado × orçado, com a razão em linha

É a 1.1.02 do benchmark. Duas barras dizem **quanto**; a linha no eixo direito
diz **se está onde deveria** — e é a primeira coisa que alguém procura na
reunião.

Mês sem orçado fica **sem barra clara e sem ponto na linha**. Um ponto em zero
seria lido como "não cumpriu nada", e o que houve foi ninguém ter orçado.

**O EBITDA fica sem par**, e de propósito: o espelho não traz EBITDA orçado.
Inventar um denominador para ter a linha seria a pior forma de completar um
gráfico. O bloco mostra o que tem.

### Os filtros, e a segunda causa da sobreposição

Girar o rótulo resolveu metade do amontoado. A outra metade é poder **estreitar
a janela**, e essa é a que a pessoa controla: 3, 6, 12 ou 13 meses.

Entraram também **serviço** e **layer** — os dois já eram lidos da query string e
não tinham campo na tela: o filtro existia e ninguém alcançava.

E entraram **valendo para a tela inteira**. Antes, `serviço` e `layer` filtravam
só a faixa da carteira: a pessoa escolhia "cftv", a lista de contratos encolhia,
e o gráfico do dinheiro continuava mostrando a empresa inteira.

> Duas faixas discordando sobre o mesmo filtro, na mesma tela, é o defeito que
> faz alguém deixar de confiar no número — e ele não dá erro nem aparece em log.

`_estreitar_por_atributo()` traduz os dois numa lista de contratos e estreita o
`Escopo` **uma vez**, antes de montar qualquer faixa. Filtro que não casa com
nada devolve `("",)` — um código que não existe —, porque tupla vazia em `Escopo`
significa "a empresa inteira".

O seletor de serviço oferece só o que existe na carteira **visível**: uma segunda
consulta poderia oferecer um serviço fora do escopo da pessoa, o que revelaria a
existência dele.

### O catálogo — onze tipos, nove no ECharts e dois fora

| # | Tipo | O que responde |
|---|---|---|
| 1 | `barras_comparadas` | realizado × orçado, com a razão em linha — a 1.1.02 |
| 2 | `serie_temporal` | como um número andou em N meses |
| 3 | `cascata` | o que entrou e o que saiu entre dois saldos |
| 4 | `empilhada_percentual` | composição por categoria, **com o valor absoluto** |
| 5 | `barra_composicao` | o mix de um total, numa barra só |
| 6 | `rosca` | participação, com o total no centro |
| 7 | `medidor` | nota com faixas de governança — o Score PEC |
| 8 | `bullet` | valor contra meta, no tamanho de uma célula |
| 9 | `dispersao` | **quais contratos são grandes E pouco rentáveis** |
| 10 | `farol` | **não é gráfico** — `<span>` com classe e rótulo |
| 11 | `mapa_calor_tabela` | **não é gráfico** — `<table>` com faixa por célula |

**A cascata não existe no ECharts.** A receita conhecida é barra empilhada com
uma série de base **transparente**: numa queda a base fica no valor de chegada e
o bloco visível sobe até o de partida. Com a base no de partida, a barra sairia
do gráfico.

**A dispersão é adição nossa**, e não do benchmark. Ela responde o que nenhuma
das outras responde: o quadrante direito-inferior, onde o dinheiro está e a
margem não. O tamanho do ponto fica entre 8 e 34 pixels — sem piso, o contrato
pequeno vira um ponto que ninguém acha; sem teto, o maior cobre os vizinhos.

**O medidor traz a quantidade por faixa na tabela**, e não só o ponteiro. Um
medidor diz onde a média caiu e esconde a distribuição: média 78 com metade dos
contratos abaixo de 50 é uma conversa diferente de média 78 com todos entre 70 e
85 — e o benchmark mostra as duas coisas lado a lado.

Medidor sem amostra desenha **sem ponteiro**. Um ponteiro em zero seria lido como
nota zero.

### Os dois que não são gráfico, e por quê

**Farol.** Desenhar um círculo colorido de 10px com ECharts custaria um
contêiner, uma inicialização e 203 KB de biblioteca para pintar um ponto. E o
ponto sozinho não diz nada a quem não distingue as cores — por isso o rótulo
está sempre ao lado, e não no `title`.

Farol **sem amostra é cinza**, e escrito "sem amostra". Vermelho ali mandaria
alguém correr atrás do problema errado: ausência de caso não é o pior caso.

E ele **inverte** quando menor é melhor — turnover, absenteísmo, custo. Sem a
inversão, quem perdeu metade da equipe apareceria em verde.

**Mapa de calor.** O prompt do catálogo dá as duas opções e recomenda a tabela.
Três razões, e a terceira decide:

- é **menor**: zero bytes de biblioteca, e o mapa costuma ser a grade inteira;
- continua legível **sem JavaScript**, que é o pior cenário do resto do catálogo
  e o normal aqui;
- o número fica **selecionável** — e uma grade de score existe para alguém copiar
  uma linha dela para um e-mail.

A escolha teve consequência no bundle: `HeatmapChart` e `VisualMapComponent`
saíram, e ele caiu de **640 KB para 595 KB** (217 → 203 KB comprimidos).

### Cor nunca sozinha, em cada tipo

| Tipo | O que acompanha a cor |
|---|---|
| barras comparadas | legenda com o nome de cada série, valor dentro da barra |
| cascata | verde/vermelho **mais** o valor escrito dentro |
| empilhada e composição | valor absoluto dentro do segmento |
| rosca | nome e percentual no rótulo externo |
| medidor | nome da faixa **e** quantidade, na tabela |
| bullet | a palavra "sim"/"não" na coluna *Atingiu* |
| farol | o rótulo textual ao lado da marca |
| mapa de calor | o número em cada célula, e a legenda nomeando as faixas |

### O que a Onda 10 apagou

`workspace/services/grafico.py` e `workspace/templates/workspace/_serie_svg.html`
— o SVG calculado à mão. Foram substituídos, e código que ninguém renderiza é o
que `test_nenhum_template_e_orfao` existe para impedir.

**O guard da vírgula ficou.** `test_svg_desenha.py` continua varrendo as telas
atrás de coordenada com vírgula decimal: o produto ainda desenha SVG à mão no
medidor da bandeja, nos ícones e na arte da tela de entrar. Nenhum tem coordenada
fracionária hoje — e é por isso que o guard precisa continuar.

---

## 25.7 Onda 11 — perfurar (mecanismo 1)

Isolado, e só na faixa do dinheiro. É o passo 7 do plano: ligar a perfuração nas
cinco faixas de uma vez tornaria impossível dizer qual delas quebrou.

### A hierarquia

`empresa → regional → centro de custo → contrato`. Cada barra do bloco de
perfuração desce um degrau; a trilha de migalhas sobe quantos forem precisos.

### O estado mora na URL — e não há parâmetro `nivel`

`?regional=Sudeste&cc=1042` é a tela inteira. Colar esse endereço numa mensagem
reproduz exatamente o que a pessoa está vendo.

**O nível é derivado dos filtros**, e não lido da URL. Um `?nivel=cc` ao lado de
`?cc=1042` seria uma segunda verdade sobre o mesmo fato, e as duas discordariam
no dia em que alguém editasse a URL à mão.

Descer **preserva** os outros filtros — janela, serviço, layer. Perder a janela
de seis meses ao descer um nível é como alguém conclui que o filtro "não
funciona". E subir na trilha **limpa** os níveis de baixo: voltar para a regional
com o centro de custo ainda ativo mostraria a regional recortada por um CC que a
trilha diz não estar mais lá.

### A trilha aparece mesmo na raiz

Com um degrau só, "Empresa". Sem isso ela nasceria no primeiro clique e sumiria
no último — que é quando a pessoa mais precisa saber onde está.

### Perfurar funciona sem JavaScript

A URL de cada ponto é montada em **Python** e viaja como dimensão do `dataset`.
O JS lê `params.data[3]` e navega; ele não sabe qual filtro pertence a qual
nível, e não precisa saber.

A **tabela irmã usa a mesma URL** num `<a>`. Não são duas implementações: as
duas leem `bloco.urls`.

E o JS só navega para caminho que comece com `/`. URL absoluta vinda de dado
seria um redirecionamento aberto com passos extras.

### A fronteira

Perfurar até o contrato funciona; até a ocorrência, não — o detalhe operacional
mora no Platform. No último nível o bloco **não tem barra para clicar**, e a tela
diz por quê. Beco sem saída silencioso é pior que a ausência do nível: quem
clicou e não viu nada acontecer conclui que a tela quebrou.

### O defeito que a perfuração descobriu

`resultados/providers.py::_recortar` combinava regional, centro de custo e
contrato com **OU**.

Consequência concreta: descer para o CC 1042 dentro do Sudeste devolvia também os
contratos do 1055, porque `regional=Sudeste OR cc=1042` é o Sudeste inteiro.
**Quem perfurou viu a lista crescer ao descer um nível.**

E o mesmo `OU` alargava a permissão: um gerente lotado no CC 1042 da unidade
Sudeste enxergava a regional inteira, e não a operação dele.

As três dimensões são uma **hierarquia**, e a mais específica passou a vencer:
`contrato > centro de custo > regional`. Isso **estreita** — a direção segura, e
a que o módulo já pratica ("o filtro estreita o escopo; nunca o alarga").

Melhor que um `E` entre as três, que daria tela vazia no dia em que o nome da
unidade no organograma não batesse com o campo `regional` do espelho — texto
livre, vindo de fora.

---

## 25.8 Onda 11 — cruzar, pivotar, detalhar (mecanismos 2, 3 e 4)

### O que este passo NÃO fez, e por quê

O prompt descreve o filtro cruzado com `history.replaceState`, sem recarregar, e
o JS recalculando as `option` a partir de um endpoint JSON.

**Foi feito por round-trip de query string.** A razão está no próprio prompt, uma
seção acima: *"os números vêm do servidor, sempre"*. Recalcular a option no
cliente exige replicar em JavaScript a agregação por mês, o recorte por escopo e
a formatação em pt-BR — as três coisas que este produto passou a onda inteira
mantendo num lugar só.

O prompt já prevê a saída: *"se passar de ~200 KB, volte ao round-trip por query
string"*. A diferença é que aqui a razão não é volume, é fonte da verdade.

O endpoint `/workspace/resultados/dados/` existe assim mesmo, com a mesma
verificação de escopo — ele é o contrato que o prompt pede, e serve a quem quiser
conferir um número sem raspar HTML.

### Dois defeitos que o mecanismo 2 encontrou

**Em apresentação, os filtros ficavam invisíveis.** `{% if not apresentacao %}`
escondia a barra inteira — então `?apresentacao=1&layer=1` mostrava números
recortados **sem nada na tela dizendo que eram**. Numa reunião, projetado.

É exatamente o que o prompt nomeia: *"filtro invisível é a principal fonte de
'esse número está errado' que não está"*.

**O botão "Apresentar" descartava os filtros.** Ele levava só a competência:
clicar com um recorte ativo trocava os números em silêncio, no caminho entre a
tela e o projetor.

### As tarjas

Aparecem **sempre** — inclusive em apresentação, onde os controles somem e elas
ficam. Cada uma com o X para remover, e "Limpar tudo" quando há alguma.

O X é um **link**, e não um botão de JavaScript: remover um filtro é navegar para
a mesma tela sem ele, e isso funciona com o script desligado.

Remover um degrau da hierarquia **limpa os de baixo**, pela mesma razão da
trilha. E "Limpar tudo" preserva competência e janela: competência é o assunto
da tela, e devolver treze meses a quem escolheu seis é surpresa, não limpeza.

### O limite de três cruzados

Quatro recortes simultâneos produzem um número que ninguém explica de cabeça, e é
aí que a tela deixa de ser usada. O quarto **substitui o mais antigo e avisa** —
recusar o clique seria pior: a pessoa clicaria de novo achando que não pegou.

O limite conta só os **atributos** (serviço, layer, deficitário). Regional,
centro de custo e contrato são o **nível**, e a trilha já os mostra.

### Pivotar é link, e não `<select>`

As opções são cinco e cabem numa linha. Um link é navegação de verdade: funciona
sem JavaScript, abre em nova aba e entra no histórico. Um `<select>` que submete
no `change` não faz nada disso.

Escolher regional, centro de custo ou contrato troca o **nível**; escolher
serviço ou layer **reagrupa sem descer**, e ali o clique vira filtro cruzado. É a
diferença entre os mecanismos 1 e 2, e ela fica visível na própria tela.

### Detalhar é tela, e não gaveta

Uma gaveta exigiria carregar a tabela por JavaScript. Uma **tela tem URL** — que
é o que permite mandar o detalhe numa mensagem, do mesmo jeito que o agregado.

Link **explícito**, e nunca clique acidental no gráfico: descer para as linhas é
outra pergunta, e não uma variação da mesma.

**O detalhe herda todos os filtros e mostra quais são no topo.** Ele reusa
`escopo_de`, `ler_filtros` e `_estreitar_por_atributo` — as mesmas funções da
tela. Uma segunda leitura de filtro divergiria da primeira, e o sintoma seria
exatamente o que o prompt avisa: *"detalhe que não bate com o agregado destrói a
confiança na tela inteira"*.

`test_o_detalhe_bate_com_o_agregado` compara os dois números. É o teste mais
importante deste passo.

Cada linha traz a **procedência** — `sankhya:snk-CT-100-202609`. Este é o nível
mais fundo da tela, e é aqui que alguém confere contra o ERP.

### O PDF carrega o recorte

Mesma razão das tarjas, e pior: o PDF é lido dias depois, longe da tela, por
gente que não escolheu o recorte. Sem filtro, ele diz "Sem recorte: a empresa
inteira" — o silêncio seria ambíguo.

---

## 25.9 ADR

### ADR-041 · O bundle é versionado; o PDF leva tabela e diz que não tem gráfico

**Contexto.** Duas decisões que o mesmo fato produz: os gráficos passaram a ser
desenhados por JavaScript, e o servidor não roda JavaScript.

**Decisão, parte 1 — o artefato vai versionado.** `build/echarts/` tem
`package.json` e `entrada.js`; o que sai dali, `echarts.min.js`, entra no
repositório. Deploy e CI **nunca precisam de Node** — só quem regenera o bundle
precisa.

**Decisão, parte 2 — o PDF é PDF-2.** Ele leva as **tabelas**, e o rodapé diz que
os gráficos ficaram de fora e onde vê-los.

**Consequência.** As alternativas eram um Chromium sem interface no pipeline de
exportação, ou o ECharts em modo servidor sob Node. As duas põem um segundo
runtime no caminho crítico de exportar um documento num projeto Django, e as duas
existem para um documento que circula para **conferência**, não para
apresentação: quem quer o gráfico abre a tela, onde ele é interativo.

O rodapé não é cortesia. Um PDF que mostra menos que a tela, em silêncio, é como
alguém conclui que o número mudou.

Se alguém reclamar, PDF-1 (Chromium) é o caminho — e aí a decisão terá um pedido
atrás, que é o que falta hoje.

### ADR-040 · `style-src` abre para a biblioteca de gráficos; `script-src` não

**Contexto.** Este repositório nasceu sem `unsafe-inline` em diretiva nenhuma, e
o README registra por que isso foi possível: o Workspace deixou de compartilhar
header com o iConnect Platform, que usa `style=` em escala. Era uma vantagem
concreta, e ela está sendo gasta de propósito.

A decisão de produto passou a ser usar biblioteca de gráficos. **Toda biblioteca
de mercado escreve `style=` no DOM** — tooltip, redimensionamento, posição de
legenda. Não é uma escolha de implementação delas que se possa contornar: é como
elas desenham.

**Decisão.**

1. `style-src` recebe `'unsafe-inline'`, e **não** recebe nonce.
2. `script-src` recebe nonce e **continua sem** `'unsafe-inline'`. Nenhuma
   biblioteca de gráfico precisa dele: todas carregam como arquivo externo. Se
   alguma exigir, ela sai.
3. `frame-src 'none'` entra, junto com as contrapartidas que já existiam.
4. A regra "nenhum `style=` nosso" vira lint sobre o repositório inteiro, e
   `{{ }}` dentro de `<style>` passa a ser proibido explicitamente.

**Consequência.** O vetor que se abriu é injeção de CSS: com `style-src` livre,
CSS controlado por atacante consegue ler valor de campo com seletor de atributo e
exfiltrar por requisição de imagem. As oito diretivas de saída fechadas são o que
torna esse vetor caro — sem elas, a contrapartida não existe.

O que se perdeu é a frase "sem `unsafe-inline` em diretiva nenhuma", que era
verificável e agora não é mais. O que se ganhou é medidor, mapa de calor e eixo
duplo sem escrever um motor de gráfico — trabalho que o benchmark exige em pelo
menos onze lugares.

**Sob qual condição isso é revisto.** No dia em que a biblioteca sair, ou o
navegador oferecer um caminho para estilo de terceiro sem `unsafe-inline`
(`style-src-attr` com hash, hoje sem suporte suficiente), fechar de volta tem de
ser **uma linha no settings**. É exatamente para isso que o lint continua
cobrando o que a CSP não cobra: sem ele, voltar atrás viraria uma auditoria de
trinta e cinco telas.

**O que não foi feito, e por quê.** A diretiva **não** é configurável por
ambiente. Uma variável de ambiente aqui é como uma política estrita vira frouxa
em produção sem ninguém notar — e o único lugar onde a diferença apareceria é um
console de navegador que ninguém abre em produção.
