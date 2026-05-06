import { Link } from 'react-router-dom'
import { Scale, ArrowLeft } from 'lucide-react'

export default function TermsPage() {
  return (
    <div data-testid="terms-page" className="min-h-screen bg-ink-50">
      <header className="bg-white border-b border-ink-200">
        <div className="max-w-3xl mx-auto px-6 h-16 flex items-center gap-3">
          <Link to="/" className="text-ink-600 hover:text-ink-900 inline-flex items-center gap-1.5 text-sm">
            <ArrowLeft className="w-4 h-4" /> Volver
          </Link>
          <div className="ml-auto flex items-center gap-2">
            <Scale className="w-5 h-5 text-brand-600" />
            <span className="font-serif text-xl font-semibold text-ink-900">Galaxy Legal</span>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12 prose prose-ink">
        <h1 className="font-serif text-4xl text-ink-900">Términos y condiciones</h1>
        <p className="text-sm text-ink-600">Última actualización: 4 de mayo de 2026</p>

        <h2>1. Aceptación</h2>
        <p>
          El uso de Galaxy Legal implica la aceptación íntegra de estos términos. Si no está de acuerdo con alguno de
          ellos, debe abstenerse de utilizar el servicio.
        </p>

        <h2>2. Descripción del servicio</h2>
        <p>
          Galaxy Legal es una plataforma SaaS de asistencia documental para profesionales del derecho. Permite cargar
          expedientes (PDF, DOCX, TXT) y generar borradores de escritos legales mediante modelos de inteligencia
          artificial, con la garantía de que cada cita textual presente en el borrador es <em>verbatim</em> respecto a
          los documentos cargados por el usuario.
        </p>

        <h2>3. Naturaleza del resultado y limitación de responsabilidad</h2>
        <p>
          <strong>Galaxy Legal NO presta servicios jurídicos.</strong> Los borradores generados son
          <em> herramientas de apoyo profesional</em> y deben ser revisados, validados y firmados por un abogado o
          profesional habilitado antes de cualquier uso ante terceros u organismos públicos. La responsabilidad
          deontológica y profesional sobre los escritos finalmente presentados recae <strong>exclusivamente</strong>
          sobre el profesional que los suscriba.
        </p>
        <p>
          La IA puede contener errores, omisiones o citas incompletas en lo relativo a normativa o jurisprudencia
          que <em>no</em> figure en los documentos del expediente cargado. La validación verbatim solo cubre las citas
          a documentos del propio expediente del usuario.
        </p>

        <h2>4. Obligaciones del usuario</h2>
        <ul>
          <li>El usuario garantiza ser titular o tener autorización para tratar los documentos que sube.</li>
          <li>El usuario se compromete a no cargar documentos que contengan datos especialmente protegidos (art. 9 RGPD) sin contar con base jurídica suficiente y, en su caso, las medidas reforzadas de seguridad pertinentes.</li>
          <li>El usuario es responsable de la confidencialidad de sus credenciales de acceso.</li>
          <li>Queda prohibido el <em>scraping</em>, ingeniería inversa o uso del servicio para entrenar modelos competidores.</li>
        </ul>

        <h2>5. Propiedad intelectual</h2>
        <p>
          La titularidad de los documentos cargados y de los borradores generados pertenece al usuario. Galaxy Legal
          únicamente almacena y procesa dichos contenidos en cumplimiento del contrato de servicio. La plataforma,
          su código, marca, diseño y demás elementos son propiedad de Galaxy Legal y están protegidos por la
          legislación de propiedad intelectual e industrial.
        </p>

        <h2>6. Precio y forma de pago</h2>
        <p>
          [Pendiente de definir el plan comercial. Esta sección se actualizará cuando se active la facturación.]
        </p>

        <h2>7. Suspensión y baja</h2>
        <p>
          El usuario puede dar de baja su cuenta en cualquier momento desde la sección de ajustes (cuando esté
          disponible) o solicitándolo a <strong>support@galaxylegal.es</strong>. Galaxy Legal podrá suspender el
          servicio por incumplimiento de estos términos previa comunicación con plazo razonable, salvo en casos de
          actividad ilícita o riesgo grave de seguridad.
        </p>

        <h2>8. Ley aplicable y jurisdicción</h2>
        <p>
          Estas condiciones se rigen por la legislación española. Para cualquier controversia derivada del uso del
          servicio, las partes se someten a los Juzgados y Tribunales de <strong>[ciudad sede del titular]</strong>,
          salvo que la normativa de consumidores establezca otro fuero imperativo.
        </p>

        <hr />
        <p className="text-xs text-ink-600">
          <strong>Aviso al usuario implementador</strong>: igual que la política de privacidad, este texto es una
          plantilla. Antes de publicar revíselo con un letrado para ajustarlo a su modelo de negocio (B2B vs B2C),
          su política de precios y la jurisdicción de su sede.
        </p>
      </main>
    </div>
  )
}
