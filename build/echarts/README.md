# Build customizado do ECharts

O que vai para produção é **`workspace/static/workspace/js/echarts.min.js`**, e ele
é **versionado**. Esta pasta existe só para regerá-lo.

## Por que o artefato é versionado

Para que o deploy e o CI **nunca precisem de Node**. Este é um projeto Django; pôr
um passo de `npm install` no caminho de subir o produto significa que uma falha
de rede na registry derruba um deploy que não tem nada a ver com JavaScript.

É a mesma razão pela qual o PDF não usa ECharts SSR em Node (ADR-041).

Quem regenera o bundle precisa de Node. Quem instala o produto, não.

## Como regerar

```bash
cd build/echarts
npm install
npm run build          # escreve em ../../workspace/static/workspace/js/echarts.min.js
```

Depois **rode a suíte**: `test_graficos.py` afirma o teto de tamanho e que os
tipos de série que ninguém usa ficaram de fora.

## Como acrescentar um tipo de gráfico

Acrescente o `import` em `entrada.js`, rode `npm run build`, e ajuste o teto em
`test_o_bundle_nao_e_o_pacote_completo` se ele subir.

Se esquecer o import, o gráfico não desenha e o console diz qual série não foi
registrada — falha barulhenta, que é o que se quer.

## Versão

ECharts **6.1.0**, com renderizador **SVG**.

SVG e não canvas por texto selecionável, árvore de acessibilidade e PDF — e não
por tamanho: o canvas mede 7 KB a MENOS. A escolha é de qualidade, e vale dizer
que ela custa alguma coisa.
