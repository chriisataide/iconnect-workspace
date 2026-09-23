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
  var aviso = form.querySelector('[data-aviso-passo]');
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

  /* Os blocos que EXISTEM num passo, para as respostas de agora.
   *
   * "Existem" leva o ramo em conta, e é aí que estava o defeito que fazia os
   * passos parecerem iguais: o passo 2 do treinamento só tem campos de curso
   * interno OU de curso externo. Antes de responder "que tipo de curso", ele
   * não tem NADA — e o "Continuar" levava para uma tela em branco, que a
   * pessoa lia, com razão, como "não mudou nada". */
  function blocosDoPasso(numero, mapa) {
    return Array.prototype.filter.call(blocos(), function (bloco) {
      if (parseInt(bloco.dataset.passo, 10) !== numero) return false;
      // O bloco em modo cinza conta como conteúdo: ele aparece de qualquer
      // jeito, apagado.
      return noRamo(bloco, mapa) || bloco.dataset.quandoModo === 'cinza';
    });
  }

  function temConteudo(numero, mapa) {
    return blocosDoPasso(numero, mapa).length > 0;
  }

  /* O último passo que tem o que mostrar AGORA.
   *
   * Não é o `data-ultimo` do servidor: o passo do adiantamento só existe para
   * quem tem um pendente, e os passos de detalhe do curso só existem depois de
   * escolher o tipo. É este número que decide onde aparece o "Enviar" — senão
   * ele fica escondido atrás de um "Continuar" que leva a lugar nenhum. */
  function ultimoUtil(mapa) {
    for (var numero = ultimo; numero > 1; numero--) {
      if (temConteudo(numero, mapa)) return numero;
    }
    return 1;
  }

  /* O que impede de seguir: campo obrigatório do passo atual sem resposta.
   *
   * Sem isto dá para atravessar o formulário inteiro no "Continuar" e só
   * descobrir o que faltava na mensagem de erro do servidor — e, no caso do
   * treinamento, dá para chegar num passo vazio porque a pergunta que decide o
   * ramo ficou em branco. */
  function pendencias(mapa) {
    return blocosDoPasso(atual, mapa).filter(function (bloco) {
      if (!bloco.hasAttribute('data-obrigatorio')) return false;
      // A lista de compras tem regra própria (uma linha completa por compra) e
      // quem a valida é o servidor: exigir aqui duplicaria a regra.
      if (bloco.querySelector('[data-despesas]')) return false;
      var campos = bloco.querySelectorAll('input, select, textarea');
      return Array.prototype.some.call(campos, function (campo) {
        return !campo.disabled && campo.type !== 'file' && !String(campo.value).trim();
      });
    });
  }

  function desenhar() {
    var mapa = respostas();
    var fim = ultimoUtil(mapa);

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
          // Passo sem conteúdo some da trilha — mas o `apos_envio` fica: ele
          // acontece em outra tela e não tem bloco nenhum aqui, e some-lo
          // esconderia justamente a etapa que a pessoa não pode esquecer.
          var doFormulario = numero <= ultimo;
          item.hidden = doFormulario && !temConteudo(numero, mapa);
          item.classList.toggle('au-trilha-passo--atual', numero === atual);
          item.classList.toggle('au-trilha-passo--feito', numero < atual);
          if (numero === atual) item.setAttribute('aria-current', 'step');
          else item.removeAttribute('aria-current');
        });
    }

    voltar.hidden = atual === 1;
    seguir.hidden = atual >= fim;
    // O enviar só no fim: um botão de enviar visível no passo 1 faz metade das
    // pessoas mandarem o formulário pela metade — e a outra metade descobrir os
    // passos seguintes pela mensagem de erro. "Fim" é o último passo que tem o
    // que mostrar agora, e não o último declarado.
    if (enviar) enviar.hidden = atual < fim;
  }

  function irPara(numero, direcao) {
    var mapa = respostas();
    var fim = ultimoUtil(mapa);
    var destino = Math.min(Math.max(numero, 1), fim);
    var passo = direcao || (destino > atual ? 1 : -1);
    // Passo vazio é pulado em vez de mostrado em branco.
    while (destino > 1 && destino < fim && !temConteudo(destino, mapa)) {
      destino += passo;
    }
    atual = Math.min(Math.max(destino, 1), fim);
    if (aviso) aviso.hidden = true;
    desenhar();
    form.scrollIntoView({ block: 'start' });
  }

  seguir.addEventListener('click', function () {
    var mapa = respostas();
    var faltando = pendencias(mapa);

    if (faltando.length) {
      // Marca, avisa e leva o foco para o primeiro — em vez de avançar para um
      // passo que depende de uma resposta que não foi dada.
      faltando.forEach(function (bloco) { bloco.classList.add('au-campo--erro'); });
      if (aviso) aviso.hidden = false;
      var primeiro = faltando[0].querySelector('input, select, textarea');
      if (primeiro) primeiro.focus();
      return;
    }

    Array.prototype.forEach.call(blocos(), function (bloco) {
      bloco.classList.remove('au-campo--erro');
    });
    irPara(atual + 1);
  });

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

    var gatilho = e.target.closest('[data-abre-resumo]');
    if (!gatilho) return;

    // A ação nunca rouba um clique que já tinha dono: dentro da linha de
    // "Minhas solicitações" existem o link do anexo e o botão de cancelar, e
    // abrir o resumo por cima deles faria o cancelar virar roleta.
    //
    // O teste é "há um dono ENTRE o clique e o gatilho?", e não "há um dono em
    // algum lugar acima?". A versão anterior perguntava a segunda coisa e por
    // isso o botão "Ver o pedido" da bandeja de aprovação nunca abria nada: ele
    // vive dentro do <form> de aprovação em lote, `closest('form')` encontrava
    // esse formulário e a função voltava antes de olhar para o gatilho. O
    // gestor clicava, e a tela não fazia absolutamente nada.
    var dono = e.target.closest('a, button, form, input, select, textarea, label');
    if (dono && dono !== gatilho && gatilho.contains(dono)) return;

    abrir(gatilho.dataset.abreResumo);
  });

  // Enter e espaço na linha focada. Sem isto, `tabindex` só daria o foco e não
  // a ação — que é pior que não ter foco nenhum: a pessoa chega no elemento e
  // ele não responde.
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var linha = e.target.closest('[data-abre-resumo]');
    if (!linha || e.target.closest('a, button, input, select, textarea')) return;
    e.preventDefault();
    abrir(linha.dataset.abreResumo);
  });
})();

/* ── O ASSISTENTE (§3) ────────────────────────────────────────────────
 *
 * Progressive enhancement, e aqui isso não é purismo: sem este arquivo o
 * `<details>` continua abrindo e o formulário continua funcionando — ele faz
 * `GET` para `/workspace/ajuda/`, que responde a mesma coisa em página cheia.
 * O que o JS acrescenta é responder SEM sair da tela.
 *
 * Uma primeira camada de atendimento que só funciona com JS carregado falha
 * exatamente para quem está na rede ruim do canteiro de obra.
 */
(function () {
  'use strict';

  var painel = document.querySelector('.au-bot-form[data-assistente]');
  if (!painel) return;

  var saida = document.getElementById('bot-resposta');
  var campo = document.getElementById('bot-q');
  var endereco = painel.getAttribute('data-assistente');

  function texto(tag, classe, conteudo) {
    var no = document.createElement(tag);
    if (classe) no.className = classe;
    // `textContent` e nunca `innerHTML`: a resposta vem do banco, e o banco é
    // editável por quem mantém a FAQ. Um `<script>` numa resposta de FAQ seria
    // XPS armazenado com autor conhecido — o pior tipo, porque parece conteúdo.
    no.textContent = conteudo;
    return no;
  }

  function desenhar(dados) {
    saida.textContent = '';
    saida.hidden = false;
    if (dados.pergunta) saida.appendChild(texto('p', 'au-bot-pergunta', dados.pergunta));
    saida.appendChild(texto('p', 'au-bot-texto', dados.texto));

    // §56 — quem respondeu fica visível. Resposta escrita e conferida por
    // alguém da empresa tem outro peso que resposta gerada por aproximação, e
    // apagar a diferença é o que faz alguém citar o portal numa reunião com
    // informação que ninguém revisou.
    if (dados.de_ia) {
      saida.appendChild(
        texto('p', 'au-bot-origem', 'Resposta gerada automaticamente — confira antes de usar.')
      );
    }

    if (!dados.acoes || !dados.acoes.length) return;
    var lista = document.createElement('ul');
    lista.className = 'au-bot-acoes';
    dados.acoes.forEach(function (acao) {
      var item = document.createElement('li');
      var link = document.createElement('a');
      link.className = 'au-bot-acao';
      link.href = acao.url;
      link.textContent = acao.rotulo;
      item.appendChild(link);
      lista.appendChild(item);
    });
    saida.appendChild(lista);
  }

  function perguntar(pergunta) {
    if (!pergunta) return;
    saida.hidden = false;
    saida.textContent = '';
    saida.appendChild(texto('p', 'au-bot-texto', 'Procurando…'));

    fetch(endereco + '?q=' + encodeURIComponent(pergunta), {
      headers: { 'X-Requested-With': 'fetch' }
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(desenhar)
      .catch(function () {
        // Mensagem de gente, não de máquina: quem lê isto quer saber o que
        // fazer agora, não qual código HTTP voltou.
        saida.textContent = '';
        saida.appendChild(
          texto('p', 'au-bot-texto', 'Não consegui responder agora. Tente de novo, ou veja o catálogo de serviços.')
        );
      });
  }

  painel.addEventListener('submit', function (e) {
    e.preventDefault();
    perguntar(campo.value.trim());
  });

  document.addEventListener('click', function (e) {
    var atalho = e.target.closest('[data-bot-pergunta]');
    if (!atalho) return;
    campo.value = atalho.getAttribute('data-bot-pergunta');
    perguntar(campo.value);
  });
})();

/* Botão "Salvar em PDF" — abre o diálogo de impressão do navegador.
 *
 * `window.print()` e não geração no servidor: o projeto não tem dependência de
 * terceiros em execução, e `weasyprint`/`reportlab` são escolha de arquitetura.
 * A folha impressa sai igual à da tela — ver `@media print` no CSS.
 *
 * Sem JS o botão não aparece de propósito (ele nasce sem `hidden`, mas o Ctrl+P
 * do navegador continua funcionando e produz o mesmo resultado). */
(function () {
  'use strict';
  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-imprimir]')) window.print();
  });
})();

/* Nome do arquivo escolhido, ao lado do botão.
 *
 * O `<input type="file">` fica escondido em `.au-sr` e o `<label>` é o controle
 * visível — ver `.au-arquivo` no CSS. O que se perde escondendo o input é o
 * nome do arquivo, que o navegador desenha ao lado do botão nativo; isto o
 * devolve.
 *
 * PROGRESSIVO de propósito: sem JavaScript o campo continua funcionando — o
 * label abre o seletor, o input envia o arquivo, e o que falta é só o texto
 * dizendo qual. Escrever o controle inteiro em JS trocaria um campo feio por
 * um campo que não existe. */
(function () {
  'use strict';
  document.addEventListener('change', function (e) {
    var entrada = e.target;
    if (!entrada.matches || !entrada.matches('input[type="file"][data-nome-em]')) return;

    var campo = entrada.closest('.au-campo');
    var destino = campo && campo.querySelector(entrada.getAttribute('data-nome-em'));
    if (!destino) return;

    var arquivos = entrada.files;
    if (!arquivos || !arquivos.length) {
      destino.textContent = destino.getAttribute('data-vazio') || '';
      return;
    }
    /* `textContent` e nunca `innerHTML`: o nome do arquivo é escolhido pela
     * pessoa, e um arquivo chamado `<img onerror=…>.png` é conteúdo de usuário
     * como qualquer outro. */
    destino.textContent = arquivos.length === 1
      ? arquivos[0].name
      : arquivos.length + ' arquivos';
  });
})();

/* O TRILHO LEMBRA ONDE ESTAVA.
 *
 * Ele tem rolagem PRÓPRIA (`overflow-y: auto`, ver `.au-rail` no CSS). Cada
 * navegação recarrega a página, e o navegador restaura a rolagem do documento —
 * mas não a de um elemento interno. Resultado: quem estava lendo o fim de uma
 * lista de vinte e oito itens voltava ao topo a cada clique, e tinha de
 * procurar de novo onde parou.
 *
 * Duas coisas são lembradas, e uma NÃO é:
 *
 *   1. a posição da rolagem;
 *   2. os grupos que a pessoa abriu ou fechou À MÃO;
 *   3. o grupo da tela atual — este NÃO se lembra, ele obedece ao servidor.
 *
 * O item 3 é a decisão que importa. Se a pessoa fechou "Gestão" ontem e hoje
 * abre uma tela de Gestão, o grupo abre: saber onde se está vale mais que a
 * preferência anterior, e é a única pista que o trilho dá disso.
 *
 * `sessionStorage` e não `localStorage`: é memória de sessão de navegação, e
 * não configuração. Fechar a aba zera, que é o comportamento esperado de "onde
 * eu estava". E tudo em `try/catch` — em janela anônima o acesso ESTOURA, e um
 * trilho que quebra porque a pessoa abriu uma aba privada é pior do que um
 * trilho que esquece.
 */
(function () {
  'use strict';
  var trilho = document.querySelector('.au-rail');
  if (!trilho) return;

  var CHAVE_ROLAGEM = 'au-rail-rolagem';
  var CHAVE_GRUPOS = 'au-rail-grupos';

  function ler(chave, padrao) {
    try {
      var bruto = window.sessionStorage.getItem(chave);
      return bruto === null ? padrao : JSON.parse(bruto);
    } catch (e) {
      return padrao;
    }
  }
  function gravar(chave, valor) {
    try {
      window.sessionStorage.setItem(chave, JSON.stringify(valor));
    } catch (e) {
      /* Cota cheia ou armazenamento bloqueado: esquecer é aceitável. */
    }
  }

  var lembrados = ler(CHAVE_GRUPOS, {});
  var grupos = trilho.querySelectorAll('.au-rail-secao[data-grupo]');

  Array.prototype.forEach.call(grupos, function (grupo) {
    var chave = grupo.getAttribute('data-grupo');
    /* O grupo que o SERVIDOR abriu é o da tela atual: ele manda, e não entra
     * no que se lembra. Os outros seguem o que a pessoa escolheu. */
    if (!grupo.open && Object.prototype.hasOwnProperty.call(lembrados, chave)) {
      grupo.open = lembrados[chave];
    }
    grupo.addEventListener('toggle', function () {
      /* Recolher o trilho abre todos os grupos para que os ícones apareçam —
       * ver o bloco "RECOLHER O TRILHO" no fim deste arquivo. Essa abertura é
       * consequência da largura e NÃO é escolha da pessoa: gravá-la faria o
       * trilho voltar com tudo aberto depois, e a preferência real se perderia.
       * Enquanto recolhido, o que se lembra fica congelado. */
      var modulo = grupo.closest('.au-modulo');
      if (modulo && modulo.getAttribute('data-trilho') === 'recolhido') return;
      lembrados[chave] = grupo.open;
      gravar(CHAVE_GRUPOS, lembrados);
    });
  });

  /* A rolagem é restaurada DEPOIS dos grupos: abrir um grupo muda a altura do
   * conteúdo, e restaurar antes daria uma posição calculada sobre outra lista. */
  var posicao = ler(CHAVE_ROLAGEM, 0);
  if (typeof posicao === 'number' && posicao > 0) trilho.scrollTop = posicao;

  /* `requestAnimationFrame` no `scroll` para não gravar a cada pixel: o evento
   * dispara dezenas de vezes por gesto, e `sessionStorage` é síncrono. */
  var agendado = false;
  trilho.addEventListener('scroll', function () {
    if (agendado) return;
    agendado = true;
    window.requestAnimationFrame(function () {
      agendado = false;
      gravar(CHAVE_ROLAGEM, trilho.scrollTop);
    });
  }, { passive: true });
})();

/* ─────────────────────────────────────────────────────────────────────
 * AS NOTAS DE LEITURA, RECOLHIDAS.
 *
 * As telas deste produto explicam o que mostram — por que a margem é mediana e
 * não média, por que a janela da pesquisa é de 12 meses e a do dinheiro de 7.
 * O texto é bom e a decisão de tê-lo está certa. O problema é que ele fica
 * ABERTO em toda seção de toda tela: quem já sabe lê o mesmo parágrafo pela
 * quinquagésima vez, e o parágrafo compete com o número que ele explica.
 *
 * Aqui a nota longa vira um "?" ao lado do título do bloco. O texto não sai do
 * sistema: ele continua no DOM, dentro de um `<details>` que o "?" abre.
 *
 * ## Por que em JavaScript e não no template
 *
 * São 137 ocorrências em 35 telas. Recolher uma a uma no template é a mesma
 * mudança escrita 137 vezes, e a 138ª nasceria aberta. Aqui a regra é uma só.
 *
 * ## Sem JavaScript
 *
 * A nota aparece aberta, como sempre apareceu. O conteúdo nunca depende disto.
 *
 * ## O que NÃO é recolhido
 *
 * Nota curta (cabe numa linha, e recolher custaria mais clique do que leitura),
 * nota de estado vazio (é a única coisa na tela — recolhê-la deixaria a seção
 * muda) e nota de alerta, que é aviso e não explicação.
 */
(function () {
  'use strict';

  var MINIMO = 90;          // caracteres; abaixo disso a nota já é uma linha
  var TITULOS = '.au-secao-titulo, .au-gr-titulo, .au-subsecao, h2, h3';

  /* O bloco a que a nota pertence. Sobe só até onde uma moldura existe: fora
     dela não há título que seja "o desta nota". */
  function blocoDe(nota) {
    return nota.closest('.au-secao-faixa, .au-secao, .au-gr, .au-card');
  }

  /* O título que a nota explica: o primeiro dentro do mesmo bloco. */
  function tituloDe(bloco) {
    if (!bloco) return null;
    var t = bloco.querySelector(TITULOS);
    return t && blocoDe(t) === bloco ? t : null;
  }

  function recolher(nota, titulo) {
    /* O bloco pode ter mais de uma nota, e quatro "?" enfileirados ao lado do
       mesmo título é a poluição de volta com outra roupa. A partir da segunda,
       a nota entra no balão que já existe. */
    var existente = titulo && titulo.querySelector(':scope > .au-comoler');
    if (existente) {
      existente.querySelector('.au-comoler-corpo').appendChild(nota);
      return;
    }

    var detalhe = document.createElement('details');
    detalhe.className = 'au-comoler';

    var resumo = document.createElement('summary');
    resumo.className = 'au-comoler-botao';
    resumo.textContent = '?';
    /* O rótulo acessível diz o que o "?" abre. Um botão cujo nome é "?" não
       informa nada a quem ouve a tela. */
    resumo.setAttribute('aria-label', 'Como ler este bloco');
    resumo.setAttribute('title', 'Como ler este bloco');

    var corpo = document.createElement('div');
    corpo.className = 'au-comoler-corpo';

    detalhe.appendChild(resumo);
    detalhe.appendChild(corpo);

    /* `replaceWith` antes de mover o conteúdo: a nota sai do fluxo onde
       ocupava uma linha inteira, e o texto dela passa a viver dentro do
       `<details>`, sem nunca ser recriado como string. */
    nota.replaceWith(detalhe);
    corpo.appendChild(nota);

    if (titulo) titulo.appendChild(detalhe);
  }

  function iniciar() {
    var notas = document.querySelectorAll('p.au-ajuda');

    Array.prototype.forEach.call(notas, function (nota) {
      if (nota.classList.contains('au-ajuda--alerta')) return;
      if (nota.closest('.au-comoler, .au-vazio, .au-empty, form')) return;
      if (nota.textContent.trim().length < MINIMO) return;

      var bloco = blocoDe(nota);
      if (!bloco) return;

      /* Um bloco cuja única coisa é a nota não tem o que explicar: recolher ali
         deixaria uma seção com um "?" e mais nada. */
      if (bloco.textContent.trim() === nota.textContent.trim()) return;

      recolher(nota, tituloDe(bloco));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();

/* ─────────────────────────────────────────────────────────────────────
 * RECOLHER O TRILHO.
 *
 * Numa tela de tabela larga, 224px de menu são uma coluna de dados a menos. O
 * botão devolve esse espaço e o estado fica gravado, porque quem recolhe quer
 * que continue recolhido na próxima tela — recolher de novo a cada navegação é
 * pior do que não poder recolher.
 *
 * ## `localStorage` e não `sessionStorage`
 *
 * Diferente da rolagem e dos grupos abertos, que são "onde eu estava" e devem
 * zerar ao fechar a aba, a largura do menu é PREFERÊNCIA: quem trabalha o dia
 * inteiro numa planilha quer o trilho estreito sempre.
 *
 * ## Os grupos, ao recolher
 *
 * Recolhido mostra UMA LINHA POR GRUPO — o ícone do `<summary>` — e esconde os
 * itens. Isso apaga um problema que existia antes: o `<summary>` fica visível
 * com o `<details>` aberto ou fechado, então não é mais preciso forçar os
 * grupos a abrir para que algo apareça. A versão anterior abria todos ao
 * recolher e guardava quais estavam fechados para devolvê-los depois — um
 * controle de largura reescrevendo a preferência de outro controle.
 *
 * Clicar num grupo recolhido EXPANDE o trilho e abre aquele grupo, em vez de
 * abrir um `<details>` cujos itens o CSS esconde. Sem isso o clique não fazia
 * nada visível, que é a pior resposta possível a um clique.
 *
 * ## Sem JavaScript
 *
 * O botão não existe e o trilho fica expandido, que é o estado completo.
 */
(function () {
  'use strict';

  var trilho = document.querySelector('.au-rail');
  var modulo = document.querySelector('.au-modulo');
  if (!trilho || !modulo) return;

  var CHAVE = 'au-trilho-recolhido';

  function ler() {
    try { return window.localStorage.getItem(CHAVE) === '1'; } catch (e) { return false; }
  }
  function gravar(recolhido) {
    try { window.localStorage.setItem(CHAVE, recolhido ? '1' : '0'); } catch (e) { /* ignora */ }
  }

  var botao = document.createElement('button');
  botao.type = 'button';
  botao.className = 'au-rail-recolher';

  var rotulo = document.createElement('span');
  rotulo.className = 'au-rail-recolher-rotulo';
  rotulo.textContent = 'Recolher';

  /* O ícone é o mesmo `#i-seta` do resto do produto, girado — em vez de uma
     segunda seta quase igual no sprite. */
  var icone = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  icone.setAttribute('class', 'au-icon');
  icone.setAttribute('aria-hidden', 'true');
  var uso = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  uso.setAttribute('href', '#i-seta');
  icone.appendChild(uso);

  botao.appendChild(rotulo);
  botao.appendChild(icone);

  function aplicar(recolhido, comFoco) {
    modulo.setAttribute('data-trilho', recolhido ? 'recolhido' : 'expandido');
    botao.setAttribute('aria-expanded', recolhido ? 'false' : 'true');
    botao.setAttribute('aria-label', recolhido ? 'Expandir o menu' : 'Recolher o menu');
    botao.setAttribute('title', botao.getAttribute('aria-label'));

    /* Recolhido sobra só o ícone do grupo; o `title` é o que devolve o nome a
       quem passa o ponteiro. Nos itens não é mais preciso — eles não estão na
       tela. */
    Array.prototype.forEach.call(trilho.querySelectorAll('.au-rail-grupo'), function (g) {
      if (recolhido) {
        if (!g.getAttribute('title')) g.setAttribute('title', g.textContent.trim());
      } else {
        g.removeAttribute('title');
      }
    });

    if (comFoco) botao.focus();
  }

  botao.addEventListener('click', function () {
    var recolhido = modulo.getAttribute('data-trilho') !== 'recolhido';
    aplicar(recolhido, false);
    gravar(recolhido);
  });

  /* RECOLHIDO, CLICAR NUM GRUPO EXPANDE O TRILHO.
     `preventDefault` porque o alvo é um `<summary>`: sem isso o navegador
     também alternaria o `<details>`, e a pessoa acabaria com o trilho aberto e
     o grupo que ela clicou FECHADO — o contrário do que pediu. */
  trilho.addEventListener('click', function (e) {
    if (modulo.getAttribute('data-trilho') !== 'recolhido') return;
    var grupo = e.target.closest ? e.target.closest('.au-rail-grupo') : null;
    if (!grupo) return;
    e.preventDefault();
    var secao = grupo.parentNode;
    if (secao && secao.tagName === 'DETAILS') secao.open = true;
    aplicar(false, false);
    gravar(false);
  });

  /* Na testa do trilho, ao lado da marca — é a única parte que não rola. */
  var topo = trilho.querySelector('.au-rail-topo');
  (topo || trilho).appendChild(botao);
  aplicar(ler(), false);
})();

/* A chave do modo escuro, no menu da conta.
 *
 * ## Três estados, dois visíveis
 *
 * A preferência tem três valores possíveis: "claro", "escuro" e NENHUM — e o
 * terceiro é o padrão, em que o tema segue o `prefers-color-scheme` do sistema
 * operacional. A chave só alterna entre ligada e desligada; quem nunca a tocou
 * fica no terceiro estado, e o rótulo diz isso ("Seguindo o sistema") em vez de
 * mentir que está desligada.
 *
 * ## Por que o `<html>` e não uma classe no `<body>`
 *
 * `tokens.css` já declara os dois temas: `@media (prefers-color-scheme: dark)`
 * guardado por `:root:not([data-theme="light"])`, e `:root[data-theme="dark"]`.
 * Essa dupla é o que permite os três estados — o atributo VENCE a media query
 * nos dois sentidos. Aqui basta escrever o atributo; nenhuma regra nova.
 *
 * ## Sem JavaScript
 *
 * O botão nasce `hidden` no template e só aparece aqui. Sem este arquivo o tema
 * segue o sistema, que é o comportamento que o produto sempre teve.
 */
(function () {
  'use strict';

  var chave = document.querySelector('[data-tema-chave]');
  if (!chave) return;

  var CHAVE = 'au-tema';
  var raiz = document.documentElement;
  var estado = chave.querySelector('[data-tema-estado]');

  function lerPreferencia() {
    try { return window.localStorage.getItem(CHAVE); } catch (e) { return null; }
  }

  /* O que está NA TELA agora, que não é o mesmo que a preferência: sem
     preferência gravada, quem decide é o sistema. */
  function escuroAgora() {
    var gravado = lerPreferencia();
    if (gravado === 'dark') return true;
    if (gravado === 'light') return false;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  function pintar() {
    var escuro = escuroAgora();
    chave.setAttribute('aria-pressed', escuro ? 'true' : 'false');
    if (!estado) return;
    var gravado = lerPreferencia();
    if (gravado === null) estado.textContent = 'Seguindo o sistema';
    else estado.textContent = escuro ? 'Ligado' : 'Desligado';
  }

  chave.addEventListener('click', function () {
    var escuro = !escuroAgora();
    raiz.setAttribute('data-theme', escuro ? 'dark' : 'light');
    try { window.localStorage.setItem(CHAVE, escuro ? 'dark' : 'light'); } catch (e) { /* ignora */ }
    pintar();
  });

  /* Quem nunca escolheu acompanha o sistema em tempo real — trocar o tema do
     macOS com a aba aberta tem de trocar aqui também, e o rótulo junto. */
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
    if (lerPreferencia() === null) pintar();
  });

  chave.hidden = false;
  pintar();
})();
