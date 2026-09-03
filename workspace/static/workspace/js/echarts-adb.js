/* Inicialização dos gráficos do Workspace.
 *
 * ## O que este arquivo NÃO faz
 *
 * Ele não soma, não converte e não formata. A `option` inteira vem pronta do
 * servidor, num `<script type="application/json">`, inclusive os rótulos em
 * pt-BR — o ECharts resolve `{@dimensao}` contra o próprio dado.
 *
 * Se o gráfico mostrar um número diferente da tabela ao lado, há UM lugar para
 * procurar, e ele é Python.
 *
 * ## A tabela irmã fecha AQUI
 *
 * O HTML manda `<details open>`. Quem não tem JavaScript vê a grade, que é o
 * conteúdo de verdade quando o gráfico não existe. Este arquivo fecha o
 * `<details>` depois de desenhar — o caminho inverso esconderia a tabela
 * justamente de quem não pode abri-la.
 *
 * ## Tema
 *
 * As cores vêm da `option`, montada em Python a partir dos tokens do produto.
 * Não há tema registrado aqui: um segundo lugar com cor é um segundo lugar para
 * a paleta divergir.
 */
(function () {
  "use strict";

  if (typeof EChartsADB === "undefined") {
    // O bundle não carregou. A tabela irmã continua aberta, que é o
    // comportamento certo — e nada quebra.
    return;
  }

  var instancias = new Map();

  function opcaoDe(chave) {
    var bloco = document.getElementById("grafico-dados-" + chave);
    if (!bloco) return null;
    try {
      return JSON.parse(bloco.textContent);
    } catch (erro) {
      // JSON quebrado é defeito do servidor. Falhar aqui em silêncio deixaria
      // um retângulo branco; falhar barulhento manda alguém olhar.
      console.error("Gráfico " + chave + ": dados ilegíveis.", erro);
      return null;
    }
  }

  function desenhar(tela) {
    var chave = tela.dataset.graficoTela;
    var opcao = opcaoDe(chave);
    if (!opcao) return;

    // A altura vem de atributo e é aplicada aqui. Em `style=` no template ela
    // seria bloqueada pelo lint do repositório — o que a biblioteca escreve é
    // aceito, o que nós escrevemos, não (ADR-040).
    tela.style.height = (tela.dataset.altura || 260) + "px";

    var grafico = EChartsADB.init(tela, null, { renderer: "svg" });
    grafico.setOption(opcao);
    instancias.set(chave, grafico);

    // A PERFURAÇÃO. O clique navega para uma URL que o SERVIDOR montou e
    // mandou como dimensão do `dataset` — este arquivo não sabe qual filtro
    // pertence a qual nível, e não precisa saber.
    //
    // Montar a URL aqui exigiria replicar a hierarquia em JavaScript, e ela
    // mudaria de lugar sozinha na primeira dimensão nova.
    if (tela.dataset.perfura) {
      grafico.on("click", function (params) {
        var destino = params && params.data && params.data[3];
        if (typeof destino === "string" && destino.charAt(0) === "/") {
          // Só caminho relativo deste produto. Uma URL absoluta vinda de dado
          // seria um redirecionamento aberto com passos extras.
          window.location.assign(destino);
        }
      });
    }

    // A tabela vira o "ver os números", e não mais o conteúdo principal.
    // `data-manter-aberta` é o bloco em que a grade É o conteúdo e o gráfico é
    // o resumo — ali fechar esconderia o principal.
    var tabela = document.querySelector('[data-grafico-tabela="' + chave + '"]');
    if (tabela && !tabela.dataset.manterAberta) tabela.open = false;
  }

  function redimensionar() {
    instancias.forEach(function (grafico) {
      grafico.resize();
    });
  }

  function iniciar() {
    document.querySelectorAll("[data-grafico-tela]").forEach(desenhar);
    if (instancias.size === 0) return;

    if (typeof ResizeObserver !== "undefined") {
      // Observa o CONTÊINER e não a janela: o gráfico também muda de largura
      // quando o trilho recolhe, e `window.resize` não dispara nisso.
      var observador = new ResizeObserver(redimensionar);
      document.querySelectorAll("[data-grafico-tela]").forEach(function (tela) {
        observador.observe(tela);
      });
    } else {
      window.addEventListener("resize", redimensionar);
    }

    // Antes de imprimir: o navegador reduz a largura da página, e um SVG
    // desenhado para 900px sai cortado no papel.
    if (window.matchMedia) {
      window.matchMedia("print").addEventListener("change", redimensionar);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
