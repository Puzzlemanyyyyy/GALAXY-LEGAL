import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import LoginPage from './pages/LoginPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import CasePage from './pages/CasePage.jsx'
import DraftEditorPage from './pages/DraftEditorPage.jsx'
import PublicDraftPage from './pages/PublicDraftPage.jsx'
import PrivacyPage from './pages/PrivacyPage.jsx'
import TermsPage from './pages/TermsPage.jsx'
import AuthCallback from './pages/AuthCallback.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/public/drafts/:token" element={<PublicDraftPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/cases/:caseId" element={<CasePage />} />
          <Route path="/cases/:caseId/drafts/:draftId" element={<DraftEditorPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
