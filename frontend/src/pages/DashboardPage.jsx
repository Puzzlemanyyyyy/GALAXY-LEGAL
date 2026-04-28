import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Scale, LogOut, Plus, FolderOpen } from 'lucide-react'
import { supabase } from '../lib/supabase'

export default function DashboardPage() {
  const [user, setUser] = useState(null)
  const [cases, setCases] = useState([])
  const navigate = useNavigate()

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user))
    supabase.from('cases').select('*').order('created_at', { ascending: false })
      .then(({ data }) => setCases(data || []))
  }, [])

  const signOut = async () => {
    await supabase.auth.signOut()
    navigate('/login')
  }

  return (
    <div data-testid="dashboard-page" className="min-h-screen bg-ink-50">
      <header className="bg-white border-b border-ink-200">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-600 grid place-items-center">
              <Scale className="w-4 h-4 text-white" />
            </div>
            <span className="font-serif text-xl font-semibold text-ink-900">Galaxy Legal</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span data-testid="user-email" className="text-ink-600">{user?.email}</span>
            <button data-testid="signout-btn" onClick={signOut} className="inline-flex items-center gap-1.5 text-ink-600 hover:text-ink-900">
              <LogOut className="w-4 h-4" /> Salir
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-12">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="font-serif text-3xl font-semibold text-ink-900">Expedientes</h1>
            <p className="text-ink-600 mt-1">Gestiona casos legales y conecta documentos desde Drive</p>
          </div>
          <button data-testid="new-case-btn" className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-ink-900 text-white font-medium hover:bg-brand-700 transition">
            <Plus className="w-4 h-4" /> Nuevo expediente
          </button>
        </div>

        {cases.length === 0 ? (
          <div className="rounded-2xl border-2 border-dashed border-ink-200 p-16 text-center bg-white">
            <FolderOpen className="w-12 h-12 text-ink-200 mx-auto mb-4" />
            <h3 className="font-serif text-xl text-ink-900 mb-1">No hay expedientes todavía</h3>
            <p className="text-ink-600 text-sm">Crea el primero para empezar a indexar documentos.</p>
          </div>
        ) : (
          <div className="grid gap-3">
            {cases.map((c) => (
              <div key={c.id} className="bg-white rounded-xl border border-ink-200 p-5 hover:shadow-sm transition">
                <div className="font-medium text-ink-900">{c.title}</div>
                <div className="text-sm text-ink-600 mt-1">
                  {c.jurisdiccion || '—'} · {c.materia || '—'} · {c.status}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
