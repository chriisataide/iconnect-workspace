"""iConnect Platform — contratos, vigência e satisfação de cliente.

## A fronteira, que este conector não atravessa

O Platform é **outro produto**. A ligação entre os dois sempre foi um link
(`ICONNECT_URL`), e este conector não muda isso: ele fala com a **API HTTP** do
Platform, com um usuário de integração somente-leitura, e nunca com o banco
dele. Acesso a banco de outro sistema é o acoplamento que custou 881 lotações
órfãs — e desta vez custaria mais, porque agora são dois deploys.

## O que atravessa, e o que fica

Atravessa o **consolidado**: contrato, vigência, valor, e a avaliação do cliente
já classificada. Fica lá o **detalhe operacional** — ocorrência por ocorrência,
medição por medição, ticket por ticket. A tela de resultados consome consolidado;
trazer o detalhe refaria o acoplamento com outra roupa.

O comentário do detrator vem; **quem escreveu não vem**. Quem respondeu é pessoa
do cliente, e o Workspace não é dono desse cadastro.

## Autenticação

`X-Workspace-Secret`, o mesmo segredo compartilhado que `workspace/integracoes/`
já usa para a troca de sessão — e a mesma variável, `WORKSPACE_SHARED_SECRET`.
Uma segunda credencial para o mesmo par de sistemas seria uma segunda coisa para
rotacionar, e a segunda é sempre a que fica para trás.

Este conector **não importa** `workspace.integracoes`: ele lê `settings`, que é
configuração, e usa o transporte de carga — ver `cargas/transporte.py` para por
que os dois transportes são diferentes.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings

from ..transporte import PAGINAS_MAXIMAS, FonteNaoConfigurada, TransporteError, pedir
from .base import ConectorBase, Janela, Registro

logger = logging.getLogger("cargas")

#: Caminho → entidade do espelho. Sobrescritível por `PLATFORM_ROTAS` para o
#: dia em que a API do Platform versionar o caminho sem versionar o conteúdo.
ROTAS = {
    "contrato": "/api/v1/integracao/contratos/",
    "avaliacao": "/api/v1/integracao/avaliacoes/",
}

TRADUCAO = {
    "contrato": {
        "codigo": "codigo",
        "cliente": "nome_cliente",
        "servico": "servico",
        "centro_custo": "centro_custo",
        "regional": "regional",
        "inicio_vigencia": "inicio_vigencia",
        "fim_vigencia": "fim_vigencia",
        "valor_mensal": "valor_mensal",
        "status": "status",
    },
    "avaliacao": {
        "contrato": "contrato",
        "data": "data",
        "nota": "nota",
        "classificacao": "classificacao",
        "comentario": "comentario",
        "tratativa_aberta": "tratativa_aberta",
        "tratativa_prazo": "tratativa_prazo",
        "tratativa_status": "tratativa_status",
    },
}

DATAS = frozenset({"inicio_vigencia", "fim_vigencia", "data", "tratativa_prazo"})
DECIMAIS = frozenset({"valor_mensal"})
INTEIROS = frozenset({"nota"})
BOOLEANOS = frozenset({"tratativa_aberta"})

#: Campos que NUNCA entram, mesmo que a API os mande. Lista explícita e não
#: confiança no outro lado: o dia em que o Platform acrescentar `cpf_respondente`
#: ao payload, ele não vira coluna do espelho por acidente.
#:
#: Ver a regra 8 do escopo: dado pessoal sensível fica fora de grade e fora de
#: exportação.
RECUSADOS = frozenset({
    "cpf", "documento", "rg", "email", "e_mail", "telefone", "endereco",
    "data_nascimento", "respondente", "respondente_nome", "respondente_email",
    "usuario", "salario",
})


class ConectorPlatform(ConectorBase):
    chave = "iconnect_platform"

    @property
    def base(self) -> str:
        return (getattr(settings, "ICONNECT_API_URL", "") or "").rstrip("/")

    @property
    def segredo(self) -> str:
        return getattr(settings, "WORKSPACE_SHARED_SECRET", "") or ""

    def rotas(self) -> dict:
        return getattr(settings, "PLATFORM_ROTAS", None) or ROTAS

    def disponivel(self) -> bool:
        return bool(self.base and self.segredo)

    # ── Coleta ──────────────────────────────────────────────────────

    def coletar(self, janela: Janela) -> Iterable[dict]:
        if not self.disponivel():
            raise FonteNaoConfigurada(
                "Faltam ICONNECT_API_URL ou WORKSPACE_SHARED_SECRET."
            )
        for entidade, rota in self.rotas().items():
            yield from self._paginar(entidade, rota, janela)

    def _paginar(self, entidade: str, rota: str, janela: Janela) -> Iterable[dict]:
        url = f"{self.base}{rota}"
        if not janela.aberta:
            partes = []
            if janela.de:
                partes.append(f"de={janela.de.isoformat()}")
            if janela.ate:
                partes.append(f"ate={janela.ate.isoformat()}")
            if partes:
                url = f"{url}?{'&'.join(partes)}"

        lidas = 0
        while url:
            if lidas >= PAGINAS_MAXIMAS:
                raise TransporteError(
                    f"{entidade}: passou de {PAGINAS_MAXIMAS} páginas no Platform."
                )
            resposta = pedir(
                url,
                cabecalhos={"X-Workspace-Secret": self.segredo},
            )
            for item in resposta.get("results") or resposta.get("lista") or []:
                yield {"_entidade": entidade, **item}

            proxima = resposta.get("next") or ""
            # A paginação do DRF devolve URL absoluta. Aceitar uma URL de outro
            # host seria seguir um redirecionamento cego para onde o outro lado
            # mandar — e mandar o segredo junto.
            if proxima and not proxima.startswith(self.base):
                raise TransporteError(
                    f"{entidade}: página seguinte aponta para fora de {self.base}."
                )
            url = proxima
            lidas += 1

    # ── Normalização ────────────────────────────────────────────────

    def normalizar(self, bruto: Iterable[dict]) -> Iterable[Registro]:
        for item in bruto:
            registro = self._converter(item)
            if registro is not None:
                yield registro

    def _converter(self, item: dict) -> Registro | None:
        entidade = item.get("_entidade", "")
        traducao = TRADUCAO.get(entidade)
        if not traducao:
            return None

        chave = str(item.get("id") or item.get("codigo") or "")
        if not chave:
            return None

        dados = {}
        for origem, destino in traducao.items():
            if origem in RECUSADOS or destino in RECUSADOS:
                continue
            if origem not in item:
                continue
            valor = _tipar(destino, item[origem])
            if valor is not None or destino in DATAS:
                dados[destino] = valor

        if entidade == "avaliacao":
            contrato = _contrato(dados.pop("contrato", ""))
            if contrato is None:
                # Avaliação de contrato que não chegou ainda. Rejeitada pelo
                # carregador com motivo, e não gravada órfã: uma avaliação sem
                # contrato não aparece em nenhuma tela e some do relatório.
                return None
            dados["contrato"] = contrato

        return Registro(entidade=entidade, chave_externa=chave, dados=dados)


def _contrato(codigo: str):
    from resultados.models import Contrato

    return Contrato.objects.filter(codigo=str(codigo)).first() if codigo else None


def _tipar(destino: str, bruto):
    if bruto in (None, ""):
        return None
    if destino in DATAS:
        try:
            return datetime.strptime(str(bruto)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    if destino in DECIMAIS:
        try:
            return Decimal(str(bruto))
        except (InvalidOperation, ValueError):
            return None
    if destino in INTEIROS:
        try:
            return int(bruto)
        except (TypeError, ValueError):
            return None
    if destino in BOOLEANOS:
        return bool(bruto)
    return str(bruto).strip()
