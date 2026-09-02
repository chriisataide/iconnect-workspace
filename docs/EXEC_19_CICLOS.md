# EXEC 19 · Ciclo de planejamento e ATA — Onda 5 do benchmark GPS

> `/workspace/ciclos/` (código `12`). A pauta como objeto do produto: a ordem de
> olhar, registrada, com a tela viva em cada item e a ATA saindo do fechamento.

---

## 19.1 A pauta é o produto

No Portal GPS a pasta `01.01 – Ciclo de Planejamento Mensal` tem dezesseis itens
numerados **na ordem em que serão apresentados**:

```
CP01 – 01.1  Destaques / Concentrações      CP09 – 16.1.6 Tratativas NPS/PTQ
CP02 – 01.2  Apresentação                   CP10 – 16.1.3.1 Visita Oper. Liderança
CP03 – 13.1.2 Apontamentos (sintética)      CP11 – 16.1.5 Íris
...
```

O ciclo trimestral é um subconjunto de nove itens, para uma plateia mais sênior.
**Mesma biblioteca de telas, recorte diferente por público.**

O que isso resolve, e que uma pauta em slides não resolve:

- a ordem de olhar é **decisão registrada**, e não improviso de quem conduz;
- cada item aponta para a **tela viva**, e não para uma imagem colada na véspera;
- o que se disse diante de cada item fica **junto do item** — e não numa ATA que
  ninguém consegue cruzar com a tela seis meses depois.

### A pauta da ADB

Doze etapas no mensal, seis no trimestral. **CP01 é a tela `10`** — Apresentação
de Resultados —, como no benchmark, onde o ciclo abre pelo resultado.

| | Tela | O quê |
|---|---|---|
| CP01 | `10` | Resultado do mês |
| CP02 | `11` | O que saiu da linha |
| CP03 | `08` | O produto está sendo usado? |
| CP04 | `02.3` | A fila das áreas |
| CP05 | `02.2` | O que espera aprovação |
| CP06 | `30` | Pessoas e papéis |
| CP07 | `03.1` | Normativos |
| CP08 | `33` | Frota |
| CP09 | `31` | Estoque e equipamentos |
| CP10 | `26.1` | Oportunidades |
| CP11 | `99` | De onde vieram os números |
| CP12 | — | Encaminhamentos e encerramento |

O trimestral é `{CP01, CP02, CP03, CP06, CP11, CP12}` — e é gerado a partir da
mesma tupla, para que não possa divergir.

---

## 19.2 Pauta e reunião são coisas diferentes

| Model | O que é | Muda quando |
|---|---|---|
| `CicloPlanejamento` | a pauta e a plateia | quem governa o ciclo decide |
| `EtapaCiclo` | CP05, e a tela que ele abre | idem |
| `OcorrenciaCiclo` | a reunião de 09/2026 | uma vez por competência |
| `AnotacaoEtapa` | o que se disse diante da CP05 | durante a reunião |

Juntar as duas metades num model só faria a edição da pauta **reescrever a
história**: mexer na ordem em janeiro mudaria a ATA de outubro.

---

## 19.3 A fronteira passa entre o GET e o POST

Restrição 7 do produto, literal, e ela vale aqui mais que em qualquer outra
tela — a ATA é o documento que uma auditoria vai citar.

| Ato | Método | Permissão |
|---|---|---|
| ver a lista de ciclos | GET | `cic.ler` **e** estar na plateia |
| ler a pauta e as anotações | GET | idem |
| apresentar (`?etapa=`, `?apresentacao=1`) | GET | idem |
| abrir a reunião | POST | `cic.conduzir` |
| anotar | POST | `cic.conduzir` |
| fechar e gerar a ATA | POST | `cic.conduzir` |

**Quem não participa de ciclo nenhum recebe 403**, e nunca uma lista vazia. Lista
vazia diria "a empresa não tem ciclo de planejamento" para quem apenas não está
na sala — e essa é uma frase que alguém repete numa reunião.

**Plateia vazia não é "todo mundo".** Um ciclo sem `papeis_leitores` é visível só
para quem tem `cic.ler.global`. O padrão errado num campo em branco é o defeito
que ninguém vê.

Papéis semeados: `diretoria` lê e conduz; `socios` lê; `gestor` lê
(`.departamento`, que abre os ciclos cuja plateia ele integra e não o trimestral
de presidência).

### O que a pauta NÃO faz

**Ela não prevê se você pode entrar no destino.** Prever exigiria uma segunda
verdade sobre permissão, dentro da etapa — e verdade duplicada sobre acesso é
como se perde acesso. Quem não pode entrar recebe o 403 da tela de destino.

O custo é um 403 possível no meio de uma reunião, para quem não deveria estar
conduzindo aquela pauta. O ganho é que a permissão continua morando num lugar só.

---

## 19.4 Fonte atrasada não impede a reunião

A conferência de frescor roda na abertura, sobre as etapas **obrigatórias**, e
devolve uma lista de impedimentos. Ela **não trava**.

Travar a reunião de setembro porque a carga do monday falhou às três da manhã
transformaria um problema de infraestrutura num problema de governança. O que a
conferência faz é pior para quem esconde e melhor para quem decide:

1. o primeiro POST recusa e **devolve a lista**;
2. o botão muda de texto — *"Abrir mesmo assim (3 fontes com atraso)"*;
3. o segundo POST abre, e os impedimentos ficam **congelados** na ocorrência;
4. eles aparecem no topo da tela e vão **inteiros para a ATA**, antes da pauta.

Quem decidiu com número velho decidiu sabendo, e o registro diz isso.

A confirmação é um campo escondido, e não um `confirm()` de JavaScript: a CSP
deste produto não tem `unsafe-inline`, e um diálogo do navegador não deixaria
registro de que alguém viu a lista.

---

## 19.5 A ATA

Fechar a reunião cria um `Documento` de tipo `ata` no acervo, com:

- o cabeçalho da reunião (quando abriu, quando fechou, quem conduziu, a plateia);
- **os impedimentos, antes da pauta** — quem lê precisa saber com que dado a sala
  decidiu antes de ler o que ela decidiu;
- cada etapa na ordem, com o código, o título, o endereço da tela, as anotações e
  **o carimbo que cada anotação congelou**;
- os encaminhamentos em destaque, com prazo.

**Etapa sem anotação é escrita, não omitida.** Etapa que some deixa a dúvida
entre "não foi apresentada" e "não teve registro", e as duas pedem coisas
diferentes na reunião seguinte.

**Fechar duas vezes não gera duas ATAs.** Duas ATAs da mesma reunião no acervo é
a pior ambiguidade possível: as duas parecem oficiais.

**A ATA não é leitura obrigatória.** Obrigar a confirmação transformaria a
bandeja de leitura de toda a plateia num contador mensal que ninguém zera — e a
leitura obrigatória perde o sentido quando vira rotina.

### Como a plateia da ATA é respeitada

`publico_alvo` recebe `papel:<chave>` para cada papel da plateia. `papel:` já é
um *subject* de ACL reconhecido por `subjects_de()` — o mesmo que o índice de
busca usa no `WHERE`. Com isso, vitrine, leitura direta e busca respeitam a
plateia **pelo caminho que já existia**, sem nenhuma exceção dentro do app de
conteúdo.

`ciclos.pode_ler_ata()` é a segunda tranca, chamada por `conteudo.pode_ver()` por
importação preguiçosa. Uma ATA órfã — ciclo apagado — cai de volta no
`publico_alvo`: negar trancaria no acervo um documento que ninguém mais poderia
reabrir.

**ATA não se escreve à mão.** Ela sai do `select` da redação e é recusada em
`conteudo.salvar()`. Uma ATA escrita à mão ficaria no acervo indistinguível da
verdadeira — e é a verdadeira que alguém vai citar numa auditoria.

---

## 19.6 Modo apresentação

`?etapa=CP05` mostra uma etapa por vez; `?apresentacao=1` tira o trilho do HTML.
Dois parâmetros **ortogonais na mesma view**: um escolhe o item, o outro tira a
moldura. A reunião usa os dois; a consulta de terça-feira, nenhum.

É o ADR-025 sendo aplicado de novo, e não uma decisão nova. O trilho some pelo
bloco vazio e não por CSS — `display:none` deixaria a navegação no HTML, e o
leitor de tela leria uma navegação que ninguém pode ver.

Etapa desconhecida na URL **cai no primeiro passo**, e não em 404: no meio de uma
reunião, um erro de digitação na barra de endereço não pode virar uma tela de
erro projetada na parede.

---

## 19.7 Os três testes que protegem a onda

1. `test_a_ata_repete_o_carimbo_do_dia_e_nao_o_de_hoje` — a anotação nasce com
   "há 3 dias" ao lado; a carga volta a ser recente; a ATA continua dizendo "há
   3 dias".
2. `test_a_fronteira_passa_entre_o_get_e_o_post` — quem lê a pauta recebe 200 no
   GET e 403 nos três POSTs.
3. `test_fonte_atrasada_nao_impede_a_reuniao_e_nao_some_da_ata` — o primeiro
   POST recusa com a lista, o segundo abre, e a lista está na ATA.

Mais 33, entre eles: etapa apontando para código inexistente não quebra a pauta;
`pk` de etapa de outro ciclo devolve 404; ciclo sem plateia não publica ATA;
semeadora idempotente; trimestral é subconjunto próprio do mensal.

---

## 19.8 ADRs

### ADR-029 · A etapa aponta para um código de tela, não para uma URL

**Contexto:** guardar a URL do destino é mais direto e dispensa uma resolução.

**Decisão:** `EtapaCiclo.tela` guarda `"10"`, `"02.3"` — o código do
endereçamento —, e a tela resolve por `enderecamento.por_codigo()`.

**Consequência:** o dia em que uma rota mudar, uma pauta com URL viraria uma
lista de links quebrados **durante a reunião**, que é o único momento em que
ninguém tem tempo de consertar. Um código que deixou de existir também não
quebra: a etapa continua legível, e a tela diz "endereço desconhecido" em vez de
oferecer um link para lugar nenhum. Um teste varre todas as pautas semeadas
atrás de código órfão.

### ADR-030 · A ATA congela o carimbo

**Contexto:** seria natural recalcular o frescor ao renderizar a ATA — o código
já existe, e o número sairia sempre "certo".

**Decisão:** `AnotacaoEtapa` copia o texto do carimbo no instante da anotação;
`OcorrenciaCiclo.impedimentos` congela a conferência no instante da abertura; o
corpo da ATA é texto, escrito uma vez.

**Consequência:** uma ATA de março continua dizendo, em setembro, que a decisão
foi tomada diante de um dado de três dias atrás. Recalcular reescreveria a
história **para melhor**, que é a direção em que ninguém percebe — e "com que
dado a sala decidiu" é exatamente o que uma auditoria procura numa ATA. O preço
é que corrigir um carimbo errado exige nova reunião; é o preço certo.

### ADR-031 · A pauta não prevê a permissão do destino

**Contexto:** um 403 no meio de uma apresentação é constrangedor, e seria fácil
declarar em `EtapaCiclo` a permissão de cada tela.

**Decisão:** a pauta mostra o link; a tela de destino responde.

**Consequência:** a permissão continua morando num lugar só. Declará-la duas
vezes criaria a divergência silenciosa — o campo diria `eco.ler` enquanto a view
checa outra coisa —, e divergência sobre acesso resolve-se sempre para o lado
errado. Quem conduz a pauta tem acesso ao que a pauta abre; se não tem, isso é
um achado sobre os papéis, e não um problema de renderização.
