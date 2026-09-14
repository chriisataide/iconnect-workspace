const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../../workspace/static/workspace/js/resultados-posicao.js'), 'utf8');
const chave = 'workspace:resultados:posicao';
const base = 'https://workspace.test/workspace/resultados/';

function pagina({ storage = new Map(), href = base, tipo = 'navigate', state = null, bloqueado = false, ancoraExiste = true, tabelaX = 0 } = {}) {
  const eventos = {}, janela = {}, scrolls = [];
  const ancora = { id: 'conta-41101', getBoundingClientRect: () => ({ top: 360 }), focus: () => {} };
  const root = { querySelectorAll: () => ancoraExiste ? [ancora] : [], contains: () => true };
  // Os seletores de tabelas alternativas não devem devolver linhas contábeis.
  root.querySelectorAll = selector => selector === '[data-grafico-tabela]' ? [] : (ancoraExiste ? [ancora] : []);
  const tabela = { scrollLeft: tabelaX };
  const history = { state, replaceState(value) { this.state = value; } };
  const context = {
    URL, URLSearchParams, Object, JSON, Date,
    location: new URL(href), performance: { getEntriesByType: () => [{ type: tipo }] }, history,
    sessionStorage: {
      getItem(key) { if (bloqueado) throw Error('Bloqueado'); return storage.get(key) || null; },
      setItem(key, value) { if (bloqueado) throw Error('Bloqueado'); storage.set(key, value); },
      removeItem(key) { storage.delete(key); }
    },
    document: { querySelector: () => root, getElementById: id => id === 'contabil-tabela' ? tabela : (id === ancora.id && ancoraExiste ? ancora : null),
      addEventListener: (type, fn) => { eventos[type] = fn; } },
    window: { scrollX: 0, scrollY: 4000, scrollTo: value => scrolls.push(value), addEventListener: (type, fn) => { janela[type] = fn; } },
    requestAnimationFrame: fn => fn()
  };
  vm.runInNewContext(script, context);
  function clicar(href, campos = {}) {
    const link = { href, target: '', hasAttribute: () => false,
      closest: selector => selector === '[data-posicao]' ? ancora : (selector === '.au-secao-faixa' ? null : root) };
    eventos.click({ button: 0, target: { closest: () => link }, ...campos });
  }
  return { clicar, eventos, janela, history, scrolls, storage, tabela };
}

test('restaura a linha somente na navegação de filtro que foi solicitada', () => {
  const storage = new Map();
  pagina({ storage }).clicar(base + '?expandir=41101');
  const nova = pagina({ storage, href: base + '?expandir=41101' });
  nova.janela.pageshow({ persisted: false });
  assert.equal(nova.scrolls[0].top, 4000);
  assert.equal(storage.has(chave), false);
  nova.janela.pageshow({ persisted: false });
  assert.equal(nova.scrolls.length, 1, 'a restauração deve ser usada uma vez');
});

test('uma rota ou filtro diferente não recebe a posição pendente', () => {
  const storage = new Map();
  pagina({ storage }).clicar(base + '?expandir=41101');
  const outra = pagina({ storage, href: base + '?area=area-03' });
  outra.janela.pageshow({ persisted: false });
  assert.equal(outra.scrolls.length, 0);
});

test('cliques modificados, páginas diferentes e âncoras mantêm navegação nativa', () => {
  const p = pagina();
  p.clicar(base + '?area=area-03', { ctrlKey: true });
  p.clicar(base + '?area=area-03', { metaKey: true });
  p.clicar(base + '?area=area-03', { defaultPrevented: true });
  p.clicar('https://outro.test/workspace/resultados/');
  p.clicar(base + 'pdf/');
  p.clicar(base + '#contabil');
  p.clicar(base + '?apresentacao=1');
  assert.equal(p.storage.size, 0);
});

test('o gráfico pode preparar a mesma navegação sem um elemento de link', () => {
  const p = pagina();
  p.eventos['resultados:navegar']({ detail: { destino: base + '?cc=1042' }, target: { closest: () => null } });
  assert.equal(JSON.parse(p.storage.get(chave)).destino, base + '?cc=1042');
});

test('refresh usa o histórico da entrada atual e preserva outros campos', () => {
  const atual = pagina({ state: { outroComponente: true } });
  atual.janela.pagehide();
  assert.equal(atual.history.state.outroComponente, true);
  const nova = pagina({ tipo: 'reload', state: atual.history.state });
  nova.janela.pageshow({ persisted: false });
  assert.equal(nova.scrolls[0].top, 4000);
});

test('se a linha desaparecer, usa a posição absoluta disponível', () => {
  const atual = pagina();
  atual.janela.pagehide();
  const nova = pagina({ tipo: 'reload', state: atual.history.state, ancoraExiste: false });
  nova.janela.pageshow({ persisted: false });
  assert.equal(nova.scrolls[0].top, 4000);
});

test('armazenamento bloqueado e conteúdo inválido não impedem a página', () => {
  assert.doesNotThrow(() => pagina({ bloqueado: true }).clicar(base + '?area=a'));
  assert.doesNotThrow(() => pagina({ storage: new Map([[chave, '{invalido']]) }));
});

test('retorno pelo cache do navegador não reposiciona uma página já restaurada', () => {
  const atual = pagina();
  atual.janela.pagehide();
  const nova = pagina({ tipo: 'back_forward', state: atual.history.state });
  nova.janela.pageshow({ persisted: true });
  assert.equal(nova.scrolls.length, 0);
});

test('rolagem horizontal é salva antes de sair e restaurada após refresh', () => {
  const atual = pagina({ tabelaX: 300 });
  atual.eventos.scroll();
  const nova = pagina({ tipo: 'reload', state: atual.history.state });
  nova.janela.pageshow({ persisted: false });
  assert.equal(nova.tabela.scrollLeft, 300);
});
