# Leitura e detalhamento da tabela contábil

A tabela de Resultados mantém oito colunas. “% do orçado” e “Folga” dão lugar
a “Desvio (%)” e “Desvio (R$)”, calculados sobre o realizado ajustado. O sinal
positivo indica melhora do resultado e o negativo, piora, considerando receitas
positivas e despesas negativas. A classificação também aparece em texto.

O percentual divide o desvio pelo valor absoluto do orçamento. Orçamento zero
permite o desvio em reais, mas não o percentual; orçamento ausente ou parcial
não gera comparação. Contas desconhecidas não recebem classificação favorável
ou desfavorável. Os campos antigos do serviço permanecem para consumidores
existentes; a nova apresentação usa a análise específica da tabela.

Ao expandir um grupo, aparecem a comparação com o mês anterior e os detalhes
de composição por contrato/centro de custo e de origem dos ajustes. Cada conta
também tem sua análise. O histórico é consultado uma única vez, apenas quando
há grupos abertos, usando o mesmo escopo autorizado. A composição considera
o realizado ajustado e reconcilia com o valor da linha.

Comparações mensais usam os registros disponíveis em cada mês: alterações de
composição também influenciam o desvio. Ausência de registros anteriores não
é tratada como zero. Autor, data do ajuste e justificativa não estão disponíveis
no contrato atual da fonte; a interface informa essa limitação e apresenta
a referência e a data de carga quando disponíveis. A data de carga não é a
data de aprovação do ajuste. Ajustes que se compensam continuam no detalhe.

O cabeçalho apresenta fonte e última carga recebida, com indicação de datas
ausentes e da carga mais antiga quando diferente. Os ajustes zerados aparecem
como zero. Desvio e detalhes permanecem em reais mesmo no modo percentual,
conforme os rótulos e a explicação abaixo da tabela.

A memória de navegação preserva também os novos detalhes abertos. O estado é
capturado no evento de abertura/fechamento, pois esperar apenas a saída da
página não preservava a abertura em um refresh real do Chrome.

Validação: 253 testes Python nas áreas contábil, filtros, perfuração, gráficos,
design e CSP; 10 testes JavaScript de navegação. Chrome isolado com banco copiado
em memória: alinhamento a 1440 e 390 px, composição aberta após refresh, posição
preservada ao recolher e ausência de exceções JavaScript. Nenhuma migração ou
alteração dos dados de origem. A suíte completa não foi repetida nesta mudança.
