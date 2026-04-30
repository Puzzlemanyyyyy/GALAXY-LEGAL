import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Scale, ShieldCheck, AlertTriangle, Loader2 } from 'lucide-react'
import { getPublicDraft } from '../lib/api'

export default function PublicDraftPage() {
  const { token } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [picked, setPicked] = useState(null)
  const [highlighted, setHighlighted] = useState(null)
  const evidenceRefs = useRef({})

  useEffect(() => {
    getPublicDraft(token)
      .then(setData)
      .catch((err) => setError(err.message || 'No se pudo cargar el análisis'))
  }, [token])

  const evidenceMap = useMemo(() => {
    if (!data) return {}
    const m = {}
    ;(data.evidences || []).forEach((e) => { m[e.external_id] = e })
    return m
  }, [data])

  const focusEvidence = (id) => {
    setPicked(id)
    const el = evidenceRefs.current[id]
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    setHighlighted(id)
    window.setTimeout(() => {
      setHighlighted((cur) => (cur === id ? null : cur))
    }, 1500)
  }

  if (error) {
    return (
      <div data-testid="public-draft-error" className="min-h-screen grid place-items-center bg-ink-50 p-6">
        <div className="max-w-md text-center">
          <AlertTriangle className="w-10 h-10 text-rose-600 mx-auto mb-3" />
          <h1 className="font-serif text-2xl text-ink-900">Enlace no disponible</h1>
          <p className="text-ink-600 mt-2 text-sm">{error}</p>
          <p className="text-ink-600 mt-4 text-xs">El link puede haber caducado o haber sido revocado por el despacho.</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen grid place-items-center bg-ink-50">
        <Loader2 className="w-6 h-6 text-ink-600 animate-spin" />
      </div>
    )
  }

  const { draft, case: caseInfo, watermark } = data

  return (
    <div data-testid="public-draft-page" className="min-h-screen bg-ink-50">
      <header className="bg-white border-b border-ink-200">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brand-600 grid place-items-center">
            <Scale className="w-4 h-4 text-white" />
          </div>
          <span className="font-serif text-xl font-semibold text-ink-900">Galaxy Legal</span>
          <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs border border-emerald-200">
            <ShieldCheck className="w-3 h-3" /> Citas verificadas por Galaxy Legal
          </span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 grid grid-cols-12 gap-6">
        <article className="col-span-12 lg:col-span-8">
          {watermark && (
            <div data-testid="public-watermark" className="mb-4 text-[10px] uppercase tracking-[0.2em] text-ink-600/70">
              {watermark}
            </div>
          )}
          <div className="mb-5">
            <h1 className="font-serif text-3xl text-ink-900">{draft.title || draft.tipo_documento}</h1>
            <div className="text-sm text-ink-600 mt-1">
              {caseInfo?.title}{caseInfo?.jurisdiccion ? ` · ${caseInfo.jurisdiccion}` : ''}{caseInfo?.materia ? ` · ${caseInfo.materia}` : ''}
              {' · '}v{draft.version}
              {draft.status === 'approved' ? ' · Aprobado' : ''}
            </div>
          </div>
          <div data-testid="public-draft-body" className="rounded-xl border border-ink-200 bg-white p-8 font-serif text-ink-900 leading-relaxed whitespace-pre-wrap">
            {renderWithMarkers(draft.content_md || '', evidenceMap, picked, focusEvidence)}
          </div>
        </article>
        <aside className="col-span-12 lg:col-span-4">
          <div className="sticky top-6">
            <div className="text-xs uppercase tracking-wider text-ink-600 mb-2">Evidencias ({(data.evidences || []).length})</div>
            <ul data-testid="public-evidences" className="space-y-2 max-h-[75vh] overflow-y-auto pr-1">
              {(data.evidences || []).map((e) => (
                <li
                  key={e.external_id}
                  ref={(el) => { if (el) evidenceRefs.current[e.external_id] = el }}
                  data-testid={`public-evidence-${e.external_id}`}
                  data-evidence-id={e.external_id}
                  className={`rounded-lg border p-3 text-sm bg-white transition-all duration-300 cursor-pointer ${
                    highlighted === e.external_id
                      ? 'border-amber-400 shadow-lg ring-2 ring-amber-300 bg-amber-50'
                      : picked === e.external_id
                        ? 'border-brand-500 shadow-sm'
                        : 'border-ink-200'
                  }`}
                  onClick={() => focusEvidence(e.external_id)}
                >
                  <div className="text-xs uppercase tracking-wider text-ink-600">
                    {e.external_id} · pág. {e.page ?? '—'} · párr. {e.paragraph ?? '—'}
                    {e.verified && <span className="ml-1 text-emerald-700 inline-flex items-center gap-1"><ShieldCheck className="w-3 h-3" />verificada</span>}
                  </div>
                  <div className="text-ink-900 italic mt-1">"{e.quote_excerpt}"</div>
                </li>
              ))}
              {(!data.evidences || data.evidences.length === 0) && <li className="text-sm text-ink-600">Sin evidencias adjuntas.</li>}
            </ul>
          </div>
        </aside>
      </main>
      <footer className="max-w-6xl mx-auto px-6 py-6 text-xs text-ink-600/70 text-center">
        Análisis generado por Galaxy Legal — cada cita ha sido validada como extracto literal del documento fuente.
        {data.expires_at && <> Este enlace caduca {new Date(data.expires_at).toLocaleString('es-ES')}.</>}
      </footer>
    </div>
  )
}

function renderWithMarkers(text, evidenceMap, picked, onPick) {
  if (!text) return null
  const parts = text.split(/(\[E:[A-Za-z0-9_-]+\])/g)
  return parts.map((p, i) => {
    const m = /^\[E:([A-Za-z0-9_-]+)\]$/.exec(p)
    if (!m) return <span key={i}>{p}</span>
    const id = m[1]
    const ev = evidenceMap[id]
    const ok = ev && ev.verified
    return (
      <button
        key={i}
        type="button"
        data-testid={`evidence-marker-${id}`}
        data-evidence-id={id}
        onClick={() => onPick(id)}
        title={ev ? `pág. ${ev.page ?? '—'} · párr. ${ev.paragraph ?? '—'}` : id}
        className={`mx-0.5 px-1 py-0.5 rounded text-[10px] font-mono cursor-pointer transition-colors ${
          picked === id
            ? 'bg-brand-600 text-white border border-brand-600'
            : ok
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:border-emerald-400'
              : 'bg-rose-50 text-rose-700 border border-rose-200'
        }`}
      >
        {id}
      </button>
    )
  })
}
