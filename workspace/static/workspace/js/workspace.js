/* Paleta de busca do iConnect Workspace.
 *
 * Sem inline: a CSP de produção não tem `unsafe-inline`. Sem framework: ~120
 * linhas resolvem, e trocar depois é mais barato do que instalar um build agora.
 *
 * O servidor devolve HTML pronto (`/workspace/buscar/`), então aqui não há
 * montagem de string com dado do usuário — nenhuma superfície de XSS.
 *
 * O modal é um `<dialog>`. O navegador entrega Esc, foco preso e fundo inerte;
 * reimplementar isso em JS é a origem mais comum de armadilha de foco.
 */
(function () {
  'use strict';

  var paleta = document.getElementById('paleta');
  var campo = document.getElementById('busca');
  var painel = document.getElementById('busca-resultados');
  if (!paleta || !campo || !painel) return;

  var url = painel.dataset.url;
  var atraso = 200;
  var timer = null;
  var requisicao = null;
  var ultimaConsulta = '';

  function abrirPaleta() {
    if (paleta.open) return;
    // `showModal` e não `show`: só o modal traz o fundo inerte e o Esc nativo.
    paleta.showModal();
    campo.focus();
    campo.select();
  }

  function fecharPaleta() {
    if (paleta.open) paleta.close();
  }

  function abrirPainel() {
    painel.hidden = false;
    campo.setAttribute('aria-expanded', 'true');
  }

  function fecharPainel() {
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
        abrirPainel();
      })
      .catch(function (e) {
        if (e.name !== 'AbortError') fecharPainel();
      });
  }

  // ── Abrir e fechar ──────────────────────────────────────────────

  document.addEventListener('click', function (e) {
    var gatilho = e.target.closest('[data-abre-busca]');
    if (gatilho) {
      e.preventDefault();
      abrirPaleta();
      return;
    }
    if (e.target.closest('[data-fecha-busca]')) {
      fecharPaleta();
      return;
    }
    // Clique no fundo escuro: o alvo é o próprio <dialog>, porque o conteúdo
    // está em filhos. É o jeito de detectar "clicou fora" sem overlay extra.
    if (paleta.open && e.target === paleta) fecharPaleta();
  });

  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (paleta.open) fecharPaleta();
      else abrirPaleta();
    }
  });

  /* Esc explícito, apesar de <dialog> fechar no Esc nativamente.
   *
   * `<input type="search">` CONSOME o Escape no Chrome para limpar o próprio
   * valor, então o evento nunca sobe até o dialog: a primeira tecla limpava o
   * campo e a paleta ficava aberta. Medido no browser, não deduzido.
   *
   * Trocar por `type="text"` resolveria o Esc e perderia o teclado de busca no
   * celular e a semântica para leitor de tela. Interceptar aqui custa três
   * linhas e mantém as duas coisas. */
  paleta.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();
    fecharPaleta();
  });

  // Limpa ao fechar. Reabrir com o resultado velho na tela faz a pessoa clicar
  // num item que ela buscou dez minutos antes.
  paleta.addEventListener('close', function () {
    if (requisicao) requisicao.abort();
    clearTimeout(timer);
    campo.value = '';
    ultimaConsulta = '';
    painel.innerHTML = '';
    fecharPainel();
  });

  // ── Digitação ───────────────────────────────────────────────────

  campo.addEventListener('input', function () {
    var termo = campo.value.trim();
    if (termo === ultimaConsulta) return;
    ultimaConsulta = termo;

    clearTimeout(timer);
    if (termo.length < 2) {
      if (requisicao) requisicao.abort();
      fecharPainel();
      return;
    }
    timer = setTimeout(function () {
      buscar(termo);
    }, atraso);
  });

  // ── Teclado nos resultados ──────────────────────────────────────

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
})();

/* Compras do reembolso — uma linha por comprovante.
 *
 * Sem inline, como o resto: a CSP não tem `unsafe-inline`. O HTML da linha vem
 * de um `<template>` no próprio documento, e a única coisa que este arquivo
 * monta é o índice — nenhum dado do usuário vira HTML aqui.
 *
 * A página funciona sem este arquivo: o servidor já manda uma linha pronta e
 * lê a lista de índices do POST. Sem JS a pessoa envia uma compra por vez, que
 * é pior, mas não é uma tela quebrada.
 */
(function () {
  'use strict';

  var caixa = document.querySelector('[data-despesas]');
  if (!caixa) return;

  var lista = caixa.querySelector('[data-despesa-lista]');
  var modelo = caixa.querySelector('[data-despesa-modelo]');
  var botao = caixa.querySelector('[data-despesa-adicionar]');
  var total = caixa.querySelector('[data-despesa-total]');
  var totalValor = caixa.querySelector('[data-despesa-total-valor]');
  if (!lista || !modelo || !botao) return;

  var maximo = parseInt(caixa.dataset.maximo, 10) || 20;

  // Contador próprio, e não `lista.children.length`: remover a linha 2 e
  // adicionar outra reusaria o índice 2, e dois `<input name="despesa_valor_2">`
  // no mesmo formulário fazem o servidor ler o valor de uma compra com o
  // comprovante da outra.
  var proximo = lista.querySelectorAll('[data-despesa]').length;

  function moeda(numero) {
    return 'R$ ' + numero.toFixed(2).replace('.', ',');
  }

  function somar() {
    if (!total || !totalValor) return;
    var campos = lista.querySelectorAll('[data-despesa-valor]');
    var soma = 0;
    var algum = false;
    Array.prototype.forEach.call(campos, function (campo) {
      var bruto = (campo.value || '').trim();
      if (!bruto) return;
      // Mesma leitura do servidor: ponto é milhar, vírgula é decimal.
      var numero = parseFloat(bruto.replace(/\./g, '').replace(',', '.'));
      if (isNaN(numero)) return;
      algum = true;
      soma += numero;
    });
    total.hidden = !algum;
    totalValor.textContent = moeda(soma);
  }

  function atualizarBotao() {
    var quantas = lista.querySelectorAll('[data-despesa]').length;
    botao.disabled = quantas >= maximo;
  }

  botao.addEventListener('click', function () {
    if (lista.querySelectorAll('[data-despesa]').length >= maximo) return;

    var indice = proximo++;
    var html = modelo.innerHTML.replace(/__i__/g, String(indice));
    var caixaTemp = document.createElement('div');
    caixaTemp.innerHTML = html;
    var linha = caixaTemp.querySelector('[data-despesa]');
    if (!linha) return;

    lista.appendChild(linha);
    atualizarBotao();
    // Foco no campo novo: sem isso a pessoa clica em "adicionar" e continua
    // digitando no fim da lista anterior.
    var primeiro = linha.querySelector('input[type="text"]');
    if (primeiro) primeiro.focus();
  });

  lista.addEventListener('click', function (e) {
    var remover = e.target.closest('[data-despesa-remover]');
    if (!remover) return;
    var linhas = lista.querySelectorAll('[data-despesa]');
    // A última não é removida: um reembolso sem nenhuma linha não tem o que
    // enviar, e a tela ficaria sem nenhum campo à vista.
    if (linhas.length <= 1) return;
    var linha = remover.closest('[data-despesa]');
    if (linha) linha.remove();
    atualizarBotao();
    somar();
  });

  lista.addEventListener('input', function (e) {
    if (e.target.matches('[data-despesa-valor]')) somar();
  });

  atualizarBotao();
  somar();
})();
