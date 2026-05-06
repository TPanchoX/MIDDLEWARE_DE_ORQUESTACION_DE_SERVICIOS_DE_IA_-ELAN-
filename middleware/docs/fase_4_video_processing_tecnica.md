# Fase 4 - Procesamiento de video tecnico

## Objetivo tecnico

Agregar al middleware un pipeline real de lectura y procesamiento de video con
OpenCV y NumPy, sin integrar todavia PyTorch, Docker ni ELAN real. El objetivo es
preparar la entrada estructurada que consumira un runner PyTorch futuro.

## Componentes

- `app/schemas/video.py`: contratos internos de video.
- `app/processing/video_loader.py`: validacion de ruta y lectura de metadata.
- `app/processing/frame_sampler.py`: extraccion de frames reales.
- `app/processing/frame_preprocessor.py`: BGR a RGB, resize y normalizacion.
- `app/processing/window_builder.py`: construccion de ventanas temporales.
- `app/processing/video_pipeline.py`: orquestacion y metricas.
- `scripts/create_test_video.py`: generador de MP4 artificial para pruebas.

## Schemas internos

- `VideoMetadata`: path, fps, total_frames, duration_ms, width, height y codec.
- `FrameSamplingConfig`: `max_frames` y `frame_stride`.
- `WindowConfig`: `window_size` y `stride`.
- `VideoProcessingMetrics`: tiempos de carga, muestreo, preprocesamiento,
  ventanas y total.
- `VideoWindow`: `window_id`, `start_frame`, `end_frame`, `frame_indices` y
  arreglo de frames.
- `VideoProcessingResult`: metadata, indices muestreados, frames
  preprocesados, ventanas y metricas.

## Flujo

1. `JobService` valida modelo y estado.
2. Cambia a `PREPROCESSING`.
3. `VideoPipeline` carga metadata real del video.
4. `FrameSampler` extrae frames e indices originales.
5. `FramePreprocessor` convierte BGR a RGB, redimensiona y normaliza.
6. `WindowBuilder` construye ventanas temporales.
7. `RunnerSelector` selecciona `DummyRunner`.
8. `DummyRunner` simula probabilidades usando fps, duracion y frames reales.
9. `TemporalPostprocessor` genera segmentos.
10. Se guarda el resultado en memoria.

## Decisiones tecnicas

- FPS invalido: se devuelve `VIDEO_OPEN_ERROR`; no se usa fallback silencioso.
- Video sin frames o dimensiones invalidas: se devuelve `VIDEO_EMPTY_OR_INVALID`.
- Ventanas cortas: si hay menos frames que `window_size`, se repite el ultimo
  frame valido hasta completar la ventana. Esta decision conserva la forma fija
  esperada por modelos temporales.
- Shape interno de ventana: `T,H,W,C`.
- Frames preprocesados: RGB `float32` en rango `0.0..1.0`.
- `DummyRunner` no consume los pixeles todavia; solo usa metadata real.

## Errores

- `INVALID_VIDEO_PATH`: path vacio o no es archivo.
- `VIDEO_NOT_FOUND`: archivo inexistente.
- `VIDEO_OPEN_ERROR`: OpenCV no puede abrir el video o FPS invalido.
- `VIDEO_EMPTY_OR_INVALID`: no hay frames validos o dimensiones invalidas.
- `VIDEO_PROCESSING_ERROR`: error generico controlado del pipeline.

## Trace

`trace.stages` incluye:

- `video_loading_ms`
- `frame_sampling_ms`
- `preprocessing_ms`
- `window_building_ms`
- `total_video_processing_ms`
- `validation_ms`
- `queue_ms`
- `inference_ms`
- `postprocessing_ms`
- `total_ms`

`trace` tambien expone:

- `fps`
- `total_frames`
- `sampled_frames`
- `windows_count`
- `original_width`
- `original_height`

## Compatibilidad

Se mantienen los endpoints de Fases 1, 2 y 3:

- `GET /health`
- `GET /api/v1/models`
- `POST /api/v1/models/install`
- `GET /api/v1/models/{model_id}`
- `PATCH /api/v1/models/{model_id}/status`
- `POST /api/v1/jobs/segment-video`
- `GET /api/v1/jobs/{job_id}`

## Limitaciones

- No hay PyTorch.
- No hay Docker.
- No se modifica ELAN.
- No se generan archivos EAF.
- No se ejecuta inferencia real.
- Los jobs siguen en memoria.
