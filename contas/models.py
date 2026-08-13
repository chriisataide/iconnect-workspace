"""A conta de quem trabalha aqui.

## Por que um modelo próprio, e não `auth.User`

Duas razões, e a segunda é a que importa.

**A conta nasce do SSO (ADR-013).** O identificador natural de uma pessoa da
empresa é o e-mail corporativo, não um `username` que alguém digita. O Entra ID
entrega `oid` (identificador imutável no tenant) e `upn` (o user principal name),
e é por `oid` que se reconhece a pessoa mesmo quando ela troca de sobrenome e o
e-mail muda. `auth.User` não tem onde guardar isso sem um model lateral.

**Pessoa daqui não é pessoa do iConnect Platform.** No projeto anterior os dois
produtos dividiam uma `auth.User`, e a consequência era medível: 881 registros de
lotação criados para técnicos do iConnect — todos com unidade, departamento,
centro de custo e gestor vazios. Não porque alguém errou, mas porque era a mesma
tabela e nada impedia. E na direção inversa era pior: uma conta criada aqui valia
como sessão lá, onde "usuário sem papel definido" era tratado como analista, com
acesso a ticket e cliente.

Tabela própria em banco próprio resolve os dois por construção. Ninguém precisa
lembrar da fronteira.

## O que este modelo deliberadamente NÃO faz

Não tem `username`. Não tem papel nem permissão de negócio — quem responde
"pode?" é `identidade.services.autorizacao.pode()`, com escopo e vigência, e
misturar as duas coisas foi o que produziu a herança acima. E não recebe
`is_staff` nem `is_superuser` de claim de SSO nenhum: o admin do Django mora
nesta mesma tabela, e derivar privilégio administrativo de um atributo do
diretório é como um grupo mal configurado no M365 vira acesso ao admin.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class PessoaManager(BaseUserManager):
    """Criação de conta com e-mail como identificador."""

    use_in_migrations = True

    def _criar(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("A conta exige e-mail — é o identificador.")
        email = self.normalize_email(email).strip().lower()
        pessoa = self.model(email=email, **extra)
        # `set_unusable_password()` quando não vem senha: é o caso normal com
        # SSO, e é diferente de senha vazia — impede login local por acidente.
        if password:
            pessoa.set_password(password)
        else:
            pessoa.set_unusable_password()
        pessoa.save(using=self._db)
        return pessoa

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._criar(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._criar(email, password, **extra)


class Pessoa(AbstractBaseUser, PermissionsMixin):
    """Quem trabalha na empresa e usa o Workspace."""

    email = models.EmailField(
        "e-mail corporativo",
        unique=True,
        help_text="Identificador da conta. Vem do SSO quando ele estiver ligado.",
    )

    nome = models.CharField("nome completo", max_length=160, blank=True)

    # ── Vínculo com o diretório corporativo ─────────────────────────
    #
    # `oid` e não e-mail como chave de reconciliação: o e-mail muda quando a
    # pessoa casa, o `oid` não muda nunca dentro do tenant. Reconciliar por
    # e-mail cria conta duplicada no dia em que alguém troca de sobrenome.
    entra_oid = models.CharField(
        "object id no Entra ID",
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Identificador imutável da pessoa no tenant M365.",
    )
    upn = models.CharField(
        "user principal name",
        max_length=254,
        blank=True,
        default="",
        help_text="Como o M365 chama a pessoa. Pode divergir do e-mail.",
    )

    is_active = models.BooleanField(
        "ativa",
        default=True,
        help_text=(
            "Desmarque em vez de apagar: apagar a conta levaria embora, em "
            "cascata, a trilha de quem aprovou o quê."
        ),
    )
    is_staff = models.BooleanField(
        "acessa o admin",
        default=False,
        help_text="Nunca derivado do SSO — concessão explícita, sempre.",
    )

    criado_em = models.DateTimeField(default=timezone.now, editable=False)

    objects = PessoaManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    # Vazio de propósito: `createsuperuser` pergunta e-mail e senha, e mais nada.
    # Nome vem do diretório; exigir digitação aqui produz "Admin Admin".
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "pessoa"
        verbose_name_plural = "pessoas"
        ordering = ["nome", "email"]

    def __str__(self) -> str:
        # `_identificacao()` e não `self.email`: esta string vai para o admin
        # ("Esperando: ana@icodev.com.br" é ruído) e para o `__str__` de
        # `AtribuicaoPapel` e `Delegacao`. Uma identificação, um formato.
        return self._identificacao()

    # ── A interface que o Workspace consome ─────────────────────────
    #
    # `AbstractBaseUser` não traz estes dois; `AbstractUser` traz. O Workspace
    # chama os dois em seis lugares (home, Meu dia, correspondência, reservas,
    # casca), então eles são contrato e não conveniência.

    def _identificacao(self) -> str:
        """O nome, ou a parte local do e-mail quando ele não veio.

        A parte local, e **não** o e-mail inteiro: a home cumprimenta com isto, e
        "Olá, semnome@icodev.com.br." é pior que não cumprimentar. Conta criada
        pelo SSO sempre traz `displayName`; a que cai aqui é conta de serviço ou
        importação incompleta, e mesmo essa merece uma saudação legível.
        """
        return self.nome or self.email.split("@")[0]

    def get_full_name(self) -> str:
        return self._identificacao()

    def get_short_name(self) -> str:
        """Só o primeiro nome — "Olá, Christopher", não "Olá, Christopher Ataide"."""
        return self._identificacao().split()[0]
