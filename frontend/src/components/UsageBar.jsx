import { useEffect, useState } from 'react'
import { Gauge } from 'lucide-react'
import { api } from '../lib/api'

export default function UsageBar() {
  const [u, setU] = useState(null)
  useEffect(() => {
    api.getUsage().then(setU).catch(() => setU(null))
  }, [])
  if (!u) return null
  // Defensive: if the API ever returns a partial payload (e.g. an upstream
  // 5xx surfaced through a fallback), don't crash the entire dashboard.
  const spent = Number(u.spent_usd ?? 0)
  const budget = Number(u.budget_usd ?? 0)
  const runCount = Number(u.run_count ?? 0)
  const month = u.month ?? '—'
  const pct = Math.min(100, Math.round((spent / Math.max(budget, 0.0001)) * 100))
  const color = u.over_budget ? 'bg-rose-500' : pct > 80 ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div data-testid="usage-bar" className="rounded-xl border border-ink-200 bg-white p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="inline-flex items-center gap-2 text-sm font-medium text-ink-900">
          <Gauge className="w-4 h-4 text-ink-600" />
          Consumo OpenAI · {month}
        </div>
        <div className="text-xs text-ink-600">{runCount} ejecuciones</div>
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span data-testid="usage-spent" className="text-xl font-serif text-ink-900">${spent.toFixed(4)}</span>
        <span className="text-xs text-ink-600">de ${budget.toFixed(2)}</span>
        {u.over_budget && <span className="ml-auto text-xs text-rose-700 font-medium">⚠ Presupuesto agotado</span>}
      </div>
      <div className="h-1.5 rounded-full bg-ink-100 overflow-hidden">
        <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
