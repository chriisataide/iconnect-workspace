# Guia de Uso do Workspace

O iConnect Workspace organiza a vida corporativa da empresa em um lugar. Ele nao
substitui o iConnect Platform: o Platform continua sendo a operacao de
atendimento aos clientes.

## Acesso

- `/workspace/` abre a home.
- `/entrar/` identifica a pessoa quando uma acao precisa de assinatura.
- `/sair/` encerra a sessao.

O Workspace e aberto para conteudo institucional: home, busca, catalogo,
documentacao, reservas e formularios. Conteudo pessoal e decisoes exigem login:
Meu dia, Minhas solicitacoes, bandeja de aprovacao, correspondencias da pessoa,
envio, aprovacao, cancelamento, leitura obrigatoria e download de anexo.

## Home e modulos

A home mostra tiles definidos em `workspace/modulos.py`.

| modulo | uso |
|---|---|
| RH | ferias, beneficios, vagas e ausencias |
| Financeiro | reembolsos, notas e aprovacoes financeiras |
| Operacoes | ordem de servico, escala e SLA |
| Suprimentos | materiais, estoque e viagens |
| Redes | VPN e conectividade |
| Vendas | proposta, desconto e cadastro de cliente |
| Marketing | material, evento e presenca de marca |
| Juridico | contrato, parecer e notificacao |
| Universidade | cursos, trilhas e certificacoes |
| Reservas | salas, veiculos e equipamentos |
| Correspondencias | cartas, encomendas e intimacoes |
| Documentacao | POPs, politicas, normas e manuais |

Os modulos por departamento sao uma vista do catalogo. A navegacao principal
continua sendo por intencao em `/workspace/servicos/`.

## Catalogo de servicos

Use `/workspace/servicos/` para pedir algo. Os itens sao agrupados por problema,
nao por departamento: equipamento, trabalho, dinheiro, viagem, espaco,
desenvolvimento e juridico.

Cada item define:

- dominio de atendimento, como `rh.ferias` ou `fin.reembolso`;
- campos do formulario;
- prazo prometido;
- necessidade de valor ou centro de custo;
- regra de aprovacao ou autoaprovacao;
- opcionalmente um link externo.

Depois do envio, o pedido pode passar por aprovacao e atendimento. A fila de
atendimento e `/workspace/fila/`.

## Aprovacoes

A bandeja fica em `/workspace/aprovacoes/`. Aprovacao e unica para varios
dominios: ferias, reembolso e compra usam o mesmo motor.

O aprovador pode:

- aprovar;
- devolver para correcao;
- reprovar definitivamente;
- aprovar em lote quando permitido.

O sistema registra quem deveria decidir, quem decidiu de fato, justificativa e
data.

## Meu dia e notificacoes

`/workspace/meu-dia/` consolida pendencias pessoais. `/workspace/notificacoes/`
lista avisos. Alertas de habilitacoes, frota, documentos e marketing dependem
dos comandos agendados descritos no runbook de operacao.

## Documentacao

`/workspace/documentacao/` mostra o acervo normativo. Documentos podem ter:

- tipo;
- situacao;
- arquivo;
- leitura obrigatoria;
- confirmacao de leitura;
- revogacao.

A redacao do acervo usa:

- `/workspace/documentacao/acervo/`
- `/workspace/documentacao/novo/`
- `/workspace/documentacao/<slug>/editar/`

## Reservas

`/workspace/reservas/` mostra recursos reservaveis, como salas, veiculos e
equipamentos. A reserva impede choque de horario. Minhas reservas ficam em
`/workspace/reservas/minhas/`.

## Correspondencias

`/workspace/correspondencias/` registra e acompanha cartas, encomendas e
intimacoes. A entrega e confirmacao ficam vinculadas a uma pessoa.

## Estoque, custodia e frota

- `/workspace/estoque/` registra materiais, saldos e movimentos.
- `/workspace/custodia/` controla quem esta com cada item.
- `/workspace/frota/` acompanha veiculos, despesas e vencimentos.

Reservar um veiculo acontece pela grade de reservas, nao por uma rota paralela
de frota.

## Busca e assistente

`/workspace/buscar/` consulta o indice interno. O indice respeita recortes de
acesso no `WHERE`: documento, comunicado, solicitacao e correspondencia nao sao
visiveis para todos do mesmo jeito.

`/workspace/assistente/` consulta FAQ e bases internas. Quando a integracao de
IA falha, o produto deve degradar para conteudo curado.
