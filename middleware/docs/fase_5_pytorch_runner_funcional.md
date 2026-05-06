# Fase 5 - PyTorch runner funcional

## Que permite hacer esta fase

El middleware ya puede cargar un modelo PyTorch instalado desde un paquete zip,
ejecutarlo sobre ventanas reales de video y convertir la salida del modelo en
segmentos temporales.

## Que significa en palabras simples

El video se procesa de verdad. Luego el modelo PyTorch recibe las ventanas de
frames y devuelve valores por frame. Esos valores se convierten en segmentos que
ELAN podra usar en una fase posterior.

## Como probar

1. Instalar dependencias: `pip install -r requirements.txt`.
2. Crear video: `python scripts/create_test_video.py`.
3. Crear paquetes PyTorch: `python scripts/create_pytorch_model_package.py`.
4. Levantar servidor con uvicorn.
5. Instalar `pytorch_binary_segmenter_demo.zip`.
6. Ejecutar `POST /api/v1/jobs/segment-video` con ese modelo.
7. Verificar `trace.runner = native_pytorch`.
8. Verificar metricas `model_load_ms`, `tensor_conversion_ms`,
   `inference_ms` y `aggregation_ms`.

## Evidencias esperadas

- `GET /health` sigue funcionando.
- `GET /api/v1/models` sigue funcionando.
- `DummyRunner` sigue funcionando.
- El modelo PyTorch compatible responde `COMPLETED`.
- El modelo incompatible responde `MODEL_ARCHITECTURE_MISMATCH`.
- Los segmentos siguen saliendo del postprocesador temporal.

## CUDA

CUDA es opcional. En una maquina sin GPU, usar:

```json
{"device_preference": "cpu"}
```

Si se envia `cuda` y no esta disponible, el middleware responde
`CUDA_NOT_AVAILABLE`.

## Valor para ELAN

ELAN no necesita saber si el modelo corre con PyTorch, dummy o futuro Docker.
Seguira llamando el mismo endpoint y recibiendo segmentos temporales JSON. Esta
fase deja listo el nucleo de inferencia real que el bridge de ELAN podra invocar
en la Fase 6.
