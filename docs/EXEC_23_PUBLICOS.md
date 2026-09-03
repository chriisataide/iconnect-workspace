# EXEC 23 · Segmentação de público — Onda 9 do benchmark GPS

> Três públicos, três produtos, uma marca. A onda mais curta das nove, e o
> benchmark já previa isso: *"decisão de marca e roteamento; provavelmente um
> ADR e um tile, não um módulo"*.

---

## 23.1 O que o benchmark descreve

No site institucional do GPS, o acesso é um menu **"Extranet"** com quatro
destinos: *GPS 360 – Cliente*, *GPS 360 – Fornecedor*, *Gerenciador Eletrônico* e
*Portal GPS*. O documento anota a intenção equivalente para a ADB: um botão com
as sub-abas **"ADB Cliente"**, **"ADB Fornecedor"** e **"Portal ADB"**.

Três públicos. Três produtos. Uma marca.

---

## 23.2 A decisão: este produto é o Portal ADB

E os outros dois públicos **não entram aqui**.

Não é escolha de escopo — é o que o produto comporta. O modelo de permissão
inteiro assume que `Pessoa` é **colaborador com `Lotacao` no organograma**:

- `escopo_de()` recorta por unidade, departamento e centro de custo, todos vindos
  da lotação;
- `pode()` resolve `.equipe` percorrendo `Lotacao.gestor` recursivamente;
- `subjects_de()` monta a ACL da busca com `unidade:`, `depto:` e `papel:`.

Cliente e fornecedor não têm nada disso. Deixá-los entrar exigiria um **segundo
modelo de identidade** — ou, pior, pessoas no organograma que não são
funcionários. Que é literalmente o defeito das **881 lotações órfãs** que este
repositório cita desde a primeira etapa.

---

## 23.3 Vazio quer dizer ausente, e não "em breve"

`AppSpec` sem rota vira um tile *"em breve"*, e está certo para um módulo do
roadmap: alguém decidiu que ele vai existir, e o Workspace comunica o roadmap em
vez de escondê-lo.

Para o ADB Cliente está **errado**. "Em breve" é uma promessa, e ninguém decidiu
que esse produto vai existir. O ADR-012 já proíbe módulo "em breve" para
preencher taxonomia; aqui é o mesmo princípio aplicado a público.

`ADB_CLIENTE_URL` vazia — o estado de hoje — significa que o ADB Cliente **não
aparece em lugar nenhum**. Nem apagado, nem "em breve", nem numa seção vazia
explicando o vazio.

O público continua **registrado**, porém: a decisão de não existir é informação,
e ela some se ele não estiver em lugar nenhum. `publicos.todos()` traz os três;
`publicos.disponiveis()` traz o que a tela mostra.

---

## 23.4 O guard que vale mais que o resto

**URL de público externo tem de ser absoluta e apontar para fora deste host.**

Um `ADB_CLIENTE_URL=/workspace/` mal configurado mandaria clientes para dentro do
portal do funcionário — e a tela de entrar diria a eles, com todas as letras, que
aquele é o lugar certo.

O registro recusa **na subida do processo**:

| Configuração | O que acontece |
|---|---|
| `/workspace/` | recusada — não é endereço absoluto |
| `//evil.example.com/` | recusada — sem esquema |
| `javascript:alert(1)` | recusada — esquema não é http(s) |
| `https://portal.adb.com.br/` com esse host em `ALLOWED_HOSTS` | recusada — aponta para este próprio produto |
| `https://cliente.adb.com.br/` | aceita |

`*` em `ALLOWED_HOSTS` **não** casa: ele diria que todo endereço é interno, e
nenhum público externo poderia ser configurado numa máquina de desenvolvimento —
o defeito apareceria só em produção, ao contrário do que se quer.

É a mesma verificação que `cargas/conectores/platform.py` faz ao recusar um
`next` que aponta para fora, com o sinal trocado.

---

## 23.5 O roteamento — a metade prática

Quem é cliente ou fornecedor e digitou o endereço errado bate hoje numa tela de
login que **nunca vai passar**, sem nada dizendo para onde ir. Ela tenta a senha
três vezes e abre um chamado.

`/entrar/` passa a mostrar, **quando houver destino configurado**:

> **Você é cliente ou fornecedor?**
> Sua entrada é outra — esta é a do colaborador da ADB.
> · **ADB Cliente** — Contratos, medições e ocorrências do seu contrato.

É o único ponto do produto onde essas pessoas aparecem, e por isso é ali que o
roteamento mora. `contas` não importa `workspace` no topo — a direção da
dependência é a outra, e inverter isso para exibir três linhas de texto seria
caro pelo motivo errado.

E o **Portal ADB não se lista na própria porta**: dizer a quem já está aqui que a
entrada dele é aqui não ajuda ninguém.

---

## 23.6 O tile

Um tile e não um módulo — foi o que o benchmark previu.

Os públicos configurados entram na faixa Aplicativos com `url_direta`, ordem 120,
logo depois do iConnect Platform: **as entradas que saem deste produto ficam
juntas no fim da faixa**. Nunca `url_name` — a rota deste produto não leva ao
produto de outro público.

---

## 23.7 Os três testes que protegem a onda

1. `test_destino_nao_configurado_nao_aparece_nem_como_em_breve` — e o público
   continua registrado, porque a decisão de não existir é informação.
2. `test_publico_externo_nao_aponta_para_dentro_deste_produto`, mais os quatro
   irmãos: caminho relativo, esquema estranho, curinga de `ALLOWED_HOSTS` e
   configuração errada derrubando a subida.
3. `test_quem_errou_a_porta_encontra_a_certa_na_tela_de_entrar` e
   `test_sem_destino_configurado_a_tela_de_entrar_nao_desenha_a_secao`.

**Sem migração, sem model, sem tela nova.** Se esta onda tivesse produzido um
módulo, ela teria errado.

---

## 23.8 ADRs

### ADR-038 · O Workspace é o Portal ADB; cliente e fornecedor não entram aqui

**Contexto:** a marca prevê três públicos, e a tentação é atender os três no
mesmo produto — o cadastro já existe, o login já existe, bastaria um papel novo.

**Decisão:** este produto atende **um** público, o colaborador. Cliente e
fornecedor são outros produtos, e o Workspace só os **roteia**.

**Consequência:** o modelo de permissão continua assumindo `Pessoa` com
`Lotacao`, que é o que faz `pode()` e `escopo_de()` funcionarem. Um "papel de
cliente" exigiria ou um segundo modelo de identidade, ou pessoas no organograma
que não são funcionários — o defeito das 881 lotações órfãs, outra vez.

O preço é que a ADB precisará construir dois produtos para servir os outros dois
públicos. É o preço certo: eles não compartilham nem o dado, nem a permissão, nem
a pergunta que o usuário chega fazendo.

### ADR-039 · Destino não configurado não aparece — e não aparece como "em breve"

**Contexto:** o launcher já sabe mostrar tile "em breve", e reusar isso seria
imediato.

**Decisão:** público externo sem endereço não aparece em lugar nenhum. Continua
registrado, sem aparecer.

**Consequência:** o produto não promete o que ninguém decidiu construir. É o
ADR-012 aplicado a público: lá, módulo "em breve" para preencher taxonomia; aqui,
sub-aba "em breve" para preencher marca.

E a diferença entre **ausente** e **registrado sem endereço** é o que permite
responder "por que não temos o ADB Cliente?" sem ninguém perguntar — a mesma
razão pela qual as regras de exceção desligadas ficam no banco.
