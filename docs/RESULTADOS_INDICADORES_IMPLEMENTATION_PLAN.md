# Plano de implementação — Resultados e Indicadores

> Companheiro de [RESULTADOS_INDICADORES_AUDIT.md](RESULTADOS_INDICADORES_AUDIT.md).
> Escrito em 08/09/2026 sobre `cac80ec`.
>
> **Este plano cobre apenas o que cabe nesta sessão.** O §6 do prompt é
> explícito: plano longo demais consome o orçamento e não sobra para código. O
> que ficou de fora está na última seção, nomeado — não esquecido.

---

## O corte, e por que ele é aqui

Os 29 itens da PARTE II se dividem em três grupos, e a divisão não é por
tamanho: é por **o que cada um espera**.

```
GRUPO 1  não espera nada        →  ESTA SESSÃO
GRUPO 2  espera uma resposta    →  a sessão seguinte à sua resposta
GRUPO 3  espera uma FONTE       →  depois de o Sankhya expor o razão
```

| Grupo | Itens | Espera |
|---|---|---|
| **1** | A1 A2 A3 A5 A6 B1(parcial) B2 E2 F1 F2 G1 G2 | — |
| **2** | A4 C4 E1 H1 H2 I1 I2 | bloqueios 1 e 2, e a decisão de vocabulário |
| **3** | C2 C3 C6 D1 D2 D3 | bloqueio 3 — o razão contábil |

**O que decidiu o corte:** o bloco D é o pedido central do prompt e é o único
que não posso nem começar. Construir a tabela sobre número inventado produziria
uma DRE que fecha por construção — e alguém a levaria para uma reunião. O §17 é
claro: entre inventar dado e bloquear por falta de dado, bloqueie.

Então esta sessão faz o que **destrava** o bloco D em vez de fingi-lo: a `Area`,
os filtros multi-valor, a barra que sobrevive à rolagem, e as duas correções de
gráfico. Quando o razão chegar, o D encontra o terreno pronto.

---

## FASE 1 · O model `Area` — A3

**Por que primeiro.** É a alavanca: destrava A5, A6, B1, E2, H2 e o bloco 2 do
I1. E não depende de nenhum bloqueio.

**Objetivo.** `regional` (string livre) vira `Area` (modelo com FK), sem que
nenhum número suma da tela.

**Arquivos**

```
resultados/models.py                      + class Area, Contrato.area (FK, null)
resultados/migrations/0003_area.py        criar + popular a partir de `regional`
resultados/providers.py                   ContratoDTO ganha area
workspace/providers/resultados.py         o DTO do contrato
workspace/services/resultados.py          Filtros.area, _estreitar, HIERARQUIA
resultados/admin.py                       Area editável — o agrupamento é cadastro
cargas/management/commands/semear_areas.py
```

**Dependências.** Nenhuma.

**Riscos**

| Risco | Mitigação |
|---|---|
| Contrato sem área some do total ao filtrar | "Sem área" é uma opção real do filtro, não um `NULL` escondido. **Teste obrigatório:** a soma de todas as áreas + "Sem área" = o total sem filtro |
| `regional` fica órfã e alguém a usa | Mantida por uma versão, marcada como legada no docstring, com a `Area` derivada dela na migration |
| A hierarquia de perfuração quebra | `HIERARQUIA` hoje é regional › CC › contrato; vira área › CC › contrato. Os 42 testes de `test_perfuracao.py` são a rede |

**Testes**

- a migration deriva uma `Area` por `regional` distinta, e nenhum contrato fica sem
- soma por área + "Sem área" == total geral (o teste que protege a confiança)
- contrato novo sem área aparece em "Sem área" e conta no total
- `?area=` inexistente não alarga o escopo de quem filtrou
- a descrição aparece no seletor

**Critério de aceite.** `/resultados/?area=area-01` recorta a tela inteira, o
total de todas as áreas somadas bate com o total sem filtro, e um contrato sem
área é visível.

---

## FASE 2 · Filtros — A1, A2, A5, A6

**Objetivo.** O vocabulário e o comportamento da barra.

**Arquivos**

```
workspace/services/resultados.py          Filtros, ler_filtros, meses, _estreitar
workspace/templates/workspace/resultados/_filtros.html
workspace/templates/workspace/resultados/_tarjas.html
workspace/static/workspace/src/workspace.css     sticky
```

**Detalhe por item**

**A1** — `?mes=` passa a ser o nome; `?competencia=` continua sendo lido, com o
valor antigo tendo precedência **menor**. Um teste afirma que os dois nomes
produzem a mesma tela, e um comentário datado diz quando a compatibilidade pode
sair.

**A2** — `mes · 3m · 6m · 9m · 12m`, padrão **12m**. Duas coisas mudam de
verdade:

- o piso de hoje é 3 meses ([resultados.py:222](../workspace/services/resultados.py#L222)),
  com a razão escrita: *"abaixo disso o gráfico é uma comparação, e comparação
  se lê melhor em tabela"*. O valor `mes` viola isso deliberadamente — então
  `mes` **não desenha série temporal**: os blocos mensais mostram a tabela do
  mês. Isso é decisão, e vai comentada;
- o padrão passa de 13 para 12. Os 13 existiam para comparar com o mesmo mês do
  ano anterior (F1); a comparação passa a ser explícita, e a série volta a ter
  o tamanho que a pessoa pediu.

**A5** — `area` e `servico` viram lista. `_estreitar` passa a receber `tuple` e
continua fazendo interseção com o permitido — **um gerente que digitar
`?area=area-09` na URL continua vendo só o dele**. É o comportamento de hoje e
não pode regredir; há teste.

**A6** — `position: sticky` na barra, e a frase corrida montada em Python
(`"Área 01 e Área 03 · monitoramento · últimos 6 meses até AGO/2026"`). A frase
sai do mesmo lugar que as tarjas, para não haver duas verdades sobre o recorte.

**Riscos**

| Risco | Mitigação |
|---|---|
| `?competencia=` some e quebra link compartilhado | Lido por uma versão, com teste |
| Multi-valor alarga escopo por URL forjada | O teste de IDOR já existente cobre; estendê-lo para lista |
| Sticky cobre conteúdo no modo apresentação | Apresentação esconde a barra e mantém as tarjas — comportamento já corrigido antes, não regredir |

**Critério de aceite.** `?area=area-01&area=area-03&servico=monitoramento&periodo=6m`
recorta todos os blocos, a frase descreve o recorte, a barra acompanha a
rolagem, e `?competencia=2026-08` ainda funciona.

---

## FASE 3 · As duas correções de gráfico — G1, G2

**G1 — o tooltip.** Correção pela via 1 da auditoria (§9.4), **não pela
prescrita**: função em JS não sobrevive à serialização JSON da `option`.

```
1. dataset.dimensions = [contrato, receita, margem, valor_mensal,
                         area, servico, fim_vigencia, layer, detalhe]
2. encode: {x: receita, y: margem, tooltip: [...]}
3. visualMap piecewise no limiar de margem  →  substitui o itemStyle por ponto
4. symbolSize por callback de dimensão      →  substitui o cálculo em laço
5. formatter continua string: "{@detalhe}", agora resolvível
```

Sai código: o laço que monta 
`itemStyle`/`symbolSize`/`label` por ponto ([series.py:1265-1290](../workspace/graficos/series.py#L1265-L1290))
desaparece.

**Teste obrigatório** (o prompt pede, e ele é bom): nenhum `option` renderizado
contém a sequência `{@` sem a dimensão correspondente declarada. Escrito como
guarda genérica sobre **todos** os onze tipos de gráfico, não só o scatter —
o mesmo erro cabe em qualquer um.

**G2 — contraste.** O objetivo é atingível; o lugar pedido, não (§9.5). A
paleta continua em [series.py:79-91](../workspace/graficos/series.py#L79-L91),
que já é um arquivo só e já é validado contra `tokens.css` por teste.

O que muda:

```
COR_PRINCIPAL   #3539a9 (azul-escuro)  →  azul-aço saturado
COR_SECUNDARIA  #a0a2e1 (azul-claro)   →  âmbar
```

Com duas amarras: o par tem de existir em `tokens.css` (o teste exige) e tem de
passar em contraste contra o fundo **e entre si**. Verde e vermelho continuam
reservados — hoje já estão.

**Riscos**

| Risco | Mitigação |
|---|---|
| Âmbar colide com `COR_LINHA` (`#d97706`, warning) | A linha de % é âmbar hoje. Se a série B virar âmbar, a linha precisa de outra cor — resolver junto, não depois |
| Cor sozinha volta a comunicar | A legenda com nome escrito continua; a regra não muda |
| Trocar cor quebra os testes de tokens | É o objetivo do teste. Token novo entra em `tokens.css` primeiro |

**Critério de aceite.** Um tooltip de bolha mostra contrato, área, serviço,
receita, margem em % e R$, vigência e layer — sem nenhum `{@`. As barras RE×OR
se distinguem em escala de cinza.

---

## FASE 4 · Narrativa mínima — B1 parcial, B2, E2

**Objetivo.** A tela conta a história na ordem certa **até onde os dados
permitem**, e cada bloco diz o que mostra.

**B1 — o que dá para reordenar hoje**

| # | Bloco | Estado nesta sessão |
|---|---|---|
| 1 | Cartões de valor | **novo** — receita, margem, EBITDA, carteira |
| 2 | Mix da carteira | **move** — sai de dentro de contratos |
| 3 | Destaques · Atenção | reordena (Concentração fica para o grupo 2) |
| 4 | Cascata da DRE | **não** — bloqueio 3 |
| 5 | Conquista × Perda | **não** — fase 5, se houver orçamento |
| 6 | Comparativo | fase 5 |
| 7-9 | Contratos, Vencimentos, Projetos | reordena |
| 10-11 | Pessoas, Satisfação | **já são telas próprias** (16 e 17) — ver nota |

> **Nota sobre 10 e 11.** Pessoas e Satisfação saíram da tela 10 numa onda
> anterior, por decisão de permissão: dar o turnover de um centro de custo a
> quem responde por gente significava dar junto a margem de todo contrato. Elas
> **não voltam** para dentro da 10. O B1 as lista como blocos 10 e 11; na
> prática são links no fim da narrativa. Se você quiser de volta, é uma decisão
> de permissão, não de layout — e vira bloqueio.

**B2 — a frase de leitura.** Regra em Python, com número real, e **silêncio
quando não há afirmação verdadeira a fazer**. Nasce com três regras, não onze:

```
dinheiro    margem contra o mês anterior, em pontos, com a causa quando
            um contrato explica mais de 40% da variação
contratos   quantos estão abaixo da margem mínima, e quanto de receita eles são
vencimentos quanto de valor mensal vence na próxima faixa
```

Três e não onze porque cada regra é uma afirmação que pode ficar falsa, e onze
afirmações que ninguém revisa é como um painel passa a mentir devagar.

**E2 — o cartão filtra.** Hoje é âncora (`href="#contratos"`). Passa a aplicar
o recorte: `?area=area-03#contratos`. A tarja e o X já existem e são reusados.

**Riscos**

| Risco | Mitigação |
|---|---|
| A frase afirma algo falso | Toda regra tem teste com o caso em que ela **não** deve falar |
| Reordenar quebra âncoras compartilhadas | As âncoras são por chave de faixa, não por posição |
| "Cartões de valor" vira mais um lugar que soma | Derivados das faixas, como os destaques já são ([:881](../workspace/services/resultados.py#L881)) — nunca consulta nova |

**Critério de aceite.** A tela abre com cartões de valor no topo e o mix logo
abaixo; um bloco sem dado suficiente não exibe frase; clicar num cartão de área
filtra a tela e mostra a tarja com X.

---

## FASE 5 · Comparativo — F1, F2 *(se sobrar orçamento)*

Marcada como condicional de propósito. F1 tem uma vantagem rara: **o dado já
está lá** — a série carrega 13 meses exatamente para isto
([:58](../workspace/services/resultados.py#L58)).

```
F1  seletor "Comparar com" (nenhum · ano_anterior · mesmo_trimestre · dois_anos)
    terceira série tracejada no bloco_re_or
    exibir sempre: período atual, período comparado e variação
F2  barras por trimestre, até três anos, hachura no trimestre parcial
```

**O ponto que decide F2:** trimestre em curso hachurado e rotulado "parcial —
2 de 3 meses". Comparar trimestre incompleto com completo sem avisar é o erro
que mais gera decisão errada em reunião — e é a única parte do F2 que não pode
sair.

---

## Sequência, e onde a suíte roda

```
FASE 1  Area                  → suíte inteira (mexe em migration e hierarquia)
FASE 2  filtros               → suíte inteira (mexe em escopo)
FASE 3  gráficos              → test_graficos + test_resultados
FASE 4  narrativa             → suíte inteira
FASE 5  comparativo           → suíte inteira
```

A suíte leva **8m20s**. Rodar depois de cada fase é caro e é o preço de não
descobrir na quinta que a primeira quebrou algo.

**Catraca:** o piso está em 3452. Sobe a cada fase, com nota do que os testes
novos protegem — a nota é o que impede o piso de virar número sem sentido.

---

## O que fica para depois, nomeado

### Espera a sua resposta (grupo 2)

| Item | Espera |
|---|---|
| **A4** serviços | O mapeamento de `cftv`/`alarme`/`instalacao` para os cinco novos. É mudança destrutiva |
| **C4** reserva técnica | Bloqueio 1 — é o mesmo que a conta 41505? |
| **E1** Concentração | O model é simples; o que falta é a decisão de vocabulário (§9.3) |
| **H1** equipamentos | Sua conferência da lista, antes de virar código |
| **H2** massa | Depende de A3 (feito na fase 1), A4 e D2 |
| **I1 I2** indicadores | Bloqueio de produto: substituir o SLA ou coexistir (§9.1) |

### Espera uma fonte (grupo 3)

| Item | Espera |
|---|---|
| **C2** impostos RE×OR | `impostos_orcado` no espelho |
| **C3** indireto e EBITDA RE×OR | `custo_indireto_orcado` e `ebitda_orcado` |
| **C5** conquista × perda | Montável em ROB hoje; a safra por ano exige ano de entrada e de saída no contrato |
| **C6** cascata da DRE | Os degraus detalhados exigem D2 |
| **D1 D2 D3** | Bloqueio 3 — o razão contábil do Sankhya |

**Sobre C2 e C3:** os três campos orçados que faltam são **três colunas** em
`CompetenciaResultado` e três linhas no CSV do seeder. Não é o mesmo tamanho do
bloco D. Se você confirmar que o orçamento da ADB tem essas três linhas, eles
entram junto com a fase 3 — e aí C2 e C3 saem do grupo 3.

---

## As quatro perguntas — RESPONDIDAS em 08/09/2026

| # | Pergunta | Resposta | O que muda |
|---|---|---|---|
| 1 | Reserva técnica = conta 41505? | **São os dois** | C4 volta ao escopo, e 41505 existe além dele |
| 2 | Áreas 04 e 05 | **04 · Lojas Americanas** · **05 · ROMU** | A3 sai do bloqueio; sem cliente fictício |
| 3 | Razão do Sankhya | **expõe por conta, e a linha carrega o CONTRATO** | **O bloco D inteiro desbloqueia, com os três níveis** |
| 4 | `/indicadores/` | **coexistem** | Ver a decisão de rota abaixo |

### O que a resposta 3 muda — e é muito

Era o bloqueio que segurava seis itens. Com o razão trazendo o contrato:

```
D1  os TRÊS níveis existem       grupo → conta → rateio por contrato
D2  o plano de contas tem onde morar, e o dado é real
D3  as dez colunas são montáveis
C6  a cascata da DRE tem os degraus detalhados
C2  impostos por conta (31201)
C3  indireto por conta
H2  o peso por conta muda com o serviço — o que torna o dropdown útil
```

**O bloco D deixa de ser impossível e passa a ser grande.** Ele é modelo novo no
espelho + conector + seeder + serviço + tela expansível + testes. Não cabe nesta
sessão junto com as fases 1 a 5, e tentar fazer os dois entregaria os dois pela
metade. Fica como a **sessão seguinte**, com o terreno pronto: a `Area` da fase 1
é filtro dele também.

### A decisão de rota da resposta 4

"Coexistem" pede duas rotas, e a escolha de qual fica com qual nome não é
neutra. Decidido, e o critério é não quebrar o que funciona:

```
/workspace/indicadores/   PERMANECE a tela de SLA de solicitações
                          rótulo passa a "Indicadores de atendimento"
/workspace/painel/        NOVA — o painel da empresa (I1)
                          rótulo "Painel da empresa"
```

Trocar a rota da tela existente quebraria link compartilhado, favorito e teste,
para ganhar uma palavra. Trocar o **rótulo** resolve a ambiguidade inteira e não
quebra nada — foi exatamente o que resolveu `/marketing/` no commit `cac80ec`,
onde "oportunidade" significava duas coisas e a correção foi de vocabulário, não
de estrutura.

**A palavra "área" segue o mesmo tratamento:** em `/indicadores/` ela passa a ser
**"setor"** (Compras, Financeiro, TI são setores internos), e "área" fica livre
para significar só o conglomerado comercial. E o bloco 4 do I1 vira
**"Dependência de cliente"**, deixando "Concentração" para a curadoria do E1.
