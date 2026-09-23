# RH — Pendências de Ponto

O R.H. importa a planilha do PontoTel, revisa quem tem pendência, dispara um
teste no próprio celular e, com permissão específica, avisa os colaboradores
por WhatsApp. Sem abrir n8n, Docker ou terminal.

---

## O bug que a integração corrigiu

A automação em `workspace/rh/integrations/ponto_whatsapp/` já existia e já
tinha rodado localmente. Ela rejeitava **57 dos 57 telefones** da planilha
real.

A planilha do PontoTel escreve o telefone como `(019) 98888-7777`, com o zero
de tronco no DDD. O normalizador original fazia:

```js
let digits = raw.replace(/\D/g, '');            // "019988887777"  (12 dígitos)
if (digits.length === 10 || digits.length === 11) digits = '55' + digits;
return /^55[1-9]\d[2-9]\d{7,8}$/.test(digits) ? digits : '';   // reprova
```

Doze dígitos não entram no `if`, então o `55` nunca era acrescentado, e a
expressão exigia início em `55`. Todo colaborador virava `telefone_invalido`.

Ninguém percebeu porque **em modo de teste o destino é substituído pelo
`TEST_PHONE` antes do envio** — a coluna de telefone nunca chegou a ser
exercitada. O dia em que `TEST_MODE=false` fosse ligado, o resultado seria zero
mensagens enviadas e 57 erros.

A correção está em `normalizar_telefone`, em [`workspace/services/ponto.py`](../workspace/services/ponto.py):

```python
if digitos.startswith("0"):
    digitos = digitos.lstrip("0")
```

O teste `test_a_planilha_de_verdade_e_processada_inteira` trava a regressão
contra o arquivo real.

---

## Arquitetura

```text
navegador
   │  HTTPS, sessão do Portal
   ▼
Django  ──  workspace/views/ponto.py          RBAC, confirmação, mensagens
   │
   ├─ services/ponto.py          regras puras: planilha, telefone, mensagem
   ├─ services/ponto_lote.py     ciclo de vida, permissões, auditoria
   └─ services/ponto_whatsapp.py barreiras + a chamada ao n8n
   │
   │  POST JSON + Authorization: Bearer
   ▼
n8n  ──  workflow "Portal (webhook)"          transporte, sem decisão
   │
   ▼
Evolution API  ──  WhatsApp
```

O navegador **nunca** fala com o n8n nem com a Evolution API. Não há chave de
API em JavaScript, HTML ou cookie.

### Por que o estado saiu do n8n

Antes, o n8n lia o Excel de um volume montado e decidia tudo: agrupava,
normalizava, escolhia destino. O resultado vivia só na aba *Executions*, podada
em 168 horas.

Isso responde *"deu certo agora?"*. Não responde *"quem importou?"*, *"quem foi
avisado em setembro?"*, *"por que o Fulano não recebeu?"*.

Agora o Portal manda a lista **já agrupada, já validada, com `loteId` e
`envioId`**. O n8n entrega e devolve o resultado por item. Ele deixou de ser o
sistema e passou a ser o transporte.

---

## Modelos

Quatro tabelas, em `workspace/models/ponto.py`:

| Modelo | O que é |
|---|---|
| `LotePonto` | A importação: arquivo, quem, quando, modo, situação |
| `ColaboradorPonto` | Uma pessoa dentro do lote — uma pessoa, uma mensagem |
| `EnvioPonto` | Cada TENTATIVA de entrega; teste e produção deixam linhas separadas |
| `EventoPonto` | A auditoria: quem mexeu no telefone, quem confirmou o disparo |

As pendências de uma pessoa moram num `JSONField` dentro de
`ColaboradorPonto`. Uma quinta tabela para elas seria um `JOIN` em todo acesso
para nunca responder pergunta própria.

**A planilha não é guardada.** Ela traz `CPF` e `Senha` (a senha do totem) de
todos os colaboradores, e nada depois do processamento precisa dela. Fica o
SHA-256, que responde *"é a mesma planilha de ontem?"* sem manter o dado
sensível. As duas colunas são descartadas na leitura — ver `COLUNAS_IGNORADAS`.

### Situações

Lote: `RASCUNHO` → `VALIDANDO` → `VALIDADO` → `PROCESSANDO` → `CONCLUIDO` |
`CONCLUIDO_COM_ERROS` | `CANCELADO`

Envio: `PENDENTE` → `ENVIANDO` → `ENVIADO` | `ERRO` | `IGNORADO`

---

## Rotas

| Método | URL | Nome | Permissão |
|---|---|---|---|
| GET | `/workspace/rh/pendencias-ponto/` | `pendencias_ponto` | `rh.ponto_ler` |
| POST | `…/importar/` | `ponto_importar` | `rh.ponto_importar` |
| GET | `…/historico/` | `ponto_historico` | `rh.ponto_ler` |
| GET | `…/lote/<pk>/` | `ponto_lote` | `rh.ponto_ler` |
| POST | `…/lote/<pk>/selecionar/` | `ponto_selecionar` | `rh.ponto_importar` |
| POST | `…/lote/<pk>/enviar/` | `ponto_enviar` | `rh.ponto_testar` **ou** `rh.ponto_enviar` |
| GET | `…/lote/<pk>/progresso/` | `ponto_progresso` | `rh.ponto_ler` |
| POST | `…/colaborador/<pk>/telefone/` | `ponto_corrigir` | `rh.ponto_importar` |
| GET | `…/colaborador/<pk>/mensagem/` | `ponto_mensagem` | `rh.ponto_ler` |

O card do catálogo aponta para cá pelo campo `ItemCatalogo.rota_interna`, que
guarda o **nome** da rota — nunca o caminho. Caminho gravado em banco quebra em
silêncio quando a URL muda; nome quebra alto, no `reverse`.

---

## Segurança

### Modo de teste — três barreiras

O lote **nasce em teste**. O `default` do campo `modo` é parte da proteção: um
lote criado por um caminho que esqueça de definir o modo continua sendo teste.

1. **`destinos_do_lote`** — em teste, o telefone do colaborador *não é sequer
   consultado*. A função devolve o telefone de teste para todos.
2. **`_conferir_barreira`** — percorre o que foi montado e compara cada destino
   com o telefone de teste. Uma divergência levanta `FalhaDeSeguranca` e para o
   **lote inteiro**, não o item.
3. **O workflow do n8n** — repete a comparação com o `telefoneTeste` do corpo.

A segunda parece redundante com a primeira, e é de propósito: a primeira
protege contra o dado errado, a segunda contra o **código** errado. Uma
refatoração futura que monte destino por outro caminho encontra a barreira
antes que alguém receba mensagem indevida.

**Não existe fallback para o telefone real.** Um `except` que "tenta o número
verdadeiro" seria a única forma de o modo de teste vazar, então ele não existe.

### RBAC

```text
rh.ponto_ler        abre a tela e o histórico
rh.ponto_importar   envia planilha e corrige telefone
rh.ponto_testar     dispara para o telefone de teste
rh.ponto_enviar     dispara para os colaboradores   ← concessão própria
```

`rh.ponto_enviar` **não está** no papel `rh` e nunca é derivada de outra. É a
única ação do produto sem desfazer.

Os nomes usam `_` e não `.` por um motivo concreto: o casamento de permissão em
`identidade/services/autorizacao.py` é **por prefixo**
(`pedida.startswith(base + ".")`). Com `rh.ponto.ler` e `rh.ponto.enviar`, uma
concessão de `rh.ponto.global` cobriria as duas. Com underscore, nenhuma das
quatro é prefixo de outra.

Autorização é conferida no servidor em toda rota. Esconder botão é cortesia com
quem olha a tela.

### Upload

Confere extensão, tamanho, arquivo vazio e **assinatura** (`PK` para XLSX). O
`Content-Type` do navegador não decide nada — quem escolhe é o cliente. Teto de
10 MB e 5.000 linhas.

O arquivo nunca toca diretório público: ele é lido em memória e descartado.

### Portal → n8n

`Authorization: Bearer <N8N_PONTO_TOKEN>`. O token vai no cabeçalho, nunca no
corpo, e o workflow recusa a chamada quando não bate — webhook aberto não
acontece por esquecimento.

### Dado pessoal

Telefone aparece **mascarado** na tela, no log e na auditoria
(`(19) 9****-1608`). O número inteiro existe só na coluna e no payload do
envio. `CPF` e `Senha` nunca são lidos.

---

## Configuração

No `.env` da **raiz do projeto** — carregado automaticamente por
`settings/base.py`, sem precisar exportar nada antes do `runserver`:

```dotenv
N8N_PONTO_WEBHOOK_URL=http://localhost:5678/webhook/ponto-pendencias
N8N_PONTO_TOKEN=<openssl rand -hex 32>
PONTO_WHATSAPP_TIMEOUT=30
PONTO_MAXIMO_POR_LOTE=500
```

No `.env` da **automação** (`workspace/rh/integrations/ponto_whatsapp/.env`):

```dotenv
N8N_PONTO_TOKEN=<o MESMO valor acima>
EVOLUTION_API_KEY=<...>
EVOLUTION_INSTANCE=teste-pessoal
TEST_MODE=true
TEST_PHONE=55DDNNNNNNNNN
```

Com `N8N_PONTO_WEBHOOK_URL` vazio, a tela funciona até a revisão e recusa o
disparo com mensagem clara em vez de falhar no meio.

---

## Como rodar em localhost

1. **Suba a automação**

   ```bash
   cd workspace/rh/integrations/ponto_whatsapp
   cp .env.example .env          # e troque todos os SUBSTITUA_
   docker compose up -d
   docker compose ps             # espere todos `healthy`
   ```

2. **Importe o workflow do Portal**

   Em <http://localhost:5678> → *Workflows* → *Import from File* →
   `n8n/workflow-portal-ponto.json`.

   Ele importa **desativado**. Ative-o: sem isso o webhook responde 404.

3. **Conecte o WhatsApp**

   <http://localhost:8080/manager>, instância `teste-pessoal`, integração
   WHATSAPP-BAILEYS, leia o QR Code com o **seu** celular.

4. **Configure o Django** com as variáveis acima e reinicie o servidor.

5. **Dê as permissões** em `/admin/identidade/atribuicaopapel/`. O papel `rh`
   já traz `ler`, `importar` e `testar`. Para `rh.ponto_enviar` é preciso um
   ato deliberado.

O workflow **antigo** (gatilho manual, lê o Excel montado) continua
funcionando e não foi alterado. Confira com:

```bash
node scripts/build-workflow.js | diff - n8n/workflow-pendencias-ponto.json
```

---

## Testes

```bash
.venv/bin/pytest workspace/tests/test_ponto_motor.py \
                 workspace/tests/test_ponto_seguranca.py \
                 workspace/tests/test_ponto_tela.py -q
```

| Arquivo | Cobre |
|---|---|
| `test_ponto_motor.py` | Planilha, telefone, agrupamento, mensagem — sem banco |
| `test_ponto_seguranca.py` | As barreiras do modo de teste, falhas do n8n |
| `test_ponto_tela.py` | RBAC, upload, correção, o caminho inteiro |

A automação continua com os próprios testes em JavaScript:

```bash
cd workspace/rh/integrations/ponto_whatsapp && npm test
```

---

## Migrar para servidor

Além do que o README da automação já diz:

1. `N8N_PONTO_WEBHOOK_URL` em **HTTPS**, atrás do proxy reverso. O token viaja
   no cabeçalho e em HTTP ele viaja em claro.
2. Gere um `N8N_PONTO_TOKEN` novo — não reutilize o de desenvolvimento.
3. Mantenha `rh.ponto_enviar` concedida a **uma ou duas pessoas**.
4. O primeiro disparo real deve ser uma planilha reduzida, com três ou quatro
   colaboradores combinados antes.
5. Defina retenção dos lotes. O Portal guarda nome, telefone e pendências por
   tempo indeterminado; a política de dado pessoal da empresa decide por quanto.

---

## Troubleshooting

| Sintoma | Causa provável |
|---|---|
| "A integração não está configurada" | `N8N_PONTO_WEBHOOK_URL` vazio |
| "O n8n recusou o lote (HTTP 404)" | Workflow importado mas **desativado** |
| "O n8n recusou o lote (HTTP 401)" ou `Token invalido` | Os dois `N8N_PONTO_TOKEN` não batem |
| "Não foi possível falar com o n8n" | Containers fora do ar |
| Mensagens não chegam, tudo "enviado" | Instância da Evolution desconectada — veja o Manager |
| Colaborador como "Telefone não disponível" | §35: a célula tem fórmula, não número |
| Todos "Telefone inválido" | Formato fora do padrão brasileiro de celular |
| 403 ao confirmar o envio real | Falta `rh.ponto_enviar` — é concessão separada |
