"""Trilha de segurança — quem entrou, quem falhou, quem mudou o quê.

## O que a auditoria de agosto encontrou

Nada. Nenhum evento de autenticação era registrado em lugar nenhum: nem entrada,
nem saída, nem falha de senha, nem concessão de papel. O `LOGGING` de produção
existia e o único logger nomeado era `workspace`, para avisar quando um provider
degradava.

O efeito prático de não ter isto aparece uma vez só, e é sempre tarde: alguém
pergunta "quem aprovou esse pagamento em março?" ou "essa conta foi usada de
onde?", e a resposta é que não dá para saber. Freio de força bruta sem log é uma
tranca sem olho mágico — ela barra, e ninguém fica sabendo que alguém tentou.

## A regra que não se quebra

**Nunca senha, nunca token, nunca segredo.** O sinal `user_login_failed` do
Django entrega `credentials` já higienizado (`_clean_credentials` troca a senha
por `********`), mas aqui nem isso é usado: o que vai para a linha é o e-mail
tentado e a origem, e mais nada. Um log de segurança que vaza credencial é uma
segunda cópia do problema que ele deveria ajudar a investigar.

## Por que e-mail e IP entram, apesar da LGPD

Os dois são dado pessoal e vão para o log de propósito. A base legal é o
legítimo interesse de segurança da informação, e a finalidade é exatamente o que
está escrito aqui — não há campo livre, não há corpo de requisição, não há
formulário. Retenção fica em `docs/EXEC_14_SEGURANCA.md`; o que este arquivo
garante é a MINIMIZAÇÃO: o mínimo que responde "quem, o quê, de onde, quando".

## Por que `logging` e não uma tabela

Tabela de auditoria dentro do mesmo banco que se está auditando é apagável por
quem tem acesso ao banco — que é justamente quem se quer auditar. Linha em
`stdout` sai do processo e vai para onde a infraestrutura decidir, que é o
lugar certo para ela. As trilhas de NEGÓCIO — quem aprovou, quem concedeu papel
— continuam em tabela (`EventoSolicitacao`, `AtribuicaoPapel.concedido_por`),
porque essas o produto precisa MOSTRAR, e não só guardar.
"""

from __future__ import annotations

import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)

#: Logger próprio para que a infraestrutura possa mandar segurança para um
#: destino diferente do resto — retenção e acesso a este fluxo são outros.
logger = logging.getLogger("seguranca")


def _origem(request) -> str:
    if request is None:
        return "-"
    return request.META.get("REMOTE_ADDR", "") or "-"


def _quem(user) -> str:
    """O identificador da conta. Nunca o objeto inteiro.

    `repr(user)` levaria o nome completo e o que mais o `__str__` decidir
    carregar amanhã — e o log passaria a crescer em dado pessoal sem que
    ninguém tivesse decidido isso.
    """
    return getattr(user, "email", "") or "-"


def ao_entrar(sender, request, user, **kwargs) -> None:
    logger.info("entrada ok conta=%s origem=%s", _quem(user), _origem(request))


def ao_sair(sender, request, user, **kwargs) -> None:
    # `user` é `None` quando a sessão já tinha expirado — sair de uma sessão
    # morta é evento normal e não merece linha diferente.
    logger.info("saida conta=%s origem=%s", _quem(user), _origem(request))


def ao_falhar(sender, credentials, request=None, **kwargs) -> None:
    """Falha de senha.

    `warning` e não `info`: é o evento que se procura depois. E só o e-mail
    tentado sai daqui — `credentials` inteiro traria qualquer campo que um
    backend de autenticação futuro resolvesse acrescentar.
    """
    tentado = (credentials or {}).get("username") or "-"
    logger.warning("entrada falhou conta=%s origem=%s", tentado, _origem(request))


def bloqueio_por_tentativas(email: str, origem: str, porta: str) -> None:
    """O freio barrou alguém. Chamado por `contas.entrada`.

    Separado da falha comum porque a pergunta é outra: cinco falhas é gente
    esquecendo a senha, o bloqueio repetido é alguém insistindo. Sem esta linha,
    o freio barra em silêncio e ninguém descobre que houve tentativa.
    """
    logger.warning(
        "entrada bloqueada conta=%s origem=%s porta=%s", email or "-", origem, porta
    )


def evento(acao: str, quem, **detalhes) -> None:
    """Um ato administrativo. `quem` é a pessoa que agiu.

    Usado pelas mudanças que alteram o alcance de alguém — conceder e encerrar
    papel, mudar centro de custo. São as alterações que ninguém vê acontecer e
    que mudam o que uma pessoa alcança no dia seguinte.
    """
    extras = " ".join(f"{chave}={valor}" for chave, valor in sorted(detalhes.items()))
    logger.info("%s por=%s %s", acao, _quem(quem), extras)


def conectar() -> None:
    """Liga os ouvintes. Chamado no `ready()` de `contas`."""
    user_logged_in.connect(ao_entrar, dispatch_uid="contas.auditoria.entrada")
    user_logged_out.connect(ao_sair, dispatch_uid="contas.auditoria.saida")
    user_login_failed.connect(ao_falhar, dispatch_uid="contas.auditoria.falha")
