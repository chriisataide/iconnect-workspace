# Execução · Etapa 2 — Definição do MVP (V1.0)

> **Documento de corte.** Aplica o teste de indispensabilidade sobre os 140 itens do [inventário canônico](EXEC_01_ESCOPO_E_DEPENDENCIAS.md), define o conteúdo exato do V1.0, justifica cada exclusão e estabelece os critérios objetivos de lançamento.
>
> **Agosto/2026** · Etapa 2 de 9 · **Aguarda aprovação antes da Etapa 3**

---

## Sumário

- [2.1 O que estamos lançando, exatamente](#21-o-que-estamos-lançando-exatamente)
- [2.2 O teste de indispensabilidade](#22-o-teste-de-indispensabilidade)
- [2.3 O princípio que organiza o corte](#23-o-princípio-que-organiza-o-corte)
- [2.4 Conteúdo do V1.0 — item a item](#24-conteúdo-do-v10--item-a-item)
- [2.5 Exclusões, com o motivo de cada uma](#25-exclusões-com-o-motivo-de-cada-uma)
- [2.6 O que o V1.0 deliberadamente não faz](#26-o-que-o-v10-deliberadamente-não-faz)
- [2.7 Critérios objetivos de lançamento](#27-critérios-objetivos-de-lançamento)
- [2.8 Métricas de sucesso do V1.0](#28-métricas-de-sucesso-do-v10)
- [2.9 Riscos específicos do corte](#29-riscos-específicos-do-corte)

---

## 2.1 O que estamos lançando, exatamente

Antes de cortar, é preciso ser preciso sobre o objeto. Um MVP mal definido é sempre um MVP inchado.

### O contexto que muda tudo

> **Este não é o MVP de um produto novo. É o MVP de uma camada nova sobre um produto que já roda em produção.**

Isso tem três consequências diretas no corte:

1. **Não precisamos entregar completude.** Os módulos operacionais existem e continuam acessíveis. O Workspace não é obrigado a cobrir tudo — só a ser o melhor lugar para o trabalho do dia.
2. **Não podemos quebrar nada.** Regressão nos módulos existentes é falha de lançamento, não bug de sprint.
3. **Temos usuários reais desde o dia 1.** Não há luxo de "vamos aprender com os primeiros usuários" — eles já dependem do sistema.

### Definição do lançamento

| Dimensão | V1.0 |
|---|---|
| **Onde** | 1 instalação dedicada ([D-01](EXEC_01_ESCOPO_E_DEPENDENCIAS.md)) |
| **Quem** | Piloto controlado: colaboradores administrativos + gestores. **Sem técnico de campo** ([D-05](EXEC_01_ESCOPO_E_DEPENDENCIAS.md)) e sem cliente externo |
| **Presets** | **2** — Colaborador e Gestor |
| **Ativação** | Por feature flag e por papel (`PLT-007`), permitindo rollout gradual e rollback em minutos |
| **Convivência** | Módulos atuais intocados. O Workspace é a nova porta; as portas antigas continuam abertas |

### A promessa que o V1.0 precisa cumprir

> **"Meu dia começa aqui: eu vejo o que precisa de mim, resolvo o que dá para resolver, e encontro o que preciso saber — sem abrir outro sistema."**

Se um item não serve a essa frase, ele não está no V1.0. É esse o critério que aplico abaixo.

---

## 2.2 O teste de indispensabilidade

Cada um dos 140 itens passou por três perguntas. **Basta uma resposta "sim" para entrar.**

| # | Pergunta | O que qualifica |
|:-:|---|---|
| **T1** | **Sem isto, o lançamento é impossível ou irresponsável?** | Fundação técnica, permissão, segurança, obrigação legal, mecanismo de rollout |
| **T2** | **Sem isto, a promessa de §2.1 falha?** | O laço diário: ver → resolver → saber |
| **T3** | **Sem isto, perdemos dado que não pode ser recuperado depois?** | Instrumentação e fundações de dado com prazo de maturação |

**Resultado:** `T1=não · T2=não · T3=não` → **fora do V1.0**, com código de motivo (§2.5).

---

## 2.3 O princípio que organiza o corte

A contagem de itens é uma métrica enganosa. O que custa não é o número de itens — é a **superfície de interface**. Um modelo de dados com admin do Django custa dias; uma tela nova custa semanas.

Por isso o corte separa duas naturezas:

| Natureza | Política de corte | Racional |
|---|---|---|
| **Superfície** — tela, widget, fluxo visível | **Cortar ao osso.** Só o que serve à promessa de §2.1 | É onde está o custo, o QA, o dark mode, o mobile, o treinamento |
| **Fundação** — modelo de dado, regra de backend, instrumentação | **Manter, mesmo sem interface** | **Dado tem prazo de maturação.** Um modelo que entra no V1.0 chega ao V1.1 com seis meses de dado. Se entrar no V1.1, a funcionalidade só existe no V2 |

### O argumento da maturação, com exemplos concretos

| Fundação | Se entrar no V1.0 | Se ficar para o V1.1 |
|---|---|---|
| `REV-001` Escopo do contrato | No V1.1, os contratos já estão tipificados → a bandeja de receita não faturada funciona no dia do lançamento | A bandeja só é útil no V2, depois de meses de cadastro |
| `FIN-003` Material consumido na OS | Custo real da OS calculável no V1.1 com histórico | Custo real só no V2, e sem série histórica |
| `PPL-004` Certificação com validade | O alerta de vencimento tem base cadastrada e já bloqueia despacho | Ninguém cadastra certificação "para depois" |
| `AIC-001` Feedback de IA | Métrica de precisão nasce com histórico | `AIC-004` (autonomia medida) fica a dois releases de distância |

**Nenhuma dessas quatro tem tela no V1.0.** Todas entram. É o melhor investimento do release.

---

## 2.4 Conteúdo do V1.0 — item a item

**58 itens. 22 de fundação (sem interface) e 36 de superfície.**

### PLT — Plataforma · 8 itens

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| PLT-001 | Design System Aurora | T1 | Tokens, grid, densidade, dark via `prefers-color-scheme`, pipeline Tailwind isolado |
| PLT-002 | Componentes | T1 | **Só os que o V1.0 usa** — inventário fechado na Etapa 6, não a biblioteca completa |
| PLT-003 | App `workspace` + `WorkspaceProvider` | T1 | Contrato somente-leitura na v1 |
| PLT-004 | Permissões com escopo | T1 | Substitui a checagem por papel plano |
| PLT-005 | Auditoria de acesso sensível | T1 | **Estender** o `AuditMiddleware` existente a leituras de `Pessoa` e `Aprovacao` |
| PLT-006 | SSO no Workspace | T1 | Ligação do SSO existente à nova casca |
| PLT-007 | Feature flags | T1 | **É o mecanismo de lançamento.** Por instalação e por papel |
| PLT-010 | Gate de cobertura em `fsm`/`km_audit` | T1 | Ratchet no nível atual, **antes** do primeiro PR que toque `fsm` |

### IDN — Identidade · 8 itens · *fundação*

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| IDN-001 | `Pessoa` com origem por campo | T1 | Modelo híbrido de [D-03](EXEC_01_ESCOPO_E_DEPENDENCIAS.md): espelho / próprio / derivado |
| IDN-002 | Unidade, Departamento, Centro de Custo | T1 | Reusa `CentroCusto` existente |
| IDN-003 | Organograma | T1 | Gestor ↔ liderados. Sustenta aprovação e público-alvo |
| IDN-004 | `Papel` + `AtribuicaoPapel` com escopo e vigência | T1 | Caminho crítico |
| IDN-005 | `Delegacao` | T1 | **Seguro contra falha boba:** aprovador de férias travando o piloto |
| IDN-006 | Vínculo `Pessoa` ↔ `Tecnico` ↔ `User` | T1 | Sem isso, escala e certificação não existem |
| IDN-007 | Importação e reconciliação | T1 | Carga inicial + fila de divergências |
| IDN-009 | Política de sincronização e conflito | T1 | Decorre de D-03. Precedência, cadência, conflito |

### WKS — Workspace · 10 itens · *superfície*

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| WKS-001 | AppShell | T2 | Topbar, sidebar, layout, tema |
| WKS-002 | Home 3 zonas | T2 | — |
| WKS-003 | Runtime de widget | T2 | Carga assíncrona por widget, cache próprio, skeleton com altura reservada |
| WKS-004 | Presets | T2 | **2 presets:** Colaborador, Gestor |
| WKS-005 | Widget · Aprovações | T2 | **Âncora 1.** Ação inline e em lote |
| WKS-007 | Widget · **Meu dia** | T2 | Fusão de `WKS-006` + `WKS-007`: minhas solicitações, meus chamados, minhas OS, o que vence hoje |
| WKS-008 | Widget · Escala e plantão | T2 | **Âncora 2.** Somente leitura |
| WKS-009 | Widget · Mural | T2 | **Âncora 3** |
| WKS-010 | Widget · Acesso rápido | T2 | Ponte para os módulos existentes. **Impede que o Workspace vire uma ilha** |
| WKS-012 | Zona 1 · **Faixa de atenção** | T2 | Comunicado obrigatório pendente + itens vencendo hoje. **Sem IA, sem o nome "briefing"** |

### SRC — Busca · 4 itens

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| SRC-001 | `SearchDocument` com `acl_subjects` | T1+T3 | Fundação. ACL como `WHERE` no índice, nunca em pós-processamento |
| SRC-002 | Ingestão | T2 | **Uma única fonte: `Pessoa`.** Prova o mecanismo de ACL num dado de baixo risco |
| SRC-003 | ⌘K — camada local | T2 | Recentes, favoritos, navegação, ações. Client-side, instantâneo |
| SRC-004 | Busca léxica (FTS) | T2 | Simples. Sem RRF, sem boost sofisticado |

### AIC — IA · 2 itens · *instrumentação*

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| AIC-001 | Registro de feedback | T3 | Instrumenta o **copiloto que já está em produção**. Sem isso, `AIC-004` não pode existir depois |
| AIC-002 | Teto de custo | T1 | O copiloto roda hoje **sem teto de custo**. É risco financeiro aberto agora, não no futuro |

### SVC — Serviços · 4 itens

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| SVC-001 | `ItemCatalogo` | T2 | Dono, SLA, política, formulário, cadeia de aprovação |
| SVC-002 | Formulário derivado da identidade | T2 | ≤3 campos livres. O resto vem de `IDN` |
| SVC-003 | Solicitação → ticket | T2 | Reusa o motor de tickets |
| SVC-005 | Catálogo inicial | T2 | **6 itens:** acesso a sistema · equipamento · férias · reembolso · compra de material · facilities |

### APR — Aprovações · 5 itens

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| APR-001 | Motor de aprovação | T2 | Cadeia por valor e tipo |
| APR-002 | Bandeja com ação inline e em lote | T2 | **Âncora 1** |
| APR-003 | Auto-aprovação dentro de política | T2 | O que separa portal rápido de portal burocrático. Custo: uma checagem |
| APR-004 | Delegação de aprovação | T2 | Par de `IDN-005` |
| APR-005 | Devolver com motivo obrigatório | T2 | Sem isso, "reprovado" não ensina nada a ninguém |

### CNT — Conteúdo · 3 itens

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| CNT-001 | `Documento` | T1 | Fundação. Tipo, dono, classificação, público-alvo, vigência. **Base de `COM`** |
| CNT-004 | Biblioteca | T2 | Listar, filtrar, visualizar, publicar. **Sem versionamento, sem fluxo de revisão** |
| CNT-005 | Leitura confirmada | T2 | **Âncora 3.** É o KPI que vale dinheiro em auditoria |

### COM — Comunicação · 4 itens

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| COM-001 | Comunicado com 3 classes | T2 | Informativo · obrigatório · crítico |
| COM-002 | Público-alvo por regra | T2 | Papel, unidade, departamento — vem de `IDN-002` |
| COM-003 | Confirmação + bloqueio no crítico | T2 | **Âncora 3** |
| COM-004 | Relatório de confirmação por gestor | T2 | Sem o relatório, a confirmação não tem consumidor |

### PPL — Pessoas · 5 itens

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| PPL-001 | Meu perfil | T2 | Onde o usuário vê seus dados e **onde a divergência de D-03 aparece** |
| PPL-003 | Ausências | T2 | Sustenta férias no catálogo, delegação e cobertura de escala |
| PPL-004 | `Certificacao` com validade | T3 | **Fundação sem tela.** Modelo + admin |
| PPL-005 | **Certificação vencida bloqueia despacho** | T3 | Regra de backend. Hook no dispatch existente. **É o diferencial mais defensável do produto** |
| PPL-006 | Alerta de vencimento 90/30/15/5 | T2 | Task Celery + notificação. Sem isso `PPL-004` é uma tabela morta |

### OPS — Operação · 1 item

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| OPS-001 | `Escala` | T2+T3 | **Modelo + Django admin + widget de leitura.** O editor completo é V1.1 |

### FIN — Financeiro · 2 itens

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| FIN-002 | Reembolso | T2 | **Custo marginal ~zero:** é um item de catálogo com cadeia de aprovação. Sem OCR |
| FIN-003 | `ConsumoMaterialOS` | T3 | **Fundação sem tela.** Preenche o vazio da lacuna L2 |

### REV — Receita & Contrato · 2 itens · *fundação*

| ID | Item | Teste | Escopo no V1.0 |
|---|---|:-:|---|
| REV-001 | `EscopoContrato` | T3 | **Fundação sem tela.** Bloqueia Q-02 (dois contratos reais para modelar) |
| REV-002 | `TabelaPreco` | T3 | Par de `REV-001` |

---

### Resumo do corte

```
Inventário total                     140 itens
Proposto como V1 na Etapa 1           68 itens
─────────────────────────────────────────────
V1.0 FINAL                            58 itens
   ├── fundação sem interface         22
   └── superfície                     36

Cortados da proposta da Etapa 1       10 itens
Fundidos                               1 (WKS-006 → WKS-007)
```

**A redução real não está no número de itens — está no escopo dentro deles.** Presets de 4 → 2. Catálogo de 8 → 6 itens. Fontes de busca de 5 → 1. Biblioteca sem versionamento. Escala sem editor. Componentes só os usados. É aí que estão os meses economizados.

---

## 2.5 Exclusões, com o motivo de cada uma

### Códigos de motivo

| Código | Motivo |
|---|---|
| **E1** | Depende de item que não está no V1.0 |
| **E2** | Existe caminho alternativo aceitável (módulo atual ou Django admin) |
| **E3** | Valor só aparece com dado ou uso acumulado |
| **E4** | Risco jurídico, LGPD ou financeiro desproporcional ao valor no V1.0 |
| **E5** | Não é indispensável à promessa de §2.1 |
| **E6** | Custo alto com valor concentrado em poucos usuários |

### Cortados da proposta original da Etapa 1

| ID | Item | Motivo | Destino | Justificativa |
|---|---|:-:|:-:|---|
| PLT-008 | Configurações admin do Workspace | **E2** | V1.1 | O admin do Django atende o piloto |
| PLT-009 | `threading.local()` → `contextvars` | **E5** | V1.1 | **[D-01] rebaixou este risco.** Com uma instalação por cliente, vazamento de contexto de tenant não tem consequência entre clientes. Continua sendo correção devida, deixa de ser bloqueio |
| IDN-008 | Diretório e perfil público | **E5** | V1.1 | `PPL-001` cobre o próprio perfil; o de terceiros não serve à promessa |
| WKS-006 | Widget Agenda / Próximas reuniões | **E1** | — | **Fundido em `WKS-007`.** "Reuniões" exigiria integração com M365/Google, que é não-objetivo declarado. Sem calendário, o widget seria uma lista de OS — que já é `WKS-007` |
| WKS-011 | Central de notificações | **E5** | V1.1 | Notificação acionável aparece dentro dos widgets. Central separada é conveniência |
| WKS-013 | Preferências (tema, densidade) | **E5** | V1.1 | Mitigado: dark mode respeita `prefers-color-scheme` sem preferência persistida |
| SVC-004 | Acompanhamento com timeline | **E2** | V1.1 | O status aparece em `WKS-007`, com link para a tela de ticket existente |
| CNT-002 | Versionamento com diff | **E3** | V1.1 | Sem histórico de conteúdo, não há o que versionar no dia 1 |
| CNT-003 | Fluxo de revisão e aprovação | **E2** | V1.1 | No V1.0, publica quem tem o papel. Fluxo formal quando houver volume |
| CNT-006 | Migração de `ArtigoConhecimento` | **E5** | V1.1 | O KB atual continua funcionando onde está. Migrar cedo é risco sem retorno |
| PPL-002 | Documentos pessoais com validade | **E4** | V1.1 | **ASO é dado de saúde (LGPD art. 11).** Exige política de retenção e classificação definidas (`A-03`, `R-12`) antes do primeiro upload. Não vale o risco no piloto |
| OPS-002 | Risco de SLA preditivo | **E5** | V1.1 | O `sla_monitor` existente continua alertando. Trazer para o Workspace é melhoria, não pré-requisito |
| OPS-003 | Pacote do dia offline | **E1** | V1.1 | **[D-05]** transformou em contrato de API para o app nativo. Sai do escopo de interface do Workspace |

### Confirmação dos cortes já decididos nas etapas anteriores

Permanecem fora, sem reabertura: os 17 itens da lista de execução da [Revisão CPO §B](CPO_REVIEW_ICONNECT.md) e os não-objetivos da [Etapa 1 §1.8](EXEC_01_ESCOPO_E_DEPENDENCIAS.md). Em especial, e por serem os mais pedidos de volta:

| Item | Motivo | Resposta pronta |
|---|:-:|---|
| Personalização de widget por arrastar | E5 | "Os presets entregam 95% do valor. Reordenar entra no V1.1" |
| Feed social, curtidas, comentários | — | Não-objetivo. Decisão de produto, não de prazo |
| LMS (autoria, SCORM, prova, gamificação) | — | Não-objetivo. Integramos |
| Holerite, ponto, banco de horas | — | Não-objetivo. Exibimos, não calculamos |
| Briefing gerado por IA | E1 | V1.1. `WKS-012` entrega a faixa sem IA |
| Busca semântica e resposta de IA | E1+E3 | V1.1. Depende de conteúdo publicado (`R-04`) |
| Agentes (receita, SLA, conhecimento) | E1 | V1.1/V2. As fundações de dado entram agora |

---

## 2.6 O que o V1.0 deliberadamente não faz

Escrito para ser dito em voz alta, sem defensiva, quando alguém perguntar.

| Alguém vai perguntar | A resposta |
|---|---|
| *"Cadê a IA?"* | Ela já está no sistema — o copiloto roda em produção. O V1.0 coloca **teto de custo e medição** nela, que é o que faltava. A IA no Workspace entra no V1.1, depois que houver conteúdo para ela responder |
| *"O técnico não usa?"* | Não no V1.0 — por decisão [D-05]. O técnico usa o app nativo. O Workspace expõe a API que o app consome |
| *"A busca só acha pessoas?"* | Sim, no V1.0. O mecanismo de índice e de permissão é o difícil, e ele está pronto. Adicionar fontes no V1.1 é incremental |
| *"Não dá para personalizar a home?"* | Dá para escolher o preset. Reordenar entra no V1.1, se a medição mostrar que alguém quer |
| *"A biblioteca não tem versionamento?"* | Não no dia 1 — não há histórico para versionar. Entra no V1.1, junto com o fluxo de revisão |
| *"Onde está o RH completo?"* | O Workspace não é um HRIS. Ele tem perfil, ausências e certificação, porque essas três se ligam à operação |
| *"Por que existe `EscopoContrato` se não tem tela?"* | Porque o dado precisa de meses de maturação. Cadastrando agora, a bandeja de receita não faturada funciona no dia do V1.1. Cadastrando depois, ela só funciona no V2 |

---

## 2.7 Critérios objetivos de lançamento

O V1.0 só é lançado quando **todos** os critérios estiverem verdes. Sem exceção negociada em reunião.

### Funcional

| # | Critério |
|:-:|---|
| F1 | Os 58 itens de §2.4 entregues no escopo ali declarado |
| F2 | Os 2 presets funcionam de ponta a ponta para um usuário real de cada tipo |
| F3 | As 3 âncoras funcionam: aprovar sem sair da home · ver a escala da semana · confirmar leitura de comunicado obrigatório |
| F4 | Os 6 itens do catálogo geram ticket no módulo correto, com aprovação encaminhada ao aprovador certo |
| F5 | Um técnico com certificação vencida **não** é despachado, e o motivo aparece para quem despacha |
| F6 | Todo módulo existente continua acessível a partir de `WKS-010` |

### Qualidade

| # | Critério |
|:-:|---|
| Q1 | Gate de cobertura ativo em `dashboard`, `fsm` e `km_audit` — nenhum abaixo do nível de entrada |
| Q2 | Cobertura do app `workspace` ≥ 75% (código novo, sem dívida herdada) |
| Q3 | Teste de isolamento de permissão por papel para **todo** endpoint novo |
| Q4 | Zero regressão nos testes existentes de `dashboard`, `fsm` e `km_audit` |
| Q5 | Nenhuma classe Tailwind fora de `workspace/` — regra de CI ativa (`A-02`) |

### Desempenho

| # | Critério | Alvo |
|:-:|---|---|
| P1 | Zona 1 da home renderizada | ≤ 800 ms (p95) |
| P2 | Cada widget da zona 2 | ≤ 1,5 s (p95), carregado de forma independente |
| P3 | ⌘K — primeiro resultado local | ≤ 120 ms |
| P4 | ⌘K — resultado federado | ≤ 600 ms (p95) |
| P5 | Nenhum salto de layout após a carga | altura reservada obrigatória |

### Segurança e conformidade

| # | Critério |
|:-:|---|
| S1 | ACL da busca aplicada como filtro no índice, com teste que prova ausência de vazamento em contagem e em trecho |
| S2 | Auditoria registrando leitura de `Pessoa` e de `Aprovacao` |
| S3 | Teto de custo de IA ativo, com alerta antes do limite |
| S4 | Nenhum dado sensível de saúde no V1.0 — `PPL-002` fora, conforme E4 |
| S5 | Revisão de segurança das rotas novas concluída |

### Operação

| # | Critério |
|:-:|---|
| O1 | Feature flag permite ligar e desligar o Workspace por papel, com rollback em ≤ 5 min |
| O2 | `IDN-007` importou e reconciliou a base real de pessoas, com fila de divergências zerada |
| O3 | Runbook de rollback escrito e testado em homologação |
| O4 | `A-01` concluída — material comercial corrigido |
| O5 | `A-03` concluída — precedência de sincronização com o RH definida |
| O6 | `Q-01` e `Q-02` respondidas |

---

## 2.8 Métricas de sucesso do V1.0

Medidas a partir do lançamento no piloto. Instrumentação faz parte do escopo, não é tarefa posterior.

| # | Métrica | Meta | Prazo | Por que esta |
|:-:|---|:-:|:-:|---|
| M1 | **Retorno diário** — DAU/MAU no piloto | ≥ 0,5 | 60 dias | Abaixo disso o portal está morrendo. É a métrica que decide se continuamos |
| M2 | **Aprovações concluídas na home**, sem abrir outra tela | ≥ 70% | 30 dias | Prova que o widget resolve, não só informa |
| M3 | **Tempo médio de aprovação** vs. linha de base atual | −40% | 60 dias | O ganho mais visível para a gestão |
| M4 | **Solicitações nascidas no catálogo** vs. e-mail/WhatsApp | ≥ 40% | 60 dias | Prova que substituiu o canal informal |
| M5 | **Leitura confirmada de comunicado obrigatório** em 72 h | ≥ 90% | por comunicado | O KPI que vale dinheiro em auditoria |
| M6 | **Uso do ⌘K** — sessões que o acionam | ≥ 30% | 30 dias | Valida a aposta de que a navegação é a busca |
| M7 | **Despachos bloqueados por certificação vencida** | > 0 | 90 dias | Prova que o diferencial funciona em operação real |
| M8 | **Contratos com escopo tipificado** | ≥ 80% da carteira | 90 dias | Habilita o V1.1. É a métrica de maturação de dado |
| M9 | **Regressões em produção** atribuídas ao Workspace | 0 críticas | contínuo | Não quebrar o que existe é critério de lançamento |

### Linha de base a medir **antes** do lançamento

Sem estes números, M3 e M4 são inverificáveis. Coletar durante o desenvolvimento:

- Tempo médio atual entre solicitação e aprovação (amostra de 30 casos)
- Proporção atual de solicitações internas por e-mail e WhatsApp
- Taxa atual de leitura de comunicado (provavelmente não medida — assumir 0 e documentar)

---

## 2.9 Riscos específicos do corte

Riscos que **este corte** cria ou agrava, além dos 16 do registro da Etapa 1.

| ID | Risco | P | I | Exp | Mitigação |
|---|---|:-:|:-:|:-:|---|
| **R-17** | **Fundação sem tela é a primeira coisa a ser cortada sob pressão de prazo** — `REV-001`, `FIN-003`, `PPL-004`, `AIC-001` não aparecem na demo e viram candidatos naturais ao corte | 4 | 5 | **20** | Marcar como **inegociáveis** no backlog (Etapa 7). Justificativa de maturação escrita no card. Se o prazo apertar, cortar superfície — nunca fundação |
| **R-18** | **V1.0 parece pobre demais para justificar o esforço** — nenhuma IA visível, busca só de pessoas, biblioteca sem versionamento | 3 | 4 | **12** | Comunicar a promessa de §2.1, não a lista de features. As 3 âncoras são o que se demonstra |
| **R-19** | **Catálogo de 6 itens sem dono real** — item de catálogo sem responsável nomeado vira chamado órfão | 4 | 3 | **12** | Cada um dos 6 tem dono nomeado **antes** de entrar no catálogo. Item sem dono não é publicado |
| **R-20** | **`IDN-007` encontra base de pessoas suja** — a reconciliação de D-03 revela divergências em volume inesperado | 4 | 3 | **12** | Rodar a importação em homologação com a base real **na semana 2**, não na véspera. Critério O2 |
| **R-21** | **Escala em Django admin é ruim demais para uso real** — sem editor, o gestor pode não conseguir manter a escala | 3 | 4 | **12** | Validar com um gestor real na semana 6. Se reprovar, o editor sobe para o V1.0 e algo de superfície desce |

---

## Próxima etapa

**Etapa 3 — Divisão em módulos.** Para cada um dos 13 domínios: objetivo, escopo, regras, fluxos, dependências, APIs, permissões, banco de dados, componentes e critérios de aceite.

**Aguarda aprovação da Etapa 2.**

---

*Etapa 2 de 9 · O conteúdo do V1.0 está fechado aqui. Alteração exige revisar este documento primeiro.*
