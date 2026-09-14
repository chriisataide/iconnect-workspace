/* Memória de leitura por aba. Os filtros e a expansão continuam na URL. */
(function () {
  'use strict';
  var pagina = document.querySelector('.au-resultados');
  if (!pagina) return;
  var chave = 'workspace:resultados:posicao';
  var navegando = false;

  function retrato(origem) {
    var ancora = origem && origem.closest('[data-posicao]');
    if (!ancora && origem) {
      var secao = origem.closest('.au-secao-faixa');
      if (secao) ancora = document.getElementById(secao.getAttribute('aria-labelledby'));
    }
    if (!ancora && window.scrollY > 0) {
      pagina.querySelectorAll('[data-posicao], .au-secao-titulo[id]').forEach(function (item) {
        if (!ancora || Math.abs(item.getBoundingClientRect().top) < Math.abs(ancora.getBoundingClientRect().top)) ancora = item;
      });
    }
    var tabela = document.getElementById('contabil-tabela');
    var abertas = {};
    pagina.querySelectorAll('[data-grafico-tabela]').forEach(function (item) {
      abertas[item.dataset.graficoTabela] = item.open;
    });
    return {
      x: window.scrollX, y: window.scrollY,
      ancora: ancora ? ancora.id : '',
      topo: ancora ? ancora.getBoundingClientRect().top : 0,
      focar: Boolean(origem && origem.closest('[data-posicao]')),
      tabelaX: tabela ? tabela.scrollLeft : 0,
      abertas: abertas
    };
  }

  function preparar(destino, origem) {
    var url = new URL(destino, location.href);
    if (url.origin !== location.origin || url.pathname !== location.pathname) return;
    if (url.searchParams.get('apresentacao') !== new URL(location.href).searchParams.get('apresentacao')) return;
    // Âncoras de navegação continuam levando à seção pedida.
    if (url.hash) return;
    try {
      sessionStorage.setItem(chave, JSON.stringify({
        destino: url.href, instante: Date.now(), posicao: retrato(origem)
      }));
      navegando = true;
    } catch (erro) { /* Armazenamento indisponível: a navegação nativa funciona. */ }
  }

  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    var link = event.target.closest('a[href]');
    if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
    if (!link.closest('.au-resultados, .au-tarjas')) return;
    preparar(link.href, link);
  });
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (event.defaultPrevented || !pagina.contains(form) || form.method.toLowerCase() !== 'get') return;
    var url = new URL(form.action || location.href, location.href);
    url.search = new URLSearchParams(new FormData(form)).toString();
    preparar(url.href, null);
  });
  document.addEventListener('resultados:navegar', function (event) {
    preparar(event.detail.destino, event.target);
  });

  var restaurar = null;
  try {
    var guardado = JSON.parse(sessionStorage.getItem(chave) || 'null');
    sessionStorage.removeItem(chave);
    if (guardado && guardado.destino === location.href && Date.now() - guardado.instante < 60000) restaurar = guardado.posicao;
  } catch (erro) { /* Não depende de armazenamento para renderizar. */ }
  var navegacao = performance.getEntriesByType('navigation')[0];
  if (!restaurar && navegacao && (navegacao.type === 'reload' || navegacao.type === 'back_forward')) {
    restaurar = history.state && history.state.resultadosPosicao;
  }

  function guardarHistorico() {
    try {
      history.replaceState(Object.assign({}, history.state, { resultadosPosicao: retrato(null) }), '');
    } catch (erro) { /* Histórico indisponível: mantém o comportamento nativo. */ }
  }
  window.addEventListener('pagehide', guardarHistorico);
  // No retorno pelo bfcache, pagehide pode chegar tarde para atualizar a entrada.
  // Captura também a rolagem horizontal dos contêineres, sem gravar a cada pixel.
  var quadroPendente = false;
  document.addEventListener('scroll', function () {
    if (quadroPendente) return;
    quadroPendente = true;
    requestAnimationFrame(function () {
      quadroPendente = false;
      guardarHistorico();
    });
  }, true);

  // Depois do load, os gráficos já fecharam suas tabelas alternativas.
  window.addEventListener('pageshow', function (event) {
    if (event.persisted) navegando = false;
    if (event.persisted || !restaurar) return;
    var posicao = restaurar;
    restaurar = null;
    pagina.querySelectorAll('[data-grafico-tabela]').forEach(function (item) {
      if (Object.hasOwn(posicao.abertas || {}, item.dataset.graficoTabela)) item.open = posicao.abertas[item.dataset.graficoTabela];
    });
    requestAnimationFrame(function () {
      if (navegando) return;
      var ancora = document.getElementById(posicao.ancora);
      var y = ancora ? window.scrollY + ancora.getBoundingClientRect().top - posicao.topo : posicao.y;
      window.scrollTo({ left: posicao.x, top: y, behavior: 'instant' });
      var tabela = document.getElementById('contabil-tabela');
      if (tabela) tabela.scrollLeft = posicao.tabelaX;
      if (ancora && posicao.focar) ancora.focus({ preventScroll: true });
    });
  });
}());
