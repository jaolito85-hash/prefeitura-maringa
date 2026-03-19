/**
 * Denuncias.jsx - Aba Denuncias.
 */
import { useEffect, useState } from 'react'
import { apiGet } from '../services/api'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'

const CATEGORIA_INFO = {
  pichacao: { emoji: '🖊️', label: 'Pichação', cor: 'bg-pink-900 text-pink-300 border-pink-700' },
  trafico: { emoji: '💊', label: 'Tráfico', cor: 'bg-red-900 text-red-300 border-red-700' },
  lixo: { emoji: '🗑️', label: 'Lixo', cor: 'bg-gray-700 text-gray-300 border-gray-600' },
  vandalismo: { emoji: '🔨', label: 'Vandalismo', cor: 'bg-orange-900 text-orange-300 border-orange-700' },
  depredacao: { emoji: '🏚️', label: 'Depredação', cor: 'bg-red-950 text-red-400 border-red-800' },
}

const STATUS_INFO = {
  novo: { label: 'Novo', cor: 'bg-blue-900 text-blue-300' },
  em_analise: { label: 'Em Análise', cor: 'bg-yellow-900 text-yellow-300' },
  encaminhado: { label: 'Encaminhado', cor: 'bg-purple-900 text-purple-300' },
  procedente: { label: 'Procedente', cor: 'bg-green-900 text-green-300' },
  improcedente: { label: 'Improcedente', cor: 'bg-gray-700 text-gray-400' },
  recompensa_paga: { label: 'Recompensa Paga', cor: 'bg-emerald-900 text-emerald-300' },
}

export default function Denuncias() {
  const [denuncias, setDenuncias] = useState([])
  const [selecionada, setSelecionada] = useState(null)
  const [filtroCategoria, setFiltroCategoria] = useState('')
  const [filtroStatus, setFiltroStatus] = useState('')

  const carregar = async () => {
    try {
      const data = await apiGet('/api/denuncias/', {
        categoria: filtroCategoria,
        status: filtroStatus,
      })
      setDenuncias(data || [])
    } catch (error) {
      console.error('Falha ao carregar denúncias:', error)
      setDenuncias([])
    }
  }

  useEffect(() => {
    carregar()
  }, [filtroCategoria, filtroStatus])

  useEffect(() => {
    const interval = setInterval(carregar, 10000)
    return () => clearInterval(interval)
  }, [filtroCategoria, filtroStatus])

  const tempoRelativo = (d) => formatDistanceToNow(new Date(d), { addSuffix: true, locale: ptBR })

  return (
    <div className="flex h-full">
      <div className="flex flex-col flex-1 overflow-hidden border-r border-gray-700">
        <div className="flex gap-3 p-4 border-b border-gray-700 bg-gray-900 flex-shrink-0">
          <select
            value={filtroCategoria}
            onChange={(e) => setFiltroCategoria(e.target.value)}
            className="bg-gray-800 text-white border border-gray-600 rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Todas as categorias</option>
            {Object.entries(CATEGORIA_INFO).map(([key, { label }]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <select
            value={filtroStatus}
            onChange={(e) => setFiltroStatus(e.target.value)}
            className="bg-gray-800 text-white border border-gray-600 rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Todos os status</option>
            {Object.entries(STATUS_INFO).map(([key, { label }]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <span className="ml-auto text-gray-400 text-sm flex items-center">
            {denuncias.length} denúncia{denuncias.length !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-4 grid grid-cols-2 gap-4 content-start">
          {denuncias.map((d) => {
            const cat = CATEGORIA_INFO[d.categoria] || {
              emoji: '📌',
              label: d.categoria,
              cor: 'bg-gray-700 text-gray-300 border-gray-600',
            }
            const sta = STATUS_INFO[d.status] || { label: d.status, cor: 'bg-gray-700 text-gray-400' }

            return (
              <div
                key={d.id}
                onClick={() => setSelecionada(d)}
                className={`rounded-2xl p-4 cursor-pointer border transition-all ${
                  selecionada?.id === d.id ? 'border-blue-500 bg-gray-700' : 'border-gray-700 bg-gray-800 hover:border-gray-500'
                }`}
              >
                {d.midia_urls?.[0] && (
                  <img src={d.midia_urls[0]} alt="evidência" className="w-full h-32 object-cover rounded-xl mb-3" />
                )}

                <div className="flex gap-2 mb-2 flex-wrap">
                  <span className={`text-xs font-bold px-2 py-1 rounded-lg border ${cat.cor}`}>
                    {cat.emoji} {cat.label}
                  </span>
                  <span className={`text-xs font-bold px-2 py-1 rounded-lg ${sta.cor}`}>{sta.label}</span>
                  {d.cidadania_ativa && (
                    <span className="text-xs font-bold px-2 py-1 rounded-lg bg-emerald-900 text-emerald-300">💰 Cidadania Ativa</span>
                  )}
                </div>

                <p className="text-gray-200 text-sm line-clamp-2 mb-2">{d.mensagem}</p>

                <div className="flex justify-between text-xs text-gray-500">
                  <span>{d.bairro || 'Bairro não informado'}</span>
                  <span>{tempoRelativo(d.created_at)}</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="w-96 bg-gray-900 overflow-y-auto flex-shrink-0 p-6">
        {selecionada ? (
          <>
            <div className="flex justify-between items-center mb-4">
              <span className="text-gray-400 font-mono text-sm">{selecionada.protocolo}</span>
              <button onClick={() => setSelecionada(null)} className="text-gray-500 hover:text-white">
                ✕
              </button>
            </div>

            {selecionada.midia_urls?.[0] && (
              <img src={selecionada.midia_urls[0]} alt="evidência" className="w-full rounded-xl mb-4" />
            )}

            <p className="text-white mb-4">{selecionada.mensagem}</p>

            <div className="space-y-3 text-sm">
              {selecionada.nome && (
                <div>
                  <span className="text-gray-400">Cidadão:</span> <span className="text-white">{selecionada.nome}</span>
                </div>
              )}
              {selecionada.endereco && (
                <div>
                  <span className="text-gray-400">Endereço:</span> <span className="text-white">{selecionada.endereco}</span>
                </div>
              )}
              <div>
                <span className="text-gray-400">Telefone:</span> <span className="text-white">{selecionada.telefone}</span>
              </div>
              <div>
                <span className="text-gray-400">Cidadania Ativa:</span>{' '}
                <span className="text-white">{selecionada.cidadania_ativa ? '✅ Sim' : '❌ Não'}</span>
              </div>
              <div>
                <span className="text-gray-400">Recebido:</span> <span className="text-white">{tempoRelativo(selecionada.created_at)}</span>
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-5xl mb-4">📋</div>
            <p className="text-gray-400">Clique em uma denúncia para ver os detalhes</p>
          </div>
        )}
      </div>
    </div>
  )
}
