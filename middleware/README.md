# Middleware FastAPI - Fases 1 a 7

Middleware local para orquestar modelos de IA desde ELAN sin acoplar ELAN a
Python, PyTorch, CUDA o Docker. Las fases actuales cubren API base, registry de
modelos, runner dummy, procesamiento real de video, ejecucion nativa PyTorch y
pipeline compuesto BIO + Keypoint Transformer.

## Alcance actual

- FastAPI con endpoints de salud, modelos y jobs.
- Registry persistente en `app/models_store/registry.json`.
- Instalacion de modelos por paquetes zip con `manifest.json`.
- Procesamiento real de video con OpenCV y NumPy.
- Ventanas temporales `T,H,W,C` con frames RGB `float32`.
- `DummyRunner` para simulacion.
- `NativePyTorchRunner` para modelos `runtime.mode=native` y
  `runtime.framework=pytorch`.
- `KeypointPipelineRunner` para modelos con
  `runtime.runner=keypoint_pipeline`.
- Arquitectura base `VideoBinarySegmenter`.
- Arquitecturas `BioSegmenterBiLSTM` y `KeypointTransformerClassifierV11`.
- Agregacion de probabilidades por frame global.
- Postprocesamiento temporal compartido para generar segmentos.
- Extraccion de keypoints reales con MediaPipe Holistic.
- Postprocesamiento BIO y clasificacion de glosas top-k.

## Fuera de alcance todavia

- Docker runner.
- Integracion ELAN real.
- Generacion de archivos EAF.
- Base de datos.

## Instalacion

```bash
cd middleware
pip install -r requirements.txt
```

## Ejecucion

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Preparar datos de prueba

Crear video artificial:

```bash
python scripts/create_test_video.py
```

Crear paquetes PyTorch de ejemplo compatible e incompatible:

```bash
python scripts/create_pytorch_model_package.py
```

Archivos generados:

```text
examples/videos/test_lsec_dummy.mp4
examples/model_packages/generated_pytorch/pytorch_binary_segmenter_demo.zip
examples/model_packages/generated_pytorch/pytorch_incompatible_demo.zip
```

## Endpoints

- `GET /health`
- `GET /api/v1/models`
- `POST /api/v1/models/install`
- `GET /api/v1/models/{model_id}`
- `PATCH /api/v1/models/{model_id}/status`
- `POST /api/v1/jobs/segment-video`
- `GET /api/v1/jobs/{job_id}`

## Probar DummyRunner

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "job-dummy",
    "media": {"path": "examples/videos/test_lsec_dummy.mp4"},
    "annotation": {"target_tier": "AUTO_SEGMENTS", "default_label": "LSEC_REGION"},
    "model": {"model_id": "dummy_lsec_segmenter", "version": "0.1.0"},
    "execution": {"device_preference": "auto", "runner": "auto", "timeout_sec": 300},
    "parameters": {"threshold": 0.5, "window_size": 16, "stride": 4, "min_segment_ms": 200, "merge_gap_ms": 120}
  }'
```

## Probar NativePyTorchRunner

Instalar modelo compatible:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/models/install \
  -F "file=@examples/model_packages/generated_pytorch/pytorch_binary_segmenter_demo.zip"
```

Ejecutar inferencia en CPU:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "job-pytorch",
    "media": {"path": "examples/videos/test_lsec_dummy.mp4"},
    "annotation": {"target_tier": "AUTO_SEGMENTS", "default_label": "LSEC_REGION"},
    "model": {"model_id": "pytorch_binary_segmenter_demo", "version": "1.0.0"},
    "execution": {"device_preference": "cpu", "runner": "auto", "timeout_sec": 300},
    "parameters": {"threshold": 0.5, "window_size": 16, "stride": 4, "min_segment_ms": 200, "merge_gap_ms": 120}
  }'
```

Consultar resultado:

```bash
curl http://127.0.0.1:8000/api/v1/jobs/job-pytorch
```

## Probar modelo incompatible

```bash
curl -X POST http://127.0.0.1:8000/api/v1/models/install \
  -F "file=@examples/model_packages/generated_pytorch/pytorch_incompatible_demo.zip"
```

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "job-bad-pytorch",
    "media": {"path": "examples/videos/test_lsec_dummy.mp4"},
    "annotation": {"target_tier": "AUTO_SEGMENTS", "default_label": "LSEC_REGION"},
    "model": {"model_id": "pytorch_incompatible_demo", "version": "1.0.0"},
    "execution": {"device_preference": "cpu", "runner": "auto", "timeout_sec": 300},
    "parameters": {"threshold": 0.5, "window_size": 16, "stride": 4, "min_segment_ms": 200, "merge_gap_ms": 120}
  }'
```

Debe responder `MODEL_ARCHITECTURE_MISMATCH`.

## Probar KeypointPipelineRunner

Preparar el paquete compuesto:

```powershell
cd examples/model_packages/lsec_bio_gloss_pipeline_v1
Copy-Item C:\Ruta\Modelos\best_bio_segmenter_v2.pt .\weights\
Copy-Item C:\Ruta\Modelos\best_keypoint_transformer_v11.pt .\weights\
cd ..
Compress-Archive -Path .\lsec_bio_gloss_pipeline_v1\* -DestinationPath .\lsec_bio_gloss_pipeline_v1.zip -Force
```

Estructura esperada del zip:

```text
lsec_bio_gloss_pipeline_v1.zip
  manifest.json
  weights/
    best_bio_segmenter_v2.pt
    best_keypoint_transformer_v11.pt
  vocab/
    gloss_vocab_top20.csv
  config/
    pipeline_config.json
  README.md
```

Instalar:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/models/install \
  -F "file=@examples/model_packages/lsec_bio_gloss_pipeline_v1.zip"
```

Ejecutar en CPU:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "job-fase-7-bio-gloss",
    "media": {"path": "examples/videos/test_lsec_dummy.mp4"},
    "annotation": {"target_tier": "AUTO_GLOSS_SEGMENTS", "default_label": "LSEC_REGION", "label_mode": "gloss_top1"},
    "model": {"model_id": "lsec_bio_gloss_pipeline_v1", "version": "1.0.0"},
    "execution": {"device_preference": "cpu", "runner": "auto", "timeout_sec": 300},
    "parameters": {
      "bio_window_size": 64,
      "bio_stride": 32,
      "gloss_max_len": 64,
      "smooth_kernel": 3,
      "min_segment_len": 4,
      "max_gap_fill": 0,
      "min_i_after_b": 3,
      "top_k": 5
    }
  }'
```

La respuesta mantiene `segments[].start_ms`, `segments[].end_ms`,
`segments[].label` y `segments[].confidence`. En Fase 7 `label` es la glosa
top-1 y `predictions` contiene el top-k.

## CUDA opcional

`device_preference` acepta:

- `auto`: usa CUDA si esta disponible; si no, CPU.
- `cpu`: fuerza CPU.
- `cuda`: usa CUDA si esta disponible; si no, responde `CUDA_NOT_AVAILABLE`.

## Trace PyTorch

El trace incluye:

- `runner`
- `device`
- `model_id`
- `model_version`
- `output_type`
- `windows_count`
- `stages.model_load_ms`
- `stages.tensor_conversion_ms`
- `stages.inference_ms`
- `stages.aggregation_ms`
- metricas de video de Fase 4
- `stages.postprocessing_ms`
- `stages.total_ms`

## Errores principales

- `MODEL_LOAD_ERROR`
- `MODEL_ARCHITECTURE_MISMATCH`
- `PYTORCH_INFERENCE_ERROR`
- `BIO_MODEL_LOAD_ERROR`
- `GLOSS_MODEL_LOAD_ERROR`
- `BIO_INFERENCE_ERROR`
- `GLOSS_INFERENCE_ERROR`
- `MEDIAPIPE_IMPORT_ERROR`
- `KEYPOINT_EXTRACTION_ERROR`
- `KEYPOINTS_EMPTY`
- `VOCAB_NOT_FOUND`
- `VOCAB_INVALID`
- `CUDA_NOT_AVAILABLE`
- `INVALID_TENSOR_SHAPE`
- `INVALID_KEYPOINT_SHAPE`
- `UNSUPPORTED_RUNTIME`
- `UNSUPPORTED_FRAMEWORK`
- `VIDEO_NOT_FOUND`
- `MODEL_NOT_FOUND`
- `MODEL_DISABLED`

## Preparacion para ELAN

El contrato externo sigue siendo `POST /api/v1/jobs/segment-video`. ELAN podra
enviar el video y el modelo seleccionado sin conocer si internamente corre dummy,
PyTorch nativo o, mas adelante, Docker. La respuesta sigue siendo JSON con
segmentos temporales listos para convertirse en anotaciones.

## Limitaciones Fase 7

- El middleware no genera EAF; ELAN crea anotaciones desde el JSON.
- Los `.pt` deben ser `state_dict` compatibles con las arquitecturas locales.
- Docker sigue fuera de alcance.
- MediaPipe debe estar instalado en el entorno Python donde corre Uvicorn.
- El paquete ejemplo no incluye pesos reales; deben copiarse antes de comprimir.
