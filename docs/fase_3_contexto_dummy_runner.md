# Fase 3 - Runner dummy y flujo de inferencia simulado

## Contexto
La Fase 1 creó el middleware base FastAPI con jobs simulados.
La Fase 2 implementó el Registry de Modelos con instalación por paquetes zip, manifest.json, persistencia en registry.json y estados available/disabled.

Ahora la Fase 3 debe formalizar el flujo de ejecución mediante un runner dummy, que simule el comportamiento de un modelo real sin usar todavía PyTorch, Docker ni procesamiento real de video.

## Objetivo de la Fase 3
Implementar un flujo de inferencia simulado pero estructuralmente equivalente al flujo real futuro:

ELAN request → middleware → job manager → runner selector → dummy runner → salida temporal simulada → postprocesador → segmentos → respuesta JSON.

## Alcance
Implementar:
- interfaz/base común para runners;
- DummyRunner;
- RunnerSelector;
- contrato interno de inferencia;
- salida dummy tipo frame_probabilities;
- postprocesador temporal básico;
- métricas de ejecución simuladas;
- trazabilidad por etapa;
- actualización de documentación.

## Fuera de alcance
No implementar:
- PyTorch real;
- Docker real;
- OpenCV/FFmpeg;
- lectura real de frames;
- integración con ELAN Java;
- generación de EAF;
- base de datos.

## Flujo requerido

1. POST /api/v1/jobs/segment-video recibe la solicitud.
2. Valida que el modelo exista y esté available.
3. Crea un job con estado RECEIVED.
4. Cambia estado a VALIDATING.
5. Cambia estado a QUEUED.
6. Selecciona runner según runtime.mode.
7. Para runtime dummy, usa DummyRunner.
8. Cambia estado a RUNNING.
9. DummyRunner genera probabilidades simuladas por frame.
10. Cambia estado a POSTPROCESSING.
11. Postprocessor convierte probabilidades a segmentos.
12. Cambia estado a COMPLETED.
13. Guarda resultado en memory store.
14. Devuelve respuesta JSON.

## Modelo dummy
El modelo dummy debe producir una salida interna similar a un modelo real:

{
  "output_type": "frame_probabilities",
  "fps": 25.0,
  "duration_ms": 10000,
  "total_frames": 250,
  "probabilities": [0.01, 0.02, ..., 0.91, 0.88, ..., 0.03]
}

Debe generar al menos dos regiones positivas simuladas, por ejemplo:
- 1000 ms a 2500 ms
- 4000 ms a 5600 ms

Pero no debe devolver segmentos directamente. Debe devolver probabilidades. El postprocessor debe construir los segmentos.

## Postprocesamiento
Implementar un postprocesador que:
- reciba probabilidades por frame;
- use threshold;
- detecte regiones positivas;
- calcule start_ms y end_ms;
- calcule confidence promedio;
- elimine segmentos menores a min_segment_ms;
- fusione segmentos separados por menos de merge_gap_ms;
- use la etiqueta default_label de la solicitud.

## Estructura sugerida

middleware/
 ├── app/
 │   ├── runners/
 │   │   ├── base_runner.py
 │   │   ├── dummy_runner.py
 │   │   └── runner_selector.py
 │   ├── processing/
 │   │   └── temporal_postprocessor.py
 │   ├── schemas/
 │   │   ├── inference.py
 │   │   └── metrics.py
 │   └── services/
 │       └── job_service.py

## Estados de job
Se deben usar los estados ya definidos:
- RECEIVED
- VALIDATING
- QUEUED
- RUNNING
- POSTPROCESSING
- COMPLETED
- FAILED
- TIMEOUT
- CANCELLED

## Trazabilidad
La respuesta final debe incluir trace enriquecido:

{
  "runner": "dummy",
  "device": "cpu",
  "model_id": "dummy_lsec_segmenter",
  "exec_ms": 50,
  "stages": {
    "validation_ms": 2,
    "queue_ms": 1,
    "inference_ms": 20,
    "postprocessing_ms": 5,
    "total_ms": 28
  }
}

## Criterios de aceptación
La Fase 3 se considera completa si:
- segment-video ya no construye segmentos directamente en el endpoint;
- existe DummyRunner;
- existe RunnerSelector;
- existe postprocesador temporal;
- el dummy genera probabilidades;
- el postprocesador genera segmentos;
- los estados del job se actualizan en orden;
- GET /api/v1/jobs/{job_id} devuelve resultado completo;
- los endpoints de Fase 1 y Fase 2 siguen funcionando;
- no se usa PyTorch;
- no se usa Docker;
- no se procesa video real;
- README y documentación quedan actualizados.