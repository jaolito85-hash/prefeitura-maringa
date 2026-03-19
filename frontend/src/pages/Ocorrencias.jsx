/**
 * Ocorrencias.jsx - Aba Ocorrencias.
 */
import { useEffect, useState } from 'react'
import { apiGet } from '../services/api'
import CityMap from '../components/Map/CityMap'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'

const SEVERIDADE_INFO = {
  baixa: { label: 'Baixa', cor: 'bg-yellow-900 text-yellow-300 border-yellow-700', dot: 'bg-yellow-400' },
  media: { label: 'Média', cor: 'bg-orange-900 text-orange-300 border-orange-700', dot: 'bg-orange-400' },
  alta: { label: 'Alta', cor: 'bg-red-900 text-red-300 border-red-700', dot: 'bg-red-400' },
  critica: { label: 'Crítica', cor: 'bg-red-900 text-red-200 border-red-600', dot: 'bg-red-500 animate-pulse' },
}

const CATEGORIA_INFO = {
  queda_arvore: { emoji: '🌳', label: 'Queda de Árvore' },
  enchente: { emoji: '🌊', label: 'Enchente/Alagamento' },
  buraco: { emoji: '🕳️', label: 'Buraco na Via' },
  poste: { emoji: '💡', label: 'Poste/Iluminação' },
  incendio: { emoji: '🔥', label: 'Incêndio' },
  vendaval: { emoji: '🌪️', label: 'Vendaval' },
  acidente: { emoji: '🚗', label: 'Acidente' },
  deslizamento: { emoji: '⛰️', label: 'Deslizamento' },
}

const STATUS_INFO = {
  aberto: { label: 'Aberto', cor: 'text-yellow-400' },
  equipe_caminho: { label: 'Equipe a caminho', cor: 'text-blue-400' },
  em_atendimento: { label: 'Em Atendimento', cor: 'text-orange-400' },
  resolvido: { label: 'Resolvido', cor: 'text-green-400' },
}

export default function Ocorrencias() {
  const [ocorrencias, setOcorrencias] = useState([])
  const [selecionada, setSelecionada] = useState(null)
  const [relatos, setRelatos] = useState([])
  const [filtroStatus, setFiltroStatus] = useState('aberto,equipe_caminho,em_atendimento')

  const carregar = async () => {
    try {
      const data = await apiGet('/api/ocorrencias/')
      setOcorrencias((data || []).filter((o) => !filtroStatus || filtroStatus.includes(o.status)))
    } catch (error) {
      console.error('Falha ao carregar ocorrências:', error)
      setOcorrencias([])
    }
  }

  const carregarRelatos = async (ocorrenciaId) => {
    try {
      const data = await apiGet(`/api/ocorrencias/${ocorrenciaId}/relatos`)
      setRelatos(data || [])
    } catch (error) {
      console.error('Falha ao carregar relatos:', error)
      setRelatos([])
    }
  }

  useEffect(() => {
    carregar()
  }, [filtroStatus])

  useEffect(() => {
    if (selecionada) carregarRelatos(selecionada.id)
  }, [selecionada])

  useEffect(() => {
    const interval = setInterval(carregar, 10000)
    return () => clearInterval(interval)
  }, [filtroStatus])

  const tempoRelativo = (d) => formatDistanceToNow(new Date(d), { addSuffix: true, locale: ptBR })

  return (
    <div className="flex h-full">
      <div className="w-96 flex flex-col bg-gray-900 border-r border-gray-700 flex-shrink-0">
        <div className="p-4 border-b border-gray-700 flex-shrink-0">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-white font-bold text-lg">Ocorrências</h2>
            <span className="text-gray-400 text-sm">{ocorrencias.length} ativas</span>
          </div>
          <select
            value={filtroStatus}
            onChange={(e) => setFiltroStatus(e.target.value)}
            className="w-full bg-gray-800 text-white border border-gray-600 rounded-lg px-3 py-2 text-sm"
          >
            <option value="aberto,equipe_caminho,em_atendimento">Ativas</option>
            <option value="resolvido">Resolvidas</option>
            <option value="">Todas</option>
          </select>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {ocorrencias.map((o) => {
            const cat = CATEGORIA_INFO[o.categoria] || { emoji: '📌', label: o.categoria }
            const sev = SEVERIDADE_INFO[o.severidade] || SEVERIDADE_INFO.baixa
            const sta = STATUS_INFO[o.status] || { label: o.status, cor: 'text-gray-400' }
            const protocolosEvitados = o.total_relatos - 1

            return (
              <div
                key={o.id}
                onClick={() => setSelecionada(o)}
                className={`rounded-2xl p-4 cursor-pointer border transition-all ${
                  selecionada?.id === o.id ? 'border-blue-500 bg-gray-700' : 'border-gray-700 bg-gray-800 hover:border-gray-600'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">{cat.emoji}</span>
                    <div>
                      <p className="text-white font-bold text-sm">{cat.label}</p>
                      <p className="text-gray-400 text-xs">{o.bairro}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className={`w-2 h-2 rounded-full ${sev.dot}`}></div>
                    <span className={`text-xs font-bold border rounded-lg px-2 py-0.5 ${sev.cor}`}>{sev.label}</span>
                  </div>
                </div>

                <div className="flex justify-between items-center">
                  <span className={`text-xs font-bold ${sta.cor}`}>{sta.label}</span>
                  <span className="text-gray-500 text-xs">{tempoRelativo(o.created_at)}</span>
                </div>

                {protocolosEvitados > 0 && (
                  <div className="mt-2 bg-emerald-900 border border-emerald-700 rounded-lg px-3 py-1.5 text-xs">
                    <span className="text-emerald-300 font-bold">👥 {o.total_relatos} cidadãos reportaram</span>
                    <span className="text-emerald-400 ml-1">
                      - {protocolosEvitados} protocolo{protocolosEvitados > 1 ? 's' : ''} evitado{protocolosEvitados > 1 ? 's' : ''}
                    </span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 min-h-0">
          <CityMap ocorrencias={ocorrencias} />
        </div>

        {selecionada && (
          <div className="h-56 bg-gray-800 border-t border-gray-700 p-4 overflow-y-auto flex-shrink-0">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="text-white font-bold text-lg">{selecionada.titulo}</h3>
                <span className="text-gray-400 font-mono text-xs">{selecionada.protocolo}</span>
              </div>
              <button onClick={() => setSelecionada(null)} className="text-gray-500 hover:text-white">
                ✕
              </button>
            </div>

            <div className="mb-3 bg-emerald-900 border border-emerald-700 rounded-xl px-4 py-2 inline-block">
              <span className="text-emerald-300 font-bold">{selecionada.total_relatos} cidadãos reportaram esta ocorrência</span>
              {selecionada.total_relatos > 1 && (
                <span className="text-emerald-400 ml-2">
                  - {selecionada.total_relatos - 1} protocolo{selecionada.total_relatos - 1 > 1 ? 's' : ''} duplicado{selecionada.total_relatos - 1 > 1 ? 's' : ''} evitado{selecionada.total_relatos - 1 > 1 ? 's' : ''}!
                </span>
              )}
            </div>

            <div className="space-y-2">
              {relatos.map((r, i) => (
                <div key={r.id} className="flex gap-3 items-start text-sm">
                  <span className="text-gray-500 text-xs w-4 flex-shrink-0">{i + 1}.</span>
                  <span className="text-gray-300">{r.mensagem}</span>
                  <span className="text-gray-500 text-xs flex-shrink-0 ml-auto">{tempoRelativo(r.created_at)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
