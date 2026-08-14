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

  var atraso = 200;

  function prepararBusca(campoBusca, painelBusca) {
    var url = painelBusca.dataset.url;
    var timer = null;
    var requisicao = null;
    var ultimaConsulta = '';

    function abrirPainel() {
      painelBusca.hidden = false;
      campoBusca.setAttribute('aria-expanded', 'true');
    }

    function fecharPainel() {
      painelBusca.hidden = true;
      campoBusca.setAttribute('aria-expanded', 'false');
    }

    function limparBusca() {
      if (requisicao) requisicao.abort();
      clearTimeout(timer);
      campoBusca.value = '';
      ultimaConsulta = '';
      painelBusca.innerHTML = '';
      fecharPainel();
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
          painelBusca.innerHTML = html;
          abrirPainel();
        })
        .catch(function (e) {
          if (e.name !== 'AbortError') fecharPainel();
        });
    }

    campoBusca.addEventListener('input', function () {
      var termo = campoBusca.value.trim();
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

    campoBusca.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        if (campoBusca === campo) {
          e.preventDefault();
          e.stopPropagation();
          fecharPaleta();
          return;
        }
        if (painelBusca.hidden && !campoBusca.value) return;
        e.preventDefault();
        e.stopPropagation();
        limparBusca();
        return;
      }

      if (e.key !== 'ArrowDown' || painelBusca.hidden) return;
      var primeiro = painelBusca.querySelector('a');
      if (primeiro) {
        e.preventDefault();
        primeiro.focus();
      }
    });

    painelBusca.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      var itens = Array.prototype.slice.call(painelBusca.querySelectorAll('a'));
      var i = itens.indexOf(document.activeElement);
      if (i === -1) return;
      e.preventDefault();
      var proximo = e.key === 'ArrowDown' ? itens[i + 1] : itens[i - 1] || campoBusca;
      if (proximo) proximo.focus();
    });

    return {
      fecharPainel: fecharPainel,
      limpar: limparBusca,
      abortar: function () {
        if (requisicao) requisicao.abort();
        clearTimeout(timer);
      },
    };
  }

  // UM campo de busca em toda a aplicação, e ele mora na paleta. A home já teve
  // um campo próprio duas vezes: na primeira o ⌘K só funcionava lá, porque o
  // atalho procurava um `#busca` que só ela tinha; na segunda, dois campos na
  // mesma tela faziam a pessoa hesitar sobre se buscavam a mesma coisa.
  var buscaPaleta = prepararBusca(campo, painel);

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
    buscaPaleta.limpar();
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

/* Stepper e ramos do formulário de pedido.
 *
 * Sem inline, como o resto — a CSP não tem `unsafe-inline`.
 *
 * A divisão em passos é do NAVEGADOR: uma requisição só, um POST só. Wizard com
 * estado no servidor entre telas exigiria guardar arquivo enviado pela metade,
 * e o formulário que mais anexa é justamente o de prestação de contas.
 *
 * Sem este arquivo a página continua funcionando: todos os passos e todos os
 * ramos ficam visíveis, e o servidor descarta o que não é do ramo escolhido.
 * Por isso nada aqui esconde nada antes de ter certeza de que vai conseguir
 * mostrar de volta.
 */
(function () {
  'use strict';

  var form = document.querySelector('[data-stepper]');
  if (!form) return;

  var ultimo = parseInt(form.dataset.ultimo, 10) || 1;
  var enviar = form.querySelector('[data-enviar]');
  var seguir = form.querySelector('[data-passo-seguir]');
  var voltar = form.querySelector('[data-passo-voltar]');
  var trilha = form.querySelector('[data-trilha]');
  if (!seguir || !voltar) return;

  var atual = 1;

  function respostas() {
    // O estado do ramo é o que está NOS CAMPOS, não uma variável paralela:
    // duas fontes de verdade divergem no primeiro botão "voltar".
    var mapa = {};
    Array.prototype.forEach.call(form.elements, function (campo) {
      if (campo.name && campo.type !== 'file') mapa[campo.name] = campo.value;
    });
    return mapa;
  }

  function noRamo(bloco, mapa) {
    var chave = bloco.dataset.quandoCampo;
    if (!chave) return true;
    var aceitos = (bloco.dataset.quandoIgual || '').split('|');
    return aceitos.indexOf(mapa[chave]) !== -1;
  }

  function blocos() {
    return form.querySelectorAll('[data-passo]');
  }

  function desenhar() {
    var mapa = respostas();

    Array.prototype.forEach.call(blocos(), function (bloco) {
      var doPasso = parseInt(bloco.dataset.passo, 10) === atual;
      var doRamo = noRamo(bloco, mapa);
      // Dois modos para o campo fora do ramo. `sumir` é o padrão — quatro
      // campos do cenário que a pessoa não escolheu são ruído. `cinza` é para
      // o campo que É a consequência da escolha ao lado: ver "até quando"
      // apagado ensina o que "definitivo" significa, e a tela não pula.
      var cinza = bloco.dataset.quandoModo === 'cinza';

      bloco.hidden = !doPasso || (!doRamo && !cinza);
      bloco.classList.toggle('au-campo--inativo', !doRamo && cinza);

      // `disabled` sempre que está fora do ramo: campo escondido continua
      // sendo enviado, e um `required` invisível trava o envio sem mostrar
      // onde. Desabilitado, o navegador nem manda — e o servidor descarta o
      // que sobrar, de qualquer jeito.
      Array.prototype.forEach.call(bloco.querySelectorAll('input, select, textarea'),
        function (campo) { campo.disabled = !doRamo; });
    });

    if (trilha) {
      Array.prototype.forEach.call(trilha.querySelectorAll('[data-trilha-passo]'),
        function (item) {
          var numero = parseInt(item.dataset.trilhaPasso, 10);
          // Passo sem conteúdo some da trilha — mas o `apos_envio` fica: ele
          // acontece em outra tela e não tem bloco nenhum aqui, e some-lo
          // esconderia justamente a etapa que a pessoa não pode esquecer.
          var doFormulario = numero <= ultimo;
          item.hidden = doFormulario && !temConteudo(numero);
          item.classList.toggle('au-trilha-passo--atual', numero === atual);
          item.classList.toggle('au-trilha-passo--feito', numero < atual);
          if (numero === atual) item.setAttribute('aria-current', 'step');
          else item.removeAttribute('aria-current');
        });
    }

    voltar.hidden = atual === 1;
    seguir.hidden = atual >= ultimo;
    // O enviar só no fim: um botão de enviar visível no passo 1 faz metade das
    // pessoas mandarem o formulário pela metade — e a outra metade descobrir os
    // passos seguintes pela mensagem de erro.
    if (enviar) enviar.hidden = atual < ultimo;
  }

  // Um passo pode ficar VAZIO por decisão do servidor: o passo do adiantamento
  // só existe para quem tem adiantamento pendente, e a seção inteira não é
  // renderizada quando não há nenhum. "Continuar" para uma tela em branco faz a
  // pessoa achar que a página quebrou — então o passo vazio é pulado, e some da
  // trilha.
  function temConteudo(numero) {
    return Array.prototype.some.call(blocos(), function (bloco) {
      return parseInt(bloco.dataset.passo, 10) === numero;
    });
  }

  function irPara(numero, direcao) {
    var destino = Math.min(Math.max(numero, 1), ultimo);
    var passo = direcao || (destino > atual ? 1 : -1);
    while (destino > 1 && destino < ultimo && !temConteudo(destino)) {
      destino += passo;
    }
    atual = Math.min(Math.max(destino, 1), ultimo);
    desenhar();
    form.scrollIntoView({ block: 'start' });
  }

  seguir.addEventListener('click', function () { irPara(atual + 1); });
  voltar.addEventListener('click', function () { irPara(atual - 1); });

  // Trocar o ramo muda o que existe no passo seguinte — e às vezes no atual.
  form.addEventListener('change', function (e) {
    if (e.target.matches('[data-ramo]')) desenhar();
  });

  // Voltou do servidor com erro? Abre no passo do primeiro campo com erro, em
  // vez de no passo 1: procurar o erro passo a passo é o que faz a pessoa
  // desistir no segundo envio.
  var comErro = form.querySelector('.au-campo--erro[data-passo]');
  if (comErro) atual = parseInt(comErro.dataset.passo, 10) || 1;

  desenhar();
})();

/* Formatação de valor enquanto se digita.
 *
 * Dinheiro em português tem ponto de milhar e vírgula decimal: `1.234,56`. A
 * pessoa digita só os números e o campo se encarrega do resto — porque a
 * alternativa é cada um digitar de um jeito, e a leitura do servidor ter de
 * adivinhar se `1.234` são mil duzentos e trinta e quatro ou um e vinte e três.
 * Essa adivinhação já causou um defeito real aqui: `1234.56` lido como cento e
 * vinte e três mil.
 *
 * O servidor continua sendo quem decide (`services/reembolso.valor_de`): isto é
 * conforto de digitação, não validação. Sem JS, o campo aceita os dois formatos
 * como sempre aceitou.
 *
 * Data e hora não precisam de máscara: `type="date"` e `type="time"` já trazem
 * o traço e os dois-pontos do próprio navegador, no formato local — e um
 * calendário de brinde.
 */
(function () {
  'use strict';

  var campos = document.querySelectorAll('[data-moeda]');
  if (!campos.length) return;

  function formatar(bruto) {
    var digitos = String(bruto).replace(/\D/g, '').replace(/^0+/, '');
    if (!digitos) return '';
    while (digitos.length < 3) digitos = '0' + digitos;

    var centavos = digitos.slice(-2);
    var inteiros = digitos.slice(0, -2);
    // Milhar de trás para frente: `1234567` → `1.234.567`.
    inteiros = inteiros.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return inteiros + ',' + centavos;
  }

  Array.prototype.forEach.call(campos, function (campo) {
    campo.addEventListener('input', function () {
      var antes = campo.value;
      var formatado = formatar(antes);
      if (formatado === antes) return;
      campo.value = formatado;
      // O cursor vai para o fim: a máscara reescreve o valor inteiro, e tentar
      // preservar a posição no meio de um número que muda de tamanho é como se
      // ganha o cursor pulando para trás a cada dígito.
      campo.setSelectionRange(formatado.length, formatado.length);
    });

    campo.addEventListener('blur', function () {
      if (campo.value) campo.value = formatar(campo.value);
    });
  });
})();

/* Resumo de um pedido, em modal.
 *
 * O conteúdo já vem pronto do servidor — este arquivo só abre e fecha. Nenhum
 * dado do usuário vira HTML aqui, então não há superfície de XSS.
 *
 * `<dialog>` de novo, pelo mesmo motivo da paleta: Esc, foco preso e fundo
 * inerte são do navegador. Sem JS, o modal simplesmente não abre e a tabela
 * continua mostrando tudo que ela já mostrava — o resumo é atalho, não a única
 * forma de ver o pedido.
 */
(function () {
  'use strict';

  if (!document.querySelector('[data-abre-resumo]')) return;

  function abrir(id) {
    var modal = document.getElementById(id);
    if (modal && typeof modal.showModal === 'function' && !modal.open) modal.showModal();
  }

  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-fecha-modal]')) {
      var aberto = e.target.closest('dialog');
      if (aberto) aberto.close();
      return;
    }

    // Clique no fundo escuro: o alvo é o próprio <dialog>, porque o conteúdo
    // está em filhos.
    if (e.target.matches('dialog.au-modal')) {
      e.target.close();
      return;
    }

    // A ação nunca rouba um clique que já tinha dono: dentro da linha existem
    // o link do anexo e o botão de cancelar, e abrir o resumo por cima deles
    // faria o cancelar virar roleta.
    if (e.target.closest('a, button:not([data-abre-resumo]), form')) return;

    var gatilho = e.target.closest('[data-abre-resumo]');
    if (gatilho) abrir(gatilho.dataset.abreResumo);
  });
})();
