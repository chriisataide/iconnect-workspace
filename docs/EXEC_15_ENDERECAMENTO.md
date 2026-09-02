# EXEC 15 · Vocabulário e frescor — Onda 1 do benchmark GPS

> Escopo: código estável por módulo e tela, carimbo de atualização **por bloco**
> e prefixos de busca. Primeira das nove ondas derivadas de
> [`BENCHMARK_GPS_LEITURA.md`](BENCHMARK_GPS_LEITURA.md).
> Não traz dado de fora, não cria model e não faz migração.

---

## Sumário

- [15.1 O que esta onda entrega](#151-o-que-esta-onda-entrega)
- [15.2 A numeração da ADB](#152-a-numeração-da-adb)
- [15.3 O carimbo, e por que ele nasce agora](#153-o-carimbo-e-por-que-ele-nasce-agora)
- [15.4 Os prefixos da busca](#154-os-prefixos-da-busca)
- [15.5 O que ficou de fora, e por quê](#155-o-que-ficou-de-fora-e-por-quê)
- [15.6 ADRs](#156-adrs)

---

## 15.1 O que esta onda entrega

Três coisas, e nenhuma delas aparece como funcionalidade nova na home:

1. **Endereço estável.** Todo módulo e toda tela-destino têm um código
   (`00`, `02.2`, `26.1`). Ele aparece discreto no cabeçalho, resolve na busca e
   funciona como URL — `/workspace/ir/02.2/`.
2. **Carimbo de frescor por bloco.** Toda faixa de números agregados declara de
   onde vem, de quando é e há quanto tempo foi carregada.
3. **Prefixos de busca anunciados** — `s:` serviços, `d:` documentos, `p:`
   pessoas, `#` número do pedido, mais o próprio código da tela.

O valor não está em nenhuma delas isoladamente. Está na conversa que passam a
permitir: *"abre a 02.2"*, *"esse número é de quando?"*, *"acha aí com d:"*.

---

## 15.2 A numeração da ADB

Não é a do Portal GPS, e não deveria ser: aquela taxonomia descreve um grupo de
serviços terceirizados com dezoito áreas e mais de cem telas. Copiar o número
junto com o padrão traria `13.1.2 Apontamentos (sintética)` para um produto que
não tem apontamento nenhum.

Quatro blocos, com folga entre eles:

| Faixa | O que ocupa | Exemplos |
|---|---|---|
| `0x` | o que toda pessoa usa | `00` Início · `02` Serviços · `03` Documentação · `08` Indicadores |
| `2x` | os departamentos | `20` RH · `21` Financeiro · `23` Suprimentos · `27` Jurídico |
| `3x` | administração e patrimônio | `30` Pessoas e papéis · `31` Estoque · `33` Frota |
| `9x` | o que leva à Platform | `90` Chamados · `91` Campo |

Dois dígitos no primeiro nível de propósito. Com um só, o décimo assunto
obrigaria a renumerar os nove anteriores — e código que renumera deixa de ser
endereço.

O segundo nível é a tela dentro do assunto: `02` é Serviços, `02.2` é a bandeja
de aprovações. O formato aceita um terceiro nível (`02.1.4`) e ele ainda não é
usado: existe para quando uma tela tiver recortes próprios, que é o caso da
Onda 3.

**A lista viva está em [`workspace/enderecamento.py`](../workspace/enderecamento.py),
e não aqui.** Um documento que repete a tabela passa a mentir na primeira tela
nova — foi assim que o README passou a dizer que a área aprova depois de a área
ter deixado de aprovar. Para ver a lista de agora:

```python
from workspace import enderecamento
for tela in enderecamento.todas():
    print(tela.codigo, tela.nome, tela.url)
```

---

## 15.3 O carimbo, e por que ele nasce agora

O Workspace ainda não lê nada de fora. Todo número destas telas é dele mesmo, e
todo carimbo desta onda diz a mesma coisa: **"Workspace · em tempo real"**.

Construir o mecanismo agora parece cedo, e é o contrário. O carimbo é uma
disciplina, não uma funcionalidade: ele só vale se toda faixa de números nascer
carimbada. Deixar para a Onda 3 significaria escrever a primeira tela com dado
do Sankhya lendo `timezone.now()` no template — um carimbo dizendo "agora" para
um dado de ontem —, e depois caçar cada template já pronto.

**Por bloco e não por tela**, e é a decisão que a multi-fonte torna obrigatória.
Um carimbo no topo funciona enquanto a tela tem uma fonte só. Ele deixa de
funcionar no dia em que a mesma tela mostra o resultado financeiro do Sankhya em
D-1 ao lado do andamento dos projetos do monday em minutos: um "atualizado às
08:45" no cabeçalho estaria certo sobre metade do conteúdo e errado sobre a
outra, sem nada na tela dizendo qual metade.

Bloco aqui não é "cada número": é **cada conjunto de números que compartilha
fonte e janela**. As quatro telas com faixa agregada têm um bloco cada.

### Como isto é mecânico e não boa vontade

A convenção: uma faixa de números agregados usa a classe `au-kpi-linha`. O teste
`test_toda_faixa_de_numeros_agregados_tem_carimbo` casa essa classe com a
inclusão de `_carimbo.html` — nos dois sentidos. Faixa sem carimbo reprova;
carimbo em tela sem faixa também, porque carimbo sem número é ruído.

O carimbo não é preenchido por view nenhuma. Ele vem do processador de contexto
`workspace.context.carimbos`, que o lê de `frescor.BLOCOS`. Mesma razão do
`rail()`: depender de cada view lembrar garante que uma esqueça.

### A janela entra no NOME quando ela muda a leitura

Regra herdada do benchmark, e que só passa a valer com dado de fora: `Medições
em Aberto (M-2)`, `Contas a Receber (D-10)`. Quando a janela do dado muda a
leitura do número, ela vai para o **título da faixa**, e não para o carimbo.

Não há campo para isso em `BlocoAgregado`, de propósito. Um rótulo montado no
serviço apareceria em letra miúda ao lado do carimbo — e quem abre a tela
precisa saber de quando é o número **antes** de lê-lo, não depois. Quem
construir a faixa 2 da Onda 3 escreve a janela no `<h2>`.

### O contrato nasce vazio, de propósito

[`workspace/providers/frescor.py`](../workspace/providers/frescor.py) declara
`ProvedorFrescor`, e nenhum domínio o implementa. Fonte sem provedor produz o
carimbo **"sem registro de carga"**, marcado como alerta — que é a informação
honesta, e não um vazio.

Três garantias que o implementador da Onda 2 precisa respeitar:

1. `carregado_em` é o instante da última carga **bem-sucedida**. Carga que
   falhou não avança o relógio.
2. `status` descreve a última **tentativa**. Uma fonte pode ter `carregado_em`
   de seis horas atrás e `status="falha"` ao mesmo tempo — é exatamente o caso
   que a tela precisa mostrar, com o dado bom e o aviso juntos.
3. Fonte indisponível devolve carimbo com `status="falha"` e `motivo`, nunca
   `None`. **Falha de carga nunca zera o bloco:** o último dado bom continua na
   tela. Zerar é dizer que a empresa parou.

---

## 15.4 Os prefixos da busca

| Prefixo | O que faz | Quem vê o atalho anunciado |
|---|---|---|
| `s:` | só serviços | todos |
| `d:` | só documentos | todos |
| `#123` | o pedido de número 123 | todos |
| `02.2` | vai para a tela | todos |
| `p:` | pessoas | **só quem administra papéis** |

O recorte do prefixo vira `WHERE origem IN (...)`, e não filtro em Python. É a
mesma regra que o índice já seguia para permissão, pelo mesmo motivo: filtrar
depois de recuperar devolveria o acervo inteiro para jogar fora, e o limite da
consulta cortaria as linhas erradas.

**`p:` não amplia alcance nenhum.** Ele é atalho para a lista que a pessoa já
pode abrir em `/workspace/pessoas/`. Para quem não administra papéis, `p:` não
é prefixo: `p: souza` cai na busca comum, sem grupo vazio e sem aviso. Avisar
contaria que existe um diretório do outro lado da porta — a contagem que o
índice foi desenhado para não vazar.

O resultado traz **nome, cargo e área**. E-mail e centro de custo ficam de fora:
grade com dado pessoal exportável é a primeira coisa que a leitura do benchmark
marcou como não copiar.

### Onde os prefixos são anunciados

Na linha abaixo do campo da paleta, e não dentro do `placeholder`. São cinco
atalhos, e um placeholder com cinco atalhos some no primeiro caractere digitado
— justamente quando a pessoa ainda está decidindo como buscar. Na linha de
baixo a legenda continua à vista enquanto ela digita.

---

## 15.5 O que ficou de fora, e por quê

| Pedido | Decisão |
|---|---|
| `Modulo` como model, com `unique=True` no código | **Não.** Ver ADR-015. |
| Código em tela de resultados e de exceções | Não existem ainda. Registro só o que tem tela — código que aponta para rota inexistente é pior do que código nenhum, e há teste para isso. |
| Endereço para rota de ação (aprovar, cancelar, baixar) | Não. Ação não é lugar; dar-lhe endereço produziria um `/ir/` que executa. |
| Endereço por item de catálogo (`/servicos/<chave>/`) | Não. Encheria o registro de uma linha por item, e o código deixaria de ser algo que se decora. |
| ⌘K pré-preenchendo formulário a partir do código | Não. Decisão já registrada no README, reafirmada aqui. |
| Carimbo com instante real | Não há registro de carga. Volta na Onda 2. |

---

## 15.6 ADRs

### ADR-015 · O código da tela não é dado, é fonte

**Contexto:** o padrão do benchmark pede unicidade de código "garantida por
constraint" — a árvore do Portal GPS tem `08.2.4` e `05.6` duas vezes, e isso é
sintoma de taxonomia sem dono. O impulso é criar `Modulo` no banco com
`unique=True`.

**Decisão:** o código mora no fonte, em `workspace/modulos.py` e
`workspace/enderecamento.py`. A unicidade é garantida por `registrar_tela()`,
que recusa código repetido **na subida do processo**.

**Consequência:** nenhuma migração, nenhum `/admin/`, nenhuma semeadora, e uma
verdade só sobre quais telas existem. Neste repositório módulo nunca foi dado:
`MODULOS` é uma tupla de dataclasses `frozen` montada no `ready()`, e o launcher
deriva os tiles dela. Pôr o código no banco criaria a segunda verdade, e a
primeira divergência entre as duas seria um `/ir/` apontando para uma rota que
ninguém escreveu.

A constraint continua existindo — é de outro tipo, e mais rígida. Um `UNIQUE` só
reprova no `INSERT`; um código duplicado escrito no fonte passaria pelo deploy
inteiro até alguém tentar gravar. Aqui ele derruba a subida do processo.

### ADR-016 · `/ir/<código>/` resolve, e não autoriza

**Contexto:** um redirecionador por código poderia checar permissão antes de
mandar a pessoa para a tela, e devolver 404 para o que ela não pode ver.

**Decisão:** `/ir/` resolve o código e redireciona. A permissão é a que a tela
já aplica. Quem não tem escopo em `/ir/08/` recebe **403 da tela de
Indicadores**, não 404 do redirecionador.

**Consequência:** existe um lugar só onde "quem vê o quê" está escrito. Um
`/ir/` que autorizasse seria o segundo, ao lado de `pode()` — e o dia em que os
dois discordassem, o produto teria duas respostas para a mesma pergunta e
nenhuma forma de saber qual vale.

O 404 do código responde igual para todo mundo, e isso é deliberado: a lista de
códigos é vocabulário público da empresa, como o organograma de departamentos. O
que é privado é o **conteúdo** de cada tela, e disso quem cuida é a tela.

### ADR-017 · O carimbo nunca sai do relógio

**Contexto:** o instante de atualização é a informação mais fácil de fabricar —
`{% now %}` num template resolve em um caractere.

**Decisão:** nenhum template lê o relógio. Dado nativo é carimbado *"em tempo
real"*, sem horário; dado de fora tira o instante do registro de carga, pelo
contrato `workspace.providers.frescor`. Fonte sem provedor diz **"sem registro
de carga"**.

**Consequência:** `test_nenhum_template_fabrica_carimbo_com_o_relogio` reprova
qualquer `{% now %}` em qualquer template, inclusive fora de carimbo — um
"atualizado agora" no rodapé de uma tela de números é lido como carimbo por quem
está na reunião, independentemente de onde o programador achou que estava pondo.

Dado nativo não ganha horário porque relógio convida a comparar com dado que tem
carga: "Workspace · 08:45" ao lado de "Sankhya · há 6 h" sugere que os dois são
a mesma espécie de afirmação, e não são.
