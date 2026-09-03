# EXEC 22 · Orçamento anual e revisão — Onda 8 do benchmark GPS

> `/workspace/orcamento/` (código `15`). A onda que começou decidindo a **posse**,
> e só depois criou model.

---

## 22.1 A decisão que veio antes do model

O prompt desta onda era explícito: *"começa por decidir a posse, não por criar
model"*. E havia mesmo o que decidir — **já existiam dois orçados no produto**:

| Onde | O quê | Quem é dono |
|---|---|---|
| `financas.CentroCusto.orcamento_mensal` | um número por CC, **sem ano e sem histórico**, usado pela bandeja de aprovação | Workspace |
| `resultados.CompetenciaResultado.receita_orcada` / `custo_orcado` | por CC e mês, espelhado | **Sankhya** |

**Eles não se fundem.** O do Workspace é o **teto de operação**, que responde
*"isto cabe?"* na aprovação; o do Sankhya é o **orçado contábil**, que responde
*"o mês fechou onde deveria?"* nos Resultados.

Quando divergem, isso é **divergência entre fontes** — a regra que a ingestão já
criou —, e não algo que um `if` resolve. A restrição 5 do produto proíbe
exatamente isso, e o motivo é simples: o `if` teria razão até o dia em que não
tivesse, e ninguém saberia dizer quando esse dia foi.

A tela mostra os dois **lado a lado**, com a diferença, e não escolhe vencedor.

---

## 22.2 O defeito que sobrou, e que a onda corrige

O teto era **um campo que qualquer pessoa com `is_staff` editava no `/admin/`
sem deixar rastro**. Sem ano, sem histórico, sem autor, sem motivo.

Três models corrigem isso, todos em `financas`, porque a posse é dele:

| Model | O que é |
|---|---|
| `OrcamentoAnual` | o teto de um CC num ano: `rascunho` → `vigente` → `encerrado` |
| `LinhaOrcamento` | uma por mês. Doze por CC-ano |
| `RevisaoOrcamento` | `numero`, `motivo`, `autor`, e o **delta por mês** |

**Uma linha por mês, e não doze colunas.** Uma revisão quase sempre mexe em UM
mês — o reajuste entrou em julho, a obra escorregou para setembro. Com doze
colunas, cada revisão reescreveria a linha inteira e o delta teria de ser
reconstruído por diferença.

**O delta, e não o valor final.** "Quanto mudou?" é a pergunta que se faz numa
revisão orçamentária, e guardar o final obrigaria a reconstruir a série.

---

## 22.3 A regra do benchmark

> *"Só pode gastar se tiver recurso e fizer a revisão orçamentária."* (§3.9)

Implementada pelo lado que importa: **o teto vigente não muda sem revisão**.

O contrato **não oferece atalho**. `montar_orcamento()` recusa em vigente; não
existe `salvar_orcamento(codigo, ano, valores)` genérico, porque ele seria a
porta por onde a exigência se perde — bastaria alguém chamá-lo. A única entrada é
`revisar_orcamento()`, que exige motivo e grava autor e delta.

É o mesmo desenho do ADR-035 (quadro de metas aprovado não muda; reabrir é ato
registrado). O ato é legítimo; o que não pode é acontecer em silêncio.

---

## 22.4 As seis colunas

O benchmark (§3.7) usa `realizado | ajustes | realizado ajustado | orçado |
%RExOR | diferença`, e a coluna do meio é onde a operação declara o que já
aconteceu e ainda não bateu na contabilidade — *"sem ela a conversa vira briga
sobre o número em vez de decisão"*.

A nossa coluna do meio é o **comprometido**: aprovado e não pago. Mesmo papel,
com um número que o Workspace **possui** — ele nasce da aprovação, que é daqui.

| Orçado | Comprometido | Realizado | Consumido | Saldo | % |
|---|---|---|---|---|---|

**Consumido = realizado + comprometido**, e é ele que decide. Decidir por
realizado é como se estoura um orçamento sem ninguém perceber: o que foi aprovado
e ainda não pagou já é dinheiro gasto, só que invisível no extrato.

**Sem teto, "—" e nunca "0%".** Sem denominador não há percentual, e 0% seria
lido como folga total — a mesma regra de `/workspace/indicadores/`. E mês sem
teto **não estoura**: não há contra o quê.

---

## 22.5 O campo antigo fica

`CentroCusto.orcamento_mensal` continua existindo, como **fallback documentado**:

- centro de custo sem ano montado usa o campo;
- ano montado só até junho usa o campo em julho.

Arrancá-lo quebraria a bandeja de aprovação no dia do deploy, para todo centro de
custo que ainda não tivesse o ano. A grade mostra o **mesmo** número que a
bandeja usa — se mostrasse outro, as duas telas discordariam sobre o mesmo mês.

`semear_orcamento --aplicar` é a ponte: importa o teto avulso de cada CC para
doze linhas iguais no ano, já em vigor. É a "carga inicial importada" da §5 do
benchmark.

**Doze iguais, e não uma curva:** inventar sazonalidade seria inventar dado. A
primeira revisão de verdade é quem corrige julho.

**Centro sem teto é pulado.** Criar um ano de zeros seria pior: a bandeja passaria
a dizer "0% de folga" onde hoje diz, corretamente, "sem orçamento definido".

---

## 22.6 A regra que a onda ligou

`cc-sem-orcado-e-o-inverso` nasceu na Onda 4 **registrada e desligada**, com o
texto: *"Só passa a valer quando o orçamento existir aqui dentro."* Agora ele
existe.

Ela ligou por **migração de dados**, e não pela semeadora. `semear_regras_excecao`
nunca reativa regra desligada — desligar quase sempre acontece no meio de um
incidente, e a semeadora roda no deploy seguinte. Esta regra é outro caso: ela
não foi desligada por ninguém, **nasceu** desligada, com a condição escrita. Uma
migração liga uma chave, uma vez, com o motivo versionado — e continua
respeitando quem a desligar depois.

**As duas direções, na mesma regra:**

- **no ERP e fora do orçamento** — o Sankhya lançou realizado num CC que ninguém
  orçou. *A linha parece estouro e não é*;
- **no orçamento e fora do ERP** — orçamos um CC que o ERP não conhece. *O teto
  existe e nunca será consumido, e a folga é falsa*.

São o mesmo defeito — um cadastro que não bate — e separá-las faria alguém
corrigir metade. Ela nasce com `exige_plano`, porque o benchmark é explícito:
*"a conciliação de códigos precisa ser uma regra de exceção, não um cuidado"*.

---

## 22.7 Quem vê o quê

| Papel | Permissão | O que alcança |
|---|---|---|
| `financeiro`, `diretoria` | `fin.orcamento.ler/revisar.global` | todos os CCs, e revisa |
| `gestor` | `fin.orcamento.ler.departamento` | o CC da própria lotação, **sem revisar** |

Quem não responde por CC nenhum recebe **403**, e nunca uma grade de zeros: uma
grade zerada faz a pessoa achar que a empresa não gastou nada.

Centro de custo alheio devolve **403 e não 404** — dizer "não existe" a quem
apenas não alcança transformaria a tela num verificador de códigos.

**Permissão sem lotação também é 403.** Devolver a empresa inteira aí seria como
uma permissão restrita vira global por acidente de cadastro — é a mesma proteção
de `resultados.escopo_de()`.

---

## 22.8 Os três testes que protegem a onda

1. `test_o_teto_vigente_nao_muda_sem_revisao` — `montar_orcamento` recusa em
   vigente, e o valor de julho continua o mesmo.
2. `test_os_dois_orcados_aparecem_lado_a_lado_e_nao_se_fundem` — 10.000 nosso,
   12.000 do Sankhya, diferença −2.000, e nenhum código escolhendo.
3. `test_a_grade_e_de_quem_responde_pelo_centro_de_custo` e
   `test_quem_nao_responde_por_centro_de_custo_recebe_403`.

Mais 61, entre eles: campo em branco é "não mexi" e não "zerei"; vírgula decimal
aceita; rascunho sem linha não vigora; mês sem linha cai no campo avulso; a
semeadora não toca no que já existe.

---

## 22.9 ADRs

### ADR-036 · O teto de operação e o orçado contábil não se fundem

**Contexto:** o produto tinha dois orçados, e a tentação era eleger um como "o
orçamento" e derivar o outro.

**Decisão:** os dois permanecem, com donos declarados. `financas` responde o teto
de operação; `resultados` espelha o orçado contábil. A tela mostra os dois lado a
lado, com a diferença, e a conciliação de códigos é uma **regra de exceção**.

**Consequência:** nenhuma linha de código escolhe vencedor entre duas fontes — é
a restrição 5 do produto, e o mesmo desenho de `RegraPrecedencia` na ingestão. O
preço é que a empresa precisa olhar dois números; o ganho é que ela **sabe** que
são dois, em vez de descobrir isso numa auditoria.

### ADR-037 · O teto vigente muda por revisão, e a revisão exige motivo

**Contexto:** editar as doze linhas de um orçamento vigente seria trivial de
implementar, e é o que o `/admin/` já permitia sobre o campo antigo.

**Decisão:** `OrcamentoAnual` só é editável em `rascunho`. Vigente muda por
`RevisaoOrcamento`, com motivo obrigatório, autor e delta por mês. O contrato não
expõe caminho alternativo, e o `/admin/` tem `situacao` e as revisões em somente
leitura.

**Consequência:** "quem mudou o teto de julho, quando e por quê" passa a ter
resposta. O preço é um formulário a mais entre a decisão e o número; é o preço
certo — antes desta onda a resposta era "não sei", e orçamento sem essa resposta
é uma planilha com aparência de sistema.
