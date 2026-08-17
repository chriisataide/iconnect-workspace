# Guia do iConnect Workspace — para quem vai testar

> **Para quem é este documento.** Para o QA que precisa entender *o que cada tela
> promete* antes de decidir se ela cumpriu. Não é um roteiro de cliques: é o
> contrato de cada aba — para que serve, em que momento da vida do colaborador
> ela aparece, o que é comportamento correto e o que é defeito.
>
> Leia a seção 1 antes de abrir o navegador. Ela evita as duas horas perdidas
> mais comuns: testar contra um banco sem dados, e abrir bug em cima de uma
> decisão de produto.

---

## 0. Antes de tudo: são dois produtos, não um

Isto é a coisa mais importante do documento e a que mais gera falso-positivo.

| | **iConnect Workspace** | **iConnect Platform** |
|---|---|---|
| Organiza | a vida corporativa da **empresa** | a operação de **atendimento aos clientes** |
| Usuário | o colaborador da icodev | o técnico, o operador, o cliente |
| Onde vive | `/workspace/…` | `/login/`, `/dashboard/…`, `/fsm/…` |
| Pessoas | organograma (`identidade.Lotacao`) | papéis do iConnect (`UserRole`, ~1.432 registros) |

**Consequência prática para o teste:** as pessoas dos dois produtos **não são as
mesmas**. Um usuário do iConnect não é colaborador do Workspace, e vice-versa. Se
uma tela do Workspace não lista alguém, a primeira pergunta é "essa pessoa tem
lotação?" — não "sumiu o usuário".

E o inverso: **bug de tela do iConnect não é bug do Workspace**. O tile
"iConnect Platform" na home leva para `/login/` e ali começa outro produto, com
outro dono e outra suíte de testes. O único contrato do Workspace ali é: o tile
existe, aponta para `/login/`, e é o **único** caminho de login na home.

---

## 1. Preparar o ambiente (faça isto primeiro)

### 1.1 O banco precisa estar migrado

O Workspace ganhou 8 migrações nas ondas recentes. Um banco de desenvolvimento
antigo quebra com `no such column: workspace_itemcatalogo.termos` — que **não é
bug**, é migração pendente.

```bash
python manage.py migrate
python manage.py showmigrations workspace   # tudo com [X]
```

### 1.2 Semear o que tem semeadora

```bash
python manage.py semear_papeis --aplicar              # os 16 papéis e suas permissões
python manage.py semear_catalogo --aplicar            # os 26 serviços do catálogo
python manage.py semear_regras_aprovacao --aplicar    # gestor → área → 50k → 300k
python manage.py importar_organograma docs/exemplos/organograma-inicial.csv --criar-usuarios --aplicar
python manage.py semear_acessos --aplicar             # senha sorteada + papel por cargo
python manage.py semear_perfis --aplicar              # um usuário POR PAPEL, para testar
python manage.py reindexar_busca                      # popula o índice da ⌘K
```

### 1.2.1 Os 16 perfis de teste — um por papel

O organograma tem gente com nome de gente (`gerente.suporte`, `tecnico.campo`).
É realista, e é péssimo para testar: para saber quem vê a fila de Compras é
preciso lembrar que Compras caiu no gerente de suporte.

O `semear_perfis` resolve isso — **o e-mail é a resposta**. Todos com a senha
`workspace123`:

| Entrar como | Atende a fila de | Aprova |
|---|---|---|
| `colaborador@icodev.com.br` | — | nada — é a pessoa que só **pede** |
| `gestor@icodev.com.br` | — | o 1º degrau de quem responde a ele |
| `rh@icodev.com.br` | R.H. | `rh.*` — e é o único que abre **`/pessoas/`** |
| `financeiro@icodev.com.br` | Financeiro | `fin.*` |
| `compras@icodev.com.br` | Compras | `com.*` |
| `vendas@icodev.com.br` | Vendas | `ven.*` |
| `sesmt@icodev.com.br` | SESMT | `hab.*` |
| `ti@icodev.com.br` | TI | — |
| `logistica@icodev.com.br` | Logística | — |
| `operacao@icodev.com.br` | Operação | — |
| `juridico@icodev.com.br` | Jurídico | — |
| `marketing@icodev.com.br` | Marketing | — |
| `diretoria@icodev.com.br` | — | **qualquer** degrau, e o de 20 acima de R$ 50 mil |
| `socios@icodev.com.br` | — | **qualquer** degrau, e o de 30 acima de R$ 300 mil |
| `auditoria@icodev.com.br` | — | — (só leitura de auditoria) |
| `monitoramento@icodev.com.br` | — | — (só o painel de operação) |

A hierarquia vem montada: `colaborador@` → `gestor@` → `diretoria@` →
`socios@`, e toda área responde a `gestor@`. Sem ela o primeiro degrau da
cadeia não existiria — a regra de ordem 10 é `GESTOR_DIRETO` e sai da
**lotação**, não de papel.

> **Diretoria e Sócios decidem sem ter fila, e isso não é bug.** Os dois papéis
> têm `apr.aprovar.global`, que alcança qualquer degrau — inclusive os de gestor
> direto. Aprovar e **atender** são coisas diferentes: eles decidem, não
> executam.

> **A bandeja abre para todos, a fila não.** Qualquer pessoa pode virar
> aprovadora (basta alguém tê-la como gestor), então bandeja vazia é verdade.
> Já "sua fila está vazia" para quem não atende nada seria mentira — por isso a
> fila responde **403**.

Todos rodam em **simulação por padrão**: sem `--aplicar` eles só relatam. Isso é
deliberado e vale testar — rodar sem a flag não pode gravar nada.

O organograma de exemplo cria **6 pessoas por cargo** (não são pessoas reais: o
arquivo vai para o git). O CSV traz cargo e hierarquia, e **não traz
credencial** — elas nascem com `set_unusable_password()`. Quem resolve isso é o
`semear_acessos`, e ele faz as duas coisas que faltavam de uma vez: sorteia
senha e concede o papel do cargo.

Sem ele o ambiente fica no pior dos dois mundos — organograma certo e ninguém
entrando, e cinco áreas de aprovação sem titular engolindo pedido.

**O que ele nunca faz**, e vale testar:

- **Não troca senha que já existe.** Rodar por engano não pode ser o jeito de
  perder o acesso ao próprio ambiente.
- **Não toca em superusuário.** Conta de emergência não é de demonstração.
- **Não roda com `DEBUG=False`** sem `--forcar`. Semear senha conhecida em
  produção é exatamente o acidente que esse guarda impede.
- **Não imprime senha na simulação.** A transação volta, e quem anotasse
  descobriria na hora de entrar que o que está no papel não vale.

As senhas são sorteadas e aparecem **uma vez** na saída do comando. Não ficam em
arquivo nem no banco em claro — se perder, o caminho é o `/admin/`.

> Para gente de verdade isto não serve: o fluxo certo é convite com link de
> definição de senha, e ele chega junto com o SSO.

### 1.3 O que **não** tem semeadora — e como criar

Três módulos não têm comando de semente. Os dados vêm pelo admin:

| Falta | Onde criar | Sem isso, a tela mostra |
|---|---|---|
| Documentos (POP, políticas) | `/admin/workspace/documento/` | acervo vazio |
| Recursos (salas, veículos) | `/admin/workspace/recurso/` | "nenhum recurso" |
| Correspondências | a própria tela, com perfil de recepção | fila vazia |
| Comunicados e notícias | `/admin/workspace/publicacao/` | cards vazios na home |

> ⚠️ **Isto é uma lacuna real, não uma pegadinha do guia.** Não existe
> `semear_workspace`, então cada QA monta a massa à mão e testa contra dados
> diferentes. Se isso atrapalhar, peça o comando — é meia hora de trabalho e
> torna o ambiente reproduzível.

### 1.4 Como testar as três camadas de permissão

Você vai precisar de **três sessões diferentes**, e o guia inteiro assume isso:

| Sessão | Como obter | Serve para |
|---|---|---|
| **Anônima** (janela privada) | não logar | provar que o hub é público |
| **Colaborador** | qualquer usuário com lotação | 90% das telas |
| **Gestor / Diretoria** | usuário com papel `gestor` ou `diretoria` | bandeja de aprovação |
| **Recepção** | usuário com papel `logistica` | fila de correspondência |

Com o `semear_acessos` aplicado, o organograma de exemplo já entrega as quatro
sessões prontas:

| Sessão | Quem, no exemplo | Papéis |
|---|---|---|
| **Colaborador** | `tecnico.campo@icodev.com.br` | colaborador |
| **Gestor** | `gerente.suporte@icodev.com.br` | gestor, compras |
| **Diretoria** | `diretor.operacoes@icodev.com.br` | diretoria, vendas |
| **Atendimento de campo** | `gerente.campo@icodev.com.br` | gestor, operação, SESMT |

Papéis também se atribuem na tela `/workspace/pessoas/` (ou em
`/admin/identidade/`). Note que **`rh.admin` fica só com o superusuário** — é
ele quem enxerga a tela de papéis, e é de propósito: ela é o mapa de poder da
empresa e ela também concede.

---

## 2. As regras que valem em TODA tela

Antes das telas, sete invariantes. Cada uma delas já foi quebrada uma vez, e cada
uma vale um caso de teste em qualquer aba que você abrir.

### 2.1 O Workspace é aberto para ver; assinar exige identidade

> *"Quem estiver na rede da empresa tem acesso ao portal, não precisa de senha."*

**Aberto** (abre em janela anônima, sem redirecionar) — tudo que é
**institucional**, isto é, igual para qualquer pessoa da empresa:
`/workspace/`, a busca, os módulos, a documentação, a agenda das reservas, as
publicações, **o catálogo de serviços e o formulário de cada um deles**.

**Exige identidade** (302 para `/entrar/?next=…`) — as telas cujo conteúdo
inteiro é de **uma pessoa**, e os atos que assinam em nome dela:

| Tela | O que ela mostra |
|---|---|
| `meu-dia` e `notificacoes` | o que exige você hoje, e os avisos endereçados a você |
| `minhas-solicitacoes` e `reservas/minhas` | os seus pedidos e as suas reservas |
| `aprovacoes` | a fila que espera a **sua** decisão — pedidos de terceiros, com valor e comprovação |
| `correspondencias` | quem recebeu intimação, de quem e quando |

E os atos:

| Rota | Por quê |
|---|---|
| `aprovacoes/<id>/decidir/` e `aprovacoes/lote/` | a decisão vai para o histórico com um nome |
| `solicitacao/<id>/acerto/` | movimenta dinheiro: declara devolução ou informa conta |
| `solicitacao/<id>/cancelar/` | derruba a aprovação em curso e libera orçamento |
| `reserva/<id>/cancelar/` | desfaz a reserva que outro marcou |
| `servicos/<chave>/` **no POST** | o formulário abre para qualquer um; o pedido nasce com um solicitante, consome o centro de custo dele e cai na fila do gestor dele |
| `reservas/<codigo>/` **no POST** | ver a agenda é aberto; marcar põe um nome no calendário |
| `documentacao/<slug>/confirmar/` | é a linha que a empresa apresenta para provar que a pessoa leu |
| `correspondencias/` e seus três POSTs | a tela responde quem recebeu intimação, de quem e quando |
| `anexo/<id>/` | atestado médico, comprovante, contrato — de uma pessoa |

O motivo é um só: **sem sessão, o produto assume a primeira pessoa ativa com
lotação** (`workspace/acesso.py`). Isso é aceitável para desenhar uma tela
institucional; não é para mostrar a vida de alguém, nem para assinar por ela.

A régua, em uma linha: **institucional é aberto; o que é de uma pessoa, e todo
ato feito em nome dela, exige identidade.** Quando o mesmo endereço faz as duas
coisas — pedir um serviço, reservar uma sala — a fronteira passa entre o GET e
o POST, e não na porta.

**Defeito se:** uma tela institucional redirecionar para `/entrar/`, **ou**
qualquer coisa das duas tabelas abrir sem sessão. As duas metades importam.

`/entrar/` existe só para isso — **nenhum link do produto leva até lá**, e não
deve aparecer botão de login em tela nenhuma (ver 2.2). Sem essa rota seria
impossível se identificar: `/admin/login/` recusa quem não é staff.

### 2.2 Não existe botão de login na topbar

Havia três portas para o mesmo lugar (topbar, tile, faixa). Sobrou **uma**: o
tile "iConnect Platform", na faixa Aplicativos. Se aparecer um "Entrar" na
topbar, é regressão.

### 2.3 A casca é igual em toda tela

Toda tela do Workspace tem: marca icodev + "Workspace" à esquerda; lupa à
direita; **sino e nome do usuário só quando logado**; rodapé "a vida corporativa
em um lugar".

**Este é o teste de regressão mais rentável do produto.** Já aconteceu: uma tela
nova entrou e a topbar perdeu o sino *e* o nome do usuário sem quebrar nada
visível. Passe pelas 6 telas principais logado e confira que o sino e o nome
aparecem em **todas**.

### 2.4 O sino só conta o que existe

Sem notificações não lidas, o sino aparece **sem número**. Sino com "0"
permanente é a coisa que se aprende a não olhar — se aparecer, é defeito.

O contador vem de um *context processor* que só roda dentro de `/workspace/` e
só para usuário autenticado. Fora do Workspace, ele não deve custar nada.

### 2.5 ⌘K funciona em toda tela

`⌘K` (ou `Ctrl+K`) abre a paleta de busca em **qualquer** tela do Workspace.
`Esc` fecha. Mínimo de 2 letras.

Já falhou duas vezes: o atalho procurava um campo que só a home tinha, e o `Esc`
era engolido pelo `<input type="search">` do Chrome. **Teste ⌘K e Esc em pelo
menos três telas diferentes**, não só na home.

### 2.6 Nenhum bloco nasce vazio

Regra de produto (ADR-012): bloco sem dado **não desenha moldura**. Ele
desaparece. Se você vê um cartão com título e nada dentro, é defeito — não é
"estado vazio".

A exceção são os cards de Comunicados e Notícias na home, que têm mensagem
explícita ("Nenhum comunicado no ar.").

### 2.7 Nada de estilo inline

A CSP de produção usa nonce em `style-src`, e navegador moderno **ignora
`unsafe-inline` quando há nonce**. Isso significa que qualquer `style="…"` num
template do Workspace é bloqueado silenciosamente em produção.

**Como testar:** abra o console do navegador em cada tela. Zero erro de CSP,
zero aviso de recurso bloqueado. O console é fonte de verdade aqui — ele já
pegou uma barra SVG que não desenhava por causa de vírgula decimal, e uma tabela
inteira sem CSS.

---

## 3. Tela por tela

### 3.1 Home — `/workspace/`

**Para que serve.** É a porta da empresa. Responde três perguntas em ordem: *o
que exige você hoje*, *o que a empresa está dizendo*, *para onde você vai*.

**Quando é útil.** Ao abrir o navegador pela manhã. É a página inicial pretendida.

**A ordem das faixas é a mensagem, e é testável:**

1. **Hero** — data em português, saudação
2. **Meu dia** — os cartões de trabalho
3. **Minha empresa** — comunicados e notícias
4. **Aplicativos** — os sistemas, **por último**

> Aplicativos em último lugar é decisão de produto, não descuido. Até 12/08/2026
> a home abria por Aplicativos com o iConnect como tile herói, e isso a tornava
> um *app launcher*: a primeira coisa que o colaborador via era uma lista de
> sistemas, e o trabalho dele vinha depois. **Não abra bug pedindo o iConnect de
> volta ao topo.**

**O que testar:**

- Anônimo: a home abre, diz "Bem-vindo ao Workspace.", sem sino e sem nome.
- Logado: diz "Olá, `<primeiro nome>`." — **só o primeiro nome**.
- A data: `"Sexta-feira, 7 de agosto"`. Uma maiúscula só, no começo. Se vier
  "Sexta-Feira, 7 De Agosto" ou "Agosto", é defeito de locale.
- O cartão "Pedir um serviço" promete um número concreto ("26 serviços"). Confira
  que bate com `ItemCatalogo` ativos.
- O cartão **"Esperando você"** só aparece para quem tem aprovação pendente.
  Colaborador comum não deve vê-lo. Card de aprovação sempre visível e sempre
  zerado ensina o aprovador a ignorá-lo.
- "Minhas solicitações" mostra um selo com a contagem de pedidos abertos, ou uma
  seta quando não há nenhum.
- Os 10 tiles de módulo levam a algum lugar. **Nenhum pode dar 404.**
- O tile de Correspondências pede login — isso é correto, é dado pessoal. O
  invariante é "não dá 404", não "responde 200".
- A lupa (⌘K) fica **antes** do sino, e é visível para todos.

**Armadilha histórica:** nove dos dez tiles não levavam a lugar nenhum, e o
catálogo — a única área real — não tinha porta na home. Vale reconferir a cada
release: **todo tile leva a uma tela real, ou está marcado "Em breve"**.

---

### 3.2 Busca universal e paleta ⌘K — `/workspace/buscar/`

**Para que serve.** Um campo para o Workspace inteiro. Acha serviço, documento,
comunicado e sistema — e, quando a frase é um pedido, **oferece a ação**.

**Quando é útil.** Quando a pessoa sabe o problema mas não sabe o nome da tela.
É o caminho de quem não quer aprender o menu.

**Como funciona (importa para o teste).** O endpoint devolve **fragmento HTML**,
não JSON — de propósito: o consumidor é o próprio navegador, e HTML pronto
elimina montagem de string no cliente e o XSS que vem com ela. Se você vê JSON
na aba Network, algo mudou.

**O recorte por permissão está no WHERE, não na tela.** O índice guarda os
*sujeitos* de cada entrada (`*`, `pessoa:N`, `unidade:N`, `depto:N`,
`papel:chave`) e a consulta filtra pelos sujeitos de quem busca. Anônimo tem só
`["*"]`.

**O que testar:**

| Digite | Resultado esperado |
|---|---|
| `a` (1 letra) | "digite ao menos 2 letras", sem consulta |
| `reembolso` | o serviço Reembolso nos resultados. **Sem** bloco de ação — palavra solta é consulta, não intenção |
| `quero solicitar férias` | bloco de ação **"Pedir: Férias"** no topo |
| `qual a política de viagens` | a política nos resultados. **Nenhum** bloco de ação |
| `preciso ver a política de férias` | a política. **Nenhum** pedido de férias oferecido |
| `laptop` | Notebook (termo curado) |
| `minha nr-35 está vencendo` | Reciclagem de NR |
| `meu equipamento parou de funcionar` | "Meu equipamento parou de funcionar" |
| `quero acesso` | **nenhuma** ação — empate entre VPN e sistema é ambiguidade |
| `ace` | **nenhuma** ação — é alguém no meio de digitar |
| `RH` | resultados, **sem erro 500** |

As quatro últimas linhas são as mais valiosas. O erro mais caro deste módulo é
oferecer um pedido a quem só queria ler a regra: a pessoa sai com um pedido
aberto e gera trabalho para outra. Por isso "preciso **ver**…" e "**qual** a…"
barram a ação, e empate não vira ação.

**Também deliberado:** `quero 3 dias de férias em setembro` abre o formulário de
férias **em branco**. O assistente não extrai valor da frase — pedido de férias
com data errada é pior que pedido vazio, porque o formulário mostra o que vai ser
enviado e o palpite não. **Não é bug.**

**Sobre a paleta:** o campo dentro dela é um campo limpo. Se aparecer borda dupla,
sombra ou um espaço vazio à esquerda onde deveria ter lupa, é o CSS da home
vazando — já aconteceu.

---

### 3.3 Meu dia — `/workspace/meu-dia/`

**Para que serve.** Responde **uma** pergunta: *o que exige você*. Só acionável.

**Quando é útil.** Todo dia, antes de qualquer sistema. É a tela que substitui
"abrir cinco abas para ver se tem algo meu".

**A distinção com Notificações é o desenho, e é testável:** Meu dia responde *o
que exige você*; Notificações responde *o que aconteceu*. Item resolvido sai do
Meu dia e **continua** no histórico de notificações.

**A ordem dos blocos é deliberada** — primeiro o que bloqueia outra pessoa,
depois o que bloqueia você, depois o que você deveria cobrar:

| # | Bloco | Aparece quando | Urgente |
|---|---|---|---|
| 1 | Esperando sua decisão | você é o aprovador da vez | ✅ sempre |
| 2 | Leitura obrigatória | há documento obrigatório não confirmado | ✅ sempre |
| 3 | Correspondência para retirar | chegou algo para você | ✅ se prazo legal |
| 4 | Precisam da sua correção | seu pedido foi devolvido | ✅ sempre |
| 5 | Passaram do prazo | seu pedido estourou o prazo prometido | — |
| 6 | Seus documentos precisam de revisão | você é **dono** de documento vencendo | ✅ só se vencido |
| 7 | Suas reservas de hoje | você tem reserva começando hoje | — |
| 8+ | Blocos dos domínios | um provider registrado tem pendência sua | — |

**O que testar:**

- **Blocos vazios não aparecem.** Com o banco limpo, a tela toda deve dizer que
  não há nada — não desenhar 7 molduras zeradas.
- A ordem acima. Ordenar por data faria a aprovação de ontem cair abaixo do
  pedido atrasado de anteontem — se você vê isso, é regressão.
- Máximo **6 itens por bloco**, com indicação de quantos ficaram fora. Quem tem
  40 pendências precisa da tela do domínio, não do resumo.
- "Esperando sua decisão" traz o valor represado em reais.
- Bloco 6 aparece **só para o dono do documento**. Ninguém mais precisa ver isso.
- **Degradação, não erro:** se um provider de domínio falhar, o bloco dele
  desaparece e o resto da tela continua. Para forçar, quebre o provider do
  dashboard e recarregue — a tela **não pode** dar 500. Falha de agregador é
  degradação.

---

### 3.4 Central de Notificações — `/workspace/notificacoes/`

**Para que serve.** O histórico do que aconteceu com você — incluindo o que já
foi resolvido.

**Quando é útil.** "Recebi um aviso ontem e não sei mais qual era."

**Tipos de notificação:** vez de aprovar, pedido aprovado, pedido devolvido,
pedido cancelado, pedido em atendimento, pedido concluído, pedido reaberto,
aprovação parada em papel sem dono, correspondência recebida.

**Os dois que NÃO vão para quem pediu**, e é de propósito:

| Aviso | Vai para | Por quê |
|---|---|---|
| **Pedido reaberto** | quem **atendeu** | é a resposta de quem recebeu a entrega dizendo que ela não resolveu |
| **Papel sem dono** | quem tem **`rh.admin`** | quem recebe não tem o que decidir, tem o que **conceder** — e o link leva à tela de papéis, não à bandeja |

**O que testar:**

- **Abrir a tela NÃO marca tudo como lido.** Isto é a regra central desta tela.
  Marcar em massa ao abrir é o padrão que faz a pessoa perder o aviso que ela
  ainda não leu: ela entrou para ver um item e apagou o rastro dos outros. A
  marcação é ação explícita, com botão.
- O sino leva para cá e **não abre painel dropdown**.
- Marcar como lida a partir de outra tela devolve você **para onde você estava** —
  não para a Central. Quem clicou no sino só para limpar o contador não quer
  mudar de tela.
- Limite de 60 itens, com indicação de truncamento.
- **Aviso repetido não é bug.** Não existe constraint de unicidade em
  notificação, de propósito: o modo de falha escolhe a si mesmo — constraint em
  aviso falha *silenciando* a pessoa, o que é pior que avisar duas vezes.

---

### 3.5 Catálogo de serviços — `/workspace/servicos/`

**Para que serve.** Os 26 serviços que a empresa presta ao próprio colaborador,
agrupados por **intenção** — não por departamento.

**Quando é útil.** "Preciso de alguma coisa da empresa e não sei com quem falar."

**Por que por intenção.** A pessoa procura "meu notebook quebrou", não "TI →
Hardware → Manutenção". Os grupos são: Equipamento e acesso, Trabalho e ausência,
Dinheiro, Viagem, Espaço e material, Desenvolvimento, Jurídico.

**O que testar:**

- Cada item mostra um **prazo**. Ele é *prometido* até haver 5 pedidos
  concluídos daquele item; a partir daí passa a ser a **mediana medida**. A tela
  deve distinguir os dois — prazo medido é o que dá credibilidade ao catálogo.
- Contadores de "abertas" e "devolvidas" no topo.
- **Item fora do seu alcance aparece marcado, não escondido.** Saber que o
  serviço existe é o que faz a pessoa parar de mandar e-mail. A recusa acontece
  na tela do pedido, com o motivo à vista.

---

### 3.6 Pedir um serviço — `/workspace/servicos/<chave>/`

**Para que serve.** O formulário. **No máximo 3 campos obrigatórios sem
condição** por item — o resto (unidade, centro de custo, gestor aprovador,
matrícula) vem da identidade. Formulário com 8 campos livres é o que faz o
usuário desistir e mandar e-mail.

**Quando é útil.** É o ato central do Workspace. Se esta tela falha, o produto
falha.

**O que testar — ramo, passo e escolha (o motor novo):**

Três mecanismos que alguns itens usam e a maioria não. Onde não são usados, a
tela continua sendo uma só, com todos os campos — e isso é o certo.

| Mecanismo | Onde ver | O que é comportamento correto |
|---|---|---|
| **Escolha** (`<select>`) | Acesso a um sistema, VPN, treinamento, abertura de vaga | Lista fechada, com "Selecione…" em branco no topo. Valor forjado no POST é recusado com "Escolha uma opção de…" |
| **Ramo** (`quando`) | VPN (só temporário pede "até quando"), reciclagem (dados do técnico terceiro), treinamento (interno × externo), abertura de vaga (só reposição pergunta "quem saiu") | O campo do outro ramo **não é exigido** e **não é gravado**, mesmo se tiver sido preenchido |
| **Passo** (trilha) | Reciclagem (2), treinamento (3), prestação de contas (3), abertura de vaga (2) | Trilha no topo, "Continuar"/"Voltar", e o **enviar só no último passo**. Passo que ficou sem conteúdo é pulado e sai da trilha — o do adiantamento só existe para quem tem um pendente |

- **Desligue o JavaScript e refaça um deles.** Todos os passos e todos os ramos
  aparecem de uma vez, e o formulário continua enviável. Quem separa o ramo é o
  servidor. Se preencher os DOIS ramos e enviar, só o escolhido é gravado — o
  outro é descartado em silêncio, e isso é correto: pedido que diz ao mesmo
  tempo "é interno" e "a instituição é a Fulana" faria o aprovador descobrir a
  contradição.
- Erro no passo 2 traz a tela de volta **no passo 2**, não no 1.
- Campo de outro ramo fica `disabled` além de escondido: campo escondido
  continua sendo enviado pelo navegador.
- **Um campo pode ficar CINZA em vez de sumir** (`quando_modo: cinza`): é o
  caso do "até quando" da VPN quando o período é definitivo. Ele fica na
  tela, apagado e desabilitado, porque vê-lo assim ensina o que "definitivo"
  significa — e a tela não pula. Sumir é o padrão para os outros.
- **Regressão já corrida:** os passos apareciam todos ao mesmo tempo, com
  "Continuar" e "Enviar" lado a lado. `[hidden] { display: none }` mora na
  folha do navegador, e `.au-campo { display: flex }` ganhava dela. Se um
  stepper voltar a mostrar dois passos juntos, é aqui que se olha.

**O que testar — cada item que mudou:**

| Item | O que ele pede agora |
|---|---|
| Acesso a um sistema | sistema (lista), motivo, nível (lista, opcional). A lista mora no admin — sistema novo entra sem deploy |
| Acesso à VPN | motivo, período (temporário/definitivo) e, só no temporário, "até quando" |
| Reciclagem de NR | qual documento vence (texto livre — a variedade é grande), a data de vencimento, e se for técnico terceiro: nome, CPF, empresa e **o responsável por ele**, porque o terceiro não acessa o Workspace |
| Treinamento ou curso | passo 1 interno ou externo; interno só escolhe o curso da lista; externo pede instituição, curso, início, período e **valor** — que não aparece no interno |
| Inscrição em vaga interna | qual vaga, por que quer, currículo opcional. **Não passa pelo gestor** — a cadeia normal faria o pedido de mudar de área ser avaliado por quem perde a pessoa |
| Abertura de vaga | cargo, quantidade (opcional, 1 por padrão), motivo da abertura e justificativa; "quem saiu" só na reposição |

**O que testar — formatação de cada tipo de dado:**

| Dado | Como tem de aparecer |
|---|---|
| Valor | `1.234,56` — ponto no milhar, vírgula no decimal, formatado **enquanto se digita** |
| Data | campo de data do navegador, com traço e calendário |
| Horário | campo de hora, com dois-pontos (o atestado tem dois: "saiu às" e "voltou às") |
| Dias | campo numérico, sem letra |

A máscara de valor é conforto de digitação: quem decide o número continua sendo o servidor, e sem JavaScript o campo aceita `1.234,56` e `1234.56` como sempre aceitou.

**O que testar — validação:**

- Envie vazio. Devem aparecer **todas** as mensagens por campo, de uma vez. Uma
  por vez é o que faz o usuário desistir no terceiro envio.
- Erro fica **junto do campo**, não numa faixa no topo.
- **Centro de custo não é digitado** — vem da lotação. Usuário sem centro de
  custo em item que exige um recebe: "Você não tem centro de custo na sua
  lotação. Peça ao RH para cadastrar." Isso é comportamento correto.
- O campo de valor aceita `1.234,56` **e** `1234.56`. O usuário digita como
  aprendeu. **Regressão já corrida:** `1234.56` era lido como **cento e vinte e
  três mil**, porque a leitura apagava todo ponto antes de trocar a vírgula.
  Hoje há uma leitura só, em `services/reembolso.valor_de()`; teste os dois
  formatos e também `1.234` (mil duzentos e trinta e quatro).
- Campo de arquivo se satisfaz com **arquivo**, não com texto. Já passou:
  digitar "cupom.jpg" num campo de texto validava o pedido sem comprovante.

**O que testar — anexos:**

- Máximo **5 arquivos por campo**. Não é limite técnico: fila de aprovação com
  40 arquivos por pedido não é revisada, é carimbada.
- Máximo **10 MB** por arquivo.
- Extensões: jpg, jpeg, png, gif, pdf, doc, docx, xls, xlsx, csv, txt.
- **Magic bytes são conferidos.** Renomeie um `.exe` para `.pdf` e envie: tem de
  ser recusado. Extensão e `Content-Type` não bastam.
- O nome original é preservado. Se aparecer `c3599522_2036a287_cupom.jpg`, é
  regressão — a validação prefixava um uuid a cada passagem, e o arquivo era
  validado duas vezes.

**O que testar — auto-aprovação:**

| Item | Limite | Comportamento |
|---|---|---|
| Prestação de contas | R$ 200 | ≤ 200 **e** cabendo no orçamento → aprovado na hora |
| Material de trabalho | R$ 300 | idem |
| EPI, atestado, declaração, chamado de TI, manutenção predial, reciclagem de NR, análise de contrato | 0, sem valor | aprovado na hora |
| Notebook, VPN, férias, home office, adiantamento, compra, viagem, veículo, treinamento | sem limite | **sempre** passa pela cadeia humana |

Auto-aprovado mostra: *"… aprovado automaticamente — está dentro da política."*
Os casos de EPI e reciclagem de NR são decisões de segurança, não de custo: negar
EPI é risco, não economia, e habilitação vencida bloqueia despacho.

**O que testar — os campos de R.H. e de dinheiro:**

| Item | Campos | Obrigatórios |
|---|---|---|
| Enviar atestado | data, horário, atestado, motivo, chefe ciente | os três primeiros |
| Trabalho remoto | período, dias, motivo | todos |
| Declaração ou comprovante | qual declaração, anexo | só a primeira |
| Adiantamento | motivo, data de pagamento, conta do beneficiário, supervisor ciente, orçamento | os três primeiros |

O teto de **3 obrigatórios** continua valendo, e é ele que decide o que ficou
opcional. Motivo do atestado é opcional porque o documento já o traz; o chefe
ciente também, porque o gestor vem da lotação — o campo existe para o caso em
que a realidade diverge do cadastro. O orçamento do adiantamento é opcional
porque foi pedido assim: "caso já haja um documento".

---

### 3.6.1 Prestação de contas item a item e acerto do adiantamento

> A tela chamava-se **Reembolso**. O nome mudou porque ele nomeava metade do
> que ela faz: ela também fecha a conta de um adiantamento, e nesse caso pode
> ser a **pessoa** que devolve, não a empresa que paga. Quem tinha dinheiro
> sobrando procurava onde devolver e não achava. `reembolso` continua entre os
> termos de busca — é como as pessoas chamam, e ⌘K tem de continuar achando.

**Para que serve.** É preenchida **uma compra por vez**: comprovante,
valor e motivo em cada linha. Não existe campo de valor total — quem soma é o
servidor. Antes eram cinco cupons somados à mão num número só, e quem aprovava
recebia "R$ 340,00" com cinco imagens sem saber qual era qual.

A tela agora é um **stepper de três passos**: as compras, o adiantamento, e o
acerto — que acontece depois do envio, em outra tela, e aparece na trilha em
cinza desde o começo. Esconder que ainda falta uma etapa é o que faz a pessoa
achar que terminou e deixar a conta do adiantamento aberta.

**O que testar — a lista de compras:**

- "Adicionar outra compra" acrescenta uma linha; "Remover" tira. A **última
  linha não é removível** — reembolso sem nenhuma compra não tem o que enviar.
- Teto de **20 compras** por reembolso. No limite, o botão de adicionar
  desabilita.
- O total aparece como **prévia** enquanto se digita. É prévia mesmo: quem soma
  para valer é o servidor, e a palavra está na tela de propósito.
- **Sem JavaScript a tela continua funcionando** — o servidor manda uma linha
  pronta e lê a lista do POST. Uma compra por envio, o que é pior, mas não é
  tela quebrada. Teste desligando o JS.
- Erro numerado por linha: *"Compra 2: anexe o comprovante."* Todos de uma vez.
- Ao voltar com erro, valor e motivo voltam preenchidos; **o arquivo não**, e a
  tela avisa disso. Nenhum navegador repopula `<input type=file>`.
- Linha aberta e deixada em branco é ignorada, não vira erro.

**O que testar — atrelar um adiantamento:**

- A seção só aparece se a pessoa tiver adiantamento pendente de prestação de
  contas. Sem nenhum, ela não existe — seletor vazio faz procurar o que não há.
- Só aparece adiantamento **já aprovado**: dinheiro que não saiu não deve
  prestação. E só o da própria pessoa.
- Adiantamento já prestado sai da lista. Se a prestação for **cancelada**, ele
  volta — senão um cancelamento acidental trancaria a pessoa para sempre.

**O que testar — o acerto (`/workspace/solicitacao/<id>/acerto/`):**

Ao enviar um reembolso atrelado, a tela seguinte é o acerto, e não "Minhas
solicitações". A conta fica aberta até ser confirmada; dá para voltar depois.

| Situação | O que a tela pede |
|---|---|
| Gastou **menos** que o adiantado | a conta da empresa à vista + **comprovante da devolução** (obrigatório) |
| Gastou **mais** | a conta bancária da pessoa, pré-preenchida com a que ela informou no adiantamento |
| Gastou **igual** | nada além de confirmar — e ainda assim vira registro |

- Sem `CONTA_BANCARIA_EMPRESA` configurada, a tela **não inventa um número**:
  diz para pedir os dados ao Financeiro. Depositar na conta errada é
  irreversível.
- Confirmar duas vezes é recusado. O acerto de outra pessoa dá 404.
- Depois de confirmado, a tela mostra "Conta fechada" com data e o link do
  comprovante.

**Na bandeja de aprovação**, o pedido item a item mostra a **lista de compras**
com o comprovante de cada valor, no lugar do bloco de anexos soltos.

---

### 3.7 Minhas solicitações — `/workspace/minhas-solicitacoes/`

**Linha do tempo.** Dentro do resumo, "O que aconteceu": pedido aberto,
aprovado por quem **em cada degrau**, assumido por quem, concluído, devolvido
com o motivo, reaberto, acerto fechado. Do mais antigo para o mais novo — ela se
lê de cima para baixo.

Numa cadeia de três degraus ela lê assim, e **os três aprovadores aparecem**:

```
Pedido aberto          Colaborador
Aprovado num degrau    Gestor       · Degrau 1 · gestor direto
Aprovado num degrau    Compras      · Degrau 2 · Compras
Aprovado — liberado    Diretoria
```

- **"Aprovado num degrau" e "Aprovado — liberado" são fatos diferentes**: um diz
  *fulano assinou*, o outro diz *o pedido está liberado*. O último degrau produz
  só o segundo — registrar os dois daria duas linhas para um fato só.
- Cadeia de **um degrau** não ganha a linha extra: ali "assinou" e "liberado"
  são a mesma coisa.
- O degrau do meio **não muda a situação** do pedido. Ele continua "aguardando
  aprovação", porque um degrau de três não liberou nada.

É o que responde *"esse pedido está parado há duas semanas, o que aconteceu com
ele?"*. Antes, a resposta exigia juntar a data de criação, a etapa de aprovação
e o `concluido_em` — e mesmo assim sumia o que importava: quem assumiu e largou,
quem devolveu e por quê.

- **Ato sem autor é caso legítimo**, e a tela escreve "automático": a
  auto-aprovação acontece porque o pedido cabe na política, e ninguém precisou
  decidir. Se aparecer um nome ali, é defeito.
- Só entra ATO que muda o estado. Acesso, leitura e navegação **não** entram —
  log que registra tudo é log que ninguém lê.

**Resumo em modal.** Clicar numa linha — ou no nome do serviço, que é um
botão de verdade — abre um `<dialog>` com o essencial: situação, valor,
centro de custo, quem decide agora, o que foi respondido no formulário, as
compras e os anexos. Esc fecha, o fundo fica inerte, e o foco não escapa —
é o mesmo elemento da paleta ⌘K, pelo mesmo motivo.

- O resumo mostra a **pergunta**, não a chave do banco: "Responsável por
  ele, e como falar com ele", nunca `tecnico_responsavel`.
- Clicar no link do anexo ou no botão Cancelar **não** abre o modal: ação
  que já tem dono não é roubada pela linha.
- Sem JavaScript o modal não abre, e a tabela continua mostrando tudo que
  ela já mostrava. O resumo é atalho, não a única forma de ver o pedido.


**Para que serve.** Onde o pedido está, e quem está com a bola.

**Quando é útil.** "Pedi reembolso semana passada e não sei se andou."

**O que testar:**

- Situações: aguardando aprovação, aprovada, em atendimento, devolvida,
  concluída, cancelada.
- **Devolvida mostra o motivo.** Devolução sem motivo é a pessoa refazendo às
  cegas.
- Cancelar funciona e só para os próprios pedidos.
- Anexos são baixáveis pelo dono.
- **"Parado: ninguém tem este papel hoje"** aparece na coluna *Esperando*
  quando a cadeia chegou a um papel vago. Quem lê não pode consertar — mas
  silêncio é o que faz a pessoa mandar e-mail perguntando, e o e-mail é o que
  este produto existe para substituir. Ver 3.8.2.

**"Não resolveu?" — a saída depois de concluído.** Dentro do resumo de um
pedido **concluído**, um bloco discreto com um campo de motivo e o botão
*Reabrir*. O pedido volta para a fila de quem atendeu — o **mesmo** pedido, com
o mesmo número e a mesma linha do tempo.

Sem isso, o notebook continuava sem ligar e a pessoa abria um **segundo**
pedido: o histórico do mesmo problema ficava partido em dois, o primeiro
fechava a estatística como *resolvido rápido*, e o atendente do segundo
começava do zero sem saber que já houve uma tentativa.

- Só **quem pediu** reabre. É por serem duas pessoas diferentes que a segunda
  palavra significa alguma coisa. O atendente arrependido apenas assume de novo.
- **Motivo obrigatório**, mesma regra da devolução: sem ele o pedido volta para
  quem já tentou uma vez, sem nada de novo para fazer diferente.
- **Prazo de 7 dias** contados da conclusão, e a data aparece por escrito na
  tela — sem ela o botão sumiria um dia sem aviso e pareceria defeito. Passado
  o prazo, a mensagem manda abrir um pedido novo, que é o certo: aquilo já é
  problema novo.
- **A aprovação não é refeita.** O que se contesta é a entrega, não a
  autorização — mandar o gestor aprovar de novo o mesmo notebook seria
  transformar reclamação em burocracia.
- **`concluido_em` volta a ser nulo**, e é a linha que mais importa: enquanto
  reaberto, o pedido sai da conta do prazo medido do catálogo. Quando for
  concluído de verdade, a conta é do dia do pedido **até a solução**.
- Quem atendeu recebe o aviso — é o único do módulo que **não** vai para quem
  pediu. Se o sino de quem reabriu tocar, é defeito.
- A linha ganha o selo *reaberto* e, enquanto dá tempo, a dica "não resolveu?
  abra o resumo". Ninguém abre um modal para procurar o que não sabe que
  está lá.

---

### 3.8 Baixar anexo — `/workspace/anexo/<id>/`

**Para que serve.** O **único** caminho até um arquivo do Workspace.

**Por que isso importa.** Os anexos moram **fora de `MEDIA_ROOT`**, porque o
nginx serve `/media/` sem autenticação nenhuma (`docker/nginx.conf`:
`location /media/ { alias /app/media/; expires 7d; }`). Não existe URL pública
para eles. Se esta view negar, **não há segunda porta**.

**O que testar:**

- O dono do pedido baixa.
- Outra pessoa recebe **403**, não 404. Quem chegou aqui tem o id de um anexo que
  existe; mentir sobre a existência não protege nada que o 403 já não proteja.
- O download vem sempre como **anexo** (`Content-Disposition: attachment`), nunca
  renderizado inline. SVG e HTML inline abrem porta para XSS na nossa origem.
- Arquivo ausente no disco com metadado na tabela → **404 com mensagem**, não 500.
- **Tente adivinhar a URL do arquivo em `/media/…`.** Deve dar 404. Se um anexo
  do Workspace aparecer sob `/media/`, é vazamento — e é grave.

---

### 3.8.1 Fila de atendimento — `/workspace/fila/`

**Para que serve.** O passo que faltava DEPOIS da aprovação. Até esta tela
existir, `EM_ATENDIMENTO` e `CONCLUIDA` eram estados que nada no produto usava:
o pedido era aprovado e parava ali para sempre, a não ser que alguém editasse
pelo `/admin/`.

**Quando é útil.** Para quem atende — R.H., Financeiro, TI, Compras, Logística,
Operações, SESMT. É a tela de trabalho deles.

**O que testar — quem vê o quê:**

- A fila mostra os pedidos dos **domínios que a pessoa pode atender**
  (`rh.atender`, `fin.atender`, `ti.atender`…). Quem não atende nada recebe
  **403** — e isso é correto: "sua fila está vazia" para quem não atende nada é
  mentira, e faz a pessoa esperar por trabalho que nunca vem.
- Pedido **ainda em aprovação não aparece**: não há o que atender enquanto
  ninguém decidiu.
- Ordem: **mais antigo primeiro**, sempre. Nunca por valor, nunca por urgência
  declarada — fila que se reordena sozinha é fila em que o pedido pequeno de
  janeiro nunca é atendido.
- O item "Atender" só aparece no trilho para quem tem fila.

**O que testar — os três verbos:**

| Ação | O que acontece |
|---|---|
| **Assumir** | põe o seu nome, situação vira "em atendimento", e quem pediu é avisado. O pedido **continua na fila** — sumir faria a pessoa perder de vista o próprio trabalho |
| **Concluir** | fecha, grava `concluido_em` e avisa. Pode ser feito sem assumir antes (o pedido de dois minutos), e o nome fica registrado do mesmo jeito |
| **Devolver** | volta para quem pediu, **com motivo obrigatório**. NÃO é reprovar: a aprovação continua valendo. É "não consigo atender assim" |

- Assumir o que outra pessoa já assumiu é recusado, com o nome dela na mensagem.
- Atender pedido de outra fila é recusado **mesmo pelo POST direto** — a tela
  não é a fonte de verdade.

**O que testar — o que voltou.** Um pedido reaberto por quem pediu (ver 3.7)
reaparece aqui, nas mãos de quem o havia concluído.

- A linha ganha o selo **"voltou sem resolver"** *com o motivo à vista*. Selo
  sem motivo faria a pessoa tentar de novo exatamente a mesma coisa — que foi o
  que já não resolveu.
- O quarto KPI, **"voltaram sem resolver"**, é o número que diz se "concluído"
  significa alguma coisa. Fila que só conta o que entra e o que sai parece
  saudável mesmo quando metade do que saiu está voltando.
- Sem atendente (a pessoa saiu da empresa), o pedido volta como **aprovado** e
  a fila inteira o vê — melhor que ficar preso a um nome que não existe mais.

**O que testar — e é a razão de a tela existir:**

Conclua **cinco** pedidos do mesmo item e volte ao catálogo. O card tem de
trocar "prazo estimado" por **"prazo medido"**. Antes desta fila isso era
impossível: `prazo_medido()` lê as conclusões, e nada no produto concluía nada —
o número na tela seria um chute para sempre.

---

### 3.8.2 Pessoas e papéis — `/workspace/pessoas/`

**Para que serve.** Cadastrar quem aprova o quê, sem passar pelo `/admin/` do
Django. Exige a permissão `rh.admin` — colaborador comum recebe **403**, e isso
é correto: a tela é o mapa de poder da empresa, e ela também *concede*.

**O que testar:**

- O **mapa vem primeiro**, antes da lista de gente. A pergunta que traz alguém
  aqui é quase sempre "por que o pedido não chegou em ninguém?".
- **Área sem aprovador aparece marcada** — "ninguém, o pedido fica parado". É o
  defeito que a tela existe para mostrar: a cadeia manda o pedido para um papel
  que não tem dono.

**E agora ele avisa, em vez de esperar ser descoberto.** Este era o jeito mais
silencioso de o produto perder um pedido: etapa por papel **não** gera
notificação — de propósito, porque "Diretoria" são três pessoas e três avisos
para um pedido só viram dois avisos órfãos depois da primeira decisão. Mas
quando o papel está **vago**, não há bandeja em que o pedido apareça: o contador
de todo mundo fica zerado e o pedido espera para sempre.

**O que testar:**

1. Deixe um papel de aprovação **sem ninguém** (ex.: Compras)
2. Abra um pedido cuja cadeia passe por ele e **aprove os degraus anteriores**
3. No momento em que a vez chega ao papel vago, quem tem `rh.admin` recebe
   *"… parou: ninguém tem o papel Compras"*, e o link leva a **`/pessoas/`** —
   não à bandeja: quem recebe não tem o que decidir, tem o que conceder
4. Quem pediu vê **"parado: ninguém tem este papel hoje"** em Minhas
   solicitações
5. Conceda o papel a alguém → o pedido aparece na bandeja dela

- **Papel COM titular não gera aviso nenhum.** O aviso é para o defeito, não
  para o funcionamento normal.
- Empresa **sem `rh.admin` cadastrado**: o pedido para do mesmo jeito e nada
  quebra — não há a quem avisar, e isso não pode virar erro de servidor.
- **Papel vago que não aparece em regra nenhuma não conta.** Ele não trava
  pedido, e marcá-lo transformaria o alerta em ruído.
- O mapa sai das **regras cruzadas com quem tem o papel** — a mesma fonte que o
  motor usa. Uma lista mantida à mão diria o que alguém achava que era verdade.
- **Escopo "unidade" ou "global" exige justificativa escrita.** É a diferença
  entre "aprova a própria equipe" e "aprova a empresa inteira", e no admin as
  duas são uma opção num `<select>` idêntico.
- **Papel para quem não tem lotação é recusado.** Aprovador sem unidade e sem
  gestor é a origem das 881 lotações vazias que fizeram este produto existir
  separado.
- **Encerrar não apaga**: a linha fica, com a data do último dia em que valeu e
  o motivo. "Quem aprovava isso em março?" continua respondível.
- Encerrar tem efeito **imediato**, não à meia-noite: a vigência é por dia e
  `vigentes()` inclui o dia de fim, então o fim gravado é o dia anterior. A
  exceção é o papel concedido e revogado no mesmo dia — esse vale até a
  meia-noite, porque vigência não pode terminar antes de começar.

---

### 3.9 Bandeja de aprovação — `/workspace/aprovacoes/`

**Para que serve.** Transformar carimbo em decisão. Aprovação sem contexto
financeiro é carimbo; com a barra tripla — realizado, comprometido, este pedido —
é decisão.

**Quando é útil.** Para o gestor, diretor ou sócio, quando algo espera assinatura.

**A cadeia, semeada por `semear_regras_aprovacao`:**

| Ordem | A partir de | Quem decide |
|---|---|---|
| 10 | R$ 0 | gestor direto |
| 20 | R$ 50.000 | diretoria |
| 30 | R$ 300.000 | sócios |

É **cumulativa**: um pedido de R$ 420.000 passa por gestor → diretoria → sócios,
nessa ordem.

**O que testar — o defeito mais grave já encontrado aqui:**

> Todas as etapas nascem `PENDENTE`. A bandeja mostrava **etapas futuras**: a
> diretoria via um pedido de R$ 420.000 cuja etapa 1 ainda era do gestor,
> rotulado "Etapa 1 de 3 · você" — **e o botão Aprovar funcionava**, por uma
> brecha de escopo global.

Reteste isso a cada release. Com um pedido de R$ 420.000 recém-criado:

- o **gestor** vê o pedido na bandeja;
- a **diretoria** e os **sócios** **não** o veem ainda;
- depois que o gestor aprova, ele aparece para a diretoria;
- o rótulo de etapa mostra a etapa correta ("Etapa 2 de 3").

**O que testar — o dossiê:**

- Barra tripla desenhada, com as três faixas. Se a barra **não desenha**,
  abra o console: já aconteceu por vírgula decimal (`8,42`) num atributo SVG,
  que é inválido e faz o navegador descartar o retângulo em silêncio.
- Pedido que estoura o orçamento: a barra **trunca** no fim e o alerta textual
  comunica o estouro. A barra não desenha fora do gráfico.
- Percentual antes e depois do pedido.
- **Os anexos abrem daqui.** Aprovar reembolso sem poder abrir o comprovante é
  exatamente o carimbo que esta tela existe para evitar.
- Histórico de etapas, com quem decidiu e quando.
- Aprovação **sem** centro de custo (férias, por exemplo) não mostra barra e
  **não quebra** a tela.

**O que testar — decisão:**

- Aprovar, devolver (exige justificativa), cancelar.
- Devolver gera notificação "vez de" / "pedido devolvido" para o solicitante.
- **Lote:** selecione várias e aprove. Se uma falhar, as outras **passam** e você
  vê o motivo específico de cada falha. Abortar tudo porque uma falhou é o
  comportamento errado.

**Questão de produto ainda aberta** (não abra bug, pergunte): a etapa do gestor
**não é intransponível** hoje — um aprovador com escopo global consegue assiná-la,
e isso fica auditado em `decidido_por`. Se deve ou não ser intransponível é
decisão pendente do dono do produto.

---

### 3.10 Módulos por departamento — `/workspace/m/<chave>/`

**Para que serve.** A vitrine de um departamento: a fatia do catálogo que ele
atende, mais os seus pedidos dentro dessa fatia.

**Quando é útil.** Departamento é onde a pessoa vai quando **já sabe com quem
quer falar**. Intenção (`/workspace/servicos/`) é onde ela vai quando **só sabe do
problema**. São dois caminhos para o mesmo lugar, de propósito.

**Um módulo não é um sistema novo** — é uma vista sobre o que já existe.

| Módulo | Domínios | Tela |
|---|---|---|
| RH | `rh.*` | catálogo |
| Financeiro | `fin.*` | catálogo |
| Operações | `ops.*` | catálogo |
| Logística | `log.*` | catálogo |
| Redes | `ti.acesso` | catálogo |
| Compras | `com.*` | catálogo |
| Universidade | `hab.*` | catálogo |
| Reservas | — | **própria** |
| Correspondências | — | **própria** |
| Documentação | — | **própria** |

**O que testar:**

- Cada módulo lista **só** os serviços dos seus domínios.
- Anônimo vê a vitrine e, no lugar de "Pedir", vê "Entrar".
- Módulo sem domínio e sem tela própria fica **"Em breve"** — e não abre página
  vazia. O honesto é dizer "em breve".
- A navegação por intenção cobre 100% do catálogo; a por departamento **não**.
  `jur.analise` (Análise de contrato) não tem tile nenhum hoje. **Isso é
  conhecido, não é bug.**

---

### 3.11 Documentação — `/workspace/documentacao/` e `/workspace/documentacao/<slug>/`

**Para que serve.** O acervo normativo com **vigência** e **trilha de leitura**.
Comunicado sem retorno é e-mail; documento com confirmação por versão é trilha de
auditoria.

**Quando é útil.** "Qual é a política de viagem?" — e, do outro lado, "quem já
leu a nova versão da NR?"

**Tipos:** POP, Política, Norma, Instrução de trabalho, Manual.
**Situações:** rascunho, vigente, revogado.

**O que testar — visibilidade:**

- **Público.** Quem está na rede vê a política de viagens sem senha.
- Documento com alvo de departamento **não** aparece para anônimo — os sujeitos
  de quem não está logado são só `["*"]`.
- Documento **vencido** e **revogado** ainda **abrem**, com aviso. Sumir com o
  texto faz a pessoa procurar no e-mail antigo, que é pior.
- **Revogado mostra o substituto.** Documento revogado sem para onde ir é um
  beco: a pessoa descobre que o texto não vale e não sabe qual vale.

**O que testar — confirmação de leitura:**

- Confirmar exige **login**. Confirmação sem identidade não é trilha de
  auditoria, é linha em branco.
- **Só POST.** Acesse a URL de confirmar por GET: deve redirecionar sem gravar.
  Sem isso, o pré-carregamento de link do navegador registraria conformidade que
  a pessoa nunca declarou — e é esse registro que se leva a uma audiência.
- A confirmação é **por versão**. Publique a v2 de um documento já confirmado: ele
  volta a aparecer como pendente em Meu dia.
- **Clique duas vezes rápido em "Confirmo que li".** Não pode dar 500. Já dava:
  `IntegrityError` capturado dentro de `transaction.atomic` quebra a transação.
- Cobertura de leitura ("quantos confirmaram a versão atual") visível para o dono.
- Aviso de vencimento: **30 dias** antes, no Meu dia do **dono**.

---

### 3.12 Reservas — `/workspace/reservas/`, `/reservas/<codigo>/`, `/reservas/minhas/`

**Para que serve.** Ocupar uma janela de tempo num recurso: sala, veículo,
equipamento.

**Quando é útil.** "Preciso da sala de reunião amanhã às 14h." Reserva **não** é
pedido que entra em fila de aprovação — é por isso que tem tela própria em vez de
formulário de catálogo.

**A decisão de desenho mais importante:** a tela mostra **a agenda antes do
formulário**. Formulário que aceita qualquer hora e responde "conflito" depois do
envio faz a pessoa tentar por adivinhação.

**O que testar — a vitrine:**

- Pública: anônimo vê os recursos e a agenda do dia.
- Navegação ontem / hoje / amanhã.
- `?dia=abacaxi` mostra **hoje**, não erro 500. O parâmetro é editável na barra
  de endereço.
- **Sem filtro por unidade, de propósito.** Quem está em Salvador pode precisar
  reservar a sala da matriz. A unidade aparece como informação, não como
  barreira.

**O que testar — reservar:**

- Exige login.
- Fim antes do início → recusa.
- **Horário no passado → recusa.** Reservar no passado não bloqueia nada e suja a
  agenda.
- Mais de **180 dias** de antecedência → recusa. O limite existe para pegar erro
  de digitação de ano ("2027" no lugar de "2026"), que é o caso real.
- Acima da duração máxima do recurso → recusa, dizendo o limite.
- **Choque de horário diz QUEM e QUANDO:** *"Sala Aurora já está reservada por
  Marina de 14:00 a 16:00 em 12/08."* "Horário indisponível" faz a pessoa tentar
  de novo às cegas; com o nome, ela resolve por conversa.
- **Encostadas passam.** 14:00–15:00 e 15:00–16:00 não conflitam. A checagem é
  estrita (`início < fim_existente` **e** `fim > início_existente`).
- **Concorrência:** duas pessoas reservando a mesma sala no mesmo segundo — só
  uma passa. A garantia é um `select_for_update()` na linha do **recurso**, dentro
  de transação. (Em SQLite o lock é no-op, mas o banco serializa escritas — os
  dois caminhos são corretos por razões diferentes.) Salas **diferentes** seguem
  em paralelo: travar a tabela faria a empresa inteira esperar por quem está
  marcando uma sala.
- Cancelar: só quem reservou, ou quem tem `res.admin.global` (papel `logistica`).
- Cancelar reserva já terminada → recusa com o motivo certo ("cancelar não muda
  nada"), diferente de "já cancelada".

---

### 3.13 Correspondências — `/workspace/correspondencias/`

**Para que serve.** Registrar o que chega na recepção **e avisar o destinatário**.
O aviso é o produto: registrar sem notificar troca a pilha na mesa por uma pilha
no banco de dados — e a segunda é pior, porque ninguém passa por ela sem querer.

**Quando é útil.** Intimação parada na recepção é o caso que este módulo existe
para evitar.

**Uma tela, dois públicos.** Quem tem `cor.registrar.global` (papel `logistica`)
vê a fila e o formulário; todo mundo vê o que chegou para si. Duas telas
separadas fariam a recepção decorar duas URLs e o resto da empresa tropeçar na
fila.

**Tipos, e a urgência é derivada do tipo:**

| Tipo | Urgente |
|---|---|
| Intimação ou notificação judicial | ✅ prazo legal |
| Multa ou autuação | ✅ prazo legal |
| Documento, Encomenda, Carta | — |

A urgência **não** depende de quem registrou marcar uma caixinha — a recepção não
tem como saber o que é urgente, e o remetente também não avisa.

**O que testar:**

- Tudo autenticado. É dado de pessoa.
- **Colaborador comum NÃO vê a fila** nem os não identificados. Correspondência
  revela quem recebe intimação e de quem, o que é informação sensível sobre a
  vida da pessoa — a fila não é pública nem para gestores.
- Registrar com destinatário conhecido → notificação **na hora**, e a mensagem
  diz "O destinatário foi avisado."
- Registrar **sem** destinatário e **sem** nome no envelope → recusa. Sem FK e sem
  nome, ninguém se reconhece na fila.
- **Destinatário não identificado é caso normal.** Registre com só o nome do
  envelope: entra na fila de não identificados, sem notificação. Carta endereçada
  à empresa, nome escrito errado, encomenda sem etiqueta — fingir que isso não
  acontece produz um cadastro obrigatório que a recepção preenche com qualquer
  nome, e aí a correspondência chega à pessoa errada.
- **Identificar depois avisa na hora.** É o único momento em que a pessoa pode
  saber que algo chegou para ela.
- Identificar o que já tem destinatário → recusa.
- Registrar entrega: `retirado_por` **pode ser outra pessoa** (secretária, colega,
  motoboy). Forçar que seja o destinatário faria a recepção registrar mentira
  para fechar a fila — e aí a trilha deixa de valer.
- Entregar duas vezes → recusa dizendo a situação atual.
- **A lista de destinatários é o organograma, não a tabela de usuários.** Só
  pessoas com lotação. Se aparecerem 1.432 nomes, é regressão: aqueles são
  técnicos e clientes do iConnect, que não trabalham aqui.

---

### 3.14 Comunicados e notícias — `/workspace/publicacao/<id>/`

**Para que serve.** O que a empresa está dizendo. Aparece em cards na home,
abre em tela própria.

**Quando é útil.** É o mural. Substitui o e-mail para todos.

**O que testar:** só publicações **publicadas** aparecem; até 4 por card na home;
sem publicação, o card diz "Nenhum comunicado no ar." (este é o estado vazio
declarado, e é correto).

---

## 4. Matriz perfil × tela

Use como plano de cobertura. **A coluna "Anônimo" é a mais esquecida e a que mais
esconde defeito** — nos dois sentidos.

| Tela | Anônimo | Colaborador | Gestor / Diretoria | Recepção (`logistica`) |
|---|---|---|---|---|
| Home | ✅ | ✅ + nome | ✅ + card "Esperando você" | ✅ |
| Busca ⌘K | ✅ só `*` | ✅ com seus sujeitos | ✅ | ✅ |
| Módulos | ✅ ("Entrar") | ✅ ("Pedir") | ✅ | ✅ |
| Documentação | ✅ só público | ✅ + do depto | ✅ | ✅ |
| Reservas (vitrine) | ✅ | ✅ | ✅ | ✅ |
| Meu dia | ➜ login | ✅ | ✅ + aprovações | ✅ |
| Notificações | ➜ login | ✅ | ✅ | ✅ |
| Catálogo / Pedir | ➜ login | ✅ | ✅ | ✅ |
| Minhas solicitações | ➜ login | ✅ | ✅ | ✅ |
| **Bandeja de aprovação** | ➜ login | ✅ **vazia** | ✅ **com itens** | ✅ vazia |
| Reservar / Minhas reservas | ➜ login | ✅ | ✅ | ✅ + cancelar de terceiros |
| Correspondências | ➜ login | ✅ **só as minhas** | ✅ **só as minhas** | ✅ **fila completa** |

As três células em negrito são os testes de autorização que valem mais: bandeja
vazia para colaborador, fila invisível para gestor, e cancelamento de terceiros
só para quem administra recurso.

---

## 5. Roteiros de ponta a ponta

### Roteiro A — reembolso auto-aprovado (o caminho felizinho)

1. Colaborador, ⌘K: `gastei com uber` → o assistente oferece **Reembolso**
2. Uma compra: foto do cupom, **R$ 80**, motivo "corrida até o cliente"
3. Envia → *"Reembolso aprovado automaticamente — está dentro da política."*
4. Minhas solicitações: situação **aprovada**, valor **R$ 80** (a soma, não um
   número digitado)
5. Meu dia: **não** aparece em "Esperando sua decisão" de ninguém

### Roteiro A2 — prestação de contas de adiantamento (o roteiro do dinheiro)

1. Colaborador pede **Adiantamento** de **R$ 1.000** — motivo, data de
   pagamento e a conta dele. Vai para a cadeia (adiantamento não tem limite).
2. Gestor aprova. O adiantamento passa a **dever prestação de contas**.
3. Colaborador pede **Reembolso**: duas compras, **R$ 620** e **R$ 180,50**, e
   atrela o adiantamento na seção que só aparece porque ele existe.
4. Envia → cai direto na tela de **acerto**: adiantado 1.000, gasto 800,50,
   **sobrou R$ 199,50**.
5. Tenta confirmar sem comprovante → recusado, com o motivo na tela.
6. Anexa o comprovante do depósito → *"Prestação de contas fechada."*
7. Volta à mesma URL: **"Conta fechada"**, com data e link do comprovante.
8. Novo reembolso: o adiantamento **não aparece mais** na lista de pendentes.

Para o outro lado, refaça com uma compra de **R$ 1.160**: a tela pede a conta
**da pessoa**, já pré-preenchida com a que ela informou no adiantamento.

### Roteiro B — a cadeia inteira (o roteiro mais valioso do produto)

1. Colaborador pede **Compra** de **R$ 420.000**
2. Sino do **gestor**: 1 não lida, "vez de aprovar"
3. Bandeja do gestor: o pedido aparece, "Etapa 1 de 3", barra tripla desenhada
4. **Bandeja da diretoria: o pedido NÃO aparece** ← o defeito histórico
5. **Bandeja dos sócios: NÃO aparece**
6. Gestor aprova → agora aparece para a **diretoria**, "Etapa 2 de 3"
7. Diretoria aprova → aparece para os **sócios**
8. Sócios aprovam → solicitante recebe "pedido aprovado"
9. Minhas solicitações: **aprovada**, com o histórico das três decisões

### Roteiro C — devolução

1. Colaborador pede **Viagem**
2. Gestor devolve com justificativa
3. Sino do colaborador: "pedido devolvido"
4. Meu dia do colaborador: bloco **"Precisam da sua correção"**, com o motivo
5. Notificações: o aviso continua no histórico depois de resolvido

### Roteiro D — leitura obrigatória com versão

1. Admin cria documento **vigente**, com **leitura obrigatória**
2. Colaborador: Meu dia mostra **"Leitura obrigatória"**
3. Abre e confirma → sai do Meu dia
4. Admin publica a **v2**
5. Colaborador: volta a aparecer como pendente ← o teste que importa
6. Dono do documento: vê a cobertura de leitura da versão atual

### Roteiro E — intimação

1. Recepção registra **Intimação** para o colaborador
2. Marcada **urgente** automaticamente, sem ninguém pedir
3. Sino do colaborador: "Intimação para você · com prazo legal"
4. Meu dia: bloco **"Correspondência para retirar"**, com etiqueta "prazo legal"
5. Colaborador retira; recepção registra a entrega
6. Sai do Meu dia; **continua** no histórico de notificações

### Roteiro F — choque de reserva

1. Colaborador A reserva a Sala Aurora, **14:00–16:00** de amanhã
2. Colaborador B tenta **15:00–17:00** → recusa **com o nome de A e o horário**
3. Colaborador B tenta **16:00–17:00** → **passa** (encostadas não conflitam)
4. A cancela a sua; B tenta 14:00–16:00 → passa
5. Meu dia de B, no dia: bloco "Suas reservas de hoje"

### Roteiro G — "não resolveu" (o roteiro que protege o número do catálogo)

1. Colaborador abre um chamado de TI; o atendente **assume** e **conclui**
2. Minhas solicitações → a linha diz *concluída* e traz "não resolveu? abra o
   resumo"
3. Abra o resumo: bloco **"Não resolveu?"**, com a **data limite por escrito**
4. Reabrir **sem motivo** → recusa. Reabrir com motivo → volta para a fila
5. Fila do atendente: a linha voltou, com o selo **e o motivo**; o KPI
   "voltaram sem resolver" marca 1; o sino **do atendente** tocou, o de quem
   reabriu **não**
6. Linha do tempo do pedido: aberto → assumido → concluído → **reaberto** →
   concluído. Um pedido só, um número só
7. Conclua de novo: o tempo medido vai do **dia do pedido até agora**, não até
   a primeira tentativa
8. Tente reabrir o pedido **de outra pessoa** pelo POST direto → **404**

---

## 6. O que ainda NÃO existe — não abra bug

| Não existe | Por quê |
|---|---|
| **Assistente de conhecimento (RAG)** | Bloqueado por dados: existem 5 documentos, todos de demonstração. A onda F precisa dos POPs e normativos reais. Não é código que falta. |
| Habilitações / certificações | O modelo vive no iConnect **Platform** (`fsm.Skill`), com **zero registros**. Não é módulo do Workspace. |
| Analytics pessoal | Decisão tomada (visível **só para a própria pessoa**, escopo `proprio`), não implementada. |
| Integração com M365 / HRIS | Suíte definida, integração não construída. |
| `semear_workspace` | Não existe. Documentos, recursos e correspondências entram pelo admin (ver 1.3). |
| Monitor de rede (viabilidade do módulo TI) | Pergunta aberta ao dono do produto. |
| 14 dos 24 módulos previstos | Marcados "Em breve" de propósito — ver 3.10. |

---

## 7. Lista de regressão — as 15 armadilhas já corridas

Cada linha abaixo é um defeito **real**, encontrado e corrigido. Elas são a
melhor lista de regressão que este produto tem, porque cada uma passou por uma
suíte verde uma vez.

| # | O defeito | Como ele se manifesta de novo |
|---|---|---|
| 1 | Bandeja mostrava etapas **futuras**, e o Aprovar funcionava | Diretoria vê pedido cuja etapa 1 é do gestor |
| 2 | Nove de dez tiles da home levavam a nada | Tile dá 404 |
| 3 | Topbar perdia sino **e** nome numa tela nova | Uma tela logada sem sino |
| 4 | ⌘K só funcionava na home | Atalho morto fora da home |
| 5 | `Esc` não fechava a paleta (Chrome consome no `type="search"`) | Modal preso |
| 6 | Campo da paleta herdava o CSS do hero | Campo dentro de campo, lupa escondida |
| 7 | `.au-tabela` **nunca** teve CSS, em 4 telas | Tabela sem estilo — invisível quando vazia |
| 8 | Barra SVG não desenhava por vírgula decimal (`8,42`) | Barra tripla ausente, só no console |
| 9 | Anexos com URL pública em `/media/` | Arquivo do Workspace acessível sem login |
| 10 | Duplo clique em "Confirmo que li" → 500 | `IntegrityError` dentro de `atomic` |
| 11 | Busca por `RH` dava `NoReverseMatch` e matava a busca inteira | Busca 500 em termo específico |
| 12 | `1234.56` no campo de valor virava **R$ 123.456,00** | Pedido cem vezes maior que o gasto, aprovado por quem confiou no número da tela |
| 13 | Etapa num papel **sem titular** não aparecia na bandeja de ninguém | Pedido em "aguardando aprovação" para sempre, sem lado do outro lado |
| 14 | Um teste publicava sempre às `08:00:00` fixas | Suíte reprovava **entre 00:00 e 08:00** — e passava o dia inteiro depois disso |
| 15 | Linha do tempo mostrava só o **último** aprovador | Cadeia de três degraus lida como se gestor e área nunca tivessem assinado |

**Se você só tiver uma hora**, teste: o Roteiro B (linha 1), a passagem pelas 6
telas logado (linha 3), ⌘K + Esc em três telas (linhas 4 e 5), e o console aberto
em todas (linhas 7, 8 e 11).

---

## 8. Onde reclamar de quê

| Sintoma | É bug de |
|---|---|
| Tela `/workspace/…` errada | **Workspace** — abra o bug |
| Tela `/dashboard/…`, `/fsm/…`, `/login/` | **iConnect Platform** — outro produto, outra suíte |
| `no such column` / `OperationalError` | migração pendente (seção 1.1) |
| Tela vazia sem dado | massa de teste faltando (seção 1.2 e 1.3) |
| "Você não tem acesso" | papel/lotação faltando (seção 1.4) |
| Módulo "Em breve" | decisão de produto (seção 6) |
| iConnect não é o tile principal | decisão de produto (seção 3.1) |
| Pedido não pré-preenchido pela frase da busca | decisão de produto (seção 3.2) |
