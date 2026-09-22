"""O ciclo de vida do lote de ponto: permissão, importação, correção, auditoria.

Três módulos, três trabalhos: `ponto.py` tem as regras puras (planilha,
telefone, mensagem) e não sabe o que é banco; este tem o lote e quem pode o
quê; `ponto_whatsapp.py` fala com o n8n. A separação existe para que a regra
mais importante — a do telefone — possa ser testada sem Django e sem Docker.

## As permissões — §32

    rh.ponto_ler        abre a tela e o histórico
    rh.ponto_importar   envia planilha e corrige telefone
    rh.ponto_testar     dispara para o telefone de teste
    rh.ponto_enviar     dispara para os colaboradores

`rh.ponto_enviar` é separada de propósito e nunca é implicada por outra. Quem
importa não envia; quem testa não envia. É a única ação do fluxo que não tem
desfazer, e por isso é a única que exige uma concessão própria.
"""

from __future__ import annotations

import hashlib

from django.core.exceptions import PermissionDenied
from django.db import transaction
from identidade.services.autorizacao import pode

from workspace.models.ponto import (
    AcaoPonto,
    ColaboradorPonto,
    EventoPonto,
    LotePonto,
    ModoEnvio,
    SituacaoLote,
)
from workspace.services import ponto as motor

PERM_LER = "rh.ponto_ler"
PERM_IMPORTAR = "rh.ponto_importar"
PERM_TESTAR = "rh.ponto_testar"
PERM_ENVIAR = "rh.ponto_enviar"

#: O que o upload aceita. XLS legado fica de fora: `openpyxl` não lê o formato
#: binário antigo, e aceitar a extensão para falhar no parser seria prometer o
#: que não se cumpre. A tela diz para salvar como XLSX.
EXTENSOES = (".xlsx", ".csv")

#: 10 MB — o mesmo teto dos anexos do produto. Uma competência real tem 94
#: linhas e pesa 20 KB.
TAMANHO_MAXIMO = 10 * 1024 * 1024


def pode_ler(pessoa, cache: dict | None = None) -> bool:
    return pode(pessoa, PERM_LER, cache=cache)


def pode_importar(pessoa, cache: dict | None = None) -> bool:
    return pode(pessoa, PERM_IMPORTAR, cache=cache)


def pode_testar(pessoa, cache: dict | None = None) -> bool:
    return pode(pessoa, PERM_TESTAR, cache=cache)


def pode_enviar_producao(pessoa, cache: dict | None = None) -> bool:
    """A permissão que libera mensagem real. Nunca derivada de outra."""
    return pode(pessoa, PERM_ENVIAR, cache=cache)


def exigir(condicao: bool) -> None:
    if not condicao:
        raise PermissionDenied


# ── Auditoria — §33 ─────────────────────────────────────────────────


def registrar(lote: LotePonto, acao: str, request=None, detalhe: str = "") -> EventoPonto:
    """Uma linha de auditoria. Nunca recebe token, chave ou telefone inteiro."""
    return EventoPonto.objects.create(
        lote=lote,
        acao=acao,
        quem=getattr(request, "user", None) if request and request.user.is_authenticated else None,
        ip=_ip_de(request),
        detalhe=detalhe[:400],
    )


def _ip_de(request) -> str | None:
    if request is None:
        return None
    encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


# ── Importação — §8, §9, §10 ────────────────────────────────────────


class UploadInvalido(Exception):
    def __init__(self, mensagem: str, colunas_ausentes: tuple[str, ...] = ()):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.colunas_ausentes = colunas_ausentes


def conferir_arquivo(arquivo) -> bytes:
    """Extensão, tamanho, vazio e assinatura — no servidor, sempre.

    O `Content-Type` que o navegador manda não é conferido sozinho porque ele
    é escolhido pelo cliente: quem quiser enviar outra coisa só precisa mudar
    o cabeçalho. Quem decide é a assinatura do arquivo, lida aqui.
    """
    nome = (getattr(arquivo, "name", "") or "").lower()
    if not nome.endswith(EXTENSOES):
        raise UploadInvalido(
            "Formato não aceito. Envie um arquivo .xlsx ou .csv. "
            "Se a sua planilha é .xls, abra no Excel e salve como .xlsx."
        )

    tamanho = getattr(arquivo, "size", 0)
    if tamanho == 0:
        raise UploadInvalido("O arquivo está vazio.")
    if tamanho > TAMANHO_MAXIMO:
        raise UploadInvalido(
            f"O arquivo tem {tamanho / 1024 / 1024:.1f} MB. O máximo é "
            f"{TAMANHO_MAXIMO // 1024 // 1024} MB."
        )

    conteudo = arquivo.read()
    if not conteudo:
        raise UploadInvalido("O arquivo está vazio.")

    # XLSX é um ZIP. Um arquivo que se chama .xlsx e não começa com `PK` é
    # outra coisa com o nome trocado, e o lugar de descobrir isso é aqui, não
    # dentro do parser.
    if nome.endswith(".xlsx") and not conteudo.startswith(b"PK"):
        raise UploadInvalido("O arquivo não é uma planilha XLSX válida.")

    return conteudo


@transaction.atomic
def importar(arquivo, request=None) -> LotePonto:
    """Upload → lote validado, com um colaborador por pessoa.

    A planilha NÃO é guardada. Ela traz CPF e a senha do totem de todo mundo, e
    depois do processamento nada precisa dela. Fica o SHA-256, que responde
    "essa é a mesma planilha de ontem?" sem manter o dado sensível.
    """
    conteudo = conferir_arquivo(arquivo)
    nome = getattr(arquivo, "name", "planilha.xlsx")

    lote = LotePonto.objects.create(
        arquivo_nome=nome[:255],
        arquivo_bytes=len(conteudo),
        arquivo_digest=hashlib.sha256(conteudo).hexdigest(),
        quem_importou=getattr(request, "user", None)
        if request and request.user.is_authenticated
        else None,
        situacao=SituacaoLote.VALIDANDO,
        modo=ModoEnvio.TESTE,
    )
    registrar(lote, AcaoPonto.UPLOAD, request, f"{nome} · {len(conteudo)} bytes")

    try:
        linhas = motor.ler_planilha(conteudo, nome)
        colaboradores = motor.agrupar(linhas)
    except motor.PlanilhaInvalida as erro:
        lote.situacao = SituacaoLote.CANCELADO
        lote.erro_validacao = erro.mensagem
        lote.save(update_fields=["situacao", "erro_validacao", "atualizado_em"])
        raise UploadInvalido(erro.mensagem, erro.colunas_ausentes) from erro

    if not colaboradores:
        lote.situacao = SituacaoLote.CANCELADO
        lote.erro_validacao = "A planilha não tem nenhuma linha com colaborador."
        lote.save(update_fields=["situacao", "erro_validacao", "atualizado_em"])
        raise UploadInvalido(lote.erro_validacao)

    ColaboradorPonto.objects.bulk_create(
        [
            ColaboradorPonto(
                lote=lote,
                nome=c.nome,
                codigo=c.codigo[:40],
                local=c.local[:200],
                telefone_planilha=(c.telefone_planilha or "")[:60],
                telefone_normalizado=c.telefone_normalizado,
                pendencias=[{"data": p.data, "motivo": p.motivo} for p in c.pendencias],
                quantidade_pendencias=len(c.pendencias),
                # §15: ninguém inválido nasce marcado.
                selecionado=c.tem_telefone,
            )
            for c in colaboradores
        ]
    )

    lote.situacao = SituacaoLote.VALIDADO
    lote.save(update_fields=["situacao", "atualizado_em"])
    registrar(
        lote,
        AcaoPonto.VALIDACAO,
        request,
        f"{len(colaboradores)} colaboradores · "
        f"{sum(len(c.pendencias) for c in colaboradores)} pendências",
    )
    return lote


# ── Correção de telefone — §14 ──────────────────────────────────────


def corrigir_telefone(colaborador: ColaboradorPonto, bruto: str, request=None) -> str:
    """Grava o telefone só neste lote e deixa rastro de quem mudou.

    O cadastro mestre da pessoa não é tocado: o Portal não é dono dele, e uma
    digitação numa tela de planilha avulsa não pode virar verdade oficial.
    """
    numero = motor.normalizar_telefone(bruto)
    if not numero:
        raise UploadInvalido("Telefone inválido. Use o formato (DD) 9XXXX-XXXX.")

    colaborador.telefone_corrigido = numero
    colaborador.selecionado = True
    colaborador.save(update_fields=["telefone_corrigido", "selecionado"])

    registrar(
        colaborador.lote,
        AcaoPonto.ALTERACAO_TELEFONE,
        request,
        # O mascarado, nunca o número. A auditoria diz QUEM mudou e DE QUEM era
        # a linha; o número inteiro já está no campo, e repeti-lo aqui só
        # espalharia dado pessoal por mais uma tabela.
        f"{colaborador.nome} → {motor.mascarar_telefone(numero)}",
    )
    return numero


# ── Painel — §7 ─────────────────────────────────────────────────────


def resumo(lote: LotePonto) -> dict:
    """Os números do topo da tela. Sempre dos dados reais do lote."""
    colaboradores = list(lote.colaboradores.all())
    prontos = [c for c in colaboradores if c.pode_produzir]
    enviados = lote.envios.filter(situacao="enviado").count()

    return {
        "pendencias": sum(c.quantidade_pendencias for c in colaboradores),
        "colaboradores": len(colaboradores),
        "prontos": len(prontos),
        "com_erro": len(colaboradores) - len(prontos),
        "enviados": enviados,
    }
