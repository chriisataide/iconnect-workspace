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

> **A confirmar antes de qualquer código:** os endpoints exatos, os limites de
> requisição e se há necessidade de credencial para o volume que vamos usar.
> Não escrevi os detalhes aqui de propósito — documentação de API pública muda,
> e um endereço errado num documento é pior que a ausência dele. A conferência é
> meia hora de quem for implementar, e ela vem **antes** da estimativa virar
> compromisso.

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

1. **Meia hora** conferindo a documentação viva do PNCP: endpoints, limites,
   e se os campos que o radar precisa estão todos lá.
2. **Uma conversa com o comercial** para definir o filtro. Sem ele, o conector
   entrega um radar que ninguém abre duas vezes.
3. **Só então** o conector, que é trabalho conhecido — o quarto de uma série em
   que os três primeiros já existem e compartilham carregador, espelho,
   procedência, carimbo de frescor e tela de fontes.

**O que muda no produto para o usuário:** o radar deixa de depender de alguém
lembrar de cadastrar, e a tela 26.1 passa a ter uma fonte na tela 99 como
qualquer outra faixa — com carimbo, histórico e "de onde vem esse número".

---

## 26.5 O que este levantamento NÃO promete

- **Não estimei prazo.** A estimativa depende do passo 1, e um número dado antes
  dele seria chute com aparência de plano.
- **Não escrevi endpoint nenhum.** Ver a nota do § 26.2.C.
- **Não decidi o filtro.** Ele é do comercial, e é a parte que decide se o radar
  serve ou vira ruído.
- **A decisão de 2026 sobre raspagem continua valendo** para feiras e eventos.
  O que este documento propõe não a contradiz: propõe uma fonte oficial para
  **outro** tipo de oportunidade, que estava na mesma tabela por acidente.
