const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const script = fs.readFileSync(path.join(__dirname, '../../workspace/static/workspace/js/echarts-adb.js'), 'utf8');

function render(option, fonts) {
  const options = [];
  const tela = { dataset: { graficoTela: 'teste' }, style: {} };
  const tabela = { dataset: {}, open: true };
  vm.runInNewContext(script, {
    document: {
      readyState: 'complete', fonts,
      getElementById: () => ({ textContent: JSON.stringify(option) }),
      querySelector: () => tabela,
      querySelectorAll: selector => selector === '[data-grafico-tela]' ? [tela] : [],
    },
    window: { addEventListener() {}, getComputedStyle: () => ({ fontFamily: 'Inter, sans-serif' }) },
    EChartsADB: { init: () => ({ setOption: value => options.push(value), resize() {} }) },
  });
  return { options, tabela };
}

test('usa a fonte real da página para medir e desenhar as legendas', () => {
  const { options } = render({ textStyle: { fontFamily: 'inherit' }, legend: { bottom: 0 } });
  assert.equal(options[0].textStyle.fontFamily, 'Inter, sans-serif');
  assert.equal(options[0].legend.textStyle.fontFamily, 'Inter, sans-serif');
});

test('legendas horizontais têm espaço e navegação quando não cabem', () => {
  const { options } = render({ legend: { bottom: 0 }, grid: { bottom: 30 } });
  assert.equal(options[0].legend.type, 'scroll');
  assert.ok(options[0].legend.itemGap >= 20);
  assert.ok(options[0].legend.itemWidth <= 16);
  assert.ok(options[0].grid.bottom >= 40);
});

test('preserva legendas ocultas e gráficos sem legenda', () => {
  assert.deepEqual(JSON.parse(JSON.stringify(render({ legend: { show: false } }).options[0].legend)), { show: false });
  assert.equal(render({ series: [] }).options[0].legend, undefined);
});

test('aguarda o carregamento da fonte antes de medir o gráfico', async () => {
  let finish;
  const ready = new Promise(resolve => { finish = resolve; });
  const { options, tabela } = render({ legend: {} }, { status: 'loading', ready });
  assert.equal(options.length, 0);
  assert.equal(tabela.open, true);
  finish();
  await ready;
  assert.equal(options.length, 1);
  assert.equal(tabela.open, false);
});
