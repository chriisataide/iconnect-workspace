# Benchmark — Portal GPS / GPS 360

Leitura do documento `15_07_2026 - Benchmark - GPS.docx` (texto + 99 capturas de
tela), organizada para decidir o que entra no **iConnect Workspace**, o que
pertence ao **iConnect Platform** e o que não deve ser copiado.

---

## 1. O que o benchmark é

Um portal corporativo do Grupo GPS que reúne, atrás de uma única casca, os
relatórios de Power BI e os sistemas transacionais da empresa. A entrada tem
três elementos e nada mais:

- **árvore "Sistemas"** à esquerda, com a taxonomia numerada da empresa;
- **busca global** no topo, com prefixos declarados no placeholder — *"Digite P:
  para pessoas ou D: para documentos"*;
- **identidade** no canto superior direito.

No site institucional, o acesso é um menu **"Extranet"** com quatro destinos:
*GPS 360 – Cliente*, *GPS 360 – Fornecedor*, *Gerenciador Eletrônico* e *Portal
GPS*. O documento anota a intenção equivalente para a ADB: botão com as sub-abas
**"ADB Cliente"**, **"ADB Fornecedor"** e **"Portal ADB"** — ou seja, três
públicos, três produtos, uma marca.

---

## 2. A taxonomia numerada

Todo módulo e toda tela têm um código estável. As pessoas conversam pelo número:
"me manda a 02.1.4", "a 7.8 apontou três contratos". Isso é vocabulário
organizacional, não enfeite.

| Cód. | Módulo | Telas relevantes |
|---|---|---|
| 00 | Orientações / Relatório de Acompanhamento | orientações gerais, reforma tributária, onboarding de Power BI |
| 01 | Apresentação de Resultado | 01.01 Ciclo Mensal, 01.02 Ciclo Trimestral |
| 02 | Medição e Liquidez | 02.1.1 Medições em Aberto (M-2), 02.1.2 (D0), 02.1.3 Geral, 02.1.4 Contas a Receber (D-10), 02.1.5 (D-1), 02.1.6 Retenções, 02.1.7 Medições dinâmica, 02.1.8/02.1.9 Exposição por Cliente, 02.2 Medições (relatório V2, conferência, mapa e prévia de receita), 02.4 Faturamento (calendário NFs emissão/vencimento), 02.5 Juros |
| 03 | Operacional | regulatório, material controlado |
| 04 | Ocorrências | 04.1 Ocorrências, 04.2 SSMA, 04.3 NPS, 04.4 Defesa de Território, 04.5 Score PEC |
| 05 | Comercial | negócios, CRM, 05.3 Oportunidades, PEC x CTB, índice de renovação, perdas e conquistas, forecast, gestão PEC, 05.10 Crescimento Orgânico |
| 06 | Processos Trabalhistas | RTs consolidada, APT em andamento, títulos, painel de indicadores, turnover x RTs, CNDT |
| 07 | Resultado Econômico | 7.1 por PEC, 7.2 por CR, 7.3–7.5 dinâmicas RE x OR, 7.6 ATA de Resultado, 7.7 comparativo, 7.8/7.9 Análise de Resultado |
| 08 | Pessoas | 08.1 turnover, absenteísmo, MRHs, folha (valores/horas/por funcionário), cotas PCD e aprendiz; 08.2 Processo Folha (rescisão, férias, conciliação ponto x folha, dissídio); 08.3 Benefícios (VR, VA, AM, VT, auditorias, inconsistências, seguro de vida) |
| 09 | Compras | por produto, médias, valor mínimo, malote, revenda, contratos de fornecedores, combustível, compras x efetivo ativo |
| 10 | Relatórios Corporativos | — |
| 11 | Processos Não Trabalhistas | cíveis, criminais, regulatórios, tributários |
| 12 | Financeiro | contas a pagar (líquido/bruto/saldo), calendário de NFs, CAR (a vencer, emissão, vencimento, baixa, saldo em aberto, saldo inicial), saldos bancários |
| 13 | Horas Extras | 13.1 apontamentos (analítica, sintética, cobertura de ausências, compensação de faltas, conferência de escala, origem, conciliação ponto x folha, relógios, banco de horas), 13.2 Gestão de Ponto, 13.5 Conformidade Legal |
| 14 | GPSvc | 14.1 Documentos Pendentes (contratos, folha de ponto, cartão de assinatura) |
| 15 | MRH | currículos, vagas, admissão RH/DP, férias, rescisão, movimentação interna, painéis |
| 16 | GPS Vista | 16.1.3.1 Visita Operacional da Liderança, 16.1.5 Íris (ponto eletrônico), 16.1.6 Tratativas NPS/PTQ |
| 17 | PEC | contrato, proposta, receita e compras PEC x contabilidade, AM/VR/VA/verbas PEC x folha, controle de vencimento PEC x CR e x NF, PEC Efetivo Futuro |
| 18 | Performance Contratual | compromissos assumidos, avaliações, performance contratual |
| 20 | Orçamento | anual e revisão orçamentária |
| 99 | Manutenção | manutenção de destaques, ajustes, déficit, documentos de apoio, inadimplência, Portal GPS360, monitoramento do Power BI, observações PEC, variação de receita |

Fora da numeração, a mesma árvore expõe os transacionais: Gestão Indireto,
Jurídico, P&O, Contratos e Propostas, Orçamento, Regulatório e Treinamento,
Atendimento e Acompanhamento, Relatórios e Consultas, CRM, Gestão de Pessoas,
Gestão Operacional, Folha de Ponto, Sistemas Mobile, Malote Eletrônico,
Assinatura de E-mail, Controle de Acesso, Clientes e Fornecedores, Centro de
Custo e Estudo de Custo.

---

## 3. Os padrões que valem ser roubados

### 3.1 O ciclo de planejamento é uma pasta ordenada

A pauta da reunião **é** o produto. A pasta `01.01 – Ciclo de Planejamento
Mensal` tem dezesseis itens numerados na ordem em que serão apresentados:

```
CP01 – 01.1  Destaques / Concentrações      CP09 – 16.1.6 Tratativas NPS/PTQ
CP02 – 01.2  Apresentação                   CP10 – 16.1.3.1 Visita Oper. Liderança
CP03 – 13.1.2 Apontamentos (sintética)      CP11 – 16.1.5 Íris
CP04 – 04.4  Defesa de Território           CP12 – 14.2.3 Treinamentos
CP05 – 02.1.1 Medições em Aberto (M-2)      CP13 – 04.5 Score PEC
CP06 – 02.1.4 Contas a Receber (D-10)       CP14 – 1.10 PA
CP07 – 01.4  PEC Efetivo Futuro             CP15 – 07.8 Análise de Resultado
CP08 – 04.3  Dashboard NPS                  CP16 – 07.1 Resultado por PEC
```

O ciclo trimestral é um subconjunto de nove itens, para plateia mais sênior
(Presidente/VP + Diretores + Gerentes) contra a mensal (Dir. Exec. + Diretores +
Gerentes + coordenadores do programa de líderes). Mesma biblioteca de telas,
recorte diferente por público.

### 3.2 Gestão por exceção — o padrão mais aproveitável do documento

O "Painel Gestão de Efetivo" não é um dashboard: é uma **lista de regras**, cada
uma com uma contagem, que expande para a grade dos registros que a violaram.

```
MRH FÉRIAS EM ATRASO OU ATRASO > 30 DIAS                1 registro
EFETIVO ATIVO COM AUSÊNCIA > 5%                       146 registros
EFETIVO ATIVO COM MAIS DE 3 ADVERTÊNCIAS              117 registros
EFETIVO COM EXPERIÊNCIA VENCENDO NOS PRÓXIMOS 30 DIAS 408 registros
EFETIVO COM ASO VENCIDO                             2.556 registros
EFETIVO COM RECICLAGEM VENCIDA                         49 registros
EFETIVO COM MAIS DE 33 HORAS EXTRAS NO MÊS             10 registros
EFETIVO COM ERRO DE JORNADA (SISTEMA OPERACIONAL)   1.106 registros
```

A grade de detalhe traz o **e-mail do gestor responsável** em cada linha — a
exceção já nasce endereçada. Carimbo no topo: `ÚLTIMA ATUALIZAÇÃO: D-1`.

### 3.3 Limiar que gera obrigação

Não é alerta, é regra: **margem abaixo de 10% exige justificativa e plano de
ação** (7.8 / 7.1). O mesmo desenho aparece no NPS: **todo detrator gera plano de
ação com prazo acordado com o cliente**, e a pesquisa precisa ser refeita ao fim
do prazo. O painel de Tratativas mede a efetividade em quatro estados —
*em andamento no prazo*, *em andamento fora do prazo*, *alterado para promotor*,
*mantido como detrator* — e quebra por diretor executivo.

### 3.4 Score composto com faixas de governança

O **Score PEC** é uma nota 0–100 por contrato, com ponteiro e distribuição por
faixa (vermelho / amarelo / verde, com valor de ROB e quantidade em cada). Os
componentes: deficitário, CAF, turnover, absenteísmo, MRH, PTQ, NPS,
compromissos fora do prazo, GPC, cumprimento de tarefas.

As **layers** convertem porte em obrigação, e não apenas em rótulo:

| Layer | ROB 6 meses | Obrigação |
|---|---|---|
| 1 | até 300k | sem apresentação de GPC |
| 2 | 300k a 600k | sem apresentação de GPC |
| 3 | acima de 600k | GPC mensal, bimestral ou trimestral + análise de cumprimento de tarefas |

A tela ainda declara a **amostra mínima** para o contrato ser avaliado (`> 2
meses` de ROB por layer) — nota sem amostra não é nota.

### 3.5 O frescor do dado é parte do nome da tela

`Medições em Aberto (M-2)`, `(D0)`; `Contas a Receber (D-10)`, `(D-1)`. Quem abre
a tela já sabe de quando é o número. Reforçado pelo carimbo em vermelho no
cabeçalho: `Atualização: 18/08/2026 08:45:10`.

### 3.6 Barra de filtros padronizada

O mesmo conjunto numerado se repete em toda tela: `1 NEGOCIO`, `2 GRUPO DE
CLIENTE`, `3 SEGM_CLIENTE`, `4 REGIONAL`, `5 DATA_CR`, `6 EMP_M&A`, `7
EMP_ORIG`, `8 SOLUCAO`, `9 PEC`, `10 CONQ/PERDA`, `11 REGIME`, `12 DEFICITARIO`,
`13 DEADLINE1`, `14 DEADLINE2` — mais o seletor de competência hierárquico
(ano › mês). Aprende-se uma vez, usa-se em tudo.

### 3.7 Realizado x Orçado com a coluna do meio

A dinâmica não é `realizado | orçado | variação`. São seis colunas: **valor
realizado, ajustes (potencial do contrato), realizado ajustado, valor orçado,
%RExOR, diferença**. A coluna "ajustes" é onde a operação declara o que já
aconteceu mas ainda não bateu na contabilidade — sem ela a conversa vira briga
sobre o número em vez de decisão.

### 3.8 Perfil, metas e desenvolvimento (P.A / P.M / P.P)

Painel da pessoa com centro de custo, líder, diretor regional, diretor
executivo, tempo de função, situação na folha e histórico de ciclos por ano com
status (`APROVADO`). Três abas:

- **Resumo** — o negócio, prioridades, estratégia para condução do negócio;
- **Quadro de Metas** — meta com *grupo* (ex.: Metas Financeiras), *descrição*,
  *tipo de cálculo* (diretamente proporcional), *lógica de pontuação*
  (ilimitada), *detalhamento* e **Fator 1 / Fator 2** (ex.: `EBITDA RE` ÷
  `EBITDA OR`) — a meta é auditável porque a fórmula está na tela;
- **Plano de Desenvolvimento** — responsabilidades, áreas de interesse,
  aspirações de curto (1–2 anos) e longo prazo (3–5 anos), e ações com mês/ano.

### 3.9 Outros mecanismos pontuais

- **Conferência de medição** — compara o mês com o anterior antes de faturar,
  para o erro cair mês a mês.
- **Conformidade legal do ponto** — teto de 3 FT no mês, para não descaracterizar
  a escala 12x36; folhas de ponto pendentes; contratos pendentes de assinatura.
- **Orçamento com revisão obrigatória** — *só pode gastar se tiver recurso e
  fizer a revisão orçamentária*.
- **Malote eletrônico** — aprovações em geral, com destaque para combustível.
- **Estudo de Custo** — "Criar Solicitação" + "Acompanhamento" convivendo dentro
  do portal de BI: o pedido nasce onde o número foi visto.
- **Módulo 99 – Manutenção** — as telas que consertam o dado (ajustes, déficit,
  inadimplência, observações, variação de receita) são um módulo declarado, não
  um back-office escondido.
- **Visita operacional da liderança** — programadas × realizadas × atrasadas ×
  não realizadas, por diretor executivo e por grupo de cliente, com série diária.

---

## 4. O que **não** copiar

| Do benchmark | Por quê não |
|---|---|
| Árvore de mais de cem itens como entrada | É exatamente o *app launcher* que o Workspace recusou ao empurrar "Aplicativos" para a última faixa da home. A taxonomia serve como **endereçamento**, não como porta de entrada. |
| CPF e e-mail pessoal em grade, com "Exportar para Excel" | Dado pessoal em lista exportável por qualquer um que abra a tela. O Workspace já trata anexo como risco (fora de `MEDIA_ROOT`); grade de CPF é o mesmo problema com outra roupa. |
| Tela sem dono | Várias telas do benchmark existem sem responsável declarado. No Workspace, cada painel precisa de escopo — a regra de `/indicadores/` (403, nunca tela zerada) vale para tudo que for novo. |
| Duplicidade na própria árvore (`08.2.4` aparece duas vezes, `05.6` duas vezes) | Sintoma de taxonomia sem dono. Se o código é vocabulário, ele precisa de unicidade garantida por constraint. |
| Trazer NPS, medições, CRM e ocorrências para cá | É operação de cliente. Pertence ao **iConnect Platform**. Trazer para o Workspace refaz o acoplamento que custou 881 lotações órfãs. |

---

## 5. Fronteira: quem é dono de quê

No GPS os dois produtos são um só, e o portal lê tudo do mesmo banco. Na ADB há
quatro sistemas distintos, e a pergunta certa não é "o que é do Workspace" —
é **quem é dono do dado** e **por onde ele entra**.

O Workspace não é dono de quase nada do que essa tela mostra. Ele é dono da
**vida corporativa** e do **espelho** dos demais.

| Assunto | Dono do dado | Como entra no Workspace |
|---|---|---|
| Ciclo de planejamento, pauta, ATA | Workspace | nativo |
| Solicitações, aprovações, fila, reservas, correspondência | Workspace | nativo |
| Metas, avaliação, PDI | Workspace | nativo |
| Documentação e leitura obrigatória | Workspace | nativo |
| Painel de exceções e planos de ação | Workspace | nativo |
| Receita, custo, margem, EBITDA, contábil | **Sankhya** | `conector_sankhya` |
| Folha, ponto, benefícios, admissão, rescisão | **Sankhya** | `conector_sankhya` |
| Compras e contas a pagar | **Sankhya** | `conector_sankhya` |
| Orçamento anual e revisão | **Workspace** (`financas`) | nativo; carga inicial importada |
| Projetos, marcos, responsáveis, bloqueios | **monday.com** | `conector_monday` |
| Contratos, vigência, carteira | **Platform** (ou Sankhya) | `conector_platform` |
| NPS, satisfação, tratativas de detrator | **Platform** | `conector_platform` |
| Ocorrências, atendimento, medições de campo | **Platform** | não entra — fica lá |
| Diretório de pessoas, gestor, departamento | **Entra ID / M365** | depois do SSO (ADR-013) |
| ASO, reciclagem, CNV, advertências | **HRIS** | depois do SSO |

Três regras que essa tabela impõe e que valem mais que a tabela:

1. **Detalhe operacional não atravessa.** A tela de resultados consome
   consolidado. Ocorrência por ocorrência, medição por medição e ticket por
   ticket continuam morando no Platform. Trazer o detalhe refaz o acoplamento
   que custou 881 lotações órfãs.
2. **Todo dado espelhado carrega procedência.** Fonte, chave externa e instante
   da carga em cada linha. Espelho sem procedência é boato com aparência de
   relatório.
3. **Duas fontes vão discordar.** Sankhya e monday sobre valor de projeto;
   Sankhya e Platform sobre vigência de contrato. A precedência é declarada por
   campo, em tabela, e a divergência acima do limiar aparece na tela — não é
   resolvida dentro de um `if`.
4. **O realizado e o orçado vêm de casas diferentes.** O realizado é do Sankhya;
   o orçado é do `financas`, aqui dentro. A comparação junta os dois por
   `(centro de custo, ano, mês)` — e isso só funciona se o código do centro de
   custo for idêntico dos dois lados. Código divergente não dá erro: produz uma
   linha com realizado e sem orçado, que parece estouro de orçamento e não é.
   A conciliação de códigos precisa ser uma regra de exceção, não um cuidado.

---

## 6. Ordem sugerida de adoção

1. **Vocabulário e frescor** — código estável por módulo e tela, carimbo de
   atualização **por bloco** (fontes com cadências diferentes na mesma tela) e
   prefixos de busca. Custo baixo, muda a conversa da empresa.
2. **Ingestão multi-fonte** — conectores, espelho com procedência, regra de
   precedência e registro de carga. Sem tela; é a espinha do resto.
3. **Apresentação de Resultados** — a tela que a diretoria pediu, mais a tela
   irmã de fontes, que responde "de onde vem esse número?".
4. **Painel de exceções** — as regras do próprio Workspace mais as que a
   ingestão destravou.
5. **Ciclo de planejamento e ATA** — a pauta como objeto do produto.
6. **Plano de ação com limiar** — generalização da regra dos 10%.
7. **Metas, avaliação e PDI** — com os fatores apontando para o espelho.
8. **Orçamento** — começa por decidir a posse, não por criar model.
9. **Segmentação de público (ADB Cliente / Fornecedor / Portal)** — decisão de
   marca e roteamento; provavelmente um ADR e um tile, não um módulo.
