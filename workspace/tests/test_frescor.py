"""O carimbo de frescor — de quando é este número.

Esta onda não traz nenhum dado de fora, e é por isso que estes testes existem
agora. O carimbo é uma disciplina, não uma funcionalidade: ele só vale se toda
faixa de números nascer carimbada, e a única forma de garantir isso é a suíte
reprovar a que nascer sem. Escrever o mecanismo depois do primeiro conector
significaria caçar carimbo em cada template já pronto.

Os três testes que mais protegem:

1. **Bloco novo nasce carimbado** — a estrutural, que casa `au-kpi-linha` com
   `_carimbo.html`. É a única que pega o defeito antes de alguém abrir a tela.
2. **Ninguém fabrica carimbo com o relógio** — um `{% now %}` no template diria
   "agora" para dado de ontem, que é a forma mais silenciosa de mentir.
3. **Fonte que falhou não zera o bloco** — o último dado bom continua na tela,
   com a idade em destaque. Zerar é dizer que a empresa parou.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.providers import frescor as contrato
from workspace.services import frescor as frs

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

#: A marca de uma faixa de números agregados no template. Ver `frescor.BLOCOS`.
LINHA_AGREGADA = "au-kpi-linha"


# ── As estruturais: bloco novo nasce carimbado ──────────────────────


def _templates():
    return sorted(TEMPLATES.rglob("*.html"))


def test_toda_faixa_de_numeros_agregados_tem_carimbo():
    """O teste que mais protege esta onda, e o único que age antes da tela.

    Casa a marca da faixa (`au-kpi-linha`) com o carimbo. Quem construir a
    próxima faixa de números descobre a obrigação aqui, e não na reunião em que
    alguém perguntar de quando é o número.
    """
    com_numeros, com_carimbo = set(), set()
    for caminho in _templates():
        texto = caminho.read_text(encoding="utf-8")
        if LINHA_AGREGADA in texto:
            com_numeros.add(caminho.name)
        if "_carimbo.html" in texto and caminho.name != "_carimbo.html":
            com_carimbo.add(caminho.name)

    assert com_numeros, "A marca da faixa agregada sumiu — o teste deixou de valer."
    assert com_numeros - com_carimbo == set(), (
        "Faixa de números sem carimbo: "
        f"{sorted(com_numeros - com_carimbo)}. "
        "Declare o bloco em `frescor.BLOCOS` e inclua `_carimbo.html`."
    )
    assert com_carimbo - com_numeros == set(), (
        "Carimbo em tela sem faixa agregada: "
        f"{sorted(com_carimbo - com_numeros)}. Carimbo sem número é ruído."
    )


def test_todo_carimbo_incluido_aponta_para_um_bloco_declarado():
    """`carimbos.panorama` só existe se `panorama` estiver em `BLOCOS`.

    Sem isto, um erro de digitação na chave renderizaria um carimbo vazio — e
    vazio parece "sem informação", não "template errado".
    """
    declaradas = {b.chave for blocos in frs.BLOCOS.values() for b in blocos}

    usadas = set()
    for caminho in _templates():
        usadas.update(
            re.findall(r'_carimbo\.html"\s+with\s+carimbo=carimbos\.(\w+)',
                       caminho.read_text(encoding="utf-8"))
        )

    assert usadas, "Nenhum template inclui o carimbo — o teste deixou de valer."
    assert usadas <= declaradas, f"Chaves não declaradas: {sorted(usadas - declaradas)}"


def test_nenhum_template_fabrica_carimbo_com_o_relogio():
    """`{% now %}` num template é um carimbo que diz "agora" para dado de ontem.

    A regra é dura de propósito — nenhuma ocorrência em template nenhum, nem
    fora de carimbo. Um "atualizado agora" no rodapé de uma tela de números é
    lido como carimbo por quem está na reunião, independentemente de onde o
    programador achou que estava pondo.
    """
    culpados = [
        c.relative_to(TEMPLATES).as_posix()
        for c in _templates()
        if "{% now" in c.read_text(encoding="utf-8")
    ]

    assert not culpados, (
        f"Template lendo o relógio: {culpados}. "
        "O instante vem do registro de carga — ver `workspace/services/frescor.py`."
    )


def test_a_marcacao_do_carimbo_mora_num_lugar_so():
    """Carimbo copiado à mão diverge na terceira tela.

    Se `au-carimbo` aparecer fora do parcial, é porque alguém montou o próprio —
    e o dele não vai ganhar o estado de alerta quando a fonte cair.
    """
    fora = [
        c.relative_to(TEMPLATES).as_posix()
        for c in _templates()
        if "au-carimbo" in c.read_text(encoding="utf-8") and c.name != "_carimbo.html"
    ]

    assert not fora, f"Marcação de carimbo fora do parcial: {fora}"


# ── A comportamental: o carimbo chega à resposta ────────────────────


def _indicadores(pessoa):
    f.atribuir(pessoa, f.papel("diretoria", ["ind.ler.global"], escopo="global"))


def _fila(pessoa):
    """A fila sai dos domínios que EXISTEM no catálogo, não da lista de módulos.

    Sem um item ativo em `com.`, a permissão de atender Compras não abre fila
    nenhuma — e a tela responde 403, corretamente.
    """
    from decimal import Decimal

    from workspace.models import GrupoCatalogo, ItemCatalogo
    from workspace.services import catalogo as svc

    item = ItemCatalogo.objects.create(
        chave="cadeira", nome="Cadeira", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="com.requisicao", prazo_prometido_dias=3,
        limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    f.atribuir(pessoa, f.papel("compras", ["com.atender.global"], escopo="global"))

    # Um pedido de verdade na fila. A faixa de números da fila só existe quando
    # há fila — o vazio dela é uma frase, não um zero —, e carimbar uma frase
    # seria o ruído que o próprio carimbo existe para evitar.
    quem_pede = f.pessoa("pede")
    f.lotar(quem_pede)
    svc.solicitar(item, quem_pede, {"o_que": "Cadeira nova"})


def _universidade(pessoa):
    f.atribuir(pessoa, f.papel("rh", ["hab.auditoria.ler.global"], escopo="global"))


def _bandeja(pessoa):
    """A bandeja abre para todo mundo — quem não decide nada a vê vazia.

    Decisão anterior do produto, e não descuido: esconder a porta faria a pessoa
    achar que o produto quebrou quando ela aprovasse o último pedido.
    """


#: Quem consegue abrir cada tela com bloco agregado. Todas as telas de
#: `frescor.BLOCOS` precisam estar aqui — o teste seguinte reprova a que faltar,
#: e é de propósito: tela de número agregado sem dono declarado é o defeito que
#: a leitura do benchmark marcou como "tela sem dono".
ACESSO = {
    "workspace:indicadores": _indicadores,
    "workspace:aprovacoes": _bandeja,
    "workspace:fila": _fila,
    "workspace:universidade_painel": _universidade,
}


def test_toda_tela_com_bloco_declara_quem_a_enxerga():
    assert set(ACESSO) == set(frs.BLOCOS), (
        "Tela com bloco agregado e sem acesso declarado neste teste: "
        f"{sorted(set(frs.BLOCOS) - set(ACESSO))}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", sorted(ACESSO))
def test_todo_bloco_declarado_aparece_carimbado_na_resposta(client, url_name):
    pessoa = f.pessoa("quem_ve")
    f.lotar(pessoa)
    ACESSO[url_name](pessoa)
    client.force_login(pessoa)

    conteudo = client.get(reverse(url_name)).content.decode()

    for bloco in frs.blocos_de(url_name):
        assert f'data-carimbo="{bloco.chave}"' in conteudo, (
            f"{url_name}: o bloco {bloco.chave!r} está declarado e não foi carimbado."
        )


@pytest.mark.django_db
def test_tela_sem_bloco_agregado_nao_ganha_carimbo(client):
    """A maioria das telas não tem número agregado, e não pode ganhar ruído."""
    conteudo = client.get(reverse("workspace:servicos")).content.decode()

    assert "data-carimbo" not in conteudo


# ── O serviço ───────────────────────────────────────────────────────


class _Provedor(contrato.ProvedorFrescor):
    key = "teste"

    def __init__(self, dto=None):
        self.dto = dto
        self.perguntas = []

    def carimbo(self, fonte, competencia=None):
        self.perguntas.append(fonte)
        return self.dto


@pytest.fixture
def sem_provedor():
    contrato.limpar()
    yield
    contrato.limpar()


def test_fonte_sem_provedor_diz_sem_registro_de_carga(sem_provedor):
    """O estado vazio é texto que explica o que falta, e não um espaço em branco.

    E vira alerta: um bloco cuja procedência ninguém sabe responder não é um
    bloco tranquilo — é um bloco que ainda não deveria estar na tela.
    """
    carimbo = frs.de("sankhya")

    assert not carimbo.conhecido
    assert carimbo.alerta
    assert "sem registro de carga" in carimbo.texto


def test_o_carimbo_nativo_nao_pergunta_ao_provedor(sem_provedor):
    """Dado do próprio Workspace é lido quando a tela abre — não há carga.

    Pôr um horário aqui faria o número nativo parecer ter carga, e convidaria a
    comparar a idade dele com a de uma fonte que tem.
    """
    provedor = _Provedor()
    contrato.registrar(provedor)

    carimbo = frs.de(frs.NATIVO)

    assert provedor.perguntas == []
    assert carimbo.texto == "Workspace · em tempo real"
    assert not carimbo.alerta


def test_fonte_que_falhou_vira_alerta_e_mantem_a_ultima_carga_boa(sem_provedor):
    """Falha de carga NUNCA zera o bloco.

    `carregado_em` é da última carga BEM-SUCEDIDA e continua valendo; `status`
    descreve a última tentativa. Os dois convivem — e é exatamente esse caso que
    a tela precisa mostrar: o dado bom, a idade e o motivo, juntos.
    """
    contrato.registrar(
        _Provedor(
            contrato.CarimboDTO(
                fonte="monday",
                rotulo="monday",
                janela="em tempo real",
                carregado_em=timezone.now() - timedelta(hours=30),
                status=contrato.FALHA,
                motivo="tempo esgotado ao coletar o board 4412",
            )
        )
    )

    carimbo = frs.de("monday")

    assert carimbo.alerta
    assert carimbo.motivo == "tempo esgotado ao coletar o board 4412"
    assert "há 30 h" in carimbo.texto


def test_fonte_dentro_da_idade_aceitavel_nao_alarma(sem_provedor):
    """A idade máxima é declarada pela FONTE, não pela tela.

    Seis horas é velho para o monday e é novo para a folha do Sankhya — uma
    constante única aqui alarmaria a metade errada da tela.
    """
    contrato.registrar(
        _Provedor(
            contrato.CarimboDTO(
                fonte="sankhya",
                rotulo="Sankhya",
                janela="competência AGO/2026",
                carregado_em=timezone.now() - timedelta(hours=6),
                idade_maxima=timedelta(hours=26),
            )
        )
    )

    carimbo = frs.de("sankhya")

    assert not carimbo.alerta
    assert carimbo.texto == "Sankhya · competência AGO/2026 · há 6 h"


def test_fonte_velha_demais_vira_alerta(sem_provedor):
    contrato.registrar(
        _Provedor(
            contrato.CarimboDTO(
                fonte="sankhya",
                rotulo="Sankhya",
                carregado_em=timezone.now() - timedelta(hours=40),
                idade_maxima=timedelta(hours=26),
            )
        )
    )

    assert frs.de("sankhya").alerta


@pytest.mark.parametrize(
    ("atras", "esperado"),
    [
        (timedelta(seconds=20), "agora há pouco"),
        (timedelta(minutes=4), "há 4 min"),
        (timedelta(hours=6), "há 6 h"),
        (timedelta(days=3), "há 3 dias"),
    ],
)
def test_a_idade_e_idade_e_nao_relogio(atras, esperado):
    """A pergunta diante do número é "isso está velho?".

    `18/08/2026 08:45` obriga cada leitor a fazer a subtração de cabeça — na
    reunião, com o número na tela.
    """
    assert frs._idade(timezone.now() - atras) == esperado


def test_relogio_adiantado_nao_vira_idade_negativa():
    """O servidor de carga pode estar adiantado. Melhor não afirmar nada do que
    afirmar "há -3 min"."""
    assert frs._idade(timezone.now() + timedelta(minutes=3)) == ""


def test_fonte_sem_idade_maxima_declarada_nunca_alarma(sem_provedor):
    """Fonte que não declara idade aceitável não tem como estar velha.

    Inventar um limite padrão aqui seria pior do que não alarmar: o padrão certo
    para a folha do Sankhya e para o monday não é o mesmo número, e um chute
    único faria metade das faixas piscarem vermelho sem motivo.
    """
    contrato.registrar(
        _Provedor(
            contrato.CarimboDTO(
                fonte="csv",
                rotulo="Carga manual",
                carregado_em=timezone.now() - timedelta(days=90),
            )
        )
    )

    assert not frs.de("csv").alerta


def test_carga_sem_instante_nao_inventa_idade(sem_provedor):
    """`carregado_em=None` é "nunca carregou", e não "carregou agora"."""
    contrato.registrar(
        _Provedor(contrato.CarimboDTO(fonte="csv", rotulo="Carga manual"))
    )

    assert frs.de("csv").idade == ""


def test_o_contrato_nasce_respondendo_none(sem_provedor):
    """A implementação padrão devolve `None` para qualquer fonte.

    É o que permite um domínio implementar só as fontes que ele carrega, sem
    escrever um `return None` para cada uma das outras.
    """

    class Mudo(contrato.ProvedorFrescor):
        key = "mudo"

    assert Mudo().carimbo("sankhya") is None


def test_provedor_precisa_herdar_do_contrato(sem_provedor):
    with pytest.raises(TypeError):
        contrato.registrar(object())


def test_provedor_precisa_declarar_chave(sem_provedor):
    """Sem `key`, o erro apareceria como "nenhum provedor registrado" — que é
    um sintoma muito longe da causa."""

    class SemChave(contrato.ProvedorFrescor):
        pass

    with pytest.raises(ValueError):
        contrato.registrar(SemChave())
