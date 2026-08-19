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

# Massa mínima para as telas terem o que mostrar
python manage.py semear_papeis --aplicar
python manage.py semear_catalogo --aplicar
python manage.py semear_regras_aprovacao --aplicar
python manage.py importar_organograma docs/exemplos/organograma-inicial.csv \
    --criar-usuarios --aplicar
python manage.py reindexar_busca

python manage.py runserver
```

Abra <http://127.0.0.1:8000/workspace/>. **O Workspace é aberto** para tudo que
é institucional — o hub, a busca, o catálogo, a documentação, a agenda das
salas e o formulário de qualquer serviço. Identificar-se é exigido para ver o
que é **de uma pessoa** ("Meu dia", "Minhas solicitações", a bandeja, a
correspondência) e para **assinar** em nome dela: enviar, aprovar, acertar,
cancelar, confirmar leitura, baixar anexo.

Todos os comandos `semear_*` rodam em **simulação por padrão**: sem `--aplicar`
eles só relatam o que fariam.

> **Falta massa para três módulos.** Documentação, Reservas e Correspondências
> não têm semeadora — os dados entram pelo `/admin/`. Ver a seção 1.3 do
> [guia de QA](docs/GUIA_QA_WORKSPACE.md).

---

## Os apps, e a direção da dependência

```
contas       →  a conta da pessoa. AUTH_USER_MODEL, e-mail como identificador
identidade   →  organograma, papel com escopo e vigência, pode()      ← RAIZ
workspace    →  a superfície e os motores do Workspace                ← FOLHA
financas     →  centro de custo e orçamento; implementa o contrato
```

A regra que não pode inverter:

    o domínio depende do CONTRATO (`workspace.providers`),
    nunca da SUPERFÍCIE (`workspace.views`, `.models`, `.services`).

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
| A cadeia de aprovação tem um degrau de ÁREA | Depois do gestor direto, antes da diretoria: o R.H. revisa o que é de R.H., o Financeiro o que é dinheiro. São perguntas diferentes — o gestor sabe se a equipe aguenta a ausência; o R.H. sabe se a pessoa tem saldo e se o período é legal. A regra casa por PREFIXO (`rh.` pega `rh.ferias` e o item que nascer amanhã). |
| O pedido tem TRÊS etapas, não duas | Pedir → aprovar → **atender**. A fila de atendimento (`/workspace/fila/`) é onde o pedido aprovado vira entregue, e é ela que alimenta o prazo REAL do catálogo: sem conclusões, o card mostraria "estimado" para sempre. |
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
python -m pytest                          # 1.172 testes, cobertura por app
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

**Referência:**

| Documento | O que responde |
|---|---|
| [Guia de QA](docs/GUIA_QA_WORKSPACE.md) | O contrato de cada tela: para que serve, quando é útil, o que é defeito e o que é decisão |
| [Blueprint](docs/BLUEPRINT_ICONNECT_WORKSPACE.md) | A visão do produto |
| [EXEC 01–10](docs/) | As dez etapas de planejamento, da arquitetura ao reposicionamento |
| [EXEC 10](docs/EXEC_10_REPOSICIONAMENTO.md) | Onde "Portal" virou "iConnect Workspace", com os ADRs 010–014 |

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
