/* Busca do Portal.
 *
 * Sem inline: a CSP de produção não tem `unsafe-inline`. Sem framework: o
 * HTMX/Alpine entram no ST-024 e este arquivo sai. Até lá, ~90 linhas de JS
 * resolvem, e trocar depois é mais barato do que instalar um build agora.
 *
 * O servidor devolve HTML pronto (`/workspace/buscar/`), então aqui não há
 * montagem de string com dado do usuário — nenhuma superfície de XSS.
 */
(function () {
  'use strict';

  var campo = document.getElementById('busca');
  var painel = document.getElementById('busca-resultados');
  if (!campo || !painel) return;

  var url = painel.dataset.url;
  var atraso = 200;
  var timer = null;
  var requisicao = null;
  var ultimaConsulta = '';

  function abrir() {
    painel.hidden = false;
    campo.setAttribute('aria-expanded', 'true');
  }

  function fechar() {
    painel.hidden = true;
    campo.setAttribute('aria-expanded', 'false');
  }

  function buscar(termo) {
    // AbortController evita a corrida clássica: uma resposta lenta de "fer"
    // chegando depois da de "ferias" e sobrescrevendo o resultado certo.
    if (requisicao) requisicao.abort();
    requisicao = new AbortController();

    fetch(url + '?q=' + encodeURIComponent(termo), {
      signal: requisicao.signal,
      headers: { 'X-Requested-With': 'fetch' },
    })
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      })
      .then(function (html) {
        painel.innerHTML = html;
        abrir();
      })
      .catch(function (e) {
        if (e.name !== 'AbortError') fechar();
      });
  }

  campo.addEventListener('input', function () {
    var termo = campo.value.trim();
    if (termo === ultimaConsulta) return;
    ultimaConsulta = termo;

    clearTimeout(timer);
    if (termo.length < 2) {
      if (requisicao) requisicao.abort();
      fechar();
      return;
    }
    timer = setTimeout(function () {
      buscar(termo);
    }, atraso);
  });

  campo.addEventListener('focus', function () {
    if (painel.innerHTML.trim() && campo.value.trim().length >= 2) abrir();
  });

  // ⌘K / Ctrl+K foca a busca de qualquer lugar da página.
  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      campo.focus();
      campo.select();
      return;
    }
    if (e.key === 'Escape' && !painel.hidden) {
      fechar();
      campo.focus();
    }
  });

  // Navegação por seta entre os resultados, sem tirar o foco do campo.
  campo.addEventListener('keydown', function (e) {
    if (e.key !== 'ArrowDown' || painel.hidden) return;
    var primeiro = painel.querySelector('a');
    if (primeiro) {
      e.preventDefault();
      primeiro.focus();
    }
  });

  painel.addEventListener('keydown', function (e) {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    var itens = Array.prototype.slice.call(painel.querySelectorAll('a'));
    var i = itens.indexOf(document.activeElement);
    if (i === -1) return;
    e.preventDefault();
    var proximo = e.key === 'ArrowDown' ? itens[i + 1] : itens[i - 1] || campo;
    if (proximo) proximo.focus();
  });

  document.addEventListener('click', function (e) {
    if (!painel.hidden && !painel.contains(e.target) && e.target !== campo) fechar();
  });
})();
