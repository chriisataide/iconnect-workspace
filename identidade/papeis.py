"""Os papéis do V1.0 e o mapa a partir dos 6 papéis planos atuais.

Hoje o sistema tem `UserRole.role` com 6 valores (`dashboard/utils/rbac.py`) e
nenhum escopo. Aqui eles ganham escopo e permissões declarativas, **sem que
ninguém perca acesso**: o comando `semear_papeis` cria as atribuições
equivalentes, e `UserRole` continua funcionando durante a transição.
"""

from __future__ import annotations

from identidade.models import (
    ESCOPO_EQUIPE,
    ESCOPO_GLOBAL,
    ESCOPO_PROPRIO,
    ESCOPO_UNIDADE,
)

# `chave`, `nome`, `escopo_padrao`, `permissoes`
#
# As permissões usam curinga por domínio onde o papel realmente responde pelo
# domínio inteiro. Enumerar 40 ações para "admin" seria lista que envelhece
# sozinha a cada feature nova.
PAPEIS_V1 = [
    {
        "chave": "admin",
        "nome": "Administrador",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": ["*"],
        "descricao": "Acesso total. Equivale ao papel `admin` atual.",
    },
    {
        "chave": "gerente",
        "nome": "Gerente",
        "escopo_padrao": ESCOPO_EQUIPE,
        "permissoes": [
            "rh.ler.equipe",
            "rh.aprovar.equipe",
            "apr.aprovar.equipe",
            "fin.ler.equipe",
            "fin.aprovar.equipe",
            "com.aprovar.equipe",
            "ops.ler.unidade",
            "hab.ler.equipe",
            "hab.inscrever.equipe",
            "log.ler.unidade",
            "doc.ler.publico",
        ],
        "descricao": "Gestão da própria equipe e leitura da operação da unidade.",
    },
    {
        "chave": "analista",
        "nome": "Analista",
        "escopo_padrao": ESCOPO_PROPRIO,
        "permissoes": [
            "rh.ler.proprio",
            "rh.solicitar.proprio",
            "fin.ler.proprio",
            "fin.solicitar.proprio",
            "com.solicitar.proprio",
            "log.solicitar.proprio",
            "hab.ler.proprio",
            "hab.inscrever.proprio",
            "ops.ler.unidade",
            "doc.ler.publico",
            "ti.solicitar.proprio",
        ],
        "descricao": "Autoatendimento e leitura da operação. É o papel padrão.",
    },
    {
        "chave": "tecnico_campo",
        "nome": "Técnico de Campo",
        "escopo_padrao": ESCOPO_PROPRIO,
        "permissoes": [
            "rh.ler.proprio",
            "rh.solicitar.proprio",
            "fin.solicitar.proprio",
            "ops.ler.proprio",
            "ops.executar.proprio",
            "log.ler.proprio",
            "log.solicitar.proprio",
            "hab.ler.proprio",
            "hab.inscrever.proprio",
            "doc.ler.publico",
        ],
        "descricao": "Sua rota, seu kit, suas habilitações. Sem KPI corporativo.",
    },
    {
        "chave": "sala_monitoramento",
        "nome": "Sala de Monitoramento",
        "escopo_padrao": ESCOPO_UNIDADE,
        # Somente leitura de propósito: turno de 12h com poder de despacho e
        # sem supervisão é onde acidente operacional acontece.
        "permissoes": [
            "ops.ler.unidade",
            "ti.status.ler",
            "doc.ler.publico",
        ],
        "descricao": "Leitura da operação ao vivo. Sem despacho, por decisão.",
    },
    {
        "chave": "cliente",
        "nome": "Cliente",
        "escopo_padrao": ESCOPO_PROPRIO,
        "permissoes": [
            "cli.ler.proprio",
        ],
        "descricao": "Portal do cliente. Nunca vê nada interno.",
    },
]

# `UserRole.role` → chave do papel em IDN. Um-para-um: nenhum papel atual se
# divide nem se funde, para que a migração seja verificável linha a linha.
MAPA_PAPEL_LEGADO = {
    "admin": "admin",
    "gerente": "gerente",
    "analista": "analista",
    "tecnico_campo": "tecnico_campo",
    "sala_monitoramento": "sala_monitoramento",
    "cliente": "cliente",
    # Aliases legados que `UserRole.LEGACY_ROLE_MAP` já resolvia.
    "supervisor": "gerente",
    "tecnico_senior": "tecnico_campo",
    "agente": "analista",
    "financeiro": "gerente",
    "visualizador": "analista",
}
