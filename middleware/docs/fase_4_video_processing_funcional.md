# Fase 4 - Procesamiento de video funcional

## Que permite hacer esta fase

Esta fase permite que el middleware lea un archivo de video real antes de
ejecutar el flujo dummy. El servicio obtiene metadata real del archivo, extrae
frames, los prepara y arma ventanas temporales.

## Que significa en palabras simples

El sistema todavia no reconoce senas ni ejecuta PyTorch. Pero ahora ya puede
abrir un video de verdad y preparar sus frames en el formato que mas adelante
necesitara el modelo. El runner dummy sigue inventando probabilidades, pero las
calcula con la duracion y cantidad de frames reales del video.

## Como probar

1. Entrar al directorio `middleware`.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Crear un video artificial con `python scripts/create_test_video.py`.
4. Ejecutar `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.
5. Enviar `POST /api/v1/jobs/segment-video` usando
   `examples/videos/test_lsec_dummy.mp4`.
6. Verificar `media_info`.
7. Verificar `trace.stages` y los campos de video del trace.
8. Consultar el job creado con `GET /api/v1/jobs/{job_id}`.

## Evidencias esperadas

Con el video generado por el script:

- `media_info.fps` debe ser cercano a `25.0`;
- `media_info.total_frames` debe ser `100`;
- `media_info.duration_ms` debe ser cercano a `4000`;
- `trace.sampled_frames` debe indicar los frames extraidos;
- `trace.windows_count` debe indicar ventanas construidas;
- `trace.original_width` debe ser `320`;
- `trace.original_height` debe ser `240`;
- `segments` debe salir del postprocesador temporal.

## Error esperado

Si se envia una ruta inexistente en `media.path`, el middleware responde con
`VIDEO_NOT_FOUND`.

## Valor para la Fase 5

La fase deja listo el insumo para PyTorch:

- frames RGB;
- resize uniforme;
- normalizacion a `float32`;
- ventanas temporales `T,H,W,C`;
- indices de frames originales;
- metadata temporal real.

Con esto, la siguiente fase podra conectar un runner PyTorch que consuma esas
ventanas y devuelva probabilidades reales sin cambiar la API que usara ELAN.

## Restricciones vigentes

- No se usa PyTorch.
- No se usa Docker.
- No se modifica ELAN.
- No se genera EAF.
- No se usa base de datos.
