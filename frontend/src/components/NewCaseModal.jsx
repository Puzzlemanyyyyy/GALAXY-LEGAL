import { useState } from 'react'
import { X, Loader2 } from 'lucide-react'
import { api } from '../lib/api'

export default function NewCaseModal({ open, onClose, onCreated }) {
  const [title, setTitle] = useState('')
  const [reference, setReference] = useState('')
  const [jurisdiccion, setJurisdiccion] = useState('')
  const [materia, setMateria] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!open) return null

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const payload = { title, reference: reference || null, jurisdiccion: jurisdiccion || null, materia: materia || null, description: description || null }
      const created = await api.createCase(payload)
      onCreated?.(created)
      setTitle(''); setReference(''); setJurisdiccion(''); setMateria(''); setDescription('')
      onClose()
    } catch (err) {
      setError(err.message || 'Error al crear el expediente')
    } finally { setBusy(false) }
  }

  return (
    <div data-testid="new-case-modal" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-900/60 backdrop-blur-sm">
      <div className="relative w-full max-w-lg rounded-2xl bg-white border border-ink-200 shadow-2xl">
        <button data-testid="new-case-close-btn" onClick={onClose} className="absolute top-4 right-4 text-ink-600 hover:text-ink-900">
          <X className="w-5 h-5" />
        </button>
        <div className="px-7 pt-7 pb-6">
          <h2 className="font-serif text-2xl font-semibold text-ink-900">Nuevo expediente</h2>
          <p className="text-ink-600 text-sm mt-1">Crea un caso para empezar a indexar documentos.</p>
        </div>
        <form onSubmit={submit} className="px-7 pb-7 space-y-4">
          <Field label="Título *">
            <input data-testid="new-case-title" required value={title} onChange={(e) => setTitle(e.target.value)} className={inputCls} placeholder="Reclamación contra ACME S.A." />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Referencia interna">
              <input data-testid="new-case-reference" value={reference} onChange={(e) => setReference(e.target.value)} className={inputCls} placeholder="2026/042" />
            </Field>
            <Field label="Jurisdicción">
              <input data-testid="new-case-jurisdiccion" value={jurisdiccion} onChange={(e) => setJurisdiccion(e.target.value)} className={inputCls} placeholder="Civil España" />
            </Field>
          </div>
          <Field label="Materia">
            <input data-testid="new-case-materia" value={materia} onChange={(e) => setMateria(e.target.value)} className={inputCls} placeholder="Contratos" />
          </Field>
          <Field label="Descripción">
            <textarea data-testid="new-case-description" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} className={inputCls + ' resize-none'} placeholder="Resumen breve del caso (opcional)" />
          </Field>
          {error && <div data-testid="new-case-error" className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">{error}</div>}
          <div className="flex justify-end gap-2 pt-2">
            <button data-testid="new-case-cancel-btn" type="button" onClick={onClose} className="px-4 py-2.5 rounded-xl border border-ink-200 text-ink-900 hover:bg-ink-50">Cancelar</button>
            <button data-testid="new-case-submit-btn" type="submit" disabled={busy} className="px-4 py-2.5 rounded-xl bg-ink-900 text-white font-medium hover:bg-brand-700 transition disabled:opacity-60 inline-flex items-center gap-2">
              {busy && <Loader2 className="w-4 h-4 animate-spin" />}
              Crear expediente
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const inputCls = "w-full px-3 py-2.5 rounded-xl border border-ink-200 bg-white text-ink-900 placeholder:text-ink-600/50 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink-900">{label}</span>
      <div className="mt-1.5">{children}</div>
    </label>
  )
}
