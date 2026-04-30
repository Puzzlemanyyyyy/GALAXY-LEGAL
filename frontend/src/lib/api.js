// API client — wraps fetch, attaches the Supabase JWT, and parses JSON.
import { supabase } from './supabase'

const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function authHeader() {
  const { data } = await supabase.auth.getSession()
  const token = data?.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const headers = { ...(await authHeader()) }
  let payload = body
  if (body && !isForm) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const res = await fetch(`${BASE}/api${path}`, { method, headers, body: payload })
  if (res.status === 204) return null
  const text = await res.text()
  let data
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!res.ok) {
    const message = (data && data.detail) || res.statusText || 'Request failed'
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  return data
}

export const api = {
  // cases
  listCases:    () => request('/cases'),
  getCase:      (id) => request(`/cases/${id}`),
  createCase:   (body) => request('/cases', { method: 'POST', body }),
  updateCase:   (id, body) => request(`/cases/${id}`, { method: 'PATCH', body }),
  deleteCase:   (id) => request(`/cases/${id}`, { method: 'DELETE' }),

  // documents
  listDocuments: (caseId) => request(`/documents?case_id=${caseId}`),
  reindexDoc:    (id) => request(`/documents/${id}/reindex`, { method: 'POST' }),
  deleteDoc:     (id) => request(`/documents/${id}`, { method: 'DELETE' }),
  uploadDoc:     async (caseId, file) => {
    const fd = new FormData()
    fd.append('case_id', caseId)
    fd.append('file', file)
    return request('/documents/upload', { method: 'POST', body: fd, isForm: true })
  },

  // runs
  listRunTypes: () => request('/runs/types'),
  listRuns:     (caseId) => request(`/runs?case_id=${caseId}`),
  getRun:       (id) => request(`/runs/${id}`),
  startRun:     (case_id, workflow_type) => request('/runs', { method: 'POST', body: { case_id, workflow_type } }),
  getRunDraft:  (id) => request(`/runs/${id}/draft`),
  getRunEvidences: (id) => request(`/runs/${id}/evidences`),

  // drafts
  listDrafts:   (caseId) => request(`/drafts?case_id=${caseId}`),
  getDraft:     (id) => request(`/drafts/${id}`),
  saveRevision: (id, content_md, title) => request(`/drafts/${id}/revision`, { method: 'POST', body: { content_md, title } }),
  approveDraft: (id) => request(`/drafts/${id}/approve`, { method: 'POST' }),
  rejectDraft:  (id) => request(`/drafts/${id}/reject`, { method: 'POST' }),
  exportDocx:   (id) => request(`/drafts/${id}/export-docx`, { method: 'POST' }),

  // sharing
  shareDraft:   (id, body) => request(`/drafts/${id}/share`, { method: 'POST', body }),
  listShares:   (id) => request(`/drafts/${id}/shares`),
  revokeShare:  (token) => request(`/drafts/shares/${token}`, { method: 'DELETE' }),

  // usage
  getUsage:     () => request('/usage/current'),
}

// Public endpoint (no auth)
export async function getPublicDraft(token) {
  const res = await fetch(`${BASE}/api/public/drafts/${token}`)
  const text = await res.text()
  let data; try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!res.ok) throw new Error((data && data.detail) || res.statusText || 'Request failed')
  return data
}
