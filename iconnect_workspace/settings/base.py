"""Configuração comum do iConnect Workspace.

## Por que este projeto existe separado do iConnect Platform

São dois produtos. O Workspace organiza a vida corporativa da empresa; o
iConnect Platform organiza a operação de atendimento aos clientes. A ligação
entre eles é **um link** — o tile do launcher, em `ICONNECT_URL` — e nada mais:
não há banco compartilhado, sessão compartilhada nem tabela de usuários
compartilhada.

Essa separação não é estética. No projeto anterior os dois dividiam uma
`auth.User` e um cookie de sessão, e a consequência era concreta: uma conta
criada pelo Workspace passava a valer no iConnect, onde "usuário sem papel
definido" era tratado como analista. Aqui isso é impossível por construção, e
não por disciplina.

## O que a separação nos deu de imediato

CSP **estrita**. O iConnect precisa de `unsafe-inline` em `style-src` porque usa
`style=` em escala; o Workspace tem zero estilo inline, garantido por teste. Nos
dois no mesmo processo, o header era o do denominador comum e o Workspace pagava
a dívida do outro sem colher o benefício. Ver `SEGURANCA_CSP` abaixo.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _env(chave: str, default: str = "") -> str:
    return os.environ.get(chave, default)


def _env_bool(chave: str, default: bool = False) -> bool:
    bruto = os.environ.get(chave)
    if bruto is None:
        return default
    return bruto.strip().lower() in ("1", "true", "yes", "on", "sim")


# ── Identidade do projeto ───────────────────────────────────────────

SECRET_KEY = _env("SECRET_KEY", "dev-only-nao-usar-em-producao")
DEBUG = False
ALLOWED_HOSTS: list[str] = [
    h.strip() for h in _env("ALLOWED_HOSTS", "").split(",") if h.strip()
]

# ── Apps ────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Conta da pessoa. App separado de `identidade` de propósito: o modelo de
    # usuário tem de existir ANTES da FK de `Lotacao`, e manter os dois no mesmo
    # app criaria um ciclo no grafo de migração daquele app.
    "contas",
    # IDN — organograma, papel com escopo e vigência. Raiz da dependência:
    # só conhece o modelo de usuário.
    "identidade",
    # WKS — a superfície e os motores do Workspace. Folha: ninguém importa dele.
    "workspace",
    # Domínio de orçamento. Implementa o contrato `workspace.providers.orcamento`
    # e se registra no `ready()` — é o que mantém a barra tripla da bandeja de
    # aprovação viva depois que `CentroCusto` deixou de morar no iConnect.
    "financas",
    # Espelho do que vem de fora. NÃO tem view, nem formulário, nem tela: o
    # dado nasce onde é operado. Implementa `workspace.providers.resultados`.
    "resultados",
    # Quem traz o dado. Conhece Sankhya, monday e Platform; o Workspace não
    # conhece nenhum dos três. A direção é cargas → resultados → contrato.
    #
    # NÃO se chama `integracoes` porque `workspace/integracoes/` já existe e
    # faz outra coisa — é o link com a Platform, dentro da requisição do
    # usuário. Dois pacotes com o mesmo nome é como um import errado passa
    # despercebido numa revisão.
    "cargas",
]

# A conta nasce do SSO (ADR-013). O identificador é o e-mail corporativo, e não
# um `username` digitado — ver `contas/models.py`.
AUTH_USER_MODEL = "contas.Pessoa"

# ── Middleware ──────────────────────────────────────────────────────

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Cabeçalhos de segurança, com a CSP estrita. Nosso, e não de biblioteca:
    # são 40 linhas cuja razão de existir é ser explícita e testada.
    "iconnect_workspace.seguranca.CabecalhosDeSeguranca",
    # A ponte SSO → JWT (§21). DEPOIS de `AuthenticationMiddleware` e de
    # `SessionMiddleware`, porque escreve na sessão. Sem `ICONNECT_API_URL`
    # configurada ele não faz nada além de um `if` por requisição.
    "workspace.integracoes.middleware.PonteSSO",
]

ROOT_URLCONF = "iconnect_workspace.urls"
WSGI_APPLICATION = "iconnect_workspace.wsgi.application"
ASGI_APPLICATION = "iconnect_workspace.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                # Os contadores do rail e do sino. Context processor e não
                # variável por view: a casca está em todas as telas, e depender
                # de cada view lembrar garante que uma esqueça — foi exatamente
                # assim que a topbar já perdeu o sino uma vez.
                "workspace.context.rail",
                "workspace.context.assistente",
                # O carimbo de frescor de cada bloco agregado. Mesma razão dos
                # dois acima, e um motivo a mais: um bloco de números sem
                # procedência não é uma tela incompleta, é uma tela que afirma
                # sem dizer de quando.
                "workspace.context.carimbos",
                # Qual grupo do trilho nasce aberto. Mesma razão dos três acima:
                # o trilho está em toda tela, e a rota é quem sabe onde a pessoa
                # está — não a view, que pode esquecer de dizer.
                "workspace.navegacao.grupo_aberto",
            ],
        },
    },
]

# ── Banco ───────────────────────────────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Autenticação ────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Para onde `@login_required` manda quem precisa se identificar. O Workspace é
# aberto; o decorador aparece só nos atos que assinam em nome de alguém, e é
# esta a tela que eles usam.
LOGIN_URL = "/entrar/"
LOGIN_REDIRECT_URL = "/workspace/meu-dia/"
LOGOUT_REDIRECT_URL = "/workspace/"

# ── Internacionalização ─────────────────────────────────────────────

# pt-BR e não en-us: a home escreve "Sexta-feira, 7 de agosto" com
# `formats.date_format`, que depende do locale do Django. Trocar isto quebra a
# data da home e a pluralização dos contadores.
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ── Arquivos ────────────────────────────────────────────────────────

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Anexos do Workspace moram FORA de `MEDIA_ROOT`, e isto é uma regra de
# segurança, não organização de pasta: servidor web serve `MEDIA_ROOT` como
# arquivo estático, sem passar por view nenhuma — foi assim que, no projeto
# anterior, o nginx expôs `/media/` sem autenticação. Aqui o único caminho até
# um anexo é `workspace:baixar_anexo`, que autoriza antes de entregar.
# Há teste que falha se este caminho cair dentro de `MEDIA_ROOT`.
ARQUIVOS_PRIVADOS_ROOT = Path(
    _env("ARQUIVOS_PRIVADOS_ROOT", str(BASE_DIR / "arquivos_privados"))
)

# ── Segurança ───────────────────────────────────────────────────────

# ── A CSP ───────────────────────────────────────────────────────────
#
# Até a Onda 9.5, esta política não tinha `unsafe-inline` em diretiva nenhuma, e
# o comentário aqui dizia isso com orgulho. Ele mudou, e a razão está no ADR-040
# (docs/EXEC_25_GRAFICOS.md): a decisão de produto passou a ser usar biblioteca
# de gráficos, e toda biblioteca de mercado escreve `style=` no DOM — tooltip,
# redimensionamento, posição de legenda.
#
# ## O que abriu, e o que NÃO abriu
#
#   style-src   'self' 'unsafe-inline'   — abriu. É o preço da biblioteca.
#   script-src  'self' 'nonce-…'         — INTOCADA quanto a inline. Nenhuma
#                                          biblioteca de gráfico precisa dela.
#
# ## Por que o nonce está em script-src e NÃO em style-src
#
# Navegador moderno **ignora `unsafe-inline` quando há nonce na mesma diretiva**.
# Um nonce em `style-src` manteria o comportamento antigo com a aparência de ter
# aberto — e o sintoma seria gráfico saindo errado, em silêncio, sem nada no log.
#
# Em `script-src` o nonce não enfraquece nada: ele só anula `unsafe-inline`, que
# não está lá. O que ele faz é permitir, sem ambiguidade, o bloco
# `<script type="application/json" nonce="…">` que leva os números do servidor
# para o gráfico.
#
# ## As contrapartidas
#
# Com `style-src` aberta, o vetor real passa a ser injeção de CSS: um seletor de
# atributo com `background-image` vaza o valor de um campo para fora. Seis das
# oito saídas já estavam fechadas desde o início; `frame-src 'none'` entrou
# nesta onda — `default-src` a cobria, e `default-src 'self'` permite iframe de
# mesma origem.
#
# A política é montada POR REQUISIÇÃO em `iconnect_workspace.seguranca`, porque o
# nonce muda a cada uma. Esta constante é o molde, com `{nonce}` no lugar.
SEGURANCA_CSP_MOLDE = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{nonce}'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "object-src 'none'"
)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"

# ── Duração da sessão ───────────────────────────────────────────────
#
# O padrão do Django é DUAS SEMANAS, absolutas. Numa estação compartilhada de
# obra ou numa recepção, isso é uma sessão viva por catorze dias depois de a
# pessoa ir embora — e o que esta sessão abre é atestado médico, comprovante e
# bandeja de aprovação.
#
# Doze horas cobre a jornada mais longa com folga, e `SAVE_EVERY_REQUEST` faz a
# contagem deslizar com o uso: quem está trabalhando não é derrubado no meio da
# tarde, e quem parou expira. Sem o segundo, o prazo contaria desde o login e
# expulsaria alguém em plena digitação.
#
# O custo é uma gravação de sessão por requisição COM sessão. O hub aberto não
# paga: sessão vazia não é gravada, e o visitante anônimo não tem nenhuma.
SESSION_COOKIE_AGE = int(_env("SESSION_COOKIE_AGE", str(12 * 60 * 60)))
SESSION_SAVE_EVERY_REQUEST = True

# ── Limites de requisição ───────────────────────────────────────────
#
# Explícitos, e não confiando no padrão: os padrões do Django são razoáveis e
# mudam entre versões, e um upload sem teto é disco cheio — que derruba o
# produto inteiro sem precisar de nenhuma falha de código.
#
# `MAX_MEMORY_SIZE` é o que o Django aceita em memória antes de ir para arquivo
# temporário. `MAX_NUMBER_FIELDS` é a defesa contra o POST com cem mil campos,
# que gasta CPU no parsing antes de qualquer view rodar. `MAX_NUMBER_FILES` é o
# teto por requisição — o validador já limita 10 MB POR arquivo, e sem um teto
# de quantidade dez mil arquivos de 10 MB passariam um a um.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1_000
DATA_UPLOAD_MAX_NUMBER_FILES = 20
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# ── Atrás de proxy ──────────────────────────────────────────────────
#
# Quantos proxies confiáveis existem entre o cliente e este processo. ZERO por
# padrão, que é o comportamento seguro: sem proxy, `REMOTE_ADDR` é o cliente.
#
# Por que isto precisa existir: o freio de tentativas conta falhas POR ORIGEM.
# Atrás de um balanceador, toda a empresa chega com o MESMO `REMOTE_ADDR` — e
# vinte senhas erradas de vinte pessoas diferentes numa segunda-feira trancariam
# o produto para todo mundo. O controle de segurança viraria a indisponibilidade.
#
# Ler `X-Forwarded-For` cru resolveria isso e abriria outro buraco: o cabeçalho
# é escrito pelo cliente, e um atacante o troca a cada tentativa. Com a
# CONTAGEM certa, o endereço é lido da posição que o proxy escreveu, e o que o
# cliente inventou fica à esquerda, ignorado. Ver `contas/entrada.py::ip_de`.
PROXIES_CONFIAVEIS = int(_env("PROXIES_CONFIAVEIS", "0"))

# Cookie com nome próprio. Se um dia os dois produtos servirem do mesmo domínio,
# é isto que impede a sessão de um valer no outro.
SESSION_COOKIE_NAME = "wks_sessao"
CSRF_COOKIE_NAME = "wks_csrf"

# ── A ligação com o iConnect Platform ───────────────────────────────
#
# Eram um link e nada mais. Continuam sendo **dois produtos, dois deploys, dois
# bancos** — o que mudou é que o Workspace passou a LER o iConnect por HTTP, em
# vez de recriar dentro de si o que já existe lá (§20, §21, §38, §52).
#
# A direção da leitura é sempre a mesma: o Workspace pergunta, o iConnect
# responde. Nunca o contrário, e nunca escrita — abrir chamado continua sendo no
# iConnect, que é onde ele é atendido.

# O destino do tile no launcher e dos cards que levam para fora.
ICONNECT_URL = _env("ICONNECT_URL", "https://app.icodev.com.br/login/")

# ── PNCP · editais públicos ─────────────────────────────────────────
#
# A ÚNICA fonte do produto sem credencial: a Lei 14.133/2021 obriga a
# publicação e a API de consulta é aberta. Conferido em 08/09/2026 — uma
# chamada sem cabeçalho nenhum responde 200.
#
# `None` nos dois quer dizer "usa o padrão do conector": as 27 UFs e a lista de
# termos definida pelo comercial. Estão aqui, e não só no código, porque a lista
# de termos É o produto deste conector — ela vai errar nas primeiras semanas, e
# ajustá-la não pode exigir um deploy.
#
# `EditalPublico.termo_casado` guarda qual termo trouxe cada linha: é com ele
# que se vê o ruído e se poda a lista.
PNCP_UFS: list[str] | None = None
PNCP_TERMOS: list[str] | None = None

# ── O nome do produto ───────────────────────────────────────────────
#
# Aqui, e em UM lugar só. O nome já esteve escrito à mão em vinte e um pontos —
# título de aba, topbar, saudação da home, as duas telas de erro, o rótulo da
# paleta — e o rebatismo de 04/09/2026 ("Workspace" → "Portal ADB360") teve de
# achar os vinte e um. O vigésimo segundo, escrito depois, ficaria com o nome
# antigo até alguém reparar numa tela que quase ninguém abre.
#
# NÃO troca a rota `/workspace/`, o app Django `workspace`, nem o nome do
# repositório. URL é endereço: mudar `/workspace/` quebraria todo link já
# colado em e-mail, ata e chamado — e endereço antigo que dá 404 é pior que
# endereço com nome antigo. O dia em que valer a pena, é redirecionamento
# permanente, não renomeação.
PRODUTO_NOME = "Portal ADB360"

# A empresa dona da marca. Vai no `alt` do logo, onde o nome do produto não
# serve: quem usa leitor de tela precisa saber de quem é o portal, e "Portal
# ADB360" já está escrito ao lado em texto.
PRODUTO_MARCA = "Autodefesa Brasil"


# ── Os outros públicos da marca ─────────────────────────────────────
#
# Três públicos, três produtos, uma marca — a leitura do benchmark. Este produto
# é o **Portal ADB**, do colaborador. Cliente e fornecedor entram em OUTRO lugar,
# e o modelo de permissão daqui não os comporta: ele assume `Pessoa` com
# `Lotacao` no organograma. Ver ADR-038.
#
# VAZIAS por padrão, e é o estado de hoje: nenhum dos dois produtos existe.
# Vazio quer dizer AUSENTE, e não "em breve" — "em breve" é promessa, e ninguém
# decidiu que eles vão existir (ADR-039).
#
# Precisam ser absolutas e apontar para fora deste host; `workspace/publicos.py`
# recusa na subida do processo o que mandaria cliente para o portal do
# funcionário.
ADB_CLIENTE_URL = _env("ADB_CLIENTE_URL", "")
ADB_FORNECEDOR_URL = _env("ADB_FORNECEDOR_URL", "")

# A raiz da API. VAZIA por padrão, e é isso que mantém o produto instalável sem
# o iConnect: sem esta variável, `integracoes.disponivel()` é falso, as telas
# que dependem dela dizem isso em português, e nada mais quebra.
ICONNECT_API_URL = _env("ICONNECT_API_URL", "").rstrip("/")

# Segundos. Curto de propósito: a chamada acontece DENTRO de uma requisição do
# Workspace, e um iConnect lento não pode virar um Workspace lento. Estourou o
# tempo, a tela mostra o que sabe e diz que a outra parte não respondeu.
ICONNECT_TIMEOUT = float(_env("ICONNECT_TIMEOUT", "4"))

# O segredo compartilhado do §2 da API do iConnect: quando configurado dos dois
# lados, o `sso-exchange` exige o header `X-Workspace-Secret`. Vazio, a checagem
# é pulada do outro lado — é o que permite o rollout independente.
WORKSPACE_SHARED_SECRET = _env("WORKSPACE_SHARED_SECRET", "")

# ── Cargas de fontes externas ───────────────────────────────────────
#
# TODAS vazias por padrão, e é isso que mantém o produto instalável sem nenhuma
# integração: `conector.disponivel()` é falso, a carga registra "não
# configurada" — que é estado normal, não falha — e o carimbo do bloco diz
# "sem registro de carga" em vez de inventar um instante.
#
# Nenhum segredo tem valor padrão. Um default de conveniência num campo de
# credencial é como uma chave de desenvolvimento chega em produção.

# Sankhya Om — OAuth2 `client_credentials` no Gateway (conferido em 01/09/2026).
# `SANKHYA_TOKEN` é o X-Token gerado em Configurações Gateway do próprio ERP; o
# par client_id/secret sai do Portal do Desenvolvedor.
SANKHYA_BASE_URL = _env("SANKHYA_BASE_URL", "").rstrip("/")
SANKHYA_CLIENT_ID = _env("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = _env("SANKHYA_CLIENT_SECRET", "")
SANKHYA_TOKEN = _env("SANKHYA_TOKEN", "")

# Quais entidades e campos ler do Sankhya. Depende da IMPLANTAÇÃO — `rootEntity`
# é o nome da view naquele ambiente — e por isso é configuração, e não código.
# Ver `cargas/conectores/sankhya.py::CONSULTAS` para o formato e o padrão.
SANKHYA_CONSULTAS: dict | None = None

# monday.com — token de usuário de SERVIÇO, somente leitura. Nunca o pessoal de
# alguém: token pessoal enxerga tudo o que a pessoa enxerga, e sai da empresa
# junto com ela.
MONDAY_TOKEN = _env("MONDAY_TOKEN", "")

# Ids de board e de coluna da conta da ADB. São números daquela conta e não têm
# valor padrão possível — o levantamento sai de `scripts/inventario_monday.py`.
MONDAY_BOARDS: dict | None = None

# Rotas da API do Platform. `None` usa o padrão do conector; existe para o dia
# em que o caminho versionar sem o conteúdo versionar junto.
PLATFORM_ROTAS: dict | None = None

# Diretório dos CSVs canônicos. É por aqui que entra a carga manual — e a massa
# de teste, que usa o mesmo caminho de qualquer outra fonte.
CARGAS_CSV_DIR = _env("CARGAS_CSV_DIR", "")

# ── Financeiro ──────────────────────────────────────────────────────

# Para onde a pessoa devolve o que sobrou de um adiantamento. Em `settings` e
# não no banco de propósito: conta bancária editável por qualquer um com acesso
# ao admin é um convite a fraude — aqui, trocar a conta exige deploy.
#
# Vazio em desenvolvimento. A tela de acerto diz "peça a conta ao Financeiro"
# em vez de mostrar um número inventado, que é o erro que faria o dinheiro ir
# para o lugar errado.
CONTA_BANCARIA_EMPRESA = _env("CONTA_BANCARIA_EMPRESA", "")

# ── Pendências de ponto → WhatsApp ──────────────────────────────────

# O Portal fala com o n8n, e só com ele. A chave da Evolution API nunca chega
# aqui: quem a conhece é o workflow, do outro lado do webhook. Um segredo a
# menos neste processo é um segredo a menos para vazar num traceback.
PONTO_N8N_WEBHOOK_URL = _env("N8N_PONTO_WEBHOOK_URL", "")
PONTO_N8N_TOKEN = _env("N8N_PONTO_TOKEN", "")
PONTO_N8N_TIMEOUT = int(_env("PONTO_WHATSAPP_TIMEOUT", "30"))

# O teto de mensagens num disparo real. Não é limite técnico: é o que impede
# que uma planilha errada vire dois mil WhatsApps antes de alguém perceber.
PONTO_MAXIMO_POR_LOTE = int(_env("PONTO_MAXIMO_POR_LOTE", "500"))
