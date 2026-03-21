/**
 * Feedbacks.jsx — Central de mensagens dos cidadãos via WhatsApp.
 * Design: command-center escuro com cards grandes e categoria-coded colors.
 */
import { useEffect, useState, useCallback } from 'react'
import { apiGet, apiPatch } from '../services/api'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'

// ─── Configurações visuais por categoria ─────────────────────────────────────

const CATEGORIA = {
  infraestrutura_obras: {
    label: 'Infraestrutura & Obras',
    emoji: '🏗️',
    badge: 'bg-amber-500/20 text-amber-300 border border-amber-500/40',
    accent: 'border-l-amber-500',
    dot: 'bg-amber-400',
    glow: 'shadow-amber-900/40',
  },
  seguranca_publica: {
    label: 'Segurança Pública',
    emoji: '🛡️',
    badge: 'bg-red-500/20 text-red-300 border border-red-500/40',
    accent: 'border-l-red-500',
    dot: 'bg-red-400',
    glow: 'shadow-red-900/40',
  },
  limpeza_urbana: {
    label: 'Limpeza Urbana',
    emoji: '♻️',
    badge: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40',
    accent: 'border-l-emerald-500',
    dot: 'bg-emerald-400',
    glow: 'shadow-emerald-900/40',
  },
  educacao_escolas: {
    label: 'Educação & Escolas',
    emoji: '📚',
    badge: 'bg-blue-500/20 text-blue-300 border border-blue-500/40',
    accent: 'border-l-blue-500',
    dot: 'bg-blue-400',
    glow: 'shadow-blue-900/40',
  },
  saude_atendimento: {
    label: 'Saúde & Atendimento',
    emoji: '🏥',
    badge: 'bg-violet-500/20 text-violet-300 border border-violet-500/40',
    accent: 'border-l-violet-500',
    dot: 'bg-violet-400',
    glow: 'shadow-violet-900/40',
  },
  transporte: {
    label: 'Transporte',
    emoji: '🚌',
    badge: 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40',
    accent: 'border-l-cyan-500',
    dot: 'bg-cyan-400',
    glow: 'shadow-cyan-900/40',
  },
}

const PRIORIDADE = {
  critico: {
    label: 'Crítico',
    badge: 'bg-red-600 text-white',
    pulse: true,
  },
  urgente: {
    label: 'Urgente',
    badge: 'bg-orange-500/90 text-white',
    pulse: false,
  },
  normal: {
    label: 'Normal',
    badge: 'bg-gray-600 text-gray-200',
    pulse: false,
  },
  baixa: {
    label: 'Baixa',
    badge: 'bg-gray-700 text-gray-400',
    pulse: false,
  },
}

const STATUS_OPTS = {
  aberto: { label: 'Aberto', cor: 'text-yellow-400', bg: 'bg-yellow-500/10 border border-yellow-500/30' },
  em_atendimento: { label: 'Em Atendimento', cor: 'text-blue-400', bg: 'bg-blue-500/10 border border-blue-500/30' },
  encaminhado: { label: 'Encaminhado', cor: 'text-purple-400', bg: 'bg-purple-500/10 border border-purple-500/30' },
  resolvido: { label: 'Resolvido', cor: 'text-emerald-400', bg: 'bg-emerald-500/10 border border-emerald-500/30' },
}

// ─── Dados mock para preview sem backend ─────────────────────────────────────

const MOCK_FEEDBACKS = [
  {
    id: '1', protocolo: 'FBK-001', telefone: '44999991111', nome: 'João Silva',
    mensagem: 'Oi, gostaria de fazer uma reclamação da minha rua. Muito buraco, já tem uns 90 dias que tem um buraco a céu aberto na Rua das Flores perto do número 340.',
    categoria: 'infraestrutura_obras', prioridade: 'critico', status: 'aberto',
    endereco: 'Rua das Flores, 340', bairro: 'Zona 5', created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: '2', protocolo: 'FBK-002', telefone: '44999992222', nome: 'Maria Santos',
    mensagem: 'Prefeito, precisa melhorar urgente a segurança pública aqui em Ivaté, pelo amor de Deus, não tem viatura, não tem policiamento de jeito nenhum.',
    categoria: 'seguranca_publica', prioridade: 'urgente', status: 'aberto',
    endereco: null, bairro: 'Ivaté', created_at: new Date(Date.now() - 5400000).toISOString(),
  },
  {
    id: '3', protocolo: 'FBK-003', telefone: '44999993333', nome: 'Carlos Oliveira',
    mensagem: 'Eu gostaria de saber quando que o caminhão do lixo da limpeza aí da cidade vai passar aqui na minha rua e retirar o entulho que ficou depois da reforma.',
    categoria: 'limpeza_urbana', prioridade: 'urgente', status: 'em_atendimento',
    endereco: null, bairro: 'Zona 3', created_at: new Date(Date.now() - 6600000).toISOString(),
  },
  {
    id: '4', protocolo: 'FBK-004', telefone: '44999994444', nome: 'Ana Lima',
    mensagem: 'Na creche minha filha está reclamando da professora Sílvia que está batendo nas crianças. Isso é um absurdo! Preciso de uma resposta urgente da prefeitura.',
    categoria: 'educacao_escolas', prioridade: 'critico', status: 'aberto',
    endereco: null, bairro: 'Jardim Alvorada', created_at: new Date(Date.now() - 7800000).toISOString(),
  },
  {
    id: '5', protocolo: 'FBK-005', telefone: '44999995555', nome: 'Pedro Rocha',
    mensagem: 'Boa tarde, eu tô aqui pra reclamar que minha rua tá cheia de buraco. Já tem uns 90 dias que tem um buraco a céu aberto.',
    categoria: 'infraestrutura_obras', prioridade: 'urgente', status: 'aberto',
    endereco: 'Av. Brasil, 1200', bairro: 'Centro', created_at: new Date(Date.now() - 9000000).toISOString(),
  },
  {
    id: '6', protocolo: 'FBK-006', telefone: '44999996666', nome: 'Lucia Fernandes',
    mensagem: 'Aqui no hospital o médico é muito ruim e não dá atenção. A fila não anda, não tem equipe médica para atender a população. Minha sobrinha está aguardando a dois dias na fila do hospital regional.',
    categoria: 'saude_atendimento', prioridade: 'critico', status: 'aberto',
    endereco: null, bairro: 'Zona Sul', created_at: new Date(Date.now() - 10200000).toISOString(),
  },
  {
    id: '7', protocolo: 'FBK-007', telefone: '44999997777', nome: 'Roberto Alves',
    mensagem: 'meu filho tá reclamando que não tem merenda a 15 dias na escola dele. Absurdo isso! Escola Municipal João XXIII na zona leste.',
    categoria: 'educacao_escolas', prioridade: 'urgente', status: 'encaminhado',
    endereco: null, bairro: 'Zona Leste', created_at: new Date(Date.now() - 14400000).toISOString(),
  },
  {
    id: '8', protocolo: 'FBK-008', telefone: '44999998888', nome: 'Fernanda Costa',
    mensagem: 'Não aguento mais o mato alto no terreno baldio da esquina. Cobra já apareceu duas vezes esse mês. Precisamos de limpeza urgente.',
    categoria: 'limpeza_urbana', prioridade: 'urgente', status: 'aberto',
    endereco: 'Rua Osvaldo Cruz', bairro: 'Bela Vista', created_at: new Date(Date.now() - 18000000).toISOString(),
  },
]

const MOCK_MENSAGENS = {
  '1': [
    { id: 'm1', de: 'cidadao', mensagem: 'Oi, gostaria de fazer uma reclamação da minha rua. Muito buraco!', created_at: new Date(Date.now() - 3700000).toISOString() },
    { id: 'm2', de: 'ia', mensagem: '📋 Olá! Recebi sua reclamação sobre infraestrutura viária. Pode me informar o endereço exato do problema?', created_at: new Date(Date.now() - 3650000).toISOString() },
    { id: 'm3', de: 'cidadao', mensagem: 'Rua das Flores, 340 - perto da padaria do Zé. Já tem 90 dias esse buraco!', created_at: new Date(Date.now() - 3600000).toISOString() },
    { id: 'm4', de: 'ia', mensagem: '✅ Registrado! Protocolo FBK-001. Sua reclamação foi categorizada como Infraestrutura & Obras com prioridade CRÍTICA. Equipe de vistoria será acionada.', created_at: new Date(Date.now() - 3580000).toISOString() },
  ],
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function Feedbacks() {
  const [feedbacks, setFeedbacks] = useState([])
  const [selecionado, setSelecionado] = useState(null)
  const [mensagens, setMensagens] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [usandoMock, setUsandoMock] = useState(false)

  const [filtroCategoria, setFiltroCategoria] = useState('')
  const [filtroPrioridade, setFiltroPrioridade] = useState('')
  const [filtroStatus, setFiltroStatus] = useState('aberto,em_atendimento,encaminhado')

  const t = (d) => formatDistanceToNow(new Date(d), { addSuffix: true, locale: ptBR })

  const carregar = useCallback(async () => {
    try {
      const params = {}
      if (filtroCategoria) params.categoria = filtroCategoria
      if (filtroPrioridade) params.prioridade = filtroPrioridade
      if (filtroStatus && filtroStatus !== 'todos') params.status = filtroStatus

      const data = await apiGet('/api/feedbacks/', params)

      if (!data || data.length === 0) {
        // Sem dados reais → usa mock para preview
        let lista = MOCK_FEEDBACKS
        if (filtroCategoria) lista = lista.filter((f) => f.categoria === filtroCategoria)
        if (filtroPrioridade) lista = lista.filter((f) => f.prioridade === filtroPrioridade)
        if (filtroStatus && filtroStatus !== 'todos') {
          lista = lista.filter((f) => filtroStatus.split(',').includes(f.status))
        }
        setFeedbacks(lista)
        setUsandoMock(true)
      } else {
        setFeedbacks(data)
        setUsandoMock(false)
      }
    } catch {
      // Fallback para mock
      let lista = MOCK_FEEDBACKS
      if (filtroCategoria) lista = lista.filter((f) => f.categoria === filtroCategoria)
      if (filtroPrioridade) lista = lista.filter((f) => f.prioridade === filtroPrioridade)
      if (filtroStatus && filtroStatus !== 'todos') {
        lista = lista.filter((f) => filtroStatus.split(',').includes(f.status))
      }
      setFeedbacks(lista)
      setUsandoMock(true)
    } finally {
      setCarregando(false)
    }
  }, [filtroCategoria, filtroPrioridade, filtroStatus])

  const carregarMensagens = useCallback(async (id) => {
    if (usandoMock) {
      setMensagens(MOCK_MENSAGENS[id] || [])
      return
    }
    try {
      const data = await apiGet(`/api/feedbacks/${id}/mensagens`)
      setMensagens(data || [])
    } catch {
      setMensagens(MOCK_MENSAGENS[id] || [])
    }
  }, [usandoMock])

  useEffect(() => { carregar() }, [carregar])

  useEffect(() => {
    const interval = setInterval(carregar, 15000)
    return () => clearInterval(interval)
  }, [carregar])

  useEffect(() => {
    if (selecionado) carregarMensagens(selecionado.id)
  }, [selecionado, carregarMensagens])

  const atualizarStatus = async (id, novoStatus) => {
    if (!usandoMock) {
      try {
        await apiPatch(`/api/feedbacks/${id}/status`, { status: novoStatus })
      } catch {
        console.error('Falha ao atualizar status')
      }
    }
    setFeedbacks((prev) =>
      prev.map((f) => (f.id === id ? { ...f, status: novoStatus } : f))
    )
    if (selecionado?.id === id) setSelecionado((prev) => ({ ...prev, status: novoStatus }))
  }

  const criticos = feedbacks.filter((f) => f.prioridade === 'critico').length
  const urgentes = feedbacks.filter((f) => f.prioridade === 'urgente').length

  return (
    <div className="flex h-full bg-gray-950 overflow-hidden">

      {/* ── Painel esquerdo: filtros + stats ─────────────────────────── */}
      <aside className="w-56 flex-shrink-0 flex flex-col bg-gray-900/70 border-r border-gray-800 p-4 gap-5">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-3">Filtros</p>

          <div className="space-y-2">
            <select
              value={filtroStatus}
              onChange={(e) => setFiltroStatus(e.target.value)}
              className="w-full bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-blue-500"
            >
              <option value="aberto,em_atendimento,encaminhado">Cards Ativos</option>
              <option value="resolvido">Resolvidos</option>
              <option value="todos">Todos</option>
            </select>

            <select
              value={filtroCategoria}
              onChange={(e) => setFiltroCategoria(e.target.value)}
              className="w-full bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-blue-500"
            >
              <option value="">Todas Categorias</option>
              {Object.entries(CATEGORIA).map(([k, v]) => (
                <option key={k} value={k}>{v.emoji} {v.label}</option>
              ))}
            </select>

            <select
              value={filtroPrioridade}
              onChange={(e) => setFiltroPrioridade(e.target.value)}
              className="w-full bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-blue-500"
            >
              <option value="">Todas Prioridades</option>
              {Object.entries(PRIORIDADE).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Stats */}
        <div className="space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-1">Resumo</p>

          <div className="bg-gray-800/60 rounded-xl p-3 border border-gray-700">
            <p className="text-2xl font-black text-white tabular-nums">{feedbacks.length}</p>
            <p className="text-[11px] text-gray-400">mensagens</p>
          </div>

          {criticos > 0 && (
            <div className="bg-red-950/60 rounded-xl p-3 border border-red-800/60">
              <p className="text-2xl font-black text-red-400 tabular-nums animate-pulse">{criticos}</p>
              <p className="text-[11px] text-red-400">críticos</p>
            </div>
          )}

          {urgentes > 0 && (
            <div className="bg-orange-950/40 rounded-xl p-3 border border-orange-800/40">
              <p className="text-2xl font-black text-orange-400 tabular-nums">{urgentes}</p>
              <p className="text-[11px] text-orange-400">urgentes</p>
            </div>
          )}
        </div>

        {/* Categorias breakdown */}
        <div className="space-y-1 mt-auto">
          <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-2">Por Categoria</p>
          {Object.entries(CATEGORIA).map(([k, v]) => {
            const n = feedbacks.filter((f) => f.categoria === k).length
            if (n === 0) return null
            return (
              <button
                key={k}
                onClick={() => setFiltroCategoria(filtroCategoria === k ? '' : k)}
                className={`w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-xs transition-all ${
                  filtroCategoria === k ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
              >
                <span>{v.emoji} {v.label.split(' ')[0]}</span>
                <span className="font-bold tabular-nums">{n}</span>
              </button>
            )
          })}
        </div>

        {usandoMock && (
          <p className="text-[10px] text-yellow-600 text-center">⚠ dados de demonstração</p>
        )}
      </aside>

      {/* ── Grid principal de cards ───────────────────────────────────── */}
      <div className={`flex-1 overflow-y-auto transition-all ${selecionado ? 'w-0 hidden lg:block lg:w-auto' : ''}`}>
        {/* Header */}
        <div className="sticky top-0 z-10 bg-gray-950/95 backdrop-blur border-b border-gray-800 px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-black text-white tracking-tight">Feedbacks</h1>
            <p className="text-xs text-gray-500">Mensagens dos cidadãos via WhatsApp · IA categoriza e responde</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-xs text-gray-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></span>
              Tempo real
            </span>
            <span className="text-xs font-bold text-gray-300 bg-gray-800 px-3 py-1 rounded-full border border-gray-700">
              {feedbacks.length} mensagem{feedbacks.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        {/* Grid */}
        {carregando ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-gray-500 text-sm">Carregando...</div>
          </div>
        ) : feedbacks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 gap-3">
            <span className="text-5xl opacity-30">💬</span>
            <p className="text-gray-500 text-sm">Nenhum feedback encontrado</p>
          </div>
        ) : (
          <div className="p-5 grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-4 content-start">
            {feedbacks.map((f) => {
              const cat = CATEGORIA[f.categoria] || {
                label: f.categoria || 'N/A', emoji: '📌',
                badge: 'bg-gray-700 text-gray-300 border border-gray-600',
                accent: 'border-l-gray-500', dot: 'bg-gray-400', glow: '',
              }
              const pri = PRIORIDADE[f.prioridade] || PRIORIDADE.normal
              const sta = STATUS_OPTS[f.status] || STATUS_OPTS.aberto
              const isSelected = selecionado?.id === f.id
              const isCritico = f.prioridade === 'critico'

              return (
                <div
                  key={f.id}
                  onClick={() => setSelecionado(isSelected ? null : f)}
                  className={`
                    group relative rounded-2xl cursor-pointer border-l-4 border border-gray-800
                    transition-all duration-200 overflow-hidden
                    ${cat.accent}
                    ${isSelected
                      ? 'bg-gray-800/90 border-gray-600 shadow-lg ' + cat.glow
                      : 'bg-gray-900/80 hover:bg-gray-800/70 hover:border-gray-700 hover:shadow-md hover:' + cat.glow
                    }
                    ${isCritico && !isSelected ? 'ring-1 ring-red-500/30' : ''}
                  `}
                >
                  {/* Topo: categoria + prioridade + tempo */}
                  <div className="flex items-start justify-between px-4 pt-4 pb-2 gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1 rounded-lg ${cat.badge}`}>
                        <span>{cat.emoji}</span>
                        <span className="uppercase tracking-wide">{cat.label}</span>
                      </span>
                      <span className={`inline-flex items-center gap-1 text-[11px] font-black px-2.5 py-1 rounded-lg ${pri.badge} ${pri.pulse ? 'animate-pulse' : ''}`}>
                        {pri.pulse && <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-ping absolute"></span>}
                        ● {pri.label}
                      </span>
                    </div>
                    <span className="text-[11px] text-gray-500 whitespace-nowrap flex-shrink-0 mt-0.5">
                      {t(f.created_at)}
                    </span>
                  </div>

                  {/* Endereço */}
                  {f.endereco || f.bairro ? (
                    <div className="px-4 pb-1">
                      <span className="text-[11px] text-gray-500 flex items-center gap-1">
                        <span>📍</span>
                        <span>{f.endereco || f.bairro}</span>
                      </span>
                    </div>
                  ) : (
                    <div className="px-4 pb-1">
                      <span className="text-[11px] text-gray-600 italic">Sem endereço</span>
                    </div>
                  )}

                  {/* Mensagem */}
                  <div className="px-4 py-3">
                    <p className="text-gray-200 text-sm leading-relaxed line-clamp-3">
                      "{f.mensagem}"
                    </p>
                  </div>

                  {/* Rodapé: status + ações */}
                  <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800/80 gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`text-[11px] font-bold px-2.5 py-1 rounded-lg ${sta.bg} ${sta.cor}`}>
                        {sta.label}
                      </span>
                      {f.protocolo && (
                        <span className="text-[10px] text-gray-600 font-mono">{f.protocolo}</span>
                      )}
                    </div>

                    <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      {/* Mudar status rápido */}
                      <select
                        value={f.status}
                        onChange={(e) => atualizarStatus(f.id, e.target.value)}
                        className="text-[11px] bg-gray-800 text-gray-300 border border-gray-700 rounded-lg px-2 py-1 focus:outline-none focus:border-blue-500 cursor-pointer"
                      >
                        {Object.entries(STATUS_OPTS).map(([k, v]) => (
                          <option key={k} value={k}>{v.label}</option>
                        ))}
                      </select>

                      <button
                        onClick={(e) => { e.stopPropagation(); setSelecionado(f) }}
                        className="text-[11px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-3 py-1 rounded-lg hover:bg-emerald-500/20 transition-colors whitespace-nowrap"
                      >
                        Ver conversa
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Painel de detalhe: conversa WhatsApp ─────────────────────── */}
      {selecionado && (
        <div className="w-full lg:w-[420px] xl:w-[460px] flex-shrink-0 flex flex-col bg-gray-900/90 border-l border-gray-800">
          {/* Header do painel */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800 flex-shrink-0">
            <div className="flex-1 min-w-0">
              {(() => {
                const cat = CATEGORIA[selecionado.categoria] || { emoji: '📌', label: selecionado.categoria }
                const pri = PRIORIDADE[selecionado.prioridade] || PRIORIDADE.normal
                return (
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">{cat.emoji}</span>
                      <span className="text-sm font-bold text-white truncate">{cat.label}</span>
                      <span className={`text-[10px] font-black px-2 py-0.5 rounded ${pri.badge}`}>
                        {pri.label}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-500 font-mono">{selecionado.protocolo}</p>
                  </div>
                )
              })()}
            </div>
            <button
              onClick={() => setSelecionado(null)}
              className="ml-3 w-8 h-8 flex items-center justify-center text-gray-500 hover:text-white hover:bg-gray-800 rounded-lg transition-colors flex-shrink-0"
            >
              ✕
            </button>
          </div>

          {/* Info do cidadão */}
          <div className="px-5 py-3 border-b border-gray-800 bg-gray-800/30 flex-shrink-0">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              {selecionado.nome && (
                <div>
                  <span className="text-gray-500">Cidadão</span>
                  <p className="text-white font-semibold">{selecionado.nome}</p>
                </div>
              )}
              <div>
                <span className="text-gray-500">Telefone</span>
                <p className="text-white font-semibold">{selecionado.telefone || '—'}</p>
              </div>
              {selecionado.endereco && (
                <div className="col-span-2">
                  <span className="text-gray-500">Endereço</span>
                  <p className="text-white font-semibold">{selecionado.endereco}</p>
                </div>
              )}
              {selecionado.bairro && (
                <div>
                  <span className="text-gray-500">Bairro</span>
                  <p className="text-white font-semibold">{selecionado.bairro}</p>
                </div>
              )}
              <div>
                <span className="text-gray-500">Status</span>
                <select
                  value={selecionado.status}
                  onChange={(e) => atualizarStatus(selecionado.id, e.target.value)}
                  className="text-xs bg-gray-800 text-white border border-gray-600 rounded-lg px-2 py-0.5 mt-0.5 focus:outline-none w-full"
                >
                  {Object.entries(STATUS_OPTS).map(([k, v]) => (
                    <option key={k} value={k}>{v.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Thread da conversa */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-600 text-center mb-4">
              Conversa via WhatsApp
            </p>

            {mensagens.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 gap-2">
                <span className="text-3xl opacity-30">💬</span>
                <p className="text-xs text-gray-600">Nenhuma mensagem no histórico</p>
              </div>
            ) : (
              mensagens.map((m) => {
                const deCidadao = m.de === 'cidadao'
                return (
                  <div key={m.id} className={`flex ${deCidadao ? 'justify-start' : 'justify-end'}`}>
                    <div
                      className={`max-w-[82%] rounded-2xl px-4 py-2.5 ${
                        deCidadao
                          ? 'bg-gray-800 border border-gray-700 rounded-tl-sm'
                          : 'bg-blue-600/30 border border-blue-500/40 rounded-tr-sm'
                      }`}
                    >
                      {!deCidadao && (
                        <p className="text-[10px] font-bold text-blue-400 mb-1">🤖 IA Prefeitura</p>
                      )}
                      <p className="text-sm text-gray-200 leading-relaxed">{m.mensagem}</p>
                      <p className="text-[10px] text-gray-500 mt-1.5 text-right">{t(m.created_at)}</p>
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Rodapé do painel */}
          <div className="px-4 py-3 border-t border-gray-800 flex-shrink-0">
            <p className="text-[11px] text-gray-600 text-center">
              Respostas automáticas via IA · WhatsApp Evolution API
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
