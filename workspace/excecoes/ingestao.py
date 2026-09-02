"""As duas regras sobre a própria ingestão.

Elas não pertencem a departamento nenhum — `escopo_papel` fica vazio, e quem
abre o painel as vê. São o "99" do painel de exceções: as regras que vigiam o
mecanismo em vez do negócio.
"""

from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from workspace.providers import frescor as contrato
from workspace.services import frescor as frs

from .base import Ocorrencia, RegraBase


class FonteAtrasada(RegraBase):
    """Regra 17 — fonte sem carga bem-sucedida além da cadência.

    A régua é a idade que a PRÓPRIA fonte declarou aceitável, e não um número
    escolhido aqui: seis horas é velho para o monday e é novo para a folha do
    Sankhya. Uma constante única alarmaria a metade errada do painel.

    Fonte **não configurada** fica de fora. Ela não está atrasada — ela nunca
    foi ligada, e num ambiente de desenvolvimento não estar ligada é o normal.
    """

    chave = "fonte-atrasada"
    fonte = "cargas"

    def disponivel(self) -> bool:
        return contrato.obter() is not None

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        provedor = contrato.obter()
        ocorrencias = []
        for fonte in provedor.fontes():
            if not fonte.ativa or not fonte.configurada:
                continue
            carimbo = frs.de(fonte.chave)
            if not carimbo.alerta:
                continue
            ocorrencias.append(
                Ocorrencia(
                    chave=f"fonte:{fonte.chave}",
                    titulo=fonte.nome,
                    detalhe=carimbo.motivo
                    or f"última carga boa {carimbo.idade or 'nunca'}",
                    url=reverse("workspace:fontes"),
                    responsavel=fonte.responsavel or "ninguém",
                    papel="ti",
                )
            )
        return ocorrencias


class DivergenciaEntreFontes(RegraBase):
    """Regra 18 — duas fontes discordam, e a divergência segue aberta.

    Ela aparece MESMO quando a regra de precedência resolveu o valor. Resolver
    não é concordar: o número entra na tela pela regra, e a divergência continua
    aberta para alguém ir descobrir por que os sistemas discordam.
    """

    chave = "divergencia-entre-fontes"
    fonte = "cargas"

    def disponivel(self) -> bool:
        return contrato.obter() is not None

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        provedor = contrato.obter()
        return [
            Ocorrencia(
                chave=f"divergencia:{d.entidade}:{d.chave}:{d.campo}",
                titulo=f"{d.entidade} {d.chave} · {d.campo}",
                detalhe=f"{d.fonte_a}: {d.valor_a}  ≠  {d.fonte_b}: {d.valor_b}",
                url=f"{reverse('workspace:fontes')}#divergencias",
                responsavel="ninguém",
                papel="ti",
                desde=d.detectada_em.date() if d.detectada_em else None,
            )
            for d in provedor.divergencias(abertas=True)
        ]
