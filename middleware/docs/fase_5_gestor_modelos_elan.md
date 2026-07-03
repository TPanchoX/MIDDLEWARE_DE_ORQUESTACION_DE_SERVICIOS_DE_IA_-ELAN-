# Fase 5 — Gestor de modelos en el front-end ELAN

## Resumen

Esta fase cierra el ciclo de usuario completo: el investigador puede instalar, activar
y seleccionar modelos de IA directamente desde el panel de ELAN, sin necesidad de
interactuar con el middleware a través de la línea de comandos ni editar archivos de
configuración. También se reemplaza la inferencia con parámetros hardcodeados por una
inferencia totalmente parametrizada desde la interfaz.

---

## Archivos creados o modificados

### ELAN — DTOs (nuevos)

| Archivo | Propósito |
|---|---|
| `dto/ModelSummary.java` | Resumen de un modelo instalado: `model_id`, `name`, `version`, `task`, `runtime`, `status`. Deserializado desde `GET /api/v1/models`. |
| `dto/ModelUiConfig.java` | Configuración de UI del manifiesto del modelo: `defaultLabel`, `defaultTargetTier`, `labelMode`, `supportsThreshold`. |
| `dto/InstalledModelDetail.java` | Detalle completo de un modelo; incluye `ModelUiConfig` para pre-poblar la UI de ELAN. Deserializado desde `GET /api/v1/models/{id}`. |

### ELAN — DTOs (modificados)

| Archivo | Cambio |
|---|---|
| `dto/ParametersPayload.java` | Añadido `createEmpty()` que serializa a `{}`. Permite que el backend Docker use su propia `pipeline_config.json` sin que ELAN sobreescriba nada. El modo BIO explícito (`createDefault`) queda marcado `@Deprecated`. |
| `dto/SegmentVideoRequest.java` | Añadido factory `create(jobId, videoPath, modelId, version, tier, label, labelMode)`. Usa `ParametersPayload.createEmpty()` y `ExecutionPayload("auto", "auto", 300)`. `createDefault()` queda marcado `@Deprecated`. |

### ELAN — Lógica HTTP (modificado)

**`AIOrchestrationMiddlewareClient.java`**

Refactorización completa orientada a URL base + endpoints separados:

| Método nuevo | Endpoint | Descripción |
|---|---|---|
| `health()` | `GET /health` | Comprueba disponibilidad del servidor. |
| `listModels()` | `GET /api/v1/models` | Lista todos los modelos con su estado. |
| `getModelDetail(id)` | `GET /api/v1/models/{id}` | Detalle completo + config de UI. |
| `installModel(zipFile)` | `POST /api/v1/models/install` | Sube un ZIP con `multipart/form-data`. |
| `updateModelStatus(id, status)` | `PATCH /api/v1/models/{id}/status` | Activa (`"available"`) o desactiva (`"disabled"`) un modelo. |
| `segmentVideo(request)` | `POST /api/v1/jobs/segment-video` | Inferencia (existía, sin cambios funcionales). |

El cliente ahora siempre trabaja con la **URL base** (p.ej. `http://127.0.0.1:8000`).
El método `extractBaseUrl()` garantiza compatibilidad con configuraciones antiguas que
almacenaban la URL completa del endpoint de inferencia.

### ELAN — UI (nuevo)

**`AIModelManagerDialog.java`** — Diálogo Swing de gestión de modelos:

- Barra de estado (dot de color + etiqueta) + botón **Probar conexión**.
- `JTable` con columnas: Nombre, Versión, Estado, Runtime.
- Botones: **Actualizar**, **Instalar ZIP…**, **Activar**, **Desactivar**.
- Área de detalle del modelo seleccionado.
- Log de actividad en tiempo real.
- Todas las operaciones HTTP en `SwingWorker` (nunca bloquea el EDT).
- `isModelListChanged()` → notifica al panel padre si debe refrescar el combo de modelos.

### ELAN — UI (modificado)

**`AIOrchestrationRecognizerPanel.java`** — Rediseño completo del panel de control:

| Sección | Componente | Funcionalidad |
|---|---|---|
| Servidor | `JTextField` (URL base) | Solo muestra `http://host:puerto`, nunca paths internos. |
| Servidor | Botón **Probar** | `GET /health` en background; muestra ✓/✗ con color. |
| Servidor | Botón **Gestionar modelos…** | Abre `AIModelManagerDialog`; refresca combo si hubo cambios. |
| Video | `JComboBox<String>` editable | Ruta del video que ELAN reporta; seleccionable manualmente. |
| Modelo | `JComboBox<ModelSummary>` | Modelos activos primero, desactivados al final. Se carga en background al hacerse visible (`addNotify`). |
| Modelo | Etiqueta de estado | ✓ Activo / ⚠ Desactivado / ✗ Error de carga. |
| Anotación | `JTextField` tier destino | Pre-población desde `ui.default_target_tier` del manifiesto. Nota explicativa debajo. |
| Anotación | `JComboBox` formato etiqueta | `gloss_top1` → "Mejor glosa predicha"; `simple` → "Solo etiqueta de región". Pre-población desde `ui.label_mode`. |

Decisión de diseño: el **timeout** (300 s) no se expone al usuario. Es un detalle de
implementación interno que no aporta valor a un investigador de lengua de señas.

Métodos públicos expuestos al recognizer:

```java
String       getBaseUrl()
String       getSelectedMediaPath()
ModelSummary getSelectedModel()
String       getTargetTier()
String       getLabelMode()
String       getCurrentDefaultLabel()
void         updateMediaFiles(List<String> mediaFiles)
void         refreshModelCombo()
```

### ELAN — Reconocedor (modificado)

**`AIOrchestrationRecognizer.java`** — Usa valores dinámicos del panel:

```java
// Antes (hardcodeado):
SegmentVideoRequest request = SegmentVideoRequest.createDefault(jobId, videoPath);
Segmentation seg = new Segmentation(TARGET_TIER, elanSegments, videoPath);

// Ahora (dinámico):
ModelSummary selectedModel = controlPanel.getSelectedModel();
SegmentVideoRequest request = SegmentVideoRequest.create(
        jobId, videoPath,
        selectedModel.getModelId(), selectedModel.getVersion(),
        controlPanel.getTargetTier(),
        controlPanel.getCurrentDefaultLabel(),
        controlPanel.getLabelMode());
Segmentation seg = new Segmentation(targetTier, elanSegments, videoPath);
```

Otros cambios en el recognizer:

- `validateParameters()` verifica que haya un modelo seleccionado antes de ejecutar.
- `getBaseUrl()` reemplaza al deprecated `getEndpoint()`.
- `getBaseUrlFromSystemProperty()` usa `DEFAULT_BASE_URL` como fallback (no el endpoint legacy).
- El log de inferencia reporta modelo, tier y label_mode para trazabilidad.

---

## Justificación frente a los objetivos del TIC

### 1. Objetivo específico 1 — integración de servicios externos en el flujo de anotación

El objetivo 1 exige "contratos de interfaz REST y el esquema de instalación de modelos
que permitan la integración de servicios externos de inferencias en el flujo de
anotación". La fase 5 convierte el bridge de ELAN en un **gestor visual completo**: el
investigador puede instalar un paquete ZIP de un modelo nuevo, activarlo y ejecutar la
inferencia sin salir de ELAN ni tocar archivos de configuración, cerrando la
integración end-to-end con la herramienta de anotación.

### 2. Extensibilidad — soportar múltiples modelos sin modificar código

La UI lista dinámicamente todos los modelos registrados en el middleware. Añadir un
nuevo modelo (instalando su ZIP) lo hace inmediatamente disponible en el combo de ELAN.
No se requiere recompilar ELAN ni el middleware, en línea con el contrato de
instalación definido por el `manifest.json`.

### 3. Separación de responsabilidades entre lógica de procesamiento e interfaz

Los DTOs (`ModelSummary`, `InstalledModelDetail`, `ModelUiConfig`) actúan como capa de
contrato entre el middleware y ELAN. Los cambios internos del middleware (rutas,
formato de respuesta) solo requieren ajustes en los DTOs, sin tocar la lógica del
recognizer ni la UI.

### 4. Usabilidad — el usuario no necesita conocer el pipeline interno

- La URL base es el único parámetro de red visible (`http://127.0.0.1:8000`).
- Los paths de los endpoints son detalles de implementación ocultos.
- El timeout de 300 s es fijo e invisible al usuario.
- Los parámetros de anotación (tier, formato de etiqueta) se explican con texto
  descriptivo en el panel y se pre-populan automáticamente desde el manifiesto del
  modelo seleccionado.

---

## Flujo de uso completo (resumen)

```
[Investigador en ELAN]
   │
   ├─ Panel: Gestionar modelos → Instalar ZIP → Activar modelo
   │         (POST /api/v1/models/install + PATCH /api/v1/models/{id}/status)
   │
   ├─ Panel: Seleccionar modelo → UI se auto-configura con tier/label del manifiesto
   │         (GET /api/v1/models/{id})
   │
   └─ Ejecutar recognizer
         ├─ ELAN llama a AIOrchestrationRecognizer.start()
         ├─ POST /api/v1/jobs/segment-video  (con model_id, tier, label_mode dinámicos)
         ├─ Middleware ejecuta Docker backend seleccionado
         └─ ELAN inserta segmentos en el tier configurado
```

---

## Decisiones de implementación

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Exponer solo URL base al usuario | Mostrar el path completo del endpoint | El path es un detalle de implementación que confunde al usuario no técnico |
| Timeout fijo de 300 s | Campo editable de timeout | No aporta valor al usuario final; el middleware gestiona los recursos internamente |
| `ParametersPayload.createEmpty()` → `{}` | Enviar siempre parámetros BIO explícitos | El backend Docker tiene su propia `pipeline_config.json`; sobrescribir parámetros externos rompe la encapsulación del modelo |
| Modelos activos primero en el combo | Orden alfabético | Minimiza clics: el usuario rara vez quiere ejecutar un modelo desactivado |
| `addNotify()` para carga lazy | Cargar en constructor | El panel puede instanciarse antes de que el servidor esté disponible; `addNotify` garantiza que el HTTP se dispara cuando el panel es realmente visible |
| `isModelListChanged()` en el diálogo | Evento/callback explícito | Solución simple sin acoplamiento entre dialog y panel; el panel consulta el flag solo al cerrarse el diálogo |
