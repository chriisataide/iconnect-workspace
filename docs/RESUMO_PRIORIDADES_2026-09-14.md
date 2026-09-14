# Resumo e prioridades

Os cards foram substituídos por listas de Destaques (sinais positivos) e
Pontos de atenção (demais sinais, com indicação textual dos críticos).
Cada linha mostra o título, valor, contexto e acesso ao detalhe. Três itens
aparecem inicialmente por categoria; “Ver todos” revela o restante.

Concentrações permanecem decisões humanas, exibidas em lista com referência,
motivo, responsável, prazo, situação e próximo passo. O próximo passo pode ser
atualizado por quem possui `eco.concentrar`. Focos encerrados permanecem no
histórico recolhido e não podem receber atualização do próximo passo.

“Definir como concentração” preenche o formulário, sem salvar automaticamente.
O vínculo identifica o sinal, a competência e o escopo. Um foco aberto vinculado
troca essa ação por “Ver concentração”. A restrição no banco impede dois focos
abertos para o mesmo vínculo, inclusive em submissões concorrentes. Após o
encerramento, é possível abrir outro acompanhamento. Indicadores agregados são
identificados como indicadores, sem atribuí-los artificialmente a um contrato.

A migração 0059 adiciona `proximo_passo` e `alerta_chave`, opcionais para os
registros anteriores, além da restrição de unicidade condicional. Foi aplicada
ao banco local. Outros ambientes devem aplicar a migração antes desta versão.

Testes cobrem permissões, criação repetida, restrição no banco, atualização,
encerramento e distinção de vínculos por mês/recorte. A regressão de Resultados,
telas irmãs, contabilidade, design e CSP passou. Chrome a 1440 e 390 px confirmou
a ausência de cards, preenchimento do formulário e ausência de transbordamento
da página e de exceções JavaScript. A suíte completa não foi repetida.
