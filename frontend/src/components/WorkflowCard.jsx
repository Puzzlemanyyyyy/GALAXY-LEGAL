import { useState } from 'react'
import { Sparkles, Loader2, ArrowRight } from 'lucide-react'
import { api } from '../lib/api'

export default function WorkflowCard({ caseId, workflow, onStarted }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const start = async () => {
    setBusy(true); setError('')
    try {
      const run = await api.startRun(caseId, workflow.workflow_type)
      onStarted?.(run)
    } catch (err) { setError(err.message || 'No se pudo iniciar') }
    finally { setBusy(false) }
  }

  return (
    <div data-testid={`workflow-card-${workflow.workflow_type}`} className="rounded-xl border border-ink-200 bg-white p-4 hover:shadow-sm transition">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-brand-600/10 ring-1 ring-brand-500/30 grid place-items-center text-brand-700 shrink-0">
          <Sparkles className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-medium text-ink-900 leading-snug">{workflow.title}</div>
          <div className="text-xs text-ink-600 mt-0.5">{workflow.description || workflowSubtitle(workflow.workflow_type)}</div>
          <button
            data-testid={`workflow-run-${workflow.workflow_type}`}
            onClick={start}
            disabled={busy}
            className="mt-3 w-full inline-flex items-center justify-center gap-2 py-2 rounded-lg bg-ink-900 text-white text-sm font-medium hover:bg-brand-700 transition disabled:opacity-60"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Ejecutar <ArrowRight className="w-3.5 h-3.5" /></>}
          </button>
          {error && <div className="mt-2 text-xs text-rose-700">{error}</div>}
        </div>
      </div>
    </div>
  )
}

function workflowSubtitle(type) {
  switch (type) {
    case 'initial_analysis':       return 'Resumen, hechos y riesgos sobre los documentos indexados'
    case 'civil_demand':           return 'Estructura demanda civil: hechos, fundamentos, petitum'
    case 'fiscal_consultation':    return 'Consulta fiscal con citas a normativa'
    case 'jurisprudence_analysis': return 'Análisis de jurisprudencia interna del caso'
    default:                       return ''
  }
}
