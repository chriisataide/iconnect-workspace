"""O frescor das fontes — o contrato que a Onda 1 deixou vazio.

Registrado por `cargas` e não por `resultados` porque a pergunta é *quando a
fonte carregou pela última vez*, e quem sabe isso é quem carrega. O espelho não
sabe sequer que existe uma execução.

Com este provider registrado, o carimbo do bloco passa a dizer
"Sankhya · competência AGO/2026 · há 6 h" — **sem nenhuma view mudar**. Era esse
o ponto de o contrato existir antes do primeiro conector.
"""

from __future__ import annotations

from workspace.providers.frescor import (
    FALHA,
    PARCIAL,
    SUCESSO,
    CarimboDTO,
    DivergenciaDTO,
    ExecucaoDTO,
    FonteDTO,
    ProvedorFrescor,
)

from .conectores import conector_de
from .models import Divergencia, ExecucaoCarga, FonteDados, StatusCarga

#: `StatusCarga` do banco → vocabulário do contrato. Um dicionário e não um
#: `if`: o dia em que aparecer um status novo, a tradução falta em UM lugar e o
#: `.get()` cai no padrão, em vez de o carimbo mentir "sucesso".
STATUS = {
    StatusCarga.SUCESSO: SUCESSO,
    StatusCarga.PARCIAL: PARCIAL,
    StatusCarga.FALHA: FALHA,
    StatusCarga.EM_ANDAMENTO: SUCESSO,
}


class FrescorDasCargas(ProvedorFrescor):
    key = "cargas"

    def carimbo(self, fonte: str, competencia=None) -> CarimboDTO | None:
        registro = FonteDados.objects.filter(chave=fonte).first()
        if registro is None:
            # `None` = "não sei nada sobre esta fonte", que é diferente de
            # "a fonte falhou". O serviço traduz isso em "sem registro de carga".
            return None

        # A última carga BEM-SUCEDIDA data o dado que está na tela; a última
        # TENTATIVA diz se a fonte está de pé agora. As duas convivem, e é
        # justamente esse caso que a tela precisa mostrar: dado bom de seis
        # horas atrás, com um aviso de que a carga das 3h falhou.
        boa = registro.ultima_boa
        tentativa = registro.ultima_tentativa

        status = SUCESSO
        motivo = ""
        if tentativa is not None and tentativa.status in (
            StatusCarga.FALHA, StatusCarga.PARCIAL
        ):
            status = STATUS.get(tentativa.status, FALHA)
            motivo = tentativa.erro_resumo

        return CarimboDTO(
            fonte=registro.chave,
            rotulo=registro.nome or registro.chave,
            janela=_janela(competencia, registro),
            carregado_em=boa.terminada_em if boa else None,
            status=status,
            idade_maxima=registro.idade_maxima_aceitavel,
            motivo=motivo,
        )


    # ── A tela de fontes (99) ───────────────────────────────────────

    def fontes(self) -> list[FonteDTO]:
        return [
            FonteDTO(
                chave=fonte.chave,
                nome=fonte.nome,
                ativa=fonte.ativa,
                cadencia=fonte.cadencia_esperada,
                idade_maxima=fonte.idade_maxima_aceitavel,
                responsavel=fonte.responsavel_tecnico,
                observacao=fonte.observacao,
                configurada=_configurada(fonte.chave),
            )
            for fonte in FonteDados.objects.order_by("nome")
        ]

    def historico(self, fonte: str = "", limite: int = 10) -> list[ExecucaoDTO]:
        consulta = ExecucaoCarga.objects.select_related("fonte")
        if fonte:
            consulta = consulta.filter(fonte__chave=fonte)
        return [
            ExecucaoDTO(
                fonte=execucao.fonte.chave,
                iniciada_em=execucao.iniciada_em,
                terminada_em=execucao.terminada_em,
                status=STATUS.get(execucao.status, FALHA),
                lidos=execucao.lidos,
                criados=execucao.criados,
                atualizados=execucao.atualizados,
                ignorados=execucao.ignorados,
                rejeitados=execucao.rejeitados,
                erro_resumo=execucao.erro_resumo,
                simulacao=execucao.simulacao,
            )
            for execucao in consulta.order_by("-iniciada_em")[:limite]
        ]

    def divergencias(self, *, abertas: bool = True) -> list[DivergenciaDTO]:
        consulta = Divergencia.objects.all()
        if abertas:
            consulta = consulta.filter(resolvida_em__isnull=True)
        return [
            DivergenciaDTO(
                entidade=d.entidade,
                chave=d.chave_externa,
                campo=d.campo,
                fonte_a=d.fonte_a,
                valor_a=d.valor_a,
                fonte_b=d.fonte_b,
                valor_b=d.valor_b,
                vencedora=d.fonte_vencedora,
                detectada_em=d.detectada_em,
                resolvida=d.resolvida_em is not None,
            )
            for d in consulta.order_by("-detectada_em")[:100]
        ]

    def recarregar(self, fonte: str, quem=None) -> bool:
        """Dispara a carga SÍNCRONA da fonte.

        Síncrona porque não há fila de tarefas neste produto, e inventar uma
        para um botão seria trocar um problema conhecido — a pessoa espera — por
        um desconhecido: uma tarefa que falha em silêncio num worker que
        ninguém observa.

        A janela fica aberta de propósito: quem aperta o botão está consertando
        alguma coisa, e estreitar a janela por ele traria menos do que ele
        espera.
        """
        from .carregador import CargaError, carregar

        registro = FonteDados.objects.filter(chave=fonte, ativa=True).first()
        if registro is None or conector_de(fonte) is None:
            return False
        try:
            resultado = carregar(fonte, aplicar=True)
        except CargaError:
            # A carga já registrou a execução com o motivo. Devolver `False`
            # faz a tela dizer que não deu, sem inventar uma segunda mensagem.
            return False

        # O STATUS, e não "não estourou".
        #
        # `carregar()` engole `FonteNaoConfigurada` de propósito: sem credencial
        # é estado normal, e a execução fica registrada como falha em vez de
        # subir exceção. Quem só olhasse a exceção — como esta função fazia —
        # diria "carga concluída" para uma fonte que nem tentou.
        #
        # Parcial conta como concluída: veio parte, e o que veio é bom.
        return resultado.status in (StatusCarga.SUCESSO, StatusCarga.PARCIAL)


def _janela(competencia, registro) -> str:
    """A janela do dado, na língua de quem lê.

    Quando a tela pede uma competência, ela é a janela — "competência AGO/2026"
    diz mais do que qualquer descrição de cadência. Sem competência, vale a
    cadência que a fonte prometeu cumprir.
    """
    if competencia is not None:
        meses = (
            "JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
            "JUL", "AGO", "SET", "OUT", "NOV", "DEZ",
        )
        return f"competência {meses[competencia.month - 1]}/{competencia.year}"
    return registro.cadencia_esperada or ""


def _configurada(chave: str) -> bool:
    """Se há credencial para esta fonte NESTE ambiente.

    Pergunta ao conector, e não ao banco: a credencial mora em variável de
    ambiente, e o banco não tem como saber se ela está preenchida.
    """
    conector = conector_de(chave)
    if conector is None:
        return False
    try:
        return bool(conector.disponivel())
    except Exception:
        # Um conector que estoura ao se auto-examinar não pode derrubar a tela
        # que existe justamente para mostrar que ele está com problema.
        return False
