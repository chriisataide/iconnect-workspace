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
          /* Terminou enquanto a pessoa olhava: recarrega uma vez para que o
             resto da tela — etapa, painel, botões — acompanhe o novo estado.
             Atualizar tudo por JavaScript seria manter uma segunda cópia da
             lógica que o template já tem. */
          window.location.reload();
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
