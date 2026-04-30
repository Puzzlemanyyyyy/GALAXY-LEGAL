import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, FileText, Loader2, RefreshCcw, Trash2, Sparkles, ShieldCheck, AlertTriangle, History } from 'lucide-react'
import { api } from '../lib/api'
import DocumentUpload from '../components/DocumentUpload'
import WorkflowCard from '../components/WorkflowCard'

const TABS = [
  { id: 'summary',   label: 'Resumen' },
  { id: 'drafts',    label: 'Borradores' },
  { id: 'evidences', label: 'Evidencias' },
  { id: 'audit',     label: 'Auditoría' },
]

export default function CasePage() {
  const { caseId } = useParams()
  const navigate = useNavigate()
  const [caseData, setCaseData] = useState(null)
  const [docs, setDocs] = useState([])
  const [drafts, setDrafts] = useState([])
  const [runs, setRuns] = useState([])
  const [workflowTypes, setWorkflowTypes] = useState([])
  const [tab, setTab] = useState('summary')
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const loadAll = async () => {
    setRefreshing(true); setError('')
    try {
      const [c, d, dr, r, wt] = await Promise.all([
        api.getCase(caseId),
        api.listDocuments(caseId),
        api.listDrafts(caseId),
        api.listRuns(caseId),
        api.listRunTypes(),
      ])
      setCaseData(c); setDocs(d || []); setDrafts(dr || []); setRuns(r || []); setWorkflowTypes(wt || [])
    } catch (err) { setError(err.message || 'No se pudo cargar el expediente') }
    finally { setRefreshing(false) }
  }

  useEffect(() => { loadAll() }, [caseId])

  // Poll documents and runs while anything is in progress.
  useEffect(() => {
    const anyIndexing = docs.some((d) => d.status === 'indexing' || d.status === 'pending')
    const anyRunning = runs.some((r) => r.status === 'queued' || r.status === 'running')
    if (!anyIndexing && !anyRunning) return
    const t = setInterval(() => { loadAll() }, 3500)
    return () => clearInterval(t)
  }, [docs, runs])

  const readyDocs = useMemo(() => docs.filter((d) => d.status === 'ready').length, [docs])

  return (
    <div data-testid="case-page" className="min-h-screen bg-ink-50">
      <header className="bg-white border-b border-ink-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center gap-4">
          <button data-testid="back-to-dashboard" onClick={() => navigate('/dashboard')} className="text-ink-600 hover:text-ink-900 inline-flex items-center gap-1.5">
            <ArrowLeft className="w-4 h-4" /> <span className="text-sm">Expedientes</span>
          </button>
          <div className="h-5 w-px bg-ink-200" />
          <div className="min-w-0 flex-1">
            <div className="font-serif text-lg font-semibold text-ink-900 truncate">{caseData?.title || 'Cargando…'}</div>
            <div className="text-xs text-ink-600 truncate">
              {[caseData?.reference, caseData?.jurisdiccion, caseData?.materia].filter(Boolean).join(' · ') || '—'}
            </div>
          </div>
          <button data-testid="refresh-case" onClick={loadAll} className="text-ink-600 hover:text-ink-900 inline-flex items-center gap-1.5">
            {refreshing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCcw className="w-4 h-4" />}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 grid grid-cols-12 gap-5">
        {/* Left rail: documents */}
        <aside className="col-span-12 lg:col-span-3 space-y-4">
          <DocumentUpload caseId={caseId} onUploaded={() => loadAll()} />
          <div className="rounded-xl border border-ink-200 bg-white">
            <div className="px-4 py-3 border-b border-ink-200 flex items-center justify-between">
              <div className="text-sm font-medium text-ink-900">Documentos</div>
              <span className="text-xs text-ink-600">{readyDocs}/{docs.length} listos</span>
            </div>
            <ul data-testid="documents-list" className="divide-y divide-ink-100 max-h-[60vh] overflow-y-auto">
              {docs.length === 0 && <li className="px-4 py-6 text-sm text-ink-600">Aún no hay documentos.</li>}
              {docs.map((d) => (
                <li key={d.id} data-testid={`document-row-${d.id}`} className="px-4 py-3 text-sm flex items-start gap-2">
                  <FileText className="w-4 h-4 text-ink-600 mt-0.5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-ink-900 truncate">{d.filename}</div>
                    <div className="text-xs text-ink-600 mt-0.5 flex items-center gap-2">
                      <DocStatus status={d.status} error={d.index_error} />
                      {d.pages_count ? <span>· {d.pages_count} pág.</span> : null}
                    </div>
                  </div>
                  <button data-testid={`document-reindex-${d.id}`} title="Reindexar" onClick={() => api.reindexDoc(d.id).then(loadAll)} className="text-ink-600 hover:text-brand-700">
                    <RefreshCcw className="w-3.5 h-3.5" />
                  </button>
                  <button data-testid={`document-delete-${d.id}`} title="Eliminar" onClick={() => api.deleteDoc(d.id).then(loadAll)} className="text-ink-600 hover:text-rose-700">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        {/* Center: tabs */}
        <section className="col-span-12 lg:col-span-6 space-y-4">
          {error && <div data-testid="case-error" className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">{error}</div>}
          <div className="rounded-xl border border-ink-200 bg-white">
            <div className="flex gap-1 border-b border-ink-200 px-3 pt-3">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  data-testid={`tab-${t.id}`}
                  onClick={() => setTab(t.id)}
                  className={`px-3 py-2 text-sm rounded-t-lg ${tab === t.id ? 'bg-ink-50 text-ink-900 border border-ink-200 border-b-white -mb-px' : 'text-ink-600 hover:text-ink-900'}`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <div className="p-5 min-h-[40vh]">
              {tab === 'summary' && <SummaryTab caseData={caseData} docs={docs} runs={runs} drafts={drafts} />}
              {tab === 'drafts' && <DraftsTab drafts={drafts} caseId={caseId} navigate={navigate} />}
              {tab === 'evidences' && <EvidencesTab runs={runs} />}
              {tab === 'audit' && <AuditTab runs={runs} />}
            </div>
          </div>
        </section>

        {/* Right rail: workflows + runs */}
        <aside className="col-span-12 lg:col-span-3 space-y-3">
          <div className="px-1">
            <div className="text-xs uppercase tracking-wider text-ink-600 mb-2">Workflows</div>
            {workflowTypes.length === 0 && <div className="text-sm text-ink-600">No hay workflows disponibles.</div>}
            <div className="space-y-2">
              {workflowTypes.map((w) => (
                <WorkflowCard
                  key={w.workflow_type}
                  caseId={caseId}
                  workflow={w}
                  onStarted={() => loadAll()}
                />
              ))}
            </div>
          </div>
          <div className="px-1">
            <div className="text-xs uppercase tracking-wider text-ink-600 mb-2">Ejecuciones</div>
            <ul data-testid="runs-list" className="space-y-2">
              {runs.length === 0 && <li className="text-sm text-ink-600">Sin ejecuciones.</li>}
              {runs.map((r) => (
                <li key={r.id} data-testid={`run-row-${r.id}`} className="rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-ink-900">{r.workflow_type}</span>
                    <RunStatus status={r.status} />
                  </div>
                  <div className="text-xs text-ink-600 mt-1">
                    Paso: {r.current_step || '—'} · ${'{'}{Number(r.cost_usd || 0).toFixed(4)}{'}'}
                  </div>
                  {(r.status === 'completed' || r.status === 'succeeded') && (
                    <button data-testid={`open-draft-${r.id}`} onClick={async () => {
                      try {
                        const d = await api.getRunDraft(r.id)
                        navigate(`/cases/${caseId}/drafts/${d.id}`)
                      } catch (e) { alert(e.message) }
                    }} className="mt-2 text-xs text-brand-700 hover:underline">Abrir borrador →</button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </main>
    </div>
  )
}

function DocStatus({ status, error }) {
  if (status === 'ready')    return <span className="inline-flex items-center gap-1 text-emerald-700"><ShieldCheck className="w-3 h-3" /> indexado</span>
  if (status === 'indexing') return <span className="inline-flex items-center gap-1 text-brand-700"><Loader2 className="w-3 h-3 animate-spin" /> indexando…</span>
  if (status === 'failed')   return <span className="inline-flex items-center gap-1 text-rose-700" title={error || ''}><AlertTriangle className="w-3 h-3" /> error</span>
  return <span className="text-ink-600">{status}</span>
}

function RunStatus({ status }) {
  const map = {
    queued:      'text-ink-600',
    running:     'text-brand-700',
    completed:   'text-emerald-700',
    succeeded:   'text-emerald-700',
    failed:      'text-rose-700',
    needs_human: 'text-amber-700',
  }
  return <span className={`text-xs uppercase tracking-wider ${map[status] || 'text-ink-600'}`}>{status}</span>
}

function SummaryTab({ caseData, docs, runs, drafts }) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-serif text-2xl text-ink-900">{caseData?.title}</h2>
        <p className="text-sm text-ink-600 mt-1">{caseData?.description || 'Sin descripción.'}</p>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Documentos" value={docs.length} sub={`${docs.filter((d) => d.status === 'ready').length} indexados`} />
        <Stat label="Ejecuciones" value={runs.length} sub={`${runs.filter((r) => r.status === 'completed' || r.status === 'succeeded').length} OK`} />
        <Stat label="Borradores" value={drafts.length} sub={`${drafts.filter((d) => d.status === 'approved').length} aprobados`} />
      </div>
      <div className="rounded-lg bg-ink-50 border border-ink-200 p-4 text-sm text-ink-600">
        Sube documentos a la izquierda y ejecuta un workflow desde el panel derecho. El primer
        análisis se centra en producir un resumen, hechos y riesgos con citas verificables.
      </div>
    </div>
  )
}

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-ink-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wider text-ink-600">{label}</div>
      <div className="mt-1 text-2xl font-serif text-ink-900">{value}</div>
      <div className="text-xs text-ink-600">{sub}</div>
    </div>
  )
}

function DraftsTab({ drafts, caseId, navigate }) {
  if (drafts.length === 0) return <div className="text-sm text-ink-600">Aún no hay borradores. Ejecuta un workflow.</div>
  return (
    <ul className="space-y-2">
      {drafts.map((d) => (
        <li key={d.id} data-testid={`draft-row-${d.id}`} className="rounded-lg border border-ink-200 bg-white p-4 hover:shadow-sm transition">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="font-medium text-ink-900 truncate">{d.title}</div>
              <div className="text-xs text-ink-600 mt-0.5">v{d.version} · {d.draft_type} · {d.status}</div>
            </div>
            <button data-testid={`open-draft-card-${d.id}`} onClick={() => navigate(`/cases/${caseId}/drafts/${d.id}`)} className="text-sm text-brand-700 hover:underline">Abrir →</button>
          </div>
        </li>
      ))}
    </ul>
  )
}

function EvidencesTab({ runs }) {
  const [evidences, setEvidences] = useState([])
  const [picked, setPicked] = useState(null)
  useEffect(() => {
    const done = runs.find((r) => r.status === 'completed' || r.status === 'succeeded')
    if (!done) { setEvidences([]); setPicked(null); return }
    setPicked(done.id)
    api.getRunEvidences(done.id).then(setEvidences).catch(() => setEvidences([]))
  }, [runs])
  if (!picked) return <div className="text-sm text-ink-600">Las evidencias aparecen tras una ejecución exitosa.</div>
  return (
    <ul className="space-y-2">
      {evidences.map((e) => (
        <li key={e.id} className="rounded-lg border border-ink-200 bg-white p-3 text-sm">
          <div className="text-xs uppercase tracking-wider text-ink-600">{e.external_id} · pág. {e.page ?? '—'} · párr. {e.paragraph ?? '—'}</div>
          <div className="text-ink-900 italic mt-1">"{e.quote_excerpt}"</div>
        </li>
      ))}
      {evidences.length === 0 && <li className="text-sm text-ink-600">Sin evidencias todavía.</li>}
    </ul>
  )
}

function AuditTab({ runs }) {
  return (
    <div className="space-y-2 text-sm">
      <div className="text-ink-600 mb-2 inline-flex items-center gap-1.5"><History className="w-3.5 h-3.5" /> Histórico de ejecuciones</div>
      {runs.length === 0 && <div className="text-ink-600">Sin actividad.</div>}
      {runs.map((r) => (
        <div key={r.id} className="rounded-lg border border-ink-200 bg-white p-3">
          <div className="font-medium text-ink-900">{r.workflow_type}</div>
          <div className="text-xs text-ink-600 mt-0.5">
            {r.status} · paso {r.current_step || '—'} · ${Number(r.cost_usd || 0).toFixed(4)} · creado {new Date(r.created_at).toLocaleString('es-ES')}
          </div>
          {r.error && <div className="text-xs text-rose-700 mt-1">{r.error}</div>}
        </div>
      ))}
    </div>
  )
}
