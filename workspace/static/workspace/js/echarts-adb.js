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

  function ajustarLegendas(opcao, tela) {
    // O canvas que mede os textos não herda o CSS do SVG. Resolver "inherit"
    // antes do setOption mantém a medida e o desenho na mesma fonte.
    var fonte = window.getComputedStyle(tela).fontFamily || "sans-serif";
    opcao.textStyle = opcao.textStyle || {};
    if (!opcao.textStyle.fontFamily || opcao.textStyle.fontFamily === "inherit") {
      opcao.textStyle.fontFamily = fonte;
    }
    var legendas = opcao.legend ? [].concat(opcao.legend) : [];
    legendas.forEach(function (legenda) {
      if (legenda.show === false) return;
      legenda.textStyle = legenda.textStyle || {};
      if (!legenda.textStyle.fontFamily || legenda.textStyle.fontFamily === "inherit") {
        legenda.textStyle.fontFamily = opcao.textStyle.fontFamily;
      }
      if (legenda.orient === "vertical") return;
      legenda.type = "scroll";
      legenda.itemGap = Math.max(24, legenda.itemGap || 0);
      legenda.itemWidth = 14;
      legenda.itemHeight = 10;
      legenda.pageTextStyle = Object.assign({}, legenda.textStyle, legenda.pageTextStyle);
      if (legenda.bottom === 0 && opcao.grid) {
        [].concat(opcao.grid).forEach(function (grade) {
          if (typeof grade.bottom === "number") grade.bottom = Math.max(40, grade.bottom);
        });
      }
    });
  }

  function desenhar(tela) {
    var chave = tela.dataset.graficoTela;
    var opcao = opcaoDe(chave);
    if (!opcao) return;

    // A altura vem de atributo e é aplicada aqui. Em `style=` no template ela
    // seria bloqueada pelo lint do repositório — o que a biblioteca escreve é
    // aceito, o que nós escrevemos, não (ADR-040).
    tela.style.height = (tela.dataset.altura || 260) + "px";

    ajustarLegendas(opcao, tela);
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
          tela.dispatchEvent(new CustomEvent('resultados:navegar', {
            bubbles: true, detail: { destino: destino }
          }));
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
    limparCamposVazios();
    // Medir antes da fonte terminar de carregar deixa larguras em cache que
    // não correspondem ao texto final, mesmo depois de redimensionar o SVG.
    if (document.fonts && document.fonts.status === "loading") {
      document.fonts.ready.then(iniciarGraficos);
    } else {
      iniciarGraficos();
    }
  }

  function iniciarGraficos() {
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

  /* A barra de filtros manda TODO campo, inclusive os vazios — é o que o
   * navegador faz com um `<form method="get">`. O resultado é uma URL como
   * `?regional=&cc=&contrato=&servico=` que funciona e é feia de colar.
   *
   * A tela é para ser COMPARTILHADA numa mensagem, e uma URL com seis campos
   * vazios convida a pessoa a truncá-la antes de enviar. Este trecho tira os
   * vazios no envio.
   *
   * Sem JavaScript, a URL continua com eles — e continua correta. Por isso a
   * limpeza mora aqui e não numa view: ela é cosmética, e o que é cosmético não
   * pode virar requisito de funcionamento.
   */
  function limparCamposVazios() {
    document.querySelectorAll("form[data-limpar-vazios]").forEach(function (form) {
      form.addEventListener("submit", function () {
        form.querySelectorAll("input[name], select[name]").forEach(function (campo) {
          if (campo.type !== "checkbox" && campo.value === "") {
            campo.disabled = true;
          }
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
