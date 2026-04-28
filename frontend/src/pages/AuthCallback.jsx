import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function AuthCallback() {
  const navigate = useNavigate()
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) navigate('/dashboard', { replace: true })
      else navigate('/login', { replace: true })
    })
  }, [navigate])
  return <div className="flex h-screen items-center justify-center text-ink-600">Autenticando…</div>
}
