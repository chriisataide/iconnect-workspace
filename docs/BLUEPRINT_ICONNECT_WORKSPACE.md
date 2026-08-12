# iConnect Workspace — Blueprint de Produto

> **O que é este documento:** o desenho completo da camada que antecede os módulos operacionais do iConnect — arquitetura, jornadas, navegação, design system, roadmap e riscos.
>
> **Data:** Agosto/2026 · **Status:** proposta para decisão · **Base analisada:** branch `feature/chris`
>
> ⚠️ **Revisado em 12/08/2026 pela [Etapa 10 — Reposicionamento](EXEC_10_REPOSICIONAMENTO.md).** O produto se chama **iConnect Workspace**, e Workspace e Platform são dois produtos — não uma camada sobre o outro. Onde este documento contradiz a Etapa 10, a Etapa 10 vence; §10.7 nomeia cada contradição. Nada aqui foi descartado.

---

## Sumário

1. [Análise crítica do conceito atual](#1-análise-crítica-do-conceito-atual)
2. [Oportunidades de melhoria](#2-oportunidades-de-melhoria)
3. [Arquitetura da plataforma](#3-arquitetura-da-plataforma)
4. [Jornada completa do usuário](#4-jornada-completa-do-usuário)
5. [Mapa de navegação](#5-mapa-de-navegação)
6. [Estrutura da Home](#6-estrutura-da-home)
7. [Estrutura de cada módulo](#7-estrutura-de-cada-módulo)
8. [Design System — "Aurora"](#8-design-system--aurora)
9. [Fluxos principais](#9-fluxos-principais)
10. [Roadmap MVP → V2 → V3](#10-roadmap-mvp--v2--v3)
11. [Funcionalidades inovadoras](#11-funcionalidades-inovadoras)
12. [Riscos e pontos de atenção](#12-riscos-e-pontos-de-atenção)
13. [Monetização e diferenciais competitivos](#13-monetização-e-diferenciais-competitivos)
14. [Recomendações finais](#14-recomendações-finais)

---

## Ponto de partida — o que já existe (fatos, não suposições)

Antes de propor, o que o código mostra hoje:

| Ativo | Estado real | Implicação para o Workspace |
|---|---|---|
| **Copiloto com tool-use** (`dashboard/services/copilot/`) | Engine Anthropic com registry de tools, `PermissionGate` por papel, mascaramento de PII no egress, confirmação obrigatória em ações de escrita e auditoria | **É o maior ativo do projeto.** A IA do Workspace deve ser este motor com mais tools — não um segundo assistente |
| **RAG + busca semântica** (`rag.py`, `knowledge_search.py`, `embeddings.py`) | Funciona, mas indexa **apenas** `ArtigoConhecimento` (KB de helpdesk) | A "pesquisa global" exige um índice unificado novo. O padrão de recuperação já está provado |
| **RBAC** (`utils/rbac.py`) | **6 papéis:** `admin`, `gerente`, `analista`, `tecnico_campo`, `sala_monitoramento`, `cliente`. `ROLE_FINANCEIRO` é apenas um alias de `gerente` | **Bloqueador nº 1.** As personas do Workspace (RH, Jurídico, Compras, Facilities, Diretoria) **não existem** no modelo de identidade |
| **Multi-tenancy** (`tenants.py`) | Row-level + middleware + `threading.local()` | Aceitável para tickets. **Insuficiente** quando o portal carregar holerite e PDI |
| **Design System** (`static/css/iconnect-design-system.css`) | Tokens `--ic-*` reais, paleta Slate `#334155` + Cyan `#06b6d4`, ~450 linhas | Base boa de *cor*. Mas a casca é Material Dashboard 2 + Bootstrap 5 |
| **Front-end** | Django templates server-rendered, Bootstrap, sem build de componentes | Tensão central: não se entrega sensação de "produto internacional" sobre Material Dashboard 2 |
| **Módulos existentes** | Helpdesk, FSM, Financeiro, Estoque, Equipamentos/Ativos, WhatsApp, KM Audit, Cálculo Vigilante, Portal do Cliente | Base operacional forte |
| **RH, LMS, Feed, Catálogo de Serviços, Biblioteca** | **Não existem.** Zero linha de código | 5 produtos novos, não 5 telas novas |

---

## 1. Análise crítica do conceito atual

### 1.1 O que está certo — e vale defender

**A tese central é correta e é a coisa mais valiosa do documento original.** "O usuário resolve sem abrir o sistema principal" é a definição certa de sucesso para uma camada de portal. A maioria dos portais corporativos falha exatamente por medir cliques em vez de resoluções.

**O timing também está certo.** O Copiloto com tool-use e permissão já existe e funciona. Portais corporativos que estão sendo construídos hoje com IA colada por cima vão passar 2 anos refazendo o que aqui já está feito.

### 1.2 Onde eu discordo — e por quê

#### Discordância nº 1 — Não é um produto. São cinco.

O escopo descrito contém, na prática:

1. Um **portal/workspace** (Microsoft 365, Atlassian Home)
2. Um **ESM / catálogo de serviços** (ServiceNow Employee Center)
3. Um **HRIS self-service** (Workday, Gupy, Senior)
4. Um **LMS corporativo** (Docebo, 360Learning)
5. Uma **rede social interna** (Workplace, Viva Engage)

Cada um é uma categoria com incumbentes de bilhões de dólares e 10+ anos de roadmap. Construir os cinco em paralelo entrega cinco produtos medianos — e um portal mediano é pior que nenhum portal, porque queima a confiança do usuário na primeira semana e ele volta para o WhatsApp e a planilha.

> **Recomendação:** escolher **uma** tese defensável e usar as outras quatro como superfície fina (integração ou MVP deliberadamente raso). A tese defensável está no item seguinte.

#### Discordância nº 2 — O posicionamento "Intranet premium" é o posicionamento perdedor

Comparar-se com Microsoft 365 e Google Workspace é escolher a briga que não dá para vencer: eles têm e-mail, arquivos, vídeo, identidade e distribuição gratuita embutida. Nenhum portal novo ganha nesse eixo.

Mas há um eixo onde **eles não competem**: o iConnect já possui a **operação** — ordens de serviço, escala de técnicos, SLA em curso, equipamentos em campo, custo por centro de custo. Nenhum Employee Center do mundo sabe que o técnico Marcos está a 12 km do cliente com uma OS crítica vencendo em 40 minutos.

> **Posicionamento recomendado:** ~~"O Workspace da empresa que opera em campo."~~
> **REVISADO §10.3 → "O Workspace corporativo de quem não trabalha sentado."** O eixo
> do vertical continua; o Workspace **conhece** a operação em vez de **fazê-la**.
> Original preservado abaixo:
>
> **"O Workspace da empresa que opera em campo."** Não é uma intranet com módulo de operação; é a operação com uma camada de trabalho humano em volta. Isso é indefensável para a Microsoft copiar e é exatamente o gap do ServiceNow no mercado brasileiro médio.

#### Discordância nº 3 — "Cada colaborador tem uma Home diferente" é um erro caro

Homes totalmente personalizadas destroem quatro coisas ao mesmo tempo:

- **Modelo mental compartilhado** — ninguém consegue dizer "está no card do canto superior direito"
- **Suporte e treinamento** — cada chamado vira uma investigação sobre o layout daquele usuário
- **QA** — a superfície de teste explode combinatoriamente
- **Comunicação institucional** — o comunicado obrigatório fica embaixo do widget que o usuário arrastou pra baixo

> **Recomendação:** **um layout, seis presets, personalização limitada.** Grid fixo com três zonas de papel definido. O usuário reordena e liga/desliga widgets **dentro** de cada zona, mas a zona 1 (comunicação institucional + IA) é imutável. Isso entrega 90% do valor percebido de personalização com 10% do custo.

#### Discordância nº 4 — Dez "GPTs especializados" é um anti-padrão de UX

Pedir ao usuário que escolha entre RH GPT, Finance GPT e TI GPT transfere para ele um problema de roteamento que é responsabilidade do sistema. O usuário não sabe se "meu notebook quebrou e preciso de um reembolso da tela" é TI ou Financeiro — e se ele escolher errado, recebe uma resposta ruim e conclui que "a IA não funciona".

Microsoft e ServiceNow ambos recuaram desse padrão entre 2024 e 2026, exatamente por isso.

> **Recomendação:** **um assistente, roteamento invisível.** O que você chama de "RH GPT" deve existir como um **skill pack** no backend — conjunto de tools + fontes + prompt de domínio — selecionado automaticamente pelo roteador. A persona pode aparecer *depois* da resposta ("Respondido com a base de RH · 3 fontes"), como transparência, nunca *antes*, como pergunta.
>
> **Exceção legítima:** assistentes especializados **escolhidos explicitamente** fazem sentido quando o usuário está num contexto de trabalho prolongado e profundo — um analista jurídico revisando contratos a manhã inteira. Isso é uma **sessão de trabalho**, não um seletor na home.

#### Discordância nº 5 — Não construa o LMS. Construa a parte que ninguém constrói.

Um LMS completo (autoria, SCORM, vídeo, avaliação, certificação, gamificação, ranking) é 8–12 meses de time dedicado, e o resultado será pior que um Docebo de prateleira.

Mas existe uma fatia pequena e brutalmente valiosa que **nenhum LMS do mercado faz**, porque nenhum LMS conhece a operação:

> **Competência que vence bloqueia a escala.** Se a NR-10 do técnico vence em 15 dias, o sistema avisa, agenda a reciclagem, e — se vencer — **remove automaticamente esse técnico da fila de despacho de OS em painel elétrico**.

Isso liga LMS ↔ FSM ↔ Compliance. É defensável, é vendável, e cabe em 6 semanas em vez de 12 meses.

#### Discordância nº 6 — O Feed estilo LinkedIn tem morte anunciada

Feeds sociais corporativos seguem uma curva previsível: pico de engajamento em 3 semanas, queda em 3 meses, cemitério de aniversários no mês 6. Em empresas com menos de ~500 pessoas, o WhatsApp já venceu essa batalha e não há como reverter.

> **Recomendação:** trocar "Feed social" por **"Mural"** — comunicação institucional com garantia de leitura. Reações sim (custo zero, sinal útil); comentários apenas onde a discussão agrega; **zero métricas de vaisdade** (contagem de curtidas no perfil, ranking de posts). O KPI do Mural não é engajamento, é **taxa de leitura confirmada de comunicados obrigatórios** — que é um requisito real de ISO e de compliance trabalhista, e que vale dinheiro.

#### Discordância nº 7 — A IA não pode ser a primeira coisa a construir

"Como solicito férias?" só tem resposta se existir um documento dizendo como solicitar férias. Hoje o RAG indexa exclusivamente `ArtigoConhecimento` do helpdesk. Um assistente corporativo lançado sobre uma biblioteca vazia produz exatamente uma impressão: *"a IA daqui não sabe nada."* E essa impressão é praticamente irreversível.

> **Ordem correta de construção:** modelo de conteúdo → ingestão e índice → busca → **depois** IA generativa por cima. A IA é a camada mais fina e a última.
>
> **Mitigação inteligente:** ver [§11.9 — Captura passiva de conhecimento](#119-captura-passiva-de-conhecimento-o-conteúdo-se-escreve-sozinho), que resolve o problema do conteúdo vazio usando a operação que já roda.

#### Discordância nº 8 — A casca visual atual não sustenta a ambição

O objetivo declarado — *"parece uma plataforma internacional"* — não é alcançável estendendo Material Dashboard 2 + Bootstrap 5. Essa base carrega decisões visuais de 2019 (sombras pesadas, cards com raio grande, gradientes saturados, densidade baixa) que são justamente o que faz um produto "parecer brasileiro de 2019".

> **Recomendação:** o Workspace é uma **ilha** — app Django novo (`workspace`), casca visual nova (`Aurora`, §8), **sem herdar** o CSS do Material Dashboard. Os ~40 telas operacionais existentes **não são reescritas**: elas continuam vivas e são acessadas a partir do Workspace. Migração por atração, não por big bang.

### 1.3 Veredito

| Componente da visão | Veredito | Ação |
|---|---|---|
| Workspace como porta de entrada única | ✅ Correto | Construir |
| IA no centro | ✅ Correto, mas na ordem errada | Construir **depois** do conteúdo |
| Home por perfil | ⚠️ Certo no espírito, errado na implementação | Presets, não homes únicas |
| Pesquisa global tipo Spotlight | ✅ Maior alavanca de percepção de qualidade | Construir cedo |
| Catálogo de serviços | ✅ Correto e subestimado | Construir no MVP |
| 10 GPTs especializados | ❌ Anti-padrão de UX | Skill packs invisíveis |
| LMS completo | ❌ Escopo inviável | Fatia compliance+operação |
| Feed social | ⚠️ Morre em 90 dias | Vira Mural com leitura confirmada |
| RH completo (20 funcionalidades) | ❌ É um HRIS | Integrar + 4 telas próprias |
| Design premium sobre a base atual | ❌ Não alcançável | Casca nova isolada |

---

## 2. Oportunidades de melhoria

### 2.1 Da "porta de entrada" para o "fim do dia"

A visão original descreve o Workspace como **início** do dia. A oportunidade maior é fechá-lo como **fim** do dia: o registro do que foi feito, o que ficou pendente e o que amanhã exige. O ritual de saída gera muito mais retenção do que o de entrada — e produz o dado mais valioso da plataforma (o que realmente ocupa o tempo das pessoas).

### 2.2 De "portal de funcionário" para "portal de todos os públicos"

O iConnect já tem `ROLE_CLIENTE` e um Portal do Cliente parcial. A mesma engine de Workspace deve servir **quatro audiências** com a mesma casca e presets diferentes:

- **Colaborador** (interno)
- **Cliente** (B2B — vê SLA, OS, contrato, faturas)
- **Parceiro / Terceiro** (técnico de empresa parceira, vê só sua escala)
- **Fornecedor** (pedidos, notas, pagamentos)

Isso multiplica o alcance sem multiplicar o código — e o Portal do Cliente vira **produto vendável white-label** (§13).

### 2.3 Do "widget que informa" para o "widget que resolve"

Widget que mostra "12 aprovações pendentes" e leva a outra tela é um link disfarçado. Todo widget do Workspace deve responder à pergunta *"o que posso concluir sem sair daqui?"*. Aprovar, comentar, reagendar, delegar, anexar — tudo inline. Essa é a diferença entre "portal de links" (o que você não quer) e workspace real.

### 2.4 Da busca por palavra para a busca por intenção

Um Spotlight que só encontra objetos é uma feature. Um Spotlight que aceita *"OS atrasadas do Marcos essa semana"*, *"contrato da Vivo"*, *"quem aprova compra acima de 5 mil"* e *"férias"* — misturando objeto, ação e conhecimento no mesmo campo — é o produto. A infra de embeddings já existe para isso.

### 2.5 Do dado apresentado para o dado explicado

Todo KPI no Workspace deve ter um affordance de **"explique"**: a IA lê a série, compara períodos, encontra o driver e escreve duas frases. Custa pouco (a engine já existe), e transforma o BI de "número que ninguém entende" em "insight que gera ação". É o recurso que mais impressiona em demonstração.

### 2.6 Da comunicação empurrada para a comunicação com contrato

Comunicado corporativo hoje é e-mail sem retorno. No Workspace, comunicado tem **classe**: informativo, obrigatório (exige confirmação de leitura), ou crítico (bloqueia a navegação até o aceite). A classe "obrigatório" com trilha auditável é diretamente requisito de ISO 9001/27001 e de defesa trabalhista — vale dinheiro real.

### 2.7 Da identidade rasa para a identidade organizacional

O `UserRole` atual não tem cargo, gestor, departamento, centro de custo, unidade nem matrícula. Sem isso não existe home por perfil, não existe fluxo de aprovação, não existe organograma, não existe delegação de férias, não existe segurança de documento por departamento. **Este é o pré-requisito de tudo** e é a primeira coisa a construir.

---

## 3. Arquitetura da plataforma

### 3.1 Princípio arquitetural

> O Workspace **não** é dono de dado de domínio. Ele é dono de **contexto, agregação e apresentação**.

Cada dado continua vivendo no seu módulo. O Workspace lê via camada de contrato e escreve via serviços existentes. Isso evita a armadilha clássica: o portal virar um segundo lugar onde o dado mora e diverge.

### 3.2 Camadas

```
┌──────────────────────────────────────────────────────────────────────┐
│  EXPERIÊNCIA — Aurora Shell                                           │
│  Workspace · Command Bar (⌘K) · Assistente · Notificações · Presets   │
└──────────────────────────────────────────────────────────────────────┘
                                  ▲
┌──────────────────────────────────────────────────────────────────────┐
│  ORQUESTRAÇÃO                                                         │
│  ┌────────────┐ ┌───────────┐ ┌────────────┐ ┌──────────────────┐   │
│  │ Widget     │ │ Intent    │ │ Search     │ │ Notification     │   │
│  │ Runtime    │ │ Router    │ │ Federator  │ │ Hub              │   │
│  └────────────┘ └───────────┘ └────────────┘ └──────────────────┘   │
│  ┌────────────┐ ┌───────────┐ ┌────────────┐ ┌──────────────────┐   │
│  │ Approval   │ │ Request   │ │ Content    │ │ Personalização   │   │
│  │ Engine     │ │ Engine    │ │ Hub        │ │ (presets)        │   │
│  └────────────┘ └───────────┘ └────────────┘ └──────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                                  ▲
┌──────────────────────────────────────────────────────────────────────┐
│  INTELIGÊNCIA                                                         │
│  Copilot Engine (existente) · Skill Packs · Índice Unificado          │
│  (pgvector) · Trust Layer (PII mask, gate, confirm, audit)            │
└──────────────────────────────────────────────────────────────────────┘
                                  ▲
┌──────────────────────────────────────────────────────────────────────┐
│  IDENTIDADE & GOVERNANÇA                                              │
│  Pessoa · Organograma · Papéis+Escopo · SSO/SAML/OIDC · Tenant        │
│  Consentimento LGPD · Auditoria · Feature Flags                       │
└──────────────────────────────────────────────────────────────────────┘
                                  ▲
┌──────────────────────────────────────────────────────────────────────┐
│  DOMÍNIOS (existentes + novos)                                        │
│  Helpdesk · FSM · CRM · Financeiro · Estoque · Equipamentos · BI      │
│  ── novos ──  Pessoas · Aprendizagem · Conteúdo · Comunicação         │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.3 Decisões técnicas

| Decisão | Escolha | Justificativa |
|---|---|---|
| **App Django** | Novo app `workspace` | O app `dashboard` já é um god-app. Não agravar |
| **Front-end** | Django templates + **HTMX + Alpine** + tokens Aurora | Entrega premium sem SPA. Mantém o time produtivo no stack atual. Islands React apenas onde houver estado complexo real (builder de widget, editor de conteúdo) |
| **Contrato Workspace↔Domínio** | `WorkspaceProvider` — interface Python por domínio | Cada módulo declara `widgets()`, `search_documents()`, `quick_actions()`, `notifications()`. O Workspace não faz query em model de outro domínio |
| **Índice de busca** | PostgreSQL + **pgvector**, tabela `SearchDocument` única | Um índice, várias origens. Colunas `tenant_id`, `acl_subjects[]`, `embedding`, `tsvector`. Híbrido BM25 + vetorial |
| **Autorização de busca** | **Security trimming no índice**, nunca no pós-processamento | Filtrar depois de recuperar vaza contagem e snippet. `acl_subjects` é filtro `WHERE`, não `filter()` em Python |
| **IA** | Estender o Copilot Engine existente | O gate, o mask, a confirmação e a auditoria já estão certos. Adicionar skill packs e tools |
| **Tempo real** | Channels (já existe) | Notificações, presença, contadores |
| **Fila** | Celery (já existe) | Indexação, digest, embeddings, lembretes |
| **Tenancy** | Row-level **+ escopo organizacional** | Ver risco crítico em §12.2 |

### 3.4 Modelo de identidade — o pré-requisito de tudo

O modelo atual (6 papéis planos) não sustenta o Workspace. Proposta mínima:

```python
Pessoa            # 1:1 User — matrícula, cargo, admissão, foto, contatos
  ├── unidade     # FK Unidade (filial/base)
  ├── departamento
  ├── gestor      # FK Pessoa — organograma
  ├── centro_custo
  └── situacao    # ativo, férias, afastado, desligado

Papel             # substitui as constantes planas
  ├── chave, nome, escopo (global|unidade|departamento|proprio)
  └── permissoes  # granular, não hardcoded

AtribuicaoPapel   # Pessoa × Papel × escopo × vigência
                  # permite: "gerente financeiro DA UNIDADE SP até 31/12"

Delegacao         # Pessoa → Pessoa, período, papéis delegados
                  # resolve férias/afastamento sem travar aprovação
```

**Por que `AtribuicaoPapel` com escopo e vigência importa:** sem escopo, "gerente" vê tudo de todas as unidades — inviável para RH e Financeiro. Sem vigência, férias do aprovador travam a empresa. Ambos são falhas clássicas de portal corporativo.

---

## 4. Jornada completa do usuário

### 4.1 Primeiro acesso — os 5 minutos que definem a adoção

```
Login (SSO) → Boas-vindas com nome e cargo reais
            → "Confirme seu gestor e centro de custo"  (valida o organograma
                                                        usando o próprio usuário)
            → Escolha de preset visual (densidade, tema)
            → Tour de 4 pontos, ancorado, pulável, nunca repetido
            → 3 comunicados obrigatórios pendentes → confirmar leitura
            → Workspace
```

**Regra:** nenhum campo de formulário que o sistema já saiba responder. Se o RH importou a base, o usuário só **confirma**.

### 4.2 Jornada do técnico de campo — o caso mais negligenciado

O técnico é quem mais usa e quem menos é considerado no design de portais. Ele está no carro, com uma mão, sol na tela, 3G instável.

```
07:00  Push: "Bom dia, Marcos. 4 OS hoje · 1ª às 08:30 em Osasco · 22 km"
07:02  Abre o Workspace mobile → não vê widget nenhum de KPI corporativo
       Vê: Rota do dia · Checklist da 1ª OS · Estoque no veículo
08:20  Sem sinal → pacote do dia já em cache. Registra tudo offline
12:00  Sincroniza → fotos, assinatura, materiais consumidos
17:40  "Fechar o dia": 4/4 concluídas · 1 pendência de material
       → 1 toque gera a requisição de reposição
17:41  Alerta: "NR-10 vence em 12 dias · reciclagem disponível sábado"
       → 1 toque inscreve
```

**Nenhum concorrente entrega isso**, porque nenhum portal corporativo conhece rota, estoque de veículo e certificação ao mesmo tempo.

### 4.3 Jornada do gestor

```
08:00  Briefing gerado por IA (§11.3), 5 linhas, no topo do Workspace:
       "2 SLAs em risco hoje · aprovações represam R$ 18,4k há 3 dias ·
        absenteísmo da equipe subiu 9% ·  contrato Vivo vence em 30 dias"
08:02  Bloco de aprovações: 6 itens, com valor, impacto no orçamento e
       histórico do solicitante  → aprova 5 em lote, devolve 1 com motivo
08:10  KPI de SLA caiu → clica "Explique" → IA: "queda concentrada na
        unidade Campinas, 3 OS do técnico em treinamento"  → abre a OS
```

### 4.4 Jornada de solicitação (o coração do ESM)

```
Usuário digita no ⌘K: "meu notebook está lento"
   ↓
Sistema NÃO abre um formulário. Ele resolve em cascata:
   1. Resposta de autoatendimento (3 passos de limpeza) — resolve ~30%
   2. "Ainda com problema?" → oferece as 2 ações certas:
        [Abrir chamado de TI]  [Solicitar upgrade de equipamento]
   3. Formulário pré-preenchido: unidade, patrimônio do equipamento
      vinculado à pessoa, centro de custo, gestor aprovador — tudo
      derivado da identidade. Usuário preenche 1 campo: a descrição
   ↓
Acompanhamento com previsão real (baseada no histórico daquele tipo),
não "em andamento"
```

### 4.5 Jornada do cliente (B2B — receita)

```
Cliente entra no MESMO Workspace, preset "Cliente"
Vê: SLA do contrato em tempo real · OS em campo com localização do técnico ·
     faturas · consumo do contrato · abrir chamado · base de conhecimento
Não vê: nada interno. Ever.
```

---

## 5. Mapa de navegação

### 5.1 Princípio: 6 destinos, não 30

Arquitetura de informação de portal falha por excesso de nós de primeiro nível. Seis é o limite de memorização confortável.

```
iConnect Workspace
│
├── 🏠 Meu Espaço          ← default. Widgets, briefing, pendências
│   ├── Meu dia
│   ├── Minhas solicitações
│   ├── Minhas aprovações
│   └── Meus documentos
│
├── 🧭 Serviços            ← catálogo unificado (TI, RH, Fin, Facilities, Jur)
│   ├── Catálogo
│   ├── Acompanhamento
│   └── Autoatendimento (KB)
│
├── 📚 Conhecimento        ← biblioteca + aprendizagem, unificados
│   ├── Documentos (POP, políticas, normas, contratos, templates)
│   ├── Trilhas e cursos
│   ├── Minhas certificações
│   └── Wiki / APIs / Manuais técnicos
│
├── 📣 Mural               ← comunicação institucional
│   ├── Comunicados     (com leitura confirmada)
│   ├── Notícias e campanhas
│   ├── Eventos e agenda corporativa
│   └── Pessoas (aniversários, novos, reconhecimentos)
│
├── 👤 Pessoas             ← RH self-service + organograma
│   ├── Meu perfil e dados
│   ├── Holerite, benefícios, férias, ponto
│   ├── Carreira, PDI, feedback, avaliações
│   └── Organograma e diretório
│
└── 🧩 Aplicativos         ← REVISADO §10.7 · era "📊 Operação"
    ├── iConnect Platform (chamados, OS, clientes, contratos)
    ├── Demais sistemas corporativos
    └── Administração (para quem tem papel)
```

### 5.2 Navegação transversal — presente em todas as telas

| Elemento | Comportamento |
|---|---|
| **⌘K / Ctrl+K** | Command Bar: busca + ação + IA no mesmo campo. É a navegação real do produto |
| **Assistente** | Painel lateral persistente, com contexto da tela atual |
| **Notificações** | Agrupadas por tipo, acionáveis inline, com "adiar até" |
| **Alternador de audiência** | Para quem tem múltiplos papéis (gestor que também é técnico) |
| **Favoritos / Recentes** | Sincronizados, com atalho no ⌘K |

**Observação de AI:** os módulos existentes (Helpdesk, FSM…) ficam sob "Operação → Aplicações" e **abrem no seu próprio layout atual**. O Workspace não tenta reimplementá-los. Com o tempo, funções migram por atração — quando um widget resolve melhor que a tela antiga, o usuário migra sozinho.

---

## 6. Estrutura da Home

### 6.1 Anatomia (desktop ≥1280px)

```
┌────────────────────────────────────────────────────────────────────────┐
│  ⌘  iConnect        [ Buscar ou perguntar…            ⌘K ]   🔔  ⚙  👤 │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Bom dia, Christopher.                          terça, 7 de agosto     │
│  ────────────────────────────────────────────────────────────────      │
│  ZONA 1 — BRIEFING  (imutável, gerada por IA, 3–5 linhas)              │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ ⚡ 2 SLAs vencem em <4h · 6 aprovações represam R$ 18,4k ·        │ │
│  │    contrato Vivo vence em 30 dias · reunião de diretoria 14h      │ │
│  │    [Ver aprovações]  [SLAs em risco]  [Perguntar ao assistente]   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  ZONA 2 — AÇÃO  (o que preciso resolver; widgets acionáveis inline)    │
│  ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐ │
│  │ Aprovações      6  │ │ Meu dia            │ │ Minhas pendências  │ │
│  │ ─────────────────  │ │ ───────────────    │ │ ─────────────────  │ │
│  │ Reembolso R$ 840   │ │ 09:00 Daily        │ │ 3 chamados         │ │
│  │ Ana · há 2 dias    │ │ 11:00 Cliente X    │ │ 1 doc p/ assinar   │ │
│  │ [✓ Aprovar] [↩]    │ │ 14:00 Diretoria    │ │ 1 curso obrigatório│ │
│  │ ─────────────────  │ │ [Entrar na reunião]│ │ vence em 5 dias    │ │
│  │ Compra R$ 12.400   │ │                    │ │ [Fazer agora]      │ │
│  │ [✓] [↩]  ver todas │ │                    │ │                    │ │
│  └────────────────────┘ └────────────────────┘ └────────────────────┘ │
│                                                                        │
│  ZONA 3 — CONTEXTO  (o que preciso saber; personalizável)              │
│  ┌────────────────────────────────────┐ ┌────────────────────────────┐│
│  │ KPIs do meu escopo      [Explique] │ │ Mural                      ││
│  │  SLA 94,2% ▲2,1  ·  OS hoje 38     │ │ 🔴 Política de viagens     ││
│  │  Backlog 12 ▼4  ·  CSAT 4,6        │ │    atualizada — confirmar  ││
│  │  ▁▂▄▆█▇▅▃  (7 dias)                │ │ 🎉 Ana faz 5 anos hoje     ││
│  └────────────────────────────────────┘ │ 📅 Treinamento NR-10 sáb   ││
│  ┌────────────────────────────────────┐ └────────────────────────────┘│
│  │ Continue de onde parou             │ ┌────────────────────────────┐│
│  │ • OS #4821 (rascunho, 12 min atrás)│ │ Acesso rápido              ││
│  │ • Relatório mensal (não enviado)   │ │ [Helpdesk][FSM][BI][Fin]   ││
│  └────────────────────────────────────┘ └────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────┘
```

### 6.2 As três zonas — por que essa divisão

| Zona | Pergunta que responde | Personalizável? |
|---|---|---|
| **1 — Briefing** | "O que mudou desde ontem e o que é urgente?" | ❌ Não. É onde a empresa fala |
| **2 — Ação** | "O que eu preciso concluir?" | ⚠️ Ordem sim, remoção não |
| **3 — Contexto** | "O que preciso saber para decidir?" | ✅ Total |

Essa hierarquia é o que impede o Workspace de virar mural de widgets. Se um widget não cabe em nenhuma das três perguntas, ele não entra no produto.

### 6.3 Catálogo de widgets

**Do documento original — mantidos e reclassificados:**

| Widget | Zona | Observação |
|---|---|---|
| Saudação personalizada | 1 | Funde no Briefing, não é widget próprio |
| IA em destaque | 1 | Vira o Briefing + ⌘K. Não é card |
| Pesquisa global | topo | Barra fixa, não widget |
| Pendências | 2 | Consolidada — não uma por sistema |
| Aprovações | 2 | Com ação inline |
| Chamados | 2 | Só os *meus*; contadores globais vão pro BI |
| Agenda / próximas reuniões | 2 | Único widget, não dois |
| Cursos obrigatórios | 2 | Só quando há prazo. Silencioso se não há |
| Notícias / comunicados / eventos | 3 | Único widget "Mural", não três |
| KPIs | 3 | Com "Explique" |
| Favoritos / Aplicativos | 3 | Um widget "Acesso rápido" |
| Atividades recentes / últimos documentos | 3 | Funde em "Continue de onde parou" |
| Alertas | 1 | Vai para o Briefing, senão compete com ele |

> **Redução deliberada:** 18 widgets propostos → 9 reais. Cada widget removido é um que não precisa ser mantido, traduzido, testado em dark mode e explicado no treinamento.

**Widgets novos que eu recomendo:**

| Widget | Público | Por que |
|---|---|---|
| **Fechar o dia** | todos | Ritual de saída. Maior gerador de retenção e de dado sobre uso do tempo |
| **Meu time hoje** | gestor | Quem está de férias/afastado/em campo. A pergunta nº 1 de todo gestor |
| **Escala e plantão** | operação | Quem está de sobreaviso agora. Hoje vive em grupo de WhatsApp |
| **Orçamento do meu centro de custo** | gestor | Consumido × previsto. Faz aprovação virar decisão informada |
| **Risco de SLA** | operação/gestor | Preditivo, não retrospectivo. Usa o `sla_monitor` existente |
| **Certificações da equipe** | gestor de campo | Vencendo em 30/60/90 dias. Liga com bloqueio de escala (§11.1) |
| **Pulso** | todos | 1 pergunta por semana, 5 segundos. Clima medido continuamente |
| **Documentos para assinar/confirmar** | todos | Trilha de compliance, não caixa de entrada |
| **Onboarding** | novatos | Só nos primeiros 90 dias. Progresso, próximos passos, quem procurar |
| **Saúde dos sistemas** | TI | Consome o `HealthCheckView` que já existe |
| **Reconhecimentos** | todos | O único elemento "social" que sobrevive a 90 dias |

### 6.4 Presets por perfil

Cada preset é uma configuração de zona 2 e 3, não um layout diferente.

| Preset | Zona 2 | Zona 3 |
|---|---|---|
| **Diretoria** | Aprovações · Agenda · Decisões pendentes | KPIs executivos · Metas/OKR · Mural · Riscos |
| **Gestor** | Aprovações · Meu time hoje · Pendências | Orçamento CC · KPIs da equipe · Certificações · Mural |
| **Operação / Monitoramento** | Risco de SLA · Fila · Incidentes | Mapa ao vivo · Escala · KPIs operacionais |
| **Técnico de campo** | Rota do dia · Checklist · Fechar o dia | Estoque do veículo · Minhas certificações · Mural |
| **RH** | Solicitações de pessoas · Aprovações | Headcount · Absenteísmo · Onboarding em curso · Pulso |
| **Financeiro** | Aprovações de despesa · Conciliações | Fluxo de caixa · Inadimplência · Contratos a vencer |
| **TI** | Chamados atribuídos · Solicitações de acesso | Saúde dos sistemas · Ativos · Licenças |
| **Comercial** | Propostas · Follow-ups · Aprovações de desconto | Funil · Metas · Contratos a renovar |
| **Cliente** | Meus chamados · Minhas OS | SLA do contrato · Faturas · KB |
| **Parceiro/Fornecedor** | Minha escala / meus pedidos | Documentos · Pagamentos |

---

## 7. Estrutura de cada módulo

### 7.1 Serviços (Catálogo / ESM) — **construir primeiro**

É o módulo com maior retorno e menor custo, porque o motor de tickets já existe.

```
Serviços
├── Catálogo         busca-first, não árvore de categorias
│   └── Card do serviço: prazo real · custo · quem aprova · o que precisa
├── Solicitação      formulário com ≤3 campos livres; o resto vem da identidade
├── Acompanhamento   timeline com previsão baseada em histórico
└── Aprovação        inline, em lote, com dossiê e delegação
```

**Catálogo inicial (~30 itens, agrupados por intenção — não por departamento):**

| Grupo | Itens |
|---|---|
| Equipamento e acesso | notebook, monitor, celular, periféricos, VPN, acesso a sistema, e-mail, crachá |
| Trabalho e ausência | férias, banco de horas, home office, atestado, licença |
| Dinheiro | reembolso, adiantamento, prestação de contas, compra, contrato |
| Viagem | passagem, hospedagem, diária, veículo, combustível |
| Espaço e material | sala, uniforme, EPI, manutenção predial, material de escritório |
| Desenvolvimento | treinamento, certificação, indicação de vaga, mudança de cargo |
| Jurídico | análise de contrato, parecer, procuração |

> **Regra de ouro do catálogo:** o usuário navega por **problema** ("meu notebook quebrou"), nunca por **departamento** ("TI → Hardware → Manutenção"). Departamento é dado de roteamento, não taxonomia de navegação.

**Diferencial de execução:** cada item do catálogo exibe **prazo real medido** (P50/P90 do histórico), não SLA prometido. Isso constrói confiança de forma que nenhum concorrente faz.

### 7.2 Conhecimento (Biblioteca + Aprendizagem, unificados)

Separar "documentos" de "cursos" é uma divisão organizacional, não uma divisão do usuário. Quem precisa saber operar um equipamento não se importa se a resposta é um POP ou um vídeo de treinamento.

```
Conhecimento
├── Biblioteca
│   ├── Tipos: POP · Política · Norma ISO · LGPD · Manual · Contrato ·
│   │          Template · Ata · Fluxograma · Doc técnica · API
│   ├── Ciclo de vida: rascunho → revisão → publicado → vigente →
│   │                  em revisão → obsoleto      (com dono e validade)
│   ├── Versionamento com diff e trilha de aprovação
│   └── Leitura confirmada por público-alvo (ISO/compliance)
├── Aprendizagem  (fatia fina — ver §1.2 discordância nº 5)
│   ├── Trilhas por cargo (derivadas do modelo de identidade)
│   ├── Cursos obrigatórios com prazo e bloqueio
│   ├── Certificações com validade e alerta de vencimento
│   └── Avaliação simples (múltipla escolha + nota mínima)
└── Busca IA sobre tudo acima, com citação de fonte e versão
```

**Modelo de conteúdo (obrigatório antes de qualquer IA):**

```python
Documento
  ├── tipo, titulo, resumo, corpo/arquivo
  ├── dono (Pessoa), departamento, classificacao (público|interno|restrito|confidencial)
  ├── publico_alvo (papéis, departamentos, unidades)  → gera acl_subjects
  ├── versao, vigencia_inicio, vigencia_fim, revisao_prevista
  ├── leitura_obrigatoria (bool), exige_aceite (bool)
  └── tags, relacionados, embedding
```

**Sobre gamificação, ranking e badges:** deliberadamente **fora do MVP**. Ranking público de aprendizagem é contraproducente em operação de campo — cria constrangimento em quem tem menos escolaridade formal, que é exatamente quem mais precisa do treinamento. Se entrar em V3, deve ser **progresso individual e reconhecimento por pares**, nunca leaderboard.

### 7.3 Mural (Comunicação)

```
Mural
├── Comunicado    3 classes: informativo · obrigatório (confirma leitura) ·
│                 crítico (bloqueia até aceite).  Com público-alvo segmentado
├── Notícia       conteúdo editorial, com autor e área
├── Campanha      com meta e progresso (segurança, saúde, qualidade)
├── Evento        com inscrição, lembrete e integração de calendário
├── Pessoas       aniversários, novos colaboradores, movimentações
├── Reconhecimento  peer-to-peer, vinculado a um valor da empresa
└── Pulso         1 pergunta/semana, anônima, série temporal
```

**Recursos que eu removo:** curtidas com contagem pública, ranking de "funcionário destaque" votado, comentários abertos em comunicado oficial. Cada um é uma fonte confiável de política interna e conflito.

**Recursos adicionais que eu recomendo:**

- **Confirmação de leitura com relatório por gestor** — "12 dos seus 15 confirmaram"
- **Tradução automática** — operação com equipe multi-nacional
- **Áudio do comunicado** — técnico ouve dirigindo. Custo baixíssimo, uso altíssimo
- **Agendamento e público-alvo por regra** — "todos de campo da unidade SP admitidos há <90 dias"
- **Retratação/correção versionada** — comunicado errado hoje não tem como ser corrigido sem confusão

### 7.4 Pessoas (RH)

**Decisão estratégica:** o iConnect **não vira um HRIS**. Folha, ponto e eSocial são território de sistemas dedicados com risco regulatório alto e zero diferenciação.

| Funcionalidade | Decisão |
|---|---|
| Meu perfil, diretório, organograma | ✅ Construir (é base de identidade, não RH) |
| Férias — solicitar e aprovar | ✅ Construir (é fluxo de aprovação, reusa o engine) |
| Holerite, banco de horas, ponto, benefícios | 🔗 **Integrar** — exibir, nunca calcular |
| PDI, feedback, competências, avaliação | ✅ Construir em V2 — liga com aprendizagem e escala |
| Onboarding / Offboarding | ✅ Construir — é um workflow, e o offboarding é risco de segurança real |
| Reembolso, solicitações | ✅ Já é o catálogo de serviços |
| Vagas, indique um amigo | ⚠️ V3 — baixo uso, alto custo |
| Plano de carreira | ⚠️ V3 |

**Adicionais que eu recomendo:**

- **Offboarding com revogação automática de acesso** — hoje é a maior falha de segurança de 90% das empresas médias. O Workspace sabe todos os sistemas que a pessoa acessa; pode revogar em cadeia e gerar evidência
- **Trilha de admissão com dono e SLA** — onboarding sem prazo não acontece
- **Ausências do time em calendário único** — resolve o problema real do gestor
- **Documentos pessoais com validade** (CNH, ASO, certificações) — vence e avisa

### 7.5 Financeiro (no Workspace)

O Workspace expõe apenas a superfície **do colaborador e do gestor** — o módulo financeiro completo continua onde está.

```
No Workspace: reembolso · prestação de contas · aprovação de despesa ·
              orçamento do centro de custo · contratos a vencer ·
              notas e boletos (cliente/fornecedor)
```

**Recursos novos de alto valor:**

- **Reembolso por foto** — OCR do cupom, categoria sugerida, política validada **antes** do envio ("almoço acima do limite de R$ 60 — precisa de justificativa")
- **Aprovação com contexto orçamentário** — "aprovar consome 82% do que resta do CC neste mês"
- **Previsão de comprometimento** — o que já foi aprovado mas ainda não pagou
- **Alerta de renovação automática de contrato** — o custo silencioso que ninguém rastreia

### 7.6 Operação (ponte, não substituição)

```
Operação
├── Painéis        BI por papel, com "Explique" em cada KPI
├── Aplicações     Helpdesk · FSM · CRM · Financeiro · Estoque · Equipamentos
│                  (abrem no layout atual — não reescrever)
└── Ao vivo        mapa de técnicos · fila · incidentes · alertas · SLA
```

**Recursos novos:**

- **Sala de guerra de incidente** — incidente crítico abre um espaço com timeline, participantes, comunicação ao cliente e pós-morte automático
- **Escala e sobreaviso como objeto de primeira classe** — hoje é planilha e WhatsApp em toda empresa de campo
- **Custo real da OS** — deslocamento + material + hora técnica, no fechamento. Amarra FSM ↔ Financeiro

---

## 8. Design System — "Aurora"

### 8.1 Por que um DS novo em vez de estender o atual

O `iconnect-design-system.css` acertou nos **tokens de cor** (Slate + Cyan é uma escolha madura e não datada). O problema não é a paleta; é a **casca** — Material Dashboard 2 traz densidade baixa, sombras pesadas, raios grandes e gradientes saturados, que são a assinatura visual de "template comprado".

Aurora **preserva a paleta** e substitui forma, espaço, tipografia e movimento.

### 8.2 Princípios

1. **Densidade é respeito.** Usuário profissional passa 6 h/dia aqui. Informação por tela importa mais que ar.
2. **Hierarquia por tipografia e espaço, não por cor e sombra.** Cor é reservada para estado e ação.
3. **Movimento informa, não decora.** Se a animação não explica de onde algo veio, remova.
4. **Dark mode é primeira classe**, não um tema alternativo. Sala de monitoramento roda dark 24 h.
5. **Cada componente responde em ≤100 ms.** Percepção de velocidade é 60% da percepção de premium.

### 8.3 Tokens

```css
:root {
  /* ── Cor: marca preservada, escala completa ───────────────────── */
  --au-brand-50:#f1f5f9; --au-brand-100:#e2e8f0; --au-brand-200:#cbd5e1;
  --au-brand-300:#94a3b8; --au-brand-400:#64748b; --au-brand-500:#475569;
  --au-brand-600:#334155; /* ← primária atual, preservada */
  --au-brand-700:#1e293b; --au-brand-800:#0f172a; --au-brand-900:#020617;

  --au-accent-400:#22d3ee; --au-accent-500:#06b6d4; /* ← accent atual */
  --au-accent-600:#0891b2;

  /* ── Semântica (papel, não valor) ─────────────────────────────── */
  --au-bg:            var(--au-brand-50);
  --au-surface:       #ffffff;
  --au-surface-raised:#ffffff;
  --au-surface-sunken: var(--au-brand-100);
  --au-border:        var(--au-brand-200);
  --au-border-strong: var(--au-brand-300);
  --au-text:          var(--au-brand-800);
  --au-text-muted:    var(--au-brand-400);
  --au-text-inverse:  #ffffff;

  --au-success:#059669; --au-warning:#d97706;
  --au-danger:#dc2626;  --au-info:var(--au-accent-600);

  /* ── Espaço: escala 4px, não 8px (densidade) ──────────────────── */
  --au-1:4px; --au-2:8px; --au-3:12px; --au-4:16px;
  --au-5:24px; --au-6:32px; --au-7:48px; --au-8:64px;

  /* ── Raio: contido. Raio grande = brinquedo ───────────────────── */
  --au-r-sm:6px; --au-r-md:10px; --au-r-lg:14px; --au-r-full:999px;

  /* ── Elevação: 3 níveis. Mais que isso vira ruído ─────────────── */
  --au-e-0:none;
  --au-e-1:0 1px 2px rgb(15 23 42/.06), 0 1px 3px rgb(15 23 42/.10);
  --au-e-2:0 4px 6px -1px rgb(15 23 42/.07), 0 2px 4px -2px rgb(15 23 42/.06);
  --au-e-3:0 12px 20px -6px rgb(15 23 42/.12), 0 4px 8px -4px rgb(15 23 42/.08);

  /* ── Tipografia: Inter (já carregada) · escala 1.200 ──────────── */
  --au-font:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;
  --au-mono:'JetBrains Mono',ui-monospace,'SF Mono',monospace;
  --au-t-xs:11px; --au-t-sm:12px; --au-t-base:13px; --au-t-md:15px;
  --au-t-lg:18px; --au-t-xl:22px; --au-t-2xl:28px; --au-t-3xl:36px;
  --au-lh-tight:1.25; --au-lh:1.5; --au-lh-loose:1.7;

  /* ── Movimento: rápido e com propósito ────────────────────────── */
  --au-dur-fast:120ms; --au-dur:180ms; --au-dur-slow:280ms;
  --au-ease:cubic-bezier(.2,0,0,1);
  --au-ease-out:cubic-bezier(0,0,.2,1);

  /* ── Densidade: chaveável pelo usuário ────────────────────────── */
  --au-row-h:36px;  /* confortável:44px · compacto:30px */
}

:root[data-theme="dark"],
:root:not([data-theme="light"]) { /* respeita prefers-color-scheme */
  --au-bg:            var(--au-brand-900);
  --au-surface:       #0b1220;
  --au-surface-raised:#111c2e;
  --au-surface-sunken: #060b16;
  --au-border:        #1e293b;
  --au-border-strong: #334155;
  --au-text:          #e2e8f0;
  --au-text-muted:    #7c8ba1;
  --au-e-1:0 1px 2px rgb(0 0 0/.4);
  --au-e-2:0 4px 8px rgb(0 0 0/.45);
  --au-e-3:0 16px 32px rgb(0 0 0/.5);
}
```

### 8.4 Uso de glassmorphism — dosagem estrita

Glass é o efeito que mais rápido faz um produto parecer datado quando usado em excesso. **Permitido em exatamente três lugares:**

1. A barra de comando (⌘K) sobreposta
2. A barra superior ao rolar a página
3. O painel do assistente sobre o conteúdo

`backdrop-filter: blur(20px) saturate(140%)` + fundo a 72% de opacidade + borda de 1px a 8% de branco. **Nunca em card de conteúdo** — prejudica contraste e legibilidade de texto denso.

### 8.5 Inventário de componentes (MVP)

| Categoria | Componentes |
|---|---|
| **Estrutura** | AppShell · Sidebar colapsável · Topbar · WidgetGrid · PageHeader · SplitView |
| **Superfície** | Card · Widget · Panel · Sheet (mobile) · Modal · Popover · Drawer |
| **Dado** | DataTable (virtualizada, densidade chaveável) · KPI tile · Sparkline · Timeline · EmptyState · Skeleton |
| **Entrada** | Input · Select · Combobox (busca assíncrona) · DatePicker · FileDrop · RichText · FormBuilder |
| **Ação** | Button (4 variantes × 3 tamanhos) · IconButton · SplitButton · CommandBar · QuickAction |
| **Feedback** | Toast · InlineAlert · ConfirmDialog · ProgressRing · StatusDot |
| **IA** | AssistantPanel · SourceCitation · ConfirmActionCard · StreamingText · SuggestionChips |
| **Navegação** | Breadcrumb · Tabs · Pagination · CommandPalette |

### 8.6 O que "parece internacional" na prática

Não é gradiente nem glass. São seis coisas mensuráveis:

| Sinal | Regra |
|---|---|
| **Alinhamento óptico** | Tudo em grade de 4px. Zero valor mágico no CSS |
| **Estados completos** | Todo componente tem default, hover, focus-visible, active, disabled, loading, error, empty |
| **Loading nunca em branco** | Skeleton com a forma do conteúdo real |
| **Vazio nunca em branco** | Empty state explica o que é, por que está vazio e a próxima ação |
| **Teclado completo** | Toda ação primária tem atalho. Tab order correto. Focus ring visível |
| **Zero jank** | Nenhum reflow ao carregar. Altura reservada antes do dado chegar |

Um produto com essas seis coisas parece internacional mesmo em cinza. Um produto sem elas parece amador mesmo com o melhor visual.

---

## 9. Fluxos principais

### 9.1 Busca global — arquitetura

```
Usuário digita  ⌘K
   │
   ├─▶ 0–120ms   Local: recentes, favoritos, ações, navegação
   │              (client-side, instantâneo — sensação de velocidade)
   │
   ├─▶ ~150ms    Léxico: Postgres FTS sobre SearchDocument
   │              WHERE tenant_id = ? AND acl_subjects && ?    ← trimming no índice
   │
   ├─▶ ~300ms    Semântico: pgvector, mesmo filtro de ACL
   │
   ├─▶           Fusão RRF (Reciprocal Rank Fusion) + boost por
   │              recência, tipo e afinidade do usuário
   │
   └─▶ ~900ms    IA: só se a consulta for pergunta (heurística + intenção)
                  Resposta ancorada nos top-K, com citação e versão
```

**Layout do resultado:**

```
┌─ ⌘K ──────────────────────────────────────────────────────┐
│  férias                                                   │
├───────────────────────────────────────────────────────────┤
│  ⚡ AÇÕES                                                  │
│     Solicitar férias                          ↵           │
│     Ver saldo de férias da equipe                         │
│                                                           │
│  🤖 RESPOSTA                                               │
│     Você tem 18 dias disponíveis. A solicitação precisa   │
│     de 30 dias de antecedência e da aprovação do seu      │
│     gestor (Ana Prado).                                   │
│     Fontes: Política de Férias v3 (vigente) · seu saldo   │
│                                                           │
│  📄 DOCUMENTOS                                             │
│     Política de Férias v3 · RH · vigente                  │
│     POP-RH-014 Programação de férias coletivas            │
│                                                           │
│  👥 PESSOAS · 📋 CHAMADOS · 🎓 CURSOS      (agrupados)     │
└───────────────────────────────────────────────────────────┘
```

**Regra de segurança inegociável:** ACL aplicada como `WHERE` no índice. Filtrar em Python depois de recuperar vaza contagem total, ordenação e — no pior caso — trecho de snippet. É a falha nº 1 de busca corporativa.

### 9.2 Fluxo do assistente (estendendo o engine atual)

```
Pergunta
   │
   ├─ Classificação de intenção  → informação | ação | navegação | análise
   │
   ├─ Seleção de skill pack       → RH · Financeiro · TI · Operação · Jurídico…
   │     (invisível ao usuário — §1.2 nº4)
   │
   ├─ PermissionGate (JÁ EXISTE)  → só as tools que o papel permite
   ├─ PII mask no egress (JÁ EXISTE)
   │
   ├─ Loop de tool-use (JÁ EXISTE)
   │     ├─ leitura → executa inline
   │     └─ escrita → PAUSA, devolve card de confirmação
   │
   ├─ Resposta com citação obrigatória de fonte + versão do documento
   └─ Auditoria (JÁ EXISTE)
```

**O que precisa ser adicionado ao engine existente:**

| Adição | Esforço |
|---|---|
| Tools de RH, conteúdo, catálogo, aprovação | médio |
| Skill packs (prompt + tools + fontes por domínio) | baixo |
| Roteador de intenção | baixo |
| Citação com versão e vigência do documento | baixo |
| Memória de conversa por sessão | baixo |
| Teto de custo por usuário/tenant | **crítico** — ver §12.6 |

### 9.3 Solicitação → Aprovação → Entrega

```
Catálogo ──▶ Formulário pré-preenchido ──▶ Validação de política
                                              (limite, orçamento, elegibilidade)
                                                     │
                                        ┌────────────┴────────────┐
                                   dentro da política      fora da política
                                        │                       │
                                  auto-aprovado          Aprovação em cadeia
                                        │                (gestor → CC → diretoria,
                                        │                 conforme valor)
                                        └────────────┬────────────┘
                                                     ▼
                                          Ticket no módulo certo
                                          (Helpdesk / FSM / Financeiro)
                                                     ▼
                                        Acompanhamento com prazo real
                                                     ▼
                                          Entrega + confirmação + CSAT
```

**Detalhe que muda tudo:** *auto-aprovação dentro da política*. Se o pedido está dentro do limite, do orçamento e da elegibilidade, ele não vai para fila humana. A maioria dos portais coloca 100% dos pedidos em aprovação manual, e é por isso que a percepção é de lentidão.

### 9.4 Aprovação em lote com contexto

```
┌─ Aprovações (6) ─────────────────────── total represado: R$ 18.430 ─┐
│ ☑ Reembolso · Ana Prado · R$ 840 · viagem SP        há 2 dias       │
│   3 notas · dentro da política · CC 1042: 68% consumido             │
│   Ana teve 4 reembolsos nos últimos 90 dias, todos aprovados        │
│                                                    [✓] [↩ devolver] │
│ ☐ Compra · TI · R$ 12.400 · 4 notebooks             há 5 dias       │
│   ⚠ dentro do teto do gestor (R$ 50.000) → ver §10.6                │
│   ⚠ consome 91% do saldo do CC neste mês                            │
│                                                    [✓] [↩] [↑]      │
├─────────────────────────────────────────────────────────────────────┤
│ [Aprovar 4 selecionados]                    [Delegar tudo a…]       │
└─────────────────────────────────────────────────────────────────────┘
```

Aprovação sem contexto financeiro é carimbo. Com contexto, é decisão. Esse é o widget que faz um diretor abrir o portal todo dia.

---

## 10. Roadmap MVP → V2 → V3

### Fase 0 — Fundação (4–6 semanas) · *sem entrega visível, inegociável*

| Entrega | Por quê |
|---|---|
| Modelo de identidade (`Pessoa`, `Unidade`, `Departamento`, organograma, `AtribuicaoPapel` com escopo e vigência, `Delegacao`) | Nada funciona sem isso |
| Endurecimento de tenancy (§12.2) | Antes de qualquer dado de RH |
| App `workspace` + casca Aurora (tokens, AppShell, 12 componentes base) | Base visual |
| Contrato `WorkspaceProvider` | Impede o acoplamento que mata portais |

### MVP — "Resolver sem abrir o sistema" (10–12 semanas)

| Entrega | Nota |
|---|---|
| **Workspace** com 3 zonas, 9 widgets, 4 presets (colaborador, gestor, técnico, cliente) | — |
| **⌘K** com busca local + léxica sobre documentos, pessoas, chamados, clientes | Sem IA ainda |
| **Catálogo de serviços** com ~30 itens e formulário derivado da identidade | Reusa motor de tickets |
| **Aprovações** inline, em lote, com delegação | — |
| **Biblioteca** com modelo de conteúdo, versionamento, leitura confirmada | **Popular antes de ligar IA** |
| **Mural** com 3 classes de comunicado e confirmação de leitura | — |
| **Pessoas**: perfil, diretório, organograma, férias | Holerite: integração |
| **Mobile PWA** para o técnico, com pacote do dia offline | — |

> **Critério de saída do MVP:** ≥60% dos acessos ao iConnect passam pelo Workspace e ≥40% das solicitações internas nascem no catálogo.

### V2 — "A inteligência entra" (10–14 semanas)

- **Assistente corporativo** sobre o Copilot Engine, com skill packs e citação de fonte
- **Busca semântica** unificada (pgvector) com security trimming
- **Briefing diário** por IA + push matinal
- **"Explique este KPI"** em todos os painéis
- **Aprendizagem**: trilhas por cargo, cursos obrigatórios, certificações com validade
- **Bloqueio de escala por certificação vencida** (§11.1) — o diferencial
- **Captura passiva de conhecimento** (§11.9)
- **Reembolso por foto** com OCR e validação de política
- **Onboarding / Offboarding** com revogação de acesso em cadeia
- **Presets** para RH, Financeiro, TI, Comercial, Parceiro, Fornecedor

### V3 — "Plataforma" (6+ meses)

- **Workspace Studio** — criação de widget, catálogo e fluxo sem código
- **Marketplace de conectores** (M365, Google, WhatsApp, ERPs, bancos)
- **Agentes proativos** — o sistema age antes de ser perguntado (§11.4)
- **Digital Twin do colaborador** (§11.5)
- **Simulador de decisão** (§11.6)
- **Multi-idioma completo** e acessibilidade AA certificada
- **API pública do Workspace** e SDK de widget para terceiros
- **White-label** do portal do cliente como produto vendável

---

## 11. Funcionalidades inovadoras

Critério aplicado: cada item aproveita dado que **só o iConnect tem** (operação + pessoas no mesmo lugar), e é mal-resolvido ou inexistente nos concorrentes.

### 11.1 Competência que vence bloqueia a operação
Certificação expirada remove o técnico da fila de despacho daquele tipo de serviço — automaticamente, com aviso em 30/15/5 dias e inscrição em 1 toque na reciclagem. **Ninguém faz** porque LMS não conversa com despacho. Valor direto: risco trabalhista, seguro, auditoria de cliente.

### 11.2 Home ciente de turno, escala e localização
A home muda por **momento**, não só por cargo. Técnico de plantão às 23h vê contatos de emergência e procedimento de escalonamento; o mesmo técnico às 9h vê rota. Portais corporativos são estáticos porque não conhecem escala.

### 11.3 Briefing diário gerado por IA
Cinco linhas escritas às 6h para cada gestor, sobre o **escopo dele**: o que mudou, o que trava, o que vence, o que decidir. Enviado por push e presente no topo da home. É o recurso que faz alguém abrir o portal antes do e-mail.

### 11.4 Agentes proativos (V3)
O sistema age antes da pergunta: *"detectei que 3 OS na região sul vão furar SLA em 2h — sugiro remanejar o Marcos, que termina às 14h a 8 km de distância. [Aplicar] [Ignorar]"*. Toda ação passa pelo gate de confirmação que já existe.

### 11.5 Digital Twin do colaborador
Uma linha do tempo única por pessoa, atravessando RH, operação, aprendizagem e comunicação: admissão, treinamentos, OS executadas, incidentes, feedbacks, certificações, reconhecimentos. Serve para 1:1, avaliação, sucessão e defesa trabalhista. Hoje esse dado existe em cinco sistemas que não se falam.

### 11.6 Simulador de decisão
*"O que acontece se eu aprovar essas 6 despesas?"* → impacto no CC, no fluxo de caixa e no fechamento. *"E se o Marcos entrar de férias na semana 32?"* → cobertura de escala, SLA em risco, certificações faltantes. Nenhum portal simula; todos apenas registram.

### 11.7 Custo antes da aprovação
Todo item do catálogo mostra o custo real e o impacto no orçamento do aprovador **antes** de o pedido ser feito. Muda o comportamento do solicitante, não só o do aprovador — o efeito de redução de pedido supérfluo é imediato e mensurável.

### 11.8 Aprovação onde a pessoa está
Aprovar por WhatsApp ou push com dossiê completo na mensagem, sem abrir o sistema, com assinatura e trilha auditável. A infra de WhatsApp já existe no projeto. Aprovação é o gargalo nº 1 de toda empresa média, e o gargalo é o aprovador não estar na frente do computador.

### 11.9 Captura passiva de conhecimento — *o conteúdo se escreve sozinho*
Toda OS resolvida e todo chamado fechado com solução geram um **rascunho de POP** por IA, roteado para o especialista revisar em 30 segundos: `[Publicar] [Editar] [Descartar]`. Resolve o problema estrutural de biblioteca vazia (§1.2 nº7) usando a operação que já roda. **Este é possivelmente o recurso mais valioso do documento inteiro** — é o que faz a IA ter o que responder sem ninguém escrever documentação.

### 11.10 Modo campo verdadeiro
Pacote do dia baixado ao sair da base: OS, checklists, manuais dos equipamentos daquela rota, contatos. Funciona sem sinal, sincroniza com resolução de conflito ao voltar. Portais corporativos assumem escritório; operação de campo brasileira não tem esse luxo.

### 11.11 Explique este número
Botão em todo KPI. A IA lê a série, compara períodos, isola o driver, escreve duas frases e oferece o drill-down. Transforma BI de relatório em conversa.

### 11.12 Ritual de fechamento do dia
Um card ao final do expediente: o que foi concluído, o que ficou, o que amanhã exige, e uma linha opcional de nota. Gera retenção diária e o dado mais escasso de qualquer empresa — para onde o tempo realmente foi.

---

## 12. Riscos e pontos de atenção

### 12.1 🔴 Escopo — o risco que mata o projeto
Cinco produtos em paralelo entregam cinco medianos. **Mitigação:** o MVP de §10 é deliberadamente estreito. Toda funcionalidade fora dele precisa responder: *"isso impede o critério de saída do MVP?"* Se não, espera.

### 12.2 🔴 Tenancy — o risco que mata a empresa
O isolamento hoje é row-level com `threading.local()`. Isso funciona enquanto o vazamento significa "ver ticket de outro cliente". Quando o Workspace carregar holerite, PDI e avaliação, **um vazamento vira incidente de dado sensível sob LGPD art. 11**.

**Mitigação obrigatória antes de qualquer dado de RH:**
- Teste automatizado de isolamento por model — CI falha se um queryset novo não filtra tenant
- Manager padrão que **exige** escopo explícito; queryset sem tenant levanta exceção em vez de retornar tudo
- Auditoria de acesso a dado sensível com alerta em volume anômalo
- Revisão do `threading.local()` sob ASGI/Channels — contexto assíncrono é onde thread-local falha silenciosamente

### 12.3 🔴 Biblioteca vazia = IA descreditada
Assistente lançado sem conteúdo produz a impressão *"a IA daqui não sabe nada"* — e ela não se reverte. **Mitigação:** IA só liga em V2, com meta mínima de conteúdo publicado (sugestão: 40 documentos das 10 dúvidas mais frequentes), mais §11.9 rodando desde o MVP.

### 12.4 🟠 Workspace que ninguém abre
Portais corporativos têm taxa de fracasso alta porque não há razão diária para voltar. **Mitigação:** três âncoras de retorno obrigatório — (1) aprovações só existem lá; (2) briefing matinal por push; (3) comunicado obrigatório bloqueia. Sem pelo menos duas, o portal morre em 60 dias.

### 12.5 🟠 LGPD com dado sensível
RH traz dado de saúde (ASO, atestado), biometria (ponto) e avaliação de desempenho. **Mitigação:** classificação por documento, minimização (o Workspace *exibe*, não *armazena* holerite), retenção definida por tipo, consentimento onde aplicável, e **PII mask já existente aplicado no egress para o LLM** — verificar que cobre os campos novos de RH.

### 12.6 🟠 Custo de IA sem teto
Assistente corporativo aberto a toda a empresa, com tool-use e loop de até 5 iterações, tem custo linear no número de funcionários e superlinear em usuários curiosos. **Mitigação:** teto por usuário e por tenant, cache agressivo de respostas frequentes, roteamento para modelo menor em intenção simples, e telemetria de custo por skill pack desde o dia 1.

### 12.7 🟠 O god-app `dashboard`
O app já concentra models, views, services e tasks de todos os domínios. Colocar o Workspace dentro dele agrava a manutenção e torna o teste mais lento. **Mitigação:** app `workspace` separado, com dependência apenas via `WorkspaceProvider`.

### 12.8 🟡 Performance da home
Home com 9 widgets = 9 conjuntos de queries em cada carregamento. **Mitigação:** widgets carregam assíncronos e independentes (HTMX), cada um com cache próprio e TTL por natureza do dado; skeleton com altura reservada; orçamento de performance de 800 ms para a primeira zona.

### 12.9 🟡 Dois design systems convivendo
Aurora no Workspace, Material Dashboard nos módulos antigos. Transição visível ao usuário. **Mitigação:** aceitar conscientemente, alinhar apenas os tokens de cor entre os dois, migrar os módulos por atração e não por decreto. Rebranding big-bang de 40 telas é o caminho mais rápido para não entregar nada.

### 12.10 🟡 Adoção do técnico de campo
É o público com menor afinidade digital e maior impacto operacional. **Mitigação:** mobile-first real para esse preset, zero KPI corporativo na tela dele, texto grande, alvos de toque grandes, funcionar offline, e piloto com 5 técnicos antes de qualquer rollout.

---

## 13. Monetização e diferenciais competitivos

### 13.1 Empacotamento

| Plano | Conteúdo | Racional |
|---|---|---|
| **Operations** | Módulos operacionais atuais | Base instalada, sem mudança |
| **Workspace** | Workspace, catálogo, biblioteca, mural, pessoas, busca | +40–60% por assento. É a camada que todo funcionário usa, não só o operacional — **multiplica assentos faturáveis** |
| **Workspace AI** | Assistente, briefing, explique, captura de conhecimento | Add-on por assento + créditos. Margem controlada por teto |
| **Compliance** | Leitura confirmada, evidência ISO/LGPD, certificação e bloqueio | Add-on por empresa. Vende para **auditoria e jurídico**, orçamento diferente de TI |

### 13.2 A alavanca de receita mais subestimada: assentos leves

O maior ganho não é cobrar mais por usuário existente — é que o Workspace torna **toda a empresa** usuária, não só a operação. Um assento leve (só portal, sem módulo) a preço baixo, vendido para 100% do headcount, geralmente supera a receita do assento operacional pesado. É exatamente o movimento que a ServiceNow fez com o Employee Center.

### 13.3 Portal do cliente como produto

O mesmo Workspace, preset "Cliente", com marca do cliente. Vira:
- **Diferencial de venda** do iConnect ("seu cliente tem portal próprio")
- **Linha de receita** própria (white-label por cliente final)
- **Retenção** — cliente com portal ativo troca de fornecedor com muito mais atrito

### 13.4 Marketplace e conectores (V3)
Conector de M365, Google, folha, ERP e banco como itens cobrados. Além de receita, cria dependência e barreira de saída.

### 13.5 O que realmente diferencia contra cada concorrente

| Concorrente | A força deles | Onde o iConnect ganha |
|---|---|---|
| **Microsoft 365 / Viva** | Distribuição, e-mail, arquivos | Não conhece a operação. Zero noção de OS, técnico, SLA, escala |
| **ServiceNow Employee Center** | ESM maduro, enterprise | Preço, tempo de implantação (meses × semanas) e realidade brasileira. Não tem FSM de campo integrado nesse patamar |
| **Atlassian Home** | Excelente para engenharia | Não serve operação de campo nem RH |
| **Salesforce** | CRM e ecossistema | Custo, complexidade, e nada de operação de serviço em campo |
| **Intranets nacionais** | Preço | Não têm IA real, não têm operação, não têm design |
| **RH SaaS (Gupy, Senior…)** | Profundidade em RH | Não têm operação nem service desk |

> **A frase de posicionamento:** *"O único workspace corporativo que sabe onde seu técnico está, se a certificação dele está válida e quanto a OS dele custou."*

---

## 14. Recomendações finais

### 14.1 As sete decisões que definem o projeto

1. **Escolher a tese estreita.** "Workspace da empresa que opera em campo", não "intranet premium". A ambição ampla se conquista depois; começar amplo garante não chegar.

2. **Construir a identidade organizacional primeiro.** Pessoa, organograma, papel com escopo e vigência, delegação. Sem isso, nada em §6 e §9 é possível. É a única fase sem entrega visível — e é a única inegociável.

3. **Endurecer o tenancy antes do primeiro dado de RH.** Testes de isolamento no CI e manager que exige escopo. Este é o risco de existência do produto.

4. **Um assistente, não dez.** Skill packs invisíveis. A persona aparece na citação da resposta, nunca como pergunta ao usuário.

5. **Conteúdo antes de IA.** E resolver o conteúdo com §11.9 (captura passiva), não com um projeto de documentação que nunca termina.

6. **Casca visual nova e isolada.** Aurora no app `workspace`, sem herdar Material Dashboard. Módulos existentes permanecem. Migração por atração.

7. **Não construir LMS nem HRIS.** Construir a fatia que liga aprendizagem e RH à **operação** — certificação que bloqueia escala, offboarding que revoga acesso. É onde está a defensabilidade.

### 14.2 As duas features que eu construiria primeiro se só pudesse escolher duas

1. **⌘K com busca federada** — é o que faz o produto "parecer internacional" em 3 segundos de demonstração, e é o que gera uso diário.
2. **Aprovações com contexto orçamentário** — é o que faz diretoria e gerência abrirem o portal todo dia, e é o que justifica o preço.

Tudo o mais pode esperar. Essas duas, juntas, já entregam a promessa central: *resolver sem abrir o sistema*.

### 14.3 Como saber que está funcionando

| Métrica | Meta MVP | Por quê |
|---|---|---|
| % de acessos ao iConnect que passam pelo Workspace | ≥60% | Prova que virou a porta de entrada |
| % de solicitações internas nascidas no catálogo | ≥40% | Prova que substituiu e-mail e WhatsApp |
| Tarefas concluídas **sem sair** do Workspace | ≥50% | Prova que não é portal de links |
| Tempo médio de aprovação | −50% | O ganho mais visível para a diretoria |
| Taxa de leitura confirmada de comunicado obrigatório | ≥90% em 72h | O KPI que vale dinheiro em auditoria |
| DAU/MAU | ≥0,5 | Abaixo disso, o portal está morrendo |
| Resposta útil do assistente (com fonte) | ≥70% | Abaixo disso, desligar até haver conteúdo |

### 14.4 O que eu tiraria do escopo hoje, sem hesitar

Gamificação e ranking · vagas e indique-um-amigo · plano de carreira · curtidas com contagem pública · funcionário-destaque votado · autoria de curso (SCORM/vídeo) · cálculo de folha, ponto e banco de horas · os dez assistentes separados · homes 100% personalizáveis · a maior parte dos 18 widgets originais.

Cada item removido é orçamento devolvido para as duas features de §14.2 — que é onde o produto realmente se decide.

---

*Documento vivo. Revisar ao fim de cada fase do roadmap.*
