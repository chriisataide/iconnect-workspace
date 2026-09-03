"""Freio de tentativas em `/entrar/`.

## Por que existe

A tela de identificação voltou a existir quando os atos que assinam em nome de
alguém passaram a exigir sessão. Ela veio sem freio nenhum: um formulário de
senha aberto na rede da empresa, contra contas reais, aceitando tentativas
ilimitadas. Isso não é um risco teórico — é o alvo mais óbvio que um produto
interno oferece, e testar 10 mil senhas contra `christopher@…` custa minutos.

## Por que sem dependência

O projeto anterior tinha `django-axes` entre 57 dependências, e este repositório
cortou todas de propósito: o código do Workspace não importa biblioteca de
terceiros. Um contador em cache resolve o mesmo problema em menos linhas do que
o `settings` que o axes exigiria, e sem trazer migração, modelo e admin de
outra pessoa para dentro do produto.

## As duas contagens, e o que cada uma protege

    e-mail + IP   5 falhas / 15 min    o ataque comum: uma conta, uma origem
    IP            20 falhas / 15 min   a varredura: muitas contas, uma origem

**Por que NÃO existe contagem por e-mail sozinho.** Ela permitiria trancar
qualquer pessoa da empresa de fora do produto de propósito: 5 tentativas erradas
contra o e-mail de alguém e essa pessoa não entra mais. Bloqueio que se vira
contra a vítima é pior que o ataque que ele evita — para o inimigo distribuído,
que é raro num sistema interno, sobra a contagem por IP.

## O que ele NÃO faz, de propósito

Não diz quantas tentativas faltam, e não distingue "senha errada" de "bloqueado
por tentativas" com precisão suficiente para virar oráculo: a mensagem de erro
continua a mesma de sempre — "e-mail ou senha não conferem" — e o bloqueio só
acrescenta "aguarde alguns minutos". Contar em voz alta ensina o atacante a
esperar o mínimo necessário.

O contador vive em cache, então reinício de processo o zera. É aceitável e é
consciente: o freio existe para tornar a força bruta inviável em janela curta,
não para ser registro de auditoria. Em produção o cache é Redis, compartilhado
entre os processos, que é onde isso importa.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.views import LoginView
from django.core.cache import cache

from contas import auditoria

# Uma janela só para as duas contagens: duas janelas diferentes só somariam
# parâmetro para ajustar sem mudar o que o freio faz.
JANELA_SEGUNDOS = 15 * 60

LIMITE_POR_CONTA = 5
LIMITE_POR_ORIGEM = 20

PREFIXO = "entrada:freio"

#: A mesma frase nas duas portas. Ela não conta quantas tentativas faltam:
#: contar em voz alta ensina o atacante a esperar o mínimo necessário.
MENSAGEM_BLOQUEIO = (
    "Muitas tentativas. Aguarde alguns minutos antes de tentar de novo."
)


def _config(nome: str, padrao: int) -> int:
    """Permite ajustar por `settings` sem editar código — e permite ao teste
    usar limites pequenos sem simular 20 requisições."""
    return int(getattr(settings, nome, padrao))


def ip_de(request) -> str:
    """O IP de quem pede.

    ## Por que não é só `REMOTE_ADDR`

    Era, e `X-Forwarded-For` cru estava descartado pela razão certa: o cabeçalho
    é escrito pelo cliente, e um atacante o troca a cada tentativa — o que
    zeraria a contagem por origem, que é exatamente a proteção que ela dá.

    O que faltava era o outro lado. Atrás de um balanceador, TODA a empresa
    chega com o mesmo `REMOTE_ADDR`: vinte senhas erradas de vinte pessoas
    diferentes numa segunda-feira trancariam o produto para todo mundo, e o
    controle de segurança viraria a indisponibilidade.

    ## Como o cabeçalho passa a ser confiável

    Pela CONTAGEM. `PROXIES_CONFIAVEIS` diz quantos saltos existem entre o
    cliente e este processo. Cada proxy ACRESCENTA à direita o endereço de quem
    falou com ele, então com N proxies o cliente está na posição `-N`:

        cliente inventa       X-Forwarded-For: 1.2.3.4
        o proxy acrescenta    X-Forwarded-For: 1.2.3.4, <ip real>
        lemos [-1]                                      ^^^^^^^^^

    O que o cliente escreveu fica à esquerda e é ignorado. Com o número errado a
    leitura fica errada — por isso o padrão é ZERO, que devolve `REMOTE_ADDR` e
    é o comportamento seguro para quem não configurou nada.
    """
    proxies = int(getattr(settings, "PROXIES_CONFIAVEIS", 0) or 0)
    if proxies > 0:
        encaminhados = [
            parte.strip()
            for parte in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
            if parte.strip()
        ]
        # `>=` e não `==`: o cliente pode ter mandado entradas a mais, e elas
        # ficam à esquerda. Menos entradas do que proxies significa cabeçalho
        # ausente ou infraestrutura diferente do configurado — e aí a resposta
        # certa é cair no endereço da conexão, não adivinhar.
        if len(encaminhados) >= proxies:
            return encaminhados[-proxies]
    return request.META.get("REMOTE_ADDR", "") or "desconhecido"


def _chaves(email: str, ip: str) -> tuple[str, str]:
    # O e-mail entra normalizado e em minúsculas: `Fulano@…` e `fulano@…` são a
    # mesma conta, e contar separado daria o dobro de tentativas de graça.
    conta = (email or "").strip().lower()
    return f"{PREFIXO}:conta:{conta}:{ip}", f"{PREFIXO}:origem:{ip}"


def _contar(chave: str) -> int:
    """Incrementa dentro da janela. Devolve o total.

    `add` antes de `incr` porque `incr` levanta em chave ausente, e criar a
    chave já com o TTL é o que faz a janela ser deslizante a partir da PRIMEIRA
    falha — e não renovar a cada tentativa, que deixaria alguém bloqueado para
    sempre por insistir.
    """
    cache.add(chave, 0, JANELA_SEGUNDOS)
    try:
        return cache.incr(chave)
    except ValueError:
        # A chave expirou entre o `add` e o `incr`. Conta como a primeira.
        cache.set(chave, 1, JANELA_SEGUNDOS)
        return 1


def bloqueado(email: str, ip: str) -> bool:
    """Já passou de algum dos dois limites?"""
    chave_conta, chave_origem = _chaves(email, ip)
    return (
        (cache.get(chave_conta) or 0) >= _config("LOGIN_LIMITE_POR_CONTA", LIMITE_POR_CONTA)
        or (cache.get(chave_origem) or 0) >= _config("LOGIN_LIMITE_POR_ORIGEM", LIMITE_POR_ORIGEM)
    )


def registrar_falha(email: str, ip: str) -> None:
    for chave in _chaves(email, ip):
        _contar(chave)


def limpar(email: str, ip: str) -> None:
    """Acertou a senha: as tentativas erradas dela deixam de contar.

    Só a contagem da CONTA é limpa. A da origem fica: um acerto no meio de uma
    varredura não deve apagar o rastro das outras 19 tentativas erradas feitas
    do mesmo lugar.
    """
    chave_conta, _ = _chaves(email, ip)
    cache.delete(chave_conta)


class ComFreio:
    """Mixin de contagem de tentativas para qualquer `LoginView`.

    ## Por que virou mixin

    Era uma classe só, aplicada a `/entrar/`. A auditoria de segurança de agosto
    mediu o óbvio que ninguém tinha medido: **`/admin/login/` aceitava vinte
    senhas erradas seguidas, todas com HTTP 200**. O produto tinha uma porta com
    tranca e outra sem — e a sem tranca é a que abre o banco inteiro, sem passar
    por regra nenhuma do produto.

    Herda de `LoginView` em vez de reescrever: autenticação, `next`,
    redirecionamento e proteção de CSRF são do Django, e um login escrito à mão
    é onde se esquece de um deles.
    """

    def form_valid(self, form):
        limpar(form.cleaned_data.get("username", ""), ip_de(self.request))
        return super().form_valid(form)

    def form_invalid(self, form):
        """Registra a falha e devolve a tela de sempre.

        O bloqueio NÃO acontece aqui, e a diferença é de uma tentativa: o limite
        é quantas falhas cabem, então a última que cabe ainda é uma tentativa
        legítima e recebe a resposta normal. Quem barra é o `dispatch()`, na
        requisição seguinte — que é também onde barrar sai mais barato.
        """
        registrar_falha((self.request.POST.get("username") or "").strip(),
                        ip_de(self.request))
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        """Bloqueado nem chega a tentar a senha.

        Sem isto, cada tentativa a mais ainda custaria uma verificação de hash —
        que é lenta de propósito — e o freio viraria um jeito de consumir CPU do
        servidor.
        """
        if request.method == "POST":
            email = (request.POST.get("username") or "").strip()
            if bloqueado(email, ip_de(request)):
                form = self.get_form()
                form.is_valid()  # popula os erros de campo obrigatório
                # O erro no formulário, e não só a flag de contexto: a tela do
                # admin é do Django e não conhece `bloqueado`. Sem isto, quem
                # for barrado lá veria o formulário voltar sem explicação
                # nenhuma — e tentaria de novo, que é o oposto do que o freio
                # existe para conseguir.
                form.add_error(None, MENSAGEM_BLOQUEIO)
                # A linha do bloqueio. Sem ela o freio barra em silêncio, e
                # ninguém descobre que houve tentativa — que é metade do valor
                # de ter um freio.
                auditoria.bloqueio_por_tentativas(email, ip_de(request), request.path)
                contexto = self.get_context_data(form=form, bloqueado=True)
                return self.render_to_response(contexto, status=429)
        return super().dispatch(request, *args, **kwargs)


class LoginComFreio(ComFreio, LoginView):
    """A porta do Workspace."""

    template_name = "contas/entrar.html"

    def get_context_data(self, **kwargs):
        """Acrescenta os OUTROS públicos da marca, quando existirem.

        Quem é cliente ou fornecedor e digitou o endereço errado bate hoje numa
        tela de login que nunca vai passar — e sem nada dizendo para onde ir. É
        o único lugar do produto onde essa pessoa aparece, e por isso é aqui que
        o roteamento mora.

        Lista vazia é o estado normal: enquanto os outros produtos não
        existirem, a tela não desenha nada. Ver ADR-039.

        Importado dentro do método porque `contas` não conhece `workspace` — a
        direção da dependência é a outra, e um `import` no topo a inverteria
        para exibir três linhas de texto.
        """
        from workspace import publicos

        contexto = super().get_context_data(**kwargs)
        contexto["outros_publicos"] = publicos.externos()
        return contexto


class LoginDoAdminComFreio(ComFreio, LoginView):
    """A porta do `/admin/`, com o MESMO freio.

    O admin do Django edita a base sem passar pelas regras, pelo histórico nem
    pelas permissões do produto: é o alvo mais valioso do sistema, e era o único
    sem contagem de tentativas.

    Registrada em `urls.py` ANTES de `admin.site.urls`, e não por
    `AdminSite` própria: trocar a `AdminSite` obrigaria a mexer em cada
    `admin.site.register` dos quatro apps, para conseguir a mesma coisa. O nome
    de rota `admin:login` continua sendo o do Django e continua resolvendo para
    cá — é a mesma URL.

    O contexto é o que `AdminSite.login()` monta; sem ele o `admin/login.html`
    renderiza sem cabeçalho e sem título.
    """

    template_name = "admin/login.html"

    @property
    def authentication_form(self):
        # Importado tarde, como o próprio Django faz: `admin.forms` puxa o
        # modelo de usuário, e no topo deste módulo isso é cedo demais.
        from django.contrib.admin.forms import AdminAuthenticationForm

        return AdminAuthenticationForm

    def dispatch(self, request, *args, **kwargs):
        from django.contrib import admin

        # `current_app` é o que faz `each_context()` e os `{% url %}` do
        # template do admin resolverem para esta instância.
        request.current_app = admin.site.name
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from django.contrib import admin
        from django.contrib.auth import REDIRECT_FIELD_NAME
        from django.urls import reverse

        contexto = super().get_context_data(**kwargs)
        contexto.update(admin.site.each_context(self.request))
        contexto["title"] = "Log in"
        contexto["subtitle"] = None
        contexto["app_path"] = self.request.get_full_path()
        contexto["username"] = self.request.user.get_username()
        if (
            REDIRECT_FIELD_NAME not in self.request.GET
            and REDIRECT_FIELD_NAME not in self.request.POST
        ):
            contexto[REDIRECT_FIELD_NAME] = reverse("admin:index")
        return contexto

    def get(self, request, *args, **kwargs):
        from django.contrib import admin
        from django.shortcuts import redirect

        # Já é staff e logado: o admin manda direto para o índice em vez de
        # mostrar um formulário de entrada para quem já entrou.
        if admin.site.has_permission(request):
            return redirect("admin:index")
        return super().get(request, *args, **kwargs)
