# Referencia de Rotas e Contratos

Esta referencia lista as principais superficies HTTP, comandos e contratos
internos do Workspace. O codigo fonte principal esta em `iconnect_workspace/urls.py`,
`workspace/urls.py`, `workspace/providers/` e `workspace/management/commands/`.

## Rotas de processo

| rota | nome | uso |
|---|---|---|
| `/saude/` | `saude` | health check; `200` com banco ok, `503` com banco indisponivel |
| `/` | redirect | envia para `workspace:home` |
| `/entrar/` | `entrar` | login com freio de tentativas |
| `/sair/` | `sair` | logout |
| `/admin/login/` | `admin_login` | login do admin com o mesmo freio |
| `/admin/` | admin | Django admin |

## Rotas publicas ou institucionais do Workspace

| rota | uso |
|---|---|
| `/workspace/` | home |
| `/workspace/buscar/` | busca |
| `/workspace/ajuda/` | ajuda |
| `/workspace/assistente/` | assistente |
| `/workspace/faq/` | perguntas frequentes |
| `/workspace/m/<chave>/` | pagina de modulo por departamento |
| `/workspace/documentacao/` | acervo normativo |
| `/workspace/reservas/` | grade de reservas |
| `/workspace/servicos/` | catalogo de servicos |

## Rotas que representam acao ou dado pessoal

Estas rotas normalmente exigem autenticacao ou autorizacao de negocio:

| rota | uso |
|---|---|
| `/workspace/meu-dia/` | pendencias da pessoa |
| `/workspace/minhas-solicitacoes/` | pedidos da pessoa |
| `/workspace/aprovacoes/` | bandeja de aprovacao |
| `/workspace/fila/` | fila de atendimento da area |
| `/workspace/notificacoes/` | avisos |
| `/workspace/anexo/<pk>/` | download autorizado de anexo |
| `/workspace/pessoas/` | administracao de pessoas e papeis |
| `/workspace/centros-custo/` | centro de custo e orcamento |

## Dominio de servicos

O contrato principal e `ItemCatalogo` + `SolicitacaoServico`.

- `ItemCatalogo.chave`: identificador do item.
- `ItemCatalogo.grupo`: agrupamento por intencao.
- `ItemCatalogo.dominio`: destino de roteamento, como `fin.reembolso`.
- `ItemCatalogo.campos`: lista JSON de campos do formulario.
- `ItemCatalogo.exige_valor`: habilita valor monetario.
- `ItemCatalogo.exige_centro_custo`: exige centro de custo.
- `ItemCatalogo.limite_auto_aprovacao`: abaixo do limite, pode pular aprovacao
  humana.
- `ItemCatalogo.url_externa`: abre outro sistema em vez de formulario interno.

Estados de `SolicitacaoServico`:

- `rascunho`
- `aguardando_aprovacao`
- `aprovada`
- `em_atendimento`
- `concluida`
- `devolvida`
- `rejeitada`
- `cancelada`

## Motor de aprovacao

O APR nao conhece os dominios especificos. Ele guarda:

- `SolicitacaoAprovacao.dominio`
- `SolicitacaoAprovacao.origem_id`
- solicitante;
- valor;
- centro de custo;
- dossie em JSON;
- etapas.

`RegraAprovacao` define etapas por dominio, faixa de valor, tipo de aprovador,
papel ou aprovador nominal.

Tipos de aprovador:

- `gestor_direto`
- `papel`
- `nominal`

Estados de etapa:

- `pendente`
- `aprovada`
- `devolvida`
- `rejeitada`
- `pulada`

## Identidade e autorizacao

`contas.Pessoa` e o `AUTH_USER_MODEL`. A conta usa e-mail como identificador e
tem campos preparados para Entra ID: `entra_oid` e `upn`.

`identidade` define:

- `Unidade`
- `Departamento`
- `Lotacao`
- `Papel`
- `AtribuicaoPapel`
- `Delegacao`

Permissoes de negocio sao strings declarativas, como `<dominio>.<acao>.<escopo>`.
O servico `identidade.services.autorizacao.pode()` resolve permissao, vigencia e
escopo.

## Contratos de provider

`workspace.providers` protege a direcao de dependencia. O dominio depende do
contrato, nao da superficie.

O contrato de orcamento e implementado por `financas`, que registra provider no
`ready()` do app. A barra de aprovacao combina:

- realizado: `financas.Lancamento`;
- comprometido: `workspace.Compromisso`;
- este pedido: valor da solicitacao em decisao.

## Comandos

Seeders e importacao:

- `semear_papeis`
- `importar_organograma`
- `exportar_organograma`
- `semear_acessos`
- `semear_perfis`
- `semear_centros_custo`
- `semear_regras_aprovacao`
- `semear_catalogo`
- `semear_recursos`
- `semear_estoque`
- `semear_frota`
- `semear_cursos`
- `semear_faq`

Operacao:

- `reindexar_busca`
- `conferir_estoque`
- `avisar_documentos`
- `avisar_frota`
- `avisar_habilitacoes`
- `avisar_marketing`

Com excecao dos comandos somente leitura, os comandos de seed e aviso usam
`--aplicar` para gravar.

## Integracao externa

A integracao com iConnect Platform e opcional e somente leitura do ponto de
vista do Workspace.

Variaveis relevantes:

- `ICONNECT_URL`
- `ICONNECT_API_URL`
- `ICONNECT_TIMEOUT`
- `WORKSPACE_SHARED_SECRET`

Quando `ICONNECT_API_URL` esta vazia, as telas informam que a integracao nao
esta configurada e o restante do Workspace continua funcionando.
