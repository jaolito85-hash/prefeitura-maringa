/**
 * Central.jsx - Aba CENTRAL do dashboard.
 */
import { useEffect, useState } from 'react'
import { apiGet } from '../services/api'
import CityMap from '../components/Map/CityMap'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'

const CATEGORIA_INFO = {
  queda_arvore: { emoji: '🌳', cor: 'text-green-400', label: 'Queda de Árvore' },
  enchente: { emoji: '🌊', cor: 'text-blue-400', label: 'Enchente' },
  buraco: { emoji: '🕳️', cor: 'text-yellow-500', label: 'Buraco' },
  poste: { emoji: '💡', cor: 'text-yellow-300', label: 'Poste' },
  incendio: { emoji: '🔥', cor: 'text-orange-500', label: 'Incêndio' },
  vendaval: { emoji: '🌪️', cor: 'text-purple-400', label: 'Vendaval' },
  acidente: { emoji: '🚗', cor: 'text-red-400', label: 'Acidente' },
  pichacao: { emoji: '🖊️', cor: 'text-pink-400', label: 'Pichação' },
  trafico: { emoji: '💊', cor: 'text-red-500', label: 'Tráfico' },
  lixo: { emoji: '🗑️', cor: 'text-gray-400', label: 'Lixo' },
  vandalismo: { emoji: '🔨', cor: 'text-orange-400', label: 'Vandalismo' },
  depredacao: { emoji: '🏚️', cor: 'text-red-300', label: 'Depredação' },
  sos_mulher: { emoji: '🛡️', cor: 'text-red-500', label: 'SOS Mulher' },
}

function KPICard({ icon, value, label, color, pulse }) {
  return (
    <div className={`bg-gray-800 rounded-2xl p-6 border ${pulse ? 'border-red-500 shadow-lg shadow-red-900' : 'border-gray-700'}`}>
      <div className="text-4xl mb-2">{icon}</div>
      <div className={`text-6xl font-black tabular-nums leading-none mb-2 ${color} ${pulse ? 'animate-pulse' : ''}`}>
        {value}
      </div>
      <div className="text-gray-400 text-lg font-medium uppercase tracking-wide">{label}</div>
    </div>
  )
}

export default function Central({ sosAtivos }) {
  const [kpis, setKpis] = useState({
    denuncias_hoje: 0,
    ocorrencias_abertas: 0,
    tempo_medio_resposta: '—',
  })
  const [feed, setFeed] = useState([])
  const [ocorrenciasMap, setOcorrenciasMap] = useState([])

  const carregarDados = async () => {
    try {
      const [kpisData, feedData, mapaData] = await Promise.all([
        apiGet('/api/kpis'),
        apiGet('/api/feed'),
        apiGet('/api/ocorrencias/mapa'),
      ])

      setKpis({
        denuncias_hoje: kpisData?.denuncias_hoje || 0,
        ocorrencias_abertas: kpisData?.ocorrencias_abertas || 0,
        tempo_medio_resposta: kpisData?.tempo_medio_resposta || '—',
      })
      setFeed(feedData || [])
      setOcorrenciasMap(mapaData || [])
    } catch (error) {
      console.error('Falha ao carregar central:', error)
      setKpis({
        denuncias_hoje: 0,
        ocorrencias_abertas: 0,
        tempo_medio_resposta: '—',
      })
      setFeed([])
      setOcorrenciasMap([])
    }
  }

  useEffect(() => {
    carregarDados()
    const interval = setInterval(carregarDados, 10000)
    return () => clearInterval(interval)
  }, [])

  const tempoRelativo = (dateStr) => {
    try {
      return formatDistanceToNow(new Date(dateStr), { addSuffix: true, locale: ptBR })
    } catch {
      return '—'
    }
  }

  return (
    <div className="flex h-full gap-4 p-4 overflow-hidden">
      <div className="flex flex-col gap-4 w-64 flex-shrink-0">
        <KPICard icon="🚨" value={sosAtivos} label="SOS Ativos" color={sosAtivos > 0 ? 'text-red-400' : 'text-gray-300'} pulse={sosAtivos > 0} />
        <KPICard icon="📋" value={kpis.denuncias_hoje} label="Denúncias Hoje" color="text-blue-300" />
        <KPICard icon="🌳" value={kpis.ocorrencias_abertas} label="Ocorrências Abertas" color="text-yellow-300" />
        <KPICard icon="⏱️" value={kpis.tempo_medio_resposta} label="Tempo Médio" color="text-green-300" />
      </div>

      <div className="flex-1 rounded-2xl overflow-hidden border border-gray-700 min-h-0">
        <CityMap ocorrencias={ocorrenciasMap} />
      </div>

      <div className="w-72 flex-shrink-0 flex flex-col gap-3 overflow-y-auto">
        <h2 className="text-gray-400 text-sm font-bold uppercase tracking-widest flex-shrink-0">Feed ao Vivo</h2>
        {feed.map((item) => {
          const info = CATEGORIA_INFO[item.categoria] || { emoji: '📌', cor: 'text-gray-400', label: item.categoria }
          const isSOS = item.tipo === 'sos'

          return (
            <div
              key={item.id}
              className={`rounded-xl p-3 border flex-shrink-0 ${
                isSOS ? 'bg-red-900 border-red-600' : 'bg-gray-800 border-gray-700 hover:border-gray-500'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xl">{info.emoji}</span>
                <span className={`text-xs font-bold uppercase ${info.cor}`}>{info.label}</span>
              </div>
              {item.titulo && <p className="text-sm text-white font-medium mb-1 line-clamp-1">{item.titulo}</p>}
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-xs">{item.bairro}</span>
                <span className="text-gray-500 text-xs">{tempoRelativo(item.created_at)}</span>
              </div>
              {item.total_relatos > 1 && <div className="mt-1 text-xs text-yellow-400">{item.total_relatos} relatos agrupados</div>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
