from django.apps import AppConfig


class CargasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cargas"
    verbose_name = "Cargas de fontes externas"

    def ready(self) -> None:
        # O contrato de frescor da Onda 1, finalmente respondido.
        #
        # Registrado AQUI e não em `resultados`: a pergunta é "quando a fonte
        # carregou pela última vez", e quem sabe isso é quem carrega. O espelho
        # não sabe sequer que existe uma execução de carga.
        from workspace.providers import frescor as contrato

        from .providers import FrescorDasCargas

        contrato.registrar(FrescorDasCargas())

        # Os quatro conectores. Todos, inclusive os sem credencial neste
        # ambiente — ver `conectores.semear` para a diferença entre "não existe
        # conector" e "falta configurar".
        from .conectores import semear

        semear()
