# Documentacao de Software e da Empresa

Guia consolidado dos 8 pilares essenciais do iConnect Workspace.

Este indice organiza a documentacao do produto a partir do codigo atual. Os
documentos executivos `EXEC_*` continuam como historico e contexto de decisao;
os documentos abaixo sao a camada de consulta pratica para uso, manutencao,
operacao, governanca e gestao.

## 1. Para quem usa o software

- [README](../README.md) - visao geral, separacao entre Workspace e Platform,
  quickstart e principais decisoes de produto.
- [Guia de uso do Workspace](GUIA_USO_WORKSPACE.md) - telas, fluxos e quem
  precisa se identificar.
- [Guia de instalacao e configuracao](GUIA_INSTALACAO_CONFIGURACAO.md) -
  dependencias, variaveis de ambiente, seeders e ambiente local.
- [Referencia de rotas e contratos](REFERENCIA_ROTAS_E_CONTRATOS.md) - rotas
  HTTP, contratos internos, comandos e integracoes.
- [Guia de QA](GUIA_QA_WORKSPACE.md) - contrato de cada tela e criterios de
  aceitacao.
- Exemplos de codigo e massa: [`docs/exemplos`](exemplos/).

## 2. Para quem desenvolve ou mantem

- [Arquitetura do sistema](ARQUITETURA_SISTEMA.md) - apps, dependencias,
  modelos centrais, servicos e padroes.
- [EXEC 05 - Arquitetura](EXEC_05_ARQUITETURA.md) - arquitetura planejada.
- [EXEC 10 - Reposicionamento](EXEC_10_REPOSICIONAMENTO.md) - ADRs e decisoes
  de reposicionamento.
- [Guia do time](EXEC_12_GUIA_DO_TIME.md) - decisoes que qualquer mudanca deve
  respeitar.
- [Changelog / historico](EXEC_11_ENTREGA.md) - ondas de entrega e pendencias.

## 3. Operacao e processo

- [Operacao](EXEC_13_OPERACAO.md) - runbook existente: subir, agendar,
  diagnosticar, monitorar.
- [Guia de instalacao e configuracao](GUIA_INSTALACAO_CONFIGURACAO.md) -
  passo a passo local e producao.
- [Continuidade e risco](CONTINUIDADE_RISCO.md) - backups, SLAs sugeridos,
  riscos e plano de resposta.
- Testes: `python -m pytest` e `python scripts/check_coverage_ratchet.py`.

## 4. Negocio e produto

- [Visao geral do produto](NEGOCIO_E_PRODUTO.md) - proposta, publico,
  requisitos e regras de dominio.
- [Blueprint](BLUEPRINT_ICONNECT_WORKSPACE.md) - visao original do produto.
- [PRD](EXEC_04_PRD.md) - requisitos de produto.
- [Roadmap](EXEC_08_ROADMAP.md) - proximas ondas.

## 5. Governanca e conformidade

- [Governanca e conformidade](GOVERNANCA_CONFORMIDADE.md) - seguranca,
  privacidade, RACI e inventario de sistemas.
- [Seguranca](EXEC_14_SEGURANCA.md) - auditoria de seguranca e garantias de
  infraestrutura.
- [`.env.example`](../.env.example) - variaveis e controles protegidos.

## 6. Continuidade e risco

- [Continuidade e risco](CONTINUIDADE_RISCO.md) - BCP/DRP, backups, rollback,
  SLAs e terceiros.
- [Operacao](EXEC_13_OPERACAO.md) - monitoramento, comandos agendados e
  diagnostico.

## 7. Gestao e stakeholders

- [Gestao e stakeholders](GESTAO_STAKEHOLDERS.md) - relatorios, custos,
  indicadores e comunicacao executiva.
- [Entrega](EXEC_11_ENTREGA.md) - estado de entrega e pendencias.
- [Validacao CTO](EXEC_09_VALIDACAO_CTO.md) - riscos tecnicos e validacoes.

## 8. Conhecimento organizacional

- [Conhecimento organizacional](CONHECIMENTO_ORGANIZACIONAL.md) - onboarding,
  wiki interna, registro de decisoes e licenca.
- [Guia do time](EXEC_12_GUIA_DO_TIME.md) - leitura obrigatoria para entrada no
  projeto.
- [Guia de QA](GUIA_QA_WORKSPACE.md) - referencia funcional de telas.

## Boas praticas transversais

- Manter a documentacao perto do codigo sempre que possivel.
- Atualizar este indice quando nascer uma rota, comando, app, variavel de
  ambiente ou decisao relevante.
- Escrever para o publico certo: usuario, operacao, desenvolvimento, negocio ou
  risco.
- Registrar o conhecimento tacito. O que so uma pessoa sabe e risco operacional.
