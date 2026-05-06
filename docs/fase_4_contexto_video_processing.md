# Fase 4 - Procesamiento real de video

## Contexto
La Fase 1 creó el middleware base.
La Fase 2 implementó el registry de modelos.
La Fase 3 formalizó el flujo de inferencia con DummyRunner, RunnerSelector y postprocesador temporal.

Ahora la Fase 4 debe agregar lectura real de video, extracción de metadatos, validación del archivo, muestreo de frames y construcción de ventanas temporales. Esta fase prepara la entrada que luego consumirá el modelo PyTorch real.

## Objetivo de la Fase 4
Implementar el pipeline de procesamiento de video necesario para convertir un archivo de video en una representación estructurada que pueda ser usada por runners futuros.

## Alcance
Implementar:
- validación real de ruta de video;
- lectura de FPS, duración, total_frames, width y height;
- extracción/muestreo de frames;
- redimensionado;
- normalización básica;
- construcción de ventanas temporales;
- métricas de procesamiento;
- integración opcional con DummyRunner para usar metadatos reales del video;
- documentación técnica y funcional.

## Fuera de alcance
No implementar:
- PyTorch real;
- Docker real;
- inferencia real;
- integración con ELAN Java;
- generación de EAF;
- clasificación real de señas.

## Dependencias permitidas
Se permite usar:
- opencv-python
- numpy

No usar todavía:
- torch
- torchvision
- docker sdk
- ffmpeg externo obligatorio

## Componentes esperados

middleware/app/processing/
 ├── video_loader.py
 ├── frame_sampler.py
 ├── frame_preprocessor.py
 ├── window_builder.py
 └── video_pipeline.py

## video_loader.py
Debe:
- validar que la ruta existe;
- abrir el video con OpenCV;
- obtener:
  - fps
  - total_frames
  - duration_ms
  - width
  - height
  - codec si es posible;
- devolver un objeto VideoMetadata.

## frame_sampler.py
Debe:
- extraer frames del video;
- permitir limitar cantidad máxima de frames para pruebas;
- permitir stride temporal;
- devolver frames y sus índices originales.

## frame_preprocessor.py
Debe:
- redimensionar frames a width/height configurables, por defecto 224x224;
- convertir BGR a RGB;
- normalizar valores a rango 0.0 - 1.0;
- devolver numpy arrays.

## window_builder.py
Debe:
- construir ventanas temporales con:
  - window_size;
  - stride;
- devolver una estructura tipo:
  - window_id;
  - start_frame;
  - end_frame;
  - frame_indices;
  - array con shape T,H,W,C o T,C,H,W según decisión interna documentada.

## video_pipeline.py
Debe orquestar:
1. cargar metadata;
2. muestrear frames;
3. preprocesar frames;
4. construir ventanas;
5. devolver VideoProcessingResult.

## Integración con segment-video
El endpoint POST /api/v1/jobs/segment-video debe poder usar el pipeline real de video cuando la ruta exista.

En esta fase:
- DummyRunner puede seguir generando probabilidades simuladas;
- pero debe usar metadata real del video si está disponible:
  - fps real;
  - duration_ms real;
  - total_frames real.
- Si el video no existe, debe devolver error controlado VIDEO_NOT_FOUND.
- Si el video no se puede abrir, devolver VIDEO_OPEN_ERROR.
- Si no se extraen frames, devolver VIDEO_EMPTY_OR_INVALID.

## Schemas nuevos sugeridos
- VideoMetadata
- FrameSamplingConfig
- WindowConfig
- VideoProcessingResult
- VideoProcessingMetrics

## Errores esperados
- VIDEO_NOT_FOUND
- VIDEO_OPEN_ERROR
- VIDEO_EMPTY_OR_INVALID
- VIDEO_PROCESSING_ERROR
- INVALID_VIDEO_PATH

## Trazabilidad
El trace debe incluir:
- video_loading_ms
- frame_sampling_ms
- preprocessing_ms
- window_building_ms
- total_video_processing_ms
- fps
- total_frames
- sampled_frames
- windows_count
- original_width
- original_height

## Criterios de aceptación
La Fase 4 se considera completa si:
- se valida realmente la existencia del video;
- se lee metadata real;
- se extraen frames;
- se preprocesan frames;
- se construyen ventanas;
- segment-video puede usar un video real;
- DummyRunner usa metadata real para simular probabilidades;
- se rechaza un video inexistente con error controlado;
- los endpoints de Fase 1, 2 y 3 siguen funcionando;
- no se usa PyTorch;
- no se usa Docker;
- README y documentación quedan actualizados.