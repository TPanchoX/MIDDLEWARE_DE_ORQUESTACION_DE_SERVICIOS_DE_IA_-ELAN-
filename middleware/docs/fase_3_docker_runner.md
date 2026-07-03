# Fase 3 — Docker Runner e Inferencia

## 1. Descripción general

El **DockerRunner** es el único runtime de ejecución activo en el middleware. Su responsabilidad es:

1. Asegurarse de que el contenedor del modelo esté corriendo.
2. Verificar que el contenedor responde al health check.
3. Enviar el payload de inferencia al endpoint `/infer` del contenedor.
4. Adaptar la respuesta del contenedor al contrato de salida del middleware.

---

## 2. Arquitectura de red

Tanto el middleware como los contenedores de modelo se comunican a través de la red Docker `elan-ai-shared`. Esta red tiene un nombre fijo (no depende del nombre del proyecto de Compose).

```
docker-compose.yml define:
  networks:
    shared:
      name: elan-ai-shared

El middleware se une a esta red en el arranque.
Cada contenedor de modelo se une a esta red al ser creado.
```

**Ventaja clave:** Los contenedores se comunican por **nombre de contenedor** como hostname (DNS interno de Docker). No se necesita mapeo de puertos al host para la comunicación interna.

```
Middleware container  →  http://elan-ai-model-lsec_bio_gloss_final_v1-1.0.0:8080/health
                      →  http://elan-ai-model-lsec_bio_gloss_final_v1-1.0.0:8080/infer
```

---

## 3. Endpoint de inferencia — contrato de entrada

**Método:** `POST`  
**URL:** `http://localhost:8000/api/v1/jobs/segment-video`  
**Content-Type:** `application/json`

### Contrato de entrada (SegmentVideoRequest)

```json
{
  "job_id": "job-fase-7-bio-gloss-v2-270526",
  "media": {
    "path": "/data/videos/PruebaPato.mp4"
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

### Descripción de cada campo

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `job_id` | string | ✅ | Identificador único del job (cualquier string no vacío) |
| `media.path` | string | ✅ | Ruta del video: **ruta del host** (se traduce automáticamente) o ruta interna `/data/videos/...` |
| `annotation.target_tier` | string | ✅ | Nombre del tier de ELAN donde se insertarán las anotaciones |
| `annotation.default_label` | string | ✅ | Etiqueta por defecto para segmentos sin clasificación |
| `annotation.label_mode` | string | ❌ | `"gloss_top1"` para usar la glosa top-1; `null` usa `default_label` |
| `model.model_id` | string | ✅ | ID del modelo instalado en el registry |
| `model.version` | string | ✅ | Versión del modelo |
| `execution.device_preference` | string | ❌ | `"auto"` (default), `"cpu"` o `"cuda"` |
| `execution.runner` | string | ❌ | `"auto"` (default) |
| `execution.timeout_sec` | int | ❌ | Timeout en segundos para la inferencia (default: 300) |
| `parameters` | object | ❌ | Parámetros adicionales pasados al backend (libre) |

### Sobre el campo `media.path`

El video debe ser accesible **dentro del contenedor del modelo**. El middleware monta la carpeta configurada en `MIDDLEWARE_VIDEOS_DIR` en el contenedor al crearlo, bajo `/data/videos` (solo lectura).

El cliente puede enviar la **ruta del host directamente** (es lo que hace ELAN): el método `DockerRunner._translate_media_path()` detecta el prefijo `MIDDLEWARE_VIDEOS_DIR` (comparación insensible a mayúsculas, tolera `\` y `/`) y lo reemplaza por el punto de montaje del contenedor antes de llamar al backend.

```
Si MIDDLEWARE_VIDEOS_DIR = "C:/Users/imbaq/OneDrive/Desktop"
y media.path = "C:/Users/imbaq/OneDrive/Desktop/PruebaPato.mp4"

El backend recibe: "/data/videos/PruebaPato.mp4"
```

Las subcarpetas se conservan en la traducción:
```
media.path:        C:/Users/imbaq/OneDrive/Desktop/tesis/videos/sena.mp4
el backend recibe: /data/videos/tesis/videos/sena.mp4
```

También se acepta la ruta interna ya traducida (`/data/videos/...`): al no coincidir con el prefijo del host, pasa sin cambios. Si la ruta no está bajo `MIDDLEWARE_VIDEOS_DIR` ni bajo el punto de montaje, el backend no podrá abrir el archivo y la inferencia fallará con `DOCKER_INFERENCE_ERROR`.

> Para usar videos de otra carpeta, actualizar `MIDDLEWARE_VIDEOS_DIR` en `docker-compose.yml`, levantar de nuevo el middleware y eliminar el contenedor del modelo para que se recree con el nuevo mount.

---

## 4. Contrato de salida (SegmentVideoResponse)

```json
{
  "job_id": "job-fase-7-bio-gloss-v2-270526",
  "status": "COMPLETED",
  "media_info": {
    "fps": 59.94,
    "duration_ms": 8508,
    "total_frames": 510
  },
  "segments": [
    {
      "start_ms": 884,
      "end_ms": 1518,
      "label": "TRABAJAR",
      "confidence": 0.164,
      "segment_id": null,
      "start_frame": null,
      "end_frame": null,
      "duration_frames": null,
      "predictions": [
        {"rank": 1, "gloss_id": 10, "gloss": "TRABAJAR",  "probability": 0.164},
        {"rank": 2, "gloss_id": 7,  "gloss": "VER",       "probability": 0.126},
        {"rank": 3, "gloss_id": 11, "gloss": "BIEN",      "probability": 0.114},
        {"rank": 4, "gloss_id": 16, "gloss": "AYUDAR",    "probability": 0.107},
        {"rank": 5, "gloss_id": 5,  "gloss": "BUSCAR",    "probability": 0.090}
      ]
    }
  ],
  "trace": {
    "runner": "docker_http",
    "device": "container",
    "model_id": "lsec_bio_gloss_final_v1",
    "model_version": "1.0.0",
    "output_type": "segments_with_gloss",
    "exec_ms": 33725,
    "stages": {
      "validation_ms": 1,
      "queue_ms": 1,
      "inference_ms": 33722,
      "postprocessing_ms": 1,
      "container_start_ms": 0,
      "healthcheck_ms": 3,
      "docker_inference_ms": 33563,
      "total_ms": 33725
    },
    "state_history": [
      "RECEIVED", "VALIDATING", "PREPROCESSING",
      "QUEUED", "RUNNING", "POSTPROCESSING", "COMPLETED"
    ],
    "fps": 59.94,
    "total_frames": 510,
    "n_detected_segments": 6,
    "docker_mode": "sdk_managed",
    "docker_image": "lsec-bio-gloss-final:1.0.0",
    "container_id": "388b391a5eb1...",
    "container_start_ms": 0,
    "healthcheck_ms": 3,
    "docker_inference_ms": 33563,
    "total_ms": 33725
  }
}
```

### Descripción de los campos de salida

#### `media_info`
| Campo | Tipo | Descripción |
|---|---|---|
| `fps` | float | Fotogramas por segundo del video |
| `duration_ms` | int | Duración total en milisegundos |
| `total_frames` | int | Total de frames del video |

#### `segments[]` — cada segmento detectado
| Campo | Tipo | Descripción |
|---|---|---|
| `start_ms` | int | Inicio del segmento en ms desde el comienzo del video |
| `end_ms` | int | Fin del segmento en ms |
| `label` | string | Glosa top-1 (si `label_mode="gloss_top1"`) |
| `confidence` | float | Probabilidad de la predicción top-1 (0.0–1.0) |
| `segment_id` | int\|null | ID del segmento (puede ser null) |
| `start_frame` | int\|null | Frame de inicio (puede ser null) |
| `end_frame` | int\|null | Frame de fin (puede ser null) |
| `duration_frames` | int\|null | Duración en frames (puede ser null) |
| `predictions[]` | array | Top-5 clasificaciones con rank, gloss_id, gloss y probability |

#### `trace` — trazabilidad de la ejecución
El trace contiene información detallada de cada etapa. Los campos más relevantes:

| Campo | Descripción |
|---|---|
| `runner` | Siempre `"docker_http"` |
| `device` | Siempre `"container"` |
| `docker_mode` | `"sdk_managed"` (el middleware maneja el ciclo de vida del contenedor) |
| `docker_image` | Imagen Docker usada |
| `container_id` | ID del contenedor Docker |
| `container_start_ms` | ms que tardó en arrancar el contenedor (0 si ya estaba corriendo) |
| `healthcheck_ms` | ms que tardó el health check |
| `docker_inference_ms` | ms que tardó el POST /infer al backend |
| `exec_ms` / `total_ms` | Tiempo total del job en ms |

---

## 5. Flujo interno completo de una inferencia

```
POST /api/v1/jobs/segment-video
│
├─ [RECEIVED] Request registrado
│
├─ [VALIDATING] JobService.create_segment_video_job()
│   └── registry_service.get_available_model(model_id, version)
│       ├── ✓ Modelo existe y status="available"
│       └── ✗ 404 MODEL_NOT_FOUND o 409 MODEL_DISABLED
│
├─ [PREPROCESSING] RunnerSelector.select(model) + construcción del InferenceInput:
│   ├── model.runtime.mode == "docker" → DockerRunner
│   ├── artifacts: dict del manifest (+ docker_image derivado de backend_config)
│   ├── container: sección "container" del manifest
│   └── media_path, model_id, version, annotation, parameters
│
├─ [QUEUED] job_queue.submit() — espera un slot FIFO si hay otro job activo
│
├─ [RUNNING] DockerRunner.run(inference_input)
│   │
│   ├── 1. _docker_image() → "lsec-bio-gloss-final:1.0.0"
│   │
│   ├── 2. DockerService.ensure_container()
│   │   ├── Busca contenedor: "elan-ai-model-lsec_bio_gloss_final_v1-1.0.0"
│   │   ├── [existe y running] → reutiliza
│   │   ├── [existe y stopped] → container.start()
│   │   └── [no existe] → containers.run(
│   │           image="lsec-bio-gloss-final:1.0.0",
│   │           network="elan-ai-shared",
│   │           volumes={"C:/...Desktop": {bind: "/data/videos", mode: "ro"}},
│   │           labels={elan-ai-orchestrator: true, ...}
│   │       )
│   │   └── base_url = "http://elan-ai-model-lsec_bio_gloss_final_v1-1.0.0:8080"
│   │
│   ├── 3. DockerService.wait_for_health()
│   │   └── GET base_url/health (timeout: 30s, retry cada 250ms)
│   │       ├── 200 → continuar
│   │       └── timeout → DockerContainerHealthcheckFailedError
│   │
│   ├── 4. DockerService.post_json()
│   │   └── POST base_url/infer con payload:
│   │       {job_id, media:{path}, annotation, parameters, model, execution}
│   │       ├── 200 → DecodedJSON
│   │       ├── 422 → DockerInferenceError (con detalle del backend)
│   │       └── timeout → DockerTimeoutError
│   │
│   └── 5. _adapt_response(payload)
│       └── valida que payload tiene "segments" y "media_info"
│
├─ [POSTPROCESSING] JobService valida output_type
│
└─ [COMPLETED] SegmentVideoResponse devuelta
```

---

## 6. Comportamiento según estado del contenedor

| Estado del contenedor | Comportamiento |
|---|---|
| Corriendo ✅ | Reutilizado directamente. `container_start_ms = 0` |
| Parado ⏸️ | Arrancado automáticamente con `container.start()` |
| Eliminado ❌ (imagen existe) | Recreado desde la imagen Docker con todos los mounts |
| Imagen eliminada 💀 | Falla con `DOCKER_IMAGE_NOT_FOUND`. Necesita reinstalar el paquete |

---

## 7. Payload que el middleware envía al backend del modelo

El middleware transforma el request externo en este payload que envía al endpoint `/infer` del contenedor:

```json
{
  "job_id": "job-fase-7-bio-gloss-v2-270526",
  "media": {
    "path": "/data/videos/PruebaPato.mp4"
  },
  "annotation": {
    "target_tier": "AUTO_GLOSS_SEGMENTS",
    "default_label": "LSEC_REGION",
    "label_mode": "gloss_top1"
  },
  "parameters": {},
  "model": {
    "model_id": "lsec_bio_gloss_final_v1",
    "version": "1.0.0"
  },
  "execution": {
    "device_preference": "auto",
    "runner": "auto",
    "timeout_sec": 300
  }
}
```

El payload que recibe el backend es idéntico al que envía el cliente, con la excepción de que `parameters` siempre se incluye (aunque vacío).

---

## 8. Respuesta que debe devolver el backend del modelo

El backend debe devolver una respuesta JSON con esta estructura mínima:

```json
{
  "output_type": "segments_with_gloss",
  "media_info": {
    "fps": 59.94,
    "duration_ms": 8508,
    "total_frames": 510
  },
  "segments": [
    {
      "start_ms": 884,
      "end_ms": 1518,
      "label": "TRABAJAR",
      "confidence": 0.164,
      "predictions": [
        {"rank": 1, "gloss_id": 10, "gloss": "TRABAJAR", "probability": 0.164},
        {"rank": 2, "gloss_id": 7,  "gloss": "VER",      "probability": 0.126}
      ]
    }
  ]
}
```

> ⚠️ Si el backend devuelve error HTTP (4xx/5xx), el middleware captura el body JSON y extrae el campo `detail` para mostrarlo al cliente. El código de error del middleware será `DOCKER_INFERENCE_ERROR`.

---

## 9. Errores del Docker Runner

| error_code | Código HTTP | Causa |
|---|---|---|
| `DOCKER_NOT_AVAILABLE` | 503 | Docker no está corriendo o SDK no instalado |
| `DOCKER_IMAGE_NOT_FOUND` | 404 | La imagen no existe (modelo eliminado) |
| `DOCKER_CONTAINER_START_ERROR` | 502 | No se pudo iniciar el contenedor |
| `DOCKER_CONTAINER_HEALTHCHECK_FAILED` | 502 | El contenedor no respondió en el tiempo límite |
| `DOCKER_INFERENCE_ERROR` | 502 | El backend devolvió un error HTTP |
| `DOCKER_TIMEOUT` | 504 | La inferencia tardó más de `timeout_sec` |
| `UNSUPPORTED_DOCKER_CONTRACT` | 422 | La respuesta del backend no tiene `segments` o `media_info` |

---

## 10. Gestión del volumen de videos

El middleware monta el directorio de videos al **crear** el contenedor. El contenedor mantiene ese mount mientras esté vivo.

```
docker-compose.yml:
  MIDDLEWARE_VIDEOS_DIR: "C:/Users/imbaq/OneDrive/Desktop"

Resultado en el contenedor:
  /data/videos/ → C:/Users/imbaq/OneDrive/Desktop (read-only)
```

### Cambiar el directorio de videos

1. Editar `MIDDLEWARE_VIDEOS_DIR` en `docker-compose.yml`.
2. Eliminar el contenedor del modelo para que se recree con el nuevo mount:
   ```bash
   docker rm -f elan-ai-model-lsec_bio_gloss_final_v1-1.0.0
   ```
3. Reconstruir el middleware:
   ```bash
   docker compose up --build -d
   ```
4. La próxima inferencia recreará el contenedor con el nuevo directorio montado.

---

## 11. Comandos de diagnóstico

```bash
# Ver logs del middleware
docker compose logs -f middleware

# Ver logs del contenedor del modelo
docker logs -f elan-ai-model-lsec_bio_gloss_final_v1-1.0.0

# Verificar la red compartida y qué contenedores están en ella
docker network inspect elan-ai-shared

# Listar contenedores activos con su red
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Networks}}"

# Probar el health check del modelo directamente desde el host
curl http://localhost:$(docker inspect --format='{{(index (index .NetworkSettings.Ports "8080/tcp") 0).HostPort}}' elan-ai-model-lsec_bio_gloss_final_v1-1.0.0)/health
```

> Los contenedores de modelo **no exponen puerto al host** cuando usan la red compartida. Para acceder desde el host (Postman, curl) tienes que ir a través del middleware en `:8000`.

---

## 12. Ejemplo completo de prueba con Postman

**Configuración:**
- Método: `POST`
- URL: `http://localhost:8000/api/v1/jobs/segment-video`
- Headers: `Content-Type: application/json`
- Body (raw JSON):

```json
{
  "job_id": "test-001",
  "media": {
    "path": "/data/videos/mi_video.mp4"
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

**Respuesta esperada:** 200 OK con `status: "COMPLETED"` y array de `segments`.

**Si es la primera inferencia después de reiniciar el middleware:** El contenedor se recreará automáticamente. La primera request tardará más (~30-60 s para levantar el contenedor y cargar los modelos PyTorch).
