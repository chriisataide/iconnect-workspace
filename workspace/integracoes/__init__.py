"""A camada de integração com o iConnect — §52.

Uma camada, e não chamadas espalhadas por telas. O §52 pede isso com todas as
letras, e a razão é a que aparece na primeira vez que o outro lado muda: com
`fetch` em oito componentes, trocar o formato de um campo é uma caçada; com uma
camada, é um arquivo.

    cliente.py    o transporte  — timeout, retry, log, erro em português
    iconnect.py   o vocabulário — `tickets_de()`, `pendencias_de()`, `posicoes()`
    sessao.py     a identidade  — a ponte SSO → JWT, e o refresh

## A regra que vale para tudo aqui

**O Workspace pergunta; o iConnect responde.** Não há escrita: abrir chamado
continua sendo no iConnect, que é onde ele é atendido. Recriar a abertura aqui
seria a duplicação que o §1 proíbe — e o §38 pede exatamente o contrário.

## Sem `requests`

`urllib.request` da biblioteca padrão. São quatro chamadas com `GET`, um `POST`
e header de autorização; `requests` traria uma dependência para manter, um
CVE a acompanhar e uma imagem maior, em troca de conveniência que não é usada.
O projeto tem **uma** dependência de execução (`reportlab`), e ela entrou porque
gerar PDF à mão não é razoável — este caso não é o mesmo.

## Nada aqui derruba uma tela

`ICONNECT_API_URL` vazia — o padrão — faz `disponivel()` ser falso, e cada tela
que depende da integração diz isso em português em vez de quebrar. Timeout,
erro HTTP e JSON malformado terminam no mesmo lugar: log no servidor, mensagem
compreensível na tela, e o resto da página inteira.
"""

from .cliente import IntegracaoError, IntegracaoIndisponivel, disponivel

__all__ = ["IntegracaoError", "IntegracaoIndisponivel", "disponivel"]
