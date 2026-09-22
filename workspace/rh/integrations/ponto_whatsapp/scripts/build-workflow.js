const aggregateCode = `function clean(value) {
  if (value === undefined || value === null) return '';
  return String(value).trim();
}

function testModeFromEnvironment(value) {
  return clean(value).toLowerCase() !== 'false';
}

function normalizePhone(value) {
  const raw = clean(value);
  if (!raw || raw.startsWith('=')) return '';

  let digits = raw.replace(/\\D/g, '');
  if (digits.length === 10 || digits.length === 11) digits = '55' + digits;
  return /^55[1-9]\\d[2-9]\\d{7,8}$/.test(digits) ? digits : '';
}

function formatDate(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    const date = new Date(Date.UTC(1899, 11, 30) + Math.round(value * 86400000));
    const day = String(date.getUTCDate()).padStart(2, '0');
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    const year = date.getUTCFullYear();
    return { display: day + '/' + month + '/' + year, sortKey: year * 10000 + Number(month) * 100 + Number(day) };
  }

  const raw = clean(value);
  const br = raw.match(/^(\\d{1,2})\\/(\\d{1,2})\\/(\\d{4})$/);
  if (br) {
    const day = br[1].padStart(2, '0');
    const month = br[2].padStart(2, '0');
    const year = br[3];
    return { display: day + '/' + month + '/' + year, sortKey: Number(year + month + day) };
  }

  const iso = raw.match(/^(\\d{4})-(\\d{2})-(\\d{2})/);
  if (iso) {
    return { display: iso[3] + '/' + iso[2] + '/' + iso[1], sortKey: Number(iso[1] + iso[2] + iso[3]) };
  }

  return { display: raw || 'data não informada', sortKey: Number.MAX_SAFE_INTEGER };
}

function joinMissing(parts) {
  if (parts.length === 1) return parts[0];
  return parts.slice(0, -1).join(', ') + ' e ' + parts[parts.length - 1];
}

function buildReason(row) {
  const missing = [];
  if (!clean(row['Entrada'])) missing.push('entrada');
  if (!clean(row['Pausa'])) missing.push('pausa');
  if (!clean(row['Retorno'])) missing.push('retorno');
  if (!clean(row['Saída'])) missing.push('saída');

  if (missing.length) return 'ausência de marcação de ' + joinMissing(missing);
  return clean(row['Observação']).replace(/\\s+/g, ' ').replace(/\\s*\\.\\s*$/, '') || 'pendência na apuração do ponto';
}

const testMode = testModeFromEnvironment($env.TEST_MODE);
const testPhone = normalizePhone($env.TEST_PHONE);
const groups = new Map();

for (const item of $input.all()) {
  const row = item.json;
  const employee = clean(row['Funcionário']).replace(/\\s+/g, ' ');
  if (!employee) continue;

  const key = employee.toLocaleUpperCase('pt-BR');
  const originalPhone = clean(row['Telefone']);
  const normalizedPhone = normalizePhone(originalPhone);
  if (!groups.has(key)) {
    groups.set(key, {
      funcionario: employee,
      telefoneOriginal: originalPhone,
      telefonePlanilha: normalizedPhone,
      pendencias: new Map(),
    });
  }

  const group = groups.get(key);
  if (!group.telefoneOriginal && originalPhone) group.telefoneOriginal = originalPhone;
  if (!group.telefonePlanilha && normalizedPhone) group.telefonePlanilha = normalizedPhone;

  const date = formatDate(row['Data']);
  const reason = buildReason(row);
  group.pendencias.set(date.display + '|' + reason.toLocaleUpperCase('pt-BR'), {
    data: date.display,
    motivo: reason,
    sortKey: date.sortKey,
  });
}

const output = [];
for (const group of groups.values()) {
  const pendencias = Array.from(group.pendencias.values())
    .sort((a, b) => a.sortKey - b.sortKey || a.motivo.localeCompare(b.motivo, 'pt-BR'))
    .map(({ data, motivo }) => ({ data, motivo }));
  const pendenciasTexto = pendencias.map((item) => '• ' + item.data + ' — ' + item.motivo).join('\\n');
  const mensagem = 'Prezado(a) colaborador(a),\\n\\n' +
    'Identificamos pendências na apuração do seu ponto nos dias listados abaixo:\\n\\n' +
    pendenciasTexto + '\\n\\n' +
    'Solicitamos que realize a regularização o quanto antes.\\n\\n' +
    'Lembramos que o registro no aplicativo PontoTel deve ser feito em tempo real, no momento exato da ação, como no início da jornada, nos intervalos e no término do expediente. A reincidência nessas ausências de marcação poderá acarretar medidas disciplinares.\\n\\n' +
    'Estamos à disposição.\\n\\n' +
    'Recursos Humanos';
  const telefoneDestino = testMode ? testPhone : group.telefonePlanilha;
  const podeEnviar = Boolean(telefoneDestino);

  output.push({
    json: {
      nome: group.funcionario,
      telefoneOriginal: group.telefoneOriginal,
      telefonePlanilha: group.telefonePlanilha,
      telefoneDestino,
      modoTeste: testMode,
      quantidadePendencias: pendencias.length,
      pendencias,
      mensagem,
      status: podeEnviar ? 'pronto_para_envio' : 'telefone_invalido',
      processadoEm: null,
      retornoEvolutionApi: null,
      erro: podeEnviar ? null : (testMode ? 'TEST_PHONE ausente ou inválido' : 'Telefone da planilha ausente, inválido ou contém fórmula'),
      podeEnviar,
    },
  });
}

return output;`;

const securityCode = `function clean(value) {
  if (value === undefined || value === null) return '';
  return String(value).trim();
}

function normalizePhone(value) {
  const raw = clean(value);
  if (!raw || raw.startsWith('=')) return '';
  let digits = raw.replace(/\\D/g, '');
  if (digits.length === 10 || digits.length === 11) digits = '55' + digits;
  return /^55[1-9]\\d[2-9]\\d{7,8}$/.test(digits) ? digits : '';
}

const environmentTestMode = clean($env.TEST_MODE).toLowerCase() !== 'false';
const expectedTestPhone = normalizePhone($env.TEST_PHONE);

return $input.all().map((item) => {
  const data = { ...item.json };
  const destination = normalizePhone(data.telefoneDestino);
  const mismatch = environmentTestMode && (!expectedTestPhone || destination !== expectedTestPhone);
  const safe = data.podeEnviar === true && Boolean(destination) && !mismatch;

  if (!safe) {
    data.status = mismatch ? 'bloqueado_seguranca' : data.status;
    data.erro = mismatch
      ? 'Barreira de segurança: em TEST_MODE o telefoneDestino deve ser exatamente igual ao TEST_PHONE'
      : (data.erro || 'Destino inválido antes do envio');
  }

  data.telefoneDestino = destination;
  data.modoTeste = environmentTestMode;
  data.podeEnviarSeguro = safe;
  return { json: data };
});`;

const rejectedLogCode = `return $input.all().map((item) => ({
  json: {
    ...item.json,
    processadoEm: new Date().toISOString(),
    retornoEvolutionApi: null,
  },
}));`;

const sentLogCode = `const origins = $('Segunda validação de segurança').all()
  .filter((item) => item.json.podeEnviarSeguro === true);

return $input.all().map((item, index) => {
  const response = item.json;
  const origin = origins[index] ? origins[index].json : {};
  const statusCode = Number(response.statusCode || 0);
  const failed = Boolean(response.error) || statusCode >= 400;
  return {
    json: {
      ...origin,
      status: failed ? 'erro_envio' : 'enviado',
      processadoEm: new Date().toISOString(),
      retornoEvolutionApi: response,
      erro: failed ? String(response.error?.message || response.message || ('HTTP ' + statusCode)) : null,
    },
  };
});`;

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
  id: 'ponto-pendencias-seguro',
  name: 'RH - Pendências de Ponto - WhatsApp (modo seguro)',
  nodes: [
    { parameters: {}, id: 'manual-trigger', name: 'Executar manualmente', type: 'n8n-nodes-base.manualTrigger', typeVersion: 1, position: [-1000, 120] },
    { parameters: { fileSelector: '/home/node/.n8n-files/ajuste-de-ponto.xlsx', options: {} }, id: 'read-xlsx', name: 'Ler ajuste-de-ponto.xlsx', type: 'n8n-nodes-base.readWriteFile', typeVersion: 1.1, position: [-780, 120] },
    { parameters: { operation: 'xlsx', options: {} }, id: 'extract-xlsx', name: 'Converter XLSX para JSON', type: 'n8n-nodes-base.extractFromFile', typeVersion: 1, position: [-560, 120] },
    { parameters: { jsCode: aggregateCode }, id: 'aggregate', name: 'Normalizar, agrupar e montar mensagens', type: 'n8n-nodes-base.code', typeVersion: 2, position: [-320, 120] },
    { parameters: booleanCondition('podeEnviar'), id: 'valid-phone', name: 'Telefone de destino válido?', type: 'n8n-nodes-base.if', typeVersion: 2.2, position: [-60, 120] },
    { parameters: { jsCode: securityCode }, id: 'security-guard', name: 'Segunda validação de segurança', type: 'n8n-nodes-base.code', typeVersion: 2, position: [180, 20] },
    { parameters: booleanCondition('podeEnviarSeguro'), id: 'safe-destination', name: 'Destino passou na barreira?', type: 'n8n-nodes-base.if', typeVersion: 2.2, position: [420, 20] },
    {
      parameters: {
        method: 'POST',
        url: "={{ $env.EVOLUTION_URL + '/message/sendText/' + $env.EVOLUTION_INSTANCE }}",
        sendHeaders: true,
        headerParameters: { parameters: [
          { name: 'apikey', value: '={{ $env.EVOLUTION_API_KEY }}' },
          { name: 'Content-Type', value: 'application/json' },
        ] },
        sendBody: true,
        contentType: 'raw',
        rawContentType: 'application/json',
        body: '={{ JSON.stringify({ number: $json.telefoneDestino, text: $json.mensagem }) }}',
        options: { response: { response: { fullResponse: true, neverError: true, responseFormat: 'json' } }, timeout: 30000 },
      },
      id: 'send-evolution',
      name: 'Enviar via Evolution API',
      type: 'n8n-nodes-base.httpRequest',
      typeVersion: 4.2,
      position: [680, -80],
      onError: 'continueRegularOutput',
    },
    { parameters: { jsCode: sentLogCode }, id: 'log-sent', name: 'Registrar resultado do envio', type: 'n8n-nodes-base.code', typeVersion: 2, position: [940, -80] },
    { parameters: { jsCode: rejectedLogCode }, id: 'log-rejected', name: 'Registrar bloqueio ou telefone inválido', type: 'n8n-nodes-base.code', typeVersion: 2, position: [680, 220] },
    { parameters: {}, id: 'results', name: 'Resultados finais', type: 'n8n-nodes-base.noOp', typeVersion: 1, position: [1180, 80] },
    {
      parameters: {
        content: '## MODO DE TESTE ATIVO — TODAS AS MENSAGENS SERÃO REDIRECIONADAS\n\nCom `TEST_MODE=true`, o destino vem exclusivamente de `TEST_PHONE`. Uma segunda barreira imediatamente antes do HTTP bloqueia qualquer divergência.',
        height: 240,
        width: 500,
        color: 5,
      },
      id: 'test-note',
      name: 'MODO DE TESTE ATIVO',
      type: 'n8n-nodes-base.stickyNote',
      typeVersion: 1,
      position: [80, -360],
    },
    {
      parameters: {
        content: '## Remetente\n\nConecte somente um WhatsApp pessoal na instância `teste-pessoal`. O número corporativo **+55 19 99631-8785** não é conectado nem alterado por este workflow.',
        height: 210,
        width: 430,
        color: 7,
      },
      id: 'sender-note',
      name: 'REMETENTE DE TESTE',
      type: 'n8n-nodes-base.stickyNote',
      typeVersion: 1,
      position: [650, -360],
    },
  ],
  connections: {
    'Executar manualmente': { main: [[{ node: 'Ler ajuste-de-ponto.xlsx', type: 'main', index: 0 }]] },
    'Ler ajuste-de-ponto.xlsx': { main: [[{ node: 'Converter XLSX para JSON', type: 'main', index: 0 }]] },
    'Converter XLSX para JSON': { main: [[{ node: 'Normalizar, agrupar e montar mensagens', type: 'main', index: 0 }]] },
    'Normalizar, agrupar e montar mensagens': { main: [[{ node: 'Telefone de destino válido?', type: 'main', index: 0 }]] },
    'Telefone de destino válido?': { main: [
      [{ node: 'Segunda validação de segurança', type: 'main', index: 0 }],
      [{ node: 'Registrar bloqueio ou telefone inválido', type: 'main', index: 0 }],
    ] },
    'Segunda validação de segurança': { main: [[{ node: 'Destino passou na barreira?', type: 'main', index: 0 }]] },
    'Destino passou na barreira?': { main: [
      [{ node: 'Enviar via Evolution API', type: 'main', index: 0 }],
      [{ node: 'Registrar bloqueio ou telefone inválido', type: 'main', index: 0 }],
    ] },
    'Enviar via Evolution API': { main: [[{ node: 'Registrar resultado do envio', type: 'main', index: 0 }]] },
    'Registrar resultado do envio': { main: [[{ node: 'Resultados finais', type: 'main', index: 0 }]] },
    'Registrar bloqueio ou telefone inválido': { main: [[{ node: 'Resultados finais', type: 'main', index: 0 }]] },
  },
  active: false,
  settings: { executionOrder: 'v1', timezone: 'America/Sao_Paulo', saveDataErrorExecution: 'all', saveDataSuccessExecution: 'all' },
  versionId: 'fe69df89-fd50-4a48-91ab-ddd624c03d1f',
  meta: { templateCredsSetupCompleted: true },
  pinData: {},
  tags: [],
};

process.stdout.write(JSON.stringify(workflow, null, 2) + '\n');
