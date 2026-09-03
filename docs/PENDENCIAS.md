# Pendências do iConnect Workspace

> **Conferido em 03/09/2026** contra o repositório e contra um banco recém-semeado.
> 3.341 testes verdes, cobertura 98,25%. As onze ondas de produto estão
> implementadas.
>
> **Nenhum item desta lista é código a escrever.** São acessos que só outra
> pessoa consegue, decisões que só o dono do produto toma, e infraestrutura que
> só existe na máquina de produção. Está separado assim de propósito: misturar
> "falta programar" com "falta pedir a senha" é como uma pendência de dez
> minutos fica seis semanas parada esperando um sprint.

---

## O quadro

| # | Pendência | Espécie | De quem depende | O que destrava |
|---|---|---|---|---|
| 1 | Credenciais das 3 fontes | acesso | T.I. / Sankhya / monday | 7 telas com dado real |
| 2 | `crontab` não instalado | infra | quem opera o servidor | carga automática |
| 3 | Teto dos centros de custo | dado | Financeiro | a tela 15 |
| 4 | Retenção de atestado médico | decisão | dono do produto + jurídico | conformidade LGPD |
| 5 | Três garantias de infraestrutura | infra | quem opera o servidor | subir em produção |
| 6 | `pip-audit` reprova ou avisa? | decisão | você | o CI |
| 7 | Senha do superusuário de dev | higiene | você, agora | 30 segundos |
| 8 | QA de gente nas telas 10 a 15 | trabalho | Victor | confiança no que foi entregue |
| 9 | Acervo real de documentos | dado | cada área | o assistente (onda F) |
| 10 | Analytics pessoal | escopo | você | módulo decidido e não construído |
| 11 | `CONTA_BANCARIA_EMPRESA` | dado | Financeiro | devolução de adiantamento |

**Se você só puder resolver três**, resolva a **7** (trinta segundos), a **3**
(cinco minutos) e a **1** (a que destrava mais tela por esforço).

---

## 1 · As credenciais das três fontes

**Estado hoje, conferido:**

```
$ python manage.py conferir_integracoes
── sankhya ──            4 FALTA
── monday ──             2 FALTA   (1 variável + o dicionário MONDAY_BOARDS)
── iconnect_platform ──  2 FALTA
0 de 3 fonte(s) configurada(s).
```

**Isto não é falha, e a distinção importa.** "Não configurada" é um dos três
estados que a tela 99 sabe dizer, e é diferente de "atrasada" e de "desativada".
Cada conector responde `disponivel() == False`, e as telas dizem isso em
português em vez de mostrar zero.

**O roteiro completo, com de quem pedir o quê, está em
[EXEC_24_LIGAR_AS_FONTES.md](EXEC_24_LIGAR_AS_FONTES.md).** O resumo:

| Fonte | O que pedir | De quem | Custo de conseguir |
|---|---|---|---|
| **iConnect Platform** | um segredo compartilhado que **você mesmo gera** | ninguém — os dois lados são nossos | **nenhum** |
| **monday.com** | token de usuário de **serviço**, somente leitura | quem administra a conta monday | baixo |
| **Sankhya Om** | `client_id`, `client_secret` **e** o X-Token do Gateway | quem administra o Sankhya | alto |

**Comece pela Platform.** Ela não depende de terceiro nenhum e já entrega
contratos, vigência e satisfação. Enquanto as três não chegam, o espelho é
enchido por CSV (`semear_resultados`), e a tela **não sabe a diferença** — é o
mesmo caminho de qualquer outra fonte.

**Duas armadilhas conhecidas, ambas custam uma tarde:**

- O **`SANKHYA_TOKEN` não é o `client_secret`**. É outro segredo, de outra tela
  (Configurações Gateway, Sankhya Om 4.16+). É onde a maioria das configurações
  trava.
- **Não aceite o token pessoal de alguém no monday.** Ele enxerga o que a pessoa
  enxerga, e sai da empresa junto com ela — deixando a carga quebrada num dia em
  que ninguém associa uma coisa à outra.

---

## 2 · O `crontab` existe no repositório e não está instalado em lugar nenhum

`deploy/crontab` tem **dez comandos**: `carregar_fonte`, `avaliar_excecoes`,
`verificar_planos`, `conferir_estoque` e cinco `avisar_*`.

```bash
crontab deploy/crontab && crontab -l
sudo mkdir -p /var/log/workspace && sudo chown "$(whoami)" /var/log/workspace
```

**A ordem dentro do dia não é decorativa.** `carregar_fonte` às 05h30,
`avaliar_excecoes` às 08h00, `verificar_planos` às 08h30. Invertida,
`verificar_planos` roda sobre o espelho da véspera e **fecha um plano de ação
pelo número que ele tinha antes da última carga** — e o registro dirá que o
problema deixou de ocorrer.

Enquanto não estiver instalado, **toda carga é manual**, e a seta de tendência
das exceções nunca aparece.

---

## 3 · Os centros de custo não têm teto, e por isso a tela 15 abre vazia

Achado seguindo o guia de QA num banco limpo:

```
semear_orcamento --aplicar
→ 0 orçamento(s) de 2026 criado(s), 3 centro(s) sem teto definido.
```

`semear_centros_custo` cria os três centros com `orcamento_mensal` **nulo**, de
propósito: vazio significa *não definido*, que é diferente de zero — zero o
aprovador leria como "tem folga".

**Como resolver, em cinco minutos:** preencha o orçamento mensal em
`/admin/financas/centrocusto/` e rode `semear_orcamento --aplicar` de novo.

Sem isso, o Victor não consegue testar a tela 15 nem a revisão orçamentária.

---

## 4 · Retenção de atestado médico (LGPD)

Anexo de dado de saúde **não tem prazo de expurgo definido**. O produto já o
mantém fora de grade e fora de exportação — a restrição está em teste — mas
guardar para sempre é a decisão que ninguém tomou explicitamente, e é a que
aparece numa auditoria.

É decisão de política, com jurídico. Não há código a escrever antes de existir
um prazo; havendo, o expurgo é um comando de management como os outros.

---

## 5 · As três garantias de infraestrutura

Nenhuma é configuração do Django. Todas dependem de como a máquina está montada:

| Garantia | Se faltar |
|---|---|
| O proxy **sobrescreve** `X-Forwarded-Proto`, e o processo não é alcançável por fora dele | qualquer um forja "esta requisição veio por HTTPS" |
| O cache é **compartilhado** entre processos | quatro workers dão ao atacante quatro vezes mais tentativas de senha |
| `PROXIES_CONFIAVEIS` reflete a topologia **real** | ou o freio lê o IP errado, ou tranca a empresa inteira atrás do balanceador |

O `.env.example` explica cada uma no lugar onde ela é usada; o detalhe está em
[EXEC_14_SEGURANCA.md](EXEC_14_SEGURANCA.md).

---

## 6 · `pip-audit` reprova o build ou só avisa?

Decisão de uma linha, com consequência real nos dois sentidos.

**Reprovando:** uma CVE publicada numa dependência transitiva trava o deploy de
uma correção urgente que não tem nada a ver com ela.

**Avisando:** o aviso vira ruído em duas semanas, e ninguém lê o do dia em que
importava.

**Recomendação:** reprovar em `high` e `critical`, avisar no resto. É o corte
que mantém o sinal caro sem travar o deploy por CVE de severidade baixa em
biblioteca de build.

---

## 7 · A senha do superusuário de desenvolvimento

Ainda é a que foi usada nos testes de força bruta: `senha-forte-de-teste-2026`.

```bash
python manage.py changepassword christopher.ataide@autodefesabrasil.com.br
```

Trinta segundos, e é a única pendência desta lista que não depende de mais
ninguém. Enquanto o banco de desenvolvimento for local, é higiene; no dia em que
alguém copiar esse banco para uma máquina compartilhada, deixa de ser.

**Junto:** `semear_perfis` cria os 17 perfis de teste com a senha `workspace123`,
impressa no terminal. Isso é correto **em desenvolvimento** e é a razão pela qual
esse comando **nunca** deve rodar em produção.

---

## 8 · Nenhuma tela das ondas 5 a 11 passou por QA de gente

Telas 10 a 15, mais os quatro movimentos do painel e os nove gráficos. Elas têm
teste automatizado — foi o que segurou a suíte em 3.341 —, mas teste automatizado
confere o que alguém pensou em conferir.

O roteiro está pronto: [GUIA_QA_WORKSPACE.md](GUIA_QA_WORKSPACE.md), com a caixa
"o que mudou nesta rodada" no topo e o **Roteiro H** cobrindo o painel em treze
passos.

**Um aviso ao Victor, e vale repetir aqui:** o guia tinha três afirmações erradas
que só apareceram quando eu o segui à risca num banco vazio — faltava o
`createsuperuser`, faltavam seis semeadoras, e "anônimo recebe 403" era mentira
(é 302). Já corrigidas. Se ele achar uma quarta, é achado do guia, não dele.

---

## 9 · O acervo de documentos reais

O assistente de conhecimento (onda F) está **bloqueado por dado, não por código**:
existem 5 documentos, todos de demonstração. Ele precisa dos POPs e normativos
reais — a referência de projeto é **40 documentos**.

Nada a construir antes disso. Construir sobre 5 documentos produziria um
assistente que responde com confiança sobre o que não sabe, que é a pior falha
possível nessa classe de produto.

---

## 10 · Analytics pessoal — decidido e não construído

A decisão está tomada e registrada (**ADR-014**): dado de uso individual é
visível **só para a própria pessoa**, escopo `proprio`; a gestão vê agregado. A
regra vale **desde a coleta**, e não como filtro na tela.

O que falta é construir. É a única linha desta lista que é trabalho de
desenvolvimento — e está aqui porque ela não pertence a nenhuma das onze ondas, e
sem registro ela some.

---

## 11 · A conta bancária da empresa

`CONTA_BANCARIA_EMPRESA` está vazia. É para onde a pessoa devolve o que sobrou de
um adiantamento.

Vazia, a tela diz *"peça a conta ao Financeiro"* em vez de mostrar um número
inventado — o comportamento correto, e não um defeito. Mas ela deixa um passo do
fluxo de dinheiro dependendo de conversa.

Fica em variável de ambiente e **não no banco** de propósito: conta bancária
editável por quem tem acesso ao admin é convite a fraude.

---

## O que NÃO está nesta lista, e por quê

| Não é pendência | Por quê |
|---|---|
| Fonte "não configurada" | Estado normal, e um dos três que a tela 99 distingue |
| Faixa de resultado sem dado | Ela diz qual fonte falta. Zerar seria dizer que a empresa parou |
| Gráfico ausente no PDF | Decisão registrada (ADR-041): exigiria um navegador inteiro no servidor |
| Módulos além dos 12 | Não estão "em breve": não existem na lista. Ausência é honesta, promessa não (ADR-039) |
| Habilitações e certificações | Moram no iConnect **Platform**, com zero registros. Não é módulo daqui |
| Integração com M365 / HRIS | Suíte definida, integração não construída — e fora do escopo das onze ondas |
| `ADB_CLIENTE_URL` / `ADB_FORNECEDOR_URL` vazias | Os dois produtos não existem. Vazio quer dizer **ausente** |
| Perfurar até ocorrência ou ticket | Fronteira de arquitetura deliberada, não tela faltando |

---

## Como manter este documento honesto

Três comandos respondem por quase tudo daqui:

```bash
python manage.py conferir_integracoes    # item 1
crontab -l                               # item 2
python manage.py semear_orcamento        # item 3 — sem --aplicar, é simulação
```

Se algum deles passar a responder outra coisa, **é aqui que a mudança se
registra**. Uma lista de pendências que ninguém atualiza vira uma lista de
desculpas — e a diferença entre as duas é só o tempo desde a última conferência.
