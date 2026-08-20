# Execução · Etapa 11 — Entrega da auditoria e evolução

> **Documento de entrega.** Responde ao §61 do prompt mestre, seção por seção (A–G).
>
> **19 de agosto de 2026** · 2.308 testes · cobertura 98,52% · ratchet verde

---

## Sumário

- [A. Auditoria](#a-auditoria)
- [B. Implementações](#b-implementações)
- [C. API](#c-api)
- [D. Banco](#d-banco)
- [E. Workflows](#e-workflows)
- [F. Testes](#f-testes)
- [G. Pendências](#g-pendências)

---

## A. Auditoria

### A.1 Duplicidades encontradas — e o que cada uma custava

| o que estava duplicado | as duas metades | o que acontecia na prática |
|---|---|---|
| **Veículo** (§18) | grade de Reservas · item de catálogo `veiculo` | marcar por um caminho não bloqueava o outro. Um lado guardava `datetime`, o outro guardava a frase *"de terça a quinta"* — o choque não era detectável em lugar nenhum, e **duas equipes chegavam na porta esperando a mesma van** |
| **Manutenção predial** (§11) | card no Workspace · chamados do iConnect | dois lugares para abrir o mesmo chamado |
| **`modulos_extras`** (§10) | campo novo · `dominio` | esquema criado para separar "módulo onde aparece" de "fila que executa". A decisão de negócio (o R.H. faz a tratativa) tornou o campo desnecessário — **removido antes de virar esquema morto** |

O item de veículo foi aposentado (`ativo=False`, migração `0044`) e `Veiculo.recurso` é um `OneToOne`: o carro da frota **é** o mesmo recurso reservável, não uma segunda ficha.

### A.2 Vazamentos de permissão — três, dois abertos para a empresa inteira

Todos da mesma classe. `AUTOATENDIMENTO` concede a todo colaborador permissões com escopo `proprio` (`log.ler.proprio`, `hab.ler.proprio`), e `pode(pessoa, "log.ler")` **sem alvo** significa *"posso em geral?"* — verdadeiro para quem tem escopo próprio. As duas coisas estão certas isoladamente; o defeito nasce ao usar essas permissões para guardar tela que mostra dado de **terceiros**.

| tela | permissão errada | o que vazava | correção |
|---|---|---|---|
| **Estoque** | `log.ler` | saldo de todas as unidades, razão, reversa | `log.estoque.ler` (Suprimentos + Compras) |
| **Painel da Universidade** | `hab.ler` | lista **nominal** de quem está com certificado vencido | `hab.auditoria.ler` (SESMT, auditoria, R.H., Diretoria) |
| **Comunicado segmentado** | — | o público-alvo nasceu no §9; o índice de busca continuava gravando `sujeitos=["*"]` com o comentário *"publicação não tem público-alvo ainda"*. A home filtrava certo; a **busca entregava a todo mundo** o comunicado de um departamento, e o detalhe por número na URL fazia o resto | sujeitos derivados de unidades/departamentos + sinal `m2m_changed` + `Publicacao.objects.para()` no detalhe |

E um quarto, introduzido pelo próprio §57 e pego pelo teste: a busca usava `pessoa_da_requisicao()` — a pessoa de **referência** do hub aberto. Com solicitação e correspondência indexadas, o visitante anônimo passava a procurar *como* uma pessoa real e via, com nome e número, os pedidos dela. Corrigido para `request.user`.

### A.3 Funcionalidades quebradas

| defeito | consequência |
|---|---|
| **`orcamento.baixar()` sem chamador** | o compromisso entrava na aprovação e só saía por cancelamento. Como `consumido = realizado + comprometido`, a mesma compra contava **duas vezes** assim que a nota era lançada — a barra do centro de custo subia sozinha até recusar um pedido legítimo |
| **`em_aberto` com lista escrita à mão** | pedido **reprovado** continuava "em aberto" meses depois de o gestor ter dito não |
| **Indicadores com `!= CANCELADA`** | pedido reprovado contava como aberto **e como atrasado, para sempre**, no painel da área |
| **Ninguém avisava a área executora** (§42) | o motor de aprovação roteava certo; o que faltava era o aviso. Aprovado numa sexta esperava até alguém abrir a fila — e o produto *parecia* devolver o pedido ao solicitante |
| **`estoque.conferir_razao()` sem chamador** | a função cuja docstring dizia *"existe para que a divergência seja DETECTÁVEL"* não era executada por ninguém |
| **`au-grade` redefinida** | o CSS da grade de horários colidiu com a do catálogo 400 linhas acima e desmontou a vitrine. O teste escrito para isso achou mais duas (`au-sino`, `au-voltar`) |
| **`Correspondencia.anexo`** | FK para `Anexo`, que exige `solicitacao` — campo impossível de preencher, nulo para sempre |
| **`_hora_fim` com ramos idênticos** | reserva terminando 11:30 deixava o slot das 11 livre |
| **`multiBuild` sem duas passagens** | o rodapé do PDF imprimia "Página 1" sem total |
| **`timezone.now().date()`** | quinta classe de *flake* de relógio: depois das 21h local, a data em UTC já é a de amanhã |

### A.4 O que a revisão de documentos encontrou (§33, §34, §37, §38)

Uma releitura do prompt seção por seção achou quatro coisas — três delas
construídas e uma delas construída **no lugar errado**.

| § | estado antes | correção |
|---|---|---|
| **33** | upload existia; a tabela do acervo tinha 6 das 8 colunas pedidas | `categoria` virou campo do modelo (separada de `tipo`: tipo é a natureza — POP, política —, categoria é o assunto — Segurança, Pessoas). Entraram também `dono` e `anexo` |
| **34** | Relatórios existia, mas como item **solto no trilho** | o pedido é literal — *"card dentro do card principal de documento"* — e é o certo: relatório de entrega e de ocorrência **são** documentos. Agora há card na tela de Documentação e item filho no trilho |
| **35** | assistente, campos e PDF prontos; **faltava a assinatura de quem recebeu** | entrega leva **duas** assinaturas; ocorrência leva uma. Um relatório de entrega prova que alguém recebeu, e prova sem a assinatura de quem recebeu é a versão dos fatos de quem entregou — a que não vale quando o cliente diz que faltou item |
| **37** | acervo, validade, obrigatórios, versão, histórico e busca prontos | entraram **filtros por categoria e texto** e a faixa **"mexeram nestes por último"** |
| **38** | o card **HelpDesk continuava na home** | removido. Ele levava para fora e não fazia mais nada, enquanto `/workspace/chamados/` faz as quatro coisas que o §38 pede — direciona, integra, exibe status, exibe histórico |

**O que do §37 NÃO foi feito, e por quê** (o prompt pede justificativa):

- **Favoritos** — exige tabela por pessoa, tela para gerenciar, e depende de alguém lembrar de marcar. Num acervo de dezenas de documentos, *"os últimos que mudaram"* responde a mesma pergunta sem pedir nada a ninguém.
- **Modelos / biblioteca de templates** — o questionário estruturado dos relatórios (§35–36) já é o modelo, e é melhor que um `.docx` em branco: ele cobra o campo que falta.
- **Assinatura digital com certificado** — é outro produto. A linha de assinatura no PDF resolve o caso real (papel assinado no local); ICP-Brasil exige integração, custódia de chave e decisão jurídica.

### A.5 Riscos que permanecem

1. **Prazo de guarda do atestado médico (LGPD).** Dado de saúde sem política de retenção escrita. Decisão de negócio + jurídico.
2. **Enviar texto para provedor de IA externo.** Contrato, relatório de ocorrência e pergunta de colaborador saem da empresa no dia em que um provedor for registrado. Por isso o padrão do produto é **não ter provedor nenhum**.
3. **`pip-audit` não roda no CI.** Dependência vulnerável é trabalho de ferramenta, não de suíte.

### A.6 Melhorias recomendadas e não feitas

- **Índice unificado com `tsvector`** quando o acervo crescer — hoje o recorte já acontece no `WHERE`, mas o casamento é por `icontains` normalizado.
- **`ExclusionConstraint` para reservas** quando o desenvolvimento rodar PostgreSQL. Hoje a garantia mora no serviço, com `select_for_update` no recurso; uma constraint que existe em produção e não em desenvolvimento é pior que nenhuma.
- **Elevar o piso de cobertura de `financas`** para 100% — subiu e ficou.

---

## B. Implementações

### B.1 Módulos novos

| § | módulo | o que responde |
|---|---|---|
| 3 | **Assistente** | FAQ curada por área, palavra-chave e prioridade; três degraus (base → intenção → IA opcional) |
| 10 | **Candidaturas** | a pergunta invertida sobre os pedidos de vaga que já existem — quem se candidatou a quê, e **quem nunca se candidatou** |
| 15–16 | **Estoque** | saldo por unidade, razão, reversa com procedência, contagem de inventário, requisição com baixa |
| 17 | **Custódia** | quem está com o quê, aceite da pessoa, devolução por condição |
| 18–19 | **Frota** | veículos, prazos de documento, combustível e pedágio, consumo tanque-a-tanque |
| 23 | **Radar de marketing** | feira, edital e patrocínio com o **prazo de decisão** — não a data do evento |
| 27–31 | **Universidade** | cursos, validade congelada na conclusão, alertas em três degraus, painel de conformidade |
| 34–36 | **Relatórios** | assistente de entrega e de ocorrência, PDF gerado no servidor |
| 37 | **Acervo normativo** | redação de POP/política/norma dentro do produto, cobrança de leitura obrigatória |
| 43 | **Rascunho** | o formulário longo deixa de ser tudo-ou-nada |
| 45 | **Comentários** | perguntar sem devolver o pedido |
| 50–51 | **Home contextual** | cards ordenados pelo que custa caro ignorar, derivados do papel |
| 53 | **400/403/404/500 + `/saude/`** | telas de erro do produto e sonda do balanceador |
| 56 | **Camada de IA** | contrato desacoplado; nenhuma tela depende de provedor |

### B.2 Reorganizações

- **Logística → Suprimentos** (§12) — só o rótulo; a chave `logistica` e o domínio `log.` permanecem, porque estão gravados em cada pedido, papel e regra já existentes.
- **Viagem: `fin.` → `log.`** (§13) — Suprimentos passa a reservar, que é quem sempre fez isso.
- **Reembolso → R.H.** (§10) — com a tratativa e a aprovação do gestor.
- **EPI + Uniforme + Material → Controle de materiais** (§14) — três formulários com os mesmos quatro campos viraram um.
- **Retirados da tela** (§10, §22, §24, §26, §11, §18): férias, atestado, declaração, trabalho remoto, card de Compras, material de divulgação, parecer jurídico, manutenção predial, veículo. **Todos com `ativo=False`** — nenhum `delete()`, os pedidos já feitos continuam no histórico e os indicadores do período continuam certos.

---

## C. API

### C.1 Endpoints do iConnect consumidos

| endpoint | § | para quê |
|---|---|---|
| `POST /api/v1/auth/sso-exchange/` | 21 | troca o código de uso único do SSO por JWT |
| `POST /api/v1/auth/jwt/refresh/` | 21 | renova o access, que vale 1 hora |
| `GET /api/v1/tickets/` | 21, 38 | os chamados da pessoa, com RBAC do lado de lá |
| `GET /api/v1/workspace/pending-items/` | 5 | pendências do iConnect no "Meu dia" |
| `GET /fsm/api/tracking/snapshot/` | 18 | onde cada técnico está — GPS do **app do técnico** |
| `GET /fsm/api/ordens-servico/` | 18 | ordens do dia, com `sequencia_rota` já otimizada lá |
| `GET /api/v1/km-audit/rotas/` | 18 | quilometragem já auditada |

**Nenhuma escrita.** Abrir chamado, coletar GPS e otimizar rota continuam sendo do iConnect — o Workspace lê.

### C.2 A camada de integração

`workspace/integracoes/` — o §52 pede uma camada e não chamadas espalhadas por telas.

| arquivo | responsabilidade |
|---|---|
| `cliente.py` | transporte: timeout, retry, log, erro em português |
| `iconnect.py` | vocabulário: `chamados_de()`, `posicoes_dos_tecnicos()`, `ordens_do_dia()` |
| `sessao.py` | identidade: a ponte SSO → JWT e o refresh |
| `middleware.py` | recebe `?sso_exchange=` e o tira da URL **por redirecionamento** |

**Sem `requests`.** `urllib.request` da biblioteca padrão: são seis leituras e um `POST` com header — `requests` traria dependência para manter e CVE para acompanhar em troca de conveniência não usada.

**Retry só em `GET`** e só em erro de rede ou `5xx`. Repetir um `POST` é reenviar, e o único que fazemos consome um código de uso único.

**O §10 do `API.md` está tratado**: vários endpoints devolvem `{"success": false}` com HTTP 200, e o cliente checa o campo; o 403 deles às vezes vem como página HTML, e por isso a mensagem que vai para a tela é nossa, por faixa de código.

### C.3 Endpoints novos criados no Workspace

- `GET /saude/` — sonda do balanceador. JSON mínimo (`{"status","banco"}`), **503** quando o banco não responde, `Cache-Control: no-store`.
- `GET /workspace/assistente/?q=` — resposta do chatbot em HTML/JSON para o painel flutuante.
- `GET /workspace/buscar/?q=` — busca global; devolve **fragmento HTML**, não JSON, porque o consumidor é o próprio navegador.

### C.4 Autenticação

Sessão Django com cookie próprio (`wks_sessao`), `HttpOnly`, `SameSite=Lax`, `Secure` em produção. Login com freio de tentativas (`contas/entrada.py`). **Não há tabela de usuários compartilhada com o iConnect** — a ligação entre os produtos é um link, e o SSO trocará sessão por JWT quando a integração entrar.

---

## D. Banco

### D.1 Models novos

`Material`, `SaldoEstoque`, `MovimentoEstoque`, `Custodia`, `Veiculo`, `DespesaVeiculo`, `Oportunidade`, `Curso`, `Matricula`, `Relatorio`, `EvidenciaRelatorio`, `PerguntaFrequente`, `ComentarioSolicitacao` — 13 modelos, totalizando 32 no app.

**Um modelo que NÃO foi criado, de propósito:** `Candidatura`. A inscrição em vaga interna já é um pedido do catálogo, com currículo e cadeia de aprovação; o §10 foi entregue como *vista* sobre os pedidos existentes.

### D.2 Alterações em models existentes

| model | mudança | por quê |
|---|---|---|
| `SituacaoServico` | `+ RASCUNHO`, `+ REJEITADA` | §43 — o produto não sabia dizer "não", nem guardar o formulário pela metade |
| `SolicitacaoServico` | `+ fase`, `+ prioridade`, `+ e_rascunho` | derivadas, nunca gravadas |
| `ItemCatalogo` | `+ url_externa` | §11 — o card leva para fora em vez de fingir formulário |
| `Correspondencia` | `anexo` (FK) → `foto` (FileField) | a FK era impossível de preencher |
| `Documento` | `+ arquivo`, `+ arquivo_nome`, `+ arquivo_tamanho` | §33 |
| `TipoNotificacao` | `+ 8 tipos` | §46 |
| `OrigemIndice` | `+ 5 origens` | §57 |
| `DespesaVeiculo` | `+ motorista`, `+ destino`, `+ finalidade` | §19 — "custo por técnico" mediria o administrativo que digitou a nota |

### D.3 Migrações

**27 migrações** (`0024`–`0050`), das quais **5 são de dados**: `0026` (trabalho remoto), `0034` (RH reorganizado), `0037` (reembolso e PJ), `0044` (veículo só na grade) e as de catálogo. Todas reversíveis; nenhuma apaga linha.

### D.4 Integridade

- `PROTECT` em tudo que tem histórico atrás: `Material`, `Veiculo`, `ItemCatalogo`, `Pessoa`.
- `CheckConstraint` `quantidade >= 0` no saldo — a regra existe no serviço **e** no banco, porque serviço se contorna com um `update()` distraído.
- `UniqueConstraint` em `SaldoEstoque(material, unidade)`, `Matricula(pessoa, curso)`, `Veiculo.placa`, `Veiculo.recurso`.
- Índices compostos para cada consulta de tela.

---

## E. Workflows

### E.1 O fluxo genérico (§42)

```
1  Colaborador solicita
2  ├─ cabe na política? → APROVADA direto (auto)
3  └─ não? → cadeia por REGRA (gestor → papel da área → diretoria >50k → sócios >300k)
4  APROVADA  →  avisa a ÁREA QUE EXECUTA          ← era o degrau que faltava
5  Área assume → EM_ATENDIMENTO → avisa quem pediu
6  Área conclui → CONCLUIDA → baixa estoque, baixa compromisso, avisa quem pediu
7  Quem pediu discorda → REABERTA, mesmo número, mesma linha do tempo
```

O roteamento sai de `ItemCatalogo.dominio`, que decide **as duas coisas**: em que módulo o item aparece e de quem é a fila. Nenhuma regra é específica de Adiantamento ou Compras.

### E.2 Os dez itens do §45

| capacidade | onde mora |
|---|---|
| etapas | `EtapaAprovacao` + `RegraAprovacao` |
| responsáveis | `TipoAprovador` (gestor direto, papel, cargo) |
| aprovação | `services/aprovacao.decidir` |
| execução | `services/atendimento` |
| conclusão | `atendimento.concluir` |
| SLA | prazo prometido → prazo **medido** (P50 de 180 dias) |
| histórico | `EventoSolicitacao` + timeline |
| comentários | `ComentarioSolicitacao` — interno e visível |
| anexos | `Anexo` em armazenamento privado |
| notificações | `TipoNotificacao`, 8 tipos novos |

### E.3 Estados, e o que cada um significa (§43)

| estado | significa | conta como |
|---|---|---|
| `rascunho` | escrito e **não enviado** | nem esteira, nem terminal |
| `aguardando_aprovacao` | na bandeja de alguém | em aberto |
| `aprovada` | liberada, **esperando a área** | em aberto |
| `em_atendimento` | alguém assumiu | em aberto |
| `devolvida` | corrija e reenvie | em aberto |
| `concluida` / `rejeitada` / `cancelada` | acabou | terminal |

A partição é de três conjuntos disjuntos, e há teste que exige que cubram todos os estados sem sobreposição — foi ele que pegou o `RASCUNHO` caindo dentro de "em aberto" por herança da fórmula antiga.

---

## F. Testes

**2.308 testes · cobertura 98,52% · ratchet verde** (contas 97,37% · financas 100% · identidade 99,66% · workspace 98,38%).

67 arquivos de teste. Os fluxos obrigatórios do §59:

| fluxo | arquivo | testes |
|---|---|---|
| criação de solicitação | `test_catalogo.py` | 63 |
| aprovação | `test_aprovacao.py` | 56 |
| rejeição | `test_reprovar.py` | 16 |
| direcionamento para a área | `test_aviso_a_fila.py` | 11 |
| conclusão | `test_atendimento.py` | 24 |
| notificação | `test_sino.py` | 8 |
| tabbar | `test_listagem.py` | 22 |
| bandeja | `test_telas_servicos.py` | 55 |
| cursos | `test_universidade.py` | 50 |
| documentos | `test_conteudo.py` | 50 |
| uploads | `test_anexos.py` | 35 |
| reservas | `test_reserva.py` | 42 |

### As auditorias são testes, não documentos

`test_auditoria_permissoes.py` (§48), `test_auditoria_seguranca.py` (§55) e `test_auditoria_final.py` (§58) rodam no CI. Uma auditoria em PDF envelhece na primeira semana.

**Elas falharam na primeira execução** — foi assim que os três vazamentos de permissão, o compromisso eterno e as cinco funções mortas apareceram.

### Testes que guardam decisão, não comportamento

- **nenhuma classe base de CSS é redefinida** — pegou `au-grade`, `au-sino`, `au-voltar` e depois `au-erro`
- **nenhuma permissão de porta de terceiros é satisfeita por `AUTOATENDIMENTO`** — falha no commit em que o defeito nasce
- **o 500 renderiza com zero queries** e não estende a casca
- **`timezone.localdate()` em vez de `now().date()`**
- **nenhuma função pública de serviço sem chamador**

---

## G. Pendências

### G.1 A integração com o iConnect — **feita**, e o que falta para ligar

§20, §21, §38 e §52 estão implementados e testados. **Nenhum endpoint novo precisou ser criado no iConnect** — o `API.md` já cobria tudo.

Para ligar em produção, três variáveis de ambiente:

```
ICONNECT_API_URL=https://app.icodev.com.br      # vazia = integração desligada
ICONNECT_TIMEOUT=4                              # segundos
WORKSPACE_SHARED_SECRET=<o mesmo dos dois lados>  # opcional
```

E, do lado do iConnect, `WORKSPACE_BASE_URL` apontando para o Workspace — é o que faz `_safe_redirect_target` aceitar o `?next=`.

**Enquanto as variáveis não existirem, o produto funciona igual**: as telas de Chamados e de Campo dizem que a integração não está configurada, e nada mais muda.

### G.2 Dependem de credencial ou configuração

| item | o que falta |
|---|---|
| **§25 · Análise de contrato com IA** | **a arquitetura está pronta** — `providers/ia.py`, contrato `analisar_documento()`, `Analise` com resumo/riscos/pontos críticos/recomendações e a ressalva jurídica no próprio contrato. Falta **registrar um provedor**: decisão de fornecedor, credencial e a decisão de LGPD sobre enviar contrato para fora |
| **§56 · demais usos de IA** | idem — a camada aceita provedor sem que nenhuma tela dependa dele |
| **agendamento dos 4 comandos diários** | `avisar_habilitacoes`, `avisar_frota`, `avisar_documentos`, `avisar_marketing` precisam de cron. Sem isso, os alertas não saem |
| **`conferir_estoque`** | conferência periódica saldo × razão; sugerido semanal |

### G.3 Dependem de decisão de negócio

| decisão | por que não posso tomá-la |
|---|---|
| **Prazo de guarda do atestado médico** | dado de saúde. Precisa de política escrita, com prazo e responsável — R.H. + jurídico |
| **Enviar documento para provedor de IA externo** | contrato e relatório de ocorrência saem da empresa. É decisão de LGPD, não de código |
| **§23 · monitoramento de fontes públicas** | o radar foi entregue com **cadastro manual**, de propósito. Varrer sites de feira é coleta automatizada de terceiros; avaliar RSS/API de fonte permitida exige escolher as fontes e ler os termos de cada uma |
| **§18 · rastreamento de rota e otimização** | a frota entregue controla cadastro, prazos, odômetro e custo. *Onde o veículo está agora* exige telemetria (GPS embarcado ou app do técnico) — hardware e contrato, não código |

### G.4 Pendências menores, nomeadas

- **Usuários na busca global** (§57). Não indexados: o vocabulário de sujeitos não tem "qualquer pessoa autenticada", e `*` entregaria o organograma — nome, cargo, e-mail — a visitante anônimo. Entra junto com o sujeito novo.
- **`Material` e `Curso`** têm porta no admin, não tela própria. São cadastros de referência mexidos poucas vezes por ano; uma tela para cada seria superfície nova para manter em troca de dois formulários que ninguém abre no dia a dia.
- **Linhas de despesa no rascunho** (§43). O rascunho guarda campos, valor e anexos; **não** guarda as linhas de prestação de contas, porque `DespesaReembolso` exige um comprovante por linha — e uma linha sem comprovante violaria o vínculo que faz a conferência deixar de ser adivinhação.
