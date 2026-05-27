# Middleware FastAPI - Version Final Docker

Middleware de orquestacion para conectar ELAN con backends de modelos de IA sin
acoplar ELAN ni el middleware a PyTorch, MediaPipe, BIO, CUDA u otra
arquitectura concreta de modelo.

La frontera final es HTTP:

```text
ELAN
  -> POST /api/v1/jobs/segment-video
  -> Middleware FastAPI
  -> Backend de modelo HTTP en Docker
```

## Arquitectura Final

El despliegue recomendado usa Docker Compose:

```text
middleware
lsec-bio-gloss-model
```

El middleware:

- valida contratos;
- administra registry de modelos;
- administra jobs;
- selecciona backends `docker_http`;
- llama `GET /health` y `POST /infer` del backend;
- devuelve segmentos compatibles con ELAN.

El backend de modelo:

- contiene preprocesamiento;
- contiene pesos/configuracion del modelo;
- ejecuta inferencia;
- postprocesa;
- devuelve `media_info` y `segments`.

## Levantar Todo

Desde esta carpeta:

```bash
docker compose up --build
```

El middleware queda disponible en:

```text
http://127.0.0.1:8000
```

Verificar:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/models
```

Debe aparecer:

```text
lsec_bio_gloss_pipeline_v1
```

registrado como modelo `docker_http`.

## Contrato Final Para ELAN/Postman

El cliente no debe enviar `runner: keypoint_pipeline` ni parametros internos del
pipeline. Esos valores pertenecen al backend del modelo.

Request recomendado:

```json
{
  "job_id": "job-postman-lsec-001",
  "media": {
    "path": "/data/videos/video_001.mp4"
  },
  "annotation": {
    "target_tier": "AUTO_GLOSS_SEGMENTS",
    "default_label": "LSEC_REGION",
    "label_mode": "gloss_top1"
  },
  "model": {
    "model_id": "lsec_bio_gloss_pipeline_v1",
    "version": "1.0.0"
  },
  "execution": {
    "timeout_sec": 300
  }
}
```

`execution` y `parameters` son opcionales. Si el cliente envia parametros
antiguos por compatibilidad, el middleware los reenvia al backend, pero no los
interpreta.

## Probar En Postman

Variables:

```text
base_url = http://127.0.0.1:8000
job_id = job-postman-lsec-001
model_id = lsec_bio_gloss_pipeline_v1
model_version = 1.0.0
video_path = /data/videos/video_001.mp4
```

### Health

```text
GET {{base_url}}/health
```

### Modelos

```text
GET {{base_url}}/api/v1/models
```

### Ejecutar Modelo

```text
POST {{base_url}}/api/v1/jobs/segment-video
Content-Type: application/json
```

Body:

```json
{
  "job_id": "{{job_id}}",
  "media": {
    "path": "{{video_path}}"
  },
  "annotation": {
    "target_tier": "AUTO_GLOSS_SEGMENTS",
    "default_label": "LSEC_REGION",
    "label_mode": "gloss_top1"
  },
  "model": {
    "model_id": "{{model_id}}",
    "version": "{{model_version}}"
  },
  "execution": {
    "timeout_sec": 300
  }
}
```

### Consultar Job

```text
GET {{base_url}}/api/v1/jobs/{{job_id}}
```

## Respuesta

La respuesta conserva:

```json
{
  "job_id": "job-postman-lsec-001",
  "status": "COMPLETED",
  "media_info": {
    "fps": 25.0,
    "duration_ms": 10000,
    "total_frames": 250
  },
  "segments": [
    {
      "start_ms": 1000,
      "end_ms": 2500,
      "label": "LSEC_REGION",
      "confidence": 0.91
    }
  ],
  "trace": {
    "runner": "docker_http",
    "docker_mode": "compose_service",
    "model_id": "lsec_bio_gloss_pipeline_v1",
    "model_version": "1.0.0"
  }
}
```

ELAN debe consumir principalmente:

- `segments[].start_ms`
- `segments[].end_ms`
- `segments[].label`
- `segments[].confidence`

## Backend Del Modelo Final

El servicio `lsec-bio-gloss-model` incluido es un backend HTTP de referencia para
el despliegue. Su configuracion interna esta en:

```text
examples/docker_model_backend/model_config/pipeline_config.json
```

Ese archivo representa los parametros que antes se enviaban desde Postman:

- `bio_window_size`
- `bio_stride`
- `gloss_max_len`
- `pose_idx`
- `raw_feature_dim`
- `final_feature_dim`
- etc.

En la arquitectura final, esos parametros pertenecen al backend del modelo, no
al cliente.

La imagen del backend copia tambien el paquete instalado:

```text
app/models_store/installed/lsec_bio_gloss_pipeline_v1/1.0.0
```

dentro de:

```text
/model_service/model_package
```

Ese es el lugar donde debe conectarse la implementacion real de inferencia del
backend.

## Integrar Otro Modelo

Para integrar otro backend:

1. Crear una imagen Docker del modelo.
2. Exponer `GET /health`.
3. Exponer `POST /infer`.
4. Agregar el servicio al `docker-compose.yml`.
5. Crear un manifest con `runtime.mode=docker` y `runner=docker_http`.
6. Copiar el manifest al directorio de bootstrap o instalarlo por
   `/api/v1/models/install`.

ELAN no cambia.

## Métricas

```text
GET {{base_url}}/api/v1/metrics
```

Devuelve contadores acumulados desde que el middleware arrancó:

```json
{
  "total_jobs": 5,
  "completed_jobs": 4,
  "failed_jobs": 0,
  "timeout_jobs": 1,
  "active_jobs": 0,
  "queued_jobs": 0,
  "average_exec_ms": 3420.5,
  "last_exec_ms": 3100,
  "error_counts": {
    "DOCKER_TIMEOUT": 1
  }
}
```

Todos los valores se reinician al reiniciar el middleware.

## Variables De Entorno

- `MIDDLEWARE_MODELS_STORE_DIR`: ruta del registry persistente.
- `MIDDLEWARE_BOOTSTRAP_MANIFESTS_DIR`: manifests cargados al iniciar.
- `MIDDLEWARE_RUNTIME_PROFILE`: perfil de ejecucion. En entrega se usa `final`.
- `MIDDLEWARE_MAX_CONCURRENT_JOBS`: número máximo de jobs de inferencia simultáneos.
  Controla cuántos backends Docker pueden inferir al mismo tiempo (control de VRAM).
  Valor por defecto: `1`. Aumentar solo si hay VRAM suficiente para múltiples modelos.

## Limitaciones

- Se requiere Docker Desktop o Docker Engine.
- El backend recibe `media.path`; el video debe estar en una ruta accesible para
  el contenedor de modelo.
- El backend de referencia ya empaqueta los artefactos instalados del modelo,
  pero su endpoint `/infer` debe conectarse con la implementacion real de
  inferencia para producir resultados reales.
- El middleware no genera EAF.
- El middleware no modifica ELAN.
