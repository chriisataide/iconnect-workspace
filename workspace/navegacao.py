"""Os grupos do trilho — e qual deles abre em cada tela.

## O problema, medido

O trilho é filtrado por permissão, e para quase todo mundo ele é curto:

    colaborador    11 itens   maior grupo: Consultar (6)
    gestor         15 itens   maior grupo: Consultar (6)
    diretoria      28 itens   maior grupo: **Acompanhar (14)**

Ou seja: o trilho não estava errado — um grupo estava. "Acompanhar" tinha
virado o depósito de tudo o que não era pedir, atender ou aprovar, e para quem
tem todas as permissões ele sozinho era metade da navegação.

## As duas mudanças, e por que nessa ordem

**Dividir** vem primeiro: catorze itens sob um verbo genérico não melhoram por
serem escondidos. "Resultados da empresa" e "Gestão" são perguntas diferentes —
a primeira é o que a empresa produziu, a segunda é como a empresa se organiza —
e quem abre uma raramente quer a outra na mesma sessão.

**Recolher** vem depois: com os grupos separados, mostrar só o da tela atual
deixa de esconder informação e passa a mostrar contexto. Aberto por padrão só o
grupo em que a pessoa está.

## Por que `url_name` e não a variável `aba` do template

`aba` é preenchida por cada view, e "cada view lembra" é a mesma aposta que já
fez a topbar perder o sino uma vez. O `resolver_match` está na requisição e não
depende de ninguém lembrar: rota nova sem entrada aqui cai no grupo nenhum, e o
trilho abre no padrão — nunca quebra.
"""

from __future__ import annotations

from django.http import HttpRequest

#: `url_name` → grupo. A ordem das chaves não importa; a ordem dos grupos no
#: trilho é a do template, que é a ordem em que se deve olhar.
GRUPO_POR_ROTA: dict[str, str] = {
    # HOJE — o que exige você agora.
    "meu_dia": "hoje",
    "notificacoes": "hoje",
    # CONSULTAR — o que já existe e você só precisa ler.
    "metas": "consultar",
    "desenvolvimento": "consultar",
    "documentacao": "consultar",
    "documento": "consultar",
    "relatorios": "consultar",
    "reservas": "consultar",
    "minhas_reservas": "consultar",
    "correspondencias": "consultar",
    "custodia": "consultar",
    # A Universidade é do COLABORADOR, não de quem administra — e o comentário
    # dela no trilho já dizia isso desde sempre. Ela vivia solta entre dois
    # grupos, sem pertencer a nenhum.
    "universidade": "consultar",
    # PEDIR
    "servicos": "pedir",
    "pedir": "pedir",
    "minhas_solicitacoes": "pedir",
    "solicitacao": "pedir",
    # RESULTADOS DA EMPRESA — o que a empresa produziu, e o que saiu da linha.
    "indicadores": "resultados",
    "ciclos": "resultados",
    "ciclo": "resultados",
    "excecoes": "resultados",
    "planos": "resultados",
    "plano": "resultados",
    "orcamento": "resultados",
    "orcamento_centro": "resultados",
    "painel": "resultados",
    "resultados": "resultados",
    "resultados_detalhe": "resultados",
    "resultados_pdf": "resultados",
    "fontes": "resultados",
    "quadro": "resultados",
    "satisfacao": "resultados",
    # GESTÃO — como a empresa se organiza e o que ela publica.
    "pessoas": "gestao",
    "publicacoes": "gestao",
    "publicacao": "gestao",
    "faq": "gestao",
    "candidaturas": "gestao",
    "marketing": "gestao",
    "documentos": "gestao",
    # ATENDER
    "fila": "atender",
    "estoque": "atender",
    "frota": "atender",
    # APROVAR
    "aprovacoes": "aprovar",
}


def grupo_aberto(request: HttpRequest) -> dict:
    """Qual grupo do trilho nasce aberto nesta tela.

    Context processor pela mesma razão do `rail()`: o trilho está em toda tela,
    e depender de cada view lembrar garante que uma esqueça.

    Devolve `""` para rota desconhecida — e aí nenhum grupo abre sozinho, que é
    o pior caso aceitável: a pessoa clica no grupo que quer. O caso inaceitável
    seria um erro, e por isso não há `KeyError` aqui.
    """
    if not request.path.startswith("/workspace/"):
        return {}

    match = getattr(request, "resolver_match", None)
    nome = getattr(match, "url_name", "") or ""
    return {"grupo_aberto": GRUPO_POR_ROTA.get(nome, "")}
