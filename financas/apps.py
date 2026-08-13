from django.apps import AppConfig


class FinancasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "financas"
    verbose_name = "Finanças"

    def ready(self) -> None:
        # Registro no ready() e não no import do módulo: é o mesmo ponto em que o
        # `dashboard` se registrava, e mantém o Workspace ignorante de quem
        # responde. Trocar este app por outro provider não toca o Workspace.
        from workspace.providers.orcamento import registrar

        from .providers import OrcamentoLocal

        registrar(OrcamentoLocal())
