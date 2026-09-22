/* ─────────────────────────────────────────────────────────────────────
 * O WORKFLOW QUE O PORTAL CHAMA.
 *
 * Arquivo SEPARADO de `build-workflow.js`, e não uma flag dentro dele — §42.
 * O gerador original continua gerando byte a byte o que gerava; quem quiser
 * conferir roda `node scripts/build-workflow.js | diff - n8n/workflow-pendencias-ponto.json`
 * e não precisa saber que este aqui existe.
 *
 * ## A diferença
 *
 * O workflow original decide tudo: lê o Excel montado no container, normaliza
 * telefone, agrupa por pessoa, monta a mensagem e escolhe o destino. O estado
 * vive na aba Executions e é podado em 168 horas.
 *
 * Este não decide nada. Recebe do Portal a lista já agrupada, já validada,
 * com `loteId` e `envioId`, entrega à Evolution API e devolve o resultado de
 * cada item. Quem guarda o que aconteceu é o Portal.
 *
 * ## O que NÃO foi removido
 *
 * A barreira de modo de teste. Ela agora compara o destino com o
 * `telefoneTeste` que veio no corpo — e não com `$env.TEST_PHONE` —, porque o
 * modo passou a ser decidido por lote. A conferência item a item e o bloqueio
 * do que divergir continuam idênticos. Duas barreiras no Portal e uma aqui:
 * quem manda a lista e quem entrega não podem ser a mesma verificação.
 */

const guardCode = `const entrada = $('Receber do Portal').first().json.body || {};
const modoTeste = entrada.modoTeste === true;
const telefoneTeste = String(entrada.telefoneTeste || '').replace(/\\D/g, '');

return $input.all().map((item) => {
  const dado = { ...item.json };
  const destino = String(dado.telefoneDestino || '').replace(/\\D/g, '');

  /* Em modo de teste, destino diferente do telefone de teste NÃO é enviado.
     O Portal já garante isso antes de chamar; esta é a última barreira, e ela
     existe para o caso de a chamada não ter vindo de onde se espera. */
  const divergente = modoTeste && (!telefoneTeste || destino !== telefoneTeste);
  const seguro = Boolean(destino) && !divergente;

  dado.loteId = entrada.loteId;
  dado.telefoneDestino = destino;
  dado.modoTeste = modoTeste;
  dado.podeEnviarSeguro = seguro;
  if (!seguro) {
    dado.status = divergente ? 'bloqueado_seguranca' : 'telefone_invalido';
    dado.erro = divergente
      ? 'Barreira de seguranca: em modo de teste o destino deve ser igual ao telefone de teste'
      : 'Destino invalido antes do envio';
  }
  return { json: dado };
});`;

const splitCode = `const corpo = $input.first().json.body || {};

/* O token do Portal. Confere ANTES de qualquer coisa: webhook aberto e
   convite a mandar WhatsApp em nome da empresa.

   FALHA FECHADA. A versao anterior so conferia quando o token existia,
   que pula a conferencia inteira quando a variavel nao chega ao container — e
   foi exatamente o que aconteceu: N8N_PONTO_TOKEN estava no .env mas nao no
   environment: do compose, e o webhook aceitou uma chamada sem token
   nenhuma com HTTP 200. Token ausente agora e recusa, nao liberacao. */
const esperado = String($env.N8N_PONTO_TOKEN || '');
if (!esperado) {
  throw new Error('N8N_PONTO_TOKEN nao configurado no n8n — recusando por seguranca');
}
const recebido = String($('Receber do Portal').first().json.headers?.authorization || '')
  .replace(/^Bearer\\s+/i, '');
if (recebido !== esperado) {
  throw new Error('Token invalido');
}

const mensagens = Array.isArray(corpo.mensagens) ? corpo.mensagens : [];
if (!mensagens.length) return [];
return mensagens.map((m) => ({ json: { ...m } }));`;

const resultCode = `/* O HTTP pode NAO ter rodado: quando todo item e bloqueado pela barreira, o
   ramo verdadeiro do IF fica vazio e referenciar o no levanta
   "hasn't been executed". Sem este try o Portal recebia 500 justamente no
   caso em que mais precisa da resposta — o de saber por que nada foi enviado. */
let enviados = [];
try {
  enviados = $('Enviar via Evolution API (Portal)').all();
} catch (e) {
  enviados = [];
}
const origens = $('Barreira de seguranca (Portal)').all()
  .filter((i) => i.json.podeEnviarSeguro === true);

const resultados = origens.map((origem, indice) => {
  const resposta = enviados[indice] ? enviados[indice].json : {};
  const codigo = Number(resposta.statusCode || 0);
  const falhou = Boolean(resposta.error) || codigo >= 400;
  return {
    envioId: origem.json.envioId,
    status: falhou ? 'erro_envio' : 'enviado',
    erro: falhou
      ? String(resposta.error?.message || resposta.message || ('HTTP ' + codigo))
      : null,
  };
});

const bloqueados = $('Barreira de seguranca (Portal)').all()
  .filter((i) => i.json.podeEnviarSeguro !== true)
  .map((i) => ({ envioId: i.json.envioId, status: i.json.status, erro: i.json.erro }));

return [{ json: { resultados: resultados.concat(bloqueados) } }];`;

const booleanCondition = (field) => ({
  conditions: {
    options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
    conditions: [{
      id: field + '-condition',
      leftValue: `={{ $json.${field} }}`,
      rightValue: true,
      operator: { type: 'boolean', operation: 'true', singleValue: true },
    }],
    combinator: 'and',
  },
  options: {},
});

const workflow = {
  id: 'ponto-pendencias-portal',
  name: 'RH - Pendencias de Ponto - Portal (webhook)',
  nodes: [
    {
      parameters: {
        httpMethod: 'POST',
        path: 'ponto-pendencias',
        responseMode: 'lastNode',
        options: {},
      },
      id: 'portal-webhook',
      name: 'Receber do Portal',
      type: 'n8n-nodes-base.webhook',
      typeVersion: 2,
      position: [-820, 120],
      /* O `webhookId` e o que faz a rota ser `/webhook/ponto-pendencias` e nao
         o caminho composto `/webhook/<id>/<nome do no>/<path>`. A interface
         gera este UUID ao criar o no; um JSON importado sem ele ativa o
         workflow e nao registra rota nenhuma — o sintoma e um 404 com
         "Activated workflow" no log, que nao parece erro de import. */
      webhookId: 'a3f81d64-9c27-4e5b-b0a8-2f6d94e7c015',
    },
    {
      parameters: { jsCode: splitCode },
      id: 'portal-split',
      name: 'Conferir token e separar',
      type: 'n8n-nodes-base.code',
      typeVersion: 2,
      position: [-580, 120],
    },
    {
      parameters: { jsCode: guardCode },
      id: 'portal-guard',
      name: 'Barreira de seguranca (Portal)',
      type: 'n8n-nodes-base.code',
      typeVersion: 2,
      position: [-340, 120],
    },
    {
      parameters: booleanCondition('podeEnviarSeguro'),
      id: 'portal-safe',
      name: 'Destino passou na barreira? (Portal)',
      type: 'n8n-nodes-base.if',
      typeVersion: 2.2,
      position: [-100, 120],
    },
    {
      parameters: {
        method: 'POST',
        url: "={{ $env.EVOLUTION_URL + '/message/sendText/' + $env.EVOLUTION_INSTANCE }}",
        sendHeaders: true,
        headerParameters: {
          parameters: [
            { name: 'apikey', value: '={{ $env.EVOLUTION_API_KEY }}' },
            { name: 'Content-Type', value: 'application/json' },
          ],
        },
        sendBody: true,
        contentType: 'raw',
        rawContentType: 'application/json',
        body: '={{ JSON.stringify({ number: $json.telefoneDestino, text: $json.mensagem }) }}',
        options: {
          response: { response: { fullResponse: true, neverError: true, responseFormat: 'json' } },
          timeout: 30000,
        },
      },
      id: 'portal-send',
      name: 'Enviar via Evolution API (Portal)',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 4.2,
      position: [160, 20],
      onError: 'continueRegularOutput',
    },
    {
      parameters: { jsCode: resultCode },
      id: 'portal-result',
      name: 'Responder ao Portal',
      type: 'n8n-nodes-base.code',
      typeVersion: 2,
      position: [420, 120],
    },
    {
      parameters: {
        content:
          '## ENTRADA DO PORTAL\n\nEste workflow NAO le Excel e NAO escolhe destinatario. Ele recebe do Portal a lista ja validada com `loteId` e devolve o resultado por `envioId`.\n\nA barreira de modo de teste continua aqui, comparando cada destino com o `telefoneTeste` do corpo.\n\nExige `N8N_PONTO_TOKEN` no header `Authorization: Bearer`.',
        height: 300,
        width: 520,
        color: 5,
      },
      id: 'portal-note',
      name: 'COMO ESTE WORKFLOW E CHAMADO',
      type: 'n8n-nodes-base.stickyNote',
      typeVersion: 1,
      position: [-820, -280],
    },
  ],
  connections: {
    'Receber do Portal': { main: [[{ node: 'Conferir token e separar', type: 'main', index: 0 }]] },
    'Conferir token e separar': {
      main: [[{ node: 'Barreira de seguranca (Portal)', type: 'main', index: 0 }]],
    },
    'Barreira de seguranca (Portal)': {
      main: [[{ node: 'Destino passou na barreira? (Portal)', type: 'main', index: 0 }]],
    },
    'Destino passou na barreira? (Portal)': {
      main: [
        [{ node: 'Enviar via Evolution API (Portal)', type: 'main', index: 0 }],
        [{ node: 'Responder ao Portal', type: 'main', index: 0 }],
      ],
    },
    'Enviar via Evolution API (Portal)': {
      main: [[{ node: 'Responder ao Portal', type: 'main', index: 0 }]],
    },
  },
  active: false,
  settings: {
    executionOrder: 'v1',
    timezone: 'America/Sao_Paulo',
    saveDataErrorExecution: 'all',
    saveDataSuccessExecution: 'all',
  },
  versionId: '7c1f0b52-6d4a-4f0e-9d2b-3a5e8c41f7d9',
  meta: { templateCredsSetupCompleted: true },
  pinData: {},
  tags: [],
};

process.stdout.write(JSON.stringify(workflow, null, 2) + '\n');
