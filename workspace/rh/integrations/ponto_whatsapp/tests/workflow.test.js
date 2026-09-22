const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const workflowPath = path.join(
  __dirname,
  '..',
  'n8n',
  'workflow-pendencias-ponto.json',
);

function loadWorkflow() {
  return JSON.parse(fs.readFileSync(workflowPath, 'utf8'));
}

function getNode(name) {
  const node = loadWorkflow().nodes.find((candidate) => candidate.name === name);
  assert.ok(node, `Node ausente no workflow: ${name}`);
  return node;
}

async function runCodeNode(name, rows, env = {}) {
  const code = getNode(name).parameters.jsCode;
  const context = vm.createContext({
    $env: env,
    $input: { all: () => rows.map((json) => ({ json })) },
    Date,
    Intl,
    Map,
    Set,
  });

  return vm.runInContext(`(async () => { ${code}\n})()`, context);
}

function row(overrides = {}) {
  return {
    Data: '14/09/2026',
    Funcionário: 'João da Silva',
    Entrada: '08:00',
    Pausa: '12:00',
    Retorno: '13:00',
    Saída: '17:00',
    Observação: '',
    Telefone: '11999999999',
    ...overrides,
  };
}

test('agrupa várias linhas em uma mensagem por funcionário e ordena por data', async () => {
  const result = await runCodeNode(
    'Normalizar, agrupar e montar mensagens',
    [
      row({ Data: '21/09/2026', Pausa: '', Retorno: '', Saída: '' }),
      row({ Data: '14/09/2026', Entrada: '' }),
      row({ Data: '16/09/2026', Entrada: '', Pausa: '', Retorno: '' }),
    ],
    { TEST_MODE: 'true', TEST_PHONE: '5519888888888' },
  );

  assert.equal(result.length, 1);
  assert.equal(result[0].json.quantidadePendencias, 3);
  assert.match(
    result[0].json.mensagem,
    /• 14\/09\/2026 — ausência de marcação de entrada[\s\S]*• 16\/09\/2026 — ausência de marcação de entrada, pausa e retorno[\s\S]*• 21\/09\/2026 — ausência de marcação de pausa, retorno e saída/,
  );
});

test('identifica uma única saída ausente', async () => {
  const result = await runCodeNode(
    'Normalizar, agrupar e montar mensagens',
    [row({ Saída: '' })],
    { TEST_MODE: 'true', TEST_PHONE: '5519888888888' },
  );

  assert.match(result[0].json.mensagem, /ausência de marcação de saída/);
});

test('combina pausa e retorno ausentes', async () => {
  const result = await runCodeNode(
    'Normalizar, agrupar e montar mensagens',
    [row({ Pausa: '', Retorno: '' })],
    { TEST_MODE: 'true', TEST_PHONE: '5519888888888' },
  );

  assert.match(result[0].json.mensagem, /ausência de marcação de pausa e retorno/);
});

test('usa a observação quando todas as marcações estão preenchidas', async () => {
  const result = await runCodeNode(
    'Normalizar, agrupar e montar mensagens',
    [row({ Observação: 'Ordem dos pontos possui erros' })],
    { TEST_MODE: 'true', TEST_PHONE: '5519888888888' },
  );

  assert.match(result[0].json.mensagem, /Ordem dos pontos possui erros/);
});

test('normaliza telefone com máscara e adiciona DDI 55', async () => {
  const result = await runCodeNode(
    'Normalizar, agrupar e montar mensagens',
    [row({ Telefone: '(11) 99999-9999' })],
    { TEST_MODE: 'false', TEST_PHONE: '5519888888888' },
  );

  assert.equal(result[0].json.telefonePlanilha, '5511999999999');
  assert.equal(result[0].json.telefoneDestino, '5511999999999');
  assert.equal(result[0].json.podeEnviar, true);
});

test('rejeita telefone inválido e fórmula da planilha em produção', async () => {
  const invalid = await runCodeNode(
    'Normalizar, agrupar e montar mensagens',
    [row({ Telefone: '123' })],
    { TEST_MODE: 'false', TEST_PHONE: '5519888888888' },
  );
  const formula = await runCodeNode(
    'Normalizar, agrupar e montar mensagens',
    [row({ Telefone: '=VLOOKUP(A2;telefones.xlsx!A:B;2;FALSE)' })],
    { TEST_MODE: 'false', TEST_PHONE: '5519888888888' },
  );

  assert.equal(invalid[0].json.podeEnviar, false);
  assert.equal(formula[0].json.podeEnviar, false);
  assert.equal(formula[0].json.telefonePlanilha, '');
});

test('TEST_MODE redireciona tecnicamente todos os itens e ignora fórmulas', async () => {
  const testPhone = '5519888888888';
  const result = await runCodeNode(
    'Normalizar, agrupar e montar mensagens',
    [
      row({ Funcionário: 'João', Telefone: '11999999999' }),
      row({ Funcionário: 'Maria', Telefone: '(21) 98888-7777' }),
      row({ Funcionário: 'Carlos', Telefone: '=VLOOKUP(A2;X;2;FALSE)' }),
    ],
    { TEST_MODE: 'true', TEST_PHONE: testPhone },
  );

  assert.equal(result.length, 3);
  assert.deepEqual(
    Array.from(result, (item) => item.json.telefoneDestino),
    [testPhone, testPhone, testPhone],
  );
  assert.ok(result.every((item) => item.json.modoTeste === true));
});

test('segunda barreira bloqueia item adulterado no modo de teste', async () => {
  const [prepared] = await runCodeNode(
    'Normalizar, agrupar e montar mensagens',
    [row()],
    { TEST_MODE: 'true', TEST_PHONE: '5519888888888' },
  );
  prepared.json.telefoneDestino = '5511999999999';

  const guarded = await runCodeNode(
    'Segunda validação de segurança',
    [prepared.json],
    { TEST_MODE: 'true', TEST_PHONE: '5519888888888' },
  );

  assert.equal(guarded[0].json.podeEnviarSeguro, false);
  assert.equal(guarded[0].json.status, 'bloqueado_seguranca');
  assert.match(guarded[0].json.erro, /TEST_PHONE/);
});

test('workflow só alcança o HTTP após a segunda barreira e usa o contrato v2.3.7', () => {
  const workflow = loadWorkflow();
  const http = getNode('Enviar via Evolution API');
  const note = getNode('MODO DE TESTE ATIVO');

  assert.equal(
    http.parameters.url,
    "={{ $env.EVOLUTION_URL + '/message/sendText/' + $env.EVOLUTION_INSTANCE }}",
  );
  assert.match(http.parameters.body, /number:\s*\$json\.telefoneDestino/);
  assert.match(http.parameters.body, /text:\s*\$json\.mensagem/);
  assert.doesNotMatch(http.parameters.body, /telefoneOriginal/);
  assert.match(note.parameters.content, /MODO DE TESTE ATIVO — TODAS AS MENSAGENS SERÃO REDIRECIONADAS/);

  const incoming = Object.entries(workflow.connections)
    .flatMap(([source, outputs]) =>
      outputs.main.flatMap((connections) =>
        connections.filter((edge) => edge.node === 'Enviar via Evolution API').map(() => source),
      ),
    );
  assert.deepEqual(incoming, ['Destino passou na barreira?']);
});
