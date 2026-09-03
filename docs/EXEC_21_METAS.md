# EXEC 21 · Metas, avaliação e PDI — Onda 7 do benchmark GPS

> `/workspace/metas/` (código `14`) e `/workspace/metas/desenvolvimento/`
> (`14.1`). A meta é auditável porque a fórmula está na tela — e os fatores
> apontam para o espelho.

---

## 21.1 A meta é auditável porque a fórmula está na tela

No Portal GPS, cada meta traz *grupo*, *descrição*, *tipo de cálculo*, *lógica de
pontuação*, *detalhamento* e **Fator 1 / Fator 2** — `EBITDA RE` ÷ `EBITDA OR`.

Não é um número que alguém digitou no fim do ciclo: é uma conta que aponta para
o dado. Aqui os fatores apontam para o **espelho**, pelo catálogo de
`workspace/services/fatores.py`.

`Meta.fator_1` guarda uma chave — `"ebitda"` —, e nunca um valor. Guardar o valor
faria a meta virar uma planilha bonita: o número entraria uma vez, ninguém
saberia de onde veio, e a conferência exigiria abrir o Sankhya ao lado.

### O catálogo

Oito fatores, e só os que o produto **sabe responder hoje**:

| Chave | Unidade | Fonte |
|---|---|---|
| `receita_bruta`, `margem_contribuicao`, `ebitda` | moeda | Sankhya |
| `turnover_pct`, `absenteismo_pct` | percentual | Sankhya |
| `efetivo_ativo` | quantidade | Sankhya |
| `orcamento_mensal`, `realizado_no_mes` | moeda | Workspace (`financas`) |

Catálogo em **código** e não em tabela, pela mesma razão do registro de regras de
exceção: cada fator é uma função que consulta o espelho. Um fator "cadastrado"
sem função atrás seria uma meta que nunca pode ser apurada — e a descoberta
aconteceria no dia da nota.

Todo fator declara a **fonte**, e é isso que faz a meta carregar o carimbo de
frescor do número que a pontua.

---

## 21.2 Quadro aprovado não muda mais

`rascunho` → `aprovado` → `apurado`. Sem o degrau do meio, a meta seria editável
até o dia da nota.

Depois do aprovado, editar meta, peso ou alvo é **recusado**. Mover a trave no
meio do ciclo é o defeito que a palavra "meta" existe para impedir — e é o mais
fácil de cometer sem má-fé, corrigindo em novembro um alvo que "estava errado".

**Reabrir continua possível, e exige motivo.** Um quadro pode ter sido escrito
errado, e uma reestruturação pode mudar o que a pessoa responde. O que não pode é
acontecer em silêncio: `reaberturas` guarda quando, quem e por quê, e a tela
mostra a lista. Um quadro reaberto três vezes num ciclo é um achado sobre como as
metas foram definidas.

**Quadro apurado não reabre.** A nota já foi para o comitê, e reabrir permitiria
reescrever a meta depois de saber o resultado dela.

**Quadro vazio não é aprovado.** Quadro vazio aprovado é a forma mais silenciosa
de não ter metas: conta como aprovado no painel do R.H. e não cobra nada de
ninguém.

---

## 21.3 Fator sem amostra não vira zero

Meta cujo fator o espelho não sabe responder fica **não apurada**, com o motivo —
e **fora do denominador da nota**.

Contá-la como zero transformaria uma fonte fora do ar na nota de uma pessoa. A
diferença entre "não bateu" e "não deu para medir" é a diferença entre uma
conversa e uma injustiça.

Sem nenhuma meta apurada, a nota é **"—"**, e nunca `0` — a mesma regra de
`/workspace/indicadores/`.

Os casos que devolvem "não apurada", cada um com o próprio texto:

- o espelho não tem o fator para este escopo;
- o consolidado veio com **zero linhas** (o campo `linhas` do DTO existe para
  isso: zero linhas e soma zero são a mesma aparência e coisas diferentes);
- o divisor é **zero** — e a mensagem diz "é zero", diferente de "não tem";
- o alvo é zero;
- o fator saiu do catálogo entre a definição e a apuração;
- o espelho estourou — e a apuração continua nas outras metas.

---

## 21.4 O cálculo

`realizado = fator_1 ÷ fator_2 × 100`, ou o valor absoluto do `fator_1` quando
não há divisor. Contra o alvo:

- **diretamente proporcional** — `realizado ÷ alvo`. Receita, margem, EBITDA.
- **inversamente proporcional** — `alvo ÷ realizado`. Turnover, absenteísmo,
  custo. Sem esta direção, quem perdeu metade da equipe apareceria com 140% de
  desempenho.

**Teto de 150%.** O benchmark descreve "lógica de pontuação ilimitada", e ela
existe — mas 400% numa meta de peso 3 dilui todas as outras e transforma o quadro
num jogo de escolher a meta fácil.

**Máximo de 12 metas.** Quinze metas não são um foco: são uma lista de tarefas
com peso.

A nota é a média ponderada das metas **apuradas**, congelada em `realizado`,
`atingimento_pct` e `carimbo_texto`. Recalcular na leitura faria a nota de 2026
mudar em 2027, quando uma carga corrigisse um mês antigo — mesma decisão do
carimbo da ATA (ADR-030).

A competência que os fatores consultam é o **último mês do ciclo**. Apurar pelo
mês corrente daria notas diferentes a cada dia de acesso.

---

## 21.5 Quem vê o quê

**`met.ler.proprio` está no autoatendimento.** Todo mundo vê o próprio quadro — é
a diferença entre um sistema de metas e um sistema de avaliação secreta.

| Papel | Permissões | O que alcança |
|---|---|---|
| todos | `met.ler.proprio` | o próprio quadro e o próprio PDI |
| `gestor` | `met.ler/definir/aprovar.equipe` | os liderados, pelo organograma |
| `diretoria` | `met.*.global` | qualquer quadro, **inclusive o próprio** |
| `rh` | `met.ler.global` | lê para acompanhar a cobertura; **não** aprova |

**Ninguém aprova o próprio quadro** — o `alvo` de `pode()` é a pessoa avaliada, e
o gestor não se alcança pelo `.equipe`. A exceção é a diretoria, com
`met.aprovar.global`, e ela é deliberada: é o que destrava o quadro de quem não
tem gestor acima.

**O R.H. lê e não homologa.** Metas são combinadas entre a pessoa e quem a
lidera; um R.H. que aprova transforma a conversa num processo de RH.

### Restrição 8, no lugar em que ela é mais fácil de violar

**Não existe grade de pessoas com nota ao lado.** A lista da equipe traz
**situação** — rascunho, aprovado, apurado — e a contagem do R.H. traz
**números por situação**, sem nome nenhum.

Uma coluna de nota ao lado de uma lista de nomes é uma planilha de desempenho, e
ela circula. Não há exportação, e o `/admin/` não mostra nota em `list_display`.

---

## 21.6 O PDI

A terceira aba do benchmark: responsabilidades, áreas de interesse, aspirações de
**1 a 2 anos** e de **3 a 5 anos**, e ações com **mês e ano**.

Os horizontes estão no rótulo da tela: "aspirações" sem prazo vira lista de
desejos. Mês e ano e não data: "fazer o curso em março de 2027" é o grão em que
essa conversa acontece, e um seletor de dia obrigaria a inventar um número.

**O PDI é escrito pela pessoa.** Diferente das metas, de propósito: a meta é
combinada com quem lidera, e o plano de desenvolvimento é a conversa de carreira
de quem o vive. O gestor **lê** — a tela diz isso — e não redige por ela.

Model separado de `QuadroMetas` pelo mesmo motivo: o PDI sobrevive ao ciclo de
metas e não é conversa de nota. Junto, ele seria apagado com a reprovação de um
quadro — e é justamente aí que ele importa mais.

---

## 21.7 Os três testes que protegem a onda

1. `test_quadro_aprovado_nao_muda_mais` — editar, acrescentar e remover são
   recusados depois do aprovado; o alvo original continua lá.
2. `test_fator_sem_amostra_nao_vira_zero` e
   `test_a_meta_sem_apuracao_fica_fora_do_denominador_da_nota` — a nota de um
   quadro com uma meta de peso 1 apurada e uma de peso 9 sem apuração é 120, e
   não 12.
3. `test_o_quadro_e_da_pessoa_e_de_quem_lidera_ela` e
   `test_a_lista_da_equipe_traz_situacao_e_nunca_a_nota`.

Mais 93, entre eles: `pk` de meta de outro quadro é recusado; ninguém aprova o
próprio quadro; fator fora do catálogo é recusado na definição; o espelho que
estoura não derruba a apuração das outras metas; toda meta de exemplo aponta para
fator existente.

---

## 21.8 ADRs

### ADR-034 · O fator aponta para o espelho, e a meta não guarda número

**Contexto:** guardar o valor apurado direto na meta seria mais simples, e
dispensaria o catálogo inteiro.

**Decisão:** `Meta.fator_1` e `fator_2` guardam **chaves** de um catálogo em
código; o valor é lido do espelho na apuração e só então congelado.

**Consequência:** a meta é auditável — quem lê sabe de onde sai o número sem
abrir o Sankhya ao lado —, e a comparação entre quadros continua funcionando no
segundo ano. Com texto livre, duas pessoas escreveriam "EBITDA" e "Ebitda
realizado" para a mesma coisa.

O preço é que **só se pode escrever meta sobre o que o produto sabe medir**. É um
preço real: uma meta qualitativa não cabe neste desenho. É o preço certo — uma
meta que ninguém consegue apurar já não era uma meta, e o que se perde é a
ilusão de que era.

### ADR-035 · Quadro aprovado é imutável; reabrir é um ato registrado

**Contexto:** seria mais cômodo permitir edição até a apuração, e evitaria o
degrau de aprovação.

**Decisão:** `rascunho` é o único estado editável. Reabrir devolve ao rascunho,
exige motivo e grava `{quando, quem, motivo}` em `reaberturas` — visível na tela.

**Consequência:** mover a trave no meio do ciclo deixa rastro. O quadro apurado
não reabre de jeito nenhum: a nota já foi para o comitê, e reabrir permitiria
reescrever a meta depois de saber o resultado dela.

A mensagem de recusa distingue as duas causas — "sem permissão" e "quadro
aprovado" —, porque dizer "sem permissão" a quem tem permissão manda a pessoa
pedir acesso que ela já tem.
