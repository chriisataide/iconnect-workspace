"""A massa fictícia do espelho — e ela entra pela porta de todo mundo.

## Por que passa pelo carregador

Porque se a semeadora precisar de um caminho especial para gravar, **o
carregador está errado**. Aqui ela escreve CSVs e roda `carregar()`, com upsert,
contagem, precedência e registro de execução — o mesmo percurso de uma carga de
madrugada. Um bug no carregador aparece ao semear, e não na primeira noite.

## Por que a mesma massa entra por três fontes

Financeiro, folha e ponto entram como **Sankhya**; projetos e marcos como
**monday**; contratos e avaliações como **Platform**. Sem isso, a tela de fontes
teria uma linha e o carimbo por bloco diria a mesma coisa nas sete faixas — e a
primeira vez que alguém veria três carimbos diferentes na mesma tela seria em
produção.

O leitor é o mesmo `ConectorCSV`, registrado sob três chaves. O que muda é de
onde o arquivo veio, que é o que uma fonte é.

## Determinismo

Semente fixa. Duas execuções produzem exatamente o mesmo banco — teste que
depende de número aleatório é teste que falha na sexta-feira.

## Os quinze defeitos plantados

Eles não são sujeira: cada um exercita uma regra da tela. Se alguém "corrigir" a
massa achando que é bug, `test_massa.py` cai e explica por quê.
"""

from __future__ import annotations

import csv
import random
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from cargas.carregador import carregar
from cargas.conectores import registro as reg
from cargas.conectores.csv import ConectorCSV
from cargas.models import Divergencia, ExecucaoCarga, FonteDados, Fonte, StatusCarga
from resultados.plano_de_contas import PLANO

SEMENTE = 42
MESES = 24

REGIONAIS = ("Sudeste", "Sul", "Nordeste", "Centro-Oeste")
CENTROS = tuple(f"{1000 + i * 7}" for i in range(12))
#: COMO o contrato foi vendido — ver `resultados.models.ServicoContrato`.
#: A lista antiga (`cftv`, `alarme`, `instalacao`) misturava equipamento com
#: contratação, e por isso o filtro por serviço não separava nada comparável.
SERVICOS = (
    "projeto", "monitoramento", "manutencao", "locacao", "projeto_turnkey",
)

#: Clientes claramente inventados. Nome de cliente real numa massa versionada é
#: vazamento com aparência de exemplo.
CLIENTES = (
    "Rede Aurora", "Grupo Meridiano", "Têxtil Bandeirante", "Cooperativa Vale Verde",
    "Hospital São Lucas Fictício", "Shopping Portal Norte", "Indústria Cambará",
    "Logística Pampa", "Colégio Novo Horizonte", "Frigorífico Serra Azul",
    "Supermercados Boa Praça", "Condomínio Alto da Colina", "Metalúrgica Itaimbé",
    "Rede Farmalux", "Parque Tecnológico Ipê", "Transportes Guaíba",
    "Clínica Vida Plena", "Distribuidora Caravela",
)

PROJETOS = (
    "Troca de CFTV", "Implantação de alarme", "Migração de monitoramento",
    "Ampliação de perímetro", "Retrofit de central", "Integração de portaria",
    "Modernização de CFTV", "Padronização de crachá", "Central redundante",
    "Cerca elétrica", "Controle de acesso", "Rede dedicada",
    "Manutenção preventiva", "Auditoria de imagens",
)

MARCOS = ("Levantamento", "Homologação com o cliente", "Entrega técnica", "Treinamento")

#: Sazonalidade real da segurança eletrônica: dezembro e janeiro fracos, março e
#: setembro com pico de instalação. Série sem sazonalidade vira reta e não testa
#: gráfico nenhum.
SAZONALIDADE = {
    1: 0.82, 2: 0.94, 3: 1.18, 4: 1.02, 5: 1.00, 6: 0.98,
    7: 1.01, 8: 1.04, 9: 1.16, 10: 1.05, 11: 1.00, 12: 0.80,
}

#: Cada fonte recebe as entidades que ela seria dona no mundo real.
POR_FONTE = {
    # `conta` é do SANKHYA, como a competência: o razão contábil vem do ERP, e
    # o agregado é derivado dele. Pô-lo noutra fonte faria a tela mostrar dois
    # carimbos de frescor para números que têm de fechar entre si.
    Fonte.SANKHYA: ("competencia", "conta", "quadro", "apontamento"),
    Fonte.MONDAY: ("projeto", "marco"),
    Fonte.PLATFORM: ("contrato", "avaliacao"),
}


class Command(BaseCommand):
    help = "Popula o espelho de resultados com massa fictícia, pelo carregador."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--aplicar", action="store_true")
        parser.add_argument("--seed", type=int, default=SEMENTE)
        parser.add_argument("--meses", type=int, default=MESES)
        parser.add_argument(
            "--limpar", action="store_true",
            help="Apaga o espelho antes. Use ao trocar a semente — sem isto, "
                 "duas massas convivem e os números somam.",
        )

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        acaso = random.Random(opcoes["seed"])
        meses = opcoes["meses"]

        if FonteDados.objects.count() < 3:
            self.stdout.write(
                self.style.ERROR(
                    "Rode `semear_fontes --aplicar` antes: sem fonte cadastrada o "
                    "carregador recusa começar, e é de propósito."
                )
            )
            return

        if not _plano_semeado():
            # AVISO e não erro: a massa é válida sem o bloco D, e quem só quer
            # ver as outras faixas não deve ser bloqueado por causa dele.
            self.stdout.write(
                self.style.WARNING(
                    "O plano de contas está vazio — o razão por conta NÃO será "
                    "gerado, e a tabela contábil dirá que falta lançamento. "
                    "Rode `semear_plano_de_contas --aplicar` e semeie de novo."
                )
            )

        if opcoes["limpar"] and aplicar:
            self._limpar()

        dados = _montar(acaso, meses)
        resumo = []

        with tempfile.TemporaryDirectory(prefix="massa-resultados-") as raiz:
            guardados = reg.todos()
            try:
                for fonte, entidades in POR_FONTE.items():
                    pasta = Path(raiz) / fonte
                    pasta.mkdir()
                    for entidade in entidades:
                        _escrever(pasta / f"{entidade}.csv", dados[entidade])
                    reg.registrar(ConectorCSV(pasta, chave=fonte), substituir=True)

                # A ordem importa: contrato antes de competência e de avaliação,
                # porque as duas apontam para ele pelo código. Um marco cujo
                # projeto ainda não chegou é rejeitado com motivo — e é o
                # comportamento certo, não um acidente a evitar.
                for fonte in (Fonte.PLATFORM, Fonte.SANKHYA, Fonte.MONDAY):
                    resultado = carregar(fonte, aplicar=aplicar)
                    resumo.append(resultado)
            finally:
                reg.limpar()
                for conector in guardados.values():
                    reg.registrar(conector, substituir=True)

        if aplicar:
            self._plantar_carga_falha()
            self._plantar_divergencia()

        for resultado in resumo:
            self.stdout.write(
                f"  {resultado.fonte:<20} lidos {resultado.lidos:>4}  "
                f"criados {resultado.criados:>4}  atualizados {resultado.atualizados:>4}  "
                f"ignorados {resultado.ignorados:>4}  rejeitados {resultado.rejeitados:>3}"
            )

        linha = (
            f"{len(dados['contrato'])} contratos · {len(dados['projeto'])} projetos · "
            f"{len(dados['competencia'])} competências · 15 defeitos plantados"
        )
        if aplicar:
            self.stdout.write(self.style.SUCCESS(linha))
        else:
            self.stdout.write(self.style.WARNING(f"SIMULAÇÃO — {linha}"))
            self.stdout.write("Rode de novo com --aplicar para gravar.")

    # ── Plantas que não passam por CSV ──────────────────────────────

    def _plantar_carga_falha(self) -> None:
        """DEFEITO 14 — o monday com carga falha há 30 h.

        Não passa por CSV porque não é dado: é o REGISTRO de uma carga que não
        deu certo. A faixa 5 precisa mostrar dado velho com a idade em destaque,
        e não sumir — e sem esta linha nenhum ambiente de teste veria isso.
        """
        fonte = FonteDados.objects.filter(chave=Fonte.MONDAY).first()
        if fonte is None:
            return

        # A carga BOA vai para 30 h atrás, e a falha para agora. É essa a ordem
        # que produz o cenário: dado velho na tela, com a idade em destaque e o
        # motivo ao lado.
        #
        # Na primeira versão eu deixei a boa no instante da semeadura e a falha
        # no passado — e o carimbo saía tranquilo, porque a última tentativa era
        # a bem-sucedida. O cenário do defeito 14 não estava sendo plantado.
        velho = timezone.now() - timedelta(hours=30)
        ExecucaoCarga.objects.filter(
            fonte=fonte, status=StatusCarga.SUCESSO
        ).update(iniciada_em=velho, terminada_em=velho)

        agora = timezone.now()
        ExecucaoCarga.objects.update_or_create(
            fonte=fonte,
            status=StatusCarga.FALHA,
            defaults={
                "iniciada_em": agora,
                "terminada_em": agora,
                "erro_resumo": "tempo esgotado ao coletar o board de projetos",
            },
        )

    def _plantar_divergencia(self) -> None:
        """DEFEITO 15 — Sankhya e monday discordam do valor do mesmo projeto."""
        from resultados.models import Projeto

        projeto = Projeto.objects.order_by("codigo").first()
        if projeto is None:
            return
        Divergencia.objects.update_or_create(
            entidade="projeto",
            chave_externa=projeto.codigo,
            campo="valor_estimado",
            defaults={
                "fonte_a": Fonte.SANKHYA,
                "valor_a": "184000.00",
                "fonte_b": Fonte.MONDAY,
                "valor_b": "212500.00",
            },
        )

    def _limpar(self) -> None:
        from resultados.models import (
            Apontamento, AvaliacaoCliente, CompetenciaResultado, Contrato,
            MarcoProjeto, Projeto, QuadroPessoas,
        )

        for modelo in (
            AvaliacaoCliente, MarcoProjeto, CompetenciaResultado, Projeto,
            Apontamento, QuadroPessoas, Contrato,
        ):
            modelo.objects.all().delete()
        Divergencia.objects.all().delete()
        self.stdout.write(self.style.WARNING("  espelho apagado"))


def _escrever(caminho: Path, linhas: list[dict]) -> None:
    if not linhas:
        return
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


# ── A empresa fictícia ──────────────────────────────────────────────
#
# Coerente com a ADB: segurança eletrônica, quatro regionais, doze centros de
# custo. Porte distribuído para as TRÊS layers existirem — sem Layer 3 a regra
# de apresentação nunca é exercida, e sem contrato novo o "sem amostra" também
# não.

#: Valor mensal por layer, em reais. A ROB de 6 meses é o que decide a faixa:
#: até 300k é Layer 1, até 600k é Layer 2, acima disso é Layer 3.
PORTE = (
    *[("3", Decimal("140000")) for _ in range(3)],
    *[("2", Decimal("72000")) for _ in range(5)],
    *[("1", Decimal("28000")) for _ in range(9)],
)


def _montar(acaso: random.Random, meses: int) -> dict[str, list[dict]]:
    hoje = timezone.localdate()
    competencias = _competencias(hoje, meses)

    contratos = _contratos(acaso, hoje)
    # As competências são montadas UMA vez e reusadas pelas contas. Recalcular
    # produziria dois conjuntos com o mesmo `random` consumido em ordens
    # diferentes — e o razão não fecharia com o agregado por uma razão que
    # ninguém acharia olhando o código do bloco D.
    resultados = _competencias_de_resultado(acaso, contratos, competencias)
    return {
        "contrato": contratos,
        "competencia": resultados,
        "projeto": _projetos(acaso, contratos, hoje),
        "marco": _marcos(acaso, hoje),
        "quadro": _quadros(acaso, competencias),
        "apontamento": _apontamentos(acaso, competencias),
        "avaliacao": _avaliacoes(contratos, hoje),
        "conta": _contas(acaso, contratos, resultados),
    }


def _contas(acaso, contratos, resultados) -> list[dict]:
    """O razão de todos os contratos, derivado das competências já montadas.

    Derivado e não gerado à parte: o agregado é a verdade, e o detalhe tem de
    somar exatamente ele. Gerar os dois de forma independente daria duas
    verdades sobre o mesmo mês.

    As linhas de RATEIO de centro de custo entram também, com o peso
    administrativo — e isso não é detalhe.

    Deixá-las de fora foi a primeira tentativa, com o argumento de "não inventar
    o rateio contábil". O argumento não se sustenta: a decomposição inteira já é
    inventada. E o custo era alto — a soma da tabela contábil não fechava com a
    margem de contribuição da faixa logo acima dela, porque os rateios entram
    numa e não na outra. Detalhe que não bate com o total destrói a confiança na
    tela inteira, e é a única coisa que o bloco D não pode errar.
    """
    # SEM PLANO, SEM RAZÃO. O aviso sai em `handle`, pelo `self.stdout` — aqui
    # não há de onde escrever, e um `print` não apareceria na captura de quem
    # chama o comando de dentro de um teste.
    #
    # Gerar as linhas assim mesmo produziria três mil lançamentos apontando para
    # contas que não existem, e a tela mostraria "3.000 lançamentos vieram com
    # códigos que não estão no plano" — um alarme sobre um problema que o
    # próprio seeder criou.
    if not _plano_semeado():
        return []

    por_codigo = {c["codigo"]: c for c in contratos}
    recentes = _meses_recentes(resultados, MESES_DE_RAZAO)
    linhas: list[dict] = []
    for resultado in resultados:
        if (int(resultado["ano"]), int(resultado["mes"])) not in recentes:
            continue
        contrato = por_codigo.get(resultado.get("contrato"))
        if contrato is None:
            linhas += _contas_do_rateio(resultado)
        else:
            linhas += _contas_do_mes(contrato, resultado, acaso)
    return linhas


def _plano_semeado() -> bool:
    """O plano de contas existe? É pré-requisito do razão, como as fontes são
    da massa inteira."""
    from resultados.models import ContaContabil

    return ContaContabil.objects.exists()


def _meses_recentes(resultados, quantos: int) -> set[tuple[int, int]]:
    """Os `quantos` meses mais recentes presentes nas competências.

    Derivado do que EXISTE, e não de `hoje`: se a massa mudar de janela, o razão
    acompanha sozinho — e nunca sobra um mês de razão sem competência para
    fechar com ele.
    """
    meses = {(int(r["ano"]), int(r["mes"])) for r in resultados}
    return set(sorted(meses, reverse=True)[:quantos])


#: Quantos meses de RAZÃO a massa gera, contando o corrente.
#:
#: Seis, e não os vinte e quatro das competências. A tabela contábil é do MÊS —
#: ela responde "onde foi o dinheiro deste mês", e nunca mostra dois meses
#: juntos. Vinte e quatro meses de razão numa massa de demonstração são dez mil
#: linhas que nenhuma tela lê.
#:
#: O preço, declarado: abrindo um mês anterior ao sexto, o bloco D diz "sem
#: lançamento por conta contábil" enquanto a faixa do dinheiro mostra números.
#: É honesto — é exatamente o que uma sincronização parcial do Sankhya produz —
#: e é um estado que o roteiro de QA precisa exercitar de qualquer jeito.
#:
#: O efeito colateral é bem-vindo: a suíte tinha passado de 8min30 para 13min14
#: porque vinte testes semeiam a massa inteira, um por um.
MESES_DE_RAZAO = 6

#: O peso do rateio administrativo. Sem gente na ponta e sem equipamento: é a
#: estrutura que não pertence a cliente nenhum.
PESO_DO_RATEIO: tuple[tuple[str, float], ...] = (
    ("41601", 0.31), ("41602", 0.14), ("41701", 0.12),
    ("41603", 0.08), ("41403", 0.15), ("41801", 0.20),
)


def _contas_do_rateio(linha) -> list[dict]:
    """O razão de uma linha de centro de custo — a que não tem contrato.

    O valor decomposto é o `custo_indireto`, e não o `custo_direto`: por
    definição essa linha é indireta, e é assim que ela aparece na faixa do
    dinheiro.
    """
    centro = linha["centro_custo"]
    ano, mes = int(linha["ano"]), int(linha["mes"])
    custo = Decimal(linha["custo_indireto"] or "0")
    if not custo:
        return []

    linhas: list[dict] = []
    for grupo, valor in _partes(custo, PESO_DO_RATEIO):
        quantas = min(ANALITICAS_DO_GRUPO.get(grupo, 0), ANALITICAS_POR_GRUPO)
        if quantas:
            fatias = (0.55, 0.30, 0.15)[:quantas]
            soma = sum(fatias)
            pesos = tuple(
                (f"{grupo}{i + 1:03d}", p / soma) for i, p in enumerate(fatias)
            )
        else:
            pesos = ((grupo, 1.0),)
        for conta, parcela in _partes(valor, pesos):
            linhas.append({
                "chave_externa": f"snk-cc{centro}-{ano}{mes:02d}-{conta}",
                # SEM contrato — é o rateio, e ele precisa aparecer no nível do
                # centro de custo em vez de sumir do total.
                "contrato": "",
                "centro_custo": centro,
                "ano": str(ano),
                "mes": str(mes),
                "conta": conta,
                "codigo_origem": conta,
                "valor_realizado": str(parcela),
                "ajustes": "0",
                "valor_orcado": "",
            })
    return linhas


#: O PESO DE CADA GRUPO DE CONTA, por forma de contratação.
#:
#: É isto que torna o detalhamento útil. Sem a diferença, todo contrato tem a
#: mesma cara e abrir a tabela não ensina nada — a pessoa olha uma vez e não
#: volta.
#:
#: Os pesos somam 1 em cada serviço, e a decomposição usa o ÚLTIMO grupo como
#: resto: distribuir por arredondamento faria a soma das contas ficar alguns
#: centavos longe do custo direto, e o teste que confere se o detalhe fecha com
#: o agregado reprovaria por um erro que não é de negócio.
PESO_POR_SERVICO: dict[str, tuple[tuple[str, float], ...]] = {
    # Gente na ponta e link de dados — é o que um contrato de monitoramento é.
    "monitoramento": (
        ("41101", 0.46), ("41104", 0.14), ("41106", 0.09),
        ("41602", 0.11), ("41301", 0.06), ("41501", 0.05),
        ("41401", 0.09),
    ),
    # Deslocamento e peça. O técnico vai até lá, e leva material.
    "manutencao": (
        ("41301", 0.24), ("41504", 0.27), ("41101", 0.22),
        ("41104", 0.07), ("41505", 0.06), ("41501", 0.06),
        ("41401", 0.08),
    ),
    # O ativo é da empresa: deprecia e é alugado.
    "locacao": (
        ("41801", 0.38), ("41403", 0.21), ("41504", 0.14),
        ("41101", 0.12), ("41301", 0.05), ("41602", 0.04),
        ("41401", 0.06),
    ),
    "projeto": (
        ("41401", 0.28), ("41501", 0.19), ("41504", 0.18),
        ("41101", 0.20), ("41104", 0.06), ("41301", 0.05),
        ("41502", 0.04),
    ),
    # Turnkey: a empresa responde pelo resultado inteiro, e o equipamento é a
    # maior fatia — é por isso que o estouro dele dói tanto (defeito 16).
    "projeto_turnkey": (
        ("41504", 0.34), ("41401", 0.23), ("41101", 0.16),
        ("41501", 0.10), ("41301", 0.06), ("41104", 0.05),
        ("41403", 0.06),
    ),
}

#: Quantas contas analíticas de cada grupo recebem valor. Três: uma só faria a
#: expansão do grupo mostrar uma linha idêntica ao grupo, e o nível 2 pareceria
#: quebrado.
ANALITICAS_POR_GRUPO = 3

#: `grupo → quantas analíticas ele tem no plano`. Derivado do próprio plano, e
#: não escrito à mão: uma lista paralela divergiria dele na primeira conta nova,
#: e o sintoma seria despesa caindo em "Conta não cadastrada" sem motivo.
ANALITICAS_DO_GRUPO = {
    codigo: len(analiticas) for codigo, _, _, _, analiticas in PLANO
}

#: As contas de receita e de imposto. A receita não muda com o serviço — o que
#: muda é como ela foi vendida, e isso já está em `Contrato.servico`.
CONTAS_DE_RECEITA = (("31101", 1.0),)
CONTAS_DE_IMPOSTO = (("31201", 1.0),)


def _partes(total: Decimal, pesos) -> list[tuple[str, Decimal]]:
    """Divide `total` entre os grupos, com o último recebendo o RESTO.

    O resto e não o arredondamento de cada parte: somar sete valores arredondados
    dá alguns centavos a mais ou a menos que o total, e a tela mostraria um
    detalhamento que não fecha com o número logo acima dele.
    """
    partes = []
    acumulado = Decimal("0")
    for i, (grupo, peso) in enumerate(pesos):
        if i == len(pesos) - 1:
            valor = total - acumulado
        else:
            valor = (total * Decimal(str(peso))).quantize(Decimal("0.01"))
            acumulado += valor
        partes.append((grupo, valor))
    return partes


def _contas_do_mes(contrato, linha, acaso) -> list[dict]:
    """As linhas do razão de UM contrato num mês.

    Elas somam exatamente a receita, os impostos e o custo direto da
    `competencia` correspondente — há teste conferindo isso, e é a única coisa
    que o bloco D não pode errar.
    """
    codigo = contrato["codigo"]
    servico = contrato["servico"]
    ano, mes = int(linha["ano"]), int(linha["mes"])
    linhas: list[dict] = []

    def emitir(grupo: str, valor: Decimal, orcado: Decimal | None) -> None:
        """Espalha o valor entre as analíticas do grupo — as que EXISTEM.

        Alguns grupos não têm analítica no plano: `41801` DEPRECIAÇÕES e
        `41103` PARTICIPAÇÃO NOS RESULTADOS são lançados direto no sintético.
        Gerar `41801001` para eles produzia 431 linhas com `conta` nula — o
        caminho de "conta não cadastrada", que existe para o dia em que a fonte
        real mandar um código novo, e não para a massa se enganar sozinha.

        A quantidade sai de `ANALITICAS_DO_GRUPO`, derivada do próprio plano:
        uma lista escrita à mão aqui divergiria dele na primeira conta nova.
        """
        quantas = min(ANALITICAS_DO_GRUPO.get(grupo, 0), ANALITICAS_POR_GRUPO)
        if not quantas:
            pesos = ((grupo, 1.0),)
        else:
            fatias = (0.55, 0.30, 0.15)[:quantas]
            total_fatias = sum(fatias)
            pesos = tuple(
                (f"{grupo}{i + 1:03d}", p / total_fatias)
                for i, p in enumerate(fatias)
            )
        for conta, parcela in _partes(valor, pesos):
            linhas.append({
                "chave_externa": f"snk-{codigo}-{ano}{mes:02d}-{conta}",
                "contrato": codigo,
                "centro_custo": contrato["centro_custo"],
                "ano": str(ano),
                "mes": str(mes),
                "conta": conta,
                "codigo_origem": conta,
                "valor_realizado": str(parcela),
                "ajustes": "0",
                "valor_orcado": str(
                    (parcela * orcado).quantize(Decimal("0.01"))
                ) if orcado else "",
            })

    for grupo, valor in _partes(Decimal(linha["receita_bruta"]), CONTAS_DE_RECEITA):
        emitir(grupo, valor, Decimal("1.03"))
    for grupo, valor in _partes(Decimal(linha["impostos"]), CONTAS_DE_IMPOSTO):
        emitir(grupo, valor, Decimal("1.03"))

    custo = Decimal(linha["custo_direto"] or "0")
    if custo:
        pesos = PESO_POR_SERVICO.get(servico, PESO_POR_SERVICO["monitoramento"])
        for grupo, valor in _partes(custo, pesos):
            # DEFEITO 16 — o turnkey que estourou no equipamento. É o caso que
            # a tabela contábil existe para achar: o contrato fecha no total e
            # a conta 41504 sozinha explica o buraco.
            estourou = (
                codigo == "CT-101" and grupo == "41504"
            )
            # DEFEITO 17 — o contrato de manutenção com garantia e retrabalho
            # acima do normal. Ele PARECE rentável no agregado; só a linha
            # 41505 mostra que não é.
            retrabalho = codigo == "CT-107" and grupo == "41505"
            orcado = Decimal("0.72") if (estourou or retrabalho) else Decimal("1.02")
            emitir(grupo, valor, orcado)
    return linhas


def _fixo(texto: str) -> int:
    """Um número estável a partir de um texto.

    `hash()` NÃO serve: o Python salga o hash de string por processo, então
    `hash("1042")` muda a cada execução. Usá-lo aqui fazia a segunda passada da
    semeadora reescrever 276 linhas com valores diferentes — a massa deixava de
    ser determinística, e o defeito só aparecia em `atualizados`, um contador
    que o resumo nem imprimia.

    Soma dos códigos dos caracteres: bobo, estável entre processos e entre
    versões, que é tudo o que se pede dele.
    """
    return sum(ord(c) for c in texto)


def _competencias(hoje: date, quantas: int) -> list[tuple[int, int]]:
    meses = []
    ano, mes = hoje.year, hoje.month
    for passo in range(quantas):
        total = ano * 12 + (mes - 1) - passo
        meses.append((total // 12, total % 12 + 1))
    return list(reversed(meses))


def _contratos(acaso: random.Random, hoje: date) -> list[dict]:
    linhas = []
    for i, (layer, valor) in enumerate(PORTE):
        codigo = f"CT-{100 + i}"
        linhas.append(
            {
                "chave_externa": f"plt-{codigo}",
                "codigo": codigo,
                "nome_cliente": CLIENTES[i],
                "servico": SERVICOS[i % len(SERVICOS)],
                "centro_custo": CENTROS[i % len(CENTROS)],
                "regional": REGIONAIS[i % len(REGIONAIS)],
                "inicio_vigencia": (hoje - timedelta(days=730 - i * 11)).isoformat(),
                "fim_vigencia": (hoje + timedelta(days=200 + i * 9)).isoformat(),
                "valor_mensal": str(valor),
                "status": "ativo",
                "_layer": layer,
            }
        )

    # DEFEITO 3 — um Layer 3 vencendo em 45 dias. Prioridade máxima da faixa 4:
    # perder um Layer 3 sem visita custa mais que perder três Layer 1.
    linhas[0]["fim_vigencia"] = (hoje + timedelta(days=45)).isoformat()
    # DEFEITO 4 — um Layer 1 vencendo em 25 dias. Prioridade baixa, e a tela
    # precisa mostrar os dois sem dar a eles o mesmo peso.
    linhas[8]["fim_vigencia"] = (hoje + timedelta(days=25)).isoformat()

    # DEFEITO 11 — duas conquistas e uma perda no último trimestre.
    linhas[5]["inicio_vigencia"] = (hoje - timedelta(days=40)).isoformat()
    linhas[6]["inicio_vigencia"] = (hoje - timedelta(days=70)).isoformat()
    linhas[7]["status"] = "encerrado"
    linhas[7]["fim_vigencia"] = (hoje - timedelta(days=20)).isoformat()

    # O contrato NOVO: um mês de história, e por isso "sem amostra". Ele não
    # pode receber Layer 1 — Layer 1 quer dizer "pequeno, e por isso
    # dispensado"; sem amostra quer dizer "ainda não sei".
    novo = "CT-999"
    linhas.append(
        {
            "chave_externa": f"plt-{novo}",
            "codigo": novo,
            "nome_cliente": CLIENTES[-1],
            "servico": "monitoramento",
            "centro_custo": CENTROS[0],
            "regional": REGIONAIS[0],
            "inicio_vigencia": (hoje - timedelta(days=25)).isoformat(),
            "fim_vigencia": (hoje + timedelta(days=340)).isoformat(),
            "valor_mensal": "90000",
            "status": "ativo",
            "_layer": "sem_amostra",
        }
    )
    return linhas


def _competencias_de_resultado(acaso, contratos, competencias) -> list[dict]:
    linhas = []
    ultimo = competencias[-1]

    for contrato in contratos:
        codigo = contrato["codigo"]
        valor = Decimal(contrato["valor_mensal"])
        # O contrato novo só tem o mês corrente — é o que o faz cair em
        # "sem amostra" na regra da layer.
        janela = competencias[-1:] if contrato["_layer"] == "sem_amostra" else competencias

        for ano, mes in janela:
            fator = Decimal(str(SAZONALIDADE[mes])) * Decimal(
                str(round(acaso.uniform(0.95, 1.06), 3))
            )
            receita = (valor * fator).quantize(Decimal("0.01"))
            margem_alvo = _margem_alvo(codigo, acaso)
            mc = (receita * margem_alvo / 100).quantize(Decimal("0.01"))
            impostos = (receita * Decimal("0.155")).quantize(Decimal("0.01"))
            custo_direto = (receita - impostos - mc).quantize(Decimal("0.01"))

            linha = {
                "chave_externa": f"snk-{codigo}-{ano}{mes:02d}",
                "contrato": codigo,
                "centro_custo": contrato["centro_custo"],
                "ano": str(ano),
                "mes": str(mes),
                "receita_bruta": str(receita),
                "impostos": str(impostos),
                "custo_direto": str(custo_direto),
                "custo_indireto": "0",
                "margem_contribuicao": str(mc),
                "ebitda": str((mc * Decimal("0.62")).quantize(Decimal("0.01"))),
                "ajuste_potencial": "0",
                "receita_orcada": str((valor * Decimal("1.03")).quantize(Decimal("0.01"))),
                "custo_orcado": "",
                "margem_orcada": "",
            }

            # DEFEITO 10 — uma competência com receita lançada e custo AUSENTE.
            # A tela precisa mostrar "—" e nunca margem de 100%: custo zero e
            # custo desconhecido produzem o mesmo número e leituras opostas.
            if codigo == "CT-102" and (ano, mes) == ultimo:
                linha["custo_direto"] = ""
                linha["margem_contribuicao"] = ""

            # A coluna do meio, em alguns meses: o que já aconteceu e ainda não
            # bateu na contabilidade. Sem ela a reunião vira briga sobre o número.
            if mes in (3, 9):
                linha["ajuste_potencial"] = str(
                    (receita * Decimal("0.04")).quantize(Decimal("0.01"))
                )
            linhas.append(linha)

    linhas += _rateios(acaso, competencias)
    return linhas


#: DEFEITO 1 — três contratos com margem entre 4% e 9%, que é a faixa que
#: dispara a regra dos 10% sem ser deficitária.
#: DEFEITO 2 — um contrato com margem NEGATIVA, que vai para o bloco de
#: deficitários, no topo, sempre.
MARGENS_PLANTADAS = {
    "CT-100": Decimal("7.4"),
    "CT-103": Decimal("5.1"),
    "CT-109": Decimal("8.8"),
    "CT-112": Decimal("-3.2"),
}


def _margem_alvo(codigo: str, acaso: random.Random) -> Decimal:
    if codigo in MARGENS_PLANTADAS:
        return MARGENS_PLANTADAS[codigo]
    return Decimal(str(round(acaso.uniform(14.0, 26.0), 2)))


def _rateios(acaso, competencias) -> list[dict]:
    """As linhas de centro de custo sem contrato — o rateio administrativo.

    Elas existem para provar que o recorte por centro de custo as inclui: filtrar
    competência por `contrato__centro_custo` as deixaria de fora, e o total do CC
    passaria a ser menor que a soma dos seus contratos.
    """
    linhas = []
    for indice, centro in enumerate(CENTROS[:4]):
        for ano, mes in competencias[-6:]:
            custo = Decimal("48000") + Decimal(indice * 7000)
            linha = {
                "chave_externa": f"snk-cc{centro}-{ano}{mes:02d}",
                "contrato": "",
                "centro_custo": centro,
                "ano": str(ano),
                "mes": str(mes),
                "receita_bruta": "0",
                "impostos": "0",
                "custo_direto": "0",
                "custo_indireto": str(custo),
                "margem_contribuicao": str(-custo),
                "ebitda": str(-custo),
                "ajuste_potencial": "0",
                # DEFEITO 5 — um CC com 97% do orçamento comprometido.
                "receita_orcada": str((custo / Decimal("0.97")).quantize(Decimal("0.01"))),
                "custo_orcado": "",
                "margem_orcada": "",
            }
            # DEFEITO 6 — um CC SEM orçamento definido. A barra precisa dizer
            # isso, e a faixa 2 precisa marcar a linha como "sem orçado" em vez
            # de mostrar variação de 100%.
            if centro == CENTROS[3]:
                linha["receita_orcada"] = ""
            linhas.append(linha)
    return linhas


def _projetos(acaso, contratos, hoje: date) -> list[dict]:
    linhas = []
    for i, nome in enumerate(PROJETOS):
        contrato = contratos[i % len(contratos)]
        # Dois projetos INTERNOS, sem contrato: obra interna existe, e a tela
        # não pode inventar um cliente para ela.
        interno = i in (4, 11)
        linhas.append(
            {
                "chave_externa": f"mon-{2000 + i}",
                "codigo": f"PJ-{200 + i}",
                "nome": f"{nome} — {'' if interno else contrato['nome_cliente']}".strip(" —"),
                "cliente": "" if interno else contrato["nome_cliente"],
                "contrato": "" if interno else contrato["codigo"],
                "responsavel": f"Pessoa Exemplo {chr(65 + i % 8)}",
                "situacao": "concluido" if i in (1, 9) else "em_andamento",
                "inicio": (hoje - timedelta(days=120 + i * 5)).isoformat(),
                "prazo": (hoje + timedelta(days=30 + i * 6)).isoformat(),
                "percentual_concluido": str(min(95, 20 + i * 6)),
                "bloqueado": "",
                "motivo_bloqueio": "",
            }
        )

    # DEFEITO 13a — três projetos bloqueados, com o motivo à vista. Bloqueio sem
    # motivo é uma bandeira vermelha que ninguém sabe o que fazer com.
    for indice, motivo in (
        (2, "Aguardando liberação de acesso do cliente"),
        (6, "Equipamento em falta no fornecedor"),
        (10, "Projeto elétrico em revisão"),
    ):
        linhas[indice]["bloqueado"] = "sim"
        linhas[indice]["motivo_bloqueio"] = motivo
    return linhas


def _marcos(acaso, hoje: date) -> list[dict]:
    linhas = []
    for i in range(14):
        for j, titulo in enumerate(MARCOS[: 2 + i % 3]):
            linhas.append(
                {
                    "chave_externa": f"mon-mc-{i}-{j}",
                    "projeto": f"PJ-{200 + i}",
                    "titulo": titulo,
                    "prazo": (hoje + timedelta(days=10 + i * 4 + j * 12)).isoformat(),
                    "concluido_em": (
                        (hoje - timedelta(days=5)).isoformat() if j == 0 and i % 3 == 0 else ""
                    ),
                    "responsavel": f"Pessoa Exemplo {chr(65 + i % 8)}",
                }
            )

    # DEFEITO 13b — dois marcos VENCIDOS e sem replanejamento. É o que faz a
    # faixa 5 ter o que destacar além da contagem por situação.
    linhas[0]["prazo"] = (hoje - timedelta(days=12)).isoformat()
    linhas[0]["concluido_em"] = ""
    linhas[5]["prazo"] = (hoje - timedelta(days=4)).isoformat()
    linhas[5]["concluido_em"] = ""
    return linhas


def _quadros(acaso, competencias) -> list[dict]:
    linhas = []
    for centro in CENTROS:
        for ano, mes in competencias[-12:]:
            efetivo = 12 + (_fixo(centro) % 9)
            # DEFEITO 8 — turnover de 8,4% num centro de custo contra ~2,1% nos
            # outros. Um número alto sozinho não prova nada; ele só vira achado
            # quando há com o que comparar.
            turnover = "8.4" if centro == CENTROS[5] else str(
                round(acaso.uniform(1.6, 2.6), 1)
            )
            linhas.append(
                {
                    "chave_externa": f"snk-q-{centro}-{ano}{mes:02d}",
                    "centro_custo": centro,
                    "ano": str(ano),
                    "mes": str(mes),
                    "efetivo_ativo": str(efetivo),
                    "admissoes": str(acaso.randint(0, 2)),
                    "rescisoes": str(acaso.randint(0, 2)),
                    "turnover_pct": turnover,
                    "absenteismo_pct": str(round(acaso.uniform(1.0, 3.4), 1)),
                    "vagas_abertas": str(acaso.randint(0, 3)),
                    "vagas_fechadas_no_prazo": str(acaso.randint(0, 2)),
                    "em_ferias": str(acaso.randint(0, 2)),
                    "afastados": str(acaso.randint(0, 1)),
                }
            )
    return linhas


def _apontamentos(acaso, competencias) -> list[dict]:
    linhas = []
    for centro in CENTROS:
        for ano, mes in competencias[-12:]:
            normais = Decimal("2200") + Decimal(_fixo(centro) % 400)
            # DEFEITO 7 — pico de HE de ineficiência em maio (cobertura de
            # afastamento). Ineficiência é o número que muda comportamento:
            # serviço extra é receita, ineficiência é escala mal resolvida.
            pico = mes == 5
            ineficiencia = normais * (Decimal("0.11") if pico else Decimal("0.018"))
            extra = normais * Decimal("0.021")
            linha = {
                "chave_externa": f"snk-a-{centro}-{ano}{mes:02d}",
                "centro_custo": centro,
                "ano": str(ano),
                "mes": str(mes),
                "horas_normais": str(normais.quantize(Decimal("0.01"))),
                "he_total": str((ineficiencia + extra).quantize(Decimal("0.01"))),
                "he_ineficiencia": str(ineficiencia.quantize(Decimal("0.01"))),
                "he_servico_extra": str(extra.quantize(Decimal("0.01"))),
                "he_sem_classificacao": "0",
                "hora_escala": str(normais.quantize(Decimal("0.01"))),
                "hora_abono": str((normais * Decimal("0.006")).quantize(Decimal("0.01"))),
                "hora_desconto": str((normais * Decimal("0.004")).quantize(Decimal("0.01"))),
                "hora_noturna": str((normais * Decimal("0.22")).quantize(Decimal("0.01"))),
                "banco_horas_saldo": str(acaso.randint(-40, 90)),
                "folhas_ponto_pendentes": "0",
                "contratos_pendentes_assinatura": "0",
            }
            # DEFEITO 12 — 14 folhas de ponto pendentes e 3 contratos sem
            # assinatura, no mês corrente. As duas viram autuação, e por isso
            # saem da tabela de horas para um bloco próprio.
            if (ano, mes) == competencias[-1] and centro == CENTROS[0]:
                linha["folhas_ponto_pendentes"] = "14"
                linha["contratos_pendentes_assinatura"] = "3"
            linhas.append(linha)
    return linhas


def _avaliacoes(contratos, hoje: date) -> list[dict]:
    """As avaliações do cliente, ancoradas no MÊS e não no dia.

    ## O defeito que isto corrige — encontrado em 09/09/2026

    A chave de negócio da avaliação é `(contrato, data)`, e a `chave_externa`
    era fixa (`plt-av-0`). Com a data saindo de `hoje`, rodar o seeder num dia
    diferente do anterior produzia uma data que não casava com nenhuma linha
    existente: o carregador tentava CRIAR, e batia no
    `UNIQUE (fonte, chave_externa)`.

    O sintoma era uma carga `parcial` com "a fonte mandou o mesmo registro duas
    vezes" — e ele só aparecia para quem semeasse duas vezes em dias
    diferentes, que é o caso normal de quem trabalha no projeto por mais de um
    dia. Ficou escondido porque a suíte semeia uma vez, num dia só.

    ## A âncora é o primeiro dia do mês, e a chave carrega a competência

    Dentro do mesmo mês, semear de novo encontra a mesma linha e não escreve.
    Virado o mês, a data E a chave mudam juntas, e nasce uma avaliação nova —
    que é o certo: avaliação de cliente é histórico, e o mês seguinte tem as
    suas.
    """
    ancora = date(hoje.year, hoje.month, 1)
    competencia = f"{ancora:%Y%m}"
    linhas = []
    for i, contrato in enumerate(contratos[:12]):
        nota = 9 - (i % 4)
        classificacao = (
            "promotor" if nota >= 9 else "neutro" if nota >= 7 else "detrator"
        )
        linhas.append(
            {
                # A COMPETÊNCIA entra na chave: sem ela, a avaliação do mês
                # seguinte colidiria com a deste na constraint de origem.
                "chave_externa": f"plt-av-{competencia}-{i}",
                "contrato": contrato["codigo"],
                "data": (ancora + timedelta(days=i * 2)).isoformat(),
                "nota": str(nota),
                "classificacao": classificacao,
                "comentario": "Atendimento dentro do combinado." if nota >= 7 else "",
                "tratativa_aberta": "",
                "tratativa_prazo": "",
                "tratativa_status": "",
            }
        )

    # DEFEITO 9 — dois detratores: um COM tratativa no prazo, um SEM.
    # Detrator com tratativa é trabalho em andamento; sem tratativa é uma pessoa
    # esperando. Só o segundo vira destaque, e a massa precisa dos dois para a
    # diferença ser testável.
    # Exatamente DOIS detratores. Um terceiro não acrescentaria regra nenhuma e
    # tornaria o teste da massa uma contagem em vez de uma afirmação: o que
    # importa é o par — um tratado, um não —, porque é a diferença entre eles
    # que a faixa 7 precisa saber destacar.
    detratores = [linha for linha in linhas if linha["classificacao"] == "detrator"]
    for excedente in detratores[2:]:
        excedente["classificacao"] = "neutro"
        excedente["nota"] = "7"
    detratores = detratores[:2]

    if detratores:
        detratores[0].update(
            comentario="Chamado demorou três dias para ser atendido.",
            tratativa_aberta="sim",
            # Também ancorado: um prazo derivado de `hoje` mudaria o hash do
            # registro todo dia, e a carga nunca diria "ignorado".
            tratativa_prazo=(ancora + timedelta(days=40)).isoformat(),
            tratativa_status="em andamento no prazo",
        )
    if len(detratores) > 1:
        detratores[1].update(
            comentario="Ninguém retornou o contato da semana passada.",
            tratativa_aberta="",
        )
    return linhas
