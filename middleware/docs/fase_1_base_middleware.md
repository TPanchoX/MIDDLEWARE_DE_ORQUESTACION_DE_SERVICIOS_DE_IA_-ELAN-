# Fase 1 — Base del Middleware ELAN-AI

## 1. Descripción general

El **ELAN-AI Middleware** es un servicio HTTP local escrito en Python/FastAPI que actúa como orquestador entre la herramienta de anotación ELAN (cliente Java) y los modelos de Inteligencia Artificial contenerizados con Docker.

ELAN no ejecuta modelos directamente. En su lugar, envía solicitudes HTTP al middleware, que gestiona el ciclo de vida completo: validar la solicitud, seleccionar el runner correcto, delegar la inferencia al contenedor del modelo y devolver segmentos temporales listos para anotar.

---

## 2. Stack tecnológico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.11 |
| Framework API | FastAPI 0.115+ |
| Validación | Pydantic v2 |
| Servidor ASGI | Uvicorn |
| Contenerización | Docker + Docker Compose |
| Persistencia | Archivos JSON sobre bind mounts del host (`./data/`) |
| Comunicación con modelos | HTTP interno (red Docker `elan-ai-shared`) |

---

## 3. Arquitectura general

```
┌─────────────────────────────────────────────────────────────────┐
│  HOST WINDOWS (Docker Desktop)                                  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Red Docker: elan-ai-shared                              │   │
│  │                                                          │   │
│  │  ┌─────────────────────┐    HTTP     ┌───────────────┐   │   │
│  │  │  elan-ai-middleware  │ ──────────► │  Contenedor   │   │   │
│  │  │  (FastAPI :8000)     │  :8080      │  del Modelo   │   │   │
│  │  │                      │ ◄────────── │  (FastAPI)    │   │   │
│  │  └─────────────────────┘             └───────────────┘   │   │
│  │            ▲                                              │   │
│  └────────────┼─────────────────────────────────────────────┘   │
│               │ HTTP :8000                                      │
│         ┌─────┴─────┐                                           │
│         │   ELAN    │  (cliente Java / Postman / curl)          │
│         └───────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

El middleware y los contenedores de modelo comparten la red `elan-ai-shared`. El middleware se comunica con los contenedores **por nombre de contenedor** (DNS interno de Docker), no por puerto del host.

---

## 4. Estructura de directorios

```
middleware/
├── app/
│   ├── main.py                        ← entrada FastAPI, routers y exception handlers
│   ├── api/
│   │   ├── routes_health.py           ← GET /health
│   │   ├── routes_models.py           ← CRUD de modelos + install
│   │   ├── routes_jobs.py             ← POST /jobs/segment-video, GET /jobs/{id}
│   │   └── routes_metrics.py          ← GET /metrics
│   ├── core/
│   │   ├── config.py                  ← Settings (env vars)
│   │   └── logging_config.py          ← configuración de logs
│   ├── runners/
│   │   ├── base_runner.py             ← clase abstracta BaseRunner
│   │   ├── docker_runner.py           ← DockerRunner (único runner activo)
│   │   └── runner_selector.py         ← selecciona el runner según el manifest
│   ├── schemas/
│   │   ├── common.py                  ← ErrorResponse / HealthResponse
│   │   ├── jobs.py                    ← contratos de entrada/salida de jobs
│   │   ├── models.py                  ← ModelManifest e InstalledModel
│   │   ├── inference.py               ← InferenceInput / InferenceOutput (internas)
│   │   ├── metrics.py                 ← StageMetrics
│   │   └── system_metrics.py          ← MiddlewareMetrics (GET /metrics)
│   ├── services/
│   │   ├── model_registry_service.py  ← instala, valida y gestiona modelos
│   │   ├── job_service.py             ← orquesta la inferencia completa
│   │   ├── docker_service.py          ← wrapper del SDK de Docker
│   │   ├── docker_lifecycle_service.py← build + start + health check al instalar
│   │   ├── job_queue.py               ← cola FIFO con límite de concurrencia
│   │   └── metrics_service.py         ← contadores thread-safe en memoria
│   └── storage/
│       └── memory_store.py            ← almacén en memoria de jobs completados
├── data/
│   ├── models_store/                  ← registry.json + paquetes instalados (bind mount)
│   └── bootstrap_manifests/           ← manifests de respaldo (bind mount)
├── Dockerfile                         ← imagen del middleware
├── docker-compose.yml                 ← orquestación
├── requirements.txt
└── .gitignore
```

> **Nota sobre la persistencia**: el registry y los paquetes instalados viven en `./data/models_store` y los manifests de respaldo en `./data/bootstrap_manifests`. Ambos son **bind mounts** del host declarados en `docker-compose.yml` (montados en `/app/data/...` dentro del contenedor), por lo que sobreviven a `docker compose down -v` y a la limpieza de volúmenes de Docker.

---

## 5. Configuración y variables de entorno

Todas las variables se definen en `docker-compose.yml`. Se leen en `app/core/config.py` vía `os.getenv`.

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `MIDDLEWARE_HOST` | `0.0.0.0` (en compose) | Interfaz de escucha dentro del contenedor |
| `MIDDLEWARE_PORT` | `8000` | Puerto del servidor |
| `MIDDLEWARE_LOG_LEVEL` | `INFO` | Nivel de log |
| `MIDDLEWARE_RUNTIME_PROFILE` | `final` | Perfil (`development`/`final`). En `final` solo se listan modelos Docker |
| `MIDDLEWARE_MODELS_STORE_DIR` | `/app/data/models_store` | Directorio del registry y paquetes instalados |
| `MIDDLEWARE_BOOTSTRAP_MANIFESTS_DIR` | `/app/data/bootstrap_manifests` | Directorio escaneado al arrancar para re-registrar modelos |
| `MIDDLEWARE_VIDEOS_DIR` | *(requerida)* | Ruta del **host** con los videos (ej: `C:/Users/user/Videos`). Se monta como `/data/videos` (ro) en cada contenedor de modelo |
| `MIDDLEWARE_DOCKER_NETWORK` | `elan-ai-shared` | Red Docker compartida con contenedores de modelo |
| `MIDDLEWARE_MAX_CONCURRENT_JOBS` | `1` | Máximo de inferencias simultáneas (cola FIFO) |

---

## 6. Cómo levantar el middleware

### Prerequisitos
- Docker Desktop instalado y corriendo
- Puerto 8000 libre en el host

### Comandos

```bash
# Desde la carpeta middleware/
cd middleware

# Primera vez o cuando hay cambios de código:
docker compose up --build -d

# Verificar que está corriendo:
docker compose ps

# Ver logs en tiempo real:
docker compose logs -f middleware

# Detener:
docker compose down
```

### Verificación rápida

```bash
curl http://localhost:8000/health
```

Respuesta esperada:
```json
{"status": "ok", "service": "elan-ai-orchestrator", "version": "0.1.0"}
```

---

## 7. Endpoints disponibles

### 7.1 GET /health

Verifica que el middleware está activo.

**Request:** ningún parámetro

**Response 200:**
```json
{
  "status": "ok",
  "service": "elan-ai-orchestrator",
  "version": "0.1.0"
}
```

---

### 7.2 GET /api/v1/models

Lista todos los modelos instalados.

**Response 200:**
```json
{
  "models": [
    {
      "model_id": "lsec_bio_gloss_final_v1",
      "name": "LSEC BIO Gloss Pipeline — Implementacion Final Tesis",
      "version": "1.0.0",
      "task": "video_segmentation_and_gloss_classification",
      "runtime": "docker",
      "status": "available"
    }
  ]
}
```

---

### 7.3 GET /api/v1/models/{model_id}

Devuelve el detalle completo de un modelo, incluyendo su manifest completo.

**Parámetros de ruta:** `model_id` — identificador del modelo

**Response 200:** objeto `InstalledModel` completo con todos los campos del manifest.

**Response 404:**
```json
{"error_code": "MODEL_NOT_FOUND", "detail": "Model 'xxx' not found."}
```

---

### 7.4 POST /api/v1/models/install

Instala un modelo desde un archivo ZIP. Ver **Fase 2** para el detalle completo.

---

### 7.5 PATCH /api/v1/models/{model_id}/status

Activa o desactiva un modelo.

**Body:**
```json
{"status": "available"}
```
o
```json
{"status": "disabled"}
```

**Response 200:** objeto `InstalledModel` actualizado.

**Posibles errores:**

| Código HTTP | error_code | Causa |
|---|---|---|
| 404 | `MODEL_NOT_FOUND` | El model_id no existe |
| 422 | — | El campo `status` no es `available` ni `disabled` |

---

### 7.6 POST /api/v1/jobs/segment-video

Ejecuta inferencia sobre un video. Ver **Fase 3** para el flujo interno completo.

---

### 7.7 GET /api/v1/jobs/{job_id}

Recupera el resultado de un job ya ejecutado (almacenado en memoria durante la sesión).

**Response 200:** objeto `SegmentVideoResponse` idéntico al devuelto por `POST /jobs/segment-video`.

**Response 404:**
```json
{"error_code": "JOB_NOT_FOUND", "detail": "Job 'xxx' was not found."}
```

> ⚠️ Los jobs se almacenan **en memoria** (`MemoryStore`). Si el middleware se reinicia, los jobs anteriores se pierden.

---

### 7.8 GET /api/v1/metrics

Devuelve contadores acumulados desde el arranque del servicio (en memoria). Ver **Fase 4** para el detalle de campos.

**Response 200 (ejemplo):**
```json
{
  "total_jobs": 2, "completed_jobs": 1, "failed_jobs": 0, "timeout_jobs": 1,
  "active_jobs": 0, "queued_jobs": 0,
  "average_exec_ms": 33725.0, "last_exec_ms": 33725,
  "error_counts": {"DOCKER_TIMEOUT": 1}
}
```

---

## 8. Manejo global de errores

Todos los errores siguen el esquema `ErrorResponse`:

```json
{
  "error_code": "CODIGO_ERROR",
  "detail": "Mensaje descriptivo del error."
}
```

| Código HTTP | Situación |
|---|---|
| 400 | Request mal formado o lógicamente inválido |
| 404 | Recurso (modelo o job) no encontrado |
| 409 | Conflicto (modelo ya instalado) |
| 422 | Validación Pydantic fallida (campos faltantes o tipos incorrectos) |
| 501 | Runtime o framework no soportado |
| 502 | Error en el contenedor Docker del modelo |
| 503 | Docker no disponible |
| 504 | Timeout del contenedor |
| 500 | Error interno inesperado |

---

## 9. Flujo de estados de un job

```
RECEIVED → VALIDATING → PREPROCESSING → QUEUED → RUNNING → POSTPROCESSING → COMPLETED
                                                                           ├→ FAILED
                                                                           └→ TIMEOUT
```

| Estado | Descripción |
|---|---|
| `RECEIVED` | Request recibido por el middleware |
| `VALIDATING` | Se valida que el modelo existe y está disponible |
| `PREPROCESSING` | Se selecciona el runner y se construye el `InferenceInput` |
| `QUEUED` | En espera de un slot de la cola FIFO de concurrencia |
| `RUNNING` | Inferencia en progreso en el contenedor Docker |
| `POSTPROCESSING` | Se validan y adaptan los segmentos devueltos |
| `COMPLETED` | Éxito — segmentos disponibles |
| `FAILED` | Error funcional en alguna etapa |
| `TIMEOUT` | La inferencia superó `execution.timeout_sec` (HTTP 504, `DOCKER_TIMEOUT`) |
