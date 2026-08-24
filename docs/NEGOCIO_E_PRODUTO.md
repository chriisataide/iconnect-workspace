# Negocio e Produto

O iConnect Workspace e o hub corporativo da empresa: servicos internos,
documentacao, comunicados, reservas, estoque, frota, aprovacoes, pessoas e
pendencias em um lugar.

## Fronteira de produto

O Workspace organiza a vida corporativa da empresa. O iConnect Platform organiza
a operacao de atendimento aos clientes.

A ligacao entre eles e:

- link para o Platform via `ICONNECT_URL`;
- integracao HTTP opcional e somente leitura quando `ICONNECT_API_URL` esta
  configurada.

Nao ha compartilhamento de banco, sessao ou tabela de usuarios.

## Publico

- Colaboradores que pedem servicos, consultam documentos e reservam recursos.
- Gestores que aprovam pedidos.
- Areas internas que atendem filas: RH, Financeiro, Suprimentos, TI, Marketing,
  Juridico, Operacoes e outras.
- Operacao e administracao interna que mantem pessoas, papeis, centros de custo,
  documentos, estoque, frota e comunicados.

## Proposta de valor

- Uma porta unica para pedir servicos internos.
- Aprovacao unificada para dominios diferentes.
- Visibilidade de pendencias pessoais.
- Acervo normativo com leitura obrigatoria.
- Controle de recursos, estoque, frota e correspondencias.
- Separacao segura entre vida corporativa e atendimento a cliente.

## Requisitos funcionais principais

- Home institucional e aberta.
- Catalogo por intencao.
- Formularios configuraveis por item.
- Rascunhos para pedidos longos.
- Cadeia de aprovacao por dominio e faixa de valor.
- Fila de atendimento depois da aprovacao.
- Anexos privados e autorizados.
- Busca com recorte de acesso.
- Modulos por departamento.
- Documentos com confirmacao de leitura.
- Reservas sem choque de horario.
- Correspondencias com entrega e confirmacao.
- Estoque com razao de movimentos.
- Custodia de itens.
- Frota com despesas e alertas de vencimento.
- Centro de custo e orcamento mensal.
- Notificacoes e comandos de aviso.

## Requisitos nao funcionais

- Separacao forte do iConnect Platform.
- CSP estrita.
- Sem `unsafe-inline`.
- Health check de prontidao.
- Sessao com expiracao de 12 horas por padrao.
- Freio de tentativas no login comum e no admin.
- Uploads com limite de tamanho, quantidade e tipo.
- Testes com ratchet de cobertura e contagem.
- Degradacao quando integracoes opcionais nao estao configuradas.

## Regras de negocio centrais

- O Workspace abre sem login para conteudo institucional.
- Assinar em nome de alguem exige identidade.
- Departamento roteia trabalho; usuario navega por problema.
- Pedido tem tres etapas conceituais: pedir, aprovar, atender.
- Reprovar e terminal; devolver mantem o pedido vivo para correcao.
- Notificacao pode repetir se isso for melhor do que silenciar uma pessoa.
- Veiculo reservavel e o mesmo recurso da grade de reservas.
- Orcamento por centro de custo pertence ao Workspace.
- Conta bancaria da empresa fica em variavel de ambiente, nao em cadastro editavel.

## Roadmap conhecido

O README aponta dois proximos movimentos:

- SSO com M365/Entra ID, usando `entra_oid` e `upn`.
- Assistente de conhecimento alimentado por POPs, normativos e futuramente
  bibliotecas corporativas.

Detalhes historicos estao em `EXEC_08_ROADMAP.md` e `EXEC_11_ENTREGA.md`.
