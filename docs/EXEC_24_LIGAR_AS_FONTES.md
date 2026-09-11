# EXEC 24 · Ligar as fontes e o agendamento

> O roteiro de quem tem os acessos. Não há código pendente — o que falta são
> **sete variáveis de ambiente, um dicionário e um `crontab`**. Conferido com
> `conferir_integracoes` em 03/09/2026: **0 de 3 fontes configuradas**.

---

## 24.1 O que está esperando o quê

Sete telas dependem das integrações e hoje **nenhuma tem dado real**. Isso não é
defeito: cada conector responde `disponivel() == False`, a carga registra "não
configurada" e o carimbo diz "sem registro de carga". As telas dizem isso em
português, e o produto continua sendo um produto.

| Tela | O que ganha quando a fonte entrar |
|---|---|
| Resultados (10) | receita, margem, EBITDA, carteira, projetos, NPS |
| Fontes de dados (99) | o histórico de execuções deixa de ser vazio |
| Exceções (11) | 9 das 19 regras saem de "não avaliada" |
| Ciclos (12) | o carimbo de cada etapa deixa de ser mudo |
| Planos (13) | as 4 regras com limiar passam a gerar dívida |
| Metas (14) | 6 dos 8 fatores passam a apurar |
| Orçamento (15) | o confronto com o orçado contábil aparece |

**A ordem certa é: Platform → monday → Sankhya.** Da mais barata para a mais
cara de conseguir, e nessa ordem cada uma já entrega tela.

---

## 24.2 Antes de qualquer coisa

```bash
python manage.py semear_fontes --aplicar     # sem isto, o carregador RECUSA
python manage.py conferir_integracoes        # o que falta, e de quem pedir
```

`conferir_integracoes` é o comando desta etapa. Ele **nunca imprime credencial** —
nem mascarada, porque segredo mascarado em log é segredo em log com uma falsa
sensação de cuidado. O que sai é `definida` ou `FALTA`, mais onde se consegue
cada uma.

A foto de hoje, para você saber que a saída abaixo é a esperada e não um erro:

```
── sankhya ──            4 FALTA
── monday ──             2 FALTA   (1 variável + o dicionário MONDAY_BOARDS)
── iconnect_platform ──  2 FALTA
0 de 3 fonte(s) configurada(s).
```

São **oito linhas** e **sete variáveis** — `MONDAY_BOARDS` é dicionário no
settings, e não variável de ambiente, porque id de board não é segredo: é
inventário, e inventário em `.env` não sobrevive à primeira coluna renomeada.

---

## 24.3 iConnect Platform — a mais barata

**De quem pedir:** de você mesmo. Os dois lados são nossos.

```bash
# Gere o segredo:
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`.env` **dos dois produtos**, com o mesmo valor:

```
ICONNECT_API_URL=https://app.icodev.com.br/api
WORKSPACE_SHARED_SECRET=<o valor gerado>
```

**Do lado da Platform**, três rotas somente leitura, autenticadas por
`X-Workspace-Secret`:

| Rota | Devolve |
|---|---|
| `/contratos/` | código, cliente, vigência, valor mensal, regional, centro de custo |
| `/competencias/` | por contrato e mês: receita, custo, margem |
| `/avaliacoes/` | NPS: data, nota, classificação, tratativa — **sem** quem respondeu |

O conector **recusa** campos de dado pessoal que cheguem por engano
(`RECUSADOS`), e recusa paginação cujo `next` aponte para fora do host. Não é
preciso filtrar do outro lado — mas mandar só o consolidado é o desenho: o
detalhe operacional continua morando lá (§5 do benchmark).

```bash
python manage.py conferir_integracoes iconnect_platform --testar
python manage.py carregar_fonte iconnect_platform          # simulação
python manage.py carregar_fonte iconnect_platform --aplicar
```

---

## 24.4 monday.com — a do meio

**De quem pedir:** de quem administra a conta monday da ADB.

**Peça um usuário de SERVIÇO, somente leitura** — nunca o token pessoal de
alguém. Token pessoal enxerga o que a pessoa enxerga, e sai da empresa junto com
ela, deixando a carga quebrada num dia em que ninguém associa uma coisa à outra.

O token está em: monday → avatar → **Developers** → **My Access Tokens**.

```
MONDAY_TOKEN=<o token do usuário de serviço>
```

**Os ids de board e coluna não vão no `.env`** — são um dicionário, e vão em
`MONDAY_BOARDS` no settings. Levante-os com:

```bash
python scripts/inventario_monday.py
```

> O JSON com `--com-amostra` contém nome de cliente e de colaborador. Ele **não
> é versionado**, e não deve ser colado em chamado.

O conector usa a API `2026-07`, pagina por cursor (`items_page` /
`next_items_page`), lê status por `label` e relação por `linked_item_ids`. O
espelho é **ignorado** de propósito: espelho de board é cópia de cópia.

```bash
python manage.py conferir_integracoes monday --testar
python manage.py carregar_fonte monday --aplicar
```

---

## 24.5 Sankhya Om — a mais cara

**De quem pedir:** de quem administra o Sankhya, e de quem responde pelo
contrato com eles.

Duas coisas, de lugares diferentes:

1. **`client_id` e `client_secret`** — Portal do Desenvolvedor da Sankhya, no
   componente da solução.
2. **`SANKHYA_TOKEN`** — o X-Token, na tela **"Configurações Gateway"** do
   próprio Sankhya Om (4.16 em diante). **É outro segredo**, e não o
   `client_secret`. É aqui que a maioria das configurações trava.

```
SANKHYA_BASE_URL=https://api.sankhya.com.br      # sandbox: api.sandbox.sankhya.com.br
SANKHYA_CLIENT_ID=
SANKHYA_CLIENT_SECRET=
SANKHYA_TOKEN=
```

O fluxo é OAuth2 `client_credentials` no Gateway — conferido na documentação
vigente em 01/09/2026, e **não** o fluxo antigo de usuário e senha em cabeçalho
que ainda circula em exemplos.

**A pergunta a fazer junto com a credencial:** *quais views o usuário de
integração enxerga?* O conector lê por `loadRecords`, e a resposta vem
posicional (`f0..fn`) — uma view a menos não dá erro, dá campo vazio.

**Comece pelo sandbox.** A primeira carga de um ERP em produção, sem janela, é
uma varredura completa.

```bash
python manage.py conferir_integracoes sankhya --testar
python manage.py carregar_fonte sankhya --janela 2026-08          # simulação
python manage.py carregar_fonte sankhya --janela 2026-08 --aplicar
```

---

## 24.6 Depois da primeira carga

```bash
python manage.py semear_regras_excecao --aplicar   # as 9 regras saem de "não avaliada"
python manage.py avaliar_excecoes --aplicar        # o primeiro retrato: a tendência nasce daqui
```

Abra `/workspace/resultados/fontes/` (código 99): o histórico de execuções
responde "de onde vem esse número" com um link, e não com um chamado.

**A divergência entre fontes vai aparecer, e é o desenho funcionando.** Sankhya
e monday discordam sobre valor de projeto; Sankhya e Platform, sobre vigência de
contrato. A precedência é declarada por campo em `RegraPrecedencia`, e o que
passa do limiar vira ocorrência na tela — nunca um `if` escolhendo (ADR-036).

---

## 24.7 O agendamento

```bash
# Ajuste APP e VENV, e instale:
crontab deploy/crontab
crontab -l
```

Dez comandos. **A ordem dentro do dia importa:**

```
05h30  carregar_fonte    →  05h50
06h00  avisar_*          →  06h15
08h00  avaliar_excecoes
08h30  verificar_planos
```

Invertida, `verificar_planos` roda sobre o espelho da véspera e **fecha um plano
pelo número que ele tinha antes da última carga**. O intervalo entre um degrau e
o seguinte é folgado de propósito: uma carga lenta não pode empurrar a avaliação
para depois da conferência.

`MAILTO=""` e saída em arquivo: dez e-mails por dia viram uma regra de filtro, e
é assim que se para de ler o erro do dia em que ele importa. Crie `$LOG` antes:

```bash
sudo mkdir -p /var/log/workspace && sudo chown "$(whoami)" /var/log/workspace
```

**Nenhuma semeadora está no cron**, e é deliberado: uma correção feita à mão
voltaria sozinha na manhã seguinte, sem ninguém associar uma coisa à outra.

---

## 24.8 O que conferir uma semana depois

| Sinal | Onde | O que quer dizer |
|---|---|---|
| a seta de tendência apareceu | `/workspace/excecoes/` | `avaliar_excecoes` está rodando |
| o histórico tem uma linha por dia por fonte | `/workspace/resultados/fontes/` | as cargas estão rodando |
| algum plano fechou sozinho | `/workspace/planos/` | `verificar_planos` está conferindo |
| o carimbo diz "há 6 h" e não "sem registro" | qualquer faixa de números | o espelho está fresco |

Se uma fonte falhar, **o bloco não zera**: a tela mostra o último dado bom com a
idade em destaque e o motivo ao lado. Zerar seria dizer que a empresa parou.

---

## 24.9 O que ainda depende de decisão sua, e não de acesso

- **Retenção de atestado médico** (LGPD). Anexo de dado de saúde não tem prazo de
  expurgo definido — é decisão de política, não de implementação.
- **Três garantias de infraestrutura**: o proxy precisa sobrescrever
  `X-Forwarded-Proto`, o cache precisa ser compartilhado entre processos, e
  `PROXIES_CONFIAVEIS` precisa refletir a topologia real.
- **`pip-audit` no CI**: decidir se ele reprova o build ou só avisa.
- **A senha do superusuário de desenvolvimento** ainda é a dos testes de força
  bruta: `python manage.py changepassword christopher.ataide@autodefesabrasil.com.br`.
