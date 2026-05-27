# Fase 4 — Colas, estados y errores

## Contexto
El middleware ELAN-AI ya tiene:
- FastAPI como API local.
- Registry de modelos por ZIP.
- DockerRunner como único runtime activo.
- Comunicación middleware → contenedor de modelo mediante red Docker elan-ai-shared.
- Endpoint principal POST /api/v1/jobs/segment-video.
- GET /api/v1/jobs/{job_id}.
- Persistencia de modelos en volumen Docker.
- Jobs actualmente almacenados en memoria.

El middleware NO ejecuta modelos directamente. El modelo vive en un contenedor Docker independiente que expone /health y /infer.

## Objetivo
Fortalecer el middleware con manejo formal de jobs:
- estados consistentes;
- cola FIFO con prioridad;
- timeouts;
- cancelación;
- errores estandarizados;
- métricas básicas;
- endpoints de observabilidad.

## Restricción principal
POST /api/v1/jobs/segment-video debe seguir funcionando de forma síncrona por defecto para no romper ELAN.

## Estados permitidos
- RECEIVED
- VALIDATING
- PREPROCESSING
- QUEUED
- RUNNING
- POSTPROCESSING
- COMPLETED
- FAILED
- TIMEOUT
- CANCELLED

## Endpoints existentes que NO deben romperse
- GET /health
- GET /api/v1/models
- GET /api/v1/models/{model_id}
- POST /api/v1/models/install
- PATCH /api/v1/models/{model_id}/status
- POST /api/v1/jobs/segment-video
- GET /api/v1/jobs/{job_id}

## Endpoints nuevos requeridos
- GET /api/v1/jobs
- DELETE /api/v1/jobs/{job_id}
- GET /api/v1/metrics
- GET /api/v1/system/status

## execution.mode
Agregar soporte opcional:
{
  "execution": {
    "mode": "sync"
  }
}

Valores:
- sync: comportamiento actual, devuelve la respuesta completa.
- async: registra el job, lo deja en cola y devuelve estado inicial.

Si execution.mode no viene, usar sync.

## Prioridad
Agregar soporte opcional:
{
  "execution": {
    "priority": "normal"
  }
}

Valores:
- high
- normal
- low

Si no viene, usar normal.

## Manejo de errores
Todos los errores deben usar:
{
  "error_code": "CODIGO",
  "detail": "Mensaje claro",
  "stage": "RUNNING",
  "job_id": "..."
}

## Métricas mínimas
- total_jobs
- completed_jobs
- failed_jobs
- timeout_jobs
- cancelled_jobs
- active_jobs
- queued_jobs
- average_exec_ms
- last_exec_ms
- runners_usage
- error_counts

## Criterios de aceptación
- ELAN sigue funcionando sin cambios.
- segment-video sync sigue devolviendo respuesta completa.
- async devuelve un job consultable.
- GET /api/v1/jobs lista jobs.
- DELETE cancela jobs pendientes.
- GET /api/v1/metrics devuelve métricas.
- GET /api/v1/system/status devuelve estado del middleware, Docker y registry.
- Errores del DockerRunner se mantienen controlados.

## Prompt propuesto apra implementar todo lo antes expeusto
Actúa como arquitecto de software senior y desarrollador Python/FastAPI especializado en orquestación, jobs, resiliencia y métricas.

Antes de implementar, lee completamente:
1. docs/fase_1_base_middleware.md
2. docs/fase_2_registry_modelos.md
3. docs/fase_3_docker_runner.md
4. docs/guia_nuevo_backend_modelo.md
5. docs/fase_4_contexto_colas_estados_errores.md
6. La implementación actual del middleware.

Necesito implementar la Fase 4: Colas, estados y errores.

Contexto actual:
El middleware fue reestructurado. El único runtime activo es DockerRunner. El middleware no ejecuta PyTorch directamente. Los modelos se instalan como paquetes ZIP, se construyen como imágenes Docker y exponen /health y /infer. El endpoint principal sigue siendo POST /api/v1/jobs/segment-video.

Objetivo:
Agregar manejo robusto de jobs, cola, estados, errores estandarizados, timeouts, cancelación y métricas, sin romper el contrato actual usado por ELAN.

Tareas obligatorias:
1. Mantener funcionando todos los endpoints existentes:
   - GET /health
   - GET /api/v1/models
   - GET /api/v1/models/{model_id}
   - POST /api/v1/models/install
   - PATCH /api/v1/models/{model_id}/status
   - POST /api/v1/jobs/segment-video
   - GET /api/v1/jobs/{job_id}

2. Mantener POST /api/v1/jobs/segment-video en modo síncrono por defecto.
   Si execution.mode no existe, usar "sync".

3. Agregar soporte opcional para:
   execution.mode = "sync" | "async"
   execution.priority = "high" | "normal" | "low"

4. Crear o refactorizar JobManager para:
   - crear jobs;
   - guardar request original;
   - actualizar estado;
   - guardar state_history;
   - guardar timestamps created_at, started_at, completed_at;
   - guardar resultado;
   - guardar error;
   - guardar trace.

5. Crear cola FIFO con prioridad:
   - high antes que normal;
   - normal antes que low;
   - dentro de cada prioridad respetar orden de llegada.

6. Crear Scheduler simple en memoria:
   - límite de concurrencia configurable;
   - ejecución segura de jobs async;
   - no bloquear uvicorn;
   - no usar base de datos.

7. Agregar timeout usando execution.timeout_sec.
   Si la inferencia excede el timeout, marcar TIMEOUT y devolver error controlado.

8. Agregar endpoint:
   GET /api/v1/jobs
   Debe listar jobs con:
   - job_id;
   - status;
   - model_id;
   - created_at;
   - started_at;
   - completed_at;
   - error_code si existe.

9. Mantener:
   GET /api/v1/jobs/{job_id}
   Debe devolver resultado completo si está completed o estado/error si aún no terminó.

10. Agregar endpoint:
    DELETE /api/v1/jobs/{job_id}
    Debe cancelar jobs en QUEUED si aún no corren.
    Si ya está RUNNING, devolver error controlado o marcar cancel_requested sin matar contenedor.
    Documentar la decisión.

11. Agregar endpoint:
    GET /api/v1/metrics
    Debe devolver:
    - total_jobs
    - completed_jobs
    - failed_jobs
    - timeout_jobs
    - cancelled_jobs
    - active_jobs
    - queued_jobs
    - average_exec_ms
    - last_exec_ms
    - runners_usage
    - error_counts

12. Agregar endpoint:
    GET /api/v1/system/status
    Debe devolver:
    - middleware status;
    - Docker disponible o no;
    - models_store_dir;
    - número de modelos instalados;
    - número de jobs activos;
    - número de jobs en cola.

13. Estandarizar errores con:
    - error_code;
    - detail;
    - stage;
    - job_id.

14. Asegurar que los errores existentes del DockerRunner se conserven:
    - DOCKER_NOT_AVAILABLE
    - DOCKER_IMAGE_NOT_FOUND
    - DOCKER_CONTAINER_START_ERROR
    - DOCKER_CONTAINER_HEALTHCHECK_FAILED
    - DOCKER_INFERENCE_ERROR
    - DOCKER_TIMEOUT
    - UNSUPPORTED_DOCKER_CONTRACT

15. Enriquecer trace con:
    - execution_mode;
    - priority;
    - queue_wait_ms;
    - timeout_sec;
    - created_at;
    - started_at;
    - completed_at.

16. Actualizar documentación:
    - docs/fase_4_colas_estados_errores_tecnica.md
    - docs/fase_4_colas_estados_errores_funcional.md

17. Actualizar README.md si existe.

Restricciones estrictas:
- No modificar ELAN.
- No cambiar el contrato de /api/v1/jobs/segment-video.
- No eliminar DockerRunner.
- No agregar NativePyTorchRunner.
- No ejecutar modelos directamente dentro del middleware.
- No cambiar /api/v1/models/install.
- No usar base de datos.
- No romper la instalación de modelos por ZIP.
- No romper el backend del modelo.
- No generar EAF.
- No cambiar la red Docker elan-ai-shared.

Criterios de aceptación:
1. docker compose up --build -d levanta el middleware.
2. GET /health funciona.
3. POST /api/v1/jobs/segment-video en modo sync sigue devolviendo la respuesta completa.
4. GET /api/v1/jobs/{job_id} recupera el job.
5. POST /api/v1/jobs/segment-video con execution.mode="async" devuelve estado inicial.
6. GET /api/v1/jobs lista jobs.
7. DELETE /api/v1/jobs/{job_id} cancela jobs pendientes.
8. GET /api/v1/metrics devuelve métricas.
9. GET /api/v1/system/status devuelve estado del sistema.
10. Los errores tienen error_code, detail, stage y job_id.
11. Los errores Docker siguen controlados.
12. ELAN no necesita cambios para seguir funcionando.

Al terminar, dame:
1. resumen de archivos creados/modificados;
2. endpoints nuevos;
3. ejemplos curl;
4. cómo probar sync;
5. cómo probar async;
6. cómo probar cancelación;
7. cómo probar métricas;
8. limitaciones conocidas.