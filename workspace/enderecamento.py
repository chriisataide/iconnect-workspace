"""O código da tela — o endereço estável de cada lugar do Workspace.

## Por que um número, se a tela já tem nome

Porque o nome muda e o endereço não pode mudar junto. "Suprimentos" já se
chamou Logística neste produto — o rótulo virou outro, e o domínio `log.`
continuou, exatamente pelo motivo que `modulos.py` explica: renomear a chave
seria migração de dados.

O código serve à conversa. "Abre a 02.3" é uma frase que atravessa e-mail,
WhatsApp e ata de reunião sem depender de a outra pessoa ter o mesmo menu
aberto — e sem depender de colar uma URL, que quebra quando a rota muda. É
vocabulário organizacional, e não enfeite: o benchmark do Portal GPS mostra a
empresa inteira conversando por número.

## Por que NÃO é um model

O impulso é criar `Modulo` no banco com `unique=True` no código. Seria errado
aqui, e por uma razão concreta: neste repositório módulo **não é dado**. É
`workspace/modulos.py`, uma tupla de dataclasses `frozen` montada no `ready()`,
e o launcher é um registro em memória. Pôr o código no banco criaria uma
segunda verdade sobre quais telas existem — a do código e a da tabela — e a
primeira divergência entre as duas seria um `/ir/` que aponta para uma rota que
ninguém escreveu.

A unicidade continua garantida por constraint. A constraint é só de outro tipo:
`registrar_tela()` recusa código repetido **na subida do processo**, como
`workspace.providers.registry` já faz com provider. É mais rígido que o `UNIQUE`
do banco, não menos — um `UNIQUE` só reprova no `INSERT`, e um código duplicado
escrito no fonte passaria pelo deploy inteiro até alguém tentar gravar.

O benchmark pede "unicidade garantida por constraint" porque a própria árvore
dele tem `08.2.4` e `05.6` duas vezes. Esta é a constraint desta arquitetura.

## A numeração

Três blocos, com folga entre eles para o que vier:

    0x   o que toda pessoa usa          (início, meu dia, serviços, acervo…)
    2x   os departamentos               (a fatia de catálogo de cada um)
    3x   administração e patrimônio     (papéis, estoque, custódia, frota)
    9x   o que leva à Platform          (chamados, campo)

O segundo nível é a tela dentro do assunto: `02` é Serviços, `02.2` é a bandeja
de aprovações. Um terceiro nível é aceito pelo formato e ainda não é usado —
ele existe para quando uma tela tiver recortes próprios, como a `02.1.4` do
benchmark.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass

from django.urls import NoReverseMatch, reverse

#: `NN`, `NN.N` ou `NN.N.N`. Dois dígitos no primeiro nível de propósito: com um
#: só, o décimo assunto obrigaria a renumerar os nove anteriores — e código que
#: renumera deixa de ser endereço.
FORMATO = re.compile(r"^\d{2}(\.\d{1,2}){0,2}$")


@dataclass(frozen=True)
class Tela:
    """Um lugar do Workspace que tem endereço.

    Só entra aqui o que é **destino**: uma página que se abre e onde se fica.
    Rota de ação (aprovar, cancelar, baixar anexo) fica de fora — ela não é
    lugar, é verbo, e dar endereço a ela produziria um `/ir/` que executa.
    """

    codigo: str
    nome: str
    url_name: str
    url_args: tuple = ()
    #: Chave do módulo a que a tela pertence, quando pertence a um. Vazio nas
    #: telas transversais. Serve à trilha, não ao roteamento.
    modulo: str = ""

    @property
    def url(self) -> str:
        """O caminho da tela, ou vazio quando a rota não existe mais.

        Vazio e não exceção: uma rota removida sem tirar o código daqui não pode
        derrubar a busca inteira, que é onde o `reverse()` acontece a cada tecla
        digitada. Quem consome trata o vazio; `test_todo_codigo_resolve` é quem
        reprova a inconsistência, na hora certa, que é a suíte.
        """
        try:
            return reverse(self.url_name, args=self.url_args)
        except NoReverseMatch:  # pragma: no cover - coberto pelo teste do registro
            return ""

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nome}"


_telas: dict[str, Tela] = {}
#: Memo de `por_caminho()`. Invalidado por `registrar_tela()` e por `limpar()`;
#: fora de teste, ninguém registra tela depois do `ready()`.
_por_caminho: dict[str, Tela] | None = None
_lock = threading.Lock()


class CodigoInvalido(ValueError):
    """Código fora do formato, ou já usado por outra tela."""


def registrar_tela(tela: Tela) -> Tela:
    """Registra uma tela. Código repetido levanta — no boot, não em produção.

    Registrar a **mesma** tela de novo é silêncio, e é de propósito: o `ready()`
    do Django pode rodar mais de uma vez conforme o servidor, e nesse caso a
    segunda passada não pode reprovar um código que ela mesma acabou de gravar.
    O que reprova é código igual apontando para tela **diferente**, que é o
    defeito de verdade — duas telas com o mesmo endereço significa que uma delas
    fica inalcançável, em silêncio.
    """
    global _por_caminho

    if not isinstance(tela, Tela):
        raise TypeError(f"{tela!r} não é uma Tela.")
    if not FORMATO.match(tela.codigo or ""):
        raise CodigoInvalido(
            f"{tela.codigo!r} não é um código válido. "
            "O formato é NN, NN.N ou NN.N.N — por exemplo 02, 02.3, 02.1.4."
        )
    if not tela.nome:
        raise CodigoInvalido(f"A tela {tela.codigo} precisa de `nome`.")
    if not tela.url_name:
        raise CodigoInvalido(f"A tela {tela.codigo} precisa de `url_name`.")

    with _lock:
        existente = _telas.get(tela.codigo)
        if existente is not None and existente != tela:
            raise CodigoInvalido(
                f"O código {tela.codigo!r} já é de {existente.nome!r} "
                f"({existente.url_name}). Códigos não se repetem: duas telas no "
                "mesmo endereço deixam uma delas inalcançável."
            )
        _telas[tela.codigo] = tela
        _por_caminho = None
    return tela


def por_codigo(codigo: str) -> Tela | None:
    """A tela desse código, ou None. Aceita espaço em volta e nada mais."""
    with _lock:
        return _telas.get((codigo or "").strip())


def por_caminho(caminho: str) -> Tela | None:
    """O código deste caminho — o inverso, para o cabeçalho da tela.

    Compara pelo CAMINHO e não pelo par (url_name, args), e a razão é concreta:
    `request.resolver_match` entrega `chave="rh"` em `kwargs`, enquanto a Tela
    declara `url_args` posicional, porque é o que `reverse()` consome. Casar os
    dois formatos exigiria adivinhar a ordem dos kwargs — e no dia em que uma
    rota tivesse dois, o cabeçalho mostraria o código errado em silêncio.

    O caminho já é único por definição. Memoizado porque isto roda em toda tela
    e um `reverse()` por Tela registrada seria trinta e seis por requisição.
    """
    global _por_caminho
    with _lock:
        if _por_caminho is None:
            _por_caminho = {t.url: t for t in _telas.values() if t.url}
        return _por_caminho.get(caminho or "")


def todas() -> list[Tela]:
    """Todas as telas com endereço, em ordem de código."""
    with _lock:
        return sorted(_telas.values(), key=lambda t: [int(p) for p in t.codigo.split(".")])


def limpar() -> None:
    """Esvazia o registro. Só para teste."""
    global _por_caminho
    with _lock:
        _telas.clear()
        _por_caminho = None


# ── As telas transversais ───────────────────────────────────────────
#
# As dos módulos NÃO estão aqui: elas vêm de `modulos.MODULOS`, para o código do
# tile e o da página serem a mesma verdade. É a mesma razão pela qual o launcher
# deriva os tiles de lá em vez de escrevê-los à mão.

TELAS: tuple[Tela, ...] = (
    Tela("00", "Início", "workspace:home"),
    Tela("00.1", "Ajuda", "workspace:ajuda"),
    Tela("01", "Meu dia", "workspace:meu_dia"),
    Tela("02", "Serviços", "workspace:servicos"),
    Tela("02.1", "Minhas solicitações", "workspace:minhas_solicitacoes"),
    Tela("02.2", "Aprovações", "workspace:aprovacoes"),
    Tela("02.3", "Fila de atendimento", "workspace:fila"),
    Tela("03.1", "Acervo normativo", "workspace:documentos"),
    Tela("04", "Comunicados e notícias", "workspace:publicacoes"),
    Tela("04.1", "Perguntas frequentes", "workspace:faq"),
    Tela("04.2", "Notificações", "workspace:notificacoes"),
    Tela("05.1", "Minhas reservas", "workspace:minhas_reservas"),
    Tela("07.1", "Trilhas e cursos", "workspace:universidade"),
    Tela("07.2", "Painel da Universidade", "workspace:universidade_painel"),
    Tela("08", "Indicadores", "workspace:indicadores"),
    # A tela que a diretoria pediu. `10` e NÃO `01.2`, que é o número dela no
    # Portal GPS: aqui `01` já é Meu dia, e renumerar um endereço é exatamente
    # o que o ADR-015 existe para impedir. Copiamos o padrão, não o número.
    Tela("10", "Resultados", "workspace:resultados"),
    Tela("11", "Exceções", "workspace:excecoes"),
    # A pauta da reunião como objeto do produto. `12` porque está livre e porque
    # ADR-015 proíbe renumerar depois — no Portal GPS este é o `01.01`, e aqui
    # `01` já é Meu dia.
    Tela("12", "Ciclos de planejamento", "workspace:ciclos"),
    # O limiar que gera obrigação — a regra dos 10% do benchmark,
    # generalizada. Vizinha da 11 de propósito: a exceção encontra, e a 13
    # é onde a resposta fica.
    Tela("13", "Planos de ação", "workspace:planos"),
    # O quadro de metas e o PDI. `14` e `14.1` porque são a MESMA
    # conversa em dois horizontes: o ciclo e a carreira.
    Tela("14", "Metas e avaliação", "workspace:metas"),
    Tela("14.1", "Plano de desenvolvimento", "workspace:desenvolvimento"),
    # O orçamento anual. `15` e não dentro de `08`: indicadores medem o
    # trabalho do produto, e orçamento é o dinheiro da empresa.
    Tela("15", "Orçamento", "workspace:orcamento"),
    # As duas que saíram de dentro da 10 em 04/09/2026. Códigos NOVOS e não
    # `10.1` e `10.2`: elas deixaram de ser parte da 10, e um código filho diria
    # que ainda são. ADR-015 proíbe renumerar depois — então é melhor errar para
    # o lado de dois códigos independentes.
    Tela("16", "Quadro e jornada", "workspace:quadro"),
    Tela("17", "Satisfação do cliente", "workspace:satisfacao"),
    Tela("09", "Relatórios", "workspace:relatorios"),
    Tela("26.1", "Marketing", "workspace:marketing"),
    Tela("30", "Pessoas e papéis", "workspace:pessoas"),
    Tela("31", "Estoque", "workspace:estoque"),
    Tela("32", "Custódia de equipamentos", "workspace:custodia"),
    Tela("33", "Frota", "workspace:frota"),
    Tela("34", "Candidaturas", "workspace:candidaturas"),
    Tela("90", "Chamados", "workspace:chamados"),
    Tela("91", "Campo", "workspace:campo"),
    # `99` espelhando de propósito o "99 – Manutenção · Monitoramento" do
    # benchmark: as telas que consertam o dado são um módulo DECLARADO, e não
    # um back-office escondido.
    Tela("99", "Fontes de dados", "workspace:fontes"),
)


def semear() -> None:
    """Carrega o registro. Chamado no `ready()` do app `workspace`.

    Os módulos primeiro: eles são os assuntos, e as telas transversais são
    recortes dentro deles. Se um módulo e uma tela brigarem por um código, é o
    módulo que está certo — mas o erro sobe de qualquer jeito, porque a briga é
    o defeito, não o desempate.
    """
    from workspace.modulos import MODULOS

    for modulo in MODULOS:
        # Módulo sem código ou sem rota não tem endereço — é o "em breve" da
        # home, e dar `/ir/` a ele levaria a lugar nenhum com cara de erro.
        if not modulo.codigo or not modulo.url_name:
            continue
        registrar_tela(
            Tela(
                codigo=modulo.codigo,
                nome=modulo.nome,
                url_name=modulo.url_name,
                url_args=modulo.url_args,
                modulo=modulo.chave,
            )
        )

    for tela in TELAS:
        registrar_tela(tela)
