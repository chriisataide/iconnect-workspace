// Build customizado do ECharts para o iConnect Workspace.
//
// Só o que o catálogo de gráficos usa. O pacote completo passa de 1 MB e a home
// carrega junto — este arquivo é a diferença entre isso e ~300 KB.
//
// Quem acrescentar um tipo de gráfico acrescenta o import AQUI e roda
// `npm run build`. Se esquecer, o gráfico não desenha e o console diz qual
// série não foi registrada — que é uma falha barulhenta, e é o que se quer.
import * as echarts from "echarts/core";

import {
  BarChart,
  LineChart,
  PieChart,
  GaugeChart,
  ScatterChart,
  HeatmapChart,
} from "echarts/charts";

import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  DatasetComponent,
  VisualMapComponent,
  AriaComponent,
} from "echarts/components";

// SVG e NÃO canvas: canvas não dá texto selecionável, não tem árvore de
// acessibilidade e piora o PDF. E sem o CanvasRenderer o bundle não o carrega.
import { SVGRenderer } from "echarts/renderers";

echarts.use([
  BarChart, LineChart, PieChart, GaugeChart, ScatterChart, HeatmapChart,
  TitleComponent, TooltipComponent, GridComponent, LegendComponent,
  MarkLineComponent, DatasetComponent, VisualMapComponent, AriaComponent,
  SVGRenderer,
]);

export const init = echarts.init;
export const use = echarts.use;
export const registerTheme = echarts.registerTheme;
export const connect = echarts.connect;
export const getInstanceByDom = echarts.getInstanceByDom;
