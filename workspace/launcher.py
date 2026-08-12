"""App Launcher — o catálogo de sistemas que o Portal apresenta.

Etapa 5 §5.9: nada de lista fixa em template. Cada aplicação declara o que
expõe, e o Portal só ordena e renderiza.

Um app real se registra no `ready()` do próprio AppConfig:

    # fsm/apps.py
    def ready(self):
        from workspace.launcher import registrar_app, AppSpec
        registrar_app(AppSpec(chave="fsm", nome="Field Service", ...))

Enquanto os sistemas não existem, o Portal semeia o catálogo com os destinos
do diagrama (`catalogo_semente()`). Cada app que nascer substitui a sua entrada
registrando a própria — a semente some sozinha.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class AppSpec:
    """Uma aplicação no launcher do Portal."""

    chave: str
    nome: str
    descricao: str = ""
    icone: str = "grid"
    # `None` = sistema ainda não existe. O tile aparece marcado "em breve",
    # em vez de sumir: o Portal comunica o roadmap, não esconde.
    url_name: str | None = None
    # Argumentos posicionais do `reverse()`. Existe porque a página de módulo é
    # uma rota só, parametrizada pela chave (`workspace:modulo` + `("rh",)`) —
    # sem isto, cada módulo precisaria da sua própria entrada em `urls.py`.
    url_args: tuple = ()
    url_direta: str | None = None
    # `None` = visível para todos, inclusive anônimo. Quando IDN existir
    # (ST-014), o Portal filtra com pode(pessoa, permissao).
    permissao: str | None = None
    cor: str = "var(--au-neutral-text)"
    cor_bg: str = "var(--au-neutral-bg)"
    ordem: int = 100
    destaque: bool = False

    @property
    def disponivel(self) -> bool:
        return bool(self.url_name or self.url_direta)


_apps: dict[str, AppSpec] = {}
_lock = threading.Lock()


def registrar_app(spec: AppSpec, *, substituir: bool = True) -> AppSpec:
    """Registra (ou substitui) uma aplicação no launcher.

    `substituir=True` é o padrão porque o caso normal é justamente um app real
    tomando o lugar da sua entrada de semente.
    """
    if not isinstance(spec, AppSpec):
        raise TypeError(f"{spec!r} não é um AppSpec.")
    if not spec.chave:
        raise ValueError("AppSpec precisa de `chave`.")
    with _lock:
        if spec.chave in _apps and not substituir:
            raise ValueError(f"Já existe app com a chave {spec.chave!r}.")
        _apps[spec.chave] = spec
    return spec


def apps_disponiveis(pessoa=None) -> list[AppSpec]:
    """Apps que esta pessoa pode ver, ordenados.

    `pessoa=None` é o acesso anônimo do Portal — devolve só o que não exige
    permissão. O filtro real por papel entra quando `pode()` existir (ST-014);
    até lá, qualquer app com `permissao` definida fica fora do anônimo.
    """
    with _lock:
        todos = list(_apps.values())

    visiveis = [
        spec
        for spec in todos
        if spec.permissao is None or (pessoa is not None and _pode_ver(pessoa, spec))
    ]
    # Disponível antes de "em breve"; depois `ordem`; depois nome, para a
    # ordenação não depender da ordem de import dos apps.
    return sorted(visiveis, key=lambda s: (not s.disponivel, s.ordem, s.nome))


def _pode_ver(pessoa, spec: AppSpec) -> bool:
    """Ponto de extensão do ST-014. Hoje nega o que exige permissão.

    Negar é o padrão certo enquanto `pode()` não existe: liberar por omissão
    é como portal corporativo vaza tela de RH para estagiário.
    """
    return False


def limpar() -> None:
    """Esvazia o catálogo. Só para teste."""
    with _lock:
        _apps.clear()


def catalogo_semente() -> list[AppSpec]:
    """Os destinos do diagrama do Portal.

    Os tiles de departamento são derivados de `workspace.modulos.MODULOS` e não
    escritos à mão aqui: o tile e a página do módulo têm de ser a mesma verdade,
    senão volta o bug que este arquivo já teve — mapa que não leva a lugar
    nenhum. Módulo sem fatia de catálogo continua "em breve".

    `iconnect` é o único destino externo: leva ao login do sistema principal.
    `helpdesk` fica sem página de propósito — chamado se abre no iConnect.
    """
    from workspace.modulos import MODULOS

    modulos = [
        AppSpec(
            chave=modulo.chave,
            nome=modulo.nome,
            descricao=modulo.descricao,
            icone=modulo.icone,
            url_name="workspace:modulo" if modulo.tem_catalogo else None,
            url_args=(modulo.chave,) if modulo.tem_catalogo else (),
            ordem=modulo.ordem,
        )
        for modulo in MODULOS
    ]

    return modulos + [
        AppSpec(
            chave="iconnect",
            nome="iConnect",
            descricao="Sistema principal — chamados, campo, clientes",
            icone="cube",
            url_direta="/login/",
            cor="var(--au-accent-text)",
            cor_bg="var(--au-accent-bg)",
            ordem=10,
            destaque=True,
        ),
        AppSpec(
            chave="helpdesk",
            nome="HelpDesk",
            descricao="Abertura e acompanhamento de chamados",
            icone="ticket",
            ordem=20,
        ),
    ]


def semear() -> None:
    """Carrega a semente. Chamado no `ready()` do app `workspace`.

    Usa `substituir=False` e engole a colisão: se um app real já se registrou,
    ele vence — a semente nunca sobrescreve o de verdade.
    """
    for spec in catalogo_semente():
        try:
            registrar_app(spec, substituir=False)
        except ValueError:
            continue
