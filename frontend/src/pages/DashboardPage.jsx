import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Scale, LogOut, Plus, FolderOpen, ChevronRight, Loader2 } from 'lucide-react'
import { supabase } from '../lib/supabase'
import { api } from '../lib/api'
import NewCaseModal from '../components/NewCaseModal'

export default function DashboardPage() {
  const [user, setUser] = useState(null)
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user))
    refreshCases()
  }, [])

  const refreshCases = async () => {
    setLoading(true); setError('')
    try {
      const list = await api.listCases()
      setCases(list || [])
    } catch (err) { setError(err.message || 'No se pudieron cargar los expedientes') }
    finally { setLoading(false) }
  }

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
          <button data-testid="new-case-btn" onClick={() => setModalOpen(true)} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-ink-900 text-white font-medium hover:bg-brand-700 transition">
            <Plus className="w-4 h-4" /> Nuevo expediente
          </button>
        </div>

        {error && <div data-testid="dashboard-error" className="mb-4 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">{error}</div>}

        {loading ? (
          <div className="rounded-2xl border-2 border-dashed border-ink-200 p-16 text-center bg-white">
            <Loader2 className="w-6 h-6 text-ink-600 mx-auto animate-spin" />
          </div>
        ) : cases.length === 0 ? (
          <div data-testid="cases-empty-state" className="rounded-2xl border-2 border-dashed border-ink-200 p-16 text-center bg-white">
            <FolderOpen className="w-12 h-12 text-ink-200 mx-auto mb-4" />
            <h3 className="font-serif text-xl text-ink-900 mb-1">No hay expedientes todavía</h3>
            <p className="text-ink-600 text-sm mb-5">Crea el primero para empezar a indexar documentos.</p>
            <button data-testid="cases-empty-cta" onClick={() => setModalOpen(true)} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-ink-900 text-white font-medium hover:bg-brand-700 transition">
              <Plus className="w-4 h-4" /> Nuevo expediente
            </button>
          </div>
        ) : (
          <div data-testid="cases-list" className="grid gap-3">
            {cases.map((c) => (
              <button
                key={c.id}
                data-testid={`case-card-${c.id}`}
                onClick={() => navigate(`/cases/${c.id}`)}
                className="text-left bg-white rounded-xl border border-ink-200 p-5 hover:border-brand-500/40 hover:shadow-sm transition group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="font-medium text-ink-900 truncate">{c.title}</div>
                    <div className="text-sm text-ink-600 mt-1 truncate">
                      {[c.reference, c.jurisdiccion, c.materia].filter(Boolean).join(' · ') || '—'}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <StatusPill status={c.status} />
                    <ChevronRight className="w-4 h-4 text-ink-600 group-hover:translate-x-0.5 transition" />
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </main>

      <NewCaseModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={(c) => { setCases((prev) => [c, ...prev]); navigate(`/cases/${c.id}`) }}
      />
    </div>
  )
}

function StatusPill({ status }) {
  const map = {
    open:    'bg-emerald-50 text-emerald-700 border-emerald-200',
    closed:  'bg-ink-100 text-ink-600 border-ink-200',
    archived:'bg-ink-100 text-ink-600 border-ink-200',
  }
  const cls = map[status] || 'bg-brand-50 text-brand-700 border-brand-100'
  return <span className={`text-xs uppercase tracking-wider border px-2 py-1 rounded-full ${cls}`}>{status || 'open'}</span>
}
