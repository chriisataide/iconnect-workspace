# iConnect Workspace

**A vida corporativa da empresa em um lugar.**

> O iConnect Workspace organiza a vida corporativa da empresa.
> O iConnect Platform organiza toda a operação de atendimento aos clientes.

São **dois produtos**. Este repositório é o primeiro.

---

## A fronteira, em uma frase

A ligação entre os dois é **um link** — o tile "iConnect Platform" no launcher da
home, configurado em `ICONNECT_URL`. Não há banco compartilhado, sessão
compartilhada nem tabela de usuários compartilhada. Pessoa daqui não é pessoa de
lá.

Isso é garantido por construção e verificado por teste
([`workspace/tests/test_isolamento.py`](workspace/tests/test_isolamento.py)):
nenhum arquivo deste repositório pode importar um app do iConnect.

### Por que a separação foi feita

Os dois produtos moravam no mesmo projeto Django, dividindo uma `auth.User` e um
cookie de sessão. A consequência era medível, não teórica:

- **881 lotações** criadas para técnicos do iConnect, todas sem unidade, sem
  departamento, sem centro de custo e sem gestor. Ninguém errou — era a mesma
  tabela e nada impedia.
- Na direção inversa, pior: uma conta criada pelo Workspace valia como sessão no
  iConnect, onde "usuário sem papel definido" era tratado como **analista**, com
  acesso a ticket e cliente.
- E o Workspace não podia ter CSP estrita, porque o header era compartilhado com
  um produto que precisa de `unsafe-inline` em `style-src`.

O terceiro item deixou de ser um problema no primeiro dia deste repositório: a
CSP aqui não tem `unsafe-inline` em nenhuma diretiva.

---

## Subir em cinco minutos

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

python manage.py migrate
python manage.py createsuperuser          # pede e-mail e senha, não username

# Massa mínima para as telas terem o que mostrar.
# A ORDEM importa: o resto pendura no organograma.
python manage.py semear_papeis --aplicar
python manage.py importar_organograma docs/exemplos/organograma-inicial.csv \
    --criar-usuarios --aplicar
python manage.py semear_acessos --aplicar          # dá papel a quem entrou no organograma
python manage.py semear_centros_custo --aplicar    # um CentroCusto por código usado na lotação
python manage.py semear_catalogo --aplicar
python manage.py semear_regras_aprovacao --aplicar
python manage.py semear_recursos --aplicar         # salas, veículos, equipamentos
python manage.py reindexar_busca

python manage.py runserver
```

**Para testar sem decorar quem é quem**, `python manage.py semear_perfis --aplicar`
cria **um usuário por papel, com o nome do papel** — `financeiro@icodev.com.br`
atende a fila do Financeiro, `colaborador@icodev.com.br` não atende nada e é
contra ele que se mede se o produto esconde o que deve. Senha de todos:
`workspace123`. A lista completa está no [guia de QA](docs/GUIA_QA_WORKSPACE.md).

> `semear_acessos` não é opcional. Sem ele o organograma entra e **ninguém tem
> papel** — todo mundo vira colaborador comum, nenhuma fila abre e nenhuma
> bandeja recebe. `semear_centros_custo` também muda comportamento: sem ele
> toda pessoa tem um código de centro de custo e nenhum código existe, e a
> bandeja de aprovação diz "CC sem orçamento definido" em vez de desenhar a
> barra.

A sequência completa — incluindo estoque, frota, cursos e FAQ — está em
[Operação § 13.1](docs/EXEC_13_OPERACAO.md).

Abra <http://127.0.0.1:8000/workspace/>. **O Workspace é aberto** para tudo que
é institucional — o hub, a busca, o catálogo, a documentação, a agenda das
salas e o formulário de qualquer serviço. Identificar-se é exigido para ver o
que é **de uma pessoa** ("Meu dia", "Minhas solicitações", a bandeja, a
correspondência) e para **assinar** em nome dela: enviar, aprovar, acertar,
cancelar, confirmar leitura, baixar anexo.

Todos os comandos `semear_*` rodam em **simulação por padrão**: sem `--aplicar`
eles só relatam o que fariam.

> **Falta massa para três coisas.** Documentação, Correspondências e
> Comunicados/Notícias não têm semeadora. Documentos e comunicados se criam
> **dentro do produto** (Documentação › Acervo normativo, e Comunicados);
> correspondência se cria na própria tela, com o perfil `recepcao@`. Reservas
> **tem** semeadora (`semear_recursos`). Ver a seção 1.3 do
> [guia de QA](docs/GUIA_QA_WORKSPACE.md).

---

## Os apps, e a direção da dependência

```
contas       →  a conta da pessoa. AUTH_USER_MODEL, e-mail como identificador
identidade   →  organograma, papel com escopo e vigência, pode()      ← RAIZ
workspace    →  a superfície e os motores do Workspace                ← FOLHA
financas     →  centro de custo e orçamento; implementa o contrato
resultados   →  espelho do que vem de fora; implementa o contrato
cargas       →  os conectores. Escreve em `resultados`, e em mais nada
```

A regra que não pode inverter:

    o domínio depende do CONTRATO (`workspace.providers`),
    nunca da SUPERFÍCIE (`workspace.views`, `.models`, `.services`).

E, para o que vem de fora, uma direção a mais:

    cargas ──escreve──► resultados ──implementa──► workspace.providers ◄── workspace

O `workspace` não conhece Sankhya, monday nem o Platform. Ele nem sabe que
`cargas` e `resultados` existem — conhece o contrato, e só. Trocar o ERP mexe em
**um conector**, e nenhuma view muda.

`financas` existe por causa da separação. `CentroCusto` e as movimentações moravam
no iConnect, e a **barra tripla** da bandeja de aprovação — realizado,
comprometido, este pedido — lia de lá. Sem federação, restavam três saídas: uma
API HTTP, perder a barra, ou o Workspace assumir o orçamento. Assumiu, porque
orçamento por centro de custo é vida corporativa e estava no iConnect por
acidente de crescimento. **O contrato não mudou** — só a implementação trocou de
casa, que era o ponto de existir um contrato.

---

## Decisões que parecem erro e não são

| O que se estranha | Por quê |
|---|---|
| Cada tela tem um **número** no topo | É endereço, não enfeite. "Abre a 02.2" atravessa e-mail, ata e WhatsApp sem depender de a outra pessoa ter o mesmo menu aberto — e sem colar URL, que quebra quando a rota muda. O número resolve na busca e em `/workspace/ir/02.2/`. Fica no fonte e não no banco: módulo aqui nunca foi dado, e uma tabela criaria a segunda verdade sobre quais telas existem ([ADR-015](docs/EXEC_15_ENDERECAMENTO.md)). |
| `/workspace/ir/08/` devolve **403**, e não 404 | O redirecionador resolve o código e manda; quem decide acesso é a tela. Se ele autorizasse, existiriam dois lugares onde "quem vê o quê" está escrito, ao lado de `pode()` — e no dia em que discordassem, o produto teria duas respostas para a mesma pergunta ([ADR-016](docs/EXEC_15_ENDERECAMENTO.md)). |
| Existem **dois** clientes HTTP no repositório | Um roda dentro da requisição do usuário (4 s, retry linear, **nunca** repete `POST`); o outro roda em carga agendada (60 s, recuo exponencial, e `POST` é o método de **leitura** do monday). Um módulo com seis parâmetros para servir aos dois não serviria bem a nenhum. O que eles dividem é um **teste** — nenhum dos dois registra credencial ([ADR-021](docs/EXEC_16_INGESTAO.md)). |
| O app de ingestão se chama `cargas`, e não `integracoes` | Porque [workspace/integracoes/](workspace/integracoes/) já existe e é outra coisa: o link com a Platform. Dois pacotes com o mesmo nome é como um `import` errado passa despercebido numa revisão. |
| Nada em [resultados/](resultados/) tem formulário, nem no `/admin/` | O dado nasce onde é operado. Editar o espelho criaria duas verdades sobre a mesma linha — e a segunda venceria até a próxima carga, ou não venceria, conforme a precedência ([ADR-018](docs/EXEC_16_INGESTAO.md)). |
| Regra de exceção com **zero** continua na lista | Sumir esconderia que a regra existe — e a discussão sobre "deveríamos vigiar X" voltaria em seis meses. E "sem ocorrências" **não** é o mesmo que "não avaliada": a segunda quer dizer que a fonte não está no ar, e as duas pedem ações opostas ([ADR-027](docs/EXEC_18_EXCECOES.md)). |
| Cinco regras estão no banco **desligadas** | ASO, reciclagem, advertências, experiência e a conciliação de centro de custo. Elas dependem do HRIS e do orçamento, e ficam registradas com a fonte anotada — é o que responde "por que não vigiamos isso?" sem ninguém perguntar. |
| Este produto atende **um** público | Três públicos, três produtos, uma marca: o Portal ADB é este; ADB Cliente e ADB Fornecedor são outros. O modelo de permissão assume `Pessoa` com lotação no organograma — um "papel de cliente" exigiria um segundo modelo de identidade, ou gente no organograma que não trabalha aqui ([ADR-038](docs/EXEC_23_PUBLICOS.md)). |
| Destino não configurado **não aparece**, nem como "em breve" | "Em breve" é promessa, e ninguém decidiu construir o ADB Cliente. Ele continua **registrado sem endereço** — a decisão de não existir é informação, e some se ele não estiver em lugar nenhum ([ADR-039](docs/EXEC_23_PUBLICOS.md)). |
| Existem **dois orçados**, e eles não se fundem | O teto de operação é nosso e responde "isto cabe?" na aprovação; o orçado contábil é do Sankhya e responde "o mês fechou onde deveria?". A tela mostra os dois lado a lado com a diferença, e nenhuma linha de código escolhe vencedor — divergência entre fontes se resolve por regra declarada, não dentro de um `if` ([ADR-036](docs/EXEC_22_ORCAMENTO.md)). |
| O **teto vigente muda por revisão** | Com motivo, autor e delta por mês. Antes disso, quem tivesse `is_staff` editava um campo e ninguém ficava sabendo — e "quem mudou o teto de julho, quando e por quê" não tinha resposta ([ADR-037](docs/EXEC_22_ORCAMENTO.md)). |
| A meta guarda a **fórmula**, e nunca o número | `Meta.fator_1` é `"ebitda"`, não `120000`. O valor é lido do espelho na apuração e só então congelado — a meta é auditável porque a conta está na tela, e a comparação entre quadros continua funcionando no segundo ano. O preço é real e é o certo: só se escreve meta sobre o que o produto sabe medir ([ADR-034](docs/EXEC_21_METAS.md)). |
| Não existe **grade de pessoas com nota** | A lista de quem você lidera traz situação; a do R.H. traz contagem. Uma coluna de nota ao lado de uma lista de nomes é uma planilha de desempenho, e ela circula — restrição 8, no lugar em que é mais fácil de violar sem perceber. |
| O plano de ação **não fecha porque alguém disse que resolveu** | Fechar roda a regra de novo sobre a mesma ocorrência. Se ela ainda dispara, o plano fecha como "não resolvido" — o texto de quem fechou fica junto, mas não decide. Um painel em que o próprio interessado declara o sucesso mede quem preenche formulário ([ADR-033](docs/EXEC_20_PLANOS.md)). |
| Fonte fora do ar **não fecha plano nenhum** | A conferência fica registrada como "não avaliada" e o plano continua aberto. Sem isso, um conector caído fecharia como resolvido tudo o que dependesse dele, e o mês apareceria como o melhor do ano — a mesma distinção entre *zero* e *não avaliada* do painel de exceções. |
| A **ATA congela o carimbo de frescor** | Uma anotação feita diante de um número de três dias atrás guarda "há 3 dias" ao lado, para sempre. Recalcular na leitura reescreveria a história **para melhor**, que é a direção em que ninguém percebe — e "com que dado a sala decidiu" é justamente o que uma auditoria procura numa ATA ([ADR-030](docs/EXEC_19_CICLOS.md)). |
| Fonte atrasada **não** impede a reunião | A conferência de frescor roda ao abrir o ciclo, recusa a primeira vez e mostra a lista; o segundo clique abre, e os impedimentos ficam congelados na ocorrência e na ATA. Travar transformaria um problema de carga num problema de governança; esconder faria a sala decidir sem saber com que dado. |
| A etapa da pauta guarda um **código de tela**, nunca uma URL | `CP01 → 10`. No dia em que uma rota mudar, uma pauta com URL viraria uma lista de links quebrados **durante a reunião** — o único momento em que ninguém tem tempo de consertar ([ADR-029](docs/EXEC_19_CICLOS.md)). |
| A tela de Resultados é a **10**, e não a `01.2` do benchmark | `01` já é *Meu dia*. Renumerar um endereço é o que o [ADR-015](docs/EXEC_15_ENDERECAMENTO.md) existe para impedir — copiamos o padrão do Portal GPS, não os números dele. A `99` das fontes ficou: ali o que se copia **é** o padrão, de as telas que consertam o dado serem um módulo declarado. |
| Quem opera as cargas **não** vê os números | `eco.carga` e `eco.ler` são permissões separadas. Ligar alguém no suporte às cargas não pode dar a ele a margem de todo contrato da empresa ([ADR-023](docs/EXEC_17_RESULTADOS.md)). |
| A massa de teste tem **quinze anomalias de propósito** | Contrato deficitário, centro de custo sem orçamento, carga do monday falhada há 30 h. Cada uma exercita uma regra da tela, e `test_massa.py` afirma todas — se alguém "consertar" a massa, o teste cai e explica por quê. |
| Faixas diferentes da mesma tela carimbam fontes diferentes | Em `/workspace/resultados/` o dinheiro vem do Sankhya em D-1 e os projetos vêm do monday em minutos. Um carimbo único no topo estaria certo sobre metade do conteúdo. Nas telas de trabalho ele ainda diz *"Workspace · em tempo real"*, porque ali o número é do próprio produto. Ele existe antes dos conectores porque é disciplina: só vale se toda faixa nascer carimbada, e a suíte reprova a que nascer sem. Nenhum template lê o relógio — carimbo fabricado com `now` diz "agora" para dado de ontem ([ADR-017](docs/EXEC_15_ENDERECAMENTO.md)). |
| O pedido tem TRÊS etapas, não duas | Pedir → aprovar → **atender**. A fila (`/workspace/fila/`) é onde o pedido aprovado vira entregue, e é ela que alimenta o prazo REAL do catálogo: sem conclusões, o card mostraria "estimado" para sempre. |
| A área NÃO aprova o que ela mesma vai executar | Existiu um degrau de aprovação por área entre o gestor e a fila, e ele saiu em 20/08/2026. Com ele, a área tocava o mesmo pedido duas vezes — aprovava na bandeja e depois executava na fila —, e quem pediu via "aguardando aprovação" **depois** de o gestor já ter aprovado. A revisão da área não sumiu: ela é a fila, onde quem atende conclui ou devolve com o motivo. |
| Devolver não é reprovar, e tem volta | Reprovar encerra. Devolver diz "não dá para atender assim": o pedido volta para quem pediu **editável**, com o motivo à vista no formulário, e o botão *Enviar solicitação* promove a MESMA linha — mesmo número, mesmos anexos, mesma conversa. A cadeia é refeita (o gestor aprovou um texto que mudou), mas o relógio do prazo **não** volta — senão devolver viraria o jeito de limpar o próprio atraso. |
| O Workspace abre sem login | Decisão de produto: quem está na rede usa o hub, o catálogo, a documentação, a agenda das salas e **o formulário de qualquer serviço** sem barreira de autenticação. |
| …mas "Meu dia", "Minhas solicitações" e a bandeja pedem | O que é **de uma pessoa** não é institucional: o dia dela, os pedidos dela, a fila que espera a decisão dela, a correspondência dela. Sem sessão o produto assume a primeira pessoa do organograma, e essas telas mostrariam a vida dela a quem passasse pela URL. |
| …e enviar qualquer coisa também | **Assinar em nome de alguém** exige identidade: enviar pedido, aprovar, acertar, cancelar, marcar reserva, confirmar leitura, baixar anexo. Sempre no envio, nunca na consulta — quando o mesmo endereço faz as duas coisas, a fronteira passa entre o GET e o POST. A tela `/entrar/` existe só para isso: nenhum link leva até ela. |
| "Aplicativos" é a última faixa da home | A home abria por lá, com o iConnect como tile herói — o que a fazia um *app launcher*, com o trabalho da pessoa em segundo lugar. |
| Anexos moram fora de `MEDIA_ROOT` | Segurança, não organização de pasta: servidor web serve `MEDIA_ROOT` sem passar por view. No projeto anterior o nginx expôs `/media/` sem autenticação. |
| Nenhum `style=` em template | A CSP não tem `unsafe-inline`. Navegador ignora `unsafe-inline` quando há nonce, e nonce não se aplica a atributo `style` — o estilo é descartado **em silêncio**. Por isso a barra da bandeja é SVG, onde `width` é atributo. |
| A busca não pré-preenche o formulário | "quero 3 dias de férias em setembro" abre o pedido em branco. Interpretar quantidade e data erra sem avisar, e pedido com data errada é pior que pedido vazio. |
| Módulos marcados "Em breve" | Módulo sem dado é pior que módulo ausente (ADR-012). |
| Notificação pode repetir | Não há constraint de unicidade, de propósito: constraint em aviso falha *silenciando* a pessoa, que é pior que avisar duas vezes. |

---

## Testes

```bash
python -m pytest                          # 2.874 testes hoje, cobertura por app
python scripts/check_coverage_ratchet.py  # os pisos, que só sobem
```

O ratchet tem **duas** métricas, porque medem falhas diferentes: cobertura pega
"código novo sem teste"; contagem de testes pega "teste que sumiu". Apagar um
arquivo com 16 testes já derrubou a cobertura em 0,15 ponto — os testes se
sobrepõem demais para a cobertura sozinha detectar remoção.

Os pisos estão em [`pyproject.toml`](pyproject.toml). Baixar qualquer um exige
justificativa no PR.

---

## Documentação

**Comece por aqui:**

| Documento | O que responde | Para quem |
|---|---|---|
| [Guia do time](docs/EXEC_12_GUIA_DO_TIME.md) | O que o produto faz, quem vê o quê, e as decisões que qualquer mudança precisa respeitar | **todo mundo** |
| [Operação](docs/EXEC_13_OPERACAO.md) | Subir, configurar, agendar, diagnosticar | quem opera |
| [Entrega](docs/EXEC_11_ENTREGA.md) | A auditoria, o que foi implementado e o que ficou pendente | produto e gestão |
| [Segurança](docs/EXEC_14_SEGURANCA.md) | A auditoria de segurança: o que foi procurado, o que foi achado, o que foi corrigido e o que a infraestrutura precisa garantir | quem opera e quem responde por risco |

**Referência:**

| Documento | O que responde |
|---|---|
| [`.env.example`](.env.example) | Todas as variáveis de ambiente, o que cada uma protege e quais são obrigatórias em produção |
| [Guia de QA](docs/GUIA_QA_WORKSPACE.md) | O contrato de cada tela: para que serve, quando é útil, o que é defeito e o que é decisão |
| [Blueprint](docs/BLUEPRINT_ICONNECT_WORKSPACE.md) | A visão do produto |
| [EXEC 01–10](docs/) | As dez etapas de planejamento, da arquitetura ao reposicionamento |
| [EXEC 10](docs/EXEC_10_REPOSICIONAMENTO.md) | Onde "Portal" virou "iConnect Workspace", com os ADRs 010–014 |
| [Benchmark GPS](docs/BENCHMARK_GPS_LEITURA.md) | A leitura do Portal GPS / GPS 360: o que copiar, o que não copiar e quem é dono de cada dado |
| [EXEC 15](docs/EXEC_15_ENDERECAMENTO.md) | O código da tela, o carimbo de frescor e os prefixos de busca, com os ADRs 015–017 |
| [EXEC 16](docs/EXEC_16_INGESTAO.md) | A ingestão multi-fonte: `cargas`, `resultados`, os quatro conectores e o carregador, com os ADRs 018–021 |
| [EXEC 17](docs/EXEC_17_RESULTADOS.md) | A Apresentação de Resultados, a tela de fontes e a massa fictícia, com os ADRs 022–025 |
| [EXEC 18](docs/EXEC_18_EXCECOES.md) | O painel de exceções: as 18 regras, as 5 desligadas e as duas ações, com os ADRs 026–028 |
| [EXEC 19](docs/EXEC_19_CICLOS.md) | O ciclo de planejamento e a ATA: a pauta como objeto do produto, com os ADRs 029–031 |
| [EXEC 20](docs/EXEC_20_PLANOS.md) | O plano de ação com limiar: a regra dos 10% generalizada, com os ADRs 032–033 |
| [EXEC 21](docs/EXEC_21_METAS.md) | Metas, avaliação e PDI: a meta auditável porque a fórmula está na tela, com os ADRs 034–035 |
| [EXEC 22](docs/EXEC_22_ORCAMENTO.md) | Orçamento anual e revisão: a onda que começou decidindo a posse, com os ADRs 036–037 |
| [EXEC 23](docs/EXEC_23_PUBLICOS.md) | Segmentação de público: um ADR e um tile, não um módulo, com os ADRs 038–039 |

---

## O que vem a seguir

**SSO com o M365.** A conta nasce do Entra ID (ADR-013) — é o que os campos
`entra_oid` e `upn` de `contas.Pessoa` esperam. A autenticação será **silenciosa**
(`prompt=none`): quem tem sessão M365 viva chega identificado sem ver tela
nenhuma, e quem não tem segue anônimo no hub público. Sem isso, o SSO viraria uma
parede de login na frente de um hub que é aberto por decisão.

Isso também corrige a raiz do problema das 881 lotações: `manager`, `department`,
`officeLocation` e `jobTitle` vêm do diretório, que é onde esses dados já são
mantidos de verdade — em vez de um CSV importado à mão.

**Assistente de conhecimento.** Depende dos POPs e normativos reais. Com o SSO
ligado, o mesmo token lê a biblioteca do SharePoint e a ingestão deixa de exigir
upload manual.
