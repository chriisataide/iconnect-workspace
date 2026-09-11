/* Menus nativos continuam funcionando sem JavaScript; aqui só há conveniências. */
(function () {
  'use strict';
  var menus = document.querySelectorAll('.au-filtro-multi');
  menus.forEach(function (menu) {
    var resumo = menu.querySelector('[data-resumo]');
    function atualizar() {
      var escolhas = Array.from(menu.querySelectorAll('input:checked'));
      resumo.textContent = escolhas.length
        ? escolhas.map(function (input) { return input.nextElementSibling.textContent; }).join(', ')
        : resumo.dataset.padrao;
    }
    atualizar();
    menu.addEventListener('change', atualizar);
    menu.addEventListener('toggle', function () {
      if (menu.open) menus.forEach(function (outro) { if (outro !== menu) outro.open = false; });
    });
    menu.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        menu.open = false;
        menu.querySelector('summary').focus();
      }
    });
  });
  document.addEventListener('click', function (event) {
    menus.forEach(function (menu) { if (!menu.contains(event.target)) menu.open = false; });
  });
}());
