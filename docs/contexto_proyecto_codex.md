# Contexto general del proyecto

## Título del componente
Desarrollo de un middleware de orquestación de servicios de Inteligencia Artificial para la herramienta de anotación ELAN.

## Problema
ELAN es una herramienta de anotación multimodal desarrollada sobre Java/JVM. El proyecto busca integrarla con modelos modernos de Inteligencia Artificial, principalmente modelos PyTorch para procesamiento de videos de Lengua de Señas Ecuatoriana. ELAN no debe ejecutar modelos directamente, porque eso acoplaría Java con dependencias Python, PyTorch, CUDA, Docker u otros entornos complejos.

## Solución arquitectónica propuesta
La solución será una arquitectura local basada en:

ELAN modificado → Bridge Java / Recognizer Adapter → Middleware Python FastAPI → Registry de modelos → Runner nativo o Docker → Modelo PyTorch → Postprocesamiento temporal → Respuesta JSON → ELAN crea anotaciones en un tier.

## Rol de cada componente

### ELAN modificado
ELAN será el cliente gráfico. Permitirá seleccionar un video, seleccionar un modelo, ejecutar la inferencia y recibir segmentos temporales para insertarlos en la línea de tiempo.

### Bridge Java / Recognizer Adapter
Será el componente dentro de ELAN que hará llamadas HTTP al middleware local.

### Middleware
Será el núcleo de orquestación. Debe recibir solicitudes de ELAN, validar contratos, gestionar modelos, administrar jobs, ejecutar inferencia y devolver segmentos anotables.

### Modelo PyTorch
El modelo base disponible es un segmentador binario de video. No devuelve un archivo EAF ni etiquetas semánticas completas. Devuelve probabilidades por frame o ventana. Por eso el middleware deberá convertir la salida del modelo en segmentos temporales con inicio, fin, etiqueta y confianza.

## Alcance de la Fase 1
La Fase 1 NO debe integrar todavía ELAN real, PyTorch real, Docker real ni procesamiento real de video.

La Fase 1 debe construir la base del middleware FastAPI con endpoints, modelos Pydantic, almacenamiento temporal en memoria, logs y documentación.

## Objetivo general de la Fase 1
Crear una base funcional del middleware local que permita:
- verificar que el servicio está activo;
- listar modelos disponibles;
- crear un job de segmentación simulado;
- consultar el estado de un job;
- devolver una respuesta compatible con la futura integración ELAN.

## Decisiones técnicas obligatorias
- Lenguaje: Python.
- Framework API: FastAPI.
- Validación: Pydantic.
- Servidor: Uvicorn.
- Arquitectura: modular.
- Persistencia en Fase 1: memoria local, no base de datos.
- Formato de comunicación: JSON.
- Puerto recomendado: 8000.
- Host recomendado: 127.0.0.1.
- No usar Docker todavía.
- No usar PyTorch todavía.
- No modificar ELAN todavía.

## Estructura esperada

middleware/
 ├── app/
 │   ├── main.py
 │   ├── api/
 │   │   ├── routes_health.py
 │   │   ├── routes_models.py
 │   │   └── routes_jobs.py
 │   ├── core/
 │   │   ├── config.py
 │   │   └── logging_config.py
 │   ├── schemas/
 │   │   ├── common.py
 │   │   ├── models.py
 │   │   └── jobs.py
 │   ├── services/
 │   │   ├── model_registry_service.py
 │   │   └── job_service.py
 │   └── storage/
 │       └── memory_store.py
 ├── docs/
 │   ├── fase_1_middleware_base_tecnica.md
 │   └── fase_1_middleware_base_funcional.md
 ├── tests/
 ├── requirements.txt
 └── README.md

## Endpoints requeridos en Fase 1

### GET /health
Debe devolver estado general del middleware.

Respuesta esperada:
{
  "status": "ok",
  "service": "elan-ai-orchestrator",
  "version": "0.1.0"
}

### GET /api/v1/models
Debe devolver modelos registrados en memoria. En Fase 1 puede existir un modelo dummy predefinido.

Respuesta esperada:
{
  "models": [
    {
      "model_id": "dummy_lsec_segmenter",
      "name": "Dummy LSEC Segmenter",
      "version": "0.1.0",
      "task": "video_segmentation",
      "runtime": "dummy",
      "status": "available"
    }
  ]
}

### POST /api/v1/jobs/segment-video
Debe crear un job simulado de segmentación.

Request esperado:
{
  "job_id": "job-001",
  "media": {
    "path": "C:/Videos/lsec/video_001.mp4"
  },
  "annotation": {
    "target_tier": "AUTO_SEGMENTS",
    "default_label": "LSEC_REGION"
  },
  "model": {
    "model_id": "dummy_lsec_segmenter",
    "version": "0.1.0"
  },
  "execution": {
    "device_preference": "auto",
    "runner": "auto",
    "timeout_sec": 300
  },
  "parameters": {
    "threshold": 0.5,
    "window_size": 16,
    "stride": 4,
    "min_segment_ms": 200,
    "merge_gap_ms": 120
  }
}

Respuesta esperada:
{
  "job_id": "job-001",
  "status": "completed",
  "media_info": {
    "fps": 25.0,
    "duration_ms": 10000,
    "total_frames": 250
  },
  "segments": [
    {
      "start_ms": 1000,
      "end_ms": 2500,
      "label": "LSEC_REGION",
      "confidence": 0.9
    }
  ],
  "trace": {
    "runner": "dummy",
    "device": "cpu",
    "model_id": "dummy_lsec_segmenter",
    "exec_ms": 50
  }
}

### GET /api/v1/jobs/{job_id}
Debe devolver el estado y resultado del job si existe.

## Estados de job permitidos
- RECEIVED
- VALIDATING
- QUEUED
- PREPROCESSING
- RUNNING
- POSTPROCESSING
- COMPLETED
- FAILED
- TIMEOUT
- CANCELLED

## Manejo de errores esperado
Si el modelo no existe, devolver error HTTP 404.
Si el request es inválido, FastAPI/Pydantic debe devolver 422.
Si el job no existe, devolver 404.
Si ocurre error interno, devolver 500 con mensaje controlado.

## Documentación obligatoria
Codex debe generar:

1. README.md con:
   - descripción del middleware;
   - instalación;
   - ejecución;
   - endpoints;
   - ejemplos curl;
   - estructura del proyecto.

2. docs/fase_1_middleware_base_tecnica.md con:
   - objetivo técnico;
   - arquitectura de la fase;
   - endpoints;
   - modelos Pydantic;
   - flujo interno;
   - decisiones técnicas;
   - limitaciones.

3. docs/fase_1_middleware_base_funcional.md con:
   - explicación para usuario no técnico;
   - qué permite hacer esta fase;
   - cómo probar;
   - evidencias esperadas.

## Criterios de aceptación
La Fase 1 se considera terminada si:
- el middleware inicia con uvicorn;
- GET /health responde correctamente;
- GET /api/v1/models lista el modelo dummy;
- POST /api/v1/jobs/segment-video crea un job simulado;
- GET /api/v1/jobs/{job_id} devuelve el job creado;
- existen logs básicos;
- existe README;
- existen documentos técnicos y funcionales;
- no se implementa todavía PyTorch, Docker ni ELAN real.