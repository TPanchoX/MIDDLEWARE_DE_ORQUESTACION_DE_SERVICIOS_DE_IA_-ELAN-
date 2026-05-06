# Fase 5 - PyTorch runner tecnico

## Objetivo tecnico

Agregar ejecucion nativa de modelos PyTorch registrados en el registry. El
runner consume ventanas generadas por el pipeline de video de Fase 4, devuelve
probabilidades por frame y reutiliza el postprocesador temporal existente.

## Componentes

- `app/runners/native_pytorch_runner.py`
- `app/runners/model_architectures/video_binary_segmenter.py`
- `app/runners/model_architectures/__init__.py`
- `app/processing/probability_aggregator.py`
- `scripts/create_pytorch_model_package.py`

## Arquitectura

`VideoBinarySegmenter` espera entrada `[B, T, C, H, W]`:

1. CNN por frame.
2. `AdaptiveAvgPool2d`.
3. BiLSTM temporal.
4. Capa lineal.
5. Logits por frame `[B, T]`.

El archivo `.pt` debe contener un `state_dict` compatible.

## Flujo

1. `JobService` valida modelo y estado.
2. El pipeline de video genera metadata, frames y ventanas.
3. `RunnerSelector` elige:
   - `DummyRunner` para `runtime.mode=dummy`;
   - `NativePyTorchRunner` para `runtime.mode=native` y `framework=pytorch`;
   - error `UNSUPPORTED_RUNTIME` para Docker.
4. `NativePyTorchRunner` resuelve `artifacts.weights`.
5. Carga `state_dict`.
6. Convierte ventanas `T,H,W,C` a tensor `[B,T,C,H,W]`.
7. Ejecuta `model.eval()` con `torch.no_grad()`.
8. Aplica `sigmoid`.
9. `ProbabilityAggregator` promedia probabilidades por frame global.
10. `TemporalPostprocessor` genera segmentos.

## Dispositivo

- `auto`: CUDA si esta disponible; si no, CPU.
- `cpu`: CPU.
- `cuda`: CUDA obligatoria; si no esta disponible responde
  `CUDA_NOT_AVAILABLE`.

## Manejo de shapes

Salidas aceptadas:

- `[B, T]`
- `[B, T, 1]`

Otros shapes devuelven `INVALID_TENSOR_SHAPE`.

## Errores

- `MODEL_LOAD_ERROR`
- `MODEL_ARCHITECTURE_MISMATCH`
- `PYTORCH_INFERENCE_ERROR`
- `CUDA_NOT_AVAILABLE`
- `INVALID_TENSOR_SHAPE`
- `UNSUPPORTED_RUNTIME`
- `UNSUPPORTED_FRAMEWORK`

Todos se manejan con respuestas JSON controladas y no tumban el servidor.

## Trace

La respuesta incluye:

- `trace.runner = native_pytorch`
- `trace.device`
- `trace.model_id`
- `trace.model_version`
- `trace.output_type`
- `trace.windows_count`
- `trace.stages.model_load_ms`
- `trace.stages.tensor_conversion_ms`
- `trace.stages.inference_ms`
- `trace.stages.aggregation_ms`
- `trace.stages.postprocessing_ms`
- metricas de video de Fase 4

## Limitaciones

- No hay Docker.
- No se modifica ELAN.
- No se genera EAF.
- No se soportan arquitecturas arbitrarias; se valida contra
  `VideoBinarySegmenter`.
