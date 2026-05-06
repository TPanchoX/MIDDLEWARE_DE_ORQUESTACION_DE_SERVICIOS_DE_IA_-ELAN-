# Fase 7 - Integración del pipeline final BIO + Keypoint Transformer

## Contexto
Las fases 1 a 6 ya implementaron:
- middleware FastAPI;
- registry de modelos por manifest;
- runner dummy;
- procesamiento real de video;
- NativePyTorchRunner;
- integración ELAN → Middleware → PyTorch → ELAN.

Ahora se integrará el pipeline final desarrollado para la tesis:
video → MediaPipe keypoints → BIO Segmenter v2 → postprocesamiento BIO → Keypoint Transformer v1.1 → glosa top-k → segmentos anotables para ELAN.

## Objetivo
Implementar un runner compuesto llamado KeypointPipelineRunner que use dos modelos PyTorch:
1. best_bio_segmenter_v2.pt
2. best_keypoint_transformer_v11.pt

El resultado debe mantener el contrato externo del middleware:
POST /api/v1/jobs/segment-video

La respuesta debe seguir devolviendo:
segments[].start_ms
segments[].end_ms
segments[].label
segments[].confidence

Pero ahora label debe ser la glosa top1 clasificada, no solo LSEC_REGION.

## Archivos fuente disponibles
El pipeline original está basado en:
- 20_pipeline_segment_and_classify.py
- 21_export_pipeline_to_eaf.py

El script 20 contiene:
- extracción de keypoints con MediaPipe Holistic;
- normalización por hombros;
- BIO Segmenter BiLSTM;
- postprocesamiento BIO;
- Keypoint Transformer Classifier V11;
- clasificación top-5 de glosas.

El script 21 NO debe usarse como salida principal, porque el middleware no debe generar EAF completo. ELAN debe crear las anotaciones desde el JSON.

## Archivos necesarios
Para que funcione el pipeline compuesto se requiere:
- best_bio_segmenter_v2.pt
- best_keypoint_transformer_v11.pt
- gloss_vocab_top20.csv

Además, se deben implementar en el middleware las arquitecturas:
- BioSegmenterBiLSTM
- KeypointTransformerClassifierV11

## Paquete de modelo esperado
El modelo compuesto debe instalarse como zip mediante el registry de modelos.

Estructura:

lsec_bio_gloss_pipeline_v1.zip
 ├── manifest.json
 ├── weights/
 │   ├── best_bio_segmenter_v2.pt
 │   └── best_keypoint_transformer_v11.pt
 ├── vocab/
 │   └── gloss_vocab_top20.csv
 ├── config/
 │   └── pipeline_config.json
 └── README.md

## Manifest esperado

{
  "model_id": "lsec_bio_gloss_pipeline_v1",
  "name": "LSEC BIO Segmenter + Gloss Classifier",
  "version": "1.0.0",
  "task": "video_segmentation_and_gloss_classification",
  "runtime": {
    "mode": "native",
    "framework": "pytorch",
    "runner": "keypoint_pipeline"
  },
  "artifacts": {
    "bio_weights": "weights/best_bio_segmenter_v2.pt",
    "gloss_weights": "weights/best_keypoint_transformer_v11.pt",
    "vocab": "vocab/gloss_vocab_top20.csv",
    "pipeline_config": "config/pipeline_config.json"
  },
  "input_contract": {
    "media_type": "video",
    "feature_type": "mediapipe_keypoints",
    "input_dim": 178
  },
  "output_contract": {
    "type": "segments_with_gloss",
    "classes": ["O", "B", "I"],
    "top_k": 5
  },
  "ui": {
    "default_target_tier": "AUTO_GLOSS_SEGMENTS",
    "label_mode": "gloss_top1",
    "supports_threshold": false
  }
}

## pipeline_config.json esperado

{
  "device_preference": "auto",
  "bio_window_size": 64,
  "bio_stride": 32,
  "gloss_max_len": 64,
  "num_bio_classes": 3,
  "smooth_kernel": 3,
  "min_segment_len": 4,
  "max_gap_fill": 0,
  "min_i_after_b": 3,
  "suppress_repeated_b_inside_segment": false,
  "top_k": 5,
  "pose_idx": [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
}

## Contrato de entrada externo
El endpoint sigue siendo:

POST /api/v1/jobs/segment-video

Ejemplo:

{
  "job_id": "job-fase-7-bio-gloss-001",
  "media": {
    "path": "C:/Videos/lsec/video_001.mp4"
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
    "device_preference": "cpu",
    "runner": "auto",
    "timeout_sec": 300
  },
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
}

## Contrato de salida externo
La respuesta debe mantener compatibilidad con ELAN:

{
  "job_id": "job-fase-7-bio-gloss-001",
  "status": "COMPLETED",
  "media_info": {
    "fps": 29.97,
    "duration_ms": 4838,
    "total_frames": 145
  },
  "segments": [
    {
      "segment_id": 1,
      "start_ms": 1000,
      "end_ms": 2500,
      "label": "ACOMPAÑAR",
      "confidence": 0.86,
      "start_frame": 30,
      "end_frame": 75,
      "duration_frames": 45,
      "predictions": [
        { "rank": 1, "gloss_id": 4, "gloss": "ACOMPAÑAR", "probability": 0.86 },
        { "rank": 2, "gloss_id": 7, "gloss": "AYUDAR", "probability": 0.07 },
        { "rank": 3, "gloss_id": 9, "gloss": "IR", "probability": 0.03 }
      ]
    }
  ],
  "trace": {
    "runner": "keypoint_pipeline",
    "device": "cpu",
    "model_id": "lsec_bio_gloss_pipeline_v1",
    "model_version": "1.0.0",
    "output_type": "segments_with_gloss",
    "exec_ms": 0,
    "stages": {
      "keypoint_extraction_ms": 0,
      "bio_model_load_ms": 0,
      "gloss_model_load_ms": 0,
      "bio_inference_ms": 0,
      "bio_postprocessing_ms": 0,
      "gloss_classification_ms": 0,
      "total_ms": 0
    }
  }
}

## Compatibilidad importante
El bridge Java de ELAN puede seguir usando:
- start_ms
- end_ms
- label
- confidence

Los campos nuevos son opcionales y no deben romper las fases anteriores.

## Componentes a crear

app/processing/keypoints/
 ├── mediapipe_keypoint_extractor.py
 ├── keypoint_normalizer.py
 └── keypoint_sequence_utils.py

app/processing/
 ├── bio_postprocessor.py
 └── temporal_resampler.py

app/runners/model_architectures/
 ├── bio_segmenter_bilstm.py
 └── keypoint_transformer_v11.py

app/runners/
 └── keypoint_pipeline_runner.py

## Lógica de extracción de keypoints
Debe replicar el script original:
- usar MediaPipe Holistic;
- extraer pose subset con POSE_IDX;
- extraer manos izquierda y derecha;
- pose usa 13 puntos x 4 valores = 52;
- mano izquierda 21 puntos x 3 = 63;
- mano derecha 21 puntos x 3 = 63;
- total input_dim = 178;
- normalizar con centro entre hombros y escala por distancia de hombros.

## BIO Segmenter
Arquitectura esperada:
BioSegmenterBiLSTM(
  input_dim=178,
  hidden_dim=128,
  num_layers=2,
  dropout=0.2,
  num_classes=3
)

Entrada:
[B, T, 178]

Salida:
{"logits": tensor [B, T, 3]}

Inferencia:
- construir ventanas de tamaño 64 y stride 32;
- padding si clip menor a 64;
- softmax por clase;
- agregar probabilidades por frame;
- pred_labels = argmax(avg_probs, axis=1).

## Postprocesamiento BIO
Debe replicar:
- smooth_labels_majority;
- suppress_inner_b opcional;
- labels_to_segments;
- fill_small_gaps;
- filter_short_segments.

## Keypoint Transformer V11
Arquitectura esperada:
KeypointTransformerClassifierV11(
  input_dim=178,
  num_classes=len(vocab_df),
  d_model=256,
  nhead=8,
  num_layers=4,
  dim_feedforward=512,
  dropout=0.2
)

Entrada:
- x: [B, 64, 178]
- mask: [B, 64]

Salida:
{"logits": tensor [B, num_classes]}

Debe:
- preparar cada segmento con temporal_resample si supera gloss_max_len;
- padding si es menor;
- crear mask;
- obtener top_k por softmax;
- label = top1_gloss;
- confidence = top1_probability.

## Manejo de dispositivos
Igual que Fase 5:
- auto: cuda si disponible, sino cpu;
- cpu: cpu;
- cuda: si no disponible, error CUDA_NOT_AVAILABLE.

## Errores esperados
- MODEL_ARTIFACT_MISSING
- VOCAB_NOT_FOUND
- VOCAB_INVALID
- MEDIAPIPE_IMPORT_ERROR
- KEYPOINT_EXTRACTION_ERROR
- KEYPOINTS_EMPTY
- BIO_MODEL_LOAD_ERROR
- GLOSS_MODEL_LOAD_ERROR
- BIO_INFERENCE_ERROR
- GLOSS_INFERENCE_ERROR
- INVALID_KEYPOINT_SHAPE
- NO_SEGMENTS_DETECTED
- CUDA_NOT_AVAILABLE

## Dependencias
Agregar:
- mediapipe
- pandas

Ya existe:
- torch
- numpy
- opencv-python

## Criterios de aceptación
La fase se considera completa si:
- el registry acepta el manifest compuesto;
- RunnerSelector selecciona KeypointPipelineRunner;
- el pipeline carga ambos .pt;
- se carga gloss_vocab_top20.csv;
- se extraen keypoints reales del video;
- se ejecuta BIO Segmenter;
- se postprocesan segmentos BIO;
- se clasifica cada segmento con Keypoint Transformer;
- la respuesta mantiene segments[].start_ms/end_ms/label/confidence;
- la respuesta incluye predictions top_k;
- el bridge ELAN puede seguir funcionando sin cambios críticos;
- DummyRunner y NativePyTorchRunner siguen funcionando;
- no se usa Docker;
- no se genera EAF desde middleware.