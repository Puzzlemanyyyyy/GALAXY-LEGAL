import { Link } from 'react-router-dom'
import { Scale, ArrowLeft } from 'lucide-react'

export default function PrivacyPage() {
  return (
    <div data-testid="privacy-page" className="min-h-screen bg-ink-50">
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
        <h1 className="font-serif text-4xl text-ink-900">Política de privacidad</h1>
        <p className="text-sm text-ink-600">Última actualización: 4 de mayo de 2026</p>

        <h2>1. Responsable del tratamiento</h2>
        <p>
          Galaxy Legal (en adelante, "el Servicio") es operado por <strong>[Nombre del titular o sociedad]</strong>,
          con domicilio en <strong>[dirección postal completa]</strong> y CIF/NIF <strong>[número]</strong>.
          Para cualquier cuestión relativa a esta política, puede escribirnos a
          <strong> privacy@galaxylegal.es</strong>.
        </p>

        <h2>2. Datos personales tratados</h2>
        <ul>
          <li><strong>Identificación</strong>: dirección de correo electrónico utilizada para el acceso por enlace mágico.</li>
          <li><strong>Documentación legal subida</strong>: contratos, escritos, sentencias y demás documentos que el usuario decida cargar para su análisis.</li>
          <li><strong>Datos técnicos</strong>: dirección IP en el momento del login (anonimizada a /24 tras 30 días), user-agent, fecha/hora de las acciones para el registro de auditoría.</li>
          <li><strong>Telemetría de uso</strong>: identificadores de expediente, ejecución y borrador. <em>No</em> registramos cookies de seguimiento ni analítica de terceros.</li>
        </ul>

        <h2>3. Finalidad y base legal</h2>
        <p>
          Tratamos sus datos para <strong>prestar el servicio contratado</strong> (análisis legal asistido por IA con
          validación verbatim de citas) y <strong>cumplir las obligaciones legales</strong> aplicables. La base
          jurídica es la ejecución del contrato de servicio (art. 6.1.b RGPD) y el cumplimiento de obligaciones
          legales tributarias, mercantiles y de prevención del blanqueo (art. 6.1.c RGPD).
        </p>

        <h2>4. Plazo de conservación</h2>
        <ul>
          <li><strong>Documentos del expediente</strong>: durante toda la vigencia de la cuenta y, tras su baja, durante el plazo legal de prescripción aplicable (mínimo 5 años en materia mercantil).</li>
          <li><strong>Logs de auditoría</strong>: 6 años, conforme al art. 30.1 RGPD.</li>
          <li><strong>IP de login</strong>: 12 meses; tras ese plazo se anonimiza.</li>
        </ul>

        <h2>5. Encargados de tratamiento</h2>
        <p>
          Para prestar el servicio recurrimos a los siguientes encargados, todos ellos con acuerdo de tratamiento
          conforme al art. 28 RGPD:
        </p>
        <ul>
          <li><strong>Supabase</strong> (Supabase Inc., USA — datos almacenados en región <em>eu-west-3</em>, París): hosting de base de datos, autenticación y almacenamiento de archivos.</li>
          <li><strong>OpenAI</strong> (OpenAI LLC, USA): generación de texto y embeddings. <em>No</em> entrenamos modelos con sus datos — la API se llama con la opción <code>data_retention=zero</code> donde aplica.</li>
          <li><strong>Google</strong> (Google LLC, USA): solo si el usuario decide importar archivos desde Google Drive. Acceso limitado al alcance <code>drive.file</code> (únicamente los archivos que usted seleccione expresamente en el Picker).</li>
          <li><strong>Railway</strong> (Railway Corp., USA): hosting del servicio de aplicación.</li>
        </ul>
        <p>
          Las transferencias internacionales fuera del EEE se rigen por las <strong>Cláusulas Contractuales Tipo</strong>
          aprobadas por la Comisión Europea (Decisión 2021/914) y por las correspondientes evaluaciones de impacto
          en transferencias.
        </p>

        <h2>6. Cifrado y seguridad</h2>
        <ul>
          <li>Los documentos se almacenan cifrados en reposo (AES-256) en buckets privados de Supabase Storage.</li>
          <li>Las comunicaciones cliente-servidor van por HTTPS (TLS 1.3).</li>
          <li>El control de acceso es por <em>Row Level Security</em> a nivel de base de datos: cada usuario solo puede leer sus propios expedientes.</li>
          <li>Las claves de servicio (Supabase service-role, OpenAI) se gestionan como secretos en el proveedor de despliegue y nunca aparecen en el repositorio.</li>
        </ul>

        <h2>7. Sus derechos</h2>
        <p>
          Puede ejercer en cualquier momento los derechos de acceso, rectificación, supresión, oposición, limitación
          y portabilidad enviando un correo a <strong>privacy@galaxylegal.es</strong>, adjuntando copia del DNI o
          documento equivalente. Atenderemos su solicitud en plazo máximo de un mes.
        </p>
        <p>
          Si considera que el tratamiento no se ajusta a la normativa, puede presentar reclamación ante la
          <strong> Agencia Española de Protección de Datos</strong> (AEPD, <a href="https://www.aepd.es" target="_blank" rel="noreferrer">www.aepd.es</a>).
        </p>

        <h2>8. No tomamos decisiones automatizadas</h2>
        <p>
          La IA de Galaxy Legal genera <em>borradores</em> de documentos legales que requieren <strong>siempre</strong>
          la revisión y aprobación de un profesional humano. Ningún borrador adquiere valor jurídico hasta que el
          usuario lo aprueba expresamente. No realizamos elaboración de perfiles ni decisiones automatizadas con
          efectos legales en el sentido del art. 22 RGPD.
        </p>

        <h2>9. Modificaciones</h2>
        <p>
          Podemos actualizar esta política para reflejar cambios legales o del servicio. Los cambios sustanciales le
          serán notificados por correo con al menos 15 días de antelación.
        </p>

        <hr />
        <p className="text-xs text-ink-600">
          <strong>Aviso al usuario implementador</strong>: este texto es una plantilla de partida. Antes de publicar la
          aplicación a clientes reales debe sustituir los datos del responsable, revisar con su abogado las cláusulas
          aplicables a su caso concreto (especialmente si presta servicios a despachos sujetos a secreto profesional)
          y ajustar los plazos de conservación a su política interna.
        </p>
      </main>
    </div>
  )
}
