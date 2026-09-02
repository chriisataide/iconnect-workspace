"""Os conectores — um por sistema de origem.

    conector_csv       o formato canônico; é o que a massa e a carga manual usam
    conector_sankhya   financeiro, contábil, folha e compras
    conector_monday    projetos, marcos e responsáveis
    conector_platform  contratos, vigência e satisfação de cliente

Todos implementam o mesmo protocolo (`base.Conector`) e **nenhum escreve no
banco**: quem grava é o carregador, uma vez só, do mesmo jeito para todos. Um
conector novo escreve `coletar` e `normalizar` e ganha idempotência, contagem,
registro de execução e resolução de conflito de graça.
"""

from .base import Conector, Janela, Registro
from .registro import conector_de, registrar

__all__ = ["Conector", "Janela", "Registro", "conector_de", "registrar"]


def semear() -> None:
    """Registra os quatro conectores. Chamado no `ready()` do app.

    Registrar TODOS, inclusive os sem credencial neste ambiente: `disponivel()`
    é quem responde por isso, e a diferença importa. Um conector ausente do
    registro diria "não há conector escrito para sankhya" — que é uma frase
    sobre o produto. `disponivel() == False` diz "falta configurar", que é uma
    frase sobre o ambiente, e é a verdadeira.
    """
    from .csv import ConectorCSV
    from .monday import ConectorMonday
    from .platform import ConectorPlatform
    from .sankhya import ConectorSankhya

    for conector in (ConectorCSV(), ConectorSankhya(), ConectorMonday(), ConectorPlatform()):
        try:
            registrar(conector)
        except ValueError:
            # Já registrado — `ready()` pode rodar mais de uma vez conforme o
            # servidor, e a segunda passada não pode derrubar a subida.
            continue
