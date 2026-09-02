"""O ciclo de planejamento — a pauta como objeto do produto.

Os três que mais protegem esta onda:

1. **A ATA repete o carimbo do dia, e não o de hoje.** Uma ATA que recalculasse
   o frescor diria, seis meses depois, que a decisão foi tomada diante de um
   dado de hoje. Ela foi tomada diante de um dado de três dias atrás — e é
   exatamente isso que uma auditoria procura.
2. **A fronteira passa entre o GET e o POST.** Ler a pauta é consulta; abrir,
   anotar e fechar é assinar em nome da reunião.
3. **Fonte atrasada não impede a reunião e não some da ATA.** Travar
   transformaria um problema de carga num problema de governança; esconder faria
   a sala decidir sem saber com que dado.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models.ciclo import (
    AnotacaoEtapa,
    CicloPlanejamento,
    EtapaCiclo,
    OcorrenciaCiclo,
    SituacaoOcorrencia,
)
from workspace.models.conteudo import Documento, TipoDocumento
from workspace.providers import frescor as contrato
from workspace.services import ciclos as svc

pytestmark = pytest.mark.django_db


# ── Cenário ─────────────────────────────────────────────────────────


@pytest.fixture
def pauta(db):
    call_command("semear_ciclos", "--aplicar", verbosity=0)
    return CicloPlanejamento.objects.get(chave="mensal")


def _com_papel(apelido, chave_do_papel, permissoes=()):
    pessoa = f.pessoa(apelido, nome=apelido.title())
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel(chave_do_papel, list(permissoes), escopo="global"),
        escopo="global",
    )
    return pessoa


@pytest.fixture
def condutor(db):
    return _com_papel(
        "diretor", "diretoria", ["cic.ler.global", "cic.conduzir.global"]
    )


@pytest.fixture
def plateia(db):
    """Lê e NÃO conduz — é esta pessoa que prova onde está a fronteira."""
    return _com_papel("gerente", "gestor", ["cic.ler.departamento"])


class _FonteFalsa:
    """Um provedor de frescor de mentira, para o teste mandar na idade do dado.

    Implementa só `carimbo`: é o único método que a pauta consulta. Registrar um
    provedor inteiro para exercitar um campo faria o teste falhar no dia em que
    o contrato ganhasse um método que esta onda não usa.
    """

    def __init__(self, carregado_em, status="sucesso", motivo=""):
        self.carregado_em = carregado_em
        self.status = status
        self.motivo = motivo

    def carimbo(self, fonte, competencia=None):
        return contrato.CarimboDTO(
            fonte=fonte,
            rotulo=fonte,
            janela="",
            carregado_em=self.carregado_em,
            status=self.status,
            motivo=self.motivo,
            idade_maxima=timedelta(hours=26),
        )


@pytest.fixture
def com_fonte_atrasada(monkeypatch):
    """A tela 10 passa a ter um bloco cuja carga é de três dias atrás."""
    from workspace.services import frescor as fr

    monkeypatch.setitem(
        fr.BLOCOS,
        "workspace:resultados",
        (fr.BlocoAgregado("economico", "Resultado", fonte="sankhya"),),
    )
    velho = _FonteFalsa(timezone.now() - timedelta(days=3))
    monkeypatch.setattr(contrato, "obter", lambda: velho)
    return velho


# ── 1. A ATA congela o carimbo ──────────────────────────────────────


def test_a_ata_repete_o_carimbo_do_dia_e_nao_o_de_hoje(
    pauta, condutor, com_fonte_atrasada, monkeypatch
):
    """O teste que justifica a onda inteira.

    A anotação nasce com "há 72 h" ao lado. Uma semana depois a carga voltou a
    ser recente — e a ATA continua dizendo "há 72 h", porque é isso que a sala
    viu quando decidiu. Recalcular reescreveria a história para melhor, que é a
    direção em que ninguém percebe.
    """
    from workspace.services import frescor as fr

    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    etapa = pauta.etapas.get(codigo="CP01")

    anotacao = svc.anotar(
        ocorrencia, etapa, condutor, texto="Margem do CT-100 abaixo de 10%."
    )
    congelado = anotacao.carimbo_texto
    assert "há 3 dias" in congelado, congelado
    assert anotacao.carimbo_alerta is True

    documento = svc.fechar(ocorrencia, condutor)
    assert congelado in documento.corpo

    # Agora a carga volta a ser recente. Nada na ATA pode mudar.
    monkeypatch.setattr(contrato, "obter", lambda: _FonteFalsa(timezone.now()))
    agora = fr.de("sankhya")
    assert "há 3 dias" not in agora.texto, "o cenário precisa ter mudado de verdade"

    documento.refresh_from_db()
    anotacao.refresh_from_db()
    assert congelado in documento.corpo
    assert anotacao.carimbo_texto == congelado


def test_o_carimbo_congelado_nao_e_recalculado_ao_reler_a_tela(
    pauta, condutor, com_fonte_atrasada, client
):
    """A tela lê o campo, e não o contrato. É o mesmo defeito por outra porta."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    etapa = pauta.etapas.get(codigo="CP01")
    svc.anotar(ocorrencia, etapa, condutor, texto="Decidido diante de dado velho.")

    AnotacaoEtapa.objects.update(carimbo_texto="sankhya · há 999 h")

    client.force_login(condutor)
    resposta = client.get(
        reverse("workspace:ciclo_competencia",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 9}),
        {"etapa": "CP01"},
    )
    assert b"h\xc3\xa1 999 h" in resposta.content


# ── 2. A fronteira passa entre o GET e o POST ───────────────────────


def test_a_fronteira_passa_entre_o_get_e_o_post(pauta, plateia, client):
    """Quem lê a pauta não abre a reunião, não anota e não fecha a ATA."""
    pauta.papeis_leitores = ["gestor"]
    pauta.save(update_fields=["papeis_leitores"])
    client.force_login(plateia)

    consulta = client.get(reverse("workspace:ciclo", kwargs={"chave": "mensal"}))
    assert consulta.status_code == 200
    assert b"CP01" in consulta.content

    apresentando = client.get(
        reverse("workspace:ciclo", kwargs={"chave": "mensal"}),
        {"etapa": "CP03", "apresentacao": "1"},
    )
    assert apresentando.status_code == 200

    for nome in ("abrir_ciclo", "fechar_ciclo", "anotar_etapa"):
        resposta = client.post(
            reverse(f"workspace:{nome}",
                    kwargs={"chave": "mensal", "ano": 2026, "mes": 9}),
            {"texto": "de nome de quem?"},
        )
        assert resposta.status_code == 403, nome


def test_o_anonimo_nao_le_a_pauta(pauta, client):
    """Ciclo de planejamento não é informação institucional: é a agenda de
    decisão da empresa, com o que ainda não foi decidido dentro."""
    resposta = client.get(reverse("workspace:ciclos"))
    assert resposta.status_code == 302
    assert "/entrar/" in resposta["Location"]


def test_quem_nao_participa_de_ciclo_nenhum_recebe_403(pauta, client):
    """403, e nunca lista vazia. Lista vazia diria "a empresa não tem ciclo de
    planejamento" para quem apenas não está na sala."""
    de_fora = _com_papel("almoxarife", "estoque", ["est.ler.global"])
    client.force_login(de_fora)

    assert client.get(reverse("workspace:ciclos")).status_code == 403


def test_ciclo_sem_plateia_nao_e_de_todo_mundo(pauta, plateia, client):
    """O padrão errado num campo em branco é o defeito que ninguém vê.

    Plateia vazia quer dizer "só quem tem `cic.ler.global`", e não "aberto".
    """
    pauta.papeis_leitores = []
    pauta.papel_condutor = ""
    pauta.save(update_fields=["papeis_leitores", "papel_condutor"])

    assert svc.pode_ler(pauta, plateia) is False


def test_o_condutor_conduz_e_a_plateia_le(pauta, condutor, plateia):
    pauta.papeis_leitores = ["gestor"]
    pauta.save(update_fields=["papeis_leitores"])

    assert svc.pode_ler(pauta, plateia) is True
    assert svc.pode_conduzir(pauta, plateia) is False
    assert svc.pode_conduzir(pauta, condutor) is True


def test_anotar_em_etapa_de_outro_ciclo_nao_atravessa(pauta, condutor, client):
    """O IDOR pela porta do formulário: um `pk` de etapa de outra pauta."""
    outro = CicloPlanejamento.objects.get(chave="trimestral")
    alheia = outro.etapas.first()
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)

    client.force_login(condutor)
    resposta = client.post(
        reverse("workspace:anotar_etapa",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 9}),
        {"etapa": alheia.pk, "texto": "escrevendo na pauta do vizinho"},
    )

    assert resposta.status_code == 404
    assert ocorrencia.anotacoes.count() == 0


# ── 3. Fonte atrasada não impede a reunião ──────────────────────────


def test_fonte_atrasada_nao_impede_a_reuniao_e_nao_some_da_ata(
    pauta, condutor, com_fonte_atrasada
):
    """Travar transformaria um problema de carga num problema de governança.

    O primeiro POST recusa e devolve a lista; o segundo abre. E o que a sala não
    tinha fica escrito na ocorrência e na ATA — congelado, para que o mês ruim
    não pareça limpo depois que a carga voltar.
    """
    with pytest.raises(svc.CicloError) as recusa:
        svc.abrir(pauta, condutor, 2026, 9)
    assert recusa.value.impedimentos, "a lista viaja com a exceção"

    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    assert ocorrencia.impedimentos
    assert ocorrencia.impedimentos[0]["etapa"] == "CP01"

    documento = svc.fechar(ocorrencia, condutor)
    assert "Fontes com atraso na abertura" in documento.corpo
    assert "CP01" in documento.corpo


def test_o_impedimento_congelado_nao_some_quando_a_carga_volta(
    pauta, condutor, com_fonte_atrasada, monkeypatch
):
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    congelados = list(ocorrencia.impedimentos)

    monkeypatch.setattr(contrato, "obter", lambda: _FonteFalsa(timezone.now()))
    contexto = svc.tela_do_ciclo(pauta, condutor, ano=2026, mes=9)

    assert contexto["impedimentos"] == congelados
    assert contexto["impedimentos_congelados"] is True


def test_sem_reuniao_aberta_a_conferencia_e_a_de_agora(
    pauta, condutor, com_fonte_atrasada
):
    """Antes de abrir não há o que congelar: a lista é a de agora, e ela existe
    justamente para que ninguém abra sem ver."""
    contexto = svc.tela_do_ciclo(pauta, condutor, ano=2026, mes=9)

    assert contexto["impedimentos"]
    assert contexto["impedimentos_congelados"] is False


def test_fonte_sem_carga_nenhuma_tambem_e_impedimento(pauta, condutor, monkeypatch):
    """"Sem registro de carga" é diferente de "atualizado", e as duas são
    diferentes de um bloco vazio — restrição 6, na pauta."""
    from workspace.services import frescor as fr

    monkeypatch.setitem(
        fr.BLOCOS,
        "workspace:resultados",
        (fr.BlocoAgregado("economico", "Resultado", fonte="sankhya"),),
    )
    monkeypatch.setattr(contrato, "obter", lambda: None)

    impedimentos = svc.conferir(pauta)

    assert impedimentos
    assert "Nenhuma carga registrada." in impedimentos[0]["motivo"]


# ── A ATA ───────────────────────────────────────────────────────────


def test_a_ata_nasce_no_acervo_com_a_plateia_do_ciclo(pauta, condutor):
    """`papel:<chave>` é sujeito de ACL: vitrine, busca e leitura direta
    concordam sem nenhuma exceção dentro do app de conteúdo."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)

    documento = svc.fechar(ocorrencia, condutor)

    assert documento.tipo == TipoDocumento.ATA
    assert "*" not in documento.publico_alvo, "ATA pública seria ATA para o anônimo"
    assert "papel:diretoria" in documento.publico_alvo
    assert documento.leitura_obrigatoria is False


def test_fechar_duas_vezes_nao_gera_duas_atas(pauta, condutor):
    """Duas ATAs da mesma reunião é a pior ambiguidade possível: as duas parecem
    oficiais."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)

    primeira = svc.fechar(ocorrencia, condutor)
    ocorrencia.refresh_from_db()
    segunda = svc.fechar(ocorrencia, condutor)

    assert primeira.pk == segunda.pk
    assert Documento.objects.filter(tipo=TipoDocumento.ATA).count() == 1


def test_reuniao_fechada_nao_recebe_anotacao(pauta, condutor):
    """ATA não recebe emenda silenciosa. Corrigir é assunto da reunião seguinte,
    onde fica visível."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    svc.fechar(ocorrencia, condutor)
    ocorrencia.refresh_from_db()

    with pytest.raises(svc.CicloError):
        svc.anotar(
            ocorrencia, pauta.etapas.first(), condutor, texto="depois de fechada"
        )


def test_a_ata_escreve_etapa_sem_anotacao_em_vez_de_omitir(pauta, condutor):
    """Etapa que some da ATA deixa a dúvida entre "não foi apresentada" e "não
    teve registro" — e as duas pedem coisas diferentes na reunião seguinte."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)

    corpo = svc.fechar(ocorrencia, condutor).corpo

    assert corpo.count("Sem anotação.") == pauta.etapas.count()


def test_a_ata_carrega_o_encaminhamento_em_destaque(pauta, condutor):
    """O que ficou de fazer é a única parte da ATA que gera trabalho."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    svc.anotar(
        ocorrencia,
        pauta.etapas.get(codigo="CP02"),
        condutor,
        texto="Duas regras dispararam.",
        encaminhamento="R.H. conclui as lotações sem centro de custo",
        prazo=timezone.localdate() + timedelta(days=15),
    )

    corpo = svc.fechar(ocorrencia, condutor).corpo

    assert "**Encaminhamento:** R.H. conclui as lotações" in corpo


def test_a_ata_nao_se_escreve_a_mao_pela_redacao(pauta, condutor):
    """Uma ATA escrita à mão ficaria no acervo indistinguível da verdadeira — e
    é a verdadeira que alguém vai citar numa auditoria."""
    from workspace.services import conteudo as cnt

    redator = _com_papel("redator", "rh", ["doc.publicar.assunto", "rh.ler.global"])

    with pytest.raises(cnt.DocumentoError):
        cnt.salvar(
            redator, None, slug="", titulo="ATA de mentira",
            tipo=TipoDocumento.ATA, publicar=True,
        )


def test_a_ata_e_lida_por_quem_participa_do_ciclo(pauta, condutor, plateia, client):
    pauta.papeis_leitores = ["diretoria", "gestor"]
    pauta.save(update_fields=["papeis_leitores"])
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    documento = svc.fechar(ocorrencia, condutor)

    client.force_login(plateia)
    resposta = client.get(
        reverse("workspace:documento", kwargs={"slug": documento.slug})
    )

    assert resposta.status_code == 200


def test_a_ata_nao_e_lida_por_quem_esta_fora_da_plateia(pauta, condutor, client):
    pauta.papeis_leitores = ["diretoria"]
    pauta.save(update_fields=["papeis_leitores"])
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    documento = svc.fechar(ocorrencia, condutor)

    de_fora = _com_papel("almoxarife", "estoque", ["est.ler.global"])
    client.force_login(de_fora)
    resposta = client.get(
        reverse("workspace:documento", kwargs={"slug": documento.slug})
    )

    assert resposta.status_code in (403, 404)


# ── A pauta ─────────────────────────────────────────────────────────


def test_a_etapa_aponta_para_um_codigo_e_o_endereco_resolve(pauta):
    """Código e não URL: no dia em que a rota mudar, uma pauta com URL vira uma
    lista de links quebrados — durante a reunião. ADR-029."""
    passo = next(p for p in svc.pauta(pauta) if p.codigo == "CP01")

    assert passo.etapa.tela == "10"
    assert passo.endereco_conhecido is True
    assert passo.url == reverse("workspace:resultados")


def test_etapa_com_codigo_que_nao_existe_mais_nao_quebra_a_pauta(pauta, condutor, client):
    """A etapa continua legível. A tela diz "endereço desconhecido" em vez de
    oferecer um link para lugar nenhum."""
    EtapaCiclo.objects.filter(ciclo=pauta, codigo="CP01").update(tela="77")

    passo = next(p for p in svc.pauta(pauta) if p.codigo == "CP01")
    assert passo.endereco_conhecido is False
    assert passo.url == ""

    client.force_login(condutor)
    resposta = client.get(
        reverse("workspace:ciclo", kwargs={"chave": "mensal"}), {"etapa": "CP01"}
    )
    assert resposta.status_code == 200
    assert "não existe mais no endereçamento" in resposta.content.decode()


def test_etapa_sem_tela_nao_ganha_carimbo_inventado(pauta):
    """Inventar "em tempo real" para uma etapa de fala ensinaria a ler o carimbo
    como enfeite — e ele existe para ser lido onde muda a decisão."""
    passo = next(p for p in svc.pauta(pauta) if p.codigo == "CP12")

    assert passo.etapa.tela == ""
    assert passo.carimbos == ()
    assert passo.carimbo is None


def test_etapa_desconhecida_na_url_cai_no_primeiro_passo(pauta, condutor):
    """No meio de uma reunião, um erro de digitação não pode virar uma tela de
    erro projetada na parede."""
    contexto = svc.tela_do_ciclo(pauta, condutor, codigo_da_etapa="CP99")

    assert contexto["passo"].codigo == "CP01"


def test_a_apresentacao_tira_o_trilho_do_html_e_nao_o_esconde(pauta, condutor, client):
    """ADR-025. `display:none` deixaria a navegação no HTML, e o leitor de tela
    leria uma navegação que ninguém pode ver."""
    client.force_login(condutor)
    url = reverse("workspace:ciclo", kwargs={"chave": "mensal"})

    normal = client.get(url, {"etapa": "CP01"}).content.decode()
    apresentando = client.get(
        url, {"etapa": "CP01", "apresentacao": "1"}
    ).content.decode()

    assert "au-rail-item" in normal
    assert "au-rail-item" not in apresentando
    assert "CP01" in apresentando


# ── A semeadora ─────────────────────────────────────────────────────


def test_a_semeadora_e_idempotente(pauta):
    """Rodar de novo no deploy seguinte não pode reescrever a pauta."""
    antes = list(EtapaCiclo.objects.values_list("pk", "codigo", "titulo"))

    call_command("semear_ciclos", "--aplicar", verbosity=0)

    assert list(EtapaCiclo.objects.values_list("pk", "codigo", "titulo")) == antes


def test_a_simulacao_nao_grava(db):
    call_command("semear_ciclos", verbosity=0)

    assert CicloPlanejamento.objects.count() == 0


def test_o_trimestral_e_um_subconjunto_do_mensal(pauta):
    """Mesma biblioteca de telas, recorte diferente por público. Duas pautas
    independentes divergiriam."""
    mensal = set(pauta.etapas.values_list("codigo", flat=True))
    trimestral = set(
        CicloPlanejamento.objects.get(chave="trimestral")
        .etapas.values_list("codigo", flat=True)
    )

    assert trimestral < mensal


def test_toda_etapa_semeada_aponta_para_um_endereco_que_existe(pauta):
    """O defeito que este teste pega: alguém acrescenta uma etapa apontando para
    um código que nunca existiu, e a pauta só revela isso na reunião."""
    orfas = [
        p.codigo
        for c in CicloPlanejamento.objects.all()
        for p in svc.pauta(c)
        if p.etapa.tela and not p.endereco_conhecido
    ]

    assert orfas == []


# ── O trilho e o panorama ───────────────────────────────────────────


def test_o_trilho_so_mostra_ciclos_para_quem_participa(pauta, plateia, client):
    pauta.papeis_leitores = ["gestor"]
    pauta.save(update_fields=["papeis_leitores"])

    client.force_login(plateia)
    with_acesso = client.get(reverse("workspace:ciclos")).content.decode()
    assert "Ciclos de planejamento" in with_acesso

    de_fora = _com_papel("almoxarife", "estoque", ["est.ler.global"])
    client.force_login(de_fora)
    home = client.get(reverse("workspace:servicos")).content.decode()
    assert "workspace:ciclos" not in home
    assert "/workspace/ciclos/" not in home


def test_a_lista_separa_as_reunioes_abertas(pauta, condutor, client):
    """Uma reunião aberta há três semanas é a única coisa nesta tela que pede
    ação hoje."""
    svc.abrir(pauta, condutor, 2026, 9, confirmado=True)

    client.force_login(condutor)
    conteudo = client.get(reverse("workspace:ciclos")).content.decode()

    assert "Reuniões abertas" in conteudo
    assert "09/2026" in conteudo


def test_abrir_e_idempotente(pauta, condutor):
    primeira = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    segunda = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)

    assert primeira.pk == segunda.pk
    assert OcorrenciaCiclo.objects.count() == 1


def test_competencia_fora_do_calendario_nao_abre(pauta, condutor, client):
    client.force_login(condutor)
    resposta = client.post(
        reverse("workspace:abrir_ciclo",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 13})
    )

    assert resposta.status_code == 404
    assert OcorrenciaCiclo.objects.count() == 0


def test_anotacao_vazia_nao_entra(pauta, condutor):
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)

    with pytest.raises(svc.CicloError):
        svc.anotar(ocorrencia, pauta.etapas.first(), condutor, texto="   ")


def test_o_post_de_anotar_volta_para_a_mesma_etapa(pauta, condutor, client):
    """Devolver a pauta inteira no meio da reunião faria quem conduz procurar o
    lugar de novo, com a sala esperando."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    etapa = pauta.etapas.get(codigo="CP05")

    client.force_login(condutor)
    resposta = client.post(
        reverse("workspace:anotar_etapa",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 9}),
        {"etapa": etapa.pk, "texto": "três pedidos parados", "apresentacao": "1"},
    )

    assert resposta.status_code == 302
    assert "etapa=CP05" in resposta["Location"]
    assert "apresentacao=1" in resposta["Location"]
    assert ocorrencia.anotacoes.count() == 1


def test_fechar_ciclo_sem_plateia_recusa_em_vez_de_publicar(pauta, condutor):
    """Sem plateia, o documento nasceria público — e público inclui o anônimo."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    pauta.papeis_leitores = []
    pauta.papel_condutor = ""
    pauta.save(update_fields=["papeis_leitores", "papel_condutor"])
    ocorrencia.refresh_from_db()

    with pytest.raises(svc.CicloError):
        svc.fechar(ocorrencia, condutor)

    ocorrencia.refresh_from_db()
    assert ocorrencia.situacao == SituacaoOcorrencia.ABERTA
    assert Documento.objects.filter(tipo=TipoDocumento.ATA).count() == 0


# ── Os POSTs pela view ──────────────────────────────────────────────
#
# Os testes acima chamam o serviço direto, que é onde a regra mora. Estes
# atravessam a view, que é onde a regra vira produto: a mensagem que a pessoa
# lê, o lugar para onde ela volta e o que acontece quando o formulário chega
# torto. Um serviço certo atrás de uma view que engole a exceção é um defeito
# que nenhum teste de unidade encontra.


def _mensagens(resposta):
    return [str(m) for m in resposta.wsgi_request._messages]


def test_o_botao_de_abrir_recusa_a_primeira_vez_e_avisa_de_cada_fonte(
    pauta, condutor, com_fonte_atrasada, client
):
    """A lista de impedimentos vira aviso na tela, um por fonte — e não uma
    frase única dizendo "há problemas", que não diz qual."""
    client.force_login(condutor)
    url = reverse("workspace:abrir_ciclo",
                  kwargs={"chave": "mensal", "ano": 2026, "mes": 9})

    recusa = client.post(url, follow=True)

    assert OcorrenciaCiclo.objects.count() == 0
    conteudo = recusa.content.decode()
    assert "CP01" in conteudo
    assert "fonte" in conteudo.lower()

    aberta = client.post(url, {"confirmar": "1"}, follow=True)

    assert OcorrenciaCiclo.objects.count() == 1
    assert "Reunião de 09/2026 aberta." in aberta.content.decode()


def test_abrir_sem_impedimento_nao_pede_confirmacao(pauta, condutor, client):
    """Confirmação que aparece sempre é confirmação que ninguém lê."""
    client.force_login(condutor)

    resposta = client.post(
        reverse("workspace:abrir_ciclo",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 9}),
        follow=True,
    )

    assert OcorrenciaCiclo.objects.count() == 1
    assert "aberta" in resposta.content.decode()


def test_fechar_pela_view_leva_para_a_ata(pauta, condutor, client):
    """Fechar termina NA ATA, e não de volta na pauta: o produto do ato é o
    documento, e quem fecha quer conferi-lo antes de mandar o link."""
    svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    client.force_login(condutor)

    resposta = client.post(
        reverse("workspace:fechar_ciclo",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 9})
    )

    documento = Documento.objects.get(tipo=TipoDocumento.ATA)
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse(
        "workspace:documento", kwargs={"slug": documento.slug}
    )


def test_fechar_sem_plateia_volta_com_o_motivo_na_tela(pauta, condutor, client):
    """A recusa é uma mensagem, e não um 500: quem fecha precisa saber que falta
    declarar a plateia, e não que "algo deu errado"."""
    svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    CicloPlanejamento.objects.filter(chave="mensal").update(
        papeis_leitores=[], papel_condutor=""
    )
    condutor.is_superuser = True  # sem papel, `cic.conduzir.global` já não alcança
    condutor.save(update_fields=["is_superuser"])
    client.force_login(condutor)

    resposta = client.post(
        reverse("workspace:fechar_ciclo",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 9}),
        follow=True,
    )

    assert Documento.objects.filter(tipo=TipoDocumento.ATA).count() == 0
    assert "não declara quem lê a ATA" in resposta.content.decode()


def test_fechar_reuniao_que_nunca_abriu_da_404(pauta, condutor, client):
    client.force_login(condutor)

    resposta = client.post(
        reverse("workspace:fechar_ciclo",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 8})
    )

    assert resposta.status_code == 404


def test_anotar_em_reuniao_que_nunca_abriu_da_404(pauta, condutor, client):
    client.force_login(condutor)

    resposta = client.post(
        reverse("workspace:anotar_etapa",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 8}),
        {"etapa": pauta.etapas.first().pk, "texto": "em reunião que não existe"},
    )

    assert resposta.status_code == 404


def test_prazo_invalido_avisa_e_anota_mesmo_assim(pauta, condutor, client):
    """Perder a anotação por causa do campo de data seria o pior desfecho: o
    texto é o que a reunião produziu, e a data é o acessório."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    client.force_login(condutor)

    resposta = client.post(
        reverse("workspace:anotar_etapa",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 9}),
        {
            "etapa": pauta.etapas.get(codigo="CP02").pk,
            "texto": "duas regras dispararam",
            "encaminhamento": "R.H. conclui as lotações",
            "prazo": "31/02/2026",
        },
        follow=True,
    )

    anotacao = ocorrencia.anotacoes.get()
    assert anotacao.prazo is None
    assert anotacao.encaminhamento == "R.H. conclui as lotações"
    assert "Data de prazo inválida" in resposta.content.decode()


def test_anotacao_vazia_pela_view_volta_com_o_motivo(pauta, condutor, client):
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    client.force_login(condutor)

    resposta = client.post(
        reverse("workspace:anotar_etapa",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 9}),
        {"etapa": pauta.etapas.first().pk, "texto": "   "},
        follow=True,
    )

    assert ocorrencia.anotacoes.count() == 0
    assert "A anotação está vazia." in resposta.content.decode()


def test_o_prazo_valido_entra(pauta, condutor, client):
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    client.force_login(condutor)

    client.post(
        reverse("workspace:anotar_etapa",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 9}),
        {
            "etapa": pauta.etapas.first().pk,
            "texto": "com prazo",
            "prazo": "2026-10-15",
        },
    )

    assert str(ocorrencia.anotacoes.get().prazo) == "2026-10-15"


def test_ciclo_desligado_nao_abre_nem_para_quem_conduz(pauta, condutor, client):
    """Desligar um ciclo é decisão de quem opera. A tela some para todo mundo —
    inclusive para quem conduzia, senão o desligamento não é desligamento."""
    CicloPlanejamento.objects.filter(chave="mensal").update(ativo=False)
    client.force_login(condutor)

    resposta = client.get(reverse("workspace:ciclo", kwargs={"chave": "mensal"}))

    assert resposta.status_code == 404


def test_quem_le_um_ciclo_nao_le_o_outro(pauta, plateia, client):
    """A plateia do trimestral é menor, e é a diferença que o benchmark faz
    entre os dois ciclos."""
    pauta.papeis_leitores = ["gestor"]
    pauta.save(update_fields=["papeis_leitores"])
    CicloPlanejamento.objects.filter(chave="trimestral").update(
        papeis_leitores=["diretoria"], papel_condutor=""
    )
    client.force_login(plateia)

    assert client.get(
        reverse("workspace:ciclo", kwargs={"chave": "mensal"})
    ).status_code == 200
    assert client.get(
        reverse("workspace:ciclo", kwargs={"chave": "trimestral"})
    ).status_code == 403


def test_a_competencia_da_url_manda_na_tela(pauta, condutor, client):
    """A competência é endereço, e não query string: a reunião de 09/2026 é um
    link que se manda por mensagem, e `?ano=` é o que alguém trunca ao copiar."""
    svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    client.force_login(condutor)

    resposta = client.get(
        reverse("workspace:ciclo_competencia",
                kwargs={"chave": "mensal", "ano": 2026, "mes": 9})
    )

    assert resposta.status_code == 200
    assert "09/2026" in resposta.content.decode()


# ── As bordas ───────────────────────────────────────────────────────


def test_anonimo_nao_tem_papel_nenhum(pauta):
    from django.contrib.auth.models import AnonymousUser

    assert svc.papeis_de(AnonymousUser()) == set()
    assert svc.pode_ler(pauta, AnonymousUser()) is False
    assert svc.pode_conduzir(pauta, AnonymousUser()) is False


def test_quem_nao_tem_a_permissao_nao_conduz_nem_com_o_papel(pauta):
    """O papel diz QUAL ciclo; a permissão diz SE conduz. Sem as duas, não.

    Sem esta separação, dar o papel `diretoria` a alguém por outro motivo — uma
    delegação de férias, por exemplo — passaria junto o direito de assinar ATA.
    """
    so_o_papel = _com_papel("assessor", "diretoria", ["rh.ler.global"])

    assert svc.pode_conduzir(pauta, so_o_papel) is False
    assert svc.pode_ler(pauta, so_o_papel) is False


def test_ciclo_sem_condutor_declarado_nao_e_conduzido_por_quem_passou_perto(pauta):
    """Escopo `.departamento` sem `papel_condutor` no ciclo não conduz nada."""
    quase = _com_papel("coordenador", "gestor", ["cic.conduzir.departamento"])
    pauta.papel_condutor = ""
    pauta.save(update_fields=["papel_condutor"])

    assert svc.pode_conduzir(pauta, quase) is False


def test_o_condutor_por_papel_conduz_sem_escopo_global(pauta):
    """`cic.conduzir.departamento` + o papel do ciclo é o caminho normal — o
    escopo global é o atalho da diretoria, e não a única porta."""
    dono = _com_papel("diretor_regional", "diretoria",
                      ["cic.ler.departamento", "cic.conduzir.departamento"])

    assert svc.pode_conduzir(pauta, dono) is True


def test_sem_a_permissao_de_ler_a_lista_e_403(pauta):
    sem_nada = _com_papel("visitante", "colaborador", [])

    with pytest.raises(svc.SemCiclos):
        svc.ciclos_de(sem_nada)


def test_ata_orfa_continua_legivel_pelo_publico_alvo(pauta, condutor, client):
    """Ciclo apagado leva a ocorrência junto. Negar a leitura trancaria no
    acervo um documento que ninguém mais poderia reabrir."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    documento = svc.fechar(ocorrencia, condutor)
    pauta.delete()

    assert svc.pode_ler_ata(documento, condutor) is True
    client.force_login(condutor)
    assert client.get(
        reverse("workspace:documento", kwargs={"slug": documento.slug})
    ).status_code == 200


def test_abrir_sem_conduzir_levanta_no_servico(pauta, plateia):
    """A view checa antes, e o serviço checa de novo. Duas trancas na mesma
    porta porque a segunda é a que vale quando alguém escrever a terceira view."""
    with pytest.raises(svc.CicloError):
        svc.abrir(pauta, plateia, 2026, 9, confirmado=True)


def test_anotar_e_fechar_sem_conduzir_levantam_no_servico(pauta, condutor, plateia):
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)

    with pytest.raises(svc.CicloError):
        svc.anotar(ocorrencia, pauta.etapas.first(), plateia, texto="de quem?")
    with pytest.raises(svc.CicloError):
        svc.fechar(ocorrencia, plateia)


def test_mes_fora_do_calendario_nao_abre_nem_pelo_servico(pauta, condutor):
    with pytest.raises(svc.CicloError):
        svc.abrir(pauta, condutor, 2026, 13, confirmado=True)


def test_a_ata_desvia_o_endereco_quando_ele_ja_esta_ocupado(pauta, condutor):
    """Só acontece com ciclo apagado e recriado com a mesma chave. Vale um
    sufixo: a reunião aconteceu, e recusar a ATA perderia o registro dela por
    causa de um endereço."""
    Documento.objects.create(
        slug="ata-mensal-2026-09", tipo=TipoDocumento.POP, titulo="ocupando o lugar",
        dono=condutor, versao="1",
    )
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)

    documento = svc.fechar(ocorrencia, condutor)

    assert documento.slug == "ata-mensal-2026-09-2"


def test_a_semeadora_corrige_o_texto_de_uma_etapa_alterada(pauta):
    """Ela garante que as etapas DECLARADAS existem com o texto certo — é o que
    faz uma correção de pergunta chegar sem alguém reescrever doze linhas."""
    EtapaCiclo.objects.filter(ciclo=pauta, codigo="CP01").update(
        titulo="alterado à mão", pergunta="", ordem=999
    )

    call_command("semear_ciclos", "--aplicar", verbosity=0)

    etapa = EtapaCiclo.objects.get(ciclo=pauta, codigo="CP01")
    assert etapa.titulo == "Resultado do mês"
    assert etapa.ordem == 10
    assert etapa.pergunta


def test_a_semeadora_corrige_a_plateia_e_nao_religa_o_ciclo(pauta):
    """`ativo` fica de fora: desligar é o freio de quem opera, e a semeadora
    roda no deploy seguinte — que é quando desfazer isso seria pior."""
    CicloPlanejamento.objects.filter(chave="mensal").update(
        ativo=False, papeis_leitores=["ninguem"]
    )

    call_command("semear_ciclos", "--aplicar", verbosity=0)

    ciclo = CicloPlanejamento.objects.get(chave="mensal")
    assert ciclo.ativo is False
    assert "diretoria" in ciclo.papeis_leitores


def test_quem_tem_a_permissao_e_nao_esta_em_plateia_nenhuma_recebe_403(pauta):
    """A permissão abre a porta; a plateia diz em qual sala se entra. Ter a
    primeira sem a segunda é 403, e não uma lista vazia."""
    CicloPlanejamento.objects.all().update(
        papeis_leitores=["diretoria"], papel_condutor="diretoria"
    )
    de_outra_sala = _com_papel("gerente_de_obra", "gestor", ["cic.ler.departamento"])

    with pytest.raises(svc.SemCiclos):
        svc.ciclos_de(de_outra_sala)


def test_etapa_opcional_com_fonte_atrasada_nao_vira_impedimento(
    pauta, com_fonte_atrasada
):
    """A conferência olha as OBRIGATÓRIAS. Uma etapa opcional atrasada não
    segura a abertura — senão "opcional" não queria dizer nada."""
    EtapaCiclo.objects.filter(ciclo=pauta, codigo="CP01").update(obrigatoria=False)

    assert svc.conferir(pauta) == []


def test_o_servico_recusa_etapa_de_outro_ciclo(pauta, condutor):
    """A view devolve 404 antes de chegar aqui. Esta é a tranca de baixo, e é a
    que vale quando alguém escrever a segunda view."""
    ocorrencia = svc.abrir(pauta, condutor, 2026, 9, confirmado=True)
    alheia = CicloPlanejamento.objects.get(chave="trimestral").etapas.first()

    with pytest.raises(svc.CicloError):
        svc.anotar(ocorrencia, alheia, condutor, texto="na pauta do vizinho")
