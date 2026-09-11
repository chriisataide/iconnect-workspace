# Auditoria — Resultados e Indicadores

> **Levantado em 08/09/2026** contra o repositório na `feature/chris`, commit
> `cac80ec`. 3.452 testes verdes, cobertura 98,16%.
>
> Nenhum item foi marcado por nome de arquivo. Todo `[OK]` e `[PARCIAL]` foi
> aberto, lido e conferido, e traz arquivo e linha.

---

## 1 · Arquitetura encontrada

O produto separa **espelho**, **contrato** e **tela**, e a separação é real —
não é convenção de nome. Vale entendê-la antes de qualquer implementação,
porque metade dos itens da PARTE II atravessa as três camadas.

```
                     cargas/                  ← conectores: Sankhya, monday,
                       ↓  escreve               Platform, CSV, manual, PNCP
                     resultados/              ← o ESPELHO (tabelas locais)
                       ↓  implementa
        workspace/providers/resultados.py     ← o CONTRATO (ABC + DTOs)
                       ↑  consome
                     workspace/               ← views, services, templates
```

**A direção é de mão única e testada.** O app `workspace` nunca importa
`cargas` nem `resultados`; a ligação acontece em `AppConfig.ready()`, por
registro. Um `import` na direção errada reprova a suíte.

**Nenhuma chamada de rede acontece numa view.** Se um número vem de fora, ele
já está no espelho quando a tela abre — a razão está escrita em
[views/resultados.py:16-21](../workspace/views/resultados.py#L16-L21) e vale para
tudo que for construído aqui.

### As telas de hoje

| Rota | View | O que é |
|---|---|---|
| `/workspace/resultados/` | [views/resultados.py:41](../workspace/views/resultados.py#L41) | Apresentação de Resultados (tela 10) |
| `/workspace/resultados/detalhe/` | `resultados_detalhe` | Perfuração — linhas por dimensão |
| `/workspace/resultados/dados/` | `resultados_dados` | O agregado em JSON |
| `/workspace/resultados/pdf/` | `resultados_pdf` | Exportação |
| `/workspace/resultados/fontes/` | `fontes` | Tela 99 — saúde das cargas |
| `/workspace/quadro/` | `quadro` | Quadro e jornada (tela 16) |
| `/workspace/satisfacao/` | `satisfacao` | Avaliação do cliente (tela 17) |
| `/workspace/indicadores/` | [views/indicadores.py:37](../workspace/views/indicadores.py#L37) | **SLA de solicitações** — ver §9.1 |

---

## 2 · Models e migrations

### O espelho — `resultados/models.py`

Toda tabela herda `ProcedenciaMixin` ([:60](../resultados/models.py#L60)): fonte,
chave externa, id da carga, instante da importação e hash do conteúdo. É o que
faz o carimbo de frescor e a idempotência funcionarem sem cada model repetir.

| Model | Linha | Observação para a PARTE II |
|---|---|---|
| `Contrato` | [:105](../resultados/models.py#L105) | `regional` é **string livre**, `servico` é enum de equipamento |
| `CompetenciaResultado` | [:140](../resultados/models.py#L140) | **seis números agregados** — ver §9.2 |
| `Projeto` / `MarcoProjeto` | [:220](../resultados/models.py#L220) | completo |
| `QuadroPessoas` / `Apontamento` | [:283](../resultados/models.py#L283) | completo, sem dado pessoal |
| `AvaliacaoCliente` | [:354](../resultados/models.py#L354) | completo |
| `EditalPublico` | [:390](../resultados/models.py#L390) | novo, do PNCP |

**Migrations:** apenas duas em `resultados/` (`0001_initial`, `0002_alter_…`).
Não há histórico complicado — qualquer migration nova entra limpa.

### O que NÃO existe no repositório inteiro

Verificado por varredura, não por suposição:

```
class Area              → nenhuma ocorrência
PlanoContas / Conta     → nenhuma ocorrência
conta_contabil          → nenhuma ocorrência
Concentracao            → nenhuma ocorrência
equipamento             → nenhuma ocorrência
```

A única `Area` do produto é [`AreaFAQ`](../workspace/models/faq.py#L35), que é
outra coisa — ver o conflito em §9.3.

---

## 3 · Endpoints

| Rota | Autorização | Escopo |
|---|---|---|
| `/resultados/` | `eco.ler` via `escopo_de` | 403 sem escopo, nunca zerado |
| `/resultados/dados/` | **o mesmo `escopo_de` e `ler_filtros`** | ver abaixo |
| `/resultados/pdf/` | idem | exportação respeita o escopo |
| `/quadro/` | `eco.pessoas` | permissão separada |
| `/satisfacao/` | `eco.satisfacao` | permissão separada |
| `/resultados/fontes/` | `eco.fontes` | ver procedência ≠ ver número |
| `/indicadores/` | `ind.ler` ou domínios visíveis | 403 sem painel |

O endpoint JSON **já não diverge da tela**, e o motivo está escrito no
docstring: as duas chamam as mesmas duas funções. É exatamente o defeito que o
§10 do prompt manda procurar, e ele não está presente.

**Anônimo:** `@login_required` redireciona para o login (302), não 403. O §10
pede 403 no GET para anônimo — ver §9.7.

---

## 4 · Frontend e gráficos

### O catálogo — `workspace/graficos/series.py`, 1.560 linhas

Onze tipos, todos com **tabela irmã** e formatação em pt-BR feita no Python:

`serie_temporal` · `barras_comparadas` · `cascata` · `barra_composicao` ·
`empilhada_percentual` · `rosca` · `medidor` · `bullet` · `dispersao` ·
`farol` · `mapa_calor_tabela` · `barras_por_categoria`

### A doutrina do JS — e ela restringe dois itens da PARTE II

[echarts-adb.js:1-24](../workspace/static/workspace/js/echarts-adb.js#L1-L24) é
explícito:

> *"Ele não soma, não converte e não formata. A `option` inteira vem pronta do
> servidor, num `<script type="application/json">`. (…) Não há tema registrado
> aqui: um segundo lugar com cor é um segundo lugar para a paleta divergir."*

A `option` viaja como **JSON**. Isso tem duas consequências que o prompt não
previu, e estão em §9.4 e §9.5.

---

## 5 · Fontes de dados

| Fonte | Conector | Estado |
|---|---|---|
| Sankhya | `cargas/conectores/sankhya.py` | **sem credencial** |
| monday | `cargas/conectores/monday.py` | **sem credencial** |
| iConnect Platform | `cargas/conectores/iconnect_platform.py` | **sem credencial** |
| CSV | `cargas/conectores/csv_local.py` | funciona — é o que enche a massa |
| manual | `cargas/conectores/manual.py` | funciona |
| PNCP | `cargas/conectores/pncp.py` | **funciona, sem senha** — 542 editais |

**Espelho ≠ integração.** As telas não sabem se o dado veio de API ou de CSV, e
`semear_resultados` enche as seis faixas sem nenhuma credencial. Isso significa
que a PARTE II inteira é construível e demonstrável **hoje**, sem esperar o T.I.

---

## 6 · Integrações

Nenhuma tela chama rede. O contrato `workspace/providers/resultados.py` expõe
sete provedores; `resultados/providers.py:105` (`EspelhoLocal`) implementa todos
sobre o banco local. Trocar a origem do dado não toca em nenhuma view.

---

## 7 · Massa de dados encontrada

[`cargas/management/commands/semear_resultados.py`](../cargas/management/commands/semear_resultados.py),
652 linhas, determinística (`random.Random` com semente fixa).

```
4 regionais genéricas ("Sudeste", "Sul", "Nordeste", "Centro-Oeste")   :52
contratos com servico ∈ {cftv, alarme, monitoramento, instalacao, manutencao}
15 defeitos plantados, numerados e comentados no código
```

Os 15 defeitos são bons e devem ser preservados — margem entre 4% e 9%, margem
negativa, Layer 3 vencendo em 45 dias, competência com receita e sem custo,
CC com 97% do orçamento, CC sem orçamento, carga do monday falhando há 30 h,
Sankhya e monday discordando do mesmo projeto.

**O que a massa não tem:** área comercial, escopo de equipamento, e despesa por
conta contábil — porque não há onde pôr.

---

## 8 · Testes encontrados

| Arquivo | Testes |
|---|---|
| `test_graficos.py` | 82 |
| `test_perfuracao.py` | 42 |
| `test_indicadores.py` | 22 |
| `test_resultados.py` | 20 |

Mais `test_quadro.py`, `test_satisfacao.py`, `test_pdf.py`, `test_frescor.py`,
`test_auditoria_*.py`. A suíte inteira tem **3.452** testes com piso de catraca
em 3452 — o piso sobe junto, e baixá-lo exige justificativa no PR.

Há guardas que a implementação vai encontrar: toda cor de gráfico precisa
existir nos tokens; todo gráfico precisa de tabela irmã; nenhum `style=` em
template nosso; nenhuma classe base redefinida.

---

## 9 · Problemas e riscos

### 9.1 · `/indicadores/` mede outra coisa — `[CONFLITO]`

A tela existe e funciona, mas o assunto dela é **solicitação de serviço e SLA**:
prazo prometido, reaberturas, "Mais pedidos", "Quem entregou"
([services/indicadores.py:117-150](../workspace/services/indicadores.py#L117-L150)).

E o "Por área" dela são as **áreas internas** — Compras, Financeiro, Jurídico,
TI ([:325](../workspace/services/indicadores.py#L325)).

Os nove blocos do item I1 são **todos novos**, e nenhum se apoia no que existe.
Duas saídas possíveis, e a escolha é de produto:

- **substituir** o conteúdo atual pelo painel de empresa, movendo o SLA para
  outra tela (a fila de atendimento já existe);
- **coexistir**, com a tela de empresa em rota própria.

Substituir sem decidir isso é remover funcionalidade sem autorização, o que o
§0 proíbe.

### 9.2 · Não existe despesa por conta contábil — `[BLOQUEADO]`

`CompetenciaResultado` guarda **seis números por contrato e mês**
([models.py:156-161](../resultados/models.py#L156-L161)):

```
receita_bruta · impostos · custo_direto · custo_indireto
margem_contribuicao · ebitda
```

O BLOCO D inteiro — e por consequência C6, e o peso por conta do H2 — pede o
razão analítico. Ele não existe no espelho, não existe no conector, e **não se
inventa**: uma tabela de contas semeada com número aleatório produziria uma DRE
que fecha por construção e não corresponde a nada.

É o bloqueio 3 do §7, e é o que mais muda o tamanho do trabalho.

### 9.3 · "Área" passaria a significar três coisas — `[RISCO]`

| Onde | O que "área" quer dizer |
|---|---|
| `/indicadores/` hoje | departamento interno (Compras, TI, Financeiro) |
| `AreaFAQ` | seção da base de conhecimento |
| A3 e I1 do prompt | conglomerado comercial de contratos |

E o I1 bloco 4 chama de **"Concentração de risco"** a dependência dos 5 maiores
clientes, enquanto o E1 chama de **"Concentração"** a curadoria humana do que a
diretoria decidiu olhar. **Duas coisas com o mesmo nome, nas duas telas que
linkam uma para a outra.**

Este é literalmente o defeito que acabamos de corrigir em
`/workspace/marketing/` no commit `cac80ec` — lá, "oportunidade" significava ao
mesmo tempo o convite de feira e o edital de licitação, e a queixa do usuário
foi exatamente essa confusão. Vale resolver o vocabulário **antes** de escrever
o código, não depois.

Sugestão: I1 bloco 4 vira **"Dependência de cliente"**; E1 mantém
"Concentração".

### 9.4 · O tooltip do scatter — a causa é a que o prompt diz, a cura não

`[series.py:1244](../workspace/graficos/series.py#L1244)`:

```python
"tooltip": {"trigger": "item", "confine": True, "formatter": "{@detalhe}"}
```

com `series.data` como lista de dicionários e **sem `dataset.dimensions`**. O
texto do tooltip está montado e correto em
[:1284](../workspace/graficos/series.py#L1284) — o formatter é que não o alcança.
O diagnóstico do G1 está certo.

**Mas o passo 2 da correção prescrita não é executável neste produto.** Ele
manda *"trocar o formatter de string para função"*. A `option` viaja como JSON
dentro de `<script type="application/json">` (§4) — **função não sobrevive à
serialização JSON**. Escrever a função no `echarts-adb.js` colocaria formatação
em JS, que é justamente o que o arquivo declara não fazer, e criaria o segundo
lugar onde o pt-BR pode divergir.

**O passo 1 sozinho resolve**, e resolve melhor: com `dataset.dimensions`
declarando `detalhe`, a string `{@detalhe}` passa a resolver. O que exige
cuidado é que hoje cada ponto carrega `itemStyle` próprio (vermelho abaixo do
limiar) e `symbolSize` próprio — coisas que a forma de `dataset` não aceita por
item. A saída idiomática é `visualMap` com corte no limiar, que é mais simples
que o que está lá e elimina o laço em Python.

### 9.5 · A paleta não pode morar no CSS — `[CONFLITO]`

O G2 pede *"paleta em variáveis CSS num único arquivo; o tema do ECharts lê
delas"*. O ECharts recebe cor **dentro da `option` JSON**, montada em Python.
Para ele ler `var(--au-accent-600)` seria preciso o JS resolver a variável e
reescrever a option — de novo, o segundo lugar com cor que o arquivo proíbe.

O **objetivo** do G2 é atingível e correto: trocar a paleta deve ser um arquivo.
Hoje ela já é um arquivo — [series.py:79-91](../workspace/graficos/series.py#L79-L91)
— e há um teste que exige que toda cor usada exista em `tokens.css`. O que falta
é o contraste, não o lugar.

### 9.6 · Renomear `ServicoContrato` apaga dado — `[BLOQUEADO]`

O A4 substitui `{cftv, alarme, monitoramento, instalacao, manutencao}` por
`{projeto, monitoramento, manutencao, locacao, projeto_turnkey}`. Três valores
saem. Contratos existentes no banco de desenvolvimento usam os antigos.

Não é problema em dev (a massa é semeada de novo), mas é mudança destrutiva pela
definição do §7. A migration precisa mapear, e o mapeamento é decisão de
negócio: `cftv` e `alarme` viram `projeto`? `manutencao`? Depende de como
aqueles contratos foram vendidos.

### 9.8 · O `OU` do escopo do dinheiro — `[RISCO]` ALTO, corrigido em 08/09/2026

Encontrado durante a FASE 1, ao acrescentar os campos novos ao `Escopo`.
**Reproduzido antes de ser afirmado**, e corrigido em seguida.

`EspelhoLocal._competencias_no_escopo` é o único recorte que não usa
`_recortar` — por uma razão legítima: a linha de centro de custo não tem
contrato, e filtrar por `contrato__centro_custo` a deixaria fora de todo
recorte. Mas ele combinava os três níveis com **OU**, enquanto o `_recortar`
passou a usar PRECEDÊNCIA na Onda 11. Ele ficou para trás.

`escopo_de` monta, para um gerente, **as duas coisas ao mesmo tempo**:

```python
Escopo(regionais=("Sudeste",), centros_custo=("1042",))
```

Com `OU`, isso é "o Sudeste inteiro OU o CC 1042" — o Sudeste inteiro. Medido:

```
carteira  (via _recortar)                 →  C-MEU
dinheiro  (via _competencias_no_escopo)   →  C-MEU, C-VIZINHO
```

A mesma tela mostrando a carteira de um centro de custo e a receita da regional
toda. **Sem erro, sem log, e sem ninguém notar** — porque os dois números nunca
aparecem lado a lado.

A precedência resolve sem custar a linha sem contrato: no nível de centro de
custo o filtro é `centro_custo__in`, campo próprio desta tabela, que pega tanto
as linhas de contrato quanto o rateio do CC. Dois testes seguram os dois lados,
em `resultados/tests/test_area.py`.

### 9.7 · Anônimo recebe 302, não 403 — `[RISCO]` baixo

O §10 pede 403 no GET para anônimo. Hoje `@login_required` devolve **302 para o
login**. Isso já foi levantado numa revisão anterior do guia de QA e corrigido
lá, no documento. A pergunta é se o comportamento deve mudar: 302 para o login é
o padrão do Django e é o que o resto do portal faz. Mudar só estas duas rotas
criaria uma exceção que ninguém lembra.

---

## 10 · Requisitos — a classificação

**Nenhum item está `[OK]`.** Vários estão perto.

### BLOCO A — Filtros e vocabulário

| ID | Estado | Onde está, e o que falta |
|---|---|---|
| **A1** | `[PARCIAL]` | `?competencia=` lido em [services/resultados.py:259](../workspace/services/resultados.py#L259), campo em [:186](../workspace/services/resultados.py#L186). Falta: renomear para `mes`, ler o antigo por compatibilidade, e o rótulo na barra |
| **A2** | `[PARCIAL]` | `janela: int` em [:203](../workspace/services/resultados.py#L203), presa entre 3 e 13 por `meses` em [:222](../workspace/services/resultados.py#L222); o seletor já existe em `_filtros.html`. Falta: os cinco valores nomeados, `mes` (=1) abaixo do piso atual, padrão 12, e o recorte no título de cada gráfico |
| **A3** | `[FALTA]` | `regional` é string livre em [models.py:114](../resultados/models.py#L114); as regionais são constante do seeder ([:52](../cargas/management/commands/semear_resultados.py#L52)). Não há model, FK, descrição nem "Sem área" |
| **A4** | `[PARCIAL]` `[BLOQUEADO]` | `ServicoContrato` em [models.py:91](../resultados/models.py#L91) tem a lista de equipamento. Ver §9.6 |
| **A5** | `[FALTA]` | Todos os filtros são `str` único ([:186-196](../workspace/services/resultados.py#L186-L196)); `_estreitar` ([:244](../workspace/services/resultados.py#L244)) aceita um valor só |
| **A6** | `[PARCIAL]` | As tarjas de filtro ativo existem, com X por filtro e "Limpar tudo" ([_tarjas.html](../workspace/templates/workspace/resultados/_tarjas.html)), e aparecem **inclusive no modo apresentação** — que foi um defeito corrigido. Faltam: `position:sticky` ([workspace.css:4349](../workspace/static/workspace/src/workspace.css#L4349) não tem) e a frase corrida |

### BLOCO B — A narrativa

| ID | Estado | Onde está, e o que falta |
|---|---|---|
| **B1** | `[PARCIAL]` | Ordem de hoje: destaques → dinheiro → contratos(+mix) → vencimentos → projetos ([_faixas.html:73-83](../workspace/templates/workspace/resultados/_faixas.html#L73-L83)). O mix existe ([:656](../workspace/services/resultados.py#L656)) mas está **dentro** de contratos. Faltam os blocos 1 (cartões de valor), 4 (cascata), 5 (conquista×perda) e 6 (comparativo) |
| **B2** | `[FALTA]` | Não existe. O que há é `Faixa.motivo`, que explica **ausência** de dado — não leitura de número |

> Nota sobre o bloco 1: "Cartões de valor" (receita, margem, EBITDA) **não é** o
> que a tela chama hoje de "Destaques". Destaques são alertas por regra. São dois
> blocos diferentes, e o B1 pede os dois.

### BLOCO C — Gráficos

| ID | Estado | Onde está, e o que falta |
|---|---|---|
| **C1** | `[PARCIAL]` | `barras_comparadas` ([series.py:364](../workspace/graficos/series.py#L364)) já entrega barras agrupadas, linha em `yAxisIndex:1`, rótulo dentro/fora conforme `FOLGA_DO_ROTULO` ([:72](../workspace/graficos/series.py#L72)), e negativo com zero no meio — **com teste afirmando que o zero não é a base**. Falta: a **cápsula sobre o ponto** do %, e o piso de fonte |
| **C2** | `[PARCIAL]` | Receita existe ([:381](../workspace/services/resultados.py#L381)). **Impostos não tem gráfico**, e o espelho não traz `impostos_orcado` — a série RE×OR de imposto não é montável hoje |
| **C3** | `[PARCIAL]` | EBITDA existe **sem par**, e o comentário em [:390-393](../workspace/services/resultados.py#L390-L393) diz por quê: o espelho não traz EBITDA orçado, e inventar denominador seria a pior forma de completar um gráfico. Indireto não tem gráfico |
| **C4** | `[BLOQUEADO]` | Nem reserva técnica nem supervisão existem no espelho ou no vocabulário. Bloqueio 1 do §7 |
| **C5** | `[PARCIAL]` | `MovimentacaoDTO` com conquistas/renovações/perdas existe ([providers/resultados.py:294](../workspace/providers/resultados.py#L294)) e aparece como **lista** em [_contratos.html:115](../workspace/templates/workspace/resultados/_contratos.html#L115). Faltam: os quatro gráficos, a safra por ano e a lista lateral com busca. ROB é montável; **MC por safra depende de margem por contrato por mês**, que existe |
| **C6** | `[PARCIAL]` | `series.cascata` está pronta e testada ([:544](../workspace/graficos/series.py#L544)) — **e nenhuma tela a usa**, só os testes. A série da DRE depende de D2; os degraus até Margem de Contribuição são montáveis com os seis campos de hoje, os detalhados não |

### BLOCO D — Tabela contábil

| ID | Estado | Onde está, e o que falta |
|---|---|---|
| **D1** | `[FALTA]` `[BLOQUEADO]` | Existe perfuração, mas por **regional › centro de custo › contrato** ([:1301](../workspace/services/resultados.py#L1301)) — hierarquia organizacional, não contábil. O estado já viaja na query string, o que é meio caminho para `?expandir=` |
| **D2** | `[FALTA]` | Nenhum plano de contas no repositório. Verificado, não suposto |
| **D3** | `[PARCIAL]` | Seis colunas do benchmark existem em `_linha_de_dinamica` ([:543](../workspace/services/resultados.py#L543)); as dez pedidas exigem D2. **Exportar PDF existe** ([views/resultados.py:199](../workspace/views/resultados.py#L199)) e já respeita filtro e permissão. Faltam: alternar absoluto/%, expandir tudo, total fixo ao rolar |

### BLOCO E — Destaques, Atenção e Concentração

| ID | Estado | Onde está, e o que falta |
|---|---|---|
| **E1** | `[PARCIAL]` | `Destaque` tem `severidade` crítico·atenção·neutro ([:873](../workspace/services/resultados.py#L873)) e sete famílias de regra ([:915-1092](../workspace/services/resultados.py#L915-L1092)). Faltam: a categoria **positiva** (hoje todo cartão é problema) e o model `Concentracao` inteiro |
| **E2** | `[PARCIAL]` | O cartão é link de **âncora** (`href="#contratos"` — [_faixas.html:33](../workspace/templates/workspace/resultados/_faixas.html#L33)): rola a página, não filtra. A regra "só aparece se disparar" **já vale** ([:903](../workspace/services/resultados.py#L903)), e o vazio é tratado como boa notícia |

### BLOCO F — Comparativo

| ID | Estado | Onde está, e o que falta |
|---|---|---|
| **F1** | `[FALTA]` | A série já traz 13 meses **exatamente para isso** ([:58](../workspace/services/resultados.py#L58): "doze para comparar com o mesmo mês do ano passado, mais o atual") — o dado está lá e ninguém compara |
| **F2** | `[FALTA]` | Nem o gráfico de trimestres, nem a hachura de trimestre parcial |

### BLOCO G — Correções

| ID | Estado | Onde está, e o que falta |
|---|---|---|
| **G1** | `[PARCIAL]` `[CONFLITO]` | Diagnóstico correto; passo 2 da cura não é executável. Ver §9.4 |
| **G2** | `[PARCIAL]` `[CONFLITO]` | A paleta já é um arquivo e já é validada contra os tokens. O lugar pedido (CSS lido pelo ECharts) contraria a arquitetura. Ver §9.5. O que falta de verdade é **contraste**: hoje RE×OR é azul-escuro × azul-claro ([:79-80](../workspace/graficos/series.py#L79-L80)), e o prompt pede azul-aço × âmbar |

> **G3 não existe mais** nesta versão do prompt. A regra dele (rótulo fora da
> barra quando não couber, sem encolher fonte) foi absorvida pelo C1. O
> cabeçalho antigo listava "G1 G2 G3"; a PARTE II atual tem dois. Registrado
> para não parecer item esquecido.

### BLOCO H — Massa de dados

| ID | Estado | Onde está, e o que falta |
|---|---|---|
| **H1** | `[FALTA]` | Nenhum vestígio de equipamento no repositório. **A lista precisa da sua conferência antes de virar código** — o próprio prompt avisa que ela é de conhecimento geral |
| **H2** | `[PARCIAL]` | O seeder é bom: 652 linhas, determinístico, **15 defeitos numerados**. Faltam: áreas, escopo de equipamento, despesa por conta (não há onde pôr), e os 3 defeitos novos. Os cenários de teste pedidos exigem A3, D2 e E1 |

### BLOCO I — Indicadores

| ID | Estado | Onde está, e o que falta |
|---|---|---|
| **I1** | `[FALTA]` `[CONFLITO]` | A tela existe e mede outra coisa. Ver §9.1. Nenhum dos nove blocos existe |
| **I2** | `[PARCIAL]` | 403 em vez de tela zerada já vale ([views/indicadores.py:44](../workspace/views/indicadores.py#L44)), e o carimbo de procedência vem de context processor para nenhuma view esquecer. Faltam: link ao detalhe em todo bloco, dupla comparação, teto de nove, e modo apresentação (existe só na tela 10) |

### Contagem

| | |
|---|---|
| `[OK]` | **0** |
| `[PARCIAL]` | 17 |
| `[FALTA]` | 9 |
| `[CONFLITO]` | 4 (I1, G1, G2, A4/§9.3) |
| `[BLOQUEADO]` | 3 (C4, D1/D2, A4) |

---

## 11 · Bloqueios

Os três do §7, com o que eu já sei e por que não posso assumir.

### Bloqueio 1 — reserva técnica (C4)

```
[BLOQUEADO]
Problema:  Não há vestígio de "reserva técnica" nem de "supervisão" como
           conceito no espelho, no vocabulário do produto ou no seeder.

Por que não posso assumir:
           No benchmark isto é provisão para cobrir substituição de posto em
           serviço com efetivo alocado. A ADB é segurança ELETRÔNICA, e o
           análogo mais provável é provisão de garantia — que você já pediu
           como a conta 41505. Se eu implementar os dois, a mesma coisa aparece
           duas vezes na DRE e o total não fecha.

Opções:    (a) C4 sai do escopo;
           (b) C4 vira "Garantia e retrabalho", lendo 41505;
           (c) são de fato dois conceitos, e você me diz o que RT cobre.

Recomendação: (b), se a ADB provisiona garantia. Senão, (a).
```

### Bloqueio 2 — áreas 04 e 05 (A3)

```
[BLOQUEADO]
Problema:  As áreas 01 a 03 têm clientes reais; 04 e 05 estão "a definir".

Por que não posso assumir:
           Área é conglomerado COMERCIAL. Inventar dois agrupamentos produz
           uma massa em que o filtro por área não ensina nada — e o defeito 18
           que você pediu ("uma área inteira com margem abaixo da média")
           precisa cair numa área que faça sentido.

Opções:    (a) você nomeia os clientes;
           (b) semeio 04 e 05 com clientes fictícios explicitamente rotulados
               como fictícios, e o modelo aceita edição sem migration.

Recomendação: (b) para não travar, com (a) quando você tiver os nomes. O
           agrupamento é editável por desenho, então trocar depois é cadastro.
```

### Bloqueio 3 — rateio de despesa por contrato (D1, e todo o BLOCO D)

```
[BLOQUEADO]
Problema:  O espelho recebe custo JÁ SOMADO por contrato e mês — seis números.
           Não há razão analítico, nem no banco nem no conector do Sankhya.

Por que não posso assumir:
           A pergunta central do bloco D é "com o que gastei". Semear contas
           com número aleatório produziria uma DRE que fecha por construção e
           não corresponde a nada — e alguém levaria isso para uma reunião.

O que preciso saber:
           1. O Sankhya expõe o razão por conta contábil?
           2. A linha do razão carrega o CONTRATO, ou só o centro de custo?

           Se for só centro de custo, o nível 3 do D1 não existe — e é melhor
           não construir uma coluna que ficará sempre vazia.

Opções:    (a) só CC → D1 tem dois níveis, e a tabela é por centro de custo;
           (b) CC + contrato → os três níveis, como especificado;
           (c) não expõe → o bloco D fica bloqueado até haver fonte, e eu
               construo o resto.

Recomendação: responder antes de eu começar o D. Os blocos A, B, E, F, G e I
           não dependem disto e podem andar em paralelo.
```

---

## 12 · Recomendações

**1. Resolva o vocabulário antes do código.** Três significados de "área" e dois
de "concentração", nas duas telas que linkam uma para a outra. Custa uma decisão
agora e uma refatoração depois — acabamos de pagar essa conta em marketing.

**2. A3 é a alavanca.** O model `Area` destrava A5, A6, B1, E2, H2 e o bloco 2
do I1. É o item que mais barateia os outros, e não depende de nenhum bloqueio.

**3. O bloco D é um projeto, não um item.** Modelo novo no espelho, mudança no
conector do Sankhya, plano de contas semeado, tabela expansível e a cascata que
se apoia nela. Enquanto o bloqueio 3 não for respondido, ele nem começa.

**4. Aceite a correção do G1 pela via 1.** `dataset.dimensions` + `visualMap`
resolve o `{@detalhe}`, elimina o laço de `itemStyle` por ponto e não põe
formatação em JS. É menos código do que há hoje.

**5. Não reverta a CSP.** `style-src` aberta é decisão registrada (ADR-040) e o
gráfico depende dela; `script-src` continua com nonce e sem `unsafe-inline`. O
lint é que cobra `style=` em template nosso.

**6. O que dá para entregar sem responder nada:** A1, A2, A5, A6, B1 (parcial),
B2, E2, F1, F2, G1, G2. É a primeira fatia do plano.
