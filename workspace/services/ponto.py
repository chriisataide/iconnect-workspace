"""As pendências de ponto — ler a planilha, agrupar por pessoa, montar a mensagem.

Este módulo é a ÚNICA fonte das regras. O workflow do n8n em
`workspace/rh/integrations/ponto_whatsapp/` tinha as mesmas regras escritas em
JavaScript e lia o Excel por conta própria; agora ele recebe do Portal os dados
já prontos e só entrega ao WhatsApp. Ver §22 de `docs/rh-pendencias-ponto.md`
para por que o estado passou a morar aqui e não lá.

## O zero do DDD

`normalizar_telefone` remove o zero de tronco antes de validar, e essa linha é
a diferença entre a automação funcionar e não funcionar. A planilha real do
PontoTel escreve `(019) 98888-7777`; o normalizador original virava
`019988887777` e reprovava no `^55...`. Medido na planilha de setembro/2026:
**57 de 57 colaboradores reprovavam**. Ninguém percebeu porque em modo de teste
o destino é substituído pelo telefone de teste antes de qualquer envio — a
coluna nunca chegou a ser usada.

## O que este módulo NÃO faz

Não fala com o n8n, não grava no banco e não sabe o que é `request`. Recebe
bytes, devolve dados. É o que torna possível testá-lo sem subir Docker.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

# ── O contrato da planilha ──────────────────────────────────────────

#: As colunas que precisam existir. `Telefone` NÃO entra: uma planilha sem
#: telefone ainda é processável — ela rende pendências revisáveis e envio em
#: modo de teste. Barrar a importação inteira por causa dela trocaria um aviso
#: por uma porta fechada.
COLUNAS_OBRIGATORIAS = ("Data", "Funcionário", "Entrada", "Pausa", "Retorno", "Saída")

#: Lidas quando existem.
COLUNAS_OPCIONAIS = ("Código", "Local de Trabalho", "Jornada", "Observação", "Telefone")

#: NUNCA são lidas, mesmo presentes. A planilha do PontoTel traz `CPF` e
#: `Senha` (a senha do totem, que é o começo do CPF). Nada neste fluxo precisa
#: de qualquer um dos dois: a mensagem identifica a pessoa pelo nome e o envio
#: usa o telefone. Guardar dado sensível que a funcionalidade não usa é criar
#: um vazamento à espera de acontecer, então o parser descarta na entrada.
COLUNAS_IGNORADAS = ("CPF", "Senha")

#: Teto de linhas. 94 é o tamanho de uma competência real; 5.000 é folga de
#: duas ordens de grandeza e ainda assim barra o arquivo que faria o parser
#: segurar o processo.
MAXIMO_LINHAS = 5_000

#: As marcações, na ordem em que aparecem no dia. A ordem importa: ela é a
#: ordem em que os motivos entram na frase.
MARCACOES = (("Entrada", "entrada"), ("Pausa", "pausa"), ("Retorno", "retorno"), ("Saída", "saída"))

MOTIVO_GENERICO = "pendência na apuração do ponto"

MENSAGEM_MODELO = (
    "Prezado(a) colaborador(a),\n\n"
    "Identificamos pendências na apuração do seu ponto nos dias listados abaixo:\n\n"
    "{pendencias}\n\n"
    "Solicitamos que realize a regularização o quanto antes.\n\n"
    "Lembramos que o registro no aplicativo PontoTel deve ser feito em tempo real, "
    "no momento exato da ação, como no início da jornada, nos intervalos e no término "
    "do expediente. A reincidência nessas ausências de marcação poderá acarretar "
    "medidas disciplinares.\n\n"
    "Estamos à disposição.\n\n"
    "Recursos Humanos"
)


class PlanilhaInvalida(Exception):
    """A planilha não pode ser lida. A mensagem vai para a tela, então é em português."""

    def __init__(self, mensagem: str, colunas_ausentes: tuple[str, ...] = ()):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.colunas_ausentes = colunas_ausentes


# ── Telefone ────────────────────────────────────────────────────────

#: Celular brasileiro com DDI: 55 + DDD (11-99) + 9 + 8 dígitos. O `9` inicial
#: do celular é exigido porque o destino é WhatsApp — fixo não recebe.
_CELULAR_BR = re.compile(r"^55[1-9][0-9]9[0-9]{8}$")


def normalizar_telefone(valor) -> str:
    """`(019) 98888-7777` → `5519988887777`. String vazia quando não serve.

    Rejeita fórmula (`=VLOOKUP(...)`) antes de qualquer coisa: a planilha busca
    o telefone em outro arquivo, e quando o vínculo quebra a célula entrega o
    texto da fórmula. Isso não é um telefone ruim, é a ausência de um — e
    mandar mensagem para os dígitos de dentro de uma fórmula é como se erra
    feio uma vez só.
    """
    bruto = "" if valor is None else str(valor).strip()
    if not bruto or bruto.startswith("="):
        return ""

    digitos = re.sub(r"\D", "", bruto)

    # O zero de tronco. `(019)` é como o Brasil escreve DDD desde sempre e é o
    # que o PontoTel exporta. Sem esta linha o número vira `019...`, nunca casa
    # com `^55` e o colaborador é reprovado por causa da grafia.
    if digitos.startswith("0"):
        digitos = digitos.lstrip("0")

    # Sem DDI: 10 dígitos (fixo) ou 11 (celular). Só o celular segue adiante,
    # mas o 55 entra antes para que a validação tenha um formato só a conferir.
    if len(digitos) in (10, 11):
        digitos = "55" + digitos

    return digitos if _CELULAR_BR.match(digitos) else ""


def motivo_sem_telefone(bruto: str, normalizado: str) -> str:
    """Por que não dá para enviar — a frase que a tela mostra na coluna.

    Função de módulo e não método: a mesma frase é usada pelo dataclass do
    motor e pelo model do banco, e a regra do §35 (fórmula ≠ número errado) não
    pode ter duas versões que discordem.
    """
    if normalizado:
        return ""
    bruto = (bruto or "").strip()
    if not bruto:
        return "Telefone não disponível"
    if bruto.startswith("="):
        # §35: a planilha busca o telefone em outro arquivo e o vínculo
        # quebrou. Dizer "inválido" mandaria o R.H. procurar erro de digitação
        # num campo que nunca teve número nenhum.
        return "Telefone não disponível"
    return "Telefone inválido"


def mascarar_telefone(numero: str) -> str:
    """`5519988887777` → `(19) 9****-1608`. Para tela e log, nunca para envio."""
    if not numero:
        return ""
    if len(numero) >= 12 and numero.startswith("55"):
        ddd, resto = numero[2:4], numero[4:]
        return f"({ddd}) {resto[0]}****-{resto[-4:]}"
    return numero[:2] + "****" + numero[-4:] if len(numero) > 6 else "****"


# ── Data ────────────────────────────────────────────────────────────


def _formatar_data(valor) -> tuple[str, int]:
    """Devolve (texto exibido, chave de ordenação). Nunca levanta.

    A chave de ordenação é `AAAAMMDD` como inteiro; data ilegível vai para o
    fim em vez de derrubar a importação, porque uma célula estranha no meio de
    94 linhas não pode custar as outras 93.
    """
    if isinstance(valor, datetime):
        valor = valor.date()
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y"), valor.year * 10000 + valor.month * 100 + valor.day

    bruto = "" if valor is None else str(valor).strip()

    if br := re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", bruto):
        dia, mes, ano = br.group(1).zfill(2), br.group(2).zfill(2), br.group(3)
        return f"{dia}/{mes}/{ano}", int(ano + mes + dia)

    if iso := re.match(r"^(\d{4})-(\d{2})-(\d{2})", bruto):
        ano, mes, dia = iso.groups()
        return f"{dia}/{mes}/{ano}", int(ano + mes + dia)

    return bruto or "data não informada", 99999999


# ── O motivo da pendência ───────────────────────────────────────────


def _juntar(partes: list[str]) -> str:
    """`['entrada','pausa','retorno']` → `'entrada, pausa e retorno'`."""
    if len(partes) == 1:
        return partes[0]
    return ", ".join(partes[:-1]) + " e " + partes[-1]


def motivo_da_linha(linha: dict) -> str:
    """O que está faltando naquele dia, em português.

    Marcação vazia é o caso que importa e vem primeiro. Quando as quatro estão
    preenchidas e ainda assim o PontoTel apontou algo, a `Observação` é a única
    fonte do que houve — e ela vem do sistema de ponto, não do usuário.
    """
    faltando = [rotulo for coluna, rotulo in MARCACOES if not str(linha.get(coluna) or "").strip()]
    if faltando:
        return "ausência de marcação de " + _juntar(faltando)

    observacao = re.sub(r"\s+", " ", str(linha.get("Observação") or "").strip())
    return re.sub(r"\s*\.\s*$", "", observacao) or MOTIVO_GENERICO


# ── Leitura da planilha ─────────────────────────────────────────────


def _normalizar_cabecalho(valor) -> str:
    return re.sub(r"\s+", " ", str(valor or "").strip())


def ler_planilha(conteudo: bytes, nome: str = "") -> list[dict]:
    """Bytes de XLSX/XLS/CSV → lista de dicionários por nome de coluna.

    As colunas são reconhecidas pelo NOME e não pela posição, porque o export
    do PontoTel muda a ordem entre competências e traz uma coluna sem título
    entre `Observação` e `Telefone`.
    """
    if not conteudo:
        raise PlanilhaInvalida("O arquivo está vazio.")

    if nome.lower().endswith(".csv"):
        linhas_brutas = _ler_csv(conteudo)
    else:
        linhas_brutas = _ler_excel(conteudo)

    if not linhas_brutas:
        raise PlanilhaInvalida("A planilha não tem nenhuma linha.")

    cabecalho = [_normalizar_cabecalho(c) for c in linhas_brutas[0]]
    presentes = {c for c in cabecalho if c}

    ausentes = tuple(c for c in COLUNAS_OBRIGATORIAS if c not in presentes)
    if ausentes:
        raise PlanilhaInvalida(
            "Não foi possível processar a planilha.", colunas_ausentes=ausentes
        )

    corpo = linhas_brutas[1:]
    if len(corpo) > MAXIMO_LINHAS:
        raise PlanilhaInvalida(
            f"A planilha tem {len(corpo)} linhas. O máximo é {MAXIMO_LINHAS:,}.".replace(",", ".")
        )

    uteis = set(COLUNAS_OBRIGATORIAS) | set(COLUNAS_OPCIONAIS)
    linhas = []
    for bruta in corpo:
        # A coluna sem título e as ignoradas (CPF, Senha) somem aqui — nunca
        # chegam a existir como dado do Portal.
        linha = {
            coluna: bruta[i] if i < len(bruta) else None
            for i, coluna in enumerate(cabecalho)
            if coluna in uteis
        }
        if any(str(v or "").strip() for v in linha.values()):
            linhas.append(linha)
    return linhas


def _ler_excel(conteudo: bytes) -> list[tuple]:
    try:
        import openpyxl

        livro = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as erro:
        raise PlanilhaInvalida(
            "Não foi possível abrir o arquivo. Ele parece corrompido ou não é uma planilha."
        ) from erro

    try:
        aba = livro.active
        if aba is None:
            raise PlanilhaInvalida("A planilha não tem nenhuma aba.")
        return [tuple(linha) for linha in aba.iter_rows(values_only=True)]
    finally:
        livro.close()


def _ler_csv(conteudo: bytes) -> list[tuple]:
    import csv

    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            texto = conteudo.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise PlanilhaInvalida("Não foi possível ler o texto do arquivo.")

    amostra = texto[:4096]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
    except csv.Error:
        dialeto = csv.excel
        dialeto.delimiter = ";" if amostra.count(";") > amostra.count(",") else ","

    return [tuple(linha) for linha in csv.reader(io.StringIO(texto), dialeto)]


# ── Agrupamento ─────────────────────────────────────────────────────


@dataclass
class Pendencia:
    data: str
    motivo: str
    ordem: int = 0


@dataclass
class Colaborador:
    """Uma pessoa e tudo que ela deve — uma pessoa, uma mensagem."""

    nome: str
    telefone_planilha: str = ""
    telefone_normalizado: str = ""
    codigo: str = ""
    local: str = ""
    pendencias: list[Pendencia] = field(default_factory=list)

    @property
    def tem_telefone(self) -> bool:
        return bool(self.telefone_normalizado)

    @property
    def telefone_mascarado(self) -> str:
        return mascarar_telefone(self.telefone_normalizado)

    @property
    def motivo_sem_telefone(self) -> str:
        return motivo_sem_telefone(self.telefone_planilha, self.telefone_normalizado)

    def texto_das_pendencias(self) -> str:
        return "\n".join(f"• {p.data} — {p.motivo}" for p in self.pendencias)

    def mensagem(self) -> str:
        return MENSAGEM_MODELO.format(pendencias=self.texto_das_pendencias())


def agrupar(linhas: list[dict]) -> list[Colaborador]:
    """Linhas do Excel → um `Colaborador` por pessoa, pendências em ordem de data.

    A chave é o nome em maiúsculas. §11 pede que isso seja trocável por
    matrícula ou CPF depois: é o que `_chave_do_colaborador` isola — uma função
    de uma linha, e não um `if` espalhado por três lugares.

    Pendências repetidas (mesmo dia, mesmo motivo) colapsam. O export do
    PontoTel duplica linha quando a competência é reprocessada, e o
    colaborador não deve receber o mesmo dia duas vezes na mesma mensagem.
    """
    grupos: dict[str, Colaborador] = {}
    vistas: dict[str, set[tuple[str, str]]] = {}

    for linha in linhas:
        nome = re.sub(r"\s+", " ", str(linha.get("Funcionário") or "").strip())
        if not nome:
            continue

        chave = _chave_do_colaborador(linha, nome)
        if chave not in grupos:
            grupos[chave] = Colaborador(
                nome=nome,
                codigo=str(linha.get("Código") or "").strip(),
                local=str(linha.get("Local de Trabalho") or "").strip(),
            )
            vistas[chave] = set()

        colaborador = grupos[chave]

        # O telefone pode vir só em algumas linhas da mesma pessoa: fica o
        # primeiro que prestar.
        bruto = str(linha.get("Telefone") or "").strip()
        if bruto and not colaborador.telefone_planilha:
            colaborador.telefone_planilha = bruto
        if not colaborador.telefone_normalizado:
            colaborador.telefone_normalizado = normalizar_telefone(bruto)

        exibida, ordem = _formatar_data(linha.get("Data"))
        motivo = motivo_da_linha(linha)
        assinatura = (exibida, motivo.upper())
        if assinatura in vistas[chave]:
            continue
        vistas[chave].add(assinatura)
        colaborador.pendencias.append(Pendencia(data=exibida, motivo=motivo, ordem=ordem))

    for colaborador in grupos.values():
        colaborador.pendencias.sort(key=lambda p: (p.ordem, p.motivo))

    return sorted(grupos.values(), key=lambda c: c.nome)


def _chave_do_colaborador(linha: dict, nome: str) -> str:
    """Quem é a mesma pessoa. `Código` quando existe, nome como reserva.

    O nome sozinho não serve: dois "JOSE DA SILVA" diferentes colapsavam num
    colaborador só — o segundo nunca recebia mensagem e o primeiro recebia
    dias que não eram dele. Num quadro de centenas de pessoas isso não é
    hipótese remota, é questão de tempo.

    `Código` é a matrícula do PontoTel. Medido na planilha de setembro/2026:
    presente em 94 das 94 linhas, 57 códigos para 57 nomes, nenhum código com
    mais de um nome. Ele também é estável quando alguém muda de sobrenome.

    O nome continua como reserva porque uma competência pode vir sem a coluna,
    e sem chave nenhuma o agrupamento não acontece. §11 pede que isto seja
    trocável por CPF ou matrícula depois; é esta linha, e só ela.
    """
    codigo = str(linha.get("Código") or "").strip()
    return f"cod:{codigo}" if codigo else f"nome:{nome.upper()}"
