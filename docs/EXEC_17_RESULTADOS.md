# EXEC 17 · Apresentação de Resultados — Onda 3 do benchmark GPS

> A tela que a diretoria pediu (`10`), a tela irmã que responde "de onde vem
> esse número" (`99`), e a massa fictícia que faz as duas terem o que mostrar.

---

## Sumário

- [17.1 As sete faixas](#171-as-sete-faixas)
- [17.2 Quem vê o quê](#172-quem-vê-o-quê)
- [17.3 O carimbo por bloco, finalmente valendo](#173-o-carimbo-por-bloco-finalmente-valendo)
- [17.4 A massa e os quinze defeitos](#174-a-massa-e-os-quinze-defeitos)
- [17.5 A tela 99](#175-a-tela-99)
- [17.6 O que os testes pegaram](#176-o-que-os-testes-pegaram)
- [17.7 O que ficou de fora](#177-o-que-ficou-de-fora)
- [17.8 ADRs](#178-adrs)

---

## 17.1 As sete faixas

| # | Faixa | Fonte | O que ela resolve |
|---|---|---|---|
| 1 | Destaques e pontos de atenção | derivada | O que exige decisão hoje |
| 2 | O dinheiro | Sankhya | Realizado × orçado, **com a coluna do meio** |
| 3 | Os contratos | Platform | Carteira, deficitários, margem abaixo de 10% |
| 4 | O que está prestes a vencer | Platform | 30/60/90/180 dias, com a layer |
| 5 | Os projetos | monday | Bloqueados, marcos em risco, parados |
| 6 | As pessoas e a jornada | Sankhya | Efetivo, turnover, HE de ineficiência |
| 7 | A avaliação do cliente | Platform | Detrator **sem tratativa** em destaque |

### A coluna do meio da faixa 2

A dinâmica não é `realizado | orçado | variação`. São seis colunas —
**realizado, ajuste, realizado ajustado, orçado, %RExOR, diferença** — e a
terceira é onde a operação declara o que já aconteceu e ainda não bateu na
contabilidade.

Sem ela a reunião vira briga sobre o número em vez de decisão sobre o que fazer.

### Nenhuma faixa nasce vazia

Três estados, e cada um diz coisa diferente:

- **sem provedor** — *"A fonte monday.com ainda não está conectada neste
  ambiente."* Nomear a fonte é o que diz **o que ligar**;
- **sem dado na competência** — *"Sem lançamento financeiro nesta competência."*
  e um traço, nunca zero;
- **com dado** — os números.

Faixa que some esconde que a faixa existe: quem abre a tela pela primeira vez
concluiria que o produto não tem projetos, e não que o monday não foi ligado.

### Os cartões saem de regra, nunca de lista

Cartão aparece **só quando a regra dispara**. Painel que sempre mostra oito
cartões ensina a ignorar os oito — foi assim que o "Painel Gestão de Efetivo" do
benchmark virou uma tela que ninguém abre.

E **a fonte quebrada vem primeiro**. Sem isso, alguém lê a tela inteira e decide
em cima de um número de três dias atrás sem saber.

---

## 17.2 Quem vê o quê

| Papel | Alcance |
|---|---|
| `diretoria`, `socios`, `rh`, `financeiro` | `eco.ler.global` — a empresa inteira |
| `gestor` | `eco.ler.departamento` — o próprio centro de custo e a própria unidade |
| `ti` | `eco.carga.global` — a tela **99**, e nenhum número |
| colaborador | **403** |
| anônimo | **403 no GET** |

O 403 do anônimo é o teste de autorização mais valioso da onda. O Workspace é
aberto para o hub, o catálogo, a documentação e a agenda das salas, e a fronteira
normal dele passa entre o GET e o POST. **Aqui não passa:** resultado financeiro
não é informação institucional, e o número já está na resposta do GET.

### O filtro estreita, nunca alarga

O gerente que digitar `?regional=Sul` na barra de endereço continua vendo o dele.
O filtro entra por **interseção** com o escopo — o que a pessoa não pode ver não
volta por uma query string, que é o caminho mais óbvio e mais tentador de
contornar um recorte.

### Permissão sem lotação não vira acesso global

Alguém ganha `eco.ler.departamento` e ainda não foi lotado. Se o escopo caísse em
"tudo" por falta de recorte, essa pessoa veria a empresa inteira — e o defeito
seria de **cadastro**, invisível numa revisão de código. Ela recebe 403, com o
motivo.

---

## 17.3 O carimbo por bloco, finalmente valendo

A Onda 1 construiu o carimbo com o contrato vazio, e as quatro faixas de então
diziam a mesma coisa: *"Workspace · em tempo real"*.

Agora a mesma tela mostra **três carimbos diferentes**:

```
O dinheiro         Sankhya · competência SET/2026 · há 6 h
Os projetos        monday.com · competência SET/2026 · há 30 h    ← alerta
A avaliação        iConnect Platform · competência SET/2026 · há 12 min
```

Era exatamente por isso que o carimbo tinha de ser **por bloco**: um carimbo
único no topo estaria certo sobre metade do conteúdo e errado sobre a outra, sem
nada na tela dizendo qual metade.

E **falha de carga não zera o bloco**: a faixa 5 continua com os projetos, com a
idade em destaque e o motivo ao lado. Zerar é dizer que a empresa parou.

---

## 17.4 A massa e os quinze defeitos

```bash
python manage.py semear_fontes --aplicar
python manage.py semear_resultados --aplicar
```

**Ela entra pelo carregador**, e não por gravação direta: escreve CSVs e roda
`carregar()`, com upsert, contagem, precedência e registro de execução. Se a
semeadora precisasse de um caminho especial para gravar, o carregador estaria
errado — e um bug dele apareceria só na primeira noite.

**E entra por três fontes.** Financeiro, folha e ponto como Sankhya; projetos e
marcos como monday; contratos e avaliações como Platform. O leitor é o mesmo
`ConectorCSV`, registrado sob três chaves. Sem isso, a tela de fontes teria uma
linha e o carimbo diria a mesma coisa nas seis faixas.

Cada defeito plantado exercita uma regra — não são sujeira:

| # | Defeito | Regra que ele exercita |
|---|---|---|
| 1 | 3 contratos com MC entre 4% e 9% | a regra dos 10% |
| 2 | 1 contrato com MC negativa | o bloco de deficitários, no topo |
| 3 | Layer 3 vencendo em 45 dias | faixa 4, prioridade máxima |
| 4 | Layer 1 vencendo em 25 dias | faixa 4, prioridade baixa |
| 5 | CC com 97% do orçamento comprometido | a barra sem estouro |
| 6 | CC **sem** orçamento definido | "sem orçado" em vez de 100% |
| 7 | pico de HE de ineficiência em maio | ineficiência ≠ serviço extra |
| 8 | turnover de 8,4% num CC contra ~2,1% | o outlier, não a média |
| 9 | 2 detratores: um com tratativa, um sem | destaque só para o segundo |
| 10 | competência com receita e sem custo | "—", nunca margem de 100% |
| 11 | 2 conquistas e 1 perda no trimestre | movimentação da carteira |
| 12 | 14 folhas e 3 contratos pendentes | conformidade legal do ponto |
| 13 | 3 projetos bloqueados, 2 marcos vencidos | faixa 5 |
| 14 | carga do monday com falha há 30 h | dado velho **não some** |
| 15 | divergência plantada entre fontes | a lista da tela 99 |

`cargas/tests/test_massa.py` afirma cada um. Se alguém "corrigir" a massa achando
que é bug, o teste cai e explica por quê.

**Determinismo:** semente fixa, e duas execuções produzem exatamente o mesmo
banco.

---

## 17.5 A tela 99

`/workspace/resultados/fontes/` responde *"de onde vem esse número?"* com um
link, e não com um chamado. É o equivalente do "99 – Manutenção · Monitoramento"
do benchmark: as telas que consertam o dado são um módulo **declarado**, e não um
back-office escondido.

Ela mostra, para cada fonte: última carga boa, cadência esperada, situação, e as
contagens de cada execução — inclusive `ignorados`, que é a resposta para *"rodei
de novo, estraguei alguma coisa?"*.

Três estados, e eles **não** são o mesmo:

- **desativada** — decisão de quem opera, quase sempre num incidente;
- **não configurada** — falta credencial neste deploy, e é normal em
  desenvolvimento;
- **atrasada** — a fonte devia ter carregado e não carregou.

Juntá-los num "com problema" faria alguém procurar defeito onde não há.

As divergências aparecem com **os dois valores lado a lado**, e não só o
vencedor: a tela existe para alguém ir descobrir *por que* os sistemas
discordam.

O botão de recarregar é **POST**. Um `GET` faria um *prefetch* do navegador
disparar uma carga, e o histórico encheria de linhas que ninguém pediu.

---

## 17.6 O que os testes pegaram

Quatro defeitos meus, encontrados pela suíte durante esta onda:

1. **`hash()` de string é salgado por processo.** A massa derivava efetivo e
   horas dele, e a segunda passada reescrevia 276 linhas com valores diferentes.
   O único sinal era o contador `atualizados`, que o resumo do comando nem
   imprimia — hoje imprime.
2. **A carga falha do monday estava plantada ao contrário.** A boa ficava no
   instante da semeadura e a falha no passado, então o carimbo saía tranquilo. O
   cenário do defeito 14 não estava sendo plantado.
3. **`quadro()` devolvia a primeira linha que aparecesse.** Com doze centros de
   custo no escopo, o painel mostrava o efetivo de um deles chamando-o de efetivo
   da empresa. Virou agregado ponderado — e ganhou `quadros()` ao lado, porque a
   média **esconde** o turnover de 8,4% que pedia ação.
4. **A regra dos 10% cobrava de quem não tem histórico.** O comentário dizia
   "sem amostra não entra" e o código não fazia isso. Foi
   `test_contrato_de_um_mes_nao_recebe_layer_nem_entra_na_regra_dos_dez` que
   cobrou o que o comentário prometia.

E um quinto, achado ao escrever o teste do serviço: **fonte nunca ligada virava
cartão de "desatualizada"** — mandando alguém procurar uma carga que nunca
existiu, num ambiente onde não existir é o estado normal.

Duas travas de ondas anteriores também dispararam, e as duas estavam certas:

- `test_toda_faixa_de_numeros_agregados_tem_carimbo` reprovou as seis parciais
  novas. O carimbo **está** lá, um nível acima — a regra passou a seguir o grafo
  de `{% include %}`, que é o comportamento correto: a regra é "nenhum bloco
  agregado chega à tela sem procedência", e não "a marcação mora no mesmo
  arquivo".
- `test_todo_campo_tem_rotulo_de_verdade` reprovou os filtros. `<label>`
  embrulhando o campo resolve para o navegador e não para leitor de tela antigo;
  virou `id` + `for`.

---

## 17.7 O que ficou de fora

| Pedido | Por quê |
|---|---|
| Código `01.2` e `99.1` | `01` já é Meu dia. Ver ADR-022 |
| Exportação em planilha | O prompt proíbe em tela que lista pessoas, e a faixa 6 lista centro de custo. PDF resume; planilha convida a recortar e colar |
| Score PEC (0–100 por contrato) | Precisa de CAF, PTQ e GPC, que não existem em fonte nenhuma daqui |
| Plano de ação a partir do limiar | É a Onda 6. Hoje a faixa 3 **marca** quem está abaixo de 10%; obrigar tem dono e prazo |
| Botão "resolver divergência" | A divergência é marcada resolvida pelo `/admin/` até a Onda 4 dar tela a ela |

---

## 17.8 ADRs

### ADR-022 · A numeração é da ADB, e não do GPS

**Contexto:** o benchmark chama a tela de resultados de `01.2` e a de
monitoramento de `99.1`. Copiar o número junto com o padrão parece coerência.

**Decisão:** a tela é **`10`** e a de fontes é **`99`**. Aqui `01` já é *Meu
dia*, atribuído na Onda 1.

**Consequência:** copiamos o padrão, não o número. Renumerar `01` para abrir
espaço seria exatamente o que o ADR-015 existe para impedir — e a taxonomia do
GPS descreve um grupo com dezoito áreas e mais de cem telas, que não é esta
empresa.

O `99` é mantido de propósito: ele espelha o "Manutenção · Monitoramento" do
benchmark, e o que se copia ali **é** o padrão — as telas que consertam o dado
são um módulo declarado, e não um back-office escondido.

### ADR-023 · Ver a procedência não dá acesso aos números

**Contexto:** a tela 99 mostra cargas, e é natural pendurá-la na mesma permissão
da tela de resultados.

**Decisão:** `eco.carga` e `eco.ler` são permissões **separadas**. O T.I. tem a
primeira; a diretoria tem as duas; o gestor tem só a segunda.

**Consequência:** ligar alguém no suporte às cargas não dá a ele a margem de
todo contrato da empresa. E a diretoria não precisa de um chamado para saber de
onde vem um número.

### ADR-024 · A massa entra pelo carregador, fingindo ser cada fonte

**Contexto:** semear direto nos models seria mais simples e mais rápido.

**Decisão:** `semear_resultados` escreve CSVs e roda `carregar()` três vezes,
com o mesmo `ConectorCSV` registrado sob as chaves `sankhya`, `monday` e
`iconnect_platform`.

**Consequência:** um bug do carregador aparece ao semear, e não na primeira
carga de madrugada. E as três fontes distintas são o que exercita a tela 99 e o
carimbo por bloco — sem elas, a primeira vez que alguém veria três carimbos
diferentes na mesma tela seria em produção.

O preço é o mesmo leitor respondendo por três chaves, o que é honesto: o caminho
percorrido é o de verdade, e o que muda é de onde o arquivo veio — que é
exatamente o que uma fonte é.

### ADR-025 · Modo apresentação é query string, não segunda tela

**Contexto:** a reunião pede tipografia maior e sem trilho. Uma tela dedicada
seria mais fácil de desenhar.

**Decisão:** `?apresentacao=1` na mesma view, com o trilho **ausente do HTML** e
não escondido por CSS.

**Consequência:** duas telas divergiriam na terceira semana — e a que a diretoria
vê na reunião é justamente a que não pode divergir. `display:none` deixaria a
navegação no HTML, e o leitor de tela leria uma navegação que ninguém pode ver.


---

## 17.x A tela 10 vira três — e por que isso é permissão, não layout

*Registrado em 04/09/2026.*

### ADR-042 · Quadro e jornada e Satisfação do cliente saem da Apresentação de Resultados

**Contexto.** A tela 10 tinha sete faixas. As faixas 6 e 7 — quadro/jornada e
avaliação do cliente — respondiam perguntas de gente que não abre as outras
cinco: o turnover de um centro de custo é conversa de R.H., e o NPS é do
comercial.

Enquanto elas moravam ali, as duas exigiam `eco.ler` — a mesma permissão que
mostra a margem de cada contrato com o nome do cliente ao lado. A consequência
não era teórica: **dar o NPS ao comercial exigia dar junto o resultado
financeiro da empresa**, ninguém fazia isso, e o comercial simplesmente não via
o NPS. A faixa existia e era lida só pela diretoria.

**Decisão.** Duas telas próprias, com códigos próprios (**16** e **17**) e
permissões próprias (`eco.pessoas` e `eco.satisfacao`).

**Códigos novos, e não `10.1` e `10.2`.** Um código filho diria que elas ainda
são parte da 10, e a decisão é justamente que não são. O ADR-015 proíbe
renumerar depois — então é melhor errar para o lado de dois códigos
independentes.

**URL fora de `resultados/`.** `/workspace/quadro/` e `/workspace/satisfacao/`,
e não `/workspace/resultados/quadro/`. Quem lê o endereço lê a hierarquia, e
aninhar diria o contrário do que se decidiu.

**Consequência — ninguém perde nada.** Todo papel que tinha `eco.ler.global`
recebeu as duas permissões novas, e o gestor recebeu `eco.pessoas.departamento`,
que é o recorte da faixa que ele já via. Uma separação que retira acesso em
silêncio é pior do que não separar: o efeito aparece semanas depois, e ninguém
associa à causa.

**O que se ganhou** é uma linha nova na matriz, e ela é a prova de que a mudança
serviu para alguma coisa:

| | 10 · Resultados | 16 · Quadro | 17 · Satisfação |
|---|---|---|---|
| Diretoria, Sócios, R.H., Financeiro | ✅ | ✅ | ✅ |
| Gestor | ✅ o CC dele | ✅ o CC dele | — |
| **Vendas** | **—** | **—** | **✅** |
| T.I. | — | — | — |

**O que NÃO foi duplicado.** As três telas compartilham `_painel()`,
`_faixas.html` e `_filtros.html`. Três cópias de `escopo_de` seriam três lugares
onde "o gerente vê só o centro de custo dele" está escrito — e no dia em que
discordassem, uma delas vazaria sem deixar rastro.

**O que as telas 16 e 17 NÃO têm.** O grupo de filtros "O quê" (serviço, layer,
deficitários) e os botões de PDF e Detalhamento: os três são atributos de
CONTRATO, e ali não há contrato por trás do número. Um filtro que a pessoa
escolhe e que não muda nada faz ela concluir que a tela quebrou.

**A tela 99 continua listando as seis faixas.** A pergunta dela é "de onde vem
cada número do produto", e essa pergunta não mudou porque duas faixas passaram a
morar em outro endereço.

### O trilho, na mesma onda

"Acompanhar" tinha catorze itens para quem tem todas as permissões — medido:

    colaborador    11 itens no trilho   maior grupo: Consultar (6)
    gestor         15 itens             maior grupo: Consultar (6)
    diretoria      28 itens             maior grupo: ACOMPANHAR (14)

O trilho não estava errado; **um grupo** estava. Ele virou dois — "Resultados da
empresa" e "Gestão" — e os grupos passaram a ser `<details>`, com só o da tela
atual aberto.

`<details>` e não JavaScript: abrir e fechar disclosure é comportamento nativo,
funciona sem JS e não pede nonce na CSP. É o mesmo mecanismo do sino.

Qual grupo abre sai de `navegacao.GRUPO_POR_ROTA`, lido do `resolver_match` — e
não da variável `aba` que cada view preenche. "Cada view lembra" é a mesma aposta
que já fez a topbar perder o sino uma vez.
