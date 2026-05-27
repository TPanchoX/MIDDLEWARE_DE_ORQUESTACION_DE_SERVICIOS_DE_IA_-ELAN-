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
| Persistencia | Archivo JSON en volumen Docker |
| Comunicación con modelos | HTTP interno (red Docker) |

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
│   ├── main.py                        ← entrada FastAPI, lifespan, montaje de routers
│   ├── api/
│   │   ├── routes_health.py           ← GET /health
│   │   ├── routes_models.py           ← CRUD de modelos + install
│   │   └── routes_jobs.py             ← POST /jobs/segment-video, GET /jobs/{id}
│   ├── core/
│   │   ├── config.py                  ← Settings (env vars)
│   │   └── logging_config.py          ← configuración de logs
│   ├── runners/
│   │   ├── base_runner.py             ← clase abstracta BaseRunner
│   │   ├── docker_runner.py           ← DockerRunner (único runner activo)
│   │   └── runner_selector.py         ← selecciona el runner según el manifest
│   ├── schemas/
│   │   ├── common.py                  ← ErrorResponse
│   │   ├── jobs.py                    ← contratos de entrada/salida de jobs
│   │   ├── models.py                  ← contratos de modelos e InstalledModel
│   │   ├── inference.py               ← InferenceInput / InferenceOutput (internas)
│   │   └── metrics.py                 ← StageMetrics
│   ├── services/
│   │   ├── model_registry_service.py  ← instala, valida y gestiona modelos
│   │   ├── job_service.py             ← orquesta la inferencia completa
│   │   ├── docker_service.py          ← wrapper del SDK de Docker
│   │   └── docker_lifecycle_service.py← build + start + health check al instalar
│   ├── storage/
│   │   └── memory_store.py            ← almacén en memoria de jobs completados
│   └── models_store/
│       ├── registry.json              ← registro local (no usado por Docker)
│       └── installed/                 ← directorio local (no usado por Docker)
├── model_packages/
│   └── lsec_bio_gloss_final_v1/       ← fuente del paquete de modelo
├── Dockerfile                         ← imagen del middleware
├── docker-compose.yml                 ← orquestación
├── requirements.txt
└── .gitignore
```

> **Nota sobre `models_store/`**: cuando el middleware corre con Docker Compose, el registry real se almacena en el **volumen Docker** `middleware_models` montado en `/app/data/models_store`. La carpeta local `app/models_store/` existe solo como referencia de desarrollo.

---

## 5. Configuración y variables de entorno

Todas las variables se definen en `docker-compose.yml`. Se leen en `app/core/config.py` vía `os.getenv`.

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `MIDDLEWARE_HOST` | `0.0.0.0` | Interfaz de escucha dentro del contenedor |
| `MIDDLEWARE_PORT` | `8000` | Puerto del servidor |
| `MIDDLEWARE_LOG_LEVEL` | `INFO` | Nivel de log |
| `MIDDLEWARE_RUNTIME_PROFILE` | `final` | Perfil (desarrollo/final) |
| `MIDDLEWARE_MODELS_STORE_DIR` | `/app/data/models_store` | Directorio del registry (en Docker) |
| `MIDDLEWARE_VIDEOS_DIR` | `""` | Ruta Windows de la carpeta de videos (ej: `C:/Users/user/Videos`) |
| `MIDDLEWARE_DOCKER_NETWORK` | `elan-ai-shared` | Red Docker compartida con contenedores de modelo |

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

> ⚠️ Los jobs se almacenan **en memoria**. Si el middleware se reinicia, los jobs anteriores se pierden.

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
                                                                           └→ FAILED
```

| Estado | Descripción |
|---|---|
| `RECEIVED` | Request recibido por el middleware |
| `VALIDATING` | Se valida que el modelo existe y está disponible |
| `PREPROCESSING` | Se prepara el runner |
| `QUEUED` | En cola de ejecución |
| `RUNNING` | Inferencia en progreso en el contenedor Docker |
| `POSTPROCESSING` | Se adaptan los segmentos devueltos |
| `COMPLETED` | Éxito — segmentos disponibles |
| `FAILED` | Error en alguna etapa |
