"""Os papéis do Portal.

**Não são os papéis do iConnect.** O iConnect é plataforma separada, com 1432
técnicos e clientes; o Portal é dos funcionários da icodev, que são algumas
dezenas. Espelhar `UserRole.role` aqui produziria `tecnico_campo` e `cliente`
como papéis do Portal, que não descrevem nada do que o Portal faz.

Os papéis abaixo derivam das permissões que os 8 módulos especificados exigem.
Cada um é uma resposta a "quem faz o quê no Portal", não a "quem é quem no
iConnect".

## Como o escopo funciona

`escopo_padrao` é o que a atribuição herda quando ninguém informa outro. As
permissões trazem o escopo embutido (`rh.ler.equipe`), e o embutido vence o
padrão — é mais específico. Ver `identidade/services/autorizacao.py`.
"""

from __future__ import annotations

from identidade.models import (
    ESCOPO_EQUIPE,
    ESCOPO_GLOBAL,
    ESCOPO_PROPRIO,
    ESCOPO_UNIDADE,
)

# Permissões que TODO funcionário tem. Repetir em cada papel produziria seis
# listas para manter em sincronia.
AUTOATENDIMENTO = [
    "rh.ler.proprio",
    "rh.solicitar.proprio",
    "fin.ler.proprio",
    "fin.solicitar.proprio",
    "com.solicitar.proprio",
    "log.ler.proprio",
    "log.solicitar.proprio",
    "hab.ler.proprio",
    "hab.inscrever.proprio",
    "ti.ler.proprio",
    "ti.solicitar.proprio",
    "ti.status.ler",
    "doc.ler.publico",
    "doc.sugerir",
]

PAPEIS_V1 = [
    {
        "chave": "colaborador",
        "nome": "Colaborador",
        "escopo_padrao": ESCOPO_PROPRIO,
        "permissoes": AUTOATENDIMENTO,
        "descricao": (
            "Todo funcionário. Autoatendimento: suas férias, seus documentos, "
            "suas habilitações, seus pedidos. É o papel padrão."
        ),
    },
    {
        "chave": "gestor",
        "nome": "Gestor",
        "escopo_padrao": ESCOPO_EQUIPE,
        "permissoes": AUTOATENDIMENTO
        + [
            "rh.ler.equipe",
            "rh.aprovar.equipe",
            "apr.aprovar.equipe",
            "fin.aprovar.equipe",
            "com.aprovar.equipe",
            "hab.ler.equipe",
            "hab.inscrever.equipe",
            "doc.leitura.cobrar.equipe",
        ],
        "descricao": (
            "Responde por uma equipe. Aprova o que vem dos liderados e vê a "
            "cobertura deles. O escopo `equipe` vem do organograma (Lotacao.gestor)."
        ),
    },
    {
        "chave": "diretoria",
        "nome": "Diretoria",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "apr.aprovar.global",
            "fin.aprovar.global",
            "com.aprovar.global",
            "rh.ler.global",
            "fin.ler.global",
            "ops.ler.global",
            # Exceção de habilitação vencida é de diretoria, auditada e
            # notificada ao jurídico. Bloqueio sem escape faz a operação burlar
            # o sistema; escape fácil torna o bloqueio decorativo.
            "ops.excecao.certificacao",
            "log.perda.registrar",
        ],
        "descricao": "Último degrau da cadeia de aprovação. Vê tudo, aprova acima do teto.",
    },
    {
        "chave": "rh",
        "nome": "RH",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "rh.ler.global",
            "rh.admin.global",
            "hab.ler.unidade",
            "hab.registrar.presenca",
            "doc.publicar.assunto",
            "com.publicar.unidade",
        ],
        "descricao": "Pessoas: perfil, férias, documentos com validade, onboarding.",
    },
    {
        "chave": "financeiro",
        "nome": "Financeiro",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "fin.ler.global",
            "fin.aprovar.centro_custo",
            "fin.contrato.ler.unidade",
            "apr.aprovar.equipe",
        ],
        "descricao": "Reembolso, prestação de contas, orçamento por centro de custo.",
    },
    {
        "chave": "compras",
        "nome": "Compras",
        "escopo_padrao": ESCOPO_UNIDADE,
        "permissoes": AUTOATENDIMENTO
        + [
            "com.operar.unidade",
            "com.receber.unidade",
            "com.ler.unidade",
            "com.fornecedor.cadastrar",
            "log.ler.unidade",
        ],
        "descricao": (
            "Transforma requisição aprovada em pedido. NÃO aprova — quem pede não "
            "aprova, quem aprova não compra, quem compra não recebe."
        ),
    },
    {
        "chave": "logistica",
        "nome": "Logística",
        "escopo_padrao": ESCOPO_UNIDADE,
        "permissoes": AUTOATENDIMENTO
        + [
            "log.ler.unidade",
            "log.movimentar.unidade",
            "log.custodia.ler.unidade",
            "log.custodia.atribuir.unidade",
            "log.inventario.contar.unidade",
        ],
        "descricao": (
            "Materiais e ativos. Conta o inventário mas NÃO o fecha — segregação "
            "de função é o controle interno mais básico de patrimônio."
        ),
    },
    {
        "chave": "ti",
        "nome": "TI",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "ti.atender.unidade",
            "ti.status.publicar",
            "ti.admin.global",
            "log.custodia.ler.unidade",
        ],
        "descricao": (
            "Status dos serviços e provisionamento de acesso. Provisiona, mas "
            "quem CONCEDE acesso é o dono do sistema — requisito de ISO 27001."
        ),
    },
    {
        "chave": "sesmt",
        "nome": "Segurança do Trabalho",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "hab.ler.unidade",
            "hab.validar.evidencia",
            "hab.exigencia.definir",
            "hab.registrar.presenca",
            "hab.auditoria.ler",
        ],
        "descricao": (
            "Valida evidência de habilitação e define o que cada serviço exige. "
            "Separado da operação de propósito: quem coordena a operação tem "
            "incentivo para liberar o técnico."
        ),
    },
    {
        "chave": "operacao",
        "nome": "Operação",
        "escopo_padrao": ESCOPO_UNIDADE,
        "permissoes": AUTOATENDIMENTO
        + [
            "ops.ler.unidade",
            "ops.despachar.unidade",
            "ops.escala.editar.unidade",
            "ops.incidente.comandar.unidade",
            "hab.ler.equipe",
        ],
        "descricao": "Painel ao vivo, despacho, escala e incidente.",
    },
    {
        "chave": "monitoramento",
        "nome": "Sala de Monitoramento",
        "escopo_padrao": ESCOPO_UNIDADE,
        # Somente leitura de propósito: turno de 12h com poder de despacho e sem
        # supervisão é onde acidente operacional acontece.
        "permissoes": ["ops.ler.unidade", "ti.status.ler", "doc.ler.publico"],
        "descricao": "Leitura da operação ao vivo, 24h. Sem despacho, por decisão.",
    },
    {
        "chave": "auditoria",
        "nome": "Auditoria",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": [
            "doc.ler.publico",
            "doc.auditoria.ler",
            "hab.auditoria.ler",
            "ti.auditoria.ler",
        ],
        "descricao": (
            "Somente leitura de trilha e evidência. Existe como papel próprio "
            "porque o auditor pode ser externo — cliente auditando fornecedor."
        ),
    },
]
