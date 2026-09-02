"""As dezenove regras de exceção, mais as que ficam registradas e desligadas.

## Por que as desligadas entram

`RegraExcecao` com `ativa=False` responde "por que não vigiamos ASO?" sem
ninguém precisar perguntar — e impede a mesma discussão de voltar em seis meses.
Cada uma traz a fonte de que depende anotada, então a pergunta seguinte
("quando vamos vigiar?") também já tem resposta.

Deixá-las fora do banco tornaria a decisão invisível, e decisão invisível é
decisão que se retoma.

## O que a semeadora NÃO faz

Não reativa regra desligada à mão. Desligar uma regra é decisão de quem opera —
quase sempre porque ela está gerando ruído — e a semeadora roda no deploy
seguinte, que é exatamente quando desfazer isso seria pior.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from workspace.models.excecao import RegraExcecao, Severidade

#: As dezenove. `janela` em DIAS, exceto em `cc-comprometido`, onde ela é
#: percentual — a única exceção, anotada na própria regra.
REGRAS = (
    # ── As dez do próprio Workspace ─────────────────────────────────
    {
        "chave": "lotacao-sem-cc", "ordem": 10,
        "titulo": "Lotação sem centro de custo",
        "descricao_curta": "Pessoa no organograma sem código de centro de custo. "
                           "O primeiro pedido que exigir um será recusado.",
        "severidade": Severidade.ALTA, "escopo_papel": "rh",
    },
    {
        "chave": "pessoa-sem-papel", "ordem": 20,
        "titulo": "Pessoa sem papel vigente",
        "descricao_curta": "Está no organograma e não tem papel: nenhuma fila "
                           "abre, nenhuma bandeja recebe.",
        "severidade": Severidade.ALTA, "escopo_papel": "rh",
    },
    {
        "chave": "papel-vencendo", "ordem": 30, "janela": 30,
        "titulo": "Papel vencendo em 30 dias",
        "descricao_curta": "Papel que vence sem renovação tira a pessoa da fila "
                           "em silêncio.",
        "severidade": Severidade.MEDIA, "escopo_papel": "rh",
    },
    {
        "chave": "solicitacao-parada", "ordem": 40,
        "titulo": "Solicitação parada além do prazo",
        "descricao_curta": "Pedido em aberto além do prazo que a pessoa viu ao "
                           "pedir.",
        "severidade": Severidade.ALTA, "escopo_papel": "",
    },
    {
        "chave": "aprovacao-pendente", "ordem": 50, "janela": 3,
        "titulo": "Aprovação pendente há mais de 3 dias",
        "descricao_curta": "O pedido está parado em ALGUÉM, e não em alguma "
                           "coisa.",
        "severidade": Severidade.ALTA, "escopo_papel": "",
    },
    {
        "chave": "leitura-nao-confirmada", "ordem": 60,
        "titulo": "Leitura obrigatória não confirmada",
        "descricao_curta": "Normativo obrigatório sem confirmação da versão "
                           "atual. A linha é o documento, não quem não leu.",
        "severidade": Severidade.MEDIA, "escopo_papel": "rh",
    },
    {
        "chave": "normativo-sem-revisao", "ordem": 70, "janela": 365,
        "titulo": "Normativo sem revisão há 12 meses",
        "descricao_curta": "Normativo velho é pior que ausente: tem autoridade "
                           "e está errado.",
        "severidade": Severidade.MEDIA, "escopo_papel": "rh",
    },
    {
        "chave": "cc-sem-orcamento", "ordem": 80,
        "titulo": "Centro de custo sem orçamento",
        "descricao_curta": "A bandeja não consegue calcular impacto, e quem lê "
                           "conclui que a barra está quebrada.",
        "severidade": Severidade.MEDIA, "escopo_papel": "financeiro",
        "fonte_requerida": "financas",
    },
    {
        "chave": "cc-comprometido", "ordem": 90, "janela": 90,
        "titulo": "Centro de custo acima de 90% do teto",
        "descricao_curta": "Noventa e não cem: em cem já estourou, e a exceção "
                           "existe para aparecer antes. A janela aqui é "
                           "PERCENTUAL, e não dias.",
        "severidade": Severidade.ALTA, "escopo_papel": "financeiro",
        "fonte_requerida": "financas",
    },
    {
        "chave": "reserva-sem-uso", "ordem": 100, "janela": 7,
        "titulo": "Reserva confirmada e não usada",
        "descricao_curta": "Sala reservada e vazia é sala que faltou para outra "
                           "equipe.",
        "severidade": Severidade.BAIXA, "escopo_papel": "",
    },
    # ── As seis que a ingestão destravou ────────────────────────────
    {
        "chave": "margem-abaixo-de-10", "ordem": 110, "janela": 10,
        "titulo": "Contrato com margem abaixo de 10%",
        "descricao_curta": "A regra dos 10% do benchmark: não é alerta, é "
                           "obrigação. Contrato sem amostra fica de fora.",
        "severidade": Severidade.ALTA, "escopo_papel": "financeiro",
        "fonte_requerida": "iconnect_platform",
    },
    {
        "chave": "contrato-vencendo-sem-visita", "ordem": 120, "janela": 60,
        "titulo": "Contrato vencendo em 60 dias",
        "descricao_curta": "A visita ainda NÃO é verificável aqui — ela mora no "
                           "Platform. A regra lista os que vencem e diz isso.",
        "severidade": Severidade.ALTA, "escopo_papel": "vendas",
        "fonte_requerida": "iconnect_platform",
    },
    {
        "chave": "layer3-sem-apresentacao", "ordem": 130,
        "titulo": "Contrato Layer 3 sem apresentação",
        "descricao_curta": "Só a Layer 3 deve apresentação. A apresentação ainda "
                           "não é registrada aqui.",
        "severidade": Severidade.MEDIA, "escopo_papel": "diretoria",
        "fonte_requerida": "iconnect_platform",
    },
    {
        "chave": "detrator-sem-tratativa", "ordem": 140, "janela": 90,
        "titulo": "Cliente detrator sem tratativa",
        "descricao_curta": "Com tratativa é trabalho em andamento; sem, é uma "
                           "pessoa esperando.",
        "severidade": Severidade.ALTA, "escopo_papel": "operacao",
        "fonte_requerida": "iconnect_platform",
    },
    {
        "chave": "projeto-bloqueado", "ordem": 150, "janela": 15,
        "titulo": "Projeto bloqueado há mais de 15 dias",
        "descricao_curta": "O motivo vem junto: bloqueio sem motivo é bandeira "
                           "vermelha que ninguém sabe o que fazer com.",
        "severidade": Severidade.MEDIA, "escopo_papel": "operacao",
        "fonte_requerida": "monday",
    },
    {
        "chave": "marco-vencido", "ordem": 160,
        "titulo": "Marco vencido sem replanejamento",
        "descricao_curta": "Se alguém tivesse replanejado, o prazo seria outro.",
        "severidade": Severidade.MEDIA, "escopo_papel": "operacao",
        "fonte_requerida": "monday",
    },
    # ── As duas que vigiam o mecanismo ──────────────────────────────
    {
        "chave": "fonte-atrasada", "ordem": 170,
        "titulo": "Fonte sem carga além da cadência",
        "descricao_curta": "A régua é a idade que a PRÓPRIA fonte declarou "
                           "aceitável. Fonte não configurada fica de fora.",
        "severidade": Severidade.ALTA, "escopo_papel": "",
        "fonte_requerida": "cargas",
    },
    {
        "chave": "divergencia-entre-fontes", "ordem": 180,
        "titulo": "Divergência entre fontes",
        "descricao_curta": "Aparece mesmo quando a precedência resolveu o "
                           "valor: resolver não é concordar.",
        "severidade": Severidade.MEDIA, "escopo_papel": "",
        "fonte_requerida": "cargas",
    },
)

#: Registradas e DESLIGADAS, com a fonte anotada.
#:
#: A 19 espera o orçamento nascer aqui dentro (onda do ciclo orçamentário); as
#: outras esperam o SSO, porque a fonte delas é o HRIS e o Entra ID (ADR-013).
#:
#: **Nenhuma delas pode chegar à grade com CPF.** Quando forem ligadas, a linha
#: é o registro — "efetivo do CC 1042" —, e nunca a pessoa com documento ao
#: lado. É o que a leitura do benchmark marcou como não copiar.
DESLIGADAS = (
    {
        "chave": "cc-sem-orcado-e-o-inverso", "ordem": 190,
        "titulo": "Centro de custo no ERP e fora do orçamento (e o inverso)",
        "descricao_curta": "A conciliação de códigos entre Sankhya e o "
                           "orçamento. Só passa a valer quando o orçamento "
                           "existir aqui dentro.",
        "severidade": Severidade.ALTA, "escopo_papel": "financeiro",
        "fonte_requerida": "sankhya + financas",
    },
    {
        "chave": "aso-vencido", "ordem": 200,
        "titulo": "Efetivo com ASO vencido",
        "descricao_curta": "Depende do HRIS, que chega com o SSO (ADR-013). "
                           "Quando ligar, a linha é o centro de custo — nunca a "
                           "pessoa com documento ao lado.",
        "severidade": Severidade.ALTA, "escopo_papel": "sesmt",
        "fonte_requerida": "hris",
    },
    {
        "chave": "reciclagem-vencida", "ordem": 210,
        "titulo": "Efetivo com reciclagem vencida",
        "descricao_curta": "Mesma fonte e mesma espera do ASO.",
        "severidade": Severidade.ALTA, "escopo_papel": "sesmt",
        "fonte_requerida": "hris",
    },
    {
        "chave": "advertencias", "ordem": 220,
        "titulo": "Efetivo com mais de três advertências",
        "descricao_curta": "Depende do HRIS. Dado disciplinar nominal em grade "
                           "é decisão de produto antes de ser de implementação.",
        "severidade": Severidade.MEDIA, "escopo_papel": "rh",
        "fonte_requerida": "hris",
    },
    {
        "chave": "experiencia-vencendo", "ordem": 230,
        "titulo": "Contrato de experiência vencendo em 30 dias",
        "descricao_curta": "Depende do HRIS, que chega com o SSO.",
        "severidade": Severidade.MEDIA, "escopo_papel": "rh",
        "fonte_requerida": "hris",
    },
)


class Command(BaseCommand):
    help = "Cadastra as regras do painel de exceções."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        criadas = atualizadas = 0

        for dados in (*REGRAS, *DESLIGADAS):
            desligada = dados in DESLIGADAS
            existente = RegraExcecao.objects.filter(chave=dados["chave"]).first()
            if existente is None:
                criadas += 1
                self.stdout.write(
                    f"  + {dados['chave']}"
                    + ("  (registrada e DESLIGADA)" if desligada else "")
                )
                if aplicar:
                    RegraExcecao.objects.create(ativa=not desligada, **dados)
                continue

            # Atualiza o TEXTO e a ordem; nunca `ativa`. Desligar uma regra é
            # decisão de quem opera — quase sempre porque ela está gerando
            # ruído —, e a semeadora roda no deploy seguinte.
            mudou = False
            for campo, valor in dados.items():
                if campo == "chave":
                    continue
                if getattr(existente, campo) != valor:
                    setattr(existente, campo, valor)
                    mudou = True
            if mudou:
                atualizadas += 1
                self.stdout.write(f"  ~ {dados['chave']}")
                if aplicar:
                    existente.save()

        resumo = (
            f"{criadas} regra(s) nova(s), {atualizadas} atualizada(s). "
            f"{len(REGRAS)} ligadas, {len(DESLIGADAS)} registradas e desligadas."
        )
        if aplicar:
            self.stdout.write(self.style.SUCCESS(resumo))
        else:
            self.stdout.write(self.style.WARNING(f"SIMULAÇÃO — {resumo}"))
            self.stdout.write("Rode de novo com --aplicar para gravar.")
