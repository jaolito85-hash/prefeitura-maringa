/**
 * CityMap.jsx — Mapa de Maringá com marcadores de ocorrências
 * Usa Leaflet + CartoDB Dark Matter (tema escuro, gratuito, sem API key)
 *
 * DICA: É neste arquivo que você pode trocar o estilo do mapa depois.
 * CartoDB Dark é o nosso padrão. Outros disponíveis:
 * - CartoDB Positron (tema claro)
 * - OpenStreetMap (padrão colorido)
 */
import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Centro de Maringá (coordenadas do centro da cidade)
const MARINGA_CENTER = [-23.4205, -51.9333]
const ZOOM_INICIAL = 13

// Cores por severidade
const COR_SEVERIDADE = {
  baixa:   '#facc15',  // amarelo
  media:   '#f97316',  // laranja
  alta:    '#ef4444',  // vermelho
  critica: '#dc2626',  // vermelho escuro
}

// Tamanho por severidade (marcador maior = mais grave)
const TAMANHO_SEVERIDADE = {
  baixa:   20,
  media:   26,
  alta:    32,
  critica: 38,
}

// Emojis por categoria
const EMOJI_CATEGORIA = {
  queda_arvore: '🌳',
  enchente:     '🌊',
  buraco:       '🕳️',
  poste:        '💡',
  incendio:     '🔥',
  vendaval:     '🌪️',
  acidente:     '🚗',
  deslizamento: '⛰️',
  pichacao:     '🖊️',
  trafico:      '💊',
  sos_mulher:   '🛡️',
}

function criarIcone(categoria, severidade) {
  const emoji = EMOJI_CATEGORIA[categoria] || '📌'
  const cor = COR_SEVERIDADE[severidade] || '#facc15'
  const tamanho = TAMANHO_SEVERIDADE[severidade] || 24
  const isPulsante = severidade === 'critica' || severidade === 'alta'

  return L.divIcon({
    html: `
      <div style="
        width: ${tamanho}px;
        height: ${tamanho}px;
        background: ${cor};
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: ${tamanho * 0.55}px;
        border: 2px solid rgba(255,255,255,0.4);
        box-shadow: 0 0 ${isPulsante ? '12px 4px' : '6px 2px'} ${cor};
        ${isPulsante ? 'animation: pulse-map 1.5s infinite;' : ''}
      ">
        ${emoji}
      </div>
    `,
    className: '',
    iconSize: [tamanho, tamanho],
    iconAnchor: [tamanho / 2, tamanho / 2],
  })
}

export default function CityMap({ ocorrencias = [] }) {
  const mapRef = useRef(null)
  const mapaInstanciaRef = useRef(null)
  const marcadoresRef = useRef([])

  // Inicializa o mapa uma única vez
  useEffect(() => {
    if (mapaInstanciaRef.current) return

    // Cria o mapa centrado em Maringá
    mapaInstanciaRef.current = L.map(mapRef.current, {
      center: MARINGA_CENTER,
      zoom: ZOOM_INICIAL,
      zoomControl: true,
    })

    // Adiciona o tile layer CartoDB Dark Matter (gratuito, sem API key)
    L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      {
        attribution: '© OpenStreetMap contributors © CARTO',
        subdomains: 'abcd',
        maxZoom: 19,
      }
    ).addTo(mapaInstanciaRef.current)

    // Adiciona CSS para animação pulsante
    const style = document.createElement('style')
    style.textContent = `
      @keyframes pulse-map {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.2); opacity: 0.8; }
      }
    `
    document.head.appendChild(style)

    return () => {
      mapaInstanciaRef.current?.remove()
      mapaInstanciaRef.current = null
    }
  }, [])

  // Atualiza os marcadores quando as ocorrências mudam
  useEffect(() => {
    if (!mapaInstanciaRef.current) return

    // Remove marcadores antigos
    marcadoresRef.current.forEach(m => m.remove())
    marcadoresRef.current = []

    // Adiciona novos marcadores
    ocorrencias.forEach(ocorr => {
      if (!ocorr.latitude || !ocorr.longitude) return

      const icone = criarIcone(ocorr.categoria, ocorr.severidade)
      const marker = L.marker([ocorr.latitude, ocorr.longitude], { icon: icone })
        .addTo(mapaInstanciaRef.current)

      // Popup com informações ao clicar
      marker.bindPopup(`
        <div style="background:#1e293b; color:#fff; padding:12px; border-radius:8px; min-width:200px; font-family:sans-serif">
          <div style="font-size:18px; margin-bottom:6px">
            ${EMOJI_CATEGORIA[ocorr.categoria] || '📌'} ${ocorr.titulo || ocorr.categoria}
          </div>
          <div style="color:#94a3b8; font-size:12px; margin-bottom:4px">
            📍 ${ocorr.bairro || 'Bairro não informado'}
          </div>
          <div style="font-size:12px; color:#fbbf24">
            ${ocorr.total_relatos} relato${ocorr.total_relatos > 1 ? 's' : ''}
            ${ocorr.total_relatos > 1 ? ` — ${ocorr.total_relatos - 1} protocolo${ocorr.total_relatos - 1 > 1 ? 's' : ''} evitado${ocorr.total_relatos - 1 > 1 ? 's' : ''}` : ''}
          </div>
          <div style="font-size:11px; color:#64748b; margin-top:4px">
            ${ocorr.protocolo}
          </div>
        </div>
      `, {
        className: 'dark-popup',
      })

      marcadoresRef.current.push(marker)
    })
  }, [ocorrencias])

  return (
    <div className="w-full h-full relative">
      <div ref={mapRef} className="w-full h-full" />
      {/* Legenda do mapa */}
      <div className="absolute bottom-4 left-4 z-[1000] bg-gray-900 bg-opacity-90 rounded-xl p-3 text-xs">
        <div className="text-gray-400 font-bold mb-2 uppercase tracking-wide">Severidade</div>
        {[
          { label: 'Baixa',    cor: '#facc15' },
          { label: 'Média',    cor: '#f97316' },
          { label: 'Alta',     cor: '#ef4444' },
          { label: 'Crítica',  cor: '#dc2626' },
        ].map(({ label, cor }) => (
          <div key={label} className="flex items-center gap-2 mb-1">
            <div className="w-3 h-3 rounded-full" style={{ background: cor, boxShadow: `0 0 6px ${cor}` }} />
            <span className="text-gray-300">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
