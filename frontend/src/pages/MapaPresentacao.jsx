/**
 * MapaPresentacao.jsx — Aba Mapa para o modo de apresentação.
 *
 * Mostra denúncias plotadas no mapa de Maringá com filtro por categoria
 * via badges no topo. Card lateral direito superior com o total de denúncias.
 */
import { useEffect, useMemo, useState } from 'react'
import { apiGet } from '../services/api'
import CityMap from '../components/Map/CityMap'

const CATEGORIAS = [
  { id: '',           label: 'TODAS',             emoji: '🗂️', cor: 'bg-blue-600 text-white border-blue-400' },
  { id: 'pichacao',   label: 'PICHAÇÃO',          emoji: '🖊️', cor: 'bg-pink-700 text-white border-pink-500' },
  { id: 'trafico',    label: 'TRÁFICO DE DROGAS', emoji: '💊', cor: 'bg-red-700 text-white border-red-500' },
  { id: 'lixo',       label: 'DESCARTE DE LIXO',  emoji: '🗑️', cor: 'bg-gray-700 text-white border-gray-500' },
  { id: 'furto_fios', label: 'FURTO DE FIOS',     emoji: '🔌', cor: 'bg-yellow-700 text-white border-yellow-500' },
  { id: 'depredacao', label: 'DEPREDAÇÃO',        emoji: '🏚️', cor: 'bg-orange-700 text-white border-orange-500' },
]

// Mapeia denúncia para o formato esperado pelo CityMap (que espera objeto de ocorrência).
function denunciaParaMarker(d) {
  return {
    id: d.id,
    protocolo: d.protocolo,
    categoria: d.categoria,
    severidade: 'media',
    titulo: d.mensagem ? d.mensagem.slice(0, 60) : (d.categoria || 'Denúncia'),
    bairro: d.bairro,
    latitude: d.latitude,
    longitude: d.longitude,
    total_relatos: 1,
  }
}

export default function MapaPresentacao() {
  const [categoria, setCategoria] = useState('')
  const [denuncias, setDenuncias] = useState([])

  const carregar = async () => {
    try {
      const data = await apiGet('/api/denuncias/', { categoria })
      setDenuncias(data || [])
    } catch (error) {
      console.error('Falha ao carregar denúncias para o mapa:', error)
      setDenuncias([])
    }
  }

  useEffect(() => {
    carregar()
    const interval = setInterval(carregar, 15000)
    return () => clearInterval(interval)
  }, [categoria])

  const markers = useMemo(
    () => denuncias.filter((d) => d.latitude && d.longitude).map(denunciaParaMarker),
    [denuncias],
  )

  return (
    <div className="relative h-full w-full">
      <CityMap ocorrencias={markers} />

      {/* Barra de badges — topo */}
      <div className="absolute top-4 left-4 right-4 z-[1000] flex flex-wrap gap-2 pointer-events-none">
        <div className="flex flex-wrap gap-2 pointer-events-auto bg-gray-900/85 backdrop-blur rounded-2xl p-2 border border-gray-700 shadow-2xl">
          {CATEGORIAS.map((cat) => {
            const ativa = categoria === cat.id
            return (
              <button
                key={cat.id || 'todas'}
                onClick={() => setCategoria(cat.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl border-2 text-xs font-bold tracking-wide transition-all ${
                  ativa
                    ? `${cat.cor} scale-105 shadow-lg`
                    : 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700 hover:text-white'
                }`}
              >
                <span className="text-base">{cat.emoji}</span>
                <span>{cat.label}</span>
              </button>
            )
          })}
        </div>

        {/* Card de total — canto superior direito */}
        <div className="ml-auto pointer-events-auto bg-gray-900/90 backdrop-blur border-2 border-blue-500 rounded-2xl px-6 py-3 shadow-2xl shadow-blue-900/50 flex items-center gap-4">
          <div className="text-3xl">📋</div>
          <div>
            <div className="text-5xl font-black text-blue-300 tabular-nums leading-none">{denuncias.length}</div>
            <div className="text-xs text-gray-400 font-bold uppercase tracking-widest mt-1">Denúncias</div>
          </div>
        </div>
      </div>
    </div>
  )
}
