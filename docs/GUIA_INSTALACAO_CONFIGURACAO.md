# Guia de Instalacao e Configuracao

Este guia descreve como preparar o iConnect Workspace em desenvolvimento,
teste e producao. A base tecnica vem de `requirements*.txt`, `pyproject.toml`,
`iconnect_workspace/settings/*`, `.env.example` e comandos `manage.py`.

## Requisitos

- Python 3.13 ou superior.
- SQLite para desenvolvimento e testes locais.
- PostgreSQL em producao.
- Redis em producao para cache compartilhado do freio de tentativas de login.
- Dependencias Python:
  - `Django==6.0.8`
  - `psycopg2-binary`
  - `redis`
  - `gunicorn`
  - `reportlab`
  - ferramentas de teste em `requirements-dev.txt`.

## Ambiente local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

python manage.py migrate
python manage.py createsuperuser
```

O usuario administrativo usa e-mail como identificador, porque o modelo de
conta e `contas.Pessoa`, nao `auth.User`.

## Massa inicial

Todos os comandos `semear_*` rodam em simulacao por padrao. Use `--aplicar`
quando quiser gravar.

```bash
python manage.py semear_papeis --aplicar
python manage.py importar_organograma docs/exemplos/organograma-inicial.csv --criar-usuarios --aplicar
python manage.py semear_acessos --aplicar
python manage.py semear_centros_custo --aplicar

python manage.py semear_regras_aprovacao --aplicar
python manage.py semear_catalogo --aplicar
python manage.py semear_recursos --aplicar
python manage.py semear_estoque --aplicar
python manage.py semear_frota --aplicar
python manage.py semear_cursos --aplicar
python manage.py semear_faq --aplicar
python manage.py reindexar_busca
```

Para perfis de teste por papel:

```bash
python manage.py semear_perfis --aplicar
```

## Subir a aplicacao

```bash
python manage.py runserver
```

Abra `/workspace/`. O hub, busca, catalogo, documentacao, reservas e formularios
institucionais sao abertos. Acoes que assinam em nome de uma pessoa exigem
login em `/entrar/`.

## Variaveis obrigatorias em producao

| variavel | motivo |
|---|---|
| `SECRET_KEY` | assina sessao e CSRF; `settings/prod.py` recusa chave vazia ou de desenvolvimento |
| `ALLOWED_HOSTS` | lista os hosts aceitos; `*` e recusado em producao |
| `POSTGRES_PASSWORD` | senha do banco de producao |

## Variaveis de infraestrutura

| variavel | padrao | uso |
|---|---|---|
| `POSTGRES_DB` | `iconnect_workspace` | nome do banco |
| `POSTGRES_USER` | `workspace` | usuario do banco |
| `POSTGRES_HOST` | `localhost` | host do banco |
| `POSTGRES_PORT` | `5432` | porta do banco |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | cache compartilhado |
| `CSRF_TRUSTED_ORIGINS` | vazio | origens HTTPS permitidas para POST |
| `SECURE_SSL_REDIRECT` | `1` | forca HTTPS |
| `PROXIES_CONFIAVEIS` | `0` | quantidade de proxies confiaveis para ler `X-Forwarded-For` |

## Arquivos privados

`ARQUIVOS_PRIVADOS_ROOT` guarda anexos, documentos e fotos fora de `MEDIA_ROOT`.
Isto e regra de seguranca: o unico acesso deve passar por view que autoriza
antes de entregar o arquivo.

Inclua este diretorio no backup. Ele nao esta todo dentro do banco.

## Logs

Em producao o portal grava em `LOG_DIR` (padrao `/var/log/workspace`), ao lado
dos logs do cron:

- `erros.log`: erros 500 com traceback e avisos do portal.
- `seguranca.log`: entrada, saida, bloqueio por tentativas e concessao de papel.

O usuario que roda o gunicorn precisa de escrita na pasta. Sem ela, o portal
sobe normalmente e loga so no terminal. A rotacao (30 dias; 180 para
seguranca) e do logrotate:

```bash
sudo cp deploy/logrotate /etc/logrotate.d/workspace
```

## Integracao com iConnect Platform

| variavel | efeito |
|---|---|
| `ICONNECT_URL` | destino do tile e links para o iConnect Platform |
| `ICONNECT_API_URL` | quando vazio, a integracao fica desligada sem quebrar o Workspace |
| `ICONNECT_TIMEOUT` | tempo maximo de chamadas HTTP ao Platform |
| `WORKSPACE_SHARED_SECRET` | segredo compartilhado no `sso-exchange` |

Os produtos continuam separados: bancos, sessoes e usuarios nao sao
compartilhados. A ligacao principal e link; a integracao HTTP e somente leitura.

## Validacao

```bash
python -m pytest
python scripts/check_coverage_ratchet.py
```

Os pisos de cobertura por app e de quantidade de testes estao em
`pyproject.toml`.
