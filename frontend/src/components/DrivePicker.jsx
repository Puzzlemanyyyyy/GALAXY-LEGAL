import { useEffect, useRef, useState } from 'react'
import { Loader2, FolderOpen, AlertTriangle } from 'lucide-react'
import { api } from '../lib/api'

const GIS_SCRIPT = 'https://accounts.google.com/gsi/client'
const GAPI_SCRIPT = 'https://apis.google.com/js/api.js'

const ACCEPTED_MIME = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.google-apps.document',
  'text/plain',
].join(',')

let _scriptCache = {}
function loadScript(src) {
  if (_scriptCache[src]) return _scriptCache[src]
  _scriptCache[src] = new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`)
    if (existing) { resolve(); return }
    const s = document.createElement('script')
    s.src = src; s.async = true; s.defer = true
    s.onload = () => resolve()
    s.onerror = () => reject(new Error(`Failed to load ${src}`))
    document.head.appendChild(s)
  })
  return _scriptCache[src]
}

export default function DrivePicker({ caseId, onImported }) {
  const [config, setConfig] = useState(null)            // {configured, apiKey, clientId, scope}
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState([])          // [{name, status, error?}]
  const [error, setError] = useState('')
  const tokenClientRef = useRef(null)
  const accessTokenRef = useRef(null)

  // 1. Fetch backend config (does the server have GOOGLE_CLIENT_ID?).
  useEffect(() => {
    let alive = true
    api.getDrivePickerConfig()
      .then((c) => { if (alive) setConfig(c) })
      .catch(() => { if (alive) setConfig({ configured: false }) })
    return () => { alive = false }
  }, [])

  // 2. Load GIS + gapi only if configured.
  useEffect(() => {
    if (!config?.configured) return
    let cancelled = false
    Promise.all([loadScript(GIS_SCRIPT), loadScript(GAPI_SCRIPT)])
      .then(() => new Promise((resolve, reject) => {
        // load picker module
        if (!window.gapi) { reject(new Error('gapi not loaded')); return }
        window.gapi.load('picker', { callback: resolve, onerror: reject })
      }))
      .then(() => {
        if (cancelled) return
        // Initialise the GIS token client (popup flow).
        tokenClientRef.current = window.google.accounts.oauth2.initTokenClient({
          client_id: config.clientId,
          scope: config.scope,
          prompt: '',  // empty = silent if user already consented this session
          callback: (tokenResponse) => {
            if (tokenResponse?.error) {
              setError(`Google: ${tokenResponse.error}`)
              setBusy(false)
              return
            }
            accessTokenRef.current = tokenResponse.access_token
            openPicker(tokenResponse.access_token)
          },
        })
        setReady(true)
      })
      .catch((err) => { if (!cancelled) setError(err.message || 'No se pudo cargar Google Drive') })
    return () => { cancelled = true }
  }, [config])

  const openPicker = (token) => {
    const view = new window.google.picker.DocsView(window.google.picker.ViewId.DOCS)
      .setIncludeFolders(false)
      .setSelectFolderEnabled(false)
      .setMimeTypes(ACCEPTED_MIME)
      .setMode(window.google.picker.DocsViewMode.LIST)

    const picker = new window.google.picker.PickerBuilder()
      .addView(view)
      .setOAuthToken(token)
      .setDeveloperKey(config.apiKey)
      .enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED)
      .setCallback((data) => onPickerCallback(data, token))
      .build()
    picker.setVisible(true)
  }

  const onPickerCallback = async (data, token) => {
    const Action = window.google.picker.Action
    if (!data || data.action === Action.CANCEL) { setBusy(false); return }
    if (data.action !== Action.PICKED) return

    const docs = (data.docs || []).map((d) => ({
      id: d.id,
      name: d.name,
      mimeType: d.mimeType,
    }))
    if (docs.length === 0) { setBusy(false); return }

    setProgress(docs.map((d) => ({ name: d.name, status: 'pending' })))
    await importBatch(docs, token)
  }

  const importBatch = async (docs, token) => {
    setBusy(true); setError('')
    setProgress(docs.map((d) => ({ name: d.name, status: 'uploading' })))
    try {
      const resp = await api.importFromDrive(caseId, docs, token)
      // Mark ok / dedupe
      const importedById = new Map((resp.imported || []).map((x) => [x.drive_id, x]))
      const errorById = new Map((resp.errors || []).map((x) => [x.drive_id, x]))
      setProgress(docs.map((d) => {
        const ok = importedById.get(d.id)
        const er = errorById.get(d.id)
        if (ok) return { name: d.name, status: ok.deduped ? 'deduped' : 'done' }
        if (er) return { name: d.name, status: 'error', error: er.error }
        return { name: d.name, status: 'pending' }
      }))
      ;(resp.imported || []).forEach((x) => onImported?.(x))
      setBusy(false)
    } catch (err) {
      // Detect DRIVE_TOKEN_EXPIRED → re-prompt + retry pending
      let detail = null
      try { detail = JSON.parse(err.message)?.detail || JSON.parse(err.message) } catch { /* ignore */ }
      const code = detail?.code
      if (code === 'DRIVE_TOKEN_EXPIRED') {
        const pending = (detail.pending || []).map((p) => ({ id: p.drive_id, name: p.name, mimeType: p.mimeType }))
        const imported = detail.imported || []
        setProgress((prev) => prev.map((p) => {
          const wasImported = imported.some((x) => x.filename === p.name)
          if (wasImported) return { ...p, status: 'done' }
          if (pending.some((x) => x.name === p.name)) return { ...p, status: 'reauth' }
          return p
        }))
        setError('La sesión de Google ha caducado. Re-autorizando…')
        // Force re-prompt: prompt='consent' guarantees fresh token
        tokenClientRef.current.requestAccessToken({ prompt: 'consent', hint: '' })
        // Stash pending so the next callback retries them
        // Implementation: replace token client callback for one-shot retry
        const original = tokenClientRef.current.callback
        tokenClientRef.current.callback = async (tokenResponse) => {
          tokenClientRef.current.callback = original
          if (tokenResponse?.error) { setError(`Google: ${tokenResponse.error}`); setBusy(false); return }
          accessTokenRef.current = tokenResponse.access_token
          if (pending.length > 0) {
            await importBatch(pending, tokenResponse.access_token)
          } else {
            setBusy(false)
          }
        }
        return
      }
      setError(err.message || 'Error importando de Drive')
      setBusy(false)
    }
  }

  const handleClick = () => {
    setError(''); setBusy(true)
    if (!tokenClientRef.current) { setError('Drive no inicializado'); setBusy(false); return }
    // requestAccessToken will trigger our callback → openPicker
    tokenClientRef.current.requestAccessToken({ prompt: '' })
  }

  // Hide entirely if backend says not configured
  if (!config) return null
  if (!config.configured) {
    return (
      <div data-testid="drive-picker-disabled" className="rounded-xl border border-dashed border-ink-200 p-3 text-xs text-ink-600 bg-white/50">
        <div className="flex items-center gap-2">
          <FolderOpen className="w-3.5 h-3.5" />
          <span>Conecta Drive: añade <code className="text-[10px]">GOOGLE_CLIENT_ID</code> + <code className="text-[10px]">GOOGLE_PICKER_API_KEY</code> al backend.</span>
        </div>
      </div>
    )
  }

  return (
    <div data-testid="drive-picker">
      <button
        data-testid="drive-picker-btn"
        onClick={handleClick}
        disabled={!ready || busy}
        className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-xl border border-ink-200 bg-white hover:border-brand-500/50 transition disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium text-ink-900"
      >
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderOpen className="w-4 h-4" />}
        {busy ? 'Importando…' : 'Importar de Google Drive'}
      </button>
      {error && (
        <div data-testid="drive-picker-error" className="mt-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-2 flex items-start gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {progress.length > 0 && (
        <ul data-testid="drive-picker-progress" className="mt-3 space-y-1.5">
          {progress.map((p, i) => (
            <li key={i} className="flex items-center justify-between text-xs px-3 py-1.5 rounded-lg bg-ink-50 border border-ink-200">
              <span className="truncate text-ink-900 mr-2">{p.name}</span>
              <span className={
                p.status === 'done' || p.status === 'deduped' ? 'text-emerald-700'
                : p.status === 'error'    ? 'text-rose-700'
                : p.status === 'uploading' ? 'text-brand-700'
                : p.status === 'reauth'   ? 'text-amber-700'
                : 'text-ink-600'
              }>
                {p.status === 'uploading' && <Loader2 className="inline w-3 h-3 mr-1 animate-spin" />}
                {p.status === 'done'    ? 'Importado'
                : p.status === 'deduped' ? 'Ya existía'
                : p.status === 'error'    ? (p.error || 'Error')
                : p.status === 'reauth'   ? 'Re-autorizando…'
                : p.status === 'uploading' ? 'Importando…' : 'En cola'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
