# Fase 4 — Cola de Jobs, Métricas y Estado TIMEOUT

## Justificación académica

Esta fase cierra la brecha entre la implementación técnica del middleware y
los objetivos explícitos de la tesis:

> **Objetivo específico 2:** "...haciendo uso de **algoritmos de gestión de
> colas** y **asignación dinámica de memoria VRAM** para asegurar la
> **estabilidad del sistema** durante la inferencia de modelos pesados."

> **Objetivo específico 3:** "Validar el desempeño técnico mediante **pruebas
> de carga**, midiendo **latencia de comunicación** y la correcta
> **recuperación de errores** ante fallos de los modelos."

Los tres componentes implementados responden directamente a esos objetivos:

| Componente | Objetivo de tesis que satisface |
|---|---|
| Cola FIFO con límite de concurrencia | Objetivo 2: gestión de colas + VRAM |
| `GET /api/v1/metrics` | Objetivo 3: medición de latencia y errores |
| Estado `TIMEOUT` diferenciado | Objetivo 3: recuperación de errores |

No se implementó nada adicional a lo que los objetivos requieren.

---

## 1. Cola FIFO con límite de concurrencia

### Archivo

`app/services/job_queue.py`

### Descripción

Implementa una cola de espera FIFO con un número máximo configurable de jobs
ejecutándose simultáneamente.  Cuando todos los slots están ocupados, los
nuevos jobs esperan en orden de llegada hasta que un slot se libera.

### Algoritmo

La cola usa `threading.Event` por cada job en espera, almacenados en un
`deque` (cola de doble extremo).  El orden FIFO se garantiza porque:

1. Cada job que no encuentra slot libre agrega su `(job_id, event)` al final
   del `deque` y bloquea su hilo en `event.wait()`.
2. Cuando un job termina, libera su slot y llama a `deque.popleft()` para
   despertar el job más antiguo en espera.
3. Todo esto ocurre bajo un único `threading.Lock`, haciendo las operaciones
   atómicas y sin race conditions.

```
Job A llega  →  slot libre  →  ejecuta de inmediato
Job B llega  →  slot ocupado  →  entra a deque[0]  →  espera
Job C llega  →  slot ocupado  →  entra a deque[1]  →  espera
Job A termina →  despierta Job B (popleft)
Job B termina →  despierta Job C (popleft)
```

### VRAM como mecanismo de control de VRAM

Cada backend de modelo Docker carga sus pesos en GPU en el momento de
inferencia.  Limitar a N jobs simultáneos equivale a limitar a N modelos
cargados en GPU al mismo tiempo.

Con `max_concurrent_jobs=1` (valor por defecto), solo un backend puede
inferir a la vez, garantizando que la GPU no sea saturada por múltiples
cargas de pesos concurrentes.

Esto es lo que el objetivo específico 2 denomina "asignación dinámica de
memoria VRAM": el middleware controla dinámicamente cuántos procesos de
inferencia pesada pueden coexistir, sin necesidad de inspeccionar VRAM
directamente (lo cual dependería del hardware y del driver GPU).

### Integración con FastAPI / uvicorn

`job_queue.submit()` bloquea el **hilo HTTP** del request (el thread pool de
uvicorn), no el event loop de asyncio.  Uvicorn puede seguir procesando otras
requests (health checks, consultas de modelos) en paralelo.  El contrato
síncrono de `POST /api/v1/jobs/segment-video` se conserva sin modificar
ELAN.

### Configuración

| Variable de entorno | Descripción | Default |
|---|---|---|
| `MIDDLEWARE_MAX_CONCURRENT_JOBS` | Máximo de jobs simultáneos | `1` |

Ejemplo en `docker-compose.yml`:
```yaml
environment:
  MIDDLEWARE_MAX_CONCURRENT_JOBS: "1"
```

### Limitaciones conocidas

- Los contadores `active_jobs` y `queued_jobs` se reinician al reiniciar el
  middleware.
- Python's `threading.Semaphore` no garantiza FIFO; esta implementación usa
  `threading.Event` + `deque` para garantía estricta.
- No se implementa cancelación de jobs en ejecución (fuera del alcance para
  el caso de uso single-user de ELAN).

---

## 2. Endpoint GET /api/v1/metrics

### Archivos

- `app/services/metrics_service.py` — contadores thread-safe
- `app/schemas/system_metrics.py` — schema de respuesta Pydantic
- `app/api/routes_metrics.py` — router FastAPI

### Descripción

Expone contadores acumulados desde el inicio del middleware para soporte de
pruebas de carga y validación de desempeño (objetivo específico 3).

### Contrato

**Request:**
```
GET /api/v1/metrics
```

**Response 200:**
```json
{
  "total_jobs": 10,
  "completed_jobs": 8,
  "failed_jobs": 1,
  "timeout_jobs": 1,
  "active_jobs": 0,
  "queued_jobs": 0,
  "average_exec_ms": 3241.75,
  "last_exec_ms": 2987,
  "error_counts": {
    "DOCKER_TIMEOUT": 1,
    "DOCKER_INFERENCE_ERROR": 1
  }
}
```

### Descripción de campos

| Campo | Tipo | Descripción |
|---|---|---|
| `total_jobs` | int | Total de jobs recibidos desde startup |
| `completed_jobs` | int | Jobs que finalizaron en COMPLETED |
| `failed_jobs` | int | Jobs que finalizaron en FAILED |
| `timeout_jobs` | int | Jobs que excedieron `timeout_sec` (TIMEOUT) |
| `active_jobs` | int | Jobs ejecutándose en este momento |
| `queued_jobs` | int | Jobs esperando un slot en la cola |
| `average_exec_ms` | float\|null | Latencia promedio de todos los COMPLETED |
| `last_exec_ms` | int\|null | Latencia del último COMPLETED |
| `error_counts` | object | Conteo por código de error |

### Implementación de contadores

Los contadores se actualizan en `job_service.py` en cada transición de estado:

```python
# Al recibir el job
metrics_service.record_started()

# Al completar exitosamente
metrics_service.record_completed(total_ms)

# Al fallar con error Docker
metrics_service.record_failed(exc.error_code)

# Al expirar el timeout
metrics_service.record_timeout("DOCKER_TIMEOUT")
```

`active_jobs` y `queued_jobs` se leen en tiempo real desde `JobQueue` (no
son contadores, son snapshots del estado actual).

### Thread safety

`MetricsService` usa un único `threading.Lock` para proteger todos los
contadores.  El método `snapshot()` toma los valores bajo el mismo lock para
devolver un estado consistente.

### Uso para pruebas de carga

Para las pruebas del objetivo específico 3, se puede:

1. Enviar N requests simultáneos a `POST /api/v1/jobs/segment-video`.
2. Consultar `GET /api/v1/metrics` al finalizar.
3. Verificar que `completed_jobs == N`, `average_exec_ms` refleja la latencia
   real bajo carga, y `timeout_jobs > 0` si algún backend no respondió a tiempo.

Ejemplo curl:
```bash
curl http://127.0.0.1:8000/api/v1/metrics
```

---

## 3. Estado TIMEOUT diferenciado de FAILED

### Archivo modificado

`app/services/job_service.py`

### Descripción

Antes de esta fase, cualquier excepción durante la inferencia resultaba en el
mismo comportamiento: la excepción propagaba al manejador global y el job no
quedaba guardado en el store.  No había distinción entre un error funcional
del backend y un timeout por latencia excesiva.

### Implementación

En `job_service.py`, el bloque que llama a `job_queue.submit()` ahora
captura `DockerTimeoutError` específicamente antes del catch genérico de
`DockerServiceError`:

```python
try:
    inference_output = job_queue.submit(job_id=request.job_id, fn=_run_inference)
except DockerTimeoutError:
    metrics_service.record_timeout("DOCKER_TIMEOUT")
    raise
except DockerServiceError as exc:
    metrics_service.record_failed(exc.error_code)
    raise
except Exception:
    metrics_service.record_failed("INTERNAL_SERVER_ERROR")
    raise
```

La excepción siempre se re-lanza para que el manejador global de `main.py`
devuelva la respuesta HTTP correcta:

| Excepción | `error_code` en respuesta | HTTP status | Contador afectado |
|---|---|---|---|
| `DockerTimeoutError` | `DOCKER_TIMEOUT` | 504 | `timeout_jobs` |
| `DockerInferenceError` | `DOCKER_INFERENCE_ERROR` | 502 | `failed_jobs` |
| `DockerContainerStartError` | `DOCKER_CONTAINER_START_ERROR` | 502 | `failed_jobs` |
| `DockerContainerHealthcheckFailedError` | `DOCKER_CONTAINER_HEALTHCHECK_FAILED` | 502 | `failed_jobs` |
| `DockerImageNotFoundError` | `DOCKER_IMAGE_NOT_FOUND` | 404 | `failed_jobs` |
| `DockerNotAvailableError` | `DOCKER_NOT_AVAILABLE` | 503 | `failed_jobs` |

### Cuándo ocurre un TIMEOUT

`DockerTimeoutError` se lanza en `docker_service.py` cuando el socket HTTP
hacia el backend expira.  Esto ocurre en `post_json()`:

```python
except (TimeoutError, socket.timeout) as exc:
    raise DockerTimeoutError(f"Docker inference timed out after {timeout_sec}s.")
```

El valor de `timeout_sec` viene de `execution.timeout_sec` en el request.
Si el cliente no lo envía, el default es `300` segundos.

### Respuesta HTTP ante TIMEOUT

```json
{
  "error_code": "DOCKER_TIMEOUT",
  "detail": "Docker inference timed out after 300s."
}
```

HTTP status: `504 Gateway Timeout`

---

## 4. Flujo completo de un job (Fase 4)

```
POST /api/v1/jobs/segment-video
         │
         ▼
  metrics_service.record_started()
         │
         ▼
  RECEIVED → VALIDATING (fuera de cola)
         │ (validar modelo en registry)
         ▼
  PREPROCESSING (fuera de cola)
         │ (construir InferenceInput)
         ▼
  QUEUED
         │
         ▼ job_queue.submit() ─────────────────────────────────────┐
         │                                                          │
         │  [si slot disponible: pasa de inmediato]                 │
         │  [si slots ocupados: bloquea hilo HTTP hasta turno]      │
         │                                                          │
         ▼ (dentro del slot)                                        │
  RUNNING                                                           │
         │ runner.run() → DockerRunner                              │
         │   GET /health del backend                                │
         │   POST /infer del backend                                │
         │                                                          │
    ┌────┴─────────┐                                                │
    │              │                                                │
  éxito          error                                              │
    │              │                                                │
    ▼              ▼                                               │
POSTPROCESSING  DockerTimeoutError → record_timeout() → 504       │
    │           DockerServiceError  → record_failed()  → 502       │
    ▼           Exception           → record_failed()  → 500       │
  COMPLETED                                                         │
    │                                                               │
    ▼                                                               │
  metrics_service.record_completed(total_ms)                       │
  store.save_job(response)                                         │
  return SegmentVideoResponse                        ◄─────────────┘
```

---

## 5. Archivos creados / modificados

### Creados

| Archivo | Propósito |
|---|---|
| `app/services/job_queue.py` | Cola FIFO + control de concurrencia |
| `app/services/metrics_service.py` | Contadores thread-safe |
| `app/schemas/system_metrics.py` | Schema Pydantic de métricas |
| `app/api/routes_metrics.py` | Endpoint GET /api/v1/metrics |

### Modificados

| Archivo | Cambio |
|---|---|
| `app/core/config.py` | Agrega `max_concurrent_jobs` + env `MIDDLEWARE_MAX_CONCURRENT_JOBS` |
| `app/services/job_service.py` | Integra cola, métricas y captura TIMEOUT |
| `app/main.py` | Registra `metrics_router` |
| `README.md` | Documenta endpoint de métricas y nueva variable |

---

## 6. Cómo verificar cada implementación

### Verificar que el endpoint de métricas funciona

```bash
curl http://127.0.0.1:8000/api/v1/metrics
```

Debe responder 200 con `total_jobs: 0` si no se ha ejecutado ningún job aún.

### Verificar la cola bajo carga

Enviar dos requests simultáneos (desde dos terminales al mismo tiempo):

**Terminal 1:**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{"job_id":"job-001","media":{"path":"/data/videos/video.mp4"},...}'
```

**Terminal 2 (inmediatamente):**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{"job_id":"job-002","media":{"path":"/data/videos/video.mp4"},...}'
```

Los logs del middleware mostrarán:
```
INFO  Job 'job-001' transitioned to 'QUEUED'.
INFO  Job 'job-001' dispatched immediately (active=1/1).
INFO  Job 'job-001' transitioned to 'RUNNING'.
INFO  Job 'job-002' transitioned to 'QUEUED'.
INFO  Job 'job-002' queued (position=1, active=1/1).
INFO  Job 'job-001' done. Dispatching next job 'job-002' (active=1/1, queued=0).
INFO  Job 'job-002' transitioned to 'RUNNING'.
```

Después de ambos jobs, consultar métricas:
```bash
curl http://127.0.0.1:8000/api/v1/metrics
```

Debe mostrar `total_jobs: 2`, `completed_jobs: 2`, `queue_ms > 0` en el
trace del segundo job.

### Verificar estado TIMEOUT

Enviar un request con `timeout_sec` muy bajo:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{..., "execution": {"timeout_sec": 1}}'
```

Si la inferencia tarda más de 1 segundo, la respuesta debe ser:
```json
{"error_code": "DOCKER_TIMEOUT", "detail": "Docker inference timed out after 1s."}
```

HTTP status 504.  Luego consultar métricas para verificar `timeout_jobs: 1`.
