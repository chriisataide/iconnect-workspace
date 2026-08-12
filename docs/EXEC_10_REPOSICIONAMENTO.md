# Execução · Etapa 10 — Reposicionamento

> **Documento de revisão.** Corrige a premissa de posicionamento das Etapas 1–9 sem descartá-las. Onde este documento contradiz um anterior, **este vence** — e a contradição está nomeada, com o trecho de origem, para que ninguém precise adivinhar qual versão vale.
>
> **12 de agosto de 2026** · Etapa 10 de 10 · **Decidido, não em consulta**

---

## Sumário

- [10.1 A decisão](#101-a-decisão)
- [10.2 A premissa corrigida — onde ela entrou](#102-a-premissa-corrigida--onde-ela-entrou)
- [10.3 A tese substituta](#103-a-tese-substituta)
- [10.4 A fronteira: destino e provedor](#104-a-fronteira-destino-e-provedor)
- [10.5 Itens que migram para a Platform](#105-itens-que-migram-para-a-platform)
- [10.6 Parâmetros decididos](#106-parâmetros-decididos)
- [10.7 Correções por documento](#107-correções-por-documento)
- [10.8 Os 24 módulos da nova lista](#108-os-24-módulos-da-nova-lista)
- [10.9 O que foi recusado, e por quê](#109-o-que-foi-recusado-e-por-quê)
- [10.10 Ondas reordenadas](#1010-ondas-reordenadas)
- [10.11 ADRs novos e revisados](#1011-adrs-novos-e-revisados)

---

## 10.1 A decisão

O produto se chama **iConnect Workspace**. E são **dois produtos** no mesmo ecossistema, não uma camada sobre o outro:

> **O iConnect Workspace organiza a vida corporativa da empresa.**
> **O iConnect Platform organiza toda a operação de atendimento aos clientes.**

Toda decisão de produto passa por essa frase. Funcionalidade que serve ao **cliente da empresa** é Platform. Funcionalidade que serve a **quem trabalha na empresa** é Workspace.

O nome não é novo no material: este repositório já tinha [`BLUEPRINT_ICONNECT_WORKSPACE.md`](BLUEPRINT_ICONNECT_WORKSPACE.md), o app Django sempre se chamou `workspace`, as rotas sempre foram `/workspace/` e o domínio no inventário sempre foi `WKS`. Nas nove etapas de execução, a palavra "Portal" aparece **duas vezes no total**. Era o **código** que ainda dizia Portal na cara do usuário — corrigido em `d9738a4`.

---

## 10.2 A premissa corrigida — onde ela entrou

A premissa a corrigir **não é** "o Workspace é dono do dado de operação". Isso nunca foi escrito; a Etapa 3 §3.1.1 e o Blueprint §3.1 dizem o contrário, com regra e teste de isolamento arquitetural.

A premissa a corrigir é **qual é o diferencial competitivo do Workspace**. As Etapas 1–9 responderam "a operação", em dois lugares centrais:

### Origem 1 · [Blueprint §1.2](BLUEPRINT_ICONNECT_WORKSPACE.md), discordância nº 2

> Posicionamento recomendado: **"O Workspace da empresa que opera em campo."** Não é uma intranet com módulo de operação; é a operação com uma camada de trabalho humano em volta.

### Origem 2 · [CPO_REVIEW §A.8](CPO_REVIEW_ICONNECT.md)

As cinco funcionalidades **promovidas** ao MVP foram: certificação que bloqueia escala, documentos pessoais com validade, escala e sobreaviso, custo real da OS, detecção de serviço fora do contrato. Com a conclusão explícita:

> O padrão das promoções: todas as cinco usam dado que **só o iConnect tem**. Nenhuma delas é "portal". Isso não é coincidência — é a tese do produto se revelando.

### A consequência de corrigir

Quatro dessas cinco são Platform pela nova fronteira. Removê-las **apaga a resposta das Etapas 1–9 para "por que este produto ganha?"** e deixa o Workspace competindo de frente com Microsoft 365, Google Workspace e ServiceNow — a briga que o próprio Blueprint §1.2 classificou como imperdível:

> Comparar-se com Microsoft 365 e Google Workspace é escolher a briga que não dá para vencer: eles têm e-mail, arquivos, vídeo, identidade e distribuição gratuita embutida.

Por isso a §10.3 existe. Reposicionamento sem tese substituta é escopo sem norte.

---

## 10.3 A tese substituta

> **O Workspace corporativo de quem não trabalha sentado.**

RH, Financeiro e Compras genéricos são **commodity** — a Microsoft entrega melhor, mais barato e já instalado. O que não é commodity é a vida corporativa de quem está em campo:

| O que a M365 pressupõe | O que este vertical tem |
|---|---|
| Mesa, monitor, e-mail | Celular, 3G instável, uma mão livre |
| Solicitação de material de escritório | Requisição de EPI com CA e validade |
| Treinamento como benefício | Reciclagem de NR que, vencida, tira a pessoa da escala |
| Reembolso de almoço com cliente | Reembolso de deslocamento, pedágio e diária de campo |
| Aprovação por hierarquia de cargo | Aprovação por faixa de valor **e** por centro de custo de base |

O diferencial não morre com o reposicionamento; ele muda de natureza:

- **Antes:** o Workspace *faz* a operação.
- **Agora:** o Workspace *conhece* a operação.

Conhecer sem possuir é exatamente o que o contrato de provider ([Etapa 3 §3.1.1](EXEC_03_MODULOS.md)) já implementa.

---

## 10.4 A fronteira: destino e provedor

A regra "o iConnect é apenas um aplicativo dentro do Workspace" descreve **uma** das duas relações. Separá-las evita uma leitura que quebraria o produto.

```
┌─────────────────────────────┐              ┌─────────────────────────────┐
│  iConnect Workspace         │              │  iConnect Platform          │
│  POSSUI                     │              │  POSSUI                     │
│                             │              │                             │
│  Identidade e organograma   │              │  Ordens de serviço e SLA    │
│  Cadeia de aprovação        │              │  Escala e sobreaviso        │
│  Catálogo de serviços       │              │  Clientes e contratos       │
│  Compromisso orçamentário   │              │  Equipamentos e estoque     │
│  Conteúdo e comunicados     │              │  Custo real do atendimento  │
│  Anexos do colaborador      │              │  Técnicos e habilitações    │
└─────────────────────────────┘              └─────────────────────────────┘
              │                                            │
              │  DESTINO ─── um tile entre outros ─────────┤
              │                                            │
              └── PROVEDOR ◄── contexto via provider ──────┘
                  (workspace/providers/)
```

**Como destino:** o iConnect Platform é um tile na faixa Aplicativos, sem destaque, sem primeira posição. Implementado e travado por teste (`workspace/tests/test_posicionamento.py`).

**Como provedor:** o `dashboard` responde ao Workspace sobre orçamento e realizado por centro de custo. Item de menu não alimenta nada.

### O caso que decide a distinção

Um técnico pede R$ 3.200 de adiantamento de viagem. A barra de aprovação mostra realizado, comprometido e este pedido contra o orçamento do centro de custo dele. Esse número vem do `dashboard` via `OrcamentoProvider`. **Se o iConnect fosse apenas um tile, o Workspace não teria como mostrá-lo — e a aprovação volta a ser carimbo.**

> **Regra derivada:** o Workspace **não possui** dado de operação, mas **lê** contexto de operação, sempre por contrato de provider, nunca por consulta a model de outro domínio. É a regra 4 da [Etapa 3 §3.1.1](EXEC_03_MODULOS.md), inalterada — o que muda é que ela deixa de ser detalhe técnico e passa a ser a expressão da fronteira entre dois produtos.

---

## 10.5 Itens que migram para a Platform

Seis itens do V1.0 definido na [Etapa 2](EXEC_02_MVP.md) deixam o escopo do Workspace.

| ID | Item | Destino | Observação |
|---|---|---|---|
| OPS-001 | Escala e sobreaviso | **Platform** | O Workspace passa a *ler* a escala para o widget "quem está de plantão" |
| REV-001 | Escopo contratual tipificado | **Platform** | Receita de cliente. Fronteira nítida |
| REV-002 | Tabela de preço por serviço | **Platform** | Idem |
| FIN-003 | Consumo de material na OS | **Platform** | É sobre `OrdemServico` |
| FIN-004 | Custo real da OS | **Platform** | Idem |
| PPL-005 | Bloqueio de despacho por certificação vencida | **Platform** | Ver divisão abaixo |

### A divisão de PPL-004/005 — certificação

Este item merece atenção porque a fronteira passa **dentro** dele:

| Metade | Onde fica | Por quê |
|---|---|---|
| Vigência, alerta de vencimento, inscrição em reciclagem, "minhas certificações" | **Workspace** | É a vida corporativa da pessoa: ela precisa saber que a NR-10 dela vence em 15 dias |
| O **bloqueio** no despacho de OS | **Platform** | É regra de operação, aplicada em `fsm/services/dispatch.py`, sobre atendimento a cliente |

O Workspace avisa; a Platform bloqueia. As duas metades conversam por evento, não por consulta direta.

### Registro de erro próprio

Eu propus **Habilitações** como próximo módulo do Workspace em duas mensagens consecutivas. Estava errado duas vezes:

1. **Não é Workspace.** É `fsm/services/dispatch.py` — motor de operação.
2. **Não tem dado.** `fsm.Skill` tem **zero registros**; a vigência seria construída sobre uma tabela vazia.

O segundo motivo é o mais instrutivo: a verificação de dado precede a decisão de escopo.

### O ganho colateral

A [Etapa 7 §7.11](EXEC_07_BACKLOG.md) registrava a Onda 5 como gargalo estrutural:

> A Onda 5 é o gargalo estrutural. Busca, Pessoas e Escala não paralelizam bem entre si — Escala depende de Pessoas, que depende de Identidade.

Escala sai do escopo. **O gargalo afrouxa sem cortar nada de valor** — e sem que ninguém precise negociar prazo.

---

## 10.6 Parâmetros decididos

Quatro decisões que estavam bloqueando implementação.

### Suíte corporativa: Microsoft 365

Consequências diretas, e todas são **redução** de escopo:

| Item | Decisão |
|---|---|
| Agenda | **Integrar** via Graph, não construir. Ninguém ganha construindo calendário |
| Documentos Recentes | Idem — vem do OneDrive/SharePoint |
| Conta de usuário | Nasce do **SSO no primeiro login**. O CSV de organograma apenas pendura estrutura em quem já entrou |
| Conversor de arquivos | Recusado (§10.9). Já existe no Office |

### Teto de aprovação por faixa de valor

Substitui os R$ 10.000 que apareciam em [Blueprint §9](BLUEPRINT_ICONNECT_WORKSPACE.md) e nas telas — **eram chute, não decisão**.

| Faixa | Quem aprova |
|---|---|
| até R$ 50.000 | gestor direto |
| R$ 50.000 – R$ 300.000 | + diretoria |
| acima de R$ 300.000 | + sócios |

**Faixas cumulativas, não excludentes.** Um pedido de R$ 400.000 passa pelos três degraus, na ordem. Sócio aprovando sem o gestor da área ter visto é como a despesa some do orçamento de quem responde por ela.

Exigiu um papel `socios` no IDN, que não existia — os 12 papéis paravam em `diretoria`. Ele nasce **sem** as permissões administrativas da diretoria: última instância com poder de administração vira superusuário de fato, e o degrau que existe para conferir passa a poder alterar o que confere.

Configurado por `python manage.py semear_regras_aprovacao --aplicar` e não por cliques no admin: quando alguém perguntar em dezembro por que uma compra de R$ 80.000 subiu, a resposta tem de estar no git com data e autor.

### Analytics Pessoal: dado individual só para a própria pessoa

Gestão vê apenas agregado, sem granularidade individual.

**A decisão vale desde a coleta, não desde a exibição.** Analytics individual visível ao gestor é vigilância, e seria o motivo pelo qual as pessoas param de usar o Workspace. Depois é irreversível: o dado já foi coletado sob outra promessa.

> **Regra de implementação:** qualquer métrica de uso pessoal tem escopo de leitura `proprio`, nunca `equipe`.

### Organograma inicial

Seis pessoas em `docs/exemplos/organograma-inicial.csv`, cobrindo os quatro degraus da cadeia e as duas formas de escopo (`equipe` pelo organograma, `unidade` pela lotação). Nomes **de cargo, não de pessoa**: o arquivo vai para o git, e planilha de RH com gente real num repositório é vazamento esperando um clone.

---

## 10.7 Correções por documento

Nenhum documento é descartado. Onde há contradição, o trecho abaixo diz o que vale.

### [BLUEPRINT_ICONNECT_WORKSPACE.md](BLUEPRINT_ICONNECT_WORKSPACE.md)

| Trecho | Correção |
|---|---|
| §1.2 discordância nº 2 — "O Workspace da empresa que opera em campo" | Substituída pela tese de §10.3. O eixo do vertical continua; o Workspace *conhece* a operação em vez de *fazê-la* |
| §1.3 veredito — "Portal como porta de entrada única" | Vale. Só o nome muda |
| §5.1 mapa de navegação — 6º destino **"📊 Operação"** | Passa a **"Aplicativos"**. O iConnect Platform mora dentro dele. "Operação" como destino de primeiro nível era a premissa antiga aparecendo na arquitetura de informação |
| §6 estrutura da Home | Ordem corrigida: **Meu dia → Minha empresa → Aplicativos**. Aplicativos por último |
| §9 fluxo de aprovação — "excede o limite de R$ 10.000" | Teto real em §10.6 |
| 21 ocorrências de "Portal" | Leia-se "Workspace" |

### [CPO_REVIEW_ICONNECT.md](CPO_REVIEW_ICONNECT.md)

| Trecho | Correção |
|---|---|
| §A.8 — as 5 promoções ao MVP | Quatro migram para a Platform (§10.5). A análise de **valor** de cada uma continua correta e válida — o que muda é em qual produto ela é entregue |
| §0 — tenancy inexistente | **Inalterado e ainda o achado mais grave do material.** Não é afetado pelo reposicionamento |

### [EXEC_01_ESCOPO_E_DEPENDENCIAS.md](EXEC_01_ESCOPO_E_DEPENDENCIAS.md)

| Trecho | Correção |
|---|---|
| §1.3 inventário de 139 itens, domínios OPS e REV | Os domínios continuam existindo; **saem do escopo do Workspace** (§10.5) |
| §1.5 mapeamento dos 15 módulos | Método confirmado e reaplicado aos 24 novos em §10.8 |
| L1–L9 lacunas de dado | **Todas confirmadas.** L3 (Skill sem validade) e L4 (sem Escala) passam a ser lacunas da Platform |
| §1.6 caminho crítico | IDN → APR → SVC permanece. A ramificação de Escala sai |

### [EXEC_02_MVP.md](EXEC_02_MVP.md)

| Trecho | Correção |
|---|---|
| §2.4 — V1.0 de 58 itens | Passa a **52**. Os 6 de §10.5 saem |
| §2.3 — "fundação sem tela entra mesmo assim, por prazo de maturação" | **Princípio mantido, e é o mais valioso do documento.** Aplica-se agora ao modelo de conteúdo, não ao escopo contratual |
| OPS-001, REV-001/002, FIN-003/004 no V1.0 | Migram. A justificativa de maturação passa a valer no roadmap da Platform |

### [EXEC_03_MODULOS.md](EXEC_03_MODULOS.md)

| Trecho | Correção |
|---|---|
| ADR-001 — evoluir `PerfilUsuario`/`UserRole` | **Vale integralmente.** Não é sobre posicionamento |
| §3.1.1 contrato `WorkspaceProvider` | **Vale, e ganha importância:** deixa de ser detalhe técnico e passa a expressar a fronteira entre dois produtos |
| Especificações de OPS e REV | Corretas; passam a ser especificação de módulo da Platform |
| "13 domínios" | 11 no Workspace + 3 novos (§10.8); OPS e REV vão para a Platform |

### [EXEC_04_PRD.md](EXEC_04_PRD.md) · [EXEC_07_BACKLOG.md](EXEC_07_BACKLOG.md)

Stories e PRDs de OPS-001, REV-001/002, FIN-003/004 e PPL-005 continuam válidos como especificação — **mudam de backlog**, não de conteúdo. Estimativas preservadas.

### [EXEC_05_ARQUITETURA.md](EXEC_05_ARQUITETURA.md) · [EXEC_06_DESIGN_SYSTEM.md](EXEC_06_DESIGN_SYSTEM.md)

**Inalterados.** Camadas, regras de dependência, matriz de acoplamento, tokens Aurora, densidade e acessibilidade não dependem de posicionamento. O design system continua sendo `--au-*`, navy `#2e3192` + crimson `#ed3a5b`.

### [EXEC_08_ROADMAP.md](EXEC_08_ROADMAP.md)

| Trecho | Correção |
|---|---|
| §8.2 V1.0 "Meu dia começa aqui" | **Nome perfeito e mantido** — descreve exatamente a ordem nova da home |
| §8.2 — "Escala é a âncora nº 2" | Deixa de ser âncora do Workspace. As âncoras passam a ser aprovação, comunicado obrigatório e catálogo |
| §8.5 gargalo da Onda 5 | Afrouxa (§10.5) |
| Ondas | Reordenadas em §10.10 |

---

## 10.8 Os 24 módulos da nova lista

Mesmo método do [EXEC_01 §1.5](EXEC_01_ESCOPO_E_DEPENDENCIAS.md), que reduziu 15 módulos propostos a 13 domínios. **Módulo é fronteira de responsabilidade, não item de menu.**

| Módulo pedido | Destino | Situação |
|---|---|---|
| RH | `PPL` | Módulo próprio |
| Financeiro | `FIN` | Módulo próprio, sem custo de atendimento |
| Compras | `SVC` + `APR` | Catálogo e cadeia. **Já funciona** |
| Documentação | `CNT` | Módulo próprio |
| Comunicação Interna | `COM` | Módulo próprio |
| Pesquisa Global / Busca Universal / Command Palette | `SRC` | Módulo próprio. São três nomes do mesmo domínio |
| IA Corporativa / Assistente Virtual | `AIC` | Módulo próprio, **depois do conteúdo** (§10.9) |
| Central de Notificações | `WKS` | Capacidade da casca |
| **Workflow Center** | `APR` | Dissolve — é o motor de aprovação com outra fachada. Já construído |
| **Normativos** | `CNT` | Dissolve — é um tipo de documento |
| **Universidade Corporativa** | `CNT` + `PPL` | Dissolve — conteúdo + certificação. Decisão já registrada no EXEC_01 §1.5 |
| **Suprimentos** | `SVC` | Dissolve — requisição é catálogo; estoque é Platform |
| **Ativos Corporativos** | `PPL` | Dissolve — "meus ativos" é leitura via provider |
| **Controladoria** | `FIN` | Dissolve — é recorte de permissão sobre FIN |
| **Dashboard Executivo** | `WKS` | Dissolve — é um **preset de home**, não um módulo |
| **Pesquisa de Satisfação** | `COM` | Dissolve — tipo de publicação até haver uso comprovado |
| **Ferramentas Corporativas** | `WKS` | Dissolve — é o launcher |
| **Links Úteis** | `WKS` | Dissolve — é o launcher. Já existe em `workspace/launcher.py` |
| **Central de Downloads** | `WKS` | Dissolve — widget sobre o modelo de anexo já construído |
| **Analytics Pessoal** | `WKS` | Dissolve — com a restrição de privacidade de §10.6 |
| Facilities | `SVC` + `RES` | Categoria de catálogo + reserva |
| **Reserva de Recursos** | `RES` *(novo)* | Salas, veículos, equipamentos. Pequeno e real |
| **Correspondências** | `COR` *(novo)* | Específico do vertical. Pequeno e real |
| **Plano de Metas** | `MET` *(novo)* | V2. É um produto próprio |
| Conversor de Arquivos | — | **Recusado** (§10.9) |
| Agenda | — | **Integração**, não construção (§10.6) |
| iConnect Platform | `WKS` | Um tile no launcher, sem destaque |

> **Resultado: 24 pedidos → 11 domínios existentes, 3 novos, 11 dissolvidos em capacidade, 2 recusados.**

O motivo da deduplicação é o mesmo do Blueprint §1.2, e continua verdadeiro: construir muitos módulos em paralelo entrega muitos módulos medianos, e **um workspace mediano é pior que nenhum**, porque queima a confiança do usuário na primeira semana e ele volta para o WhatsApp e a planilha.

---

## 10.9 O que foi recusado, e por quê

### Conversor de arquivos

Processamento de arquivo arbitrário no servidor corporativo. Parser de imagem e de PDF é superfície clássica de execução remota — e o ganho é uma função usada duas vezes por pessoa por ano, que já existe no Office e no Drive. Se ficar, fica como **link para ferramenta externa**, não como código que nós mantemos e defendemos.

### Central de Downloads e Links Úteis como módulos

Ambos são widgets sobre coisas que já existem. Um módulo carrega admin, permissão, teste, tela e treinamento; um widget não.

### Assistente de conhecimento agora

Reafirma o Blueprint §1.2 discordância nº 7, com a evidência de hoje: o RAG indexa **exclusivamente** `ArtigoConhecimento`, a base de helpdesk. Não existe um POP, uma política ou um normativo no sistema.

Assistente sobre biblioteca vazia produz uma impressão só — *"a IA daqui não sabe nada"* — e ela é praticamente irreversível.

> **Ordem obrigatória:** modelo de conteúdo → ingestão e índice → busca → **depois** IA generativa.

**Mas metade vem agora.** O **assistente de ação** — *"quero solicitar férias"* → inicia o fluxo — é casamento de intenção com item de catálogo sobre 19 registros. Não precisa de RAG, funciona no primeiro dia, e é a metade que o usuário lembra. Onda E de §10.10.

### Dez widgets numa home que tem três fontes de dado

Medido em 12/08/2026:

| Fonte | Registros | Consequência |
|---|---:|---|
| `identidade.Lotacao` | 6 *(semeado hoje)* | Antes disto, toda cadeia de aprovação era ficção |
| `fsm.OrdemServico` | 0 | Widget de operação não tem o que mostrar |
| `fsm.Skill` | 0 | Alerta de vencimento não tem base |
| `fsm.BaseOperacional` | 0 | Sem unidades operacionais |
| conteúdo, agenda, metas, treinamentos, correspondências | — | Modelos não existem |
| `dashboard.Ticket` · `dashboard.Cliente` | 145 · 17 | Dado real — e é Platform |

> **Princípio de produto: nenhum widget nasce vazio.** Faixa sem dado não renderiza, e a home cresce conforme as fontes ficam reais. **Uma home vazia é pior que um app launcher**, porque o launcher pelo menos funciona.

---

## 10.10 Ondas reordenadas

A regra que ordena: **nada que dependa de dado inexistente entra antes do dado.**

| | Onda | Conteúdo | Estado |
|:-:|---|---|---|
| ✓ | **Fundações** | Identidade com escopo, motor de aprovação, compromisso orçamentário, catálogo por intenção, anexos em armazenamento privado, navegação fechada | **Feito.** 100% de cobertura em `workspace` e `identidade` |
| ✓ | **A · Desbloqueio** | Organograma por CSV, cadeia com o teto real, renomeio, inversão da home | **Feito** em `d9738a4` |
| | **B · Meu dia** | A faixa que abre o Workspace, alimentada só por fontes que existem. Central de notificações | Próxima |
| | **C · Conteúdo** | Documento com dono, vigência, público-alvo e leitura obrigatória. Ingestão dos POP e normativos | Gate: 40 documentos |
| | **D · Busca universal** | Índice único com *security trimming* no `WHERE`. Objeto, ação e conhecimento no mesmo campo | Maior alavanca de percepção |
| | **E · Assistente de ação** | Intenção → fluxo do catálogo. Sem RAG | Pode anteceder C e D |
| | **F · Assistente de conhecimento** | RAG sobre o conteúdo real, *skill packs*, citação de fonte | Depende do gate de C |
| | **G · Módulos pequenos** | `RES` reserva de recursos, `COR` correspondências | Escopo estreito, um problema cada |

---

## 10.11 ADRs novos e revisados

### ADR-010 · Workspace e Platform são dois produtos

**Contexto:** a premissa anterior tratava o Workspace como camada que antecede os módulos operacionais.
**Decisão:** dois produtos no mesmo ecossistema, com fronteira por audiência — quem trabalha na empresa vs. quem é cliente dela.
**Consequência:** OPS e REV saem do escopo do Workspace. O iConnect Platform é um tile sem destaque. O contrato de provider passa a expressar a fronteira entre produtos, não só entre apps.

### ADR-011 · O Workspace lê contexto de operação, mas não o possui

**Contexto:** "apenas um aplicativo" leria-se como "nenhuma integração de dado", o que tornaria a bandeja de aprovação um carimbo.
**Decisão:** leitura por contrato de provider, sempre; propriedade do dado, nunca.
**Consequência:** `workspace/providers/` é a única travessia permitida, garantida por `test_isolamento.py`.

### ADR-012 · Nenhum widget nasce vazio

**Contexto:** a home descrita exige ~10 fontes de dado; três existem.
**Decisão:** faixa sem dado não renderiza. A home cresce com as fontes.
**Consequência:** o layout precisa ser resiliente a faixas ausentes, e cada widget declara sua fonte e o que fazer sem ela.

### ADR-013 · Conta nasce do SSO, não da planilha

**Contexto:** a empresa usa Microsoft 365, e o importador de organograma poderia criar contas.
**Decisão:** em produção, a conta nasce do primeiro login por SSO; o CSV apenas pendura estrutura organizacional. `--criar-usuarios` é opt-in explícito e cria com `set_unusable_password()`.
**Consequência:** username digitado errado não gera conta fantasma que recebe etapa de aprovação.

### ADR-014 · Métrica de uso pessoal tem escopo `proprio`

**Contexto:** Analytics Pessoal poderia ser visível ao gestor.
**Decisão:** dado individual só para a própria pessoa; gestão vê agregado.
**Consequência:** vale desde a coleta. Nenhuma métrica de uso individual recebe escopo `equipe` ou acima.

### ADR-001 a ADR-009 · Inalterados

Evoluir `PerfilUsuario`/`UserRole` em vez de criar um terceiro cadastro, casca visual isolada sem herdar Material Dashboard, contrato de provider, curto-circuito do context processor fora de `/workspace/` — todos independem de posicionamento e seguem valendo.

---

## Referência rápida

| Pergunta | Resposta |
|---|---|
| Como se chama o produto? | **iConnect Workspace** |
| E o sistema de atendimento? | **iConnect Platform** |
| Escala e sobreaviso, de quem é? | Platform. O Workspace lê |
| Quem aprova R$ 80.000? | Gestor direto **e** diretoria, nessa ordem |
| Quem aprova R$ 400.000? | Gestor, diretoria **e** sócios, nessa ordem |
| Quem vê meu Analytics Pessoal? | Só você |
| Construímos calendário? | Não. Integra com M365 |
| Quando entra o assistente de conhecimento? | Depois de 40 documentos no acervo |
