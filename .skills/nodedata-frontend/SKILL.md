---
name: nodedata-frontend
description: "Skill especializada para construir e modificar o frontend do Node Data — dashboard de segurança pública para a Prefeitura de Maringá. Use SEMPRE que o usuário pedir qualquer mudança visual, novo componente, nova aba, novo modal, novo gráfico, card, tabela, filtro, animação, ou qualquer alteração no frontend/index.html. Também use quando o usuário mostrar um print/screenshot e pedir para reproduzir ou melhorar algo visual. Trigger em: 'painel', 'dashboard', 'aba', 'tela', 'componente', 'card', 'modal', 'gráfico', 'chart', 'layout', 'visual', 'CSS', 'estilo', 'botão', 'filtro', 'tabela', 'responsivo', 'animação', 'index.html', 'frontend', 'React', 'mapa', 'sidebar', 'KPI', 'badge'."
---

# Node Data Frontend — Guia de Desenvolvimento

Este guia contém TUDO que você precisa saber para construir componentes no dashboard Node Data. Siga estas instruções para manter consistência visual e funcional.

## Regra #1: Arquivo Único

O frontend inteiro vive em **`frontend/index.html`**. É um HTML monolítico com React 18 via CDN + Babel standalone. Não existe build step, não existe Webpack, não existe Vite em produção. Toda mudança frontend DEVE ser feita neste arquivo.

Nunca crie arquivos `.jsx`, `.css` ou `.js` separados para produção. Os arquivos em `frontend/src/` existem apenas como referência — o deploy usa `index.html`.

## Arquitetura do Arquivo

```
index.html
├── <head> — CDN imports (React, ReactDOM, Babel, Mapbox)
├── <style> — TODO o CSS (variáveis, classes, animações)
├── <div id="root"> — mount point
└── <script type="text/babel">
    ├── Constantes (API_URL, MAPBOX_TOKEN, BASES, CAT_DEN, CAT_OC, etc.)
    ├── Variáveis globais (OC, DEN, SOS, FBK, KPIS, RECOMP, etc.)
    ├── useApiPolling() — polling a cada 5s
    ├── Utilitários (ago, nearestBase, fetchRoute, googleMapsLink)
    ├── Componentes de gráfico (BarChart, AreaChart, DonutChart)
    ├── AnimatedNumber
    ├── PageTransition
    ├── Componentes de página (Central, Mapa, Ocorrencias, Denuncias, etc.)
    ├── App (navegação por abas)
    └── ReactDOM.createRoot(...)
```

## Tema Visual

### CSS Variables
```css
--bg: #050507          /* fundo principal */
--surface: #0b0c10     /* fundo de painéis/headers */
--card: #111217        /* fundo de cards */
--card-hover: #1c1e26  /* card hover */
--border: #23252e      /* bordas */
--border-light: #2d3039
--accent: #059669      /* verde principal — ações, nav ativo */
--accent-light: #34d399
--blue: #3b82f6        /* secundário */
--text: #ffffff        /* texto principal */
--text-secondary: #d1d5db
--text-muted: #8b949e  /* texto terciário */
--danger: #ef4444
--warn: #f59e0b
--success: #22c55e
--purple: #a855f7
--radius: 12px
```

### Paleta de cores para dados
Use estas cores para gráficos, badges e indicadores visuais:
- Verde: `#4ade80` (sucesso, resolvido)
- Vermelho: `#f87171` (perigo, SOS, crítico)
- Amarelo: `#fbbf24` (aviso, pendente)
- Azul: `#60a5fa` (info, secundário)
- Roxo: `#a78bfa` (categorias especiais)
- Laranja: `#fb923c` (escalado)
- Rosa: `#e879f9` (SOS Mulher)

### Fontes
- **Texto geral:** `Inter` (via Google Fonts CDN)
- **Números/dados:** `IBM Plex Mono` (classe `.mono`)
- Números SEMPRE usam `IBM Plex Mono` para dar peso visual. Use a classe `mono` ou `fontFamily:'IBM Plex Mono'`.
- Formato numérico brasileiro: `toLocaleString('pt-BR')`
- Moeda: `toLocaleString('pt-BR', {minimumFractionDigits: 2})`

## Classes CSS Reutilizáveis

### Cards e Containers
- `.card` — card básico (background, border, radius)
- `.chart-card` — card para gráficos (flex column, padding 20px)
- `.chart-title` — título de seção (11px, uppercase, letter-spacing, muted)
- `.kpi` — card KPI grande (padding 20px, borderLeft colorido)
- `.stat-box` — stat compacto (text-align center)
- `.stat-num` — número grande mono
- `.stat-lbl` — label pequeno uppercase

### Badges
```
.badge — base (inline-flex, padding 4px 10px, border-radius 6px)
.b-blue   — rgba(59,130,246,.12) + cor #60a5fa
.b-red    — rgba(239,68,68,.12) + cor #fca5a5
.b-warn   — rgba(245,158,11,.12) + cor #fcd34d
.b-green  — rgba(34,197,94,.12) + cor #4ade80
.b-purple — rgba(168,85,247,.12) + cor #c4b5fd
.b-gray   — rgba(139,148,158,.12) + cor #8b949e
```

### Botões
- `.btn` — base (inline-flex, gap 6px, padding 8px 16px)
- `.btn-primary` — fundo verde accent
- `.btn-outline` — transparente + borda
- `.btn-danger` — fundo vermelho

### Layout
- `.scrollable` — overflow-y auto (use no container que precisa de scroll)
- `.tab-bar` / `.tab` / `.tab.active` — barra de abas com indicador inferior
- `.modal-overlay` / `.modal-box` — sistema de modais

## Componentes de Gráfico

Os 3 componentes SVG disponíveis:

### BarChart
```jsx
<BarChart data={[{label:'Jan',vendas:10,metas:8}]} keys={['vendas','metas']} colors={['#4ade80','#fbbf24']} height={240}/>
```
- `data`: array de objetos com `label` + campos numéricos
- `keys`: quais campos plotar
- `colors`: cor de cada série
- `height`: altura (default 220)

### AreaChart
```jsx
<AreaChart data={[{label:'Jan',val:10}]} keys={['val']} colors={['#3b82f6']} height={240}/>
```
- Mesma API do BarChart, mas com linhas + preenchimento gradiente

### DonutChart
```jsx
<DonutChart data={[{v:18,c:'#3b82f6',n:'Categoria A'},{v:9,c:'#fbbf24',n:'Categoria B'}]} size={160}/>
```
- `data`: array com `v` (valor), `c` (cor), `n` (nome)
- `size`: diâmetro em pixels

### Legenda de gráfico
```jsx
<div className="chart-legend">
  <div className="chart-legend-item">
    <div style={{width:10,height:10,borderRadius:3,background:'#3b82f6'}}/>
    Nome da série
  </div>
</div>
```

## Padrões de UI Obrigatórios

### Modal
```jsx
{modalAberto&&(
  <div className="modal-overlay" onClick={()=>setModalAberto(null)}>
    <div className="modal-box" onClick={e=>e.stopPropagation()} style={{maxWidth:600}}>
      {/* Header */}
      <div style={{padding:'18px 22px',borderBottom:'1px solid var(--border)'}}>
        <div style={{fontSize:16,fontWeight:700,color:'#fff'}}>Título</div>
      </div>
      {/* Body — SEMPRE com scrollable */}
      <div className="scrollable" style={{flex:1,padding:'20px 22px',minHeight:0}}>
        {/* conteúdo */}
      </div>
      {/* Footer (opcional) */}
      <div style={{padding:'14px 22px',borderTop:'1px solid var(--border)',display:'flex',gap:10}}>
        <button className="btn btn-outline" onClick={()=>setModalAberto(null)}>Cancelar</button>
        <button className="btn btn-primary">Confirmar</button>
      </div>
    </div>
  </div>
)}
```
Regras: overlay com `onClick` fecha o modal, `stopPropagation` no box, body com `scrollable` + `minHeight:0`, botão `✕` no header.

### IIFE para Lógica Complexa
Quando precisa de variáveis intermediárias dentro de JSX condicional:
```jsx
{condicao&&(()=>{
  const calc = algumCalculo();
  const formatted = format(calc);
  return(
    <div>
      {formatted}
    </div>
  );
})()}
```
Isso evita poluir o escopo do componente. Use sempre que tiver mais de 2-3 linhas de lógica antes do return.

### KPI Card
```jsx
<div className="kpi anim-card" style={{borderLeft:`3px solid ${cor}`}}>
  <div className="kpi-top">
    <span className="kpi-label">{label}</span>
    <div className="kpi-icon" style={{background:`${cor}15`,color:cor}}>{icon}</div>
  </div>
  <div className="kpi-value"><AnimatedNumber value={valor}/></div>
  {sub&&<div className="kpi-sub">{sub}</div>}
</div>
```

### Stat Card Inline (estilo Relatórios)
```jsx
<div style={{background:'var(--card)',border:'1px solid var(--border)',borderRadius:14,padding:'22px 20px',position:'relative',overflow:'hidden'}}>
  <div style={{position:'absolute',top:0,left:0,right:0,height:3,background:cor,opacity:.6}}/>
  <div className="mono" style={{fontSize:32,fontWeight:700,color:cor,lineHeight:1}}>{numero}</div>
  <div style={{fontSize:12,fontWeight:600,color:'var(--text-muted)',marginTop:8,textTransform:'uppercase',letterSpacing:'.5px'}}>{label}</div>
</div>
```

### Barra Horizontal de Progresso
```jsx
<div style={{marginBottom:10}}>
  <div style={{display:'flex',justifyContent:'space-between',marginBottom:5}}>
    <span style={{fontSize:12,color:'var(--text)',fontWeight:500}}>{label}</span>
    <span className="mono" style={{fontSize:12,fontWeight:600,color}}>{valor}</span>
  </div>
  <div style={{height:6,borderRadius:3,background:'rgba(255,255,255,.04)'}}>
    <div style={{height:'100%',borderRadius:3,background:cor,width:`${percentual}%`,transition:'width .6s ease',opacity:.85}}/>
  </div>
</div>
```

## Dados Globais Disponíveis

Todas as variáveis abaixo são atualizadas a cada 5 segundos pelo polling:

| Variável | Conteúdo |
|----------|----------|
| `OC` | Ocorrências (com lat/lng) |
| `DEN` | Denúncias (com lat/lng) |
| `SOS` | Alertas SOS ativos |
| `SOS_HIST` | Histórico SOS resolvidos |
| `FBK` | Feedbacks |
| `KPIS` | KPIs do dashboard |
| `RECOMP` | Recompensas |
| `RECOMP_KPIS` | KPIs financeiros |
| `RECOMP_CFG` | Config de recompensas |
| `REL_DATA` | Dados consolidados do relatório |
| `BASES` | Bases operacionais (GCM, SAMU, Bombeiros, PM) |

### Lookup Objects
- `CAT_DEN` — categorias de denúncia `{label, icon, badge, valor}`
- `CAT_OC` — categorias de ocorrência `{label, icon, c}`
- `SEV` — severidade `{label, c, dot}`
- `S_OC` — status ocorrência `{label, badge}`
- `S_DEN` — status denúncia `{label, badge}`
- `S_RECOMP` — status recompensa `{label, badge}`
- `CAT_FBK` — categorias feedback `{label, emoji, color}`

### Utilitários
- `ago(date)` — formata tempo relativo ("agora", "5min", "2h", "3d")
- `nearestBase(lat, lng, tipo)` — acha base mais próxima
- `fetchRoute(fromLng, fromLat, toLng, toLat)` — rota Mapbox
- `googleMapsLink(fromLat, fromLng, toLat, toLng)` — link Google Maps

## Animações

### Classes de animação
- `.anim-card` — fadeSlideUp com delay escalonado (cada nth-child adiciona .05s)
- `.anim-fade` — fadeIn simples
- `.anim-scale` — scaleIn (bom para modais/popovers)
- `.anim-bar` — growBar (barras de gráfico crescem de baixo)
- `.anim-line` — drawLine (linhas de gráfico se desenham)
- `.anim-dot` — scaleIn (pontos de gráfico)

### AnimatedNumber
```jsx
<AnimatedNumber value={1234} prefix="R$ " duration={1200}/>
```
Conta de 0 até o valor target. Use para KPIs e números de destaque.

## Mapbox Integration

- Token: `MAPBOX_TOKEN` (constante global)
- Style: `mapbox://styles/mapbox/dark-v11`
- Centro de Maringá: `[-51.9375, -23.4205]`
- Zoom padrão: 13, pitch: 45
- Heatmap layer disponível com toggle
- Markers coloridos por severidade/categoria

## Checklist Antes de Entregar

1. Todo código vai no `frontend/index.html` — NUNCA em arquivo separado
2. Variáveis de estado com `useState` — React Hooks apenas
3. Números usam `.mono` ou `fontFamily:'IBM Plex Mono'`
4. Formato brasileiro (pt-BR) para datas e valores
5. Cores do tema — nunca hardcodar cinzas, usar `var(--text-muted)` etc.
6. Modal usa `modal-overlay` + `modal-box` + `stopPropagation`
7. Scroll interno usa classe `scrollable`
8. Cards animados usam `anim-card`
9. Labels pequenos: `fontSize:10-11px`, `textTransform:'uppercase'`, `letterSpacing:'.5px'`
10. Backgrounds sutis: `rgba(255,255,255,.02)` a `.04` — nunca opaco

## Anti-Patterns — NÃO Faça Isso

- Não usar `localStorage` ou `sessionStorage`
- Não importar bibliotecas externas sem perguntar (temos React, Mapbox, Babel — só)
- Não criar arquivos separados (.jsx, .css, .js)
- Não usar CSS-in-JS libraries (styled-components, emotion)
- Não usar class components — apenas function components com hooks
- Não expor dados sensíveis (cpf_encrypted, dados_bancarios_encrypted)
- Não colocar estilos inline que já existem como classe CSS
- Não esquecer `key` em `.map()` — React reclama
