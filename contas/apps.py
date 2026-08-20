from django.apps import AppConfig


class ContasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "contas"
    verbose_name = "Contas"

    def ready(self) -> None:
        # A trilha de segurança. Por sinal e não por chamada nas views: entrada
        # e saída acontecem em views do Django que não são nossas — o admin tem
        # a dele —, e depender de cada porta lembrar de registrar garante que
        # uma esqueça. Foi assim que o `/admin/login/` ficou sem freio.
        from .auditoria import conectar

        conectar()
