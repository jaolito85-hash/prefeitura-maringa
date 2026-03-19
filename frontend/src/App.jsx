/**
 * App.jsx - Dashboard de Seguranca Publica - Maringa.
 */
import { useEffect, useState } from 'react'
import { apiGet } from './services/api'
import Central from './pages/Central'
import Denuncias from './pages/Denuncias'
import SOSMulher from './pages/SOSMulher'
import Ocorrencias from './pages/Ocorrencias'
import AudioManager from './components/AudioManager'

const ABAS = [
  { id: 'central', icon: '📊', label: 'CENTRAL' },
  { id: 'denuncias', icon: '📋', label: 'DENÚNCIAS' },
  { id: 'sos', icon: '🛡️', label: 'SOS MULHER' },
  { id: 'ocorrencias', icon: '🌳', label: 'OCORRÊNCIAS' },
]

export default function App() {
  const [abaAtiva, setAbaAtiva] = useState('central')
  const [mutado, setMutado] = useState(false)
  const [sosAtivos, setSosAtivos] = useState(0)
  const [ultimoSOS, setUltimoSOS] = useState(null)
  const [hora, setHora] = useState(new Date())

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
          <div className="flex items-center gap-2 text-sm">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
            <span className="text-green-400">Online</span>
          </div>

          <div className="text-right">
            <div className="text-2xl font-mono font-bold text-white tabular-nums">{formatarHora(hora)}</div>
            <div className="text-xs text-gray-400 capitalize">{formatarData(hora)}</div>
          </div>

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

      {sosAtivos > 0 && ultimoSOS && (
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
          {abaAtiva === 'denuncias' && <Denuncias />}
          {abaAtiva === 'sos' && <SOSMulher />}
          {abaAtiva === 'ocorrencias' && <Ocorrencias />}
        </main>
      </div>
    </div>
  )
}
