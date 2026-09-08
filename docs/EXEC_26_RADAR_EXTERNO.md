# EXEC 26 · Trazer oportunidades de fora — o levantamento

> Pedido em 08/09/2026: *"conseguimos trazer direto da internet, visto que seria
> uma oportunidade para a empresa?"*
>
> Este documento é **levantamento, não implementação**. Ele existe para a
> decisão ser tomada com os custos na mesa.

---

## 26.1 A decisão que já existia, e por que ela merece ser revista

`workspace/models/marketing.py` abre com uma frase explícita:

> **Nada aqui é coletado automaticamente.** O cadastro é manual, por decisão
> explícita: varrer sites de feira para preencher esta tabela seria coleta
> automatizada de terceiros, e não é o que este produto faz.

Essa decisão continua **certa para feiras e eventos** — e está **errada para
editais públicos**, que é onde uma empresa de segurança patrimonial ganha
contrato. As duas coisas foram tratadas como uma só porque moram na mesma
tabela.

O radar tem dois tipos (`TipoOportunidade`), e eles não têm nada em comum quanto
à origem:

| Tipo | De onde viria | Custo de trazer |
|---|---|---|
| **Feira / evento** | site do organizador, sem formato | alto e permanente |
| **Edital / licitação** | portal público, com API oficial | baixo e estável |

---

## 26.2 As três formas de "trazer da internet", e o que cada uma custa

### A · Raspagem de site (o que a frase original recusou)

Ler o HTML do site de cada organizador de feira.

**Por que continua sendo não.** Não há formato: cada site é uma página
diferente, e a página muda sem avisar. Uma raspagem é um contrato que a outra
parte não assinou e pode rescindir a qualquer momento mudando uma `<div>`. Na
prática, ela quebra em silêncio, a tabela para de crescer, e ninguém percebe até
alguém perguntar por que faz três meses que não aparece feira nenhuma.

Some-se o lado jurídico: termos de uso de site de terceiro costumam proibir
coleta automatizada, e o produto teria de decidir se os ignora.

**Recomendação: não fazer.** É a única das três em que o custo cresce para
sempre.

### B · Feeds estruturados, onde existirem

Alguns organizadores publicam calendário em **iCal** (`.ics`) ou **RSS**.
Quando existe, é barato: formato estável, uma URL, sem raspagem.

**O problema é a cobertura.** Não dá para saber de antemão quantos dos
organizadores relevantes publicam algo assim — isso é uma pergunta para a área
de marketing responder com a lista de feiras que ela acompanha, e não para o
código descobrir.

**Recomendação: perguntar ao marketing primeiro.** Se cinco dos dez eventos que
importam têm feed, vale; se um tem, não vale o conector.

### C · Editais públicos — **o caminho que vale a pena**

Aqui há fonte oficial, aberta e documentada. Contratação pública no Brasil é
regida pela **Lei 14.133/2021**, e o **PNCP — Portal Nacional de Contratações
Públicas** é o repositório oficial dessas contratações, com **API pública**.

Para uma empresa de segurança patrimonial isto não é acessório: é onde estão os
contratos de vigilância de órgão público, que é boa parte do mercado.

**O que muda em relação a A e B:**

- é **fonte oficial**, e não site de terceiro — sem questão de termos de uso;
- tem **formato declarado**, e não HTML a interpretar;
- a informação que o radar quer já está lá: objeto, órgão, valor estimado,
  **data limite para proposta** — que é exatamente o campo `prazo_resposta`.

---

## 26.2.1 A conferência, feita — 08/09/2026

Não é mais estimativa. Abaixo está o que foi **medido contra a API de
produção**, e as três surpresas que só apareceram assim.

### O que existe

A especificação OpenAPI está em `pncp.gov.br/api/consulta/v3/api-docs` e declara
**12 endpoints de consulta**. Um deles é exatamente o que o radar precisa:

    GET /api/consulta/v1/contratacoes/proposta

É "contratações com proposta ainda aberta". Obrigatórios: `dataFinal` e
`pagina`. Opcionais que interessam: `uf`, `codigoModalidadeContratacao`,
`codigoMunicipioIbge`, `cnpj`. `tamanhoPagina` aceita de **10 a 50**.

### Surpresa 1 — não precisa de token

A especificação **declara** um `bearerAuth` (JWT), e por isso o levantamento
anterior deixou a pergunta em aberto. Declarar não é exigir: uma chamada sem
cabeçalho nenhum voltou **HTTP 400 de validação de parâmetro**, e não 401. Ou
seja, ela passou pela porta e parou na conferência dos campos.

Com os parâmetros certos: **HTTP 200**. O `bearerAuth` é das APIs de
manutenção — as que os órgãos usam para publicar —, e não das de consulta.

**Consequência prática: nenhuma credencial a pedir a ninguém.** Este conector é
o único dos quatro que não depende de terceiro para começar.

### Surpresa 2 — a API não filtra por palavra, e isso é caro

**Não existe** parâmetro de busca por texto do objeto, CNAE ou código de item.
Os filtros são todos estruturados: data, UF, município, CNPJ, modalidade.

Então a triagem por "vigilância" é **nossa**, depois de baixar. Medido na Bahia:

    2.164 editais com proposta aberta
    300 lidos (6 páginas de 50)
      3 batem com os termos de segurança  →  1%

Um por cento. Sem a triagem, o radar receberia dois mil itens de merenda
escolar, obra e material de escritório — e viraria a tela que ninguém abre duas
vezes. **A lista de termos é o que decide se isto serve**, e ela é do comercial.

### Surpresa 3 — há limite de requisição, e ele morde

Sete requisições em treze segundos → **HTTP 429 Too Many Requests**.

Medido depois, com pausa: **uma requisição por segundo passa** (6 de 6). Houve
também um `TimeoutError` isolado numa chamada mais lenta — o portal é público e
às vezes demora, o que o conector agendado já sabe tratar (60 s de espera e
recuo exponencial, `cargas/transporte.py`).

**Consequência para o desenho:** o conector precisa de pausa entre páginas. Não
é detalhe de implementação — é a diferença entre uma carga que roda de
madrugada e uma que é bloqueada na terceira página todo dia.

### O que a resposta traz, campo a campo

Conferido num item real. À esquerda o campo do PNCP, à direita onde ele encaixa
no que o radar **já tem**:

| PNCP | `Oportunidade` |
|---|---|
| `numeroControlePNCP` | chave externa e procedência |
| `objetoCompra` | título |
| `valorTotalEstimado` | valor |
| **`dataEncerramentoProposta`** | **`prazo_resposta`** — o campo que o radar existe para ter |
| `unidadeOrgao.{ufSigla, municipioNome, nomeUnidade}` | órgão e lugar |
| `modalidadeNome` | ex.: "Pregão - Eletrônico" |

`linkSistemaOrigem` veio **nulo** no item conferido. Vale não contar com ele: o
link para o edital pode ter de ser montado a partir do `numeroControlePNCP`.

### O que a triagem achou de verdade

Na primeira amostra, em Salvador, com proposta encerrando em **23/09**:

    R$ 5.871.050,16   serviços de vigilância
    R$ 5.115.249,72   serviços de vigilância

Onze milhões em dois editais, abertos agora, que hoje só entram no radar se
alguém lembrar de cadastrar à mão.

---

## 26.2.2 O custo, agora com número

**Volume.** Cinco UFs a ~2.000 editais cada = 10.000 registros. A 50 por página
são 200 requisições; a uma por segundo, **cerca de três minutos e meio**. É
carga de madrugada, e cabe folgado na janela que o `deploy/crontab` já reserva.

**Trabalho.** Um conector no padrão dos três que já existem, e nenhuma peça de
arquitetura nova: carregador, espelho, procedência, carimbo de frescor, tela de
fontes e histórico já estão prontos e são os mesmos.

O que este conector tem **a menos** que os outros três:

- não precisa de credencial;
- não precisa de dicionário de ids (o `MONDAY_BOARDS` não tem equivalente aqui).

O que ele tem **a mais**:

- a pausa entre páginas;
- a triagem por termo, que é a única regra de negócio de verdade — e a única
  parte que não posso escrever sozinho.

---

## 26.3 Como isto entra no produto sem virar um segundo sistema

**Não é código novo de arquitetura.** É mais um conector, no mesmo lugar e com o
mesmo contrato dos três que já existem:

    cargas/conectores/pncp.py        ← novo, ao lado de sankhya.py e monday.py
    cargas/models.py                 ← uma linha em `Fonte`, pelo semeador
    workspace/models/marketing.py    ← procedência na Oportunidade

O conector obedece às regras que já valem para os outros:

1. **Nenhuma chamada de rede na tela.** A carga roda no cron; a tela lê o
   espelho. Um portal público lento não pode virar um portal ADB lento.
2. **Credencial em variável de ambiente**, se houver.
3. **Procedência em toda linha** — `pncp:<id do edital>`, e o link para a fonte.
4. **Somente leitura.** O Workspace nunca escreve no lado de lá.
5. **Carga que falha não zera a tela.** O radar mostra o que já tinha, com a
   idade em destaque.

### O que precisa ser decidido, e não é técnico

- **O filtro.** O PNCP publica contratação de todo o país, de todo tipo. Trazer
  tudo entope o radar e o torna inútil — que é o mesmo defeito de um painel com
  oito cartões sempre visíveis. É preciso definir: quais UFs, qual faixa de
  valor, quais objetos (CNAE ou palavra-chave).
- **Quem tria.** Um edital que entra sozinho no radar é uma linha que ninguém
  decidiu que interessa. Sugestão: entrar como `descoberta`, e alguém do
  comercial promove para `aberta` — que é o estado que hoje pede decisão.
- **A retenção.** Edital vencido vira ruído em três meses.

---

## 26.4 O que eu recomendo

**Fazer o C, não fazer o A, e perguntar antes de decidir o B.**

Em ordem:

1. ~~Conferir a documentação viva do PNCP.~~ **Feito em 08/09/2026** — § 26.2.1.
   Nenhum bloqueio: a consulta é pública, os campos que o radar precisa estão
   todos lá, e o limite de requisição tem contorno conhecido.
2. **Uma conversa com o comercial** para definir o filtro — e ela virou o
   ÚNICO caminho crítico. Não é preferência: a API não filtra por palavra, a
   triagem é nossa, e sem a lista de termos o conector baixa dois mil editais de
   merenda escolar por UF. **Preciso de duas coisas:**
   - as **UFs** onde a empresa disputa;
   - os **termos** que definem um edital nosso — começo sugerido, tirado dos
     objetos reais que a amostra devolveu: `vigilância`, `segurança
     patrimonial`, `vigia`, `portaria`, `monitoramento eletrônico`, `controle de
     acesso`, `brigada`, `segurança privada`, `guarda patrimonial`.
3. **Só então** o conector, que é trabalho conhecido — o quarto de uma série em
   que os três primeiros já existem e compartilham carregador, espelho,
   procedência, carimbo de frescor e tela de fontes.

**O que muda no produto para o usuário:** o radar deixa de depender de alguém
lembrar de cadastrar, e a tela 26.1 passa a ter uma fonte na tela 99 como
qualquer outra faixa — com carimbo, histórico e "de onde vem esse número".

---

## 26.5 O que este levantamento NÃO promete

- **Não decidi o filtro.** Ele é do comercial, e é a parte que decide se o radar
  serve ou vira ruído. É também, agora, a única coisa que falta para começar.
- **Não conferi os códigos de modalidade.** A especificação não os enumera. Dá
  para ignorar no começo — sem `codigoModalidadeContratacao` a consulta traz
  todas as modalidades, que é o que se quer enquanto o filtro é por palavra.
- **Não sei a cobertura fora da amostra.** Medi Bahia. A proporção de 1% e o
  volume de ~2.000 editais abertos por UF podem variar bastante em São Paulo, e
  a leitura da primeira carga real é que responde isso.
- **Não medi o limite de requisição com precisão.** Sei que 7 em 13 s reprova e
  que 1 por segundo passa. Não fui além disso de propósito: é um portal público
  do governo, e descobrir o teto exato exigiria justamente o tipo de rajada que
  o conector nunca vai fazer.
- **A decisão de 2026 sobre raspagem continua valendo** para feiras e eventos.
  O que este documento propõe não a contradiz: propõe uma fonte oficial para
  **outro** tipo de oportunidade, que estava na mesma tabela por acidente.
