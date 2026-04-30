import { useEffect, useState } from 'react'
import { X, Share2, Copy, Trash2, Loader2, ExternalLink } from 'lucide-react'
import { api } from '../lib/api'

const OPTIONS = [
  { value: '24h',   label: '24 horas' },
  { value: '7d',    label: '7 días' },
  { value: '30d',   label: '30 días' },
  { value: 'never', label: 'Sin expiración' },
]

export default function ShareDraftModal({ open, onClose, draft }) {
  const [expires, setExpires] = useState('7d')
  const [watermark, setWatermark] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [shares, setShares] = useState([])
  const [copied, setCopied] = useState(null)

  const publicBase = (import.meta.env.VITE_API_BASE_URL || window.location.origin).replace(/\/$/, '')

  const refresh = async () => {
    if (!draft) return
    try { setShares((await api.listShares(draft.id)) || []) } catch { setShares([]) }
  }
  useEffect(() => { if (open) refresh() }, [open, draft?.id])

  if (!open || !draft) return null

  const create = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await api.shareDraft(draft.id, { expires_in: expires, watermark: watermark || null })
      await refresh()
      setWatermark('')
    } catch (err) { setError(err.message || 'Error al crear el link') }
    finally { setBusy(false) }
  }

  const revoke = async (token) => {
    if (!confirm('¿Revocar este link? El destinatario ya no podrá verlo.')) return
    try { await api.revokeShare(token); await refresh() } catch (err) { setError(err.message) }
  }

  const copyLink = async (token) => {
    const url = `${publicBase}/public/drafts/${token}`
    try {
      await navigator.clipboard.writeText(url)
      setCopied(token); setTimeout(() => setCopied(null), 2000)
    } catch {
      prompt('Copia el enlace:', url)
    }
  }

  return (
    <div data-testid="share-draft-modal" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-900/60 backdrop-blur-sm">
      <div className="relative w-full max-w-xl rounded-2xl bg-white border border-ink-200 shadow-2xl">
        <button data-testid="share-close-btn" onClick={onClose} className="absolute top-4 right-4 text-ink-600 hover:text-ink-900">
          <X className="w-5 h-5" />
        </button>
        <div className="px-7 pt-7 pb-6">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-brand-600/10 ring-1 ring-brand-500/30 grid place-items-center text-brand-700">
              <Share2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="font-serif text-2xl font-semibold text-ink-900">Compartir análisis</h2>
              <p className="text-ink-600 text-sm">Genera un link público read-only con citas verificables.</p>
            </div>
          </div>
        </div>

        <form onSubmit={create} className="px-7 pb-6 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm font-medium text-ink-900">Expiración</span>
              <select data-testid="share-expires-select" value={expires} onChange={(e) => setExpires(e.target.value)} className="mt-1.5 w-full px-3 py-2.5 rounded-xl border border-ink-200 bg-white text-ink-900 focus:outline-none focus:ring-2 focus:ring-brand-500">
                {OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-ink-900">Watermark (opcional)</span>
              <input data-testid="share-watermark-input" value={watermark} onChange={(e) => setWatermark(e.target.value)} placeholder="Despacho XYZ" className="mt-1.5 w-full px-3 py-2.5 rounded-xl border border-ink-200 bg-white text-ink-900 placeholder:text-ink-600/50 focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </label>
          </div>
          {error && <div data-testid="share-error" className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">{error}</div>}
          <button data-testid="share-submit-btn" type="submit" disabled={busy} className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-xl bg-ink-900 text-white font-medium hover:bg-brand-700 transition disabled:opacity-60">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Share2 className="w-4 h-4" />}
            Generar nuevo link
          </button>
        </form>

        <div className="px-7 pb-7">
          <div className="text-xs uppercase tracking-wider text-ink-600 mb-2">Links activos ({shares.length})</div>
          <ul data-testid="share-list" className="space-y-2 max-h-64 overflow-y-auto">
            {shares.length === 0 && <li className="text-sm text-ink-600">Ningún link generado todavía.</li>}
            {shares.map((s) => (
              <li key={s.token} data-testid={`share-row-${s.token}`} className="rounded-lg border border-ink-200 bg-ink-50 p-3 text-sm">
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-mono text-xs text-ink-900 truncate">{publicBase}/public/drafts/{s.token}</div>
                    <div className="text-xs text-ink-600 mt-1">
                      {s.expires_at ? `Expira ${new Date(s.expires_at).toLocaleString('es-ES')}` : 'Sin expiración'} · {s.view_count} vistas
                      {s.watermark ? ` · watermark "${s.watermark}"` : ''}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <a data-testid={`share-open-${s.token}`} href={`${publicBase}/public/drafts/${s.token}`} target="_blank" rel="noreferrer" className="p-1.5 rounded hover:bg-ink-100 text-ink-600" title="Abrir en nueva pestaña">
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                    <button data-testid={`share-copy-${s.token}`} onClick={() => copyLink(s.token)} className="p-1.5 rounded hover:bg-ink-100 text-ink-600" title="Copiar">
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                    <button data-testid={`share-revoke-${s.token}`} onClick={() => revoke(s.token)} className="p-1.5 rounded hover:bg-rose-50 text-rose-700" title="Revocar">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                {copied === s.token && <div className="mt-1.5 text-xs text-emerald-700">Link copiado al portapapeles.</div>}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
