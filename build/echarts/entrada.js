// Build customizado do ECharts para o iConnect Workspace.
//
// Só o que o catálogo de gráficos usa. O pacote completo passa de 1 MB e a home
// carrega junto — este arquivo é a diferença entre isso e ~300 KB.
//
// Quem acrescentar um tipo de gráfico acrescenta o import AQUI e roda
// `npm run build`. Se esquecer, o gráfico não desenha e o console diz qual
// série não foi registrada — que é uma falha barulhenta, e é o que se quer.
import * as echarts from "echarts/core";

// O `HeatmapChart` SAIU: o mapa de calor do catálogo é uma TABELA HTML, e não
// um gráfico — menor, legível sem JavaScript, e com o número selecionável.
// Manter o import traria uma série que nada desenha.
import {
  BarChart,
  LineChart,
  PieChart,
  GaugeChart,
  ScatterChart,
} from "echarts/charts";

import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  DatasetComponent,
  // `VisualMapComponent` saiu junto: ele existia para o heatmap.
  AriaComponent,
} from "echarts/components";

// SVG e NÃO canvas: canvas não dá texto selecionável, não tem árvore de
// acessibilidade e piora o PDF. E sem o CanvasRenderer o bundle não o carrega.
import { SVGRenderer } from "echarts/renderers";

echarts.use([
  BarChart, LineChart, PieChart, GaugeChart, ScatterChart,
  TitleComponent, TooltipComponent, GridComponent, LegendComponent,
  MarkLineComponent, DatasetComponent, AriaComponent,
  SVGRenderer,
]);

export const init = echarts.init;
export const use = echarts.use;
export const registerTheme = echarts.registerTheme;
export const connect = echarts.connect;
export const getInstanceByDom = echarts.getInstanceByDom;
