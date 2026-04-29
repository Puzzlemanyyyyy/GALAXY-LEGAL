import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ShieldCheck, AlertTriangle, Save, CheckCircle2, Loader2 } from 'lucide-react'
import { api } from '../lib/api'

export default function DraftEditorPage() {
  const { caseId, draftId } = useParams()
  const navigate = useNavigate()
  const [draft, setDraft] = useState(null)
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [approving, setApproving] = useState(false)
  const [evidences, setEvidences] = useState([])
  const [error, setError] = useState('')
  const [picked, setPicked] = useState(null)
  const [success, setSuccess] = useState('')

  const reload = async () => {
    setError('')
    try {
      const d = await api.getDraft(draftId)
      setDraft(d); setContent(d.content_md)
      if (d.run_id) {
        const ev = await api.getRunEvidences(d.run_id)
        setEvidences(ev || [])
      }
    } catch (err) { setError(err.message || 'No se pudo cargar el borrador') }
  }
  useEffect(() => { reload() }, [draftId])

  const evidenceMap = useMemo(() => {
    const m = {}
    evidences.forEach((e) => { m[e.external_id] = e })
    return m
  }, [evidences])

  const referencedIds = useMemo(() => Array.from(new Set((content.match(/\[E:([A-Za-z0-9_-]+)\]/g) || []).map((s) => s.slice(3, -1)))), [content])
  const unverified = referencedIds.filter((id) => !evidenceMap[id] || !evidenceMap[id].verified)

  const save = async () => {
    setSaving(true); setError(''); setSuccess('')
    try {
      const created = await api.saveRevision(draftId, content, draft?.title)
      setSuccess(`Revisión v${created.version} guardada`)
      navigate(`/cases/${caseId}/drafts/${created.id}`, { replace: true })
    } catch (err) { setError(err.message) }
    finally { setSaving(false) }
  }

  const approve = async () => {
    setApproving(true); setError(''); setSuccess('')
    try {
      const updated = await api.approveDraft(draftId)
      setDraft(updated); setSuccess('Borrador aprobado (inmutable).')
    } catch (err) { setError(err.message) }
    finally { setApproving(false) }
  }

  if (!draft) return <div className="min-h-screen grid place-items-center text-ink-600"><Loader2 className="w-5 h-5 animate-spin" /></div>

  const isApproved = draft.status === 'approved'

  return (
    <div data-testid="draft-editor-page" className="min-h-screen bg-ink-50">
      <header className="bg-white border-b border-ink-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center gap-4">
          <button data-testid="back-to-case" onClick={() => navigate(`/cases/${caseId}`)} className="text-ink-600 hover:text-ink-900 inline-flex items-center gap-1.5">
            <ArrowLeft className="w-4 h-4" /> <span className="text-sm">Expediente</span>
          </button>
          <div className="h-5 w-px bg-ink-200" />
          <div className="min-w-0 flex-1">
            <div className="font-serif text-lg font-semibold text-ink-900 truncate">{draft.title}</div>
            <div className="text-xs text-ink-600">v{draft.version} · {draft.draft_type} · <span className={isApproved ? 'text-emerald-700' : 'text-ink-600'}>{draft.status}</span></div>
          </div>
          <button data-testid="save-revision-btn" disabled={saving || isApproved} onClick={save} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-ink-200 bg-white text-ink-900 text-sm hover:bg-ink-50 disabled:opacity-50">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Guardar revisión
          </button>
          <button data-testid="approve-btn" disabled={approving || isApproved || unverified.length > 0 || !draft.citations_valid} onClick={approve} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ink-900 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50">
            {approving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />} Aprobar
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 grid grid-cols-12 gap-5">
        <section className="col-span-12 lg:col-span-8">
          {(error || success) && (
            <div data-testid="draft-banner" className={`mb-3 text-sm rounded-lg p-3 border ${error ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
              {error || success}
            </div>
          )}
          {unverified.length > 0 && (
            <div data-testid="unverified-banner" className="mb-3 text-sm rounded-lg p-3 border bg-rose-50 text-rose-700 border-rose-200 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 mt-0.5" />
              <div>
                <div className="font-medium">Citas sin verificar</div>
                <div className="text-xs">Antes de aprobar, todas las marcas <code>[E:xxx]</code> deben coincidir con una evidencia verificada.</div>
                <div className="text-xs mt-1">Sin verificar: {unverified.join(', ')}</div>
              </div>
            </div>
          )}
          <textarea
            data-testid="draft-editor-textarea"
            disabled={isApproved}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="w-full min-h-[60vh] rounded-xl border border-ink-200 bg-white p-5 font-mono text-sm leading-relaxed text-ink-900 focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-ink-50 disabled:text-ink-600"
          />
          <div className="mt-3">
            <div className="text-xs uppercase tracking-wider text-ink-600 mb-2">Vista previa</div>
            <div data-testid="draft-preview" className="rounded-xl border border-ink-200 bg-white p-5 text-sm whitespace-pre-wrap font-serif text-ink-900 leading-relaxed">
              {renderWithMarkers(content, evidenceMap)}
            </div>
          </div>
        </section>

        <aside className="col-span-12 lg:col-span-4">
          <div className="text-xs uppercase tracking-wider text-ink-600 mb-2">Evidencias</div>
          <ul data-testid="draft-evidences" className="space-y-2">
            {evidences.length === 0 && <li className="text-sm text-ink-600">Sin evidencias adjuntas.</li>}
            {evidences.map((e) => (
              <li key={e.id} data-testid={`evidence-${e.external_id}`} className={`rounded-lg border p-3 text-sm bg-white ${picked === e.external_id ? 'border-brand-500' : 'border-ink-200'}`} onMouseEnter={() => setPicked(e.external_id)}>
                <div className="text-xs uppercase tracking-wider text-ink-600">
                  {e.external_id} · pág. {e.page ?? '—'} · párr. {e.paragraph ?? '—'} {e.verified && <span className="text-emerald-700 inline-flex items-center gap-1 ml-1"><ShieldCheck className="w-3 h-3" /> verificada</span>}
                </div>
                <div className="text-ink-900 italic mt-1">"{e.quote_excerpt}"</div>
              </li>
            ))}
          </ul>
        </aside>
      </main>
    </div>
  )
}

function renderWithMarkers(text, evidenceMap) {
  if (!text) return null
  const parts = text.split(/(\[E:[A-Za-z0-9_-]+\])/g)
  return parts.map((p, i) => {
    const m = /^\[E:([A-Za-z0-9_-]+)\]$/.exec(p)
    if (!m) return <span key={i}>{p}</span>
    const id = m[1]
    const ev = evidenceMap[id]
    const ok = ev && ev.verified
    return (
      <sup key={i} title={ev ? `${ev.external_id} — "${ev.quote_excerpt.slice(0, 120)}"` : 'evidencia desconocida'} className={`mx-0.5 px-1 py-0.5 rounded text-[10px] font-mono cursor-help ${ok ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'}`}>
        {id}
      </sup>
    )
  })
}
