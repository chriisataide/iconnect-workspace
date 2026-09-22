"""Enche as telas que as outras semeadoras deixam vazias.

    python manage.py semear_demonstracao --aplicar
    python manage.py semear_lancamentos  --aplicar   # financas
    python manage.py semear_editais      --aplicar   # cargas → resultados

## Por que ela existe

As dezenove semeadoras `semear_*` cadastram o que o produto precisa para
FUNCIONAR: recursos reserváveis, materiais, cursos, regras, centros de custo.
Nenhuma delas cadastra o que o produto precisa para ser VISTO — reserva,
correspondência, matrícula, relatório, custódia, despesa, meta, plano, ATA,
concentração, comentário.

O resultado é um sistema inteiro de estados vazios: cada tela mostra a mesma
frase cinza, e nenhum filtro ("vencendo", "em aberto", "concluído") tem os dois
lados. Não dá para revisar o desenho de uma lista olhando para a ausência dela.

São TRÊS comandos e não um porque `workspace` é a folha da árvore de
dependências e não importa app de domínio — o que escreve em `financas` e em
`resultados` mora no app dono. Ver "O que NÃO mora aqui", no fim do arquivo.

## O que ela NÃO é

Não é dado real. Cliente, placa, patrimônio, nota fiscal e valor são inventados
e plausíveis, e **nenhum deles deve sobreviver ao primeiro dado de verdade**.
Ela é para demonstração e para desenvolvimento; num banco de produção com
movimento, ela não acrescenta nada e polui o histórico.

## As três decisões de desenho

**1 · A chave de idempotência nunca é uma data.** Rodar duas vezes no mesmo dia
é fácil de acertar; rodar de novo na semana seguinte é onde toda semeadora de
demonstração duplica. Por isso a identidade de cada linha é algo estável — o
`slug` do documento, o motivo da reserva, a finalidade da viagem — e as datas,
que são relativas a hoje, ficam só no conteúdo.

**2 · Variedade de estado é o produto.** Onde há cinco situações, as cinco
aparecem; onde há prazo, há vencido, vencendo e folgado. Semear tudo no mesmo
estado deixaria a tela de uma cor só, que é quase tão inútil quanto vazia.

**3 · Ninguém novo é criado.** Autor, responsável e solicitante saem das pessoas
que já existem. Uma semeadora que inventa conta é uma semeadora que deixa gente
de mentira no `/admin/` depois de a demonstração acabar.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from contas.models import Pessoa
from identidade.models import Unidade
from workspace.models.ciclo import (
    AnotacaoEtapa,
    CicloPlanejamento,
    OcorrenciaCiclo,
    SituacaoOcorrencia,
)
from workspace.models.comentario import ComentarioSolicitacao
from workspace.models.concentracao import Concentracao, OrigemConcentracao
from workspace.models.conteudo import (
    ConfirmacaoLeitura,
    Documento,
    SituacaoDocumento,
    TipoDocumento,
)
from workspace.models.correspondencia import (
    Correspondencia,
    SituacaoCorrespondencia,
    TipoCorrespondencia,
)
from workspace.models.custodia import Custodia
from workspace.models.estoque import CondicaoMaterial, Material
from workspace.models.frota import DespesaVeiculo, TipoDespesaVeiculo, Veiculo
from workspace.models.habilitacao import Curso, Matricula, SituacaoMatricula
from workspace.models.meta import (
    AcaoDesenvolvimento,
    CicloMetas,
    GrupoMeta,
    Meta,
    PlanoDesenvolvimento,
    QuadroMetas,
    SituacaoQuadro,
    TipoCalculo,
)
from workspace.models.catalogo import SolicitacaoServico
from workspace.models.plano import PlanoAcao, SituacaoPlano, VerificacaoPlano
from workspace.models.relatorio import (
    EvidenciaRelatorio,
    Relatorio,
    SituacaoRelatorio,
    TipoRelatorio,
)
from workspace.models.reserva import Recurso, Reserva, SituacaoReserva

# ── Quem faz o quê ──────────────────────────────────────────────────
#
# E-mails das contas que `semear_perfis` cria. Resolvidos em tempo de execução
# e com queda para a primeira pessoa do banco: a semeadora não pode explodir
# porque um perfil foi renomeado — ela é de demonstração, e a demonstração
# continua servindo com outro nome no autor.
RECEPCAO = "recepcao@icodev.com.br"
SUPRIMENTOS = "logistica@icodev.com.br"
SESMT = "sesmt@icodev.com.br"
RH = "rh@icodev.com.br"
TI = "ti@icodev.com.br"
JURIDICO = "juridico@icodev.com.br"
FINANCEIRO = "financeiro@icodev.com.br"
OPERACAO = "operacao@icodev.com.br"
MONITORAMENTO = "monitoramento@icodev.com.br"
COMPRAS = "compras@icodev.com.br"
MARKETING = "marketing@icodev.com.br"
VENDAS = "vendas@icodev.com.br"
QUALIDADE = "auditoria@icodev.com.br"
DIRETORIA = "diretoria@icodev.com.br"
SOCIO = "socio.fundador@icodev.com.br"
DIR_OPERACOES = "diretor.operacoes@icodev.com.br"
GER_CAMPO = "gerente.campo@icodev.com.br"
GER_SUPORTE = "gerente.suporte@icodev.com.br"
TECNICO = "tecnico.campo@icodev.com.br"
ANALISTA = "analista.suporte@icodev.com.br"
COLABORADOR = "colaborador@icodev.com.br"
GESTOR = "gestor@icodev.com.br"


def somar_meses(base: date, meses: int) -> date:
    """`base` mais `meses`, grudando no último dia quando o mês é curto.

    31/01 + 1 mês é 28/02, e não um `ValueError`. A validade de uma NR concluída
    num dia 31 cai nesse caso duas vezes por ano.
    """
    total = base.month - 1 + meses
    ano = base.year + total // 12
    mes = total % 12 + 1
    return date(ano, mes, min(base.day, monthrange(ano, mes)[1]))


class Command(BaseCommand):
    help = "Semeia movimento de demonstração nas telas que as outras semeadoras deixam vazias."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--aplicar", action="store_true", help="Grava.")

    # ── Entrada ─────────────────────────────────────────────────────

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        self.hoje = timezone.localdate()
        self.agora = timezone.now()
        self.contagem: dict[str, list[int]] = {}
        self.pulados: list[str] = []

        self.pessoas = {p.email: p for p in Pessoa.objects.all()}
        self.padrao = Pessoa.objects.order_by("pk").first()
        if self.padrao is None:
            self.stdout.write(
                self.style.ERROR(
                    "Nenhuma pessoa cadastrada — todo registro aqui tem autor. "
                    "Rode `semear_perfis --aplicar` antes."
                )
            )
            return

        self.matriz = Unidade.objects.order_by("pk").first()
        self.salvador = Unidade.objects.order_by("pk").last()

        with transaction.atomic():
            self._reservas()
            self._correspondencias()
            docs = self._documentos()
            self._confirmacoes(docs)
            self._matriculas()
            self._relatorios()
            self._custodias()
            self._despesas_de_veiculo()
            self._quadros_de_metas()
            self._planos_de_desenvolvimento()
            self._planos_de_acao()
            self._ocorrencias_de_ciclo(docs)
            self._concentracoes()
            self._comentarios()

            if not aplicar:
                transaction.set_rollback(True)

        self._resumo(aplicar)

    # ── Utilidades ──────────────────────────────────────────────────

    def p(self, email: str) -> Pessoa:
        """A pessoa daquele e-mail, ou a primeira do banco."""
        return self.pessoas.get(email, self.padrao)

    def semear(self, rotulo: str, model, chave: dict, **defaults):
        """`get_or_create` com contador. A chave NUNCA carrega data — ver o topo."""
        obj, criado = model.objects.get_or_create(**chave, defaults=defaults)
        linha = self.contagem.setdefault(rotulo, [0, 0])
        linha[0 if criado else 1] += 1
        return obj

    def pular(self, rotulo: str, motivo: str) -> None:
        self.pulados.append(f"{rotulo}: {motivo}")

    def momento(self, dias: int, hora: int, minuto: int = 0):
        """Um instante consciente de fuso, a `dias` de hoje."""
        return timezone.make_aware(
            datetime.combine(self.hoje + timedelta(days=dias), time(hora, minuto))
        )

    def dia(self, dias: int) -> date:
        return self.hoje + timedelta(days=dias)

    # ── RES · reservas ──────────────────────────────────────────────

    def _reservas(self) -> None:
        recursos = {r.codigo: r for r in Recurso.objects.all()}
        if not recursos:
            self.pular("Reserva", "nenhum Recurso cadastrado")
            return

        # (recurso, dia, início, fim, motivo, quem, cancelada)
        #
        # Sem sobreposição por recurso, de propósito: a semeadora não pode
        # criar o choque que `services/reserva.py` existe para impedir — um
        # banco de demonstração com conflito faria a grade parecer quebrada.
        agenda = [
            ("sala-reuniao-1", -14, 9, 11, "Comitê de operações — fechamento de agosto", DIR_OPERACOES, False),
            ("sala-reuniao-1", -2, 14, 16, "Alinhamento do contrato CT-101 · Rede Aurora", GER_CAMPO, False),
            ("sala-reuniao-1", 3, 9, 11, "Reunião do ciclo mensal de planejamento", DIRETORIA, False),
            ("sala-reuniao-2", -7, 10, 11, "Entrevista de vigilante — posto Portal Norte", RH, False),
            ("sala-reuniao-2", 1, 15, 16, "Revisão do POP de ronda noturna", SESMT, False),
            ("sala-rapida", 0, 8, 9, "Ligação com o cliente sobre a ocorrência de sábado", MONITORAMENTO, False),
            ("sala-rapida", 5, 11, 12, "Call de renovação com a Rede Farmalux", VENDAS, False),
            ("auditorio", -21, 8, 12, "Treinamento NR-35 — turma 3", SESMT, False),
            ("auditorio", 10, 8, 16, "Integração de novos vigilantes", RH, False),
            ("sala-treinamento", -5, 13, 17, "Reciclagem de primeiros socorros", SESMT, False),
            ("sala-treinamento", 7, 8, 12, "Direção defensiva — turma 2", GER_CAMPO, False),
            ("sala-treinamento", 14, 8, 12, "Treinamento adiado a pedido do cliente", GER_CAMPO, True),
            ("van-1", -3, 6, 18, "Ronda extraordinária no Shopping Portal Norte", OPERACAO, False),
            ("van-1", 2, 6, 18, "Apoio ao Hospital São Lucas — troca de turno", OPERACAO, False),
            ("utilitario-1", -10, 7, 19, "Instalação de CFTV no Frigorífico Serra Azul", TECNICO, False),
            ("utilitario-1", 4, 7, 19, "Troca de equipamentos na Rede Farmalux", TECNICO, False),
            ("utilitario-1", 6, 7, 19, "Vistoria cancelada — obra do cliente parada", TECNICO, True),
            ("projetor-portatil", -1, 9, 17, "Apresentação trimestral para a diretoria", DIRETORIA, False),
            ("projetor-portatil", 9, 9, 17, "Workshop de qualidade com a equipe de campo", QUALIDADE, False),
            ("kit-videoconferencia", 0, 14, 18, "Ciclo trimestral com sócios e diretores", SOCIO, False),
        ]

        for codigo, dias, inicio, fim, motivo, email, cancelada in agenda:
            recurso = recursos.get(codigo)
            if recurso is None:
                continue
            self.semear(
                "Reserva",
                Reserva,
                {"recurso": recurso, "motivo": motivo},
                solicitante=self.p(email),
                inicio=self.momento(dias, inicio),
                fim=self.momento(dias, fim),
                situacao=(
                    SituacaoReserva.CANCELADA if cancelada else SituacaoReserva.CONFIRMADA
                ),
                cancelado_em=self.momento(dias - 2, 10) if cancelada else None,
                cancelado_por=self.p(SUPRIMENTOS) if cancelada else None,
            )

    # ── COR · correspondência ───────────────────────────────────────

    def _correspondencias(self) -> None:
        # (descrição, tipo, remetente, empresa, rastreio, destinatário,
        #  nome no envelope, situação, dias desde a chegada)
        pauta = [
            ("Intimação trabalhista — processo 0012345-67.2026.5.05.0001",
             TipoCorrespondencia.INTIMACAO, "1ª Vara do Trabalho de Salvador",
             "Oficial de justiça", "", JURIDICO, "", SituacaoCorrespondencia.ENTREGUE, 12, True),
            ("Notificação do Ministério Público do Trabalho",
             TipoCorrespondencia.INTIMACAO, "MPT — PRT 5ª Região", "Correios",
             "JT884512367BR", JURIDICO, "", SituacaoCorrespondencia.AGUARDANDO, 3, False),
            ("Auto de infração de trânsito — placa RTA1B23",
             TipoCorrespondencia.MULTA, "DETRAN-BA", "Correios", "BR993217845BR",
             FINANCEIRO, "", SituacaoCorrespondencia.ENTREGUE, 21, True),
            ("Multa por excesso de velocidade — BR-324",
             TipoCorrespondencia.MULTA, "PRF", "Correios", "BR993217846BR",
             "", "Setor de Frota", SituacaoCorrespondencia.AGUARDANDO, 6, False),
            ("Contrato assinado — CT-113 · Rede Farmalux",
             TipoCorrespondencia.DOCUMENTO, "Rede Farmalux Ltda.", "Motoboy",
             "", VENDAS, "", SituacaoCorrespondencia.ENTREGUE, 9, True),
            ("Certidão negativa de débitos federais",
             TipoCorrespondencia.DOCUMENTO, "Receita Federal", "Correios",
             "BR551239087BR", FINANCEIRO, "", SituacaoCorrespondencia.ENTREGUE, 30, True),
            ("Apólice de seguro da frota — renovação 2026",
             TipoCorrespondencia.DOCUMENTO, "Corretora Âncora", "Correios",
             "BR551239088BR", "", "Departamento Administrativo",
             SituacaoCorrespondencia.AGUARDANDO, 1, False),
            ("Caixa com 40 rádios HT para o posto Portal Norte",
             TipoCorrespondencia.ENCOMENDA, "Tele Rádio Comércio", "Transportadora Ipiranga",
             "TI0099887766", SUPRIMENTOS, "", SituacaoCorrespondencia.ENTREGUE, 15, True),
            ("Dois notebooks do pedido de compra 2026/114",
             TipoCorrespondencia.ENCOMENDA, "Info Distribuidora", "Jadlog",
             "JD4455667788", TI, "", SituacaoCorrespondencia.AGUARDANDO, 2, False),
            ("Uniformes — 60 camisas tamanho M",
             TipoCorrespondencia.ENCOMENDA, "Confecções Bandeirante", "Transportadora Ipiranga",
             "TI0099887767", SUPRIMENTOS, "", SituacaoCorrespondencia.ENTREGUE, 24, False),
            ("Encomenda sem etiqueta de destinatário legível",
             TipoCorrespondencia.ENCOMENDA, "", "Correios", "BR118822334BR",
             "", "", SituacaoCorrespondencia.AGUARDANDO, 8, False),
            ("Encomenda devolvida — endereço de cobrança desatualizado",
             TipoCorrespondencia.ENCOMENDA, "Papelaria Central", "Correios",
             "BR118822335BR", "", "Almoxarifado", SituacaoCorrespondencia.DEVOLVIDA, 33, False),
            ("Boleto do condomínio da Base Salvador",
             TipoCorrespondencia.CARTA, "Condomínio Empresarial Iguatemi", "Correios",
             "", FINANCEIRO, "", SituacaoCorrespondencia.ENTREGUE, 18, True),
            ("Carta de agradecimento do Colégio Novo Horizonte",
             TipoCorrespondencia.CARTA, "Colégio Novo Horizonte", "Correios",
             "", DIRETORIA, "", SituacaoCorrespondencia.ENTREGUE, 27, False),
            ("Correspondência bancária — cartão corporativo",
             TipoCorrespondencia.CARTA, "Banco Meridiano", "Correios", "BR770011223BR",
             "", "Diretoria Financeira", SituacaoCorrespondencia.AGUARDANDO, 11, False),
            ("Carta devolvida — destinatário já desligado",
             TipoCorrespondencia.CARTA, "Sindicato dos Vigilantes", "Correios",
             "", "", "Marcos A. (desligado)", SituacaoCorrespondencia.DEVOLVIDA, 40, False),
        ]

        for (descricao, tipo, remetente, empresa, rastreio, email, envelope,
             situacao, dias, confirmada) in pauta:
            entregue = situacao != SituacaoCorrespondencia.AGUARDANDO
            self.semear(
                "Correspondencia",
                Correspondencia,
                {"descricao": descricao},
                tipo=tipo,
                remetente=remetente,
                empresa=empresa,
                numero_rastreio=rastreio,
                destinatario=self.p(email) if email else None,
                nome_no_envelope=envelope,
                unidade=self.matriz if dias % 2 == 0 else self.salvador,
                situacao=situacao,
                recebido_em=self.momento(-dias, 9, 30),
                recebido_por=self.p(RECEPCAO),
                retirado_em=self.momento(-dias + 1, 16) if entregue else None,
                retirado_por=(
                    self.p(email) if entregue and email else
                    (self.p(RECEPCAO) if entregue else None)
                ),
                confirmado_em=self.momento(-dias + 1, 17) if confirmada else None,
                observacao=(
                    "Prazo legal — conferir com o Jurídico antes de responder."
                    if tipo in (TipoCorrespondencia.INTIMACAO, TipoCorrespondencia.MULTA)
                    else ""
                ),
            )

    # ── CNT · acervo normativo ──────────────────────────────────────

    def _documentos(self) -> dict[str, Documento]:
        # (slug, tipo, título, categoria, resumo, dono, versão, público-alvo,
        #  leitura obrigatória, início da vigência, fim da vigência, situação)
        acervo = [
            ("pop-ronda-noturna", TipoDocumento.POP, "POP-001 · Ronda noturna em posto fixo",
             "Operação", "Como fazer, registrar e comunicar a ronda entre 22h e 6h.",
             OPERACAO, "3.1", ["*"], True, -420, 340, SituacaoDocumento.VIGENTE),
            ("pop-revista-de-acesso", TipoDocumento.POP, "POP-002 · Revista e controle de acesso",
             "Operação", "Abordagem, revista de bolsa e registro de visitante.",
             OPERACAO, "2.0", ["*"], True, -300, 65, SituacaoDocumento.VIGENTE),
            ("pop-uso-de-arma", TipoDocumento.POP, "POP-003 · Porte e guarda de arma de fogo",
             "Segurança", "Retirada, conferência e devolução do armamento no posto.",
             SESMT, "4.2", ["papel:operacao", "papel:sesmt"], True, -180, 25,
             SituacaoDocumento.VIGENTE),
            ("pop-atendimento-de-alarme", TipoDocumento.POP, "POP-004 · Atendimento de alarme",
             "Monitoramento", "Tempo de resposta, acionamento e fechamento da ocorrência.",
             MONITORAMENTO, "1.4", ["*"], False, -120, None, SituacaoDocumento.VIGENTE),
            ("pop-recebimento-de-valores", TipoDocumento.POP, "POP-005 · Recebimento de malote",
             "Operação", "Conferência de lacre e assinatura do termo de custódia.",
             OPERACAO, "1.0", ["*"], False, -60, -5, SituacaoDocumento.VIGENTE),
            ("politica-uso-de-radio", TipoDocumento.POLITICA, "Política de uso de rádio e celular",
             "Operação", "O que pode ser dito no canal aberto, e o que não pode.",
             OPERACAO, "2.1", ["*"], False, -240, 120, SituacaoDocumento.VIGENTE),
            ("politica-de-privacidade-cftv", TipoDocumento.POLITICA,
             "Política de imagens de CFTV e LGPD", "Qualidade",
             "Quem vê a imagem, por quanto tempo ela fica, e como é descartada.",
             JURIDICO, "1.2", ["*"], True, -90, 275, SituacaoDocumento.VIGENTE),
            ("politica-de-viagem", TipoDocumento.POLITICA, "Política de viagem e diária",
             "Pessoas", "Limites, comprovação e prazo de prestação de contas.",
             FINANCEIRO, "3.0", ["*"], False, -400, -30, SituacaoDocumento.VIGENTE),
            ("norma-uniforme-e-epi", TipoDocumento.NORMA, "Norma de uniforme e EPI",
             "Segurança", "O que é obrigatório por tipo de posto, e quem repõe.",
             SESMT, "2.3", ["*"], True, -150, 200, SituacaoDocumento.VIGENTE),
            ("norma-de-escala-12x36", TipoDocumento.NORMA, "Norma de escala 12×36",
             "Pessoas", "Troca de turno, banco de horas e folga compensatória.",
             RH, "1.1", ["*"], False, -75, None, SituacaoDocumento.VIGENTE),
            ("instrucao-livro-de-ocorrencia", TipoDocumento.INSTRUCAO,
             "IT-001 · Preenchimento do livro de ocorrência", "Operação",
             "O que entra, o que não entra, e como corrigir sem rasurar.",
             QUALIDADE, "1.0", ["*"], False, -45, None, SituacaoDocumento.VIGENTE),
            ("instrucao-abertura-de-chamado", TipoDocumento.INSTRUCAO,
             "IT-002 · Abertura de chamado técnico de CFTV", "Qualidade",
             "Como descrever o defeito para o técnico não ir à toa.",
             TI, "0.9", ["*"], False, 5, None, SituacaoDocumento.RASCUNHO),
            ("manual-do-vigilante", TipoDocumento.MANUAL, "Manual do vigilante",
             "Operação", "O manual de bolso entregue na integração.",
             RH, "5.0", ["*"], True, -500, 45, SituacaoDocumento.VIGENTE),
            ("manual-da-central-de-monitoramento", TipoDocumento.MANUAL,
             "Manual da central de monitoramento", "Monitoramento",
             "Telas, códigos de evento e o que fazer em cada um.",
             MONITORAMENTO, "2.0", ["papel:monitoramento"], False, 12, None,
             SituacaoDocumento.RASCUNHO),
            ("pop-ronda-noturna-v2", TipoDocumento.POP, "POP-001 · Ronda noturna (revogado)",
             "Operação", "Substituído pela versão 3.1 após o incidente de julho.",
             OPERACAO, "2.4", ["*"], False, -700, -420, SituacaoDocumento.REVOGADO),
            ("politica-de-brindes", TipoDocumento.POLITICA, "Política de brindes e hospitalidade",
             "Qualidade", "Revogada — absorvida pelo Código de Conduta.",
             DIRETORIA, "1.0", ["*"], False, -600, -200, SituacaoDocumento.REVOGADO),
        ]

        documentos: dict[str, Documento] = {}
        for (slug, tipo, titulo, categoria, resumo, email, versao, alvo,
             obrigatoria, inicio, fim, situacao) in acervo:
            documentos[slug] = self.semear(
                "Documento",
                Documento,
                {"slug": slug},
                tipo=tipo,
                titulo=titulo,
                categoria=categoria,
                resumo=resumo,
                corpo=(
                    f"{resumo}\n\nEste texto é conteúdo de DEMONSTRAÇÃO. Substitua "
                    "pelo normativo real antes de publicar para a empresa."
                ),
                dono=self.p(email),
                versao=versao,
                publico_alvo=alvo,
                leitura_obrigatoria=obrigatoria,
                vigencia_inicio=self.dia(inicio),
                vigencia_fim=self.dia(fim) if fim is not None else None,
                situacao=situacao,
            )

        # A revogação, ligada depois de todos existirem: `revoga` aponta para
        # outro documento, e a ordem do laço não pode ser um pré-requisito.
        antigo = documentos.get("pop-ronda-noturna-v2")
        novo = documentos.get("pop-ronda-noturna")
        if antigo and novo and antigo.revoga_id is None:
            novo.revoga = antigo
            novo.save(update_fields=["revoga"])

        return documentos

    def _confirmacoes(self, documentos: dict[str, Documento]) -> None:
        """Leitura confirmada por parte de quem deve — e só por parte.

        Confirmar por todo mundo deixaria a regra `leitura-nao-confirmada` sem
        nenhuma ocorrência, e a tela de pendência nasceria vazia de novo.
        """
        leitores = [
            OPERACAO, MONITORAMENTO, TECNICO, GER_CAMPO, RH, SESMT,
            COLABORADOR, ANALISTA, GER_SUPORTE, SUPRIMENTOS,
        ]
        obrigatorios = [
            d for d in documentos.values()
            if d.leitura_obrigatoria and d.situacao == SituacaoDocumento.VIGENTE
        ]
        for posicao, documento in enumerate(obrigatorios):
            # Quantos leram varia de propósito: um normativo com 9 de 10 e
            # outro com 3 de 10 é o que faz a coluna de cobertura significar
            # alguma coisa na tela.
            quantos = 3 + (posicao * 2) % 7
            for email in leitores[:quantos]:
                self.semear(
                    "ConfirmacaoLeitura",
                    ConfirmacaoLeitura,
                    {
                        "documento": documento,
                        "pessoa": self.p(email),
                        "versao": documento.versao,
                    },
                )

    # ── HAB · matrículas ────────────────────────────────────────────

    def _matriculas(self) -> None:
        cursos = {c.codigo: c for c in Curso.objects.all()}
        if not cursos:
            self.pular("Matricula", "nenhum Curso cadastrado")
            return

        # (curso, pessoa, situação, percentual, prazo, conclusão)
        #
        # As datas de conclusão são espalhadas de propósito para que `vence_em`
        # caia nos três lados: vencido, vencendo em 30 dias, e folgado.
        turma = [
            ("nr-35", TECNICO, SituacaoMatricula.CONCLUIDO, 100, None, -700),
            ("nr-35", GER_CAMPO, SituacaoMatricula.CONCLUIDO, 100, None, -715),
            ("nr-35", OPERACAO, SituacaoMatricula.CONCLUIDO, 100, None, -700),
            ("nr-35", COLABORADOR, SituacaoMatricula.EM_ANDAMENTO, 60, 20, None),
            ("nr-10", TECNICO, SituacaoMatricula.CONCLUIDO, 100, None, -740),
            ("nr-10", ANALISTA, SituacaoMatricula.CONCLUIDO, 100, None, -365),
            ("nr-10", TI, SituacaoMatricula.PENDENTE, 0, 45, None),
            ("nr-33", TECNICO, SituacaoMatricula.CONCLUIDO, 100, None, -350),
            ("nr-33", GER_CAMPO, SituacaoMatricula.CONCLUIDO, 100, None, -380),
            ("nr-33", SESMT, SituacaoMatricula.DISPENSADO, 0, None, None),
            ("nr-12", TECNICO, SituacaoMatricula.EM_ANDAMENTO, 35, -6, None),
            ("nr-12", OPERACAO, SituacaoMatricula.PENDENTE, 0, -15, None),
            ("integracao", COLABORADOR, SituacaoMatricula.CONCLUIDO, 100, None, -40),
            ("integracao", ANALISTA, SituacaoMatricula.CONCLUIDO, 100, None, -220),
            ("integracao", RECEPCAO, SituacaoMatricula.EM_ANDAMENTO, 80, 10, None),
            ("lgpd", JURIDICO, SituacaoMatricula.CONCLUIDO, 100, None, -330),
            ("lgpd", MONITORAMENTO, SituacaoMatricula.CONCLUIDO, 100, None, -345),
            ("lgpd", TI, SituacaoMatricula.CONCLUIDO, 100, None, -120),
            ("lgpd", RH, SituacaoMatricula.PENDENTE, 0, 60, None),
            ("primeiros-socorros", OPERACAO, SituacaoMatricula.CONCLUIDO, 100, None, -690),
            ("primeiros-socorros", MONITORAMENTO, SituacaoMatricula.CONCLUIDO, 100, None, -200),
            ("primeiros-socorros", COLABORADOR, SituacaoMatricula.EM_ANDAMENTO, 15, 30, None),
            ("direcao-defensiva", TECNICO, SituacaoMatricula.CONCLUIDO, 100, None, -710),
            ("direcao-defensiva", SUPRIMENTOS, SituacaoMatricula.CONCLUIDO, 100, None, -90),
            ("direcao-defensiva", GER_CAMPO, SituacaoMatricula.DISPENSADO, 0, None, None),
        ]

        for codigo, email, situacao, percentual, prazo, conclusao in turma:
            curso = cursos.get(codigo)
            if curso is None:
                continue
            concluido_em = self.dia(conclusao) if conclusao is not None else None
            vence_em = (
                somar_meses(concluido_em, curso.validade_meses)
                if concluido_em and curso.validade_meses
                else None
            )
            self.semear(
                "Matricula",
                Matricula,
                {"pessoa": self.p(email), "curso": curso},
                situacao=situacao,
                percentual=percentual,
                prazo=self.dia(prazo) if prazo is not None else None,
                concluido_em=concluido_em,
                vence_em=vence_em,
                certificado=(
                    f"CERT-{curso.codigo.upper()}-{abs(conclusao):04d}"
                    if conclusao is not None else ""
                ),
                observacao=(
                    "Dispensado por equivalência com certificação anterior."
                    if situacao == SituacaoMatricula.DISPENSADO else ""
                ),
                responsavel=self.p(RH),
            )

    # ── REL · relatórios ────────────────────────────────────────────

    def _relatorios(self) -> None:
        # (tipo, título, cliente, local, dias, hora, situação, dados)
        pauta = [
            (TipoRelatorio.OCORRENCIA, "Tentativa de arrombamento no portão de carga",
             "Supermercados Boa Praça", "CD Lauro de Freitas — portão 3", -31, time(3, 15),
             SituacaoRelatorio.EMITIDO,
             {"gravidade": "alta", "policia_acionada": True, "prejuizo_estimado": "0,00",
              "providencia": "Reforço de ronda motorizada por 15 dias."}),
            (TipoRelatorio.OCORRENCIA, "Acionamento indevido de alarme de pânico",
             "Rede Farmalux", "Loja Pituba", -24, time(19, 40),
             SituacaoRelatorio.EMITIDO,
             {"gravidade": "baixa", "policia_acionada": False,
              "providencia": "Reciclagem do POP-004 com a equipe da loja."}),
            (TipoRelatorio.OCORRENCIA, "Furto de cabo de cobre no pátio",
             "Metalúrgica Itaimbé", "Pátio de expedição", -17, time(2, 5),
             SituacaoRelatorio.EMITIDO,
             {"gravidade": "media", "policia_acionada": True,
              "prejuizo_estimado": "4.200,00",
              "providencia": "Instalação de dois pontos de CFTV com análise de vídeo."}),
            (TipoRelatorio.OCORRENCIA, "Queda de colaborador na escada de acesso",
             "Hospital São Lucas Fictício", "Bloco B — escada de serviço", -9, time(14, 22),
             SituacaoRelatorio.EMITIDO,
             {"gravidade": "media", "cat_aberta": True,
              "providencia": "CAT aberta e comunicação ao SESMT no mesmo dia."}),
            (TipoRelatorio.OCORRENCIA, "Veículo não identificado no estacionamento",
             "Shopping Portal Norte", "Estacionamento G2", -3, time(23, 50),
             SituacaoRelatorio.RASCUNHO,
             {"gravidade": "baixa", "policia_acionada": False}),
            (TipoRelatorio.OCORRENCIA, "Princípio de incêndio em quadro elétrico",
             "Indústria Cambará", "Casa de máquinas", -1, time(5, 30),
             SituacaoRelatorio.RASCUNHO,
             {"gravidade": "alta", "bombeiros_acionados": True}),
            (TipoRelatorio.OCORRENCIA, "Registro duplicado da ocorrência de 12/08",
             "Rede Aurora", "Loja Centro", -41, time(21, 0),
             SituacaoRelatorio.CANCELADO,
             {"motivo_cancelamento": "Duplicidade com o relatório REL-2026-0311."}),
            (TipoRelatorio.ENTREGA, "Entrega de 12 rádios HT ao posto Portal Norte",
             "Shopping Portal Norte", "Portaria de serviço", -28, time(10, 0),
             SituacaoRelatorio.EMITIDO,
             {"itens": 12, "conferente": "Supervisão do posto", "divergencia": False}),
            (TipoRelatorio.ENTREGA, "Instalação de 8 câmeras no perímetro",
             "Frigorífico Serra Azul", "Perímetro norte", -20, time(8, 30),
             SituacaoRelatorio.EMITIDO,
             {"itens": 8, "conferente": "Engenharia do cliente", "divergencia": False}),
            (TipoRelatorio.ENTREGA, "Troca de uniformes do efetivo — 2º semestre",
             "Grupo Meridiano", "Almoxarifado do cliente", -13, time(9, 15),
             SituacaoRelatorio.EMITIDO,
             {"itens": 60, "conferente": "Almoxarifado", "divergencia": True,
              "observacao_divergencia": "Faltaram 2 camisas tamanho GG."}),
            (TipoRelatorio.ENTREGA, "Entrega de kit de primeiros socorros",
             "Colégio Novo Horizonte", "Secretaria", -6, time(11, 0),
             SituacaoRelatorio.EMITIDO,
             {"itens": 4, "conferente": "Coordenação", "divergencia": False}),
            (TipoRelatorio.ENTREGA, "Substituição do nobreak da central",
             "Condomínio Alto da Colina", "Guarita", -2, time(16, 45),
             SituacaoRelatorio.RASCUNHO, {"itens": 1}),
            (TipoRelatorio.ENTREGA, "Entrega programada de lacres e malotes",
             "Transportes Guaíba", "Base operacional", 4, time(8, 0),
             SituacaoRelatorio.RASCUNHO, {"itens": 30}),
            (TipoRelatorio.ENTREGA, "Entrega cancelada — obra do cliente parada",
             "Parque Tecnológico Ipê", "Bloco C", -11, time(9, 0),
             SituacaoRelatorio.CANCELADO,
             {"motivo_cancelamento": "Cliente suspendeu a obra por 60 dias."}),
        ]

        autores = [OPERACAO, MONITORAMENTO, TECNICO, GER_CAMPO, SUPRIMENTOS]
        for posicao, (tipo, titulo, cliente, local, dias, horario, situacao, dados) in enumerate(pauta):
            relatorio = self.semear(
                "Relatorio",
                Relatorio,
                {"tipo": tipo, "titulo": titulo},
                cliente=cliente,
                local=local,
                ocorrido_em=self.dia(dias),
                horario=horario,
                dados=dados,
                situacao=situacao,
                emitido_em=(
                    self.momento(dias + 1, 10)
                    if situacao == SituacaoRelatorio.EMITIDO else None
                ),
                autor=self.p(autores[posicao % len(autores)]),
                unidade=self.matriz if posicao % 2 == 0 else self.salvador,
            )
            if situacao == SituacaoRelatorio.CANCELADO:
                continue
            # O arquivo em si NÃO existe em disco: o `FileField` guarda o
            # caminho, e o download responderá 404. É de propósito — inventar
            # um binário só para a lista parecer cheia seria criar lixo que
            # ninguém sabe apagar depois.
            for indice in range(1, 3 if tipo == TipoRelatorio.OCORRENCIA else 2):
                nome = f"{relatorio.tipo}-{abs(dias):03d}-{indice}.jpg"
                self.semear(
                    "EvidenciaRelatorio",
                    EvidenciaRelatorio,
                    {"relatorio": relatorio, "nome_original": nome},
                    arquivo=f"demonstracao/relatorios/{nome}",
                    legenda=(
                        "Foto do local no momento do registro." if indice == 1
                        else "Detalhe do ponto de acesso."
                    ),
                    tamanho=380_000 + indice * 55_000,
                )

    # ── EST · custódia ──────────────────────────────────────────────

    def _custodias(self) -> None:
        materiais = {m.codigo: m for m in Material.objects.all()}
        if not materiais or self.matriz is None:
            self.pular("Custodia", "nenhum Material ou nenhuma Unidade cadastrada")
            return

        # (material, pessoa, qtd, patrimônio, série, entrega, aceite, devolução, condição)
        termos = [
            ("capacete", TECNICO, 1, "PAT-004512", "", -210, -208, None, ""),
            ("capacete", COLABORADOR, 1, "PAT-004513", "", -12, None, None, ""),
            ("bota-seguranca", TECNICO, 1, "", "", -210, -208, None, ""),
            ("bota-seguranca", OPERACAO, 1, "", "", -95, -94, None, ""),
            ("colete-refletivo", GER_CAMPO, 1, "PAT-004598", "", -150, -149, None, ""),
            ("colete-refletivo", ANALISTA, 1, "PAT-004599", "", -5, None, None, ""),
            ("camisa-uniforme", COLABORADOR, 3, "", "", -40, -39, None, ""),
            ("camisa-uniforme", RECEPCAO, 2, "", "", -320, -319, -30, CondicaoMaterial.USADO_BOM),
            ("luva-nitrilica", TECNICO, 4, "", "", -60, -59, None, ""),
            ("cabo-utp", TECNICO, 1, "", "", -33, -32, -7, CondicaoMaterial.USADO_BOM),
            ("cadeado", SUPRIMENTOS, 5, "", "", -120, -118, None, ""),
            ("cadeado", OPERACAO, 2, "", "", -260, -259, -45, CondicaoMaterial.NOVO),
            ("fita-isolante", TECNICO, 3, "", "", -2, None, None, ""),
            ("papel-a4", RECEPCAO, 2, "", "", -18, -17, None, ""),
            ("conector-rj45", ANALISTA, 50, "", "", -400, -398, -120, CondicaoMaterial.SUCATA),
        ]

        for (codigo, email, quantidade, patrimonio, serie, entrega,
             aceite, devolucao, condicao) in termos:
            material = materiais.get(codigo)
            if material is None:
                continue
            self.semear(
                "Custodia",
                Custodia,
                {"material": material, "pessoa": self.p(email)},
                unidade=self.matriz if entrega % 2 == 0 else (self.salvador or self.matriz),
                quantidade=quantidade,
                patrimonio=patrimonio,
                numero_serie=serie,
                entregue_em=self.momento(entrega, 9),
                entregue_por=self.p(SUPRIMENTOS),
                aceito_em=self.momento(aceite, 14) if aceite is not None else None,
                devolvido_em=self.momento(devolucao, 15) if devolucao is not None else None,
                devolvido_por=self.p(SUPRIMENTOS) if devolucao is not None else None,
                condicao_devolucao=condicao,
                observacao=(
                    "Devolvido na troca de posto." if devolucao is not None else ""
                ),
            )

    # ── FRT · despesas de veículo ───────────────────────────────────

    def _despesas_de_veiculo(self) -> None:
        veiculos = list(Veiculo.objects.order_by("placa"))
        if not veiculos:
            self.pular("DespesaVeiculo", "nenhum Veiculo cadastrado")
            return

        # (índice do veículo, tipo, dias, valor, km, litros, tanque cheio,
        #  fornecedor, motorista, destino, finalidade)
        gastos = [
            (0, TipoDespesaVeiculo.COMBUSTIVEL, -84, "412.90", 68120, "71.500", True,
             "Posto Ipiranga Paralela", TECNICO, "Lauro de Freitas",
             "Abastecimento antes da rota do CD Boa Praça"),
            (0, TipoDespesaVeiculo.COMBUSTIVEL, -56, "398.40", 68940, "69.000", True,
             "Posto Ipiranga Paralela", TECNICO, "Camaçari",
             "Abastecimento da rota industrial"),
            (0, TipoDespesaVeiculo.COMBUSTIVEL, -28, "435.10", 69810, "75.200", True,
             "Posto Shell Iguatemi", OPERACAO, "Salvador",
             "Abastecimento do apoio ao Hospital São Lucas"),
            (0, TipoDespesaVeiculo.COMBUSTIVEL, -7, "210.00", 70240, "36.000", False,
             "Posto BR Pituba", OPERACAO, "Salvador",
             "Completada parcial para a ronda noturna"),
            (0, TipoDespesaVeiculo.MANUTENCAO, -63, "1890.00", 68800, None, True,
             "Oficina Central Diesel", None, "",
             "Revisão de 70 mil km e troca de correia"),
            (0, TipoDespesaVeiculo.PEDAGIO, -28, "38.60", None, None, True,
             "ViaBahia", OPERACAO, "Feira de Santana",
             "Deslocamento ao posto do Frigorífico Serra Azul"),
            (0, TipoDespesaVeiculo.LAVAGEM, -14, "90.00", None, None, True,
             "Lava a Jato Aeroporto", TECNICO, "Salvador",
             "Higienização após transporte de equipamento"),
            (1, TipoDespesaVeiculo.COMBUSTIVEL, -75, "287.30", 41200, "49.500", True,
             "Posto Ale Pituba", TECNICO, "Salvador",
             "Abastecimento da rota de manutenção de CFTV"),
            (1, TipoDespesaVeiculo.COMBUSTIVEL, -44, "301.70", 41930, "52.000", True,
             "Posto Ale Pituba", TECNICO, "Salvador",
             "Abastecimento da rota de instalação"),
            (1, TipoDespesaVeiculo.COMBUSTIVEL, -16, "318.20", 42700, "54.800", True,
             "Posto Petrobras Bonocô", TECNICO, "Simões Filho",
             "Abastecimento da visita à Metalúrgica Itaimbé"),
            (1, TipoDespesaVeiculo.ESTACIONAMENTO, -16, "24.00", None, None, True,
             "Estapar Comércio", TECNICO, "Salvador",
             "Vistoria no Shopping Portal Norte"),
            (1, TipoDespesaVeiculo.MULTA, -52, "195.23", None, None, True,
             "DETRAN-BA", TECNICO, "BR-324",
             "Excesso de velocidade — em recurso administrativo"),
            (1, TipoDespesaVeiculo.MANUTENCAO, -30, "740.00", 42300, None, True,
             "Auto Center Bonocô", None, "", "Troca de pastilhas e alinhamento"),
            (1, TipoDespesaVeiculo.LAVAGEM, -4, "70.00", None, None, True,
             "Lava a Jato Aeroporto", TECNICO, "Salvador",
             "Lavagem mensal do utilitário"),
            (2, TipoDespesaVeiculo.COMBUSTIVEL, -90, "245.00", 22400, "42.100", True,
             "Posto Shell Iguatemi", GER_CAMPO, "Salvador",
             "Abastecimento da agenda comercial"),
            (2, TipoDespesaVeiculo.COMBUSTIVEL, -60, "252.80", 23010, "43.600", True,
             "Posto Shell Iguatemi", GER_CAMPO, "Salvador",
             "Abastecimento das visitas de renovação"),
            (2, TipoDespesaVeiculo.COMBUSTIVEL, -33, "266.40", 23680, "45.900", True,
             "Posto Ipiranga Paralela", VENDAS, "Camaçari",
             "Abastecimento da visita à Indústria Cambará"),
            (2, TipoDespesaVeiculo.COMBUSTIVEL, -5, "180.00", 24050, "31.000", False,
             "Posto BR Pituba", VENDAS, "Salvador",
             "Completada parcial antes da reunião com a Rede Aurora"),
            (2, TipoDespesaVeiculo.PEDAGIO, -33, "19.30", None, None, True,
             "ViaBahia", VENDAS, "Camaçari", "Ida e volta à Indústria Cambará"),
            (2, TipoDespesaVeiculo.ESTACIONAMENTO, -12, "32.00", None, None, True,
             "Estapar Iguatemi", GER_CAMPO, "Salvador",
             "Reunião de renovação com a Rede Farmalux"),
            (2, TipoDespesaVeiculo.MULTA, -71, "130.16", None, None, True,
             "Prefeitura de Salvador", GER_CAMPO, "Salvador",
             "Estacionamento em local proibido — multa paga"),
            (2, TipoDespesaVeiculo.LAVAGEM, -21, "65.00", None, None, True,
             "Lava a Jato Aeroporto", GER_CAMPO, "Salvador",
             "Lavagem antes da visita à diretoria do cliente"),
            (2, TipoDespesaVeiculo.MANUTENCAO, -48, "980.00", 23400, None, True,
             "Chevrolet Serviços", None, "", "Revisão de 23 mil km"),
            (0, TipoDespesaVeiculo.PEDAGIO, -2, "38.60", None, None, True,
             "ViaBahia", OPERACAO, "Feira de Santana",
             "Apoio emergencial ao posto do Frigorífico"),
        ]

        for (indice, tipo, dias, valor, km, litros, cheio, fornecedor,
             motorista, destino, finalidade) in gastos:
            if indice >= len(veiculos):
                continue
            self.semear(
                "DespesaVeiculo",
                DespesaVeiculo,
                {"veiculo": veiculos[indice], "tipo": tipo, "finalidade": finalidade},
                data=self.dia(dias),
                valor=Decimal(valor),
                km=km,
                litros=Decimal(litros) if litros else None,
                tanque_cheio=cheio,
                fornecedor=fornecedor,
                motorista=self.p(motorista) if motorista else None,
                destino=destino,
                quem=self.p(FINANCEIRO),
            )

    # ── MET · quadros de metas ──────────────────────────────────────

    def _quadros_de_metas(self) -> None:
        ciclo = CicloMetas.objects.order_by("-inicio").first()
        if ciclo is None:
            self.pular("QuadroMetas", "nenhum CicloMetas cadastrado")
            return

        # (pessoa, situação, resumo)
        quadros = [
            (DIR_OPERACOES, SituacaoQuadro.APURADO,
             "Operação em nove contratos, com foco em margem e retenção. A "
             "prioridade do ano é recuperar a rentabilidade do CT-107."),
            (GER_CAMPO, SituacaoQuadro.APURADO,
             "Campo com 62 postos ativos. A prioridade é reduzir a cobertura "
             "de falta e manter a habilitação do efetivo em dia."),
            (GER_SUPORTE, SituacaoQuadro.APURADO,
             "Suporte técnico de CFTV e alarme. Prioridade em tempo de "
             "atendimento e em reduzir a reincidência de chamado."),
            (SOCIO, SituacaoQuadro.APROVADO,
             "Condução do plano de crescimento: dois contratos novos por "
             "trimestre e EBITDA acima do orçado."),
            (FINANCEIRO, SituacaoQuadro.APROVADO,
             "Fechamento contábil no prazo, orçamento revisado por ciclo e "
             "inadimplência sob controle."),
            (RH, SituacaoQuadro.APROVADO,
             "Redução de turnover no efetivo operacional e cobertura total "
             "das reciclagens obrigatórias."),
            (MONITORAMENTO, SituacaoQuadro.RASCUNHO,
             "Central 24h. As metas de tempo de resposta ainda estão sendo "
             "acordadas com a diretoria de operações."),
            (VENDAS, SituacaoQuadro.RASCUNHO,
             "Carteira comercial e radar de editais públicos. Rascunho em "
             "discussão para o segundo semestre."),
        ]

        # (grupo, descrição, fator 1, fator 2, cálculo, peso, alvo,
        #  realizado, atingimento, motivo de não apurar)
        modelo = [
            (GrupoMeta.FINANCEIRA, "EBITDA realizado sobre o orçado",
             "ebitda", "orcamento_mensal", TipoCalculo.DIRETO, 4, None,
             "118400.00", "104.3", ""),
            (GrupoMeta.OPERACIONAL, "Gasto dentro do teto do centro de custo",
             "realizado_no_mes", "orcamento_mensal", TipoCalculo.INVERSO, 3, None,
             "91250.00", "95.1", ""),
            (GrupoMeta.PESSOAS, "Turnover do efetivo abaixo de 3%",
             "turnover_pct", "", TipoCalculo.INVERSO, 2, "3", "4.10", "73.2", ""),
            (GrupoMeta.PROJETO, "Efetivo ativo no fim da competência",
             "efetivo_ativo", "", TipoCalculo.DIRETO, 1, "310", None, None,
             "A carga do Sankhya de agosto não trouxe o quadro de pessoas."),
        ]

        for email, situacao, resumo in quadros:
            pessoa = self.p(email)
            aprovado = situacao in (SituacaoQuadro.APROVADO, SituacaoQuadro.APURADO)
            apurado = situacao == SituacaoQuadro.APURADO
            quadro = self.semear(
                "QuadroMetas",
                QuadroMetas,
                {"ciclo": ciclo, "pessoa": pessoa},
                situacao=situacao,
                resumo=resumo,
                aprovado_por=self.p(SOCIO) if aprovado else None,
                aprovado_em=self.momento(-200, 11) if aprovado else None,
                apurado_em=self.momento(-4, 8) if apurado else None,
                reaberturas=(
                    [{
                        "quando": self.momento(-120, 15).isoformat(),
                        "quem": self.p(SOCIO).get_full_name(),
                        "motivo": "Alvo de turnover corrigido após a revisão do quadro de pessoas.",
                    }]
                    if email == GER_CAMPO else []
                ),
            )
            for ordem, (grupo, descricao, f1, f2, calculo, peso, alvo,
                        realizado, atingimento, motivo) in enumerate(modelo, 1):
                self.semear(
                    "Meta",
                    Meta,
                    {"quadro": quadro, "descricao": descricao},
                    grupo=grupo,
                    detalhamento=(
                        "A fórmula aponta para o espelho — o número não é digitado."
                    ),
                    peso=peso,
                    fator_1=f1,
                    fator_2=f2,
                    tipo_calculo=calculo,
                    alvo=Decimal(alvo) if alvo else None,
                    ordem=ordem * 10,
                    realizado=Decimal(realizado) if apurado and realizado else None,
                    atingimento_pct=(
                        Decimal(atingimento) if apurado and atingimento else None
                    ),
                    motivo_sem_apuracao=motivo if apurado else "",
                    carimbo_texto=(
                        "Sankhya · carga de ontem às 06:12" if apurado else ""
                    ),
                    apurado_em=self.momento(-4, 8) if apurado else None,
                )

    # ── PDI ─────────────────────────────────────────────────────────

    def _planos_de_desenvolvimento(self) -> None:
        ciclo = CicloMetas.objects.order_by("-inicio").first()
        if ciclo is None:
            self.pular("PlanoDesenvolvimento", "nenhum CicloMetas cadastrado")
            return

        planos = [
            (DIR_OPERACOES,
             "Responde pela operação dos contratos de vigilância patrimonial e pela "
             "supervisão de campo das duas bases.",
             "Gestão de contratos complexos e análise de rentabilidade por posto.",
             "Assumir a diretoria de operações das duas regionais.",
             "Participar da definição estratégica da companhia.",
             [("Curso de gestão de contratos de serviço continuado", 11, 0, False),
              ("Acompanhar o fechamento contábil com o Financeiro por 3 meses", 6, 0, True),
              ("Assumir a condução do ciclo mensal de planejamento", 2, 0, True)]),
            (GER_CAMPO,
             "Coordena 62 postos e 18 supervisores de campo.",
             "Dimensionamento de escala e redução de cobertura de falta.",
             "Assumir a gerência regional da Base Salvador.",
             "Migrar para a diretoria de operações.",
             [("Formação em escala e legislação do vigilante", 10, 0, False),
              ("Implantar a conferência diária de efetivo em campo", 1, 0, True),
              ("Mentoria com o diretor de operações — quinzenal", 12, 0, False)]),
            (GER_SUPORTE,
             "Responde pelo suporte técnico de CFTV, alarme e controle de acesso.",
             "Análise de vídeo e integração de sistemas prediais.",
             "Estruturar a engenharia de projetos da empresa.",
             "Liderar a área de tecnologia da companhia.",
             [("Certificação de fabricante em análise de vídeo", 9, 0, False),
              ("Reduzir a reincidência de chamado técnico em 20%", 12, 0, False),
              ("Documentar o parque instalado dos 18 contratos", 4, 0, True)]),
            (MONITORAMENTO,
             "Opera a central 24h e responde pelo tempo de atendimento de alarme.",
             "Procedimento de crise e comunicação com as forças de segurança.",
             "Assumir a coordenação da central de monitoramento.",
             "Gerenciar a operação remota de toda a carteira.",
             [("Treinamento de gestão de crise com a Polícia Militar", 11, 0, False),
              ("Revisar o POP-004 com a equipe dos três turnos", 8, 0, True)]),
            (FINANCEIRO,
             "Conduz o fechamento contábil e o orçamento por centro de custo.",
             "Controladoria e precificação de contrato de serviço.",
             "Assumir a controladoria da companhia.",
             "Atuar como CFO.",
             [("Curso de controladoria aplicada a serviços", 10, 0, False),
              ("Implantar a revisão orçamentária trimestral", 3, 0, True),
              ("Construir o painel de margem por contrato", 12, 0, False)]),
            (RH,
             "Responde por recrutamento, treinamento obrigatório e clima.",
             "Universidade corporativa e trilha de formação do vigilante.",
             "Estruturar a área de desenvolvimento humano.",
             "Assumir a diretoria de gente e gestão.",
             [("Desenhar a trilha de formação do vigilante", 11, 0, False),
              ("Levar a cobertura de reciclagem obrigatória a 100%", 12, 0, False),
              ("Conduzir a pesquisa de clima da Base Salvador", 5, 0, True)]),
        ]

        ano = ciclo.fim.year
        for (email, responsabilidades, interesses, curta, longa, acoes) in planos:
            plano = self.semear(
                "PlanoDesenvolvimento",
                PlanoDesenvolvimento,
                {"ciclo": ciclo, "pessoa": self.p(email)},
                responsabilidades=responsabilidades,
                interesses=interesses,
                aspiracao_curta=curta,
                aspiracao_longa=longa,
            )
            for descricao, mes, deslocamento_ano, concluida in acoes:
                self.semear(
                    "AcaoDesenvolvimento",
                    AcaoDesenvolvimento,
                    {"plano": plano, "descricao": descricao},
                    mes=mes,
                    ano=ano + deslocamento_ano,
                    concluida_em=date(ano, mes, 15) if concluida else None,
                )

    # ── Planos de ação com limiar ───────────────────────────────────

    def _planos_de_acao(self) -> None:
        # (regra, ocorrência, título, detalhe, responsável, prazo em dias,
        #  situação, justificativa, ação, desfecho)
        planos = [
            ("margem-abaixo-de-10", "contrato:CT-107",
             "CT-107 · Logística Pampa com margem de 4,2%", "margem de 4,2% em agosto",
             DIR_OPERACOES, 12, SituacaoPlano.ABERTO,
             "Três postos foram abertos sem repasse do reajuste de convenção.",
             "Renegociar o aditivo de reajuste e remanejar um posto para escala 12×36.", ""),
            ("margem-abaixo-de-10", "contrato:CT-110",
             "CT-110 · Supermercados Boa Praça com margem de 7,8%",
             "margem de 7,8% em agosto", GER_CAMPO, -9, SituacaoPlano.ABERTO,
             "Horas extras de cobertura acima do previsto em dois CDs.",
             "Revisar a escala do CD de Lauro de Freitas e contratar dois vigilantes.", ""),
            ("contrato-vencendo-sem-visita", "contrato:CT-104",
             "CT-104 · Hospital São Lucas vence em 46 dias sem visita registrada",
             "vencimento em 46 dias", VENDAS, 25, SituacaoPlano.ABERTO,
             "A troca do responsável comercial deixou a conta sem visita desde maio.",
             "Agendar visita de renovação com a diretoria do hospital ainda neste mês.", ""),
            ("contrato-vencendo-sem-visita", "contrato:CT-113",
             "CT-113 · Rede Farmalux vence em 58 dias sem visita registrada",
             "vencimento em 58 dias", VENDAS, 33, SituacaoPlano.ABERTO,
             "Conta atendida por telefone desde a mudança de comprador do cliente.",
             "Apresentar proposta de renovação com a nova matriz de postos.", ""),
            ("detrator-sem-tratativa", "avaliacao:CT-107:2026-09-15",
             "Cliente detrator sem tratativa — CT-107", "nota 4 na pesquisa de setembro",
             DIR_OPERACOES, 5, SituacaoPlano.ABERTO,
             "A troca de supervisor coincidiu com duas faltas de cobertura.",
             "Visita do diretor ao cliente e plano de estabilização de 30 dias.", ""),
            ("projeto-bloqueado", "projeto:PJ-202",
             "PJ-202 bloqueado há 22 dias", "bloqueado desde 31/08", GER_SUPORTE,
             -3, SituacaoPlano.ABERTO,
             "O cliente não liberou o acesso à casa de máquinas para o lançamento.",
             "Escalar para o facilities do cliente e replanejar o marco de energia.", ""),
            ("marco-vencido", "marco:PJ-200:Levantamento",
             "Marco de levantamento vencido no PJ-200", "vencido há 14 dias",
             GER_SUPORTE, 8, SituacaoPlano.ABERTO,
             "O levantamento dependia da planta atualizada, entregue com atraso.",
             "Refazer o cronograma do projeto com a data real de entrega da planta.", ""),
            ("cc-comprometido", "cc:1042",
             "Centro de custo 1042 em 94% do teto", "94% do teto em setembro",
             FINANCEIRO, 2, SituacaoPlano.ABERTO,
             "Manutenção corretiva de frota concentrada no trimestre.",
             "Abrir revisão orçamentária remanejando saldo do 1000 para o 1042.", ""),
            ("aso-vencido", "efetivo:ef-0042",
             "Vigilante com ASO vencido há 9 dias", "ASO vencido em 13/09",
             SESMT, 1, SituacaoPlano.ABERTO,
             "A clínica cancelou a agenda de exames periódicos de setembro.",
             "Reagendar o exame e afastar o colaborador do posto até a liberação.", ""),
            ("reciclagem-vencida", "efetivo:ef-0117",
             "Vigilante com reciclagem vencida", "reciclagem vencida em 02/09",
             RH, -6, SituacaoPlano.ABERTO,
             "A turma de reciclagem de agosto foi cancelada por falta de quórum.",
             "Matricular na turma de outubro e remanejar para posto desarmado.", ""),
            ("solicitacao-parada", "solicitacao:7",
             "Prestação de contas parada há 11 dias", "sem movimento desde 11/09",
             FINANCEIRO, -1, SituacaoPlano.ABERTO,
             "O comprovante enviado estava ilegível e o pedido ficou aguardando.",
             "Solicitar o comprovante por comentário e definir prazo de 3 dias.", ""),
            ("leitura-nao-confirmada", "documento:pop-ronda-noturna",
             "POP-001 sem confirmação de leitura de 7 pessoas",
             "7 pendências de leitura", OPERACAO, -18, SituacaoPlano.RESOLVIDO,
             "O POP foi publicado durante a escala de férias da supervisão.",
             "Cobrar a leitura na passagem de turno e no mural dos postos.",
             "A regra parou de apontar pendência na verificação de vencimento."),
            ("normativo-sem-revisao", "documento:politica-uso-de-radio",
             "Política de rádio sem revisão há 14 meses", "última revisão em julho de 2025",
             QUALIDADE, -40, SituacaoPlano.RESOLVIDO,
             "A revisão anual não estava no calendário da Qualidade.",
             "Revisar o texto com a Operação e publicar a versão 2.1.",
             "Versão 2.1 publicada; a regra não aponta mais o normativo."),
            ("layer3-sem-apresentacao", "contrato:CT-101",
             "CT-101 · Rede Aurora sem apresentação de resultado",
             "sem apresentação no trimestre", VENDAS, -25, SituacaoPlano.NAO_RESOLVIDO,
             "A agenda com o cliente foi remarcada três vezes no trimestre.",
             "Fixar a apresentação trimestral no calendário do cliente.",
             "A reverificação encontrou a ocorrência de novo — segue sem apresentação."),
            ("advertencias", "efetivo:ef-0088",
             "Colaborador com quatro advertências em 12 meses", "4 advertências",
             RH, -52, SituacaoPlano.NAO_RESOLVIDO,
             "Reincidência de atraso no posto do turno da madrugada.",
             "Conversa formal com o RH e mudança de escala para o turno diurno.",
             "A quinta advertência foi registrada dentro do prazo do plano."),
        ]

        for (regra, ocorrencia, titulo, detalhe, email, prazo, situacao,
             justificativa, acao, desfecho) in planos:
            fechado = situacao != SituacaoPlano.ABERTO
            plano = self.semear(
                "PlanoAcao",
                PlanoAcao,
                {"regra_chave": regra, "ocorrencia_chave": ocorrencia},
                titulo=titulo,
                detalhe=detalhe,
                justificativa=justificativa,
                acao=acao,
                responsavel=self.p(email),
                prazo=self.dia(prazo),
                situacao=situacao,
                desfecho=desfecho,
                aberto_por=self.p(QUALIDADE),
                fechado_em=self.momento(prazo, 7) if fechado else None,
            )

            # A série de reverificações. Mais de uma no plano que reabriu: é
            # esse padrão — o problema que some e volta — que o model existe
            # para deixar visível.
            verificacoes = [
                ("Reverificação automática no vencimento do plano.",
                 situacao == SituacaoPlano.NAO_RESOLVIDO or not fechado,
                 True, prazo),
            ]
            if situacao == SituacaoPlano.NAO_RESOLVIDO:
                verificacoes.append(
                    ("Segunda reverificação, sete dias depois.", True, True, prazo + 7)
                )
            if regra == "cc-comprometido":
                verificacoes.append(
                    ("Fonte do orçamento fora do ar — plano não avaliado.",
                     False, False, prazo - 5)
                )
            for observacao, ainda, avaliada, dias in verificacoes:
                self.semear(
                    "VerificacaoPlano",
                    VerificacaoPlano,
                    {"plano": plano, "observacao": observacao},
                    verificado_em=self.momento(min(dias, 0), 6),
                    ainda_ocorre=ainda,
                    avaliada=avaliada,
                )

    # ── CIC · ocorrências de ciclo e ATAs ───────────────────────────

    def _ocorrencias_de_ciclo(self, documentos: dict[str, Documento]) -> None:
        ciclos = {c.chave: c for c in CicloPlanejamento.objects.all()}
        if not ciclos:
            self.pular("OcorrenciaCiclo", "nenhum CicloPlanejamento cadastrado")
            return

        mensal = ciclos.get("mensal") or next(iter(ciclos.values()))
        trimestral = ciclos.get("trimestral")

        # As anotações que se repetem por reunião, por código de etapa.
        falas = {
            "CP01": ("O mês fechou 3,1% acima do orçado, puxado por dois contratos "
                     "novos na Base Salvador.",
                     "Levar a abertura por contrato na próxima reunião.", 20),
            "CP02": ("Duas exceções seguem abertas: margem do CT-107 e reciclagem "
                     "vencida de um vigilante.",
                     "Plano de ação do CT-107 revisado até o fim da semana.", 5),
            "CP03": ("A adoção do módulo de reserva subiu; correspondência segue "
                     "com pouca confirmação de retirada.", "", None),
            "CP04": ("A fila de Suprimentos está em 4 dias de espera média, dentro "
                     "do acordado.", "", None),
            "CP05": ("Três pedidos aguardam aprovação há mais de três dias, todos "
                     "do centro de custo 1042.",
                     "Diretoria decide o remanejamento orçamentário.", 8),
            "CP06": ("O efetivo caiu 4 pessoas no mês; duas saídas foram do posto "
                     "do Portal Norte.",
                     "RH apresenta o plano de reposição na próxima reunião.", 25),
            "CP07": ("O POP-003 vence em 25 dias e ainda não foi revisado.",
                     "SESMT assume a revisão do POP-003.", 20),
            "CP08": ("Uma multa em recurso e a revisão do Ducato concluída.", "", None),
            "CP09": ("Estoque de colete refletivo abaixo do mínimo na Base Salvador.",
                     "Compras emite o pedido de reposição.", 10),
            "CP10": ("Quatro editais do PNCP entraram no radar; dois com prazo neste mês.",
                     "Comercial decide sobre o edital do TRT-5 até sexta.", 3),
            "CP11": ("A carga do monday atrasou 9 horas no dia da reunião; o "
                     "restante das fontes está em dia.", "", None),
            "CP12": ("Encaminhamentos registrados e responsáveis confirmados em sala.",
                     "", None),
        }

        hoje = self.hoje
        # A reunião do mês corrente aberta, e as duas anteriores fechadas. É a
        # sequência que faz a tela ter histórico e trabalho em aberto ao mesmo
        # tempo.
        competencias = []
        for recuo in (0, 1, 2):
            total = hoje.month - 1 - recuo
            competencias.append((hoje.year + total // 12, total % 12 + 1, recuo == 0))

        for ano, mes, aberta in competencias:
            ata = None
            if not aberta:
                ata = self.semear(
                    "Documento",
                    Documento,
                    {"slug": f"ata-mensal-{ano}-{mes:02d}"},
                    tipo=TipoDocumento.ATA,
                    titulo=f"ATA · Ciclo mensal {mes:02d}/{ano}",
                    categoria="Governança",
                    resumo="Registro do que foi visto e decidido na reunião mensal.",
                    corpo=(
                        "ATA gerada ao fechar a reunião, com os carimbos de frescor "
                        "congelados. Conteúdo de demonstração."
                    ),
                    dono=self.p(DIRETORIA),
                    versao="1.0",
                    publico_alvo=mensal.alvo_da_ata or ["papel:diretoria"],
                    leitura_obrigatoria=False,
                    vigencia_inicio=date(ano, mes, min(28, monthrange(ano, mes)[1])),
                    vigencia_fim=None,
                    situacao=SituacaoDocumento.VIGENTE,
                )

            ocorrencia = self.semear(
                "OcorrenciaCiclo",
                OcorrenciaCiclo,
                {"ciclo": mensal, "ano": ano, "mes": mes},
                situacao=(
                    SituacaoOcorrencia.ABERTA if aberta else SituacaoOcorrencia.FECHADA
                ),
                conduzida_por=self.p(DIRETORIA),
                fechada_em=None if aberta else self.momento(-28 * (hoje.month - mes or 1), 17),
                impedimentos=(
                    [{
                        "etapa": "CP11",
                        "titulo": "De onde vieram os números",
                        "carimbo": "monday · última carga há 9h",
                        "motivo": "Fonte atrasada em relação à cadência prometida.",
                    }]
                    if not aberta else []
                ),
                ata=ata,
            )

            etapas = list(ocorrencia.ciclo.etapas.all())
            # A reunião aberta é anotada só até onde ela chegou. Anotar tudo
            # faria "em andamento" parecer "fechada" na tela.
            if aberta:
                etapas = etapas[:5]
            for etapa in etapas:
                fala = falas.get(etapa.codigo)
                if fala is None:
                    continue
                texto, encaminhamento, prazo = fala
                self.semear(
                    "AnotacaoEtapa",
                    AnotacaoEtapa,
                    {"ocorrencia": ocorrencia, "etapa": etapa},
                    texto=texto,
                    encaminhamento=encaminhamento,
                    prazo=self.dia(prazo) if prazo is not None else None,
                    autor=self.p(DIRETORIA),
                    carimbo_fonte="sankhya",
                    carimbo_texto="Sankhya · carga das 06:12",
                    carimbo_alerta=etapa.codigo == "CP11" and not aberta,
                )

        if trimestral is not None:
            # O trimestre fechado mais recente.
            mes_trimestre = ((self.hoje.month - 1) // 3) * 3 or 12
            ano_trimestre = self.hoje.year if mes_trimestre != 12 else self.hoje.year - 1
            ocorrencia = self.semear(
                "OcorrenciaCiclo",
                OcorrenciaCiclo,
                {"ciclo": trimestral, "ano": ano_trimestre, "mes": mes_trimestre},
                situacao=SituacaoOcorrencia.FECHADA,
                conduzida_por=self.p(SOCIO),
                fechada_em=self.momento(-80, 18),
                impedimentos=[],
                ata=None,
            )
            for etapa in trimestral.etapas.all():
                fala = falas.get(etapa.codigo)
                if fala is None:
                    continue
                texto, encaminhamento, prazo = fala
                self.semear(
                    "AnotacaoEtapa",
                    AnotacaoEtapa,
                    {"ocorrencia": ocorrencia, "etapa": etapa},
                    texto=texto,
                    encaminhamento=encaminhamento,
                    prazo=self.dia(prazo) if prazo is not None else None,
                    autor=self.p(SOCIO),
                    carimbo_fonte="sankhya",
                    carimbo_texto="Sankhya · carga do fechamento trimestral",
                    carimbo_alerta=False,
                )

    # ── ECO · concentrações ─────────────────────────────────────────

    def _concentracoes(self) -> None:
        # (tipo, referência, título, motivo, próximo passo, responsável,
        #  prazo, encerrada há, resultado)
        pauta = [
            (OrigemConcentracao.CONTRATO, "CT-107",
             "Recuperar a margem do CT-107 · Logística Pampa",
             "A margem está abaixo de 10% há quatro meses e o contrato renova em "
             "janeiro. É o maior contrato da carteira e o que mais consome "
             "supervisão.",
             "Fechar o aditivo de reajuste com o cliente.", DIR_OPERACOES, 18, None, ""),
            (OrigemConcentracao.CONTRATO, "CT-104",
             "Renovar o CT-104 · Hospital São Lucas",
             "Contrato vence em 46 dias e ainda não houve visita de renovação. "
             "Perder a conta levaria 22 postos de uma vez.",
             "Visita da diretoria com proposta de renovação por 24 meses.",
             VENDAS, 30, None, ""),
            (OrigemConcentracao.CONTRATO, "CT-110",
             "Estabilizar a cobertura no CT-110 · Boa Praça",
             "Duas faltas de cobertura no mês geraram reclamação formal do cliente.",
             "Contratar dois vigilantes e revisar a escala do CD.", GER_CAMPO, -6, None, ""),
            (OrigemConcentracao.CONTRATO, "CT-101",
             "Apresentação trimestral de resultado à Rede Aurora",
             "O contrato é Layer 3 e não recebe apresentação há dois trimestres. "
             "É a conta mais antiga da empresa.",
             "Fixar a data da apresentação com o cliente.", VENDAS, -14, None, ""),
            (OrigemConcentracao.AREA, "area-03",
             "Reduzir a hora extra da Área 03",
             "A área respondeu por 41% da hora extra do trimestre com 22% do efetivo.",
             "Revisar o dimensionamento dos seis postos de maior custo.",
             DIR_OPERACOES, 45, None, ""),
            (OrigemConcentracao.AREA, "area-05",
             "Implantar a conferência diária de efetivo na Área 05",
             "A área é a que mais gera exceção de cobertura, e a conferência hoje é "
             "feita por planilha do supervisor.",
             "Treinar os supervisores no módulo de campo.", GER_CAMPO, None, None, ""),
            (OrigemConcentracao.INDICADOR, "turnover_pct",
             "Turnover do efetivo operacional",
             "O turnover está em 4,1% contra a meta de 3%. Cada saída custa uma "
             "reciclagem e trinta dias de cobertura.",
             "Plano de retenção com ajuste de escala e vale-transporte.", RH, 60, None, ""),
            (OrigemConcentracao.INDICADOR, "margem_contribuicao",
             "Margem de contribuição da carteira",
             "Três contratos abaixo de 10% derrubam a média da carteira.",
             "Revisar a precificação dos contratos com reajuste vencido.",
             FINANCEIRO, 25, None, ""),
            (OrigemConcentracao.CONTRATO, "CT-113",
             "Renovação antecipada do CT-113 · Rede Farmalux",
             "O cliente abriu cotação com concorrente e a renovação venceria em "
             "novembro.",
             "", VENDAS, None, 20,
             "Renovado por 24 meses com reajuste de 6,2%. A cotação do concorrente "
             "não avançou."),
            (OrigemConcentracao.CONTRATO, "CT-109",
             "Regularizar o CFTV do Frigorífico Serra Azul",
             "Oito câmeras do perímetro estavam fora de operação desde julho.",
             "", GER_SUPORTE, None, 12,
             "Perímetro restabelecido em 20/08 e vistoria aceita pelo cliente."),
            (OrigemConcentracao.AREA, "area-01",
             "Cobertura de reciclagem obrigatória na Área 01",
             "Onze colaboradores estavam com NR vencida ou a vencer em 30 dias.",
             "", RH, None, 35,
             "Turmas extras em julho e agosto zeraram a pendência da área."),
            (OrigemConcentracao.INDICADOR, "absenteismo_pct",
             "Absenteísmo na Base Salvador",
             "O absenteísmo passou de 5% em dois meses consecutivos.",
             "", GER_CAMPO, None, 50,
             "Caiu para 3,4% após o ajuste de escala. Segue em acompanhamento "
             "pelo painel, sem concentração aberta."),
        ]

        for (tipo, ref, titulo, motivo, passo, email, prazo, encerrada, resultado) in pauta:
            self.semear(
                "Concentracao",
                Concentracao,
                {"origem_tipo": tipo, "origem_ref": ref, "titulo": titulo},
                motivo=motivo,
                proximo_passo=passo,
                responsavel=self.p(email),
                prazo=self.dia(prazo) if prazo is not None else None,
                aberta_por=self.p(DIRETORIA),
                encerrada_em=self.momento(-encerrada, 16) if encerrada else None,
                resultado=resultado,
            )

    # ── WKF · comentários nos pedidos ───────────────────────────────

    def _comentarios(self) -> None:
        pedidos = list(SolicitacaoServico.objects.order_by("pk"))
        if not pedidos:
            self.pular("ComentarioSolicitacao", "nenhuma SolicitacaoServico cadastrada")
            return

        # (autor, texto, interno) — aplicados em rodízio sobre os pedidos.
        conversa = [
            (SUPRIMENTOS, "Recebido. Confirma para qual posto é a entrega?", False),
            (SUPRIMENTOS, "Conferir se o contrato com o fornecedor cobre este item "
                          "antes de emitir o pedido.", True),
            (COMPRAS, "Orçamento com três fornecedores anexado. O menor preço tem "
                      "prazo de 12 dias.", False),
            (FINANCEIRO, "Centro de custo 1042 já está em 94% do teto — precisa da "
                         "revisão orçamentária antes de aprovar.", True),
            (FINANCEIRO, "Comprovante ilegível. Pode reenviar a foto da nota com o "
                         "CNPJ visível?", False),
            (TI, "Acesso liberado no perfil padrão. A VPN exige o segundo fator no "
                 "primeiro acesso.", False),
            (TI, "Conta criada fora do padrão de nomenclatura — corrigir no "
                 "próximo ciclo de revisão.", True),
            (RH, "A reciclagem foi remanejada para a turma de outubro por falta de "
                 "quórum em setembro.", False),
            (GER_CAMPO, "De acordo. O colaborador fica em posto desarmado até a "
                        "conclusão.", False),
            (OPERACAO, "Entrega feita no posto ontem às 10h, conferida pela "
                       "supervisão.", False),
            (SUPRIMENTOS, "Item entregue. Termo de custódia assinado e arquivado.", False),
            (COMPRAS, "Fornecedor atrasou a entrega em 4 dias. Registrar no "
                      "histórico do contrato.", True),
            (ANALISTA, "Sem movimento há 11 dias. Estou cobrando o solicitante por "
                       "aqui para não perder a posição na fila.", False),
            (RECEPCAO, "Chegou correspondência relacionada a este pedido; está na "
                       "recepção da Matriz.", False),
            (GER_SUPORTE, "Equipamento testado em bancada antes do envio.", False),
            (QUALIDADE, "Pedido usado como exemplo no treinamento do fluxo.", True),
            (JURIDICO, "O contrato do fornecedor não prevê este item. Vamos precisar "
                       "de um aditivo.", True),
            (DIR_OPERACOES, "Aprovado do meu lado. Prioridade alta por causa do "
                            "prazo do cliente.", False),
        ]

        for posicao, (email, texto, interno) in enumerate(conversa):
            pedido = pedidos[posicao % len(pedidos)]
            self.semear(
                "ComentarioSolicitacao",
                ComentarioSolicitacao,
                {"solicitacao": pedido, "autor": self.p(email), "texto": texto},
                interno=interno,
            )

    # ── FIN · lançamentos ───────────────────────────────────────────

    # ── O que NÃO mora aqui ─────────────────────────────────────────
    #
    # `financas.Lancamento` e `resultados.EditalPublico` também ficavam vazios,
    # mas `workspace` é a FOLHA da árvore de dependências: ele não importa app
    # de domínio, consome tudo por provider, e
    # `test_workspace_nao_importa_app_de_dominio` cobra isso. Os dois têm
    # semeadora no app dono:
    #
    #     python manage.py semear_lancamentos --aplicar   # financas
    #     python manage.py semear_editais     --aplicar   # cargas → resultados

    # ── Saída ───────────────────────────────────────────────────────

    def _resumo(self, aplicar: bool) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Demonstração"))
        self.stdout.write(f"  {'modelo':26} {'criados':>8} {'já existiam':>12}")
        total_criado = total_existente = 0
        for rotulo in sorted(self.contagem):
            criados, existentes = self.contagem[rotulo]
            total_criado += criados
            total_existente += existentes
            self.stdout.write(f"  {rotulo:26} {criados:>8} {existentes:>12}")
        self.stdout.write(f"  {'TOTAL':26} {total_criado:>8} {total_existente:>12}")

        if self.pulados:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Pulados (dependência ausente):"))
            for linha in self.pulados:
                self.stdout.write(f"  · {linha}")

        self.stdout.write("")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("✓ Aplicado."))
            self.stdout.write(
                "Rode `python manage.py reindexar_busca` para o acervo novo entrar na busca."
            )
        else:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada gravado. Rode de novo com --aplicar.")
            )
