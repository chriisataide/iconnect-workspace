# EXEC 18 · Painel de exceções — Onda 4 do benchmark GPS

> `/workspace/excecoes/` (código `11`). Dezoito regras ligadas, cinco
> registradas e desligadas, e uma decisão em cada uma.

---

## 18.1 Não é um dashboard

É uma **lista de regras**, cada uma com uma contagem, que expande para a grade
dos registros que a violaram. É o padrão mais aproveitável do benchmark, e o
"Painel Gestão de Efetivo" do Portal GPS é exatamente isso:

```
MRH FÉRIAS EM ATRASO                                    1 registro
EFETIVO ATIVO COM AUSÊNCIA > 5%                       146 registros
EFETIVO COM ASO VENCIDO                             2.556 registros
```

E cada linha da grade traz o **responsável**. A exceção nasce endereçada — sem
isso a lista vira um relatório que alguém precisa distribuir à mão, e a
distribuição para de acontecer na terceira semana.

---

## 18.2 Três estados, e eles não são dois

| Estado | O que quer dizer | O que fazer |
|---|---|---|
| **com ocorrências** | a regra rodou e achou | resolver |
| **sem ocorrências** | a regra rodou e não achou | nada — e a regra **fica na lista** |
| **não avaliada** | a fonte da regra não está no ar | ligar a fonte |

**Regra com zero não some.** Sumir esconderia que a regra existe, e o efeito
prático é alguém reabrir a discussão sobre "deveríamos vigiar X" seis meses
depois de já estarmos vigiando.

**"Não avaliada" não é zero.** Zero é tranquilidade; não avaliada é uma fonte
para ligar. Somá-las faria uma fonte caída parecer um mês sem problema — que é o
pior resultado possível num painel de exceções.

---

## 18.3 A lógica é código; se a regra está ligada é dado

`RegraExcecao` no banco guarda `ativa`, `ordem`, `severidade` e `janela`. O
avaliador mora em `workspace/excecoes/`, num registro em memória.

Se a lógica fosse dado, daria para "ativar" pelo `/admin/` uma regra que ninguém
escreveu — e o erro apareceria às três da manhã, no cron. Se a configuração
fosse código, mudar a severidade exigiria deploy, e severidade é decisão de quem
opera, tomada no dia.

`test_todo_avaliador_registrado_tem_regra_no_banco` guarda os dois lados:
avaliador sem regra é código que nunca roda, e passaria em toda revisão.

---

## 18.4 As dezoito

### As dez do próprio Workspace

| # | Regra | Quem responde |
|---|---|---|
| 1 | Lotação sem centro de custo | R.H. |
| 2 | Pessoa sem papel vigente | R.H. |
| 3 | Papel vencendo em 30 dias | R.H. |
| 4 | Solicitação parada além do prazo | a área que atende |
| 5 | Aprovação pendente há mais de 3 dias | quem decide |
| 6 | Leitura obrigatória não confirmada | R.H. |
| 7 | Normativo sem revisão há 12 meses | o dono do documento |
| 8 | Centro de custo sem orçamento | Financeiro |
| 9 | Centro de custo acima de 90% do teto | Financeiro |
| 10 | Reserva confirmada e não usada | quem reservou |

### As seis que a ingestão destravou

| # | Regra | Fonte |
|---|---|---|
| 11 | Contrato com margem abaixo de 10% | Platform |
| 12 | Contrato vencendo em 60 dias | Platform |
| 13 | Contrato Layer 3 sem apresentação | Platform |
| 14 | Detrator sem tratativa | Platform |
| 15 | Projeto bloqueado há mais de 15 dias | monday |
| 16 | Marco vencido sem replanejamento | monday |

### As duas que vigiam o mecanismo

| # | Regra | Observação |
|---|---|---|
| 17 | Fonte sem carga além da cadência | fonte **não configurada** fica de fora |
| 18 | Divergência entre fontes | aparece mesmo quando a precedência resolveu |

As duas últimas não pertencem a departamento nenhum — `escopo_papel` fica vazio,
e elas aparecem para quem já está no painel por outro motivo. Mostrá-las sozinhas
transformaria o painel numa tela de infraestrutura para quem não opera
infraestrutura, e por isso elas **não bastam** para abrir a tela.

### Duas regras que prometem menos do que o nome sugere

As regras 12 e 13 dizem "sem visita" e "sem apresentação", e o Workspace **não
registra nenhuma das duas**: visita e apresentação moram no Platform, e a
integração de hoje traz consolidado, não agenda. A regra lista os contratos que
vencem e os Layer 3, e o texto diz isso.

É diferente de fingir que verificou. Uma regra que promete o que não cumpre
ensina a desconfiar das outras dezessete.

---

## 18.5 As cinco registradas e desligadas

| Regra | Depende de |
|---|---|
| CC no ERP e fora do orçamento (e o inverso) | `sankhya + financas` — ciclo orçamentário |
| Efetivo com ASO vencido | `hris` — depois do SSO (ADR-013) |
| Efetivo com reciclagem vencida | `hris` |
| Efetivo com mais de três advertências | `hris` |
| Contrato de experiência vencendo | `hris` |

Elas existem no banco, desligadas, com a fonte anotada. É o que responde "por que
não vigiamos ASO?" sem ninguém precisar perguntar — e o que impede a mesma
discussão de voltar em seis meses.

**Quando forem ligadas, a linha é o registro — nunca a pessoa com documento ao
lado.** O benchmark tem grade de CPF com botão de exportar, e é a primeira coisa
que a leitura marcou como não copiar.

---

## 18.6 As duas ações, e o que elas não fazem

**Avisar quem responde** manda **um aviso por pessoa**, e não um por ocorrência.
Quarenta avisos sobre a mesma regra transformam o sino num lugar que se aprende a
ignorar — e o aviso que importa some junto.

**Abrir solicitação** leva ao catálogo com `?origem=excecao:<chave>`. A origem
atravessa o envio e vira **linha de histórico** do pedido; o conteúdo do
formulário **nunca** é pré-preenchido. Pedido com dado adivinhado é pior que
pedido vazio: o formulário mostra o que vai ser enviado, e o palpite não. É a
mesma decisão do §57 sobre a busca.

**Não há "marcar como resolvido".** Resolver é trabalho de gente, e um botão
desses só ensinaria a limpar a lista sem tocar no problema.

---

## 18.7 A tendência

`ResultadoExcecao` guarda o retrato de cada avaliação, e a tela mostra a
**variação** ao lado da contagem. Uma regra que foi de 3 para 40 importa mais que
uma que está em 40 há um ano — e a contagem sozinha não conta isso.

Sem histórico, a tela **não inventa uma seta**: `None` e não zero.

Quem grava o retrato é `avaliar_excecoes`, o comando. **A tela avalia ao vivo e
não escreve.**

```bash
python manage.py avaliar_excecoes                    # simula
python manage.py avaliar_excecoes --aplicar          # grava o retrato
python manage.py avaliar_excecoes --aplicar --avisar # e notifica
python manage.py avaliar_excecoes --regra papel-vencendo   # uma só
```

`--avisar` é separado de `--aplicar` de propósito: gravar o retrato é barato e
silencioso; avisar gente é caro e acorda o sino de todo mundo. Quem agenda decide
a cadência de cada um.

---

## 18.8 O que os testes pegaram

Duas regras estouraram na primeira avaliação, e o guarda funcionou — elas
viraram "não avaliada" com o motivo, e as outras dezesseis rodaram:

1. **`permissoes__contains` não existe no SQLite.** `Papel.permissoes` é
   `JSONField`, e a consulta funcionava em produção e estourava
   `NotSupportedError` em desenvolvimento. É a pior forma de um defeito existir:
   ele só aparece para quem está desenvolvendo. Virou filtro em Python sobre
   quinze linhas.
2. **`EtapaAprovacao` não tem `criado_em`.** O relógio da regra 5 passou a ser o
   da `SolicitacaoAprovacao` — que é, aliás, o número que a diretoria pergunta:
   *há quanto tempo este pedido está parado esperando alguém decidir*.

---

## 18.9 ADRs

### ADR-026 · A lógica da regra é código; a configuração é dado

**Contexto:** um painel de regras convida a pôr tudo no banco, para "ligar e
desligar sem deploy".

**Decisão:** `RegraExcecao` guarda `ativa`, `ordem`, `severidade` e `janela`; o
avaliador é código, num registro em memória.

**Consequência:** não é possível ligar uma regra que ninguém escreveu, e não é
preciso deploy para mudar severidade. Os dois lados são guardados por teste:
avaliador sem regra no banco reprova, e regra ligada sem avaliador aparece como
"não avaliada" com o motivo, em vez de "sem ocorrências".

### ADR-027 · Zero e "não avaliada" são estados diferentes

**Contexto:** seria mais simples tratar fonte indisponível como zero
ocorrências.

**Decisão:** três estados, e o total do painel **não** soma as não avaliadas.

**Consequência:** uma fonte fora do ar não pode parecer um mês tranquilo. É a
mesma família de decisão do carimbo de frescor — falha de carga não zera o
bloco — e do painel de indicadores — sem amostra, "—" e não "0".

### ADR-028 · A exceção nasce endereçada, e sem dado pessoal

**Contexto:** o benchmark põe o e-mail do gestor em cada linha da grade, e isso
é o que faz a lista virar ação.

**Decisão:** cada ocorrência traz **nome e papel** de quem responde. Nunca
e-mail, nunca documento. Papel sem ocupante aparece como **"ninguém"**, escrito
assim.

**Consequência:** quem abre a tela tem o papel da regra, e não o direito de ver
dado pessoal de terceiro. E "ninguém" é um achado — é a regra 2 aparecendo por
outro caminho —, enquanto uma coluna vazia pareceria defeito de renderização.
