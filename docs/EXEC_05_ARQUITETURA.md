# Execução · Etapa 5 — Arquitetura

> **Documento de arquitetura.** Como o sistema se comporta em conjunto: ciclo de requisição, cache, tempo real, assíncrono, degradação e escala — além das 11 vistas arquiteturais pedidas.
>
> **Agosto/2026** · Etapa 5 de 9 · **Aguarda aprovação antes da Etapa 6**

---

## Sumário

- [5.0 Princípios e decisões (ADRs)](#50-princípios-e-decisões-adrs)
- [5.1 Arquitetura lógica](#51-arquitetura-lógica)
- [5.2 Arquitetura técnica](#52-arquitetura-técnica)
- [5.3 Arquitetura dos módulos](#53-arquitetura-dos-módulos)
- [5.4 Arquitetura de permissões](#54-arquitetura-de-permissões)
- [5.5 Arquitetura do banco de dados](#55-arquitetura-do-banco-de-dados)
- [5.6 Arquitetura das APIs](#56-arquitetura-das-apis)
- [5.7 Arquitetura de navegação](#57-arquitetura-de-navegação)
- [5.8 Arquitetura dos widgets](#58-arquitetura-dos-widgets)
- [5.9 Arquitetura do App Launcher](#59-arquitetura-do-app-launcher)
- [5.10 Arquitetura da busca global](#510-arquitetura-da-busca-global)
- [5.11 Arquitetura da IA](#511-arquitetura-da-ia)
- [5.12 Ciclo de requisição, cache e tempo real](#512-ciclo-de-requisição-cache-e-tempo-real)
- [5.13 Degradação e falhas](#513-degradação-e-falhas)
- [5.14 Escala e capacidade](#514-escala-e-capacidade)
- [5.15 Observabilidade](#515-observabilidade)
- [5.16 Implantação](#516-implantação)

---

## 5.0 Princípios e decisões (ADRs)

### Princípios

| # | Princípio | Consequência prática |
|:-:|---|---|
| 1 | **A complexidade tem que caber na cabeça de uma pessoa** | Nenhum componente de infraestrutura novo. Postgres, Redis, Celery e Channels já existem — é o que temos |
| 2 | **Renderizar no servidor é a escolha padrão** | HTMX devolve HTML. JavaScript só onde há estado de interface genuíno |
| 3 | **Degradar, nunca cair** | Falha de dependência degrada a parte afetada. A página sempre carrega |
| 4 | **Uma porta por responsabilidade** | Uma função de permissão, um índice de busca, um motor de aprovação |
| 5 | **Não tocar no que já funciona** | Extensão por FK e sinal. Zero alteração destrutiva em modelo existente |
| 6 | **O caro é a interface, não o dado** | Fundação entra cedo e barata; superfície entra sob corte |

### Decisões arquiteturais

| ADR | Decisão | Alternativa recusada | Por quê |
|---|---|---|---|
| **ADR-001** | `PerfilUsuario` evolui in-place; conceitos novos em app novo | Criar `Pessoa` do zero | Evita um terceiro cadastro da mesma pessoa ([Etapa 3](EXEC_03_MODULOS.md)) |
| **ADR-002** | **Alpine.js na distribuição CSP** (`@alpinejs/csp`) | Alpine padrão + `unsafe-eval` | A CSP em produção **não tem `unsafe-eval`** ([security.py:234](../dashboard/utils/security.py)). Alpine padrão usa `new Function` e quebraria. Afrouxar a CSP para acomodar uma biblioteca é trocar segurança por conveniência |
| **ADR-003** | **Reusar `ws/notifications/`** com novos tipos de evento | Criar `ws/workspace/` | Uma conexão WebSocket por usuário em vez de duas. Daphne comporta ~1.000 conexões por worker; dobrar conexões corta a capacidade pela metade |
| **ADR-004** | Cache por **geração** (contador Redis por domínio + pessoa) | Invalidação por chave explícita | `INCR` é atômico e elimina toda a classe de bugs de invalidação. Chave velha simplesmente deixa de ser consultada |
| **ADR-005** | Permissão resolvida **por request**, nunca entre requests | Cache de permissão em Redis | Mudança de papel precisa valer na requisição seguinte. Cache entre requests cria janela de privilégio indevido |
| **ADR-006** | Widgets carregam **independentes**, com timeout individual | Renderizar tudo na view da home | Um provider lento derrubaria a página inteira |
| **ADR-007** | Busca em **PostgreSQL** (FTS + GIN, e pgvector no V1.1) | Elasticsearch / OpenSearch | Um componente a menos para operar, monitorar e sincronizar. O volume não justifica |
| **ADR-008** | **Sem SPA e sem API-first** para o Workspace | React/Vue com API JSON | O Workspace é conteúdo, não aplicação de estado complexo. HTMX entrega a mesma sensação com uma fração do custo |
| **ADR-009** | Middlewares do Workspace só rodam sob `/workspace/` | Middleware global | Não penalizar as 155 telas existentes com trabalho que não usam |

---

## 5.1 Arquitetura lógica

### Visão em camadas

```
╔══════════════════════════════════════════════════════════════════════════╗
║  EXPERIÊNCIA                                                              ║
║  ┌────────────┐ ┌───────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐ ║
║  │ AppShell   │ │ Home      │ │ Command  │ │ Bandeja │ │ Biblioteca / │ ║
║  │            │ │ 3 zonas   │ │ Bar ⌘K   │ │ APR     │ │ Mural / SVC  │ ║
║  └────────────┘ └───────────┘ └──────────┘ └─────────┘ └──────────────┘ ║
╚══════════════════════════════════════════════════════════════════════════╝
                                    ▲  HTML (HTMX) · eventos (WS)
╔══════════════════════════════════════════════════════════════════════════╗
║  APLICAÇÃO — orquestração, sem regra de domínio                           ║
║  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐║
║  │ WidgetRuntime│ │ SearchQuery  │ │ Navigation   │ │ NotificationHub  │║
║  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────────┘║
╚══════════════════════════════════════════════════════════════════════════╝
                                    ▲
╔══════════════════════════════════════════════════════════════════════════╗
║  DOMÍNIO — a regra de negócio mora aqui, e só aqui                        ║
║  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐      ║
║  │  APR   │ │  SVC   │ │  CNT   │ │  COM   │ │  PPL   │ │  OPS   │      ║
║  │ motor  │ │catálogo│ │conteúdo│ │comunic.│ │pessoas │ │ escala │      ║
║  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘      ║
║  ┌────────┐ ┌────────┐                                                   ║
║  │  FIN   │ │  REV   │        ← domínios existentes: Helpdesk, FSM,      ║
║  │ custo  │ │contrato│           Estoque, Equipamentos, Financeiro       ║
║  └────────┘ └────────┘                                                   ║
╚══════════════════════════════════════════════════════════════════════════╝
                                    ▲
╔══════════════════════════════════════════════════════════════════════════╗
║  FUNDAÇÃO — atravessa tudo                                                ║
║  ┌──────────────┐ ┌────────────┐ ┌──────────┐ ┌─────────┐ ┌───────────┐ ║
║  │ IDN          │ │ Autorização│ │ Auditoria│ │ Flags   │ │ Governança│ ║
║  │ identidade   │ │ pode()     │ │          │ │         │ │ de IA     │ ║
║  └──────────────┘ └────────────┘ └──────────┘ └─────────┘ └───────────┘ ║
╚══════════════════════════════════════════════════════════════════════════╝
```

### As três regras de dependência

```
Experiência  ──▶  pode chamar Aplicação e Domínio
Aplicação    ──▶  pode chamar Domínio (via Provider) e Fundação
Domínio      ──▶  pode chamar apenas Fundação
Fundação     ──▶  não chama ninguém
```

**Proibido, e verificado em revisão:**
- Domínio importando de Experiência ou Aplicação
- Um domínio importando model de outro domínio (só via serviço ou provider)
- Experiência consultando model diretamente (só via serviço ou provider)

---

## 5.2 Arquitetura técnica

### Topologia de execução

```
                        ┌─────────────┐
   Navegador  ─────────▶│    NGINX    │  TLS · estáticos · buffer de upload
   App nativo ─────────▶└──────┬──────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
      ┌───────────────┐                 ┌───────────────┐
      │   Daphne      │  HTTP + WS      │   Daphne      │   (N réplicas)
      │   (ASGI)      │◀───────────────▶│   (ASGI)      │
      └───────┬───────┘                 └───────┬───────┘
              │                                 │
              └────────────┬────────────────────┘
                           ▼
         ┌─────────────────┴─────────────────┐
         ▼                 ▼                 ▼
   ┌──────────┐      ┌──────────┐      ┌──────────────┐
   │PostgreSQL│      │  Redis   │      │   Celery     │
   │  FTS+GIN │      │ cache ·  │      │ worker+beat  │
   │ (pgvector│      │ sessão · │      │              │
   │  no V1.1)│      │ channels │      └──────┬───────┘
   └──────────┘      │ · broker │             │
         ▲           └──────────┘             │
         └────────────────────────────────────┘
```

**Nada novo.** Todos os componentes já estão no `docker-compose.yml`.

### Stack por camada

| Camada | Tecnologia | Nota |
|---|---|---|
| **Servidor** | Django 5.2 + Daphne (ASGI) | Existente |
| **Templates** | Django Templates | Existente |
| **Interatividade** | **HTMX 2.x** | Novo. Sem build; um `<script>` com nonce |
| **Estado de UI** | **Alpine.js (build CSP)** | Novo. Ver [ADR-002](#50-princípios-e-decisões-adrs) |
| **Estilo** | **Tailwind CSS** | Novo, **restrito a `workspace/`** |
| **Banco** | PostgreSQL 15+ | Existente. Requer `btree_gist` (escala) e, no V1.1, `pgvector` |
| **Cache / sessão / broker / channels** | Redis | Existente, alias `default`, prefixo `iconnect` |
| **Assíncrono** | Celery + Beat | Existente |
| **Tempo real** | Channels sobre Redis | Existente, reusando `ws/notifications/` |

### Estrutura de diretórios

```
identidade/                        # app novo — fundação
  models.py                        # Unidade, Departamento, Papel, AtribuicaoPapel,
                                   # Delegacao, Ausencia, Certificacao, ConflitoSincronizacao
  services/
    autorizacao.py                 # pode() — a única porta
    sincronizacao.py               # conector + reconciliação
    habilitacao.py                 # pode_executar(tecnico, os)  ← hook do FSM
    busca.py                       # subjects_de(pessoa)
  migrations/
  tests/

workspace/                         # app novo — superfície + motores
  models/
    aprovacao.py  catalogo.py  conteudo.py  comunicacao.py
    busca.py      widget.py    plataforma.py
  services/
    aprovacao.py  solicitacao.py  publicacao.py  indexacao.py  widgets.py
  providers/
    base.py                        # WorkspaceProvider (ABC)
    registry.py
  views/
    home.py  widget.py  aprovacao.py  servico.py  conteudo.py
    comunicado.py  busca.py  perfil.py
  middleware.py                    # WorkspaceContext · ComunicadoCritico
  templatetags/
  templates/workspace/
    _shell.html  home.html
    apr/  svc/  cnt/  com/  src/  wks/
  static/workspace/
    src/aurora.css                 # entrada Tailwind
    dist/aurora.css                # gerado
    js/htmx.min.js  js/alpine-csp.min.js  js/workspace.js
  tailwind.config.js
  tests/

dashboard/                         # extensões
  models/receita.py                # TipoServico, EscopoContrato, TabelaPreco
  models/copilot.py                # + FeedbackIA, ConsumoIA, TetoIA
  models/base.py                   # PerfilUsuario evoluído
  services/precificacao.py

fsm/                               # extensões
  models_escala.py                 # Escala, TurnoEscala
  models_consumo.py                # ConsumoMaterialOS
  services/dispatch.py             # + chamada a habilitacao.pode_executar()
```

### Middlewares

Dois novos, **ambos com curto-circuito fora de `/workspace/`** ([ADR-009](#50-princípios-e-decisões-adrs)):

```python
MIDDLEWARE = [
    ...                                                  # os 15 existentes, na ordem atual
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    ...
    "workspace.middleware.WorkspaceContextMiddleware",    # ← novo
    "workspace.middleware.ComunicadoCriticoMiddleware",   # ← novo
    "axes.middleware.AxesMiddleware",                     # permanece por último
]
```

| Middleware | Faz | Custo |
|---|---|---|
| `WorkspaceContextMiddleware` | Resolve `request.pessoa` e cria o cache de permissão do request | 1 query (`select_related`), só sob `/workspace/` |
| `ComunicadoCriticoMiddleware` | Redireciona se houver crítico não confirmado | 1 leitura de cache; consulta ao banco só em cache miss |

```python
class WorkspaceContextMiddleware:
    def __call__(self, request):
        if not request.path.startswith("/workspace/"):
            return self.get_response(request)          # ADR-009
        if request.user.is_authenticated:
            request.pessoa = (PerfilUsuario.objects
                              .select_related("unidade", "departamento_fk",
                                              "gestor", "centro_custo")
                              .filter(user=request.user).first())
            request.perm_cache = {}                    # ADR-005 — vive só neste request
        return self.get_response(request)
```

---

## 5.3 Arquitetura dos módulos

### Acoplamento permitido

```
                    ┌─────────────────────────────────┐
                    │            IDN                  │  ← ninguém depende de nada
                    │  Pessoa · Papel · Escopo        │     para chegar aqui
                    └────┬───┬───┬───┬───┬───┬────────┘
          ┌──────────────┘   │   │   │   │   └──────────────┐
          ▼                  ▼   ▼   ▼   ▼                  ▼
     ┌────────┐        ┌────────┐ │ ┌────────┐        ┌──────────┐
     │  APR   │◀───────│  SVC   │ │ │  PPL   │───────▶│   OPS    │
     └───┬────┘        └────────┘ │ └───┬────┘        └────┬─────┘
         │                        │     │                  │
         │                   ┌────▼───┐ │                  │
         │                   │  CNT   │ │                  │
         │                   └───┬────┘ │                  │
         │                       ▼      │                  │
         │                   ┌────────┐ │                  │
         │                   │  COM   │ │                  │
         │                   └────────┘ │                  │
         └───────────┬──────────────────┴──────────────────┘
                     ▼
              ┌─────────────┐        ┌──────┐      ┌──────┐
              │     WKS     │◀───────│ SRC  │      │ REV  │◀──── FIN
              └─────────────┘        └──────┘      └──────┘
                     ▲                   ▲
                     └───── AIC ─────────┘   (V1.1+)
```

### Matriz de dependência

| Módulo | Depende de | É consumido por | Fronteira |
|---|---|---|---|
| **IDN** | — | todos | `pode()`, `subjects_de()`, `pode_executar()` |
| **PLT** | IDN | todos | Tokens, componentes, `WorkspaceProvider`, flags |
| **APR** | IDN | SVC, FIN, PPL, WKS | `criar_solicitacao_aprovacao()`, `decidir()` |
| **SVC** | IDN, APR, Ticket | WKS, SRC | `solicitar()` |
| **CNT** | IDN | COM, SRC, WKS, AIC | `publicar()`, `acl_subjects()` |
| **COM** | CNT, IDN | WKS, app nativo | `publicar_comunicado()` |
| **PPL** | IDN | OPS, FSM, WKS | `pode_executar()`, `ausencias_de()` |
| **OPS** | IDN, PPL | WKS, app nativo | `plantao_agora()`, `escala_semana()` |
| **SRC** | IDN, providers | WKS | `buscar()`, `indexar()` |
| **WKS** | todos (via provider) | usuário | — (folha) |
| **AIC** | copilot existente | — (V1.0) | `registrar_feedback()`, `verificar_teto()` |
| **FIN** | SVC, APR, estoque, FSM | REV | `registrar_consumo()` |
| **REV** | Contrato, FSM | FIN, AIC (V1.1+) | `preco_de()`, `esta_coberto()` |

### O contrato de provider, na prática

```python
# fsm/workspace_provider.py
class FSMProvider(WorkspaceProvider):
    key, label = "fsm", "Field Service"

    def pending_items(self, pessoa):
        tecnico = getattr(pessoa.user, "tecnico", None)
        if not tecnico:
            return []
        qs = OrdemServico.objects.filter(
            tecnico=tecnico, status__in=["agendada", "em_execucao"]
        ).order_by("data_agendada")[:5]
        return [PendingItemDTO(titulo=os.titulo, url=..., prazo=os.janela_fim) for os in qs]

    def search_documents(self, since=None):
        ...   # gerador — V1.1

    def quick_actions(self, pessoa):
        if pode(pessoa, "fsm.os.criar.unidade"):
            yield ActionSpec(label="Nova OS", url=reverse("fsm:os_nova"))
```

**Registro por `AppConfig.ready()`** — o `workspace` nunca importa app de domínio:

```python
# fsm/apps.py
def ready(self):
    from workspace.providers.registry import register
    from .workspace_provider import FSMProvider
    register(FSMProvider())
```

---

## 5.4 Arquitetura de permissões

### O algoritmo

```
pode(pessoa, "apr.aprovar.equipe", alvo=solicitacao)
  │
  ├─ 1. cache do request?                          ──▶ devolve
  │
  ├─ 2. atribuições vigentes de `pessoa`
  │       AtribuicaoPapel.objects.filter(
  │           pessoa=pessoa,
  │           vigencia_inicio__lte=hoje,
  │           Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=hoje))
  │
  ├─ 3. + delegações ativas recebidas
  │       Delegacao.objects.filter(delegado=pessoa, ativa=True,
  │                                inicio__lte=hoje, fim__gte=hoje)
  │       (interseção com o que o delegante tinha — nunca amplia)
  │
  ├─ 4. alguma atribuição concede a permissão pedida?
  │       (comparação por prefixo: "apr.aprovar.global" satisfaz
  │        "apr.aprovar.equipe" — escopo maior contém o menor)
  │
  ├─ 5. escopo × alvo
  │       global      → True
  │       unidade     → alvo.pessoa.unidade == escopo_unidade
  │       departamento→ alvo.pessoa.departamento_fk == escopo_departamento
  │       equipe      → alvo.pessoa ∈ liderados_recursivos(pessoa)
  │       proprio     → alvo.pessoa == pessoa
  │
  └─ 6. grava no cache do request e devolve
```

### Hierarquia de escopo

```
global  ⊃  unidade  ⊃  departamento  ⊃  equipe  ⊃  proprio
```
Quem tem `apr.aprovar.global` satisfaz qualquer `apr.aprovar.*`. Isso evita ter que atribuir cinco permissões a um diretor.

### Cache — o desenho e o porquê

| Camada | Onde | Vida | Racional |
|---|---|---|---|
| Resultado de `pode()` | `request.perm_cache` | O request | Uma home chama `pode()` ~40 vezes; sem cache, 40 queries |
| Atribuições vigentes | `request.perm_cache["_atrib"]` | O request | Uma query por request |
| `liderados_recursivos()` | `request.perm_cache["_lid"]` | O request | CTE recursiva, cara |
| **Entre requests** | **nenhum** | — | **[ADR-005]** Mudança de papel vale na requisição seguinte |

### Liderados recursivos, em uma query

```sql
WITH RECURSIVE equipe AS (
    SELECT id FROM dashboard_perfilusuario WHERE gestor_id = %(pessoa_id)s
    UNION ALL
    SELECT p.id FROM dashboard_perfilusuario p JOIN equipe e ON p.gestor_id = e.id
)
SELECT id FROM equipe;
```
Índice em `gestor_id`. Com 500 pessoas e profundidade 5, resolve em poucos milissegundos.

### Os três pontos de aplicação

| Ponto | Como | Falha |
|---|---|---|
| **View** | Decorador `@requer("apr.aprovar.equipe")` | 403 |
| **Serviço** | `pode()` explícito antes de agir | `PermissaoNegada` |
| **Consulta** | `acl_subjects && subjects_de(pessoa)` no `WHERE` | Registro não existe para quem consulta |

> **O terceiro é o mais importante e o mais esquecido.** Verificar permissão *depois* de recuperar vaza contagem, ordenação e, no pior caso, trecho de conteúdo. É a falha nº 1 de busca corporativa.

---

## 5.5 Arquitetura do banco de dados

### Organização física

| Grupo | Tabelas | Volume esperado/ano | Nota |
|---|---|---|---|
| **Identidade** | 8 | baixo (centenas) | Lido em quase todo request → cabe em cache do Postgres |
| **Aprovação** | 3 | médio (milhares) | Índice por status e etapa |
| **Catálogo** | 2 | baixo | Praticamente estático |
| **Conteúdo** | 3 | médio | `PendenciaLeitura` cresce por documento × pessoa |
| **Busca** | 1 | médio-alto | Projeção; pode ser reconstruída |
| **Operação** | 2 | médio | Turnos por semana × pessoas |
| **Custo/Receita** | 5 | alto (`ConsumoMaterialOS`) | Cresce com o volume de OS |

### Índices que importam

```sql
-- Identidade: o caminho quente de pode()
CREATE INDEX idx_atrib_vigencia ON identidade_atribuicaopapel
    (pessoa_id, vigencia_inicio, vigencia_fim);
CREATE INDEX idx_perfil_gestor  ON dashboard_perfilusuario (gestor_id);

-- Aprovação: a bandeja
CREATE INDEX idx_solic_status   ON workspace_solicitacaoaprovacao (status, etapa_atual);
CREATE INDEX idx_etapa_aprov    ON workspace_etapaaprovacao (aprovador_id, status)
    WHERE status = 'aguardando';                       -- parcial: só o que está na fila

-- Conteúdo: pendências do usuário
CREATE INDEX idx_pend_pessoa    ON workspace_pendencialeitura (pessoa_id)
    WHERE confirmada_em IS NULL;                       -- parcial

-- Busca: os dois GIN
CREATE INDEX idx_sd_tsv         ON workspace_searchdocument USING GIN (tsv);
CREATE INDEX idx_sd_acl         ON workspace_searchdocument USING GIN (acl_subjects);

-- Escala: intervalo
CREATE EXTENSION IF NOT EXISTS btree_gist;
-- ExclusionConstraint definida no model (ver Etapa 3)

-- Consumo: agregação por OS
CREATE INDEX idx_consumo_os     ON fsm_consumomaterialos (os_id);
```

**Índices parciais (`WHERE`) são deliberados:** a bandeja consulta apenas `status='aguardando'`, e as pendências apenas as não confirmadas. Índice parcial é menor, mais rápido e não cresce com o histórico.

### Estratégia de migração

| Regra | Motivo |
|---|---|
| Nenhuma coluna existente é removida ou renomeada no V1.0 | Rollback tem que ser possível sem perda |
| Coluna nova sempre `null=True` ou com default | Migração não trava tabela grande |
| `departamento` (texto) e `departamento_fk` convivem | Remoção só com resíduo zero, medido |
| Migração de dados em comando de gestão, **não** em `RunPython` de migração | Reexecutável, com relatório e sem travar deploy |
| Toda migração testada contra dump de produção antes do deploy | Tempo de lock medido, não estimado |

### Sequência de migração no V1.0

```
1. identidade.0001  Unidade, Departamento, Papel                    (tabelas novas)
2. dashboard.XXXX   PerfilUsuario += matricula, situacao, FKs       (colunas nullable)
3. comando          casar departamento texto → FK, com relatório
4. identidade.0002  AtribuicaoPapel, Delegacao
5. comando          migrar UserRole → AtribuicaoPapel (LEGACY_ROLE_MAP)
6. workspace.0001   aprovação, catálogo, conteúdo, comunicação, busca
7. fsm.XXXX         Escala, TurnoEscala, ConsumoMaterialOS
8. dashboard.XXXX   TipoServico, EscopoContrato, TabelaPreco
9. dashboard.XXXX   FeedbackIA, ConsumoIA, TetoIA
```

> **Passos 3 e 5 são comandos, não migrações.** Podem rodar várias vezes, produzem relatório e não bloqueiam o deploy se algo não casar.

### Retenção

| Dado | Retenção | Base |
|---|---|---|
| `PendenciaLeitura` confirmada | permanente | Evidência de conformidade |
| Auditoria de decisão de aprovação | permanente | Rastreabilidade |
| `SearchDocument` | reconstruível | Projeção, não fonte |
| `FeedbackIA` | 24 meses | Insumo de métrica |
| `ConsumoIA` | 36 meses | Financeiro |
| `ConflitoSincronizacao` resolvido | 12 meses | Diagnóstico |

---

## 5.6 Arquitetura das APIs

### Três superfícies, três propósitos

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. HTMX  ·  /workspace/…                                               │
│    Retorna: fragmento HTML   Auth: sessão + CSRF   Consumidor: browser │
│    Sem versionamento — cliente e servidor sobem juntos                  │
├────────────────────────────────────────────────────────────────────────┤
│ 2. JSON  ·  /api/v1/workspace/…                                        │
│    Retorna: JSON (DRF)       Auth: JWT           Consumidor: app nativo │
│    Versionada. Contrato estável. 6 endpoints no V1.0                    │
├────────────────────────────────────────────────────────────────────────┤
│ 3. WS    ·  /ws/notifications/  (reusado — ADR-003)                    │
│    Retorna: evento JSON      Auth: sessão/JWT    Consumidor: browser    │
└────────────────────────────────────────────────────────────────────────┘
```

### Os 6 endpoints JSON do V1.0

Só existe endpoint JSON com consumidor declarado. Todos servem o app nativo.

| Endpoint | Método | Para quê |
|---|:-:|---|
| `/api/v1/workspace/pessoas/me/` | GET | Identidade e permissões efetivas |
| `/api/v1/workspace/aprovacoes/` | GET | Bandeja no celular |
| `/api/v1/workspace/comunicados/` | GET | Comunicado obrigatório para o técnico |
| `/api/v1/workspace/comunicados/<id>/confirmar/` | POST | Confirmação de leitura em campo |
| `/api/v1/workspace/escala/atual/` | GET | Plantão e turno |
| `/api/v1/workspace/os/<id>/consumo/` | POST | Registro de material consumido |

### Convenções HTMX

| Padrão | Uso |
|---|---|
| `hx-get` + `hx-trigger="load"` | Carga preguiçosa de widget |
| `hx-post` + `hx-swap="outerHTML"` | Ação que substitui o próprio card |
| `HX-Trigger` no cabeçalho | Avisa outros elementos (contador do topo) |
| `HX-Redirect` | Redireciona depois de uma ação |
| `hx-push-url="true"` | Mantém o botão voltar funcionando |
| `hx-indicator` | Estado de carregamento sem JavaScript |

```python
# Padrão de resposta de ação
def aprovar(request, pk):
    solicitacao = get_object_or_404(SolicitacaoAprovacao, pk=pk)
    servico.decidir(request.pessoa, solicitacao, "aprovar")   # permissão dentro do serviço
    resp = render(request, "workspace/apr/_card.html", {"s": solicitacao})
    resp["HX-Trigger"] = json.dumps({"apr:contador": {"delta": -1}})
    return resp
```

### Idempotência

Toda ação de escrita vinda do app nativo aceita `Idempotency-Key`. O padrão já existe no FSM (`OSEvidencia.client_event_id`) e é replicado — rede de campo repete requisição, e repetir não pode duplicar aprovação nem consumo.

---

## 5.7 Arquitetura de navegação

### Mapa de URLs

```
/workspace/                        Home
/workspace/aprovacoes/             Bandeja
/workspace/servicos/               Catálogo
/workspace/servicos/<slug>/        Formulário
/workspace/biblioteca/             Conteúdo
/workspace/biblioteca/<slug>/      Documento
/workspace/mural/                  Comunicados
/workspace/mural/<slug>/           Comunicado
/workspace/escala/                 Escala da semana
/workspace/perfil/                 Meu perfil
/workspace/buscar/                 Fragmento de busca (⌘K)
/workspace/widget/<chave>/         Fragmento de widget

/dashboard/…  /fsm/…  /financeiro/…  /estoque/…      ← intactos
```

### Modelo de navegação

```
                     ┌─────────────────────────────┐
                     │  ⌘K — a navegação primária  │
                     │  vai a qualquer lugar       │
                     └──────────────┬──────────────┘
                                    │
   ┌──────────┬──────────┬──────────┼──────────┬──────────┬──────────┐
   ▼          ▼          ▼          ▼          ▼          ▼          ▼
 Home     Aprovações  Serviços  Biblioteca   Mural     Escala    [Módulos]
   │                                                                  │
   └──────── Acesso rápido (WKS-010) ────────────────────────────────┘
```

**6 destinos no menu lateral, mais o launcher.** O ⌘K é a navegação real; o menu é a rede de segurança para quem não usa teclado.

### Regras

| # | Regra |
|:-:|---|
| N1 | Toda tela é alcançável em **≤ 2 cliques** a partir da home |
| N2 | Breadcrumb só com profundidade ≥ 2. Em tela de nível 1 é ruído |
| N3 | `hx-push-url` em toda navegação — o botão voltar do navegador funciona |
| N4 | Link direto sempre funciona, mesmo sem HTMX (`HX-Request` ausente → renderiza a página completa) |
| N5 | Módulo antigo abre **na mesma aba**. Nova aba quebra a continuidade |
| N6 | Item de menu sem permissão não é renderizado |

```python
# N4 — o padrão que faz o link direto funcionar
def bandeja(request):
    ctx = {...}
    if request.headers.get("HX-Request"):
        return render(request, "workspace/apr/_bandeja.html", ctx)   # fragmento
    return render(request, "workspace/apr/bandeja.html", ctx)        # página completa
```

---

## 5.8 Arquitetura dos widgets

### O contrato

```python
@dataclass(frozen=True)
class WidgetSpec:
    chave: str
    titulo: str
    zona: int                      # 1 | 2 | 3
    permissao: str | None          # None = todos
    ttl: int = 60                  # segundos de cache
    timeout: float = 3.0           # limite de execução
    template: str = ""
    dominio: str = ""              # qual geração de cache observar
```

### Ciclo de vida

```
Home renderiza a casca
   └─▶ para cada widget do preset, com permissão:
       <div id="w-aprovacoes"
            hx-get="/workspace/widget/aprovacoes/"
            hx-trigger="load, apr:contador from:body"
            class="au-widget" style="min-height:280px">        ← altura reservada
         <div class="au-skeleton">…</div>
       </div>
                    │
                    ▼  (N requisições paralelas)
       ┌────────────────────────────────────────────────┐
       │ GET /workspace/widget/aprovacoes/              │
       │   1. pode(pessoa, spec.permissao)?  não → 204  │
       │   2. gen = redis.get(f"wks:gen:apr:{pid}")     │
       │   3. cache.get(f"wks:w:aprovacoes:{pid}:{gen}")│
       │      hit  → devolve HTML                       │
       │   4. miss → provider(timeout=3s)               │
       │      erro/timeout → template de erro           │
       │   5. renderiza, grava no cache com ttl         │
       └────────────────────────────────────────────────┘
```

### Cache por geração — [ADR-004]

```python
def chave_widget(spec, pessoa):
    gen = cache.get(f"wks:gen:{spec.dominio}:{pessoa.id}", 0)
    return f"wks:w:{spec.chave}:{pessoa.id}:{gen}"

def invalidar(dominio: str, pessoa_id: int):
    """Chamado por sinal de domínio. INCR é atômico."""
    cache.incr_or_set(f"wks:gen:{dominio}:{pessoa_id}")
```

**Por que isso é melhor que apagar a chave:** não é preciso saber quais widgets dependem de quê. A chave antiga fica órfã e expira sozinha pelo TTL. Elimina a classe inteira de bugs de invalidação — que é onde o cache costuma dar errado.

### Atualização ao vivo

```
Aprovação decidida por outra pessoa
   └─▶ sinal → invalidar("apr", pessoa_id)
       └─▶ group_send(f"ws.pessoa.{pessoa_id}", {"tipo":"widget.invalidado","dominio":"apr"})
           └─▶ navegador recebe → dispara evento `apr:contador` no body
               └─▶ hx-trigger="… from:body" recarrega só aquele widget
```

Sem polling. Sem recarregar a página. Um evento, um widget.

### Os 6 widgets e sua fonte

| Chave | Zona | TTL | Domínio | Fonte | Ação inline |
|---|:-:|:-:|---|---|---|
| `atencao` | 1 | 30 s | `cnt` | `PendenciaLeitura` + itens vencendo | Confirmar |
| `aprovacoes` | 2 | 30 s | `apr` | `EtapaAprovacao` aguardando | Aprovar / reprovar / devolver / lote |
| `meu_dia` | 2 | 60 s | `svc` | `pending_items()` de todos os providers | Abrir |
| `escala` | 2 | 300 s | `ops` | `plantao_agora()` | Ligar |
| `mural` | 3 | 120 s | `com` | Comunicados do público-alvo | Confirmar |
| `acesso_rapido` | 3 | 3600 s | `plt` | Registro de apps + permissão | Abrir |

---

## 5.9 Arquitetura do App Launcher

### Como as aplicações são descobertas

Nada de lista fixa em template. Cada app declara o que expõe:

```python
# fsm/apps.py
def ready(self):
    from workspace.launcher import registrar_app
    registrar_app(AppSpec(
        chave="fsm",
        nome="Field Service",
        descricao="Ordens de serviço e roteirização",
        icone="truck",
        url_name="fsm:dashboard",
        permissao="fsm.acessar",
        cor="var(--au-accent-500)",
        ordem=20,
    ))
```

### Resolução

```
GET /workspace/lancador/
  ├─ apps registrados
  ├─ filtra por pode(pessoa, app.permissao)          ← N6: sem permissão, não existe
  ├─ ordena por: (1) uso da pessoa nos últimos 30 dias, (2) app.ordem
  └─ renderiza a grade
```

### Uso — o dado que orienta o roadmap

```python
class UsoApp(models.Model):
    pessoa   = FK("dashboard.PerfilUsuario")
    app      = CharField(max_length=40)
    contador = PositiveIntegerField(default=0)
    ultimo   = DateTimeField(auto_now=True)
    class Meta:
        constraints = [UniqueConstraint(fields=["pessoa", "app"], name="uniq_uso_app")]
```

Incrementado de forma assíncrona (Celery), nunca no caminho da requisição.

> **`UsoApp` alimenta `K-WKS-05`.** O app que continua sendo muito acessado pelo launcher é o próximo candidato a ganhar profundidade dentro do Workspace. É a migração por atração virando decisão baseada em dado, não em opinião.

---

## 5.10 Arquitetura da busca global

### Fluxo completo

```
Usuário pressiona ⌘K
   │
   ├─ CAMADA LOCAL  (Alpine, 0 ms, sem rede)
   │    · últimos 10 acessos (localStorage)
   │    · favoritos
   │    · 6 destinos de navegação
   │    · ações do catálogo (JSON cacheado por 1 h)
   │
   └─ digita ≥ 2 caracteres → debounce 200 ms
        GET /workspace/buscar/?q=ana
          │
          ├─ subjects = subjects_de(pessoa)          ← do cache do request
          │    ["*", "pessoa:42", "depto:7", "unid:2", "papel:gestor"]
          │
          ├─ SELECT origem, titulo, subtitulo, url, icone,
          │         ts_rank(tsv, q) AS rank
          │    FROM workspace_searchdocument, plainto_tsquery('portuguese', %s) q
          │    WHERE acl_subjects && %(subjects)s        ← GIN, security trimming
          │      AND tsv @@ q                            ← GIN
          │    ORDER BY rank DESC, atualizado_em DESC
          │    LIMIT 20
          │
          └─ agrupa por `origem` → fragmento HTML
```

### Indexação

```
Sinal do domínio (post_save, post_delete, documento_publicado, pessoa_sincronizada)
   └─▶ Celery: indexar_documento.delay(origem, origem_id)
       └─▶ provider.search_documents(desde=…) devolve o DTO
           └─▶ upsert em SearchDocument, com acl_subjects recalculado
               └─▶ UPDATE … SET tsv = to_tsvector('portuguese', titulo||' '||corpo)
```

**Mais uma varredura diária de reconciliação** (Celery Beat), que compara contagem por origem e corrige o que ficou órfão. Sinal perdido acontece; a varredura é a rede.

### Por que PostgreSQL e não Elasticsearch — [ADR-007]

| Critério | Postgres FTS + GIN | Elasticsearch |
|---|---|---|
| Componentes a operar | 0 novos | +1 (cluster, memória, backup, upgrade) |
| Security trimming | `WHERE acl && …`, no mesmo lugar do dado | Filtro replicado, com risco de divergir |
| Consistência | Transacional | Eventual, com janela de vazamento |
| Volume esperado (< 500 mil docs) | Confortável | Superdimensionado |
| Semântica (V1.1) | pgvector, mesma tabela | Índice separado |

> **O argumento decisivo não é desempenho, é segurança.** Com o índice no mesmo banco, o filtro de permissão vive junto do dado. Com índice externo, a ACL é replicada — e replicação de ACL é onde vazamento acontece.

### Evolução para o V1.1

```sql
CREATE EXTENSION vector;
ALTER TABLE workspace_searchdocument ADD COLUMN embedding vector(384);
CREATE INDEX idx_sd_emb ON workspace_searchdocument
    USING hnsw (embedding vector_cosine_ops);
```

Busca híbrida com fusão RRF, **sem alterar o esquema existente** — o desenho do V1.0 já previu a coluna.

---

## 5.11 Arquitetura da IA

### As três camadas e onde cada uma vive

```
╔════════════════════════════════════════════════════════════════════╗
║  AGÊNTICA          V2 — agentes com autonomia medida                ║
║  ┌──────────────────────────────────────────────────────────────┐ ║
║  │ ContratoAgente: objetivo · gatilho · escopo · tools ·        │ ║
║  │ autonomia (0-3) · orçamento · precisao_medida · kill_switch  │ ║
║  └──────────────────────────────────────────────────────────────┘ ║
╠════════════════════════════════════════════════════════════════════╣
║  ASSISTIVA         V1.1 — ⌘K com resposta, briefing, skill packs   ║
╠════════════════════════════════════════════════════════════════════╣
║  AMBIENTE          V1.1 — enriquecimento sem interface (Celery)     ║
╠════════════════════════════════════════════════════════════════════╣
║  GOVERNANÇA        V1.0 ← É O QUE SE CONSTRÓI AGORA                 ║
║  ┌──────────────────────────────────────────────────────────────┐ ║
║  │ TetoIA · ConsumoIA · FeedbackIA                              │ ║
║  └──────────────────────────────────────────────────────────────┘ ║
╠════════════════════════════════════════════════════════════════════╣
║  MOTOR             JÁ EXISTE — copilot/engine.py                    ║
║  PermissionGate → mask_pii → tool-use loop → confirmação → audit    ║
╚════════════════════════════════════════════════════════════════════╝
```

### O ponto de instrumentação no V1.0

Uma única costura, sem alterar o comportamento do motor:

```python
# dashboard/services/copilot/engine.py  — envelope, não reescrita
def responder(pessoa, mensagem, **kw):
    with governanca.orcamento(pessoa) as orc:        # levanta TetoExcedido se estourar
        resultado = _responder_original(pessoa, mensagem, **kw)
        orc.registrar(resultado.tokens_entrada, resultado.tokens_saida)
    governanca.registrar_evento(pessoa, resultado)   # denominador do feedback
    return resultado
```

```python
class TetoExcedido(Exception):
    """Tratada na view: mensagem clara ao usuário, nunca erro genérico."""
```

### Fluxo de custo

```
Antes    → consumo do mês (pessoa, papel, instalação) < teto?
           ├─ sim  → segue
           └─ não  → TetoExcedido → mensagem clara
Depois   → ConsumoIA += tokens · custo
           └─ cruzou 70% ou 90%? → notifica admin (uma vez por marco)
```

### Feedback — explícito e implícito

| Sinal | Como | Peso |
|---|---|:-:|
| Explícito | 👍 / 👎 no rodapé da resposta | alto |
| Implícito — ação executada | A ação sugerida foi feita em ≤ 5 min? | alto |
| Implícito — reformulação | O usuário reperguntou a mesma coisa? | negativo |
| Implícito — abandono | Fechou sem interagir | fraco |

> Feedback explícito costuma ficar abaixo de 15%. Sem o sinal implícito, `precisao_medida` levaria anos para ter significância — e `AIC-004` (autonomia conquistada) nunca sairia do papel.

---

## 5.12 Ciclo de requisição, cache e tempo real

### Carga da home, do início ao fim

```
GET /workspace/                                              t=0
  │
  ├─ NGINX → Daphne
  ├─ middlewares existentes (segurança, sessão, auditoria)   ~8 ms
  ├─ WorkspaceContextMiddleware  → request.pessoa            ~3 ms  (1 query)
  ├─ ComunicadoCriticoMiddleware → cache hit                 ~1 ms
  ├─ view home: preset + widgets permitidos                  ~5 ms
  ├─ Zona 1 (síncrona): pendências + vencimentos             ~40 ms (2 queries)
  └─ HTML da casca ──────────────────────────────────────▶   ~60 ms  ✅ meta: 800 ms
        │
        └─ navegador dispara 6 requisições paralelas         t≈100 ms
             ├─ /widget/atencao/        cache hit    ~15 ms
             ├─ /widget/aprovacoes/     miss → 2 q   ~80 ms
             ├─ /widget/meu_dia/        miss → 3 prov ~150 ms
             ├─ /widget/escala/         cache hit    ~12 ms
             ├─ /widget/mural/          cache hit    ~14 ms
             └─ /widget/acesso_rapido/  cache hit    ~10 ms
                                          tudo pronto ≈ 250 ms  ✅ meta: 1.500 ms
        │
        └─ WebSocket conecta (ws/notifications/)             t≈300 ms
```

### Mapa de cache

| Chave | TTL | Invalidação | Escopo |
|---|:-:|---|---|
| `wks:w:<widget>:<pessoa>:<gen>` | por widget | Geração | Pessoa |
| `wks:gen:<dominio>:<pessoa>` | ∞ | `INCR` por sinal | Pessoa |
| `wks:critico:<pessoa>` | 300 s | Publicação de crítico | Pessoa |
| `wks:preset:<pessoa>` | 3600 s | Mudança de papel | Pessoa |
| `wks:acoes` | 3600 s | Mudança de catálogo | Global |
| `src:q:<hash>:<subjects_hash>` | 60 s | TTL | Por conjunto de permissão |

> **`src:q` inclui o hash dos subjects na chave.** Sem isso, duas pessoas com permissões diferentes compartilhariam resultado — vazamento por cache, que é o mais difícil de detectar em revisão.

### Tempo real — o que trafega

| Evento | Origem | Ação no cliente |
|---|---|---|
| `widget.invalidado` | Sinal de domínio | Recarrega aquele widget |
| `contador.atualizado` | Aprovação decidida | Atualiza o badge do topo |
| `comunicado.critico` | Publicação | Redireciona para o aceite |
| `notificacao.nova` | Existente | Toast |

**Grupos:** `ws.pessoa.<id>` e `ws.papel.<chave>`.

### Tarefas assíncronas

| Task | Cadência | Fila |
|---|---|---|
| `indexar_documento` | Por sinal | `indexacao` |
| `reconciliar_indice` | Diária, 03h | `manutencao` |
| `sincronizar_pessoas` | A definir (`A-03`) | `integracao` |
| `verificar_vencimentos` | Diária, 06h | `alertas` |
| `expirar_documentos` | Diária, 00h | `manutencao` |
| `atualizar_situacao_ausencia` | Diária, 00h | `manutencao` |
| `registrar_uso_app` | Por evento | `telemetria` |
| `consolidar_consumo_ia` | Horária | `telemetria` |

**Filas separadas por criticidade.** Indexação lenta não pode atrasar alerta de vencimento.

---

## 5.13 Degradação e falhas

### Matriz de degradação

| Falha | Efeito | Comportamento | Usuário percebe |
|---|---|---|---|
| **Redis fora** | Sem cache, sem tempo real | Widgets recalculam a cada carga; sessão sobrevive (`cached_db`); sem atualização ao vivo | Mais lento; sem contador ao vivo |
| **Um provider lento** | 1 widget | Timeout em 3 s → estado de erro com [tentar de novo] | 1 widget com erro |
| **Um provider com exceção** | 1 widget | Log + estado de erro | 1 widget com erro |
| **Celery fora** | Índice e alertas param | Busca fica desatualizada; alertas atrasam; nada quebra | Resultado de busca antigo |
| **Índice de busca fora** | Busca federada | ⌘K degrada para a camada local, com aviso | *"Busca completa indisponível"* |
| **LLM fora** | Copiloto | Mensagem clara, sem stack trace | *"Assistente indisponível"* |
| **Teto de IA atingido** | Copiloto | Mensagem clara | *"Limite de uso atingido"* |
| **PostgreSQL fora** | Tudo | Página de erro | Sistema fora |

### Os invariantes de degradação

| # | Invariante |
|:-:|---|
| D1 | **A home sempre carrega.** Nenhum widget derruba a página |
| D2 | **Nenhuma falha vira erro genérico.** Toda falha tem mensagem específica |
| D3 | **Falha nunca amplia permissão.** Em dúvida, o padrão é negar |
| D4 | **Falha de cache nunca serve dado errado.** Miss recalcula; nunca devolve o de outra pessoa |
| D5 | **Escrita é atômica.** Solicitação + aprovação em uma transação; falha reverte as duas |

```python
# D1 na prática
def widget(request, chave):
    spec = registro.get(chave)
    if not spec or not pode(request.pessoa, spec.permissao):
        return HttpResponse(status=204)                    # D3
    try:
        ctx = _com_timeout(spec.provider, request.pessoa, timeout=spec.timeout)
    except (TimeoutError, Exception) as exc:
        logger.warning("widget %s falhou: %s", chave, exc)
        return render(request, "workspace/wks/_widget_erro.html",
                      {"spec": spec}, status=200)          # 200: HTMX troca o conteúdo
    return render(request, spec.template, ctx)
```

> **O erro devolve HTTP 200 de propósito.** HTMX só substitui o conteúdo em resposta bem-sucedida; um 500 deixaria o esqueleto congelado na tela para sempre.

---

## 5.14 Escala e capacidade

### Perfil de carga real

Instalação dedicada, empresa de porte médio do vertical:

| Dimensão | Estimativa |
|---|---|
| Pessoas cadastradas | 150–400 |
| Usuários do Workspace no piloto | 30–80 |
| Cargas de home por pessoa/dia | 3–5 |
| Requisições de widget/dia | 80 × 4 × 6 ≈ **2.000** |
| Pico (login da manhã, 30 min) | 80 pessoas × 7 req ≈ **560 req** ≈ 19 req/min |
| WebSockets simultâneos | ≤ 80 |
| `SearchDocument` no V1.0 (pessoas) | ~400 linhas |
| `SearchDocument` no V1.1 (todas as fontes) | 50–200 mil linhas |

### Conclusão honesta sobre escala

> **A carga do Workspace é irrelevante para esta infraestrutura.** 19 requisições por minuto no pico é ruído para um Django com Redis. Não há problema de escala a resolver no V1.0 — e projetar para uma escala que não existe seria exatamente a complexidade desnecessária que a Etapa 9 pede para evitar.

**O que realmente merece atenção não é volume, é latência de cauda:**

| Ponto | Risco | Mitigação |
|---|---|---|
| `pode()` com organograma profundo | CTE recursiva por chamada | Cache por request (`ADR-005`) + índice em `gestor_id` |
| Widget `meu_dia` agregando N providers | O mais lento define o total | Timeout individual; provider lento não bloqueia os outros |
| GIN em `acl_subjects` no V1.1 | Cresce com o índice | Medir com 200 mil documentos antes de liberar as fontes |
| `PendenciaLeitura` documento × pessoa | 50 documentos × 400 pessoas = 20 mil linhas | Índice parcial em não confirmadas |

### Onde quebraria, se quebrasse

| Limite | Quando | O que fazer |
|---|---|---|
| ~1.000 WS por worker Daphne | > 800 usuários simultâneos | Mais réplicas de Daphne |
| GIN de ACL degradando | > 500 mil documentos | Particionar por origem |
| Bandeja de aprovação lenta | > 100 mil solicitações históricas | Particionar por ano |

Nenhum desses cenários acontece no V1.0. Ficam registrados para não serem redescobertos.

---

## 5.15 Observabilidade

### O que instrumentar desde o dia 1

| Categoria | Métrica | Onde |
|---|---|---|
| **Latência** | Home (p50/p95/p99), por widget, `⌘K` local e federado | Middleware + decorador |
| **Erro** | Taxa por widget, timeouts de provider, exceções por módulo | Logger + Sentry (já configurado) |
| **Negócio** | Aprovações decididas, solicitações criadas, leituras confirmadas, buscas | Sinal → tabela de evento |
| **IA** | Tokens, custo, feedback, bloqueios por teto | `ConsumoIA`, `FeedbackIA` |
| **Permissão** | Negativas por permissão e por pessoa | Log estruturado |
| **Cache** | Taxa de acerto por widget | Redis `INFO` + contador |

### Log estruturado

```python
logger.info("widget.render", extra={
    "widget": chave, "pessoa_id": pessoa.id, "cache": "hit",
    "duracao_ms": ms, "erro": None,
})
```

### O painel que decide a continuidade do produto

Um só, com as 9 métricas de produto ([Etapa 2 §2.8](EXEC_02_MVP.md)) e os 4 gatilhos de versão ([Etapa 4 §4.18](EXEC_04_PRD.md)). Atualizado diariamente por Celery.

> **Se o painel não existir no dia do lançamento, o V1.0 não lançou** — porque não haverá como saber se funcionou. Instrumentação é parte da feature, não tarefa posterior.

---

## 5.16 Implantação

### Pipeline

```
PR
 ├─ lint (ruff) + format
 ├─ regra: nenhuma classe Tailwind fora de workspace/     (A-02)
 ├─ testes: dashboard · fsm · km_audit · identidade · workspace
 ├─ gates de cobertura (todos precisam passar)
 ├─ build do Tailwind + collectstatic
 └─ ✅ merge

Deploy
 ├─ migrações (testadas contra dump de produção)
 ├─ comandos de migração de dado (reexecutáveis)
 ├─ restart rolling do Daphne
 ├─ smoke test: /health/ · /workspace/ com usuário de teste
 └─ flag `workspace_ativo` ligada para o grupo piloto
```

### Rollback

| Cenário | Ação | Tempo |
|---|---|---|
| Workspace com problema | **Desligar a flag** | ≤ 1 min |
| Regressão em módulo existente | Rollback da imagem | ~5 min |
| Migração problemática | Migração reversa (todas nullable, por desenho) | ~10 min |

> **A flag é o mecanismo primário de rollback.** Como nenhuma migração do V1.0 é destrutiva, desligar a flag devolve o sistema ao estado anterior sem tocar no banco. É por isso que `PLT-007` é V1.0 e não uma conveniência.

### Ambientes

| Ambiente | Banco | Diferenças conhecidas |
|---|---|---|
| Dev | SQLite ou Postgres | `ExclusionConstraint` e FTS só em Postgres → `clean()` equivalente |
| Homologação | Postgres com dump de produção | Onde a migração é medida |
| Produção | Postgres + Redis + Celery | Instalação dedicada ([D-01]) |

**O CI roda em PostgreSQL**, não em SQLite — do contrário, constraint e FTS nunca seriam testados.

---

## Correção à Etapa 3

Duas especificações mudam com a verificação da infraestrutura real:

| Item | Etapa 3 dizia | Corrigido para | Por quê |
|---|---|---|---|
| WebSocket do Workspace | `/ws/workspace/` (novo) | **Reusar `/ws/notifications/`** | [ADR-003] — uma conexão por usuário em vez de duas |
| Alpine.js | Não especificado | **Build CSP obrigatório** | [ADR-002] — a CSP de produção não tem `unsafe-eval` |

---

## Próxima etapa

**Etapa 6 — Design System.** Componentes, cards, widgets, menus, formulários, modais, dashboards, tabelas, listas, ícones, botões, breadcrumb, navbar, sidebar, timeline, feed, cores, tipografia, espaçamentos, grid, responsividade e dark mode.

**Aguarda aprovação da Etapa 5.**

---

*Etapa 5 de 9 · 9 ADRs · 11 vistas arquiteturais · 0 componentes de infraestrutura novos.*
