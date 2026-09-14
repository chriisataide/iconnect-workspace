# Varredura do iConnect Workspace — 14/09/2026

## Parecer

O Workspace já é um produto corporativo com abrangência considerável, regras de
negócio próprias e uma base de testes forte. A próxima etapa deveria priorizar
confiabilidade operacional e facilidade de uso: fechar inconsistências entre
fluxos, validar concorrência no banco correto, reduzir consultas repetidas e
colocar as integrações e rotinas para funcionar com dados reais.

Não recomendo uma reescrita nem dividir o produto em microserviços agora. A
separação atual de responsabilidades é útil; os principais problemas encontrados
podem ser resolvidos dentro dela, com alterações delimitadas.

## Alcance e evidências

- Seis apps próprios: `workspace`, `identidade`, `contas`, `financas`,
  `resultados` e `cargas`.
- Inventário: **73 models**, **118 rotas de Workspace**, **92 templates** e
  **133 arquivos de testes Python** nos seis apps.
- Varredura transversal das rotas, serviços, providers, persistência, integração,
  autorização, arquivos, frontend, comandos agendados e documentação.
- **60 rotas sem parâmetros de caminho**, exercitadas como visitante e como
  administrador: **120 requisições**, sem respostas 500 ou exceções não tratadas.
  Redirecionamentos, recusas de acesso e métodos não permitidos são respostas
  esperadas em parte delas; não são 120 páginas acessíveis publicamente.
- Essa verificação usou uma cópia do SQLite local em memória. Login, sessões e
  experimentos não alteraram o banco original. Nenhuma mensagem foi enviada.
- Suíte integral, antes da correção de rolagem: **3.685 testes aprovados**,
  **98,17% de cobertura**, com pisos de cobertura e contagem aprovados.
- Após a correção de rolagem: **215 testes Python focados** e **9 testes
  JavaScript** aprovados, além de testes reais no Chrome.

Esta varredura cobre os módulos e camadas do repositório. Não equivale a uma
homologação manual de cada ação de cada perfil, a um teste de carga concorrente,
a uma auditoria de CVEs atualizada ou à inspeção da infraestrutura de produção.
Os registros locais também não comprovam adoção real pela empresa.

## Problemas comprovados e melhorias prioritárias

### 1. O CI não usa o PostgreSQL que inicia — prioridade alta

O workflow [ci.yml](../.github/workflows/ci.yml) inicia PostgreSQL e define
`DATABASE_URL`, mas usa `iconnect_workspace.settings.dev`. Nem `dev.py` nem
`base.py` interpretam essa variável; o banco efetivo continua SQLite.

**Verificação:** carregar as configurações com os mesmos valores do CI devolve
`django.db.backends.sqlite3` em `settings.DATABASES['default']['ENGINE']`.

Isso corrige uma conclusão da avaliação de 11/09: o PostgreSQL estava declarado
no workflow, mas não era usado pelo Django. A diferença importa especialmente
para operações que dependem de bloqueios de linha, como aprovação e estoque.

**Melhoria:** criar uma configuração explícita de testes em PostgreSQL, fazer o
CI usá-la e acrescentar uma checagem do engine. Depois, testar concorrência real
com transações e conexões distintas. Não basta mudar o comentário do workflow.

### 2. Atendimento aceita uma segunda conclusão com estado desatualizado — alta

Em [atendimento.py](../workspace/services/atendimento.py), `assumir()` e
`concluir()` recebem uma instância e verificam seu estado em memória.
`transaction.atomic` não relê nem bloqueia automaticamente essa instância.

**Reprodução isolada:** carregar o mesmo pedido em dois objetos, concluir o
primeiro e depois concluir o segundo. A segunda chamada foi aceita e gerou
**dois eventos de conclusão**. O teste atual de repetição reutiliza o objeto já
atualizado, por isso não cobre esse caso.

Há risco adicional no caminho de material: `concluir()` chama a baixa de estoque
e `baixar_por_pedido()` grava um movimento por chamada. A duplicidade do evento
foi reproduzida; a dupla baixa sob concorrência deve ser coberta pelo teste
específico, antes de afirmar seu impacto em produção.

**Melhoria:** reler e bloquear o pedido antes de validar a transição, aplicar o
mesmo princípio a assumir/devolver/reabrir e definir idempotência para os efeitos
associados. O motor de aprovação já utiliza `select_for_update()` e serve como
referência local.

### 3. O link de PDF perde filtros — alta

O link em [_filtros.html](../workspace/templates/workspace/resultados/_filtros.html)
envia apenas a competência. A view de PDF aceita os filtros, mas não os recebe
quando a pessoa exporta pela barra.

**Impacto:** a tela pode mostrar uma área ou serviço e o PDF trazer um conjunto
mais amplo, ainda dentro da permissão da pessoa. É uma divergência de recorte,
não uma comprovação de vazamento entre permissões.

**Melhoria:** gerar o link com o mesmo objeto de filtros e testar a equivalência
dos totais entre tela, JSON, detalhe e PDF.

### 4. Consultas ao banco crescem demais — alta para expansão de volume

Medições pontuais com Django Client, conta administrativa e banco local:

| Tela | Consultas | HTML aproximado |
|---|---:|---:|
| Resultados | 208 | 177,5 KB |
| Exceções | 198 | 76,8 KB |
| PDF de Resultados | 186 | resposta PDF |
| Orçamento | 174 | 25,0 KB |
| Painel da empresa | 88 | 34,9 KB |
| Planos de ação | 86 | 36,9 KB |
| Quadro | 78 | 46,5 KB |
| Satisfação | 73 | 42,6 KB |
| Pessoas e papéis | 56 | 101,0 KB |

O banco local tinha **18 contratos e 3 centros de custo**. Em Resultados,
[resultados/providers.py](../resultados/providers.py) calcula dados consultando
competências por contrato. Em Orçamento, a view chama a grade anual por centro,
que monta os valores mês a mês. São alvos concretos para carregar e agregar em
lote e reutilizar resultados dentro da requisição.

A medição anterior de 203 consultas usava RequestFactory, sem todo o caminho do
Client. Os números não são uma comparação antes/depois de desempenho. O tempo
local foi baixo, mas não representa rede, volume e concorrência de produção.

**Melhoria:** medir o crescimento com 20, 200 e 2.000 contratos, estabelecer
limites de consultas por tela e otimizar os provedores antes de adicionar cache
compartilhado a números sensíveis a filtro e permissão.

### 5. Memória de navegação em Resultados — corrigido nesta entrega

Os filtros e expansões tinham URLs válidas, mas recarregavam a tela no início.
A reprodução no Chrome mostrou a rolagem cair de **4.287 para 0 pixels** ao abrir
um grupo contábil.

Foi acrescentada memória de leitura por aba e por entrada do histórico:

- posição relativa da linha contábil ou da seção, sem alterar os filtros da URL;
- restauração após a montagem dos gráficos;
- preservação da rolagem horizontal da tabela e das tabelas alternativas abertas;
- suporte a filtros, cliques no gráfico, troca de modo, expandir/recolher e refresh;
- links de seção, novas abas e navegação para outros destinos continuam nativos;
- sem armazenamento disponível, a página continua funcionando pelo caminho normal.

O recarregamento completo continua existindo. A correção preserva o ponto de
leitura; não transforma a tela em uma aplicação com atualização parcial.

**Verificado no Chrome:** expandir, recolher, trocar modo, filtrar período,
refresh, Voltar, rolagem horizontal em viewport móvel e clique real na barra do
gráfico. A linha contábil manteve exatamente o deslocamento medido; na perfuração
do gráfico a diferença ficou abaixo de 1 pixel. Sem exceções JavaScript.

Se um filtro eliminar a linha ou tornar a página mais curta, o navegador só
consegue restaurar uma posição que exista no novo conteúdo.

### 6. CSS global produz efeitos fora do componente — média

A regra móvel `.au-check, .au-lote-barra { display: none; }` pretendia esconder
seleção em lote, mas afetava outros checkboxes. O efeito na barra de Resultados
foi corrigido em 11/09; a regra ampla ainda deve ser restringida ao componente
que a motivou.

**Melhoria:** revisar controles de formulário em celular, foco, espaços clicáveis,
estados vazios e mensagens de erro. Testes que procuram texto no HTML não
comprovam que um controle apareça ou seja utilizável.

### 7. Manutenção e operação precisam acompanhar o tamanho do produto — média

- `workspace/services/resultados.py` tem mais de 3.700 linhas; o CSS global mais
  de 4.700. Separar gradualmente filtros, composição de faixas e gráficos, sem
  criar novas fontes para a mesma regra de negócio.
- A central limita o histórico de notificações a 60 itens e informa o corte.
  Paginar permitiria consultar o histórico antigo sem aumentar a carga inicial.
- Pessoas e algumas filas materializam conjuntos antes de montar a tela.
  Revisar crescimento, paginação e contadores agregados conforme o uso real.
- O CI não tem etapa de navegador real nem auditoria de dependências. Os novos
  testes JavaScript desta entrega são executáveis, mas ainda não estão ligados
  ao workflow.
- `/saude/` verifica o banco; a configuração de produção também depende de Redis.
  Definir prontidão, alertas de cache, falhas de carga, rotinas não executadas e
  logs com retenção. Ter arquivos de configuração não comprova monitoramento ativo.

## Avaliação por frente funcional

| Frente | O que já existe no código | O que melhorar ou completar |
|---|---|---|
| Hub e navegação | Launcher, catálogo, busca, endereçamento por código, trilho e contadores | Medir os caminhos mais usados e reduzir a quantidade de decisões para tarefas frequentes; rever navegação móvel |
| Meu dia e notificações | Pendências pessoais, histórico e avisos por eventos | Histórico paginado, preferências de frequência e resumos fora do portal, se aprovados como escopo |
| Solicitações | Catálogo, formulários, rascunho, anexos, reenvio e histórico | Testar jornadas completas por perfil; padronizar validações, mensagens e restauração de contexto |
| Aprovações | Cadeias, justificativas, limites, orçamento comprometido e bloqueio do próprio pedido | Testar concorrência no PostgreSQL; validar regras reais, substituições e responsáveis ausentes |
| Atendimento | Fila, responsável, conclusão, devolução e reabertura | Corrigir estado desatualizado e idempotência; medir tempo em cada etapa |
| Pessoas e papéis | Organograma, concessões, escopo, vigência, delegações e administração | SSO corporativo, sincronização do diretório e processo de entrada/saída de colaboradores |
| Conteúdo e comunicação | Documentos, versões, revogação, públicos e confirmação de leitura | Acervo real, responsáveis e revisão periódica; ingestão do repositório corporativo ainda requer implementação |
| Assistente e busca | FAQ curada, interpretação determinística e índice filtrado por acesso | Provedor real de IA, fontes citadas, avaliação de respostas e tratamento de perguntas sem resposta |
| Reservas | Recursos, agenda, cancelamento e controle de sobreposição | Testar disputa concorrente no banco correto; decidir integração com calendário corporativo |
| Correspondências | Registro, identificação, entrega e confirmação | Validar rotina física e exceções; verificar se avisos e comprovantes atendem à operação real |
| Estoque e custódia | Razão, saldos, movimentos, reversa, entrega, aceite e devolução | Idempotência vinculada ao pedido, inventário operacional e cenários de concorrência |
| Frota | Veículos, despesas, alertas e aproveitamento do sistema de reservas | Carga real, documentos, responsáveis e indicadores de custo por veículo/período |
| Reembolso e orçamento | Despesas, adiantamentos, acerto, compromissos, orçamento anual e revisões | Conta de devolução configurada, reconciliação contábil, concorrência e consultas em lote |
| Universidade | Habilitações pessoais, pendências e painel de conformidade | Conteúdo/certificações reais e integração com a fonte de RH; não confundir com LMS completo |
| Recrutamento interno | Candidaturas apoiadas no catálogo e consulta de inscrições | Validar etapas, responsáveis, confidencialidade e encerramento com RH |
| Marketing e radar | Oportunidades, decisão e coleta de editais do PNCP | Validar filtros e qualidade dos editais, acompanhamento comercial e rotina de carga |
| Resultados e painel | Áreas, plano de contas, DRE, comparações, gráficos, tabelas e perfuração | PDF coerente, escala de consultas, fontes reais e continuidade da navegação |
| Quadro e satisfação | Telas próprias com permissões e filtros | Homologar fontes, denominadores, períodos e tratamento de dados incompletos |
| Exceções | Regras, ocorrências, fontes e retratos para tendência | Ativar as fontes necessárias, avaliar falsos positivos e medir resolução |
| Ciclos e planos | Pauta, registros, fechamento e verificação de resultados | Comprovar uso recorrente e execução do agendamento; medir eficácia dos planos |
| Metas e PDI | Quadros individuais, fórmulas, avaliação e ações | Homologar com RH e gestores. Havia zero quadros no banco local, o que não significa ausência de implementação |
| Integrações e operação | Conectores, espelho, procedência, diagnóstico e cron de referência | Credenciais, agendamento real, alertas, reconciliação, backup e teste de restauração |

## O que não está feito, distinguindo código de configuração

### Falta implementação

1. **SSO do Workspace com M365/Entra e sincronização do diretório.** Existe uma
   ponte de troca de código/JWT com o iConnect Platform; isso não é login
   corporativo completo do Workspace. A entrada atual usa senha.
2. **Provedor concreto de IA.** Existe a interface e o fallback determinístico;
   não foi encontrado registro de um provedor real na inicialização. Busca
   semântica, análise de contrato e redação por IA não devem ser anunciadas como
   entregues apenas porque há métodos declarados na interface.
3. **Ingestão do acervo corporativo, como SharePoint.** O catálogo/documentação
   funciona, mas o conector e o fluxo de sincronização precisam ser construídos.
4. **Analytics pessoal**, descrito no ADR-014: visão individual somente para o
   próprio usuário e gestão com agregado. Não foi localizado módulo implementado.
5. **Canais externos de notificação.** O serviço declara que não envia e-mail nem
   push; implementar digest, preferências, tentativas e entrega é trabalho novo.
6. **Expurgo e retenção de anexos sensíveis.** A política precisa ser definida
   pelos responsáveis e depois implementada, incluindo arquivos, registros e
   cópias. Não é apenas preencher uma variável de ambiente.
7. **Testes reais de navegador integrados ao CI**, verificação de concorrência
   em PostgreSQL e uma política automatizada de auditoria de dependências.

### O código existe, mas falta comprovar a operação

- As três fontes empresariais estavam sem configuração no diagnóstico local.
  Isso não permite afirmar o mesmo sobre produção.
- Há `deploy/crontab`; não foi verificada instalação e execução no servidor real.
  A sequência por horário não é uma dependência de execução: atrasos e
  sobreposição ainda precisam ser monitorados.
- O banco local tinha **1 documento**, **26 FAQs**, **30 itens de catálogo**,
  **19 solicitações** e **542 editais**. Essas contagens substituem números
  antigos da documentação para este ambiente, sem dizer se o conteúdo é real
  ou está homologado.
- Orçamentos, papéis, responsáveis, catálogo, metas, acervo e fontes precisam de
  validação pelos donos de cada processo.
- Backup do banco e dos arquivos privados, restauração, proxy e Redis
  compartilhado precisam de evidência operacional; não inspecionei produção.

### O que é oportunidade, não compromisso já assumido

- Visões salvas dos painéis: recortes nomeados por pessoa ou equipe, mantendo
  as mesmas permissões e sem criar outra versão dos números.
- Resumo diário de pendências e alertas com frequência controlada.
- Central de operação das cargas: última execução, duração, falhas, registros
  processados e reconciliação numa leitura única.
- Onboarding por perfil, com os poucos caminhos que cada pessoa usa de fato.
- Indicadores de adoção e eficiência do processo: conclusão, tempo parado,
  retrabalho e pendências sem responsável, sem ranking individual de produtividade.

Não trataria folha, ponto, LMS completo, chat ou portais de clientes/fornecedores
como “funcionalidades faltando”. São produtos ou domínios distintos e exigem
uma decisão de escopo. Recrutamento, habilitações, planos, metas, áreas e plano
de contas **já têm implementação**, mesmo quando documentos antigos dizem o
contrário.

## Sequência recomendada

1. **Confiabilidade:** corrigir engine do CI, estado desatualizado no atendimento
   e filtros do PDF; preservar os testes atuais e acrescentar os cenários que
   escaparam deles.
2. **Operação:** fontes reais, responsáveis, execução agendada, alertas,
   reconciliação e restauração testada.
3. **Usabilidade e escala:** revisão dos principais fluxos no celular, consultas
   em lote, paginação e navegador no CI.
4. **Evolução de produto:** SSO/diretório, acervo conectado, IA com avaliação,
   visões salvas e notificações externas conforme a necessidade comprovada.

A priorização é por dependência e impacto. Datas e estimativas fechadas exigem
conhecer volume real, infraestrutura, equipe disponível e regras homologadas.

## Como verificar a correção de rolagem

- `node --test scripts/tests/resultados-posicao.test.cjs`
- Testes Python: `test_contabil`, `test_perfuracao`, `test_filtros_resultados`,
  `test_graficos` e `test_csp_e_estilo_inline`.
- No navegador: ir à tabela contábil, expandir/recolher uma linha, alternar
  reais/percentual, aplicar período, atualizar, voltar e navegar horizontalmente
  na tabela em tela estreita. Repetir a seleção clicando na barra de um gráfico.
