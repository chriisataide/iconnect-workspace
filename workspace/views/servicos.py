"""Catálogo de serviços — as telas de pedir e acompanhar."""

from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.acesso import pessoa_da_requisicao
from workspace.models.anexo import Anexo
from workspace.models.catalogo import ItemCatalogo, TipoCampo
from workspace.services import anexos as anx
from workspace.services import catalogo as svc
from workspace.services import formulario as frm
from workspace.services import reembolso as rmb
from workspace.services.anexos import AnexoError
from workspace.services.catalogo import SolicitacaoError
from workspace.services.reembolso import ReembolsoError


def _cache(request: HttpRequest) -> dict:
    """Cache de permissão por requisição. O middleware do ST-0xx cria isto;
    até lá, cada view garante o seu."""
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def catalogo(request: HttpRequest) -> HttpResponse:
    """O catálogo agrupado por intenção, com prazo real medido.

    A ÚNICA das telas pessoais que não fechou, e de propósito: a lista de
    serviços é institucional — quais existem, quanto demoram, o que exige
    aprovação. Fechá-la poria uma parede de login na frente do formulário que
    acabou de ser deixado aberto, e a pessoa descobriria o catálogo pelo
    WhatsApp de novo.

    O que era de alguém e saiu são os CONTADORES do trilho ("3 em aberto",
    "1 devolvida"): sem sessão, eles vinham da primeira pessoa do organograma.
    """
    cache = _cache(request)
    pessoa = pessoa_da_requisicao(request)
    grupos = []
    for rotulo, itens in svc.agrupado_para(pessoa, cache=cache).items():
        grupos.append(
            {
                "rotulo": rotulo,
                "itens": [
                    {"item": item, "prazo": svc.prazo_medido(item)} for item in itens
                ],
            }
        )

    minhas = svc.minhas(request.user)
    return render(
        request,
        "workspace/servicos/catalogo.html",
        {
            "grupos": grupos,
            # `svc.minhas()` devolve vazio para anônimo, então os contadores
            # zeram sozinhos — e o trilho já esconde contador zerado (ADR-012:
            # bloco sem dado não desenha moldura).
            "abertas": minhas.filter(situacao__in=_ABERTAS).count(),
            "devolvidas": minhas.filter(situacao="devolvida").count(),
        },
    )


_ABERTAS = ["aguardando_aprovacao", "aprovada", "em_atendimento", "devolvida"]


def pedir(request: HttpRequest, chave: str) -> HttpResponse:
    """Formulário de um item. Valida antes de enviar e bloqueia com o motivo.

    A fronteira passa DENTRO da view, como em `reservar()`: o formulário abre
    para qualquer um — é assim que a pessoa descobre o que o serviço pede antes
    de decidir usá-lo, e fechar isso seria pôr uma parede de login na frente do
    ato central do produto.

    ENVIAR é outra coisa. O pedido nasce com um solicitante, consome o centro de
    custo dele e entra na fila do gestor dele; anônimo, nasceria em nome da
    primeira pessoa do organograma, que descobriria pela notificação. Por isso
    o POST se identifica — e o `next` traz a pessoa de volta a este formulário.
    """
    item = get_object_or_404(ItemCatalogo, chave=chave, ativo=True)
    cache = _cache(request)
    # `request.user`, e não `pessoa_da_requisicao()`: o que esta tela mostra de
    # pessoal — o centro de custo e os adiantamentos a prestar contas — é de
    # quem está identificado. Sem sessão, não é de ninguém.
    pessoa = request.user

    dados = {}
    arquivos = {}
    valor = None
    impedimentos = []
    linhas = []
    adiantamento = None

    if request.method == "POST":
        if not pessoa.is_authenticated:
            return redirect_to_login(request.get_full_path())
        dados = {
            campo["chave"]: (request.POST.get(campo["chave"]) or "").strip()
            for campo in item.campos
            if campo.get("tipo") not in _NAO_SAO_TEXTO
        }
        arquivos = {
            campo["chave"]: request.FILES.getlist(campo["chave"])
            for campo in item.campos
            if campo.get("tipo") == TipoCampo.ARQUIVO
        }
        valor = _valor_de(request.POST.get("valor"))
        linhas = _linhas_de(request)

        try:
            adiantamento = rmb.adiantamento_escolhido(
                pessoa, request.POST.get("adiantamento")
            )
            solicitacao = svc.solicitar(
                item,
                pessoa,
                dados,
                valor,
                cache=cache,
                arquivos=arquivos,
                linhas=linhas,
                adiantamento=adiantamento,
            )
        except (SolicitacaoError, AnexoError, ReembolsoError) as erro:
            # Revalida para devolver a lista completa por campo, e não só a
            # primeira mensagem: corrigir um erro por vez é o que faz o usuário
            # desistir no terceiro envio.
            impedimentos = svc.verificar(
                item,
                pessoa,
                dados,
                valor,
                cache=cache,
                arquivos=arquivos,
                linhas=linhas,
            )
            if not impedimentos:
                # A revalidação não reproduziu a falha — só acontece se algo
                # falhou na gravação, não na validação. Formulário que recusa
                # sem dizer nada é pior que a mensagem crua.
                impedimentos = [svc.Impedimento("anexos", str(erro))]
        else:
            if solicitacao.auto_aprovada:
                messages.success(
                    request,
                    f"{item.nome} aprovado automaticamente — está dentro da política.",
                )
            else:
                messages.success(request, f"{item.nome} enviado para aprovação.")

            # Prestação de contas não termina no envio: falta a diferença
            # contra o adiantamento, e é ela que o Financeiro cobra depois.
            # Mandar para "minhas solicitações" aqui deixaria a conta aberta
            # sem que a pessoa soubesse que faltava um passo.
            if solicitacao.adiantamento_id:
                return redirect(reverse("workspace:acerto", args=[solicitacao.pk]))
            return redirect(reverse("workspace:minhas_solicitacoes"))

    # Campos já montados com valor e erro. O template não faz busca por chave
    # dinâmica — é a regra do design system: a view agrega, o template desenha.
    por_campo = {i.campo: i.motivo for i in impedimentos}
    campos = [
        {
            **campo,
            "valor": dados.get(campo["chave"], ""),
            "erro": por_campo.get(campo["chave"]),
            # O template não compara string de tipo: a view resolve, como manda
            # o design system.
            "e_arquivo": campo.get("tipo") == TipoCampo.ARQUIVO,
            "e_despesas": campo.get("tipo") == TipoCampo.DESPESAS,
            "e_adiantamento": campo.get("tipo") == TipoCampo.ADIANTAMENTO,
            "e_escolha": campo.get("tipo") == TipoCampo.ESCOLHA,
            "opcoes_normalizadas": frm.opcoes_de(campo),
            "passo": frm.passo_do_campo(campo),
            # O ramo vai para o HTML como dado (`data-`), e não como campo
            # escondido pelo servidor: sem JS todos os ramos ficam visíveis e a
            # página continua enviável — quem descarta o que não é do ramo é o
            # servidor, em `limpar_fora_do_ramo()`.
            "quando_campo": (campo.get("quando") or {}).get("campo", ""),
            "quando_igual": _quando_igual(campo),
        }
        for campo in item.campos
    ]

    passos = frm.passos_de(item)
    return render(
        request,
        "workspace/servicos/pedir.html",
        {
            "item": item,
            "prazo": svc.prazo_medido(item),
            "campos": campos,
            "passos": passos,
            # O passo do formulário em si — o `apos_envio` acontece em outra
            # tela e não tem botão de "continuar" para chegar até ele.
            "ultimo_passo": max(
                [p["numero"] for p in passos if not p["apos_envio"]] or [1]
            ),
            "valor_passo": _passo_do_valor(item),
            "valor": valor,
            "erro_valor": por_campo.get("valor"),
            "impedimentos": impedimentos,
            # Sem sessão não há centro de custo a mostrar — e o aviso "você não
            # tem centro de custo, peça ao RH" seria mentira contada a quem
            # ainda nem disse quem é.
            "identificada": pessoa.is_authenticated,
            "centro_custo": (
                svc._centro_custo_de(pessoa) if pessoa.is_authenticated else ""
            ),
            "maximo_anexos": anx.MAXIMO_POR_CAMPO,
            # Item a item: o valor deixa de ser digitado e passa a ser somado.
            "por_despesa": rmb.tem_despesas(item),
            "despesas": _despesas_para_tela(linhas),
            "erro_despesas": por_campo.get("despesas"),
            "maximo_despesas": rmb.MAXIMO_DESPESAS,
            "adiantamentos": (
                rmb.adiantamentos_pendentes(pessoa)
                if rmb.aceita_adiantamento(item)
                else []
            ),
            "adiantamento_escolhido": (
                str(adiantamento.pk) if adiantamento else request.POST.get("adiantamento", "")
            ),
        },
    )


def _quando_igual(campo: dict) -> str:
    """A condição do ramo, em texto separado por `|` para o `data-` do HTML."""
    esperado = (campo.get("quando") or {}).get("igual")
    if esperado is None:
        return ""
    if isinstance(esperado, (list, tuple)):
        return "|".join(str(v) for v in esperado)
    return str(esperado)


def _passo_do_valor(item: ItemCatalogo) -> int:
    """Em qual passo mostrar o campo de valor.

    No último do formulário: o preço é a última coisa que se confirma, e num
    stepper ele não pode cair sozinho num passo anterior ao que o explica.
    """
    passos = [
        p["numero"] for p in frm.passos_de(item) if not p["apos_envio"]
    ]
    return max(passos or [1])


# Tipos que não são texto no POST: arquivo vem em `request.FILES`, e despesas e
# adiantamento têm leitura própria.
_NAO_SAO_TEXTO = (TipoCampo.ARQUIVO, TipoCampo.DESPESAS, TipoCampo.ADIANTAMENTO)


def _linhas_de(request: HttpRequest) -> list[rmb.Linha]:
    """Lê as compras do POST.

    Os campos são NUMERADOS (`despesa_valor_3`) e a lista de índices vem num
    hidden. Sem isso, `getlist` desalinharia valores e arquivos na primeira
    linha em que a pessoa esquecesse o comprovante: `<input type=file>` vazio
    não é enviado pelo navegador, e a compra 3 herdaria o cupom da 4.
    """
    linhas: list[rmb.Linha] = []
    for indice in request.POST.getlist("despesa_indice")[: rmb.MAXIMO_DESPESAS]:
        valor = request.POST.get(f"despesa_valor_{indice}")
        motivo = request.POST.get(f"despesa_motivo_{indice}") or ""
        arquivo = request.FILES.get(f"despesa_anexo_{indice}")
        # Linha em branco é linha que a pessoa abriu e não usou — ignorar é o
        # certo; recusar o envio por causa dela seria punir um clique a mais.
        if not (valor or motivo.strip() or arquivo):
            continue
        linhas.append(
            rmb.Linha(valor=rmb.valor_de(valor), motivo=motivo, arquivo=arquivo)
        )
    return linhas


def _despesas_para_tela(linhas) -> list[dict]:
    """Devolve o que a pessoa digitou, para o formulário não voltar vazio.

    O arquivo NÃO volta — nenhum navegador aceita repopular `<input type=file>`,
    por segurança. A tela diz isso com todas as letras em vez de fingir que o
    anexo continua lá.
    """
    return [
        {
            "indice": indice,
            "valor": _texto_do_valor(linha.valor),
            "motivo": linha.motivo,
            "tinha_arquivo": linha.arquivo is not None,
        }
        for indice, linha in enumerate(linhas)
    ]


def _texto_do_valor(valor) -> str:
    """De volta para a tela no formato em que foi digitado: `1234,56`."""
    if valor is None:
        return ""
    return f"{valor:.2f}".replace(".", ",")


@login_required
def baixar_anexo(request: HttpRequest, pk: int) -> HttpResponse:
    """O único caminho até um anexo. Autoriza, então entrega.

    Não existe URL pública para estes arquivos: eles moram fora de MEDIA_ROOT e
    o storage não tem `base_url` (ver `workspace/storage.py`). Se esta view negar,
    não há segunda porta.

    `@login_required` aqui não é sobre decidir, é sobre O QUE estes arquivos
    são: atestado médico, comprovante, contrato em análise. `pode_baixar()`
    responde "esta pessoa pode?" — e com o fallback anônimo a resposta seria
    calculada para a primeira pessoa do organograma, entregando o atestado dela
    a quem passasse pela URL. É o mesmo furo que o projeto fechou ao tirar os
    anexos de `MEDIA_ROOT`, reaberto por outro caminho.
    """
    anexo = get_object_or_404(
        Anexo.objects.select_related("solicitacao", "solicitacao__aprovacao"), pk=pk
    )

    if not anx.pode_baixar(request.user, anexo, cache=_cache(request)):
        # 403 e não 404: quem chegou aqui tem o id de um anexo que existe, e
        # mentir sobre a existência não protege nada que o 403 já não proteja.
        raise PermissionDenied("Você não tem acesso a este anexo.")

    try:
        arquivo = anexo.arquivo.open("rb")
    except FileNotFoundError:
        # Metadado na tabela e arquivo ausente no disco: erro de operação, e a
        # tela precisa dizer "não está lá" em vez de estourar 500.
        raise Http404("Arquivo não encontrado no armazenamento.")

    # `as_attachment` sempre: comprovante e atestado não devem ser renderizados
    # inline no navegador — SVG e HTML abrem porta para XSS na nossa origem.
    return FileResponse(
        arquivo, as_attachment=True, filename=anexo.nome_original
    )


def _valor_de(bruto: str | None) -> Decimal | None:
    """Aceita `1.234,56` e `1234.56` — o usuário digita como aprendeu.

    Uma leitura só para todo o Workspace, em `services/reembolso`. Havia duas —
    esta e a das linhas de despesa — e a daqui lia `1234.56` como cento e vinte
    e três mil, porque apagava todo ponto antes de trocar a vírgula. Duas
    funções que interpretam dinheiro divergem; é sempre a menos usada que fica
    com o bug.
    """
    return rmb.valor_de(bruto)


@login_required
def minhas_solicitacoes(request: HttpRequest) -> HttpResponse:
    solicitacoes = svc.minhas(request.user)
    return render(
        request,
        "workspace/servicos/minhas.html",
        {
            "solicitacoes": solicitacoes,
            "abertas": solicitacoes.filter(situacao__in=_ABERTAS).count(),
        },
    )


@login_required
def acerto(request: HttpRequest, pk: int) -> HttpResponse:
    """O segundo passo da prestação de contas: o que fazer com a diferença.

    Tela própria, e não um bloco no fim do formulário, porque o valor da
    diferença só existe DEPOIS que as compras foram somadas — mostrar antes
    exigiria calcular no navegador, e aí a conta que a pessoa vê e a conta que
    o sistema grava seriam duas.

    `@login_required` porque aqui se movimenta dinheiro: o acerto declara que
    uma devolução foi feita, ou informa a conta em que a empresa vai depositar.
    Ato assinado — sem identidade, seria assinado com o nome de outra pessoa.
    """
    pessoa = request.user
    prestacao = get_object_or_404(
        svc.minhas(pessoa).select_related("adiantamento"), pk=pk
    )
    conta = rmb.calcular_acerto(prestacao)
    if conta is None:
        raise Http404("Este pedido não presta contas de um adiantamento.")

    ja_feito = rmb.AcertoAdiantamento.objects.filter(prestacao=prestacao).first()
    erro = None

    if request.method == "POST" and ja_feito is None:
        try:
            rmb.confirmar_acerto(
                prestacao,
                pessoa,
                dados_bancarios=request.POST.get("dados_bancarios", ""),
                comprovante=request.FILES.get("comprovante"),
            )
        except (ReembolsoError, AnexoError) as falha:
            erro = str(falha)
        else:
            messages.success(request, "Prestação de contas fechada.")
            return redirect(reverse("workspace:minhas_solicitacoes"))

    # A mesma trilha do formulário, agora no último passo: a pessoa vê que
    # chegou onde o pedido dizia que ela chegaria, e não numa tela avulsa.
    passos = frm.passos_de(prestacao.item)
    return render(
        request,
        "workspace/servicos/acerto.html",
        {
            "passos": passos,
            "passo_atual": len(passos),
            "prestacao": prestacao,
            "adiantamento": prestacao.adiantamento,
            "conta": conta,
            "despesas": prestacao.despesas.all(),
            "ja_feito": ja_feito,
            "erro": erro,
            "conta_empresa": rmb.conta_da_empresa(),
            "conta_sugerida": (
                request.POST.get("dados_bancarios")
                or rmb.conta_sugerida(prestacao)
            ),
        },
    )


@login_required
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    """Cancelar é ato: derruba a aprovação em curso e libera o orçamento
    comprometido. Sem identidade, qualquer um cancelaria o pedido de alguém."""
    pessoa = request.user
    solicitacao = get_object_or_404(svc.minhas(pessoa), pk=pk)
    if request.method == "POST":
        try:
            svc.cancelar(solicitacao, pessoa)
            messages.success(request, "Solicitação cancelada.")
        except SolicitacaoError as erro:
            messages.error(request, str(erro))
    return redirect(reverse("workspace:minhas_solicitacoes"))
