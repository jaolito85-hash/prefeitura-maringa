/**
 * SOSMulher.jsx - Aba SOS Mulher.
 */
import { useEffect, useState } from 'react'
import { apiGet, apiPatch } from '../services/api'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'

export default function SOSMulher() {
  const [alertas, setAlertas] = useState([])
  const [alertaSelecionado, setAlertaSelecionado] = useState(null)
  const [carregando, setCarregando] = useState(true)

  const carregarAlertas = async () => {
    try {
      const data = await apiGet('/api/sos/alertas')
      setAlertas(data || [])
      const ativo = (data || []).find((a) => a.status === 'active')
      if (ativo && !alertaSelecionado) setAlertaSelecionado(ativo)
    } catch (error) {
      console.error('Falha ao carregar alertas SOS:', error)
      setAlertas([])
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    carregarAlertas()
    const interval = setInterval(carregarAlertas, 10000)
    return () => clearInterval(interval)
  }, [])

  const alertasAtivos = alertas.filter((a) => a.status === 'active')
  const temAtivo = alertasAtivos.length > 0
  const alerta = alertaSelecionado || alertasAtivos[0]

  const aceitar = async (id) => {
    await apiPatch(`/api/sos/alertas/${id}/aceitar`, { operador: 'Operador' })
    await carregarAlertas()
  }

  const resolver = async (id) => {
    await apiPatch(`/api/sos/alertas/${id}/resolver`, { notas: 'Resolvido pelo dashboard' })
    await carregarAlertas()
  }

  const statusLabel = { active: '🔴 Ativo', attending: '🟡 Em Atendimento', resolved: '✅ Resolvido' }
  const statusCor = { active: 'text-red-400', attending: 'text-yellow-400', resolved: 'text-green-400' }

  if (carregando) {
    return <div className="flex items-center justify-center h-full text-gray-400 text-2xl">Carregando...</div>
  }

  return (
    <div className={`flex h-full transition-colors duration-500 ${temAtivo ? 'bg-red-950' : 'bg-gray-950'}`}>
      <div className="flex-1 p-6 overflow-y-auto">
        {temAtivo ? (
          <div className={`rounded-3xl p-8 border-2 border-red-500 ${alertaSelecionado?.status === 'active' ? 'bg-red-900 animate-pulse' : 'bg-red-950'}`}>
            <div className="text-center mb-8">
              <div className="text-8xl mb-4">🚨</div>
              <h1 className="text-5xl font-black text-white tracking-wide">ALERTA SOS MULHER</h1>
              {alerta && (
                <p className="text-red-300 text-xl mt-2">
                  Recebido {formatDistanceToNow(new Date(alerta.created_at), { addSuffix: true, locale: ptBR })}
                </p>
              )}
            </div>

            {alerta && (
              <>
                <div className="grid grid-cols-2 gap-6 mb-8">
                  <div className="bg-red-950 rounded-2xl p-6">
                    <p className="text-red-400 text-sm font-bold uppercase mb-1">Nome</p>
                    <p className="text-white text-3xl font-black">{alerta.sos_cadastros?.nome || 'Não cadastrada'}</p>
                  </div>
                  <div className="bg-red-950 rounded-2xl p-6">
                    <p className="text-red-400 text-sm font-bold uppercase mb-1">Endereço</p>
                    <p className="text-white text-2xl font-bold">{alerta.sos_cadastros?.endereco || 'Não disponível'}</p>
                    {alerta.sos_cadastros?.referencia && <p className="text-red-300 text-sm mt-1">{alerta.sos_cadastros.referencia}</p>}
                  </div>
                  {alerta.sos_cadastros?.agressor && (
                    <div className="bg-red-950 rounded-2xl p-6">
                      <p className="text-red-400 text-sm font-bold uppercase mb-1">Agressor</p>
                      <p className="text-white text-2xl font-bold">{alerta.sos_cadastros.agressor}</p>
                    </div>
                  )}
                  {alerta.sos_cadastros?.contato_confianca_nome && (
                    <div className="bg-red-950 rounded-2xl p-6">
                      <p className="text-red-400 text-sm font-bold uppercase mb-1">Contato de Confiança</p>
                      <p className="text-white text-2xl font-bold">{alerta.sos_cadastros.contato_confianca_nome}</p>
                      <p className="text-red-300 text-lg">{alerta.sos_cadastros.contato_confianca_telefone}</p>
                    </div>
                  )}
                </div>

                <div className="flex gap-4 flex-wrap">
                  <button className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-black text-2xl py-5 px-8 rounded-2xl transition-all">
                    📞 LIGAR VÍTIMA
                    <br />
                    <span className="text-lg font-normal">{alerta.telefone}</span>
                  </button>
                  <button className="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-black text-2xl py-5 px-8 rounded-2xl transition-all">
                    🚔 ACIONAR PM
                    <br />
                    <span className="text-lg font-normal">190</span>
                  </button>
                  <button className="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-black text-2xl py-5 px-8 rounded-2xl transition-all">
                    🛡️ GUARDA MUNICIPAL
                    <br />
                    <span className="text-lg font-normal">153</span>
                  </button>

                  {alerta.status === 'active' && (
                    <button
                      onClick={() => aceitar(alerta.id)}
                      className="w-full bg-yellow-600 hover:bg-yellow-500 text-white font-black text-2xl py-5 px-8 rounded-2xl transition-all"
                    >
                      ✋ ACEITAR ATENDIMENTO
                    </button>
                  )}
                  {alerta.status === 'attending' && (
                    <button
                      onClick={() => resolver(alerta.id)}
                      className="w-full bg-green-700 hover:bg-green-600 text-white font-black text-2xl py-5 px-8 rounded-2xl transition-all"
                    >
                      ✅ MARCAR COMO RESOLVIDO
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-8xl mb-6">✅</div>
            <h2 className="text-4xl font-black text-green-400 mb-4">Nenhum alerta SOS ativo</h2>
            <p className="text-gray-400 text-xl">O sistema está monitorando os 3 canais</p>
          </div>
        )}
      </div>

      <div className="w-80 bg-gray-900 border-l border-gray-700 p-4 overflow-y-auto flex-shrink-0">
        <h3 className="text-gray-400 text-sm font-bold uppercase tracking-widest mb-4">Histórico de Alertas</h3>
        {alertas.map((a) => (
          <div
            key={a.id}
            onClick={() => setAlertaSelecionado(a)}
            className={`rounded-xl p-4 mb-3 cursor-pointer border transition-all ${
              alertaSelecionado?.id === a.id ? 'border-red-500 bg-red-950' : 'border-gray-700 bg-gray-800 hover:border-gray-500'
            }`}
          >
            <div className="flex justify-between items-start mb-1">
              <span className="text-white font-bold text-sm">{a.sos_cadastros?.nome || 'Não cadastrada'}</span>
              <span className={`text-xs font-bold ${statusCor[a.status]}`}>{statusLabel[a.status]}</span>
            </div>
            <p className="text-gray-400 text-xs">{a.sos_cadastros?.endereco || a.telefone}</p>
            <p className="text-gray-500 text-xs mt-1">
              {formatDistanceToNow(new Date(a.created_at), { addSuffix: true, locale: ptBR })}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
