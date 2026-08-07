# Execução · Etapa 4 — PRD por Módulo

> **Documento de produto.** Para cada um dos 13 módulos: problema, usuários, personas, casos de uso, estados, validações, integrações, métricas, KPIs, riscos, backlog e roadmap.
>
> **Agosto/2026** · Etapa 4 de 9 · **Aguarda aprovação antes da Etapa 5**

---

## 4.0 Método — o que esta etapa acrescenta

A [Etapa 3](EXEC_03_MODULOS.md) fixou o **contrato estrutural**: schema, API, permissões, componentes, fluxos principais e critérios de aceite técnicos. Repetir isso aqui produziria um documento longo e sem informação nova.

**A Etapa 4 acrescenta a camada de produto:**

| Seção pedida | Onde está | Nota |
|---|---|---|
| Objetivo · Fluxos · Regras · Permissões · Critérios de aceite | **Etapa 3** | Referenciado, não repetido |
| **Problema** (a dor, quantificada) | Aqui | Novo |
| **Usuários e Personas** | §4.1 (global) | Definidos uma vez, referenciados por módulo |
| **Casos de uso** com ID rastreável | Aqui | Novo — `UC-<DOM>-NN` |
| **Estados** (máquinas de estado) | Aqui | Novo — a lacuna mais séria de qualquer spec |
| **Validações** com mensagem ao usuário | Aqui | Novo |
| **Integrações** | Aqui | Novo |
| **Métricas e KPIs** por módulo | Aqui | Novo |
| **Riscos** por módulo | Aqui | Novo, além dos 21 globais |
| **Backlog** (épico → feature) | Aqui | `EP-NNN` / `FT-NNN`. Story e task na Etapa 7 |
| **Roadmap** por módulo | Aqui | V1.0 → V1.1 → V2 → V3 |

### Convenções

| Elemento | Formato | Exemplo |
|---|---|---|
| Caso de uso | `UC-<DOM>-NN` | `UC-APR-03` |
| Épico | `EP-NNN` | `EP-014` |
| Feature | `FT-NNN` | `FT-041` |
| Estado | `minusculo_com_underscore` | `pendente_configuracao` |
| Validação | `VAL-<DOM>-NN` | `VAL-SVC-02` |

---

## 4.1 Personas

Cinco personas primárias no V1.0, mais uma afetada-mas-não-usuária. Todas ancoradas no vertical: empresa de segurança eletrônica, monitoramento e serviço de campo, porte médio.

### P1 · Marina — Analista administrativa
**Papel:** `colaborador` · 29 anos · 3 anos de casa · escritório, desktop

> *"Toda vez que preciso de alguma coisa eu mando mensagem pra alguém e torço."*

| Dimensão | |
|---|---|
| **Faz no dia** | Atende cliente por e-mail, lança dados, pede coisas para TI/RH/Compras |
| **Dor** | Não sabe onde pedir nada. Pede no WhatsApp, não tem protocolo, não sabe o prazo, esquece |
| **O que a faria voltar** | Ver o status do que pediu sem perguntar a ninguém |
| **Risco de rejeição** | Se o Workspace for "mais um sistema para lembrar de abrir", ela não abre |
| **Módulos** | SVC · CNT · COM · WKS · SRC |

### P2 · Rogério — Gestor de operação
**Papel:** `gestor` + `operacao` · 46 anos · 12 anos de casa · desktop e celular, muito em movimento

> *"Aprovo no celular sem saber direito o que estou aprovando, porque se eu não aprovar a operação para."*

| Dimensão | |
|---|---|
| **Faz no dia** | Monta escala, cobre falta, aprova pedido, apaga incêndio de SLA |
| **Dor** | Escala em planilha compartilhada. Aprova por WhatsApp sem contexto. Descobre certificação vencida quando o cliente reclama |
| **O que o faria voltar** | Uma tela que responde "quem está trabalhando agora e o que trava" |
| **Risco de rejeição** | Se aprovar der mais trabalho que o WhatsApp, ele volta pro WhatsApp |
| **Módulos** | APR · OPS · PPL · WKS |

### P3 · Cláudia — Analista de RH
**Papel:** `rh` · 38 anos · desktop

> *"Ninguém me avisa que a NR do técnico venceu. Eu descubro na auditoria."*

| Dimensão | |
|---|---|
| **Faz no dia** | Mantém cadastro, controla férias, corre atrás de documento e certificação |
| **Dor** | Base de pessoas divergente entre sistemas. Certificação controlada em planilha. Comunicado enviado por e-mail sem prova de leitura |
| **O que a faria voltar** | Fila de divergências e alerta de vencimento chegando antes do problema |
| **Módulos** | IDN · PPL · COM |

### P4 · Paulo — Diretor
**Papel:** `admin` (escopo global) · 52 anos · celular, sempre em reunião

> *"Eu sou o gargalo e sei disso."*

| Dimensão | |
|---|---|
| **Faz no dia** | Aprova o que passa do limite, cobra número, decide |
| **Dor** | Recebe pedido sem contexto. Aprova no escuro ou trava a fila |
| **O que o faria voltar** | Bandeja com valor, orçamento e histórico do solicitante, resolvida em 2 minutos |
| **Risco de rejeição** | Se levar mais de 5 minutos, ele não usa |
| **Módulos** | APR · WKS |

### P5 · Sandra — Comunicação interna
**Papel:** `comunicacao` · 34 anos · desktop

> *"Mando o comunicado e não faço ideia se alguém leu."*

| Dimensão | |
|---|---|
| **Faz no dia** | Escreve comunicado, política, campanha. Responde à qualidade em auditoria |
| **Dor** | E-mail sem retorno. Auditoria pede evidência de que a política foi comunicada, e não existe |
| **O que a faria voltar** | Relatório de quem confirmou leitura |
| **Módulos** | COM · CNT |

### P6 · Marcos — Técnico de campo *(afetado, não usuário do V1.0)*
**Papel:** `tecnico_campo` · 41 anos · celular, app nativo, muito sem sinal

Não usa o Workspace no V1.0 ([D-05](EXEC_01_ESCOPO_E_DEPENDENCIAS.md)). **É afetado por duas coisas:**
1. `PPL-005` — se a certificação vencer, ele deixa de receber OS daquele tipo
2. `COM` — recebe comunicado obrigatório pelo app nativo, via API

> **Cuidado de produto:** Marcos precisa entender o bloqueio **antes** de ser bloqueado. Se a primeira notícia for "você não recebeu OS hoje", o recurso vira punição. Por isso `PPL-006` (alerta em 90/30/15/5) é V1.0 junto com `PPL-005`, não depois.

### P7 · Administrador de TI *(operador da plataforma)*
**Papel:** `admin` · Configura papéis, publica catálogo, liga flags, monitora custo de IA. Não é usuário-fim, é quem sustenta.

---

## 4.2 Jornadas de referência

Quatro jornadas que atravessam módulos. Servem de teste de integração de produto: se a jornada quebra, o release não sai.

### J1 · Primeiro acesso de Marina *(5 minutos que decidem a adoção)*
```
SSO  →  "Confirme seu gestor e centro de custo"     [IDN — valida o organograma
                                                     usando a própria pessoa]
     →  3 comunicados obrigatórios pendentes        [COM]
     →  confirma leitura                            [CNT]
     →  Workspace: Zona 1 limpa, 6 widgets
```
**Critério:** nenhum campo que o sistema já saiba. Marina só **confirma**.

### J2 · Rogério aprova antes da reunião das 9h
```
Notificação 08:00  →  abre Workspace  →  widget Aprovações (6 itens)
   →  aprova 4 em lote                             [APR]
   →  devolve 1 com motivo                         [APR]
   →  1 fica: valor acima do limite dele → sobe pro Paulo
   →  olha widget Escala: 1 lacuna de cobertura    [OPS]
Tempo alvo: < 4 minutos
```

### J3 · Marina pede um notebook
```
⌘K "notebook"                                      [SRC]
   →  item "Equipamento de trabalho"               [SVC]
   →  formulário com 1 campo livre (justificativa) —
      unidade, CC, gestor e equipamento atual vêm do perfil  [IDN]
   →  [Enviar]  →  ticket criado + aprovação para o Rogério  [APR]
   →  status aparece em "Meu dia"                  [WKS]
```

### J4 · Cláudia evita uma não-conformidade
```
Alerta automático: "NR-10 de Marcos vence em 30 dias"   [PPL-006]
   →  Cláudia agenda a reciclagem
   →  se vencer: Marcos sai da fila de despacho daquele tipo  [PPL-005]
   →  quem despacha vê o motivo e quem está habilitado        [OPS]
```
**Este é o diferencial do produto em uma jornada.**

---

## 4.3 Convenções de estado, validação e métrica

### Estados — regras gerais

| # | Regra |
|:-:|---|
| E1 | Todo objeto com ciclo de vida tem estado **explícito** em campo, nunca inferido de datas nulas |
| E2 | Transição inválida levanta exceção no **serviço**, não é só ausência de botão na tela |
| E3 | Todo estado terminal é irreversível por operação normal — reverter exige ação administrativa auditada |
| E4 | Mudança de estado registra **quem, quando e por quê** quando houver decisão humana |

### Validações — regras gerais

| # | Regra |
|:-:|---|
| V1 | Validação de negócio vive no **serviço ou no model**, nunca só no formulário |
| V2 | Toda validação tem mensagem em português, específica, e diz **o que fazer** |
| V3 | Validação que depende de permissão usa `pode()` ([Etapa 3 §3.1.3](EXEC_03_MODULOS.md)) |
| V4 | Constraint de banco existe para o que não pode acontecer nunca — não substitui a mensagem, garante a integridade |

### Métricas — regras gerais

| # | Regra |
|:-:|---|
| M1 | Métrica sem linha de base não é métrica. Coletar antes do lançamento ([Etapa 2 §2.8](EXEC_02_MVP.md)) |
| M2 | Instrumentação faz parte da feature, não é tarefa posterior |
| M3 | Toda métrica tem dono, meta e prazo. Sem os três, sai do painel |

---

## 4.4 PRD · IDN — Identidade & Organização

### Problema
A empresa não sabe formalmente quem responde por quem. Cargo e departamento existem como texto livre em `PerfilUsuario`; não há unidade, gestor, centro de custo nem organograma. Isso torna impossível: rotear uma aprovação, definir público-alvo de um documento, saber quem cobre quem nas férias, ou dar permissão por escopo.

**Custo atual:** toda aprovação é roteada por conhecimento tácito ("manda pro Rogério que ele resolve"). Quando Rogério sai de férias, a fila para.

### Usuários e personas
**Primários:** P3 (Cláudia/RH), P7 (admin) · **Consumidores indiretos:** todos

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-IDN-01 | Importar a base inicial de pessoas do RH | P3 | V1.0 |
| UC-IDN-02 | Resolver divergência entre iConnect e RH | P3 | V1.0 |
| UC-IDN-03 | Atribuir papel com escopo e vigência | P7 | V1.0 |
| UC-IDN-04 | Delegar papéis por período | P2, P4 | V1.0 |
| UC-IDN-05 | Registrar desligamento e revogar acessos | P3 | V1.0 |
| UC-IDN-06 | Confirmar meu gestor e centro de custo no primeiro acesso | P1 | V1.0 |
| UC-IDN-07 | Consultar o organograma | todos | V1.1 |

### Estados

**`PerfilUsuario.situacao`**
```
        ┌──────────────────────────────┐
        ▼                              │
   ┌─────────┐   ausência aprovada  ┌──┴──────┐
   │  ativo  │────────────────────▶ │ ferias  │
   │         │                      │afastado │
   └────┬────┘ ◀────────────────────└─────────┘
        │            fim da ausência
        │  desligamento
        ▼
   ┌────────────┐   TERMINAL
   │ desligado  │   revoga atribuições + delegações (mesma transação)
   └────────────┘
```

**`ConflitoSincronizacao.status`:** `aberto` → `resolvido` (terminal, com decisão e justificativa)

**`AtribuicaoPapel`** — não tem campo de estado. A vigência **é** o estado: vigente se `vigencia_inicio <= hoje <= (vigencia_fim ou ∞)`. Isso evita o clássico "status=ativo mas vigência vencida".

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-IDN-01 | Gestor não pode gerar ciclo no organograma | *"Não é possível: isso criaria um ciclo na hierarquia (Ana → Bruno → Ana)."* |
| VAL-IDN-02 | Gestor deve estar ativo | *"Ana Prado está desligada e não pode ser definida como gestora."* |
| VAL-IDN-03 | `vigencia_fim` ≥ `vigencia_inicio` | *"A data de fim precisa ser igual ou posterior à de início."* |
| VAL-IDN-04 | Delegação não amplia permissão | *"Você não pode delegar 'aprovar global' porque não possui essa permissão."* |
| VAL-IDN-05 | Delegação nunca inclui o papel `admin` | *"O papel Administrador não pode ser delegado."* |
| VAL-IDN-06 | Campo espelho não é editável pelo colaborador | *"Cargo é mantido pelo RH. Se estiver incorreto, abra uma solicitação."* |
| VAL-IDN-07 | Matrícula única quando informada | *"A matrícula 4821 já pertence a Bruno Lima."* |
| VAL-IDN-08 | Override em campo derivado exige justificativa (≥10 caracteres) | *"Explique por que este valor difere do sistema de RH."* |

### Integrações

| Sistema | Direção | Natureza | Nota |
|---|:-:|---|---|
| Sistema de RH | ← leitura | Conector por CSV, API ou banco | **Bloqueado por Q-01.** O desenho não depende da resposta; a implementação sim |
| `dashboard.User` | ↔ | OneToOne existente | Preservado |
| `fsm.Tecnico` | ↔ | Via `User` | `IDN-006` |
| `dashboard.CentroCusto` | ← | FK | Reuso |
| SSO (SAML/OIDC) | ← | Atributos do provedor podem popular campos espelho | Existente |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo | Dono |
|---|---|:-:|:-:|---|
| K-IDN-01 | Pessoas com gestor definido | 100% | lançamento | P3 |
| K-IDN-02 | Pessoas com centro de custo | ≥ 95% | lançamento | P3 |
| K-IDN-03 | Conflitos abertos há mais de 7 dias | 0 | contínuo | P3 |
| K-IDN-04 | Tempo de resolução de `pode()` (p95) | ≤ 20 ms | contínuo | eng |
| K-IDN-05 | Aprovações que caíram em `pendente_configuracao` | < 2% | 60 dias | P7 |

> **K-IDN-05 é o termômetro do organograma.** Se sobe, é sinal de que a estrutura está incompleta — não de que o motor de aprovação falhou.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-IDN-01 | Base de pessoas suja (`R-20`) | Importar em homologação com a base real na semana 2 |
| RM-IDN-02 | Cache de permissão desatualizado após mudança de papel | Cache **por request**, nunca entre requests |
| RM-IDN-03 | Organograma incompleto trava aprovação | `pendente_configuracao` + alerta (nunca falha em silêncio) |
| RM-IDN-04 | Migração `departamento` texto → FK deixa resíduo | Comando de gestão reporta o não casado; texto só sai com resíduo zero |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-001** | **Fundação de identidade** | V1.0 |
| FT-001 | Modelos `Unidade`, `Departamento`, `Papel` | V1.0 |
| FT-002 | Evolução de `PerfilUsuario` (matrícula, situação, FKs, `origem_campos`) | V1.0 |
| FT-003 | Migração `UserRole` → `AtribuicaoPapel` com escopo e vigência | V1.0 |
| FT-004 | `Delegacao` com validação de não-ampliação | V1.0 |
| FT-005 | Serviço `pode()` com resolução dos 5 escopos + cache por request | V1.0 |
| **EP-002** | **Sincronização com o RH** | V1.0 |
| FT-006 | Conector e importação inicial | V1.0 |
| FT-007 | Reconciliação e `ConflitoSincronizacao` | V1.0 |
| FT-008 | Fila de conflitos com resolução | V1.0 |
| FT-009 | Task Celery de sincronização periódica | V1.0 |
| **EP-003** | **Organograma** | V1.0 |
| FT-010 | Gestor ↔ liderados com validação de ciclo | V1.0 |
| FT-011 | Confirmação de gestor e CC no primeiro acesso (J1) | V1.0 |
| FT-012 | Visualização do organograma | V1.1 |
| FT-013 | Diretório e perfil público (`IDN-008`) | V1.1 |

### Roadmap

| Versão | Entrega |
|:-:|---|
| **V1.0** | Identidade, organograma, papéis com escopo, delegação, sincronização híbrida |
| **V1.1** | Diretório, perfil público, visualização do organograma |
| **V2** | Sucessão e cobertura automática, histórico de carreira |
| **V3** | Grafo organizacional (quem trabalha com quem, inferido da operação) |

---

## 4.5 PRD · PLT — Plataforma

### Problema
A base visual atual (Material Dashboard 2 + Bootstrap) carrega decisões de 2019 e não sustenta a ambição de qualidade. Além disso, não existe mecanismo para ligar uma funcionalidade para um grupo e desligar em minutos — todo lançamento é "tudo ou nada por deploy", o que torna qualquer piloto arriscado.

### Usuários e personas
**Primário:** P7 (admin) · **Beneficiário:** todos

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-PLT-01 | Ligar o Workspace para um grupo piloto | P7 | V1.0 |
| UC-PLT-02 | Desligar o Workspace em minutos, sem deploy | P7 | V1.0 |
| UC-PLT-03 | Usar o Workspace em tema escuro | todos | V1.0 |
| UC-PLT-04 | Auditar quem acessou dados de uma pessoa | P3, P7 | V1.0 |

### Estados

**`FeatureFlag`** — não tem máquina de estado; é booleano com público-alvo. **Deliberado:** flag com ciclo de vida vira feature própria e ninguém desliga.

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-PLT-01 | Flag desligada nunca serve o conteúdo (servidor, não CSS) | — (invisível ao usuário) |
| VAL-PLT-02 | Componente sem os 8 estados não entra na biblioteca | — (revisão de código) |
| VAL-PLT-03 | Classe Tailwind fora de `workspace/` reprova o PR | *"Tailwind é restrito ao app workspace (ADR/A-02)."* |

### Integrações

| Sistema | Natureza |
|---|---|
| SSO existente | Reuso direto |
| `AuditMiddleware` existente | Estendido para leituras de `Pessoa` e `Aprovacao` |
| Tailwind CLI | Build isolado, fora do `compressor` |
| CSP nonce existente | Mantido — Alpine e HTMX precisam de configuração compatível |

> **Atenção técnica:** o projeto usa CSP com nonce ([CSPNonceMiddleware](../dashboard/middleware.py)). Alpine.js exige `unsafe-eval` ou o build CSP-friendly. **Decisão para a Etapa 5:** usar a distribuição CSP do Alpine, sem afrouxar a política.

### Métricas e KPIs

| ID | Métrica | Meta | Prazo |
|---|---|:-:|:-:|
| K-PLT-01 | Tempo de rollback do Workspace | ≤ 5 min | lançamento |
| K-PLT-02 | Cobertura do app `workspace` | ≥ 75% | lançamento |
| K-PLT-03 | Violações de Tailwind fora do escopo | 0 | contínuo |
| K-PLT-04 | Regressões em produção atribuídas ao Workspace | 0 críticas | contínuo |

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-PLT-01 | CSP quebra Alpine/HTMX em produção | Testar CSP em homologação com a política **de produção**, não a de dev |
| RM-PLT-02 | Estilo do Material Dashboard vaza para o Workspace (`R-09`) | Casca sem herança de CSS; verificação de especificidade no aceite |
| RM-PLT-03 | Flag esquecida ligada permanentemente | Revisão trimestral; flag com mais de 2 releases vira decisão de remover |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-004** | **Aurora — fundação visual** | V1.0 |
| FT-014 | Tokens (cor, espaço, tipografia, elevação, movimento, densidade) | V1.0 |
| FT-015 | Pipeline Tailwind isolado + regra de CI | V1.0 |
| FT-016 | Dark mode por `prefers-color-scheme` | V1.0 |
| FT-017 | Biblioteca de ~24 componentes (inventário na Etapa 6) | V1.0 |
| **EP-005** | **Infraestrutura do Workspace** | V1.0 |
| FT-018 | App `workspace` + `WorkspaceProvider` | V1.0 |
| FT-019 | Feature flags por papel e por pessoa | V1.0 |
| FT-020 | Extensão da auditoria para dados de pessoa e aprovação | V1.0 |
| FT-021 | Gate de cobertura em `fsm` e `km_audit` | V1.0 |
| FT-022 | Configurações administrativas do Workspace | V1.1 |
| FT-023 | `threading.local()` → `contextvars` | V1.1 |

### Roadmap

| Versão | Entrega |
|:-:|---|
| **V1.0** | Aurora, app isolado, flags, auditoria estendida, gates |
| **V1.1** | Configurações no produto, `contextvars`, preferências de usuário |
| **V2** | Mudança operacional revisada (diff + blame de configuração) |
| **V3** | Tenancy real, API pública de widget |

---

## 4.6 PRD · APR — Aprovações

> **Módulo de maior impacto percebido do V1.0.**

### Problema
Não existe motor de aprovação. Aprovação acontece por WhatsApp e e-mail, sem registro, sem cadeia, sem contexto e sem delegação. Três consequências:

1. **O aprovador decide no escuro** — recebe "posso comprar?" sem valor, sem orçamento, sem histórico
2. **Férias travam a empresa** — não há delegação, então a fila para
3. **Não há prova** — quando alguém pergunta "quem autorizou isso?", a resposta é uma busca no WhatsApp

**Custo atual a medir antes do lançamento:** tempo médio entre pedido e decisão (amostra de 30 casos).

### Usuários e personas
**Primários:** P2 (Rogério), P4 (Paulo) · **Secundário:** P1 (Marina, como solicitante) · **Configurador:** P7

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-APR-01 | Ver o que espera minha decisão | P2, P4 | V1.0 |
| UC-APR-02 | Aprovar um item sem sair da home | P2 | V1.0 |
| UC-APR-03 | Aprovar vários em lote | P4 | V1.0 |
| UC-APR-04 | Devolver pedindo mais informação | P2 | V1.0 |
| UC-APR-05 | Reprovar com motivo | P2 | V1.0 |
| UC-APR-06 | Delegar minhas aprovações nas férias | P2 | V1.0 |
| UC-APR-07 | Acompanhar o que eu pedi | P1 | V1.0 |
| UC-APR-08 | Configurar política de auto-aprovação | P7 | V1.0 |
| UC-APR-09 | Ver o impacto no orçamento antes de aprovar | P4 | V1.1 |
| UC-APR-10 | Escalonar o que está parado | sistema | V1.1 |

### Estados

**`SolicitacaoAprovacao.status`**
```
                    ┌─── política: dentro do limite ───▶ aprovada (auto)
                    │
   [criada] ────────┼─── política: fora ──▶ ┌─────────────────┐
                    │                       │  em_aprovacao   │
                    │                       └────┬───┬────┬───┘
                    │       todas as etapas OK ──┘   │    │
                    │                    ▼           │    │
                    │              ┌──────────┐      │    │
                    │              │ aprovada │      │    │  TERMINAL
                    │              └──────────┘      │    │
                    │      qualquer etapa reprova ───┘    │
                    │                    ▼                │
                    │              ┌───────────┐          │  TERMINAL
                    │              │ reprovada │          │
                    │              └───────────┘          │
                    │      etapa devolve ─────────────────┘
                    │                    ▼
                    │              ┌────────────┐  solicitante corrige
                    │              │ devolvida  │──────────────┐
                    │              └────────────┘              │
                    │                    │ solicitante desiste │
                    │                    ▼                     ▼
                    └──────────────▶ ┌───────────┐      (volta a em_aprovacao,
                                     │ cancelada │       etapa 1, cadeia nova)
                                     └───────────┘  TERMINAL
```

**`EtapaAprovacao.status`**
```
aguardando ──▶ aprovada | reprovada | devolvida
     │
     └──▶ pendente_configuracao   ← nenhum aprovador resolvido (alerta ao admin)
              └──▶ aguardando     ← admin corrige o organograma
```

> **`pendente_configuracao` é o estado mais importante desta máquina.** É o que impede a falha silenciosa que caracteriza motores de aprovação mal feitos.

**Regras de transição:**
- `devolvida` → `em_aprovacao` **recria a cadeia** (o pedido mudou, os aprovadores podem mudar)
- `aprovada` e `reprovada` são terminais; reverter exige ação administrativa auditada (E3)
- Cancelamento só pelo solicitante, e só enquanto não houver nenhuma etapa decidida

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-APR-01 | Solicitante não aprova o próprio pedido | *"Você não pode aprovar um pedido que você mesmo criou. Ele foi encaminhado para Ana Prado."* |
| VAL-APR-02 | Devolução exige motivo ≥ 10 caracteres | *"Explique o que falta para que a pessoa possa corrigir."* |
| VAL-APR-03 | Reprovação exige motivo | *"Informe o motivo da reprovação."* |
| VAL-APR-04 | Só o aprovador da etapa atual decide | *"Esta aprovação está com Bruno Lima no momento."* |
| VAL-APR-05 | Etapa já decidida não é decidida de novo | *"Esta etapa já foi aprovada em 05/08 por Ana Prado."* |
| VAL-APR-06 | Lote ignora item sem permissão, sem falhar o lote | *"5 aprovados. 1 não pôde ser aprovado: sem permissão."* |
| VAL-APR-07 | Cancelamento só antes da primeira decisão | *"Não é possível cancelar: a aprovação já foi iniciada. Peça a devolução."* |
| VAL-APR-08 | Política com etapas vazias é inválida | *"Defina ao menos uma etapa ou marque como auto-aprovação."* |

### Integrações

| Sistema | Direção | Natureza |
|---|:-:|---|
| IDN | ← | Organograma, delegação, `pode()` |
| SVC | ← | Origem da maioria das solicitações |
| `dashboard.Ticket` | → | Aprovação concluída movimenta o ticket |
| `dashboard.CentroCusto` | ← | Contexto de valor (V1.1) |
| Channels | → | Contador ao vivo |
| Notificações existentes | → | Push e e-mail ao aprovador |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo | Liga com |
|---|---|:-:|:-:|:-:|
| K-APR-01 | Tempo médio de aprovação vs. linha de base | −40% | 60 dias | M3 |
| K-APR-02 | Aprovações concluídas na home, sem navegar | ≥ 70% | 30 dias | M2 |
| K-APR-03 | Aprovações em lote / total | ≥ 25% | 60 dias | — |
| K-APR-04 | Devoluções / total | 10–20% | 90 dias | — |
| K-APR-05 | Aprovações paradas > 72 h | < 5% | 60 dias | — |
| K-APR-06 | Auto-aprovações / total | ≥ 30% | 90 dias | — |

> **K-APR-04 tem faixa, não teto.** Devolução perto de zero significa que ninguém lê antes de aprovar. Acima de 20%, o formulário do catálogo está mal desenhado.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-APR-01 | Cadeia sem aprovador some | `pendente_configuracao` + alerta (regra de arquitetura) |
| RM-APR-02 | Aprovar vira carimbo sem leitura | Card com contexto suficiente; K-APR-04 monitora |
| RM-APR-03 | Delegação usada para burlar alçada | R7 (não amplia) + auditoria de toda decisão delegada |
| RM-APR-04 | Volume alto de notificação irrita | Agrupar por período; digest em vez de item a item |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-006** | **Motor de aprovação** | V1.0 |
| FT-024 | Modelos genéricos (`GenericFK`) e resolução de cadeia | V1.0 |
| FT-025 | `PoliticaAprovacao` com condições em JSON | V1.0 |
| FT-026 | Auto-aprovação registrada como decisão | V1.0 |
| FT-027 | Resolução de aprovador com delegação e regra anti-autoaprovação | V1.0 |
| FT-028 | Estado `pendente_configuracao` + alerta ao admin | V1.0 |
| **EP-007** | **Bandeja de aprovações** | V1.0 |
| FT-029 | Bandeja completa com filtros | V1.0 |
| FT-030 | Widget de aprovações com ação inline | V1.0 |
| FT-031 | Aprovação em lote com resultado consolidado | V1.0 |
| FT-032 | Devolução com motivo obrigatório | V1.0 |
| FT-033 | Contexto orçamentário no card | V1.1 |
| FT-034 | Escalonamento por inatividade | V1.1 |
| FT-035 | Aprovação por canal externo | V2 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | Motor, bandeja, lote, delegação, auto-aprovação | É a âncora de retorno diário. Sem ele o Workspace não tem motivo de existir |
| **V1.1** | Contexto orçamentário, escalonamento | Depende de `FIN-001`, que depende de dado de orçamento consolidado |
| **V2** | Canal externo (WhatsApp/push) | Depende de parecer jurídico sobre não-repúdio ([D-04]) |
| **V3** | Aprovação assistida por IA (recomendação com histórico) | Depende de volume de decisões para treinar a recomendação |

---

## 4.7 PRD · SVC — Serviços

### Problema
Não existe um lugar para pedir. Cada área tem seu canal informal, e o pedido nasce sem protocolo, sem prazo e sem os dados que quem vai atender precisa. O atendente gasta a primeira interação perguntando o que o sistema já sabe: unidade, centro de custo, qual equipamento a pessoa usa.

### Usuários e personas
**Primário:** P1 (Marina) · **Secundários:** P2 (pede para o time), todos · **Configurador:** P7

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-SVC-01 | Encontrar como pedir algo, partindo do problema | P1 | V1.0 |
| UC-SVC-02 | Pedir com o mínimo de digitação | P1 | V1.0 |
| UC-SVC-03 | Acompanhar o que pedi | P1 | V1.0 |
| UC-SVC-04 | Pedir em nome de um liderado | P2 | V1.0 |
| UC-SVC-05 | Publicar um item de catálogo sem deploy | P7 | V1.0 |
| UC-SVC-06 | Ver o prazo real antes de pedir | P1 | V1.1 |
| UC-SVC-07 | Resolver sozinho, sem abrir pedido | P1 | V1.1 |

### Estados

**`Solicitacao.status`** — derivado do ticket e da aprovação, **não é um terceiro estado independente**:

```
   criada ──▶ em_aprovacao ──▶ aprovada ──▶ em_atendimento ──▶ concluida
      │            │              │                                 
      │            ▼              │                              TERMINAL
      │        reprovada          │
      │            │              │
      └────────────┴──────────────┴──▶ cancelada        TERMINAL
```

> **Decisão de produto:** a `Solicitacao` **espelha** o estado do ticket e da aprovação. Duplicar a máquina de estado do ticket criaria divergência — o erro mais comum em catálogos de serviço.

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-SVC-01 | Máximo 3 campos livres por item | *"Este item tem 4 campos de texto. Reduza para no máximo 3 ou derive do perfil."* (admin) |
| VAL-SVC-02 | Item sem dono não publica | *"Defina o responsável por este serviço antes de publicar."* |
| VAL-SVC-03 | Item sem categoria de destino não publica | *"Defina para qual fila este pedido será encaminhado."* |
| VAL-SVC-04 | Pedir para outra pessoa exige `svc.solicitar.equipe` | *"Você só pode abrir solicitações para você mesmo."* |
| VAL-SVC-05 | Campo obrigatório do formulário JSON | *"Informe a justificativa."* (mensagem vem do próprio JSON) |
| VAL-SVC-06 | Ticket e aprovação criados na mesma transação | — (falha em um reverte o outro; erro genérico ao usuário) |

### Integrações

| Sistema | Direção | Natureza |
|---|:-:|---|
| IDN | ← | Pré-preenchimento e roteamento |
| APR | → | Cria `SolicitacaoAprovacao` |
| `dashboard.Ticket` | → | Destino real do pedido |
| `dashboard.CategoriaTicket` | ← | Fila de destino |
| CNT | ← | Deflexão por artigo (V1.1) |
| SRC | → | Itens de catálogo indexados (V1.1) |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo | Liga com |
|---|---|:-:|:-:|:-:|
| K-SVC-01 | Solicitações nascidas no catálogo vs. e-mail/WhatsApp | ≥ 40% | 60 dias | M4 |
| K-SVC-02 | Campos preenchidos pelo usuário por solicitação | ≤ 2 (mediana) | 30 dias | — |
| K-SVC-03 | Tempo de preenchimento | ≤ 60 s (mediana) | 30 dias | — |
| K-SVC-04 | Solicitações devolvidas por falta de informação | < 10% | 60 dias | — |
| K-SVC-05 | Itens de catálogo sem uso em 90 dias | reportado | 90 dias | — |

> **K-SVC-05 alimenta o corte.** Item sem uso não é ampliado; é removido. É o mecanismo que impede o catálogo de virar um cemitério de 30 itens.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-SVC-01 | Item sem dono real vira chamado órfão (`R-19`) | `VAL-SVC-02` no model, não só na tela |
| RM-SVC-02 | Catálogo cresce por pressão política | Expansão só por `K-SVC-01` medido, nunca por pedido de área |
| RM-SVC-03 | Formulário JSON vira linguagem de programação improvisada | Tipos fechados: texto, textarea, número, data, seleção, anexo. Nada de condicional no V1.0 |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-008** | **Catálogo de serviços** | V1.0 |
| FT-036 | `ItemCatalogo` com validação de dono e campos livres | V1.0 |
| FT-037 | Renderizador de formulário declarativo (JSON) | V1.0 |
| FT-038 | Pré-preenchimento a partir da identidade | V1.0 |
| FT-039 | Catálogo navegável com busca | V1.0 |
| FT-040 | Os 6 itens iniciais, com donos nomeados | V1.0 |
| **EP-009** | **Solicitação** | V1.0 |
| FT-041 | Solicitação → ticket + aprovação em transação única | V1.0 |
| FT-042 | Solicitar em nome de liderado | V1.0 |
| FT-043 | Timeline de acompanhamento | V1.1 |
| FT-044 | Prazo real medido (P50/P90) | V1.1 |
| FT-045 | Deflexão por autoatendimento | V1.1 |
| FT-046 | Expansão para 30 itens | V2 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | Catálogo de 6, formulário derivado, solicitação → ticket | 6 itens cobrem o maior volume; 30 exigiriam 30 donos e 30 SLAs |
| **V1.1** | Timeline, prazo medido, deflexão | Prazo medido exige histórico do V1.0; deflexão exige conteúdo publicado |
| **V2** | 30 itens, formulário condicional | Expansão guiada por uso medido |
| **V3** | Catálogo gerado por IA a partir de padrões de chamado | Exige volume |

---

## 4.8 PRD · CNT — Conteúdo

### Problema
A documentação da empresa está em pasta de rede, e-mail e cabeça de gente. Não há dono, vigência nem público-alvo. Em auditoria, ninguém consegue provar que a política vigente é aquela e que as pessoas certas a receberam.

E há um problema estrutural para a IA: o RAG atual indexa apenas `ArtigoConhecimento` (base do help desk). Um assistente corporativo lançado sobre essa base responde "não encontrei" para quase tudo.

### Usuários e personas
**Primários:** P5 (Sandra), P3 (Cláudia) · **Consumidores:** todos

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-CNT-01 | Publicar documento com dono, público e vigência | P5 | V1.0 |
| UC-CNT-02 | Encontrar o documento vigente sobre um assunto | P1 | V1.0 |
| UC-CNT-03 | Confirmar que li um documento obrigatório | P1 | V1.0 |
| UC-CNT-04 | Provar em auditoria quem leu o quê e quando | P5 | V1.0 |
| UC-CNT-05 | Restringir documento a um público | P5 | V1.0 |
| UC-CNT-06 | Ver o que mudou entre duas versões | P5 | V1.1 |
| UC-CNT-07 | Publicar com revisão de um segundo | P5 | V1.1 |

### Estados

**`Documento`**
```
   rascunho ──▶ publicado ──▶ vigente ──▶ vencido
       ▲            │                        │
       └────────────┘                        │  (some da biblioteca e do índice,
       despublicado                          │   permanece acessível por link
                                             │   a quem tem permissão)
                                             ▼
                                        [arquivado]  — nunca apagado
```
- `publicado` → `vigente` é automático quando `vigencia_inicio <= hoje`
- `vigente` → `vencido` é automático quando `vigencia_fim < hoje` (task diária)
- **Nada é apagado.** Documento é evidência

**`PendenciaLeitura`**
```
   pendente ──▶ confirmada    TERMINAL
       │
       └──▶ dispensada    ← pessoa saiu do público-alvo ou foi desligada
```
> `dispensada` existe para que o relatório de conformidade não conte como pendente quem já não deveria ler. Sem esse estado, o número nunca fecha.

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-CNT-01 | Documento sem dono não publica | *"Defina o responsável por este documento."* |
| VAL-CNT-02 | Classificação `restrito` exige público-alvo | *"Documentos restritos precisam de ao menos um papel, departamento ou unidade."* |
| VAL-CNT-03 | `vigencia_fim` > `vigencia_inicio` | *"A vigência final precisa ser posterior à inicial."* |
| VAL-CNT-04 | Leitura obrigatória exige público-alvo definido | *"Defina quem precisa ler este documento."* |
| VAL-CNT-05 | Confirmação exige que a pessoa esteja no público-alvo | *"Este documento não está direcionado a você."* |
| VAL-CNT-06 | Documento sem corpo nem arquivo não publica | *"Adicione o conteúdo ou anexe o arquivo."* |

### Integrações

| Sistema | Direção | Natureza |
|---|:-:|---|
| IDN | ← | Público-alvo e dono |
| SRC | → | Indexação com `acl_subjects()` |
| COM | ← | Comunicado é um `Documento` |
| `ArtigoConhecimento` | — | **Intocado no V1.0**; migração em V1.1 |
| AIC | → | Fonte do RAG a partir do V1.1 |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo | Liga com |
|---|---|:-:|:-:|:-:|
| K-CNT-01 | Documentos publicados | ≥ 40 | antes de ligar a IA (V1.1) | R-04 |
| K-CNT-02 | Documentos com dono e vigência | 100% | contínuo | — |
| K-CNT-03 | Documentos vencidos ainda listados | 0 | contínuo | — |
| K-CNT-04 | Leitura confirmada em 72 h | ≥ 90% | por documento | M5 |
| K-CNT-05 | Buscas na biblioteca sem resultado | < 20% | 90 dias | — |

> **K-CNT-01 é o gatilho do V1.1.** Abaixo de 40 documentos publicados, a IA generativa **não é ligada** — é a mitigação de `R-04` transformada em critério objetivo.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-CNT-01 | Biblioteca vazia (`R-04`) | K-CNT-01 como gate do V1.1; captura passiva (`AIC-008`) desde o V1.1 |
| RM-CNT-02 | Documento restrito vaza pela busca | `acl_subjects()` é a mesma função para biblioteca e índice; teste de vazamento |
| RM-CNT-03 | Ninguém mantém a vigência | Alerta ao dono 30 dias antes do vencimento (V1.1) |
| RM-CNT-04 | Publicação sem revisão gera conteúdo errado vigente | V1.0 aceita o risco (piloto controlado); V1.1 traz o fluxo de revisão |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-010** | **Modelo de conteúdo** | V1.0 |
| FT-047 | `Documento` com tipo, dono, classificação, público, vigência | V1.0 |
| FT-048 | `acl_subjects()` compartilhado com o índice | V1.0 |
| FT-049 | Task de vencimento automático | V1.0 |
| **EP-011** | **Biblioteca** | V1.0 |
| FT-050 | Listagem com filtro por tipo, departamento e vigência | V1.0 |
| FT-051 | Visualizador de documento e anexo | V1.0 |
| FT-052 | Publicação | V1.0 |
| **EP-012** | **Leitura confirmada** | V1.0 |
| FT-053 | `PendenciaLeitura` com geração por público-alvo | V1.0 |
| FT-054 | Confirmação com registro de pessoa, data e IP | V1.0 |
| FT-055 | Estado `dispensada` para quem saiu do público | V1.0 |
| FT-056 | Versionamento com diff | V1.1 |
| FT-057 | Fluxo de revisão e aprovação | V1.1 |
| FT-058 | Migração de `ArtigoConhecimento` | V1.1 |
| FT-059 | Documento executável (POP = checklist) | V2 |
| FT-060 | Comentário ancorado | V2 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | Modelo, biblioteca, leitura confirmada | Sem modelo de conteúdo, COM não existe e a IA não tem o que responder |
| **V1.1** | Versionamento, revisão, migração do KB | Só faz sentido com histórico acumulado |
| **V2** | Documento executável, comentário ancorado | Depende do checklist do FSM e de volume de revisão |
| **V3** | Grafo de conhecimento, sugestão de documento faltante | Depende de massa de conteúdo |

---

## 4.9 PRD · COM — Comunicação

### Problema
Comunicado corporativo é e-mail sem retorno. Sandra não sabe quem leu; a qualidade não consegue provar em auditoria ISO que a política foi comunicada; e o técnico em campo simplesmente não recebe.

Há também um risco jurídico real: em ação trabalhista, "a empresa comunicou a norma" precisa de evidência, e hoje não existe.

### Usuários e personas
**Primária:** P5 (Sandra) · **Consumidores:** todos, inclusive P6 (via app nativo) · **Relatório:** P2, P3

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-COM-01 | Publicar comunicado para um público específico | P5 | V1.0 |
| UC-COM-02 | Exigir confirmação de leitura | P5 | V1.0 |
| UC-COM-03 | Bloquear a navegação até o aceite de algo crítico | P5 | V1.0 |
| UC-COM-04 | Ver quem do meu time confirmou | P2 | V1.0 |
| UC-COM-05 | Receber comunicado no app de campo | P6 | V1.0 |
| UC-COM-06 | Agendar publicação | P5 | V1.1 |
| UC-COM-07 | Publicar correção vinculada | P5 | V1.1 |
| UC-COM-08 | Ouvir o comunicado em áudio | P6 | V2 |

### Estados

**`Comunicado`**
```
   rascunho ──▶ agendado ──▶ publicado ──▶ expirado
                    │            │
                    └────────────┘
                      (publicar_em atingido)
```
- `expirado` quando `expira_em < agora`; o documento permanece na biblioteca como histórico
- **Publicado não retorna a rascunho** — correção é um novo comunicado vinculado (R5)

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-COM-01 | Comunicado crítico exige `com.publicar.global` | *"Apenas a comunicação interna pode publicar comunicados críticos."* |
| VAL-COM-02 | Alerta ao criar o 2º crítico ativo | *"Já existe um comunicado crítico ativo. Dois bloqueios simultâneos prejudicam a leitura de ambos. Continuar?"* |
| VAL-COM-03 | Comunicado publicado não é editado | *"Comunicados publicados não podem ser alterados. Publique uma correção."* |
| VAL-COM-04 | Público-alvo por regra, não por lista de pessoas | *"Selecione papéis, departamentos ou unidades — não pessoas individuais."* |
| VAL-COM-05 | Crítico exige texto de aceite | *"Informe o texto que a pessoa vai confirmar."* |
| VAL-COM-06 | `expira_em` > `publicar_em` | *"A expiração precisa ser posterior à publicação."* |

### Integrações

| Sistema | Direção | Natureza |
|---|:-:|---|
| CNT | ← | `Documento` e `PendenciaLeitura` |
| IDN | ← | Público-alvo |
| App nativo | → | JSON com o mesmo filtro de público |
| Channels | → | Notificação ao vivo |
| Notificações existentes | → | Push e e-mail |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo | Liga com |
|---|---|:-:|:-:|:-:|
| K-COM-01 | Leitura confirmada em 72 h | ≥ 90% | por comunicado | M5 |
| K-COM-02 | Tempo mediano até a confirmação | ≤ 8 h | por comunicado | — |
| K-COM-03 | Comunicados críticos ativos simultâneos | ≤ 1 | contínuo | — |
| K-COM-04 | Confirmação de quem está em campo (via app) | ≥ 80% | 90 dias | — |
| K-COM-05 | Comunicados publicados por mês | 4–12 | contínuo | — |

> **K-COM-05 tem faixa por um motivo:** menos de 4 significa que o canal não pegou; mais de 12 significa ruído, e a taxa de leitura cai junto.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-COM-01 | Bloqueio crítico usado em excesso e vira ruído | `VAL-COM-02` + K-COM-03 + só `com.publicar.global` |
| RM-COM-02 | Bloqueio impede o usuário de trabalhar de verdade | Logout e a própria confirmação sempre acessíveis; teste explícito |
| RM-COM-03 | Confirmação de leitura tratada como assinatura jurídica | **Deixar claro na tela** que é confirmação de ciência, não assinatura eletrônica qualificada |
| RM-COM-04 | Técnico não confirma porque está sem sinal | App nativo enfileira e sincroniza; K-COM-04 monitora |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-013** | **Mural** | V1.0 |
| FT-061 | `Comunicado` com 3 classes | V1.0 |
| FT-062 | Público-alvo por regra | V1.0 |
| FT-063 | Middleware de bloqueio do crítico | V1.0 |
| FT-064 | Widget do mural | V1.0 |
| FT-065 | Relatório de confirmação por gestor | V1.0 |
| FT-066 | API JSON para o app nativo | V1.0 |
| FT-067 | Agendamento e correção vinculada | V1.1 |
| FT-068 | Áudio (TTS) | V2 |
| FT-069 | Pulso semanal | V2 |
| FT-070 | Notícias, eventos, reconhecimento | V3 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | 3 classes, público por regra, bloqueio, relatório, API | É a âncora 3 e o KPI de auditoria. Sem ele, o Workspace não tem razão institucional |
| **V1.1** | Agendamento, correção vinculada | Necessidade aparece com volume |
| **V2** | Áudio, pulso | Áudio depende de adoção do app nativo; pulso depende de confiança estabelecida |
| **V3** | Camada editorial (notícia, evento, reconhecimento) | Só faz sentido depois que a comunicação obrigatória funcionar |

---

## 4.10 PRD · PPL — Pessoas

> **Contém o diferencial mais defensável do produto: `PPL-005`.**

### Problema
Duas dores distintas com a mesma raiz — não há vínculo entre pessoa, habilitação e operação:

1. **Colaborador** não vê nem corrige os próprios dados, e descobre divergência quando o holerite vem errado
2. **Operação** despacha técnico com certificação vencida, porque o controle é uma planilha que ninguém olha. O custo é risco trabalhista, perda de cobertura de seguro e não-conformidade em auditoria de cliente

### Usuários e personas
**Primários:** P3 (Cláudia), P2 (Rogério) · **Secundário:** P1 · **Afetado:** P6 (Marcos)

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-PPL-01 | Ver e corrigir meus dados | P1 | V1.0 |
| UC-PPL-02 | Cadastrar certificação com validade | P3 | V1.0 |
| UC-PPL-03 | Ser avisado antes de a certificação vencer | P3, P6 | V1.0 |
| UC-PPL-04 | Impedir despacho de quem não está habilitado | sistema | V1.0 |
| UC-PPL-05 | Ver quem do meu time está ausente | P2 | V1.0 |
| UC-PPL-06 | Solicitar férias | P1 | V1.0 (via SVC) |
| UC-PPL-07 | Guardar documento pessoal com validade | P3 | V1.1 |
| UC-PPL-08 | Desligar alguém e revogar todos os acessos | P3 | V2 |

### Estados

**`Certificacao`** — estado derivado da data, não armazenado:
```
   vigente ──▶ a_vencer_90 ──▶ a_vencer_30 ──▶ a_vencer_15 ──▶ a_vencer_5 ──▶ vencida
      ▲                                                                          │
      └──────────────────── renovação (nova Certificacao) ───────────────────────┘
```
> **Decisão:** o estado é calculado de `vigencia_fim`, nunca gravado. Estado gravado com data desatualizada é a fonte clássica de "sistema diz que está válido e não está". `AlertaVencimento` grava apenas **o que já foi notificado**, para não repetir.

**`Ausencia.status`**
```
   solicitada ──▶ aprovada ──▶ em_curso ──▶ concluida    TERMINAL
        │              │            │
        └──────────────┴────────────┴──▶ cancelada       TERMINAL
```
- `aprovada` → `em_curso` automático em `inicio`; muda `PerfilUsuario.situacao`
- `em_curso` → `concluida` automático em `fim`; devolve `situacao` para `ativo`

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-PPL-01 | `vigencia_fim` > `emissao` | *"A validade precisa ser posterior à emissão."* |
| VAL-PPL-02 | Certificação duplicada vigente do mesmo tipo | *"Marcos já possui NR-10 vigente até 12/2027. Deseja substituir?"* |
| VAL-PPL-03 | Ausência sobreposta para a mesma pessoa | *"Já existe uma ausência de 10/09 a 20/09 para Marina."* |
| VAL-PPL-04 | Colaborador não edita campo espelho | *"Cargo é mantido pelo RH."* (= `VAL-IDN-06`) |
| VAL-PPL-05 | Ausência retroativa acima de 30 dias exige papel de RH | *"Ausências com mais de 30 dias no passado só podem ser registradas pelo RH."* |
| VAL-PPL-06 | Técnico sem habilitação sinalizado ao entrar em turno | *"Atenção: a NR-10 de Marcos vence em 3 dias, dentro deste turno."* |

### Integrações

| Sistema | Direção | Natureza |
|---|:-:|---|
| IDN | ← | Pessoa, organograma |
| `fsm.Skill` | ← | `TipoCertificacao.skill` liga habilitação a competência da OS |
| `fsm` dispatch | → | **Hook de bloqueio** — o ponto de integração mais importante do V1.0 |
| OPS | → | Ausência gera lacuna de cobertura |
| SVC + APR | ← | Férias como item de catálogo |
| Notificações | → | Alertas de vencimento |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo | Liga com |
|---|---|:-:|:-:|:-:|
| K-PPL-01 | Técnicos com certificações cadastradas | 100% | 60 dias | — |
| K-PPL-02 | Despachos bloqueados por certificação vencida | > 0 | 90 dias | M7 |
| K-PPL-03 | Certificações que venceram sem renovação prévia | ↓ 80% | 180 dias | — |
| K-PPL-04 | Alertas de vencimento que resultaram em renovação | ≥ 70% | 180 dias | — |
| K-PPL-05 | Divergências de perfil reportadas pelo colaborador | reportado | contínuo | — |

> **K-PPL-02 é contraintuitivo de propósito.** Bloqueio maior que zero **prova que o mecanismo funciona**. Zero pode significar que ninguém cadastrou certificação — por isso K-PPL-01 vem junto.
>
> **K-PPL-03 é a métrica que realmente importa.** O objetivo não é bloquear muito; é bloquear cada vez menos, porque as renovações passaram a acontecer antes.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-PPL-01 | Bloqueio surpreende o técnico e vira punição | `PPL-006` é V1.0 junto com `PPL-005`. Comunicar ao time de campo **antes** de ligar |
| RM-PPL-02 | Bloqueio paralisa a operação num dia crítico | Papel `operacao` pode registrar exceção **com justificativa e auditoria** — não pode desligar a regra |
| RM-PPL-03 | Dado de saúde entra sem política (`R-12`) | `PPL-002` fora do V1.0. Nenhum campo de saúde no schema |
| RM-PPL-04 | Certificação cadastrada errada bloqueia quem está habilitado | Evidência anexada + correção com auditoria |

> **RM-PPL-02 merece atenção de produto.** Uma regra rígida demais sem válvula de escape é desligada pela operação na primeira crise — e nunca mais é religada. A exceção auditada é o que mantém a regra viva.

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-014** | **Perfil e ausências** | V1.0 |
| FT-071 | Meu perfil com campos espelho e próprios | V1.0 |
| FT-072 | `Ausencia` com estados automáticos | V1.0 |
| FT-073 | Calendário de ausências do time | V1.0 |
| **EP-015** | **Habilitação operacional** | V1.0 |
| FT-074 | `TipoCertificacao` ligado a `fsm.Skill` | V1.0 |
| FT-075 | `Certificacao` com evidência | V1.0 |
| FT-076 | **Hook de bloqueio no dispatch** | V1.0 |
| FT-077 | Exceção com justificativa e auditoria | V1.0 |
| FT-078 | Alertas em 90/30/15/5 sem repetição | V1.0 |
| FT-079 | Documentos pessoais com validade | V1.1 |
| FT-080 | Offboarding com revogação em cadeia | V2 |
| FT-081 | Onboarding com trilha e SLA | V2 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | Perfil, ausências, certificação, bloqueio, alertas | O bloqueio é o diferencial defensável, e é barato porque o dispatch já existe |
| **V1.1** | Documentos pessoais | Exige política de retenção LGPD antes |
| **V2** | Offboarding, onboarding | Alto valor, uso esporádico |
| **V3** | PDI, feedback, avaliação | Só faz sentido com competências consolidadas |

---

## 4.11 PRD · OPS — Operação

*(PRD proporcional: 1 item no V1.0)*

### Problema
A escala vive em planilha compartilhada e grupo de WhatsApp. Três consequências diárias: ninguém sabe com certeza quem está de plantão agora; a falta é descoberta tarde; e não há vínculo entre estar escalado e estar habilitado.

### Usuários e personas
**Primário:** P2 (Rogério) · **Consumidores:** todos da unidade

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-OPS-01 | Saber quem está de plantão agora | todos | V1.0 |
| UC-OPS-02 | Ver a escala da semana | P2 | V1.0 |
| UC-OPS-03 | Publicar a escala | P2 | V1.0 (admin) |
| UC-OPS-04 | Ver lacuna de cobertura por ausência | P2 | V1.0 |
| UC-OPS-05 | Editar a escala no Workspace | P2 | V1.1 |
| UC-OPS-06 | Trocar turno entre pessoas | P2 | V1.1 |

### Estados

**`Escala`**
```
   rascunho ──▶ publicada ──▶ encerrada
       ▲            │
       └────────────┘
        despublicar (só se ainda não iniciada)
```
**`TurnoEscala`** — sem estado próprio. É um intervalo; "ativo agora" é uma consulta, não um campo.

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-OPS-01 | Turno sobreposto para a mesma pessoa | *"Marcos já está escalado das 08:00 às 18:00 neste dia."* |
| VAL-OPS-02 | Turno com `fim` ≤ `inicio` | *"O fim do turno precisa ser posterior ao início."* |
| VAL-OPS-03 | Pessoa em ausência aprovada | *"Marina está de férias de 10/09 a 20/09."* (bloqueia) |
| VAL-OPS-04 | Certificação vencendo dentro do turno | *"Atenção: a NR-10 de Marcos vence em 3 dias."* (alerta, não bloqueia) |
| VAL-OPS-05 | Escala publicada sem cobertura de plantão | *"Não há ninguém de plantão em 12/09 e 13/09. Publicar mesmo assim?"* |

### Integrações

| Sistema | Direção | Natureza |
|---|:-:|---|
| IDN | ← | Pessoa e unidade |
| PPL | ← | Ausência (bloqueio) e certificação (alerta) |
| `fsm.Tecnico` | ← | Vínculo via `IDN-006` |
| App nativo | → | JSON de escala atual |
| WKS | → | Widget |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo |
|---|---|:-:|:-:|
| K-OPS-01 | Escalas publicadas no sistema vs. planilha | 100% | 90 dias |
| K-OPS-02 | Consultas ao widget "quem está de plantão" | ≥ 5/dia | 30 dias |
| K-OPS-03 | Lacunas de cobertura identificadas antes do dia | ≥ 80% | 90 dias |
| K-OPS-04 | Turnos publicados com pessoa não habilitada | 0 | contínuo |

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-OPS-01 | Django admin ruim demais para uso real (`R-21`) | Validar com Rogério na semana 6. Se reprovar, o editor sobe para o V1.0 e algo de superfície desce |
| RM-OPS-02 | Escala no sistema e na planilha convivendo | K-OPS-01 monitora; planilha é descontinuada por decisão, não por esperança |
| RM-OPS-03 | `ExclusionConstraint` não funciona em SQLite (dev) | Validação equivalente no `clean()`; diferença documentada; teste roda em PostgreSQL no CI |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-016** | **Escala** | V1.0 |
| FT-082 | `Escala` e `TurnoEscala` com constraint de sobreposição | V1.0 |
| FT-083 | Admin de escala com validações | V1.0 |
| FT-084 | Widget "plantão agora" e semana | V1.0 |
| FT-085 | Lacuna de cobertura por ausência | V1.0 |
| FT-086 | API de escala atual | V1.0 |
| FT-087 | Editor de escala no Workspace | V1.1 |
| FT-088 | Troca de turno com aprovação | V1.1 |
| FT-089 | Sugestão de cobertura por IA | V2 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | Modelo, admin, widget de leitura | O valor está em **saber**; editar bem custa uma tela complexa que pode esperar |
| **V1.1** | Editor, troca de turno | Depois de provado que a escala no sistema é usada |
| **V2** | Sugestão de cobertura, modo foco por turno | Depende de dado histórico |
| **V3** | Otimização de escala com custo e SLA | Depende de custo real da OS |

---

## 4.12 PRD · SRC — Busca Global

### Problema
Encontrar qualquer coisa exige saber em qual módulo procurar. Não existe um único campo que atravesse o sistema, e a navegação depende de decorar o menu. Para quem usa o sistema esporadicamente — que é a maioria da empresa — isso é barreira suficiente para não usar.

### Usuários e personas
**Primários:** todos · **Persona de referência:** P1 (Marina)

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-SRC-01 | Ir para qualquer lugar sem usar o menu | todos | V1.0 |
| UC-SRC-02 | Encontrar uma pessoa e seu contato | todos | V1.0 |
| UC-SRC-03 | Executar uma ação direto da busca | todos | V1.0 |
| UC-SRC-04 | Voltar a algo que acessei recentemente | todos | V1.0 |
| UC-SRC-05 | Buscar documento, chamado, cliente, OS | todos | V1.1 |
| UC-SRC-06 | Perguntar em linguagem natural | todos | V1.1 |

### Estados
**Não há máquina de estado.** `SearchDocument` é projeção: existe e está atualizado, ou não existe. Documento removido da origem é removido do índice pelo sinal.

**Estados de interface do ⌘K:** `fechado` → `aberto_vazio` (recentes e ações) → `digitando` (local, instantâneo) → `carregando` (federado) → `com_resultados` | `sem_resultados` | `erro_degradado` (só local).

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-SRC-01 | Consulta com menos de 2 caracteres não vai ao servidor | — (só camada local) |
| VAL-SRC-02 | Resultado sem permissão nunca é retornado, nem contado | — (invisível por design) |
| VAL-SRC-03 | Falha do índice degrada para a camada local | *"Busca completa indisponível. Mostrando itens recentes."* |
| VAL-SRC-04 | Sem resultado sugere o caminho | *"Nada encontrado para 'xyz'. Tente buscar uma pessoa ou abrir uma solicitação."* |

### Integrações

| Sistema | Direção | Natureza |
|---|:-:|---|
| IDN | ← | `subjects_de(pessoa)` e a fonte `Pessoa` |
| Providers | ← | `search_documents()` de cada domínio |
| PostgreSQL FTS | ← | `tsvector` com dicionário português |
| pgvector | ← | V1.1 — campo já previsto no schema |
| Celery | ← | Reindexação assíncrona |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo | Liga com |
|---|---|:-:|:-:|:-:|
| K-SRC-01 | Sessões que usam o ⌘K | ≥ 30% | 30 dias | M6 |
| K-SRC-02 | Latência do primeiro resultado local | ≤ 120 ms | contínuo | P3 |
| K-SRC-03 | Latência do resultado federado (p95) | ≤ 600 ms | contínuo | P4 |
| K-SRC-04 | Buscas sem resultado | < 25% | 60 dias | — |
| K-SRC-05 | Buscas seguidas de clique em resultado | ≥ 60% | 60 dias | — |
| K-SRC-06 | Vazamento de permissão detectado | 0 | contínuo | S1 |

> **K-SRC-04 é diagnóstico, não meta de vaidade.** Busca sem resultado alta significa que faltam fontes no índice — é o insumo que prioriza quais adicionar no V1.1.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-SRC-01 | Vazamento por ACL mal aplicada | ACL como `WHERE` (regra de arquitetura) + teste de vazamento no aceite |
| RM-SRC-02 | Índice desatualizado mostra o que não existe mais | Reindexação por sinal + varredura de reconciliação diária |
| RM-SRC-03 | Busca só de pessoas frustra o usuário (`R-18`) | Camada local cobre navegação e ações; comunicar o escopo |
| RM-SRC-04 | GIN em `acl_subjects` não escala | Medir com 100 mil documentos antes do V1.1 |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-017** | **Índice unificado** | V1.0 |
| FT-090 | `SearchDocument` com `acl_subjects` e índices GIN | V1.0 |
| FT-091 | `subjects_de(pessoa)` | V1.0 |
| FT-092 | Ingestão de `Pessoa` via provider | V1.0 |
| FT-093 | Reindexação por sinal + reconciliação diária | V1.0 |
| **EP-018** | **Command Bar** | V1.0 |
| FT-094 | Camada local (recentes, favoritos, navegação, ações) | V1.0 |
| FT-095 | Busca léxica com FTS português | V1.0 |
| FT-096 | Agrupamento e navegação por teclado | V1.0 |
| FT-097 | Teste de vazamento de permissão | V1.0 |
| FT-098 | Fontes: documento, chamado, cliente, OS | V1.1 |
| FT-099 | Busca semântica (pgvector) + fusão RRF | V1.1 |
| FT-100 | Resposta de IA ancorada | V1.1 |
| FT-101 | Unfurl de objeto | V2 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | Índice, ACL, ⌘K local, léxica sobre pessoas | O difícil é o mecanismo de permissão. Provar em uma fonte de baixo risco |
| **V1.1** | Mais fontes, semântica, resposta de IA | Fontes priorizadas por K-SRC-04; IA depende de K-CNT-01 ≥ 40 |
| **V2** | Unfurl, busca por intenção | Depende de massa de conteúdo indexado |
| **V3** | Grafo operacional e análise de impacto | Depende de todas as fontes indexadas |

---

## 4.13 PRD · WKS — Workspace

### Problema
Hoje o usuário entra e vê um dashboard genérico ou um menu. Não há um lugar que responda "o que precisa de mim agora". O resultado é que cada pessoa mantém sua própria lista mental do que está pendente — e esquece.

### Usuários e personas
**Todos.** Personas de referência: P1 (preset colaborador) e P2 (preset gestor)

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-WKS-01 | Ver o que precisa de mim ao entrar | todos | V1.0 |
| UC-WKS-02 | Concluir uma tarefa sem sair da home | P2 | V1.0 |
| UC-WKS-03 | Alcançar qualquer módulo existente | todos | V1.0 |
| UC-WKS-04 | Ver o urgente antes de tudo | todos | V1.0 |
| UC-WKS-05 | Ter uma home coerente com meu papel | todos | V1.0 |
| UC-WKS-06 | Reordenar meus widgets | todos | V1.1 |
| UC-WKS-07 | Fechar o dia | todos | V2 |

### Estados

**Estados de widget** — o contrato que todo widget cumpre:
```
   inicial (skeleton com altura reservada)
      ├──▶ carregado_com_dados
      ├──▶ carregado_vazio      (mensagem específica + próxima ação)
      ├──▶ erro                 (mensagem + [tentar de novo]; não derruba a página)
      └──▶ nao_renderizado      (sem permissão — nem aparece no HTML)
```
> **`nao_renderizado` é diferente de `carregado_vazio`.** Widget sem permissão não pode aparecer bloqueado nem vazio — isso vaza a existência da funcionalidade.

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-WKS-01 | Widget sem permissão não é renderizado | — (ausente do HTML) |
| VAL-WKS-02 | Widget com timeout > 3 s cai para estado de erro | *"Não foi possível carregar agora."* + [tentar de novo] |
| VAL-WKS-03 | Estado vazio traz próxima ação | *"Nenhuma aprovação pendente. Bom trabalho."* |
| VAL-WKS-04 | Preset sem widget permitido cai para o padrão | — (invisível) |

### Integrações
Consumidor de **todos** os módulos, sempre via `WorkspaceProvider` ou serviço de domínio. Nunca query direta.

### Métricas e KPIs

| ID | Métrica | Meta | Prazo | Liga com |
|---|---|:-:|:-:|:-:|
| K-WKS-01 | DAU/MAU no piloto | ≥ 0,5 | 60 dias | M1 |
| K-WKS-02 | Tarefas concluídas sem sair da home | ≥ 50% | 60 dias | — |
| K-WKS-03 | Zona 1 renderizada (p95) | ≤ 800 ms | contínuo | P1 |
| K-WKS-04 | Widget renderizado (p95) | ≤ 1,5 s | contínuo | P2 |
| K-WKS-05 | Sessões que chegam ao módulo antigo pelo launcher | reportado | 90 dias | — |
| K-WKS-06 | Taxa de erro por widget | < 1% | contínuo | — |

> **K-WKS-05 é o mapa da migração por atração.** Widget cujo módulo antigo continua sendo muito acessado é o próximo candidato a ganhar profundidade no Workspace.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-WKS-01 | Portal sem razão de retorno (`R-08`) | As 3 âncoras; K-WKS-01 decide a continuidade |
| RM-WKS-02 | Home lenta por N widgets (`R-08` de performance) | Carga independente, cache por widget, orçamento de 800 ms na Zona 1 |
| RM-WKS-03 | Workspace vira ilha desconectada dos módulos | `WKS-010` no V1.0; A7 exige 2 cliques para qualquer módulo |
| RM-WKS-04 | Usuário não percebe que pode agir no widget | Ação primária visível sem hover; teste com usuário real |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-019** | **Casca** | V1.0 |
| FT-102 | AppShell (topbar, sidebar, layout, tema) | V1.0 |
| FT-103 | Home 3 zonas com grid responsivo | V1.0 |
| FT-104 | Runtime de widget (assíncrono, cache, skeleton, erro) | V1.0 |
| FT-105 | Presets colaborador e gestor | V1.0 |
| **EP-020** | **Os 6 widgets** | V1.0 |
| FT-106 | Zona de atenção | V1.0 |
| FT-107 | Widget Aprovações (compartilhado com FT-030) | V1.0 |
| FT-108 | Widget Meu dia | V1.0 |
| FT-109 | Widget Escala | V1.0 |
| FT-110 | Widget Mural | V1.0 |
| FT-111 | Widget Acesso rápido | V1.0 |
| FT-112 | Contadores ao vivo por WebSocket | V1.0 |
| FT-113 | Central de notificações | V1.1 |
| FT-114 | Preferências (tema, densidade, ordem) | V1.1 |
| FT-115 | Widget orçamento do CC | V1.1 |
| FT-116 | Widget Meu time hoje | V1.1 |
| FT-117 | Fechar o dia | V2 |
| FT-118 | Modo foco operacional | V2 |
| FT-119 | Handoff desktop ↔ mobile | V2 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | Casca, 3 zonas, 6 widgets, 2 presets | É o recipiente. Sem ele nada tem onde aparecer |
| **V1.1** | Notificações, preferências, 2 widgets novos | Conveniências que só fazem sentido com uso real medido |
| **V2** | Fechar o dia, modo foco, handoff | Dependem de hábito estabelecido |
| **V3** | Widgets de terceiros, studio no-code | Depende de haver plataforma |

---

## 4.14 PRD · AIC — IA & Agentes

*(PRD proporcional: 2 itens de instrumentação no V1.0)*

### Problema
O copiloto já roda em produção **sem teto de custo e sem medição de qualidade**. São dois problemas abertos hoje:

1. **Financeiro:** o custo cresce linearmente com o uso e não há limite nem alerta
2. **De produto:** não existe registro de que a resposta foi útil. Sem isso, `AIC-004` (autonomia por desempenho medido) — a proposta mais defensável do produto — **nunca poderá existir**, porque a métrica não é retroativa

### Usuários e personas
**Primário:** P7 (admin) · **Beneficiário:** todos que usam o copiloto

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-AIC-01 | Dizer se a resposta foi útil | todos | V1.0 |
| UC-AIC-02 | Ver quanto a IA custou no mês | P7 | V1.0 |
| UC-AIC-03 | Definir teto por pessoa e por instalação | P7 | V1.0 |
| UC-AIC-04 | Ser avisado antes de estourar o limite | P7 | V1.0 |
| UC-AIC-05 | Aplicar uma sugestão como diff | P2 | V1.1 |
| UC-AIC-06 | Promover um agente por desempenho | P7 | V2 |

### Estados

**`ConsumoIA`** — sem estado; é acumulador diário.

**Estado de disponibilidade da IA** (calculado):
```
   disponivel ──▶ alerta_70 ──▶ alerta_90 ──▶ bloqueado
        ▲                                          │
        └──────── virada do período ───────────────┘
```
`bloqueado` degrada com mensagem clara — nunca falha em silêncio nem com erro genérico.

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-AIC-01 | Teto atingido degrada com mensagem | *"O limite de uso da IA foi atingido neste mês. Fale com o administrador."* |
| VAL-AIC-02 | Teto de pessoa ≤ teto da instalação | *"O limite individual não pode ser maior que o da instalação."* |
| VAL-AIC-03 | Feedback exige mensagem existente | — (erro técnico) |

### Integrações

| Sistema | Direção | Natureza |
|---|:-:|---|
| [copilot/engine.py](../dashboard/services/copilot/engine.py) | ↔ | Instrumentação, sem mudar comportamento |
| `mask_pii` existente | — | Fronteira de PII preservada |
| Provedor de LLM | ← | Tokens da resposta para cálculo de custo |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo |
|---|---|:-:|:-:|
| K-AIC-01 | Respostas com evento de feedback registrado | 100% | lançamento |
| K-AIC-02 | Taxa de feedback explícito (👍/👎) | ≥ 15% | 90 dias |
| K-AIC-03 | Custo de IA por pessoa ativa/mês | reportado | contínuo |
| K-AIC-04 | Chamadas bloqueadas por teto | < 1% | contínuo |
| K-AIC-05 | Taxa de aprovação das respostas | ≥ 70% | 180 dias |

> **K-AIC-01 é 100% de propósito.** O evento é registrado com ou sem reação do usuário — é o denominador de tudo que vem depois.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-AIC-01 | Custo sem teto (`R-05`) | `AIC-002` é V1.0, obrigatório |
| RM-AIC-02 | Instrumentação altera o comportamento do copiloto | A5: nenhuma mudança funcional; testes existentes devem passar sem alteração |
| RM-AIC-03 | Feedback explícito com volume baixo demais para significar algo | Capturar também o sinal implícito (a ação sugerida foi executada?) |
| RM-AIC-04 | Teto individual usado como controle disciplinar | Teto é por papel e por instalação; individual é exceção justificada |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-021** | **Governança de IA** | V1.0 |
| FT-120 | `FeedbackIA` com sinal explícito e implícito | V1.0 |
| FT-121 | `ConsumoIA` por chamada, com tokens | V1.0 |
| FT-122 | `TetoIA` com degradação e alertas | V1.0 |
| FT-123 | Painel de consumo | V1.0 |
| FT-124 | `ContratoAgente` | V1.1 |
| FT-125 | UI de proposta como diff | V1.1 |
| FT-126 | Skill packs e roteador de intenção | V1.1 |
| FT-127 | Briefing diário por IA | V1.1 |
| FT-128 | Agente de Conhecimento (OS → POP) | V1.1 |
| FT-129 | Autonomia por desempenho medido | V2 |
| FT-130 | Agente de Receita Não Faturada | V2 |
| FT-131 | Agente de Risco de SLA | V2 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | Feedback, custo, teto | Riscos abertos **hoje**; a métrica não é retroativa |
| **V1.1** | Contrato de agente, diff, skill packs, briefing, agente de conhecimento | Depende de K-CNT-01 ≥ 40 documentos |
| **V2** | Autonomia medida, agentes de receita e SLA | Autonomia exige histórico de feedback do V1.0/V1.1; receita exige `REV-003/004` |
| **V3** | Agentes proativos, camada ambiente completa | Depende de precisão medida e confiança estabelecida |

---

## 4.15 PRD · FIN — Financeiro

*(PRD proporcional: 2 itens no V1.0, sendo 1 sem interface)*

### Problema
Duas lacunas de dado com consequências desproporcionais:

1. **Reembolso** hoje é planilha e e-mail, sem política aplicada antes do envio
2. **Material consumido não é atribuível à OS.** A movimentação de estoque é por técnico (`MovimentacaoKitTecnico`), não por atendimento. Isso torna impossível calcular o custo real de uma OS — e, por consequência, a margem por contrato

### Usuários e personas
**Primários:** P1 (reembolso), P6 (registra consumo pelo app) · **Beneficiário futuro:** P4

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-FIN-01 | Pedir reembolso com aprovação | P1 | V1.0 |
| UC-FIN-02 | Registrar material consumido na OS | P6 | V1.0 |
| UC-FIN-03 | Ver o custo real de uma OS | P2 | V1.1 |
| UC-FIN-04 | Ver o consumo do meu centro de custo | P2 | V1.1 |
| UC-FIN-05 | Reembolso por foto com OCR | P1 | V2 |

### Estados
**`ConsumoMaterialOS`** — sem estado. É um evento imutável; correção é estorno com novo registro.

**Reembolso** — não tem estado próprio; é `Solicitacao` + `SolicitacaoAprovacao`. Deliberado: um terceiro estado divergiria.

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-FIN-01 | Quantidade > 0 | *"Informe uma quantidade maior que zero."* |
| VAL-FIN-02 | Custo unitário congelado no registro | — (automático) |
| VAL-FIN-03 | Consumo só em OS não concluída há mais de 7 dias | *"Esta OS foi concluída há mais de 7 dias. Peça ajuste ao supervisor."* |
| VAL-FIN-04 | Reembolso com valor acima da política exige justificativa | *"Valor acima do limite de R$ 60 para refeição. Justifique."* |

### Integrações

| Sistema | Direção | Natureza |
|---|:-:|---|
| SVC + APR | ← | Reembolso é item de catálogo |
| `dashboard.Produto` | ← | Material |
| `dashboard.MovimentacaoEstoque` | ↔ | Vínculo opcional |
| `fsm.OrdemServico` | ← | Dono do consumo |
| App nativo | ← | Registro em campo |
| REV | → | Insumo da classificação de serviço (V1.1) |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo |
|---|---|:-:|:-:|
| K-FIN-01 | OS concluídas com consumo registrado | ≥ 70% | 90 dias |
| K-FIN-02 | Reembolsos pelo catálogo vs. planilha | ≥ 80% | 90 dias |
| K-FIN-03 | Tempo de aprovação de reembolso | ≤ 48 h | 60 dias |
| K-FIN-04 | OS com custo calculável | ≥ 70% | 90 dias |

> **K-FIN-01 é o pré-requisito do V1.1.** Sem consumo registrado, `FIN-004` (custo real) não tem o que calcular.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-FIN-01 | Técnico não registra material (fricção em campo) | Registro em 2 toques no app; K-FIN-01 monitora; kit pré-carregado como padrão |
| RM-FIN-02 | Consumo divergente do estoque real | Consumo e movimentação são eventos distintos por design; reconciliação é relatório, não bloqueio |
| RM-FIN-03 | Custo congelado diverge do custo contábil | Documentar: custo do consumo é gerencial, não contábil |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-022** | **Custo da operação** | V1.0 |
| FT-132 | `ConsumoMaterialOS` com custo congelado | V1.0 |
| FT-133 | API de registro de consumo (app nativo) | V1.0 |
| FT-134 | Reembolso como item de catálogo | V1.0 |
| FT-135 | Custo real da OS (deslocamento + material + hora) | V1.1 |
| FT-136 | Orçamento por centro de custo | V1.1 |
| FT-137 | Contexto orçamentário na aprovação | V1.1 |
| FT-138 | OCR de cupom | V2 |
| FT-139 | Camada semântica de métricas | V2 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | Consumo de material, reembolso | Consumo é fundação com prazo de maturação; reembolso tem custo marginal ~zero |
| **V1.1** | Custo real, orçamento, contexto na aprovação | Dependem de 90 dias de consumo registrado |
| **V2** | OCR, camada semântica | Melhorias sobre base funcionando |
| **V3** | Precificação dinâmica, previsão de margem | Depende de série histórica |

---

## 4.16 PRD · REV — Receita & Contrato

*(PRD proporcional: 2 itens de fundação, sem interface)*

### Problema
O contrato é texto livre (`Contrato.descricao`). Não há declaração estruturada do que está coberto, qual a franquia e quanto custa o que está fora. Consequência direta e cara: **o técnico executa serviço fora do escopo, registra em observação, e ninguém fatura.**

Não sabemos hoje quanto isso soma — e essa é exatamente a questão. Um número que ninguém consegue produzir é um número que ninguém está cobrando.

### Usuários e personas
**Primário no V1.0:** P7 e comercial (cadastro) · **Beneficiário no V1.1+:** P4 e financeiro

### Casos de uso

| ID | Caso de uso | Persona | Prioridade |
|---|---|:-:|:-:|
| UC-REV-01 | Declarar o que o contrato cobre | comercial | V1.0 |
| UC-REV-02 | Manter tabela de preço com vigência | comercial | V1.0 |
| UC-REV-03 | Consultar se um serviço está coberto | sistema | V1.0 |
| UC-REV-04 | Classificar o serviço executado na OS | P6 | V1.1 |
| UC-REV-05 | Ver o que foi executado e não faturado | P4 | V1.1 |
| UC-REV-06 | Decidir faturar ou dar cortesia | P4 | V1.1 |
| UC-REV-07 | Detecção automática por IA | sistema | V2 |

### Estados
**Nenhuma máquina de estado no V1.0.** São dados de referência com vigência. `EscopoContrato` é válido enquanto o contrato estiver ativo; `TabelaPreco` é válida no período de vigência.

> Isso é uma característica, não uma omissão: dado de referência com máquina de estado costuma esconder modelagem confusa.

### Validações

| ID | Regra | Mensagem |
|---|---|---|
| VAL-REV-01 | Tipo de serviço único por contrato | *"Este tipo de serviço já está declarado neste contrato."* |
| VAL-REV-02 | Franquia exige período | *"Informe o período da franquia (mês, trimestre ou ano)."* |
| VAL-REV-03 | Preço > 0 | *"Informe um preço maior que zero."* |
| VAL-REV-04 | Vigências de tabela do mesmo contrato não se sobrepõem | *"Já existe tabela vigente para este contrato entre 01/01 e 31/12."* |
| VAL-REV-05 | Escopo vazio ao ativar contrato | *"Este contrato não tem nenhum serviço declarado. Continuar?"* (alerta) |

### Integrações

| Sistema | Direção | Natureza |
|---|:-:|---|
| `dashboard.Contrato` | ← | Dono do escopo |
| `fsm.Skill` | ← | `TipoServico.skill` liga ao que o técnico executa |
| FIN | ← | Consumo de material como evidência (V1.1) |
| `fsm.OSEvidencia` | ← | Evidência de execução (V1.1) |
| AIC | → | Insumo do agente de receita (V2) |

### Métricas e KPIs

| ID | Métrica | Meta | Prazo | Liga com |
|---|---|:-:|:-:|:-:|
| K-REV-01 | Contratos com escopo tipificado | ≥ 80% | 90 dias | M8 |
| K-REV-02 | Tipos de serviço catalogados | ≥ 20 | 60 dias | — |
| K-REV-03 | Contratos com tabela de preço vigente | ≥ 80% | 90 dias | — |
| K-REV-04 | Receita identificada como não faturada | reportado | V1.1 | tese comercial |
| K-REV-05 | Receita recuperada / faturamento do período | ≥ 3% | V2 | pitch |

> **K-REV-01 é a métrica mais importante do V1.0 que ninguém vai ver na tela.** Ela é o que determina se o V1.1 entrega a tese comercial ou se ela escorrega para o V2.

### Riscos

| ID | Risco | Mitigação |
|---|---|---|
| RM-REV-01 | Escopo mais complexo que o modelado (`R-06`) | Modelar com 2 contratos reais na mão (**Q-02**) antes de codificar |
| RM-REV-02 | Ninguém cadastra o escopo, por ser trabalho sem retorno visível | Demonstrar o valor do V1.1 antes; K-REV-01 com dono nomeado |
| RM-REV-03 | Contratos muito heterogêneos para um modelo único | Começar por **um tipo** de contrato, não por todos |
| RM-REV-04 | Cadastro vira projeto de meses | Priorizar os 20 contratos de maior faturamento; o resto entra por demanda |

### Backlog

| ID | Épico / Feature | Versão |
|---|---|:-:|
| **EP-023** | **Escopo contratual** | V1.0 |
| FT-140 | `TipoServico` ligado a `fsm.Skill` | V1.0 |
| FT-141 | `EscopoContrato` com franquia | V1.0 |
| FT-142 | `TabelaPreco` e `ItemTabelaPreco` com vigência | V1.0 |
| FT-143 | `preco_de()` com precedência | V1.0 |
| FT-144 | Admin de cadastro em massa | V1.0 |
| **EP-024** | **Receita não faturada** | V1.1 |
| FT-145 | Classificação do serviço executado na OS | V1.1 |
| FT-146 | Bandeja de receita não faturada (por regra) | V1.1 |
| FT-147 | Ações Faturar / Cortesia com trilha | V1.1 |
| FT-148 | Detecção por IA sobre evidência e texto livre | V2 |
| FT-149 | Margem por contrato | V2 |

### Roadmap

| Versão | Entrega | Por quê nesta versão |
|:-:|---|---|
| **V1.0** | `TipoServico`, escopo, tabela de preço, resolução | **Dado com prazo de maturação.** Cadastrando agora, o V1.1 entrega valor no dia do lançamento |
| **V1.1** | Classificação, bandeja, faturar/cortesia | Depende de escopo cadastrado (K-REV-01 ≥ 80%) e de consumo registrado (K-FIN-01 ≥ 70%) |
| **V2** | Detecção por IA, margem por contrato | Depende de volume classificado por regra para treinar e validar |
| **V3** | Precificação sugerida, renovação com base em margem | Depende de série histórica |

---

## 4.17 Casos de uso consolidados

**63 casos de uso.** 44 no V1.0.

| Módulo | V1.0 | V1.1 | V2 | Total |
|---|:-:|:-:|:-:|:-:|
| IDN | 6 | 1 | — | 7 |
| PLT | 4 | — | — | 4 |
| APR | 8 | 2 | — | 10 |
| SVC | 5 | 2 | — | 7 |
| CNT | 5 | 2 | — | 7 |
| COM | 5 | 2 | 1 | 8 |
| PPL | 6 | 1 | 1 | 8 |
| OPS | 4 | 2 | — | 6 |
| SRC | 4 | 2 | — | 6 |
| WKS | 5 | 1 | 1 | 7 |
| AIC | 4 | 1 | 1 | 6 |
| FIN | 2 | 2 | 1 | 5 |
| REV | 3 | 3 | 1 | 7 |
| **Total** | **44** | **21** | **6** | **63** |

---

## 4.18 KPIs consolidados

### Os 9 KPIs de nível de produto ([Etapa 2 §2.8](EXEC_02_MVP.md)) e o que os alimenta

| KPI de produto | Meta | Alimentado por |
|---|:-:|---|
| M1 · DAU/MAU | ≥ 0,5 | K-WKS-01 |
| M2 · Aprovações na home | ≥ 70% | K-APR-02 |
| M3 · Tempo de aprovação | −40% | K-APR-01 |
| M4 · Solicitações no catálogo | ≥ 40% | K-SVC-01 |
| M5 · Leitura confirmada | ≥ 90% | K-COM-01, K-CNT-04 |
| M6 · Uso do ⌘K | ≥ 30% | K-SRC-01 |
| M7 · Despachos bloqueados | > 0 | K-PPL-02 |
| M8 · Contratos tipificados | ≥ 80% | K-REV-01 |
| M9 · Regressões | 0 críticas | K-PLT-04 |

### Os 4 KPIs que **gatilham** o V1.1

Estas métricas não medem o V1.0 — elas **autorizam** o V1.1. Abaixo do limiar, a funcionalidade correspondente não é construída.

| Gatilho | Limiar | Autoriza |
|---|:-:|---|
| K-CNT-01 · Documentos publicados | ≥ 40 | Ligar a IA generativa (`SRC-006`, `AIC-014`) |
| K-REV-01 · Contratos tipificados | ≥ 80% | Bandeja de receita não faturada (`REV-004`) |
| K-FIN-01 · OS com consumo registrado | ≥ 70% | Custo real da OS (`FIN-004`) |
| K-PPL-01 · Técnicos com certificação | 100% | Confiar no bloqueio como regra operacional |

> **Este é o mecanismo mais importante do documento.** Ele transforma "vamos ver se dá certo" em um contrato objetivo: a próxima versão só é construída quando a fundação da anterior estiver de fato populada.

---

## 4.19 Backlog consolidado

**24 épicos · 149 features.** Explosão em story, task e subtask na Etapa 7.

| Épico | Módulo | Features | Versão |
|---|:-:|:-:|:-:|
| EP-001 Fundação de identidade | IDN | 5 | V1.0 |
| EP-002 Sincronização com o RH | IDN | 4 | V1.0 |
| EP-003 Organograma | IDN | 4 | V1.0/V1.1 |
| EP-004 Aurora — fundação visual | PLT | 4 | V1.0 |
| EP-005 Infraestrutura do Workspace | PLT | 6 | V1.0/V1.1 |
| EP-006 Motor de aprovação | APR | 5 | V1.0 |
| EP-007 Bandeja de aprovações | APR | 7 | V1.0→V2 |
| EP-008 Catálogo de serviços | SVC | 5 | V1.0 |
| EP-009 Solicitação | SVC | 6 | V1.0→V2 |
| EP-010 Modelo de conteúdo | CNT | 3 | V1.0 |
| EP-011 Biblioteca | CNT | 3 | V1.0 |
| EP-012 Leitura confirmada | CNT | 8 | V1.0→V2 |
| EP-013 Mural | COM | 10 | V1.0→V3 |
| EP-014 Perfil e ausências | PPL | 3 | V1.0 |
| EP-015 Habilitação operacional | PPL | 8 | V1.0→V2 |
| EP-016 Escala | OPS | 8 | V1.0→V2 |
| EP-017 Índice unificado | SRC | 4 | V1.0 |
| EP-018 Command Bar | SRC | 8 | V1.0→V2 |
| EP-019 Casca | WKS | 4 | V1.0 |
| EP-020 Os 6 widgets | WKS | 14 | V1.0→V2 |
| EP-021 Governança de IA | AIC | 12 | V1.0→V2 |
| EP-022 Custo da operação | FIN | 8 | V1.0→V2 |
| EP-023 Escopo contratual | REV | 5 | V1.0 |
| EP-024 Receita não faturada | REV | 5 | V1.1/V2 |

**Distribuição por versão:**

```
V1.0   ████████████████████████████████████████  86 features
V1.1   ████████████████                          34 features
V2     ██████████                                22 features
V3     ███                                        7 features
```

---

## 4.20 Roadmap consolidado

| Módulo | V1.0 | V1.1 | V2 | V3 |
|---|---|---|---|---|
| **IDN** | Identidade, papéis, delegação, sync | Diretório, organograma visual | Sucessão | Grafo organizacional |
| **PLT** | Aurora, flags, auditoria | Configurações, contextvars | Mudança revisada | Tenancy, API de widget |
| **APR** | Motor, bandeja, lote | Orçamento, escalonamento | Canal externo | Aprovação assistida |
| **SVC** | Catálogo de 6 | Timeline, prazo, deflexão | 30 itens | Catálogo por IA |
| **CNT** | Modelo, biblioteca, leitura | Versionamento, revisão | Doc executável | Grafo de conhecimento |
| **COM** | 3 classes, bloqueio, relatório | Agendamento, correção | Áudio, pulso | Camada editorial |
| **PPL** | Certificação + **bloqueio** | Documentos pessoais | Off/onboarding | PDI, avaliação |
| **OPS** | Escala (modelo + leitura) | Editor, troca de turno | Sugestão por IA | Otimização |
| **SRC** | Índice, ⌘K, pessoas | Mais fontes, semântica, IA | Unfurl | Análise de impacto |
| **WKS** | Casca, 6 widgets, 2 presets | Notificações, preferências | Fechar o dia, foco | Studio |
| **AIC** | Feedback, custo, teto | Agentes, diff, briefing | **Autonomia medida** | Agentes proativos |
| **FIN** | Consumo, reembolso | Custo real, orçamento | OCR, semântica | Previsão de margem |
| **REV** | Escopo, tabela de preço | **Receita não faturada** | Detecção por IA, margem | Precificação |

### A lógica das versões, em uma frase cada

| Versão | Tese |
|:-:|---|
| **V1.0** | *"Meu dia começa aqui."* — o laço diário funciona, e as fundações de dado começam a maturar |
| **V1.1** | *"O sistema começa a me dizer coisas."* — a IA liga porque há conteúdo; a receita aparece porque há escopo cadastrado |
| **V2** | *"O sistema age comigo."* — agentes com autonomia conquistada, receita detectada automaticamente |
| **V3** | *"O sistema é uma plataforma."* — extensível por terceiros, tenancy real, grafo completo |

---

## Próxima etapa

**Etapa 5 — Arquitetura.** Arquitetura lógica, técnica, de módulos, da IA, de permissões, de banco, de APIs, de navegação, da busca global, dos widgets e do App Launcher — com os diagramas correspondentes.

> **Nota de método:** a Etapa 3 deu o contrato estrutural por módulo e a Etapa 4 a camada de produto. A Etapa 5 responde **como o sistema se comporta em conjunto** — fluxo de requisição, cache, tempo real, tarefas assíncronas, degradação e escala — que nenhuma das duas cobriu.

**Aguarda aprovação da Etapa 4.**

---

*Etapa 4 de 9 · 63 casos de uso · 24 épicos · 149 features · 4 gatilhos de versão.*
