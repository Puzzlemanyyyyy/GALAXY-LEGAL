import { useRef, useState } from 'react'
import { UploadCloud, Loader2 } from 'lucide-react'
import { api } from '../lib/api'

export default function DocumentUpload({ caseId, onUploaded }) {
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState([])  // [{name, status, error?}]
  const [drag, setDrag] = useState(false)
  const inputRef = useRef(null)

  const accept = '.pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain'

  const handleFiles = async (files) => {
    const arr = Array.from(files || [])
    if (arr.length === 0) return
    setBusy(true)
    setProgress(arr.map((f) => ({ name: f.name, status: 'pending' })))
    for (let i = 0; i < arr.length; i++) {
      const f = arr[i]
      setProgress((prev) => prev.map((p, idx) => idx === i ? { ...p, status: 'uploading' } : p))
      try {
        const created = await api.uploadDoc(caseId, f)
        setProgress((prev) => prev.map((p, idx) => idx === i ? { ...p, status: 'done' } : p))
        onUploaded?.(created)
      } catch (err) {
        setProgress((prev) => prev.map((p, idx) => idx === i ? { ...p, status: 'error', error: err.message } : p))
      }
    }
    setBusy(false)
  }

  return (
    <div data-testid="document-upload">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handleFiles(e.dataTransfer.files) }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-5 text-center transition ${drag ? 'border-brand-500 bg-brand-50' : 'border-ink-200 bg-white hover:border-brand-500/40'}`}
      >
        <UploadCloud className="w-7 h-7 text-ink-600 mx-auto mb-2" />
        <div className="text-sm text-ink-900 font-medium">Subir documento</div>
        <div className="text-xs text-ink-600 mt-1">Arrastra PDF, DOCX o TXT (máx. 100 MB) o haz clic.</div>
        <input
          data-testid="document-upload-input"
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {progress.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {progress.map((p, i) => (
            <li key={i} className="flex items-center justify-between text-xs px-3 py-1.5 rounded-lg bg-ink-50 border border-ink-200">
              <span className="truncate text-ink-900 mr-2">{p.name}</span>
              <span className={
                p.status === 'done'      ? 'text-emerald-700'
                : p.status === 'error'   ? 'text-rose-700'
                : p.status === 'uploading' ? 'text-brand-700'
                : 'text-ink-600'
              }>
                {p.status === 'uploading' && <Loader2 className="inline w-3 h-3 mr-1 animate-spin" />}
                {p.status === 'done' ? 'Subido' : p.status === 'error' ? (p.error || 'Error') : p.status === 'uploading' ? 'Subiendo…' : 'En cola'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
