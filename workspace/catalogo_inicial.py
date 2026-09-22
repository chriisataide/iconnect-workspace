"""Os itens iniciais do catálogo.

Agrupados por **intenção**, não por departamento — o usuário procura "meu
notebook quebrou", não "TI → Hardware → Manutenção".

Cada item declara no máximo **3 campos obrigatórios**. O resto (unidade, centro
de custo, gestor aprovador, matrícula) vem da identidade. Formulário com 8
campos livres é o que faz o usuário desistir e mandar e-mail.

Os `limite_auto_aprovacao` aqui são **conservadores de propósito**: a pergunta
"qual o teto por nível?" ainda não foi respondida. Item sem limite (`None`)
sempre passa pela cadeia — o padrão seguro.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from workspace.models.catalogo import GrupoCatalogo, TipoCampo

CATALOGO_INICIAL = [
    # ── Equipamento e acesso ────────────────────────────────────────
    {
        "chave": "notebook",
        "termos": ["laptop", "computador", "maquina", "pc", "equipamento novo"],
        "nome": "Notebook",
        "descricao_curta": "Novo equipamento ou substituição do atual",
        "grupo": GrupoCatalogo.EQUIPAMENTO,
        "icone": "cube",
        "dominio": "com.requisicao",
        "prazo_prometido_dias": 12,
        "exige_valor": False,
        "exige_centro_custo": True,
        "campos": [
            {
                "chave": "motivo",
                "rotulo": "Por que você precisa",
                "tipo": TipoCampo.TEXTO_LONGO,
                "obrigatorio": True,
                "ajuda": "Substituição, novo colaborador, projeto específico.",
            },
        ],
    },
    {
        "chave": "equipamento-quebrado",
        "termos": ["quebrou", "parou de funcionar", "nao liga", "defeito", "conserto", "manutencao de equipamento"],
        "nome": "Meu equipamento parou de funcionar",
        "descricao_curta": "Notebook, celular, monitor ou periférico com defeito",
        "grupo": GrupoCatalogo.EQUIPAMENTO,
        "icone": "cube",
        "dominio": "ti.chamado",
        "prazo_prometido_dias": 2,
        "campos": [
            {
                "chave": "o_que_acontece",
                "rotulo": "O que está acontecendo",
                "tipo": TipoCampo.TEXTO_LONGO,
                "obrigatorio": True,
            },
        ],
        # Chamado de TI não consome orçamento: entra direto na fila.
        "limite_auto_aprovacao": Decimal("0"),
    },
    {
        "chave": "acesso-vpn",
        "termos": ["vpn", "acesso remoto", "trabalhar de casa acesso", "conexao remota"],
        "nome": "Acesso à VPN",
        "descricao_curta": "Conexão remota à rede da empresa",
        "grupo": GrupoCatalogo.EQUIPAMENTO,
        "icone": "globe",
        "dominio": "ti.acesso",
        "prazo_prometido_dias": 1,
        "campos": [
            {"chave": "motivo", "rotulo": "Motivo", "tipo": TipoCampo.TEXTO_LONGO,
             "obrigatorio": True,
             "ajuda": "Para que você vai usar a VPN."},
            # Temporário e definitivo são acessos diferentes para quem concede:
            # um tem data para sair, o outro entra na revisão periódica. Sem a
            # pergunta, todo acesso vira definitivo por omissão — e é assim que
            # se acumula gente com VPN de um projeto que acabou.
            {"chave": "periodo", "rotulo": "Período", "tipo": TipoCampo.ESCOLHA,
             "obrigatorio": True,
             "opcoes": [
                 {"valor": "temporario", "rotulo": "Temporário"},
                 {"valor": "definitivo", "rotulo": "Definitivo"},
             ]},
            # `quando_modo: cinza` — fica na tela, apagado, em vez de sumir.
            # Aqui o campo é a consequência da escolha ao lado, e vê-lo
            # desabilitado ensina o que "definitivo" significa: não tem data
            # para sair. Sumir ensinaria menos e ainda faria a tela pular.
            {"chave": "ate_quando", "rotulo": "Até quando", "tipo": TipoCampo.DATA,
             "obrigatorio": True,
             "quando": {"campo": "periodo", "igual": "temporario"},
             "quando_modo": "cinza",
             "ajuda": "O acesso é removido nesta data."},
        ],
    },
    {
        "chave": "acesso-sistema",
        "termos": ["senha", "login", "permissao de sistema", "acesso a sistema", "usuario bloqueado"],
        "nome": "Acesso a um sistema",
        "descricao_curta": "iConnect, portal de operadora, SharePoint",
        "grupo": GrupoCatalogo.EQUIPAMENTO,
        "icone": "cube",
        "dominio": "ti.acesso",
        "prazo_prometido_dias": 2,
        "campos": [
            # Lista fechada, e não texto livre. À mão, o mesmo sistema chegava
            # como `iconnect`, `IConnect`, `portal` e `aquele sistema da
            # operadora` — impossível de rotear e impossível de medir. A lista
            # mora no admin: sistema novo entra sem deploy.
            {"chave": "sistema", "rotulo": "Qual sistema", "tipo": TipoCampo.ESCOLHA,
             "obrigatorio": True,
             "opcoes": [
                 {"valor": "iconnect", "rotulo": "iConnect Platform"},
                 {"valor": "m365", "rotulo": "Microsoft 365 / SharePoint"},
                 {"valor": "portal-operadora", "rotulo": "Portal de operadora"},
                 {"valor": "erp", "rotulo": "ERP / Financeiro"},
                 {"valor": "outro", "rotulo": "Outro — diga no motivo"},
             ]},
            {"chave": "motivo", "rotulo": "Motivo", "tipo": TipoCampo.TEXTO_LONGO,
             "obrigatorio": True,
             "ajuda": "Por que você precisa deste acesso, e para qual trabalho."},
            {"chave": "nivel", "rotulo": "Nível de acesso", "tipo": TipoCampo.ESCOLHA,
             "obrigatorio": False,
             "opcoes": [
                 {"valor": "leitura", "rotulo": "Leitura"},
                 {"valor": "operacao", "rotulo": "Operação"},
                 {"valor": "administracao", "rotulo": "Administração"},
             ]},
        ],
    },
    # ── Trabalho e ausência ─────────────────────────────────────────
    {
        "chave": "vaga-interna",
        "termos": [
            "vaga", "vaga interna", "recrutamento interno", "me candidatar",
            "mudar de area", "processo seletivo", "inscricao em vaga",
        ],
        "nome": "Inscrição em vaga interna",
        "descricao_curta": "Candidatar-se a uma vaga aberta na empresa",
        "grupo": GrupoCatalogo.TRABALHO,
        "icone": "users",
        "dominio": "rh.vaga",
        "prazo_prometido_dias": 5,
        "campos": [
            # Texto livre e não lista: a lista de vagas abertas muda toda
            # semana, e um `select` semeado em código estaria errado no mês que
            # vem. Quando o módulo de vagas existir, isto vira escolha.
            {"chave": "vaga", "rotulo": "Qual vaga", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True,
             "ajuda": "Como ela foi divulgada — título e unidade."},
            {"chave": "motivo", "rotulo": "Por que você quer esta vaga",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": True},
            {"chave": "curriculo", "rotulo": "Currículo", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": False,
             "ajuda": "Opcional: o R.H. já tem o seu cadastro."},
        ],
        # Candidatura não passa pelo gestor: a cadeia de aprovação normal faria
        # o pedido de mudar de área ser avaliado por quem perde a pessoa.
        "limite_auto_aprovacao": Decimal("0"),
    },
    {
        "chave": "abertura-vaga",
        "termos": [
            "abrir vaga", "contratar", "nova vaga", "reposicao", "aumento de quadro",
            "headcount", "requisicao de pessoal",
        ],
        "nome": "Abertura de vaga",
        "descricao_curta": "Pedir a contratação de alguém para a sua equipe",
        "grupo": GrupoCatalogo.TRABALHO,
        "icone": "users",
        "dominio": "rh.vaga",
        "prazo_prometido_dias": 10,
        "passos": [
            {"titulo": "A vaga"},
            {"titulo": "Por quê"},
        ],
        "campos": [
            {"chave": "cargo", "rotulo": "Cargo", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True, "passo": 1},
            # Opcional porque o teto de 3 obrigatórios vale, e porque a
            # resposta é 1 em quase todo pedido: campo que quase sempre tem a
            # mesma resposta é candidato natural a ter padrão em vez de
            # asterisco.
            {"chave": "quantidade", "rotulo": "Quantas pessoas",
             "tipo": TipoCampo.NUMERO, "obrigatorio": False, "passo": 1,
             "ajuda": "Em branco, entende-se uma."},
            {"chave": "tipo", "rotulo": "Motivo da abertura",
             "tipo": TipoCampo.ESCOLHA, "obrigatorio": True, "passo": 2,
             "opcoes": [
                 {"valor": "reposicao", "rotulo": "Reposição — alguém saiu"},
                 {"valor": "aumento", "rotulo": "Aumento de quadro"},
                 {"valor": "temporario", "rotulo": "Temporário / safra"},
             ]},
            # Só na reposição, porque só nela existe: perguntar "quem saiu" a
            # quem está aumentando o quadro é o campo que a pessoa preenche com
            # um traço.
            {"chave": "substituido", "rotulo": "Quem saiu", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True, "passo": 2,
             "quando": {"campo": "tipo", "igual": "reposicao"}},
            {"chave": "justificativa", "rotulo": "Justificativa",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": True, "passo": 2,
             "ajuda": "O que deixa de ser feito enquanto a vaga não é preenchida."},
        ],
        # Contratação é decisão de custo recorrente: sempre passa pela cadeia.
        "exige_centro_custo": True,
    },
    {
        "chave": "pendencias-ponto",
        "termos": [
            "ponto", "pendencia de ponto", "folha de ponto", "espelho de ponto",
            "batida", "esqueci de bater", "marcacao", "nao registrei",
            "abono de hora", "ajuste de ponto", "correcao de ponto",
        ],
        "nome": "Pendências de Ponto",
        "descricao_curta": "Justificar uma marcação que faltou no seu espelho",
        "grupo": GrupoCatalogo.TRABALHO,
        "icone": "relogio",
        # `rh.ponto` e não `rh.` puro: o domínio é hierárquico e a regra de
        # revisão de área casa por PREFIXO, então o item nasce coberto pela
        # cadeia que já existe. Sub-domínio próprio é o que deixa a fila do
        # ponto ser separada da de férias no dia em que isso importar.
        "dominio": "rh.ponto",
        "prazo_prometido_dias": 5,
        "campos": [
            {"chave": "dia", "rotulo": "Dia da pendência", "tipo": TipoCampo.DATA,
             "obrigatorio": True},
            # Opcional porque a pendência tanto pode ser UMA batida perdida
            # quanto o dia inteiro sem registro. Exigir a hora obrigaria quem
            # faltou o dia todo a inventar um horário para o campo aceitar.
            {"chave": "horario", "rotulo": "Horário que faltou",
             "tipo": TipoCampo.HORA, "obrigatorio": False,
             "ajuda": "Em branco, se o dia inteiro ficou sem registro."},
            {"chave": "motivo", "rotulo": "O que aconteceu",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": True},
            {"chave": "comprovante", "rotulo": "Comprovante",
             "tipo": TipoCampo.ARQUIVO, "obrigatorio": False,
             "ajuda": "Opcional — declaração, e-mail, o que sustente a correção."},
        ],
        # Sem `limite_auto_aprovacao`: correção de ponto passa pelo gestor de
        # propósito. É ele quem sabe se a pessoa estava lá — aprovar sozinho
        # transformaria o espelho em campo de digitação livre.
    },
    # ── Dinheiro ────────────────────────────────────────────────────
    {
        "chave": "prestacao-contas",
        "termos": [
            "reembolso", "gastei", "despesa", "nota fiscal", "cupom", "taxi", "uber",
            "combustivel", "pedagio", "restituicao", "prestar contas", "prestacao de contas",
        ],
        # "Reembolso" nomeava metade do que a tela faz. Ela também fecha a conta
        # de um adiantamento — e nesse caso pode ser a PESSOA que devolve, não a
        # empresa que paga. Chamar isso de reembolso fazia quem tinha dinheiro
        # sobrando procurar outro lugar para devolver, e não achar nenhum.
        # `reembolso` continua na lista de termos: é como as pessoas chamam.
        "nome": "Prestação de contas",
        "descricao_curta": "Gastos com comprovante — seus, ou de um adiantamento",
        "grupo": GrupoCatalogo.DINHEIRO,
        "icone": "wallet",
        "dominio": "rh.reembolso",
        "prazo_prometido_dias": 5,
        # `exige_valor` continua True porque o reembolso TEM valor — ele só não
        # é digitado. Quem soma é `services/reembolso.total()`, a partir das
        # linhas, e é essa soma que vai para o limite e para o orçamento.
        "exige_valor": True,
        "exige_centro_custo": True,
        # Os três momentos do que era uma tela só. O terceiro acontece DEPOIS do
        # envio, em outra tela, e aparece na trilha mesmo assim: sem ele, quem
        # atrelou um adiantamento acha que terminou e deixa a conta aberta.
        "passos": [
            {"titulo": "As compras"},
            {"titulo": "Adiantamento"},
            {"titulo": "Acerto", "apos_envio": True},
        ],
        # `rh.` e não `fin.`: quem faz a TRATATIVA do reembolso — confere
        # comprovante, valida a despesa e libera para pagamento — é o R.H.
        #
        # A cadeia fica gestor direto → R.H., pelas regras que já existem:
        # `*` ordem 10 é o gestor, `rh.` ordem 15 é a área. Nenhuma regra nova.
        #
        # O ADIANTAMENTO continua em `fin.`: dinheiro que sai ANTES da despesa é
        # do Financeiro. A prestação de contas de um adiantamento cruza os dois
        # domínios de propósito — o R.H. confere os recibos, o Financeiro
        # adiantou o valor.
        "campos": [
            {"chave": "despesas", "rotulo": "Compras", "tipo": TipoCampo.DESPESAS,
             "obrigatorio": True, "passo": 1,
             "ajuda": "Um comprovante por compra, com o valor e o motivo dela."},
            {"chave": "adiantamento", "rotulo": "Adiantamento a prestar contas",
             "tipo": TipoCampo.ADIANTAMENTO, "obrigatorio": False, "passo": 2,
             "ajuda": "Se este gasto saiu de um adiantamento, atrele aqui."},
        ],
        "limite_auto_aprovacao": Decimal("200"),
    },
    {
        # §10 — Pagamento de PJ.
        #
        # Domínio `rh.`: é o R.H. que trata o pagamento do PJ, como trata o
        # reembolso. Aparece só no painel do R.H.
        #
        # Privacidade não precisou de nada especial e é bom dizer por quê: o
        # produto já mostra a cada pessoa SÓ os pedidos dela (`svc.minhas()`), e
        # anexo só é servido depois de autorizar (`baixar_anexo`). Um "módulo de
        # PJ" com listagem própria é justamente o que criaria o vazamento que o
        # pedido teme.
        "chave": "pagamento-pj",
        "termos": ["pj", "nota fiscal", "nf", "pessoa juridica", "prestador",
                   "faturar", "competencia", "meu pagamento", "rpa"],
        "nome": "Pagamento de PJ",
        "descricao_curta": "Enviar a nota fiscal do mês",
        "grupo": GrupoCatalogo.DINHEIRO,
        "icone": "wallet",
        "dominio": "rh.pj",
        "prazo_prometido_dias": 5,
        "exige_valor": True,
        "exige_centro_custo": True,
        "campos": [
            {"chave": "competencia", "rotulo": "Competência", "tipo": TipoCampo.ESCOLHA,
             "obrigatorio": True,
             "ajuda": "O mês de referência do serviço, não o mês em que a nota foi emitida.",
             "opcoes": [
                 {"valor": "01", "rotulo": "Janeiro"}, {"valor": "02", "rotulo": "Fevereiro"},
                 {"valor": "03", "rotulo": "Março"}, {"valor": "04", "rotulo": "Abril"},
                 {"valor": "05", "rotulo": "Maio"}, {"valor": "06", "rotulo": "Junho"},
                 {"valor": "07", "rotulo": "Julho"}, {"valor": "08", "rotulo": "Agosto"},
                 {"valor": "09", "rotulo": "Setembro"}, {"valor": "10", "rotulo": "Outubro"},
                 {"valor": "11", "rotulo": "Novembro"}, {"valor": "12", "rotulo": "Dezembro"},
             ]},
            {"chave": "nota_fiscal", "rotulo": "Nota fiscal", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": True,
             "ajuda": "PDF da NF. É o documento que o Financeiro precisa para pagar."},
            {"chave": "numero_nota", "rotulo": "Número da nota", "tipo": TipoCampo.TEXTO,
             "obrigatorio": False},
            {"chave": "observacao", "rotulo": "Observações", "tipo": TipoCampo.TEXTO_LONGO,
             "obrigatorio": False,
             "ajuda": "Retenções, desconto combinado, o que o Financeiro precisa saber."},
        ],
    },
    {
        "chave": "adiantamento",
        "termos": ["dinheiro antes", "vale", "antecipacao", "adiantar despesa"],
        "nome": "Adiantamento",
        "descricao_curta": "Dinheiro antes da despesa, com prestação de contas",
        "grupo": GrupoCatalogo.DINHEIRO,
        "icone": "wallet",
        "dominio": "fin.adiantamento",
        "prazo_prometido_dias": 3,
        "exige_valor": True,
        "exige_centro_custo": True,
        "campos": [
            {"chave": "motivo", "rotulo": "Motivo", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "data_pagamento", "rotulo": "Data de pagamento",
             "tipo": TipoCampo.DATA, "obrigatorio": True,
             "ajuda": "Quando você precisa do dinheiro na conta."},
            {"chave": "dados_bancarios", "rotulo": "Conta do beneficiário",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": True,
             "ajuda": "Banco, agência, conta e chave PIX, se houver."},
            # Opcionais para respeitar o teto de 3 obrigatórios. O supervisor
            # ciente é informação, não autorização: quem aprova continua sendo
            # a cadeia de `RegraAprovacao`, e não o nome digitado aqui.
            {"chave": "supervisor_ciente", "rotulo": "Supervisor ciente",
             "tipo": TipoCampo.TEXTO, "obrigatorio": False,
             "ajuda": "Quem você combinou o adiantamento."},
            {"chave": "orcamento", "rotulo": "Orçamento", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": False,
             "ajuda": "Anexe se já houver orçamento ou proposta."},
        ],
    },
    {
        "chave": "compra",
        "termos": ["comprar", "aquisicao", "requisicao de compra", "orcamento de compra", "fornecedor"],
        "nome": "Comprar algo",
        "descricao_curta": "Material, serviço ou equipamento",
        "grupo": GrupoCatalogo.DINHEIRO,
        "icone": "cart",
        "dominio": "com.requisicao",
        "prazo_prometido_dias": 12,
        "exige_valor": True,
        "exige_centro_custo": True,
        "campos": [
            {"chave": "o_que", "rotulo": "O que você precisa", "tipo": TipoCampo.TEXTO_LONGO,
             "obrigatorio": True},
            {"chave": "quando", "rotulo": "Precisa até", "tipo": TipoCampo.DATA,
             "obrigatorio": False},
        ],
    },
    # ── Viagem ──────────────────────────────────────────────────────
    {
        "chave": "viagem",
        "termos": ["passagem", "hospedagem", "hotel", "diaria", "deslocamento longo",
                   # "aluguel de carro" saiu: "carro" é termo de `veiculo` — reservar o
                   # carro DA EMPRESA —, e as duas intenções competindo faziam o
                   # motor não escolher nenhuma. Locação em viagem continua
                   # alcançável por "locacao de veiculo".
                   "aviao", "voo", "aereo", "locacao de veiculo"],
        "nome": "Viagem",
        "descricao_curta": "Passagem, hospedagem e locação",
        "grupo": GrupoCatalogo.VIAGEM,
        "icone": "truck",
        # §13 — DE `fin.viagem` PARA `log.viagem`.
        #
        # Não é troca de rótulo: `dominio` decide as duas coisas ao mesmo tempo
        # — em que módulo o item aparece E de quem é a fila que executa. Mover
        # para `log.` faz Suprimentos passar a RESERVAR a viagem, que é quem
        # sempre fez isso na prática; o Financeiro entrava na cadeia só porque
        # o item nasceu com prefixo `fin.`.
        #
        # O dinheiro não deixa de ser olhado: as regras por FAIXA DE VALOR
        # (diretoria acima de 50k, sócios acima de 300k) valem para todo domínio.
        "dominio": "log.viagem",
        "prazo_prometido_dias": 5,
        "exige_valor": False,
        "exige_centro_custo": True,
        "campos": [
            # Três obrigatórios sem condição — o teto do produto. A escolha de
            # quais três é de PRODUTO: sem destino, sem data de ida e sem saber
            # O QUE se pede, Suprimentos não consegue cotar nada.
            #
            # `volta` ficou de fora do trio de propósito: viagem só de ida
            # existe (mudança de base, ida de véspera com volta a definir), e
            # exigi-la obrigaria a pessoa a inventar uma data.
            {"chave": "o_que", "rotulo": "O que você precisa", "tipo": TipoCampo.ESCOLHA,
             "obrigatorio": True,
             "opcoes": [
                 {"valor": "aviao", "rotulo": "Passagem aérea"},
                 {"valor": "hospedagem", "rotulo": "Hospedagem"},
                 {"valor": "carro", "rotulo": "Locação de veículo"},
                 {"valor": "varios", "rotulo": "Mais de um item"},
             ]},
            {"chave": "destino", "rotulo": "Destino", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True, "ajuda": "Cidade e estado."},
            {"chave": "ida", "rotulo": "Ida", "tipo": TipoCampo.DATA, "obrigatorio": True},
            {"chave": "volta", "rotulo": "Volta", "tipo": TipoCampo.DATA,
             "obrigatorio": False, "ajuda": "Em branco, entende-se só ida."},
            {"chave": "origem", "rotulo": "Saindo de", "tipo": TipoCampo.TEXTO,
             "obrigatorio": False,
             "ajuda": "Em branco, entende-se a cidade da sua unidade."},
            # Os campos de RAMO. Aparecem só para quem escolheu aquele item, e é
            # o que permite perguntar o específico sem pôr tudo à mostra: quem
            # precisa de hotel não deveria ver pergunta sobre bagagem despachada.
            {"chave": "voo_preferencia", "rotulo": "Preferência de horário",
             "tipo": TipoCampo.TEXTO, "obrigatorio": False,
             "quando": {"campo": "o_que", "igual": "aviao"},
             "ajuda": "Manhã, tarde ou noite. Em branco, vale o mais barato."},
            {"chave": "hospedagem_noites", "rotulo": "Quantas noites",
             "tipo": TipoCampo.NUMERO, "obrigatorio": False,
             "quando": {"campo": "o_que", "igual": "hospedagem"}},
            {"chave": "carro_categoria", "rotulo": "Categoria do veículo",
             "tipo": TipoCampo.ESCOLHA, "obrigatorio": False,
             "quando": {"campo": "o_que", "igual": "carro"},
             "opcoes": [
                 {"valor": "economico", "rotulo": "Econômico"},
                 {"valor": "intermediario", "rotulo": "Intermediário"},
                 {"valor": "utilitario", "rotulo": "Utilitário ou van"},
             ]},
            {"chave": "motivo", "rotulo": "Motivo da viagem",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": False,
             "ajuda": "Cliente, obra ou evento. Ajuda Suprimentos a priorizar."},
            {"chave": "observacoes", "rotulo": "Observações",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": False},
            {"chave": "anexo", "rotulo": "Anexo", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": False,
             "ajuda": "Convite do evento, cotação já feita, o que ajudar."},
        ],
    },
    # "Veículo da empresa" SAIU daqui — ver `0044_veiculo_so_na_grade_de_reservas`.
    #
    # Ele duplicava a grade de Reservas, que já garante que duas pessoas não
    # peguem a van no mesmo horário. Este item guardava o período como TEXTO
    # LIVRE ("de terça a quinta"), então o choque entre os dois caminhos não era
    # detectável em lugar nenhum — e duas equipes chegavam na porta esperando o
    # mesmo veículo.
    #
    # Fora da semente pelo mesmo motivo do home office: `semear_catalogo` pula o
    # que já existe, e um banco novo nasceria com o item ativo de novo.
    # ── Espaço e material ───────────────────────────────────────────
    {
        # §14 — UM item no lugar de três.
        #
        # "EPI", "Uniforme" e "Material de trabalho" eram três formulários com
        # os mesmos quatro campos, e a diferença entre eles era só a palavra do
        # título. Isso empurrava a classificação para quem PEDE: a pessoa que
        # precisa de uma luva tem de decidir se luva é EPI ou material, e quando
        # ela erra o pedido cai na fila certa mesmo assim — o que prova que a
        # separação nunca serviu para nada operacional.
        #
        # Um item com o TIPO como campo mantém a informação (Suprimentos
        # continua sabendo que foi EPI) e tira a decisão de quem não deveria
        # tomá-la.
        "chave": "controle-materiais",
        "termos": [
            "epi", "uniforme", "material", "material de trabalho", "luva",
            "capacete", "bota", "camisa", "cracha", "equipamento de protecao",
            "papelaria", "almoxarifado", "estoque",
        ],
        "nome": "Controle de materiais",
        "descricao_curta": "EPI, uniforme, papelaria e material de trabalho",
        "grupo": GrupoCatalogo.ESPACO,
        "icone": "truck",
        "dominio": "log.requisicao",
        "prazo_prometido_dias": 3,
        # Auto-aprovado, herdando a regra do EPI que ele substitui: negar
        # capacete é risco, não economia. Quem pede material de trabalho não
        # deveria esperar decisão de ninguém para receber uma luva.
        "limite_auto_aprovacao": Decimal("0"),
        "campos": [
            {"chave": "tipo", "rotulo": "Tipo de material", "tipo": TipoCampo.ESCOLHA,
             "obrigatorio": True,
             "opcoes": [
                 {"valor": "epi", "rotulo": "EPI — equipamento de proteção"},
                 {"valor": "uniforme", "rotulo": "Uniforme"},
                 {"valor": "trabalho", "rotulo": "Material de trabalho"},
                 {"valor": "papelaria", "rotulo": "Papelaria e escritório"},
             ]},
            {"chave": "o_que", "rotulo": "O que você precisa", "tipo": TipoCampo.TEXTO_LONGO,
             "obrigatorio": True,
             "ajuda": "Item e tamanho, quando fizer diferença. Ex.: luva nitrílica G, 2 pares."},
            {"chave": "onde_usa", "rotulo": "Onde vai usar", "tipo": TipoCampo.TEXTO,
             "obrigatorio": False,
             "ajuda": "Unidade, obra ou setor. Em branco, entende-se a sua lotação."},
        ],
    },
    {
        # §16 — requisição do que JÁ EXISTE no estoque.
        #
        # Diferente de `controle-materiais`, e a diferença é real: lá a pessoa
        # descreve o que precisa e Suprimentos compra ou providencia; aqui ela
        # escolhe de uma lista do que está na prateleira, e o pedido é recusado
        # na hora se não couber no saldo da unidade dela.
        #
        # As opções ficam vazias na semente de propósito: elas são preenchidas
        # a partir do cadastro de materiais, que muda toda semana. Lista escrita
        # aqui envelheceria no primeiro item novo.
        "chave": "requisicao-material",
        "termos": ["requisicao", "retirar material", "almoxarifado", "pegar do estoque",
                   "saldo", "estoque disponivel"],
        "nome": "Requisição de material",
        "descricao_curta": "Retirar do que já está em estoque",
        "grupo": GrupoCatalogo.ESPACO,
        "icone": "cube",
        "dominio": "log.requisicao",
        "prazo_prometido_dias": 2,
        # Auto-aprovada: o material já é da empresa e já está pago. Pôr uma
        # cadeia de aprovação na frente de uma retirada de almoxarifado é o que
        # faz a pessoa parar de pedir e simplesmente levar.
        "limite_auto_aprovacao": Decimal("0"),
        "campos": [
            {"chave": "material", "rotulo": "Material", "tipo": TipoCampo.ESCOLHA,
             "obrigatorio": True, "opcoes": [], "dinamico": True,
             "ajuda": "A lista mostra o que existe em estoque na sua unidade."},
            {"chave": "quantidade", "rotulo": "Quantidade", "tipo": TipoCampo.NUMERO,
             "obrigatorio": True},
            {"chave": "finalidade", "rotulo": "Para que vai usar",
             "tipo": TipoCampo.TEXTO, "obrigatorio": True,
             "ajuda": "Obra, cliente ou atividade."},
            {"chave": "onde_usa", "rotulo": "Local de utilização",
             "tipo": TipoCampo.TEXTO, "obrigatorio": False,
             "ajuda": "Em branco, entende-se a sua unidade."},
        ],
    },
    {
        # §11 — o chamado predial abre no iConnect Platform.
        #
        # O Workspace NÃO recria o sistema de chamados: ordem de serviço,
        # despacho de técnico e SLA de campo já existem lá, com histórico e
        # com o cliente. Um segundo sistema de chamados criaria duas filas para
        # o mesmo trabalho — e a segunda seria a que ninguém olha.
        #
        # `url_externa` em vez de formulário: o card marca que sai daqui, e a
        # pessoa descobre ANTES de digitar.
        "chave": "chamado-predial-iconnect",
        # "iconnect" NÃO entra: é termo de `acesso-sistema` — quem escreve
        # "preciso de acesso ao iConnect" quer login, não abrir chamado. Roubar
        # o termo mandaria essa pessoa para o lugar errado.
        "termos": ["chamado predial", "ordem de servico", "abrir chamado",
                   "chamado", "atendimento predial", "despacho"],
        "nome": "Abrir chamado no iConnect",
        "descricao_curta": "Ordem de serviço, despacho e SLA de campo",
        "grupo": GrupoCatalogo.ESPACO,
        "icone": "ticket",
        "dominio": "ops.chamado",
        "prazo_prometido_dias": 1,
        # De `settings`, não escrito à mão: o endereço muda entre
        # desenvolvimento e produção, e um literal aqui mandaria todo mundo para
        # o iConnect de dev — que é onde os dados não são reais.
        "url_externa": settings.ICONNECT_URL,
        "campos": [],
    },
    {
        "chave": "treinamento",
        "termos": ["curso", "capacitacao", "estudar", "formacao"],
        "nome": "Treinamento ou curso",
        "descricao_curta": "Curso externo, certificação, congresso",
        "grupo": GrupoCatalogo.DESENVOLVIMENTO,
        "icone": "book",
        "dominio": "hab.treinamento",
        "prazo_prometido_dias": 7,
        "exige_valor": True,
        "exige_centro_custo": True,
        # Curso interno da empresa não tem preço a informar. Sem esta condição,
        # o ramo interno travaria num "Valor *" impossível de responder certo.
        "valor_quando": {"campo": "origem", "igual": "externo"},
        "passos": [
            {"titulo": "Interno ou externo"},
            {"titulo": "O curso"},
            {"titulo": "Aplicação"},
        ],
        "campos": [
            # A pergunta que separa os dois cenários, e por isso é o passo 1
            # sozinho: as perguntas seguintes dependem inteiramente dela.
            {"chave": "origem", "rotulo": "Que tipo de curso",
             "tipo": TipoCampo.ESCOLHA, "obrigatorio": True, "passo": 1,
             "opcoes": [
                 {"valor": "interno", "rotulo": "Curso interno da empresa"},
                 {"valor": "externo", "rotulo": "Curso externo"},
             ]},
            # Interno: a pessoa escolhe o que já existe. Nada de instituição,
            # valor ou período — a empresa já sabe tudo isso.
            {"chave": "curso_interno", "rotulo": "Qual curso",
             "tipo": TipoCampo.ESCOLHA, "obrigatorio": True, "passo": 2,
             "quando": {"campo": "origem", "igual": "interno"},
             "opcoes": [
                 {"valor": "integracao", "rotulo": "Integração de novos colaboradores"},
                 {"valor": "seguranca", "rotulo": "Segurança do trabalho"},
                 {"valor": "iconnect", "rotulo": "iConnect Platform na prática"},
                 {"valor": "atendimento", "rotulo": "Atendimento ao cliente"},
                 {"valor": "lideranca", "rotulo": "Liderança e gestão de equipe"},
             ]},
            # Externo: tudo o que a empresa ainda não sabe, e precisa saber para
            # aprovar — quem dá, o quê, quando e por quanto.
            {"chave": "instituicao", "rotulo": "Empresa ou instituição do curso",
             "tipo": TipoCampo.TEXTO, "obrigatorio": True, "passo": 2,
             "quando": {"campo": "origem", "igual": "externo"}},
            {"chave": "curso", "rotulo": "Qual curso", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True, "passo": 2,
             "quando": {"campo": "origem", "igual": "externo"}},
            {"chave": "inicio", "rotulo": "Começa em", "tipo": TipoCampo.DATA,
             "obrigatorio": True, "passo": 2,
             "quando": {"campo": "origem", "igual": "externo"}},
            {"chave": "periodo", "rotulo": "Período e carga horária",
             "tipo": TipoCampo.TEXTO, "obrigatorio": True, "passo": 2,
             "quando": {"campo": "origem", "igual": "externo"},
             "ajuda": "Ex.: 4 sábados, 32 h no total."},
            {"chave": "aplicacao", "rotulo": "Como vai aplicar no trabalho",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": True, "passo": 3},
        ],
    },
    {
        "chave": "reciclagem-nr",
        "termos": ["nr", "nr-10", "nr-35", "reciclagem", "norma regulamentadora", "certificado vencendo"],
        "nome": "Reciclagem de NR",
        "descricao_curta": "NR-10, NR-35 e outras habilitações a vencer",
        "grupo": GrupoCatalogo.DESENVOLVIMENTO,
        "icone": "book",
        "dominio": "hab.reciclagem",
        "prazo_prometido_dias": 10,
        "passos": [
            {"titulo": "O que vence"},
            {"titulo": "De quem é"},
        ],
        "campos": [
            # Texto livre, e não lista: a variedade é grande (NR-10, NR-35,
            # NR-33, curso de operador, CNH especial) e cada pessoa tem a sua
            # combinação. Lista fechada aqui viraria "Outro" na maioria dos
            # pedidos, que é o pior dos dois mundos.
            {"chave": "habilitacao", "rotulo": "Qual documento vai vencer",
             "tipo": TipoCampo.TEXTO, "obrigatorio": True, "passo": 1,
             "ajuda": "NR-10, NR-35, curso de operador, CNH especial…"},
            # A data é o que permite ao setor priorizar: habilitação vencida
            # bloqueia despacho, e quem vence em 15 dias não pode esperar na
            # mesma fila de quem vence em 6 meses.
            {"chave": "vencimento", "rotulo": "Vence em", "tipo": TipoCampo.DATA,
             "obrigatorio": True, "passo": 1},
            {"chave": "para_quem", "rotulo": "Para quem é",
             "tipo": TipoCampo.ESCOLHA, "obrigatorio": True, "passo": 2,
             "opcoes": [
                 {"valor": "propria", "rotulo": "Para mim"},
                 {"valor": "terceiro", "rotulo": "Para um técnico terceiro"},
             ]},
            # O técnico terceiro NÃO tem acesso ao Workspace — ele não pede por
            # si, e não recebe as notificações. Por isso os dados dele são
            # digitados por quem pede, e o responsável é obrigatório: é com essa
            # pessoa que o setor vai tratar, e sem ela o pedido chega sem
            # ninguém do outro lado.
            {"chave": "tecnico_nome", "rotulo": "Nome do técnico",
             "tipo": TipoCampo.TEXTO, "obrigatorio": True, "passo": 2,
             "quando": {"campo": "para_quem", "igual": "terceiro"}},
            {"chave": "tecnico_documento", "rotulo": "CPF do técnico",
             "tipo": TipoCampo.TEXTO, "obrigatorio": True, "passo": 2,
             "quando": {"campo": "para_quem", "igual": "terceiro"}},
            {"chave": "tecnico_empresa", "rotulo": "Empresa do técnico",
             "tipo": TipoCampo.TEXTO, "obrigatorio": True, "passo": 2,
             "quando": {"campo": "para_quem", "igual": "terceiro"}},
            {"chave": "tecnico_responsavel",
             "rotulo": "Responsável por ele, e como falar com ele",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": True, "passo": 2,
             "quando": {"campo": "para_quem", "igual": "terceiro"},
             "ajuda": "Nome, telefone e e-mail. O técnico terceiro não acessa o "
                      "Workspace — tudo é tratado direto com o responsável."},
        ],
        # Reciclagem obrigatória não passa por aprovação: habilitação vencida
        # bloqueia despacho, e negar a reciclagem trava a operação.
        "limite_auto_aprovacao": Decimal("0"),
    },
    # ── Jurídico ────────────────────────────────────────────────────
    {
        "chave": "analise-contrato",
        "termos": ["juridico", "contrato", "revisao de contrato", "clausula"],
        "nome": "Análise de contrato",
        "descricao_curta": "Revisão jurídica antes de assinar",
        "grupo": GrupoCatalogo.JURIDICO,
        "icone": "file",
        "dominio": "jur.analise",
        "prazo_prometido_dias": 7,
        "campos": [
            {"chave": "contrato", "rotulo": "Contrato", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": True},
            {"chave": "prazo", "rotulo": "Precisa até", "tipo": TipoCampo.DATA,
             "obrigatorio": False},
        ],
        "limite_auto_aprovacao": Decimal("0"),
    },
    # ── Vendas ──────────────────────────────────────────────────────
    #
    # Área nova. Os itens abaixo são o mínimo plausível para a área existir de
    # verdade — quem conhece o processo comercial ajusta no admin, sem deploy.
    {
        "chave": "desconto-especial",
        "termos": ["desconto", "condicao especial", "preco", "proposta", "negociacao"],
        "nome": "Desconto fora da tabela",
        "descricao_curta": "Condição comercial que precisa de aprovação",
        "grupo": GrupoCatalogo.DINHEIRO,
        "icone": "cart",
        "dominio": "ven.desconto",
        "prazo_prometido_dias": 2,
        # Desconto TEM valor — é o valor do negócio, e é ele que decide se a
        # diretoria entra na cadeia. Sem isso, um desconto de R$ 400 mil seria
        # aprovado pelo gestor direto como se fosse um pedido de material.
        "exige_valor": True,
        "campos": [
            {"chave": "cliente", "rotulo": "Cliente", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "condicao", "rotulo": "Qual condição você precisa",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": True,
             "ajuda": "Percentual, prazo de pagamento, escopo incluído."},
            {"chave": "proposta", "rotulo": "Proposta", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": False},
        ],
    },
    {
        "chave": "cadastro-cliente",
        "termos": ["cliente novo", "cadastrar cliente", "abertura de cliente", "cnpj"],
        "nome": "Cadastro de cliente",
        "descricao_curta": "Abrir um cliente novo no sistema",
        "grupo": GrupoCatalogo.ESPACO,
        "icone": "users",
        "dominio": "ven.cadastro",
        "prazo_prometido_dias": 2,
        "campos": [
            {"chave": "razao_social", "rotulo": "Razão social", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "documento", "rotulo": "CNPJ", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "contato", "rotulo": "Contato do cliente",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": False},
        ],
        "limite_auto_aprovacao": Decimal("0"),
    },
    # ── Marketing ───────────────────────────────────────────────────
    {
        "chave": "evento",
        "termos": ["feira", "evento", "patrocinio", "stand", "congresso"],
        "nome": "Evento ou patrocínio",
        "descricao_curta": "Feira, congresso, stand ou patrocínio",
        "grupo": GrupoCatalogo.DINHEIRO,
        "icone": "megafone",
        "dominio": "mkt.evento",
        "prazo_prometido_dias": 10,
        "exige_valor": True,
        "exige_centro_custo": True,
        "campos": [
            {"chave": "evento", "rotulo": "Qual evento", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "quando", "rotulo": "Quando", "tipo": TipoCampo.DATA,
             "obrigatorio": True},
            {"chave": "retorno", "rotulo": "O que a empresa ganha com isso",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": True},
        ],
    },
    # ── Jurídico (o módulo ganhou tile; o domínio já existia) ────────
]
