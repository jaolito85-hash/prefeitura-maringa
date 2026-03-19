/**
 * AudioManager.jsx — Gerenciador de Sons do Dashboard
 * Usa Web Audio API — sem arquivos MP3, gera os sons no código
 *
 * DICA: É aqui que você pode trocar os sons de alerta depois.
 * Web Audio API é nativa do browser, funciona sem internet.
 */
import { useEffect, useRef } from 'react'

export default function AudioManager({ sosAtivos, mutado, abaAtiva }) {
  const audioContextRef = useRef(null)
  const sireneIntervalRef = useRef(null)
  const anteriorSosRef = useRef(0)

  const getContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)()
    }
    return audioContextRef.current
  }

  // Toca um bipe simples
  const tocarBipe = (frequencia = 880, duracao = 0.15, volume = 0.3) => {
    if (mutado) return
    try {
      const ctx = getContext()
      const oscillator = ctx.createOscillator()
      const gainNode = ctx.createGain()

      oscillator.connect(gainNode)
      gainNode.connect(ctx.destination)

      oscillator.type = 'sine'
      oscillator.frequency.setValueAtTime(frequencia, ctx.currentTime)

      gainNode.gain.setValueAtTime(volume, ctx.currentTime)
      gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duracao)

      oscillator.start(ctx.currentTime)
      oscillator.stop(ctx.currentTime + duracao)
    } catch (e) {
      // Silencioso — Web Audio API pode ser bloqueada antes de interação do usuário
    }
  }

  // Toca a sirene de emergência SOS (3 bipes graves + agudos)
  const tocarSirene = () => {
    if (mutado) return
    try {
      const ctx = getContext()
      const now = ctx.currentTime

      const sequencia = [
        { freq: 440, inicio: 0,    dur: 0.2 },
        { freq: 880, inicio: 0.25, dur: 0.2 },
        { freq: 440, inicio: 0.5,  dur: 0.2 },
        { freq: 880, inicio: 0.75, dur: 0.2 },
        { freq: 440, inicio: 1.0,  dur: 0.3 },
      ]

      sequencia.forEach(({ freq, inicio, dur }) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain)
        gain.connect(ctx.destination)

        osc.type = 'sawtooth'
        osc.frequency.setValueAtTime(freq, now + inicio)

        gain.gain.setValueAtTime(0.4, now + inicio)
        gain.gain.exponentialRampToValueAtTime(0.001, now + inicio + dur)

        osc.start(now + inicio)
        osc.stop(now + inicio + dur)
      })
    } catch (e) {}
  }

  // Dispara sirene quando um novo SOS aparece
  useEffect(() => {
    if (sosAtivos > anteriorSosRef.current) {
      // Novo alerta SOS detectado!
      tocarSirene()

      // Repete a cada 30 segundos enquanto houver alerta ativo
      clearInterval(sireneIntervalRef.current)
      sireneIntervalRef.current = setInterval(() => {
        if (sosAtivos > 0 && !mutado) {
          tocarSirene()
        }
      }, 30000)
    }

    if (sosAtivos === 0) {
      clearInterval(sireneIntervalRef.current)
    }

    anteriorSosRef.current = sosAtivos
    return () => clearInterval(sireneIntervalRef.current)
  }, [sosAtivos, mutado])

  // Som quando muda de aba para SOS (com alerta ativo)
  useEffect(() => {
    if (abaAtiva === 'sos' && sosAtivos > 0) {
      tocarSirene()
    }
  }, [abaAtiva])

  return null // Componente invisível — só gerencia áudio
}
