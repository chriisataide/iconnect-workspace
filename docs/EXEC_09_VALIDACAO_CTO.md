# Execução · Etapa 9 — Validação de CTO

> **Auditoria técnica do plano.** Verificação de que as 8 etapas anteriores são implementáveis no stack declarado, onde o plano está complexo demais, onde está simples demais, o que já existe e eu ia reconstruir, e o custo de manutenção em dois anos.
>
> **Agosto/2026** · Etapa 9 de 10
>
> ⚠️ **Revisado em 12/08/2026 pela [Etapa 10 — Reposicionamento](EXEC_10_REPOSICIONAMENTO.md).** As 6 condições do parecer seguem válidas; o que muda é o escopo do Workspace (OPS e REV migram para a Platform). §10.7.

---

## Sumário

- [9.0 O que esta etapa é](#90-o-que-esta-etapa-é)
- [9.1 Reuso — o que eu ia construir e já existe](#91-reuso--o-que-eu-ia-construir-e-já-existe)
- [9.2 Auditoria de implementabilidade](#92-auditoria-de-implementabilidade)
- [9.3 Onde meu plano está complexo demais](#93-onde-meu-plano-está-complexo-demais)
- [9.4 Onde meu plano está simples demais](#94-onde-meu-plano-está-simples-demais)
- [9.5 Os pontos que estressam o stack](#95-os-pontos-que-estressam-o-stack)
- [9.6 Custo de manutenção em dois anos](#96-custo-de-manutenção-em-dois-anos)
- [9.7 Dívida assumida conscientemente](#97-dívida-assumida-conscientemente)
- [9.8 Alterações ao plano](#98-alterações-ao-plano)
- [9.9 Spikes obrigatórios](#99-spikes-obrigatórios)
- [9.10 Veredito](#910-veredito)

---

## 9.0 O que esta etapa é

Não é carimbo de aprovação do que escrevi nas oito etapas anteriores. É a leitura do plano **por quem vai manter o resultado em 2028** — e essa leitura encontrou coisas.

Três achados mudam o plano de forma concreta, e um deles é constrangedor: **projetei uma solução de cache que já existe no código, linha por linha.**

---

## 9.1 Reuso — o que eu ia construir e já existe

### 🔴 Achado 1 · O cache por geração já está implementado

Na [Etapa 5, ADR-004](EXEC_05_ARQUITETURA.md), especifiquei invalidação de cache por geração com `INCR` atômico como se fosse desenho novo. Ele existe em [`dashboard/services/cache_service.py:93`](../dashboard/services/cache_service.py):

```python
def _ns_version(self, namespace: str) -> int:
    """Versão atual de um namespace (cria como 1 se ausente)."""

def bump_namespace(self, namespace: str) -> int:
    """Invalida todo o namespace incrementando sua versão."""
    try:
        return cache.incr(vkey)
    except ValueError:
        cache.set(vkey, 2, None)      # chave ainda não existe
```

É exatamente o padrão que descrevi — inclusive o tratamento de `ValueError` quando a chave ainda não existe.

| | |
|---|---|
| **Correção** | `ST-041` usa `CacheService.bump_namespace("wks:apr:<pessoa>")`. Nenhum código novo de cache |
| **Efeito** | `ST-041` cai de 8 para **6 pontos** |
| **Lição** | A Etapa 5 desenhou infraestrutura sem auditar `services/` primeiro. Deveria ter começado por lá |

### 🔴 Achado 2 · Validação de upload existe e o plano não a usava

[`dashboard/utils/security.py:268`](../dashboard/utils/security.py) tem `validate_file_upload()` com verificação de extensão, MIME type **e magic bytes**.

O plano prevê upload em três lugares novos — `Documento.arquivo`, `Certificacao.evidencia` e anexo de solicitação — e **não especificava nenhuma validação**.

| | |
|---|---|
| **Correção** | Os três chamam `validate_file_upload()`. Vira item de DoD |
| **Efeito** | Fecha um buraco de segurança que o plano estava abrindo |

### 🟠 Achado 3 · Cache de permissão entre requests já existe — e conflita com o ADR-005

`CacheService` tem `cache_user_permissions()` e `get_user_permissions()`, que guardam permissão **entre requisições**.

Isso contradiz frontalmente o [ADR-005](EXEC_05_ARQUITETURA.md), que determina cache de permissão apenas dentro do request — porque mudança de papel precisa valer na requisição seguinte, e cache entre requests cria janela de privilégio indevido.

**Não é bug do código existente.** Ele cacheia os papéis planos legados, que quase nunca mudam. O problema é o novo `AtribuicaoPapel`, que tem **vigência** — uma atribuição pode expirar à meia-noite, e um cache de 5 minutos concederia acesso vencido.

| | |
|---|---|
| **Decisão** | ADR-005 permanece. `pode()` **nunca** usa `CacheService` para permissão |
| **Proteção** | Teste que falha se `pode()` importar `cache_user_permissions` |
| **Risco real** | Alguém "otimizar" `pode()` no futuro usando o helper que já está ali, achando que está reusando bem |

### Inventário completo de reuso

| Ativo existente | Onde | Usado por | Estado no plano |
|---|---|---|---|
| `CacheService.bump_namespace` | `services/cache_service.py:105` | Runtime de widget | 🔴 **corrigido agora** |
| `validate_file_upload` | `utils/security.py:268` | CNT, PPL, SVC | 🔴 **corrigido agora** |
| `mask_pii` / `unmask_pii` | `utils/pii_mask.py` | AIC | ✅ já previsto |
| `AuditMiddleware` | `services/audit_system.py` | PLT-005 | ✅ já previsto |
| SSO SAML/OIDC | `utils/sso.py` | PLT-006 | ✅ já previsto |
| `NotificationConsumer` | `dashboard/consumers.py` | WKS tempo real | ✅ ADR-003 |
| Copilot engine | `services/copilot/` | AIC | ✅ envelope, não reescrita |
| Padrão FTS | `services/knowledge_search.py` | SRC-004 | ✅ mesmo padrão |
| `LEGACY_ROLE_MAP` | `utils/rbac.py:136` | ST-012 | ✅ ponte da migração |
| `SoftDeleteModel` | `models/base.py` | Documento, ItemCatalogo | 🟡 **avaliar** — ver §9.8 |
| `CategoriaTicket`, `Tag` | `models/base.py` | SVC | ✅ |
| `sla_calculator` / `sla_monitor` | `services/` | OPS-002 (V1.1) | ✅ |
| `client_event_id` (idempotência) | `fsm/models.py:474` | APIs do app nativo | ✅ mesmo padrão |

---

## 9.2 Auditoria de implementabilidade

Os 58 itens do V1.0 contra o stack declarado.

| Mecanismo | Itens | Tecnologia | Veredito |
|---|:-:|---|:-:|
| Modelo + migração + admin | 22 | Django ORM · PostgreSQL | ✅ Trivial |
| Serviço de domínio | 9 | Python puro | ✅ Trivial |
| Tela renderizada no servidor | 11 | Templates + Tailwind | ✅ Trivial |
| Fragmento com ação inline | 8 | HTMX | ✅ É o caso de uso canônico |
| Estado de interface | 3 | Alpine (build CSP) | ⚠️ Um exige atenção — ver §9.5 |
| Tarefa assíncrona | 7 | Celery + Beat | ✅ Já em produção |
| Evento em tempo real | 2 | Channels | ✅ Consumer existente |
| Busca textual | 3 | Postgres FTS + GIN | ⚠️ Falta `unaccent` — §9.4 |
| Constraint de integridade | 4 | PostgreSQL | ⚠️ Falta `btree_gist` — §9.4 |
| Endpoint JSON | 6 | DRF | ✅ Já em produção |

**Nenhum item do V1.0 é inimplementável no stack.** Três exigem cuidado, e os três estão tratados em §9.4 e §9.5.

### O que o stack dispensa e vale registrar

| Não precisamos de | Porque |
|---|---|
| SPA (React/Vue) | O Workspace é conteúdo com ação, não aplicação de estado complexo |
| Camada de API para o próprio front | HTMX consome HTML. Só o app nativo precisa de JSON |
| Elasticsearch | [ADR-007](EXEC_05_ARQUITETURA.md) — e o argumento decisivo é segurança, não desempenho |
| Message broker adicional | Redis já é broker do Celery e camada do Channels |
| Servidor de estado (Zustand, Redux) | Não há estado de cliente que sobreviva à navegação |
| Storybook / build de componentes | Componentes são templates Django com `{% include %}` |
| Node em produção | Tailwind roda no build. Runtime é só Python |

> **A ausência mais valiosa é o Node em produção.** O `dist/aurora.css` é gerado no CI e servido como estático. Nenhuma dependência de JavaScript no servidor, nenhuma superfície de segurança de npm em runtime.

---

## 9.3 Onde meu plano está complexo demais

Auditoria das minhas próprias oito etapas. Quatro casos de excesso.

### 🟠 E1 · `Preset` como model, com apenas 2 presets

A [Etapa 3](EXEC_03_MODULOS.md) especificou `Preset` com tabela, layout em JSON e M2M para papéis. **No V1.0 existem exatamente dois presets, definidos por mim, que nenhum usuário edita.**

Tabela, migração, admin e JSON de layout para dois valores constantes é infraestrutura sem consumidor.

```python
# Simplificação: constante em Python, não tabela
PRESETS = {
    "colaborador": ["atencao", "meu_dia", "mural", "acesso_rapido"],
    "gestor": ["atencao", "aprovacoes", "meu_dia", "escala", "mural", "acesso_rapido"],
}
```

**Promover para model no V1.1**, quando forem 6 presets e alguém precisar editar sem deploy. **`ST-057`: 3 → 1 ponto.**

### 🟠 E2 · `WidgetRegistro` como model — e como código

A Etapa 3 definiu `WidgetRegistro` (tabela) e a Etapa 5 definiu `WidgetSpec` (dataclass). **São a mesma coisa, duas vezes.** O registro declarativo em código já resolve; a tabela não tem quem a edite.

**Correção: apenas `WidgetSpec` em código.** Remover `WidgetRegistro` da Etapa 3.

### 🟡 E3 · `PoliticaAprovacao.condicao` em JSON pode virar uma linguagem

```python
condicao = JSONField()   # {"valor_max": 500, "categorias": ["material"]}
```

Começa assim. Em seis meses alguém precisa de "OR", depois de "valor entre X e Y se o solicitante for de tal unidade" — e o JSON vira um interpretador de expressões escrito nas horas vagas.

**Restrição a aplicar agora:** chaves fechadas, avaliadas por código, sem expressão.

```python
CHAVES_PERMITIDAS = {"valor_max", "valor_min", "categorias", "unidades", "tipos_objeto"}
# Combinação é sempre E lógico. Precisa de OU? Crie duas políticas com `ordem` diferente.
```

O mesmo vale para `ItemCatalogo.formulario` — os 6 tipos de campo são fechados, e **sem campo condicional no V1.0**.

### 🟡 E4 · `WorkspaceProvider` para 3 providers

A abstração custa ~60 linhas para servir 3 implementações no V1.0. É próximo do ponto onde abstrair é prematuro.

**Mantenho** — mas com a restrição explícita de **não estendê-la especulativamente**. Os 4 métodos atuais bastam. Método novo só quando dois providers precisarem do mesmo.

> Se em 12 meses ainda houver 3 providers, foi over-engineering. Se houver 8, foi a decisão certa. **Registro a aposta para que ela seja avaliada, não esquecida.**

---

## 9.4 Onde meu plano está simples demais

Seis lacunas encontradas. **Estas importam mais que as complexidades** — excesso de abstração custa manutenção; ausência de tratamento custa defeito em produção.

### 🔴 L1 · Corrida na decisão de aprovação

Nenhuma etapa especificou controle de concorrência em `EtapaAprovacao`. Dois cenários reais:

- O gestor aprova pelo Workspace no mesmo instante em que o delegado aprova pelo celular
- O usuário clica duas vezes antes do HTMX marcar `htmx-request`

Sem trava, a etapa é decidida duas vezes e a cadeia avança dois passos.

```python
def decidir(pessoa, solicitacao, acao, motivo=""):
    with transaction.atomic():
        etapa = (EtapaAprovacao.objects
                 .select_for_update()
                 .get(solicitacao=solicitacao, ordem=solicitacao.etapa_atual))
        if etapa.status != "aguardando":
            raise JaDecidida(f"Decidida em {etapa.decidido_em} por {etapa.aprovador_efetivo}")
        ...
```

**Correção:** `select_for_update()` em `ST-036`, mais teste de concorrência com duas transações simultâneas. **+2 pontos.**

### 🔴 L2 · Busca sem `unaccent` — e a extensão não existe

`plainto_tsquery('portuguese', 'joao')` **não encontra "João"**. Num sistema em português, isso é defeito no primeiro dia de uso.

Nenhuma migração do projeto cria extensão nenhuma — verifiquei `unaccent`, `pg_trgm` e `btree_gist`: nenhuma está criada.

```python
# workspace/migrations/0001_extensoes.py
operations = [
    UnaccentExtension(),        # busca insensível a acento
    BtreeGistExtension(),       # ExclusionConstraint do TurnoEscala
]
```
```sql
-- e a configuração de busca precisa usá-la
CREATE TEXT SEARCH CONFIGURATION portuguese_unaccent (COPY = portuguese);
ALTER TEXT SEARCH CONFIGURATION portuguese_unaccent
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;
```

**Correção:** nova story `ST-108` (extensões e configuração de busca), **P0**, dependência de `ST-004`. **+1 ponto.**

### 🟠 L3 · `tsvector` do corpo inteiro faz o índice inchar

O plano indexa `titulo || corpo` sem limite. Um manual de 80 páginas em `Documento.corpo` gera um `tsvector` enorme; o GIN cresce e a busca degrada.

```python
tsv = (SearchVector("titulo", weight="A", config="portuguese_unaccent")
       + SearchVector("subtitulo", weight="B", config="portuguese_unaccent")
       + SearchVector(Substr("corpo", 1, 8000), weight="C", config="portuguese_unaccent"))
```
8.000 caracteres cobrem o que é discriminante em uma busca. O resto é ruído estatístico.

### 🟠 L4 · N+1 nos providers

`pending_items()` e `search_documents()` devolvem DTOs, e nenhuma etapa especificou `select_related`. O widget "Meu dia" agrega 3 providers — sem cuidado, são dezenas de queries por carga.

**Correção:** DoD do provider passa a exigir teste com `assertNumQueries`. É o único jeito de impedir a regressão silenciosa.

### 🟠 L5 · Recomputar `PendenciaLeitura` quando o público-alvo muda

Existe o estado `dispensada`, mas não o gatilho. Se a pessoa muda de departamento, quem dispensa a pendência antiga e cria a nova?

**Correção:** sinal `pessoa_alterada` → task que recalcula pendências dos documentos obrigatórios vigentes. Cabe em `ST-047`.

### 🟡 L6 · Idempotência sem armazenamento definido

A [Etapa 5](EXEC_05_ARQUITETURA.md) previu `Idempotency-Key` nas APIs do app nativo, sem dizer onde a chave vive.

**Correção:** chave em Redis com TTL de 24 h, guardando a resposta. É o padrão mais simples que funciona, e o `client_event_id` do `OSEvidencia` já provou o conceito no projeto.

---

## 9.5 Os pontos que estressam o stack

Três lugares onde a escolha tecnológica trabalha no limite. Nenhum é impeditivo; todos merecem spike antes de virar compromisso de prazo.

### ⚠️ P1 · Command Bar sob Alpine CSP

O ⌘K é o componente mais interativo do produto: navegação por teclado, foco preso, debounce, resultado assíncrono, agrupamento.

A distribuição CSP do Alpine **não avalia expressões em atributo**. Nada de `x-on:click="items[i].run()"` — só métodos declarados no componente.

```javascript
Alpine.data('commandBar', () => ({
  aberto: false, q: '', indice: 0, grupos: [],
  abrir()    { this.aberto = true; this.$nextTick(() => this.$refs.input.focus()) },
  descer()   { this.indice = Math.min(this.indice + 1, this.total() - 1) },
  executar() { window.location = this.selecionado().url },
}))
```

É expressável — **mas é o único lugar do V1.0 onde a restrição do CSP realmente aperta.**

**Mitigação:** spike de 1 dia antes da Onda 5. Se não couber, a alternativa é ~150 linhas de JavaScript próprio com nonce, sem Alpine. Aceitável, e melhor que afrouxar a CSP.

### ⚠️ P2 · `ExclusionConstraint` só existe em PostgreSQL

Dev em SQLite não valida sobreposição de turno. `ST-004` (CI em Postgres) cobre, mas o desenvolvedor local pode escrever código que passa localmente e falha no CI.

**Mitigação:** `clean()` equivalente em Python, que roda nos dois ambientes. O banco é a garantia; o `clean()` é a mensagem ao usuário.

### ⚠️ P3 · HTMX e o botão voltar

`hx-push-url` é fácil de esquecer, e o resultado é um botão voltar que sai do Workspace inteiro — a queixa nº 1 de aplicações HTMX mal configuradas.

**Mitigação:** `hx-push-url="true"` como padrão de projeto (`htmx.config`), com exceção declarada em vez de regra declarada. Mais um teste de navegação nas 4 jornadas.

---

## 9.6 Custo de manutenção em dois anos

O que vai doer em 2028 se nada for feito agora.

| Risco de manutenção | Sintoma em 2 anos | Contenção desde já |
|---|---|---|
| **Biblioteca de componentes inchando** | 26 → 70 componentes, metade duplicada | Portão de governança da [Etapa 6 §6.17](EXEC_06_DESIGN_SYSTEM.md); revisão semestral do que não é usado |
| **JSON de política virando linguagem** | Interpretador caseiro sem testes | Chaves fechadas (§9.3 E3); OU exige política nova |
| **Duas famílias de CSS** | Ninguém sabe qual usar em tela nova | Regra `A-02` no CI; toda tela nova é Aurora |
| **Providers implementados de formas diferentes** | Cada domínio com seu jeito, sem contrato real | Suíte de conformidade de provider, rodando contra todos |
| **Índice de busca crescendo** | Reindexação leva horas | Reindexação incremental por origem, não total |
| **`PendenciaLeitura` crescendo** | Documento × pessoa × tempo | Índice parcial já previsto; particionar acima de 1 milhão |
| **`departamento` texto convivendo com FK** | Dois campos, nenhum confiável | Prazo declarado: remoção quando o resíduo for zero |
| **Migrações do V1.0 nunca "fechadas"** | Colunas nullable para sempre | Após o V1.1, migração que aplica `NOT NULL` onde já não há nulo |
| **Cobertura caindo por exceção** | Ratchet baixado "temporariamente" | Baixar ratchet exige justificativa no PR |

### O maior risco de manutenção não é técnico

`R-11` — concentração de conhecimento. 72 mil linhas com um autor principal, e o plano adiciona ~15 mil.

| Contenção | Custo |
|---|---|
| ADR para toda decisão relevante (9 já escritos) | Baixo |
| PRD por módulo ([Etapa 4](EXEC_04_PRD.md)) | Já pago |
| Cobertura como documentação executável | Já no DoD |
| Revisão em dia separado, com checklist, quando solo | Baixo |
| **Uma segunda pessoa** | Alto — e é o único que resolve de verdade |

---

## 9.7 Dívida assumida conscientemente

Dívida registrada não é dívida escondida. Estas são escolhas, não descuidos.

| Dívida | Por que aceitamos | Quando pagar |
|---|---|---|
| `departamento` texto + FK convivendo | Migração destrutiva no V1.0 impediria rollback | Quando o resíduo for zero |
| `UserRole` vivo durante a transição | Nada pode quebrar durante o piloto | Após o V1.0 estabilizado |
| Escala só no Django admin | Editor custa uma tela complexa e não é o valor | V1.1, se `K-OPS-01` provar uso |
| Sem versionamento de conteúdo | Não há histórico para versionar no dia 1 | V1.1 |
| Busca só de pessoas | O difícil é o mecanismo de ACL, e ele fica pronto | V1.1, priorizado por `K-SRC-04` |
| Duas famílias de CSS | Reescrever 155 templates está fora de escopo | Migração por atração, sem data |
| `threading.local()` | [D-01] rebaixou o risco a quase nada | V1.1 |
| Sem virtualização de tabela | Maior conjunto tem 400 linhas | Se passar de 5 mil |
| `a { color: #06b6d4 }` nos templates antigos | Fora do escopo do Workspace | **Correção de 1 linha — vale fazer já** |

---

## 9.8 Alterações ao plano

Consolidado do que muda por causa desta auditoria.

### Correções (obrigatórias)

| # | Alteração | Onde | Δ pontos |
|:-:|---|---|:-:|
| 1 | `ST-041` usa `CacheService.bump_namespace` | Etapa 5 ADR-004, Etapa 7 | **−2** |
| 2 | `validate_file_upload()` obrigatório em CNT, PPL, SVC | DoD | +0 |
| 3 | `pode()` **nunca** usa `cache_user_permissions` + teste que impede | Etapa 5 ADR-005 | +1 |
| 4 | **Nova `ST-108`** — extensões `unaccent`, `btree_gist` e configuração de busca | Onda 0, P0 | **+1** |
| 5 | `select_for_update()` + teste de concorrência em `decidir()` | `ST-036` | **+2** |
| 6 | `Substr("corpo", 1, 8000)` no `tsvector` | `ST-077` | +0 |
| 7 | `assertNumQueries` no DoD de provider | DoD | +0 |
| 8 | Recomputar `PendenciaLeitura` ao mudar público-alvo | `ST-047` | **+1** |
| 9 | Idempotência em Redis, TTL 24 h | `ST-103` | +0 |
| 10 | `hx-push-url` como padrão global | `ST-024` | +0 |

### Simplificações

| # | Alteração | Δ pontos |
|:-:|---|:-:|
| 11 | `Preset` vira constante Python; model só no V1.1 | **−2** |
| 12 | Remover `WidgetRegistro` — `WidgetSpec` em código basta | **−1** |
| 13 | `PoliticaAprovacao.condicao` com chaves fechadas | +0 |
| 14 | `ItemCatalogo.formulario` sem condicional no V1.0 | +0 |

### Decisões técnicas adicionais

| # | Decisão |
|:-:|---|
| 15 | `Documento` e `ItemCatalogo` **não** usam `SoftDeleteModel` — documento vencido é estado, não exclusão; item despublicado idem. Soft delete aqui esconde o ciclo de vida real |
| 16 | `WorkspaceProvider` congelado em 4 métodos no V1.0 |
| 17 | Spikes de §9.9 antes de firmar prazo |

### Efeito no total

```
404 pontos (Etapa 7)
  −5  simplificações
  +5  correções
─────────────────
404 pontos   →   sem alteração material
```

> **O valor desta auditoria não está em pontos.** Está em três defeitos que teriam chegado à produção — corrida na aprovação, busca que não encontra "João", e cache de permissão vencida — e em uma solução que eu ia reconstruir do zero.

---

## 9.9 Spikes obrigatórios

Cinco investigações timeboxed, **antes** de assumir compromisso de data. Total: 5 dias.

| # | Spike | Prazo | Pergunta | Se falhar |
|:-:|---|:-:|---|---|
| **S1** | Alpine CSP no ⌘K | 1 dia | Navegação por teclado e foco preso são expressáveis sem avaliar expressão? | ~150 linhas de JS próprio com nonce |
| **S2** | `PerfilUsuario` contra dump de produção | 1 dia | Quanto tempo de lock a migração exige? | Migração em duas fases, com backfill assíncrono |
| **S3** | CSP de produção com HTMX + Alpine | 0,5 dia | Alguma violação no console? | Ajustar a política **sem** adicionar `unsafe-eval` |
| **S4** | Hook de bloqueio no dispatch do FSM | 1 dia | Onde exatamente o ponto de extensão cabe, sem regressão? | Repensar o ponto de integração |
| **S5** | FTS português com `unaccent` | 0,5 dia | "joao" encontra "João"? Ranking faz sentido? | Avaliar `pg_trgm` como complemento |
| **S6** | Conector do RH | 1 dia | Formato, cadência, volume — **depende de `Q-01`** | Começar por CSV manual |

> **S2 e S6 são os que mais podem mudar o cronograma.** S2 porque toca um modelo com dados reais em produção; S6 porque depende de uma resposta que ainda não temos.

---

## 9.10 Veredito

### Implementabilidade

> **Os 58 itens do V1.0 são implementáveis em Django, Templates, HTMX, Alpine, Tailwind, PostgreSQL, Redis, Celery e WebSockets. Nenhum componente novo de infraestrutura. Nenhum item exige tecnologia fora do stack declarado.**

### Os quatro critérios pedidos

| Critério | Avaliação | Evidência |
|---|:-:|---|
| **Simplicidade** | ✅ Boa, após as 4 simplificações | Sem SPA, sem API para o próprio front, sem Elasticsearch, sem Node em produção |
| **Reuso** | ⚠️ **Era o ponto fraco** | 3 ativos que eu ia reconstruir. Corrigido em §9.1 |
| **Escalabilidade** | ✅ Folgada | 19 req/min no pico. Limites reais registrados e distantes |
| **Custo de manutenção** | ⚠️ Aceitável, com disciplina | 9 riscos mapeados; o maior (`R-11`) é organizacional, não técnico |

### Parecer: **prosseguir, com condições**

| # | Condição | Quando |
|:-:|---|---|
| 1 | Aplicar as 14 alterações de §9.8 nos documentos das Etapas 3, 5 e 7 | Antes da Onda 0 |
| 2 | Executar os 6 spikes de §9.9 | Antes de firmar data |
| 3 | Responder **`Q-01`** (sistema de RH) e **`Q-02`** (dois contratos reais) | `Q-01` antes da Onda 2; `Q-02` antes de `ST-098` |
| 4 | Concluir **`A-01`** — corrigir o material comercial | Antes da próxima proposta |
| 5 | Recalibrar a velocidade ao fim da Onda 1 e republicar a linha do tempo | ~mês 2 |
| 6 | Definir a capacidade: 1 ou 2 pessoas ([Etapa 7 §7.12](EXEC_07_BACKLOG.md)) | Antes da Onda 0 |

### As três coisas que eu vigiaria pessoalmente

1. **Os 20 itens 🔒** — a fundação sem tela é a primeira a ser cortada sob pressão, e cortá-la adia o V1.1 inteiro
2. **A velocidade real da Onda 1** — 9 pontos/semana é premissa de mercado, não medição deste time
3. **`Q-01` e `Q-02`** — as duas perguntas abertas travam a Onda 2 e a trilha B0, e nenhuma se resolve com engenharia

---

## Encerramento do planejamento

| Etapa | Documento | Entrega |
|:-:|---|---|
| 1 | [Escopo e dependências](EXEC_01_ESCOPO_E_DEPENDENCIAS.md) | 139 itens, 19 fusões, 16 riscos, 5 decisões |
| 2 | [MVP](EXEC_02_MVP.md) | V1.0 com 58 itens, 13 exclusões justificadas |
| 3 | [Módulos](EXEC_03_MODULOS.md) | 13 domínios, 21 modelos novos, ADR-001 |
| 4 | [PRD](EXEC_04_PRD.md) | 63 casos de uso, 24 épicos, 149 features, 4 portões |
| 5 | [Arquitetura](EXEC_05_ARQUITETURA.md) | 11 vistas, 9 ADRs, zero infra nova |
| 6 | [Design System](EXEC_06_DESIGN_SYSTEM.md) | 26 componentes, paleta AA, 1 defeito de produção achado |
| 7 | [Backlog](EXEC_07_BACKLOG.md) | 107 stories, 404 pontos, 20 inegociáveis |
| 8 | [Roadmap](EXEC_08_ROADMAP.md) | 4 versões, 9 portões, 10 compromissos |
| 9 | Este documento | Auditoria, 14 alterações, 6 spikes, parecer |

**O planejamento está encerrado. A próxima ação é a Onda 0.**

---

*Etapa 9 de 9 · 3 ativos reusados que seriam reconstruídos · 4 excessos removidos · 6 lacunas fechadas · parecer favorável com 6 condições.*
