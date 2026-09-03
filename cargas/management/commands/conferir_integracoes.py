"""O que falta para cada fonte externa entrar no ar — sem imprimir segredo nenhum.

## Por que este comando existe

Configurar as três integrações é preencher onze variáveis de ambiente e dois
dicionários no settings. O jeito de descobrir se deu certo, até aqui, era rodar
uma carga e ler o motivo da falha — o que mistura "não configurei" com "a
credencial expirou" e com "o endpoint mudou".

Este comando separa as três coisas, e responde a única pergunta que importa
antes da primeira carga: **o que ainda falta, e de quem eu peço**.

## Ele NUNCA imprime credencial

Nem truncada, nem mascarada. Segredo mascarado em log é segredo em log com uma
falsa sensação de cuidado — quatro caracteres de um token bastam para confirmar
um palpite. O que sai daqui é `definida` ou `FALTA`, e nada mais.

É a mesma regra de `test_nenhum_transporte_registra_credencial`, aplicada à
saída de um comando que alguém vai colar num chamado.

## `--testar` faz UMA chamada por fonte

Sem a flag, o comando não toca a rede: ele lê configuração. Com ela, faz o
handshake mínimo de cada fonte — autenticar no Sankhya, uma consulta trivial no
monday, um GET numa rota do Platform — e diz se a credencial é aceita do lado de
lá.

Uma chamada e não uma carga: descobrir que o token está errado não deveria custar
uma varredura de doze meses.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from cargas.conectores import registro
from cargas.models import Fonte, FonteDados

#: O que cada fonte precisa, na ordem em que se preenche. `(rótulo, nome do
#: settings, onde se consegue)` — a terceira coluna é o que evita o chamado
#: "onde eu acho isso?".
EXIGIDAS: dict[str, tuple[tuple[str, str, str], ...]] = {
    Fonte.SANKHYA: (
        ("SANKHYA_BASE_URL", "SANKHYA_BASE_URL",
         "https://api.sankhya.com.br (produção) ou .sandbox. (homologação)"),
        ("SANKHYA_CLIENT_ID", "SANKHYA_CLIENT_ID",
         "Portal do Desenvolvedor da Sankhya, no componente da solução"),
        ("SANKHYA_CLIENT_SECRET", "SANKHYA_CLIENT_SECRET",
         "mesmo lugar do client_id — é outro segredo"),
        ("SANKHYA_TOKEN", "SANKHYA_TOKEN",
         "tela 'Configurações Gateway' do Sankhya Om 4.16+; NÃO é o client_secret"),
    ),
    Fonte.MONDAY: (
        ("MONDAY_TOKEN", "MONDAY_TOKEN",
         "monday → avatar → Developers → My Access Tokens, de um usuário de "
         "SERVIÇO somente leitura"),
        ("MONDAY_BOARDS", "MONDAY_BOARDS",
         "settings: dicionário de board e coluna. Levante com "
         "`python scripts/inventario_monday.py`"),
    ),
    Fonte.PLATFORM: (
        ("ICONNECT_API_URL", "ICONNECT_API_URL",
         "a raiz da API do iConnect Platform, com esquema e host"),
        ("WORKSPACE_SHARED_SECRET", "WORKSPACE_SHARED_SECRET",
         "gerado com `python -c \"import secrets;print(secrets.token_urlsafe(48))\"` "
         "e colado nos DOIS lados"),
    ),
}


class Command(BaseCommand):
    help = "Diz o que falta para cada fonte externa entrar no ar."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--testar",
            action="store_true",
            help="Faz UMA chamada por fonte configurada, para saber se a "
                 "credencial é aceita do lado de lá. Sem isto, o comando não "
                 "toca a rede.",
        )
        parser.add_argument(
            "chave", nargs="?", default="",
            help="Conferir só uma fonte. Sem isto, confere as três.",
        )

    def handle(self, *args, **opcoes) -> None:
        alvo = opcoes["chave"]
        chaves = [c for c in EXIGIDAS if not alvo or c == alvo]
        if not chaves:
            self.stdout.write(
                self.style.ERROR(
                    f"Fonte desconhecida: {alvo!r}. "
                    f"Conhecidas: {', '.join(EXIGIDAS)}."
                )
            )
            return

        prontas = 0
        for chave in chaves:
            if self._conferir(chave, testar=opcoes["testar"]):
                prontas += 1

        self.stdout.write("")
        if prontas == len(chaves):
            self.stdout.write(
                self.style.SUCCESS(
                    f"{prontas} de {len(chaves)} fonte(s) configurada(s). "
                    "Próximo passo: `carregar_fonte <chave> --aplicar`."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"{prontas} de {len(chaves)} fonte(s) configurada(s). "
                    "As demais respondem 'não configurada' — que é estado "
                    "NORMAL, e não falha: as telas dizem isso em português."
                )
            )

    # ── Uma fonte ────────────────────────────────────────────────────

    def _conferir(self, chave: str, testar: bool) -> bool:
        registro_no_banco = FonteDados.objects.filter(chave=chave).first()
        conector = registro.conector_de(chave)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"── {chave} ──"))

        if registro_no_banco is None:
            # Sem registro de fonte o carregador RECUSA começar, de propósito:
            # carga sem procedência é dado sem procedência.
            self.stdout.write(self.style.ERROR(
                "  ✗ sem registro em FonteDados — rode `semear_fontes --aplicar`"
            ))
            return False
        if not registro_no_banco.ativa:
            self.stdout.write(self.style.WARNING(
                "  ~ fonte DESATIVADA à mão. Reative no /admin/ quando quiser "
                "voltar — a semeadora nunca reativa sozinha."
            ))

        faltando = []
        for rotulo, nome, onde in EXIGIDAS[chave]:
            valor = getattr(settings, nome, None)
            if valor:
                # `definida` e nunca o valor. Segredo mascarado em log é segredo
                # em log com uma falsa sensação de cuidado.
                self.stdout.write(f"  ✓ {rotulo}: definida")
            else:
                faltando.append((rotulo, onde))
                self.stdout.write(self.style.ERROR(f"  ✗ {rotulo}: FALTA"))

        for rotulo, onde in faltando:
            self.stdout.write(f"      {rotulo} → {onde}")

        if conector is None:
            self.stdout.write(self.style.ERROR(
                "  ✗ nenhum conector registrado para esta chave"
            ))
            return False

        if not conector.disponivel():
            self.stdout.write(self.style.WARNING(
                "  → o conector se declara INDISPONÍVEL. A carga registra "
                "'não configurada' e o carimbo diz 'sem registro de carga'."
            ))
            return False

        self.stdout.write(self.style.SUCCESS("  → o conector está disponível."))
        if testar:
            return self._testar(chave, conector)
        self.stdout.write(
            "      Rode com --testar para conferir se o lado de lá aceita."
        )
        return True

    def _testar(self, chave: str, conector) -> bool:
        """UMA chamada. Nunca uma carga.

        Descobrir que o token está errado não deveria custar uma varredura de
        doze meses — e a mensagem de erro de uma carga mistura credencial
        recusada com campo que mudou de nome.
        """
        from cargas.conectores.base import Janela

        self.stdout.write("      testando o lado de lá…")
        try:
            # `janela` mínima e o primeiro registro só: `coletar` é um gerador,
            # e parar no primeiro item evita puxar a fonte inteira para
            # descobrir que a credencial funciona.
            for _ in conector.coletar(Janela()):
                break
        except Exception as erro:  # noqa: BLE001 - o diagnóstico é a saída
            # `type(erro).__name__` e a mensagem, sem `repr`: alguns clientes
            # HTTP põem a URL — com token na query — no `repr` da exceção.
            self.stdout.write(self.style.ERROR(
                f"  ✗ o lado de lá recusou: {type(erro).__name__}: {erro}"
            ))
            return False

        self.stdout.write(self.style.SUCCESS("  ✓ o lado de lá respondeu."))
        return True
