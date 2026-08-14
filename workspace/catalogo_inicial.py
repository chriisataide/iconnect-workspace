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
            {"chave": "ate_quando", "rotulo": "Até quando", "tipo": TipoCampo.DATA,
             "obrigatorio": True,
             "quando": {"campo": "periodo", "igual": "temporario"},
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
        "chave": "ferias",
        "termos": ["descanso", "folga longa", "periodo de ferias", "tirar ferias"],
        "nome": "Férias",
        "descricao_curta": "Programar suas férias",
        "grupo": GrupoCatalogo.TRABALHO,
        "icone": "users",
        "dominio": "rh.ferias",
        "prazo_prometido_dias": 2,
        "campos": [
            {"chave": "inicio", "rotulo": "Início", "tipo": TipoCampo.DATA,
             "obrigatorio": True},
            {"chave": "dias", "rotulo": "Dias", "tipo": TipoCampo.NUMERO,
             "obrigatorio": True},
        ],
    },
    {
        "chave": "atestado",
        "termos": [
            "atestado medico", "afastamento", "consulta medica", "declaracao de comparecimento", "fiquei doente",
        ],
        "nome": "Enviar atestado",
        "descricao_curta": "Atestado médico ou declaração de comparecimento",
        "grupo": GrupoCatalogo.TRABALHO,
        "icone": "file",
        "dominio": "rh.ausencia",
        "prazo_prometido_dias": 1,
        "campos": [
            {"chave": "data", "rotulo": "Data da ausência", "tipo": TipoCampo.DATA,
             "obrigatorio": True},
            {"chave": "horario", "rotulo": "Horário", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True,
             "ajuda": "Das 14h às 16h, ou o dia todo."},
            {"chave": "arquivo", "rotulo": "Atestado", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": True},
            # Opcionais para não estourar o teto de 3 obrigatórios: o atestado
            # já traz o motivo, e o gestor da lotação já é conhecido. Estes dois
            # existem para o caso em que a realidade diverge do cadastro.
            {"chave": "motivo", "rotulo": "Motivo", "tipo": TipoCampo.TEXTO_LONGO,
             "obrigatorio": False,
             "ajuda": "Consulta, exame, acompanhamento de familiar."},
            {"chave": "chefe_ciente", "rotulo": "Qual chefe estava ciente",
             "tipo": TipoCampo.TEXTO, "obrigatorio": False,
             "ajuda": "Quem você avisou. Em branco, entende-se o gestor da sua lotação."},
        ],
        "limite_auto_aprovacao": Decimal("0"),
    },
    {
        "chave": "home-office",
        "termos": ["trabalho remoto", "trabalhar de casa", "teletrabalho"],
        "nome": "Trabalho remoto",
        "descricao_curta": "Solicitar dias de home office",
        "grupo": GrupoCatalogo.TRABALHO,
        "icone": "users",
        "dominio": "rh.ausencia",
        "prazo_prometido_dias": 2,
        "campos": [
            {"chave": "periodo", "rotulo": "Período", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True, "ajuda": "De 10/09 a 14/09, ou toda quarta-feira."},
            {"chave": "dias", "rotulo": "Dias", "tipo": TipoCampo.NUMERO,
             "obrigatorio": True, "ajuda": "Quantos dias de trabalho remoto."},
            {"chave": "motivo", "rotulo": "Motivo", "tipo": TipoCampo.TEXTO_LONGO,
             "obrigatorio": True},
        ],
    },
    {
        "chave": "declaracao",
        "termos": ["comprovante de vinculo", "declaracao de renda", "comprovante de trabalho", "carta"],
        "nome": "Declaração ou comprovante",
        "descricao_curta": "Vínculo, renda, tempo de serviço",
        "grupo": GrupoCatalogo.TRABALHO,
        "icone": "file",
        "dominio": "rh.documento",
        "prazo_prometido_dias": 1,
        "campos": [
            {"chave": "tipo", "rotulo": "Qual declaração", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            # Opcional porque aqui a pessoa PEDE um documento — o anexo serve
            # para o caso em que ela já tem um modelo, um formulário do banco
            # ou a versão anterior a renovar.
            {"chave": "anexo", "rotulo": "Anexo", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": False,
             "ajuda": "Modelo exigido por quem pediu a declaração, se houver."},
        ],
        # Documento próprio da pessoa: nada a aprovar.
        "limite_auto_aprovacao": Decimal("0"),
    },
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
        "dominio": "fin.reembolso",
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
        "termos": ["passagem", "hospedagem", "hotel", "diaria", "deslocamento longo"],
        "nome": "Viagem",
        "descricao_curta": "Passagem, hospedagem e diária",
        "grupo": GrupoCatalogo.VIAGEM,
        "icone": "truck",
        "dominio": "fin.viagem",
        "prazo_prometido_dias": 5,
        "exige_valor": False,
        "exige_centro_custo": True,
        "campos": [
            {"chave": "destino", "rotulo": "Destino", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "ida", "rotulo": "Ida", "tipo": TipoCampo.DATA, "obrigatorio": True},
            {"chave": "volta", "rotulo": "Volta", "tipo": TipoCampo.DATA, "obrigatorio": True},
        ],
    },
    {
        "chave": "veiculo",
        "termos": ["carro", "van", "utilitario", "frota", "reservar carro"],
        "nome": "Veículo da empresa",
        "descricao_curta": "Reservar carro ou utilitário",
        "grupo": GrupoCatalogo.VIAGEM,
        "icone": "truck",
        "dominio": "log.veiculo",
        "prazo_prometido_dias": 2,
        "campos": [
            {"chave": "periodo", "rotulo": "Período", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "destino", "rotulo": "Destino", "tipo": TipoCampo.TEXTO,
             "obrigatorio": False},
        ],
    },
    # ── Espaço e material ───────────────────────────────────────────
    {
        "chave": "material",
        "termos": ["insumo", "suprimento", "material de escritorio", "papelaria"],
        "nome": "Material de trabalho",
        "descricao_curta": "Cabo, conector, ferramenta, material de escritório",
        "grupo": GrupoCatalogo.ESPACO,
        "icone": "cube",
        "dominio": "log.requisicao",
        "prazo_prometido_dias": 3,
        "campos": [
            {"chave": "itens", "rotulo": "O que você precisa", "tipo": TipoCampo.TEXTO_LONGO,
             "obrigatorio": True, "ajuda": "Um item por linha, com a quantidade."},
        ],
        "limite_auto_aprovacao": Decimal("300"),
    },
    {
        "chave": "epi",
        "termos": ["equipamento de protecao", "capacete", "luva", "bota", "cinto", "talabarte", "protecao individual"],
        "nome": "EPI ou uniforme",
        "descricao_curta": "Equipamento de proteção, bota, camisa",
        "grupo": GrupoCatalogo.ESPACO,
        "icone": "cube",
        "dominio": "log.requisicao",
        "prazo_prometido_dias": 5,
        "campos": [
            {"chave": "itens", "rotulo": "O que e qual tamanho", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
        ],
        # EPI nunca é barrado por orçamento: negar EPI é risco, não economia.
        "limite_auto_aprovacao": Decimal("0"),
    },
    {
        "chave": "manutencao-predial",
        "termos": ["ar condicionado", "lampada", "infiltracao", "predio", "instalacao predial", "reparo no escritorio"],
        "nome": "Manutenção predial",
        "descricao_curta": "Ar-condicionado, elétrica, hidráulica, limpeza",
        "grupo": GrupoCatalogo.ESPACO,
        "icone": "activity",
        "dominio": "ops.facilities",
        "prazo_prometido_dias": 4,
        "campos": [
            {"chave": "o_que", "rotulo": "O que precisa", "tipo": TipoCampo.TEXTO_LONGO,
             "obrigatorio": True},
            {"chave": "local", "rotulo": "Onde", "tipo": TipoCampo.TEXTO,
             "obrigatorio": False},
        ],
        "limite_auto_aprovacao": Decimal("0"),
    },
    # ── Desenvolvimento ─────────────────────────────────────────────
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
]
