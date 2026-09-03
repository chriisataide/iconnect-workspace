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

        # O endereçamento das telas. Antes de tudo o que fala com o banco, e de
        # propósito: código duplicado tem de derrubar a subida do processo, e
        # descobrir isso depois de conectar cinco sinais só torna o rastro mais
        # difícil de ler.
        from .enderecamento import semear as semear_enderecamento

        semear_enderecamento()

        # Os avaliadores das regras de exceção. Registro em memória, como o
        # endereçamento e os conectores: regra é CÓDIGO — se ela estivesse no
        # banco, daria para "ativar" pelo /admin/ uma regra que ninguém
        # escreveu, e o erro apareceria no cron, de madrugada.
        from .excecoes import semear as semear_excecoes

        semear_excecoes()

        # O catálogo de fatores das metas. Mesmo raciocínio: fator é CÓDIGO —
        # cada um é uma função que consulta o espelho. Um fator "cadastrado" sem
        # função atrás seria uma meta que nunca pode ser apurada, e a descoberta
        # aconteceria no dia da nota.
        from .services.fatores import semear as semear_fatores

        semear_fatores()

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

        # O nome da área que executa cada domínio sai do papel que declara
        # `<raiz>.atender`, e é memoizado — a fase de um pedido aprovado o
        # pergunta uma vez por linha de lista. Criar, renomear ou desativar um
        # papel invalida o memo na hora; sem isto a tela mostraria o nome antigo
        # até o próximo deploy.
        from django.db.models.signals import post_delete, post_save

        from identidade.models import Papel

        from .services.atendimento import esquecer_areas

        post_save.connect(esquecer_areas, sender=Papel, dispatch_uid="wks_areas")
        post_delete.connect(esquecer_areas, sender=Papel, dispatch_uid="wks_areas")
