# Execução · Etapa 6 — Design System "Aurora"

> **Documento de design.** Tokens, escalas, grid, componentes, responsividade, dark mode e governança. Escopo: app `workspace/` ([D-02](EXEC_01_ESCOPO_E_DEPENDENCIAS.md)). Os 155 templates existentes não são tocados.
>
> **Agosto/2026** · Etapa 6 de 9 · **Aguarda aprovação antes da Etapa 7**

---

## Sumário

- [6.0 O achado que define a paleta](#60-o-achado-que-define-a-paleta)
- [6.1 Princípios](#61-princípios)
- [6.2 Cor](#62-cor)
- [6.3 Tipografia](#63-tipografia)
- [6.4 Espaçamento e densidade](#64-espaçamento-e-densidade)
- [6.5 Raio, elevação e movimento](#65-raio-elevação-e-movimento)
- [6.6 Dark mode](#66-dark-mode)
- [6.7 Tokens — o arquivo completo](#67-tokens--o-arquivo-completo)
- [6.8 Integração com Tailwind](#68-integração-com-tailwind)
- [6.9 Ícones](#69-ícones)
- [6.10 Grid e layout](#610-grid-e-layout)
- [6.11 Inventário de componentes](#611-inventário-de-componentes)
- [6.12 Especificação dos componentes](#612-especificação-dos-componentes)
- [6.13 Composições por módulo](#613-composições-por-módulo)
- [6.14 Responsividade](#614-responsividade)
- [6.15 Acessibilidade](#615-acessibilidade)
- [6.16 Anti-padrões](#616-anti-padrões)
- [6.17 Governança](#617-governança)

---

## 6.0 O achado que define a paleta

Ao validar contraste antes de fixar os tokens, encontrei um defeito de acessibilidade **em produção hoje**:

```
static/css/dashboard-colors.css:453   a { color: #06b6d4; }
static/css/dashboard-colors.css:27    --bs-link-color: #06b6d4 !important;
```

| Cor | Sobre branco | WCAG AA (texto normal, mínimo 4,5) |
|---|:-:|---|
| `#06b6d4` — ciano da marca | **2,43** | ❌ **Falha** |
| `#0891b2` — ciano 600 | 3,68 | ⚠️ Só para texto grande |
| `#0e7490` — ciano 700 | **5,36** | ✅ Passa |

**Todo link do sistema está hoje abaixo do mínimo de contraste.** Não é hipótese — é o valor medido da cor aplicada em `a { color }`.

E o problema não é só do ciano:

| Cor | Sobre branco | Situação |
|---|:-:|---|
| `#059669` verde | 3,77 | ❌ falha como texto |
| `#d97706` âmbar | 3,19 | ❌ falha como texto |
| `#dc2626` vermelho | 4,83 | ✅ passa |

### A decisão que isso força

> **Toda cor semântica tem dois tokens: um para preencher e outro para escrever.**

```
--au-accent        #06b6d4   ← preenchimento, borda, ícone grande, gráfico
--au-accent-text   #0e7490   ← texto, link, ícone pequeno
```

Isso preserva a identidade visual da marca — o ciano continua sendo o ciano em todo lugar que ele aparece como **superfície** — e resolve a legibilidade onde ele aparece como **texto**. É a separação que falta na maioria dos design systems construídos a partir de uma paleta de marca.

> **Ação para fora do Workspace:** o defeito existe nos 155 templates atuais. Corrigir `a { color }` em `dashboard-colors.css` é uma linha, fora do escopo do V1.0, e vale registrar como dívida separada.

---

## 6.1 Princípios

| # | Princípio | Consequência prática |
|:-:|---|---|
| 1 | **Densidade é respeito** | Escala de 4px, não 8px. Usuário profissional passa horas aqui |
| 2 | **Hierarquia por tipografia e espaço** | Cor é reservada para estado e ação, não para decoração |
| 3 | **Movimento informa** | Se a animação não explica de onde algo veio, ela é removida |
| 4 | **Dark é primeira classe** | Nenhuma cor tem definição única dentro de media query |
| 5 | **Contraste antes de estética** | Token que falha AA não entra na paleta |
| 6 | **Componente nasce do uso** | Nada especulativo. 26 no V1.0 porque 26 são usados |

---

## 6.2 Cor

### Escala de marca

Preservada do design system atual (`--ic-primary` Slate + `--ic-accent` Cyan), agora com escala completa.

```
Brand (Slate)  50  #f8fafc   100 #f1f5f9   200 #e2e8f0   300 #cbd5e1
               400 #94a3b8   500 #64748b   600 #475569   700 #334155  ← primária atual
               800 #1e293b   900 #0f172a   950 #020617

Accent (Cyan)  300 #67e8f9   400 #22d3ee   500 #06b6d4  ← accent atual
               600 #0891b2   700 #0e7490   800 #155e75
```

### Papéis semânticos

| Token | Light | Dark | Uso |
|---|---|---|---|
| `--au-bg` | `#f8fafc` | `#020617` | Fundo da página |
| `--au-surface` | `#ffffff` | `#0b1220` | Card, widget, painel |
| `--au-surface-raised` | `#ffffff` | `#111c2e` | Modal, popover, dropdown |
| `--au-surface-sunken` | `#f1f5f9` | `#060b16` | Cabeçalho de tabela, área rebaixada |
| `--au-border` | `#e2e8f0` | `#1e293b` | Divisória padrão |
| `--au-border-strong` | `#cbd5e1` | `#334155` | Contorno de campo, ênfase |
| `--au-text` | `#0f172a` | `#e2e8f0` | Texto primário |
| `--au-text-muted` | `#64748b` | `#94a3b8` | Secundário — **4,76 / 7,30** ✅ |
| `--au-text-subtle` | `#94a3b8` | `#64748b` | Terciário, só para texto ≥16px |

### Semântica com par fill/text

| Papel | `--au-<x>` (fill) | `--au-<x>-text` | `--au-<x>-bg` (sutil) |
|---|---|---|---|
| Accent | `#06b6d4` | `#0e7490` ✅ 5,36 | `rgb(6 182 212 / .10)` |
| Sucesso | `#059669` | `#047857` ✅ 5,48 | `rgb(5 150 105 / .10)` |
| Aviso | `#d97706` | `#b45309` ✅ 5,02 | `rgb(217 119 6 / .10)` |
| Perigo | `#dc2626` | `#b91c1c` ✅ 6,3 | `rgb(220 38 38 / .10)` |
| Neutro | `#64748b` | `#475569` ✅ 7,5 | `rgb(100 116 139 / .10)` |

### Cores de estado herdadas

Os status de ticket e prioridade já têm padrão no sistema (`--ic-status-*`). Aurora **mantém os mesmos valores** para não criar dois vocabulários visuais, aplicando a regra fill/text:

```
aberto      #ef4444 / texto #b91c1c      andamento  #f59e0b / texto #b45309
aguardando  #64748b / texto #475569      resolvido  #22c55e / texto #15803d
fechado     #334155 / texto #334155
```

---

## 6.3 Tipografia

### Família

**Inter**, já carregada no projeto. **Recomendação:** auto-hospedar a variável (`InterVariable.woff2`, ~110 KB) em vez de buscar no Google Fonts.

| Motivo | Ganho |
|---|---|
| Elimina requisição a terceiro | −1 conexão, −1 dependência externa |
| Remove `fonts.googleapis.com` do `style-src` | CSP mais fechada |
| Sem FOUT | O texto não pisca ao carregar |

### Escala — razão 1,2, base 13px

Base menor que o padrão web (16px) porque a densidade é requisito ([princípio 1](#61-princípios)). 13px em Inter tem legibilidade equivalente a 14px em fontes de menor altura-x.

| Token | Tamanho | Altura | Peso | Uso |
|---|:-:|:-:|:-:|---|
| `--au-t-2xs` | 10px | 1.4 | 600 | Rótulo de badge, uppercase |
| `--au-t-xs` | 11px | 1.45 | 500 | Metadado, timestamp |
| `--au-t-sm` | 12px | 1.5 | 400 | Texto secundário |
| `--au-t-base` | **13px** | 1.55 | 400 | **Corpo padrão** |
| `--au-t-md` | 15px | 1.5 | 500 | Título de card, item de lista |
| `--au-t-lg` | 18px | 1.4 | 600 | Título de widget |
| `--au-t-xl` | 22px | 1.3 | 600 | Título de página |
| `--au-t-2xl` | 28px | 1.25 | 700 | Número de KPI |
| `--au-t-3xl` | 36px | 1.2 | 700 | Saudação da home |

**Números tabulares obrigatórios** em valor monetário, contador e coluna numérica:

```css
.au-num { font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; }
```
Sem isso, um contador que vai de 9 para 10 desloca o layout — e o olho percebe como instabilidade.

---

## 6.4 Espaçamento e densidade

### Escala de 4px

```
--au-0  0      --au-1  4px    --au-2  8px    --au-3  12px
--au-4  16px   --au-5  20px   --au-6  24px   --au-8  32px
--au-10 40px   --au-12 48px   --au-16 64px
```

**Regra:** nenhum valor de espaço fora desta escala. Valor mágico em template reprova revisão.

### Densidade

Três níveis previstos; **o V1.0 entrega apenas `padrao`** — o seletor chega com `WKS-013` (V1.1). Os tokens já existem para que a mudança seja de uma linha.

| Nível | `--au-row-h` | `--au-card-pad` | Para quem |
|---|:-:|:-:|---|
| `compacto` | 30px | 12px | Sala de monitoramento, tabela longa |
| **`padrao`** | **36px** | **16px** | **Padrão do V1.0** |
| `confortavel` | 44px | 20px | Toque, tablet |

---

## 6.5 Raio, elevação e movimento

### Raio — contido de propósito

```
--au-r-sm   6px    campo, badge
--au-r-md   10px   card, widget, botão
--au-r-lg   14px   modal, painel
--au-r-full 999px  avatar, pill, contador
```
Raio grande faz interface profissional parecer brinquedo. 10px é o limite para superfície de conteúdo.

### Elevação — três níveis, nunca mais

```css
--au-e-0: none;
--au-e-1: 0 1px 2px rgb(15 23 42/.06), 0 1px 3px rgb(15 23 42/.10);   /* card em repouso */
--au-e-2: 0 4px 6px -1px rgb(15 23 42/.07), 0 2px 4px -2px rgb(15 23 42/.06);  /* hover, dropdown */
--au-e-3: 0 12px 20px -6px rgb(15 23 42/.12), 0 4px 8px -4px rgb(15 23 42/.08); /* modal, ⌘K */
```

> Em dark mode, sombra não funciona (não há luz para bloquear). **Profundidade no escuro vem de superfície mais clara**, não de sombra mais forte — por isso `--au-surface-raised` é mais claro que `--au-surface`.

### Movimento

```
--au-dur-fast  120ms   estado de botão, hover
--au-dur       180ms   troca de conteúdo HTMX, popover
--au-dur-slow  280ms   modal, painel lateral
--au-ease      cubic-bezier(.2,0,0,1)     entrada
--au-ease-out  cubic-bezier(0,0,.2,1)     saída
```

**Nada acima de 280ms.** E:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    transition-duration: .01ms !important;
  }
}
```

### Glassmorphism — exatamente três lugares

Permitido apenas em: **⌘K sobreposto**, **topbar ao rolar** e **painel do assistente** (V1.1).

```css
.au-glass {
  background: color-mix(in srgb, var(--au-surface) 72%, transparent);
  backdrop-filter: blur(20px) saturate(140%);
  border: 1px solid color-mix(in srgb, var(--au-text) 8%, transparent);
}
```
**Nunca em card de conteúdo** — prejudica contraste de texto denso, que é a maior parte deste produto.

---

## 6.6 Dark mode

### A estratégia em três blocos

```css
:root { /* claro — TODA cor definida aqui, sempre */ }

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* redefine apenas os tokens que mudam */ }
}

:root[data-theme="dark"] { /* mesmos overrides — o seletor vence a media query */ }
```

**Por que os três blocos, se o V1.0 nunca escreve `data-theme`:** o V1.0 respeita apenas a preferência do sistema. Quando `WKS-013` chegar no V1.1, ligar o seletor manual é escrever um atributo — sem reescrever CSS. O custo hoje é zero; o custo depois seria uma refatoração.

### As duas regras que não podem ser quebradas

| # | Regra | Por quê |
|:-:|---|---|
| DM1 | **Nenhuma cor tem definição única dentro de media query** | Se existe só no bloco escuro, o modo claro herda o valor do host e quebra |
| DM2 | **`body` sempre pinta o fundo explicitamente** | Fundo transparente empresta o tema de quem hospeda a página |

### O que muda e o que não muda

| Muda | Não muda |
|---|---|
| Superfícies, bordas, texto | Escala de espaço, raio, tipografia |
| Sombra → superfície mais clara | Semântica de estado (erro continua vermelho) |
| Accent para `#22d3ee` (10,36 no escuro ✅) | Peso e tamanho de fonte |

---

## 6.7 Tokens — o arquivo completo

`workspace/static/workspace/src/tokens.css`

```css
/* ═══════════════════════════════════════════════════════════════
   AURORA — Design System do iConnect Workspace
   Marca preservada: Slate #334155 + Cyan #06b6d4
   Todo token de texto validado em WCAG AA (≥ 4,5:1)
   ═══════════════════════════════════════════════════════════════ */

:root {
  /* ── Marca ─────────────────────────────────────────────────── */
  --au-brand-50:#f8fafc; --au-brand-100:#f1f5f9; --au-brand-200:#e2e8f0;
  --au-brand-300:#cbd5e1; --au-brand-400:#94a3b8; --au-brand-500:#64748b;
  --au-brand-600:#475569; --au-brand-700:#334155; --au-brand-800:#1e293b;
  --au-brand-900:#0f172a; --au-brand-950:#020617;

  --au-accent-300:#67e8f9; --au-accent-400:#22d3ee; --au-accent-500:#06b6d4;
  --au-accent-600:#0891b2; --au-accent-700:#0e7490; --au-accent-800:#155e75;

  /* ── Superfície e texto ────────────────────────────────────── */
  --au-bg:              var(--au-brand-50);
  --au-surface:         #ffffff;
  --au-surface-raised:  #ffffff;
  --au-surface-sunken:  var(--au-brand-100);
  --au-border:          var(--au-brand-200);
  --au-border-strong:   var(--au-brand-300);
  --au-text:            var(--au-brand-900);
  --au-text-muted:      var(--au-brand-500);
  --au-text-subtle:     var(--au-brand-400);
  --au-text-inverse:    #ffffff;

  /* ── Semântica: fill / text / bg ───────────────────────────── */
  --au-accent:          var(--au-accent-500);
  --au-accent-text:     var(--au-accent-700);
  --au-accent-bg:       rgb(6 182 212 / .10);

  --au-success:         #059669;
  --au-success-text:    #047857;
  --au-success-bg:      rgb(5 150 105 / .10);

  --au-warning:         #d97706;
  --au-warning-text:    #b45309;
  --au-warning-bg:      rgb(217 119 6 / .10);

  --au-danger:          #dc2626;
  --au-danger-text:     #b91c1c;
  --au-danger-bg:       rgb(220 38 38 / .10);

  --au-neutral:         var(--au-brand-500);
  --au-neutral-text:    var(--au-brand-600);
  --au-neutral-bg:      rgb(100 116 139 / .10);

  /* ── Estado operacional (herdado do padrão existente) ──────── */
  --au-st-aberto:#ef4444;      --au-st-aberto-text:#b91c1c;
  --au-st-andamento:#f59e0b;   --au-st-andamento-text:#b45309;
  --au-st-aguardando:#64748b;  --au-st-aguardando-text:#475569;
  --au-st-resolvido:#22c55e;   --au-st-resolvido-text:#15803d;
  --au-st-fechado:#334155;     --au-st-fechado-text:#334155;

  /* ── Espaço ────────────────────────────────────────────────── */
  --au-0:0; --au-1:4px; --au-2:8px; --au-3:12px; --au-4:16px;
  --au-5:20px; --au-6:24px; --au-8:32px; --au-10:40px; --au-12:48px; --au-16:64px;

  /* ── Densidade (padrão no V1.0) ────────────────────────────── */
  --au-row-h:36px;
  --au-card-pad:var(--au-4);
  --au-control-h:34px;

  /* ── Raio ──────────────────────────────────────────────────── */
  --au-r-sm:6px; --au-r-md:10px; --au-r-lg:14px; --au-r-full:999px;

  /* ── Elevação ──────────────────────────────────────────────── */
  --au-e-0:none;
  --au-e-1:0 1px 2px rgb(15 23 42/.06), 0 1px 3px rgb(15 23 42/.10);
  --au-e-2:0 4px 6px -1px rgb(15 23 42/.07), 0 2px 4px -2px rgb(15 23 42/.06);
  --au-e-3:0 12px 20px -6px rgb(15 23 42/.12), 0 4px 8px -4px rgb(15 23 42/.08);

  /* ── Tipografia ────────────────────────────────────────────── */
  --au-font:'InterVariable','Inter',system-ui,-apple-system,'Segoe UI',sans-serif;
  --au-mono:'JetBrains Mono',ui-monospace,'SF Mono',monospace;
  --au-t-2xs:10px; --au-t-xs:11px; --au-t-sm:12px; --au-t-base:13px;
  --au-t-md:15px;  --au-t-lg:18px; --au-t-xl:22px; --au-t-2xl:28px; --au-t-3xl:36px;

  /* ── Movimento ─────────────────────────────────────────────── */
  --au-dur-fast:120ms; --au-dur:180ms; --au-dur-slow:280ms;
  --au-ease:cubic-bezier(.2,0,0,1);
  --au-ease-out:cubic-bezier(0,0,.2,1);

  /* ── Foco ──────────────────────────────────────────────────── */
  --au-focus:0 0 0 2px var(--au-surface), 0 0 0 4px var(--au-accent-600);

  /* ── Layout ────────────────────────────────────────────────── */
  --au-sidebar-w:236px;
  --au-sidebar-w-collapsed:60px;
  --au-topbar-h:52px;
  --au-content-max:1440px;
}

/* ── DARK ─────────────────────────────────────────────────────── */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --au-bg:              var(--au-brand-950);
    --au-surface:         #0b1220;
    --au-surface-raised:  #111c2e;
    --au-surface-sunken:  #060b16;
    --au-border:          var(--au-brand-800);
    --au-border-strong:   var(--au-brand-700);
    --au-text:            var(--au-brand-200);
    --au-text-muted:      var(--au-brand-400);
    --au-text-subtle:     var(--au-brand-500);

    --au-accent:          var(--au-accent-400);
    --au-accent-text:     var(--au-accent-400);
    --au-accent-bg:       rgb(34 211 238 / .14);
    --au-success-text:    #34d399;
    --au-warning-text:    #fbbf24;
    --au-danger-text:     #f87171;
    --au-neutral-text:    var(--au-brand-400);

    --au-e-1:0 1px 2px rgb(0 0 0/.40);
    --au-e-2:0 4px 8px rgb(0 0 0/.45);
    --au-e-3:0 16px 32px rgb(0 0 0/.50);

    --au-focus:0 0 0 2px var(--au-surface), 0 0 0 4px var(--au-accent-400);
  }
}

/* Seletor manual — inerte no V1.0, pronto para o V1.1 (WKS-013) */
:root[data-theme="dark"] { /* mesmos overrides do bloco acima */ }

/* DM2 */
body { background: var(--au-bg); color: var(--au-text); font-family: var(--au-font); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration:.01ms!important; transition-duration:.01ms!important;
  }
}
```

---

## 6.8 Integração com Tailwind

### Recomendação: Tailwind 4, configuração em CSS

Tailwind 4 dispensa `tailwind.config.js` — o tema vive no próprio CSS, referenciando os tokens. **Um arquivo a menos, uma linguagem a menos.**

`workspace/static/workspace/src/aurora.css`

```css
@import "tailwindcss";
@import "./tokens.css";

@theme inline {
  --color-bg:            var(--au-bg);
  --color-surface:       var(--au-surface);
  --color-surface-raised:var(--au-surface-raised);
  --color-surface-sunken:var(--au-surface-sunken);
  --color-border:        var(--au-border);
  --color-border-strong: var(--au-border-strong);
  --color-fg:            var(--au-text);
  --color-fg-muted:      var(--au-text-muted);
  --color-fg-subtle:     var(--au-text-subtle);

  --color-accent:        var(--au-accent);
  --color-accent-text:   var(--au-accent-text);
  --color-accent-bg:     var(--au-accent-bg);
  --color-success:       var(--au-success);
  --color-success-text:  var(--au-success-text);
  --color-warning-text:  var(--au-warning-text);
  --color-danger:        var(--au-danger);
  --color-danger-text:   var(--au-danger-text);

  --font-sans:  var(--au-font);
  --font-mono:  var(--au-mono);

  --text-2xs:   var(--au-t-2xs);
  --text-xs:    var(--au-t-xs);
  --text-sm:    var(--au-t-sm);
  --text-base:  var(--au-t-base);
  --text-md:    var(--au-t-md);
  --text-lg:    var(--au-t-lg);
  --text-xl:    var(--au-t-xl);
  --text-2xl:   var(--au-t-2xl);
  --text-3xl:   var(--au-t-3xl);

  --radius-sm:  var(--au-r-sm);
  --radius-md:  var(--au-r-md);
  --radius-lg:  var(--au-r-lg);

  --shadow-e1:  var(--au-e-1);
  --shadow-e2:  var(--au-e-2);
  --shadow-e3:  var(--au-e-3);
}

@source "../../templates/workspace/**/*.html";   /* A-02: escopo restrito */
```

> **Se o ambiente exigir Tailwind 3:** manter `tailwind.config.js` com `theme.extend` apontando para as mesmas variáveis, e `content` limitado a `workspace/templates/**`. O resto deste documento não muda — os tokens são a fonte da verdade em qualquer versão.

### Build

```bash
npx @tailwindcss/cli \
  -i workspace/static/workspace/src/aurora.css \
  -o workspace/static/workspace/dist/aurora.css --minify
```

Fora do `compressor` e fora do pipeline SCSS do Material Dashboard. Nenhum arquivo existente é lido pelo build.

### Convenção de uso

| Situação | Como |
|---|---|
| Layout, espaço, alinhamento | Utilitário Tailwind direto |
| Componente repetido em ≥3 lugares | Classe `au-*` em `components.css` com `@apply` |
| Valor arbitrário (`w-[137px]`) | **Proibido.** Reprova revisão |
| Cor literal (`text-[#06b6d4]`) | **Proibido.** Só token |

---

## 6.9 Ícones

### Decisão: SVG inline por sprite, não fonte de ícone

O projeto já sofreu com fonte de ícone — o commit `b77a0b6` corrige *"ícone Base do Copiloto no sidebar (fonte errada)"*, e hoje convivem `nucleo-icons` e Material Symbols.

| Critério | Fonte de ícone | **Sprite SVG** |
|---|:-:|:-:|
| Ícone errado por fonte trocada | acontece | impossível |
| FOUT / bloco no carregamento | sim | não |
| Cor via `currentColor` | limitado | nativo |
| Peso (26 ícones) | ~40 KB da fonte inteira | ~8 KB só do que se usa |
| Acessibilidade | vira caractere no leitor de tela | `aria-hidden` explícito |

**Fonte:** [Lucide](https://lucide.dev) — traço de 1,5px, geometria consistente com Inter, licença MIT.

```html
<!-- sprite carregado uma vez no shell -->
<svg class="au-icon" aria-hidden="true" focusable="false">
  <use href="{% static 'workspace/icons.svg' %}#check"></use>
</svg>
```

```css
.au-icon { width:16px; height:16px; stroke:currentColor; stroke-width:1.5;
           fill:none; flex-shrink:0; }
.au-icon--sm{width:14px;height:14px} .au-icon--lg{width:20px;height:20px}
```

### Os 26 ícones do V1.0

```
check · x · alert-triangle · alert-circle · info · clock · calendar
search · command · chevron-right · chevron-down · arrow-left · external-link
user · users · building · file-text · book-open · megaphone
inbox · check-circle · rotate-ccw · send · paperclip · grid · bell
```

Um ícone novo só entra com uso real, e sempre pelo mesmo processo de build do sprite.

---

## 6.10 Grid e layout

### Estrutura do shell

```
┌──────────────────────────────────────────────────────────────┐
│  TOPBAR                                        52px          │
├──────────┬───────────────────────────────────────────────────┤
│ SIDEBAR  │  CONTEÚDO                                         │
│  236px   │  max-width 1440px · padding 24px                  │
│          │                                                   │
│  colapsa │  ┌──── grid de 12 colunas · gap 16px ────────┐   │
│  p/ 60px │  │                                            │   │
│          │  └────────────────────────────────────────────┘   │
└──────────┴───────────────────────────────────────────────────┘
```

### As três zonas da home

| Zona | Colunas ≥1280 | 1024–1279 | 640–1023 | <640 |
|---|:-:|:-:|:-:|:-:|
| **1 · Atenção** | 12 (largura total) | 12 | 12 | 12 |
| **2 · Ação** | 4 + 4 + 4 | 6 + 6 | 12 | 12 |
| **3 · Contexto** | 8 + 4 | 12 | 12 | 12 |

```html
<div class="grid grid-cols-12 gap-4">
  <section class="col-span-12"><!-- zona 1 --></section>

  <div class="col-span-12 md:col-span-6 xl:col-span-4"><!-- aprovações --></div>
  <div class="col-span-12 md:col-span-6 xl:col-span-4"><!-- meu dia --></div>
  <div class="col-span-12 xl:col-span-4"><!-- escala --></div>

  <div class="col-span-12 xl:col-span-8"><!-- mural --></div>
  <div class="col-span-12 xl:col-span-4"><!-- acesso rápido --></div>
</div>
```

### Altura reservada — regra estrutural

Todo widget declara `min-height` **antes** do conteúdo chegar. É o que garante `CLS = 0` ([Etapa 3, A3](EXEC_03_MODULOS.md)).

```
atencao 96px · aprovacoes 280px · meu_dia 280px
escala 200px · mural 240px · acesso_rapido 160px
```

---

## 6.11 Inventário de componentes

**26 componentes no V1.0.** A estimativa da Etapa 3 era ~24; a contagem fechada é 26.

| # | Componente | Grupo | Usado por |
|:-:|---|---|---|
| 1 | `au-app-shell` | Estrutura | WKS |
| 2 | `au-sidebar` | Estrutura | WKS |
| 3 | `au-topbar` | Estrutura | WKS |
| 4 | `au-widget-grid` | Estrutura | WKS |
| 5 | `au-card` | Superfície | todos |
| 6 | `au-widget` | Superfície | WKS |
| 7 | `au-modal` | Superfície | APR, SVC, CNT |
| 8 | `au-panel` | Superfície | APR, CNT |
| 9 | `au-breadcrumb` | Navegação | CNT, SVC |
| 10 | `au-nav-item` | Navegação | WKS |
| 11 | `au-command-bar` | Navegação | SRC |
| 12 | `au-button` | Ação | todos |
| 13 | `au-icon-button` | Ação | todos |
| 14 | `au-quick-action` | Ação | WKS, SVC |
| 15 | `au-field` | Entrada | SVC, CNT, COM, PPL |
| 16 | `au-input` | Entrada | idem |
| 17 | `au-select` | Entrada | idem |
| 18 | `au-file-drop` | Entrada | SVC, CNT, PPL |
| 19 | `au-table` | Dado | APR, CNT, COM |
| 20 | `au-list-row` | Dado | WKS, SVC, OPS |
| 21 | `au-empty` | Dado | todos |
| 22 | `au-skeleton` | Dado | WKS |
| 23 | `au-toast` | Feedback | todos |
| 24 | `au-inline-alert` | Feedback | todos |
| 25 | `au-badge` | Feedback | todos |
| 26 | `au-avatar` | Feedback | IDN, APR, COM |

### Planejados, **não construídos** no V1.0

Registrados para não serem inventados de novo — e deliberadamente fora, por [PLT R6](EXEC_03_MODULOS.md):

`au-timeline` (V1.1, `SVC-004`) · `au-kpi-tile` (V1.1, `FIN-001`) · `au-sparkline` (V1.1) · `au-datepicker` (V1.1) · `au-combobox` (V1.1) · `au-tabs` (V1.1) · `au-pagination` (V1.1) · `au-assistant-panel` (V1.1, IA) · `au-source-citation` (V1.1) · `au-diff-card` (V1.1, `AIC-005`)

> **Sobre "Feed":** não existe componente de feed social — a decisão de matar o feed é anterior ([Revisão CPO §B](CPO_REVIEW_ICONNECT.md)). O Mural é uma lista de `au-card`, não um componente próprio.
>
> **Sobre "Dashboards":** o V1.0 não tem painel de BI (`OPS-010` é V2). O que existe é `au-widget-grid`. `au-kpi-tile` e `au-sparkline` entram no V1.1.

---

## 6.12 Especificação dos componentes

### Os 8 estados — contrato obrigatório

Todo componente interativo entrega os oito. Componente sem os oito não entra na biblioteca.

```
default · hover · focus-visible · active · disabled · loading · error · empty
```

```css
.au-focusable:focus-visible {
  outline: none;
  box-shadow: var(--au-focus);       /* anel duplo: funciona sobre qualquer fundo */
}
```

`focus-visible`, nunca `focus` — quem usa mouse não deve ver anel; quem usa teclado sempre deve.

---

### 6.12.1 Botões

| Variante | Uso | Aparência |
|---|---|---|
| `primary` | Uma por tela | Fundo `--au-brand-700`, texto branco |
| `secondary` | Ação alternativa | Fundo `--au-surface`, borda `--au-border-strong` |
| `ghost` | Ação terciária, dentro de card | Sem fundo, texto `--au-text-muted` |
| `danger` | Destrutiva | Texto `--au-danger-text`, borda `--au-danger` |

| Tamanho | Altura | Padding | Fonte |
|---|:-:|:-:|:-:|
| `sm` | 28px | 8/12px | `--au-t-sm` |
| `md` | 34px | 8/16px | `--au-t-base` |
| `lg` | 40px | 10/20px | `--au-t-md` |

```html
<button class="au-btn au-btn--primary au-btn--md"
        hx-post="{% url 'workspace:apr_aprovar' s.pk %}"
        hx-target="#apr-{{ s.pk }}" hx-swap="outerHTML"
        hx-indicator="#spin-{{ s.pk }}">
  <svg class="au-icon"><use href="#check"></use></svg>
  Aprovar
  <span id="spin-{{ s.pk }}" class="au-spinner htmx-indicator"></span>
</button>
```

```css
.au-btn {
  display:inline-flex; align-items:center; gap:var(--au-2);
  border-radius:var(--au-r-md); font-weight:500; white-space:nowrap;
  transition:background var(--au-dur-fast) var(--au-ease),
             box-shadow var(--au-dur-fast) var(--au-ease);
}
.au-btn:disabled { opacity:.5; cursor:not-allowed; }
.au-btn.htmx-request { pointer-events:none; }         /* loading vem do HTMX */
```

> **O estado `loading` é do HTMX, não de JavaScript próprio.** `htmx-request` é adicionado automaticamente durante a requisição — é a forma mais barata e confiável de garantir que ninguém clique duas vezes.

---

### 6.12.2 Card e Widget

`au-card` é a superfície genérica. `au-widget` é um card com **contrato de estados** ([Etapa 5 §5.8](EXEC_05_ARQUITETURA.md)).

```
┌─ au-widget ────────────────────────────────┐
│ ┌─ header ─────────────────────────────┐   │  título + contador + ação
│ │ Aprovações            6      [ver →] │   │  padding 16px, borda inferior
│ └──────────────────────────────────────┘   │
│ ┌─ body ───────────────────────────────┐   │  conteúdo · scroll interno
│ │                                      │   │  max-height quando necessário
│ └──────────────────────────────────────┘   │
│ ┌─ footer (opcional) ──────────────────┐   │  ação em lote
│ └──────────────────────────────────────┘   │
└────────────────────────────────────────────┘
```

```css
.au-card {
  background:var(--au-surface); border:1px solid var(--au-border);
  border-radius:var(--au-r-md); box-shadow:var(--au-e-1);
}
.au-widget { display:flex; flex-direction:column; overflow:hidden; }
.au-widget__header {
  display:flex; align-items:center; gap:var(--au-2);
  padding:var(--au-3) var(--au-card-pad);
  border-bottom:1px solid var(--au-border);
  font-size:var(--au-t-md); font-weight:600;
}
.au-widget__body  { padding:var(--au-card-pad); flex:1; overflow-y:auto; }
```

**Os quatro estados do widget:**

| Estado | Renderização |
|---|---|
| `carregando` | `au-skeleton` com a forma do conteúdo real |
| `com dados` | Conteúdo |
| `vazio` | `au-empty` com mensagem específica + próxima ação |
| `erro` | `au-inline-alert` variante `danger` + `[Tentar de novo]` (HTTP 200) |

---

### 6.12.3 Formulários

`au-field` é o invólucro que carrega rótulo, dica, erro e obrigatoriedade — o controle nunca aparece sozinho.

```html
<div class="au-field" :class="{'au-field--error': erro}">
  <label class="au-field__label" for="justificativa">
    Justificativa <span class="au-field__req" aria-hidden="true">*</span>
  </label>
  <textarea id="justificativa" class="au-input" rows="3"
            aria-describedby="hint-just erro-just" required></textarea>
  <p id="hint-just" class="au-field__hint">Explique por que o equipamento é necessário.</p>
  <p id="erro-just" class="au-field__error" role="alert">{{ erro }}</p>
</div>
```

| Regra | Detalhe |
|---|---|
| Rótulo **sempre visível** | Placeholder como rótulo desaparece ao digitar e quebra acessibilidade |
| Erro **abaixo** do campo, com `role="alert"` | Leitor de tela anuncia sem precisar de foco |
| Obrigatoriedade por `*` **e** `required` | Visual e semântica |
| Erro nunca só por cor | Ícone + texto, para daltonismo |
| Campo espelho (`IDN`) | Somente leitura, com ícone e origem: *"mantido pelo RH"* |

**Campos suportados no `au-form-dinamico`** — tipos fechados, sem condicional no V1.0:

```
texto · textarea · numero · data · selecao · anexo
```

---

### 6.12.4 Tabela e lista

| Componente | Quando |
|---|---|
| `au-table` | Dado tabular comparável, ≥3 colunas — relatório de leitura, bandeja completa |
| `au-list-row` | Item com hierarquia própria — aprovação, pendência, escala |

```css
.au-table th {
  position:sticky; top:0; z-index:1;
  background:var(--au-surface-sunken);
  font-size:var(--au-t-xs); font-weight:600; text-transform:uppercase;
  letter-spacing:.04em; color:var(--au-text-muted);
  height:var(--au-row-h); text-align:left; padding:0 var(--au-3);
}
.au-table td { height:var(--au-row-h); padding:0 var(--au-3);
               border-top:1px solid var(--au-border); }
.au-table tbody tr:hover { background:var(--au-surface-sunken); }
.au-table .au-num { text-align:right; font-variant-numeric:tabular-nums; }
```

**Sem virtualização no V1.0.** O maior conjunto previsto é o relatório de confirmação de leitura (≤400 linhas), que o navegador renderiza sem esforço. Virtualizar seria complexidade sem problema.

---

### 6.12.5 Estados vazios

Estado vazio em branco é defeito. Todo `au-empty` responde três coisas: **o que é**, **por que está vazio**, **o que fazer agora**.

```html
<div class="au-empty">
  <svg class="au-icon au-icon--lg au-empty__icon"><use href="#inbox"></use></svg>
  <p class="au-empty__title">Nenhuma aprovação pendente</p>
  <p class="au-empty__desc">Tudo que precisava de você já foi decidido.</p>
</div>
```

| Contexto | Título | Descrição / ação |
|---|---|---|
| Aprovações | Nenhuma aprovação pendente | Tudo que precisava de você já foi decidido |
| Meu dia | Nada pendente para hoje | [Abrir uma solicitação] |
| Busca | Nada encontrado para "xyz" | Tente uma pessoa, um documento ou [abra uma solicitação] |
| Biblioteca | Nenhum documento neste filtro | [Limpar filtros] |
| Escala | Escala ainda não publicada | Fale com o gestor da unidade |

---

### 6.12.6 Command Bar

O único componente com uso pesado de Alpine — e por isso o que exige a distribuição CSP ([ADR-002](EXEC_05_ARQUITETURA.md)).

```
┌─────────────────────────────────────────────────────┐
│  🔍  ana prado                                  esc │  56px, glass
├─────────────────────────────────────────────────────┤
│  AÇÕES                                              │  rótulo 10px uppercase
│  ▸ Solicitar férias                            ↵    │
│  PESSOAS                                            │
│  ▸ Ana Prado · Gestora de Operação · SP             │
│  ▸ Ana Lima  · Analista Financeiro · RJ             │
└─────────────────────────────────────────────────────┘
```

| Tecla | Ação |
|---|---|
| `⌘K` / `Ctrl+K` | Abre |
| `Esc` | Fecha |
| `↑` `↓` | Navega |
| `↵` | Abre o selecionado |
| `⌘↵` | Abre em nova aba |

Posicionamento: 20% do topo, largura 640px, `--au-e-3`, `au-glass`, foco preso dentro do overlay.

---

### 6.12.7 Badge, avatar, alerta

```css
.au-badge {
  display:inline-flex; align-items:center; gap:var(--au-1);
  height:20px; padding:0 var(--au-2); border-radius:var(--au-r-full);
  font-size:var(--au-t-2xs); font-weight:600;
  text-transform:uppercase; letter-spacing:.03em;
}
.au-badge--success { background:var(--au-success-bg); color:var(--au-success-text); }
.au-badge--danger  { background:var(--au-danger-bg);  color:var(--au-danger-text);  }
```

> **É aqui que o par fill/text se paga.** O fundo usa a cor de preenchimento a 10% e o texto usa a variante escura — o badge fica legível em vez de decorativo. Com uma cor só, `background: cyan` + `color: cyan` seria ilegível, e `color: cyan` sobre branco daria 2,43:1.

**Contador do topo** — `au-badge--counter`, números tabulares, `aria-live="polite"` para que o leitor de tela anuncie mudança sem interromper.

**Avatar** — iniciais quando não há foto, cor derivada do hash do nome (12 tons pré-validados em contraste), `--au-r-full`, tamanhos 24/32/40px.

---

## 6.13 Composições por módulo

Não são componentes novos — são arranjos dos 26. Ficam no módulo, não na biblioteca.

| Composição | Módulo | Feita de |
|---|:-:|---|
| `apr-card` | APR | card + badge + avatar + button × 3 |
| `apr-lote-bar` | APR | panel + button + badge |
| `svc-form-dinamico` | SVC | field + input + select + file-drop |
| `svc-catalogo-grid` | SVC | widget-grid + card + icon |
| `cnt-doc-viewer` | CNT | card + breadcrumb + badge + button |
| `com-critico` | COM | modal em tela cheia, sem fechar |
| `com-progresso` | COM | card + table + badge |
| `ops-plantao-agora` | OPS | widget + list-row + avatar + button |
| `src-resultados` | SRC | command-bar + list-row + badge |
| `wks-launcher` | WKS | widget-grid + card + icon |
| `ppl-perfil` | PPL | field + input + badge (campo espelho) |

---

## 6.14 Responsividade

### Alvo declarado

| Faixa | Suporte no V1.0 |
|---|---|
| **≥1280px** | **Primário.** Layout completo de 3 colunas |
| 1024–1279 | Primário. 2 colunas |
| 640–1023 | Suportado. Coluna única, sidebar em drawer |
| <640 | **Funciona, não é otimizado** |

> **Por que assumir isso:** o técnico de campo não usa o Workspace no V1.0 ([D-05](EXEC_01_ESCOPO_E_DEPENDENCIAS.md)) — ele usa o app nativo. As personas do V1.0 (Marina, Rogério, Cláudia, Paulo, Sandra) trabalham em desktop, com uso ocasional em tablet. Otimizar para celular seria investir onde não há usuário. **A página não pode quebrar abaixo de 640px, mas também não recebe design dedicado.**

### Comportamento por faixa

| Elemento | ≥1280 | 1024–1279 | 640–1023 | <640 |
|---|---|---|---|---|
| Sidebar | Fixa 236px | Colapsada 60px | Drawer | Drawer |
| Topbar | Completa | Completa | Busca vira ícone | Só logo + busca + avatar |
| Zonas | 3 colunas | 2 colunas | 1 coluna | 1 coluna |
| Tabela | Completa | Completa | Scroll horizontal | Vira lista de cards |
| Modal | Centralizado 640px | 640px | 90% da largura | Sheet inferior |
| ⌘K | Overlay 640px | 640px | 90% | Tela cheia |

**Regra estrutural:** conteúdo largo (tabela, código) rola dentro do próprio contêiner com `overflow-x:auto`. **O `body` nunca rola na horizontal.**

---

## 6.15 Acessibilidade

**Alvo: WCAG 2.1 AA.**

| # | Requisito | Como se verifica |
|:-:|---|---|
| A1 | Contraste ≥4,5:1 em texto normal, ≥3:1 em texto grande e em contorno de controle | Script de validação no CI, sobre os tokens |
| A2 | Toda ação alcançável por teclado, com ordem de tabulação correta | Percurso manual por tela |
| A3 | `focus-visible` sempre visível, com anel duplo | Visual |
| A4 | Todo controle tem nome acessível (`label`, `aria-label`) | axe-core no CI |
| A5 | Ícone decorativo com `aria-hidden="true"` | Revisão |
| A6 | Erro anunciado por `role="alert"` | Leitor de tela |
| A7 | Contador dinâmico com `aria-live="polite"` | Leitor de tela |
| A8 | Foco preso dentro de modal e ⌘K, devolvido ao fechar | Manual |
| A9 | `prefers-reduced-motion` respeitado | Manual |
| A10 | Informação nunca só por cor | Revisão |
| A11 | Página funciona com zoom de 200% | Manual |

### O teste automatizável que vale a pena

```python
# workspace/tests/test_tokens_contraste.py
PARES_OBRIGATORIOS = [
    ("--au-text",         "--au-surface", 4.5),
    ("--au-text-muted",   "--au-surface", 4.5),
    ("--au-accent-text",  "--au-surface", 4.5),
    ("--au-success-text", "--au-surface", 4.5),
    ("--au-warning-text", "--au-surface", 4.5),
    ("--au-danger-text",  "--au-surface", 4.5),
]
# Roda em claro e escuro. Token que regride reprova o PR.
```

> **Este teste é o que impede o defeito de `a { color: #06b6d4 }` de se repetir.** Contraste vira parte da definição de pronto, não item de checklist que se esquece.

---

## 6.16 Anti-padrões

Cada linha vem de um erro que este projeto já cometeu ou que a base atual carrega.

| ❌ Não fazer | ✅ Fazer | Origem |
|---|---|---|
| `color: #06b6d4` em texto | `var(--au-accent-text)` | Defeito real, §6.0 |
| Fonte de ícone | Sprite SVG | Bug do commit `b77a0b6` |
| `w-[137px]`, `mt-[13px]` | Escala de 4px | Princípio 1 |
| Cor definida só no bloco escuro | Definir no claro, redefinir no escuro | DM1 |
| Glass em card de conteúdo | Só nos 3 lugares permitidos | §6.5 |
| Estado vazio em branco | `au-empty` com próxima ação | §6.12.5 |
| Widget sem `min-height` | Altura reservada | CLS = 0 |
| Erro sinalizado só por cor | Ícone + texto | A10 |
| `:focus` | `:focus-visible` | §6.12 |
| Sombra mais forte no escuro | Superfície mais clara | §6.5 |
| Placeholder como rótulo | `label` sempre visível | §6.12.3 |
| Componente "para o futuro" | Só com uso real | PLT R6 |
| Classe Tailwind fora de `workspace/` | Reprova o PR | A-02 |
| Contador sem números tabulares | `.au-num` | §6.3 |

---

## 6.17 Governança

### Como um componente entra na biblioteca

```
1. Precisa em ≥3 lugares?         não → fica no módulo como composição
2. Existe algo parecido?          sim → estender, não criar
3. Entrega os 8 estados?          não → não entra
4. Passa nos pares de contraste?  não → não entra
5. Só tokens, nenhum literal?     não → não entra
6. Documentado com exemplo?       não → não entra
                                  ✅ → entra
```

### Onde vive

```
workspace/static/workspace/src/
  tokens.css          fonte da verdade — só variáveis
  components.css      as 26 classes au-*
  aurora.css          entrada: @import tailwindcss + tokens + components

workspace/templates/workspace/_components/
  _button.html  _card.html  _widget.html  _field.html  _empty.html …
  → inclusão via {% include %}, sem lógica dentro
```

### Versionamento

O DS versiona junto com a aplicação — não é pacote separado. Mudança de token que altere aparência exige registro no `CHANGELOG.md` com antes e depois.

### Critérios de aceite da Etapa 6

| # | Critério |
|:-:|---|
| C1 | Todos os pares de contraste passam AA, em claro e escuro, verificado no CI |
| C2 | Os 26 componentes existem com os 8 estados |
| C3 | Nenhum literal de cor, espaço ou raio nos templates do `workspace` |
| C4 | Build do Tailwind não lê nenhum arquivo fora de `workspace/` |
| C5 | Dark mode sem nenhuma cor definida apenas em media query |
| C6 | CLS = 0 na home, medido |
| C7 | Percurso completo por teclado em todas as telas do V1.0 |
| C8 | axe-core sem violação crítica |

---

## Próxima etapa

**Etapa 7 — Backlog completo.** Épico → Feature → Story → Task → Subtask, com critérios de aceite, prioridade, estimativa e dependências, a partir dos 24 épicos e 149 features da [Etapa 4](EXEC_04_PRD.md).

**Aguarda aprovação da Etapa 6.**

---

*Etapa 6 de 9 · 26 componentes · paleta validada em WCAG AA · 1 defeito de produção encontrado e corrigido no desenho.*
