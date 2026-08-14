"""Leva ao banco já semeado o que os apontamentos de R.H., Redes e Universidade
pediram: escolha em vez de texto livre, ramo, passos, e os itens de vaga.

Mesma razão das 0011, 0013 e 0015: `semear_catalogo` casa por `chave` e não
sobrescreve item existente, então mudar `catalogo_inicial.py` não muda nada em
banco que já rodou o semeador.

Esta migração é mais invasiva que as anteriores, e de propósito: aqui campos
**mudam de tipo** (`sistema` era texto e vira escolha) e um item **muda de
chave** (`reembolso` → `prestacao-contas`). Acrescentar sem substituir deixaria
o formulário com as duas versões da mesma pergunta.

O que ela NÃO faz: mexer nos pedidos já criados. Um pedido antigo de acesso a
sistema continua com `dados["sistema"] = "aquele portal da operadora"` em texto
livre — é o que a pessoa respondeu, e reescrever resposta de alguém para caber
numa lista nova seria inventar dado. A lista fechada vale dali para a frente.
"""

from django.db import migrations

# Os itens que ganham (ou trocam) campos, na forma final. Escrito à mão, e não
# lido de `catalogo_inicial.py`, porque migração é retrato de um ponto da
# história: se a semente mudar de novo, esta continua aplicando o que aplicava
# hoje.
CAMPOS = {
    "acesso-vpn": [
        {"chave": "motivo", "rotulo": "Motivo", "tipo": "texto_longo",
         "obrigatorio": True, "ajuda": "Para que você vai usar a VPN."},
        {"chave": "periodo", "rotulo": "Período", "tipo": "escolha",
         "obrigatorio": True,
         "opcoes": [
             {"valor": "temporario", "rotulo": "Temporário"},
             {"valor": "definitivo", "rotulo": "Definitivo"},
         ]},
        {"chave": "ate_quando", "rotulo": "Até quando", "tipo": "data",
         "obrigatorio": True,
         "quando": {"campo": "periodo", "igual": "temporario"},
         "ajuda": "O acesso é removido nesta data."},
    ],
    "acesso-sistema": [
        {"chave": "sistema", "rotulo": "Qual sistema", "tipo": "escolha",
         "obrigatorio": True,
         "opcoes": [
             {"valor": "iconnect", "rotulo": "iConnect Platform"},
             {"valor": "m365", "rotulo": "Microsoft 365 / SharePoint"},
             {"valor": "portal-operadora", "rotulo": "Portal de operadora"},
             {"valor": "erp", "rotulo": "ERP / Financeiro"},
             {"valor": "outro", "rotulo": "Outro — diga no motivo"},
         ]},
        {"chave": "motivo", "rotulo": "Motivo", "tipo": "texto_longo",
         "obrigatorio": True,
         "ajuda": "Por que você precisa deste acesso, e para qual trabalho."},
        {"chave": "nivel", "rotulo": "Nível de acesso", "tipo": "escolha",
         "obrigatorio": False,
         "opcoes": [
             {"valor": "leitura", "rotulo": "Leitura"},
             {"valor": "operacao", "rotulo": "Operação"},
             {"valor": "administracao", "rotulo": "Administração"},
         ]},
    ],
    "reciclagem-nr": [
        {"chave": "habilitacao", "rotulo": "Qual documento vai vencer",
         "tipo": "texto", "obrigatorio": True, "passo": 1,
         "ajuda": "NR-10, NR-35, curso de operador, CNH especial…"},
        {"chave": "vencimento", "rotulo": "Vence em", "tipo": "data",
         "obrigatorio": True, "passo": 1},
        {"chave": "para_quem", "rotulo": "Para quem é", "tipo": "escolha",
         "obrigatorio": True, "passo": 2,
         "opcoes": [
             {"valor": "propria", "rotulo": "Para mim"},
             {"valor": "terceiro", "rotulo": "Para um técnico terceiro"},
         ]},
        {"chave": "tecnico_nome", "rotulo": "Nome do técnico", "tipo": "texto",
         "obrigatorio": True, "passo": 2,
         "quando": {"campo": "para_quem", "igual": "terceiro"}},
        {"chave": "tecnico_documento", "rotulo": "CPF do técnico", "tipo": "texto",
         "obrigatorio": True, "passo": 2,
         "quando": {"campo": "para_quem", "igual": "terceiro"}},
        {"chave": "tecnico_empresa", "rotulo": "Empresa do técnico", "tipo": "texto",
         "obrigatorio": True, "passo": 2,
         "quando": {"campo": "para_quem", "igual": "terceiro"}},
        {"chave": "tecnico_responsavel",
         "rotulo": "Responsável por ele, e como falar com ele",
         "tipo": "texto_longo", "obrigatorio": True, "passo": 2,
         "quando": {"campo": "para_quem", "igual": "terceiro"},
         "ajuda": "Nome, telefone e e-mail. O técnico terceiro não acessa o "
                  "Workspace — tudo é tratado direto com o responsável."},
    ],
    "treinamento": [
        {"chave": "origem", "rotulo": "Que tipo de curso", "tipo": "escolha",
         "obrigatorio": True, "passo": 1,
         "opcoes": [
             {"valor": "interno", "rotulo": "Curso interno da empresa"},
             {"valor": "externo", "rotulo": "Curso externo"},
         ]},
        {"chave": "curso_interno", "rotulo": "Qual curso", "tipo": "escolha",
         "obrigatorio": True, "passo": 2,
         "quando": {"campo": "origem", "igual": "interno"},
         "opcoes": [
             {"valor": "integracao", "rotulo": "Integração de novos colaboradores"},
             {"valor": "seguranca", "rotulo": "Segurança do trabalho"},
             {"valor": "iconnect", "rotulo": "iConnect Platform na prática"},
             {"valor": "atendimento", "rotulo": "Atendimento ao cliente"},
             {"valor": "lideranca", "rotulo": "Liderança e gestão de equipe"},
         ]},
        {"chave": "instituicao", "rotulo": "Empresa ou instituição do curso",
         "tipo": "texto", "obrigatorio": True, "passo": 2,
         "quando": {"campo": "origem", "igual": "externo"}},
        {"chave": "curso", "rotulo": "Qual curso", "tipo": "texto",
         "obrigatorio": True, "passo": 2,
         "quando": {"campo": "origem", "igual": "externo"}},
        {"chave": "inicio", "rotulo": "Começa em", "tipo": "data",
         "obrigatorio": True, "passo": 2,
         "quando": {"campo": "origem", "igual": "externo"}},
        {"chave": "periodo", "rotulo": "Período e carga horária", "tipo": "texto",
         "obrigatorio": True, "passo": 2,
         "quando": {"campo": "origem", "igual": "externo"},
         "ajuda": "Ex.: 4 sábados, 32 h no total."},
        {"chave": "aplicacao", "rotulo": "Como vai aplicar no trabalho",
         "tipo": "texto_longo", "obrigatorio": True, "passo": 3},
    ],
}

PASSOS = {
    "reciclagem-nr": [{"titulo": "O que vence"}, {"titulo": "De quem é"}],
    "treinamento": [
        {"titulo": "Interno ou externo"},
        {"titulo": "O curso"},
        {"titulo": "Aplicação"},
    ],
    "prestacao-contas": [
        {"titulo": "As compras"},
        {"titulo": "Adiantamento"},
        {"titulo": "Acerto", "apos_envio": True},
    ],
    "abertura-vaga": [{"titulo": "A vaga"}, {"titulo": "Por quê"}],
}

VALOR_QUANDO = {"treinamento": {"campo": "origem", "igual": "externo"}}

# O passo de cada campo dos itens que já existiam e agora têm stepper.
PASSO_DOS_CAMPOS = {
    "prestacao-contas": {"despesas": 1, "adiantamento": 2},
}


def aplicar(apps, schema_editor):
    ItemCatalogo = apps.get_model("workspace", "ItemCatalogo")

    # 1. Reembolso vira Prestação de contas. A chave muda porque ela é a URL, e
    #    `/servicos/reembolso/` contradiria o nome da tela — mas os pedidos já
    #    feitos seguem intactos: eles apontam para o item por id, não por chave.
    reembolso = ItemCatalogo.objects.filter(chave="reembolso").first()
    if reembolso is not None and not ItemCatalogo.objects.filter(
        chave="prestacao-contas"
    ).exists():
        reembolso.chave = "prestacao-contas"
        reembolso.nome = "Prestação de contas"
        reembolso.descricao_curta = "Gastos com comprovante — seus, ou de um adiantamento"
        # `reembolso` continua nos termos: é como as pessoas chamam, e a busca
        # tem de continuar achando por lá.
        termos = list(reembolso.termos or [])
        for novo in ("reembolso", "prestar contas", "prestacao de contas"):
            if novo not in termos:
                termos.append(novo)
        reembolso.termos = termos
        reembolso.save(
            update_fields=["chave", "nome", "descricao_curta", "termos"]
        )

    # 2. Campos substituídos por inteiro nos itens que mudaram de forma.
    for chave, campos in CAMPOS.items():
        item = ItemCatalogo.objects.filter(chave=chave).first()
        if item is None:
            continue
        item.campos = [dict(c) for c in campos]
        item.save(update_fields=["campos"])

    # 3. Passos, condição do valor, e o passo dos campos que já existiam.
    for chave, passos in PASSOS.items():
        item = ItemCatalogo.objects.filter(chave=chave).first()
        if item is None:
            continue
        item.passos = [dict(p) for p in passos]
        if chave in VALOR_QUANDO:
            item.valor_quando = dict(VALOR_QUANDO[chave])
        por_campo = PASSO_DOS_CAMPOS.get(chave)
        if por_campo:
            item.campos = [
                {**c, "passo": por_campo.get(c.get("chave"), c.get("passo", 1))}
                for c in (item.campos or [])
            ]
        item.save(update_fields=["passos", "valor_quando", "campos"])


def desfazer(apps, schema_editor):
    """A volta devolve o nome e a chave, e esvazia os passos.

    Os campos NÃO voltam ao texto livre: descer de versão com o formulário
    antigo é recuperável; perder a distinção entre `iconnect` e `IConnect` nos
    pedidos feitos no meio do caminho, não.
    """
    ItemCatalogo = apps.get_model("workspace", "ItemCatalogo")

    prestacao = ItemCatalogo.objects.filter(chave="prestacao-contas").first()
    if prestacao is not None:
        prestacao.chave = "reembolso"
        prestacao.nome = "Reembolso"
        prestacao.descricao_curta = "Despesa que você pagou e a empresa devolve"
        prestacao.save(update_fields=["chave", "nome", "descricao_curta"])

    ItemCatalogo.objects.filter(chave__in=list(PASSOS) + ["reembolso"]).update(
        passos=[], valor_quando=None
    )


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0016_itemcatalogo_passos_itemcatalogo_valor_quando"),
    ]

    operations = [
        migrations.RunPython(aplicar, desfazer),
    ]
