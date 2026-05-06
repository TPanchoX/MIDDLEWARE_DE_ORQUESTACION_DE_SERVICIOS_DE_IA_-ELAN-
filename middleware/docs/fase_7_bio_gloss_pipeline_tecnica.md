# Fase 7 - Pipeline BIO + Keypoint Transformer - Tecnica

## Objetivo

Integrar un runner compuesto `KeypointPipelineRunner` para ejecutar:

```text
video -> MediaPipe Holistic -> keypoints [N,178] -> BIO Segmenter BiLSTM -> postprocesamiento BIO -> Keypoint Transformer v1.1 -> segmentos con glosa top-k
```

El endpoint externo no cambia: `POST /api/v1/jobs/segment-video`.

## Componentes nuevos

- `app/processing/keypoints/mediapipe_keypoint_extractor.py`: abre video con OpenCV, usa MediaPipe Holistic, extrae pose subset, mano izquierda y mano derecha, y devuelve `keypoints`, `fps` y `frame_count`.
- `app/processing/keypoints/keypoint_normalizer.py`: normaliza por centro entre hombros y escala por distancia entre hombros.
- `app/processing/keypoints/keypoint_sequence_utils.py`: crea ventanas BIO, remuestrea secuencias y prepara tensores/masks para glosa.
- `app/processing/bio_postprocessor.py`: suaviza etiquetas BIO, suprime `B` internas opcionalmente, decodifica segmentos, rellena gaps y filtra segmentos cortos.
- `app/runners/model_architectures/bio_segmenter_bilstm.py`: `BioSegmenterBiLSTM`, salida `{"logits": logits}` con forma `[B,T,3]`.
- `app/runners/model_architectures/keypoint_transformer_v11.py`: `KeypointTransformerClassifierV11`, salida `{"logits": logits}` con forma `[B,num_classes]`.
- `app/runners/keypoint_pipeline_runner.py`: orquesta artefactos, inferencia BIO, postprocesamiento y clasificacion top-k.

## Manifest

El selector usa `runtime.runner == "keypoint_pipeline"`:

```json
{
  "runtime": {
    "mode": "native",
    "framework": "pytorch",
    "runner": "keypoint_pipeline"
  }
}
```

Artefactos requeridos:

- `bio_weights`
- `gloss_weights`
- `vocab`
- `pipeline_config`

Los pesos se cargan siempre como `state_dict`; no se ejecuta codigo desde el paquete.

## Salida

La respuesta mantiene:

- `job_id`
- `status`
- `media_info`
- `segments`
- `trace`

Cada segmento conserva `start_ms`, `end_ms`, `label`, `confidence`. Para Fase 7 se agregan:

- `segment_id`
- `start_frame`
- `end_frame`
- `duration_frames`
- `predictions`

`label` es la glosa top-1 y `confidence` es su probabilidad.

## Errores controlados

- `MODEL_ARTIFACT_MISSING`
- `VOCAB_NOT_FOUND`
- `VOCAB_INVALID`
- `MEDIAPIPE_IMPORT_ERROR`
- `KEYPOINT_EXTRACTION_ERROR`
- `KEYPOINTS_EMPTY`
- `BIO_MODEL_LOAD_ERROR`
- `GLOSS_MODEL_LOAD_ERROR`
- `BIO_INFERENCE_ERROR`
- `GLOSS_INFERENCE_ERROR`
- `INVALID_KEYPOINT_SHAPE`
- `CUDA_NOT_AVAILABLE`

Si BIO no detecta segmentos, el job termina `COMPLETED` con `segments: []`.

## Trace

El `trace` conserva campos anteriores y `stages` agrega:

- `keypoint_extraction_ms`
- `bio_model_load_ms`
- `gloss_model_load_ms`
- `vocab_load_ms`
- `bio_inference_ms`
- `bio_postprocessing_ms`
- `gloss_classification_ms`
- `total_ms`

Tambien se informa `output_type: "segments_with_gloss"` y `n_detected_segments`.

