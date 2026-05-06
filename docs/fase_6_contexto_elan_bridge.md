# Fase 6 - Bridge ELAN → Middleware usando pipeline final BIO + Keypoint Transformer

## Contexto
El workspace contiene dos proyectos:
1. Middleware: FastAPI con fases 1 a 7 implementadas.
2. ELAN 7.1: código fuente Java que debe integrarse con el middleware.

El middleware ya expone el endpoint:
POST http://127.0.0.1:8000/api/v1/jobs/segment-video

La Fase 7 del middleware ya integra el pipeline final:
video → MediaPipe keypoints → BIO Segmenter v2 → Keypoint Transformer v1.1 → segmentos con glosa.

## Objetivo
Implementar en ELAN un bridge Java capaz de:
1. Obtener la ruta del video actual.
2. Construir el request JSON final.
3. Enviar POST al middleware.
4. Recibir respuesta JSON.
5. Crear o reutilizar un tier llamado AUTO_GLOSS_SEGMENTS.
6. Insertar anotaciones usando start_ms, end_ms y label. Aquí tener en cuenta que deberiamos ver si es viable crear el .eaf para que ELAN lo abra directamente, o si es necesario usar la API de ELAN para insertar anotaciones en el proyecto abierto. Pero lo ideal seria esta parte valdiar también si podemos usar el protocolo heredado avatech.
7. Manejar errores sin cerrar ELAN.

## Endpoint
POST http://127.0.0.1:8000/api/v1/jobs/segment-video

## Request final

{
  "job_id": "job-fase-7-bio-gloss-001",
  "media": {
    "path": "C:/Users/imbaq/OneDrive/Desktop/Tesis - Desarrollo/Middleware/middleware/test_assets/videoplayback.mp4"
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
    "runner": "keypoint_pipeline",
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
    "suppress_repeated_b_inside_segment": false,
    "top_k": 5,
    "pose_idx": [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
  }
}

## Response final
La respuesta contiene:
- job_id
- status
- media_info
- segments
- trace

Cada segmento contiene como mínimo:
- start_ms
- end_ms
- label
- confidence

También puede contener:
- segment_id
- start_frame
- end_frame
- duration_frames
- predictions[]

ELAN debe usar principalmente:
- start_ms
- end_ms
- label
- confidence

## Comportamiento esperado en ELAN
Si status == COMPLETED:
- Crear o reutilizar tier AUTO_GLOSS_SEGMENTS.
- Por cada segmento:
  - validar start_ms >= 0;
  - validar end_ms > start_ms;
  - insertar anotación alineada;
  - usar label como valor principal.
- Opcionalmente incluir confidence en el valor:
  IR (0.5449)

Si segments está vacío:
- No insertar anotaciones.
- Mostrar mensaje: no se detectaron segmentos.

Si status != COMPLETED:
- No insertar anotaciones.
- Mostrar/loguear error.

## Restricciones
- No modificar el middleware.
- No cambiar el contrato REST.
- No generar EAF desde middleware.
- No implementar Docker.
- No implementar entrenamiento.
- No crear gestor visual completo todavía.
- No romper compilación de ELAN.