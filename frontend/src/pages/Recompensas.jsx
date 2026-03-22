/**
 * Recompensas.jsx - Aba Recompensas (Camada Financeira)
 * =====================================================
 * Painel exclusivo do financeiro para gerenciar pagamentos
 * do Programa Cidadão Ativo (Decreto 291/2026).
 *
 * SEGURANÇA:
 * - CPF e PIX aparecem MASCARADOS por padrão
 * - Dados completos só com clique + confirmação (registrado no audit_log)
 * - Nenhum conteúdo da denúncia é exibido aqui (fotos, mensagem, etc)
 */
import { useEffect, useState } from 'react'
import { apiGet, apiPatch, apiUrl } from '../services/api'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'

// ── Status das recompensas com cores e ícones ──
const STATUS_INFO = {
  pendente_validacao: { label: 'Pendente Validação', cor: 'bg-yellow-900 text-yellow-300', icon: '⏳' },
  validada:           { label: 'Validada',           cor: 'bg-blue-900 text-blue-300',     icon: '✅' },
  aguardando_pagamento: { label: 'Aguardando Pgto',  cor: 'bg-orange-900 text-orange-300', icon: '💰' },
  paga:               { label: 'Paga',               cor: 'bg-emerald-900 text-emerald-300', icon: '✓' },
  rejeitada:          { label: 'Rejeitada',          cor: 'bg-red-900 text-red-400',        icon: '✗' },
}

// ── Tipo de chave PIX ──
const TIPO_PIX = {
  cpf: 'CPF',
  email: 'E-mail',
  telefone: 'Telefone',
  aleatoria: 'Chave Aleatória',
}

export default function Recompensas() {
  const [recompensas, setRecompensas] = useState([])
  const [kpis, setKpis] = useState(null)
  const [config, setConfig] = useState([])
  const [selecionada, setSelecionada] = useState(null)
  const [filtroStatus, setFiltroStatus] = useState('')
  const [dadosPagamento, setDadosPagamento] = useState(null)
  const [mostrarDados, setMostrarDados] = useState(false)
  const [loading, setLoading] = useState(false)

  // ── Modal de ações ──
  const [modalAcao, setModalAcao] = useState(null) // 'validar' | 'rejeitar' | 'pagar'
  const [motivoRejeicao, setMotivoRejeicao] = useState('')
  const [empenho, setEmpenho] = useState('')
  const [dotacao, setDotacao] = useState('')

  // ── Carregar lista ──
  const carregar = async () => {
    try {
      const data = await apiGet('/api/recompensas/', { status: filtroStatus })
      setRecompensas(data || [])
    } catch (error) {
      console.error('Falha ao carregar recompensas:', error)
      setRecompensas([])
    }
  }

  // ── Carregar KPIs ──
  const carregarKpis = async () => {
    try {
      const data = await apiGet('/api/recompensas/kpis')
      setKpis(data)
    } catch (error) {
      console.error('Falha ao carregar KPIs recompensas:', error)
    }
  }

  // ── Carregar config de valores ──
  const carregarConfig = async () => {
    try {
      const data = await apiGet('/api/recompensas/config')
      setConfig(data || [])
    } catch (error) {
      console.error('Falha ao carregar config recompensas:', error)
    }
  }

  useEffect(() => {
    carregar()
    carregarKpis()
    carregarConfig()
  }, [filtroStatus])

  // Polling a cada 10s
  useEffect(() => {
    const interval = setInterval(() => {
      carregar()
      carregarKpis()
    }, 10000)
    return () => clearInterval(interval)
  }, [filtroStatus])

  const tempoRelativo = (d) => {
    if (!d) return '—'
    return formatDistanceToNow(new Date(d), { addSuffix: true, locale: ptBR })
  }

  const formatarValor = (v) => {
    if (!v) return 'R$ —'
    return `R$ ${parseFloat(v).toFixed(2).replace('.', ',')}`
  }

  // ── Ver dados de pagamento (ação auditada!) ──
  const verDadosPagamento = async (recompensa) => {
    if (!confirm('⚠️ ATENÇÃO: Este acesso será registrado no log de auditoria (LGPD).\n\nDeseja visualizar os dados de pagamento?')) {
      return
    }
    setLoading(true)
    try {
      const data = await apiGet(`/api/recompensas/${recompensa.id}/dados-pagamento`, {
        operador: 'Operador Demo',
      })
      setDadosPagamento(data)
      setMostrarDados(true)
    } catch (error) {
      alert('Erro ao acessar dados: ' + error.message)
    }
    setLoading(false)
  }

  // ── Validar recompensa ──
  const executarValidacao = async (procedente) => {
    if (!selecionada) return
    setLoading(true)
    try {
      await apiPatch(`/api/recompensas/${selecionada.id}/validar`, {
        procedente,
        operador: 'Operador Demo',
        motivo_rejeicao: procedente ? undefined : motivoRejeicao,
      })
      setModalAcao(null)
      setMotivoRejeicao('')
      setSelecionada(null)
      carregar()
      carregarKpis()
    } catch (error) {
      alert('Erro: ' + error.message)
    }
    setLoading(false)
  }

  // ── Registrar pagamento ──
  const executarPagamento = async () => {
    if (!selecionada) return
    setLoading(true)
    try {
      await apiPatch(`/api/recompensas/${selecionada.id}/pagar`, {
        operador: 'Financeiro Demo',
        numero_empenho: empenho,
        dotacao_orcamentaria: dotacao,
      })
      setModalAcao(null)
      setEmpenho('')
      setDotacao('')
      setSelecionada(null)
      carregar()
      carregarKpis()
    } catch (error) {
      alert('Erro: ' + error.message)
    }
    setLoading(false)
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* ── KPIs ── */}
      <div className="grid grid-cols-5 gap-4 p-4 bg-gray-900 border-b border-gray-700 flex-shrink-0">
        <div className="bg-gray-800 rounded-2xl p-4 border border-gray-700">
          <p className="text-gray-400 text-xs uppercase tracking-wider mb-1">Pendentes Validação</p>
          <p className="text-3xl font-black text-yellow-400">{kpis?.pendentes_validacao ?? '—'}</p>
        </div>
        <div className="bg-gray-800 rounded-2xl p-4 border border-gray-700">
          <p className="text-gray-400 text-xs uppercase tracking-wider mb-1">Aguardando Pagamento</p>
          <p className="text-3xl font-black text-orange-400">{kpis?.aguardando_pagamento ?? '—'}</p>
        </div>
        <div className="bg-gray-800 rounded-2xl p-4 border border-gray-700">
          <p className="text-gray-400 text-xs uppercase tracking-wider mb-1">Total Pago</p>
          <p className="text-3xl font-black text-emerald-400">{kpis ? formatarValor(kpis.total_pago) : '—'}</p>
        </div>
        <div className="bg-gray-800 rounded-2xl p-4 border border-gray-700">
          <p className="text-gray-400 text-xs uppercase tracking-wider mb-1">Recompensas Pagas</p>
          <p className="text-3xl font-black text-emerald-300">{kpis?.quantidade_pagas ?? '—'}</p>
        </div>
        <div className="bg-gray-800 rounded-2xl p-4 border border-gray-700">
          <p className="text-gray-400 text-xs uppercase tracking-wider mb-1">Rejeitadas</p>
          <p className="text-3xl font-black text-red-400">{kpis?.rejeitadas ?? '—'}</p>
        </div>
      </div>

      {/* ── Conteúdo principal ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Lista de recompensas ── */}
        <div className="flex flex-col flex-1 overflow-hidden border-r border-gray-700">

          {/* Filtros */}
          <div className="flex gap-3 p-4 border-b border-gray-700 bg-gray-900 flex-shrink-0">
            <select
              value={filtroStatus}
              onChange={(e) => setFiltroStatus(e.target.value)}
              className="bg-gray-800 text-white border border-gray-600 rounded-lg px-3 py-2 text-sm"
            >
              <option value="">Todos os status</option>
              {Object.entries(STATUS_INFO).map(([key, { label }]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <span className="ml-auto text-gray-400 text-sm flex items-center">
              {recompensas.length} recompensa{recompensas.length !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Tabela */}
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-800 sticky top-0">
                <tr className="text-gray-400 text-left text-xs uppercase tracking-wider">
                  <th className="px-4 py-3">Protocolo</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Valor</th>
                  <th className="px-4 py-3">Tipo PIX</th>
                  <th className="px-4 py-3">CPF</th>
                  <th className="px-4 py-3">Validado por</th>
                  <th className="px-4 py-3">Pago por</th>
                  <th className="px-4 py-3">Data</th>
                </tr>
              </thead>
              <tbody>
                {recompensas.map((r) => {
                  const sta = STATUS_INFO[r.status] || { label: r.status, cor: 'bg-gray-700 text-gray-400', icon: '?' }

                  return (
                    <tr
                      key={r.id}
                      onClick={() => { setSelecionada(r); setMostrarDados(false); setDadosPagamento(null); }}
                      className={`border-b border-gray-800 cursor-pointer transition-all ${
                        selecionada?.id === r.id
                          ? 'bg-gray-700'
                          : 'hover:bg-gray-800'
                      }`}
                    >
                      <td className="px-4 py-3 font-mono text-blue-400 font-semibold">{r.protocolo}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-bold px-2 py-1 rounded-lg ${sta.cor}`}>
                          {sta.icon} {sta.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-bold text-emerald-400">{formatarValor(r.valor)}</td>
                      <td className="px-4 py-3 text-gray-300">{TIPO_PIX[r.tipo_chave_pix] || '—'}</td>
                      <td className="px-4 py-3 text-gray-400 font-mono text-xs">{r.cpf_mascarado}</td>
                      <td className="px-4 py-3 text-gray-300">{r.validado_por || '—'}</td>
                      <td className="px-4 py-3 text-gray-300">{r.pago_por || '—'}</td>
                      <td className="px-4 py-3 text-gray-500">{tempoRelativo(r.created_at)}</td>
                    </tr>
                  )
                })}
                {recompensas.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-gray-500">
                      Nenhuma recompensa encontrada
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Painel de detalhes ── */}
        <div className="w-[420px] bg-gray-900 overflow-y-auto flex-shrink-0 p-6">
          {selecionada ? (
            <>
              {/* Cabeçalho */}
              <div className="flex justify-between items-center mb-4">
                <span className="text-blue-400 font-mono font-bold text-lg">{selecionada.protocolo}</span>
                <button onClick={() => { setSelecionada(null); setMostrarDados(false); }} className="text-gray-500 hover:text-white">✕</button>
              </div>

              {/* Status badge grande */}
              {(() => {
                const sta = STATUS_INFO[selecionada.status] || { label: selecionada.status, cor: 'bg-gray-700', icon: '?' }
                return (
                  <div className={`${sta.cor} rounded-xl p-4 mb-4 text-center`}>
                    <p className="text-3xl mb-1">{sta.icon}</p>
                    <p className="text-lg font-black">{sta.label}</p>
                  </div>
                )
              })()}

              {/* Valor */}
              <div className="bg-gray-800 rounded-xl p-4 mb-4 text-center border border-gray-700">
                <p className="text-gray-400 text-xs uppercase mb-1">Valor da Recompensa</p>
                <p className="text-4xl font-black text-emerald-400">{formatarValor(selecionada.valor)}</p>
              </div>

              {/* Dados */}
              <div className="space-y-3 text-sm mb-6">
                <div>
                  <span className="text-gray-400">CPF (mascarado):</span>{' '}
                  <span className="text-white font-mono">{selecionada.cpf_mascarado}</span>
                </div>
                <div>
                  <span className="text-gray-400">Tipo chave PIX:</span>{' '}
                  <span className="text-white">{TIPO_PIX[selecionada.tipo_chave_pix] || '—'}</span>
                </div>
                {selecionada.validado_por && (
                  <div>
                    <span className="text-gray-400">Validado por:</span>{' '}
                    <span className="text-white">{selecionada.validado_por}</span>
                    <span className="text-gray-500 ml-2">({tempoRelativo(selecionada.validado_em)})</span>
                  </div>
                )}
                {selecionada.pago_por && (
                  <div>
                    <span className="text-gray-400">Pago por:</span>{' '}
                    <span className="text-white">{selecionada.pago_por}</span>
                    <span className="text-gray-500 ml-2">({tempoRelativo(selecionada.pago_em)})</span>
                  </div>
                )}
                {selecionada.numero_empenho && (
                  <div>
                    <span className="text-gray-400">Nº Empenho:</span>{' '}
                    <span className="text-white font-mono">{selecionada.numero_empenho}</span>
                  </div>
                )}
                {selecionada.dotacao_orcamentaria && (
                  <div>
                    <span className="text-gray-400">Dotação Orçamentária:</span>{' '}
                    <span className="text-white font-mono">{selecionada.dotacao_orcamentaria}</span>
                  </div>
                )}
                {selecionada.motivo_rejeicao && (
                  <div className="bg-red-950 border border-red-800 rounded-lg p-3 mt-3">
                    <p className="text-red-400 text-xs uppercase font-bold mb-1">Motivo da Rejeição</p>
                    <p className="text-red-200">{selecionada.motivo_rejeicao}</p>
                  </div>
                )}
              </div>

              {/* ── Dados de pagamento (acesso auditado) ── */}
              {(selecionada.status === 'aguardando_pagamento' || selecionada.status === 'paga') && (
                <div className="mb-4">
                  {!mostrarDados ? (
                    <button
                      onClick={() => verDadosPagamento(selecionada)}
                      disabled={loading}
                      className="w-full py-3 rounded-xl bg-amber-700 hover:bg-amber-600 text-white font-bold transition-all border border-amber-500 flex items-center justify-center gap-2"
                    >
                      <span>🔐</span>
                      <span>{loading ? 'Acessando...' : 'Ver Dados de Pagamento'}</span>
                    </button>
                  ) : dadosPagamento && (
                    <div className="bg-amber-950 border border-amber-700 rounded-xl p-4">
                      <p className="text-amber-400 text-xs uppercase font-bold mb-3 flex items-center gap-2">
                        <span>🔐</span> Dados de Pagamento (acesso registrado)
                      </p>
                      <div className="space-y-2 text-sm">
                        <div>
                          <span className="text-amber-400">CPF:</span>{' '}
                          <span className="text-white font-mono font-bold">{dadosPagamento.cpf}</span>
                        </div>
                        <div>
                          <span className="text-amber-400">Chave PIX:</span>{' '}
                          <span className="text-white font-mono font-bold">{dadosPagamento.chave_pix}</span>
                        </div>
                        <div>
                          <span className="text-amber-400">Tipo:</span>{' '}
                          <span className="text-white">{TIPO_PIX[dadosPagamento.tipo_chave_pix] || '—'}</span>
                        </div>
                      </div>
                      <p className="text-amber-600 text-xs mt-3">⚠️ {dadosPagamento.aviso}</p>
                    </div>
                  )}
                </div>
              )}

              {/* ── Botões de ação ── */}
              <div className="space-y-2">
                {selecionada.status === 'pendente_validacao' && (
                  <>
                    <button
                      onClick={() => setModalAcao('validar')}
                      className="w-full py-3 rounded-xl bg-emerald-700 hover:bg-emerald-600 text-white font-bold transition-all"
                    >
                      ✅ Validar Denúncia (Procedente)
                    </button>
                    <button
                      onClick={() => setModalAcao('rejeitar')}
                      className="w-full py-3 rounded-xl bg-red-800 hover:bg-red-700 text-white font-bold transition-all"
                    >
                      ✗ Rejeitar Recompensa
                    </button>
                  </>
                )}

                {selecionada.status === 'aguardando_pagamento' && (
                  <button
                    onClick={() => setModalAcao('pagar')}
                    className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition-all text-lg"
                  >
                    💰 Registrar Pagamento PIX
                  </button>
                )}

                {/* Botão Gerar Termo PDF — disponível pra todas recompensas validadas/pagas */}
                {['aguardando_pagamento', 'paga', 'validada'].includes(selecionada.status) && (
                  <a
                    href={apiUrl(`/api/recompensas/${selecionada.id}/termo`, { operador: 'Operador Demo' })}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full py-3 rounded-xl bg-blue-700 hover:bg-blue-600 text-white font-bold transition-all flex items-center justify-center gap-2 mt-2"
                  >
                    📄 Gerar Termo de Recompensa (PDF)
                  </a>
                )}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="text-5xl mb-4">💰</div>
              <p className="text-gray-400 mb-2">Programa Cidadão Ativo</p>
              <p className="text-gray-500 text-sm">Decreto 291/2026</p>
              <p className="text-gray-600 text-xs mt-4">Selecione uma recompensa para gerenciar</p>

              {/* Mini tabela de valores */}
              {config.length > 0 && (
                <div className="mt-8 w-full">
                  <p className="text-gray-400 text-xs uppercase tracking-wider mb-3">Valores por Categoria</p>
                  <div className="space-y-2">
                    {config.map((c) => (
                      <div key={c.id} className="flex justify-between items-center bg-gray-800 rounded-lg px-3 py-2 text-sm">
                        <span className="text-gray-300 capitalize">{c.categoria.replace('_', ' ')}</span>
                        <span className="text-emerald-400 font-bold font-mono">{formatarValor(c.valor_padrao)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ══════════════════════════════════════════ */}
      {/* MODAIS DE AÇÃO                            */}
      {/* ══════════════════════════════════════════ */}

      {modalAcao && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-2xl p-6 w-[480px] border border-gray-600">

            {/* Modal: Validar */}
            {modalAcao === 'validar' && (
              <>
                <h2 className="text-xl font-black text-emerald-400 mb-4">✅ Validar Denúncia</h2>
                <p className="text-gray-300 mb-2">
                  Confirma que a denúncia <span className="text-blue-400 font-mono font-bold">{selecionada?.protocolo}</span> é <span className="text-emerald-400 font-bold">procedente</span>?
                </p>
                <p className="text-gray-400 text-sm mb-6">
                  A recompensa de <span className="text-emerald-400 font-bold">{formatarValor(selecionada?.valor)}</span> será liberada para pagamento pelo setor financeiro.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => executarValidacao(true)}
                    disabled={loading}
                    className="flex-1 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
                  >
                    {loading ? 'Processando...' : 'Confirmar Validação'}
                  </button>
                  <button
                    onClick={() => setModalAcao(null)}
                    className="px-6 py-3 rounded-xl bg-gray-700 hover:bg-gray-600 text-white"
                  >
                    Cancelar
                  </button>
                </div>
              </>
            )}

            {/* Modal: Rejeitar */}
            {modalAcao === 'rejeitar' && (
              <>
                <h2 className="text-xl font-black text-red-400 mb-4">✗ Rejeitar Recompensa</h2>
                <p className="text-gray-300 mb-4">
                  Informe o motivo da rejeição para <span className="text-blue-400 font-mono font-bold">{selecionada?.protocolo}</span>:
                </p>
                <textarea
                  value={motivoRejeicao}
                  onChange={(e) => setMotivoRejeicao(e.target.value)}
                  placeholder="Ex: Evidência fotográfica insuficiente, imagem não mostra o dano relatado..."
                  className="w-full bg-gray-700 text-white border border-gray-600 rounded-xl p-3 text-sm h-28 mb-4 resize-none"
                />
                <div className="flex gap-3">
                  <button
                    onClick={() => executarValidacao(false)}
                    disabled={loading || !motivoRejeicao.trim()}
                    className="flex-1 py-3 rounded-xl bg-red-700 hover:bg-red-600 text-white font-bold disabled:opacity-50"
                  >
                    {loading ? 'Processando...' : 'Confirmar Rejeição'}
                  </button>
                  <button
                    onClick={() => { setModalAcao(null); setMotivoRejeicao(''); }}
                    className="px-6 py-3 rounded-xl bg-gray-700 hover:bg-gray-600 text-white"
                  >
                    Cancelar
                  </button>
                </div>
              </>
            )}

            {/* Modal: Pagar */}
            {modalAcao === 'pagar' && (
              <>
                <h2 className="text-xl font-black text-emerald-400 mb-4">💰 Registrar Pagamento PIX</h2>
                <p className="text-gray-300 mb-4">
                  Registrar pagamento de <span className="text-emerald-400 font-bold text-xl">{formatarValor(selecionada?.valor)}</span> para o protocolo <span className="text-blue-400 font-mono font-bold">{selecionada?.protocolo}</span>
                </p>

                <div className="space-y-3 mb-6">
                  <div>
                    <label className="text-gray-400 text-xs uppercase block mb-1">Nº do Empenho</label>
                    <input
                      type="text"
                      value={empenho}
                      onChange={(e) => setEmpenho(e.target.value)}
                      placeholder="EMP-2026-00XXX"
                      className="w-full bg-gray-700 text-white border border-gray-600 rounded-lg px-3 py-2 text-sm font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-gray-400 text-xs uppercase block mb-1">Dotação Orçamentária</label>
                    <input
                      type="text"
                      value={dotacao}
                      onChange={(e) => setDotacao(e.target.value)}
                      placeholder="DOT-15.452.0045.2.048"
                      className="w-full bg-gray-700 text-white border border-gray-600 rounded-lg px-3 py-2 text-sm font-mono"
                    />
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={executarPagamento}
                    disabled={loading}
                    className="flex-1 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-lg"
                  >
                    {loading ? 'Processando...' : '✓ Confirmar Pagamento'}
                  </button>
                  <button
                    onClick={() => { setModalAcao(null); setEmpenho(''); setDotacao(''); }}
                    className="px-6 py-3 rounded-xl bg-gray-700 hover:bg-gray-600 text-white"
                  >
                    Cancelar
                  </button>
                </div>
              </>
            )}

          </div>
        </div>
      )}
    </div>
  )
}
