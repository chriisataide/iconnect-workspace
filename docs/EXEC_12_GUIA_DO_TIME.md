# Execução · Etapa 12 — Guia do time

> **Documento de referência.** O que o iConnect Workspace faz hoje, quem vê o quê, e as decisões que qualquer mudança precisa respeitar.
>
> Se você vai **operar** (deploy, cron, variáveis), o documento é o [EXEC_13_OPERACAO](EXEC_13_OPERACAO.md).
> Se você quer saber **o que mudou na última rodada**, é o [EXEC_11_ENTREGA](EXEC_11_ENTREGA.md).
>
> **19 de agosto de 2026** · 2.308 testes · cobertura 98,52%

---

## Sumário

- [12.1 A frase que decide tudo](#121-a-frase-que-decide-tudo)
- [12.2 O mapa: onde cada coisa mora](#122-o-mapa-onde-cada-coisa-mora)
- [12.3 O ciclo de vida de uma solicitação](#123-o-ciclo-de-vida-de-uma-solicitação)
- [12.4 Quem vê o quê](#124-quem-vê-o-quê)
- [12.5 As oito regras que o código faz cumprir](#125-as-oito-regras-que-o-código-faz-cumprir)
- [12.6 A fronteira com o iConnect](#126-a-fronteira-com-o-iconnect)
- [12.7 Onde acrescentar coisa nova](#127-onde-acrescentar-coisa-nova)
- [12.8 O que vai reprovar no CI](#128-o-que-vai-reprovar-no-ci)

---

## 12.1 A frase que decide tudo

> **O iConnect Workspace organiza a vida corporativa da empresa.**
> **O iConnect Platform organiza a operação de atendimento aos clientes.**

Toda dúvida de escopo passa por aí. Funcionalidade que serve **ao cliente da empresa** é Platform. Funcionalidade que serve **a quem trabalha na empresa** é Workspace.

E a regra que evita a duplicação mais cara:

> **Se já existe no iConnect, o Workspace lê — não recria.**

Foi o que decidiu o §11 (chamado predial vai para lá), o §38 (abertura de chamado é lá) e o §18 (rastreamento e otimização de rota são do FSM, e o Workspace só mostra).

---

## 12.2 O mapa: onde cada coisa mora

### Os três apps, e a direção da dependência

```
contas  →  identidade  →  workspace
   │           │              │
 Pessoa    organograma    tudo o mais
           papel, escopo   (é FOLHA: ninguém importa dele)
```

`identidade` **nunca** importa `workspace`. Há teste que reprova o commit que tentar.

### As telas, por quem as usa

| quem | telas |
|---|---|
| **todo colaborador** | Início, Meu dia, Notificações, Catálogo, Minhas solicitações, Documentação (com Relatórios dentro), Reservas, Correspondências, Equipamentos, Universidade, Meus chamados, Assistente |
| **quem aprova** | Bandeja de aprovação |
| **quem atende uma fila** | Fila de atendimento |
| **Suprimentos** | Estoque, Custódia (lista de todos), Frota, Campo, Correspondências (registrar) |
| **Recepção** | Correspondências (registrar) — e mais nada |
| **R.H.** | Comunicados, Acervo normativo, Candidaturas, Pessoas e papéis (com **Centros de custo**), Painel da Universidade |
| **Marketing** | Radar de oportunidades |
| **Diretoria e Sócios** | Indicadores |

### Os módulos da home

`rh` · `financeiro` · `operacoes` · `suprimentos` · `redes` · `vendas` · `marketing` · `juridico` · `universidade` · `reservas` · `correspondencias` · `documentacao`

O tile leva à vitrine daquele departamento — a fatia do catálogo que ele atende (`ItemCatalogo.dominio`).

### O fluxo de um pedido — os quatro passos

Vale para **todos** os módulos: Financeiro, R.H., Operação, Suprimentos, Redes, Vendas e Universidade. O que muda entre eles é só quem é a área.

```
  1  colaborador abre no módulo        →  bandeja do GESTOR dele
  2  gestor aprova                     →  fila da ÁREA do módulo onde foi aberto
  3  a área conclui                    →  fim
     ou devolve com o motivo           →  volta para quem pediu, EDITÁVEL
  4  a pessoa corrige e reenvia        →  recomeça do passo 1
```

Acima de R$ 50.000 a diretoria entra entre 1 e 2; acima de R$ 300.000, os sócios também. As faixas **somam** degraus, não os substituem.

**A área toca o pedido uma vez.** Até 20/08/2026 havia um degrau a mais — a área aprovava na bandeja e depois executava na fila —, e o efeito era um pedido que continuava dizendo "aguardando aprovação" depois de o gestor já ter aprovado, sem nada ter mudado de mãos. A revisão da área não sumiu: ela é a fila.

**Devolver tem volta.** Foi o que tornou o parágrafo acima possível. Enquanto devolver era um beco — o pedido voltava, ficava aberto para sempre e a única saída era abrir outro —, reprovar na bandeja era a única forma de dizer não sem prender o pedido. Agora o pedido devolvido volta editável, com o motivo à vista no formulário, e o botão *Enviar solicitação* o promove: **mesma linha, mesmo número, mesmos anexos, mesma conversa.**

Duas decisões dentro do reenvio que custam caro se forem invertidas:

- **a cadeia é refeita.** O gestor aprovou um texto; a pessoa mudou o texto. Reaproveitar a aprovação seria fazer alguém assinar o que não viu;
- **o relógio não volta.** `criado_em` fica onde estava. Se o reenvio zerasse a contagem, devolver viraria o jeito de limpar o próprio atraso.

Quem participa do fluxo não é uma lista escrita em lugar nenhum: é `<raiz>.atender` existir em algum papel. Módulo sem isso aprova o pedido e o deixa numa fila que ninguém abre — e a fase passa a dizer *"Aprovada · sem área responsável"*, que é o diagnóstico. Há teste para os sete.

### O vocabulário de domínios

`dominio` decide **duas coisas ao mesmo tempo**, e é a decisão de arquitetura mais carregada do produto:

1. em que **módulo** o item aparece;
2. de quem é a **fila** que o executa (`rh.` → `rh.atender`).

Mudar o domínio de um item muda as duas. Foi assim que Viagem saiu do Financeiro para Suprimentos (§13) com uma linha.

O nome da área que executa **não** é uma tabela escrita à mão: sai do papel que declara `<raiz>.atender`, a mesma fonte que decide quem vê a fila. É isso que faz a tela dizer *"Aprovada · aguardando Financeiro"* em vez de *"aguardando a área"* — e é isso que faz um pedido cair em *"Aprovada · sem área responsável"* quando nenhum papel atende aquela raiz, que é o diagnóstico que interessa.

| prefixo | área |
|---|---|
| `rh.` | R.H. |
| `fin.` | Financeiro |
| `com.` | Compras |
| `log.` | Suprimentos (o rótulo mudou no §12; a **chave não**, porque está gravada em cada pedido já feito) |
| `ti.` | TI e Redes |
| `ops.` | Operações |
| `mkt.` | Marketing |
| `jur.` | Jurídico |
| `hab.` | Universidade (quem ATENDE a fila é a Segurança do Trabalho) |
| `ven.` | Vendas |
| `res.` `cor.` `cnt.` `apr.` `ind.` `doc.` `faq.` | recursos, correspondência, conteúdo, aprovação, indicadores, documentos, FAQ |

---

## 12.3 O ciclo de vida de uma solicitação

```
  RASCUNHO ─────► AGUARDANDO_APROVACAO ──► APROVADA ──► EM_ATENDIMENTO ──► CONCLUIDA
     │                    │  │                                                  │
  descartar          DEVOLVIDA │                                            REABERTA
  (apaga)            (corrija) │                                          (mesmo nº)
                          REJEITADA / CANCELADA
```

Ou, quando cabe na política (**auto-aprovação**): `RASCUNHO → APROVADA` direto, sem bandeja.

### O que cada estado significa

| estado | significa | conta como |
|---|---|---|
| `rascunho` | escrito e **não enviado** | nem esteira, nem terminal |
| `aguardando_aprovacao` | está na bandeja de alguém | em aberto |
| `aprovada` | liberada, **esperando a área executar** | em aberto |
| `em_atendimento` | alguém assumiu | em aberto |
| `devolvida` | corrija e reenvie — o pedido continua vivo | em aberto |
| `concluida` | entregue | terminal |
| `rejeitada` | não vai acontecer, com autor e motivo | terminal |
| `cancelada` | quem pediu desistiu | terminal |

**A partição é de três conjuntos disjuntos** — em aberto, terminal, não enviado — e há teste que exige que cubram todos os estados sem sobreposição. Foi ele que pegou o `RASCUNHO` caindo dentro de "em aberto".

### Quem é avisado, e quando

| aconteceu | quem recebe |
|---|---|
| pedido criado e precisa de aprovação | o **aprovador da vez** |
| aprovado | quem pediu **e a área que executa** |
| a área assumiu | quem pediu |
| concluído | quem pediu |
| devolvido / reprovado / cancelado | quem pediu |
| reaberto | **o atendente** |
| comentário | **o outro lado** |
| etapa parada num papel sem ninguém | quem pode conceder o papel |

O aviso à **área que executa** era o degrau que faltava. Sem ele, o pedido aprovado numa sexta esperava até alguém abrir a fila — e o produto *parecia* devolver o pedido ao solicitante.

---

## 12.4 Quem vê o quê

### Como uma permissão é escrita

```
<dominio>.<acao>.<escopo>        rh.aprovar.equipe · log.estoque.ler.unidade
```

O **papel** declara com escopo. Quem **chama** pergunta pela ação, sem escopo:

```python
pode(pessoa, "rh.ler", alvo=outra_pessoa)     # o serviço resolve o escopo
```

Escopos: `proprio` · `equipe` · `departamento` · `unidade` · `global`.

### A armadilha que já custou três vazamentos

`AUTOATENDIMENTO` dá a **todo colaborador** um punhado de permissões com escopo `proprio` — `rh.ler.proprio`, `log.ler.proprio`, `hab.ler.proprio`. Elas estão certas: é o que permite alguém ver as próprias férias.

E `pode(pessoa, "log.ler")` **sem alvo** significa *"posso em geral?"* — verdadeiro para quem tem escopo próprio. Também está certo: é assim que "Minhas solicitações" decide que pode abrir.

**O defeito nasce ao juntar as duas coisas:** usar `log.ler` ou `hab.ler` para guardar uma tela que mostra dado de **outras pessoas**. A permissão parece específica da área, o teste manual passa — porque quem testa tem o papel — e a tela fica aberta para a empresa inteira.

> **Regra:** tela de terceiros nunca é guardada por permissão cuja forma `.proprio` esteja em `AUTOATENDIMENTO`. `test_auditoria_permissoes.py` reprova o commit que tentar.

### A guarda de cada tela

| tela | exige |
|---|---|
| Fila de atendimento | `<área>.atender` |
| Bandeja | `apr.aprovar`, ou liderar alguém, ou ter pendência |
| Estoque | `log.estoque.ler` · movimentar exige `log.movimentar` · contar exige `log.inventario.contar` |
| Custódia (lista dos outros) | `log.custodia.ler` · entregar exige `log.custodia.atribuir` |
| Frota e Campo | `log.frota.ler` · editar exige `log.frota.operar` |
| Marketing | `mkt.ler` · decidir exige `mkt.atender` |
| Acervo normativo | `doc.publicar` |
| Comunicados | `com.publicar` |
| Candidaturas | `rh.recrutar` |
| Pessoas e papéis | administração de papel |
| Indicadores | `ind.ler`, ou atender alguma fila |
| Painel da Universidade | `hab.auditoria.ler` |
| Correspondência (fila) | `cor.registrar` |

**403 e nunca lista vazia.** *"Sua fila está vazia"* para quem não atende nada é mentira — e mentira que faz a pessoa esperar por trabalho que nunca vem.

### O hub é aberto, e o que isso NÃO inclui

Sem login, a pessoa vê: a home, a vitrine do catálogo, a documentação pública, a agenda de reservas, o assistente e a busca do que é institucional.

Não vê **nada de ninguém**. `pessoa_da_requisicao()` devolve uma conta real do organograma para calcular *alcance* — quais tiles, quais itens —, e **nunca** para contar. Usá-la para contar já produziu dois vazamentos: os contadores do trilho e, depois, a busca entregando os pedidos de uma pessoa real ao visitante anônimo.

---

## 12.5 As oito regras que o código faz cumprir

### 1 · Estado que depende do calendário é derivado, nunca gravado

Documento vencido, habilitação a vencer, prazo de veículo, situação de custódia, fase do pedido. Um campo gravado fica errado no dia seguinte, a menos que alguém mantenha um cron — e no dia em que o cron falhar, um POP vencido continua sendo apresentado como vigente.

### 2 · Nada é apagado

Item de catálogo retirado vira `ativo=False`. Pedido cancelado vira `CANCELADA`. Documento revogado sai da vitrine e continua acessível por link direto. **Uma exceção**, e ela se justifica: descartar um **rascunho** apaga — nunca foi enviado, ninguém foi avisado, nenhum prazo correu, e guardá-lo como "cancelado" faria a taxa de cancelamento contar pedidos que nunca existiram.

### 3 · O razão é a verdade; o saldo é atalho

`MovimentoEstoque` é um livro: uma linha por movimento, e nada apaga linha. `SaldoEstoque.quantidade` é o mesmo número somado, denormalizado porque "cabe no saldo?" é perguntado a cada requisição. Quando os dois discordam, **o razão está certo** — e `conferir_estoque` existe para detectar isso.

### 4 · A conferência não pode ter duas fontes

Confirmação de leitura guarda a **versão**. Comentário não se edita nem se apaga. Relatório emitido não muda. Compromisso baixado fica no histórico.

### 5 · Prioridade e prazo são medidos, não declarados

O card do catálogo mostra o prazo **real** (P50 dos últimos 180 dias) depois de 5 conclusões. A prioridade da fila é derivada do prazo prometido. Prioridade declarada por quem pede vira "urgente" para todo mundo no terceiro mês.

### 6 · Nada depende de IA

`providers/ia.py` é um contrato. Sem provedor registrado, todo método devolve `None` e cada tela mantém o caminho determinístico: o assistente responde pela base curada, a busca funciona pelo índice, o relatório sai do questionário. Um assistente que só responde com o provedor de pé falha no dia do incidente — e é no dia do incidente que as pessoas perguntam onde fica alguma coisa.

### 7 · Arquivo nunca fica onde o servidor web serve sem perguntar

Todo `FileField` usa `ArmazenamentoPrivado`, que **não tem `base_url`** — `.url` levanta `ValueError` de propósito. A única porta até o arquivo é uma view que pergunta quem é. Todo upload passa pelo mesmo validador: extensão, MIME e *magic bytes*.

### 8 · Nenhum estilo ou handler inline

A CSP é `default-src 'self'`, sem `unsafe-inline`. Navegador moderno **descarta `style=""` em silêncio** quando há política estrita — o elemento simplesmente não recebe o estilo, e nada aparece no log. Por isso a barra tripla da bandeja é desenhada em SVG, onde `width` é atributo.

---

## 12.6 A fronteira com o iConnect

**Dois produtos, dois deploys, dois bancos.** Não há tabela de usuários compartilhada, banco comum nem sessão comum. O que existe:

```
   Workspace  ──── lê por HTTP ───►  iConnect
       │                                │
   SSO comum ◄──── código de uso único ─┘
```

### A divisão que evita a próxima duplicação

| | dono |
|---|---|
| chamado — abrir, atender, encerrar | **iConnect** |
| onde o técnico está, rota, ordem de serviço, KM auditado | **iConnect** (FSM, alimentado pelo app do técnico) |
| placa, licenciamento, seguro, IPVA, combustível, custo por km | **Workspace** |
| solicitação corporativa, aprovação, estoque, custódia, acervo, universidade | **Workspace** |

### O que o Workspace lê

| endpoint | para quê |
|---|---|
| `POST /api/v1/auth/sso-exchange/` | troca o código do SSO por JWT |
| `POST /api/v1/auth/jwt/refresh/` | renova o access (vale 1h) |
| `GET /api/v1/tickets/` | os chamados da pessoa |
| `GET /api/v1/workspace/pending-items/` | pendências no "Meu dia" |
| `GET /fsm/api/tracking/snapshot/` | onde cada técnico está |
| `GET /fsm/api/ordens-servico/` | ordens do dia, com a rota já otimizada lá |
| `GET /api/v1/km-audit/rotas/` | quilometragem auditada |

**Nenhuma escrita.** Há teste que verifica que todas as chamadas são `GET`.

### E quando o iConnect não responde

Nada quebra. A tela desenha, diz o que houve **em português**, e mostra o que o Workspace já sabia. O contador de chamados no trilho **nunca levanta** — ele está em toda tela do portal, e uma exceção ali derrubaria o produto inteiro por causa de outro deploy.

Sem `ICONNECT_API_URL` configurada, a integração está **desligada** e isso é estado normal, não falha: as telas dizem "não está configurada", e nada mais muda.

---

## 12.7 Onde acrescentar coisa nova

### Um serviço novo no catálogo

Não escreva view nem template. Acrescente um item em `workspace/catalogo_inicial.py` e rode `semear_catalogo --atualizar`. O formulário, a validação, a cadeia de aprovação, a fila, o histórico e as notificações vêm de graça.

```python
{
    "chave": "cracha-novo",
    "termos": ["crachá", "credencial", "identificação"],   # como as pessoas CHAMAM
    "nome": "Segunda via de crachá",
    "grupo": GrupoCatalogo.EQUIPAMENTO,   # por INTENÇÃO, nunca por departamento
    "dominio": "rh.documento",            # decide o módulo E a fila
    "prazo_prometido_dias": 3,
    "campos": [...],
}
```

`termos` é o que faz o assistente e a busca funcionarem sem IA — **cada termo aqui é um e-mail que ninguém precisou mandar.**

### Uma regra de aprovação nova

`workspace/models/aprovacao.py` + `semear_regras_aprovacao`. As regras valem por **domínio e faixa de valor**, e a cadeia é montada por ordem: gestor direto (10) → papel da área (15) → diretoria acima de R$ 50k (20) → sócios acima de R$ 300k (30).

### Um módulo inteiro novo

O caminho é sempre o mesmo, nesta ordem:

```
models/<nome>.py     ── o que é, com as invariantes no banco
services/<nome>.py   ── as regras, e a permissão. Nenhuma view decide nada
views/<nome>.py      ── agrega. O template desenha
templates/           ── burro de propósito: sem comparar string de estado
urls.py              ── a rota
services/painel.py   ── o contador e o card, se houver
_rail_servicos.html  ── a porta, só para quem pode abri-la
tests/test_<nome>.py ── inclusive quem NÃO pode
```

### Uma origem nova na busca

`services/indice.py` → uma função `indexar_<coisa>` e uma linha em `_origens()`. Sinal e reindexação saem da **mesma tabela** — listas separadas é como uma origem passa a existir só depois de alguém rodar o comando à mão.

### Uma classe CSS nova

Prefixo do módulo, sempre: `au-frota-`, `au-custodia-`, `au-tela-erro-`. Nomes curtos e óbvios **já estão tomados** — `au-grade` derrubou o catálogo inteiro uma vez, e `au-erro` quase transformou cada aviso de campo num bloco centrado de 34rem.

Etiqueta de estado leva prefixo do domínio: `au-etiqueta--cst-devolvida`, `au-etiqueta--tk-aberto`. Sem isso, "devolvida" do pedido (vermelho, voltou errado) pinta de perigo a custódia devolvida (que é o fim feliz).

---

## 12.8 O que vai reprovar no CI

O CI não roda só os testes de comportamento. Estes cinco guardam **decisões**, e falham no commit em que a decisão é violada:

| teste | reprova quando |
|---|---|
| `test_auditoria_permissoes` | uma tela de terceiros é guardada por permissão satisfeita por `AUTOATENDIMENTO`; uma permissão pedida não existe em papel nenhum |
| `test_auditoria_seguranca` | `style=` ou handler inline num template; formulário `POST` sem CSRF; `FileField` fora do armazenamento privado; ação que muda estado respondendo a `GET`; tela pessoal aberta a anônimo |
| `test_auditoria_final` | rota órfã; template órfão; função pública de serviço sem chamador; modelo sem tela e sem admin; migração faltando |
| `test_classes_com_css` | classe base de CSS redefinida (a cascata faz a de baixo vencer, 400 linhas depois) |
| `test_isolamento` | `identidade` importando `workspace` |

E o **ratchet**: cobertura por app só sobe (`contas` 97 · `financas` 99 · `identidade` 99 · `workspace` 98) e a contagem de testes tem piso. Queda intencional exige justificativa no PR.

```bash
pytest -q                                  # a suíte
python scripts/check_coverage_ratchet.py   # o ratchet
python manage.py makemigrations --check    # modelo mudado sem migração
```
