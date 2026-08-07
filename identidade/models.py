"""Modelos de IDN — Identidade & Organização.

Vazio de propósito. O ST-002 cria apenas o esqueleto do app; os modelos entram
nas stories da Onda 1 (Frente A), nesta ordem de dependência:

    ST-007  Unidade, Departamento
    ST-008  Papel (permissões declarativas)
    ST-009  evolução de PerfilUsuario (mora em `dashboard`, não aqui)
    ST-012  AtribuicaoPapel (escopo + vigência)
    ST-013  Delegacao

`Pessoa` NÃO vira modelo novo: a Etapa 3 decidiu evoluir o `PerfilUsuario`
existente em `dashboard`, para não duplicar identidade nem quebrar o
`related_name="perfil"` já usado em views e templates.
"""
