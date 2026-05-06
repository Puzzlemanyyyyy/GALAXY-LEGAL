# Galaxy Legal — Manual de usuario

> Versión 0.5 · Fase 2(b) cerrada · Drive Picker + páginas legales añadidos
> Última actualización: 4 de mayo de 2026

Este manual es para abogados y operadores del despacho. Si eres desarrollador, mira `docs/CURRENT_STATE.md`.

---

## 0. Acceder por primera vez

1. Abre la URL del servicio.
   - Preview de desarrollo: `https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com`
   - Producción Railway: pendiente de Fase 2(c)
2. Te recibe la pantalla **Acceder**. Dos opciones:
   - **Enlace mágico** (recomendado): introduce tu email → revisa tu correo → haz clic en el enlace → entras al panel sin contraseña. El enlace caduca a la hora.
   - **Contraseña** (solo cuentas internas/test): pulsa el enlace pequeño *"¿Tienes contraseña? Acceder con contraseña"* y mete usuario + contraseña.
3. La primera vez te crea automáticamente un perfil vacío. No hay onboarding, no hay tarjeta de crédito, no hay verificación de email manual.

---

## 1. Concepto base — el "expediente" como unidad de trabajo

Toda la app se estructura en torno a **expedientes** (cases). Un expediente equivale a un asunto/caso de un cliente. Dentro de un expediente puedes:

- Subir N **documentos** (contratos, escritos, sentencias, correspondencia).
- Lanzar N **ejecuciones** (runs) de los workflows de IA disponibles.
- Producir N **borradores** (drafts) de escritos legales con versionado y aprobación humana obligatoria.

Los expedientes son **privados por usuario**: nadie excepto tú ve los tuyos (control de acceso a nivel de fila en la base de datos).

---

## 2. Dashboard

Al entrar verás:

| Elemento | Función |
|---|---|
| Cabecera | Tu email + botón **Salir**. |
| Tarjeta *Consumo OpenAI* | Cuánto llevas gastado este mes vs el límite ($50). Verde <80%, ámbar 80-100%, rojo si lo superas (la app bloquea nuevas ejecuciones con HTTP 402). |
| Lista de Expedientes | Tus casos. Vacía la primera vez. |
| Botón **+ Nuevo expediente** | Crea uno nuevo. |

### 2.1 Crear expediente

Pulsa **+ Nuevo expediente**. Modal con:

- **Título**: `Reclamación cantidad — ACME vs Beta` (libre, lo verás en la lista).
- **Jurisdicción**: `civil`, `penal`, `fiscal`, `contencioso`, `mercantil`, `laboral`...
- **Materia**: `reclamación de cantidad`, `despido improcedente`, `IVA-IRPF`, etc.

Crea → te redirige a la página del expediente.

---

## 3. Página del expediente — 3 columnas

### 3.1 Columna izquierda — Documentos

**Cómo subir**:

- **Drag & drop o clic** sobre el rectángulo "Subir documento". Acepta PDF, DOCX, TXT (máx. 25 MB).
- **Importar de Google Drive** (si tu administrador ha configurado las credenciales de Google):
  1. Pulsa *Importar de Google Drive*.
  2. Si es la primera vez, Google te pide consentimiento para que la app vea **solo los archivos que tú selecciones** (alcance `drive.file`, no toca el resto de tu Drive).
  3. Aparece el Picker de Google. Selecciona uno o varios archivos (no carpetas — el Picker está bloqueado para forzar selección individual).
  4. Pulsa *Select*. La app descarga, deduplica por SHA-256 y procesa.

**Estados de un documento**:

- `indexando` (anaranjado): se está extrayendo texto y generando embeddings. ~5-30 segundos según tamaño.
- `listo` (verde): disponible para que los workflows lo usen.
- `error` (rojo): el archivo está corrupto, protegido con contraseña o el formato no es compatible. Puedes pulsar *Reindexar* para reintentarlo o eliminarlo.

**Deduplicación**: si subes el mismo archivo dos veces (mismo SHA-256), la segunda subida no crea un duplicado, te devuelve la referencia al original. Lo verás como `Ya existía` en el caso de Drive.

### 3.2 Columna central — Borradores (drafts)

Lista de los borradores que han producido los workflows. Cada uno con:

- Tipo (`Análisis inicial`, `Demanda civil`, `Consulta fiscal`, `Análisis jurisprudencia`).
- Versión (`v1`, `v2`...).
- Estado (`draft`, `in_review`, `approved`, `exported`, `rejected`).

Click en un borrador → te lleva al **Editor de borrador** (sección 4).

### 3.3 Columna derecha — Workflows y ejecuciones

**Tarjetas de workflow** disponibles:

| Workflow | Para qué sirve | Tiempo aprox. | Coste aprox. |
|---|---|---|---|
| **Análisis inicial** | Extrae hechos clave + bandera de riesgos. Es lo primero que se suele lanzar para entender el caso. | 20-40 s | ~$0.01 |
| **Demanda civil** | Genera demanda completa: encabezamiento, hechos numerados (cada uno con cita verbatim), fundamentos de derecho, petitum, otrosíes. | 60-90 s | ~$0.04-0.08 |
| **Consulta fiscal** | Informe estructurado: planteamiento, cuestiones, normativa aplicable, análisis, implicaciones, riesgos, conclusión. | 60-90 s | ~$0.03-0.06 |
| **Análisis jurisprudencia** | Busca jurisprudencia favorable y contraria DENTRO de los documentos del expediente. *No consulta CENDOJ todavía.* | 40-60 s | ~$0.02-0.04 |

**Cómo ejecutar**:

1. Asegúrate de tener al menos 1 documento `listo`.
2. Pulsa **Ejecutar** en la tarjeta del workflow.
3. Aparece una fila nueva en *Ejecuciones* con estado `running`.
4. Espera. La página se refresca sola cada 3.5 s mientras haya algo en marcha.
5. Cuando pase a `completed`, automáticamente aparece un draft nuevo en la columna central.

### 3.4 Estados de las ejecuciones

| Estado | Significado |
|---|---|
| `queued` | En cola, todavía sin empezar. |
| `running` | LLM trabajando. |
| `completed` | OK. Draft generado y citas validadas. |
| `needs_human` | **El validador anti-fantasma cazó una cita parafraseada.** El sistema rechazó generar el draft porque alguna cita no coincide verbatim con el documento original. **Lanza otra ejecución** — suele acertar al segundo intento. Si pasa repetidamente, revisa que los documentos del expediente sean adecuados. |
| `failed` | Error técnico (timeout, error de API, etc.). |

---

## 4. Editor de borrador

Click en un draft → editor en dos paneles.

### 4.1 Panel principal — el texto

Renderizado en Markdown:
- `# H1`, `## H2`, `### H3` para encabezados.
- `**negrita**`, `*cursiva*`.
- `- elemento` para listas.
- Marcadores `[E:e001]`, `[E:e002]`... son **citas verificables**. Pasa el ratón → tooltip con la página y párrafo del documento original. Click → resalta la fila correspondiente en el panel de evidencias.

### 4.2 Panel lateral — Evidencias

Lista todas las citas. Cada una muestra:
- Documento de origen.
- Página y párrafo.
- `quote_excerpt`: el texto literal extraído del documento (lo que la cita refleja en el draft).
- Badge **VERIFICADA** en verde si el validador confirmó la coincidencia verbatim.

### 4.3 Acciones del editor

| Acción | Qué hace |
|---|---|
| **Editar** | Permite modificar el texto. Si introduces marcadores `[E:xxx]` que no existen, al guardar el sistema los marca como `unverified_markers`. |
| **Guardar revisión** | Crea v2 (o v3, etc.) a partir del actual con tus cambios. Calcula diff con el anterior. Re-valida que tus citas siguen cuadrando. |
| **Aprobar** | Marca el borrador como `approved`. **Después de aprobar, el contenido se vuelve inmutable** (un trigger de base de datos bloquea cualquier modificación a `content_md`). Si quieres cambiar algo, hay que crear una revisión NUEVA antes de aprobarla. Si hay errores de validación pendientes, devuelve 422 y no aprueba. |
| **Rechazar** | Marca como `rejected`. No genera nada nuevo. Queda en historial para auditoría. |
| **Exportar DOCX** | Genera un `.docx` con headings, listas y formato. Te devuelve un link de descarga firmado válido **1 hora**. Cuando exportas, el campo `exported_at` se actualiza para que la UI sepa que ya hubo descarga. |
| **Compartir** | Abre el modal de share (sección 5). |

---

## 5. Compartir un borrador con un cliente

En el editor, botón **Compartir** → modal:

| Campo | Opciones |
|---|---|
| Expiración | `24h`, `7 días`, `30 días`, `nunca` |
| Watermark (opcional) | Texto que aparecerá como sello en cabecera del link público. Ej: `Despacho XYZ - Confidencial` |

**Pulsa Crear** → te genera un link tipo:
```
https://<tu-dominio>/public/drafts/<token-uuid>
```

**Cópialo y mándalo al cliente** (email, WhatsApp, lo que sea).

### 5.1 Lo que ve el cliente al abrir el link

- **Sin login**. El link funciona en navegador anónimo / incógnito.
- **Banner verde** arriba: *"Citas verificadas por Galaxy Legal"*.
- **Watermark** del despacho (si lo configuraste).
- **El borrador entero** con marcadores `[E:xxx]` clicables.
- **Panel lateral** con las evidencias verificadas — al hacer clic en un marcador, la fila correspondiente del panel se resalta en ámbar 1.5s y hace scroll.
- **Footer** con la fecha de expiración del enlace.

### 5.2 Lo que tú ves en el panel del despacho

En el editor, debajo del modal, aparecen los links activos con:
- Token (puedes copiar el link otra vez).
- Fecha de expiración.
- **Contador de visualizaciones** (`view_count`) y `last_viewed_at` (cuándo fue la última vez que el cliente lo abrió).
- Botón **Revocar** → invalida el link inmediatamente. Si el cliente lo tiene abierto y refresca, ve un error.

### 5.3 Demo público

Para enseñar a alguien sin darle acceso a tu cuenta, usa el link demo activo:
```
https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/public/drafts/4a1d042b-9f35-4cc0-a98a-1cde263be263
```

---

## 6. Garantías técnicas que puedes vender

Cuando enseñes esto a un colega de despacho, los puntos diferenciales son:

1. **Anti-fantasma verificado en producción**: 81/81 evidencias verbatim-verified contra documentos de origen. Cuando la IA intenta parafrasear una cita, el sistema rechaza el borrador en lugar de pasártelo con un error oculto.
2. **Trazabilidad**: cada acción (ejecución, edición, aprobación, exportación, compartir) queda en el log de auditoría. Plazo de retención 6 años conforme RGPD.
3. **Inmutabilidad post-aprobación**: una vez apruebas un borrador, ni tú puedes cambiarlo. Si necesitas modificarlo, hay que crear v2 (que será una revisión nueva, también auditable).
4. **Cifrado en reposo y en tránsito**: AES-256 + HTTPS TLS 1.3.
5. **Soberanía RGPD**: datos almacenados en `eu-west-3` (París). Cláusulas tipo de la Comisión Europea para los proveedores fuera del EEE.
6. **No entrenamos con tus datos**: la API de OpenAI se llama con la opción de no retención.

---

## 7. Lo que NO hace todavía (sé honesto con tus clientes)

| Funcionalidad | Estado | Cuándo |
|---|---|---|
| Importar de Google Drive | ✅ Implementado, requiere credenciales del admin | Ya |
| Deploy en dominio propio (Railway) | 🟡 En backlog | Fase 2(c), siguiente sesión |
| Validar citas a artículos del CC, CP, etc. contra el BOE | ❌ NO | Fase 3a |
| Validar citas a sentencias del TS contra CENDOJ | ❌ NO | Fase 3a |
| Conectar con Eur-Lex (derecho UE) | ❌ NO | Fase 3b |
| vLex / Aranzadi / Tirant | ❌ NO | Fase 3c, requiere licencia comercial |
| Transcripción de juicios (audio → texto) | ❌ NO | Backlog |
| Multi-tenant (varios usuarios por despacho) | ❌ NO | Backlog |
| Facturación al cliente final (Stripe) | ❌ NO | Backlog |

**Importante**: las citas a normativa española y jurisprudencia que aparezcan en los borradores **vienen del entrenamiento del LLM**, no de una fuente verificada. **Solo las citas a documentos del propio expediente están validadas verbatim.** Hasta que se complete Fase 3, revisa siempre con tu propia documentación las referencias a leyes y sentencias antes de presentar un escrito.

---

## 8. Cuestiones frecuentes

**¿Por qué un workflow se queda en `needs_human`?**
Porque el LLM intentó pasar una cita parafraseada y el validador la rechazó. Lánzalo otra vez. Si pasa repetidamente, los documentos del expediente probablemente no contienen la información necesaria para el tipo de escrito que pides — añade más documentos relevantes.

**¿Cuánto cuesta cada ejecución?**
Entre $0.01 (análisis inicial pequeño) y $0.08 (demanda civil con expediente grande). Lo ves en la columna *Ejecuciones* después de que termine. El presupuesto mensual por defecto es $50 — cuando lo agotes, las nuevas ejecuciones devuelven HTTP 402 hasta el siguiente mes natural.

**¿Por qué el draft tiene `[E:e001]` en lugar de citar tipo "(folio 3)"?**
Es el formato interno que permite la verificación verbatim. En el editor y en la vista pública, los marcadores son clicables y muestran la cita real con página y párrafo. En el DOCX exportado, los marcadores quedan como referencia pequeña en gris.

**¿Puedo borrar un expediente?**
Por seguridad y trazabilidad, esta versión no expone borrado de expedientes desde la UI. Si necesitas eliminar uno (ej. RGPD: derecho de supresión del cliente), contacta al admin para hacerlo desde la base de datos.

**¿Y si pierdo mi sesión?**
Vuelves a la pantalla de Acceder y pides un enlace mágico nuevo. Las sesiones duran 1 hora desde el último uso, se renuevan automáticamente al navegar.

---

## 9. Soporte

- **Bugs / errores técnicos**: contacta al equipo de desarrollo (interno).
- **Cuestiones legales del servicio**: `legal@galaxylegal.es` (cuando esté activo).
- **Privacidad / RGPD**: `privacy@galaxylegal.es`.
- **Soporte general**: `support@galaxylegal.es`.

Páginas estáticas:
- Política de privacidad: `/privacy`
- Términos y condiciones: `/terms`

---

## 10. Resumen ejecutivo (1 minuto)

1. **Crea un expediente**.
2. **Sube documentos** (drag & drop o desde Drive).
3. Espera a que estén `listos`.
4. **Lanza un workflow**.
5. **Revisa el borrador** generado, edita si quieres.
6. **Aprueba o crea nueva revisión**.
7. **Exporta a DOCX** o **comparte un link público** con tu cliente.
8. Cada cita tiene página, párrafo y texto verbatim del documento de origen. Si una cita no cuadraba, el sistema no te ha generado el draft (`needs_human`) — esa es la promesa de Galaxy Legal.

Galaxy Legal no sustituye al abogado, le quita 4 horas de redacción mecánica por escrito y le añade trazabilidad criptográfica de cada cita. El abogado sigue siendo responsable de revisar y firmar.
