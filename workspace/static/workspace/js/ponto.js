/* ─────────────────────────────────────────────────────────────────────
 * O ACOMPANHAMENTO DO ENVIO.
 *
 * Enquanto o lote roda, a tela pergunta ao Portal como vai — §26 e §27. É
 * polling simples, e é de propósito: SSE e WebSocket pedem processo que fica
 * de pé, e este projeto é Django com Gunicorn síncrono. Um `fetch` a cada três
 * segundos resolve um disparo que dura menos de um minuto, e o dia em que
 * durar mais é o dia de trocar o mecanismo — não antes.
 *
 * ## Sem JavaScript
 *
 * A página já vem renderizada com os números do servidor. Sem este arquivo o
 * acompanhamento não se atualiza sozinho e o F5 mostra o estado atual, que é
 * exatamente o que se fazia antes de existir tela nenhuma.
 *
 * ## Por que para sozinho
 *
 * O `terminou` vem do servidor. Um contador que continua batendo num lote
 * concluído é requisição a cada três segundos para sempre, em toda aba que
 * alguém esqueceu aberta.
 */
(function () {
  'use strict';

  var painel = document.querySelector('[data-ponto-progresso]');
  if (!painel) return;

  var url = painel.getAttribute('data-ponto-progresso');
  if (!url) return;

  /* O estado no momento em que a pagina abriu. Se ja estava pronto, nao ha
     transicao para observar e nao ha por que recarregar. */
  var jaTerminou = painel.getAttribute('data-ponto-terminou') === '1';

  var INTERVALO = 3000;
  var MAXIMO = 200;          // ~10 minutos, e então desiste em vez de insistir
  var tentativas = 0;

  function escrever(seletor, valor) {
    var alvo = painel.querySelector(seletor);
    if (alvo) alvo.textContent = String(valor);
  }

  function aplicar(estado) {
    escrever('[data-ponto-contagem]', estado.enviados + '/' + estado.total);
    escrever('[data-ponto-enviadas]', estado.enviados);
    escrever('[data-ponto-falhas]', estado.falhas);
    escrever('[data-ponto-restantes]', estado.restantes);
  }

  function perguntar() {
    if (++tentativas > MAXIMO) return;

    fetch(url, { headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin' })
      .then(function (resposta) {
        if (!resposta.ok) throw new Error('HTTP ' + resposta.status);
        return resposta.json();
      })
      .then(function (estado) {
        aplicar(estado);
        if (estado.terminou) {
          /* Recarrega UMA vez, e so se o lote terminou enquanto a pessoa
             olhava. Sem o `jaTerminou`, abrir um lote ja concluido entrava em
             recarga infinita: perguntar, ver `terminou`, recarregar, repetir.
             O template tambem nao emite mais o gancho nesse caso; as duas
             guardas existem porque uma recarga em laco apaga o que a pessoa
             esta digitando, e isso nao pode depender de um `if` so. */
          if (!jaTerminou) window.location.reload();
          return;
        }
        window.setTimeout(perguntar, INTERVALO);
      })
      .catch(function () {
        /* Rede instável não é motivo para parar: o lote continua rodando no
           servidor, e a próxima tentativa pode alcançá-lo. */
        window.setTimeout(perguntar, INTERVALO * 2);
      });
  }

  window.setTimeout(perguntar, INTERVALO);
})();

/* ─────────────────────────────────────────────────────────────────────
 * ARRASTAR A PLANILHA.
 *
 * O `<label>` já abre o seletor sozinho — isso é HTML, não precisa de script.
 * O que só existe aqui é o realce enquanto o arquivo paira e o nome depois de
 * escolhido.
 *
 * ## O `preventDefault` no documento inteiro
 *
 * Sem ele, soltar a planilha fora da área faz o navegador ABRIR o arquivo e
 * sair da página. Quem está importando erra a mira com frequência — a área é
 * um retângulo no meio de uma tela cheia —, e perder o que estava na tela por
 * causa de dois centímetros é o defeito que mais irrita.
 */
(function () {
  'use strict';

  var area = document.querySelector('[data-ponto-solta]');
  if (!area) return;

  var input = area.querySelector('input[type="file"]');
  var nome = area.querySelector('[data-ponto-nome]');
  if (!input) return;

  /* Soltar em qualquer lugar que não seja a área não pode navegar. */
  ['dragover', 'drop'].forEach(function (evento) {
    document.addEventListener(evento, function (e) {
      if (!area.contains(e.target)) e.preventDefault();
    });
  });

  function realcar(ligado) {
    area.classList.toggle('au-ponto-solta--ativa', ligado);
  }

  area.addEventListener('dragenter', function (e) { e.preventDefault(); realcar(true); });
  area.addEventListener('dragover', function (e) { e.preventDefault(); realcar(true); });
  area.addEventListener('dragleave', function (e) {
    /* `dragleave` dispara ao passar por cima dos filhos. Só apaga o realce
       quando o ponteiro saiu da área de verdade. */
    if (!area.contains(e.relatedTarget)) realcar(false);
  });

  area.addEventListener('drop', function (e) {
    e.preventDefault();
    realcar(false);
    var arquivos = e.dataTransfer && e.dataTransfer.files;
    if (!arquivos || !arquivos.length) return;

    /* `DataTransfer` direto no input: é o que faz o arquivo solto virar o
       arquivo do formulário, sem upload por fetch e sem segunda rota. */
    try {
      var caixa = new DataTransfer();
      caixa.items.add(arquivos[0]);
      input.files = caixa.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (erro) {
      /* Navegador sem DataTransfer construível: o clique continua servindo. */
    }
  });

  input.addEventListener('change', function () {
    if (!nome) return;
    nome.textContent = input.files && input.files.length ? input.files[0].name : '';
  });
})();
