# Arquitetura do Sistema

O iConnect Workspace e uma aplicacao Django separada do iConnect Platform. A
fronteira e deliberada: sem banco compartilhado, sem sessao compartilhada e sem
tabela de usuarios compartilhada.

## Apps

| app | responsabilidade |
|---|---|
| `contas` | modelo de usuario `Pessoa`, login com e-mail, freio de tentativas e auditoria de entrada |
| `identidade` | organograma, lotacao, papeis, escopos, delegacao e autorizacao |
| `workspace` | superficie do produto, catalogo, aprovacao, conteudo, reservas, estoque, frota, busca e notificacoes |
| `financas` | centro de custo, lancamentos e provider de orcamento |
| `iconnect_workspace` | settings, URLs de raiz, WSGI/ASGI, saude e cabecalhos de seguranca |

## Direcao de dependencia

Regra central:

```text
dominio -> contratos/providers
superficie -> dominio
financas -> contrato de orcamento
```

`identidade` e raiz de autorizacao. `workspace` e folha: ele consome identidade,
contas e contratos, mas outros dominios nao devem depender da sua superficie de
views.

## Configuracao

`settings/base.py` contem:

- apps instalados;
- middleware;
- banco SQLite padrao;
- `AUTH_USER_MODEL = "contas.Pessoa"`;
- login em `/entrar/`;
- `pt-br` e `America/Sao_Paulo`;
- `ARQUIVOS_PRIVADOS_ROOT`;
- CSP estrita;
- limites de upload;
- configuracao da integracao com Platform;
- conta bancaria da empresa para acerto de adiantamento.

`settings/prod.py` troca para PostgreSQL, Redis, cookies seguros, HSTS,
`ManifestStaticFilesStorage` e logging estruturado em console.

## Middleware

Ordem relevante:

- `SecurityMiddleware`
- `SessionMiddleware`
- `LocaleMiddleware`
- `CsrfViewMiddleware`
- `AuthenticationMiddleware`
- `CabecalhosDeSeguranca`
- `PonteSSO`

`PonteSSO` roda depois de sessao e autenticacao porque pode escrever na sessao.
Sem `ICONNECT_API_URL`, ele degrada para uma checagem barata.

## Modelos centrais

Identidade:

- `Pessoa`
- `Unidade`
- `Departamento`
- `Lotacao`
- `Papel`
- `AtribuicaoPapel`
- `Delegacao`

Servicos e workflow:

- `ItemCatalogo`
- `SolicitacaoServico`
- `SolicitacaoAprovacao`
- `EtapaAprovacao`
- `RegraAprovacao`
- `EventoSolicitacao`
- `ComentarioSolicitacao`
- `Anexo`

Conteudo e comunicacao:

- `Documento`
- `ConfirmacaoLeitura`
- `Publicacao`
- `PerguntaFrequente`
- `EntradaIndice`
- `SujeitoIndice`

Operacao interna:

- `Recurso`
- `Reserva`
- `Correspondencia`
- `Material`
- `SaldoEstoque`
- `MovimentoEstoque`
- `Custodia`
- `Veiculo`
- `DespesaVeiculo`
- `Curso`
- `Matricula`
- `Relatorio`
- `Oportunidade`

Financeiro:

- `CentroCusto`
- `Lancamento`
- `Compromisso`
- `DespesaReembolso`
- `AcertoAdiantamento`

## Padroes de dominio

Catalogo:

- navegacao por intencao, nao departamento;
- no maximo tres campos obrigatorios incondicionais;
- dados conhecidos devem vir da identidade;
- dominio e roteamento, nao taxonomia visual.

Aprovacao:

- motor unico para varios dominios;
- acoplamento por `dominio + origem_id`;
- cadeia definida por dados em `RegraAprovacao`;
- reprovar e devolver sao estados diferentes.

Arquivos:

- anexos fora de `MEDIA_ROOT`;
- download somente por view autorizada;
- validacao por extensao, MIME e magic bytes;
- limite por campo.

Busca:

- indice interno;
- ACL aplicada na consulta;
- reindexacao por comando quando houver update em massa.

## Seguranca por desenho

- CSP sem `unsafe-inline`.
- Cookies com nomes proprios: `wks_sessao` e `wks_csrf`.
- Login do produto e do admin com freio de tentativas.
- `PROXIES_CONFIAVEIS` controla leitura de `X-Forwarded-For`.
- Uploads com tamanho e quantidade limitados.
- Health check anonimo sem dados sensiveis.

## Testes e qualidade

O projeto usa `pytest`, `pytest-django` e `pytest-cov`. A configuracao esta em
`pyproject.toml`.

Ha dois ratchets:

- cobertura por app;
- quantidade minima de testes coletados.

Comandos:

```bash
python -m pytest
python scripts/check_coverage_ratchet.py
```
