# Automação local de pendências de ponto

Ambiente local e determinístico para o fluxo:

`Excel → n8n → agrupamento por colaborador → Evolution API → WhatsApp`

Não há IA, serviço pago, Selenium ou automação de navegador. O workflow é importado desativado e só executa manualmente. Por padrão, `TEST_MODE=true` redireciona todas as mensagens ao telefone pessoal configurado em `TEST_PHONE`.

## Dois workflows

Desde a integração com o Portal existem **dois** arquivos em `n8n/`:

| Arquivo | Gatilho | Quem decide |
|---|---|---|
| `workflow-pendencias-ponto.json` | manual | o n8n: lê o Excel montado, agrupa, escolhe destino |
| `workflow-portal-ponto.json` | webhook | o Portal: manda a lista pronta com `loteId` |

O primeiro é o original e **não foi alterado**. Confira quando quiser:

```bash
node scripts/build-workflow.js | diff - n8n/workflow-pendencias-ponto.json
```

O segundo é gerado por `scripts/build-portal-workflow.js` e recebe em
`POST /webhook/ponto-pendencias` um corpo com `loteId`, `modoTeste`,
`telefoneTeste` e a lista `mensagens[]` já agrupada por colaborador. Ele não lê
arquivo, não normaliza telefone e não monta mensagem — isso passou a viver no
Django, em `workspace/services/ponto.py`.

A barreira de modo de teste continua nele, comparando cada destino com o
`telefoneTeste` do corpo. Ele exige `N8N_PONTO_TOKEN` no header
`Authorization: Bearer`.

Documentação do lado do Portal: `docs/rh-pendencias-ponto.md`.

> **Atenção ao telefone.** O normalizador deste workflow original rejeita o
> formato `(019) 98888-7777` que a planilha real usa — o zero de tronco faz o
> número ter 12 dígitos e nunca receber o prefixo `55`. Medido na planilha de
> setembro/2026: 57 de 57 colaboradores reprovados. Em `TEST_MODE=true` isso
> não aparece, porque o destino é substituído antes do envio. O caminho do
> Portal corrige; este aqui não, e por isso ele não deve ser usado com
> `TEST_MODE=false`.

## Estrutura

```text
.
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── arquivos/
│   └── ajuste-de-ponto.xlsx
├── n8n/
│   └── workflow-pendencias-ponto.json
├── postgres/init/
│   └── 01-create-databases.sql
└── tests/
    └── workflow.test.js
```

## Pré-requisitos e instalação do Docker

- macOS ou Windows: instale e abra o [Docker Desktop](https://docs.docker.com/desktop/).
- Linux: instale o [Docker Engine](https://docs.docker.com/engine/install/) e o plugin Docker Compose.
- Para executar os testes unitários sem Docker: Node.js 20 ou superior.

Confirme a instalação:

```bash
docker --version
docker compose version
```

## Configuração segura

Crie o arquivo local de configuração:

```bash
cp .env.example .env
```

Gere três valores diferentes e fortes:

```bash
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
```

Edite `.env` e substitua `POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY` e `EVOLUTION_API_KEY`. Configure o seu WhatsApp pessoal em `TEST_PHONE`, usando apenas dígitos no formato `55 + DDD + número`.

Não inicie os containers enquanto qualquer valor começar com `SUBSTITUA_` ou enquanto `TEST_PHONE` contiver `X`.

Mantenha obrigatoriamente:

```dotenv
EVOLUTION_INSTANCE=teste-pessoal
TEST_MODE=true
TEST_PHONE=5519999999999
```

O número acima é apenas ilustrativo. O `.env` está ignorado pelo Git. Não coloque credenciais no workflow nem versione esse arquivo.

## Validar e iniciar

Valide a composição:

```bash
docker compose config --quiet
```

Baixe e inicie os serviços:

```bash
docker compose pull
docker compose up -d
docker compose ps
```

Espere até que todos os serviços exibam `healthy`. Se algum falhar:

```bash
docker compose logs --tail=200 postgres redis evolution-api n8n
```

Se o PostgreSQL já tiver sido iniciado anteriormente com outra senha, `--force-recreate` não basta: esse comando preserva o volume e a senha gravada no banco. Em um ambiente local ainda sem dados úteis, depois de preencher corretamente o `.env`, reinicialize os volumes com:

```bash
docker compose down --volumes
docker compose up -d
```

O primeiro comando apaga o banco, o usuário local do n8n e eventuais sessões da Evolution API. Não o execute depois que houver dados que precisem ser preservados.

Portas expostas somente em loopback:

- n8n: <http://localhost:5678>
- Evolution API: <http://localhost:8080>
- Evolution Manager: <http://localhost:8080/manager>

PostgreSQL e Redis não publicam portas no host.

A Evolution API usa `CORS_ORIGIN=*` para permitir a navegação direta ao Manager, que pode chegar sem cabeçalho `Origin`. Isso permanece restrito à máquina local porque a porta `8080` está vinculada exclusivamente a `127.0.0.1`; ao migrar para servidor, restrinja o CORS ao domínio HTTPS do proxy.

## Preparar o n8n

1. Abra <http://localhost:5678>.
2. No primeiro acesso, crie o usuário proprietário local do n8n.
3. Selecione **Workflows → Import from File**.
4. Importe `n8n/workflow-pendencias-ponto.json`.
5. Confirme que o workflow continua desativado e que a anotação vermelha informa: **MODO DE TESTE ATIVO — TODAS AS MENSAGENS SERÃO REDIRECIONADAS**.

O arquivo local `./arquivos/ajuste-de-ponto.xlsx` é montado, somente para leitura, em:

```text
/home/node/.n8n-files/ajuste-de-ponto.xlsx
```

Para trocar a planilha, mantenha exatamente esse nome e as colunas esperadas. Fórmulas de telefone iniciadas por `=` são rejeitadas em produção. No modo de teste, `TEST_PHONE` prevalece mesmo quando o telefone da planilha está ausente ou contém fórmula.

## Criar a instância e visualizar o QR Code

A opção mais simples é pelo Evolution Manager:

1. Abra <http://localhost:8080/manager>.
2. Informe a URL `http://localhost:8080` e a `EVOLUTION_API_KEY` do seu `.env`.
3. Crie a instância `teste-pessoal` com a integração **WHATSAPP-BAILEYS**.
4. Solicite/exiba o QR Code.
5. No seu WhatsApp pessoal, abra **Aparelhos conectados → Conectar um aparelho** e leia o QR Code.
6. Confirme no Manager que o estado da instância é `open`.

Alternativamente, crie a instância pela API. Carregue o `.env` somente no seu terminal local:

```bash
set -a
source .env
set +a

curl --fail-with-body --request POST \
  --url http://localhost:8080/instance/create \
  --header "apikey: ${EVOLUTION_API_KEY}" \
  --header 'Content-Type: application/json' \
  --data '{"instanceName":"teste-pessoal","qrcode":true,"integration":"WHATSAPP-BAILEYS"}'
```

Para pedir um QR Code novo da instância já criada:

```bash
curl --fail-with-body \
  --url http://localhost:8080/instance/connect/teste-pessoal \
  --header "apikey: ${EVOLUTION_API_KEY}"
```

Esses comandos não usam nem conectam o número corporativo. O futuro remetente `+55 19 99555-0001` está apenas documentado; não é configurado automaticamente.

## Executar o teste controlado

Antes de executar, confirme dentro do container:

```bash
docker compose exec n8n sh -lc 'printf "TEST_MODE=%s\nTEST_PHONE=%s\nEVOLUTION_INSTANCE=%s\n" "$TEST_MODE" "$TEST_PHONE" "$EVOLUTION_INSTANCE"'
```

O resultado deve mostrar `TEST_MODE=true`, seu número pessoal e `teste-pessoal`.

No n8n, abra o workflow importado e clique em **Execute Workflow**. O comportamento esperado é:

- uma mensagem consolidada por colaborador;
- pendências em ordem cronológica;
- mensagens de colaboradores diferentes chegando sequencialmente ao mesmo `TEST_PHONE`;
- nenhum telefone da planilha alcançando o node HTTP;
- falha de um item não interrompendo os demais.

Há duas proteções independentes:

1. O agrupamento substitui todos os destinos por `TEST_PHONE` quando `TEST_MODE=true`.
2. Imediatamente antes do HTTP, outra validação compara novamente `telefoneDestino` com `TEST_PHONE`; qualquer divergência recebe `status=bloqueado_seguranca` e não é enviada.

## Resultados e logs

Cada item final contém:

- `nome`;
- `telefoneOriginal` e `telefoneDestino`;
- `modoTeste`;
- `quantidadePendencias` e `mensagem`;
- `status` e `processadoEm`;
- `retornoEvolutionApi` ou `erro`.

No n8n, consulte **Executions**, abra a execução e veja os nodes **Registrar resultado do envio**, **Registrar bloqueio ou telefone inválido** e **Resultados finais**. As execuções são podadas após 168 horas ou 1.000 registros para reduzir a retenção de dados pessoais.

Logs dos containers:

```bash
docker compose logs --tail=200 n8n
docker compose logs --tail=200 evolution-api
docker compose logs -f evolution-api n8n
```

Não compartilhe logs sem revisar nomes, telefones e mensagens.

## Testes automatizados

Os testes executam exatamente o JavaScript embutido no workflow:

```bash
npm test
```

Eles cobrem uma e várias pendências, entrada/saída/pausa/retorno ausentes, observação, telefones inválidos e mascarados, inclusão do DDI 55, fórmula externa e as duas barreiras de `TEST_MODE`.

Se o JavaScript do workflow for alterado manualmente, atualize o gerador e recrie o JSON para manter uma única fonte:

```bash
node scripts/build-workflow.js > /tmp/workflow-pendencias-ponto.json
diff -u n8n/workflow-pendencias-ponto.json /tmp/workflow-pendencias-ponto.json
```

## Parar, reiniciar e remover dados

Parar sem apagar dados:

```bash
docker compose down
```

Reiniciar:

```bash
docker compose restart
```

Subir novamente:

```bash
docker compose up -d
```

Apagar todos os volumes locais, incluindo banco, usuário n8n e sessão do WhatsApp:

```bash
docker compose down --volumes
```

Esse último comando é destrutivo e exige nova configuração e novo pareamento.

## Migração futura para servidor

Antes de migrar:

1. mantenha `TEST_MODE=true` na primeira implantação;
2. use um domínio com HTTPS e proxy reverso;
3. remova os binds `127.0.0.1` somente para o proxy, nunca para PostgreSQL ou Redis;
4. use um gerenciador de segredos e credenciais novas;
5. restrinja firewall e CORS;
6. configure backup criptografado dos volumes PostgreSQL, n8n e Evolution;
7. defina retenção, acesso e descarte dos dados pessoais conforme a política da empresa;
8. valide uma lista pequena e autorizada antes de considerar `TEST_MODE=false`;
9. conecte a instância oficial do RH somente após aprovação explícita.

Não reutilize as credenciais locais no servidor. Não desligue `TEST_MODE` apenas porque os containers estão saudáveis: isso confirma a infraestrutura, não autoriza disparos reais.

O fluxo local precisa ler `TEST_MODE`, `TEST_PHONE` e os dados da Evolution API, por isso o acesso a variáveis de ambiente nos nós do n8n está habilitado. Em produção, mova a chave da API para uma credencial do n8n, bloqueie esse acesso nos nós de código e proteja o editor com controle de acesso.

## Versões e contrato da API

- n8n `2.39.10` (estável e fixado no Compose).
- Evolution API `2.3.7` (última versão estável; a linha `2.4.0` disponível durante esta implementação era release candidate).
- PostgreSQL `17.6` e Redis `7.4.5` (imagens fixadas no Compose).
- O workflow usa `POST /message/sendText/{instance}`, header `apikey` e corpo `{ "number": "...", "text": "..." }`, conforme o schema da Evolution API `2.3.7`.

Para atualizar qualquer imagem, revise as notas de versão, execute `npm test`, `docker compose config --quiet` e repita todo o teste em `TEST_MODE=true`.
