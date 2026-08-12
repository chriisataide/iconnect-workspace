from django.apps import AppConfig


class WorkspaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "workspace"
    verbose_name = "iConnect Workspace"

    def ready(self) -> None:
        # A semente nunca sobrescreve um app que já se registrou, então a
        # ordem do INSTALLED_APPS não importa: quem chegar primeiro vence, e
        # o app real sempre vence a semente.
        from .launcher import semear

        semear()

        # Liga orçamento ao motor de aprovação. APR não conhece Compromisso e
        # orçamento não conhece cadeia de aprovação — o sinal é a costura.
        from .services.orcamento import conectar as conectar_orcamento

        conectar_orcamento()

        # O catálogo também ouve a decisão, para refletir no pedido de serviço.
        from .services.catalogo import conectar as conectar_catalogo

        conectar_catalogo()

        # Notificação também ouve, e não é chamada: sem o sinal, o motor de
        # aprovação passaria a ter opinião sobre como avisar as pessoas.
        from .services.notificacoes import conectar as conectar_notificacoes

        conectar_notificacoes()

        # O índice de busca também ouve. Por sinal e não por rotina noturna:
        # índice que atualiza de madrugada faz o autor publicar um POP e não
        # achá-lo — e quem não acha publica de novo.
        from .services.indice import conectar as conectar_indice

        conectar_indice()
