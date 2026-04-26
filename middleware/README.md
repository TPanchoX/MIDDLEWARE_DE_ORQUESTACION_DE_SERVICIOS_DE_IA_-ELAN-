# Middleware FastAPI - Fase 1

Este directorio contiene la base funcional del middleware local que conectara ELAN con futuros servicios de IA. En esta fase el middleware expone contratos HTTP, administra modelos en memoria, crea jobs simulados de segmentacion y devuelve respuestas JSON compatibles con la arquitectura final.

## Alcance de esta fase

- FastAPI como base del middleware local.
- Registro de modelos en memoria con un modelo dummy disponible.
- Creacion y consulta de jobs de segmentacion simulados.
- Logging basico y configuracion centralizada.
- Documentacion tecnica y funcional de la fase.

## Lo que no hace todavia

- No integra ELAN real.
- No usa PyTorch.
- No usa Docker.
- No procesa video real.
- No persiste en base de datos.

## Estructura del proyecto

```text
middleware/
|-- app/
|   |-- main.py
|   |-- api/
|   |   |-- routes_health.py
|   |   |-- routes_models.py
|   |   `-- routes_jobs.py
|   |-- core/
|   |   |-- config.py
|   |   `-- logging_config.py
|   |-- schemas/
|   |   |-- common.py
|   |   |-- models.py
|   |   `-- jobs.py
|   |-- services/
|   |   |-- model_registry_service.py
|   |   `-- job_service.py
|   `-- storage/
|       `-- memory_store.py
|-- docs/
|   |-- fase_1_middleware_base_tecnica.md
|   `-- fase_1_middleware_base_funcional.md
|-- tests/
|-- requirements.txt
`-- README.md
```

## Instalacion

```bash
cd middleware
pip install -r requirements.txt
```

## Ejecucion

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Endpoints disponibles

### GET /health

Verifica que el middleware este activo.

Respuesta esperada:

```json
{
  "status": "ok",
  "service": "elan-ai-orchestrator",
  "version": "0.1.0"
}
```

### GET /api/v1/models

Lista el modelo dummy registrado en memoria.

### POST /api/v1/jobs/segment-video

Crea un job de segmentacion simulado y devuelve un resultado completado.

### GET /api/v1/jobs/{job_id}

Recupera el resultado del job guardado en memoria.

## Ejemplos curl

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl http://127.0.0.1:8000/api/v1/models
```

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "job-001",
    "media": {
      "path": "C:/Videos/lsec/video_001.mp4"
    },
    "annotation": {
      "target_tier": "AUTO_SEGMENTS",
      "default_label": "LSEC_REGION"
    },
    "model": {
      "model_id": "dummy_lsec_segmenter",
      "version": "0.1.0"
    },
    "execution": {
      "device_preference": "auto",
      "runner": "auto",
      "timeout_sec": 300
    },
    "parameters": {
      "threshold": 0.5,
      "window_size": 16,
      "stride": 4,
      "min_segment_ms": 200,
      "merge_gap_ms": 120
    }
  }'
```

```bash
curl http://127.0.0.1:8000/api/v1/jobs/job-001
```

## Notas para la Fase 2

La estructura modular deja separados contratos, almacenamiento, servicios y rutas para facilitar la integracion posterior de runners reales, modelos PyTorch, ELAN y procesamiento de video sin rehacer la base de la API.
