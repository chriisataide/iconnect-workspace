from django.apps import AppConfig


class ResultadosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "resultados"
    verbose_name = "Espelho de resultados"

    def ready(self) -> None:
        # Registro no `ready()` e não no import do módulo, como `financas` faz:
        # é o que mantém o Workspace ignorante de quem responde. Trocar este app
        # por outro provedor não toca uma linha da superfície.
        #
        # O contrato de FRESCOR não é registrado aqui, e sim em `cargas`. Ele
        # responde "quando a fonte carregou pela última vez", e isso é assunto
        # de quem carrega — o espelho não sabe nem que existe uma execução.
        from workspace.providers import resultados as contrato

        from .providers import EspelhoLocal

        contrato.registrar(EspelhoLocal())
