"""Fábricas mínimas para os testes de IDN.

Sem factory_boy de propósito: são 6 modelos com poucos campos, e a dependência
extra não se paga.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone

from identidade.models import (
    AtribuicaoPapel,
    Delegacao,
    Departamento,
    Lotacao,
    Papel,
    Unidade,
)


def pessoa(identificador: str, **kwargs):
    """Uma conta de teste. `identificador` pode ser um apelido ou um e-mail.

    Deriva o e-mail quando recebe apelido — `pessoa("ana")` vira
    `ana@icodev.com.br`. Isso mantém os ~200 chamadores desta fábrica intactos
    depois de o identificador da conta passar de `username` para e-mail, e é o
    motivo de a troca de modelo de usuário ter custado uma função e não uma
    varredura na suíte.
    """
    Pessoa = get_user_model()
    email = (
        identificador
        if "@" in identificador
        else f"{identificador}@icodev.com.br"
    )
    return Pessoa.objects.create_user(email, password="x", **kwargs)


def unidade(codigo="SP", nome="Matriz SP") -> Unidade:
    return Unidade.objects.create(codigo=codigo, nome=nome)


def departamento(codigo="TI", nome="Tecnologia") -> Departamento:
    return Departamento.objects.create(codigo=codigo, nome=nome)


def lotar(user, gestor=None, uni=None, dep=None, **kwargs) -> Lotacao:
    return Lotacao.objects.create(
        user=user, gestor=gestor, unidade=uni, departamento=dep, **kwargs
    )


def papel(chave, permissoes, escopo="proprio", ativo=True) -> Papel:
    return Papel.objects.create(
        chave=chave, nome=chave.title(), permissoes=permissoes,
        escopo_padrao=escopo, ativo=ativo,
    )


def atribuir(user, pap, escopo=None, uni=None, dep=None, inicio=None, fim=None) -> AtribuicaoPapel:
    return AtribuicaoPapel.objects.create(
        user=user,
        papel=pap,
        escopo=escopo or pap.escopo_padrao,
        unidade=uni,
        departamento=dep,
        vigencia_inicio=inicio or timezone.localdate(),
        vigencia_fim=fim,
    )


def delegar(de, para, inicio, fim, papeis=(), ativa=True) -> Delegacao:
    d = Delegacao.objects.create(
        de_user=de, para_user=para, inicio=inicio, fim=fim, ativa=ativa
    )
    if papeis:
        d.papeis.set(papeis)
    return d
