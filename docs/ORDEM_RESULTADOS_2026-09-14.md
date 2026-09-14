# Sequência de leitura de Resultados

A página passa a apresentar a carteira antes do resultado que ela produz:

1. Destaques e pontos de atenção, com os focos já registrados.
2. Nossa carteira: quantidade, valor mensal, mix por serviço, conquistas e perdas.
   Safras ficam em consulta opcional, aberta quando há uma safra selecionada.
3. Resultado financeiro: receita, margem, EBITDA, evolução e comparação.
4. Composição do resultado: cascata e contas contábeis.
5. Rentabilidade dos contratos: deficitários, abaixo da margem e dispersão.
6. Vencimentos dos contratos.
7. Projetos, entregas e bloqueios.

Rentabilidade reutiliza a faixa de carteira após a contabilidade, sem outra
consulta ou outro cálculo. Seus destaques continuam no início e apontam para
a nova âncora. As âncoras existentes das demais seções permanecem válidas.
O modo de apresentação usa a mesma sequência; Quadro e Satisfação mantêm suas
próprias faixas.

O mix aparece uma única vez, com tabela acessível de serviço, quantidade de
contratos, valor mensal e participação. Nomes técnicos são apresentados com
rótulos legíveis. Os percentuais do mix usam formatação brasileira e os rótulos
da rosca usam quebra de linha real. Valor mensal contratado é identificado
como diferente de receita realizada.

Validação: testes de gráficos, resultados, leitura, contabilidade, telas irmãs,
serviços, design e CSP passaram. Há teste explícito da sequência nos modos
normal e apresentação e do conteúdo da tabela do mix. Chrome a 1440 e 390 px
confirmou a sequência, apenas um mix, ausência de transbordamento da página e
nenhuma exceção JavaScript. Não houve alteração de dados nem migração.
