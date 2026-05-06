# Fase 5 - Integración PyTorch real mediante NativePyTorchRunner

## Contexto
La Fase 1 creó el middleware base.
La Fase 2 implementó el registry de modelos.
La Fase 3 creó el flujo formal de runner dummy y postprocesamiento.
La Fase 4 implementó procesamiento real de video: metadata, frames, preprocesamiento y ventanas.

Ahora la Fase 5 debe integrar PyTorch real mediante un NativePyTorchRunner.

## Objetivo
Implementar un runner nativo de PyTorch que cargue modelos registrados en el registry y ejecute inferencia sobre las ventanas de video construidas en la Fase 4.

## Alcance
Implementar:
- dependencia torch;
- NativePyTorchRunner;
- carga de modelo desde manifest;
- reconstrucción de arquitectura base del modelo segmentador binario;
- carga de state_dict;
- inferencia sobre ventanas;
- conversión logits → sigmoid → probabilidades;
- agregación temporal de probabilidades por frame;
- integración con postprocessor existente;
- manejo de errores del modelo;
- métricas de inferencia;
- documentación técnica y funcional.

## Modelo base esperado
El modelo base disponible corresponde a un segmentador binario de video.

Características esperadas:
- archivo .pt contiene state_dict, no modelo completo serializado;
- entrada esperada: [B, T, C, H, W];
- channels: 3;
- tamaño recomendado: 224x224;
- salida esperada: logits por frame con forma [B, T] o compatible;
- se debe aplicar sigmoid para obtener probabilidades;
- el postprocessor convierte probabilidades en segmentos.

## Arquitectura base a implementar
Se debe crear una arquitectura compatible con el modelo base:

VideoBinarySegmenter:
- encoder CNN por frame;
- extractor temporal BiLSTM;
- capa lineal final;
- salida binaria por frame.

IMPORTANTE:
Si la arquitectura exacta del state_dict no coincide, el sistema debe devolver MODEL_LOAD_ERROR o MODEL_ARCHITECTURE_MISMATCH con mensaje controlado, no romper el servidor.

## Componentes esperados

middleware/app/runners/
 ├── native_pytorch_runner.py
 ├── model_architectures/
 │   ├── __init__.py
 │   └── video_binary_segmenter.py
 └── runner_selector.py

middleware/app/processing/
 └── probability_aggregator.py

## probability_aggregator.py
Debe:
- recibir ventanas, frame_indices y probabilidades por ventana;
- acumular probabilidades por frame global;
- promediar probabilidades cuando un frame aparece en varias ventanas;
- devolver una lista de probabilidades globales con longitud total_frames.

## RunnerSelector
Debe:
- seleccionar DummyRunner para runtime.mode dummy;
- seleccionar NativePyTorchRunner para runtime.mode native y framework pytorch;
- mantener error controlado para runtime.mode docker.

## Manifest para modelo PyTorch
El modelo instalado debe usar algo como:

{
  "model_id": "lsec_segmenter_v1",
  "name": "LSEC Binary Segmenter",
  "version": "1.0.0",
  "task": "video_segmentation",
  "runtime": {
    "mode": "native",
    "framework": "pytorch"
  },
  "artifacts": {
    "weights": "weights/model.pt",
    "preprocess_config": "config/preprocess.json",
    "labels": "labels.json"
  },
  "input_contract": {
    "media_type": "video",
    "layout": "B,T,C,H,W",
    "window_size": 16,
    "channels": 3,
    "height": 224,
    "width": 224
  },
  "output_contract": {
    "type": "frame_probabilities",
    "classes": ["background", "gesture"]
  },
  "ui": {
    "default_label": "LSEC_REGION",
    "supports_threshold": true
  }
}

## Flujo requerido

1. POST /api/v1/jobs/segment-video recibe solicitud.
2. Valida modelo existente y available.
3. Procesa video real con pipeline de Fase 4.
4. RunnerSelector identifica runtime native/pytorch.
5. NativePyTorchRunner carga arquitectura.
6. Carga state_dict.
7. Convierte ventanas numpy a tensores PyTorch.
8. Ejecuta inferencia en CPU o GPU si está disponible.
9. Convierte logits a probabilidades con sigmoid.
10. Agrega probabilidades por frame global.
11. Devuelve frame_probabilities.
12. temporal_postprocessor genera segmentos.
13. job_service devuelve respuesta JSON compatible.

## Manejo de dispositivo
Debe soportar:
- device_preference: auto;
- device_preference: cpu;
- device_preference: cuda.

Si cuda se solicita pero no está disponible, devolver error controlado o hacer fallback a CPU según decisión documentada.

Recomendación:
- auto: usa cuda si disponible, sino cpu.
- cpu: usa cpu.
- cuda: usa cuda si disponible; si no, error CUDA_NOT_AVAILABLE.

## Errores esperados
- MODEL_NOT_FOUND
- MODEL_DISABLED
- MODEL_LOAD_ERROR
- MODEL_ARCHITECTURE_MISMATCH
- MODEL_ARTIFACT_MISSING
- PYTORCH_INFERENCE_ERROR
- CUDA_NOT_AVAILABLE
- INVALID_TENSOR_SHAPE
- UNSUPPORTED_RUNTIME
- UNSUPPORTED_FRAMEWORK

## Trazabilidad
Trace debe incluir:
- runner;
- device;
- model_id;
- model_version;
- model_load_ms;
- tensor_conversion_ms;
- inference_ms;
- aggregation_ms;
- postprocessing_ms;
- total_ms;
- windows_count;
- total_frames;
- output_type.

## Criterios de aceptación
La Fase 5 se considera completa si:
- el middleware sigue ejecutando DummyRunner;
- NativePyTorchRunner existe;
- RunnerSelector selecciona NativePyTorchRunner para runtime.mode native/framework pytorch;
- se puede cargar un modelo .pt desde un paquete instalado;
- se ejecuta inferencia sobre ventanas reales;
- se obtienen probabilidades por frame;
- el postprocessor genera segmentos;
- errores de carga o arquitectura se manejan sin tumbar el servidor;
- no se usa Docker todavía;
- no se modifica ELAN todavía;
- README y documentación quedan actualizados.