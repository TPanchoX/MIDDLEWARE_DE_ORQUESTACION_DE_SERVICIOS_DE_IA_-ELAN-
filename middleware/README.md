# Middleware de Orquestación ELAN–IA

Middleware local desarrollado como Trabajo de Integración Curricular (TIC) para
conectar la herramienta de anotación **ELAN** con backends de modelos de
Inteligencia Artificial, sin acoplar ELAN ni el middleware a PyTorch,
MediaPipe, CUDA ni a ninguna arquitectura concreta de modelo.

La frontera entre componentes es siempre HTTP:

```text
ELAN (cliente Java, reconocedor AVATecH)
  -> POST /api/v1/jobs/segment-video
  -> Middleware FastAPI (orquestador local)
  -> Backend de modelo HTTP en Docker (GET /health, POST /infer)
```

## Arquitectura

Tres capas desacopladas:

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| ELAN | Java 11+ (paquete `mpi.eudico.client.annotator.recognizer.ai`) | Configuración, ejecución del reconocedor e inserción de anotaciones |
| Middleware | Python 3.11 + FastAPI + Pydantic + Uvicorn | Validación de contratos, registro de modelos, cola de jobs, métricas y orquestación Docker |
| Backends de modelo | Contenedores Docker (uno por modelo) | Pipeline de inferencia real sobre el video |

El middleware y los contenedores de modelo comparten la red Docker
`elan-ai-shared`; el middleware se comunica con cada backend por **nombre de
contenedor** (DNS interno de Docker), sin exponer puertos de los modelos al
host.

## Inicio rápido

Requisitos: Docker Desktop (o Docker Engine) y el puerto 8000 libre.

```bash
# Desde esta carpeta (middleware/)
docker compose up --build -d

# Verificar
curl http://127.0.0.1:8000/health
# -> {"status": "ok", "service": "elan-ai-orchestrator", "version": "0.1.0"}
```

Antes de la primera inferencia, configurar `MIDDLEWARE_VIDEOS_DIR` en
`docker-compose.yml` con la carpeta del host donde están los videos.

## Endpoints de la API REST

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/health` | Disponibilidad general del servicio |
| `GET` | `/api/v1/models` | Lista los modelos instalados |
| `GET` | `/api/v1/models/{id}` | Detalle completo de un modelo (incluye bloque `ui`) |
| `POST` | `/api/v1/models/install` | Instala un modelo desde un ZIP (`multipart/form-data`, campo `file`) |
| `PATCH` | `/api/v1/models/{id}/status` | Activa (`available`) o desactiva (`disabled`) un modelo |
| `POST` | `/api/v1/jobs/segment-video` | Ejecuta una inferencia sobre un video |
| `GET` | `/api/v1/jobs/{job_id}` | Recupera el resultado de un job (en memoria, por sesión) |
| `GET` | `/api/v1/metrics` | Contadores acumulados desde el arranque |

## Instalación de modelos (ZIP + manifest.json)

Cada modelo se distribuye como un ZIP con `manifest.json` en la raíz. Al
recibir el paquete, el middleware:

1. Valida el ZIP, el manifest (schema Pydantic `ModelManifest`) y los
   artefactos declarados; rechaza rutas inseguras (`..`, absolutas).
2. Extrae el paquete a `data/models_store/installed/{model_id}/{version}/`
   y lo registra en `registry.json`.
3. Construye la imagen Docker (`backend/Dockerfile`, contexto = paquete) y
   arranca el contenedor `elan-ai-model-{model_id}-{version}` en la red
   compartida.
4. Espera el health check del backend (hasta
   `backend_config.startup_timeout_sec`).
5. Guarda un manifest de respaldo en `data/bootstrap_manifests/`, con el que
   el registro se reconstruye automáticamente en el próximo arranque si
   `registry.json` se pierde.

Si el build, el arranque o el health check fallan, se ejecuta **rollback**
(se quita el modelo del registry y se borran los archivos extraídos) y la
respuesta es `400 MODEL_PACKAGE_INVALID` con el detalle del error.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/models/install \
     -F "file=@lsec_bio_gloss_final_v1.zip"
```

La guía completa para crear un backend nuevo está en
[`docs/guia_nuevo_backend_modelo.md`](docs/guia_nuevo_backend_modelo.md).

## Contrato de inferencia

Request (`POST /api/v1/jobs/segment-video`):

```json
{
  "job_id": "job-postman-001",
  "media": {
    "path": "C:/Users/usuario/Videos/video_001.mp4"
  },
  "annotation": {
    "target_tier": "AUTO_GLOSS_SEGMENTS",
    "default_label": "LSEC_REGION",
    "label_mode": "gloss_top1"
  },
  "model": {
    "model_id": "lsec_bio_gloss_final_v1",
    "version": "1.0.0"
  },
  "execution": {
    "timeout_sec": 300
  }
}
```

Notas:

- `media.path` acepta la **ruta del host** (el middleware la traduce al punto
  de montaje `/data/videos/...` del contenedor) o la ruta interna ya
  traducida.
- `execution` y `parameters` son opcionales; los parámetros internos del
  pipeline pertenecen al backend (`config/pipeline_config.json`), no al
  cliente.

Respuesta (recortada):

```json
{
  "job_id": "job-postman-001",
  "status": "COMPLETED",
  "media_info": {"fps": 59.94, "duration_ms": 8508, "total_frames": 510},
  "segments": [
    {
      "start_ms": 884,
      "end_ms": 1518,
      "label": "TRABAJAR",
      "confidence": 0.164,
      "predictions": [
        {"rank": 1, "gloss_id": 10, "gloss": "TRABAJAR", "probability": 0.164}
      ]
    }
  ],
  "trace": {
    "runner": "docker_http",
    "docker_mode": "sdk_managed",
    "exec_ms": 33725,
    "stages": {"validation_ms": 1, "queue_ms": 1, "docker_inference_ms": 33563},
    "state_history": ["RECEIVED", "VALIDATING", "PREPROCESSING", "QUEUED",
                      "RUNNING", "POSTPROCESSING", "COMPLETED"]
  }
}
```

ELAN consume principalmente `segments[].start_ms`, `end_ms`, `label` y
`confidence`; el campo `trace` aporta trazabilidad por etapas para
diagnóstico y validación.

## Estados de un job

```text
RECEIVED → VALIDATING → PREPROCESSING → QUEUED → RUNNING → POSTPROCESSING → COMPLETED
                                                                           ├→ FAILED
                                                                           └→ TIMEOUT
```

La cola FIFO (`JobQueue`) limita las inferencias simultáneas a
`MIDDLEWARE_MAX_CONCURRENT_JOBS` (1 por defecto): mientras un job espera su
turno, el resto de la API sigue respondiendo.

## Errores estructurados

Todas las fallas responden `{"error_code": "...", "detail": "..."}`:

| HTTP | error_code | Situación |
|---|---|---|
| 400 | `MODEL_PACKAGE_INVALID` / `MODEL_MANIFEST_NOT_FOUND` / `MODEL_MANIFEST_INVALID` / `MODEL_ARTIFACT_MISSING` | Paquete ZIP inválido o fallo de instalación (con rollback) |
| 404 | `MODEL_NOT_FOUND` / `JOB_NOT_FOUND` / `DOCKER_IMAGE_NOT_FOUND` | Recurso inexistente (imagen borrada ⇒ reinstalar el modelo) |
| 409 | `MODEL_ALREADY_EXISTS` / `MODEL_DISABLED` | Conflicto de estado del modelo |
| 422 | — (Pydantic) / `UNSUPPORTED_DOCKER_CONTRACT` | Request malformado o respuesta del backend fuera de contrato |
| 501 | `UNSUPPORTED_RUNTIME` / `UNSUPPORTED_FRAMEWORK` | Manifest con runtime no soportado |
| 502 | `DOCKER_CONTAINER_START_ERROR` / `DOCKER_CONTAINER_HEALTHCHECK_FAILED` / `DOCKER_INFERENCE_ERROR` | Fallo del contenedor o del backend |
| 503 | `DOCKER_NOT_AVAILABLE` | Docker no está disponible |
| 504 | `DOCKER_TIMEOUT` | La inferencia superó `execution.timeout_sec` (job en estado `TIMEOUT`) |
| 500 | `INTERNAL_SERVER_ERROR` | Error interno inesperado |

## Métricas

```text
GET /api/v1/metrics
```

```json
{
  "total_jobs": 5, "completed_jobs": 4, "failed_jobs": 0, "timeout_jobs": 1,
  "active_jobs": 0, "queued_jobs": 0,
  "average_exec_ms": 3420.5, "last_exec_ms": 3100,
  "error_counts": {"DOCKER_TIMEOUT": 1}
}
```

Los contadores viven en memoria y se reinician con el proceso.

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `MIDDLEWARE_HOST` / `MIDDLEWARE_PORT` | `0.0.0.0` / `8000` | Interfaz y puerto de Uvicorn |
| `MIDDLEWARE_LOG_LEVEL` | `INFO` | Nivel del logging estructurado |
| `MIDDLEWARE_RUNTIME_PROFILE` | `final` | En `final` solo se listan modelos `docker_http` |
| `MIDDLEWARE_MODELS_STORE_DIR` | `/app/data/models_store` | Registry y paquetes instalados (bind mount) |
| `MIDDLEWARE_BOOTSTRAP_MANIFESTS_DIR` | `/app/data/bootstrap_manifests` | Manifests de respaldo escaneados al arrancar |
| `MIDDLEWARE_VIDEOS_DIR` | *(requerida)* | Carpeta del host con los videos; se monta como `/data/videos` (ro) en cada backend |
| `MIDDLEWARE_DOCKER_NETWORK` | `elan-ai-shared` | Red compartida middleware ↔ backends |
| `MIDDLEWARE_MAX_CONCURRENT_JOBS` | `1` | Límite de inferencias simultáneas (control indirecto de RAM/VRAM) |

La persistencia usa **bind mounts** (`./data/`), por lo que los modelos
instalados sobreviven a `docker compose down -v` y a la limpieza de volúmenes.

## Estructura del proyecto

```text
middleware/
├── app/
│   ├── main.py                 # FastAPI: routers y manejadores globales de error
│   ├── api/                    # Endpoints HTTP (health, models, jobs, metrics)
│   ├── core/                   # Settings (env vars) y logging estructurado
│   ├── schemas/                # Contratos Pydantic (manifest, jobs, métricas)
│   ├── services/               # Registry, ciclo de vida Docker, cola, métricas
│   ├── runners/                # BaseRunner / DockerRunner / selector
│   └── storage/                # MemoryStore (jobs por sesión)
├── data/
│   ├── models_store/           # registry.json + paquetes instalados
│   └── bootstrap_manifests/    # manifests de respaldo
├── docs/                       # Documentación técnica por fases (1–6) y guía de backends
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Integración con ELAN

El cliente se implementa como un reconocedor AVATecH dentro del código fuente
de ELAN 7.1 (paquete `mpi.eudico.client.annotator.recognizer.ai`): panel de
configuración, diálogo de gestión de modelos, cliente HTTP/1.1
(`java.net.http.HttpClient`) y DTOs. El procedimiento de compilación con
Maven, el registro vía SPI y la verificación de la integración están
documentados en el Anexo de compilación del TIC y en
[`docs/fase_5_gestor_modelos_elan.md`](docs/fase_5_gestor_modelos_elan.md).

## Documentación por fases

| Documento | Contenido |
|---|---|
| [`docs/fase_1_base_middleware.md`](docs/fase_1_base_middleware.md) | Base HTTP, configuración, estados y errores |
| [`docs/fase_2_registry_modelos.md`](docs/fase_2_registry_modelos.md) | Registry, manifest.json, instalación y rollback |
| [`docs/fase_3_docker_runner.md`](docs/fase_3_docker_runner.md) | DockerRunner, red compartida y contrato de inferencia |
| [`docs/fase_4_colas_metricas_timeout.md`](docs/fase_4_colas_metricas_timeout.md) | Cola FIFO, métricas y estado TIMEOUT |
| [`docs/fase_5_gestor_modelos_elan.md`](docs/fase_5_gestor_modelos_elan.md) | Integración gráfica en ELAN |
| [`docs/fase_6_validacion_final.md`](docs/fase_6_validacion_final.md) | Escenarios E-01…E-15, caja blanca y rendimiento |
| [`docs/guia_nuevo_backend_modelo.md`](docs/guia_nuevo_backend_modelo.md) | Cómo crear e instalar un backend nuevo |

## Limitaciones

- Requiere Docker Desktop o Docker Engine en la estación de trabajo.
- Escenario local de usuario único: la API escucha solo en `127.0.0.1:8000`.
- Los jobs y las métricas viven en memoria (se pierden al reiniciar).
- El middleware no genera archivos EAF ni modifica el núcleo de ELAN: propone
  segmentos y la anotación final queda bajo revisión del investigador.
