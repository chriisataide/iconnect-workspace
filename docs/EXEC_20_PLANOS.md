# EXEC 20 · Plano de ação com limiar — Onda 6 do benchmark GPS

> `/workspace/planos/` (código `13`). A regra dos 10% generalizada: quatro
> regras de exceção passam a **cobrar resposta**, e o desfecho é conferido pela
> própria regra no vencimento.

---

## 20.1 Limiar não é alerta: é obrigação

No Portal GPS, **margem abaixo de 10% exige justificativa e plano de ação**. O
mesmo desenho aparece no NPS: todo detrator gera plano com prazo acordado com o
cliente, e **a pesquisa é refeita ao fim do prazo**. O painel de Tratativas mede
a efetividade em quatro estados.

A Onda 4 entregou a metade que encontra: dezoito regras, cada uma com uma
contagem e um responsável. Faltava onde guardar a **resposta** — por que
aconteceu, o que será feito, quem faz e até quando. Sem isso, uma regra que
dispara todo mês dispara todo mês para sempre, e a lista vira um relatório que
se aprende a rolar até o fim.

## 20.2 As quatro regras que passam a cobrar

| Regra | Prazo | Quem responde |
|---|---|---|
| `margem-abaixo-de-10` | 30 dias | `financeiro` |
| `detrator-sem-tratativa` | 30 dias | `operacao` |
| `projeto-bloqueado` | 15 dias | `operacao` |
| `cc-sem-orcamento` | 30 dias | `financeiro` |

`margem` e `detrator` são as duas que o benchmark nomeia. `projeto-bloqueado`
tem o prazo curto porque um projeto parado há 15 dias com plano de 30 ficaria
parado 45. As outras catorze continuam avisando sem cobrar — limiar em toda
regra transformaria o painel numa fila de formulários.

---

## 20.3 O desfecho é reverificado, e nunca declarado

É a decisão que sustenta a onda inteira.

Quando o prazo vence, `verificar_planos` roda **a mesma regra** e procura **a
mesma chave de ocorrência**. Se ela ainda está lá, o plano fecha como *não
resolvido* — mesmo que o responsável tenha escrito que resolveu. O texto de quem
fechou fica junto, porque é o que a pessoa entendeu; ele só não decide.

Isso não é desconfiança do responsável. É o único jeito de o número da tela
significar alguma coisa: **um painel em que o próprio interessado declara o
sucesso mede quem preenche formulário.**

O botão *Fechar o plano* faz a mesma coisa, na hora. A tela avisa antes do
clique, e não depois.

### Fonte fora do ar não fecha plano nenhum

A verificação fica registrada como **não avaliada** e o plano continua aberto.
Sem isso, um conector caído fecharia como resolvido todo plano que dependesse
dele — um mês inteiro de metas batidas por causa de uma credencial vencida.

É a mesma distinção do painel de exceções entre *zero* e *não avaliada*, e o
mesmo motivo: somá-las faz uma fonte caída parecer um mês tranquilo.

### A carência de dois dias

O cron pode ter ficado fora do ar. Fechar um plano no primeiro dia em que a
máquina voltou, com a fonte ainda subindo, produziria um desfecho aleatório — e
desfecho aleatório num registro que ninguém revisa é pior que desfecho nenhum.

---

## 20.4 Os quatro estados, e a dívida

| Estado | De onde vem |
|---|---|
| em andamento **no prazo** | `situacao=aberto` e `prazo >= hoje` |
| em andamento **fora do prazo** | `situacao=aberto` e `prazo < hoje` |
| **resolvido** | a reverificação não achou mais a ocorrência |
| **não resolvido** | a reverificação achou de novo |

Dois guardados, dois derivados do relógio. Um campo `atrasado` precisaria de um
processo para mantê-lo, e o plano ficaria "no prazo" até o cron rodar — que é
exatamente quando ninguém está olhando.

Antes dos quatro vem a **dívida**: ocorrência de regra com limiar que ainda não
tem plano. A palavra é escolhida. "Pendência" é o que se diz de coisa que talvez
alguém faça; aqui a obrigação já existe, e o que falta é a resposta.

**A efetividade** — quantos por cento dos fechados resolveram — é o que o painel
de Tratativas do benchmark mede. Sem plano fechado nenhum ela **não aparece**:
uma porcentagem sobre zero seria 0%, e 0% de efetividade é uma afirmação sobre
um trabalho que não houve.

---

## 20.5 Quem lê e quem responde

**Ler não ganhou permissão nova.** Quem vê a regra vê os planos dela — é a
resposta que a Onda 4 já deu, e uma segunda regra de visibilidade para a mesma
lista divergiria da primeira. Quem não acompanha regra nenhuma com limiar recebe
**403**, e não uma tela de zeros.

**`pla.responder`** para abrir, editar e fechar — **e** o papel que atende a
regra. Assinar o que a empresa vai fazer sobre um contrato deficitário é ato de
quem responde por ele.

| Papel | Escopo | O que alcança |
|---|---|---|
| `diretoria` | `.global` | qualquer regra, inclusive as sem papel atribuído |
| `financeiro` | `.departamento` | margem e centro de custo sem orçamento |
| `operacao` | `.unidade` | detrator e projeto bloqueado |

Regra **sem papel** — as que vigiam o mecanismo, como `fonte-atrasada` — exige
escopo global para responder: um plano sobre carga atrasada é da operação de
dados, e não de quem passou pela tela.

O `select` de responsável oferece **os titulares do papel da regra**, e não a
empresa inteira: o responsável por um plano de margem é quem responde por
margem, e uma lista com todo mundo faz a escolha cair em quem estiver mais perto
no alfabeto. Papel sem ocupante é um achado — a tela diz isso, e o plano fica
com quem registrou.

---

## 20.6 Um plano aberto por ocorrência — e quantos fechados forem preciso

A restrição de unicidade é **condicional**: `(regra, ocorrência)` único enquanto
`situacao='aberto'`.

Dois planos abertos para o mesmo contrato produzem duas versões do que a empresa
vai fazer, e a reverificação fecharia as duas com o mesmo desfecho — um deles
ganhando crédito por trabalho que não fez.

Fechados podem repetir, e **devem**: a margem cair de novo em março depois de um
plano cumprido em janeiro é justamente o que o histórico precisa mostrar.

Pelo mesmo raciocínio, `VerificacaoPlano` guarda a **série** e não a última: o
comando roda todo dia, e é a série que revela o padrão mais caro de todos — o
problema que se resolve e reaparece.

---

## 20.7 O que é congelado

`titulo` e `detalhe` são copiados da ocorrência no dia da abertura. Reler a regra
para reconstruí-los faria um plano de março mudar de assunto em setembro, quando
o contrato mudasse de nome. É a mesma decisão do carimbo da ATA (ADR-030).

`regra_chave` e `ocorrencia_chave` são **texto**, e nunca FK. O sujeito da
exceção mora em outro app — às vezes num espelho que a próxima carga reescreve —,
e uma FK morreria junto com ele. O plano é registro de uma decisão tomada, e
sobrevive à regra que o cobrou.

E, como em `ResultadoExcecao.chaves`: **a chave nunca identifica pessoa**.

---

## 20.8 Os três testes que protegem a onda

1. `test_o_desfecho_e_reverificado_e_nao_declarado` — fechar escrevendo
   "resolvido, pode fechar", com a regra ainda disparando, grava *não resolvido*.
2. `test_ocorrencia_que_exige_plano_e_nao_tem_aparece_como_divida` — e o ciclo
   inteiro: a dívida some quando o plano abre e **volta** quando ele fecha sem
   resolver.
3. `test_fonte_fora_do_ar_nao_fecha_plano_nenhum` — a verificação fica não
   avaliada e o plano continua aberto.

Mais 51, entre eles: dois planos abertos para a mesma ocorrência são recusados e
dois fechados são permitidos; plano sobre ocorrência que sumiu é recusado; regra
que estoura não derruba o comando; toda regra com limiar tem avaliador escrito.

---

## 20.9 ADRs

### ADR-032 · O limiar é campo da regra, não uma tabela

**Contexto:** um modelo `Limiar` apontando para `RegraExcecao` seria o desenho
óbvio, e permitiria vários limiares por regra.

**Decisão:** dois campos em `RegraExcecao` — `exige_plano` e `prazo_do_plano`.

**Consequência:** não existe segunda verdade sobre quais regras são cobradas.
Uma tabela permitiria um limiar apontando para uma regra desligada, ou dois
limiares para a mesma regra com prazos diferentes — e a pergunta "esta regra
cobra plano?" passaria a ter duas respostas possíveis. É o ADR-026 outra vez: a
configuração da regra mora com a regra.

O preço é não poder ter dois limiares na mesma regra. Se um dia for preciso —
margem abaixo de 10% em 30 dias, abaixo de 5% em 10 —, o caminho é uma **segunda
regra**, que é o que ela é: outra severidade, outro prazo, outra lista.

### ADR-033 · O desfecho é reverificado, e nunca declarado

**Contexto:** o desenho mais simples é um botão "marcar como resolvido", e ele
funcionaria — para quem preenche.

**Decisão:** fechar um plano roda a regra de novo sobre a mesma chave de
ocorrência. Se ela ainda encontra, o plano fecha como *não resolvido*.

**Consequência:** a efetividade da tela mede resultado, e não esforço. O preço é
que a regra precisa ser **determinística sobre a mesma chave** — o que já era
exigido pelo histórico de `ResultadoExcecao`, e é testado.

O segundo preço, mais caro: **fonte fora do ar não pode fechar plano**. Um
conector caído fecharia como resolvido tudo o que dependesse dele, e o mês
apareceria como o melhor do ano. Por isso a verificação tem um terceiro estado —
*não avaliada* —, e ele deixa o plano aberto.

Também é por isso que **não existe** botão de "marcar como resolvido" na tela de
exceções, decidido lá na Onda 4 e mantido aqui: resolver é trabalho de gente, e
o produto confere.
