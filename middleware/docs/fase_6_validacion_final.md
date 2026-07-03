# Fase 6 — Validación final e integración con ELAN

## Relación con el alcance del componente (tesis)

El alcance definido en la tesis establece tres fases para el componente. Las
fases 1–5 cubrieron las dos primeras; esta fase cierra la tercera:

> **"Por último, en la fase de validación se desplegará el sistema en un
> entorno controlado para realizar pruebas de caja blanca y caja negra. Se
> verificará la correcta orquestación de un modelo de inteligencia artificial
> sobre videos LSEc, registrando métricas de latencia, consumo de recursos del
> sistema y documentando la arquitectura final para garantizar la
> mantenibilidad y escalabilidad del sistema desarrollado."**

Cada elemento de esa definición se aborda de la siguiente manera:

| Requisito del TIC | Cómo se cubre en esta fase |
|---|---|
| Entorno controlado | Docker Compose (mismo en desarrollo y validación) |
| Pruebas de caja negra | Escenarios funcionales § 2 |
| Pruebas de caja blanca | Verificación de estado interno § 3 |
| Modelo de IA orquestado | El modelo real `lsec_bio_gloss_final_v1` — ver § 1.1 |
| Videos de LSEc | Video real de LSEc usado en todos los escenarios |
| Consumo de recursos del sistema | `docker stats` durante inferencia — ver § 4 |
| Métricas de latencia | `GET /api/v1/metrics` y `trace.stages` — implementados en Fase 4 |
| Documentación de arquitectura | § 5 |

---

## § 1. Decisiones metodológicas

### § 1.1 Por qué la validación usa el modelo real y no un stub

Durante el desarrollo se implementó temporalmente un `DummyRunner` que
devolvía segmentos fijos sin procesamiento real. Su propósito fue validar el
flujo ELAN → middleware → anotaciones de forma aislada, sin depender de un
backend Docker funcional.

El runner dummy fue **eliminado al completarse la integración Docker**, y la
validación final se ejecuta con el modelo real por las siguientes razones:

1. **Un stub no valida la hipótesis central.** Si el sistema solo funciona
   con respuestas predefinidas, no se demuestra que el middleware orquesta
   correctamente un modelo de IA real. El alcance del TIC exige verificar
   "la correcta orquestación de un modelo de inteligencia artificial sobre
   videos LSEc"; un stub no es un modelo de IA.

2. **El modelo real es un superconjunto del stub.** Todo lo que el dummy
   probaba (serialización de request, deserialización de response,
   construcción de anotaciones en ELAN) también lo prueba el modelo real, más
   la complejidad de la inferencia genuina: build de imagen, carga de pesos,
   lectura de video y ejecución del pipeline.

3. **`lsec_bio_gloss_final_v1` es el modelo con el que se hace la validación
   controlada.** Usar un modelo funcional real en las pruebas eleva la
   calidad de la evidencia y produce métricas representativas.

### § 1.2 Por qué se mide CPU/RAM con `docker stats` y no con `psutil`

La alternativa natural sería añadir `psutil` al middleware para reportar su
propio consumo de CPU/RAM en el endpoint `/api/v1/metrics`. Sin embargo, esa
aproximación es **incompleta**:

- El sistema no es un proceso único. Involucra el contenedor del middleware
  **y** el contenedor del modelo backend. `psutil` dentro del middleware solo
  mediría el orquestador, invisibilizando el costo real de la inferencia
  (que ocurre en el backend).

- `docker stats` mide **todos los contenedores simultáneamente** desde fuera,
  dando una visión del consumo total del sistema tal como lo vería un
  administrador o el sistema operativo anfitrión.

- Desde la perspectiva de la tesis, lo que importa es el impacto del sistema
  en el hardware del usuario final, no el consumo aislado de uno de los dos
  procesos. `docker stats` responde exactamente esa pregunta.

- Añadir `psutil` requeriría una nueva dependencia y cambiar el schema de
  métricas. El valor adicional no justifica el costo frente a una medición
  externa con herramientas estándar de la industria.

### § 1.3 Pruebas de caja blanca vs. caja negra — interpretación aplicada

En el contexto de esta tesis, los términos se definen así:

**Caja negra:** El evaluador conoce las entradas y salidas esperadas del
sistema pero no el código interno. Solo interactúa con las interfaces públicas
(ELAN, Postman, `curl`). Los escenarios del § 2 son todos de caja negra.

**Caja blanca:** El evaluador conoce la estructura interna del código y diseña
casos de prueba para ejercitar rutas específicas, verificando el estado interno
resultante. En este proyecto, eso significa:

- Confirmar que el **registro de modelos** (`registry.json`) se actualiza
  correctamente.
- Confirmar que el **bootstrap manifest** se genera en disco al instalar.
- Confirmar que los **contadores de métricas** incrementan en las
  transiciones esperadas.
- Confirmar que los **logs estructurados** reflejan la ruta de código
  correcta (QUEUED → RUNNING → COMPLETED vs. QUEUED → RUNNING → TIMEOUT).

Esto no requiere tests unitarios formales con frameworks como pytest o JUnit.
La caja blanca en el contexto de una tesis de ingeniería se satisface
demostrando que el evaluador conoce el código y puede predecir y verificar el
estado interno del sistema ante cada estímulo. Los escenarios del § 3
documentan exactamente eso.

---

## § 2. Escenarios de caja negra

Los escenarios de caja negra se ejecutan desde **ELAN** o **Postman/curl**,
sin ningún conocimiento del código interno. Solo se observan las respuestas
de las interfaces públicas.

### Requisitos previos

- Middleware corriendo: `docker compose up -d`
- Modelo instalado y activo: `lsec_bio_gloss_final_v1 v1.0.0` (status
  `available`)
- Video de prueba disponible en la ruta configurada en `MIDDLEWARE_VIDEOS_DIR`
- ELAN abierto con un archivo `.eaf` que tenga un tier de video cargado

---

### E-01: Comprobación de disponibilidad desde Postman

**Objetivo:** Verificar que el middleware responde a peticiones de salud.

**Acción:**
```
GET http://127.0.0.1:8000/health
```

**Resultado esperado:**
```json
{"status": "ok", "service": "elan-ai-orchestrator", "version": "0.1.0"}
```
HTTP 200, respuesta en menos de 50 ms.

---

### E-02: Comprobación de disponibilidad desde ELAN

**Objetivo:** Verificar que el panel de ELAN detecta el estado del servidor.

**Acción:** En el panel del reconocedor (o en "Gestionar modelos…"), pulsar
**Probar conexión**.

**Resultado esperado:** Indicador en verde con el texto
`Conectado a http://127.0.0.1:8000`. Internamente el cliente Java ejecuta
`GET /health`.

---

### E-03: Instalación de modelo mediante ZIP

**Objetivo:** Verificar que un paquete ZIP válido se instala correctamente.

**Acción (ELAN):** Gestionar modelos → Instalar ZIP… → seleccionar el paquete
del modelo `lsec_bio_gloss_final_v1`.

**Resultado esperado (log del diálogo):**
```
✓ Modelo instalado correctamente.
```
La tabla de modelos se actualiza y muestra el nuevo modelo con estado "Activo".

**Acción (Postman):**
```
POST http://127.0.0.1:8000/api/v1/models/install
Body: form-data  →  file = <archivo .zip>
```

**Resultado esperado:** HTTP 200 con
```json
{"message": "Model installed successfully.", "model": {"model_id": "lsec_bio_gloss_final_v1", "...": "..."}}
```
Además: imagen Docker construida, contenedor saludable, `registry.json`
actualizado y bootstrap manifest generado.

---

### E-04: Listado de modelos

**Objetivo:** Verificar que todos los modelos instalados son listados.

**Acción:**
```
GET http://127.0.0.1:8000/api/v1/models
```

**Resultado esperado:**
```json
{
  "models": [
    {
      "model_id": "lsec_bio_gloss_final_v1",
      "name": "LSEc BIO-Gloss Final",
      "version": "1.0.0",
      "task": "video_segmentation_and_gloss_classification",
      "runtime": "docker",
      "status": "available"
    }
  ]
}
```

**En ELAN:** El combo del panel del reconocedor muestra el modelo disponible.

> **Verificación complementaria — detalle de modelo:**
> `GET /api/v1/models/lsec_bio_gloss_final_v1` responde HTTP 200 con
> `model_id`, `name`, `version`, `task`, `status`, `runtime`, `installed_at`,
> `source` y el bloque `ui` con `default_label`, `default_target_tier` y
> `label_mode` (usados por ELAN para pre-poblar el panel).

---

### E-05: Activar o desactivar modelo

**Objetivo:** Verificar que el estado de un modelo puede cambiarse sin
eliminarlo.

**Acción (desactivar):**
```
PATCH http://127.0.0.1:8000/api/v1/models/lsec_bio_gloss_final_v1/status
Body: {"status": "disabled"}
```

**Acción (reactivar):**
```
PATCH http://127.0.0.1:8000/api/v1/models/lsec_bio_gloss_final_v1/status
Body: {"status": "available"}
```

**Resultado esperado:** HTTP 200 en ambos casos, con
`{"message": "Model status updated successfully.", "model": {...}}` y el
nuevo estado persistido en `registry.json`.

**En ELAN:** Botones "Activar"/"Desactivar" según el estado del modelo
seleccionado. Tras pulsar: `✓ Modelo 'lsec_bio_gloss_final_v1' activado correctamente.`

---

### E-06: Instalación duplicada

**Objetivo:** Verificar que reinstalar la misma combinación
`(model_id, version)` se rechaza de forma controlada.

**Acción:** Repetir E-03 con el mismo ZIP ya instalado.

**Resultado esperado:** HTTP 409 con
```json
{
  "error_code": "MODEL_ALREADY_EXISTS",
  "detail": "Model 'lsec_bio_gloss_final_v1' version '1.0.0' is already installed."
}
```
En ELAN: `✗ Error al instalar: Model 'lsec_bio_gloss_final_v1' version '1.0.0' is already installed.`

---

### E-07: Inferencia exitosa desde ELAN

**Objetivo:** Verificar el flujo completo de orquestación desde la interfaz.

**Acción (ELAN):**
1. Panel del reconocedor → seleccionar modelo `lsec_bio_gloss_final_v1`.
2. Seleccionar el video de LSEc cargado en el archivo `.eaf`.
3. Pulsar **"Start"** en el diálogo de reconocedores.

**Resultado esperado:**
- ELAN muestra progreso del job.
- Al completar, aparecen anotaciones en el nivel configurado
  (`ui.default_target_tier` del modelo, `AUTO_GLOSS_SEGMENTS`).
- Las etiquetas de anotación corresponden a las glosas detectadas.

---

### E-08: Verificación visual de anotaciones

**Objetivo:** Verificar que los segmentos retornados se insertan correctamente
en la línea de tiempo de ELAN.

**Evidencia a capturar:** Captura de pantalla del timeline de ELAN mostrando
las anotaciones generadas sobre el video de LSEc. Las anotaciones deben:
- Estar en el nivel correcto (`ui.default_target_tier` del modelo).
- Tener tiempos de inicio/fin alineados con las señas visibles en el video.
- Mostrar etiquetas que corresponden a glosas de LSEc.

---

### E-09: Inferencia exitosa desde Postman

**Objetivo:** Verificar el contrato REST completo sin pasar por ELAN.

**Acción:**
```
POST http://127.0.0.1:8000/api/v1/jobs/segment-video
Content-Type: application/json
Body:
{
  "job_id": "test-e09",
  "media": {"path": "C:/Users/imbaq/OneDrive/Desktop/PruebaPato.mp4"},
  "model": {"model_id": "lsec_bio_gloss_final_v1", "version": "1.0.0"},
  "annotation": {"target_tier": "AUTO_GLOSS_SEGMENTS", "default_label": "LSEC_REGION", "label_mode": "gloss_top1"},
  "execution": {"device_preference": "auto", "runner": "auto", "timeout_sec": 300}
}
```
> `media.path` acepta la ruta del host (se traduce automáticamente a
> `/data/videos/...`) o la ruta interna ya traducida.

**Resultado esperado:** HTTP 200 con `status: "COMPLETED"`, `media_info`,
segmentos en milisegundos y trazabilidad por etapas:
```json
{
  "job_id": "test-e09",
  "status": "COMPLETED",
  "media_info": {"fps": 59.94, "duration_ms": 8508, "total_frames": 510},
  "segments": [
    {"start_ms": 884, "end_ms": 1518, "label": "TRABAJAR", "confidence": 0.164,
     "predictions": [{"rank": 1, "gloss_id": 10, "gloss": "TRABAJAR", "probability": 0.164}, "..."]}
  ],
  "trace": {"runner": "docker_http", "exec_ms": 33725, "stages": {"...": "..."}, "state_history": ["..."]}
}
```

---

### E-10: Error — video inexistente

**Objetivo:** Verificar que el sistema reporta un error claro cuando el video
no se encuentra en la ruta especificada.

**Acción:** Enviar un request con un path de video que no existe.

**Resultado esperado:** HTTP 502 con `error_code: DOCKER_INFERENCE_ERROR`.
El backend responde con error al no poder abrir el video; el middleware
captura el campo `detail` del body y lo propaga. El error llega hasta ELAN
y se muestra en el log del reconocedor.

---

### E-11: Error — modelo desactivado

**Objetivo:** Verificar que la inferencia falla de forma controlada si el
modelo está en estado `disabled`.

**Acción:** Desactivar el modelo (E-05) y luego intentar inferencia (E-09).

**Resultado esperado:**
```json
{"error_code": "MODEL_DISABLED", "detail": "Model 'lsec_bio_gloss_final_v1' version '1.0.0' is disabled."}
```
HTTP 409. En ELAN: error descriptivo en el log del reconocedor.

---

### E-12: Error — middleware detenido desde ELAN

**Objetivo:** Verificar que ELAN muestra un error de conectividad claro
cuando el middleware no está disponible.

**Acción:** Detener el contenedor (`docker compose stop`) y luego intentar
cualquier acción desde ELAN.

**Resultado esperado en ELAN:**
```
✗ Cannot connect to middleware at http://127.0.0.1:8000
```
No hay crash de ELAN. El error se muestra en el log de actividad.

---

### E-13: Error — timeout de inferencia forzado

**Objetivo:** Verificar que el sistema no queda bloqueado indefinidamente
ante una inferencia que supera el tiempo límite.

**Acción (Postman):**
```json
"execution": {"timeout_sec": 1}
```
Enviar con `timeout_sec: 1` (inferior al tiempo real de inferencia).

**Resultado esperado:**
```json
{"error_code": "DOCKER_TIMEOUT", "detail": "Docker inference timed out after 1s."}
```
HTTP 504. El job termina en estado `TIMEOUT`; el middleware sigue disponible
para nuevas peticiones y `timeout_jobs` se incrementa en las métricas.

---

### E-14: Contenedor del modelo detenido

**Objetivo:** Verificar que el middleware recupera automáticamente un
contenedor de modelo detenido.

**Acción:** Detener manualmente el contenedor del modelo
(`docker stop elan-ai-model-lsec_bio_gloss_final_v1-1.0.0`) y luego ejecutar
una inferencia (E-09).

**Resultado esperado:** HTTP 200. `DockerService.ensure_container()` detecta
el contenedor detenido y lo reinicia (`container.start()`) antes de la
inferencia; en el `trace` aparece `container_start_ms > 0` (arranque en frío).
Solo si la **imagen** fue eliminada, la respuesta es 404
`DOCKER_IMAGE_NOT_FOUND` y el modelo debe reinstalarse.

---

### E-15: Métricas después de fallos

**Objetivo:** Verificar que el endpoint de métricas refleja los jobs
ejecutados, incluidos los fallidos y expirados.

**Acción (tras ejecutar E-09 y E-13):**
```
GET http://127.0.0.1:8000/api/v1/metrics
```

**Resultado esperado (ejemplo tras 1 exitoso + 1 timeout):**
```json
{
  "total_jobs": 2,
  "completed_jobs": 1,
  "failed_jobs": 0,
  "timeout_jobs": 1,
  "active_jobs": 0,
  "queued_jobs": 0,
  "average_exec_ms": 3200.0,
  "last_exec_ms": 3200,
  "error_counts": {"DOCKER_TIMEOUT": 1}
}
```

---

### Escenario complementario: revisión de logs del middleware

**Objetivo:** Verificar que los logs son informativos y estructurados.

**Acción:**
```bash
docker logs elan-ai-middleware --tail 50
```

**Resultado esperado:** Entradas con nivel (`INFO`, `WARNING`, `ERROR`),
timestamp, módulo origen y mensaje descriptivo. Ejemplo:
```
2026-05-27 18:34:00,760 | INFO  | app.services.docker_lifecycle_service | Building Docker image 'lsec-bio-gloss-final:1.0.0'
2026-05-27 18:34:00,824 | INFO  | app.services.docker_lifecycle_service | Docker image built successfully.
```

---

## § 3. Escenarios de caja blanca

Los escenarios de caja blanca se diseñan con conocimiento del código interno.
El evaluador no solo observa la respuesta de la API, sino que verifica el
**estado interno** resultante para confirmar que la ruta de código correcta
fue ejecutada.

### B-01: Verificar persistencia en registry tras instalación

**Conocimiento interno:** La instalación escribe el modelo en
`data/models_store/registry.json` (bind mount del host).

**Acción:** Instalar un modelo (E-03).

**Verificación interna:**
```
cat middleware/data/models_store/registry.json
```
o desde Docker:
```bash
docker exec elan-ai-middleware cat /app/data/models_store/registry.json
```

**Resultado esperado:** El modelo aparece en el JSON con `"status": "available"`
y `"source": "installed"`.

**Ruta de código ejercitada:** `ModelRegistryService._save_registry()`

---

### B-02: Verificar generación de bootstrap manifest

**Conocimiento interno:** Al instalar un modelo Docker, `_save_bootstrap_manifest()`
escribe un archivo `<model_id>__<version>.json` en `data/bootstrap_manifests/`.
Esto garantiza que el modelo sobrevive a una eliminación del volumen.

**Acción:** Instalar un modelo (E-03).

**Verificación interna:**
```
dir middleware\data\bootstrap_manifests\
```

**Resultado esperado:** Existe un archivo `lsec_bio_gloss_final_v1__1.0.0.json`
con el manifiesto del modelo.

**Ruta de código ejercitada:** `ModelRegistryService._save_bootstrap_manifest()`

---

### B-03: Verificar recuperación automática por bootstrap

**Conocimiento interno:** Al arrancar, el middleware escanea
`bootstrap_manifests_dir` y re-registra modelos ausentes del registry.

**Acción:**
1. Instalar un modelo (verificar B-02).
2. Eliminar `data/models_store/registry.json`.
3. Reiniciar el middleware: `docker compose restart middleware`.
4. Consultar `GET /api/v1/models`.

**Resultado esperado:** El modelo sigue apareciendo, re-registrado
automáticamente desde el bootstrap manifest.

**Ruta de código ejercitada:**
`ModelRegistryService._bootstrap_docker_manifests()` (ejecutado al construir
el singleton del servicio durante el arranque del proceso)

---

### B-04: Verificar contadores de métricas por transición de estado

**Conocimiento interno:** En `job_service.py`, cada transición de estado
llama al método correspondiente de `metrics_service`:
- `record_started()` al recibir el job.
- `record_completed(ms)` al finalizar con éxito.
- `record_failed(error_code)` ante error Docker.
- `record_timeout("DOCKER_TIMEOUT")` ante timeout.

**Acción A — inferencia exitosa:**
1. Consultar métricas antes: anotar `total_jobs` y `completed_jobs`.
2. Ejecutar E-07.
3. Consultar métricas después.

**Resultado esperado:** `total_jobs` incrementó en 1, `completed_jobs`
incrementó en 1, `last_exec_ms` refleja el tiempo real de la inferencia.

**Acción B — timeout:**
1. Ejecutar E-13.
2. Consultar métricas.

**Resultado esperado:** `timeout_jobs` incrementó en 1,
`error_counts.DOCKER_TIMEOUT` incrementó en 1.

---

### B-05: Verificar ruta de traducción de path del video

**Conocimiento interno:** `DockerRunner._translate_media_path()` convierte el
path del host (p.ej. `C:/Users/imbaq/OneDrive/Desktop/video.mp4`) al path
interno del contenedor del modelo (`/data/videos/video.mp4`) antes de enviar
el request al backend.

**Acción:** Ejecutar E-07 y revisar los logs del contenedor **del modelo**
(no del middleware):
```bash
docker logs <nombre-contenedor-modelo> --tail 20
```

**Resultado esperado:** El backend recibe la ruta como `/data/videos/video.mp4`,
no como la ruta Windows original.

**Ruta de código ejercitada:** `DockerRunner._translate_media_path()`

---

### B-06: Verificar bind mount del volumen de videos

**Conocimiento interno:** El bind mount declarado en `docker-compose.yml`
para los videos es `MIDDLEWARE_VIDEOS_DIR → /data/videos` dentro del
contenedor del modelo.

**Acción:**
```bash
docker inspect <nombre-contenedor-modelo> --format "{{json .Mounts}}"
```

**Resultado esperado:** Aparece un mount con:
- `Source`: ruta del host configurada en `MIDDLEWARE_VIDEOS_DIR`
- `Destination`: `/data/videos`
- `Mode`: `ro` (read-only)

---

## § 4. Métricas de rendimiento computacional (CPU y RAM)

### Justificación del método

La tesis requiere medir "rendimiento computacional (uso de CPU/RAM)". El
sistema está compuesto por dos contenedores Docker que se ejecutan
simultáneamente durante la inferencia:

- `elan-ai-middleware` — el orquestador (CPU/RAM bajo)
- `elan-ai-model-lsec_bio_gloss_final_v1-1.0.0` — el backend de inferencia
  (CPU/RAM alto)

`docker stats` mide ambos en tiempo real desde el sistema operativo anfitrión,
dando la visión completa del impacto en el hardware. Esta es la herramienta
estándar de la industria para monitoreo de rendimiento en contenedores.

### Protocolo de medición

**1. Antes de la inferencia — estado de reposo:**
```bash
docker stats --no-stream elan-ai-middleware
```
Capturar: CPU%, MEM USAGE, MEM LIMIT.

**2. Durante la inferencia — estado de carga:**

Abrir dos terminales simultáneamente:

*Terminal A — lanzar la inferencia:*
```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "perf-test-001",
    "media": {"path": "C:/Users/imbaq/OneDrive/Desktop/PruebaPato.mp4"},
    "model": {"model_id": "lsec_bio_gloss_final_v1", "version": "1.0.0"},
    "annotation": {"target_tier": "AUTO_GLOSS_SEGMENTS", "default_label": "LSEC_REGION", "label_mode": "gloss_top1"},
    "execution": {"device_preference": "auto", "runner": "auto", "timeout_sec": 300}
  }'
```

*Terminal B — monitoreo continuo (ejecutar mientras A corre):*
```bash
docker stats elan-ai-middleware elan-ai-model-lsec_bio_gloss_final_v1-1.0.0
```

**3. Valores a registrar como evidencia:**

| Métrica | Herramienta | Momento |
|---|---|---|
| CPU% middleware | `docker stats` | Durante inferencia |
| RAM middleware | `docker stats` | Durante inferencia |
| CPU% backend modelo | `docker stats` | Durante inferencia |
| RAM backend modelo | `docker stats` | Durante inferencia (pico) |
| Tiempo de respuesta total | `GET /api/v1/metrics` → `last_exec_ms` | Tras completar |
| Tiempo promedio (N jobs) | `GET /api/v1/metrics` → `average_exec_ms` | Tras N jobs |

**Captura de pantalla requerida:** `docker stats` corriendo mientras la
inferencia está en progreso, mostrando ambos contenedores.

### Valores de referencia esperados

Los valores exactos dependen del hardware, pero los rangos típicos para este
modelo con CPU (sin GPU):

| Contenedor | CPU% | RAM |
|---|---|---|
| Middleware (orquestador) | < 5% | < 150 MB |
| Backend modelo (inferencia) | 60–200% | 1–4 GB |

Un CPU% > 100% en Docker es normal: indica uso de múltiples núcleos (200%
= 2 núcleos al 100%).

### Prueba de carga controlada (2 jobs simultáneos)

Para validar el objetivo específico 3 ("pruebas de carga"):

**Terminal A:**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{"job_id": "load-001", ...}' &
```

**Terminal B (inmediatamente):**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{"job_id": "load-002", ...}'
```

**Resultado esperado:**
- `load-001` ejecuta de inmediato (slot libre).
- `load-002` queda en QUEUED hasta que `load-001` termina (la cola FIFO
  con `max_concurrent_jobs=1` garantiza esto).
- Los logs confirman: `"Job 'load-002' queued (position=1, active=1/1)"`.
- Métricas tras ambos: `total_jobs: 2`, `completed_jobs: 2`.

---

## § 5. Arquitectura final del sistema

### Visión general de componentes

```
┌─────────────────────────────────────────────────────────────────┐
│  HOST  (Windows / macOS / Linux)                                │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ELAN (Java Swing)                                      │   │
│  │                                                         │   │
│  │  AIOrchestrationRecognizerPanel  ←→  AIModelManagerDialog│  │
│  │              │                                          │   │
│  │  AIOrchestrationMiddlewareClient (HTTP/1.1)             │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                             │ HTTP REST (localhost:8000)        │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  Docker Desktop                                         │   │
│  │                                                         │   │
│  │  ┌─────────────────────────────────────────────────┐   │   │
│  │  │  elan-ai-middleware  (python:3.11-slim)          │   │   │
│  │  │                                                  │   │   │
│  │  │  FastAPI / Uvicorn                               │   │   │
│  │  │    /health            ← HealthRouter             │   │   │
│  │  │    /api/v1/models/*   ← ModelsRouter             │   │   │
│  │  │    /api/v1/jobs/*     ← JobsRouter               │   │   │
│  │  │    /api/v1/metrics    ← MetricsRouter             │   │   │
│  │  │                                                  │   │   │
│  │  │  ModelRegistryService  →  registry.json (bind)   │   │   │
│  │  │  DockerLifecycleService → build + start backend  │   │   │
│  │  │  JobQueue (FIFO)        → concurrencia controlada│   │   │
│  │  │  MetricsService         → contadores en memoria  │   │   │
│  │  │  DockerRunner           → HTTP al backend        │   │   │
│  │  │                                                  │   │   │
│  │  │  Bind mounts (host):                             │   │   │
│  │  │    ./data/models_store → /app/data/models_store  │   │   │
│  │  │    ./data/bootstrap_manifests → /app/data/...    │   │   │
│  │  │    /var/run/docker.sock → /var/run/docker.sock   │   │   │
│  │  └──────────────────────┬───────────────────────────┘   │   │
│  │                         │ Docker API (UNIX socket)       │   │
│  │                         │ Docker network: elan-ai-shared │   │
│  │  ┌──────────────────────▼───────────────────────────┐   │   │
│  │  │  elan-ai-model-lsec_bio_gloss_final_v1-1.0.0     │   │   │
│  │  │  (imagen construida por DockerLifecycleService)   │   │   │
│  │  │                                                   │   │   │
│  │  │  FastAPI backend                                  │   │   │
│  │  │    GET /health   ← health check del lifecycle     │   │   │
│  │  │    POST /infer   ← inferencia real del modelo     │   │   │
│  │  │                                                   │   │   │
│  │  │  Bind mounts (host):                              │   │   │
│  │  │    MIDDLEWARE_VIDEOS_DIR → /data/videos (ro)      │   │   │
│  │  └───────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Flujo de datos — inferencia exitosa

```
1. ELAN              → POST /api/v1/jobs/segment-video (JSON)
2. Middleware        → Valida modelo en registry
3. Middleware        → JobQueue.submit() → QUEUED → RUNNING
4. Middleware        → DockerRunner.run()
5. DockerRunner      → Traduce path del host → /data/videos/...
6. DockerRunner      → POST /infer al contenedor del modelo
7. Contenedor modelo → Carga video desde /data/videos/
8. Contenedor modelo → Ejecuta pipeline de IA
9. Contenedor modelo → Retorna segmentos temporales JSON
10. Middleware       → Deserializa respuesta del backend
11. Middleware       → MetricsService.record_completed(ms)
12. Middleware       → Retorna SegmentVideoResponse a ELAN
13. ELAN             → Deserializa segmentos
14. ELAN             → Inserta anotaciones en tiers del archivo .eaf
```

### Flujo de datos — instalación de modelo

```
1. ELAN              → POST /api/v1/models/install (multipart ZIP)
2. Middleware        → Valida ZIP y detecta prefijo de carpeta raíz
3. Middleware        → Valida manifest.json con Pydantic (ModelManifest)
4. Middleware        → Verifica artifacts declarados dentro del ZIP
5. Middleware        → Extrae a models_store/installed/{id}/{version}/
                       y registra el modelo (_save_registry → registry.json)
6. Middleware        → DockerLifecycleService.build_and_start()
7. Lifecycle         → docker build (backend/Dockerfile, contexto = paquete)
8. Lifecycle         → DockerService.ensure_container() (crea o reusa)
9. Lifecycle         → Health check hasta 200 OK del backend
10. Middleware       → _save_bootstrap_manifest() → bootstrap_manifests/
11. Middleware       → Retorna {"message": "Model installed successfully.", model}
    (si 7–9 fallan  → rollback: quita del registry y borra el directorio,
     respuesta 400 MODEL_PACKAGE_INVALID)
```

### Decisiones de diseño que garantizan mantenibilidad

| Decisión | Justificación |
|---|---|
| **Bind mounts sobre named volumes** | Los datos de modelos y manifests sobreviven a `docker compose down -v`, `docker volume prune` y reinstalaciones de Docker Desktop |
| **Bootstrap manifests separados del registry** | El registry puede corromperse o eliminarse; los manifests garantizan re-registro automático al reiniciar sin intervención manual |
| **HTTP/REST como IPC entre todos los componentes** | Agnóstico al lenguaje del backend; cualquier framework que exponga `/health` y `/infer` es compatible |
| **Pydantic para validación de manifests** | Errores de configuración se detectan en tiempo de instalación, no en tiempo de inferencia |
| **Cola FIFO con límite configurable** | Control de VRAM por configuración, no por código; ajustable sin tocar el middleware |
| **Métricas en memoria** | Sin dependencia de base de datos; adecuado para el caso de uso single-user de ELAN |
| **`extractBaseUrl()` en el cliente Java** | Compatibilidad hacia atrás con configuraciones antiguas que almacenaban la URL completa del endpoint |

### Decisiones de diseño que garantizan escalabilidad

| Decisión | Cómo escala |
|---|---|
| **Un contenedor por modelo** | Múltiples modelos pueden estar activos simultáneamente; cada uno en su propio proceso y red |
| **Red Docker compartida (`elan-ai-shared`)** | Los contenedores se descubren por nombre sin exponer puertos al host; añadir modelos no requiere cambiar `docker-compose.yml` del middleware |
| **`MIDDLEWARE_MAX_CONCURRENT_JOBS`** | Aumentar a N permite usar N modelos diferentes simultáneamente si el hardware lo permite |
| **`runner_selector.py`** | El middleware puede añadir nuevos tipos de runner (p.ej. ONNX local, gRPC) sin cambiar la capa HTTP ni ELAN |

---

## § 6. Checklist de evidencias para la tesis

Cada ítem debe quedar documentado con captura de pantalla o texto copiado
en el informe de validación.

### Evidencias funcionales (caja negra)
- [ ] E-01: Respuesta JSON de `GET /health` desde Postman
- [ ] E-02: Captura del indicador verde en ELAN ("Conectado a...")
- [ ] E-03: Log del diálogo ELAN mostrando instalación exitosa
- [ ] E-04: Respuesta JSON de `GET /api/v1/models` con el modelo listado
- [ ] E-07: Progreso y anotaciones generadas al ejecutar desde ELAN
- [ ] E-08: Captura del timeline de ELAN con anotaciones generadas
- [ ] E-09: Respuesta JSON de `POST /api/v1/jobs/segment-video` con segmentos y `trace`
- [ ] E-10: Error 502 `DOCKER_INFERENCE_ERROR` ante video inexistente
- [ ] E-11: Error 409 `MODEL_DISABLED` ante modelo desactivado
- [ ] E-12: Mensaje de error de conectividad en ELAN sin crash
- [ ] E-13: Respuesta HTTP 504 con `error_code: DOCKER_TIMEOUT`
- [ ] E-14: Inferencia exitosa tras detener el contenedor (reinicio automático)

### Evidencias de estado interno (caja blanca)
- [ ] B-01: Contenido de `registry.json` tras instalación
- [ ] B-02: Listado de `data/bootstrap_manifests/` con archivo generado
- [ ] B-03: `GET /api/v1/models` devuelve el modelo tras eliminar registry y reiniciar
- [ ] B-04: `GET /api/v1/metrics` mostrando contadores correctos tras cada job
- [ ] B-06: `docker inspect` confirmando bind mount de videos

### Evidencias de rendimiento (CPU/RAM y timing)
- [ ] Captura de `docker stats` durante inferencia (ambos contenedores)
- [ ] Captura de `GET /api/v1/metrics` tras N inferencias (average_exec_ms)
- [ ] Logs del middleware mostrando transición QUEUED→RUNNING→COMPLETED
- [ ] Captura de prueba de carga: 2 jobs simultáneos, el segundo en QUEUED

### Evidencias de arquitectura
- [ ] Diagrama de componentes de esta sección (puede incluirse como figura)
- [ ] `docker compose config` mostrando la configuración de despliegue final
- [ ] `cat requirements.txt` mostrando las dependencias del middleware
