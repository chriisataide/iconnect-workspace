# Execução · Etapa 3 — Especificação dos Módulos

> **Documento de arquitetura modular.** Para cada um dos 13 domínios: objetivo, escopo, regras, fluxos, dependências, APIs, permissões, banco de dados, componentes e critérios de aceite. Escopo especificado = **V1.0** ([Etapa 2](EXEC_02_MVP.md)); a fronteira do módulo é declarada para o futuro.
>
> **Agosto/2026** · Etapa 3 de 9 · **Aguarda aprovação antes da Etapa 4**
>
> ⚠️ **Revisado em 12/08/2026 pela [Etapa 10 — Reposicionamento](EXEC_10_REPOSICIONAMENTO.md).** O produto se chama **iConnect Workspace**, e Workspace e Platform são dois produtos — não uma camada sobre o outro. Onde este documento contradiz a Etapa 10, a Etapa 10 vence; §10.7 nomeia cada contradição. Nada aqui foi descartado.

---

## Sumário

- [3.0 Decisão estrutural: onde cada módulo mora](#30-decisão-estrutural-onde-cada-módulo-mora)
- [3.1 Contratos transversais](#31-contratos-transversais)
- [3.2 IDN — Identidade & Organização](#32-idn--identidade--organização)
- [3.3 PLT — Plataforma](#33-plt--plataforma)
- [3.4 APR — Aprovações](#34-apr--aprovações)
- [3.5 SVC — Serviços](#35-svc--serviços)
- [3.6 CNT — Conteúdo](#36-cnt--conteúdo)
- [3.7 COM — Comunicação](#37-com--comunicação)
- [3.8 PPL — Pessoas](#38-ppl--pessoas)
- [3.9 OPS — Operação](#39-ops--operação)
- [3.10 SRC — Busca Global](#310-src--busca-global)
- [3.11 WKS — Workspace](#311-wks--workspace)
- [3.12 AIC — IA & Agentes](#312-aic--ia--agentes)
- [3.13 FIN — Financeiro](#313-fin--financeiro)
- [3.14 REV — Receita & Contrato](#314-rev--receita--contrato)
- [3.15 Matriz consolidada de permissões](#315-matriz-consolidada-de-permissões)
- [3.16 Modelo de dados consolidado](#316-modelo-de-dados-consolidado)
- [3.17 Ordem de construção](#317-ordem-de-construção)

---

## 3.0 Decisão estrutural: onde cada módulo mora

### O problema descoberto ao especificar

Já existem **dois** modelos ligados ao usuário:

| Modelo | Onde | O que tem |
|---|---|---|
| `PerfilUsuario` | [dashboard/models/base.py:920](../dashboard/models/base.py) | `cpf`, `telefone`, `endereco`, `cidade`, `estado`, `cep` (criptografado), **`cargo` e `departamento` como texto livre** |
| `UserRole` | [dashboard/utils/rbac.py:116](../dashboard/utils/rbac.py) | `role` (6 valores planos), `access_type`, `empresa` |

Criar um `Pessoa` novo produziria um **terceiro** cadastro da mesma pessoa — exatamente o problema que `IDN-001` existe para resolver.

### Decisão: **ADR-001 — evoluir o que existe, criar só o que não existe**

| Ação | Alvo | Racional |
|---|---|---|
| **Evoluir in-place** | `PerfilUsuario` → passa a ser a entidade `Pessoa` | Tem dados reais, tem `related_name="perfil"` usado em views e templates. Movê-lo é refatoração de alto risco e zero valor. Ganha FKs, `matricula`, `situacao` e a origem por campo de [D-03] |
| **Evoluir in-place** | `UserRole` → `AtribuicaoPapel` com escopo e vigência | Mesmo motivo. `LEGACY_ROLE_MAP` já existe e serve de ponte |
| **Criar novo** | `Unidade`, `Departamento`, `Papel`, `Delegacao`, `Ausencia`, `Certificacao` | Conceitos que não existem em lugar nenhum |

> **Regra derivada:** *domínio novo nasce em app novo; extensão de domínio existente evolui onde está.* Isso preserva o objetivo de não engordar o `dashboard` sem pagar o custo de uma refatoração que ninguém pediu.

### Alocação em apps Django

```
identidade/          ← APP NOVO · fundação, referenciada por todos
    Unidade · Departamento · Papel · AtribuicaoPapel · Delegacao
    Ausencia · Certificacao · TipoCertificacao
    (PerfilUsuario evoluído permanece em dashboard, com FKs para cá)

workspace/           ← APP NOVO · superfície + motores
    WKS  home, widgets, runtime, preferências
    APR  motor de aprovação
    SVC  catálogo e solicitações
    CNT  documentos e biblioteca
    COM  comunicados
    SRC  índice, ingestão, ⌘K
    PLT  design system, feature flags, provider

dashboard/           ← EXISTENTE · extensões de domínio existente
    PerfilUsuario (evoluído)  ·  UserRole → AtribuicaoPapel
    REV-001 EscopoContrato · REV-002 TabelaPreco   (estendem Contrato)
    AIC-001 FeedbackIA · AIC-002 OrcamentoIA       (estendem copilot)

fsm/                 ← EXISTENTE · extensões de domínio existente
    OPS-001 Escala · TurnoEscala
    FIN-003 ConsumoMaterialOS
    PPL-005 hook de bloqueio no dispatch
```

**Justificativa da alocação:** `Escala` é sobre `Tecnico`; `ConsumoMaterialOS` é sobre `OrdemServico`; `EscopoContrato` é sobre `Contrato`. Todos os três são extensões naturais de agregados existentes. Colocá-los em `workspace` criaria acoplamento reverso — o app da superfície virando dono de dado de domínio, que é justamente o que o `WorkspaceProvider` existe para impedir.

---

## 3.1 Contratos transversais

Definidos uma vez, valem para todos os módulos. Evita repetição e garante consistência.

### 3.1.1 `WorkspaceProvider` — o contrato entre superfície e domínio

```python
# workspace/providers/base.py
class WorkspaceProvider(ABC):
    """Contrato somente-leitura entre o Workspace e um domínio.

    O Workspace NUNCA consulta model de outro domínio diretamente.
    Escrita acontece pelos serviços do próprio domínio.
    """
    key: str                    # "fsm", "helpdesk", "financeiro"
    label: str

    def widgets(self, pessoa) -> list[WidgetSpec]: ...
    def search_documents(self, since=None) -> Iterator[SearchDocumentDTO]: ...
    def quick_actions(self, pessoa) -> list[ActionSpec]: ...
    def pending_items(self, pessoa) -> list[PendingItemDTO]: ...
```

**Regras:**
1. O provider é **somente leitura**. Escrita passa pelos serviços do domínio.
2. Todo método recebe `pessoa` e devolve **já filtrado por permissão**. O Workspace não filtra depois.
3. Provider que levanta exceção **degrada o widget**, nunca a página. Timeout de 3 s por provider.
4. Registro por entry point no `apps.py` do domínio — o Workspace não importa app de domínio.

### 3.1.2 Convenção de API

O stack é HTMX-first. Isso simplifica drasticamente a superfície de API.

| Superfície | Rota | Retorna | Consumidor |
|---|---|---|---|
| **Workspace (HTMX)** | `/workspace/...` | Fragmento HTML | O próprio navegador |
| **JSON pública** | `/api/v1/workspace/...` | JSON (DRF) | App nativo, integrações |
| **WebSocket** | `/ws/workspace/...` | Evento JSON | Contadores e notificações ao vivo |

**Regra:** só existe endpoint JSON quando há consumidor externo declarado. Não se cria API "por padrão" — cada uma é superfície de manutenção e de segurança.

**Convenções:**
- Fragmentos HTMX: `GET` para render, `POST` para ação, resposta com `HX-Trigger` para atualizar contadores irmãos
- Nomes de rota: `workspace:<modulo>_<recurso>_<acao>` — ex. `workspace:apr_bandeja_aprovar`
- Toda ação de escrita: CSRF, verificação de permissão no serviço (não só na view) e registro de auditoria

### 3.1.3 Modelo de permissão

```
Formato:  <dominio>.<acao>.<escopo>
Exemplos: apr.aprovar.equipe · cnt.publicar.departamento · idn.ler.global
```

| Escopo | Alcance | Resolução |
|---|---|---|
| `proprio` | Só os próprios registros | `pessoa == request.pessoa` |
| `equipe` | Liderados diretos e indiretos | Recursivo pelo organograma (`IDN-003`) |
| `departamento` | Todo o departamento | `pessoa.departamento` |
| `unidade` | Toda a unidade | `pessoa.unidade` |
| `global` | Toda a instalação | — |

**Resolução em uma chamada** (`identidade/services/autorizacao.py`):

```python
def pode(pessoa, permissao: str, alvo=None) -> bool:
    """Única porta de autorização do Workspace.

    1. Reúne AtribuicaoPapel vigentes (hoje entre vigencia_inicio/fim)
    2. Soma as delegações ativas recebidas
    3. Casa a permissão e resolve o escopo contra `alvo`
    """
```

**Regra inegociável:** nenhuma view checa permissão por conta própria. Toda checagem passa por `pode()`. Isso torna a matriz de §3.15 executável e testável.

### 3.1.4 Eventos

```python
# Sinais de domínio → Celery (assíncrono) → Channels (tempo real)
workspace.signals.aprovacao_decidida       → reindexa, notifica, atualiza contador
workspace.signals.documento_publicado      → reindexa, dispara leitura obrigatória
workspace.signals.solicitacao_criada       → cria ticket, inicia cadeia de aprovação
identidade.signals.pessoa_sincronizada     → reindexa, resolve divergências
fsm.signals.os_concluida                   → consumo de material, custo, futuro POP
```

**Grupos de Channels:** `ws.pessoa.<id>` (notificações pessoais) e `ws.papel.<chave>` (avisos por papel).

### 3.1.5 Convenções de nomenclatura

| Elemento | Padrão | Exemplo |
|---|---|---|
| Model | Português, singular | `AtribuicaoPapel` |
| Campo | Português, snake_case | `vigencia_fim` |
| Serviço | `<dominio>/services/<assunto>.py` | `workspace/services/aprovacao.py` |
| Template | `workspace/<modulo>/<tela>.html` | `workspace/apr/bandeja.html` |
| Partial HTMX | prefixo `_` | `workspace/apr/_card_aprovacao.html` |
| Componente CSS | `au-` (Aurora) | `au-card`, `au-widget` |
| Permissão | `<dom>.<acao>.<escopo>` | `svc.solicitar.proprio` |

---

## 3.2 IDN — Identidade & Organização

> **É o módulo do caminho crítico. Nada funciona antes dele.**

### Objetivo
Ser a **fonte única de quem é quem** na empresa: identidade, posição na estrutura, o que cada um pode fazer e sobre o quê, e quem responde por quem quando alguém está ausente.

### Escopo V1.0
`IDN-001` a `IDN-007`, `IDN-009`. **Fora:** diretório público (`IDN-008` → V1.1).

### Regras

| # | Regra |
|:-:|---|
| R1 | **Uma pessoa, um registro.** `PerfilUsuario` é a única representação de pessoa. `Tecnico` e `Cliente` referenciam-na, não a duplicam |
| R2 | **Origem por campo** ([D-03]). Cada campo é `espelho` (RH), `proprio` (iConnect) ou `derivado` (RH com override) |
| R3 | **Campo espelho nunca é sobrescrito silenciosamente.** Divergência entra na fila de conflitos e exige decisão humana |
| R4 | **Override em campo derivado exige justificativa** e fica registrado com autor e data |
| R5 | **Papel sem escopo não existe.** Toda `AtribuicaoPapel` tem escopo e vigência |
| R6 | **Vigência é obrigatória no início, opcional no fim.** `vigencia_fim = NULL` significa indeterminado |
| R7 | **Delegação não amplia.** O delegado recebe no máximo o que o delegante tem, e nunca o papel `admin` |
| R8 | **Desligamento revoga.** `situacao = desligado` encerra todas as atribuições e delegações na mesma transação |
| R9 | **Organograma sem ciclo.** Validação impede A → B → A |

### Fluxos

**F1 · Sincronização com o RH**
```
Celery (cadência definida em A-03)
  └─▶ conector lê a base do RH
      └─▶ para cada pessoa: compara campos ESPELHO
          ├─ igual        → nada
          ├─ divergente   → cria ConflitoSincronizacao (status=aberto)
          └─ inexistente  → cria PerfilUsuario (situacao=ativo)
      └─▶ notifica RH: "7 divergências aguardando decisão"
```

**F2 · Resolução de conflito** — RH abre a fila → vê `valor_atual` × `valor_origem` → `[Aceitar origem]` ou `[Manter atual + justificar]` → registrado em auditoria.

**F3 · Atribuição de papel** — admin escolhe pessoa → papel → escopo → vigência → `pode()` passa a refletir na próxima requisição (sem cache de permissão além do request).

**F4 · Delegação** — pessoa que sai de férias delega papéis a outra, por período. `Ausencia` aprovada pode **sugerir** a delegação, nunca criá-la sozinha.

### Dependências
**Recebe de:** nenhuma (é a raiz). **Entrega para:** todos os demais módulos.

### APIs

| Rota | Método | Retorna | Nota |
|---|:-:|---|---|
| `/workspace/perfil/` | GET | HTML | Meu perfil (`PPL-001`) |
| `/workspace/perfil/conflitos/` | GET | HTML | Fila de divergências (papel RH) |
| `/workspace/perfil/conflitos/<id>/resolver/` | POST | HTML | Decisão do conflito |
| `/api/v1/workspace/pessoas/me/` | GET | JSON | **App nativo** — identidade e permissões do usuário |

### Permissões

| Permissão | Quem |
|---|---|
| `idn.ler.proprio` | todos |
| `idn.ler.equipe` | gestor |
| `idn.ler.global` | RH, admin |
| `idn.editar.proprio` | todos (só campos `proprio`) |
| `idn.editar.global` | RH, admin |
| `idn.papel.atribuir` | admin |
| `idn.conflito.resolver` | RH, admin |

### Banco de dados

```python
# identidade/models.py
class Unidade(models.Model):
    codigo, nome, cidade, uf, ativa

class Departamento(models.Model):
    codigo, nome
    unidade       = FK(Unidade, null=True)      # depto pode ser corporativo
    centro_custo  = FK("dashboard.CentroCusto", null=True)
    responsavel   = FK("dashboard.PerfilUsuario", null=True)

class Papel(models.Model):
    chave         = SlugField(unique=True)      # "gestor_operacao"
    nome, descricao
    permissoes    = JSONField(default=list)     # ["apr.aprovar.equipe", ...]
    ativo

class AtribuicaoPapel(models.Model):            # evolui UserRole
    pessoa            = FK("dashboard.PerfilUsuario", related_name="atribuicoes")
    papel             = FK(Papel)
    escopo_tipo       = CharField(choices=["global","unidade","departamento","equipe","proprio"])
    escopo_unidade    = FK(Unidade, null=True)
    escopo_departamento = FK(Departamento, null=True)
    vigencia_inicio   = DateField()
    vigencia_fim      = DateField(null=True)
    criado_por, criado_em
    class Meta:
        constraints = [UniqueConstraint(fields=["pessoa","papel","escopo_tipo",
                                                "escopo_unidade","escopo_departamento",
                                                "vigencia_inicio"],
                                        name="uniq_atribuicao_vigente")]
        indexes = [Index(fields=["pessoa","vigencia_inicio","vigencia_fim"])]

class Delegacao(models.Model):
    delegante, delegado = FK("dashboard.PerfilUsuario", related_name="+")
    papeis            = M2M(Papel)
    inicio, fim       = DateField()
    motivo            = CharField()
    ativa             = BooleanField(default=True)

class ConflitoSincronizacao(models.Model):
    pessoa, campo, valor_atual, valor_origem
    status            = CharField(choices=["aberto","resolvido"])
    resolvido_por, resolvido_em, decisao, justificativa
```

**Evolução de `PerfilUsuario`** (migração em `dashboard`):

```python
+ matricula        = CharField(max_length=30, unique=True, null=True, db_index=True)
+ unidade          = FK("identidade.Unidade", null=True)
+ departamento_fk  = FK("identidade.Departamento", null=True)   # convive com o texto legado
+ gestor           = FK("self", null=True, related_name="liderados")
+ centro_custo     = FK("dashboard.CentroCusto", null=True)
+ situacao         = CharField(choices=["ativo","ferias","afastado","desligado"], default="ativo")
+ data_admissao    = DateField(null=True)
+ origem_campos    = JSONField(default=dict)   # {"cargo": "espelho", "gestor": "derivado"}
+ tecnico          = (reverso do OneToOne existente em fsm.Tecnico.user)
```

> **Nota de migração:** `departamento` (texto) e `departamento_fk` convivem durante a transição. Um comando de gestão faz o casamento por nome e reporta o que não casou. `departamento` texto é removido só quando o resíduo for zero.

### Componentes
`au-perfil-header` · `au-org-chip` (pessoa + cargo + unidade) · `au-conflito-row` (valor atual × origem) · `au-papel-badge` · `au-vigencia-tag`

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Importar a base real de pessoas e reconciliar sem perder registro existente |
| A2 | `pode()` resolve os 5 escopos corretamente, com teste por escopo |
| A3 | Delegação nunca amplia permissão — teste que tenta e falha |
| A4 | Desligamento revoga atribuições e delegações na mesma transação |
| A5 | Organograma rejeita ciclo |
| A6 | Divergência de campo espelho **nunca** sobrescreve — teste com valor conflitante |
| A7 | `pode()` resolve em ≤ 20 ms com organograma de 500 pessoas (cache por request) |

---

## 3.3 PLT — Plataforma

### Objetivo
Fornecer a casca visual, o mecanismo de lançamento controlado e a instrumentação transversal, sem que nenhum módulo funcional precise reimplementá-los.

### Escopo V1.0
`PLT-001` a `PLT-007`, `PLT-010`.

### Regras

| # | Regra |
|:-:|---|
| R1 | **Tailwind só em `workspace/`.** Regra de CI reprova o PR que violar (`A-02`) |
| R2 | Nenhum valor de cor, espaço ou raio fora dos tokens. Hex literal em template reprova revisão |
| R3 | Todo componente entrega **8 estados**: default, hover, focus-visible, active, disabled, loading, error, empty |
| R4 | Dark mode via `prefers-color-scheme` no V1.0. Nenhuma cor definida apenas dentro do bloco escuro |
| R5 | Feature flag avaliada **no servidor**. Nunca esconder no CSS o que não deveria ser servido |
| R6 | Componente novo só entra na biblioteca com uso real. Nada especulativo |

### Fluxos

**F1 · Rollout** — flag `workspace_ativo` por papel → usuário com flag vê o Workspace em `/`, sem flag continua no fluxo atual → rollback é desligar a flag (≤ 5 min, sem deploy).

**F2 · Build de CSS** — `workspace/static/workspace/src.css` → Tailwind CLI com `content` limitado a `workspace/templates/**` → saída em `workspace/static/workspace/aurora.css` → `collectstatic`. **Não passa pelo `compressor`** nem pelo pipeline do Material Dashboard.

### Dependências
**Recebe de:** IDN (papel para flags). **Entrega para:** todos.

### APIs
Nenhuma pública. `PLT` é biblioteca e infraestrutura.

### Permissões
`plt.flag.gerenciar` → admin.

### Banco de dados

```python
class FeatureFlag(models.Model):
    chave        = SlugField(unique=True)
    descricao
    ativa_global = BooleanField(default=False)
    papeis       = M2M("identidade.Papel", blank=True)   # vazio = todos
    pessoas      = M2M("dashboard.PerfilUsuario", blank=True)  # override individual
    atualizado_por, atualizado_em
```

### Componentes
Inventário fechado na **Etapa 6**. No V1.0, apenas os efetivamente usados — estimativa: ~24 componentes.

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | `aurora.css` gerado sem tocar em nenhum arquivo fora de `workspace/` |
| A2 | CI reprova classe Tailwind fora de `workspace/` |
| A3 | Flag liga e desliga o Workspace por papel, verificado em produção, ≤ 5 min |
| A4 | Toda cor tem definição fora de bloco de media query — verificado por lint de CSS |
| A5 | Gate de cobertura ativo em `dashboard`, `fsm` e `km_audit` |
| A6 | Nenhum estilo do Material Dashboard vaza para `workspace/` — verificado visualmente e por especificidade |

---

## 3.4 APR — Aprovações

> **Âncora de retorno diário nº 1. É o widget que faz a gestão abrir o Workspace todo dia.**

### Objetivo
Ser o **único motor de aprovação** da plataforma — qualquer módulo que precise de "alguém precisa autorizar" usa este, sem reimplementar fila, cadeia, delegação ou auditoria.

### Escopo V1.0
`APR-001` a `APR-005`. **Fora:** contexto orçamentário (`APR-006` → V1.1), escalonamento (`APR-007` → V1.1), canal externo (`APR-008` → V2).

### Regras

| # | Regra |
|:-:|---|
| R1 | **Aprovação é genérica.** Referencia o objeto por `GenericForeignKey`. O motor não conhece "reembolso" nem "férias" |
| R2 | **A cadeia é resolvida na criação e congelada.** Mudança de organograma depois não altera pedido em curso |
| R3 | **Uma etapa por vez.** Etapa N+1 só abre quando N é aprovada |
| R4 | **Reprovação encerra a cadeia.** Não existe "reprovado mas segue" |
| R5 | **Devolução exige motivo** com no mínimo 10 caracteres, e volta ao solicitante — não é reprovação |
| R6 | **Ninguém aprova o próprio pedido.** Nem por delegação. Se a cadeia resolver para o solicitante, sobe um nível |
| R7 | **Auto-aprovação é registrada como decisão**, com `decidido_por = NULL` e `motivo = "dentro da política X"`. Nunca é invisível |
| R8 | **Lote é atômico por item**, não por lote. 5 de 6 aprovados é resultado válido |
| R9 | **Delegação é resolvida no momento da decisão**, não na criação. Delegar depois do pedido criado funciona |

### Fluxos

**F1 · Ciclo de vida**
```
Solicitação criada
   └─▶ PoliticaAprovacao avalia (tipo, valor, solicitante, centro de custo)
       ├─ dentro da política  → aprovada automaticamente, registrada, segue
       └─ fora                → monta CadeiaAprovacao [etapa1, etapa2, ...]
                                 └─▶ etapa 1 aberta → notifica aprovador
                                     ├─ [Aprovar]  → próxima etapa ou concluída
                                     ├─ [Reprovar] → encerra
                                     └─ [Devolver] → volta ao solicitante (motivo obrigatório)
```

**F2 · Resolução do aprovador de uma etapa**
```
1. Delegação ativa recebida por alguém para este papel?   → delegado
2. Senão, quem tem `apr.aprovar.<escopo>` no escopo do pedido?
3. É o próprio solicitante?  → sobe um nível no organograma (R6)
4. Ninguém encontrado?       → etapa vai para `pendente_configuracao` + alerta ao admin
```
> **Passo 4 é obrigatório.** Cadeia sem aprovador não pode falhar silenciosamente — é a falha clássica de motor de aprovação.

**F3 · Lote** — seleciona N cards → `[Aprovar selecionados]` → cada um em sua transação → resultado consolidado ("5 aprovados, 1 falhou: sem permissão").

### Dependências
**Recebe de:** IDN (organograma, delegação, `pode()`). **Entrega para:** SVC, FIN, PPL, CNT.

### APIs

| Rota | Método | Retorna |
|---|:-:|---|
| `/workspace/aprovacoes/` | GET | HTML — bandeja completa |
| `/workspace/aprovacoes/widget/` | GET | HTML — partial do widget (`WKS-005`) |
| `/workspace/aprovacoes/<id>/aprovar/` | POST | HTML — card atualizado + `HX-Trigger: apr:contador` |
| `/workspace/aprovacoes/<id>/reprovar/` | POST | HTML |
| `/workspace/aprovacoes/<id>/devolver/` | POST | HTML — exige `motivo` |
| `/workspace/aprovacoes/lote/` | POST | HTML — resultado consolidado |
| `/api/v1/workspace/aprovacoes/` | GET | JSON — **app nativo** |

### Permissões

| Permissão | Quem |
|---|---|
| `apr.ver.proprio` | todos (as que criei) |
| `apr.aprovar.equipe` | gestor |
| `apr.aprovar.departamento` | gestor de departamento |
| `apr.aprovar.global` | diretoria |
| `apr.politica.gerenciar` | admin |

### Banco de dados

```python
# workspace/models/aprovacao.py
class PoliticaAprovacao(models.Model):
    chave, nome
    tipo_objeto     = FK(ContentType)
    condicao        = JSONField()   # {"valor_max": 500, "categorias": ["material"]}
    auto_aprovar    = BooleanField(default=False)
    etapas          = JSONField()   # [{"papel":"gestor","escopo":"equipe","valor_min":0}, ...]
    ativa, ordem                     # avaliação por `ordem`; primeira que casar vence

class SolicitacaoAprovacao(models.Model):
    objeto_type, objeto_id, objeto = GenericForeignKey
    solicitante     = FK("dashboard.PerfilUsuario")
    titulo, resumo
    valor           = DecimalField(null=True)
    centro_custo    = FK("dashboard.CentroCusto", null=True)
    politica        = FK(PoliticaAprovacao, null=True)
    status          = CharField(choices=["em_aprovacao","aprovada","reprovada","devolvida","cancelada"])
    etapa_atual     = PositiveSmallIntegerField(default=1)
    criada_em, concluida_em
    class Meta:
        indexes = [Index(fields=["status","etapa_atual"]),
                   Index(fields=["solicitante","status"])]

class EtapaAprovacao(models.Model):
    solicitacao     = FK(SolicitacaoAprovacao, related_name="etapas_registro")
    ordem           = PositiveSmallIntegerField()
    aprovador       = FK("dashboard.PerfilUsuario", null=True)   # NULL = auto
    aprovador_efetivo = FK("dashboard.PerfilUsuario", null=True, related_name="+")  # se delegado
    status          = CharField(choices=["aguardando","aprovada","reprovada","devolvida","pendente_configuracao"])
    decidido_em, motivo
    class Meta:
        constraints = [UniqueConstraint(fields=["solicitacao","ordem"], name="uniq_etapa_ordem")]
```

### Componentes
`au-aprovacao-card` (título, solicitante, valor, idade, ações) · `au-aprovacao-lote-bar` · `au-cadeia-stepper` · `au-motivo-dialog` · `au-contador-badge`

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Aprovar da home, sem navegar, com o card atualizando em ≤ 400 ms |
| A2 | Lote de 10 com 1 falha devolve 9 aprovados e 1 erro nomeado |
| A3 | Solicitante nunca aparece como aprovador do próprio pedido — teste explícito |
| A4 | Delegação criada **depois** do pedido é respeitada na decisão |
| A5 | Cadeia sem aprovador vai para `pendente_configuracao` e alerta o admin — nunca some |
| A6 | Auto-aprovação gera registro de decisão consultável |
| A7 | Mudança de organograma não altera cadeia de pedido em curso |
| A8 | Devolução sem motivo é rejeitada pelo serviço, não só pelo formulário |

---

## 3.5 SVC — Serviços

### Objetivo
Ser o **lugar único onde qualquer pedido interno nasce**, com o mínimo de digitação possível — porque a identidade já sabe quase tudo.

### Escopo V1.0
`SVC-001`, `SVC-002`, `SVC-003`, `SVC-005` (6 itens). **Fora:** timeline (`SVC-004` → V1.1), prazo medido (`SVC-006` → V1.1), deflexão (`SVC-007` → V1.1).

### Regras

| # | Regra |
|:-:|---|
| R1 | **Máximo 3 campos livres por item.** O resto deriva da identidade. Item com mais de 3 não é publicado |
| R2 | **Todo item tem dono nomeado.** Item sem dono não é publicado (mitiga `R-19`) |
| R3 | **Navegação por problema, nunca por departamento.** Departamento é roteamento, não taxonomia |
| R4 | **A solicitação vira ticket no módulo destino.** O catálogo não é um segundo sistema de chamado |
| R5 | Item com `exige_aprovacao` cria `SolicitacaoAprovacao` na mesma transação do ticket |
| R6 | Formulário é declarativo (JSON), não código. Novo item de catálogo não exige deploy |

### Fluxos

**F1 · Solicitar**
```
⌘K ou Catálogo  →  item  →  formulário pré-preenchido
   (unidade, centro de custo, gestor, equipamento vinculado vêm de IDN)
   →  [Enviar]
      ├─ cria Ticket no módulo destino (categoria/fila do item)
      ├─ se exige_aprovacao → cria SolicitacaoAprovacao (APR)
      └─ aparece em WKS-007 "Meu dia"
```

**F2 · Publicar item** (admin) — define dono, destino, formulário JSON, política de aprovação, SLA → validação de R1 e R2 → publicado.

### Dependências
**Recebe de:** IDN (pré-preenchimento, roteamento), APR (aprovação), dashboard (Ticket). **Entrega para:** WKS, SRC.

### APIs

| Rota | Método | Retorna |
|---|:-:|---|
| `/workspace/servicos/` | GET | HTML — catálogo com busca |
| `/workspace/servicos/<slug>/` | GET | HTML — formulário pré-preenchido |
| `/workspace/servicos/<slug>/solicitar/` | POST | HTML — confirmação + link |

### Permissões

| Permissão | Quem |
|---|---|
| `svc.solicitar.proprio` | todos |
| `svc.solicitar.equipe` | gestor (pedir para liderado) |
| `svc.catalogo.gerenciar` | admin |

### Banco de dados

```python
class ItemCatalogo(models.Model):
    slug            = SlugField(unique=True)
    nome, descricao, icone
    grupo           = CharField(choices=["acesso","equipamento","trabalho","dinheiro","espaco"])
    dono            = FK("dashboard.PerfilUsuario")          # R2 — obrigatório
    destino_categoria = FK("dashboard.CategoriaTicket")
    formulario      = JSONField()   # [{"campo":"justificativa","tipo":"texto","obrigatorio":true}]
    politica_aprovacao = FK("workspace.PoliticaAprovacao", null=True)
    sla_horas       = PositiveIntegerField(null=True)
    publicado       = BooleanField(default=False)
    def clean(self):  # R1 + R2
        if len([c for c in self.formulario if c.get("tipo") in ("texto","textarea")]) > 3:
            raise ValidationError("Máximo 3 campos livres")

class Solicitacao(models.Model):
    item            = FK(ItemCatalogo)
    solicitante     = FK("dashboard.PerfilUsuario")
    para            = FK("dashboard.PerfilUsuario", related_name="+")  # normalmente = solicitante
    dados           = JSONField()
    ticket          = FK("dashboard.Ticket", null=True)
    aprovacao       = FK("workspace.SolicitacaoAprovacao", null=True)
    criada_em
```

**Catálogo inicial do V1.0 — 6 itens, com dono a nomear antes do lançamento:**

| Slug | Nome | Grupo | Aprovação | Destino |
|---|---|---|:-:|---|
| `acesso-sistema` | Acesso a sistema | acesso | gestor | TI |
| `equipamento` | Equipamento de trabalho | equipamento | gestor + valor | TI |
| `ferias` | Solicitar férias | trabalho | gestor | RH |
| `reembolso` | Reembolso de despesa | dinheiro | gestor + valor | Financeiro |
| `compra-material` | Compra de material | dinheiro | gestor + valor | Compras |
| `facilities` | Manutenção predial | espaco | — (auto) | Facilities |

### Componentes
`au-catalogo-grid` · `au-servico-card` · `au-form-dinamico` (render do JSON) · `au-campo-derivado` (mostra o valor com ícone de "vem do seu perfil")

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Os 6 itens geram ticket na categoria correta |
| A2 | Item com aprovação cria a solicitação de aprovação na mesma transação — falha em uma reverte a outra |
| A3 | Formulário nunca pede dado que a identidade já tem |
| A4 | Item sem dono não pode ser publicado — validação no model |
| A5 | Item com 4 campos livres é rejeitado |
| A6 | Novo item de catálogo criado sem deploy |

---

## 3.6 CNT — Conteúdo

### Objetivo
Ser o repositório único de conteúdo institucional com **dono, público-alvo e vigência** — as três coisas que faltam em toda intranet e que transformam documento em prova de conformidade.

### Escopo V1.0
`CNT-001`, `CNT-004`, `CNT-005`. **Fora:** versionamento (`CNT-002` → V1.1), fluxo de revisão (`CNT-003` → V1.1), migração do KB (`CNT-006` → V1.1).

### Regras

| # | Regra |
|:-:|---|
| R1 | **Todo documento tem dono.** Sem dono não publica |
| R2 | **Classificação define visibilidade:** `publico` · `interno` · `restrito` (por público-alvo) · `confidencial` (lista nominal) |
| R3 | **`publico_alvo` gera `acl_subjects`** para o índice de busca (`SRC-001`). Uma regra, dois consumidores |
| R4 | Documento com `vigencia_fim` passada some da biblioteca e do índice — mas não é apagado |
| R5 | `leitura_obrigatoria` gera pendência para **todos** do público-alvo, inclusive quem entrar depois |
| R6 | O KB existente (`ArtigoConhecimento`) **não é tocado** no V1.0 |

### Fluxos

**F1 · Publicar** — autor cria → tipo, dono, classificação, público-alvo, vigência → `[Publicar]` → sinal `documento_publicado` → indexa (SRC) + gera pendências de leitura (se obrigatório).

**F2 · Leitura confirmada**
```
Documento obrigatório publicado
  └─▶ resolve público-alvo → cria PendenciaLeitura para cada pessoa
      └─▶ aparece em WKS-007 e (se crítico) na Zona 1
          └─▶ [Li e confirmo] → registra pessoa, data, IP, versão
              └─▶ COM-004 mostra ao gestor: "12 de 15 confirmaram"
```

### Dependências
**Recebe de:** IDN (público-alvo, dono). **Entrega para:** COM, SRC, WKS.

### APIs

| Rota | Método | Retorna |
|---|:-:|---|
| `/workspace/biblioteca/` | GET | HTML — lista com filtros |
| `/workspace/biblioteca/<slug>/` | GET | HTML — visualização |
| `/workspace/biblioteca/<slug>/confirmar/` | POST | HTML — registra leitura |
| `/workspace/biblioteca/novo/` | GET/POST | HTML — publicação |

### Permissões

| Permissão | Quem |
|---|---|
| `cnt.ler.publico` | todos |
| `cnt.ler.restrito` | conforme `publico_alvo` |
| `cnt.publicar.departamento` | dono de conteúdo do departamento |
| `cnt.publicar.global` | admin, qualidade |

### Banco de dados

```python
class Documento(models.Model):
    slug            = SlugField(unique=True)
    tipo            = CharField(choices=["pop","politica","norma","manual","contrato",
                                         "template","ata","fluxograma","tecnico"])
    titulo, resumo
    corpo           = TextField(blank=True)
    arquivo         = FileField(null=True, blank=True)
    dono            = FK("dashboard.PerfilUsuario")             # R1
    departamento    = FK("identidade.Departamento", null=True)
    classificacao   = CharField(choices=["publico","interno","restrito","confidencial"])
    publico_papeis       = M2M("identidade.Papel", blank=True)
    publico_departamentos = M2M("identidade.Departamento", blank=True)
    publico_unidades     = M2M("identidade.Unidade", blank=True)
    vigencia_inicio, vigencia_fim = DateField(null=True)
    leitura_obrigatoria  = BooleanField(default=False)
    publicado, publicado_em, criado_em, atualizado_em

    def acl_subjects(self) -> list[str]:
        """R3 — alimenta SRC-001."""
        if self.classificacao in ("publico", "interno"):
            return ["*"]
        return ([f"papel:{p.chave}" for p in self.publico_papeis.all()] +
                [f"depto:{d.id}"    for d in self.publico_departamentos.all()] +
                [f"unid:{u.id}"     for u in self.publico_unidades.all()])

class PendenciaLeitura(models.Model):
    documento, pessoa
    confirmada_em   = DateTimeField(null=True)
    ip              = GenericIPAddressField(null=True)
    class Meta:
        constraints = [UniqueConstraint(fields=["documento","pessoa"], name="uniq_pendencia")]
        indexes = [Index(fields=["pessoa","confirmada_em"])]
```

### Componentes
`au-doc-card` · `au-doc-viewer` · `au-classificacao-badge` · `au-confirmar-leitura` · `au-vigencia-tag`

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Documento restrito não aparece na biblioteca nem na busca de quem não é público-alvo |
| A2 | `acl_subjects()` produz o mesmo resultado usado pela biblioteca e pelo índice |
| A3 | Documento vencido some da lista e do índice, e continua acessível por link direto para quem tem permissão |
| A4 | Pessoa admitida depois da publicação recebe a pendência de leitura |
| A5 | Confirmação registra pessoa, data e IP |
| A6 | O KB atual continua funcionando sem alteração |

---

## 3.7 COM — Comunicação

> **Âncora de retorno diário nº 3, e o KPI que vale dinheiro em auditoria.**

### Objetivo
Garantir que a comunicação institucional **chegue e seja comprovadamente lida** — não que seja curtida.

### Escopo V1.0
`COM-001` a `COM-004`.

### Regras

| # | Regra |
|:-:|---|
| R1 | **Três classes.** `informativo` (aparece) · `obrigatorio` (gera pendência) · `critico` (bloqueia a navegação até o aceite) |
| R2 | **Crítico é escasso por design.** Só `com.publicar.global` pode criar, e o sistema alerta se houver mais de 1 ativo |
| R3 | Comunicado é um `Documento` com `tipo="comunicado"`. **Não é um segundo modelo de conteúdo** |
| R4 | Público-alvo por regra, nunca lista manual de pessoas |
| R5 | Comunicado publicado **não é editado** — publica-se uma correção vinculada (V1.1 formaliza; V1.0 apenas impede a edição) |
| R6 | Bloqueio do crítico é no **middleware do Workspace**, não no JavaScript |

### Fluxos

**F1 · Publicar** — autor escolhe classe e público → agenda ou publica → gera `PendenciaLeitura` (obrigatório/crítico) → notifica via Channels.

**F2 · Bloqueio do crítico**
```
Requisição em /workspace/*
  └─▶ ComunicadoCriticoMiddleware
      ├─ há crítico ativo sem confirmação para esta pessoa?
      │   └─▶ redireciona para /workspace/mural/<slug>/  (sem link de escape)
      └─ não → segue
```
> Exceções: rota de logout e a própria rota de confirmação. Sem isso, o usuário fica preso de verdade.

### Dependências
**Recebe de:** CNT (`Documento`, `PendenciaLeitura`), IDN (público-alvo). **Entrega para:** WKS.

### APIs

| Rota | Método | Retorna |
|---|:-:|---|
| `/workspace/mural/` | GET | HTML |
| `/workspace/mural/<slug>/` | GET | HTML |
| `/workspace/mural/<slug>/confirmar/` | POST | HTML |
| `/workspace/mural/<slug>/relatorio/` | GET | HTML — quem confirmou (gestor) |
| `/api/v1/workspace/comunicados/` | GET | JSON — **app nativo**, para o técnico receber comunicado |

### Permissões

| Permissão | Quem |
|---|---|
| `com.ler` | todos |
| `com.publicar.departamento` | comunicação do departamento |
| `com.publicar.global` | comunicação interna, admin |
| `com.relatorio.equipe` | gestor |

### Banco de dados

Reusa `Documento` com `tipo="comunicado"`, mais:

```python
class Comunicado(models.Model):          # extensão 1:1 de Documento
    documento    = OneToOneField(Documento, related_name="comunicado")
    classe       = CharField(choices=["informativo","obrigatorio","critico"])
    publicar_em  = DateTimeField(null=True)
    expira_em    = DateTimeField(null=True)
    autor        = FK("dashboard.PerfilUsuario")
```

### Componentes
`au-comunicado-card` · `au-comunicado-critico` (tela cheia) · `au-classe-badge` · `au-confirmacao-progresso` (12/15) · `au-mural-lista`

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Crítico bloqueia toda rota do Workspace até a confirmação — teste em 5 rotas |
| A2 | Logout continua acessível durante o bloqueio |
| A3 | Público-alvo por regra alcança exatamente quem deve |
| A4 | Relatório mostra confirmados e pendentes, filtrável pelo gestor |
| A5 | Comunicado publicado não pode ser editado |
| A6 | App nativo recebe comunicados via JSON com o mesmo filtro de público-alvo |

---

## 3.8 PPL — Pessoas

### Objetivo
Dar ao colaborador visibilidade e controle sobre seus próprios dados, e à operação a garantia de que **quem executa está habilitado**.

### Escopo V1.0
`PPL-001`, `PPL-003`, `PPL-004`, `PPL-005`, `PPL-006`. **Fora:** documentos pessoais (`PPL-002` → V1.1, por LGPD).

### Regras

| # | Regra |
|:-:|---|
| R1 | Colaborador edita apenas campos `proprio`. Campos espelho são somente leitura, com origem visível |
| R2 | **Certificação vencida bloqueia despacho** da OS que exige a skill correspondente |
| R3 | Bloqueio é **explícito**: quem despacha vê o motivo e quem está habilitado no lugar |
| R4 | Alerta de vencimento em 90, 30, 15 e 5 dias — para a pessoa **e** para o gestor |
| R5 | `Ausencia` aprovada muda `situacao` da pessoa e aparece na cobertura de escala |
| R6 | **`PPL-002` fora do V1.0.** Nenhum dado de saúde entra antes da política de retenção (`A-03`, `R-12`) |

### Fluxos

**F1 · Bloqueio por certificação**
```
fsm.dispatch tenta atribuir OS ao técnico
   └─▶ hook `identidade.services.habilitacao.pode_executar(tecnico, os)`
       ├─ para cada skill exigida pela OS:
       │     certificação vigente?  (vigencia_fim >= hoje)
       ├─ tudo ok       → prossegue
       └─ alguma vencida → recusa + motivo + lista de técnicos habilitados
```

**F2 · Alerta de vencimento** — task diária → certificações vencendo em 90/30/15/5 → notifica pessoa e gestor → registra para não repetir no mesmo marco.

### Dependências
**Recebe de:** IDN. **Entrega para:** OPS (escala), FSM (dispatch), WKS.

### APIs

| Rota | Método | Retorna |
|---|:-:|---|
| `/workspace/perfil/` | GET/POST | HTML |
| `/workspace/ausencias/` | GET | HTML |
| `/api/v1/workspace/habilitacao/<tecnico_id>/` | GET | JSON — **consumido pelo dispatch do FSM** |

### Permissões

| Permissão | Quem |
|---|---|
| `ppl.perfil.editar.proprio` | todos |
| `ppl.ausencia.ver.equipe` | gestor |
| `ppl.certificacao.gerenciar` | RH, gestor de operação |
| `ppl.certificacao.ver.equipe` | gestor |

### Banco de dados

```python
class TipoCertificacao(models.Model):
    codigo          = SlugField(unique=True)      # "nr10", "nr35"
    nome, descricao
    skill           = FK("fsm.Skill", null=True)  # liga certificação ↔ competência da OS
    validade_meses  = PositiveSmallIntegerField(null=True)
    bloqueia_despacho = BooleanField(default=True)

class Certificacao(models.Model):
    pessoa          = FK("dashboard.PerfilUsuario", related_name="certificacoes")
    tipo            = FK(TipoCertificacao)
    numero, emissor = CharField(blank=True)
    emissao         = DateField()
    vigencia_fim    = DateField(db_index=True)
    evidencia       = FileField(null=True, blank=True)
    class Meta:
        indexes = [Index(fields=["pessoa","vigencia_fim"]),
                   Index(fields=["tipo","vigencia_fim"])]

class Ausencia(models.Model):
    pessoa          = FK("dashboard.PerfilUsuario", related_name="ausencias")
    tipo            = CharField(choices=["ferias","afastamento","folga","licenca"])
    inicio, fim     = DateField()
    aprovacao       = FK("workspace.SolicitacaoAprovacao", null=True)
    status          = CharField(choices=["solicitada","aprovada","cancelada"])
    class Meta:
        indexes = [Index(fields=["pessoa","inicio","fim"])]

class AlertaVencimento(models.Model):
    certificacao, marco = PositiveSmallIntegerField()   # 90|30|15|5
    enviado_em
    class Meta:
        constraints = [UniqueConstraint(fields=["certificacao","marco"], name="uniq_alerta_marco")]
```

### Componentes
`au-perfil-form` · `au-campo-espelho` (somente leitura + origem) · `au-certificacao-row` (com semáforo de validade) · `au-ausencia-calendario` · `au-bloqueio-alerta`

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Técnico com NR vencida **não** é despachado para OS que exige a skill |
| A2 | O motivo do bloqueio aparece para quem despacha, com alternativas habilitadas |
| A3 | Alerta dispara nos 4 marcos, sem repetir |
| A4 | Campo espelho não é editável pelo colaborador |
| A5 | Ausência aprovada reflete na cobertura de escala |
| A6 | Nenhum campo de dado de saúde existe no schema do V1.0 |

---

## 3.9 OPS — Operação

> **Âncora de retorno diário nº 2. Hoje isso vive em planilha e grupo de WhatsApp.**

### Objetivo
Tornar a escala um **objeto de primeira classe** — quem está trabalhando, quem está de plantão, quem cobre quem, e se está habilitado.

### Escopo V1.0
`OPS-001` — modelo + Django admin + widget de leitura. **Editor no Workspace é V1.1.**

### Regras

| # | Regra |
|:-:|---|
| R1 | Turno tem tipo: `normal` · `plantao` · `sobreaviso` |
| R2 | **Uma pessoa não está em dois turnos sobrepostos** — constraint de banco, não validação de formulário |
| R3 | Ausência aprovada gera **lacuna de cobertura**, sinalizada — o sistema não remaneja sozinho |
| R4 | O widget mostra **agora** e **a semana**. Nada de histórico no V1.0 |
| R5 | Escala é por `Unidade` — plantão é sempre de alguma base |

### Fluxos

**F1 · Publicar escala (V1.0, via admin)** — gestor cria turnos no Django admin → validação de sobreposição e de habilitação (`PPL-005`) → publicada → visível no widget.

**F2 · Ver plantão agora** — widget consulta turnos ativos no instante → mostra nome, telefone, unidade e tipo → um clique abre o contato.

### Dependências
**Recebe de:** IDN, PPL (ausência, certificação). **Entrega para:** WKS.

### APIs

| Rota | Método | Retorna |
|---|:-:|---|
| `/workspace/escala/widget/` | GET | HTML — partial (`WKS-008`) |
| `/workspace/escala/` | GET | HTML — semana |
| `/api/v1/workspace/escala/atual/` | GET | JSON — **app nativo** e integrações |

### Permissões

| Permissão | Quem |
|---|---|
| `ops.escala.ver.unidade` | todos da unidade |
| `ops.escala.ver.global` | operação, diretoria |
| `ops.escala.gerenciar.unidade` | gestor de operação |

### Banco de dados

```python
# fsm/models_escala.py
class Escala(models.Model):
    unidade       = FK("identidade.Unidade")
    inicio, fim   = DateField()          # normalmente uma semana
    publicada     = BooleanField(default=False)
    criada_por, criada_em

class TurnoEscala(models.Model):
    escala        = FK(Escala, related_name="turnos")
    pessoa        = FK("dashboard.PerfilUsuario")
    tipo          = CharField(choices=["normal","plantao","sobreaviso"])
    inicio, fim   = DateTimeField()
    observacao    = CharField(blank=True)
    class Meta:
        constraints = [
            ExclusionConstraint(                       # R2 — no banco
                name="sem_turno_sobreposto",
                expressions=[(TsTzRange("inicio","fim", RangeBoundary()), RangeOperators.OVERLAPS),
                             ("pessoa", RangeOperators.EQUAL)],
            ),
        ]
        indexes = [Index(fields=["inicio","fim"]), Index(fields=["pessoa","inicio"])]
```

> **`ExclusionConstraint` exige PostgreSQL com `btree_gist`.** Em SQLite (dev), a validação cai para o `clean()`. Documentado como diferença conhecida entre ambientes.

### Componentes
`au-escala-agora` (quem está de plantão) · `au-escala-semana` (grade) · `au-turno-chip` · `au-cobertura-alerta` (lacuna)

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Widget mostra corretamente quem está de plantão neste instante |
| A2 | Turno sobreposto é rejeitado pelo banco em PostgreSQL |
| A3 | Ausência aprovada aparece como lacuna de cobertura |
| A4 | Escala de uma unidade não é visível para quem não tem escopo |
| A5 | Técnico sem certificação vigente é sinalizado ao ser colocado em turno |

---

## 3.10 SRC — Busca Global

### Objetivo
Ser a navegação real do produto — um campo que aceita objeto, ação e destino, **sem nunca mostrar o que a pessoa não pode ver**.

### Escopo V1.0
`SRC-001` a `SRC-004`, com **uma única fonte de ingestão: `Pessoa`**.

### Regras

| # | Regra |
|:-:|---|
| R1 | **ACL é `WHERE` no índice, nunca filtro em Python depois.** Filtrar depois vaza contagem, ordenação e trecho |
| R2 | `acl_subjects` é array. `["*"]` = visível a todos os autenticados |
| R3 | Camada local responde em ≤ 120 ms sem tocar o servidor |
| R4 | Reindexação é assíncrona (Celery), disparada por sinal do domínio |
| R5 | **Nenhum resultado sem permissão, nem como contagem.** "3 resultados ocultos" é vazamento |
| R6 | Fonte nova entra por `WorkspaceProvider.search_documents()`. O índice não conhece o domínio |

### Fluxos

**F1 · Buscar**
```
⌘K aberto
  ├─ 0 ms     camada local: recentes, favoritos, navegação, ações  (Alpine, client-side)
  └─ debounce 200 ms → GET /workspace/buscar/?q=
       └─▶ SELECT ... FROM search_document
           WHERE acl_subjects && %(subjects)s          ← R1
             AND tsv @@ plainto_tsquery('portuguese', %(q)s)
           ORDER BY ts_rank(tsv, ...) DESC LIMIT 20
       └─▶ agrupa por tipo → fragmento HTML
```

**F2 · Indexação** — sinal do domínio → task Celery → provider devolve `SearchDocumentDTO` → upsert com `acl_subjects` recalculado.

### Dependências
**Recebe de:** IDN (subjects da pessoa), providers. **Entrega para:** WKS.

### APIs

| Rota | Método | Retorna |
|---|:-:|---|
| `/workspace/buscar/` | GET | HTML — fragmento de resultados |
| `/workspace/buscar/acoes/` | GET | JSON — catálogo de ações do ⌘K (leve, cacheável) |

### Permissões
Nenhuma permissão própria. **A busca herda a permissão da fonte** — é o ponto central do módulo.

### Banco de dados

```python
class SearchDocument(models.Model):
    origem        = CharField(db_index=True)       # "pessoa","documento","ticket","os"
    origem_id     = CharField(db_index=True)
    titulo        = CharField(max_length=300)
    subtitulo     = CharField(max_length=300, blank=True)
    corpo         = TextField(blank=True)
    url           = CharField(max_length=500)
    icone         = CharField(max_length=40, blank=True)
    acl_subjects  = ArrayField(CharField(max_length=60), default=list)   # R2
    tsv           = SearchVectorField(null=True)
    atualizado_em = DateTimeField(auto_now=True)
    class Meta:
        constraints = [UniqueConstraint(fields=["origem","origem_id"], name="uniq_origem")]
        indexes = [
            GinIndex(fields=["tsv"]),
            GinIndex(fields=["acl_subjects"]),      # essencial para o && ser rápido
            Index(fields=["origem","atualizado_em"]),
        ]
```

**Subjects de uma pessoa** (`identidade.services.busca.subjects_de(pessoa)`):
```python
["*", f"pessoa:{p.id}", f"depto:{p.departamento_fk_id}", f"unid:{p.unidade_id}",
 *[f"papel:{a.papel.chave}" for a in atribuicoes_vigentes(p)]]
```

> **Reserva para o V1.1:** o campo `embedding = VectorField(384)` entra com pgvector. O schema já é desenhado para recebê-lo sem migração destrutiva.

### Componentes
`au-command-bar` (overlay com glass) · `au-resultado-grupo` · `au-resultado-item` · `au-atalho-hint` (⌘K, ↵, Esc)

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Primeiro resultado local em ≤ 120 ms |
| A2 | Resultado federado em ≤ 600 ms (p95) com 10 mil documentos |
| A3 | **Teste de vazamento:** duas pessoas de departamentos distintos buscam o mesmo termo e recebem conjuntos diferentes, sem contagem residual |
| A4 | Pessoa removida do público-alvo perde o resultado na próxima reindexação |
| A5 | Falha do índice degrada para a camada local, sem erro de página |
| A6 | Adicionar uma fonte não exige alteração no módulo SRC |

---

## 3.11 WKS — Workspace

### Objetivo
Ser a superfície onde tudo se encontra — e, principalmente, **onde o trabalho se conclui**, não onde ele é apenas listado.

### Escopo V1.0
`WKS-001` a `WKS-005`, `WKS-007` a `WKS-010`, `WKS-012`. **10 itens, 6 widgets, 2 presets.**

### Regras

| # | Regra |
|:-:|---|
| R1 | **Widget que não permite concluir algo é um link disfarçado.** Todo widget da Zona 2 tem ação inline |
| R2 | **Zona 1 é imutável.** É onde a empresa fala |
| R3 | Cada widget carrega **independente**, com cache e TTL próprios. Um widget lento não atrasa a página |
| R4 | Altura reservada antes do dado chegar. **Zero salto de layout** |
| R5 | Widget que falha mostra estado de erro **no próprio widget** e não derruba a home |
| R6 | Widget sem permissão **não é renderizado** — não aparece vazio nem bloqueado |
| R7 | Preset define quais widgets e em que ordem. No V1.0 o usuário não reordena |

### Fluxos

**F1 · Carga da home**
```
GET /workspace/
  └─▶ resolve pessoa, preset e widgets permitidos
      └─▶ renderiza a casca + Zona 1 (síncrona, ≤ 800 ms)
          └─▶ cada widget: <div hx-get="/workspace/widget/<chave>/" hx-trigger="load">
              └─▶ N requisições paralelas, cada uma com seu cache
```

**F2 · Ação inline** — `[Aprovar]` no card → `hx-post` → serviço → fragmento atualizado + `HX-Trigger` para o contador do topo. Sem recarregar a página.

### Dependências
**Recebe de:** todos. **Entrega para:** o usuário. É o consumidor final.

### APIs

| Rota | Método | Retorna |
|---|:-:|---|
| `/workspace/` | GET | HTML — casca + Zona 1 |
| `/workspace/widget/<chave>/` | GET | HTML — partial do widget |
| `/workspace/lancador/` | GET | HTML — apps permitidos (`WKS-010`) |
| `/ws/workspace/` | WS | Eventos — contadores e notificações |

### Permissões
Nenhuma própria. Cada widget declara a permissão que exige; o runtime filtra (R6).

### Banco de dados

```python
class Preset(models.Model):
    chave         = SlugField(unique=True)      # "colaborador", "gestor"
    nome
    papeis        = M2M("identidade.Papel")
    layout        = JSONField()   # {"zona2":["aprovacoes","meu_dia","escala"],
                                  #  "zona3":["mural","acesso_rapido"]}

class WidgetRegistro(models.Model):   # catálogo declarativo, não instâncias
    chave         = SlugField(unique=True)
    nome, descricao
    permissao     = CharField(blank=True)       # vazio = todos
    zona          = PositiveSmallIntegerField() # 1|2|3
    ttl_segundos  = PositiveIntegerField(default=60)
```

> **Não existe tabela de "widget do usuário" no V1.0.** Personalização é V1.1; guardar layout por usuário agora seria estrutura sem consumidor.

### Componentes

| Componente | Uso |
|---|---|
| `au-app-shell` | Topbar + sidebar + área de conteúdo |
| `au-widget` | Contêiner com título, ação, estados de loading/erro/vazio |
| `au-zona-atencao` | Zona 1 |
| `au-widget-grid` | Grade responsiva de 12 colunas |
| `au-launcher` | Grade de aplicações |
| `au-contador-topo` | Badge com atualização por WebSocket |
| `au-skeleton` | Por forma de widget, com altura reservada |

**Os 6 widgets do V1.0:**

| Chave | Zona | Permissão | TTL | Ação inline |
|---|:-:|---|:-:|---|
| `atencao` | 1 | — | 30 s | Confirmar leitura |
| `aprovacoes` | 2 | `apr.aprovar.*` | 30 s | Aprovar, reprovar, devolver, lote |
| `meu_dia` | 2 | — | 60 s | Abrir item |
| `escala` | 2 | `ops.escala.ver.*` | 300 s | Ligar para quem está de plantão |
| `mural` | 3 | — | 120 s | Confirmar leitura |
| `acesso_rapido` | 3 | — | 3600 s | Abrir aplicação |

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Zona 1 em ≤ 800 ms (p95); cada widget em ≤ 1,5 s |
| A2 | Widget que falha mostra erro próprio; os outros 5 continuam funcionando |
| A3 | Zero salto de layout — verificado com CLS = 0 |
| A4 | Widget sem permissão não é renderizado nem aparece na resposta HTML |
| A5 | Aprovar da home não recarrega a página e atualiza o contador do topo |
| A6 | Os 2 presets entregam experiências distintas para usuários reais |
| A7 | Todo módulo existente é alcançável em ≤ 2 cliques a partir da home |

---

## 3.12 AIC — IA & Agentes

### Objetivo no V1.0
**Instrumentar e conter** o copiloto que já roda em produção. Nenhuma IA nova. É o release que torna a IA mensurável e financeiramente previsível.

### Escopo V1.0
`AIC-001` (feedback) e `AIC-002` (teto de custo).

### Regras

| # | Regra |
|:-:|---|
| R1 | **Toda resposta do copiloto registra um evento** — com ou sem reação do usuário |
| R2 | Teto por pessoa, por papel e por instalação. Ao atingir, degrada com mensagem clara — **nunca falha em silêncio** |
| R3 | Custo é registrado por chamada, com tokens de entrada e saída |
| R4 | Alerta em 70% e 90% do teto, para o admin |
| R5 | Nenhum dado novo vai ao LLM no V1.0. O `mask_pii` existente continua sendo a fronteira |

### Fluxos

**F1 · Registro de feedback** — resposta renderizada com `[👍] [👎]` e captura implícita (a ação sugerida foi executada?) → `FeedbackIA` → alimenta a futura `precisao_medida`.

**F2 · Controle de custo**
```
Antes da chamada  → consumo do período < teto?
                    ├─ sim  → prossegue
                    └─ não  → "limite de IA atingido, fale com o administrador"
Depois da chamada → registra tokens e custo, avalia alerta de 70%/90%
```

### Dependências
**Recebe de:** o engine existente ([copilot/engine.py](../dashboard/services/copilot/engine.py)). **Entrega para:** o V1.1 (é fundação).

### APIs

| Rota | Método | Retorna |
|---|:-:|---|
| `/dashboard/copilot/feedback/` | POST | JSON — registra reação |
| `/workspace/admin/ia/consumo/` | GET | HTML — painel de consumo (admin) |

### Permissões
`aic.consumo.ver` → admin.

### Banco de dados

```python
# dashboard/models/copilot.py  (extensão do existente)
class FeedbackIA(models.Model):
    conversa_id   = CharField(db_index=True)
    mensagem_id   = CharField(db_index=True)
    pessoa        = FK("dashboard.PerfilUsuario")
    tipo          = CharField(choices=["positivo","negativo","aceito","rejeitado","editado"])
    contexto      = JSONField(default=dict)   # tools usadas, papel, origem
    criado_em     = DateTimeField(auto_now_add=True, db_index=True)

class ConsumoIA(models.Model):
    pessoa        = FK("dashboard.PerfilUsuario", null=True)
    escopo        = CharField(choices=["pessoa","papel","instalacao"])
    periodo       = DateField(db_index=True)          # granularidade diária
    tokens_entrada, tokens_saida = PositiveIntegerField(default=0)
    custo_estimado = DecimalField(max_digits=10, decimal_places=4, default=0)
    class Meta:
        constraints = [UniqueConstraint(fields=["pessoa","escopo","periodo"], name="uniq_consumo")]

class TetoIA(models.Model):
    escopo        = CharField(choices=["pessoa","papel","instalacao"])
    alvo_id       = CharField(blank=True)
    limite_mensal = DecimalField(max_digits=10, decimal_places=2)
    ativo
```

### Componentes
`au-feedback-inline` (👍/👎 discreto) · `au-consumo-gauge` · `au-limite-alerta`

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Toda resposta do copiloto gera evento, mesmo sem reação do usuário |
| A2 | Teto atingido degrada com mensagem clara, sem exceção não tratada |
| A3 | Custo por chamada registrado com tokens de entrada e saída |
| A4 | Alerta em 70% e 90% chega ao admin |
| A5 | Nenhuma alteração no comportamento funcional do copiloto atual |

---

## 3.13 FIN — Financeiro

### Objetivo no V1.0
Duas coisas pequenas e desproporcionalmente importantes: **reembolso como item de catálogo** (custo marginal ~zero) e **material consumido na OS** (fundação sem tela).

### Escopo V1.0
`FIN-002` e `FIN-003`.

### Regras

| # | Regra |
|:-:|---|
| R1 | Reembolso não tem tela própria — é `ItemCatalogo` + `PoliticaAprovacao` |
| R2 | `ConsumoMaterialOS` registra **o que foi usado na OS**, não o que saiu do estoque. São eventos diferentes |
| R3 | Consumo referencia `MovimentacaoEstoque` quando houver baixa; pode existir sem ela (material do kit do técnico) |
| R4 | Custo unitário é **congelado no momento do consumo** — preço de produto muda, histórico não |

### Fluxos

**F1 · Reembolso** — catálogo → formulário (valor, categoria, data, anexo) → aprovação por valor → aprovado vira `MovimentacaoFinanceira`.

**F2 · Consumo de material** — técnico registra material na OS (app nativo) → `ConsumoMaterialOS` → se veio do estoque, vincula a `MovimentacaoEstoque` → congela custo unitário.

### Dependências
**Recebe de:** SVC, APR, estoque, FSM. **Entrega para:** REV, FIN-004 (V1.1).

### APIs

| Rota | Método | Retorna |
|---|:-:|---|
| `/api/v1/workspace/os/<id>/consumo/` | POST | JSON — **app nativo** registra material |

### Permissões
`fin.consumo.registrar` → técnico, operação.

### Banco de dados

```python
# fsm/models_consumo.py
class ConsumoMaterialOS(models.Model):
    os              = FK("fsm.OrdemServico", related_name="consumos")
    produto         = FK("dashboard.Produto")
    quantidade      = DecimalField(max_digits=10, decimal_places=3)
    custo_unitario  = DecimalField(max_digits=10, decimal_places=2)   # R4 — congelado
    movimentacao    = FK("dashboard.MovimentacaoEstoque", null=True, blank=True)
    registrado_por  = FK(User, null=True)
    registrado_em   = DateTimeField(auto_now_add=True)
    class Meta:
        indexes = [Index(fields=["os"]), Index(fields=["produto","registrado_em"])]

    @property
    def custo_total(self):
        return self.quantidade * self.custo_unitario
```

### Componentes
Nenhum no Workspace. `FIN-003` é fundação; `FIN-002` reusa `au-form-dinamico` do SVC.

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Reembolso funciona ponta a ponta sem uma linha de código específica de reembolso |
| A2 | Consumo registrado congela o custo unitário |
| A3 | Consumo sem movimentação de estoque é válido (material do kit) |
| A4 | Soma de consumos de uma OS é consultável em uma query |

---

## 3.14 REV — Receita & Contrato

### Objetivo no V1.0
Estruturar o que hoje é texto livre: **o que o contrato cobre e quanto custa o que ele não cobre.** Zero interface; puro habilitador da tese comercial.

### Escopo V1.0
`REV-001` e `REV-002`.

### Regras

| # | Regra |
|:-:|---|
| R1 | Escopo é **lista positiva**: o que não está declarado, está fora |
| R2 | Franquia é opcional e por período — "4 visitas/mês inclusas" |
| R3 | Tabela de preço tem vigência. Preço muda; histórico não |
| R4 | Um serviço pode estar em várias tabelas com preços distintos — a do contrato tem precedência sobre a padrão |
| R5 | **Nenhuma detecção automática no V1.0.** O modelo existe para ser populado |

### Fluxos

**F1 · Cadastrar escopo (admin/comercial)** — abre contrato → adiciona serviços cobertos, franquia e exceções → salva. Meta: 80% da carteira em 90 dias (`M8`).

**F2 · Manter tabela de preço** — cadastra serviço, preço e vigência → contrato pode sobrescrever.

### Dependências
**Recebe de:** `dashboard.Contrato`, catálogo de serviços de campo. **Entrega para:** `REV-003/004` (V1.1) e `AIC-010` (V2).

### APIs
Nenhuma no V1.0. Django admin.

### Permissões
`rev.escopo.gerenciar` → comercial, admin.

### Banco de dados

```python
# dashboard/models/receita.py
class TipoServico(models.Model):
    codigo        = SlugField(unique=True)
    nome, descricao
    skill         = FK("fsm.Skill", null=True)      # liga ao que o técnico executa
    ativo

class EscopoContrato(models.Model):
    contrato      = FK("dashboard.Contrato", related_name="escopos")
    tipo_servico  = FK(TipoServico)
    incluso       = BooleanField(default=True)      # R1
    franquia_qtd  = PositiveIntegerField(null=True) # R2
    franquia_periodo = CharField(choices=["mes","trimestre","ano"], blank=True)
    observacao
    class Meta:
        constraints = [UniqueConstraint(fields=["contrato","tipo_servico"], name="uniq_escopo")]

class TabelaPreco(models.Model):
    nome
    contrato      = FK("dashboard.Contrato", null=True, blank=True)   # NULL = tabela padrão
    vigencia_inicio, vigencia_fim = DateField(null=True)
    ativa

class ItemTabelaPreco(models.Model):
    tabela        = FK(TabelaPreco, related_name="itens")
    tipo_servico  = FK(TipoServico)
    preco         = DecimalField(max_digits=10, decimal_places=2)
    class Meta:
        constraints = [UniqueConstraint(fields=["tabela","tipo_servico"], name="uniq_item_preco")]
```

**Resolução de preço** (`dashboard/services/precificacao.py`):
```python
def preco_de(tipo_servico, contrato, data) -> Decimal | None:
    """R4 — tabela do contrato tem precedência sobre a padrão."""
```

### Componentes
Nenhum. Django admin no V1.0.

### Critérios de aceite

| # | Critério |
|:-:|---|
| A1 | Dois contratos reais modelados com o schema, sem campo sobrando nem faltando (**depende de Q-02**) |
| A2 | `preco_de()` resolve a precedência corretamente |
| A3 | Escopo consultável: "este serviço está coberto por este contrato?" em uma query |
| A4 | Alteração de preço não altera histórico |

---

## 3.15 Matriz consolidada de permissões

### Papéis do V1.0

| Chave | Nome | Origem |
|---|---|---|
| `colaborador` | Colaborador | novo — o papel base, que hoje não existe |
| `gestor` | Gestor | evolui `gerente` |
| `rh` | RH | novo |
| `comunicacao` | Comunicação interna | novo |
| `operacao` | Gestor de operação | evolui `sala_monitoramento` |
| `admin` | Administrador | evolui `admin` |

> A migração `LEGACY_ROLE_MAP` mapeia os 6 papéis planos atuais para os novos, preservando o acesso existente.

### Matriz

| Permissão | colaborador | gestor | rh | comunicacao | operacao | admin |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `idn.ler.proprio` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `idn.ler.equipe` | — | ✅ | ✅ | — | ✅ | ✅ |
| `idn.ler.global` | — | — | ✅ | — | — | ✅ |
| `idn.editar.global` | — | — | ✅ | — | — | ✅ |
| `idn.papel.atribuir` | — | — | — | — | — | ✅ |
| `idn.conflito.resolver` | — | — | ✅ | — | — | ✅ |
| `apr.ver.proprio` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `apr.aprovar.equipe` | — | ✅ | ✅ | — | ✅ | ✅ |
| `apr.aprovar.global` | — | — | — | — | — | ✅ |
| `apr.politica.gerenciar` | — | — | — | — | — | ✅ |
| `svc.solicitar.proprio` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `svc.solicitar.equipe` | — | ✅ | ✅ | — | ✅ | ✅ |
| `svc.catalogo.gerenciar` | — | — | — | — | — | ✅ |
| `cnt.ler.publico` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cnt.publicar.departamento` | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cnt.publicar.global` | — | — | — | ✅ | — | ✅ |
| `com.publicar.departamento` | — | ✅ | ✅ | ✅ | — | ✅ |
| `com.publicar.global` | — | — | — | ✅ | — | ✅ |
| `com.relatorio.equipe` | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| `ppl.perfil.editar.proprio` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `ppl.ausencia.ver.equipe` | — | ✅ | ✅ | — | ✅ | ✅ |
| `ppl.certificacao.gerenciar` | — | — | ✅ | — | ✅ | ✅ |
| `ops.escala.ver.unidade` | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `ops.escala.gerenciar.unidade` | — | — | — | — | ✅ | ✅ |
| `fin.consumo.registrar` | — | — | — | — | ✅ | ✅ |
| `rev.escopo.gerenciar` | — | — | — | — | — | ✅ |
| `aic.consumo.ver` | — | — | — | — | — | ✅ |
| `plt.flag.gerenciar` | — | — | — | — | — | ✅ |

---

## 3.16 Modelo de dados consolidado

```
                        ┌──────────────────────────────┐
                        │  PerfilUsuario  (= Pessoa)   │  dashboard, evoluído
                        │  matricula · situacao        │
                        │  origem_campos {}            │
                        └──┬────┬────┬────┬────┬───────┘
         ┌─────────────────┘    │    │    │    └──────────────┐
         ▼                      ▼    ▼    ▼                   ▼
    ┌─────────┐        ┌──────────┐ │ ┌────────────┐   ┌────────────┐
    │ Unidade │◀───────│Departa-  │ │ │AtribuicaoP.│   │ Delegacao  │
    └─────────┘        │mento     │ │ │ escopo+vig.│   └────────────┘
         ▲             └────┬─────┘ │ └─────┬──────┘
         │                  │       │       ▼
         │                  ▼       │  ┌────────┐
         │           ┌────────────┐ │  │ Papel  │──▶ permissoes []
         │           │CentroCusto │ │  └────────┘
         │           └────────────┘ │
         │                          ├──▶ Certificacao ──▶ TipoCertificacao ──▶ fsm.Skill
         │                          ├──▶ Ausencia
         │                          └──▶ fsm.Tecnico (OneToOne via User)
         │
    ┌────┴──────┐         ┌──────────────────┐        ┌────────────────────┐
    │  Escala   │────────▶│   TurnoEscala    │        │ SolicitacaoAprov.  │
    └───────────┘         └──────────────────┘        │  GenericFK → alvo  │
                                                       └────────┬───────────┘
                                                                ▼
                                                       ┌────────────────────┐
                                                       │  EtapaAprovacao    │
                                                       └────────────────────┘
                                                                ▲
    ┌────────────────┐      ┌──────────────┐                    │
    │ ItemCatalogo   │─────▶│ Solicitacao  │────────────────────┘
    │  dono · form   │      │  → Ticket    │
    └────────────────┘      └──────────────┘

    ┌────────────────┐      ┌────────────────────┐
    │   Documento    │─────▶│  PendenciaLeitura  │
    │  acl_subjects()│      └────────────────────┘
    └───┬────────────┘
        │  1:1
        ▼
    ┌────────────┐
    │ Comunicado │  classe: informativo|obrigatorio|critico
    └────────────┘

    ┌──────────────────┐  ◀── providers (pessoa, documento, ticket, os…)
    │  SearchDocument  │      acl_subjects[] + tsv   (+ embedding no V1.1)
    └──────────────────┘

    fsm.OrdemServico ──▶ ConsumoMaterialOS ──▶ dashboard.Produto
    dashboard.Contrato ──▶ EscopoContrato ──▶ TipoServico ◀── ItemTabelaPreco ◀── TabelaPreco
```

**Contagem:** 21 modelos novos · 2 modelos evoluídos (`PerfilUsuario`, `UserRole`) · 0 modelos existentes quebrados.

---

## 3.17 Ordem de construção

Derivada do grafo de dependências, respeitando as duas frentes paralelas identificadas na Etapa 1.

| Bloco | Módulos | Frente | Entrega verificável |
|:-:|---|---|---|
| **B1** | IDN (completo) + PLT-010 | Identidade | `pode()` resolve os 5 escopos; base real importada |
| **B2** | PLT-001/002/003 + WKS-001 | Casca | AppShell renderizando com tokens Aurora |
| **B3** | APR (completo) | Identidade | Aprovação ponta a ponta via admin |
| **B4** | CNT + COM | Identidade | Comunicado crítico bloqueando |
| **B5** | SVC + FIN-002 | Identidade | 6 itens gerando ticket |
| **B6** | WKS-002/003/004 + 6 widgets | Casca | Home completa com os 2 presets |
| **B7** | SRC (completo) | Casca | ⌘K com pessoas e teste de vazamento |
| **B8** | PPL + OPS | Identidade | Bloqueio por certificação funcionando |
| **B0** | REV, FIN-003, AIC-001/002, PLT-004/005/006/007 | **Independente** | Podem começar a qualquer momento |

> **B0 é a válvula de escape do cronograma.** São itens sem dependência, que destravam o maior valor futuro. Se uma frente travar, ela migra para B0 em vez de ficar ociosa.

---

## Próxima etapa

**Etapa 4 — PRD por módulo.** Objetivo, problema, usuários, personas, casos de uso, fluxos, regras de negócio, permissões, estados, validações, integrações, critérios de aceite, métricas, KPIs, riscos, backlog e roadmap — para cada um dos 13 módulos.

> **Nota de método:** a Etapa 3 fixou o **contrato estrutural** (dados, API, permissões, componentes). A Etapa 4 não vai repeti-lo — vai cobrir a camada de produto (persona, caso de uso, estado, métrica, risco) e referenciar esta.

**Aguarda aprovação da Etapa 3.**

---

*Etapa 3 de 9 · Contratos estruturais fixados. Alteração de schema ou de API se decide aqui primeiro.*
