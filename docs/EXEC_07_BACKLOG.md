# Execução · Etapa 7 — Backlog

> **Documento de execução.** 24 épicos → 149 features → **107 stories** do V1.0, com critérios de aceite, prioridade, estimativa e dependências. Plano de ondas, caminho crítico e cenários de capacidade.
>
> **Agosto/2026** · Etapa 7 de 9 · **Aguarda aprovação antes da Etapa 8**
>
> ⚠️ **Revisado em 12/08/2026 pela [Etapa 10 — Reposicionamento](EXEC_10_REPOSICIONAMENTO.md).** O produto se chama **iConnect Workspace**, e Workspace e Platform são dois produtos — não uma camada sobre o outro. Onde este documento contradiz a Etapa 10, a Etapa 10 vence; §10.7 nomeia cada contradição. Nada aqui foi descartado.

---

## Sumário

- [7.0 Método — por que a profundidade varia](#70-método--por-que-a-profundidade-varia)
- [7.1 Convenções](#71-convenções)
- [7.2 Onda 0 — Preparação](#72-onda-0--preparação)
- [7.3 Onda 1 — Fundação](#73-onda-1--fundação)
- [7.4 Onda 2 — Motores](#74-onda-2--motores)
- [7.5 Onda 3 — Conteúdo e Home](#75-onda-3--conteúdo-e-home)
- [7.6 Onda 4 — Serviços e widgets](#76-onda-4--serviços-e-widgets)
- [7.7 Onda 5 — Busca, Pessoas e Escala](#77-onda-5--busca-pessoas-e-escala)
- [7.8 Onda 6 — Fechamento e piloto](#78-onda-6--fechamento-e-piloto)
- [7.9 Trilha B0 — independente](#79-trilha-b0--independente)
- [7.10 Consolidado de estimativas](#710-consolidado-de-estimativas)
- [7.11 Caminho crítico e plano de ondas](#711-caminho-crítico-e-plano-de-ondas)
- [7.12 Cenários de capacidade — a conversa difícil](#712-cenários-de-capacidade--a-conversa-difícil)
- [7.13 Itens inegociáveis e ordem de corte](#713-itens-inegociáveis-e-ordem-de-corte)

---

## 7.0 Método — por que a profundidade varia

Você pediu Épico → Feature → Story → Task → Subtask. Vou entregar isso, mas **com profundidade decrescente conforme a distância**, e quero justificar em vez de fazer em silêncio.

| Distância | Profundidade | Por quê |
|---|---|---|
| **Ondas 0 e 1** (começam agora) | Story + Task | É onde a decomposição vira ação imediata |
| **Ondas 2 a 6** (V1.0) | Story com critério de aceite | Task se decide no planejamento, por quem executa |
| **V1.1 e além** | Feature ([Etapa 4](EXEC_04_PRD.md)) | Escrever task para trabalho de 6 meses à frente é desperdício — ele vai mudar |

> **Escrever 1.500 subtasks agora produziria um documento impressionante e inútil.** Metade estaria errada na terceira sprint, e a outra metade ninguém leria. Detalhe tem prazo de validade.

### Sobre o formato "Como usuário, quero…"

Uso a forma de user story onde há **usuário e valor percebido**. Para habilitadores técnicos — migração, índice, gate de cobertura — uso título imperativo.

> Forçar *"Como usuário, quero uma migração de banco para que…"* é teatro de processo. A story existe para carregar o **porquê**; quando o porquê é técnico, o formato técnico comunica melhor.

---

## 7.1 Convenções

### Identificadores

| Nível | Formato | Onde foi definido |
|---|---|---|
| Épico | `EP-NNN` | Etapa 4 |
| Feature | `FT-NNN` | Etapa 4 |
| **Story** | `ST-NNN` | **Aqui** |
| Task | `ST-NNN.T1` | Aqui |
| Subtask | `ST-NNN.T1.a` | No planejamento |

### Estimativa

Fibonacci, com âncora de calibração — pontos sem âncora não servem para planejar sem histórico de velocidade.

| Pontos | Esforço ideal | Exemplo desta lista |
|:-:|---|---|
| **1** | 2–3 h | Adicionar índice, ajustar template |
| **2** | ~meio dia | Modelo simples + admin |
| **3** | ~1 dia | Modelo + serviço + teste |
| **5** | ~2 dias | Fluxo completo com UI e testes |
| **8** | ~3–4 dias | Componente central com muitos casos de borda |
| **13** | — | **Proibido.** Precisa ser dividido |

**Premissa de velocidade:** um desenvolvedor sênior nesta base entrega ~**9 pontos por semana** de trabalho de feature — o resto da semana é revisão, correção, reunião e troca de contexto. Isso é observação de mercado, não medição deste time. **Recalibrar após a Onda 1**, que é a primeira medição real.

### Prioridade

| Nível | Significado |
|:-:|---|
| **P0** | Bloqueia o lançamento. Caminho crítico ou critério de saída da [Etapa 2 §2.7](EXEC_02_MVP.md) |
| **P1** | Necessário para o V1.0 |
| **P2** | Desejável. **Primeiro a cair** sob pressão de prazo |
| 🔒 | **Inegociável** — fundação sem tela, protegida contra o risco `R-17` |

### Definição de pronto para começar (DoR)

Uma story entra em execução quando: critério de aceite escrito · dependências concluídas · decisão de UX resolvida (Etapa 6) · sem pergunta aberta bloqueante.

### Definição de pronto (DoD)

| # | Item |
|:-:|---|
| 1 | Critérios de aceite verificados |
| 2 | Teste automatizado cobrindo o caminho feliz **e** o principal caso de borda |
| 3 | Gate de cobertura do app permanece verde |
| 4 | Permissão verificada **no serviço**, não só na view |
| 5 | Sem literal de cor, espaço ou raio (se tocar em template) |
| 6 | Migração reversível |
| 7 | Log estruturado nos pontos de falha |
| 8 | Revisão de outra pessoa — ou, se solo, revisão em sessão separada com checklist |

> **Item 8 endereça `R-11` (concentração de conhecimento).** Auto-revisão no mesmo dia não encontra nada. Revisão no dia seguinte, com checklist, encontra.

---

## 7.2 Onda 0 — Preparação

**6 stories · 17 pontos.** Sem entrega visível. É a onda que evita retrabalho nas seguintes.

| ID | Story | Pts | Pri | Dep |
|---|---|:-:|:-:|---|
| **ST-001** | Estender o gate de cobertura a `fsm` e `km_audit` | 3 | P0 🔒 | — |
| **ST-002** | Criar os apps `identidade` e `workspace` com esqueleto e testes | 2 | P0 | — |
| **ST-003** | Pipeline Tailwind isolado + regra de CI (`A-02`) | 3 | P0 | ST-002 |
| **ST-004** | Rodar o CI em PostgreSQL, não SQLite | 2 | P0 | — |
| **ST-005** | Sprite de ícones Lucide + build | 2 | P1 | ST-002 |
| **ST-006** | Coletar a linha de base das métricas M3 e M4 | 5 | P0 🔒 | — |

### Decomposição

**ST-001 · Estender o gate de cobertura** — `EP-005 / FT-021` · 3 pts · P0 🔒

> O núcleo vertical (`fsm` 6.700 linhas, `km_audit` 4.100) está sem rede de segurança, e a Onda 5 vai alterar o dispatch do FSM.

| Task | Descrição |
|---|---|
| T1 | Medir a cobertura atual de `fsm` e `km_audit` isoladamente |
| T2 | Adicionar ambos ao `--cov` em `pyproject.toml`, com `fail_under` no nível medido |
| T3 | Documentar os três ratchets no `pyproject.toml` |
| T4 | Confirmar que o CI reprova ao remover um teste existente |

**Aceite:** ① os três apps têm gate ativo · ② nenhum gate abaixo do nível de entrada · ③ remover um teste reprova o build.

---

**ST-002 · Criar os apps** — `EP-005 / FT-018` · 2 pts · P0

| Task | Descrição |
|---|---|
| T1 | `identidade/` com `models`, `services`, `migrations`, `tests` |
| T2 | `workspace/` conforme a estrutura da [Etapa 5 §5.2](EXEC_05_ARQUITETURA.md) |
| T3 | Registrar em `INSTALLED_APPS`; incluir `workspace.urls` sob `/workspace/` |
| T4 | `WorkspaceProvider` (ABC) + `registry` com `register()` e `all()` |
| T5 | Teste de fumaça: `/workspace/` responde 200 para usuário autenticado |

**Aceite:** ① apps carregam sem erro · ② `/workspace/` acessível · ③ registry aceita e devolve provider · ④ nenhum import de `workspace` dentro de `dashboard` ou `fsm`.

---

**ST-003 · Pipeline Tailwind + regra de CI** — `EP-004 / FT-015` · 3 pts · P0

| Task | Descrição |
|---|---|
| T1 | `tokens.css` completo da [Etapa 6 §6.7](EXEC_06_DESIGN_SYSTEM.md) |
| T2 | `aurora.css` com `@import "tailwindcss"` e `@source` restrito |
| T3 | Alvo no `Makefile`: `make css` |
| T4 | Script de CI que reprova classe Tailwind fora de `workspace/` |
| T5 | Confirmar que `collectstatic` inclui `dist/aurora.css` e que o `compressor` o ignora |

**Aceite:** ① build lê apenas `workspace/templates/**` · ② CI reprova violação de `A-02` · ③ nenhum estilo do Material Dashboard vaza para o shell.

---

**ST-004 · CI em PostgreSQL** — `EP-005` · 2 pts · P0

> Sem isto, `ExclusionConstraint` (`ST-085`), FTS (`ST-077`) e índices GIN nunca são testados — só quebram em produção.

| Task | Descrição |
|---|---|
| T1 | Serviço PostgreSQL no CI, com `btree_gist` habilitado |
| T2 | Apontar `DATABASES` de teste para ele |
| T3 | Marcar como `skip` em SQLite os testes que exigem Postgres, com motivo explícito |

**Aceite:** ① suíte roda em Postgres no CI · ② teste de `ExclusionConstraint` passa lá e é pulado localmente com aviso.

---

**ST-005 · Sprite de ícones** — `EP-004 / FT-017` · 2 pts · P1

| Task | Descrição |
|---|---|
| T1 | Baixar os 26 ícones Lucide da [Etapa 6 §6.9](EXEC_06_DESIGN_SYSTEM.md) |
| T2 | Script que gera `icons.svg` com `<symbol>` |
| T3 | Classe `.au-icon` e template tag `{% au_icon "check" %}` |

**Aceite:** ① sprite ≤10 KB · ② ícone herda `currentColor` · ③ `aria-hidden` por padrão.

---

**ST-006 · Linha de base das métricas** — `EP-005` · 5 pts · P0 🔒

> **Sem isto, M3 (−40% no tempo de aprovação) e M4 (40% das solicitações no catálogo) são inverificáveis** — e o sucesso do V1.0 vira opinião.

| Task | Descrição |
|---|---|
| T1 | Amostrar 30 aprovações reais dos últimos 90 dias e medir o tempo pedido → decisão |
| T2 | Estimar a proporção atual de solicitações por e-mail e WhatsApp (amostra de 2 semanas) |
| T3 | Registrar a taxa atual de leitura de comunicado (provavelmente não medida → assumir 0 e documentar) |
| T4 | Gravar em `docs/METRICAS_LINHA_BASE.md`, com método e data |

**Aceite:** ① as três linhas de base documentadas com método · ② números defensáveis, com amostra declarada.

---

## 7.3 Onda 1 — Fundação

**19 stories · 70 pontos.** Duas frentes paralelas, sem bloqueio mútuo.

### Frente A · Identidade — 11 stories, 40 pts

| ID | Story | Pts | Pri | Dep |
|---|---|:-:|:-:|---|
| **ST-007** | Modelos `Unidade` e `Departamento` | 3 | P0 🔒 | ST-002 |
| **ST-008** | Modelo `Papel` com permissões declarativas | 3 | P0 🔒 | ST-002 |
| **ST-009** | Evoluir `PerfilUsuario` (matrícula, situação, FKs, `origem_campos`) | 5 | P0 🔒 | ST-007 |
| **ST-010** | Comando para casar `departamento` texto → FK | 3 | P0 | ST-009 |
| **ST-011** | Vincular `Pessoa` ↔ `Tecnico` ↔ `User` | 2 | P0 🔒 | ST-009 |
| **ST-012** | `AtribuicaoPapel` com escopo e vigência + migrar `UserRole` | 5 | P0 🔒 | ST-008, ST-009 |
| **ST-013** | `Delegacao` com validação de não-ampliação | 3 | P0 | ST-012 |
| **ST-014** | Serviço `pode()` com os 5 escopos e cache por request | 8 | P0 🔒 | ST-012, ST-013 |
| **ST-015** | `liderados_recursivos()` em uma CTE | 3 | P0 | ST-009 |
| **ST-016** | Decorador `@requer()` para views | 2 | P0 | ST-014 |
| **ST-017** | Organograma com validação de ciclo | 3 | P0 | ST-009 |

#### Decomposição das três mais delicadas

**ST-009 · Evoluir `PerfilUsuario`** — `EP-001 / FT-002` · 5 pts · P0 🔒

> A story mais arriscada da onda: altera um modelo com dados reais e `related_name="perfil"` usado em views e templates.

| Task | Descrição |
|---|---|
| T1 | Migração aditiva: `matricula`, `situacao`, `data_admissao`, `origem_campos` (todos nullable) |
| T2 | FKs `unidade`, `departamento_fk`, `gestor`, `centro_custo` (todos nullable) |
| T3 | Índice em `gestor_id` (usado pela CTE de `ST-015`) |
| T4 | Propriedades de leitura por classe de campo: `e_espelho(campo)`, `e_proprio(campo)` |
| T5 | `save()` respeita `origem_campos` — campo espelho não sobrescreve sem decisão |
| T6 | Testar a migração contra dump de produção e **medir o tempo de lock** |

**Aceite:** ① nenhuma coluna existente alterada ou removida · ② migração reversível · ③ tudo que usa `user.perfil` hoje continua funcionando · ④ tempo de lock medido e registrado · ⑤ campo espelho não é sobrescrito (`VAL-IDN-06`).

---

**ST-012 · `AtribuicaoPapel` + migrar `UserRole`** — `EP-001 / FT-003` · 5 pts · P0 🔒

| Task | Descrição |
|---|---|
| T1 | Modelo com escopo, vigência e a constraint de unicidade da [Etapa 3](EXEC_03_MODULOS.md) |
| T2 | Índice `(pessoa, vigencia_inicio, vigencia_fim)` |
| T3 | Seed dos 6 papéis do V1.0 com suas permissões |
| T4 | Comando de migração `UserRole` → `AtribuicaoPapel` usando `LEGACY_ROLE_MAP` |
| T5 | Relatório do que não casou; reexecutável sem duplicar |
| T6 | Manter `UserRole` funcionando durante a transição (nada quebra) |

**Aceite:** ① todo `UserRole` existente vira atribuição equivalente · ② ninguém perde acesso · ③ comando reexecutável · ④ vigência aberta (`fim = NULL`) no migrado.

---

**ST-014 · Serviço `pode()`** — `EP-001 / FT-005` · 8 pts · P0 🔒

> **A função mais chamada do sistema.** Uma home a invoca ~40 vezes. Erro aqui é falha de segurança; lentidão aqui é lentidão em tudo.

| Task | Descrição |
|---|---|
| T1 | Assinatura `pode(pessoa, permissao, alvo=None) -> bool` |
| T2 | Reunir atribuições vigentes (1 query) |
| T3 | Somar delegações ativas, com interseção — nunca amplia |
| T4 | Casamento por prefixo com hierarquia de escopo (`global ⊃ unidade ⊃ … ⊃ proprio`) |
| T5 | Resolução de escopo contra `alvo`, nos 5 casos |
| T6 | Cache em `request.perm_cache` — e **nada entre requests** (`ADR-005`) |
| T7 | Suíte de teste: um caso por escopo, mais delegação, mais vigência vencida |
| T8 | Teste de desempenho: ≤20 ms (p95) com organograma de 500 pessoas |

**Aceite:** ① os 5 escopos corretos · ② delegação não amplia (`VAL-IDN-04`) · ③ atribuição vencida não concede · ④ escopo maior satisfaz menor · ⑤ mudança de papel vale na requisição seguinte · ⑥ ≤20 ms p95 · ⑦ **cobertura de 100% neste módulo** — é código de segurança.

---

### Frente B · Aurora — 8 stories, 30 pts

| ID | Story | Pts | Pri | Dep |
|---|---|:-:|:-:|---|
| **ST-018** | `tokens.css` completo, claro e escuro | 3 | P0 | ST-003 |
| **ST-019** | Teste de contraste dos tokens no CI | 2 | P0 🔒 | ST-018 |
| **ST-020** | Componentes: `button`, `icon-button`, `card`, `badge` | 5 | P0 | ST-018 |
| **ST-021** | Componentes: `field`, `input`, `select`, `file-drop` | 5 | P0 | ST-018 |
| **ST-022** | Componentes: `table`, `list-row`, `empty`, `skeleton` | 5 | P0 | ST-018 |
| **ST-023** | Componentes: `modal`, `panel`, `toast`, `inline-alert`, `avatar` | 5 | P1 | ST-018 |
| **ST-024** | HTMX + Alpine (build CSP) integrados ao shell | 3 | P0 | ST-003 |
| **ST-025** | Auto-hospedar Inter variável | 2 | P2 | ST-003 |

**ST-019 · Teste de contraste** — `EP-004 / FT-014` · 2 pts · P0 🔒

> É o que impede a repetição do defeito `a { color: #06b6d4 }` — contraste 2,43:1, encontrado na [Etapa 6 §6.0](EXEC_06_DESIGN_SYSTEM.md).

| Task | Descrição |
|---|---|
| T1 | Parser que lê os tokens de `tokens.css` |
| T2 | Função de razão de contraste (WCAG 2.1) |
| T3 | Tabela de pares obrigatórios, avaliada em claro e escuro |
| T4 | Rodar no CI; token que regride reprova o PR |

**Aceite:** ① os 6 pares passam AA nos dois temas · ② alterar um token para valor ruim reprova o build.

**ST-024 · HTMX + Alpine CSP** — `EP-004` · 3 pts · P0

| Task | Descrição |
|---|---|
| T1 | HTMX 2.x local (sem CDN), com nonce |
| T2 | **Alpine na distribuição CSP** (`@alpinejs/csp`) — [ADR-002](EXEC_05_ARQUITETURA.md) |
| T3 | Verificar com a **CSP de produção**, não a de dev |
| T4 | `workspace.js`: config global do HTMX, tratamento de erro, indicadores |

**Aceite:** ① nenhuma violação de CSP no console sob a política de produção · ② HTMX troca fragmento · ③ Alpine funciona com métodos declarados (`x-data="componente"`), sem expressão avaliada.

---

## 7.4 Onda 2 — Motores

**18 stories · 74 pontos.**

### Frente A · Sincronização + Aprovação — 11 stories, 44 pts

| ID | Story | Pts | Pri | Dep | Aceite (resumo) |
|---|---|:-:|:-:|---|---|
| **ST-026** | Interface de conector do RH + implementação CSV | 5 | P0 | ST-009 | Conector trocável sem alterar o serviço |
| **ST-027** | Reconciliação e `ConflitoSincronizacao` | 5 | P0 🔒 | ST-026 | Campo espelho divergente **nunca** sobrescreve |
| **ST-028** | Fila de conflitos com resolução | 3 | P1 | ST-027 | Decisão registra autor, data e justificativa |
| **ST-029** | Task Celery de sincronização periódica | 2 | P1 | ST-027 | Cadência configurável; execução concorrente bloqueada |
| **ST-030** | Importação inicial com relatório | 3 | P0 | ST-026 | Reexecutável; relatório de criados/atualizados/conflitos |
| **ST-031** | `PoliticaAprovacao` e avaliação | 5 | P0 | ST-014 | Primeira política que casar por `ordem` vence |
| **ST-032** | `SolicitacaoAprovacao` + `EtapaAprovacao` | 5 | P0 | ST-031 | `GenericFK`; cadeia congelada na criação |
| **ST-033** | Resolução de cadeia com delegação e regra anti-autoaprovação | 5 | P0 | ST-032, ST-013 | Solicitante nunca aprova o próprio (`VAL-APR-01`) |
| **ST-034** | Estado `pendente_configuracao` + alerta ao admin | 3 | P0 🔒 | ST-033 | Cadeia sem aprovador **nunca** falha em silêncio |
| **ST-035** | Auto-aprovação registrada como decisão | 3 | P0 | ST-031 | Decisão consultável, com `decidido_por = NULL` |
| **ST-036** | `decidir()`: aprovar, reprovar, devolver | 5 | P0 | ST-033 | Devolução recria a cadeia; motivo ≥10 caracteres |

### Frente B · Casca — 7 stories, 30 pts

| ID | Story | Pts | Pri | Dep | Aceite (resumo) |
|---|---|:-:|:-:|---|---|
| **ST-037** | AppShell — topbar, sidebar, layout, tema | 5 | P0 | ST-020…023 | Item de menu sem permissão não é renderizado (N6) |
| **ST-038** | `WorkspaceContextMiddleware` | 3 | P0 | ST-014 | Curto-circuito fora de `/workspace/` (`ADR-009`) |
| **ST-039** | `FeatureFlag` com ativação por papel e por pessoa | 3 | P0 🔒 | ST-008 | **Rollback em ≤5 min sem deploy** |
| **ST-040** | Registro de providers via `AppConfig.ready()` | 3 | P0 | ST-002 | `workspace` não importa app de domínio |
| **ST-041** | Runtime de widget — cache por geração, timeout, erro | 8 | P0 | ST-038, ST-040 | Widget que falha devolve 200 e não derruba a home |
| **ST-042** | Eventos de widget em `ws/notifications/` | 5 | P1 | ST-041 | Reusa o consumer existente (`ADR-003`) |
| **ST-043** | Auditoria estendida a `Pessoa` e `Aprovacao` | 3 | P0 | ST-038 | Leitura de dado de pessoa registrada |

**ST-041 · Runtime de widget** — `EP-019 / FT-104` · 8 pts · P0

| Task | Descrição |
|---|---|
| T1 | `WidgetSpec` e registro declarativo |
| T2 | View `/workspace/widget/<chave>/` com verificação de permissão → 204 se negada |
| T3 | Cache por geração: `wks:w:<chave>:<pessoa>:<gen>` + `INCR` na invalidação |
| T4 | Execução com timeout individual (3 s), isolando o provider |
| T5 | Templates dos 4 estados: carregando, com dados, vazio, erro |
| T6 | Erro devolve **HTTP 200** — 500 congelaria o esqueleto no HTMX |
| T7 | Altura reservada por widget (CLS = 0) |

**Aceite:** ① widget sem permissão ausente do HTML · ② provider lento não afeta os outros · ③ erro isolado no widget · ④ `INCR` invalida na próxima carga · ⑤ CLS = 0 medido.

---

## 7.5 Onda 3 — Conteúdo e Home

**18 stories · 71 pontos.**

### Frente A · Conteúdo e Comunicação — 12 stories, 42 pts

| ID | Story | Pts | Pri | Dep | Aceite (resumo) |
|---|---|:-:|:-:|---|---|
| **ST-044** | `Documento` + `acl_subjects()` | 5 | P0 | ST-007 | A mesma função serve biblioteca e índice |
| **ST-045** | Biblioteca — listar, filtrar, visualizar | 5 | P0 | ST-044 | Documento restrito ausente para quem não é público-alvo |
| **ST-046** | Publicação de documento | 3 | P0 | ST-044 | Sem dono não publica (`VAL-CNT-01`) |
| **ST-047** | `PendenciaLeitura` gerada por público-alvo | 5 | P0 | ST-044 | Quem é admitido depois recebe a pendência |
| **ST-048** | Confirmação de leitura | 3 | P0 | ST-047 | Registra pessoa, data e IP |
| **ST-049** | Estado `dispensada` | 2 | P1 | ST-047 | Relatório de conformidade fecha |
| **ST-050** | Task de expiração de documentos | 2 | P1 | ST-044 | Vencido some da lista e do índice |
| **ST-051** | `Comunicado` com 3 classes | 3 | P0 | ST-044 | Publicado não é editável (`VAL-COM-03`) |
| **ST-052** | Público-alvo por regra | 3 | P0 | ST-007 | Regra, nunca lista de pessoas |
| **ST-053** | `ComunicadoCriticoMiddleware` | 5 | P0 | ST-051 | **Logout sempre acessível durante o bloqueio** |
| **ST-054** | Relatório de confirmação por gestor | 3 | P1 | ST-048, ST-015 | Confirmados e pendentes, filtrável |
| **ST-055** | API JSON de comunicados (app nativo) | 3 | P1 | ST-051 | Mesmo filtro de público-alvo da web |

### Frente B · Home e Aprovações — 6 stories, 29 pts

| ID | Story | Pts | Pri | Dep | Aceite (resumo) |
|---|---|:-:|:-:|---|---|
| **ST-056** | Home com 3 zonas e grid responsivo | 5 | P0 | ST-037, ST-041 | Zona 1 em ≤800 ms (p95) |
| **ST-057** | `Preset` e resolução por papel | 3 | P0 | ST-056 | 2 presets com experiências distintas |
| **ST-058** | Widget · Zona de atenção | 3 | P0 | ST-047, ST-041 | Pendência obrigatória + o que vence hoje |
| **ST-059** | Widget · Aprovações com ação inline | 8 | P0 | ST-036, ST-041 | Aprovar sem sair da home, ≤400 ms |
| **ST-060** | Aprovação em lote | 5 | P0 | ST-059 | 10 itens com 1 falha → 9 aprovados + erro nomeado |
| **ST-061** | Bandeja completa com filtros | 5 | P1 | ST-036 | Link direto funciona sem HTMX (N4) |

---

## 7.6 Onda 4 — Serviços e widgets

**10 stories · 37 pontos.** Frente única — as duas convergem aqui.

| ID | Story | Pts | Pri | Dep | Aceite (resumo) |
|---|---|:-:|:-:|---|---|
| **ST-062** | `ItemCatalogo` com validações | 3 | P0 | ST-031 | Sem dono e com >3 campos livres não publica |
| **ST-063** | Renderizador de formulário declarativo | 5 | P0 | ST-021, ST-062 | 6 tipos fechados, sem condicional |
| **ST-064** | Pré-preenchimento pela identidade | 3 | P0 | ST-063, ST-009 | Não pede o que o perfil já sabe |
| **ST-065** | Catálogo navegável com busca | 3 | P0 | ST-062 | Navegação por problema, não por departamento |
| **ST-066** | `solicitar()` — ticket + aprovação atômicos | 5 | P0 | ST-064, ST-032 | Falha em um reverte o outro |
| **ST-067** | Os 6 itens do catálogo, com donos nomeados | 3 | P0 | ST-066 | Cada um com dono real (`R-19`) |
| **ST-068** | Solicitar em nome de liderado | 2 | P2 | ST-066, ST-015 | Exige `svc.solicitar.equipe` |
| **ST-069** | Widget · Meu dia | 5 | P0 | ST-041, ST-066 | Agrega providers; um lento não trava os outros |
| **ST-070** | Widget · Mural | 3 | P0 | ST-051, ST-041 | Confirmação inline |
| **ST-071** | Widget · Acesso rápido + `AppSpec` + `UsoApp` | 5 | P0 | ST-041 | Todo módulo alcançável em ≤2 cliques (A7) |

> **`ST-067` tem uma dependência que não é de código:** os 6 donos precisam ser nomeados por pessoas reais antes da publicação. É item de organização, não de engenharia — e vale acompanhar desde a Onda 0.

---

## 7.7 Onda 5 — Busca, Pessoas e Escala

**17 stories · 61 pontos.** A onda mais pesada, e a que contém o diferencial do produto.

### Busca — 7 stories, 24 pts

| ID | Story | Pts | Pri | Dep | Aceite (resumo) |
|---|---|:-:|:-:|---|---|
| **ST-072** | `SearchDocument` com os dois índices GIN | 3 | P0 | ST-004 | Coluna `embedding` prevista, sem uso no V1.0 |
| **ST-073** | `subjects_de(pessoa)` | 2 | P0 | ST-014 | Reusa o cache do request |
| **ST-074** | Provider de `Pessoa` e ingestão | 3 | P0 | ST-072, ST-040 | Fonte única no V1.0 |
| **ST-075** | Task de indexação + reconciliação diária | 3 | P0 | ST-074 | Sinal perdido é corrigido pela varredura |
| **ST-076** | ⌘K — camada local | 5 | P0 | ST-024 | Primeiro resultado em ≤120 ms, sem rede |
| **ST-077** | Busca léxica com FTS e agrupamento | 5 | P0 | ST-073, ST-074 | ≤600 ms (p95); degrada para local se o índice falhar |
| **ST-078** | Teste de vazamento de permissão | 3 | P0 🔒 | ST-077 | Duas pessoas, conjuntos distintos, **sem contagem residual** |

### Pessoas e Escala — 10 stories, 37 pts

| ID | Story | Pts | Pri | Dep | Aceite (resumo) |
|---|---|:-:|:-:|---|---|
| **ST-079** | `TipoCertificacao` + `Certificacao` | 3 | P0 🔒 | ST-011 | Ligado a `fsm.Skill`; estado calculado, nunca gravado |
| **ST-080** | `Ausencia` com transições automáticas | 3 | P0 | ST-009 | Muda `situacao` no início e devolve no fim |
| **ST-081** | Meu perfil com campos espelho e próprios | 5 | P0 | ST-027 | Campo espelho somente leitura, com origem visível |
| **ST-082** | `pode_executar()` + **hook no dispatch do FSM** | 5 | P0 🔒 | ST-079, ST-001 | Certificação vencida **bloqueia** o despacho |
| **ST-083** | Exceção com justificativa auditada | 3 | P0 | ST-082 | `operacao` registra exceção; **não pode desligar a regra** |
| **ST-084** | Alertas de vencimento em 90/30/15/5 | 3 | P0 🔒 | ST-079 | Um alerta por marco, sem repetir |
| **ST-085** | `Escala` + `TurnoEscala` com `ExclusionConstraint` | 5 | P0 | ST-004, ST-011 | Sobreposição rejeitada **pelo banco** |
| **ST-086** | Admin de escala com validações | 3 | P0 | ST-085 | Ausência bloqueia; certificação a vencer alerta |
| **ST-087** | Widget · Escala e plantão agora | 5 | P0 | ST-085, ST-041 | Plantão correto no instante; lacuna de cobertura visível |
| **ST-088** | API de escala atual | 2 | P1 | ST-085 | Consumida pelo app nativo |

**ST-082 · Hook no dispatch** — `EP-015 / FT-076` · 5 pts · P0 🔒

> **É o diferencial mais defensável do produto** ([Revisão CPO §E.5](CPO_REVIEW_ICONNECT.md)) — e a única story do V1.0 que altera o comportamento de um módulo existente em produção.

| Task | Descrição |
|---|---|
| T1 | `identidade/services/habilitacao.py :: pode_executar(tecnico, os)` |
| T2 | Para cada skill exigida pela OS, verificar certificação vigente |
| T3 | Devolver motivo estruturado **e a lista de técnicos habilitados** |
| T4 | Chamar do dispatch do FSM, atrás de feature flag própria |
| T5 | Mensagem para quem despacha, com as alternativas |
| T6 | Testes: com certificação, sem, vencida hoje, vencida ontem, sem tipo mapeado |
| T7 | Teste de regressão do dispatch com a flag **desligada** |

**Aceite:** ① técnico com NR vencida não é despachado · ② motivo e alternativas visíveis · ③ tipo sem `bloqueia_despacho` não bloqueia · ④ **com a flag desligada, o dispatch se comporta exatamente como antes** · ⑤ nenhuma regressão na suíte do FSM.

---

## 7.8 Onda 6 — Fechamento e piloto

**8 stories · 40 pontos.**

| ID | Story | Pts | Pri | Dep | Aceite (resumo) |
|---|---|:-:|:-:|---|---|
| **ST-089** | Instrumentar as 9 métricas de produto | 5 | P0 🔒 | todas | Evento gravado no ato, não calculado depois |
| **ST-090** | Painel de métricas + 4 gatilhos de versão | 5 | P0 🔒 | ST-089 | **Sem o painel, o V1.0 não lança** |
| **ST-091** | Testes de aceite das 4 jornadas (J1–J4) | 8 | P0 | todas | Jornada quebrada reprova o release |
| **ST-092** | Runbook de rollback, testado | 3 | P0 | ST-039 | Rollback executado em homologação em ≤5 min |
| **ST-093** | Migrações validadas contra dump de produção | 3 | P0 | todas | Tempo de lock medido por migração |
| **ST-094** | Percurso de acessibilidade + axe-core no CI | 5 | P1 | todas | Teclado completo; zero violação crítica |
| **ST-095** | Carga do piloto — importação real e flags | 3 | P0 | ST-030, ST-039 | Fila de divergências zerada (critério O2) |
| **ST-096** | Reserva para ajustes do piloto | 8 | P0 | — | Buffer explícito, não otimismo implícito |

---

## 7.9 Trilha B0 — independente

**11 stories · 34 pontos.** Não dependem de identidade nem da casca. **São a válvula de escape do cronograma:** quando uma frente trava, ela migra para cá em vez de ficar ociosa.

| ID | Story | Pts | Pri | Dep | Nota |
|---|---|:-:|:-:|---|---|
| **ST-097** | `TipoServico` ligado a `fsm.Skill` | 2 | P1 🔒 | — | Fundação |
| **ST-098** | `EscopoContrato` com franquia | 3 | P1 🔒 | ST-097, **Q-02** | Modelar com 2 contratos reais |
| **ST-099** | `TabelaPreco` + `ItemTabelaPreco` | 3 | P1 🔒 | ST-097 | Vigência sem sobreposição |
| **ST-100** | `preco_de()` com precedência | 3 | P1 | ST-099 | Tabela do contrato vence a padrão |
| **ST-101** | Admin de cadastro em massa de escopo | 3 | P1 | ST-098 | Habilita a meta K-REV-01 ≥80% |
| **ST-102** | `ConsumoMaterialOS` com custo congelado | 3 | P1 🔒 | — | Preenche a lacuna L2 |
| **ST-103** | API de registro de consumo | 2 | P1 | ST-102 | App nativo, com idempotência |
| **ST-104** | `FeedbackIA` — explícito e implícito | 5 | P0 🔒 | — | **Métrica não é retroativa** |
| **ST-105** | `ConsumoIA` + `TetoIA` + degradação | 5 | P0 🔒 | — | Risco financeiro aberto **hoje** |
| **ST-106** | Painel de consumo de IA | 3 | P1 | ST-105 | Alerta em 70% e 90% |
| **ST-107** | SSO ligado ao Workspace | 2 | P0 | ST-037 | Reuso do SSO existente |

> **`ST-098` está bloqueada por `Q-02`** — quais dois contratos reais serão usados para modelar. É a única dependência externa do V1.0 que ainda não tem resposta.

---

## 7.10 Consolidado de estimativas

| Onda | Stories | Pontos | Frente |
|---|:-:|:-:|---|
| 0 · Preparação | 6 | 17 | única |
| 1 · Fundação | 19 | 70 | A(40) ∥ B(30) |
| 2 · Motores | 18 | 74 | A(44) ∥ B(30) |
| 3 · Conteúdo e Home | 18 | 71 | A(42) ∥ B(29) |
| 4 · Serviços e widgets | 10 | 37 | única |
| 5 · Busca, Pessoas, Escala | 17 | 61 | única |
| 6 · Fechamento e piloto | 8 | 40 | única |
| B0 · Independente | 11 | 34 | encaixe |
| **Total** | **107** | **404** | |

### Por prioridade

```
P0   ████████████████████████████████████  312 pts   77%
P1   ████████████                           81 pts   20%
P2   ██                                     11 pts    3%
```

### Por módulo

| Módulo | Pts | | Módulo | Pts |
|---|:-:|---|---|:-:|
| IDN | 61 | | SRC | 24 |
| WKS | 56 | | PLT | 39 |
| APR | 44 | | REV | 14 |
| CNT + COM | 42 | | FIN | 5 |
| PPL + OPS | 42 | | AIC | 13 |
| SVC | 24 | | Fechamento | 40 |

---

## 7.11 Caminho crítico e plano de ondas

### Caminho crítico

```
ST-002 → ST-007 → ST-009 → ST-012 → ST-014 → ST-038 → ST-041 → ST-056
  2       3        5        5        8        3        8        5      = 39 pts
                                       │
                                       └─▶ ST-031 → ST-032 → ST-033 → ST-036 → ST-059
                                            5        5        5        5        8   = 28 pts
```

**Caminho crítico: 67 pontos.** É o mínimo teórico do projeto: nem com infinitas pessoas ele encolhe, porque cada elo depende do anterior.

### Ondas e paralelismo

```
Onda 0  ████ 17           única frente
Onda 1  A ████████ 40  ∥  B ██████ 30
Onda 2  A █████████ 44 ∥  B ██████ 30
Onda 3  A ████████ 42  ∥  B ██████ 29
Onda 4  ███████ 37          convergência
Onda 5  ████████████ 61     única frente ← gargalo
Onda 6  ████████ 40         única frente
B0      ██████ 34           encaixe em qualquer folga
```

**A Onda 5 é o gargalo estrutural.** Busca, Pessoas e Escala não paralelizam bem entre si — Escala depende de Pessoas, que depende de Identidade. Com duas pessoas, é onde uma fica ociosa; é exatamente onde a trilha B0 deve ser consumida.

---

## 7.12 Cenários de capacidade — a conversa difícil

### A correção que preciso fazer

O [Blueprint](BLUEPRINT_ICONNECT_WORKSPACE.md) estimou *"Fase 0: 4–6 semanas · MVP: 10–12 semanas"* — 14 a 18 semanas. **Aquele número foi produzido antes da auditoria de baseline**, que revelou 9 lacunas de dados, e antes de os módulos estarem especificados.

Com o escopo especificado em 107 stories: **404 pontos.**

### Conversão

Premissa: **9 pontos por semana por pessoa** de trabalho de feature.

| Cenário | Duração | Observação |
|---|:-:|---|
| **1 pessoa** | **45 semanas** ≈ 10 meses | Sem paralelismo; as duas frentes viram fila |
| **2 pessoas** | **~24 semanas** ≈ 5,5 meses | O paralelismo funciona nas Ondas 1–3; a Onda 5 é gargalo |
| **3 pessoas** | **~19 semanas** ≈ 4,5 meses | A terceira pessoa consome B0 e a Onda 5; retorno decrescente |

> **Com 2 pessoas o número real é ~24 semanas, não 14–18.** A diferença não é pessimismo — é o custo de ter especificado o que antes era intenção. Prefiro entregar o número certo agora do que o número confortável e explicá-lo depois.

### Se 18 semanas for restrição inegociável

Com 2 pessoas, 18 semanas comportam ~324 pontos. É preciso cortar **80 pontos**. Na ordem em que eu cortaria:

| # | Corte | Pts | O que se perde |
|:-:|---|:-:|---|
| 1 | Todos os P2 (ST-025, ST-068, e afins) | 11 | Nada relevante |
| 2 | `ST-061` bandeja completa | 5 | O widget resolve; a bandeja fica no V1.1 |
| 3 | `ST-054` relatório de confirmação | 3 | **Perde-se o KPI de auditoria (M5)** — corte doloroso |
| 4 | `ST-055` + `ST-088` APIs do app nativo | 5 | Técnico sem comunicado e sem escala no celular |
| 5 | `ST-049` estado `dispensada` | 2 | O relatório de conformidade não fecha |
| 6 | `ST-071` Acesso rápido | 5 | **Recuso.** Sem ele o Workspace vira ilha (`RM-WKS-03`) |
| 7 | `ST-072`…`ST-078` **busca inteira** | 24 | ⌘K some. **Perde-se M6 e o maior efeito de demonstração** |
| 8 | `ST-085`…`ST-088` **escala inteira** | 15 | **Perde-se a âncora 2 de retorno diário** |
| 9 | `ST-094` acessibilidade | 5 | Dívida que volta mais cara |

**Os cortes 1–5 somam 26 pontos.** Para chegar a 80, é preciso sacrificar busca (7) ou escala (8) — e as duas são âncoras do produto.

> **Minha recomendação:** manter o escopo e ajustar o prazo, ou acrescentar a segunda pessoa. Cortar busca ou escala entrega um Workspace que cumpre a promessa pela metade — e um portal que cumpre metade da promessa não é meio adotado, é abandonado.

### O que eu **não** cortaria em nenhum cenário

Os 20 itens marcados 🔒 — 84 pontos de fundação sem tela. São a mitigação de `R-17`, e cortá-los adia o V1.1 inteiro em um release.

---

## 7.13 Itens inegociáveis e ordem de corte

### Os 20 inegociáveis 🔒

| ID | Story | Pts | Por que é inegociável |
|---|---|:-:|---|
| ST-001 | Gate de cobertura | 3 | A Onda 5 altera o dispatch do FSM |
| ST-006 | Linha de base das métricas | 5 | Sem ela, o sucesso é opinião |
| ST-007…009 | Unidade, Departamento, Papel, Pessoa | 11 | Fundação de tudo |
| ST-011 | Vínculo Pessoa↔Técnico | 2 | Escala e certificação dependem |
| ST-012 | AtribuicaoPapel | 5 | Permissão com escopo |
| ST-014 | `pode()` | 8 | Segurança |
| ST-019 | Teste de contraste | 2 | Impede a repetição do defeito |
| ST-027 | Reconciliação sem sobrescrita | 5 | Integridade do dado de pessoa |
| ST-034 | `pendente_configuracao` | 3 | Falha silenciosa em aprovação |
| ST-039 | Feature flag | 3 | **É o mecanismo de rollback** |
| ST-078 | Teste de vazamento | 3 | Segurança da busca |
| ST-079, ST-082, ST-084 | Certificação e bloqueio | 11 | O diferencial do produto |
| ST-089, ST-090 | Métricas e painel | 10 | Sem eles não se sabe se funcionou |
| ST-097…099 | Escopo contratual | 8 | Maturação de dado — atrasa o V1.1 |
| ST-102 | Consumo de material | 3 | Maturação de dado |
| ST-104, ST-105 | Feedback e teto de IA | 10 | Métrica não é retroativa; custo é risco aberto |

### A ordem de corte, escrita antes da pressão

```
1º  P2 (11 pts)
2º  Conveniências de UI:  ST-061, ST-025          (10 pts)
3º  APIs do app nativo:   ST-055, ST-088          ( 5 pts)
4º  Relatórios:           ST-054, ST-049          ( 5 pts)
5º  ─────── daqui em diante, dói de verdade ───────
6º  Acessibilidade:       ST-094                  ( 5 pts)   dívida cara
7º  Busca ou Escala                               (24 ou 15) uma âncora se perde
8º  ═══ NUNCA: os 20 itens 🔒 ═══
```

> **Esta lista existe para ser consultada sob pressão, não para ser escrita sob pressão.** Decisão de corte tomada às pressas, em reunião, escolhe o que é mais fácil de tirar — que quase nunca é o que é menos importante.

---

## Próxima etapa

**Etapa 8 — Roadmap.** Versões 1.0, 1.1, 2.0 e 3.0, com a justificativa de por que cada funcionalidade pertence a cada versão.

**Aguarda aprovação da Etapa 7.**

---

*Etapa 7 de 9 · 107 stories · 404 pontos · caminho crítico de 67 pontos · 20 itens inegociáveis.*
