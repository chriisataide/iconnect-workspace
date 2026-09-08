# Guia do Portal ADB360 — para quem vai testar

> **Para quem é este documento.** Para o QA que precisa entender *o que cada tela
> promete* antes de decidir se ela cumpriu. Não é um roteiro de cliques: é o
> contrato de cada aba — para que serve, em que momento da vida do colaborador
> ela aparece, o que é comportamento correto e o que é defeito.
>
> Leia a seção 1 antes de abrir o navegador. Ela evita as duas horas perdidas
> mais comuns: testar contra um banco sem dados, e abrir bug em cima de uma
> decisão de produto.

---

## O que mudou nesta rodada (setembro/2026)

Se você já testou o Workspace antes, **estas são as telas novas**. Elas foram
construídas juntas e nunca passaram por QA de gente — é aqui que o retorno vale
mais.

| Tela | Onde está | O teste que mais protege |
|---|---|---|
| Apresentação de Resultados | 3.18 | 403 para quem não tem escopo — **nunca** tela zerada |
| Perfurar / cruzar / pivotar / detalhar | **3.18.1** | o número **encolhe** ao descer, e o estado sobrevive a copiar-e-colar a URL |
| Fontes de dados | 3.19 | `eco.carga` ≠ `eco.ler`: o T.I. não vê a margem |
| Painel de exceções | 3.20 | nenhum cartão que não disparou |
| Ciclos e ATA | 3.21 | ler a pauta ≠ conduzir a reunião |
| Planos de ação | 3.22 | fonte fora do ar **não fecha** plano |
| Metas, avaliação e PDI | 3.23 | a meta guarda a fórmula, não o número |
| Orçamento anual e revisão | 3.24 | revisão não apaga a versão anterior |
| Os outros públicos da marca | 3.25 | nenhum link para fora que aponte para dentro |
| Gráficos com biblioteca | **2.8** | tabela irmã em todos, e console limpo |
| **Quadro e jornada** (16) | **3.18.2** | `vendas` NÃO abre; R.H. abre sem ver dinheiro |
| **Satisfação do cliente** (17) | **3.18.3** | `vendas` abre — e não vê a 10 |
| Trilho em grupos recolhíveis | **1.6** | só o grupo da tela atual nasce aberto |

**Comece por aqui, nesta ordem:**

1. A **seção 1 inteira** — em especial o bloco de semeadoras da § 1.2, que
   cresceu. **Sem ele, as telas 10 a 15 abrem vazias**, e isso não é bug.
2. A **seção 2.8** (gráficos) e a **4** (matriz de permissão), que valem para
   várias telas de uma vez.
3. O **Roteiro H** (seção 5). É o mais denso do produto: sozinho ele cobre seis
   das armadilhas já corridas da seção 7.

**As três coisas que são achado de segurança, e não bug de tela:** dado pessoal
em grade ou em query string; endpoint que aceita um recorte que a tela recusa; e
tela de dado agregado que abre zerada em vez de recusar.

---

## 0. Antes de tudo: são dois produtos, não um

Isto é a coisa mais importante do documento e a que mais gera falso-positivo.

| | **Portal ADB360** | **iConnect Platform** |
|---|---|---|
| Organiza | a vida corporativa da **empresa** | a operação de **atendimento aos clientes** |
| Usuário | o colaborador da Autodefesa Brasil | o técnico, o operador, o cliente |
| Onde vive | `/workspace/…` | `/login/`, `/dashboard/…`, `/fsm/…` |
| Pessoas | organograma (`identidade.Lotacao`) | papéis do iConnect (`UserRole`, ~1.432 registros) |

> **O produto foi rebatizado em 04/09/2026.** Chamava-se *iConnect Workspace* e
> agora é **Portal ADB360**. Duas coisas **não** mudaram, e as duas geram
> falso-positivo se você esperar o contrário:
>
> - **A rota continua `/workspace/…`.** Endereço é endereço: mudar quebraria
>   todo link já colado em e-mail, ata e chamado, e link antigo que dá 404 é
>   pior que link com nome antigo.
> - **O app Django continua se chamando `workspace`**, e o `/admin/` mostra o
>   nome novo. Se você vir "iConnect Workspace" em alguma tela, **é bug** — há
>   um teste varrendo todos os templates atrás disso.
>
> O selo com o número da tela **saiu da topbar** na mesma data (ver 3.2.1).
>
> **O logo é o da Autodefesa Brasil**, e o favicon é a águia. Confira nas duas
> cascas — `/workspace/` e `/entrar/`, que têm cascas DIFERENTES — e na aba do
> navegador. Logo quebrado **não derruba tela nenhuma**: o navegador desenha o
> ícone de imagem faltando e segue, e quem testa olha o conteúdo. Se aparecer o
> retângulo vazio no alto, é bug.
>
> O `alt` do logo diz **"Autodefesa Brasil"** e não "Portal ADB360" — o nome do
> produto já está escrito ao lado, em texto, e repetir faria o leitor de tela
> dizer o nome duas vezes sem nunca dizer de quem é o portal.
>
> **A cor da barra do navegador continua azul-marinho**, e é deliberado: o
> `theme-color` acompanha o sistema de design, que é navy em todas as telas. O
> vermelho da marca é do logo, não da interface.

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

**E o banco precisa de um superusuário ANTES de semear.**

```bash
python manage.py createsuperuser
```

Não é formalidade: `semear_acessos` e `semear_perfis` **abortam** sem ele, com
*"Nenhum superusuário no banco. Toda concessão precisa de autor"*. É de
propósito — dar papel a alguém é um ato que fica registrado, e registro sem autor
não serve para auditar nada. Sem esse passo você fica sem **os 17 perfis de
teste da § 1.2.1**, que é metade deste guia.

### 1.2 Semear o que tem semeadora

```bash
python manage.py semear_papeis --aplicar              # os 17 papéis e suas permissões
python manage.py importar_organograma docs/exemplos/organograma-inicial.csv --criar-usuarios --aplicar
python manage.py semear_acessos --aplicar             # senha sorteada + papel por cargo
python manage.py semear_perfis --aplicar              # um usuário POR PAPEL, para testar
python manage.py semear_centros_custo --aplicar       # um CentroCusto por código usado na lotação
python manage.py semear_catalogo --aplicar            # os serviços do catálogo
python manage.py semear_regras_aprovacao --aplicar    # gestor → 50k → 300k
python manage.py semear_recursos --aplicar            # salas, veículos, equipamentos
python manage.py semear_estoque --aplicar             # materiais e saldo inicial
python manage.py semear_frota --aplicar               # veículos, ligados aos recursos
python manage.py semear_cursos --aplicar              # NRs e treinamentos
python manage.py semear_faq --aplicar                 # a base do assistente
python manage.py semear_orcamento --aplicar           # o teto por centro de custo vira orçamento anual

# As telas 10 a 15 (§ 3.18 a 3.24) NÃO EXISTEM sem estas cinco linhas.
# `semear_fontes` vem antes de `semear_resultados` por regra do produto: o
# carregador RECUSA começar sem registro de fonte — carga sem procedência é
# boato com aparência de relatório.
python manage.py semear_fontes --aplicar              # as 4 fontes e a precedência entre elas
python manage.py semear_resultados --aplicar          # o espelho: 13 meses, por 3 fontes
python manage.py semear_regras_excecao --aplicar      # as 18 regras + as 5 desligadas
python manage.py semear_ciclos --aplicar              # a pauta mensal (12 etapas)
python manage.py semear_ciclo_metas --aplicar         # o ciclo de metas do ano corrente

python manage.py reindexar_busca                      # popula o índice da ⌘K
```

**Um passo à mão, e só um: o teto de cada centro de custo.**
`semear_centros_custo` cria os centros **sem** orçamento mensal, de propósito —
vazio significa *não definido*, que é diferente de zero (zero o aprovador leria
como "tem folga"). Consequência prática: `semear_orcamento` termina com *"0
orçamentos criados, 3 centros sem teto definido"*, e **a tela 15 (§ 3.24) abre
com estado vazio**.

Para testá-la, preencha o **orçamento mensal** dos três centros em
`/admin/financas/centrocusto/` e rode `semear_orcamento --aplicar` de novo. Isso
não é defeito: é a mesma distinção entre "não definido" e "zero" que a bandeja de
aprovação usa.

> **Se as telas de resultado abrirem vazias, é porque faltou este bloco** — e
> não é bug. Toda semeadora é idempotente e roda em simulação **sem**
> `--aplicar`: sem a flag ela mostra o que faria e desfaz a transação, o que é o
> jeito seguro de conferir antes de gravar.

> **`semear_centros_custo` não é enfeite.** Sem ele toda pessoa tem um código de
> centro de custo e nenhum código existe — e a bandeja de aprovação diz "CC sem
> orçamento definido" em vez de desenhar a barra tripla. Já foi confundido com
> defeito da barra.

### 1.2.1 Os 17 perfis de teste — um por papel

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
| `logistica@icodev.com.br` | Suprimentos | — |
| `recepcao@icodev.com.br` | — | — (registra correspondência, e **nada** de estoque) |
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

Três coisas não têm comando de semente. **Nenhuma delas precisa do `/admin/`** —
as três se criam dentro do produto, o que é o ponto: se a única porta fosse o
admin, quem publica norma ou comunicado precisaria de `is_staff`.

| Falta | Onde criar, DENTRO do produto | Sem isso, a tela mostra |
|---|---|---|
| Documentos (POP, políticas) | Documentação › Acervo normativo › Novo documento, como `rh@` | acervo vazio |
| Comunicados e notícias | Comunicados › Escrever, como `rh@` ou `diretoria@` | cards vazios na home |
| Correspondências | a própria tela, como `recepcao@` | fila vazia |

Recursos (salas, veículos) **têm** semeadora desde a onda de reservas:
`semear_recursos --aplicar`.

> ⚠️ **A lacuna é real, e é menor do que já foi.** Sem semeadora, cada QA monta
> a massa à mão e testa contra dados diferentes. Se atrapalhar, peça o comando —
> é meia hora de trabalho e torna o ambiente reproduzível.

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

### 1.5 A topbar diz quem você é, e por onde sair

Em **toda** tela do Workspace, no canto superior direito:

| Estado | O que aparece |
|---|---|
| **Entrou** | nome, a área embaixo em corpo menor, e o botão de **sair** |
| **Anônimo** | só o botão **Entrar** — "Sair" para quem nunca entrou não faz nada |

- **O visitante anônimo não pode ver o nome de ninguém.** O hub é aberto e
  `pessoa_da_requisicao()` devolve uma pessoa de *referência* para calcular
  alcance — usar aquela função na topbar poria o nome de um colega no canto da
  tela de quem nunca entrou. Se aparecer um nome sem login, é bug grave.
- **Sair é POST, não link.** `LogoutView` recusa GET desde o Django 4.1, e está
  certo: link que desloga permite a um site de fora tirar você daqui com uma
  imagem escondida. Abrir `/sair/` pela barra de endereço **não** pode
  deslogar.
- Em tela estreita a área some e fica o nome: nome sem área ainda identifica;
  área sem nome, não.

---

### 1.6 O trilho abre um grupo, e não todos

Os grupos do trilho são `<details>`: só o da tela em que você está nasce aberto.
Antes todos ficavam abertos, e para quem tem todas as permissões isso eram 28
itens de uma vez.

**O que testar:**

- **Abra `/workspace/resultados/`** — "Resultados da empresa" está aberto e os
  outros fechados. Vá para `/workspace/pessoas/` — agora "Gestão" abre e o
  anterior fecha.
- **Clique num título de grupo.** Ele abre e fecha. Se não fechar, alguém trocou
  o `<details>` por JavaScript — e a CSP bloqueia `onclick` **em silêncio**.
- **Desligue o JavaScript.** Os grupos continuam abrindo. É o teste que separa
  disclosure nativo de gambiarra.
- **Conte os itens de cada grupo: no máximo oito.** Acima disso a lista deixa de
  ser lida de relance e passa a ser varrida item a item.
- **"Acompanhar" não existe mais.** Ele virou "Resultados da empresa" e
  "Gestão". Se você vir o antigo, é regressão.

**Quantos itens cada perfil vê** — use como gabarito:

```
colaborador    11 itens   3 grupos: Hoje, Consultar, Pedir
gestor         15 itens   5 grupos
diretoria      28 itens   7 grupos
```

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

`style-src` tem `unsafe-inline` desde a Onda 9.5 — a biblioteca de gráficos
precisa dele. O navegador **aceita** um `style="…"` agora, e por isso a regra
passou a ser cobrada por lint (`test_csp_e_estilo_inline.py`), sobre o
repositório inteiro.

O que continua valendo: **estilo inline escrito por nós é bug**, mesmo desenhando
na tela. O que a biblioteca injeta é aceito. E `script-src` continua sem
`unsafe-inline` — um `onclick=` segue bloqueado, em silêncio.

**Como testar:** abra o console do navegador em cada tela. Zero erro de CSP,
zero aviso de recurso bloqueado. O console é fonte de verdade aqui — ele já
pegou uma barra SVG que não desenhava por causa de vírgula decimal, e uma tabela
inteira sem CSS.

---

### 2.8 Todo gráfico tem tabela irmã, e ela vem do mesmo lugar

Os gráficos são desenhados por uma biblioteca (Apache ECharts, servida **pelo
projeto** — nunca por CDN). Isso significa que **sem JavaScript não há gráfico**,
e por isso todo gráfico traz abaixo um `<details>` com os mesmos números em
tabela.

**Como testar, em quatro passos:**

1. **Abra a tabela de cada gráfico.** Os números têm de ser **os mesmos**, e em
   pt-BR (`1.234,56`, `840 Mil`, `1,23 Mi`). Se um deles vier com ponto decimal,
   o formatador foi contornado — os dois desenham do mesmo objeto, então divergir
   é sempre bug.
2. **Desligue o JavaScript e recarregue.** A tabela tem de aparecer **já aberta**.
   Se ela vier fechada, quem depende dela é exatamente quem não consegue abri-la.
3. **Console limpo.** Zero erro de CSP. Um bloqueio aqui deixa o gráfico
   **em branco, sem erro visível na tela** — o console é a única testemunha.
4. **Cor nunca sozinha.** Todo estado colorido tem rótulo ou texto ao lado.
   Verde e vermelho como única diferença exclui quem não distingue os dois, e é
   bug de acessibilidade, não preferência.

**No PDF não há gráfico, de propósito** — ele leva as tabelas, e o rodapé diz
isso e onde ver os desenhos. Gráfico em PDF exigiria um navegador inteiro rodando
no servidor. **Não abra bug por isso** (ADR-041).

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
- O cartão "Pedir um serviço" promete um número concreto. Confira que bate com
  `ItemCatalogo` ativos — o número sai do banco, e um guia que o repete aqui
  passa a mentir na primeira vez que alguém desativa um item.
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

#### 3.2.1 Prefixos e código da tela

Cinco atalhos, anunciados na linha abaixo do campo. A legenda fica **fora** do
`placeholder` de propósito: placeholder some no primeiro caractere digitado,
justamente quando a pessoa ainda está decidindo como buscar.

| Digite | Resultado esperado |
|---|---|
| `02.2` | **um** resultado, "Aprovações", no grupo *Ir para*. Nada mais junto |
| `02` | "Serviços". Um resultado só |
| `77` | busca comum por "77" — código que não existe não é atalho |
| `s: reembolso` | só o **serviço**. Sem o documento, sem aplicativo, sem ação |
| `d: reembolso` | só a **política**. Sem o serviço |
| `#<nº de um pedido seu>` | o seu pedido |
| `#<nº de um pedido alheio>` | **nada**. O recorte por sujeito continua valendo |
| `x: reembolso` | busca comum — prefixo desconhecido é texto, não erro |
| `s:` sozinho | nada. Ainda não é uma busca |

**`p:` é o teste que mais importa aqui.**

- Com `rh@icodev.com.br` (administra papéis): `p: souza` traz **nome, cargo e
  área**. Se aparecer e-mail, CPF ou centro de custo na linha, **abra bug** — é
  exatamente a grade que a leitura do benchmark marcou como não copiar.
- Com `colaborador@icodev.com.br`: `p: souza` faz uma busca **comum**, sem grupo
  "Pessoas" e **sem aviso nenhum**. Um grupo vazio dizendo "sem resultados"
  seria defeito, não cortesia: ele contaria que existe um diretório do outro
  lado da porta.
- A legenda embaixo do campo **não deve mostrar `p:`** para quem não administra
  papéis. Atalho anunciado que devolve vazio é pior do que atalho nenhum.

**O código da tela NÃO aparece mais na topbar** — saiu em 04/09/2026. Ele ficava
ao lado do nome do produto e, lido ali, virava número de página; com a contagem
do sino do outro lado, a barra tinha duas numerações que não conversavam.

**O endereçamento continua inteiro**, e é isso que se testa agora: digite `02` na
busca, e abra `/workspace/ir/02/`. Os dois têm de levar ao catálogo de serviços.
Se pararem de funcionar, **abra bug** — o selo era a etiqueta, não o mecanismo, e
"abra a 10" numa ata precisa continuar abrindo alguma coisa.

O que se perdeu é a **descoberta**: quem estava numa tela via o código dela sem
procurar. A lista viva sai do próprio produto:

```bash
python manage.py shell -c "from workspace import enderecamento as e; [print(t.codigo, t.nome, t.url) for t in e.todas()]"
```

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

**Para que serve.** Os serviços que a empresa presta ao próprio colaborador,
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
**Filtro, busca e paginação.** Chips de situação, uma caixa de busca e 20 por
página.

- O recorte fica na **URL** (`method="get"`), então dá para mandar o link para
  alguém e voltar nele pelo histórico. Filtro que só existe em POST se perde
  ao apertar F5.
- **O filtro sobrevive à troca de página.** Clicar em "próxima" dentro de um
  recorte não pode voltar para a lista inteira.
- **A busca olha o NOME do serviço e o motivo da devolução — não o conteúdo do
  formulário.** Ali moram atestado, dados bancários e motivo de afastamento;
  uma busca que varre isso vira um vazador de dado sensível para quem espia a
  tela de alguém.
- **`?p=99` numa lista de duas páginas não dá 404**, cai na última: quem chega
  assim veio de um link velho, e castigar a pessoa por uma URL que o próprio
  produto deu é falta de educação do software.
- **Filtro sem resultado NÃO diz "você ainda não pediu nada".** Essa frase para
  quem filtrou é mentira, e faz a pessoa achar que perdeu os pedidos.
- Lista com uma página só **não mostra a paginação** — controle dizendo
  "página 1 de 1" ensina a ignorá-lo.

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

**O que testar — os filtros.** Tudo · Assumidos por mim · Sem dono · Além do
prazo.

- **Os KPIs do topo NÃO acompanham o filtro.** "3 atrasados" não pode virar "0
  atrasados" porque a pessoa clicou noutra aba — a tela passaria a esconder
  justamente o que ela existe para mostrar.
- **"Sem dono" é o recorte que mais importa**: é onde a fila trava quando todo
  mundo acha que é do outro.
- Filtro vazio numa fila cheia diz **"nada com esse recorte"**, e não "nada
  esperando você".

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

São **doze**, e nenhum deles é "Em breve" (conferido em 03/09/2026):

| Módulo | Domínios | Tela |
|---|---|---|
| RH | `rh.*` | catálogo |
| Financeiro | `fin.*` | catálogo |
| Operações | `ops.*` | catálogo |
| Suprimentos | `log.*` | catálogo |
| Redes | `ti.acesso` | catálogo |
| Vendas | `ven.*` | catálogo |
| Marketing | `mkt.*` | catálogo |
| Jurídico | `jur.*` | catálogo |
| Universidade | `hab.*` | catálogo |
| Reservas | — | **própria** |
| Correspondências | — | **própria** |
| Documentação | — | **própria** |

**O que testar:**

- Cada módulo lista **só** os serviços dos seus domínios.
- Anônimo vê a vitrine e, no lugar de "Pedir", vê "Entrar".
- **Nenhum módulo abre "Em breve" hoje**, e o selo não aparece na home. Se ele
  voltar a aparecer, é regressão: "em breve" é uma promessa, e uma promessa que
  ninguém assinou é pior que a ausência (ADR-039).
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

### 3.15 Indicadores — `/workspace/indicadores/`

**Para que serve.** Os números que respondem se o portal está funcionando:
quanto entra por área, quanto tempo leva até resolver, onde trava, e o que
volta sem resolver.

**Por que isso importa.** O produto media tudo e não mostrava nada. O índice
`wks_evento_quem_idx` foi criado com um comentário dizendo para que servia —
*"quantos o Fulano concluiu em julho"* — e **nada consultava**.

**Quem vê o quê:**

| Entrar como | Vê |
|---|---|
| `diretoria@` · `socios@` · `rh@` | a **empresa inteira** (permissão `ind.ler`) |
| `compras@` · `financeiro@` · `ti@` … | **só a própria área** |
| `colaborador@` · `gestor@` · `auditoria@` · `monitoramento@` | **403** |

O item aparece no trilho, em "Acompanhar", só para quem tem painel.

**O que testar:**

- **403 e não tela zerada** para quem não tem área nenhuma. Números todos em
  zero para quem nunca vai ter dado faz a pessoa achar que a empresa parou —
  é a mesma regra da fila de atendimento.
- **Quem atende vê só a sua fatia.** `compras@` não pode enxergar os números
  do R.H. — e não deveria precisar pedir relatório para a diretoria toda
  semana para ver os próprios.
- **Os tempos são MEDIANAS, não médias**, e isso está escrito na tela. Um
  pedido esquecido oitenta dias numa fila puxaria a média da área inteira e
  faria o setor parecer lento.
- **"Até aprovar" e "até resolver" ficam separados.** Somados viram um número
  que ninguém sabe consertar: não se sabe se falta gente na fila ou se o
  gestor não decide.
- **"—" e não "0" sem amostra.** Zero diria "resolve no mesmo dia", que é o
  oposto de "ainda não sei".
- **Área sem movimento não vira linha.** Zero em todas as colunas é ruído que
  empurra para baixo as áreas que têm o que mostrar.
- **A taxa de reabertura nunca passa de 100%.** Na primeira medição deu
  **200%**: um pedido reaberto deixa de estar "concluído", então saía do
  denominador e continuava no numerador. O denominador é quantos já foram
  entregues *alguma vez*.
- **O período muda tudo**: 30, 90 ou 365 dias. `?dias=99999` cai no padrão em
  vez de fazer uma consulta enorme por uma URL digitada.
- **Fora da janela não conta.** Indicador acumulado desde a fundação nunca
  melhora, por melhor que a equipe fique.

---

### 3.16 Carimbo de frescor — em toda faixa de números

**Para que serve.** Responde, sem ninguém abrir código, *de quando é este
número*. Fica logo acima da faixa de números, em letra miúda.

**Onde aparece hoje.** Quatro telas, uma faixa cada: Indicadores, Bandeja de
aprovação, Fila de atendimento e Painel da Universidade.

**O que ele diz hoje, e por que é pouco.** *"Workspace · em tempo real"*, nas
quatro. Todo número destas telas é do próprio Workspace, e dado próprio é lido
no instante em que a tela abre — não há carga, não há atraso, não há o que
carimbar além de "agora". O carimbo passa a dizer coisas diferentes quando os
conectores existirem.

**Por que ele existe antes de haver dado de fora.** Porque é uma disciplina, e
disciplina só vale se toda faixa nascer com ela. A suíte reprova faixa de
números sem carimbo — e reprova carimbo em tela sem números, porque carimbo sem
número é ruído.

**O que testar:**

- O carimbo aparece **acima** da faixa, e não no cabeçalho da tela. Um carimbo
  no topo estaria certo sobre metade do conteúdo no dia em que a tela tiver
  duas fontes.
- Em tela **sem** faixa de números agregados (catálogo, documentação, formulário
  de serviço), **não** deve haver carimbo nenhum.
- Na fila de atendimento com a fila **vazia**, não há faixa de números e não há
  carimbo — o vazio ali é uma frase, não um zero, e frase não se carimba.
- **Nenhuma tela mostra um horário de relógio.** Se aparecer "atualizado às
  14:32" em qualquer lugar, **abra bug**: o instante tem de vir do registro de
  carga, e um template que lê o relógio diz "agora" para dado de ontem.
- O carimbo só ganha **cor** quando é alerta. Como nenhuma fonte externa existe
  ainda, hoje **nenhum** carimbo deve aparecer colorido. Um colorido agora
  significa fonte declarada sem provedor.

**O que ainda não dá para testar** (volta com os conectores, na onda de
ingestão): fonte com carga falha mostrando o último dado bom com a idade em
destaque, e a idade passando do limite declarado pela fonte.

---

### 3.17 Cargas de fontes externas — sem tela, por enquanto

**Para que serve.** Trazer para dentro o que o Workspace não é dono: resultado
financeiro e folha do Sankhya, projetos do monday, contratos e satisfação do
Platform, e o que vier por planilha.

**Onde fica a tela.** Não fica. Esta onda é a espinha; a tela de resultados e a
tela irmã de fontes vêm na próxima. Até lá, o que dá para conferir é a linha de
comando, o `/admin/` e — o mais importante — **o carimbo das quatro faixas de
números**, que muda sozinho quando uma fonte passa a carregar.

**Como testar sem nenhuma credencial:**

```bash
python manage.py semear_fontes --aplicar
python manage.py carregar_fonte sankhya            # simulação
```

Sem `SANKHYA_*` no ambiente, a saída diz **"não está configurada"** e o status
fica `falha`. Isso é o **comportamento correto**, não um defeito: rodar sem o ERP
configurado é estado normal em desenvolvimento. Se aparecer traceback, abra bug.

**O teste que mais vale, e ele não precisa de API nenhuma:**

```bash
mkdir -p /tmp/cargas
printf 'chave_externa,codigo,nome_cliente,servico,centro_custo,valor_mensal\next-1,C-100,Cliente Fictício,cftv,1042,12000\n' > /tmp/cargas/contrato.csv
CARGAS_CSV_DIR=/tmp/cargas python manage.py carregar_fonte csv --aplicar
CARGAS_CSV_DIR=/tmp/cargas python manage.py carregar_fonte csv --aplicar   # de novo
```

A segunda passada tem de dizer **`ignorados 1`** e `criados 0`. Se vier
`atualizados 1`, a idempotência quebrou — e o sintoma na tela seria o espelho
inteiro dizendo "há 2 min" sem nada realmente novo. **Abra bug.**

**O que mais testar:**

- **Simulação é o padrão.** `carregar_fonte csv` sem `--aplicar` relata o que
  faria e **não grava**. A `ExecucaoCarga` da simulação aparece no `/admin/`
  marcada — e não pode virar carimbo de frescor em tela nenhuma.
- **Linha ruim não derruba o arquivo.** Tire o `chave_externa` de uma linha do
  CSV e deixe as outras: ela conta em `rejeitados` e as demais entram.
- **O `/admin/` do espelho é somente leitura.** Em *Contratos*, *Competências*,
  *Projetos*: **não pode** haver botão de adicionar, salvar nem excluir. Se
  houver, abra bug — editar ali cria uma segunda verdade que a próxima carga
  desfaz em silêncio.
- **Fonte desativada não carrega.** Desative o monday no `/admin/` e rode
  `carregar_fonte monday`: tem de recusar. É o único freio de quem opera às três
  da manhã, e `semear_fontes --aplicar` **não pode reativá-la**.
- **O carimbo muda sozinho.** Com uma carga bem-sucedida registrada para uma
  fonte, o carimbo daquela faixa deixa de dizer "sem registro de carga" — sem
  ninguém tocar em template. É o contrato da onda anterior sendo cumprido.

**Sobre dado pessoal:** o espelho **não tem** campo de CPF, e-mail ou nome de
quem respondeu a pesquisa. O conector do Platform tem uma lista explícita de
campos recusados. Se algum aparecer numa tela ou numa exportação, é achado de
segurança, não de produto.

**O que ainda não dá para testar:** as três APIs de verdade. Faltam
`MONDAY_TOKEN`, as credenciais do Sankhya e as rotas de integração do Platform —
ver [EXEC 16 § 16.7](EXEC_16_INGESTAO.md).

---

### 3.18 Apresentação de Resultados — `/workspace/resultados/` (código 10)

**Para que serve.** É a tela que a diretoria pediu: o dinheiro, os contratos, o
que vence e os projetos — **quatro** faixas, na competência escolhida.

> **Eram sete até 04/09/2026.** Quadro/jornada e avaliação do cliente saíram
> para as telas **16** e **17** (§ 3.18.2 e § 3.18.3): eram perguntas de outra
> gente presas atrás da permissão do dinheiro. Se você as procurar aqui e não
> achar, **não é bug** — e nenhum papel perdeu acesso na mudança.

**Quando é útil.** Na reunião mensal, com `?apresentacao=1`.

**Antes de testar:**

```bash
python manage.py semear_fontes --aplicar
python manage.py semear_resultados --aplicar
```

**O que testar, em ordem de importância:**

- **Anônimo é mandado para o login (302)**, e não entra. O Workspace é aberto
  para quase tudo; esta tela não. Se ela **abrir** sem login, é bug de
  segurança — mas 302 para `/entrar/` é o comportamento certo, e não achado.
- **O 403 é para quem ESTÁ logado e não tem escopo** — é aí que a distinção
  importa, porque é aí que a alternativa errada (tela zerada) seria plausível.
- **`colaborador@icodev.com.br` recebe 403**, e não um painel de zeros. Zero
  para quem nunca vai ter dado faz a pessoa achar que a empresa parou.
- **Gerente vê só o dele.** Entre com um perfil de `eco.ler.departamento` e
  confira o total da faixa 2 — ele tem de bater com o centro de custo da lotação,
  e não com a empresa. Vazamento em soma não deixa rastro: some dentro de um
  total plausível.
- **Digite `?regional=Sul` na barra de endereço com esse mesmo perfil.** O
  número **não pode mudar**. O filtro estreita, nunca alarga.
- **Três carimbos diferentes na mesma tela.** O dinheiro diz Sankhya, os
  projetos dizem monday, a avaliação diz iConnect Platform. Se os três disserem
  a mesma coisa, a massa entrou por uma fonte só.
- **A faixa de projetos aparece em alerta e NÃO some.** A massa planta uma carga
  do monday falhada há 30 h: a faixa mostra os projetos com a idade em destaque
  e o motivo ao lado. Se ela sumir ou zerar, **abra bug** — zerar é dizer que a
  empresa parou.
- **O primeiro cartão é a fonte quebrada.** Sem isso alguém lê a tela inteira e
  decide em cima de dado de três dias.
- **Competência sem dado mostra "—" e o motivo.** Escolha `2019-01` no seletor.
- **Nenhum cartão que não disparou.** Se aparecerem cartões com valor zero, a
  regra virou lista — e painel que sempre mostra oito cartões ensina a ignorar
  os oito.
- **Linha "sem orçado" aparece em cinza com "—", e não em vermelho.** Ela parece
  estouro de orçamento e não é: é código de centro de custo que não bate entre o
  ERP e o orçamento.
- **Console limpo.** A CSP é estrita: se algum `style=` escapar, o gráfico sai
  torto **sem erro nenhum** no console — confira que as barras existem e têm
  altura diferente entre si.
- **Nove gráficos e um mapa de calor.** Receita, EBITDA, exceções, carteira,
  mix, vencimentos, projetos (**dois**: situação e marcos) e satisfação, mais o
  mapa do quadro de pessoas. Faixa com número e sem desenho é regressão.
- **Toda tabela irmã abre.** Clique no `<details>` abaixo de cada gráfico: os
  números da tabela têm de ser os mesmos do desenho, em pt-BR. Se um deles vier
  com ponto decimal, o formatador foi contornado em algum lugar.
- **O mapa do quadro pinta turnover alto de VERMELHO.** Menor é melhor nessas
  duas métricas. Se o centro de custo que mais perdeu gente estiver em verde,
  **abra bug**: é o modo mais caro do painel estar errado, porque ninguém
  desconfia de verde.
- **A dispersão da carteira diz quantos ficaram de fora.** Contrato com menos de
  três meses de histórico sai do gráfico e é contado por escrito. Se o texto
  disser zero e a carteira tiver contrato novo, a exclusão parou de funcionar.
- **A barra da satisfação mostra a CONTAGEM dentro do segmento.** Uma barra de
  100% sobre doze respostas e outra sobre mil desenham igual.

**Modo apresentação** (`?apresentacao=1`): sem trilho, sem filtros, tipografia
maior. Confira no *view-source* que `au-rail-item` **não está no HTML** — e não
apenas invisível. Escondido por CSS, o leitor de tela leria uma navegação que
ninguém pode ver.

**PDF** (`/workspace/resultados/pdf/`): abre no navegador, com o mesmo recorte
da tela. **Não pode conter comentário de cliente nem nome de colaborador** — se
contiver, é achado de segurança. O PDF sai do prédio.

---

### 3.18.1 Os quatro movimentos do painel — perfurar, cruzar, pivotar, detalhar

**Para que serve.** É o que separa um painel de um relatório impresso: a pergunta
que nasce olhando o número tem de ser respondível na mesma tela.

Tudo vive na **query string**, e essa é a primeira coisa a testar: copie a URL
depois de três cliques, cole em outra aba, e a tela tem de voltar igual. Painel
cujo estado não sobrevive a um copiar-e-colar não é usável em reunião.

**1 · Perfurar — clicar na barra desce um nível**

A hierarquia tem três degraus: **Regional → Centro de custo → Contrato**.

- Clique numa barra do gráfico da faixa 2. A URL ganha `?regional=…` e a trilha
  de migalhas aparece no topo.
- Clique de novo, e de novo. Três degraus, e só três.
- **No quarto clique tem de aparecer a fronteira**, com o texto explicando que
  ocorrência, medição e ticket moram no iConnect Platform. **Se o painel abrir
  uma tela do Platform, abra bug de arquitetura** — é o acoplamento que este
  produto existe para desfazer.
- **A migalha volta.** Clicar em "Centro de custo" na trilha tem de LIMPAR o
  contrato. Se o filtro de baixo sobreviver, o número mostrado não corresponde à
  migalha em que a pessoa está — e ela não tem como perceber.

**O teste que mais importa aqui:** descendo um nível, o número **encolhe ou fica
igual**, nunca cresce. Já houve um defeito exatamente assim — descer para o
centro de custo 1042 trazia contratos do 1055, e a lista **aumentava** ao
descer. Some dentro de um total plausível.

**2 · Cruzar — no máximo três recortes**

Serviço, Layer e "só deficitários" são **atributos**: eles recortam sem descer.

- Aplique três. Ao aplicar o quarto, o mais antigo **sai** e a tela **avisa** que
  saiu. Se ele sair calado, abra bug: um recorte que desapareceu sem aviso
  produz um número que ninguém consegue explicar de cabeça.
- **Todo recorte ativo tem tarja.** Conte as tarjas e compare com a URL: filtro
  na query string sem tarja na tela é o defeito mais perigoso desta tela.
- **"Limpar" some com todas** e volta para a empresa inteira.

**3 · Pivotar — reagrupar sem mudar o recorte**

O seletor de dimensão troca **como o mesmo conjunto é agrupado**. Regional, CC e
contrato mudam o nível; serviço e layer reagrupam sem descer.

- **O total do rodapé não pode mudar ao pivotar.** É a mesma massa, somada de
  outro jeito. Total que muda ao trocar o agrupamento é bug de soma.
- A opção atual fica destacada.

**4 · Detalhar — `/workspace/resultados/detalhe/`**

O nível mais fundo da tela, linha a linha, com a **procedência** de cada uma
(`sankhya:snk-CT-100-202609`). É aqui que alguém confere contra o ERP.

**Sem dado pessoal, em nenhuma hipótese** — nem na tabela, nem na query string.
CPF, documento ou dado de saúde aparecendo aqui é achado de segurança, e a URL
é copiada e colada em conversa de WhatsApp o tempo todo.

**Modo apresentação e PDF carregam o recorte**

`?apresentacao=1` esconde o trilho, **mas as tarjas continuam**. E o PDF traz os
filtros no rodapé — ele é lido dias depois, longe da tela, por gente que não
escolheu o recorte. Sem filtro, ele diz "Sem recorte: a empresa inteira", porque
o silêncio seria ambíguo.

**O endpoint tem o mesmo escopo da tela**

`/workspace/resultados/dados/` alimenta os gráficos. Entre com o perfil de
gerente e chame o endereço direto, com `?regional=` de outra regional: ele tem de
recusar igual à tela. **Endpoint mais frouxo que a tela é achado de segurança** —
é a porta que ninguém olha porque não tem botão.

---

### 3.18.2 Quadro e jornada — `/workspace/quadro/` (código 16)

**Para que serve.** Efetivo, turnover, absenteísmo e horas por centro de custo.
Era a faixa 6 da tela 10 até 04/09/2026.

**Por que virou tela.** Enquanto morava dentro dos Resultados, ela exigia
`eco.ler` — a mesma permissão que mostra a margem de cada contrato com o nome do
cliente. Dar o turnover a quem responde por gente significava dar junto o
resultado financeiro da empresa.

**O teste que mais importa:** entre com **`rh@icodev.com.br`** e depois com
**`vendas@icodev.com.br`**.

- `rh` → **200** aqui, e **200** na tela 10 (ele já tinha as duas).
- `vendas` → **403** aqui, e **403** na 10.

Se algum papel que abria a tela 10 **perdeu** alguma coisa nesta mudança, **abra
bug**: a separação foi feita para somar público, não para tirar.

**O que mais testar:**

- **O mapa de calor pinta turnover alto de VERMELHO.** Menor é melhor nessas
  duas métricas — ver 3.18.
- **O centro de custo que destoa aparece.** A média esconde: 8,4% num centro
  contra 2,1% nos outros vira 2,6%.
- **Nenhum nome de colaborador.** O quadro é agregado por centro de custo. Nome
  em grade aqui é achado de segurança.
- **Não há filtro de Serviço, Layer nem "Só deficitários"**, e não há botão de
  PDF nem de Detalhamento. Os cinco são de CONTRATO, e aqui não há contrato por
  trás do número. Se aparecerem, **abra bug** — filtro que não muda nada faz a
  pessoa concluir que a tela quebrou.
- **Competência e Regional continuam.** Esses recortam.

---

### 3.18.3 Satisfação do cliente — `/workspace/satisfacao/` (código 17)

**Para que serve.** Promotores, neutros, detratores — e o **detrator sem
tratativa** em destaque. Era a faixa 7 da tela 10.

**A linha que prova que a separação serviu para alguma coisa:**

- **`vendas@icodev.com.br` → 200 aqui, e 403 em `/workspace/resultados/`.**

Antes isso era impossível: a única permissão que abria o NPS abria junto a
margem de todo contrato. Na prática o comercial não via o NPS.

**O que mais testar:**

- **O detrator sem tratativa é DESTAQUE, não linha de tabela.** Com tratativa é
  trabalho em andamento; sem tratativa é uma pessoa esperando.
- **A barra mostra a CONTAGEM dentro do segmento.** 100% sobre doze respostas e
  sobre mil desenham igual.
- **Não existe botão de PDF nesta tela**, e é deliberado: o comentário do
  cliente não sai daqui. Se aparecer um, **abra bug de segurança** — o PDF sai
  do prédio.
- **Nenhum nome de quem respondeu.** O provedor recusa esses campos; se um
  aparecer, é achado de segurança.

---

### 3.19 Fontes de dados — `/workspace/resultados/fontes/` (código 99)

**Para que serve.** Responde *"de onde vem esse número?"* com um link, e não com
um chamado.

**A permissão é OUTRA, e é o teste que mais importa aqui.** `eco.carga` dá a
tela 99; `eco.ler` dá os números. Entre com `ti@icodev.com.br`:

- `/workspace/resultados/fontes/` → **200**
- `/workspace/resultados/` → **403**

Se o T.I. enxergar a margem dos contratos, **abra bug**: ligar alguém no suporte
às cargas não pode dar a ele o resultado financeiro da empresa.

**O que testar:**

- **Três estados distintos** na coluna de situação: *desativada*, *não
  configurada* e *atrasada*. Eles não são o mesmo — em desenvolvimento nenhuma
  fonte tem credencial, e isso é normal. Se as três aparecerem como "com
  problema", alguém juntou o que precisava ficar separado.
- **A divergência mostra OS DOIS valores.** Só o vencedor esconderia a pergunta
  que a tela existe para fazer.
- **O histórico mostra `ignorados`.** É a resposta para "rodei a carga de novo,
  estraguei alguma coisa?".
- **Recarregar é POST.** Cole a URL de recarregar na barra de endereço: tem de
  dar **405**, e não disparar carga. Um `GET` faria um *prefetch* do navegador
  carregar sozinho.
- **Recarregar uma fonte sem credencial avisa** e não estoura. Traceback aqui é
  bug.

**O mapa faixa → fonte** no meio da tela não depende de carga nenhuma: ele
aparece mesmo num ambiente onde nada foi configurado.

---

### 3.20 Painel de exceções — `/workspace/excecoes/` (código 11)

**Para que serve.** Responde *"o que exige ação agora?"* — uma lista de regras
com contagem, que expande para a grade dos registros que a violaram. Cada linha
traz **quem responde**.

**Antes de testar:**

```bash
python manage.py semear_regras_excecao --aplicar
```

**O que testar, em ordem de importância:**

- **Regra com zero CONTINUA na lista**, escrita "sem ocorrências" e em cinza. Se
  ela sumir, **abra bug**: sumir esconde que a regra existe, e a discussão sobre
  "deveríamos vigiar X" volta em seis meses.
- **"Não avaliada" NÃO é zero.** Num ambiente sem os conectores, as regras de
  contrato e de projeto aparecem assim, em amarelo, com o motivo — e **não**
  entram na contagem do topo. Se elas aparecerem como "sem ocorrências", **abra
  bug de gravidade alta**: uma fonte fora do ar estaria parecendo um mês
  tranquilo.
- **A grade traz nome e papel, e NUNCA e-mail nem documento.** Se aparecer
  `@icodev.com.br` numa linha, é achado de segurança.
- **Papel sem ocupante aparece como "ninguém"**, escrito assim. Coluna vazia
  pareceria defeito de renderização, e o achado real — o papel sem dono — passaria
  despercebido.
- **Cada papel vê as SUAS regras.** Entre com `rh@icodev.com.br`: as regras de
  organograma aparecem, as do Financeiro não. Com `diretoria@`, todas.
- **`colaborador@icodev.com.br` recebe 403**, e não uma lista vazia. Lista vazia
  é a mesma mentira de um painel de zeros.
- **`marketing@` também recebe 403**, mesmo havendo regras "de todo mundo"
  (fonte atrasada, divergência). Elas existem para quem já está no painel por
  outro motivo — sozinhas, transformariam a tela numa tela de infraestrutura.
- **Uma regra que estoura não derruba as outras.** Se a tela der 500, **abra
  bug**: o painel existe justamente para ser aberto quando algo está errado.

**As duas ações:**

- **Avisar quem responde** manda **um** aviso por pessoa, e não um por
  ocorrência. Confira no sino: cinco lotações sem centro de custo têm de produzir
  **uma** notificação para o R.H., não cinco.
- **Abrir solicitação** leva ao catálogo com `?origem=excecao:<chave>` na URL. O
  formulário abre **em branco** — se vier pré-preenchido, **abra bug**: pedido
  com dado adivinhado é pior que pedido vazio.
- **Não existe "marcar como resolvido"**, e é decisão de produto. Resolver é
  trabalho de gente.

**A seção "Registradas e ainda desligadas"** no fim da tela lista ASO,
reciclagem, advertências, experiência e a conciliação de centro de custo, com a
fonte de que cada uma depende. Elas **não** são bug e **não** devem ser ligadas
pelo `/admin/`: sem avaliador escrito, elas aparecem como "não avaliada".

**A tendência** (a seta ao lado da contagem) só aparece depois de
`avaliar_excecoes --aplicar` ter rodado ao menos uma vez. Sem histórico, a tela
não inventa uma seta — e isso é o correto.

---

### 3.21 Ciclo de planejamento e ATA — `/workspace/ciclos/` (código 12)

**Para que serve.** A pauta da reunião como objeto do produto: a ordem de olhar,
registrada, com a tela viva em cada item, o carimbo de frescor de cada destino e
a ATA saindo do fechamento.

**Antes de testar:**

```bash
python manage.py semear_ciclos --aplicar
python manage.py semear_papeis --aplicar
```

**O que testar, em ordem de importância:**

- **A ATA repete o carimbo do DIA, e não o de hoje.** Anote alguma coisa na CP01
  com uma fonte atrasada, feche a reunião, rode `carregar_fonte --aplicar` e
  reabra a ATA no acervo. O texto tem de continuar dizendo a idade antiga. Se ele
  mudar, **abra bug de gravidade alta**: a ATA estaria reescrevendo o que a sala
  viu, e "com que dado se decidiu" é o que uma auditoria procura ali.
- **Fonte atrasada NÃO impede a reunião.** O primeiro "Abrir" recusa e lista as
  fontes; o botão passa a dizer *"Abrir mesmo assim (N fontes com atraso)"*; o
  segundo abre. Se o botão travar de vez, **abra bug**: um problema de carga não
  pode virar um problema de governança.
- **O impedimento não some quando a carga volta.** Depois de aberta, a lista no
  topo é a **congelada**. Rode a carga e recarregue a tela: a lista tem de
  continuar igual. Se ela esvaziar, o mês ruim está parecendo limpo.
- **A fronteira passa entre o GET e o POST.** Entre com `gerente@icodev.com.br`
  (lê e não conduz): a pauta abre, a apresentação abre, e **não existe** botão de
  abrir, de anotar nem de fechar. Um POST forjado tem de dar **403**.
- **Anônimo é redirecionado para `/entrar/`**, e não vê a pauta. Ciclo de
  planejamento não é informação institucional: é a agenda de decisão da empresa.
- **`almoxarife@` recebe 403**, e não uma lista vazia. Lista vazia diria "a
  empresa não tem ciclo de planejamento" para quem apenas não está na sala.

**O modo apresentação:**

- `?etapa=CP05` mostra uma etapa por vez; `?apresentacao=1` tira o trilho. São
  **dois parâmetros na mesma tela** — se aparecer uma segunda URL de
  apresentação, **abra bug** (ADR-025).
- Com `?apresentacao=1`, o trilho tem de estar **ausente do HTML** (confira no
  "ver código-fonte"), e não escondido por CSS.
- `?etapa=CP99` cai no primeiro passo, e **não** em 404. Erro de digitação no
  meio de uma reunião não pode virar tela de erro projetada na parede.
- Depois de anotar, a tela volta **para a mesma etapa**, e continua em
  apresentação se estava.

**A ATA, no acervo:**

- Abre em `/workspace/documentacao/ata-mensal-2026-09/`, tipo "ATA de ciclo".
- Traz os **impedimentos antes da pauta**, e cada etapa na ordem — inclusive as
  que ficaram **"Sem anotação."**, escrito. Se uma etapa sumir, **abra bug**:
  some a diferença entre "não foi apresentada" e "não teve registro".
- **Fechar duas vezes não gera duas ATAs.** Se aparecerem duas no acervo, é
  achado alto: as duas parecem oficiais.
- **A ATA não aparece no `select` da redação de documentos**, e um POST forjado
  com `tipo=ata` tem de ser recusado.
- Quem está **fora da plateia** do ciclo não abre a ATA nem a encontra na busca.
  Teste com `almoxarife@` no link direto: 403 ou 404, nunca 200.

**A etapa órfã.** Se alguém apontar uma etapa para um código de tela que não
existe (`/admin/`, campo "tela"), a pauta **continua funcionando** e o item diz
que o endereço precisa ser corrigido. Um link para lugar nenhum é bug; a frase
não é.

**O que NÃO existe, e não é bug:** reabrir reunião fechada, editar anotação,
apagar ATA, e calendário de reuniões futuras. Reunião futura é do M365.

---

### 3.22 Planos de ação — `/workspace/planos/` (código 13)

**Para que serve.** Responde *"o que a empresa deve fazer sobre o que a regra
encontrou, e funcionou?"*. É a regra dos 10% do benchmark generalizada: quatro
regras de exceção passam a cobrar justificativa, ação, dono e prazo.

**Antes de testar:**

```bash
python manage.py semear_regras_excecao --aplicar   # liga os quatro limiares
python manage.py semear_papeis --aplicar           # pla.responder
```

**O que testar, em ordem de importância:**

- **Fechar dizendo que resolveu, com a regra ainda disparando, grava "NÃO
  resolvido".** Abra um plano, não faça nada, e feche escrevendo "resolvido". A
  tela tem de avisar que a regra ainda encontra a ocorrência, e o plano fecha
  como não resolvido. Se ele fechar como resolvido, **abra bug de gravidade
  alta**: a tela passou a medir preenchimento de formulário.
- **Fonte fora do ar não fecha plano.** Com os conectores desligados (o padrão
  em desenvolvimento), tente fechar um plano de `margem-abaixo-de-10`: a tela diz
  que o desfecho não pôde ser conferido e o plano **continua aberto**. Se ele
  fechar como resolvido, é o achado mais caro desta tela — um conector caído
  viraria um mês de metas batidas.
- **A dívida volta quando o plano fecha sem resolver.** Feche um plano com a
  ocorrência ainda ativa e recarregue a lista: ela tem de reaparecer em "Devem
  plano". Se não voltar, o problema ficou sem dono.
- **Não existem dois planos abertos para a mesma ocorrência.** O segundo é
  recusado com o motivo. Mas depois de o primeiro fechar, um **novo** é
  permitido — e tem de ser: a margem cair de novo em março depois de um plano
  cumprido em janeiro é o que o histórico precisa mostrar.
- **Plano sem justificativa OU sem ação é recusado.** São as duas metades da
  exigência do benchmark.
- **Ocorrência que sumiu não aceita plano.** Abra o formulário de uma ocorrência
  que a regra já não encontra: ele diz isso e **não mostra os campos**. Se
  mostrar, é possível registrar um plano que fecha como resolvido sem ninguém ter
  feito nada — e a efetividade sobe de graça.

**A efetividade** (a linha no topo) **só aparece depois do primeiro plano
fechado**. Sem nenhum, ela não aparece — 0% seria uma afirmação sobre um trabalho
que não houve.

**Os quatro estados sempre aparecem, mesmo vazios**, cada um com o texto
explicando o vazio. Se uma seção sumir por estar zerada, **abra bug**: some a
informação de que aquele estado existe.

**Permissão:**

- `financeiro@icodev.com.br` responde por margem e centro de custo; `operacao@`
  por detrator e projeto bloqueado; `diretoria@` por todos.
- **Quem vê a regra lê o plano e não o fecha.** Entre com um perfil que tenha
  `exc.ler.global` e não `pla.responder`: a lista e o detalhe abrem, e **não há**
  botão de fechar. Um POST forjado tem de dar 403.
- **`almoxarife@` recebe 403** na lista, e não uma tela de zeros.
- **Anônimo** é redirecionado para `/entrar/`.

**O comando do vencimento:**

```bash
python manage.py verificar_planos            # simulação: diz o que conferiria
python manage.py verificar_planos --aplicar  # confere e grava o desfecho
```

A simulação **não grava** — nem a conferência. Se `VerificacaoPlano` aparecer no
`/admin/` depois de rodar sem `--aplicar`, **abra bug**.

Planos que venceram **hoje ou ontem** não são conferidos: há dois dias de
carência, porque o cron pode ter ficado fora do ar e o desfecho sairia aleatório.

**O que NÃO existe, e não é bug:** reabrir plano fechado, apagar conferência,
dois limiares na mesma regra, e "marcar como resolvido" sem conferência.

---

### 3.23 Metas, avaliação e PDI — `/workspace/metas/` (código 14)

**Para que serve.** O quadro de metas de **uma pessoa** num ciclo, com a fórmula
de cada meta à vista, e o plano de desenvolvimento em `14.1`.

**Antes de testar:**

```bash
python manage.py semear_ciclo_metas --aplicar
python manage.py semear_papeis --aplicar
# Só em ambiente de demonstração — meta de mentira em quadro de pessoa real
# aparece no painel do R.H. como se fosse verdade:
python manage.py semear_ciclo_metas --aplicar --com-exemplos
```

**O que testar, em ordem de importância:**

- **Quadro aprovado não muda mais.** Aprove um quadro e tente editar uma meta: a
  tela recusa e diz para reabrir. Se a edição passar, **abra bug de gravidade
  alta** — mover a trave no meio do ciclo é o que a palavra "meta" existe para
  impedir.
- **Reabrir exige motivo, e o motivo fica na tela.** Reabra duas vezes e confira
  a seção "Reaberturas". Se ela não aparecer, o achado — metas mal definidas —
  desaparece junto.
- **Fator sem amostra não vira zero.** Com os conectores desligados (o padrão em
  desenvolvimento), aprove e apure um quadro: cada meta tem de dizer *"Sem
  apuração: o espelho não tem …"*, e a nota tem de ser **"—"**. Se aparecer
  **0%**, é o achado mais caro desta tela: uma fonte fora do ar viraria a nota de
  uma pessoa.
- **A meta sem apuração fica fora do denominador.** Um quadro com uma meta
  apurada de peso 1 (120%) e uma sem apuração de peso 9 tem nota **120**, e não
  12. Se der 12, as não apuradas estão entrando como zero.
- **Nenhuma tela lista pessoas com nota.** A lista "Quadros de quem você lidera"
  traz **situação**, e a linha do R.H. traz **contagem**. Se aparecer uma coluna
  de nota, **abra achado de privacidade** — é uma planilha de desempenho, e ela
  circula.
- **A fórmula aparece em cada meta**, em monoespaçado: `ebitda ÷
  orcamento_mensal`. É o que torna a meta auditável — se sumir, o número volta a
  ser opinião.

**A separação dos atos:**

- **Ninguém aprova o próprio quadro.** Entre como `gestor@icodev.com.br` e abra
  o próprio: não há botão de aprovar. A exceção é `diretoria@`, com
  `met.aprovar.global`, e ela é deliberada — é o que destrava quem não tem
  gestor acima.
- **O liderado não escreve a própria meta**, e **o R.H. não aprova**.
- **Quadro vazio não é aprovado.** Se aprovar, ele conta como cobertura sem
  cobrar nada de ninguém.
- **Só quadro aprovado é apurado.** Apurar rascunho permitiria escrever a meta
  depois de ver o número.

**O PDI (`14.1`):**

- **É escrito pela própria pessoa.** Abra o PDI de um liderado como gestor: o
  formulário **não aparece**, e a tela diz por quê. Se aparecer, **abra bug**.
- Ações têm **mês e ano**, e não data. Ação de mês passado sem conclusão aparece
  marcada como atrasada.
- Ciclo fechado não recebe PDI novo nem ação nova.

**O carimbo.** Cada meta apurada mostra de quando é o número que a pontuou,
**congelado**. Rode uma carga depois de apurar e reabra: o texto tem de continuar
o mesmo. Se mudar, a nota de 2026 mudaria em 2027.

**O que NÃO existe, e não é bug:** meta qualitativa (o fator precisa existir no
catálogo), mais de 12 metas por quadro, atingimento acima de 150%, exportação de
qualquer tela desta onda, e reabertura de quadro apurado.

---

### 3.24 Orçamento anual e revisão — `/workspace/orcamento/` (código 15)

**Para que serve.** O teto de operação, mês a mês — o número que a bandeja de
aprovação usa para dizer se um pedido cabe. E a **revisão**, que é a única forma
de mudá-lo depois que ele entra em vigor.

**Antes de testar:**

```bash
python manage.py semear_centros_custo --aplicar
python manage.py semear_orcamento     --aplicar   # importa o teto avulso
python manage.py semear_papeis        --aplicar
```

**O que testar, em ordem de importância:**

- **O teto vigente não muda sem revisão.** Vá ao `/admin/` e tente mudar a
  situação de um orçamento vigente: o campo é somente leitura. Tente editar as
  linhas — elas mudam, mas só valem em rascunho. Se houver qualquer caminho que
  altere o teto **vigente** sem gravar uma `RevisaoOrcamento`, **abra bug de
  gravidade alta**: era o defeito que esta onda veio consertar.
- **A revisão exige motivo.** Deixe o campo em branco: a tela recusa. Sem motivo,
  a revisão vira uma edição com data.
- **Campo em branco é "não mexi", e não "zerei".** Revise só julho e confira os
  outros onze meses: têm de ficar como estavam. Se zerarem, **abra bug** — uma
  revisão de julho teria apagado o ano.
- **Os dois orçados aparecem lado a lado.** Com o espelho conectado, a seção "O
  nosso teto e o orçado do Sankhya" mostra os dois e a diferença. Se aparecer
  **um número só**, alguém escolheu vencedor dentro do código — é o que a
  restrição 5 proíbe.
- **Consumido é realizado + comprometido.** Aprove um pedido de R$ 4.000 num CC
  e confira: a coluna "Comprometido" sobe **antes** de qualquer pagamento. Se
  ela só mexer no pagamento, um orçamento pode estourar sem ninguém ver.
- **Sem teto, "—" e nunca "0%".** Abra um centro de custo sem orçamento: as
  colunas de saldo e % mostram travessão. Se mostrarem `0,0%`, o aprovador leria
  como folga total.

**Permissão:**

- `financeiro@icodev.com.br` e `diretoria@` leem todos os CCs e **revisam**.
- `gestor@` lê **só o próprio** CC e **não** revisa — a tela não mostra o
  formulário, e um POST forjado dá 403.
- **`almoxarife@` recebe 403**, e não uma grade de zeros.
- Centro de custo alheio dá **403, e não 404** — 404 transformaria a tela num
  verificador de códigos.
- Quem tem a permissão e **não tem lotação** também recebe 403.

**A regra que ligou nesta onda.** `cc-sem-orcado-e-o-inverso` estava registrada e
desligada desde a Onda 4, esperando o orçamento existir aqui dentro. Ela agora
aparece **ligada** no painel de exceções e **cobra plano de ação**. Confira as
duas direções: CC com realizado e sem teto, e CC com teto e desconhecido no ERP.

**A carga inicial.** `semear_orcamento --aplicar` importa o teto avulso de cada
CC para doze meses iguais, já em vigor. Rodar de novo **não** toca no que já
existe — se ele apagar uma revisão, **abra bug**. Centro sem teto é **pulado**, e
não vira um ano de zeros.

**O que NÃO existe, e não é bug:** editar orçamento vigente, apagar revisão,
curva de sazonalidade na importação, e orçamento por projeto ou por contrato — o
grão é o centro de custo.

---

### 3.25 Os outros públicos da marca — `/entrar/` e a faixa Aplicativos

**Para que serve.** Três públicos, três produtos, uma marca. Este produto é o
**Portal ADB**, do colaborador; cliente e fornecedor entram em outro lugar, e o
Workspace só os **roteia**.

**Não há tela nova.** Se você procurar um módulo de públicos, ele não existe — e
isso é a entrega, não a falta dela.

**O estado de hoje:** `ADB_CLIENTE_URL` e `ADB_FORNECEDOR_URL` vazias. Nada
aparece em lugar nenhum.

**Para testar o roteamento**, ponha no `.env`:

```
ADB_CLIENTE_URL=https://cliente.exemplo.com.br/
```

e reinicie o servidor.

**O que testar:**

- **Com a variável vazia**, `/entrar/` **não** mostra a seção "Você é cliente ou
  fornecedor?" — nem vazia, nem com "em breve". Se aparecer um destino apagado
  ou uma promessa, **abra bug**: ninguém decidiu que esses produtos vão existir.
- **Com a variável preenchida**, a seção aparece abaixo do formulário, com o
  nome e a descrição, e o link leva para fora.
- **O "Portal ADB" não aparece na própria tela de entrar.** Dizer a quem já está
  aqui que a entrada dele é aqui não ajuda ninguém.
- **O tile aparece na faixa Aplicativos da home**, no fim, ao lado do iConnect
  Platform — as entradas que **saem** deste produto ficam juntas.

**As configurações que o produto RECUSA** (o servidor não sobe, e a mensagem diz
por quê — teste uma de cada vez):

| Valor | Por que é recusado |
|---|---|
| `/workspace/` | não é absoluto: mandaria cliente para dentro deste produto |
| `//evil.exemplo.com/` | sem esquema |
| `javascript:alert(1)` | esquema não é http(s), e o valor vira `href` na tela de login |
| um host que esteja em `ALLOWED_HOSTS` | aponta para este próprio produto |

Se qualquer um desses **subir o servidor**, é achado de segurança: a tela de
entrar estaria confirmando a um cliente que o portal do funcionário é o lugar
certo dele.

**O que NÃO existe, e não é bug:** login de cliente ou fornecedor aqui, papel de
"cliente", e módulo de públicos. O modelo de permissão assume colaborador com
lotação no organograma — ver ADR-038.

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
| **Resultados** (10) | ➜ login | **403** | ✅ **só o escopo dele** | **403** |
| **Quadro e jornada** (16) | ➜ login | **403** | ✅ só o escopo dele | **403** |
| **Satisfação** (17) | ➜ login | **403** | ✅ (Vendas também) | **403** |
| **Fontes de dados** (99) | ➜ login | **403** | **403** — é `eco.carga`, e não `eco.ler` | **403** |
| **Exceções** (11) | ➜ login | **403** | ✅ só as do escopo | **403** |
| Indicadores | ➜ login | **403** | ✅ | **403** |
| **Ciclos de planejamento** | ➜ login | **403** | ✅ lê; só Diretoria **conduz** | **403** |
| **Planos de ação** | ➜ login | **403** | ✅ lê; só o papel da regra **fecha** | **403** |
| **Metas e PDI** | ➜ login | ✅ **só o próprio** | ✅ os liderados; só o gestor **aprova** | ✅ só o próprio |
| **Orçamento** | ➜ login | **403** | ✅ lê o próprio CC; só Financeiro **revisa** | **403** |

As células em negrito são os testes de autorização que valem mais: bandeja vazia
para colaborador, fila invisível para gestor, cancelamento de terceiros só para
quem administra recurso — e, nos ciclos, a diferença entre **ler a pauta** e
**conduzir a reunião**, que é onde passa a fronteira entre o GET e o POST.

**Repare na diferença entre as duas colunas da esquerda, nas linhas de dado
agregado.** O anônimo é mandado para o login — comportamento normal, e **não é
achado**. Quem está **logado e sem escopo** recebe **403**, e é aqui que mora a
regra: tela de dado agregado nega, nunca mostra zero. Se alguma delas abrir
zerada em vez de recusar, é bug — e um dos piores, porque parece que funcionou.

Conferido num banco recém-semeado, e vale como gabarito:

```
                resultados  fontes  exceções  metas  orçamento  indicadores
anônimo            302       302      302      302     302         302
colaborador        403       403      403      200     403         403
ti                 403       200      403      200     403         200
diretoria          200       200      200      200     200         200
```

As duas células que mais surpreendem: `colaborador` recebe **200 em metas**
(ele vê as **próprias**, e só elas), e `ti` recebe **200 em fontes** e **403 em
resultados** — a mesma pessoa opera as cargas e não enxerga a margem.

**A linha das Fontes é a que mais pega gente.** `eco.carga` abre a tela 99;
`eco.ler` abre os números. São permissões **diferentes** de propósito: o T.I.
opera as cargas sem enxergar a margem dos contratos.

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

### Roteiro H — o painel da diretoria (o roteiro que protege o número da reunião)

Pré-requisito: o bloco das cinco semeadoras da § 1.2 rodado com `--aplicar`.

1. **Anônimo** abre `/workspace/resultados/` → **302 para o login**. Se a tela
   abrir, é bug de segurança; se redirecionar, está certo.
2. **`colaborador@icodev.com.br`** → **403** também. Zero para quem nunca vai ter
   dado faz a pessoa achar que a empresa parou.
3. **`ti@icodev.com.br`** → `/workspace/resultados/fontes/` dá **200**, e
   `/workspace/resultados/` dá **403**. Ligar alguém ao suporte das cargas não
   pode dar a ele o resultado financeiro da empresa.
4. Entre com a **diretoria**. Anote o total da faixa 2 — este é o número da
   empresa inteira, e ele é a referência de tudo que vem a seguir.
5. **Conte os gráficos: nove**, cada um com tabela irmã, mais o mapa de calor do
   quadro. Abra três tabelas e confira que os números batem com o desenho.
6. **Perfure três vezes** (regional → CC → contrato). A cada degrau, o total
   **encolhe ou fica igual** — nunca cresce. No quarto clique, a fronteira.
7. **Volte pela migalha do meio.** O contrato tem de sumir do recorte.
8. **Cruze quatro filtros.** O quarto derruba o primeiro **com aviso**. Conte as
   tarjas: uma por filtro na URL, sem exceção.
9. **Pivote.** O total do rodapé **não muda** — é a mesma massa, agrupada de
   outro jeito.
10. **Copie a URL e cole em outra aba.** Tela idêntica. Se não for, o estado não
    está na URL, e a tela não serve para mandar por e-mail.
11. **`?apresentacao=1`** com os filtros ativos: as tarjas **continuam** e o
    trilho some do *view-source* — não apenas da tela.
12. **Baixe o PDF.** Os filtros no rodapé; as tabelas presentes; **nenhum nome de
    colaborador e nenhum comentário de cliente**. O PDF sai do prédio.
13. **Entre com um gerente** (`eco.ler.departamento`) e digite `?regional=Sul` na
    barra de endereço. O número **não muda**. Depois chame
    `/workspace/resultados/dados/?regional=Sul` direto: tem de recusar igual.

Achado em qualquer um dos passos 2, 3, 6, 12 ou 13 é **bug de segurança**, e não
bug de tela.

---

## 6. O que ainda NÃO existe — não abra bug

| Não existe | Por quê |
|---|---|
| **Assistente de conhecimento (RAG)** | Bloqueado por dados: existem 5 documentos, todos de demonstração. A onda F precisa dos POPs e normativos reais. Não é código que falta. |
| Habilitações / certificações | O modelo vive no iConnect **Platform** (`fsm.Skill`), com **zero registros**. Não é módulo do Workspace. |
| Analytics pessoal | Decisão tomada (visível **só para a própria pessoa**, escopo `proprio`), não implementada. |
| Integração com M365 / HRIS | Suíte definida, integração não construída. |
| `semear_workspace` | Não existe. Documentos, comunicados e correspondências se criam dentro do produto (ver 1.3); recursos têm `semear_recursos`. |
| Monitor de rede (viabilidade do módulo TI) | Pergunta aberta ao dono do produto. |
| Os módulos previstos além dos 12 | Não estão marcados "Em breve": simplesmente **não existem na lista**. Ausência é honesta; promessa não é (ADR-039). |
| **Fonte externa "não configurada"** | Nenhuma credencial de Sankhya, monday ou Platform existe em desenvolvimento — e **nunca** existirá no repositório (ela vive em variável de ambiente). "Não configurada" é estado **normal**, e é diferente de "atrasada" e de "desativada". O espelho é enchido por CSV via `semear_resultados`. |
| Gráfico dentro do PDF | Decisão registrada (ADR-041) — ver 2.8. |
| Carga automática de madrugada | O `deploy/crontab` existe no repositório e **não está instalado** em nenhuma máquina. Carga só roda por comando à mão. |
| Perfurar até ocorrência, medição ou ticket | Fronteira de arquitetura, não falta de tela — ver 3.18.1. |

---

## 7. Lista de regressão — as 26 armadilhas já corridas

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
| 16 | Trilho mostrava ao **anônimo** os contadores de uma pessoa real | "4 não lidas" do superusuário visível a quem só abriu o endereço |
| 17 | `var(--au-7)` — a escala pula o 7 | Declaração inválida derruba o `padding` inteiro; dois painéis sem margem |
| 18 | Catálogo fazia **28 consultas** de prazo, uma por item | Cada uma lia todo o histórico do item; a tela mais visitada do produto |
| 19 | Taxa de reabertura deu **200%** | Pedido reaberto sai do denominador e fica no numerador — número impossível num painel |
| 20 | 3º flake por hora do dia (`daqui(4)` cruzava a meia-noite) | Suíte reprovava depois das 20h e passava o resto do dia |
| 21 | **106 atributos de SVG com vírgula decimal** — a mesma classe da linha 8, semanas depois | Gráfico em branco, console limpo. `LANGUAGE_CODE = pt-br` localiza `{{ 10.52 }}` para `10,52`, que é inválido em atributo de SVG, e o navegador **descarta o elemento em silêncio** |
| 22 | Descer para o CC 1042 trazia contratos do CC 1055 | A lista **cresce** ao descer um nível. Os escopos eram combinados com OU; o certo é o mais específico vencer |
| 23 | "Apresentar" descartava todos os filtros menos a competência | O número da reunião não é o número que a pessoa estava olhando — e ninguém percebe, porque a tela ficou bonita |
| 24 | Dois filtros ativos **sem tarja** na tela | Recorte aplicado e invisível: o total parece o da empresa inteira |
| 25 | Rótulo girado cortado no topo do gráfico | O número da barra mais alta some — justamente a que interessa |
| 26 | Redirect do PDI escrito à mão (`/workspace/desenvolvimento/`) em vez de `reverse()` | 404 no lugar da mensagem de erro que deveria aparecer |

**Se você só tiver uma hora**, teste: o Roteiro B (linha 1), a passagem pelas 6
telas logado (linha 3), ⌘K + Esc em três telas (linhas 4 e 5), e o console aberto
em todas (linhas 7, 8 e 11).

**Se você tiver mais uma hora**, gaste-a no painel de resultados: o Roteiro H
inteiro. Ele cobre sozinho seis das armadilhas acima (21 a 26), e é a tela onde
um erro custa mais caro — porque ela é lida em reunião de diretoria, por gente
que não tem como conferir o número.

---

## 8. Onde reclamar de quê

| Sintoma | É bug de |
|---|---|
| Tela `/workspace/…` errada | **Workspace** — abra o bug |
| Tela `/dashboard/…`, `/fsm/…`, `/login/` | **iConnect Platform** — outro produto, outra suíte |
| `no such column` / `OperationalError` | migração pendente (seção 1.1) |
| Tela vazia sem dado | massa de teste faltando (seção 1.2 e 1.3) |
| "Você não tem acesso" | papel/lotação faltando (seção 1.4) |
| Módulo que você esperava e não está na lista | decisão de produto (seção 6) — são 12, e a lista está na 3.10 |
| iConnect não é o tile principal | decisão de produto (seção 3.1) |
| Pedido não pré-preenchido pela frase da busca | decisão de produto (seção 3.2) |
| Gráfico em branco, mas a tabela abaixo tem os números | **Workspace** — abra o bug **com o console anexado**. É sempre CSP ou número mal formatado, e a tela não mostra erro nenhum (seção 2.8) |
| Faixa de resultado vazia dizendo qual fonte falta | comportamento correto (seção 6) — zerar seria dizer que a empresa parou |
| Fonte "não configurada" | estado normal em desenvolvimento (seção 6) |
| Número que **cresce** ao descer um nível | **Workspace** — bug de escopo, prioridade máxima (seção 3.18.1) |
| Telas 10 a 15 vazias | faltou o bloco das cinco semeadoras (seção 1.2) |
