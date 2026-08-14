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

# Uma janela só para as duas contagens: duas janelas diferentes só somariam
# parâmetro para ajustar sem mudar o que o freio faz.
JANELA_SEGUNDOS = 15 * 60

LIMITE_POR_CONTA = 5
LIMITE_POR_ORIGEM = 20

PREFIXO = "entrada:freio"


def _config(nome: str, padrao: int) -> int:
    """Permite ajustar por `settings` sem editar código — e permite ao teste
    usar limites pequenos sem simular 20 requisições."""
    return int(getattr(settings, nome, padrao))


def ip_de(request) -> str:
    """O IP de quem pede.

    `REMOTE_ADDR` e não `X-Forwarded-For` cru: o cabeçalho é escrito pelo
    cliente e um atacante o troca a cada tentativa, o que zeraria a contagem por
    origem — exatamente a proteção que ela existe para dar. Atrás de proxy, quem
    tem de normalizar isso é a infraestrutura (`SECURE_PROXY_SSL_HEADER` já segue
    esse mesmo princípio), e não este arquivo.
    """
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


class LoginComFreio(LoginView):
    """`LoginView` com contagem de tentativas.

    Herda em vez de reescrever: autenticação, `next`, redirecionamento e
    proteção de CSRF são do Django, e um login escrito à mão é onde se esquece
    de um deles.
    """

    template_name = "contas/entrar.html"

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
                contexto = self.get_context_data(form=form, bloqueado=True)
                return self.render_to_response(contexto, status=429)
        return super().dispatch(request, *args, **kwargs)
