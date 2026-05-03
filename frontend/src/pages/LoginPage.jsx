import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Scale, Mail, ArrowRight, Loader2, ShieldCheck, FileText, Sparkles } from 'lucide-react'
import { supabase } from '../lib/supabase'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('idle') // idle | sending | sent | error
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const sendMagicLink = async (e) => {
    e.preventDefault()
    if (!email) return
    setStatus('sending')
    setError('')
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    })
    if (error) { setStatus('error'); setError(error.message) }
    else setStatus('sent')
  }

  return (
    <div data-testid="login-page" className="min-h-screen w-full grid lg:grid-cols-2 bg-gradient-to-br from-ink-50 via-white to-brand-50">
      {/* LEFT: brand panel */}
      <aside className="relative hidden lg:flex flex-col justify-between p-12 bg-gradient-to-br from-ink-900 via-brand-900 to-ink-900 text-white overflow-hidden">
        <div className="absolute inset-0 opacity-20" style={{
          backgroundImage: 'radial-gradient(circle at 30% 20%, #6366f1 0%, transparent 40%), radial-gradient(circle at 80% 80%, #d4a157 0%, transparent 35%)'
        }} />
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-gold-500/20 ring-1 ring-gold-400/40 grid place-items-center">
              <Scale className="w-6 h-6 text-gold-400" />
            </div>
            <div>
              <div className="font-serif text-2xl font-semibold tracking-tight">Galaxy Legal</div>
              <div className="text-xs text-ink-200/70 tracking-wider uppercase">AI legal workspace</div>
            </div>
          </div>
        </div>

        <div className="relative space-y-8">
          <h1 className="font-serif text-5xl leading-tight text-balance">
            El despacho que <em className="text-gold-400 not-italic">no inventa</em>.
          </h1>
          <p className="text-ink-100/80 text-lg max-w-md leading-relaxed">
            Conecta tus expedientes desde Google Drive. Genera demandas, recursos y
            consultas fiscales con cada cita verificada contra el documento original.
          </p>

          <div className="space-y-4 pt-2">
            <Feature icon={<ShieldCheck className="w-5 h-5" />} title="Cero alucinaciones" text="Cada afirmación enlazada a documento, página y párrafo." />
            <Feature icon={<FileText className="w-5 h-5" />} title="Borradores trazables" text="Versionado, diff y revisión humana obligatoria." />
            <Feature icon={<Sparkles className="w-5 h-5" />} title="Workflows acotados" text="Demanda civil, consulta fiscal, jurisprudencia." />
          </div>
        </div>

        <div className="relative text-xs text-ink-200/50">
          © {new Date().getFullYear()} Galaxy Legal · Datos en eu-west-3 · RGPD compliant
        </div>
      </aside>

      {/* RIGHT: login form */}
      <main className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <div className="w-10 h-10 rounded-xl bg-brand-600 grid place-items-center">
              <Scale className="w-5 h-5 text-white" />
            </div>
            <span className="font-serif text-2xl font-semibold text-ink-900">Galaxy Legal</span>
          </div>

          <h2 className="font-serif text-3xl sm:text-4xl text-ink-900 font-semibold mb-2">Acceder</h2>
          <p className="text-ink-600 mb-8">
            Recibe un enlace mágico por correo. Sin contraseñas, sin terceros.
          </p>

          {status === 'sent' ? (
            <div data-testid="magic-link-sent-banner" className="rounded-xl border border-emerald-200 bg-emerald-50 p-6">
              <div className="font-medium text-emerald-900">Enlace enviado a {email}</div>
              <div className="text-sm text-emerald-800/80 mt-1">
                Revisa tu correo. El enlace expira en 1 hora.
              </div>
              <button data-testid="use-another-email-btn" onClick={() => setStatus('idle')} className="mt-4 text-sm text-emerald-900 underline">
                Usar otro correo
              </button>
            </div>
          ) : (
            <>
              <form data-testid="magic-link-form" onSubmit={sendMagicLink} className="space-y-4">
                <label className="block">
                  <span className="text-sm font-medium text-ink-900">Correo electrónico</span>
                  <div className="mt-1.5 relative">
                    <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-600" />
                    <input
                      data-testid="login-email-input"
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="abogado@despacho.es"
                      className="w-full pl-10 pr-3 py-3 rounded-xl border border-ink-200 bg-white text-ink-900 placeholder:text-ink-600/50 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                    />
                  </div>
                </label>

                <button
                  data-testid="send-magic-link-btn"
                  type="submit"
                  disabled={status === 'sending'}
                  className="w-full inline-flex items-center justify-center gap-2 py-3 rounded-xl bg-ink-900 text-white font-medium hover:bg-brand-700 transition disabled:opacity-60"
                >
                  {status === 'sending' ? <Loader2 className="w-4 h-4 animate-spin" /> : <>
                    Enviar enlace mágico <ArrowRight className="w-4 h-4" />
                  </>}
                </button>
              </form>

              {error && (
                <div data-testid="login-error-banner" className="mt-4 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">
                  {error}
                </div>
              )}
            </>
          )}

          <p className="mt-10 text-xs text-ink-600 leading-relaxed">
            Al continuar aceptas que Galaxy Legal procese tus datos según el RGPD. Los
            documentos legales se cifran en reposo y solo son accesibles por ti.
          </p>
        </div>
      </main>
    </div>
  )
}

function Feature({ icon, title, text }) {
  return (
    <div className="flex gap-3">
      <div className="w-9 h-9 rounded-lg bg-white/10 ring-1 ring-white/15 grid place-items-center text-gold-400 shrink-0">{icon}</div>
      <div>
        <div className="font-medium text-white">{title}</div>
        <div className="text-sm text-ink-200/70">{text}</div>
      </div>
    </div>
  )
}
