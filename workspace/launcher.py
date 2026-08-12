"""App Launcher — o catálogo de sistemas que o Workspace apresenta.

Etapa 5 §5.9: nada de lista fixa em template. Cada aplicação declara o que
expõe, e o Workspace só ordena e renderiza.

Um app real se registra no `ready()` do próprio AppConfig:

    # fsm/apps.py
    def ready(self):
        from workspace.launcher import registrar_app, AppSpec
        registrar_app(AppSpec(chave="fsm", nome="Field Service", ...))

Enquanto os sistemas não existem, o Workspace semeia o catálogo com os destinos
do diagrama (`catalogo_semente()`). Cada app que nascer substitui a sua entrada
registrando a própria — a semente some sozinha.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class AppSpec:
    """Uma aplicação no launcher do Workspace."""

    chave: str
    nome: str
    descricao: str = ""
    icone: str = "grid"
    # `None` = sistema ainda não existe. O tile aparece marcado "em breve",
    # em vez de sumir: o Workspace comunica o roadmap, não esconde.
    url_name: str | None = None
    # Argumentos posicionais do `reverse()`. Existe porque a página de módulo é
    # uma rota só, parametrizada pela chave (`workspace:modulo` + `("rh",)`) —
    # sem isto, cada módulo precisaria da sua própria entrada em `urls.py`.
    url_args: tuple = ()
    url_direta: str | None = None
    # `None` = visível para todos, inclusive anônimo. Quando IDN existir
    # (ST-014), o Workspace filtra com pode(pessoa, permissao).
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

    `pessoa=None` é o acesso anônimo do Workspace — devolve só o que não exige
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
    """Os destinos da faixa Aplicativos do Workspace.

    Os tiles de departamento são derivados de `workspace.modulos.MODULOS` e não
    escritos à mão aqui: o tile e a página do módulo têm de ser a mesma verdade,
    senão volta o bug que este arquivo já teve — mapa que não leva a lugar
    nenhum. Módulo sem fatia de catálogo continua "em breve".

    `iconnect` é o único destino externo: leva ao login da Platform. `helpdesk`
    fica sem página de propósito — chamado se abre lá, e uma segunda fila aqui
    seria duas verdades sobre o mesmo chamado.
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
            nome="iConnect Platform",
            descricao="Chamados, ordens de serviço, clientes e contratos",
            icone="cube",
            url_direta="/login/",
            # SEM `destaque` e com ordem alta, de propósito.
            #
            # Até 12/08/2026 este tile era o herói da home: primeiro, com borda
            # de marca. Isso dizia ao colaborador que o Workspace existe para
            # levá-lo ao iConnect. São dois produtos — o Workspace organiza a
            # vida corporativa, a Platform organiza o atendimento ao cliente —
            # e aqui a Platform é um destino entre outros.
            #
            # A relação de PROVEDOR é outra coisa e continua: o `dashboard`
            # alimenta o Workspace com orçamento e realizado via
            # `workspace/providers/`. Tile não é a única ponte entre os dois.
            #
            # Ordem 110/120: as duas entradas que levam à Platform ficam juntas
            # no fim da faixa. Com dez tiles numa grade sem rolagem, a posição é
            # sinal fraco — o que importa é não ter borda de marca.
            ordem=110,
        ),
        AppSpec(
            chave="helpdesk",
            nome="HelpDesk",
            descricao="Chamados — abre dentro do iConnect Platform",
            icone="ticket",
            ordem=120,
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
