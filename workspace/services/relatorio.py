"""REL — o assistente que ajuda a preencher, e o documento que sai.

## O §35 pede "assistente", e assistente aqui não é IA

O que faz alguém desistir de um relatório de campo é a folha em branco: a pessoa
não sabe o que precisa ser dito, escreve pouco, e o relatório volta com pedido
de complemento três dias depois — quando ninguém lembra mais.

O assistente deste módulo é a estrutura: um questionário por tipo, com pergunta,
ajuda e obrigatoriedade. É a mesma escolha do catálogo de serviços, e resolve o
mesmo problema — o formulário estruturado é o que transforma "descreva a
ocorrência" em cinco perguntas respondíveis.

## Sobre o PDF

**Este módulo não gera PDF no servidor.** A página emitida é desenhada para
impressão (`@media print`), e o navegador exporta em PDF com um comando — sem
biblioteca, sem fonte embarcada, sem serviço de renderização.

Não é gambiarra e também não é a melhor solução possível; é a solução honesta
para as restrições deste projeto, que não tem nenhuma dependência de terceiros
em execução. PDF gerado no servidor exige `weasyprint` (que traz Cairo e Pango)
ou `reportlab` (que exige desenhar o layout em código). As duas são decisões de
arquitetura, não de implementação — e é o tipo de coisa que se escolhe de olhos
abertos, não como efeito colateral de uma tarefa.
"""

from __future__ import annotations

from django.utils import timezone

from workspace.models.relatorio import (
    EvidenciaRelatorio,
    Relatorio,
    SituacaoRelatorio,
    TipoRelatorio,
)

PERMISSAO_VER_TUDO = "ops.ler"


class RelatorioError(Exception):
    """O relatório não pode ser gravado ou emitido assim."""


#: O questionário de cada tipo — §35 e §36.
#:
#: Aqui e não no banco, ao contrário do catálogo de serviços: o catálogo muda
#: com a operação (item novo toda semana) e por isso mora em tabela; o
#: questionário de um relatório muda com o CONTRATO, e mudança de contrato passa
#: por revisão de código de qualquer forma.
QUESTIONARIOS = {
    TipoRelatorio.ENTREGA: [
        {"chave": "responsavel_cliente", "rotulo": "Quem recebeu",
         "obrigatorio": True,
         "ajuda": "Nome de quem conferiu a entrega no local."},
        {"chave": "itens", "rotulo": "Itens entregues", "tipo": "texto_longo",
         "obrigatorio": True,
         "ajuda": "Um por linha, com quantidade. Ex.: 4 câmeras IP · 1 switch 24p."},
        {"chave": "conferido", "rotulo": "Conferido no local", "tipo": "escolha",
         "obrigatorio": True,
         "opcoes": [
             {"valor": "completo", "rotulo": "Sim — tudo conferido"},
             {"valor": "parcial", "rotulo": "Parcial — falta item"},
             {"valor": "divergente", "rotulo": "Divergente — item errado"},
         ]},
        # Obrigatório E condicional: só é cobrado quando a conferência não
        # fechou. A ajuda dizia isso e o campo não estava marcado — entrega
        # parcial saía sem dizer o que faltou, que é a única informação que
        # importa numa entrega parcial.
        {"chave": "pendencias", "rotulo": "O que ficou pendente",
         "tipo": "texto_longo", "obrigatorio": True,
         "quando": {"campo": "conferido", "diferente_de": "completo"},
         "ajuda": "Obrigatório quando a conferência não fechou."},
        {"chave": "observacoes", "rotulo": "Observações", "tipo": "texto_longo"},
    ],
    TipoRelatorio.OCORRENCIA: [
        {"chave": "o_que_aconteceu", "rotulo": "O que aconteceu",
         "tipo": "texto_longo", "obrigatorio": True,
         "ajuda": "Os fatos, na ordem em que aconteceram. Sem conclusão ainda."},
        {"chave": "causa", "rotulo": "Causa", "tipo": "texto_longo",
         "ajuda": "Deixe em branco se ainda não se sabe — inventar causa é pior "
                  "que assumir que não se sabe."},
        {"chave": "acoes", "rotulo": "Ações executadas", "tipo": "texto_longo",
         "obrigatorio": True,
         "ajuda": "O que foi feito no momento, por quem."},
        {"chave": "equipe", "rotulo": "Equipe presente",
         "ajuda": "Quem estava no local."},
        {"chave": "resultado", "rotulo": "Resultado", "tipo": "escolha",
         "obrigatorio": True,
         "opcoes": [
             {"valor": "resolvido", "rotulo": "Resolvido no local"},
             {"valor": "paliativo", "rotulo": "Paliativo — exige retorno"},
             {"valor": "nao_resolvido", "rotulo": "Não resolvido"},
         ]},
        {"chave": "conclusao", "rotulo": "Conclusão", "tipo": "texto_longo",
         "obrigatorio": True,
         "ajuda": "O que a empresa conclui do episódio, e o que recomenda."},
        {"chave": "observacoes", "rotulo": "Observações", "tipo": "texto_longo"},
    ],
}


def questionario(tipo: str) -> list[dict]:
    return QUESTIONARIOS.get(tipo, [])


def campo_ativo(campo: dict, dados: dict) -> bool:
    """Campo condicional — `quando` com `diferente_de`.

    Regra mais simples que a do catálogo de propósito: aqui só existe um caso
    ("pendências, quando a conferência não fechou"), e uma máquina de condições
    completa para um caso é máquina que ninguém entende quando aparece o
    segundo.
    """
    condicao = campo.get("quando")
    if not condicao:
        return True
    valor = (dados or {}).get(condicao["campo"], "")
    if "diferente_de" in condicao:
        return valor != condicao["diferente_de"] and bool(valor)
    return valor == condicao.get("igual")


def faltando(tipo: str, dados: dict) -> list[str]:
    """Os rótulos dos campos obrigatórios em branco."""
    return [
        campo["rotulo"]
        for campo in questionario(tipo)
        if campo.get("obrigatorio")
        and campo_ativo(campo, dados)
        and not str((dados or {}).get(campo["chave"], "")).strip()
    ]


# ── Escrever ────────────────────────────────────────────────────────


def salvar(
    pessoa,
    relatorio: Relatorio | None = None,
    *,
    tipo: str,
    titulo: str,
    dados: dict | None = None,
    cliente: str = "",
    local: str = "",
    ocorrido_em=None,
    horario=None,
    unidade=None,
) -> Relatorio:
    """Cria ou atualiza um RASCUNHO. Emitido não se edita."""
    if tipo not in TipoRelatorio.values:
        raise RelatorioError("Tipo de relatório inválido.")
    if relatorio is not None and not relatorio.editavel:
        raise RelatorioError(
            "Relatório emitido não pode ser alterado. Cancele e faça outro."
        )

    titulo = (titulo or "").strip()
    if not titulo:
        raise RelatorioError("O título é obrigatório.")

    novo = relatorio is None
    relatorio = relatorio or Relatorio(autor=pessoa)
    relatorio.tipo = tipo
    relatorio.titulo = titulo[:200]
    relatorio.cliente = (cliente or "").strip()[:160]
    relatorio.local = (local or "").strip()[:200]
    relatorio.dados = dados or {}
    if ocorrido_em:
        relatorio.ocorrido_em = ocorrido_em
    relatorio.horario = horario
    if unidade is not None:
        relatorio.unidade = unidade
    if novo:
        relatorio.autor = pessoa
    relatorio.save()
    return relatorio


def emitir(relatorio: Relatorio, pessoa) -> Relatorio:
    """Fecha o relatório. Daí em diante ele não muda.

    A checagem de obrigatórios acontece AQUI e não no rascunho: o campo em
    branco no meio da redação é normal — a pessoa está escrevendo. O que não
    pode é sair da empresa incompleto.
    """
    if relatorio.autor_id != getattr(pessoa, "pk", None):
        raise RelatorioError("Só quem escreveu pode emitir.")
    if relatorio.emitido:
        return relatorio
    if relatorio.situacao == SituacaoRelatorio.CANCELADO:
        raise RelatorioError("Relatório cancelado não pode ser emitido.")

    pendentes = faltando(relatorio.tipo, relatorio.dados)
    if pendentes:
        raise RelatorioError(
            "Falta preencher: " + ", ".join(pendentes) + "."
        )

    relatorio.situacao = SituacaoRelatorio.EMITIDO
    relatorio.emitido_em = timezone.now()
    relatorio.save(update_fields=["situacao", "emitido_em"])
    return relatorio


def cancelar(relatorio: Relatorio, pessoa) -> Relatorio:
    """Cancela — inclusive emitido.

    Emitido cancelado continua existindo e continua legível: a correção de um
    relatório errado é OUTRO relatório, e a trilha entre os dois é o que permite
    explicar a divergência depois.
    """
    if relatorio.autor_id != getattr(pessoa, "pk", None):
        raise RelatorioError("Só quem escreveu pode cancelar.")
    relatorio.situacao = SituacaoRelatorio.CANCELADO
    relatorio.save(update_fields=["situacao"])
    return relatorio


def anexar(relatorio: Relatorio, arquivo, legenda: str = "") -> EvidenciaRelatorio:
    """Uma evidência. Recusada depois de emitido, pelo mesmo motivo da edição."""
    if not relatorio.editavel:
        raise RelatorioError("Relatório emitido não recebe evidência nova.")

    # Reusa o validador do módulo de anexos — extensão, MIME e magic bytes.
    # Um segundo validador aqui produziria dois caminhos de upload no mesmo
    # sistema com regras diferentes, e é sempre o mais novo que esquece os
    # magic bytes.
    from workspace.services import anexos as anx

    motivo = anx.validar(arquivo)
    if motivo:
        raise RelatorioError(f"{getattr(arquivo, 'name', 'arquivo')}: {motivo}")

    return EvidenciaRelatorio.objects.create(
        relatorio=relatorio,
        arquivo=arquivo,
        nome_original=getattr(arquivo, "name", "")[:255],
        legenda=legenda[:200],
        tamanho=getattr(arquivo, "size", 0) or 0,
    )


# ── Ler ─────────────────────────────────────────────────────────────


def pode_ver(relatorio: Relatorio, pessoa, cache=None) -> bool:
    """O autor sempre; quem tem `ops.ler` também.

    Relatório de ocorrência é documento de operação: quem responde pela
    operação precisa ler os de todo mundo, senão a informação que justifica o
    relatório fica presa em quem já sabe do episódio.
    """
    from identidade.services.autorizacao import pode

    if relatorio.autor_id == getattr(pessoa, "pk", None):
        return True
    return pode(pessoa, PERMISSAO_VER_TUDO, cache=cache)


def visiveis_para(pessoa, cache=None):
    from identidade.services.autorizacao import pode

    consulta = Relatorio.objects.select_related("autor").prefetch_related("evidencias")
    if pode(pessoa, PERMISSAO_VER_TUDO, cache=cache):
        return consulta
    return consulta.filter(autor=pessoa)


def para_impressao(relatorio: Relatorio) -> list[dict]:
    """As respostas na ordem do questionário, com rótulo — para a página que
    vira PDF.

    Ordenado pelo QUESTIONÁRIO e não pelas chaves do JSON: dicionário não tem
    ordem garantida entre versões de Python, e um relatório impresso com as
    perguntas embaralhadas é um documento que ninguém assina.
    """
    linhas = []
    for campo in questionario(relatorio.tipo):
        if not campo_ativo(campo, relatorio.dados):
            continue
        valor = (relatorio.dados or {}).get(campo["chave"], "")
        if not str(valor).strip():
            continue
        if campo.get("opcoes"):
            valor = next(
                (o["rotulo"] for o in campo["opcoes"] if o["valor"] == valor), valor
            )
        linhas.append({"rotulo": campo["rotulo"], "valor": valor})
    return linhas
