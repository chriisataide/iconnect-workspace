# Gestao e Stakeholders

Este documento orienta acompanhamento executivo, status de projeto, custos e
comunicacao com stakeholders.

## Stakeholders principais

| grupo | interesse |
|---|---|
| Diretoria | continuidade, risco, produtividade e governanca |
| RH | organograma, papeis, beneficios, ferias, vagas e documentos |
| Financeiro | centros de custo, orcamento, reembolso e adiantamentos |
| Operacoes | frota, reservas, estoque, correspondencias e atendimento |
| TI/SecOps | infraestrutura, seguranca, SSO e integracoes |
| Gestores | aprovacoes, equipe e orcamento |
| Colaboradores | pedidos, documentos, reservas e pendencias |
| Desenvolvimento | evolucao, testes e arquitetura |

## Relatorio de status sugerido

Frequencia: semanal durante implantacao; mensal em operacao estavel.

Campos:

- periodo;
- versao/commit implantado;
- disponibilidade;
- incidentes;
- mudancas entregues;
- riscos abertos;
- proximas entregas;
- decisoes pendentes;
- metricas de uso;
- metricas de atendimento;
- custo operacional estimado.

## Indicadores de produto

Indicadores possiveis a partir dos modelos atuais:

- pedidos criados por dominio;
- pedidos concluidos;
- tempo em aprovacao;
- tempo em atendimento;
- quantidade de rascunhos;
- aprovacoes pendentes por papel;
- pedidos devolvidos ou reprovados;
- anexos por solicitacao;
- documentos com leitura obrigatoria pendente;
- reservas por recurso;
- divergencias de estoque;
- vencimentos de frota e habilitacao;
- consumo por centro de custo.

## Custos documentaveis

Infraestrutura:

- aplicacao;
- banco PostgreSQL;
- Redis;
- storage privado;
- backup;
- logs/monitoramento;
- proxy/CDN/balanceador, se houver.

Licencas:

- dependencias Python atuais sao open source.
- SSO pode depender de licencas Microsoft ja existentes.
- o repositorio nao declara uma licenca publica; ver `CONHECIMENTO_ORGANIZACIONAL.md`.

Manutencao:

- evolucao de produto;
- operacao de seeders/comandos;
- revisao de papeis;
- gestao de documentos e leitura obrigatoria;
- suporte a usuarios.

## Apresentacao executiva

Formato recomendado:

- uma pagina com saude do produto;
- top 5 riscos;
- top 5 ganhos entregues;
- decisoes que precisam de diretoria;
- custo mensal e variacao;
- roadmap dos proximos 30/60/90 dias.

## Decisoes pendentes tipicas

- teto de autoaprovacao por dominio;
- orcamento mensal por centro de custo;
- RPO/RTO finais;
- politica de retencao de anexos e documentos;
- dono de cada documento normativo;
- responsaveis por cada papel critico;
- calendario de auditoria de acessos.

## Relacao com documentos existentes

- `EXEC_11_ENTREGA.md`: historico de entrega.
- `EXEC_08_ROADMAP.md`: roadmap.
- `EXEC_09_VALIDACAO_CTO.md`: validacao tecnica.
- `EXEC_14_SEGURANCA.md`: riscos e controles de seguranca.
- `CONTINUIDADE_RISCO.md`: continuidade e resposta a incidentes.
