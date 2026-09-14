# Avaliação do iConnect Workspace — 11/09/2026

> Atualização: a [varredura de 14/09](VARREDURA_WORKSPACE_2026-09-14.md)
> corrigiu a conclusão sobre o CI: PostgreSQL é iniciado, mas os testes usam
> SQLite porque a configuração não lê `DATABASE_URL`. Consulte o relatório
> mais recente para os achados e resultados atualizados.

## Parecer

O sistema tem uma base técnica bem estruturada: regras de acesso centralizadas,
separação entre operação e integração, rastreabilidade dos números e testes
extensos. As prioridades são tornar a interface tão consistente quanto essas
regras, reduzir consultas repetidas e comprovar a operação com fontes reais.

Esta é uma revisão transversal do código, configuração e documentação, com
validação visual específica de Resultados. Não é uma homologação funcional de
todas as telas nem uma auditoria da infraestrutura de produção.

## Pontos fortes verificados

- **Organização por responsabilidade.** `contas` cuida da identidade de login;
  `identidade` resolve autorização e organograma; `financas` cuida de orçamento;
  `resultados` mantém o espelho; `cargas` faz ingestão; `workspace` apresenta os
  fluxos. As interfaces em `workspace/providers/` evitam acoplar as telas ao ERP.
- **Permissões com escopo.** `identidade/services/autorizacao.py` centraliza
  concessões e delegações. A tela, o detalhe e o JSON de resultados usam os
  serviços de escopo, com testes para acesso indevido e isolamento regional.
- **Rastreabilidade.** DTOs carregam procedência; frescor é tratado separadamente.
  `cargas/carregador.py` usa hash de conteúdo e transações para ingestão.
  Isso ajuda a explicar números e a repetir cargas sem duplicar registros.
- **Regras de negócio explícitas.** Aprovação, orçamento, planos, ciclos e metas
  têm serviços próprios. O histórico e a documentação de decisões ajudam a
  entender por que determinada ação é permitida ou recusada.
- **Qualidade automatizada.** O CI executa testes com PostgreSQL, checa migrações,
  cobertura por app, contagem de testes, isolamento e CSP. São controles mais
  úteis do que apenas exigir um percentual global de cobertura.
- **Base visual reaproveitável.** Há tokens, componentes CSS e uma estrutura de
  navegação comum. Gráficos têm tabela alternativa, útil sem JavaScript.
- **Proteções de produção declaradas.** A configuração recusa chave de
  desenvolvimento e hosts indiscriminados; define cookies seguros, HTTPS e
  logs de segurança. O login tem limitação de tentativas. Isso foi verificado
  no código, não na configuração efetiva de um servidor de produção.

## Melhorias prioritárias

| Prioridade | Evidência | Impacto e próximo passo |
|---|---|---|
| Alta | O link de PDF em `workspace/templates/workspace/resultados/_filtros.html` envia somente `competencia`, embora `resultados_pdf()` aceite os filtros do painel. | Ao exportar uma tela filtrada, o PDF pode ter totais diferentes. Gerar o link a partir do mesmo recorte e testar equivalência entre painel e exportação. A permissão do usuário continua sendo aplicada; o problema é perder o filtro escolhido. |
| Alta | Uma renderização local autenticada de Resultados executou **203 consultas**, sendo **136** sobre `resultados_competenciaresultado`. | `resultados/providers.py::_contrato_dto` consulta competências por contrato, além do cálculo de layer. Carregar os dados em lote e reutilizá-los por requisição; acrescentar um teste cujo orçamento de consultas não cresça por contrato. |
| Alta operacional | `manage.py conferir_integracoes` informou **0 de 3 fontes configuradas** neste ambiente: Sankhya, monday e Platform. | Validar credenciais, carga inicial, reconciliação de totais e atualização agendada antes de depender dos painéis na operação. Isso não prova que as fontes estejam ausentes em produção. |
| Média | A regra móvel `.au-check, .au-lote-barra { display: none; }` em `workspace.css` esconde qualquer checkbox com essa classe, embora o comentário trate apenas de aprovação em lote. | O efeito foi corrigido nos filtros de Resultados. Revisar as demais telas e restringir a regra ao componente de aprovação em lote. |
| Média | `workspace/services/resultados.py` tem mais de 3.700 linhas; o CSS global tem mais de 4.700 e o JS comum mais de 800. | Separar gradualmente filtros, montagem de faixas e gráficos; separar estilos por componente. Manter os serviços de permissão como referência única e preservar os testes. |
| Média | O CI tem testes de HTML/CSS, mas não foi encontrada uma etapa que execute os fluxos em navegador real. | Automatizar login, filtro, aprovação e exportação em desktop e celular. A regra que escondia checkboxes mostra a limitação de conferir apenas o código-fonte. |
| Média | `docs/PENDENCIAS.md` registra pendências de agendamento, infraestrutura, documentos reais e decisões operacionais. | Revalidar cada item com responsável, data e evidência. A lista é de 03/09 e não deve ser tratada como inventário atualizado automaticamente. |
| Evolução | O README descreve SSO com M365 como próximo passo; a rota de entrada usa login com senha. | Planejar SSO e ciclo de admissão/desligamento quando a identidade corporativa estiver pronta, incluindo expiração de acessos e comportamento do hub público. |

A medição de consultas foi feita com `CaptureQueriesContext`, RequestFactory,
banco SQLite local e uma conta administrativa já existente, sem alterar a conta.
O tempo observado foi aproximadamente **0,13 s**, mas uma execução local isolada
não mede latência de produção, concorrência nem volume futuro. A quantidade e o
padrão de consultas são a evidência relevante para a prioridade de desempenho.

## Melhoria implementada nos filtros

- Área e Serviço agora abrem menus com caixas de seleção, permitindo escolher e
  desmarcar várias opções sem depender de Ctrl/Cmd.
- Centro de custo e Contrato agora são selects na tela de Resultados. As opções
  vêm da carteira acessível, antes do recorte escolhido, preservando alternativas
  para trocar os filtros e os valores de links existentes.
- Quando, Onde e O quê usam uma grade com tamanhos de campo consistentes.
- Aplicar filtros tem destaque visual; navegação e exportação ficam em uma faixa
  separada dos campos.
- No celular, a barra deixa de ser fixa, os campos ocupam a largura disponível e
  as caixas de seleção permanecem visíveis.
- Os menus funcionam sem JavaScript. O pequeno script acrescenta resumo das
  escolhas, fechamento ao clicar fora e Escape com retorno de foco.
- As telas Quadro e Satisfação compartilham a apresentação dos grupos; seus
  campos de localização preservam o funcionamento anterior, pois seus dados
  podem existir sem uma carteira de contratos correspondente.

## Verificação desta alteração

- Django: checagem do projeto sem problemas; nenhuma migração pendente.
- Testes focados: **72 aprovados**, incluindo isolamento das opções, valores
  selecionados e compatibilidade das telas que compartilham os filtros.
- Chrome temporário: página renderizada pelo Django validada em **320, 768,
  1024 e 1440 px**, sem transbordamento horizontal da barra; seleção,
  desmarcação e Escape verificados, sem exceções JavaScript observadas.
- A validação visual usou uma cópia HTML renderizada da tela, com os arquivos
  reais de CSS e JS. Não utilizou a sessão pessoal do navegador nem comprovou
  uma navegação autenticada de ponta a ponta por HTTP.
- Suíte ampla: **3.682 aprovados e 2 falhas** em 3.684 testes coletados. Essa
  execução começou antes do ajuste final do estado sem áreas. Os dois casos
  foram reexecutados após a correção: **2 aprovados**. O conjunto focado de
  72 testes também passou após o ajuste. Não houve segunda execução integral.
- Cobertura medida na suíte ampla: **98,17%**. Os pisos por app e de contagem
  foram aprovados por `scripts/check_coverage_ratchet.py`.
- O teste de preservação da seleção foi acrescentado depois da coleta da suíte
  ampla e está incluído no conjunto focado aprovado.

## Ordem de trabalho sugerida

1. Corrigir a preservação de filtros no PDF e reduzir consultas por contrato.
2. Validar as fontes reais e o agendamento com reconciliação dos números.
3. Estender a revisão visual aos fluxos mais usados: solicitação, aprovação,
   busca e consulta de resultados; adicionar testes reais de navegador ao CI.
4. Dividir os arquivos mais concentrados conforme esses componentes forem
   alterados e atualizar o inventário de pendências operacionais.
