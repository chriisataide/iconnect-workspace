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
        "nome": "Acesso à VPN",
        "descricao_curta": "Conexão remota à rede da empresa",
        "grupo": GrupoCatalogo.EQUIPAMENTO,
        "icone": "globe",
        "dominio": "ti.acesso",
        "prazo_prometido_dias": 1,
        "campos": [
            {
                "chave": "justificativa",
                "rotulo": "Para que você vai usar",
                "tipo": TipoCampo.TEXTO,
                "obrigatorio": True,
            },
        ],
    },
    {
        "chave": "acesso-sistema",
        "nome": "Acesso a um sistema",
        "descricao_curta": "iConnect, portal de operadora, SharePoint",
        "grupo": GrupoCatalogo.EQUIPAMENTO,
        "icone": "cube",
        "dominio": "ti.acesso",
        "prazo_prometido_dias": 2,
        "campos": [
            {"chave": "sistema", "rotulo": "Qual sistema", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "nivel", "rotulo": "Nível de acesso", "tipo": TipoCampo.TEXTO,
             "obrigatorio": False, "ajuda": "Leitura, operação, administração."},
        ],
    },
    # ── Trabalho e ausência ─────────────────────────────────────────
    {
        "chave": "ferias",
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
        "nome": "Enviar atestado",
        "descricao_curta": "Atestado médico ou declaração de comparecimento",
        "grupo": GrupoCatalogo.TRABALHO,
        "icone": "file",
        "dominio": "rh.ausencia",
        "prazo_prometido_dias": 1,
        "campos": [
            {"chave": "data", "rotulo": "Data da ausência", "tipo": TipoCampo.DATA,
             "obrigatorio": True},
            {"chave": "arquivo", "rotulo": "Atestado", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": True},
        ],
        "limite_auto_aprovacao": Decimal("0"),
    },
    {
        "chave": "home-office",
        "nome": "Trabalho remoto",
        "descricao_curta": "Solicitar dias de home office",
        "grupo": GrupoCatalogo.TRABALHO,
        "icone": "users",
        "dominio": "rh.ausencia",
        "prazo_prometido_dias": 2,
        "campos": [
            {"chave": "periodo", "rotulo": "Período", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
        ],
    },
    {
        "chave": "declaracao",
        "nome": "Declaração ou comprovante",
        "descricao_curta": "Vínculo, renda, tempo de serviço",
        "grupo": GrupoCatalogo.TRABALHO,
        "icone": "file",
        "dominio": "rh.documento",
        "prazo_prometido_dias": 1,
        "campos": [
            {"chave": "tipo", "rotulo": "Qual declaração", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
        ],
        # Documento próprio da pessoa: nada a aprovar.
        "limite_auto_aprovacao": Decimal("0"),
    },
    # ── Dinheiro ────────────────────────────────────────────────────
    {
        "chave": "reembolso",
        "nome": "Reembolso",
        "descricao_curta": "Despesa que você pagou e a empresa devolve",
        "grupo": GrupoCatalogo.DINHEIRO,
        "icone": "wallet",
        "dominio": "fin.reembolso",
        "prazo_prometido_dias": 5,
        "exige_valor": True,
        "exige_centro_custo": True,
        "campos": [
            {"chave": "comprovantes", "rotulo": "Comprovantes", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": True, "ajuda": "Fotografe os cupons — nós lemos o resto."},
        ],
        "limite_auto_aprovacao": Decimal("200"),
    },
    {
        "chave": "adiantamento",
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
        ],
    },
    {
        "chave": "compra",
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
        "nome": "Treinamento ou curso",
        "descricao_curta": "Curso externo, certificação, congresso",
        "grupo": GrupoCatalogo.DESENVOLVIMENTO,
        "icone": "book",
        "dominio": "hab.treinamento",
        "prazo_prometido_dias": 7,
        "exige_valor": True,
        "exige_centro_custo": True,
        "campos": [
            {"chave": "curso", "rotulo": "Qual curso", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "aplicacao", "rotulo": "Como vai aplicar no trabalho",
             "tipo": TipoCampo.TEXTO_LONGO, "obrigatorio": True},
        ],
    },
    {
        "chave": "reciclagem-nr",
        "nome": "Reciclagem de NR",
        "descricao_curta": "NR-10, NR-35 e outras habilitações a vencer",
        "grupo": GrupoCatalogo.DESENVOLVIMENTO,
        "icone": "book",
        "dominio": "hab.reciclagem",
        "prazo_prometido_dias": 10,
        "campos": [
            {"chave": "habilitacao", "rotulo": "Qual habilitação", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
        ],
        # Reciclagem obrigatória não passa por aprovação: habilitação vencida
        # bloqueia despacho, e negar a reciclagem trava a operação.
        "limite_auto_aprovacao": Decimal("0"),
    },
    # ── Jurídico ────────────────────────────────────────────────────
    {
        "chave": "analise-contrato",
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
