# Execução · Etapa 13 — Operação

> **Runbook.** Como subir, configurar, agendar e diagnosticar o iConnect Workspace.
>
> Para entender **o produto**, leia o [EXEC_12_GUIA_DO_TIME](EXEC_12_GUIA_DO_TIME.md).
>
> **19 de agosto de 2026**

---

## Sumário

- [13.1 Subir do zero](#131-subir-do-zero)
- [13.2 Variáveis de ambiente](#132-variáveis-de-ambiente)
- [13.3 Os comandos agendados](#133-os-comandos-agendados)
- [13.4 Os comandos sob demanda](#134-os-comandos-sob-demanda)
- [13.5 Ligar a integração com o iConnect](#135-ligar-a-integração-com-o-iconnect)
- [13.6 Monitoramento](#136-monitoramento)
- [13.7 Diagnóstico](#137-diagnóstico)
- [13.8 Antes de cada deploy](#138-antes-de-cada-deploy)

---

## 13.1 Subir do zero

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser

# 1 · IDENTIDADE primeiro. A ordem importa: o resto pendura no organograma.
python manage.py semear_papeis            --aplicar   # os papéis e suas permissões
python manage.py importar_organograma docs/exemplos/organograma-inicial.csv --aplicar
python manage.py semear_acessos           --aplicar   # dá papel a quem está no organograma
python manage.py semear_centros_custo     --aplicar   # um CentroCusto por código usado na lotação

# 2 · WORKSPACE. O saldo de estoque é POR UNIDADE — sem unidade, não tem onde morar.
python manage.py semear_regras_aprovacao  --aplicar   # a cadeia por faixa de valor
python manage.py semear_catalogo          --aplicar   # os itens de serviço
python manage.py semear_recursos          --aplicar   # salas, veículos, equipamentos
python manage.py semear_estoque           --aplicar   # materiais e saldo inicial
python manage.py semear_frota             --aplicar   # veículos, ligados aos recursos
python manage.py semear_cursos            --aplicar   # NRs e treinamentos
python manage.py semear_faq               --aplicar   # a base do assistente

# 3 · INGESTÃO. Sem `semear_fontes`, o carregador RECUSA começar — de propósito:
#     carga sem registro de fonte é dado sem procedência.
python manage.py semear_fontes            --aplicar   # as 4 fontes e a precedência
python manage.py semear_resultados        --aplicar   # a massa do espelho, por 3 fontes
python manage.py semear_regras_excecao    --aplicar   # as 18 regras + as 5 desligadas
python manage.py semear_ciclos            --aplicar   # a pauta mensal (12 etapas) e o recorte trimestral

python manage.py reindexar_busca                      # o índice

python manage.py runserver
```

Todo seeder é **idempotente** e roda em simulação sem `--aplicar`. Sem a flag, ele mostra o que faria e desfaz a transação.

### Para testar sem decorar quem é quem

```bash
python manage.py semear_perfis --aplicar
```

Cria **um usuário por papel**, com o nome do papel: quem entra como `compras@icodev.com.br` atende Compras; `financeiro@` vê a fila do Financeiro; `colaborador@` não vê fila nenhuma — e é esse o teste.

Convive com o organograma de propósito: o organograma prova que o produto funciona com gente de verdade; estes perfis provam **o que** cada papel alcança.

### Ao atualizar uma instalação que já existia

`semear_regras_aprovacao --aplicar` **desativa** o degrau de revisão de área (ordem 15), retirado da cadeia em 20/08/2026. Ele não é apagado: `EtapaAprovacao` de todo pedido que passou por ele aponta para aquela linha, e apagá-la levaria junto a explicação de por que aquele pedido teve um degrau a mais.

Efeito prático depois de rodar: um pedido aprovado pelo gestor passa a cair **direto na fila da área**, em vez de esperar uma segunda aprovação da mesma área. Pedidos que já estavam parados naquele degrau continuam lá — a etapa deles já existe — e seguem normalmente quando alguém a decidir.

### As cargas de fontes externas

`semear_fontes --aplicar` cadastra Sankhya, monday, Platform e a carga por
arquivo, mais as quatro regras de precedência entre elas. Ele **não** conecta
nada: sem credencial no ambiente, cada conector responde `disponivel() == False`
e a carga registra *"não está configurada"* — que é estado normal, e não falha.

Ele **nunca reativa** uma fonte desligada à mão. Desativar é o freio de quem
opera, quase sempre no meio de um incidente; a semeadora roda no deploy
seguinte, que é exatamente quando desfazer isso seria pior.

Rodar uma carga:

```bash
python manage.py carregar_fonte sankhya --janela 2026-08            # simula
python manage.py carregar_fonte sankhya --janela 2026-08 --aplicar  # grava
```

Simulação é o padrão, como em todo comando daqui — e a `ExecucaoCarga` da
simulação nasce marcada, para nunca virar carimbo de frescor na tela.

O número a olhar depois de rodar **duas vezes** é `ignorados`: ele conta o que
chegou com conteúdo idêntico e não foi regravado. Se ele vier zero na segunda
passada, a idempotência quebrou — e o sintoma na tela seria o espelho inteiro
dizendo "há 2 min" sem nada realmente novo.

#### Cadência sugerida por fonte

| Fonte | Cadência | Idade que vira alerta | Comando |
|---|---|---|---|
| Sankhya | diária, madrugada | 30 h | `carregar_fonte sankhya --janela AAAA-MM --aplicar` |
| monday | a cada 15 min | 2 h | `carregar_fonte monday --aplicar` |
| Platform | de hora em hora | 6 h | `carregar_fonte iconnect_platform --aplicar` |
| Arquivo | sob demanda | — | `carregar_fonte csv --aplicar` |

A idade máxima é **declarada pela fonte**, e não uma constante do produto: seis
horas é velho para o monday e é novo para a folha do Sankhya. Ela vive em
`FonteDados.idade_maxima_aceitavel` e é editável no `/admin/` — mudar a cadência
não pode exigir deploy.

> **O agendamento em si continua sem dono.** Estes comandos precisam de cron, e
> ele ainda não existe — junto com os quatro `avisar_*` que estão pendentes
> desde a onda de notificações. Enquanto não houver, as cargas rodam à mão e o
> carimbo da tela diz a verdade sobre isso.

### A massa do espelho, e por que ela vem depois das fontes

`semear_resultados --aplicar` popula 18 contratos, 14 projetos e 24 competências
— e ela **passa pelo carregador**, escrevendo CSVs e rodando `carregar()` três
vezes, uma por fonte. Se ela precisasse de um caminho especial para gravar, o
carregador estaria errado.

Sem `semear_fontes` antes, ela avisa e não faz nada: sem fonte cadastrada o
carregador recusa começar.

Ela planta **quinze anomalias de propósito** — contrato deficitário, centro de
custo sem orçamento, carga do monday falhada há 30 h, divergência entre fontes.
Não são sujeira: cada uma exercita uma regra da tela de resultados, e
`cargas/tests/test_massa.py` afirma todas. **Não "conserte" a massa** — o teste
cai e explica por quê.

É determinística: semente fixa, e duas execuções produzem exatamente o mesmo
banco. A segunda passada tem de mostrar `atualizados 0`.

```bash
python manage.py semear_resultados --aplicar --limpar   # ao trocar a semente
```

`--limpar` apaga o espelho antes. Sem ele, duas massas convivem e os números
somam.

### O painel de exceções

`semear_regras_excecao --aplicar` cadastra 18 regras ligadas e 5 **registradas e
desligadas**, cada uma com a fonte de que depende anotada. As desligadas
respondem "por que não vigiamos ASO?" sem ninguém precisar perguntar.

Ela **não reativa** regra desligada à mão — desligar é decisão de quem opera,
quase sempre porque a regra está gerando ruído.

A tela avalia ao vivo. Quem grava o retrato — e portanto a **tendência** que
aparece ao lado da contagem — é o comando:

```bash
python manage.py avaliar_excecoes                     # simula
python manage.py avaliar_excecoes --aplicar           # grava o retrato
python manage.py avaliar_excecoes --aplicar --avisar  # e notifica quem responde
```

`--avisar` é separado de `--aplicar` de propósito: gravar é barato e silencioso;
avisar acorda o sino de todo mundo. Sem cron, a tendência simplesmente não
aparece — a tela mostra a contagem de agora e omite a seta, em vez de inventar
uma.

> **Cadência sugerida:** `--aplicar` de hora em hora, `--avisar` uma vez por dia
> pela manhã. Aviso de hora em hora é como o sino vira ruído.

### Os centros de custo, e por que eles vêm logo depois do organograma

`semear_centros_custo` lê os códigos que já estão em `Lotacao.centro_custo_codigo` e cria um `CentroCusto` para cada um. Ele **não** define orçamento — isso é decisão do Financeiro, e "não definido" é o que a bandeja de aprovação precisa dizer enquanto ninguém decidiu.

Sem este passo o ambiente fica num estado que confunde: toda pessoa tem um código e nenhum código existe. A consequência aparece longe daqui, na bandeja: *"o CC 1042 não tem orçamento mensal definido — não consigo calcular o impacto desta aprovação"*. Quem estava testando o fluxo lê isso e conclui que a barra de orçamento está quebrada; ela não está, não havia o que ler.

O orçamento de cada centro se define depois, **dentro do produto**: *Pessoas e papéis › Centros de custo*. É a mesma tela onde se troca o centro de custo de uma pessoa.

> **O que os seeders criam é plausível e inventado.** Quantidade de estoque, placa de veículo, prazo de curso: substitua pelos dados reais. O que **não** é inventado é a forma — sala de duas pessoas tem duração máxima menor que auditório, a matriz recebe o lote cheio e as bases uma fração.

---

## 13.2 Variáveis de ambiente

> **A lista completa, com o que cada variável protege, está em [`.env.example`](../.env.example).** Ele é versionado e nunca contém valor real; há teste que reprova o contrário, e outro que reprova uma variável nova lida pelo `settings` e ausente dele.
>
> **Antes de subir em produção, leia [EXEC 14 · Segurança](EXEC_14_SEGURANCA.md) § 14.7.** Três garantias são da infraestrutura e o código não consegue dar sozinho: o proxy tem de **sobrescrever** `X-Forwarded-Proto`, o cache tem de ser **compartilhado** entre os processos (a contagem do freio de senha vive nele), e `PROXIES_CONFIAVEIS` tem de ter o número **certo** de saltos.

### Obrigatórias em produção

| variável | o que acontece sem ela |
|---|---|
| `SECRET_KEY` | **o processo não sobe.** Chave de desenvolvimento em produção é o defeito que ninguém percebe até alguém forjar uma sessão |
| `ALLOWED_HOSTS` | **o processo não sobe** |
| `POSTGRES_PASSWORD` | conexão recusada |

### O banco e o cache

`POSTGRES_DB` (`iconnect_workspace`) · `POSTGRES_USER` (`workspace`) · `POSTGRES_HOST` (`localhost`) · `POSTGRES_PORT` (`5432`) · `REDIS_URL` (`redis://127.0.0.1:6379/0`)

### A integração com o iConnect

| variável | padrão | efeito |
|---|---|---|
| `ICONNECT_URL` | `https://app.icodev.com.br/login/` | destino dos cards que levam para fora |
| `ICONNECT_API_URL` | **vazia** | vazia = **integração desligada**, e isso é estado normal |
| `ICONNECT_TIMEOUT` | `4` | segundos. Curto de propósito: a chamada acontece dentro de uma requisição do Workspace |
| `WORKSPACE_SHARED_SECRET` | vazia | quando preenchida **dos dois lados**, o `sso-exchange` exige o header `X-Workspace-Secret` |

### O resto

| variável | padrão | para quê |
|---|---|---|
| `ARQUIVOS_PRIVADOS_ROOT` | `BASE_DIR/arquivos_privados` | onde os anexos moram. **Fora de `MEDIA_ROOT`**, e é o ponto: nenhum arquivo pode ficar num caminho que o nginx serve sem perguntar quem é |
| `CONTA_BANCARIA_EMPRESA` | vazia | para onde devolver sobra de adiantamento. Vazia, a tela diz "peça a conta ao Financeiro" em vez de mostrar um número inventado |
| `CSRF_TRUSTED_ORIGINS` | vazia | separado por vírgula |
| `SECURE_SSL_REDIRECT` | `True` | desligue só atrás de um proxy que já força HTTPS |

> **`ARQUIVOS_PRIVADOS_ROOT` precisa de backup.** Ele não está no banco. Atestado, comprovante de reembolso, currículo e POP moram ali.

---

## 13.3 Os comandos agendados

**Sem cron, os alertas não saem.** Os quatro comandos abaixo são a razão de existir de quatro módulos — e todos são inertes sem agendamento.

```cron
# Alertas diários. Rodam cedo, antes do expediente.
0 6 * * *   cd /app && python manage.py avisar_habilitacoes --aplicar
5 6 * * *   cd /app && python manage.py avisar_frota        --aplicar
10 6 * * *  cd /app && python manage.py avisar_documentos   --aplicar
15 6 * * *  cd /app && python manage.py avisar_marketing    --aplicar

# Conferência semanal do estoque, segunda de manhã.
0 7 * * 1   cd /app && python manage.py conferir_estoque
```

| comando | avisa quem | sobre o quê |
|---|---|---|
| `avisar_habilitacoes` | a pessoa **e** quem responde por ela | NR ou curso vencendo — 30, 15, 7 dias e vencido |
| `avisar_frota` | quem tem `log.frota.operar` | licenciamento, seguro, IPVA ou revisão vencendo |
| `avisar_documentos` | cada pessoa alcançada **e** o dono do documento | leitura obrigatória pendente; vigência acabando |
| `avisar_marketing` | quem tem `mkt.atender` **e** o responsável | prazo de decisão de feira ou edital |
| `conferir_estoque` | ninguém — imprime | divergência entre saldo e razão |

**Rodar todo dia não vira spam.** O dedupe olha o aviso **não lido**: quem já viu e não leu continua com um. E a chave inclui o degrau ou a versão — publicar a v2 de um POP volta a cobrar quem leu a v1, e "vence em 30 dias" e "vence em 7" são dois eventos.

Todos aceitam `--dias N` para mudar a antecedência, e **nenhum grava sem `--aplicar`** — rode sem a flag primeiro para ver o que sairia.

---

## 13.4 Os comandos sob demanda

| comando | quando rodar |
|---|---|
| `reindexar_busca` | depois de migração de dado, de `queryset.update()` em massa, ou se a busca não achar algo que existe |
| `conferir_estoque [--unidade SP]` | conferência periódica, ou quando o saldo parecer errado |
| `semear_catalogo --atualizar` | depois de mexer em `catalogo_inicial.py` — **atualiza** os itens existentes em vez de pular |

> **`conferir_estoque` é somente leitura, de propósito.** Corrigir automaticamente esconderia o defeito de origem. A correção certa é uma **contagem de inventário** na tela de estoque — que tem autor, fica no razão e pode ser explicada depois.

---

## 13.5 Ligar a integração com o iConnect

Nenhum endpoint novo precisa ser criado do lado do iConnect. São três passos.

**1 · No Workspace:**

```bash
ICONNECT_API_URL=https://app.icodev.com.br
ICONNECT_TIMEOUT=4
WORKSPACE_SHARED_SECRET=<um segredo longo>
```

**2 · No iConnect:**

```bash
WORKSPACE_BASE_URL=https://workspace.icodev.com.br   # habilita o ?next= do SSO
WORKSPACE_SHARED_SECRET=<o MESMO segredo>
```

**3 · Confira o caminho:** entre pelo SSO do iConnect com `?next=<url do Workspace>`. O iConnect redireciona com `?sso_exchange=<código>`; o middleware do Workspace troca por JWT e **redireciona limpando o parâmetro**. Abra `/workspace/chamados/` — se a tabela aparece, está ligado.

### Como saber se está ligado

| o que a tela diz | significa |
|---|---|
| "A integração não está configurada neste ambiente" | `ICONNECT_API_URL` vazia. **Não é falha** |
| "Você não está conectado ao iConnect nesta sessão" | a pessoa entrou por senha, sem passar pelo SSO. Não há token dela |
| "O iConnect está com problema" | tentou e não deu. O log tem o endpoint e o código |

### O rollout pode ser independente

`WORKSPACE_SHARED_SECRET` vazia de um dos lados faz a checagem ser pulada. Ligue um lado, depois o outro.

---

## 13.6 Monitoramento

### A sonda

```
GET /saude/   →  200 {"status":"ok","banco":"ok"}
              →  503 {"status":"indisponivel","banco":"erro"}
```

`Cache-Control: no-store`. **503 e não 200 com um JSON dizendo "erro"** — o balanceador lê o código.

> **Se a sonda voltar 400 e não 200**, o problema não é a aplicação: a sonda do orquestrador chega pelo **IP do contêiner**, e o Django recusa `Host` desconhecido antes de qualquer view rodar. Ponha o IP do pod em `ALLOWED_HOSTS`.

### O que observar no log

| linha | o que fazer |
|---|---|
| `iConnect GET ... → HTTP 401` | o JWT da pessoa expirou e o refresh não resolveu. Normal em sessão longa |
| `iConnect GET ... → HTTP 5xx` recorrente | o outro lado está fora. As telas degradam sozinhas |
| `provedor de IA ... falhou` | o provedor de IA estourou. O assistente volta à base curada sozinho |
| `sso-exchange recusado` | código expirado (60s) ou já usado. Rotina — só investigue se for constante |
| `aprovacao_sem_dono` (notificação) | uma etapa parou num papel que ninguém ocupa. **Isto exige ação**: conceda o papel |

---

## 13.7 Diagnóstico

### "O pedido foi aprovado e ninguém fez nada"

1. `/workspace/fila/` como alguém da área — o pedido está lá?
2. Alguém tem `<área>.atender`? Sem ninguém com a permissão, a fila existe e não tem dono.
3. Chegou notificação `PEDIDO_NA_FILA`? Se não, o domínio do item pode estar apontando para a área errada.

### "A busca não acha uma coisa que existe"

`python manage.py reindexar_busca`. O índice é mantido por sinal, mas `queryset.update()` em massa não dispara `post_save` — é a causa mais comum.

Se continuar sem achar: o conteúdo pode não **alcançar** a pessoa. Documento e comunicado têm público-alvo; solicitação e correspondência são recortadas por pessoa no `WHERE`.

### "O saldo do estoque está errado"

```bash
python manage.py conferir_estoque
```

O razão é a verdade. A divergência só nasce por caminho que não passou pelo serviço — um `update()` em migração, uma correção no shell. **Corrija por contagem de inventário na tela**, nunca no banco: o `update()` recria a divergência sem deixar rastro.

### "O orçamento diz que acabou e não acabou"

`consumido = realizado + comprometido`. Compromisso sai do comprometido quando o pedido é **concluído**. Pedido entregue e não marcado como concluído mantém o valor preso — confira a fila.

### "A pessoa não vê uma tela que deveria ver"

1. Ela tem o papel? `/workspace/pessoas/`
2. O papel tem a permissão? `identidade/papeis.py`
3. O **escopo** alcança? Permissão `.unidade` não vê outra unidade.
4. Papel concedido vale **a partir da requisição seguinte** — o cache de permissão vive dentro de uma requisição só. Peça para recarregar.

### "Alguém vê uma tela que NÃO deveria"

Rode `pytest workspace/tests/test_auditoria_permissoes.py`. Se passar e o vazamento existir, **acrescente a porta à lista `PORTAS_DE_TERCEIROS`** do arquivo — ele só verifica o que conhece.

---

## 13.8 Antes de cada deploy

```bash
pytest -q                                     # 2.291 testes
python scripts/check_coverage_ratchet.py      # cobertura e contagem
python manage.py makemigrations --check       # modelo mudado sem migração
python manage.py check --deploy               # checagem de produção do Django
python manage.py collectstatic --noinput      # o hash no nome vem daqui
```

> **`check --deploy` acusa 6 avisos com as settings de desenvolvimento** — HSTS, cookie seguro, `DEBUG`. É esperado: essas configurações moram em `settings/prod.py`. Rode com `DJANGO_SETTINGS_MODULE=iconnect_workspace.settings.prod`, e o resultado é limpo.

E, no primeiro deploy depois de mexer em índice ou catálogo:

```bash
python manage.py migrate
python manage.py reindexar_busca
python manage.py semear_catalogo --atualizar   # se catalogo_inicial.py mudou
```

### O que NÃO fazer

- **Não apague item de catálogo.** `SolicitacaoServico.item` é `PROTECT`, e apagar levaria junto o histórico que explica quem pediu o quê.
- **Não corrija saldo com `UPDATE`.** Use contagem de inventário.
- **Não mexa em `MovimentoEstoque`, `EventoSolicitacao` nem `ConfirmacaoLeitura`.** São livros, e é por isso que não têm tela de edição.
- **Não sirva `ARQUIVOS_PRIVADOS_ROOT` pelo nginx.** O diretório existe fora de `MEDIA_ROOT` exatamente para isso.
