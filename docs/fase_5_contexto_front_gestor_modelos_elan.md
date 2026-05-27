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