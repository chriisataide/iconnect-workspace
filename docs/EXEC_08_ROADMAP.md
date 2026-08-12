# Execução · Etapa 8 — Roadmap

> **Documento de sequenciamento.** V1.0, V1.1, V2.0 e V3.0 — o que entra em cada versão, **por que** entra ali e não antes, os portões entre versões e como o plano se adapta quando algo dá errado.
>
> **Agosto/2026** · Etapa 8 de 9 · **Aguarda aprovação antes da Etapa 9**
>
> ⚠️ **Revisado em 12/08/2026 pela [Etapa 10 — Reposicionamento](EXEC_10_REPOSICIONAMENTO.md).** O produto se chama **iConnect Workspace**, e Workspace e Platform são dois produtos — não uma camada sobre o outro. Onde este documento contradiz a Etapa 10, a Etapa 10 vence; §10.7 nomeia cada contradição. Nada aqui foi descartado.

---

## Sumário

- [8.0 O que faz uma versão ser uma versão](#80-o-que-faz-uma-versão-ser-uma-versão)
- [8.1 Taxonomia de posicionamento](#81-taxonomia-de-posicionamento)
- [8.2 V1.0 — "Meu dia começa aqui"](#82-v10--meu-dia-começa-aqui)
- [8.3 V1.1 — "O sistema começa a me dizer coisas"](#83-v11--o-sistema-começa-a-me-dizer-coisas)
- [8.4 V2.0 — "O sistema age comigo"](#84-v20--o-sistema-age-comigo)
- [8.5 V3.0 — "O sistema é uma plataforma"](#85-v30--o-sistema-é-uma-plataforma)
- [8.6 Linha do tempo](#86-linha-do-tempo)
- [8.7 Os portões entre versões](#87-os-portões-entre-versões)
- [8.8 Decisões contenciosas — por que não antes](#88-decisões-contenciosas--por-que-não-antes)
- [8.9 O que não está em nenhuma versão](#89-o-que-não-está-em-nenhuma-versão)
- [8.10 Como o roadmap se adapta quando dá errado](#810-como-o-roadmap-se-adapta-quando-dá-errado)
- [8.11 Compromissos de arquitetura entre versões](#811-compromissos-de-arquitetura-entre-versões)

---

## 8.0 O que faz uma versão ser uma versão

Roadmap de produto costuma ser uma lista de features distribuída por trimestres, e por isso não resiste ao primeiro imprevisto — quando algo atrasa, ninguém sabe o que puxar nem o que empurrar.

**Aqui, cada versão é uma tese verificável.**

| Versão | Tese | Como se prova |
|:-:|---|---|
| **V1.0** | *"Meu dia começa aqui."* | DAU/MAU ≥ 0,5 e 50% das tarefas concluídas sem sair da home |
| **V1.1** | *"O sistema começa a me dizer coisas."* | A IA responde com fonte e a receita não faturada aparece em R$ |
| **V2.0** | *"O sistema age comigo."* | Agentes executam com autonomia conquistada e medida |
| **V3.0** | *"O sistema é uma plataforma."* | Terceiros estendem sem tocar no núcleo |

**Consequência prática:** uma funcionalidade pertence a uma versão quando **serve à tese daquela versão** e **suas condições de existência estão satisfeitas**. Não porque "sobrou espaço no trimestre".

### Política de numeração

| Mudança | Versão |
|---|---|
| Nova tese de produto | Maior (1.0 → 2.0) |
| Novas capacidades dentro da mesma tese | Menor (1.0 → 1.1) |
| Correção e ajuste sem nova capacidade | Patch (1.0.1) |
| Quebra de contrato de API pública | Maior, sempre |

---

## 8.1 Taxonomia de posicionamento

Todo item adiado carrega um **código de motivo**. Sem isso, "fica para depois" vira arbitrariedade — e a primeira pessoa que reclamar mais alto consegue antecipar o item dela.

| Código | Motivo | Quando se resolve |
|:-:|---|---|
| **D** | **Dependência técnica** — precisa de algo ainda não construído | Quando a dependência entrega |
| **M** | **Maturação de dado** — precisa de dado acumulado que ainda não existe | Quando o gate de dado é atingido |
| **V** | **Validação** — precisa de prova medida antes de investir | Quando a métrica responde |
| **R** | **Risco** — jurídico, LGPD ou financeiro exige mitigação prévia | Quando a mitigação existe |
| **C** | **Capacidade** — cabe no produto, não cabe no orçamento da versão | Quando há capacidade |
| **A** | **Adoção** — depende de hábito estabelecido para fazer sentido | Quando o hábito existe |
| **∅** | **Fora do produto** — decisão, não adiamento | Nunca |

> **A diferença entre `C` e os demais importa.** `C` é a única razão negociável — se aparecer capacidade, o item sobe. `D`, `M`, `V`, `R` e `A` não se resolvem com mais gente.

---

## 8.2 V1.0 — "Meu dia começa aqui"

### O que a versão entrega

**58 itens · 107 stories · 404 pontos** ([Etapa 7](EXEC_07_BACKLOG.md)).

```
LAÇO DIÁRIO                      FUNDAÇÃO SEM TELA (o investimento invisível)
├─ Ver o que precisa de mim      ├─ Identidade e organograma
├─ Aprovar sem sair da home      ├─ Escopo contratual e tabela de preço
├─ Pedir com 1 campo             ├─ Consumo de material na OS
├─ Confirmar leitura             ├─ Certificação com validade
├─ Saber quem está de plantão    ├─ Feedback e teto de IA
└─ Achar pessoa e navegar (⌘K)   └─ Índice de busca com ACL
```

### Por que exatamente isto, e não mais

| Bloco | Razão de estar no V1.0 |
|---|---|
| **Aprovações** | Sem ela, a gestão não tem motivo para abrir. É a âncora nº 1 de retorno diário |
| **Comunicado obrigatório** | Âncora nº 3 e o único KPI que vale dinheiro em auditoria desde o dia 1 |
| **Escala** | Âncora nº 2. Substitui a planilha e o grupo de WhatsApp — a dor mais universal do vertical |
| **Catálogo de 6** | Sem origem de pedido, o motor de aprovação não tem o que aprovar |
| **⌘K** | É a navegação real. Sem ele, o Workspace é um menu com widgets |
| **Bloqueio por certificação** | É o diferencial defensável, e é barato porque o dispatch já existe |
| **Fundação sem tela** | **Dado tem prazo de maturação.** Entra agora para o V1.1 valer no dia do lançamento |

### Por que não mais que isto

Cada item fora do V1.0 tem código de motivo em §8.3 e §8.4. Nenhum ficou fora por acaso.

### Critério de saída

Os 5 eixos da [Etapa 2 §2.7](EXEC_02_MVP.md) — funcional, qualidade, desempenho, segurança e operação. Todos verdes, sem exceção negociada em reunião.

---

## 8.3 V1.1 — "O sistema começa a me dizer coisas"

### A tese

O V1.0 é um bom lugar para trabalhar. O V1.1 é onde o sistema passa a **produzir informação que ninguém pediu** — e é onde a tese comercial aparece em reais.

### Conteúdo, com o motivo de cada item

#### Inteligência — a IA liga

| Item | Motivo de não estar no V1.0 | Condição para entrar |
|---|:-:|---|
| Busca semântica (pgvector) e fusão RRF | **M** | ≥40 documentos publicados |
| Resposta de IA ancorada no ⌘K | **M** | idem — assistente sobre biblioteca vazia se autodestrói |
| Briefing diário gerado por IA | **D** + **M** | Depende de conteúdo e do teto de custo do V1.0 |
| `ContratoAgente` (objetivo, gatilho, orçamento) | **D** | Depende de `FeedbackIA` e `TetoIA`, entregues no V1.0 |
| UI de proposta como diff | **D** | Depende do contrato de agente |
| Skill packs e roteador de intenção | **M** | Depende de conteúdo por domínio |
| Agente de Conhecimento (OS → rascunho de POP) | **D** | Depende do modelo de conteúdo e do contrato de agente |
| Camada Ambiente (enriquecimento sem interface) | **C** | Cabe, não coube |

> **A IA generativa não liga no V1.0 por uma razão só, e ela é decisiva:** *"Como solicito férias?"* só tem resposta se existir um documento dizendo como. Um assistente lançado sobre biblioteca vazia produz a impressão **"a IA daqui não sabe nada"** — e essa impressão é praticamente irreversível.

#### Receita — a tese comercial aparece

| Item | Motivo | Condição |
|---|:-:|---|
| Classificação do serviço executado na OS | **D** | Depende de `EscopoContrato` (V1.0) e `ConsumoMaterialOS` (V1.0) |
| **Bandeja de receita não faturada** | **M** | ≥80% dos contratos com escopo tipificado |
| Ações Faturar / Cortesia com trilha | **D** | Depende da bandeja |
| Custo real da OS | **M** | ≥70% das OS com consumo registrado |
| Orçamento por centro de custo | **D** | Depende do custo real |
| Contexto orçamentário na aprovação | **D** | Depende do orçamento |

> **É aqui que o investimento invisível do V1.0 se paga.** `EscopoContrato`, `TabelaPreco` e `ConsumoMaterialOS` entraram no V1.0 sem tela alguma justamente para que a bandeja funcione **no dia do lançamento do V1.1**, e não seis meses depois.

#### Conteúdo e conveniências

| Item | Motivo | Nota |
|---|:-:|---|
| Versionamento de documento com diff | **M** | Sem histórico, não há o que versionar no dia 1 |
| Fluxo de revisão e aprovação de conteúdo | **C** + **V** | V1.0 publica quem tem o papel; formalizar antes de haver volume é burocracia |
| Migração do `ArtigoConhecimento` | **C** | O KB atual funciona; migrar cedo é risco sem retorno |
| Timeline de acompanhamento (SVC) | **C** | O status aparece em "Meu dia" com link para a tela existente |
| Prazo real medido (P50/P90) | **M** | Precisa do histórico do V1.0 |
| Deflexão por autoatendimento | **M** | Precisa de conteúdo publicado |
| **Documentos pessoais com validade** | **R** | **ASO é dado de saúde, LGPD art. 11.** Exige política de retenção (`A-03`) |
| Editor de escala no Workspace | **V** | O admin atende o piloto; validar que a escala é usada antes de investir na tela |
| Central de notificações | **C** | Notificação acionável já vive dentro dos widgets |
| Preferências (tema, densidade, ordem) | **V** | Medir se alguém quer reordenar antes de construir |
| Diretório e perfil público | **C** | `PPL-001` cobre o próprio perfil |
| Agendamento e correção de comunicado | **A** | A necessidade aparece com volume de publicação |
| Mais fontes na busca | **V** | `K-SRC-04` (buscas sem resultado) diz quais adicionar primeiro |
| `contextvars` no lugar de `threading.local()` | **R↓** | [D-01] rebaixou o risco: com instalação dedicada, não há consequência entre clientes |

**Estimativa: ~34 features ≈ 200 pontos ≈ 11 semanas com 2 pessoas.**

---

## 8.4 V2.0 — "O sistema age comigo"

### A tese

O V1.1 informa. O V2 **age** — com autonomia que foi conquistada por desempenho medido, não configurada numa caixa de seleção.

### Conteúdo

#### Agentes com autonomia conquistada

| Item | Motivo | Condição |
|---|:-:|---|
| **Autonomia por desempenho medido (níveis 0–3)** | **M** | Precisa de histórico de `FeedbackIA` acumulado desde o V1.0 |
| Agente de Receita Não Faturada (detecção por IA) | **V** | Precisa de volume classificado **por regra** no V1.1 para validar contra |
| Agente de Risco de SLA com reroteirização | **D** | Depende do contrato de agente e da UI de diff |
| Agente de Qualidade de Evidência (antifraude) | **R** + **A** | Precisa de comunicação prévia ao time de campo |
| Agente de Margem por Contrato | **D** | Depende do custo real da OS |
| Agente de Peça Certa | **M** | Precisa de série histórica de consumo |
| Cache semântico de respostas | **C** | Otimização sobre base funcionando |
| "Explique este KPI" | **D** | Depende de KPIs consolidados |

> **`AIC-004` (autonomia conquistada) é a proposta mais defensável do produto** ([Revisão CPO §D.3](CPO_REVIEW_ICONNECT.md)) — e é estruturalmente impossível antes do V2. Um agente sobe de nível com ≥90% de aceitação em 200 propostas. Sem 200 propostas registradas, o número não existe. **É por isso que `FeedbackIA` entra no V1.0 sem nenhuma interface.**

#### Produto e operação

| Item | Motivo | Nota |
|---|:-:|---|
| Documento executável (POP = checklist = formulário) | **D** | Depende de versionamento (V1.1) e do checklist do FSM |
| Comentário ancorado no objeto | **C** | Alto valor, custo médio |
| Mudança operacional revisada (diff + blame de configuração) | **C** | Auditoria ISO como subproduto |
| Ciclo operacional com fechamento automático | **D** | Depende de escopo, custo e margem |
| Sala de guerra de incidente | **C** | Alto valor por evento, poucos eventos |
| Offboarding com revogação em cadeia | **C** | Uso raro, valor altíssimo |
| Onboarding com trilha e SLA | **C** | — |
| Catálogo expandido para 30 itens | **V** | Guiado por `K-SVC-01` medido, nunca por pedido de área |
| Aprovação por canal externo (WhatsApp) | **R** | Depende de parecer jurídico sobre não-repúdio ([D-04]) |
| Áudio de comunicado (TTS) | **A** | Depende de adoção do app nativo pelo campo |
| Pulso semanal | **A** | Depende de confiança estabelecida — pesquisa em ambiente de desconfiança mede desconfiança |
| Painéis de BI por papel | **D** | Depende da camada semântica de métricas |
| Fechar o dia · Modo foco · Handoff | **A** | Dependem de hábito diário estabelecido |
| Reembolso por foto com OCR | **C** | Risco de execução em cupom fiscal brasileiro |

**Estimativa: ~22 features ≈ 180 pontos ≈ 10 semanas com 2 pessoas.**

---

## 8.5 V3.0 — "O sistema é uma plataforma"

### A tese

Até o V2, quem constrói é o time. No V3, **terceiros estendem sem tocar no núcleo** — e o produto passa a crescer mais rápido do que a equipe.

### Conteúdo — direcional, não estimado

| Item | Motivo | Pré-condição real |
|---|:-:|---|
| **Tenancy real multi-cliente** | **R** + **C** | Reavaliar [D-01] em 2027. 123 models, migrações, testes de isolamento |
| API pública de widget e SDK | **A** | Só faz sentido com clientes querendo estender |
| Marketplace de conectores | **A** | Marketplace sem massa crítica é prateleira vazia |
| Workspace Studio (no-code) | **A** | Ferramenta de plataforma antes de haver plataforma |
| Grafo operacional e análise de impacto | **D** | Depende de todas as fontes indexadas |
| Agentes proativos | **M** | Depende de precisão medida e confiança estabelecida |
| Multi-idioma | **∅→C** | Sem cliente fora do Brasil. Quando houver, ~3 semanas |
| PDI, feedback, avaliação | **C** | Depende de competências consolidadas |
| Precificação sugerida por margem | **M** | Depende de série histórica de margem |

> **Estimar o V3 hoje seria ficção.** Ele depende de decisões comerciais que ainda não foram tomadas e de aprendizado que ainda não aconteceu. O que está registrado é a **direção**, para que as decisões de arquitetura do V1.0 e do V1.1 não fechem essas portas.

---

## 8.6 Linha do tempo

Com **2 pessoas**, a premissa da [Etapa 7](EXEC_07_BACKLOG.md).

```
Mês   1     2     3     4     5     6     7     8     9    10    11    12
      │     │     │     │     │     │     │     │     │     │     │     │
V1.0  ██████████████████████████████████████████▓
      Ondas 0-1   Ondas 2-3     Ondas 4-5    Onda 6  ▓ = piloto (4 sem)
                                                     │
                                              LANÇAMENTO V1.0
                                                     │
      ┌── janela de maturação (90 dias) ──────────────┼─────────────┐
      │  cadastro de escopo contratual · publicação de conteúdo ·   │
      │  registro de consumo · cadastro de certificação             │
      └─────────────────────────────────────────────────────────────┘
                                                     │
V1.1                                                 ████████████████████
                                                     └─ parte não-travada
                                                        começa junto
                                                                        │
                                                              LANÇAMENTO V1.1
V2.0                                                                    ████...
```

| Marco | Quando | Condição |
|---|:-:|---|
| Fim da Onda 1 | ~mês 2 | **Primeira recalibração de velocidade** |
| Código completo do V1.0 | ~mês 5 | Critérios de qualidade verdes |
| Piloto | mês 5–6 | Grupo controlado por feature flag |
| **Lançamento V1.0** | **~mês 6** | 5 eixos de critério de saída |
| Portões do V1.1 | ~mês 9 | 4 gates de dado atingidos |
| **Lançamento V1.1** | **~mês 9–10** | — |
| **Lançamento V2.0** | **~mês 12–13** | — |

### A janela de maturação não é ociosidade

Entre o V1.0 e os portões do V1.1 existem ~90 dias de acumulação de dado. **O time não fica esperando:** constrói nesse período tudo do V1.1 que **não** depende de gate — versionamento de conteúdo, editor de escala, timeline, preferências, `contextvars`, central de notificações.

O que fica travado é apenas o que depende de dado: IA generativa, bandeja de receita, custo real, prazo medido.

> **Este é o argumento mais forte para manter a fundação sem tela no V1.0.** Se `EscopoContrato` só entrasse no V1.1, os 90 dias de maturação começariam depois — e a bandeja de receita escorregaria para o mês 13, junto com o V2.

---

## 8.7 Os portões entre versões

Um portão não é uma data. É uma **condição verificável** que autoriza a construção.

### V1.0 → V1.1

| Portão | Limiar | Autoriza | O que acontece se não for atingido |
|---|:-:|---|---|
| `K-CNT-01` documentos publicados | **≥ 40** | IA generativa (`SRC-006`, `AIC-014`) | **A IA não liga.** Mobiliza-se conteúdo antes |
| `K-REV-01` contratos tipificados | **≥ 80%** | Bandeja de receita não faturada | Bandeja adiada; comercial assume o cadastro |
| `K-FIN-01` OS com consumo registrado | **≥ 70%** | Custo real da OS | Investiga-se a fricção no app de campo |
| `K-PPL-01` técnicos com certificação | **100%** | Confiar no bloqueio como regra operacional | Bloqueio permanece em modo alerta |
| `M1` DAU/MAU | **≥ 0,5** | **Continuar investindo no produto** | Ver §8.10 — não é hora de construir mais |

### V1.1 → V2.0

| Portão | Limiar | Autoriza |
|---|:-:|---|
| Propostas de IA com feedback registrado | **≥ 200 por agente** | Autonomia nível 2 |
| Taxa de aceitação | **≥ 90%** | Promoção de nível |
| Receita não faturada identificada | **> 0 e verificável** | Investir no agente de detecção por IA |
| `K-APR-02` aprovações resolvidas na home | **≥ 70%** | Aprovação por canal externo |

### A regra do portão

> **Portão não atingido não vira exceção.** Ele vira **investigação**: por que o dado não apareceu? Quase sempre a resposta não é "falta de tempo", é um problema de produto que construir mais features pioraria.

---

## 8.8 Decisões contenciosas — por que não antes

Os itens que serão questionados, com a resposta pronta.

| Item | Versão | Resposta em uma frase |
|---|:-:|---|
| **IA no ⌘K** | V1.1 | *"Ela responde o que estiver na biblioteca. Com a biblioteca vazia, o usuário conclui que a IA não sabe nada — e essa impressão não se reverte."* |
| **Receita não faturada** | V1.1 | *"O modelo de dados entra agora, sem tela. A bandeja funciona no dia do lançamento do V1.1 porque os contratos já estarão cadastrados."* |
| **Autonomia de IA** | V2.0 | *"Um agente sobe de nível com 200 propostas medidas. Sem 200 propostas, o número não existe — por isso o registro de feedback entra no V1.0."* |
| **Editor de escala** | V1.1 | *"O valor está em saber quem está de plantão, e isso o widget entrega. Editar bem custa uma tela complexa; primeiro validamos que a escala no sistema é usada."* |
| **Documentos pessoais (ASO)** | V1.1 | *"É dado de saúde sob o art. 11 da LGPD. Entra depois da política de retenção, não antes."* |
| **Versionamento de documento** | V1.1 | *"No dia 1 não há histórico para versionar."* |
| **Personalização de widget** | V1.1 | *"Os presets entregam 95% do valor percebido. Reordenar entra se a medição mostrar demanda."* |
| **Timeline de solicitação** | V1.1 | *"O status aparece em 'Meu dia' com link para a tela de ticket que já existe."* |
| **Aprovação por WhatsApp** | V2.0 | *"Não-repúdio em canal externo é problema jurídico, não técnico. Depende de parecer."* |
| **Catálogo com 30 itens** | V2.0 | *"30 itens exigem 30 donos e 30 SLAs. Começamos com 6 e crescemos por uso medido."* |
| **Documento executável** | V2.0 | *"Depende de versionamento e da integração com o checklist do FSM."* |
| **Offboarding** | V2.0 | *"Valor altíssimo, uso raro. Não compete com a âncora diária."* |
| **BI por papel** | V2.0 | *"Sem camada semântica, cada tela dá um número diferente — e painel que se contradiz destrói confiança."* |
| **Pulso de clima** | V2.0 | *"Pesquisa em ambiente de desconfiança mede desconfiança. Precisa de hábito e confiança primeiro."* |
| **Tenancy real** | 2027 | *"Decisão [D-01]. Instalação dedicada agora; reavaliar quando houver demanda de SaaS."* |
| **Feed social / LMS / HRIS** | ∅ | *"Não é adiamento, é decisão de produto."* |

---

## 8.9 O que não está em nenhuma versão

Restado aqui para não ser reaberto sem fato novo — e porque a pergunta volta a cada seis meses.

| Item | Motivo |
|---|---|
| Feed social, curtidas, comentários públicos | Morre em 90 dias no porte-alvo. O WhatsApp já venceu essa disputa |
| Gamificação, ranking, badges de aprendizagem | Ranking público constrange quem mais precisa de treinamento |
| LMS completo (autoria, SCORM, vídeo, prova) | Categoria com incumbentes maduros. Integramos |
| HRIS (folha, ponto, banco de horas, eSocial) | Risco regulatório alto, diferenciação zero. Exibimos, não calculamos |
| Vagas, indique um amigo, plano de carreira | Baixo uso, alto custo, fora da tese |
| Métricas individuais de produtividade | **Princípio.** Vigilância e passivo trabalhista. Só nível de equipe |
| Dashboards gerados por IA | Produz gráfico errado com confiança |
| Resumo de reunião | M365 e Google fazem melhor e de graça. Integramos o resultado |
| Substituir e-mail, arquivo, chat, videoconferência | Não é a briga a travar |
| Reescrever os módulos operacionais existentes | Migração por atração, guiada por `K-WKS-05` |

---

## 8.10 Como o roadmap se adapta quando dá errado

Cenários prováveis, com a resposta decidida **antes** da pressão.

### C1 · O gate de conteúdo não é atingido (< 40 documentos)

**Não ligar a IA.** A tentação será ligar mesmo assim, "só para mostrar".

| Ação | |
|---|---|
| Investigar | Ninguém publica porque falta dono? Porque a ferramenta atrapalha? Porque não há cultura? |
| Antecipar | O **Agente de Conhecimento** (OS → rascunho de POP) sobe na fila do V1.1 — ele resolve a causa em vez do sintoma |
| Substituir | Entregar as conveniências não-travadas do V1.1 |

### C2 · O escopo contratual não é cadastrado (< 80%)

| Ação | |
|---|---|
| Reduzir o alvo | Cadastrar apenas os **20 contratos de maior faturamento** e rodar a bandeja neles |
| Provar o valor | Um número em R$ num contrato real converte mais que qualquer apresentação |
| Não fazer | Adiar tudo por causa da cauda longa |

### C3 · DAU/MAU abaixo de 0,4 no segundo mês

**É o cenário mais grave, e o mais mal respondido em geral.**

> A reação instintiva é construir mais features. Quase sempre é a resposta errada: o portal não está sendo aberto porque **não há razão para abrir**, e mais features não criam razão.

| Ação | |
|---|---|
| Verificar as 3 âncoras | Aprovação vive só no Workspace? A escala é publicada lá? Há comunicado obrigatório circulando? |
| Se alguma âncora vazou | Fechar o canal alternativo — aprovar por WhatsApp precisa deixar de existir |
| Se as três estão firmes e ninguém abre | O problema é a promessa, não a execução. **Parar e reavaliar antes do V1.1** |

### C4 · O time de campo rejeita o bloqueio por certificação

| Ação | |
|---|---|
| Não remover | Passar `PPL-005` para **modo alerta** — sinaliza sem impedir |
| Corrigir a causa | Quase sempre é cadastro incompleto (`K-PPL-01` < 100%), não a regra |
| Reativar | Com comunicação prévia e o alerta de 90 dias funcionando |

### C5 · Só há uma pessoa disponível

Roadmap alternativo, com V1.0 em **~10 meses**:

| Prioridade | O que fazer |
|:-:|---|
| 1 | Manter os 20 itens 🔒 — cortá-los adia o V1.1 inteiro |
| 2 | Cortar na ordem de [§7.13](EXEC_07_BACKLOG.md) |
| 3 | **Reduzir o piloto a 15 pessoas de uma área** — menos superfície de suporte |
| 4 | Aceitar 10 meses **ou** cortar uma âncora — e, se for cortar, cortar a busca, não a escala |

> **Por que a busca antes da escala:** o ⌘K é o que mais impressiona em demonstração, mas a escala é o que substitui a planilha. Impressão se recupera; a substituição de um processo, uma vez perdida, custa muito mais para reconquistar.

### C6 · A Onda 1 mostra velocidade muito abaixo de 9 pts/semana

| Ação | |
|---|---|
| Recalibrar | Refazer a linha do tempo com o número real, **imediatamente** |
| Comunicar | Antes de a diferença acumular, não depois |
| Não fazer | Manter a data e apertar a qualidade — é o caminho para o V1.0 que não pode ser lançado |

---

## 8.11 Compromissos de arquitetura entre versões

Decisões tomadas no V1.0 **porque** versões futuras dependem delas. Quebrar qualquer uma custa uma migração destrutiva depois.

| Compromisso | Assumido em | Necessário para | Se for quebrado |
|---|:-:|---|---|
| `SearchDocument` com coluna `embedding` prevista | V1.0 | Busca semântica (V1.1) | Migração de tabela grande em produção |
| `acl_subjects()` como **função única** para biblioteca e índice | V1.0 | Toda expansão de busca | Dois filtros divergem → vazamento |
| `FeedbackIA` com sinal explícito **e** implícito | V1.0 | `precisao_medida` (V2) | Autonomia medida nunca existe |
| `ConsumoMaterialOS` como evento **imutável** | V1.0 | Custo real e margem | Histórico de custo não reconstrói |
| `EscopoContrato` como **lista positiva** | V1.0 | Detecção de fora-de-escopo | Ambiguidade sobre o que é exceção |
| `WorkspaceProvider` **somente leitura** | V1.0 | Toda extensão de domínio | Acoplamento reverso, refatoração impossível |
| Cadeia de aprovação **congelada** na criação | V1.0 | Auditoria e não-repúdio | Histórico muda retroativamente |
| Toda migração do V1.0 **reversível** | V1.0 | Rollback por feature flag | Rollback exige restauração de backup |
| Tokens Aurora como **fonte única** de cor | V1.0 | Tema manual (V1.1), densidade | Refatoração de CSS em todas as telas |
| `Documento` com vigência e público desde o início | V1.0 | Versionamento (V1.1), doc executável (V2) | Migração de dado com semântica ambígua |

> **Estes dez compromissos são o verdadeiro produto da Etapa 5.** Eles custam quase nada agora e valem meses depois — e é exatamente por isso que são os primeiros a serem questionados por quem chega no meio do projeto.

---

## Próxima etapa

**Etapa 9 — Visão de CTO.** Validação de que todo o plano é implementável no stack declarado (Django, Templates, HTMX, Alpine, Tailwind, PostgreSQL, Redis, Celery, WebSockets), com foco em simplicidade, reuso, escalabilidade e baixo custo de manutenção.

**Aguarda aprovação da Etapa 8.**

---

*Etapa 8 de 9 · 4 versões · 7 códigos de motivo · 9 portões · 6 cenários de adaptação · 10 compromissos de arquitetura.*
