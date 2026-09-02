# EXEC 16 · Ingestão multi-fonte — Onda 2 do benchmark GPS

> Escopo: os apps `cargas` e `resultados`, os contratos de resultado, os quatro
> conectores e o carregador comum.
> **Sem tela.** É a espinha que sustenta a Apresentação de Resultados (Onda 3).

---

## Sumário

- [16.1 A arquitetura em uma imagem](#161-a-arquitetura-em-uma-imagem)
- [16.2 Por que o app não se chama `integracoes`](#162-por-que-o-app-não-se-chama-integracoes)
- [16.3 O carregador é um só](#163-o-carregador-é-um-só)
- [16.4 Os quatro conectores](#164-os-quatro-conectores)
- [16.5 Conflito entre fontes](#165-conflito-entre-fontes)
- [16.6 O que a documentação vigente corrigiu](#166-o-que-a-documentação-vigente-corrigiu)
- [16.7 O que ficou pendente, e de quem depende](#167-o-que-ficou-pendente-e-de-quem-depende)
- [16.8 ADRs](#168-adrs)

---

## 16.1 A arquitetura em uma imagem

```
  FONTES              INGESTÃO            ESPELHO              CONTRATO      TELA
  ───────             ────────            ───────              ────────      ────
  Sankhya (ERP)   ┐
  monday.com      ├──►    cargas    ──►  resultados  ──implementa──►  workspace
  iConnect Platf. ┤    (conectores)      (somente     workspace.providers  .views
  CSV / manual    ┘                       leitura)        .resultados
```

O app `workspace` conhece **apenas** `workspace/providers/resultados.py`. Ele não
sabe que existe Sankhya, não sabe que existe monday, não sabe sequer que existem
os apps `cargas` e `resultados`.

O ganho é concreto: trocar o ERP, ou passar o orçamento do CSV para uma API, mexe
em **um conector**. Nenhuma view muda.

A direção é guardada por `workspace/tests/test_isolamento.py`, que ganhou dois
testes nesta onda: `test_o_espelho_nao_conhece_quem_carrega` e
`test_os_conectores_nao_conhecem_a_superficie`.

---

## 16.2 Por que o app não se chama `integracoes`

Porque `workspace/integracoes/` já existe e faz outra coisa: é o **link** com o
iConnect Platform — cliente HTTP curto, sessão e middleware, tudo rodando dentro
de uma requisição do usuário.

Dois pacotes com o mesmo nome fazendo trabalhos diferentes é como um `import`
errado passa despercebido numa revisão. `cargas` diz o que o app faz, e
`ExecucaoCarga` mora ali sem precisar de explicação.

### E por que há dois transportes HTTP

Porque os requisitos são opostos:

| | `workspace/integracoes/cliente.py` | `cargas/transporte.py` |
|---|---|---|
| roda | dentro de uma requisição | em comando agendado |
| timeout | 4 s — a tela não pode esperar | 60 s — a carga pode |
| retry | linear, 3× | recuo **exponencial** |
| `POST` | **nunca** repete | é o método de **leitura** do monday |
| paginação | não tem | limite de páginas por execução |
| falha | degrada o widget | marca a carga "parcial" |

A linha do `POST` decide sozinha. A API do monday é GraphQL: toda leitura é um
`POST`, e o cliente do iConnect recusa repetir `POST` — por um motivo correto
lá, que é não duplicar o consumo de um código de uso único.

Além disso, aquele módulo não é um cliente HTTP genérico: é *o cliente do
iConnect*. Ele lê `settings.ICONNECT_API_URL`, e a exceção dele diz "a
integração com o iConnect não está configurada".

**O que os dois compartilham é a disciplina, e ela é amarrada por teste, não por
herança.** `test_nenhum_transporte_registra_credencial` exercita os dois com um
segredo reconhecível no cabeçalho e afirma que ele não aparece em log nenhum.
Código compartilhado ainda pode ser mal usado; o teste amarra os dois
independentemente de como cada um é escrito.

---

## 16.3 O carregador é um só

Conector faz duas coisas: `coletar(janela)` devolve o bruto como veio, e
`normalizar(bruto)` devolve `Registro` no vocabulário do espelho. **Nenhum
conector grava.**

Separar coleta de normalização é o que torna o conector testável sem rede: a
fixture é a saída de `coletar`, e `normalizar` é função pura em cima dela. Os 23
testes de conector desta onda não abrem um socket.

Gravar direito é difícil e sempre igual — e é o que o carregador faz para os
quatro:

**Idempotência por `hash_conteudo`.** Cada registro carrega o SHA-256 do que a
fonte disse. Hash igual não escreve **nada**, nem `importado_em`. Sem isso, rodar
a mesma carga de novo por precaução marcaria o espelho inteiro como
recém-atualizado, e a idade do dado na tela viraria ficção: tudo "há 2 min", nada
realmente novo. O contador `ignorados` é o que prova isso ao operador.

**Falha no meio não desfaz o que entrou.** Cada registro é sua própria
transação. Uma exceção na linha 400 deixa as 399 primeiras gravadas e a execução
marcada `parcial`, com o motivo. Envolver a carga inteira numa transação faria o
oposto: uma linha ruim na quinta hora descartaria cinco horas de dado bom.

**Parcial ≠ falha.** Parcial quer dizer "veio parte, e o que veio é bom". Nada
veio é falha. Chamar os dois de parcial faria o operador procurar um dado que
nunca entrou.

**Rejeitar uma linha não recusa o arquivo.** Planilha feita à mão tem linha ruim
no meio, e descartar as outras trezentas por causa dela seria o pior atendimento
possível a quem preencheu. `rejeitados` conta separado de `ignorados`, porque só
um dos dois pede ação.

---

## 16.4 Os quatro conectores

### `csv` — o canônico, e o primeiro

Um arquivo por entidade em `CARGAS_CSV_DIR`. O formato daqui é o **vocabulário
alvo** dos outros três: um `Registro` produzido pelo CSV e um produzido pelo
Sankhya são indistinguíveis para o carregador.

É por isso que ele vem primeiro, e é o que fará a massa de teste da Onda 3 entrar
pelo mesmo caminho de qualquer outra fonte. **Se a semeadora precisar de um
caminho especial para gravar, o carregador está errado.**

### `sankhya` — financeiro, contábil, folha e ponto

OAuth2 `client_credentials` no Gateway, `loadRecords` paginado por `offsetPage`.
O token dura ~300 s e é renovado sob demanda com 30 s de folga — uma carga de
competência inteira passa disso, e um `401` no meio da paginação custaria a
página e apareceria como carga parcial sem motivo aparente.

**O que este conector não pode saber:** quais entidades e campos a ADB usa.
`rootEntity` é o nome da view *naquela instalação*. O mapa está em `CONSULTAS`,
sobrescritível por `settings.SANKHYA_CONSULTAS`, e o conector falha alto quando
ele não bate — uma consulta que devolvesse zero linhas em silêncio produziria um
espelho vazio com carga "sucesso", que é o pior resultado possível.

### `monday` — projetos, marcos, bloqueios

O parsing de `column_values` é o trabalho de verdade, e as três armadilhas estão
codificadas:

- **status** — usa `label`, não `text`. Quem renomeia um rótulo na tela muda o
  `text` de todo o histórico.
- **board_relation** — não tem `text` útil; traz `linked_item_ids`. É por ele que
  o projeto acha o contrato.
- **mirror** — **ignorado**. Às vezes vem vazio na API mesmo aparecendo na tela,
  e um campo que zera sozinho na carga seguinte é pior que um campo ausente.

### `platform` — contratos, vigência, satisfação

Atravessa o **consolidado**; o detalhe operacional continua lá. O comentário do
detrator vem, **quem escreveu não vem** — é pessoa do cliente, e o Workspace não
é dono desse cadastro.

Há uma lista explícita de campos recusados (`cpf`, `email`, `respondente_*`…), e
ela existe para o dia em que o Platform acrescentar um deles ao payload: ele não
vira coluna do espelho por acidente, que é como grade com CPF nasce.

A paginação recusa `next` apontando para outro host — seguir a URL que o outro
lado mandar é seguir um redirecionamento cego, com o segredo compartilhado junto.

---

## 16.5 Conflito entre fontes

Sankhya e Platform discordam sobre vigência de contrato; Sankhya e monday sobre
valor de projeto. A precedência é **declarada por campo**, em tabela:

| Entidade | Campo | Vence | Por quê |
|---|---|---|---|
| contrato | `fim_vigencia` | Platform | A vigência é renegociada no atendimento, que é onde o Platform vive |
| contrato | `valor_mensal` | Sankhya | Valor é o **cobrado**, e é o cobrado que fecha com a contabilidade |
| contrato | `centro_custo` | Sankhya | O plano de centros de custo é do ERP |
| projeto | `percentual_concluido` | monday | Andamento é atualizado por quem toca o projeto |

Uma linha pode ter `valor_mensal` do Sankhya e `fim_vigencia` do Platform — e
esse é o caso normal, não a exceção.

**Resolver não é concordar.** A divergência é registrada mesmo quando a regra
decidiu: o número entra na tela pela regra, e os dois valores aparecem lado a
lado na tela de fontes (Onda 3) para alguém ir descobrir por que os sistemas
discordam. Silenciar trocaria um problema visível por um invisível.

Campo **sem** regra declarada não trava a carga: a última vence. Exigir uma regra
por campo faria toda coluna nova precisar de uma decisão de negócio antes de
existir — e o efeito prático seria ninguém acrescentar coluna nenhuma.

---

## 16.6 O que a documentação vigente corrigiu

O prompt desta onda mandou conferir a documentação de cada API antes de escrever
o cliente, e não presumir a partir de memória ou exemplo antigo. Foi conferida em
**01/09/2026**, e três coisas mudaram o código:

| Fonte | O que a doc diz hoje | O que eu teria presumido |
|---|---|---|
| monday | versão estável **2026-07** | `scripts/inventario_monday.py` estava com `2024-10` — vencida |
| monday | erro de limite traz `retry_in_seconds` | recuo exponencial cego, esperando de menos ou de mais |
| Sankhya | OAuth2 `client_credentials` + `X-Token` | o fluxo antigo de `username`/`password` em cabeçalho, que ainda circula em exemplos |

O script de inventário também importava `requests`, que **não é dependência
deste projeto** — ele quebraria num venv limpo. Reescrito sobre `urllib`, sem
dependência nova.

A versão da API do monday é **fixada** no conector, e não omitida: sem o
cabeçalho a conta cai na versão padrão do dia, e o dia em que o monday promover a
release candidate a carga mudaria de comportamento sozinha, num domingo.

---

## 16.7 O que ficou pendente, e de quem depende

Nenhum conector de API foi exercitado contra um servidor real, porque nenhuma
credencial existe neste ambiente. Todos foram escritos contra a **forma
documentada** e testados contra **resposta gravada** — que é o que o prompt pede
—, mas isso não substitui a primeira carga de verdade.

| Fonte | O que falta | Quem destrava |
|---|---|---|
| monday | `MONDAY_TOKEN` e os ids de board/coluna | rodar `scripts/inventario_monday.py --com-amostra` |
| Sankhya | `SANKHYA_*` e **quais views** o usuário de integração enxerga | a implantação da ADB |
| Platform | `ICONNECT_API_URL`, `WORKSPACE_SHARED_SECRET` e as rotas de integração | o outro produto |

O acesso MCP ao monday nesta sessão está bloqueado — falta o administrador da
conta habilitar *Public Hosted MCP* —, então o levantamento dos boards reais
continua sendo o script.

**Também pendente:** o agendamento. Estes comandos precisam de cron, junto com os
quatro `avisar_*` que estão abertos desde a onda de notificações.

---

## 16.8 ADRs

### ADR-018 · O espelho não é dono, e não tem formulário

**Contexto:** ter `Contrato` no banco convida a editá-lo — inclusive pelo
`/admin/`, que qualquer `is_staff` alcança.

**Decisão:** nenhum model de `resultados` tem view de criação ou edição, e o
`/admin/` os expõe em **somente leitura**. O dado nasce onde é operado.

**Consequência:** um erro no espelho se conserta na origem, e a próxima carga o
traz certo. Editar aqui produziria duas verdades sobre a mesma linha — e a
segunda venceria até a carga seguinte, ou não venceria, dependendo da
precedência. As duas hipóteses são ruins.

### ADR-019 · Procedência sem integridade referencial

**Contexto:** `ProcedenciaMixin` quer apontar para `FonteDados` e
`ExecucaoCarga`, que moram em `cargas`. FK seria mais forte.

**Decisão:** `fonte` é `CharField` e `carga_id` é inteiro. Sem FK.

**Consequência:** `resultados` não importa `cargas`, e não há ciclo entre apps —
ciclo no grafo de migração é problema de fim de semana. É o mesmo acoplamento
frouxo que `EntradaIndice` já usa com `dominio` + `origem_id`, pelo mesmo motivo:
**o espelho sobrevive à origem**. Apagar o registro de uma carga antiga não pode
apagar o resultado de agosto junto.

O preço é não ter integridade no `carga_id`, e `test_o_espelho_nao_conhece_quem_carrega`
é quem guarda a direção que o banco deixou de guardar.

### ADR-020 · `layer` é calculada, nunca gravada

**Contexto:** layer sai da ROB de 6 meses, e converte porte em obrigação — Layer
3 deve apresentação de resultado. Gravá-la seria mais barato de consultar.

**Decisão:** calculada em `resultados/services.py::layer_de`, com a competência
como corte.

**Consequência:** um contrato que cresceu em julho não fica Layer 1 até alguém
rodar um recálculo. E a layer de agosto não enxerga setembro, então reabrir um
relatório antigo mostra o que a reunião viu — e não o de hoje.

Contrato com menos de dois meses de ROB recebe **"sem amostra"**, e não Layer 1:
Layer 1 quer dizer "pequeno, e por isso dispensado"; "sem amostra" quer dizer
"ainda não sei". Confundir os dois faria um contrato grande e novo escapar da
apresentação no trimestre em que mais precisaria.

### ADR-021 · Dois transportes HTTP, um teste

**Contexto:** `workspace/integracoes/cliente.py` já resolve timeout, retry, log
sem segredo e erro tipado. Reaproveitá-lo parece óbvio.

**Decisão:** `cargas/transporte.py` é um módulo próprio. A garantia
compartilhada — nenhum dos dois registra credencial — mora em
`test_nenhum_transporte_registra_credencial`, que exercita os dois.

**Consequência:** cada transporte tem as constantes certas para o seu contexto
em vez de seis parâmetros para servir aos dois. Ver a tabela em §16.2; a linha
decisiva é o `POST`, que é leitura no monday e escrita no iConnect.
