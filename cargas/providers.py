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
    ProvedorFrescor,
)

from .models import FonteDados, StatusCarga

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
