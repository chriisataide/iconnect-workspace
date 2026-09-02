"""`/workspace/ir/<código>/` — o código vira lugar.

## Por que uma rota, se o ⌘K já resolve o código

Porque o código precisa funcionar **fora** do produto. "Abre a 02.2" vira link
em e-mail, em ata de reunião e em mensagem de WhatsApp; a paleta só existe para
quem já está com o Workspace aberto. Um endereço que só funciona dentro da tela
não é endereço, é atalho.

## Esta view NÃO decide permissão

Ela resolve o código e manda para a tela. A permissão é a que a tela já aplica
— e é assim de propósito: um `/ir/` que checasse acesso criaria um **segundo
lugar** onde "quem vê o quê" está escrito, ao lado de `pode()`. O dia em que os
dois discordassem, o produto teria duas respostas para a mesma pergunta e
nenhuma forma de saber qual vale.

A consequência é visível e testada: quem não tem escopo em `/ir/08/` recebe
**403 da tela de Indicadores**, não 404 aqui.

## E por que 404 não vaza a existência do código

O 404 daqui é sobre o **código**, não sobre a pessoa: ele responde igual para
todo mundo, porque o registro de telas é o mesmo para todo mundo. Não há o que
inferir — a lista de códigos é vocabulário público da empresa, como o organograma
de departamentos. O que é privado é o CONTEÚDO de cada tela, e disso quem cuida
é a tela.
"""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect

from workspace import enderecamento as end


def ir_para(request: HttpRequest, codigo: str) -> HttpResponse:
    tela = end.por_codigo(codigo)
    if tela is None or not tela.url:
        raise Http404(f"Não existe tela com o código {codigo}.")
    return redirect(tela.url)
