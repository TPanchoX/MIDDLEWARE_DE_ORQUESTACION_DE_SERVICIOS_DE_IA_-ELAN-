# Fase 5 — Front gestor de modelos en ELAN

## Contexto
ELAN ya se comunica con el middleware mediante HTTP pero esto fue implementado antes del cambio general realizado a todo el middleware.
El middleware ya permite:
- listar modelos;
- instalar modelos por ZIP;
- activar/desactivar modelos;
- ejecutar inferencia;
- consultar jobs;
- exponer métricas y system/status.

## Objetivo
Crear una interfaz dentro de ELAN para gestionar modelos y parámetros sin usar Postman, esto ya estaba implementado antes de la refactorización del middleware.

## Funcionalidades requeridas
1. Verificar conexión con middleware.
2. Listar modelos instalados.
3. Ver detalle de un modelo.
4. Instalar modelo desde ZIP.
5. Activar/desactivar modelo (validar si todavía funciona).
6. Seleccionar modelo o backend para inferencia.
7. Configurar parámetros básicos:
   - target tier;
   - label mode;
   - timeout;
   - priority (aquí ya entra el tema de la cola fifo que ejecuta uno a la vez asi que no tiene sentido mandar como parámetro desde la petición, no tiene sentido creo yo).
8. Ejecutar inferencia desde ELAN usando el modelo seleccionado.
9. Mostrar resultado o error.

## Endpoints usados
- GET /health
- GET /api/v1/models
- GET /api/v1/models/{model_id}
- POST /api/v1/models/install
- PATCH /api/v1/models/{model_id}/status
- POST /api/v1/jobs/segment-video
- GET /api/v1/jobs/{job_id}
- GET /api/v1/metrics
- GET /api/v1/system/status

## Restricciones
- No cambiar middleware.
- No cambiar contratos.
- No generar EAF desde middleware.
- No agregar dependencias Java innecesarias.
- No romper ELAN.

## Prompt sugerido para poder implementar (no sabemos si esta bien o mal)
Actúa como arquitecto de software senior y desarrollador Java/Swing especializado en ELAN e integración HTTP.

Antes de implementar, lee:
1. docs/fase_5_contexto_front_gestor_modelos_elan.md en el proyecto ELAN.
2. Documentación del middleware:
   - fase_1_base_middleware.md
   - fase_2_registry_modelos.md
   - fase_3_docker_runner.md
   - fase_4_colas_estados_errores_tecnica.md si existe.
3. La implementación actual del bridge ELAN → Middleware.
4. La estructura actual de ELAN.

Necesito implementar la Fase 5: Front gestor de modelos en ELAN.

Objetivo:
Crear una interfaz simple dentro de ELAN para gestionar modelos instalados en el middleware, seleccionar un modelo, configurar parámetros básicos y ejecutar inferencia sin usar Postman.

Tareas obligatorias:
1. Reutilizar el cliente HTTP existente del bridge si ya existe.
2. Crear o extender un cliente:
   AIOrchestrationMiddlewareClient
   con métodos:
   - health()
   - listModels()
   - getModel(modelId)
   - installModel(zipFile)
   - updateModelStatus(modelId, status)
   - segmentVideo(request)
   - getJob(jobId)
   - getMetrics()
   - getSystemStatus()

3. Crear DTOs Java necesarios para:
   - ModelSummary;
   - InstalledModelDetail;
   - InstallModelResponse;
   - ModelStatusUpdateRequest;
   - MetricsResponse;
   - SystemStatusResponse;
   - JobSummary;
   - ErrorResponse.

4. Crear una ventana o panel Swing:
   AIModelManagerDialog o nombre coherente con el proyecto.

5. La ventana debe incluir:
   - campo editable endpoint base, default http://127.0.0.1:8000;
   - botón "Probar conexión";
   - tabla de modelos instalados;
   - botón "Actualizar lista";
   - botón "Instalar modelo ZIP";
   - botón "Activar";
   - botón "Desactivar";
   - área de detalle del modelo seleccionado;
   - selector de modelo para inferencia;
   - campo target tier, default AUTO_GLOSS_SEGMENTS;
   - campo label mode, default gloss_top1;
   - campo timeout, default 300;
   - selector execution mode: sync/async;
   - selector priority: high/normal/low;
   - botón "Ejecutar inferencia";
   - área de logs/resultados.

6. Al instalar modelo:
   - abrir JFileChooser;
   - aceptar solo .zip;
   - enviar multipart/form-data a /api/v1/models/install;
   - mostrar éxito o error;
   - refrescar tabla de modelos.

7. Al activar/desactivar:
   - llamar PATCH /api/v1/models/{model_id}/status;
   - refrescar tabla.

8. Al ejecutar inferencia:
   - obtener la ruta del video actual en ELAN;
   - convertirla a ruta compatible con el middleware si ya existe lógica;
   - construir request con:
     - media.path;
     - annotation.target_tier;
     - annotation.default_label;
     - annotation.label_mode;
     - model.model_id;
     - model.version;
     - execution.timeout_sec;
     - execution.mode;
     - execution.priority.
   - enviar POST /api/v1/jobs/segment-video.

9. Si execution.mode=sync:
   - recibir SegmentVideoResponse;
   - insertar anotaciones en el tier indicado.

10. Si execution.mode=async:
   - recibir job inicial;
   - permitir consultar estado con GET /api/v1/jobs/{job_id};
   - si termina COMPLETED, insertar anotaciones.

11. Mostrar errores sin cerrar ELAN:
   - middleware apagado;
   - modelo no encontrado;
   - modelo desactivado;
   - ZIP inválido;
   - timeout;
   - error Docker.

12. No romper el bridge actual.
13. No cambiar el middleware.
14. Crear documentación:
   - docs/fase_5_front_gestor_modelos_elan_tecnica.md
   - docs/fase_5_front_gestor_modelos_elan_funcional.md

Restricciones estrictas:
- No modificar contratos del middleware.
- No agregar dependencias Java externas si no son necesarias.
- No cambiar la arquitectura de inferencia.
- No generar EAF desde middleware.
- No eliminar la forma actual de ejecutar inferencia.
- No bloquear la UI durante llamadas largas: usar SwingWorker o mecanismo equivalente.
- No dejar excepciones sin controlar.

Criterios de aceptación:
1. ELAN compila.
2. Se puede abrir el gestor de modelos.
3. Probar conexión llama GET /health.
4. La tabla lista modelos desde GET /api/v1/models.
5. Se puede instalar un ZIP.
6. Se puede activar/desactivar modelo.
7. Se puede seleccionar modelo.
8. Se puede ejecutar inferencia desde la UI.
9. Si sync, se insertan anotaciones.
10. Si async, se puede consultar job.
11. Errores se muestran sin cerrar ELAN.
12. Documentación creada.

Al terminar, dame:
1. resumen de archivos creados/modificados;
2. clases principales;
3. cómo abrir la UI;
4. cómo probar con middleware;
5. limitaciones conocidas.