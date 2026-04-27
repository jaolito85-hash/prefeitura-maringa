/**
 * App.jsx - Dashboard de Seguranca Publica - Maringa.
 */
import { useEffect, useState } from 'react'
import { apiGet } from './services/api'
import Central from './pages/Central'
import Denuncias from './pages/Denuncias'
import SOSMulher from './pages/SOSMulher'
import Ocorrencias from './pages/Ocorrencias'
import Recompensas from './pages/Recompensas'
import MapaPresentacao from './pages/MapaPresentacao'
import AudioManager from './components/AudioManager'

const ABAS_COMPLETAS = [
  { id: 'central', icon: '📊', label: 'CENTRAL' },
  { id: 'denuncias', icon: '📋', label: 'DENÚNCIAS' },
  { id: 'sos', icon: '🛡️', label: 'SOS MULHER' },
  { id: 'ocorrencias', icon: '🌳', label: 'OCORRÊNCIAS' },
  { id: 'recompensas', icon: '💰', label: 'RECOMPENSAS' },
]

const ABAS_APRESENTACAO = [
  { id: 'mapa', icon: '🗺️', label: 'MAPA' },
  { id: 'denuncias', icon: '📋', label: 'DENÚNCIAS' },
  { id: 'recompensas', icon: '💰', label: 'RECOMPENSAS' },
]

export default function App() {
  const [modoApresentacao, setModoApresentacao] = useState(
    () => localStorage.getItem('modoApresentacao') === '1',
  )
  const ABAS = modoApresentacao ? ABAS_APRESENTACAO : ABAS_COMPLETAS

  const [abaAtiva, setAbaAtiva] = useState(() => (
    localStorage.getItem('modoApresentacao') === '1' ? 'mapa' : 'central'
  ))
  const [mutado, setMutado] = useState(false)

  // Garante que a aba ativa sempre exista no conjunto atual de abas
  useEffect(() => {
    if (!ABAS.some((a) => a.id === abaAtiva)) {
      setAbaAtiva(ABAS[0].id)
    }
  }, [modoApresentacao])

  const alternarApresentacao = () => {
    const novo = !modoApresentacao
    setModoApresentacao(novo)
    localStorage.setItem('modoApresentacao', novo ? '1' : '0')
  }
  const [sosAtivos, setSosAtivos] = useState(0)
  const [ultimoSOS, setUltimoSOS] = useState(null)
  const [hora, setHora] = useState(new Date())

  // ── Busca por protocolo ──
  const [buscaProtocolo, setBuscaProtocolo] = useState('')
  const [resultadoBusca, setResultadoBusca] = useState(null)
  const [buscando, setBuscando] = useState(false)
  const [erroBusca, setErroBusca] = useState(null)
  const [mostrarResultado, setMostrarResultado] = useState(false)

  const buscarProtocolo = async () => {
    const termo = buscaProtocolo.trim().toUpperCase()
    if (!termo) return

    setBuscando(true)
    setErroBusca(null)
    setResultadoBusca(null)
    setMostrarResultado(true)

    try {
      const data = await apiGet(`/api/protocolo/${encodeURIComponent(termo)}`)
      setResultadoBusca(data)
    } catch (error) {
      setErroBusca(error.message?.includes('404')
        ? `Protocolo ${termo} não encontrado.`
        : error.message?.includes('400')
        ? 'Formato inválido. Use MGA-2026-XXXXX.'
        : 'Erro ao buscar. Tente novamente.')
    } finally {
      setBuscando(false)
    }
  }

  useEffect(() => {
    const timer = setInterval(() => setHora(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const buscarSOS = async () => {
      try {
        const data = await apiGet('/api/sos/alertas/ativos')
        setSosAtivos(data?.length || 0)
        setUltimoSOS(data?.[0] || null)
      } catch (error) {
        console.error('Falha ao carregar alertas SOS:', error)
        setSosAtivos(0)
        setUltimoSOS(null)
      }
    }

    buscarSOS()
    const interval = setInterval(buscarSOS, 10000)
    return () => clearInterval(interval)
  }, [])

  const formatarHora = (date) =>
    date.toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })

  const formatarData = (date) =>
    date.toLocaleDateString('pt-BR', {
      weekday: 'long',
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    })

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-white overflow-hidden">
      <AudioManager sosAtivos={sosAtivos} mutado={mutado} abaAtiva={abaAtiva} />

      <header className="flex items-center justify-between px-6 py-3 bg-gray-900 border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center gap-4">
          <div className="text-2xl font-black text-blue-400 tracking-tight">NODE DATA</div>
          <div className="text-gray-400 text-sm">|</div>
          <div className="text-white font-semibold">Central de Segurança Pública - Maringá-PR</div>
        </div>

        <div className="flex items-center gap-6">
          {/* Barra de busca por protocolo */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <input
                type="text"
                placeholder="Buscar protocolo (MGA-2026-...)"
                value={buscaProtocolo}
                onChange={(e) => setBuscaProtocolo(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && buscarProtocolo()}
                className="w-64 px-3 py-1.5 pl-8 bg-gray-800 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 text-sm">🔍</span>
            </div>
            <button
              onClick={buscarProtocolo}
              disabled={buscando || !buscaProtocolo.trim()}
              className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {buscando ? '...' : 'Buscar'}
            </button>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
            <span className="text-green-400">Online</span>
          </div>

          <div className="text-right">
            <div className="text-2xl font-mono font-bold text-white tabular-nums">{formatarHora(hora)}</div>
            <div className="text-xs text-gray-400 capitalize">{formatarData(hora)}</div>
          </div>

          <button
            onClick={alternarApresentacao}
            className={`px-3 py-2 rounded-lg text-sm font-semibold transition-all ${
              modoApresentacao
                ? 'bg-purple-600 text-white hover:bg-purple-500 shadow-lg shadow-purple-900/40'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            title={modoApresentacao ? 'Sair do modo apresentação' : 'Ativar modo apresentação'}
          >
            🎬 {modoApresentacao ? 'Apresentação ON' : 'Apresentação'}
          </button>

          <button
            onClick={() => setMutado(!mutado)}
            className={`px-3 py-2 rounded-lg text-lg transition-all ${
              mutado ? 'bg-gray-700 text-gray-400 hover:bg-gray-600' : 'bg-blue-600 text-white hover:bg-blue-500'
            }`}
            title={mutado ? 'Ativar sons' : 'Mutar sons'}
          >
            {mutado ? '🔇' : '🔊'}
          </button>
        </div>
      </header>

      {!modoApresentacao && sosAtivos > 0 && ultimoSOS && (
        <div
          className="flex items-center justify-between px-6 py-3 bg-red-600 animate-pulse cursor-pointer flex-shrink-0"
          onClick={() => setAbaAtiva('sos')}
        >
          <div className="flex items-center gap-3">
            <span className="text-2xl">🚨</span>
            <div>
              <span className="font-black text-lg">ALERTA SOS MULHER ATIVO</span>
              {ultimoSOS.sos_cadastros?.nome && <span className="ml-3 font-semibold">{ultimoSOS.sos_cadastros.nome}</span>}
              {ultimoSOS.sos_cadastros?.endereco && (
                <span className="ml-2 text-red-100">- {ultimoSOS.sos_cadastros.endereco}</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-red-100 text-sm">CLIQUE PARA VER DETALHES</span>
            <span className="text-white font-bold bg-red-800 px-3 py-1 rounded">
              {sosAtivos} ativo{sosAtivos > 1 ? 's' : ''}
            </span>
          </div>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <nav className="flex flex-col gap-1 p-3 bg-gray-900 border-r border-gray-700 w-52 flex-shrink-0">
          {ABAS.map((aba) => (
            <button
              key={aba.id}
              onClick={() => setAbaAtiva(aba.id)}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-all font-semibold ${
                abaAtiva === aba.id ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              } ${aba.id === 'sos' && sosAtivos > 0 ? 'ring-2 ring-red-500' : ''}`}
            >
              <span className="text-xl">{aba.icon}</span>
              <span className="text-sm tracking-wide">{aba.label}</span>
              {aba.id === 'sos' && sosAtivos > 0 && (
                <span className="ml-auto bg-red-500 text-white text-xs font-black px-2 py-0.5 rounded-full animate-pulse">
                  {sosAtivos}
                </span>
              )}
            </button>
          ))}

          <div className="mt-auto pt-4 border-t border-gray-700">
            <p className="text-xs text-gray-500 mb-2 px-1">WhatsApp</p>
            {['Denúncias', 'SOS', 'Ocorrências'].map((inst) => (
              <div key={inst} className="flex items-center gap-2 px-1 py-1">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span>
                <span className="text-xs text-gray-400">{inst}</span>
              </div>
            ))}
          </div>
        </nav>

        <main className="flex-1 overflow-hidden">
          {abaAtiva === 'central' && <Central sosAtivos={sosAtivos} />}
          {abaAtiva === 'mapa' && <MapaPresentacao />}
          {abaAtiva === 'denuncias' && <Denuncias />}
          {abaAtiva === 'sos' && <SOSMulher />}
          {abaAtiva === 'ocorrencias' && <Ocorrencias />}
          {abaAtiva === 'recompensas' && <Recompensas />}
        </main>
      </div>

      {/* ═══ Modal resultado da busca por protocolo ═══ */}
      {mostrarResultado && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setMostrarResultado(false)}>
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-lg mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-white">Resultado da Busca</h2>
              <button onClick={() => setMostrarResultado(false)} className="text-gray-400 hover:text-white text-xl">&times;</button>
            </div>

            {buscando && (
              <div className="text-center py-8 text-gray-400">
                <div className="animate-spin text-3xl mb-2">🔍</div>
                <p>Buscando protocolo...</p>
              </div>
            )}

            {erroBusca && (
              <div className="bg-red-900/30 border border-red-800 rounded-lg p-4 text-center">
                <p className="text-red-300">{erroBusca}</p>
              </div>
            )}

            {resultadoBusca && (
              <div>
                {/* Badge do canal */}
                <div className="flex items-center gap-3 mb-4">
                  <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${
                    resultadoBusca.canal === 'denuncia' ? 'bg-yellow-600 text-white' :
                    resultadoBusca.canal === 'ocorrencia' ? 'bg-orange-600 text-white' :
                    resultadoBusca.canal === 'feedback' ? 'bg-blue-600 text-white' :
                    resultadoBusca.canal === 'sos' ? 'bg-red-600 text-white' :
                    'bg-gray-600 text-white'
                  }`}>
                    {resultadoBusca.canal === 'denuncia' ? '📋 Denúncia' :
                     resultadoBusca.canal === 'ocorrencia' ? '🚨 Ocorrência' :
                     resultadoBusca.canal === 'feedback' ? '💬 Feedback' :
                     resultadoBusca.canal === 'sos' ? '🆘 SOS' :
                     resultadoBusca.canal}
                  </span>
                  <span className="text-gray-400 text-sm font-mono">{resultadoBusca.protocolo}</span>
                </div>

                {/* Dados do registro */}
                <div className="space-y-2 text-sm">
                  {resultadoBusca.dados?.status && (
                    <div className="flex justify-between py-2 border-b border-gray-800">
                      <span className="text-gray-400">Status</span>
                      <span className={`font-semibold ${
                        resultadoBusca.dados.status === 'resolvido' || resultadoBusca.dados.status === 'resolved' ? 'text-green-400' :
                        resultadoBusca.dados.status === 'active' ? 'text-red-400' :
                        resultadoBusca.dados.status === 'novo' ? 'text-blue-400' :
                        'text-yellow-400'
                      }`}>
                        {resultadoBusca.dados.status.replace('_', ' ').toUpperCase()}
                      </span>
                    </div>
                  )}
                  {resultadoBusca.dados?.categoria && (
                    <div className="flex justify-between py-2 border-b border-gray-800">
                      <span className="text-gray-400">Categoria</span>
                      <span className="text-white">{resultadoBusca.dados.categoria.replace('_', ' ')}</span>
                    </div>
                  )}
                  {resultadoBusca.dados?.nome && (
                    <div className="flex justify-between py-2 border-b border-gray-800">
                      <span className="text-gray-400">Cidadão</span>
                      <span className="text-white">{resultadoBusca.dados.nome}</span>
                    </div>
                  )}
                  {resultadoBusca.dados?.bairro && (
                    <div className="flex justify-between py-2 border-b border-gray-800">
                      <span className="text-gray-400">Bairro</span>
                      <span className="text-white">{resultadoBusca.dados.bairro}</span>
                    </div>
                  )}
                  {resultadoBusca.dados?.endereco && (
                    <div className="flex justify-between py-2 border-b border-gray-800">
                      <span className="text-gray-400">Endereço</span>
                      <span className="text-white">{resultadoBusca.dados.endereco}</span>
                    </div>
                  )}
                  {resultadoBusca.dados?.mensagem && (
                    <div className="py-2 border-b border-gray-800">
                      <span className="text-gray-400 block mb-1">Mensagem</span>
                      <span className="text-white text-xs leading-relaxed">{resultadoBusca.dados.mensagem}</span>
                    </div>
                  )}
                  {resultadoBusca.dados?.cidadania_ativa && (
                    <div className="flex justify-between py-2 border-b border-gray-800">
                      <span className="text-gray-400">Cidadão Ativo</span>
                      <span className="text-green-400 font-semibold">SIM - Elegível a recompensa</span>
                    </div>
                  )}
                  {resultadoBusca.dados?.created_at && (
                    <div className="flex justify-between py-2">
                      <span className="text-gray-400">Data</span>
                      <span className="text-white">{new Date(resultadoBusca.dados.created_at).toLocaleString('pt-BR')}</span>
                    </div>
                  )}
                </div>

                {/* Botão para ir à aba correspondente */}
                <button
                  onClick={() => {
                    const abaMap = { denuncia: 'denuncias', ocorrencia: 'ocorrencias', feedback: 'central', sos: 'sos' }
                    setAbaAtiva(abaMap[resultadoBusca.canal] || 'central')
                    setMostrarResultado(false)
                  }}
                  className="w-full mt-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-semibold transition-all"
                >
                  Ir para aba {
                    resultadoBusca.canal === 'denuncia' ? 'Denúncias' :
                    resultadoBusca.canal === 'ocorrencia' ? 'Ocorrências' :
                    resultadoBusca.canal === 'feedback' ? 'Central' :
                    resultadoBusca.canal === 'sos' ? 'SOS Mulher' :
                    'Central'
                  }
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
