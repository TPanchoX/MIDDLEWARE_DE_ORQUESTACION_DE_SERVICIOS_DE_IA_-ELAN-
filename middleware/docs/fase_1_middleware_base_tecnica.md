# Fase 1 - Base tecnica del middleware

## Objetivo tecnico

Construir una base FastAPI local, modular y verificable para el middleware de orquestacion que mas adelante integrara ELAN, modelos de IA y runners reales. En esta fase la prioridad es definir contratos, flujo interno, almacenamiento temporal y endpoints funcionales.

## Arquitectura de la fase

La Fase 1 implementa esta cadena simplificada:

ELAN futuro -> Bridge Java futuro -> FastAPI -> servicios internos -> almacenamiento en memoria -> respuesta JSON

Componentes implementados:

- `app/main.py`: crea la aplicacion FastAPI, registra routers y manejadores de errores.
- `app/api/`: expone los endpoints de salud, modelos y jobs.
- `app/core/`: centraliza configuracion y logging.
- `app/schemas/`: define contratos Pydantic de entrada y salida.
- `app/services/`: encapsula la logica de registry y jobs.
- `app/storage/`: mantiene modelos y jobs en memoria local.

## Endpoints

### `GET /health`

Retorna estado del servicio, nombre y version.

### `GET /api/v1/models`

Lista modelos registrados. En Fase 1 expone un unico modelo:

- `dummy_lsec_segmenter`
- `Dummy LSEC Segmenter`
- `0.1.0`
- `video_segmentation`
- `dummy`
- `available`

### `POST /api/v1/jobs/segment-video`

Valida el request con Pydantic, verifica que el modelo exista y crea un resultado simulado con estado `COMPLETED`.

### `GET /api/v1/jobs/{job_id}`

Consulta en memoria el job previamente guardado y devuelve su estado y resultado.

## Modelos Pydantic

Modelos principales:

- `HealthResponse`
- `ErrorResponse`
- `RegisteredModel`
- `ModelReference`
- `ModelListResponse`
- `JobStatus`
- `SegmentVideoRequest`
- `TemporalSegment`
- `MediaInfo`
- `ExecutionTrace`
- `SegmentVideoResponse`

## Flujo interno

1. El cliente envia un request HTTP.
2. FastAPI valida el payload con Pydantic.
3. El router delega en el servicio correspondiente.
4. `ModelRegistryService` consulta el modelo dummy en memoria.
5. `JobService` construye una respuesta simulada con segmentos temporales.
6. El job se guarda en `MemoryStore`.
7. El middleware responde JSON listo para una futura integracion con ELAN.

## Manejo de errores

- Modelo no encontrado: `404 model_not_found`
- Job no encontrado: `404 job_not_found`
- Payload invalido: `422` manejado por FastAPI/Pydantic
- Error interno no controlado: `500 internal_server_error`

## Decisiones tecnicas

- FastAPI para la capa HTTP.
- Pydantic para contratos y validacion.
- Uvicorn como servidor ASGI recomendado.
- Almacenamiento en memoria para evitar persistencia prematura.
- Servicios separados para mantener limpia la evolucion hacia runners reales.
- Respuestas dummy compatibles con el formato esperado por la arquitectura final.

## Limitaciones

- Sin ELAN real.
- Sin Docker.
- Sin PyTorch.
- Sin procesamiento real de frames o video.
- Sin cola de jobs real.
- Sin base de datos.
- Los jobs se pierden al reiniciar el proceso.
