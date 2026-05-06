# Fase 7 - Pipeline BIO + Glosas - Funcional

## Que permite

La Fase 7 permite enviar un video al mismo endpoint del middleware y recibir
segmentos temporales con una glosa propuesta por IA. ELAN puede seguir usando
los campos conocidos:

- `start_ms`
- `end_ms`
- `label`
- `confidence`

La diferencia es que ahora `label` contiene la glosa top-1 detectada por el
clasificador de keypoints.

## Flujo de usuario

1. Preparar un paquete zip con manifest, pesos, vocabulario y configuracion.
2. Instalarlo con `POST /api/v1/models/install`.
3. Ejecutar `POST /api/v1/jobs/segment-video` con `model_id` igual a `lsec_bio_gloss_pipeline_v1`.
4. Revisar los segmentos devueltos y sus predicciones top-k.

## Estructura esperada del paquete

```text
lsec_bio_gloss_pipeline_v1.zip
  manifest.json
  weights/
    best_bio_segmenter_v2.pt
    best_keypoint_transformer_v11.pt
  vocab/
    gloss_vocab_top20.csv
  config/
    pipeline_config.json
  README.md
```

## Comprimir el paquete

Desde `middleware/examples/model_packages`:

```powershell
Compress-Archive -Path .\lsec_bio_gloss_pipeline_v1\* -DestinationPath .\lsec_bio_gloss_pipeline_v1.zip -Force
```

Antes de comprimir se deben copiar los `.pt` reales en `weights/`.

## Ejecutar

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Instalar:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/models/install -F "file=@examples/model_packages/lsec_bio_gloss_pipeline_v1.zip"
```

Ejecutar pipeline:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/jobs/segment-video -H "Content-Type: application/json" -d "{\"job_id\":\"job-fase-7\",\"media\":{\"path\":\"examples/videos/test_lsec_dummy.mp4\"},\"annotation\":{\"target_tier\":\"AUTO_GLOSS_SEGMENTS\",\"default_label\":\"LSEC_REGION\",\"label_mode\":\"gloss_top1\"},\"model\":{\"model_id\":\"lsec_bio_gloss_pipeline_v1\",\"version\":\"1.0.0\"},\"execution\":{\"device_preference\":\"cpu\",\"runner\":\"auto\",\"timeout_sec\":300},\"parameters\":{\"bio_window_size\":64,\"bio_stride\":32,\"gloss_max_len\":64,\"smooth_kernel\":3,\"min_segment_len\":4,\"max_gap_fill\":0,\"min_i_after_b\":3,\"top_k\":5}}"
```

## Resultado esperado

Respuesta `COMPLETED` con `segments`. Cada segmento contiene la glosa top-1 y
una lista `predictions` con alternativas ordenadas por probabilidad.

Si no se detectan segmentos, la respuesta tambien es `COMPLETED`, pero con
`segments: []`.

