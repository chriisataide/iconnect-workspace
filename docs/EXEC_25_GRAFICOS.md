# EXEC 25 · Gráficos com biblioteca

> Três ondas: abrir `style-src` com contrapartidas (9.5), montar os gráficos
> (10) e ligar a interação (11). Este documento começa pela primeira, que é a
> única que mexe em segurança.

---

## 25.1 A onda 9.5 em uma frase

`style-src` passou a ter `unsafe-inline`. `script-src` não. E a regra "nenhum
`style=` em template nosso" saiu do navegador e virou lint.

---

## 25.2 O que a CSP era, e o que ela é

```diff
  default-src 'self';
- script-src  'self';
+ script-src  'self' 'nonce-…';
- style-src   'self';
+ style-src   'self' 'unsafe-inline';
  img-src     'self' data:;
  font-src    'self';
  connect-src 'self';
  form-action 'self';
+ frame-src   'none';
  frame-ancestors 'none';
  base-uri    'self';
  object-src  'none'
```

Três mudanças. Duas delas abrem alguma coisa; a terceira fecha.

### O que o prompt supunha e não era verdade aqui

O prompt mandava **tirar o nonce de `style-src`**. Não havia nonce em lugar
nenhum: `SEGURANCA_CSP` era uma string estática, sem nonce em diretiva alguma. A
armadilha que ele descrevia — nonce anulando `unsafe-inline` — não podia
acontecer neste repositório.

E **seis das oito contrapartidas já estavam em vigor** desde o primeiro dia:
`img-src 'self' data:`, `font-src`, `connect-src`, `base-uri`, `form-action` e
`object-src`. Só `frame-src 'none'` faltava — `default-src 'self'` a cobria, e
`default-src 'self'` **permite** iframe de mesma origem.

---

## 25.3 Por que o nonce entrou em `script-src`

A onda 10 leva os números do servidor para o gráfico num bloco de dados:

```html
<script type="application/json" nonce="…" id="grafico-ebitda">{"series": […]}</script>
```

Um bloco `type="application/json"` não é executado, e por isso quase certamente
não seria bloqueado por `script-src 'self'`. **"Quase certamente" não é base para
uma decisão de segurança**, e a alternativa custa pouco: nonce em `script-src`
não enfraquece nada — ele só anularia um `unsafe-inline` que não está lá — e
torna o bloco inequivocamente permitido.

O preço é real e vale registrar: a CSP deixou de ser uma constante e passou a ser
montada por requisição, em `iconnect_workspace.seguranca`. `SEGURANCA_CSP` virou
`SEGURANCA_CSP_MOLDE`, com `{nonce}` no lugar.

O nonce vive em `request.csp_nonce`, e não num `threading.local`: o segundo
sobrevive à requisição num servidor com pool de threads, e nonce que vaza de uma
requisição para a seguinte é nonce reutilizável.

---

## 25.4 O detalhe mecânico que não pode ser errado

Navegador moderno **ignora `unsafe-inline` quando há nonce na mesma diretiva**.

Manter os dois não é meio-termo: é manter o comportamento antigo achando que
abriu. E o sintoma seria o pior possível — o gráfico não quebra, ele **sai
errado**: sem tooltip posicionado, sem redimensionamento, com a legenda no lugar
errado. Nada no log do servidor, nada no console além de avisos que ninguém lê.

Por isso `test_a_csp_abriu_style_e_nao_abriu_script` afirma os quatro fatos ao
mesmo tempo, e não um de cada vez:

| | tem que ser |
|---|---|
| `script-src` | **sem** `'unsafe-inline'` |
| `script-src` | **com** nonce |
| `style-src` | **com** `'unsafe-inline'` |
| `style-src` | **sem** nonce |

Qualquer um deles sozinho passa despercebido numa revisão. É o tipo de linha que
alguém "arruma" numa faxina de configuração.

---

## 25.5 A disciplina que a CSP não cobra mais

`style=` em template **nosso** continua proibido. O que a biblioteca injeta é
aceito; o que nós escrevemos, não.

**Dois testes cobram, pelos dois lados:**

- `test_nenhum_template_nosso_escreve_style` varre os **templates**, como
  arquivo — o repositório inteiro, e não quatro rotas. A versão anterior cobria
  quatro telas de trinta e cinco, e cobria porque o navegador fazia o resto do
  trabalho;
- `test_nenhuma_tela_usa_atributo_style` varre o **HTML renderizado** — e pega o
  `style=` que não está em template nenhum: o que um serviço monta em string, o
  que vem de um campo do banco, o que um filtro produz.

Eles se sobrepõem de propósito. Quando a cobrança sai do browser, é melhor que
ela sobre em dois lugares do que caia em nenhum.

**E a entrada também fecha:** `test_nenhum_template_interpola_dentro_de_style`
recusa `{{ }}` dentro de `<style>`. Com `style-src` aberta, isso é injeção de
CSS direta — e injeção de CSS não é enfeite: um seletor de atributo com
`background-image: url(…)` lê o valor de um campo e o manda para fora,
caractere por caractere. `img-src 'self' data:` fecha a saída; essa regra fecha
a entrada.

A barra tripla da bandeja **continua em SVG**, onde `width` é atributo. Não
porque precise mais, mas porque desenhar assim sobrevive a `style-src` fechada —
e fechar de novo não deveria custar uma reescrita.

---

## 25.6 ADR

### ADR-040 · `style-src` abre para a biblioteca de gráficos; `script-src` não

**Contexto.** Este repositório nasceu sem `unsafe-inline` em diretiva nenhuma, e
o README registra por que isso foi possível: o Workspace deixou de compartilhar
header com o iConnect Platform, que usa `style=` em escala. Era uma vantagem
concreta, e ela está sendo gasta de propósito.

A decisão de produto passou a ser usar biblioteca de gráficos. **Toda biblioteca
de mercado escreve `style=` no DOM** — tooltip, redimensionamento, posição de
legenda. Não é uma escolha de implementação delas que se possa contornar: é como
elas desenham.

**Decisão.**

1. `style-src` recebe `'unsafe-inline'`, e **não** recebe nonce.
2. `script-src` recebe nonce e **continua sem** `'unsafe-inline'`. Nenhuma
   biblioteca de gráfico precisa dele: todas carregam como arquivo externo. Se
   alguma exigir, ela sai.
3. `frame-src 'none'` entra, junto com as contrapartidas que já existiam.
4. A regra "nenhum `style=` nosso" vira lint sobre o repositório inteiro, e
   `{{ }}` dentro de `<style>` passa a ser proibido explicitamente.

**Consequência.** O vetor que se abriu é injeção de CSS: com `style-src` livre,
CSS controlado por atacante consegue ler valor de campo com seletor de atributo e
exfiltrar por requisição de imagem. As oito diretivas de saída fechadas são o que
torna esse vetor caro — sem elas, a contrapartida não existe.

O que se perdeu é a frase "sem `unsafe-inline` em diretiva nenhuma", que era
verificável e agora não é mais. O que se ganhou é medidor, mapa de calor e eixo
duplo sem escrever um motor de gráfico — trabalho que o benchmark exige em pelo
menos onze lugares.

**Sob qual condição isso é revisto.** No dia em que a biblioteca sair, ou o
navegador oferecer um caminho para estilo de terceiro sem `unsafe-inline`
(`style-src-attr` com hash, hoje sem suporte suficiente), fechar de volta tem de
ser **uma linha no settings**. É exatamente para isso que o lint continua
cobrando o que a CSP não cobra: sem ele, voltar atrás viraria uma auditoria de
trinta e cinco telas.

**O que não foi feito, e por quê.** A diretiva **não** é configurável por
ambiente. Uma variável de ambiente aqui é como uma política estrita vira frouxa
em produção sem ninguém notar — e o único lugar onde a diferença apareceria é um
console de navegador que ninguém abre em produção.
