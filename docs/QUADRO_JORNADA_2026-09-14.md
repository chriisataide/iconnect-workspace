# Quadro e jornada: indicadores e perfuração

## Comparação, cobertura e ações

A análise inclui comparação com o mês anterior, mesmo quando o período escolhido
é de um mês. Esse mês adicional é consultado para comparação e não é acrescentado
ao gráfico do período. Registro ausente e valor zero recebem tratamentos distintos;
uma base anterior zero não gera variação percentual.

O ranking pode usar volume ou horas por 100 horas normais. A proporção de cada
grupo é calculada sobre as somas, não sobre a média dos percentuais dos contratos.
Grupos sem base positiva são excluídos apenas da visão proporcional, com aviso.
Filtros e modo de ranking são preservados na navegação e apresentação.

Cada contrato com apontamentos tem uma abertura de detalhe com evolução mensal,
comparação e composição das HE em serviço extra, ineficiência e sem classificação.
Diferenças entre a soma das classificações e a HE total são sinalizadas. A memória
da página reconhece os detalhes abertos e suas âncoras de leitura.

A cobertura conta contratos da carteira do recorte com pelo menos um registro
vinculado no mês e lista os sem registro. Ela indica presença, não certifica a
completude da importação. A frase de leitura distingue a variação geral das maiores
altas entre contratos que possuem dados comparáveis nos dois meses.

O registro de ações reutiliza concentrações com responsável, prazo e próximo passo.
Ações existentes do contrato são vinculadas ao detalhe. Permissão `eco.concentrar`
continua obrigatória. Após salvar/atualizar/encerrar, o retorno ao Quadro preserva
seu recorte; apenas URLs relativas das duas páginas permitidas são aceitas.

Validação adicional: 92 testes Python e 10 testes de navegação passaram. A
renderização Django com banco copiado em memória verificou volume, proporção,
contrato e apresentação, incluindo formulário de ação e IDs únicos. Nenhuma linha
contratual de teste foi gravada no banco real. Sem migração adicional. A limitação
de inspeção visual descrita ao final permanece.

A página Quadro abre com dez indicadores mensais de horas, seus percentuais
sobre horas normais, evolução mensal de HE de ineficiência, abono, desconto e
HE sem classificação, e rankings por área, centro de custo e contrato.
O usuário escolhe o tipo de hora do ranking e clica na barra ou no nome da
tabela acessível para aplicar o filtro. Mês e período são preservados. O botão
de visão geral limpa os filtros de localização, respeitando a autorização.
Efetivo, turnover, movimentação e pendências permanecem em consulta recolhida.

## Granularidade e cobertura

O espelho anterior contém somente apontamentos mensais por centro de custo.
A migração `resultados.0010_apontamento_contrato` adiciona um contrato opcional
e permite registros separados por contrato/CC/mês. Foi aplicada localmente.
Não foram distribuídas horas históricas nem criados apontamentos no banco real.

Quando coexistem o total de CC e seus detalhes contratuais, o total prevalece
nos indicadores gerais e na visão por CC. A visão por contrato e área considera
somente linhas vinculadas. Por isso ela pode representar uma cobertura parcial,
explicitada na interface. Filtrar por contrato nunca atribui a ele o total
não discriminado de seu centro de custo. As áreas vêm do cadastro dos contratos.
Meses sem registro permanecem ausentes, não viram zero. O saldo do banco de
horas aparece como saldo mensal, não como soma de saldos entre competências.

O quadro de efetivo também é agregado por CC e não é mostrado como se fosse
de um contrato ao filtrar área/contrato. A fonte não fornece apontamentos
diários, intrajornada nem hora reduzida; esses dados não foram inventados.

## Como fornecer o vínculo

O carregador CSV aceita a coluna opcional `contrato` em `apontamento.csv`, com
o código de um contrato já cadastrado. Exemplo de registro mensal:

```csv
chave_externa,contrato,centro_custo,ano,mes,horas_normais,he_total,he_ineficiencia
jornada-CT100-202609,CT-100,1042,2026,9,1760,80,20
```

Sem a coluna, a carga mantém o total por CC. Código de contrato inexistente é
recusado, para que um detalhe não seja confundido com total de CC. Cada registro
mensal precisa de uma chave externa distinta. A consulta Sankhya atual ainda
não solicita o código do contrato: para preencher automaticamente esses rankings
nessa integração, a view de origem e seu mapeamento precisam fornecer o vínculo.
O código não adivinha o nome dessa coluna externa.

## Validação

191 testes passaram: provedores, recortes, total versus detalhe, modelos,
carregador, conversão, telas irmãs, serviços, design e CSP. Renderização real
com Django foi verificada com cópia do banco em memória, nos modos geral,
filtrado e apresentação; uma linha contratual de teste existiu apenas nessa
cópia. Não há migrações pendentes de geração nem erros no diff.

A inspeção visual em navegador não foi realizada nesta mudança. A abertura da
prévia havia sido bloqueada pela revisão automática por limite de uso da
ferramenta; as verificações acima não usam navegador nem rede.
