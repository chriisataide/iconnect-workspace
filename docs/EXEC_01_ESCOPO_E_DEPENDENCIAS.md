# Execução · Etapa 1 — Escopo, Consolidação, Dependências e Riscos

> **Documento de linha de base.** Consolida a visão oficial ([Blueprint](BLUEPRINT_ICONNECT_WORKSPACE.md) + [Revisão CPO](CPO_REVIEW_ICONNECT.md)) em um inventário único, deduplicado, com baseline verificada no código, grafo de dependências, caminho crítico e registro de riscos.
>
> **Agosto/2026** · Etapa 1 de 9 · **Aguarda aprovação antes da Etapa 2**

---

## Sumário

- [1.1 Método e convenções](#11-método-e-convenções)
- [1.2 Baseline verificada — o que já existe no código](#12-baseline-verificada--o-que-já-existe-no-código)
- [1.3 Inventário canônico consolidado](#13-inventário-canônico-consolidado)
- [1.4 Deduplicação — o que foi fundido e por quê](#14-deduplicação--o-que-foi-fundido-e-por-quê)
- [1.5 Mapeamento da sua lista de módulos](#15-mapeamento-da-sua-lista-de-módulos)
- [1.6 Grafo de dependências e caminho crítico](#16-grafo-de-dependências-e-caminho-crítico)
- [1.7 Registro de riscos](#17-registro-de-riscos)
- [1.8 Declaração de escopo](#18-declaração-de-escopo)
- [1.9 Decisões pendentes que bloqueiam a Etapa 2](#19-decisões-pendentes-que-bloqueiam-a-etapa-2)

---

## 1.1 Método e convenções

### Domínios de capacidade

Toda funcionalidade recebe um **ID estável** no formato `DOM-NNN`. Esse ID acompanha o item por todas as etapas seguintes — PRD, backlog, story, commit e teste. Não muda nunca.

| Código | Domínio | Responde por |
|---|---|---|
| **PLT** | Plataforma | Design system, permissões, auditoria, configuração, SSO, feature flags |
| **IDN** | Identidade & Organização | Pessoa, organograma, papéis com escopo, delegação |
| **WKS** | Workspace | Shell, home, widgets, notificações, launcher, preferências |
| **SRC** | Busca Global | Índice unificado, ⌘K, security trimming |
| **AIC** | IA & Agentes | Motor, skill packs, contrato de agente, feedback, orçamento |
| **SVC** | Serviços | Catálogo, solicitação, acompanhamento |
| **APR** | Aprovações | Motor de aprovação, cadeia, política, delegação, lote |
| **CNT** | Conteúdo | Biblioteca, documento executável, versionamento, leitura confirmada |
| **COM** | Comunicação | Mural, comunicado, confirmação, pulso |
| **PPL** | Pessoas | Self-service, ausências, certificação, documentos com validade |
| **OPS** | Operação | Escala, campo/offline, risco de SLA, evidência, ciclo operacional |
| **FIN** | Financeiro | Orçamento, custo da OS, reembolso |
| **REV** | Receita & Contrato | Escopo contratual, receita não faturada, margem |

### Estado de baseline

| Marca | Significado |
|:-:|---|
| ✅ | **Existe e serve.** Reusar sem reescrever |
| 🟡 | **Existe parcial.** Precisa de extensão, não de construção |
| 🔴 | **Não existe.** Construção nova |
| ⚫ | **Existe e atrapalha.** Precisa ser corrigido antes de ser usado |

### Classe de escopo

| Classe | Significado |
|---|---|
| **V1** | Entra na versão 1.0. É indispensável para lançar |
| **V1.1** | Primeira evolução. Já planejado, fora do lançamento |
| **V2** | Segunda onda |
| **V3** | Horizonte |
| **OUT** | Fora do produto. Decisão registrada, não reaberta sem novo fato |

> A definição final de V1 é a **Etapa 2**. Aqui o escopo é *proposto* e as classes servem para revelar dependências. A Etapa 2 pode rebaixar itens; não pode promover sem revisitar este documento.

---

## 1.2 Baseline verificada — o que já existe no código

Esta seção é o insumo mais importante da Etapa 1. Plano enterprise quebra na terceira sprint quando alguém assume que um dado existe.

### ✅ Ativos reusáveis (não reconstruir)

| Ativo | Onde | O que habilita |
|---|---|---|
| **Motor de IA com governança** | [copilot/engine.py](../dashboard/services/copilot/engine.py), `registry.py`, `permissions.py` | Gate por papel, PII mask no egress, confirmação em escrita, auditoria. **Base de todo o AIC** |
| **RAG + busca semântica** | [rag.py](../dashboard/services/rag.py), `knowledge_search.py`, `embeddings.py` | Padrão de recuperação provado. Base do SRC |
| **OrdemServico completa** | [fsm/models.py:233](../fsm/models.py) | SLA resposta/resolução, janela, `data_agendada`, `sequencia_rota`, `distancia_km`, `duracao_estimada_min`, `iniciado_em`/`concluido_em`, `motivo_atraso` |
| **OSEvidencia com geo e idempotência** | [fsm/models.py:474](../fsm/models.py) | `arquivo`, `latitude`/`longitude`, `capturado_em`, `autor`, `client_event_id`. **Base de OPS-antifraude e de REV** |
| **Checklist template + resposta** | [fsm/checklist_models.py](../fsm/checklist_models.py) | Template por skill, resposta por OS, vínculo com evidência. **Base do documento executável (CNT)** |
| **Técnico com skills, base e capacidade** | [fsm/models.py:117](../fsm/models.py) | `skills` M2M, `base`, `capacidade_diaria`, `home_lat/lng`, `status`, `last_seen_at` |
| **Contrato com taxa de KM** | [models/base.py:1326](../dashboard/models/base.py) | `valor_mensal`, **`valor_km_rate`** — combinado com `OS.distancia_km` e o app `km_audit`, o custo de deslocamento **já é calculável** |
| **Centro de custo hierárquico** | [models/base.py:1477](../dashboard/models/base.py) | `centro_pai`, `departamento`. Base do FIN |
| **SLA policy + monitor** | `services/sla_calculator.py`, `sla_monitor.py` | Base do OPS-risco |
| **Workflows, notificações, Channels, Celery** | `services/workflows.py`, `notifications.py`, `consumers.py`, `tasks.py` | Infra de eventos, tempo real e assíncrono |
| **SSO SAML/OIDC + MFA + auditoria** | `utils/sso.py`, `views/mfa.py`, `services/audit_system.py` | PLT-SSO praticamente pronto |
| **Tokens de cor** | [iconnect-design-system.css](../static/css/iconnect-design-system.css) | Paleta Slate+Cyan preservável |

### 🔴 Lacunas de dados que bloqueiam funcionalidades de alto valor

**Estas são as descobertas que mudam a ordem do plano.**

| # | Lacuna | Verificação | O que bloqueia |
|:-:|---|---|---|
| **L1** | **Contrato não tem escopo de serviço tipificado** | `Contrato` tem `descricao` (TextField livre), `valor_mensal`, `valor_km_rate`. Não há catálogo de serviços contratados nem tabela de preço por serviço | **REV-001 (Receita Não Faturada) — a funcionalidade nº 1 do roadmap.** Sem escopo estruturado, não há como dizer o que está "fora do escopo" |
| **L2** | **Estoque não tem vínculo com Ordem de Serviço** | Nenhuma referência a `OrdemServico` em [models/estoque.py](../dashboard/models/estoque.py). A movimentação é por técnico (`MovimentacaoKitTecnico`), não por OS | **REV-001** e **FIN-004 (custo real da OS)**. Material consumido não é atribuível ao atendimento |
| **L3** | **`Skill` não tem validade** | [fsm/models.py:49](../fsm/models.py) — `nome`, `descricao`, `ativa`. Sem vencimento, sem emissor, sem evidência | **PPL-004 (certificação que bloqueia escala)** — o diferencial mais defensável do produto |
| **L4** | **Não existe modelo de Escala / Turno / Sobreaviso** | Os 8 models do FSM são `Skill`, `BaseOperacional`, `MotivoAtraso`, `Tecnico`, `DispositivoTecnico`, `OrdemServico`, `OSEvento`, `OSEvidencia` | **OPS-001 (escala)** e, por consequência, **PPL-004** e **WKS-widget de escala** |
| **L5** | **Não existe identidade organizacional** | Não há `Pessoa`, `Cargo`, `Departamento`, `Unidade`, gestor ou delegação. `CargoTrabalho` é de auto-atribuição de ticket; `UnidadeMedida` é de estoque | **Praticamente tudo.** Home por perfil, aprovação, ACL de documento, organograma, ausências |
| **L6** | **Não existe motor de aprovação** | Há `workflows.py` (automação de ticket), não um motor com cadeia por valor, política, delegação e lote | **APR inteiro**, que sustenta SVC e FIN |
| **L7** | **Não existe modelo de conteúdo** | Só `ArtigoConhecimento` (KB de helpdesk, `publico` bool). Sem tipo, dono, vigência, versão, público-alvo, leitura obrigatória | **CNT inteiro** e, por consequência, a qualidade do **AIC** |
| **L8** | **Não existe índice unificado de busca** | `knowledge_search` cobre apenas `ArtigoConhecimento` | **SRC inteiro** |
| **L9** | **Não existe registro de feedback de IA** | O engine audita a chamada, não a aceitação da sugestão | **AIC-004 (autonomia medida)** — sem histórico, a métrica não pode nascer depois |

### ⚫ Passivos que precisam ser corrigidos antes de serem usados

| # | Passivo | Verificação | Impacto |
|:-:|---|---|---|
| **P1** | **Tenancy inexistente na prática** | 1 model de 123 com FK `tenant`, e "soft" (`NULL` = visível) | Bloqueia posicionamento SaaS. Ver [CPO §0](CPO_REVIEW_ICONNECT.md) |
| **P2** | **`threading.local()` para contexto de tenant** | [tenants.py:19](../dashboard/tenants.py) sob Daphne/ASGI | Falha silenciosa sob concorrência assíncrona |
| **P3** | **Gate de cobertura não cobre o núcleo vertical** | `--cov=dashboard` em [pyproject.toml:22](../pyproject.toml). `fsm` (6.700 linhas) e `km_audit` (4.100) sem gate | O código onde mora a diferenciação é o menos protegido |
| **P4** | **App `dashboard` com ~60 mil linhas** | 123 models, 33 views, 34 services | Todo domínio novo dentro dele agrava. Novos domínios nascem fora |
| **P5** | **Duas famílias de CSS + a terceira proposta** | Material Dashboard 2 (SCSS/Bootstrap) + `iconnect-design-system.css` + Tailwind agora no stack alvo | Ver [R-09](#17-registro-de-riscos) |

---

## 1.3 Inventário canônico consolidado

**139 itens.** Cada um com ID estável, baseline verificada e dependências diretas.

| Domínio | PLT | IDN | WKS | SRC | AIC | SVC | APR | CNT | COM | PPL | OPS | FIN | REV | **Total** |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Itens | 11 | 9 | 19 | 7 | 21 | 8 | 8 | 11 | 9 | 12 | 10 | 7 | 7 | **139** |

### PLT — Plataforma

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| PLT-001 | Design System Aurora — tokens, grid, densidade, dark | 🟡 | **V1** | — |
| PLT-002 | Biblioteca de componentes (inventário na Etapa 6) | 🔴 | **V1** | PLT-001 |
| PLT-003 | App `workspace` isolado + contrato `WorkspaceProvider` | 🔴 | **V1** | — |
| PLT-004 | Permissões granulares com escopo (substitui papéis planos) | ⚫🟡 | **V1** | IDN-002 |
| PLT-005 | Auditoria de acesso a dado sensível | 🟡 | **V1** | PLT-004 |
| PLT-006 | SSO SAML/OIDC no Workspace | ✅ | **V1** | PLT-003 |
| PLT-007 | Feature flags por instalação e por papel | 🔴 | **V1** | PLT-003 |
| PLT-008 | Configurações da instalação (admin do Workspace) | 🔴 | **V1.1** | PLT-007 |
| PLT-009 | `threading.local()` → `contextvars` | ⚫ | **V1** | — |
| PLT-010 | Gate de cobertura em `fsm` e `km_audit` | ⚫ | **V1** | — |
| PLT-011 | Tenancy real multi-cliente | 🔴 | **OUT (2027)** | decisão D-01 |

### IDN — Identidade & Organização

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| IDN-001 | `Pessoa` — matrícula, cargo, admissão, contatos, situação | 🔴 | **V1** | — |
| IDN-002 | `Unidade`, `Departamento`, `CentroCusto` vinculados a Pessoa | 🟡 | **V1** | IDN-001 |
| IDN-003 | Organograma (gestor ↔ liderados) | 🔴 | **V1** | IDN-001 |
| IDN-004 | `Papel` + `AtribuicaoPapel` com escopo e vigência | ⚫ | **V1** | IDN-002 |
| IDN-005 | `Delegacao` — período e papéis delegados | 🔴 | **V1** | IDN-004 |
| IDN-006 | Vínculo `Pessoa` ↔ `Tecnico` ↔ `User` | 🟡 | **V1** | IDN-001 |
| IDN-007 | Importação inicial de pessoas (CSV/planilha) | 🟡 | **V1** | IDN-001 |
| IDN-008 | Diretório e perfil público | 🔴 | **V1.1** | IDN-003 |

### WKS — Workspace

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| WKS-001 | AppShell — topbar, sidebar, layout, tema | 🔴 | **V1** | PLT-002 |
| WKS-002 | Home 3 zonas com grid de widget | 🔴 | **V1** | WKS-001 |
| WKS-003 | Runtime de widget (carga assíncrona, cache, skeleton) | 🔴 | **V1** | WKS-002 |
| WKS-004 | Presets por papel (4 no V1) | 🔴 | **V1** | WKS-003, IDN-004 |
| WKS-005 | Widget · Aprovações | 🔴 | **V1** | APR-002 |
| WKS-006 | Widget · Meu dia (agenda + OS + reuniões) | 🔴 | **V1** | IDN-006 |
| WKS-007 | Widget · Minhas pendências | 🔴 | **V1** | SVC-003, CNT-005 |
| WKS-008 | Widget · Escala e plantão | 🔴 | **V1** | OPS-001 |
| WKS-009 | Widget · Mural | 🔴 | **V1** | COM-001 |
| WKS-010 | Widget · Acesso rápido (App Launcher) | 🔴 | **V1** | PLT-004 |
| WKS-011 | Central de notificações acionável | 🟡 | **V1** | WKS-001 |
| WKS-012 | Zona 1 · Briefing (estático no V1, IA no V1.1) | 🔴 | **V1** | WKS-002 |
| WKS-013 | Preferências do usuário (tema, densidade, ordem) | 🔴 | **V1** | WKS-003 |
| WKS-014 | Widget · Orçamento do centro de custo | 🔴 | **V1.1** | FIN-001 |
| WKS-015 | Widget · Fechar o dia | 🔴 | **V2** | WKS-003 |
| WKS-016 | Widget · Meu time hoje | 🔴 | **V1.1** | PPL-003 |
| WKS-017 | Modo Foco operacional | 🔴 | **V2** | OPS-001 |
| WKS-018 | Handoff desktop ↔ mobile | 🔴 | **V2** | WKS-001 |
| WKS-019 | Personalização por arrastar | — | **OUT** | — |

### SRC — Busca Global

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| SRC-001 | `SearchDocument` — índice unificado com `acl_subjects` | 🔴 | **V1** | IDN-004 |
| SRC-002 | Ingestão por `WorkspaceProvider` (5 fontes no V1) | 🔴 | **V1** | SRC-001, PLT-003 |
| SRC-003 | ⌘K — camada local (recentes, favoritos, navegação, ações) | 🔴 | **V1** | WKS-001 |
| SRC-004 | Busca léxica (Postgres FTS) com trimming no índice | 🟡 | **V1** | SRC-001 |
| SRC-005 | Busca semântica (pgvector) e fusão RRF | 🟡 | **V1.1** | SRC-004 |
| SRC-006 | Resposta de IA ancorada no resultado | 🟡 | **V1.1** | SRC-005, AIC-002 |
| SRC-007 | Unfurl de objeto (colar link → card vivo) | 🔴 | **V2** | SRC-001 |

### AIC — IA & Agentes

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| AIC-001 | Registro de feedback (aceito/rejeitado/editado) | 🔴 | **V1** | — |
| AIC-002 | Teto de custo por usuário / instalação / agente | 🔴 | **V1** | — |
| AIC-003 | `ContratoAgente` — objetivo, gatilho, escopo, tools, orçamento | 🔴 | **V1.1** | AIC-001, AIC-002 |
| AIC-004 | Autonomia por desempenho medido (níveis 0–3) | 🔴 | **V2** | AIC-003 |
| AIC-005 | UI de proposta como diff aplicável | 🔴 | **V1.1** | AIC-003 |
| AIC-006 | Skill packs por domínio + roteador de intenção | 🟡 | **V1.1** | CNT-002 |
| AIC-007 | Camada Ambiente (enriquecimento sem interface) | 🟡 | **V1.1** | AIC-002 |
| AIC-008 | Agente · Conhecimento (OS resolvida → rascunho de POP) | 🔴 | **V1.1** | CNT-002, AIC-003 |
| AIC-009 | Agente · Risco de SLA com proposta de reroteirização | 🟡 | **V2** | AIC-005, OPS-002 |
| AIC-010 | Agente · Receita Não Faturada | 🔴 | **V2** | REV-002 |
| AIC-011 | Agente · Qualidade de evidência | 🔴 | **V2** | AIC-003 |
| AIC-012 | Agente · Peça Certa | 🔴 | **V2** | REV-001 |
| AIC-013 | Agente · Margem por contrato | 🔴 | **V2** | FIN-004 |
| AIC-014 | Briefing diário gerado por IA | 🔴 | **V1.1** | WKS-012, AIC-002 |
| AIC-015 | "Explique este KPI" | 🔴 | **V2** | AIC-002 |
| AIC-016 | Cache semântico de respostas | 🔴 | **V2** | AIC-002 |
| AIC-017 | Agente · Reincidência | 🔴 | **V3** | AIC-003 |
| AIC-018 | Agente · Fechamento de ciclo | 🔴 | **V3** | OPS-005 |
| AIC-019 | Dashboards gerados por IA | — | **OUT** | — |
| AIC-020 | Produtividade individual por IA | — | **OUT (princípio)** | — |
| AIC-021 | Resumo de reunião | — | **OUT (integrar)** | — |

### SVC — Serviços

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| SVC-001 | `ItemCatalogo` — dono, SLA, política, formulário, aprovadores | 🔴 | **V1** | IDN-004 |
| SVC-002 | Formulário derivado da identidade (≤3 campos livres) | 🔴 | **V1** | SVC-001, IDN-002 |
| SVC-003 | Solicitação → ticket no módulo destino | 🟡 | **V1** | SVC-002 |
| SVC-004 | Acompanhamento com timeline | 🟡 | **V1** | SVC-003 |
| SVC-005 | Catálogo inicial de 8 itens | 🔴 | **V1** | SVC-001 |
| SVC-006 | Prazo real medido (P50/P90) no card | 🔴 | **V1.1** | SVC-004 |
| SVC-007 | Deflexão por autoatendimento antes do formulário | ✅🟡 | **V1.1** | CNT-002 |
| SVC-008 | Expansão do catálogo a 30 itens | 🔴 | **V2** | SVC-005 |

### APR — Aprovações

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| APR-001 | Motor de aprovação — cadeia por valor e tipo | 🔴 | **V1** | IDN-003 |
| APR-002 | Bandeja com ação inline e em lote | 🔴 | **V1** | APR-001 |
| APR-003 | Política de auto-aprovação dentro de limite | 🔴 | **V1** | APR-001 |
| APR-004 | Delegação de aprovação | 🔴 | **V1** | IDN-005 |
| APR-005 | Devolver com motivo obrigatório | 🔴 | **V1** | APR-002 |
| APR-006 | Contexto orçamentário no card | 🔴 | **V1.1** | FIN-001 |
| APR-007 | Escalonamento por inatividade | 🔴 | **V1.1** | APR-001 |
| APR-008 | Aprovação por canal externo (WhatsApp/push) | 🟡 | **V2** | APR-002, D-04 |

### CNT — Conteúdo

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| CNT-001 | `Documento` — tipo, dono, classificação, público-alvo, vigência | 🔴 | **V1** | IDN-002 |
| CNT-002 | Versionamento com histórico e diff | 🔴 | **V1** | CNT-001 |
| CNT-003 | Publicação com fluxo de revisão e aprovação | 🔴 | **V1** | CNT-002, APR-001 |
| CNT-004 | Biblioteca — navegação, filtro, visualização | 🔴 | **V1** | CNT-001 |
| CNT-005 | Leitura confirmada por público-alvo + relatório | 🔴 | **V1** | CNT-001, IDN-003 |
| CNT-006 | Migração de `ArtigoConhecimento` para `Documento` | 🟡 | **V1** | CNT-001 |
| CNT-007 | Documento executável (POP = checklist = formulário) | 🟡 | **V2** | CNT-002, checklist FSM |
| CNT-008 | Comentário ancorado no objeto | 🔴 | **V2** | CNT-004 |
| CNT-009 | Trilhas, cursos obrigatórios, certificação de curso | 🔴 | **V2** | PPL-004 |
| CNT-010 | Autoria de curso, SCORM, vídeo, avaliação | — | **OUT** | — |
| CNT-011 | Gamificação, ranking, badges | — | **OUT** | — |

### COM — Comunicação

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| COM-001 | `Comunicado` com 3 classes (informativo/obrigatório/crítico) | 🔴 | **V1** | CNT-001 |
| COM-002 | Público-alvo por regra (papel, unidade, departamento) | 🔴 | **V1** | IDN-002 |
| COM-003 | Confirmação de leitura + bloqueio no crítico | 🔴 | **V1** | COM-001 |
| COM-004 | Relatório de confirmação por gestor | 🔴 | **V1** | COM-003, IDN-003 |
| COM-005 | Agendamento e retratação versionada | 🔴 | **V1.1** | COM-001 |
| COM-006 | Áudio do comunicado (TTS) | 🔴 | **V2** | COM-001 |
| COM-007 | Pulso — 1 pergunta/semana, anônimo | 🔴 | **V2** | IDN-002 |
| COM-008 | Notícia, campanha, evento, aniversário, reconhecimento | 🔴 | **V3** | COM-001 |
| COM-009 | Feed social, curtidas, comentários públicos | — | **OUT** | — |

### PPL — Pessoas

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| PPL-001 | Meu perfil — dados, foto, contatos | 🔴 | **V1** | IDN-001 |
| PPL-002 | `DocumentoPessoal` com validade (CNH, ASO, NR) | 🔴 | **V1** | IDN-001 |
| PPL-003 | Ausências — férias, afastamento, folga (calendário do time) | 🔴 | **V1** | IDN-003 |
| PPL-004 | `Certificacao` com validade, emissor e evidência | 🔴 | **V1** | IDN-006 |
| PPL-005 | **Certificação vencida bloqueia despacho** | 🔴 | **V1** | PPL-004, OPS-001 |
| PPL-006 | Alerta de vencimento 90/30/15/5 dias | 🔴 | **V1** | PPL-002, PPL-004 |
| PPL-007 | Solicitação de férias via catálogo | 🔴 | **V1.1** | SVC-001, APR-001 |
| PPL-008 | Offboarding com revogação de acesso em cadeia | 🔴 | **V2** | IDN-004 |
| PPL-009 | Onboarding com trilha e SLA | 🔴 | **V2** | SVC-001 |
| PPL-010 | Holerite, ponto, banco de horas, benefícios | — | **INTEGRAR (V2)** | D-03 |
| PPL-011 | PDI, feedback, avaliação | 🔴 | **V3** | IDN-003 |
| PPL-012 | Vagas, indique um amigo, plano de carreira | — | **OUT** | — |

### OPS — Operação

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| OPS-001 | `Escala` — turno, plantão, sobreaviso, cobertura | 🔴 | **V1** | IDN-006 |
| OPS-002 | Risco de SLA preditivo (sinal, sem IA) | 🟡 | **V1** | — |
| OPS-003 | Pacote do dia offline (técnico) | 🟡 | **V1** | OPS-001, D-05 |
| OPS-004 | Mapa ao vivo no Workspace (embed do FSM) | ✅ | **V1.1** | PLT-003 |
| OPS-005 | Ciclo operacional com fechamento automático | 🔴 | **V2** | REV-002 |
| OPS-006 | Auditoria de evidência (antifraude) | 🔴 | **V2** | AIC-011 |
| OPS-007 | Sala de guerra de incidente | 🔴 | **V2** | WKS-001 |
| OPS-008 | Mudança operacional revisada (diff + blame de configuração) | 🔴 | **V2** | PLT-005 |
| OPS-009 | Grafo operacional / análise de impacto | 🔴 | **V3** | SRC-001 |
| OPS-010 | Painéis de BI por papel | 🟡 | **V2** | camada semântica |

### FIN — Financeiro

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| FIN-001 | Orçamento por centro de custo (previsto × consumido × comprometido) | 🟡 | **V1.1** | IDN-002 |
| FIN-002 | Reembolso via catálogo + aprovação | 🔴 | **V1.1** | SVC-001, APR-001 |
| FIN-003 | **`ConsumoMaterialOS` — vínculo estoque ↔ OS** | 🔴 | **V1** | — |
| FIN-004 | Custo real da OS (deslocamento + material + hora) | 🟡 | **V1.1** | FIN-003 |
| FIN-005 | Contratos a vencer / renovação | 🟡 | **V1.1** | — |
| FIN-006 | Reembolso por foto com OCR | 🔴 | **V2** | FIN-002 |
| FIN-007 | Camada semântica de métrica | 🔴 | **V2** | — |

### REV — Receita & Contrato

| ID | Item | Base | Classe | Depende de |
|---|---|:-:|:-:|---|
| REV-001 | **`EscopoContrato` — serviços cobertos, franquia, exceções** | 🔴 | **V1** | — |
| REV-002 | **`TabelaPreco` — preço por serviço fora do escopo** | 🔴 | **V1** | REV-001 |
| REV-003 | Classificação do serviço executado na OS | 🔴 | **V1.1** | REV-001, FIN-003 |
| REV-004 | Bandeja de receita não faturada (regra, sem IA) | 🔴 | **V1.1** | REV-003, REV-002 |
| REV-005 | Ação [Faturar] / [Cortesia] com trilha | 🔴 | **V1.1** | REV-004 |
| REV-006 | Detecção por IA sobre evidência e texto livre | 🔴 | **V2** | AIC-010, REV-004 |
| REV-007 | Margem por contrato | 🔴 | **V2** | FIN-004, REV-005 |

---

## 1.4 Deduplicação — o que foi fundido e por quê

**19 fusões.** Cada uma elimina um item que existia em duplicidade entre a visão original, o blueprint e a revisão CPO.

| Itens originais | Fundido em | Racional |
|---|---|---|
| Saudação personalizada · IA em destaque · Alertas | **WKS-012** Briefing | Três nomes para a mesma faixa superior |
| Notícias · Comunicados · Eventos | **WKS-009** / **COM-001** | Um widget, um objeto com tipo |
| Atividades recentes · Últimos documentos · Continue de onde parou | **WKS-007** Pendências + **SRC-003** recentes | Recência é função da busca, não widget próprio |
| Favoritos · Aplicativos · App Launcher | **WKS-010** Acesso rápido | Um widget. Launcher não é módulo |
| Pesquisa Global · Spotlight · ⌘K | **SRC-003/004/005** | Uma capacidade em camadas |
| Chamados · Solicitações · Pendências | **SVC-003/004** + **WKS-007** | Solicitação é ticket com origem no catálogo |
| Cursos obrigatórios (widget) · Documentos a confirmar | **CNT-005** leitura confirmada | Mesmo mecanismo de "pendência de conteúdo com prazo" |
| Biblioteca · Wiki · POP · Manuais · APIs · Contratos · Templates · Atas | **CNT-001** `Documento` com `tipo` | Oito modelos viravam um campo |
| Universidade Corporativa · LMS · Trilhas · Certificações | **CNT-009** + **PPL-004** | A parte que importa é certificação com validade (PPL), não LMS (CNT) |
| Competências (RH) · Skills (FSM) · Certificações | **PPL-004** ligado a `fsm.Skill` | Havia dois vocabulários para a mesma coisa |
| Aprovações (RH) · (Financeiro) · (Compras) · (Serviços) | **APR-001** motor único | Quatro filas viravam quatro implementações |
| Fluxos de Aprovação (Financeiro) · Workflow builder | **APR-001** + `workflows.py` existente | Aprovação é caso especial de workflow, com UI própria |
| Solicitações (RH) · (Financeiro) · (TI) · (Facilities) | **SVC-001** catálogo único | Departamento é roteamento, não taxonomia |
| Agenda · Próximas reuniões | **WKS-006** Meu dia | Um widget |
| Escalas (Operações) · Plantão · Sobreaviso · Turno | **OPS-001** `Escala` | Um objeto |
| Técnicos (Operações) · Colaboradores (RH) | **IDN-001** `Pessoa` ↔ **IDN-006** vínculo com `Tecnico` | Duas identidades para a mesma pessoa era o erro estrutural |
| Monitoramento · Alertas · Incidentes · SLA (Operações) | **OPS-002** + **OPS-007** | Alerta é notificação; SLA é métrica; incidente é objeto |
| KPIs · Dashboards · BI · Analytics | **OPS-010** + **FIN-007** | Sem camada semântica, cada tela dá um número diferente |
| 10 GPTs especializados | **AIC-006** skill packs | Roteamento é responsabilidade do sistema |

---

## 1.5 Mapeamento da sua lista de módulos

Você propôs 15 módulos. Nenhum foi perdido; alguns deixaram de ser módulo e viraram capacidade dentro de outro — que é o resultado esperado da deduplicação.

| Seu módulo | Onde ficou | Observação |
|---|---|---|
| Workspace | **WKS** | Módulo próprio |
| IA | **AIC** | Módulo próprio |
| Pesquisa Global | **SRC** | Módulo próprio |
| **App Launcher** | WKS-010 | Vira um widget. Não sustenta um módulo |
| Comunicação | **COM** | Módulo próprio, reduzido a comunicado + pulso |
| RH | **PPL** | Módulo próprio, reduzido a self-service + certificação |
| Financeiro | **FIN** + **REV** | **Dividido.** REV é a tese comercial e merece separação |
| Operações | **OPS** | Módulo próprio |
| **Universidade** | CNT-009 + PPL-004 | Deixa de ser módulo. Vira conteúdo + certificação |
| Documentação | **CNT** | Módulo próprio |
| **Analytics** | OPS-010 + FIN-007 | Deixa de ser módulo até existir camada semântica |
| Catálogo de Serviços | **SVC** | Módulo próprio |
| **Configurações** | PLT-007/008 | Capacidade de plataforma |
| **Permissões** | PLT-004 + IDN-004 | Divide-se entre plataforma e identidade |
| **SSO** | PLT-006 | Já existe. Capacidade, não módulo |
| — | **APR** *(novo)* | Emergiu da deduplicação: quatro filas de aprovação viraram um motor |
| — | **IDN** *(novo)* | Emergiu como pré-requisito de tudo |

> **Resultado: 15 módulos propostos → 13 domínios, sendo 2 novos e 4 dissolvidos.** Menos módulos, cada um com fronteira real.

---

## 1.6 Grafo de dependências e caminho crítico

### Camadas de dependência

```
CAMADA 0 — FUNDAÇÃO  (nada visível ao usuário; nada depois funciona sem)
┌─────────────────────────────────────────────────────────────────────┐
│ IDN-001 Pessoa ──┬─▶ IDN-002 Unidade/Depto/CC                       │
│                  ├─▶ IDN-003 Organograma                            │
│                  ├─▶ IDN-006 Pessoa↔Tecnico↔User                    │
│                  └─▶ IDN-007 Importação                             │
│ IDN-002 ─▶ IDN-004 Papel+Escopo ─▶ IDN-005 Delegação                │
│ PLT-003 app workspace + WorkspaceProvider                           │
│ PLT-009 contextvars   PLT-010 gate de cobertura                     │
│ AIC-001 feedback de IA   AIC-002 teto de custo                      │
└─────────────────────────────────────────────────────────────────────┘
        │
CAMADA 1 — CASCA E MOTORES
┌─────────────────────────────────────────────────────────────────────┐
│ PLT-001 Aurora ─▶ PLT-002 Componentes ─▶ WKS-001 AppShell           │
│ IDN-004 ─▶ PLT-004 Permissões ─▶ SRC-001 SearchDocument (acl)       │
│ IDN-003 ─▶ APR-001 Motor de aprovação ─▶ APR-003 auto-aprovação     │
│ IDN-002 ─▶ CNT-001 Documento ─▶ CNT-002 Versionamento               │
│ IDN-006 ─▶ OPS-001 Escala                                           │
│ IDN-006 ─▶ PPL-004 Certificação                                     │
│ (independente) REV-001 EscopoContrato ─▶ REV-002 TabelaPreco        │
│ (independente) FIN-003 ConsumoMaterialOS                            │
└─────────────────────────────────────────────────────────────────────┘
        │
CAMADA 2 — SUPERFÍCIE
┌─────────────────────────────────────────────────────────────────────┐
│ WKS-001 ─▶ WKS-002 Home ─▶ WKS-003 Runtime ─▶ WKS-004 Presets       │
│ APR-001 ─▶ APR-002 Bandeja ─▶ WKS-005 Widget Aprovações             │
│ OPS-001 ─▶ WKS-008 Widget Escala   +   PPL-005 bloqueio de despacho │
│ CNT-001 ─▶ CNT-004 Biblioteca · CNT-005 Leitura · COM-001 Comunicado│
│ IDN-004 ─▶ SVC-001 Catálogo ─▶ SVC-002 Formulário ─▶ SVC-003        │
│ SRC-001 ─▶ SRC-002 Ingestão ─▶ SRC-004 Léxica ; SRC-003 ⌘K local    │
└─────────────────────────────────────────────────────────────────────┘
        │
CAMADA 3 — VALOR COMPOSTO  (V1.1+)
┌─────────────────────────────────────────────────────────────────────┐
│ REV-002 + FIN-003 ─▶ REV-003 ─▶ REV-004 ─▶ REV-005                  │
│ FIN-003 ─▶ FIN-004 Custo da OS ─▶ REV-007 Margem                    │
│ AIC-001 + AIC-002 ─▶ AIC-003 ContratoAgente ─▶ AIC-005 diff         │
│ CNT-002 ─▶ AIC-008 Agente Conhecimento                              │
│ AIC-003 ─▶ AIC-004 Autonomia medida (V2)                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Caminho crítico do V1

O caminho mais longo entre o primeiro commit e o lançamento. Atraso aqui é atraso de release, um para um.

```
IDN-001 → IDN-002 → IDN-004 → PLT-004 → SRC-001 → SRC-002 → SRC-004
   │                              │
   └─▶ IDN-003 → APR-001 → APR-002 → WKS-005
                                        │
PLT-001 → PLT-002 → WKS-001 → WKS-002 → WKS-003 → WKS-004 → [V1]
```

**Dois caminhos paralelos, um ponto de junção.** A trilha de identidade/permissão e a trilha de casca visual podem correr em paralelo desde o dia 1, e só se encontram em `WKS-004` (presets). Isso permite duas frentes simultâneas sem bloqueio mútuo — informação relevante para a Etapa 7.

### Trilhas independentes (podem começar a qualquer momento)

Não dependem de identidade nem da casca. Podem ser feitas por quem estiver livre, e destravam o maior valor do produto.

| Trilha | Itens | Destrava |
|---|---|---|
| **Dados de contrato** | REV-001, REV-002 | Toda a tese de receita (REV-003 a REV-007, AIC-010) |
| **Material na OS** | FIN-003 | Custo real (FIN-004) e classificação de serviço (REV-003) |
| **Higiene técnica** | PLT-009, PLT-010 | Reduz risco antes de a base crescer |
| **Instrumentação de IA** | AIC-001, AIC-002 | Sem histórico agora, AIC-004 não existe depois |

### 🔁 Correção de uma recomendação minha anterior

Na [Revisão CPO §H.3](CPO_REVIEW_ICONNECT.md) eu recomendei *"fazer da Receita Não Faturada a funcionalidade nº 1 do roadmap"*. A baseline verificada mostra que ela tem **duas dependências estruturais de dados que não existem** (L1: escopo contratual; L2: material↔OS).

**A correção:** REV-004 continua sendo a funcionalidade de maior valor do produto, mas **não é a primeira a ser construída** — é a primeira a **valer**. O que vai para o topo do plano são os habilitadores dela: **REV-001, REV-002 e FIN-003**. São modelos de dados pequenos, sem interface, que podem correr em paralelo à trilha de identidade, e sem os quais a tese comercial inteira fica a seis meses de distância em vez de dois.

Se a Etapa 2 cortar apenas um item do V1, que não seja nenhum desses três.

---

## 1.7 Registro de riscos

Exposição = Probabilidade × Impacto, ambos de 1 a 5.

| ID | Risco | P | I | Exp | Mitigação | Gatilho de escalonamento |
|---|---|:-:|:-:|:-:|---|---|
| **R-01** | **Material comercial promete tenancy que o código não tem** | 5 | 5 | **25** | Decisão D-01 nesta semana: assumir instalação dedicada e corrigir o material | Qualquer proposta comercial enviada antes da decisão |
| **R-02** | **Escopo volta a inchar durante a execução** | 4 | 5 | **20** | Este inventário é a única fonte de escopo. Item novo entra só por revisão formal deste documento | 2ª solicitação de item fora do inventário no mesmo mês |
| **R-03** | **IDN atrasa e trava o caminho crítico inteiro** | 3 | 5 | **15** | IDN-001..004 é a primeira entrega, sem interface. Timebox rígido | IDN-004 não concluído até o fim da 5ª semana |
| **R-04** | **Biblioteca vazia no lançamento → IA descreditada** | 4 | 4 | **16** | IA generativa só no V1.1. Meta de 40 documentos publicados antes de ligar. AIC-008 desde cedo | Menos de 20 documentos publicados 30 dias antes do V1.1 |
| **R-05** | **Custo de IA sem teto** | 3 | 5 | **15** | AIC-002 é V1, obrigatório, antes de qualquer agente | Qualquer chamada de LLM em produção sem contador de custo |
| **R-06** | **Escopo contratual (REV-001) mais complexo que o previsto** | 4 | 4 | **16** | Modelar com 2 contratos reais na mão antes de codificar. Começar por 1 tipo de contrato, não por todos | Terceira reunião de modelagem sem esquema fechado |
| **R-07** | **Técnico de campo não adota** | 3 | 5 | **15** | Piloto com 5 técnicos antes de rollout. Preset sem KPI corporativo. OPS-003 offline no V1 | Menos de 60% de uso diário no piloto após 3 semanas |
| **R-08** | **Portal sem razão de retorno diário** | 3 | 4 | **12** | Três âncoras no V1: aprovação só existe lá, escala só existe lá, comunicado obrigatório bloqueia | DAU/MAU < 0,4 no 2º mês pós-lançamento |
| **R-09** | **Três famílias de CSS convivendo (Bootstrap + iConnect + Tailwind)** | 4 | 3 | **12** | Tailwind **apenas** dentro de `workspace`, com escopo de build isolado. Módulos antigos intocados. Decisão D-02 | Qualquer classe Tailwind aparecendo em template fora de `workspace/` |
| **R-10** | **Regressão nos módulos existentes ao ligar o Workspace** | 3 | 4 | **12** | `WorkspaceProvider` só lê. Nenhuma alteração em model existente sem migração testada. PLT-010 antes de tocar em FSM | Qualquer PR que altere model de `fsm` sem teste novo |
| **R-11** | **Concentração de conhecimento em um único desenvolvedor** | 4 | 4 | **16** | ADR por decisão relevante, PRD por módulo (Etapa 4), cobertura como documentação executável | — (risco estrutural, monitorar) |
| **R-12** | **LGPD — dado sensível de RH sem classificação** | 3 | 5 | **15** | PPL-002 (ASO é dado de saúde) exige classificação e retenção definidas **antes** do primeiro registro | Primeiro upload de ASO em produção sem política de retenção |
| **R-13** | **`threading.local()` sob ASGI causa vazamento de contexto** | 2 | 5 | **10** | PLT-009 no V1. Teste de concorrência | — |
| **R-14** | **Falso positivo de REV-004 gera atrito com cliente final** | 3 | 4 | **12** | Nunca automático. Sempre sugestão com evidência anexada e decisão humana | Taxa de rejeição > 40% no piloto |
| **R-15** | **Antifraude (OPS-006) interpretado como vigilância** | 3 | 4 | **12** | Sinaliza evidência, nunca pessoa. Motivo objetivo e verificável. Comunicar ao time de campo antes de ligar | Primeira reclamação formal do time de campo |
| **R-16** | **Estimativas irreais por baseline otimista** | 3 | 3 | **9** | Este documento marca 🟡 e 🔴 item a item. Estimativa na Etapa 7 parte daqui, não da intuição | Desvio > 30% em 2 entregas seguidas |

### Os quatro riscos que eu monitoro semanalmente

`R-01` (25) · `R-02` (20) · `R-04` (16) · `R-06` (16). Os dois primeiros são de decisão — resolvem-se com uma escolha. Os dois últimos são de execução — resolvem-se com disciplina.

---

## 1.8 Declaração de escopo

### Objetivo do produto (uma frase, para caber em qualquer discussão)

> **O iConnect Workspace é a camada onde o colaborador resolve o trabalho do dia — solicitar, aprovar, saber e executar — sem abrir o sistema operacional da empresa; e onde a operação, as pessoas e o dinheiro se encontram no mesmo dado.**

### Dentro do escopo do produto

| # | Compromisso |
|:-:|---|
| 1 | Ponto de entrada único, com identidade organizacional real |
| 2 | Resolver a solicitação e a aprovação sem sair da tela |
| 3 | Encontrar qualquer coisa por um único campo, com permissão respeitada |
| 4 | Publicar, versionar e provar leitura de conteúdo institucional |
| 5 | Escala, certificação e despacho amarrados: quem não pode, não é despachado |
| 6 | Custo e receita da operação visíveis onde a decisão acontece |
| 7 | IA governada — permissão, custo, feedback e auditoria antes de autonomia |

### Explicitamente fora do escopo — não-objetivos

Registrados para não serem reabertos sem fato novo.

| Não-objetivo | Motivo |
|---|---|
| Substituir e-mail, arquivo, chat ou videoconferência | M365/Google fazem melhor. Integramos |
| Ser um LMS (autoria, SCORM, vídeo, prova) | Categoria com incumbentes. Compramos |
| Ser um HRIS (folha, ponto, eSocial) | Risco regulatório, zero diferenciação |
| Ser uma rede social corporativa | Morre em 90 dias no porte-alvo |
| Reescrever os módulos operacionais existentes | Migração por atração, não por decreto |
| SaaS multi-tenant em 2026 | Decisão D-01. Reavaliar em 2027 |
| Multi-idioma | Sem cliente fora do Brasil |
| Marketplace, no-code studio, API pública de widget | Plataforma antes de haver plataforma |
| Métricas individuais de produtividade | Princípio. Risco trabalhista e destrói confiança |

### Critérios de saída da Etapa 1

| # | Critério | Estado |
|:-:|---|:-:|
| 1 | Todo item da visão tem ID estável e domínio | ✅ 139 itens |
| 2 | Duplicidades identificadas e fundidas | ✅ 19 fusões |
| 3 | Baseline verificada no código, não presumida | ✅ 9 lacunas + 5 passivos |
| 4 | Dependências mapeadas e caminho crítico identificado | ✅ |
| 5 | Riscos com probabilidade, impacto e gatilho | ✅ 16 riscos |
| 6 | Escopo e não-objetivos declarados | ✅ |
| 7 | Decisões bloqueantes explicitadas | ⏳ §1.9 — **exige você** |

---

## 1.9 Decisões tomadas

Registradas em 07/08/2026. São vinculantes para as etapas seguintes; reabrir exige fato novo.

| ID | Decisão | Escolha | Consequência no escopo |
|---|---|---|---|
| **D-01** | Modelo de entrega | ✅ **Instalação dedicada por cliente** | `PLT-011` → **OUT (2027)**. Abre a ação **A-01** (corrigir material comercial). Risco `R-01` deixa de ser risco e vira tarefa |
| **D-02** | Tailwind no stack | ✅ **Somente dentro de `workspace/`**, build isolado | `PLT-001` ganha o pipeline de build. Nasce a regra de lint **A-02**. `R-09` cai de exposição 12 para 4 |
| **D-03** | Fonte de dados de pessoas | ✅ **Híbrido** — cadastrais do RH, operacionais do iConnect | Muda `IDN-001` e `IDN-007`. Nasce `IDN-009`. Abre a pergunta aberta **Q-01** |
| **D-04** | Aprovação por canal externo | ✅ **Adiar para V2** com parecer jurídico | `APR-008` permanece V2, condicionado a parecer |
| **D-05** | Mobile do técnico | ✅ **App nativo + Workspace desktop/tablet** | Muda `OPS-003` de funcionalidade para contrato de API. Presets do V1 caem de 4 para 3. `R-07` muda de dono |

### Impacto de D-03 (Híbrido) — o mais delicado

Modelo híbrido é a escolha realista, e também a que mais exige disciplina de desenho. Sem regra explícita, "híbrido" degenera em dois cadastros divergentes — exatamente o problema que `IDN-001` existe para resolver.

**Regra que passa a valer, e que a Etapa 4 detalha no PRD de IDN:**

| Classe de campo | Fonte | Comportamento no iConnect |
|---|---|---|
| **Espelho** — nome, matrícula, CPF, admissão, cargo, departamento, situação | Sistema de RH | Somente leitura. Divergência é conflito registrado, nunca sobrescrita silenciosa |
| **Próprio** — papel, escopo, delegação, certificação, escala, preferências, foto de perfil | iConnect | Leitura e escrita. O RH não conhece esses conceitos |
| **Derivado** — gestor, centro de custo | Ambos | Vem do RH quando existe; editável no iConnect com marca de override e justificativa |

**Itens novos e alterados:**

| ID | Item | Base | Classe |
|---|---|:-:|:-:|
| IDN-001 | `Pessoa` **com `origem` por campo e marca de override** | 🔴 | **V1** |
| IDN-007 | Importação **e reconciliação** (era só CSV) | 🔴 | **V1** |
| **IDN-009** | **Política de sincronização e conflito** — cadência, precedência, fila de divergências | 🔴 | **V1** |

### Impacto de D-05 — redução real de escopo do Workspace

O técnico de campo sai do escopo de interface do Workspace V1. Isso é uma redução bem-vinda, e precisa estar escrita:

| Item | Antes | Depois |
|---|---|---|
| `OPS-003` Pacote do dia offline | Funcionalidade do Workspace | **Contrato de API** que o Workspace expõe ao app nativo. Sem interface própria |
| `WKS-004` Presets | 4 no V1 (colaborador, gestor, técnico, cliente) | **3 no V1** — colaborador, gestor, cliente. O preset técnico sai |
| `R-07` Técnico não adota | Risco do Workspace | **Risco do app nativo.** Sai deste registro; o Workspace herda apenas o risco de o técnico não receber comunicado obrigatório — mitigado por `COM-001` no app via API |

### Ações abertas decorrentes das decisões

| ID | Ação | Dono | Prazo |
|---|---|---|---|
| **A-01** | Corrigir [PRECIFICACAO_E_DOCUMENTACAO_SISTEMA.md](PRECIFICACAO_E_DOCUMENTACAO_SISTEMA.md): remover "multi-tenant" dos diferenciais e substituir os planos SaaS por modelo de instalação dedicada | Produto | Antes da próxima proposta comercial |
| **A-02** | Regra de lint/CI: classe Tailwind fora de `workspace/` reprova o PR | Engenharia | Junto com `PLT-001` |
| **A-03** | Definir precedência e cadência de sincronização com o RH (`IDN-009`) | Produto + RH | Antes de `IDN-001` entrar em código |

### Perguntas abertas (não bloqueiam a Etapa 2)

| ID | Pergunta | Bloqueia |
|---|---|---|
| **Q-01** | **Qual sistema de RH é a fonte dos campos espelho?** Define o conector, o formato e a cadência de `IDN-007` | Implementação de `IDN-007`, não seu desenho |
| **Q-02** | Quais dois contratos reais serão usados para modelar `REV-001`? | Início de `REV-001` (ver `R-06`) |

---

## Próxima etapa

**Etapa 2 — Definição do MVP.** Aplicar *"é indispensável para lançar?"* item a item sobre os 140 (139 + `IDN-009`), produzir o corte final do V1 com justificativa de cada exclusão, e definir os critérios objetivos de lançamento.

**Aguarda aprovação da Etapa 1.**

---

*Etapa 1 de 9 · Este documento é a fonte única de escopo. Alteração de escopo se faz aqui primeiro, no código depois.*
