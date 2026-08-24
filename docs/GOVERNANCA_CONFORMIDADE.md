# Governanca e Conformidade

Este documento consolida controles de seguranca, privacidade, responsabilidades
e inventario de sistemas observados no codigo atual.

## Politicas de seguranca implementadas

- CSP estrita em `SEGURANCA_CSP`, sem `unsafe-inline`.
- `X-Frame-Options = DENY`.
- `frame-ancestors 'none'`.
- `X-Content-Type-Options: nosniff`.
- `Referrer-Policy: strict-origin-when-cross-origin`.
- `Permissions-Policy` restritiva.
- `Cross-Origin-Opener-Policy: same-origin`.
- `Cross-Origin-Resource-Policy: same-origin`.
- Cookies `HttpOnly`, `SameSite=Lax` e seguros em producao.
- HSTS em producao.
- Nomes proprios de cookie: `wks_sessao` e `wks_csrf`.
- Login com freio de tentativas para `/entrar/` e `/admin/login/`.
- Anexos fora de `MEDIA_ROOT`.
- Health check sem vazamento de detalhes internos.

## Privacidade e LGPD

Dados pessoais tratados pelo Workspace:

- nome e e-mail corporativo;
- identificadores do Entra ID;
- lotacao, gestor, cargo, unidade e departamento;
- centro de custo;
- solicitacoes, anexos, comentarios e historico;
- correspondencias;
- comprovantes e evidencias;
- confirmacoes de leitura;
- matriculas em cursos e habilitacoes.

Controles observados:

- acesso pessoal exige autenticacao;
- anexos exigem autorizacao antes do download;
- busca aplica recorte de acesso;
- contas sao desativadas em vez de apagadas para preservar trilha;
- privilegio administrativo nao e derivado automaticamente de SSO.

Pontos que dependem de politica organizacional:

- prazo de retencao de anexos, comprovantes e relatorios;
- classificacao de documentos;
- base legal para leitura obrigatoria e registros de auditoria;
- processo de atendimento a solicitacoes de titular.

## RACI sugerido

| area | responsavel | conta | consulta | informa |
|---|---|---|---|---|
| Produto Workspace | Produto/Operacoes internas | Diretoria | RH, Financeiro, TI | usuarios |
| Identidade e papeis | RH/Administracao | Operacoes | Gestores | usuarios afetados |
| Seguranca tecnica | TI/SecOps | CTO | Produto | Diretoria |
| Infraestrutura | DevOps/TI | CTO | Desenvolvimento | usuarios em incidente |
| Centro de custo | Financeiro | Diretoria financeira | Gestores | areas solicitantes |
| Acervo normativo | Dono do documento | Compliance/RH | Juridico | publico-alvo |
| Estoque e custodia | Suprimentos | Operacoes | Financeiro | pessoas custodiantes |
| Frota | Operacoes/Suprimentos | Operacoes | Financeiro | condutores |

## Inventario de sistemas e dependencias

| item | tipo | criticidade | observacao |
|---|---|---|---|
| Django app `iconnect-workspace` | aplicacao | alta | sistema principal |
| PostgreSQL | banco | alta | producao |
| Redis | cache | media/alta | freio de tentativas precisa ser compartilhado |
| `ARQUIVOS_PRIVADOS_ROOT` | armazenamento | alta | anexos e documentos; precisa de backup |
| iConnect Platform | integracao opcional | media | somente leitura; falha degrada telas integradas |
| Entra ID/M365 | SSO futuro | alta quando habilitado | campos ja preparados em `Pessoa` |
| ReportLab | dependencia | media | geracao de PDF de relatorios |

## Conformidade operacional

Antes de producao:

- preencher `.env` sem segredos versionados;
- configurar `ALLOWED_HOSTS` sem `*`;
- garantir HTTPS e proxy sobrescrevendo `X-Forwarded-Proto`;
- configurar Redis compartilhado entre workers;
- definir `PROXIES_CONFIAVEIS` corretamente;
- garantir backup de banco e `ARQUIVOS_PRIVADOS_ROOT`;
- rodar testes e ratchets;
- revisar `EXEC_14_SEGURANCA.md`.

## Evidencias recomendadas

- relatorio de testes (`junit.xml`);
- `coverage.json`;
- log de deploy;
- saida de `python manage.py check --deploy`;
- evidencias de backup e restore testado;
- changelog da versao implantada;
- lista de variaveis de ambiente sem valores secretos.
