"""Como o `MONDAY_BOARDS` do settings fica, a partir do inventário.

Este arquivo é DOCUMENTAÇÃO, não configuração: ele não é importado por nada. O
valor real vai no settings do ambiente, com os ids da conta da ADB — que saem de
`python scripts/inventario_monday.py --com-amostra`.

Os ids abaixo são os da amostra anonimizada em `monday-inventario-exemplo.json`.
"""

MONDAY_BOARDS = {
    # A chave é a ENTIDADE do espelho — a mesma string que o carregador usa
    # para achar o model. Ver `cargas/carregador.py::ENTIDADES`.
    "projeto": {
        "board": 1000000001,
        # campo do espelho → id da coluna no monday.
        #
        # O id, e não o título: título é o que se renomeia numa terça-feira,
        # e o id é o que a API garante. Foi assim que o benchmark acabou com
        # `08.2.4` duas vezes — vocabulário sem chave estável.
        "colunas": {
            "situacao": "status",
            "responsavel": "person",
            "prazo": "date4",
            "percentual_concluido": "numeros",
            "contrato": "conexao_contrato",
            # `espelho_cliente` é MIRROR e NÃO entra: mirror às vezes vem vazio
            # na API mesmo aparecendo na tela, e um campo que zera sozinho é
            # pior que um campo ausente. O nome do cliente vem do contrato.
        },
    },
    "marco": {
        "board": 1000000002,
        "colunas": {
            "projeto": "conexao_projeto",
            "prazo": "date_prazo",
            "concluido_em": "date_conclusao",
            "responsavel": "person",
        },
    },
}
