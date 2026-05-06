# Fase 3 - Dummy runner tecnico

## Objetivo tecnico

Formalizar el flujo interno de inferencia del middleware sin integrar todavia
PyTorch, Docker ni procesamiento real de video. La fase introduce runners,
selector de runners, contratos internos de inferencia y postprocesamiento
temporal.

## Arquitectura de la fase

Flujo principal:

Cliente HTTP -> `JobService` -> `RunnerSelector` -> `DummyRunner` ->
`TemporalPostprocessor` -> `MemoryStore` -> respuesta JSON

Componentes nuevos:

- `app/runners/base_runner.py`: interfaz base de runners.
- `app/runners/dummy_runner.py`: runner simulado que devuelve probabilidades por
  frame.
- `app/runners/runner_selector.py`: selecciona runner segun `runtime.mode`.
- `app/schemas/inference.py`: contratos internos de inferencia.
- `app/schemas/metrics.py`: metricas por etapa.
- `app/processing/temporal_postprocessor.py`: transforma probabilidades en
  segmentos temporales.

## Contratos internos

### `InferenceInput`

Contiene la informacion necesaria para ejecutar un runner:

- `job_id`
- `media_path`
- `model_id`
- `model_version`
- `runtime_mode`
- `runtime_framework`
- `device_preference`
- `runner_preference`
- `timeout_sec`
- `artifacts`

### `FrameProbabilityOutput`

Salida interna equivalente a una salida de modelo de segmentacion:

```json
{
  "output_type": "frame_probabilities",
  "fps": 25.0,
  "duration_ms": 10000,
  "total_frames": 250,
  "probabilities": [0.03, 0.04, 0.05]
}
```

### `InferenceOutput`

Envuelve la salida de probabilidades y metricas internas del runner.

### `StageMetrics`

Metricas expuestas en `trace.stages`:

- `validation_ms`
- `queue_ms`
- `inference_ms`
- `postprocessing_ms`
- `total_ms`

## DummyRunner

`DummyRunner` no devuelve segmentos. Genera probabilidades por frame para un
video simulado:

- `fps`: 25.0
- `duration_ms`: 10000
- `total_frames`: 250
- regiones positivas simuladas:
  - 1000 ms a 2500 ms
  - 4000 ms a 5600 ms

Estas regiones se expresan solamente como valores altos en el arreglo
`probabilities`.

## RunnerSelector

Regla actual:

- `runtime.mode = dummy`: selecciona `DummyRunner`.
- `runtime.mode = native`: devuelve `RUNTIME_NOT_SUPPORTED`.
- `runtime.mode = docker`: devuelve `RUNTIME_NOT_SUPPORTED`.

El error controlado usa HTTP 501 porque el runtime esta registrado pero no es
ejecutable todavia en esta fase.

## Postprocesamiento temporal

`TemporalPostprocessor` recibe `FrameProbabilityOutput`, parametros de
segmentacion y `default_label`.

Pasos:

1. aplica `threshold`;
2. detecta regiones consecutivas positivas;
3. convierte frames a `start_ms` y `end_ms`;
4. calcula `confidence` promedio de la region;
5. elimina segmentos menores a `min_segment_ms`;
6. fusiona segmentos con separacion menor a `merge_gap_ms`;
7. asigna la etiqueta `default_label`.

## Flujo de estados

`JobService` actualiza internamente los estados en este orden:

1. `RECEIVED`
2. `VALIDATING`
3. `QUEUED`
4. `RUNNING`
5. `POSTPROCESSING`
6. `COMPLETED`

La respuesta final incluye `trace.state_history` para dejar evidencia del flujo.

## Compatibilidad

Se mantienen los endpoints de Fases 1 y 2:

- `GET /health`
- `GET /api/v1/models`
- `POST /api/v1/models/install`
- `GET /api/v1/models/{model_id}`
- `PATCH /api/v1/models/{model_id}/status`
- `POST /api/v1/jobs/segment-video`
- `GET /api/v1/jobs/{job_id}`

El modelo builtin `dummy_lsec_segmenter` sigue funcionando. Los modelos
instalados con `runtime.mode = dummy` tambien usan `DummyRunner`.

## Limitaciones

- No se carga PyTorch.
- No se ejecuta Docker.
- No se leen frames reales.
- No se usa OpenCV ni FFmpeg.
- No se generan archivos EAF.
- No se ejecuta codigo desde paquetes de modelo.
- Los jobs siguen almacenados en memoria.
