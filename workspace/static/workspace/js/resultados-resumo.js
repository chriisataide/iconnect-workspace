(function () {
  'use strict';
  document.addEventListener('click', function (event) {
    var link = event.target.closest('[data-concentrar]');
    var painel = document.getElementById('nova-concentracao');
    if (!link || !painel || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    painel.open = true;
    document.getElementById('c-tipo').value = 'indicador';
    document.getElementById('c-ref').value = link.dataset.referencia;
    document.getElementById('c-alerta').value = link.dataset.chave;
    document.getElementById('c-titulo').value = link.dataset.titulo;
    document.getElementById('c-motivo').value = link.dataset.motivo;
    document.getElementById('c-passo').value = '';
    document.getElementById('c-passo').focus({preventScroll: true});
  });
}());
