/**
 * supabase.js — Cliente Supabase para o Frontend
 * Usado para o Realtime (atualizações ao vivo no dashboard)
 *
 * IMPORTANTE: Aqui usamos a ANON KEY (não a service key!)
 * A anon key é pública e segura para o frontend.
 */
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
