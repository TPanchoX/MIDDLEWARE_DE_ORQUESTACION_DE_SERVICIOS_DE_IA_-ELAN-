# Fase 3 - Dummy runner funcional

## Que permite hacer esta fase

Esta fase permite probar el camino completo de inferencia sin usar un modelo real.
El middleware recibe una solicitud de segmentacion, selecciona un runner dummy,
genera probabilidades por frame y luego convierte esas probabilidades en
segmentos temporales.

## Que significa en palabras simples

Antes el endpoint devolvia segmentos simulados directamente. Ahora el resultado
nace de un flujo mas parecido al futuro sistema real:

1. se revisa que el modelo exista;
2. se elige quien lo ejecuta;
3. el runner produce probabilidades por frame;
4. el postprocesador decide donde empiezan y terminan los segmentos.

Todavia no se analiza un video real. El runner dummy solo simula la salida que
mas adelante produciria un modelo PyTorch.

## Como probar

1. Entrar al directorio `middleware`.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Ejecutar `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.
4. Probar `GET /health`.
5. Probar `GET /api/v1/models`.
6. Enviar un `POST /api/v1/jobs/segment-video` con `dummy_lsec_segmenter`.
7. Revisar que la respuesta incluya `segments`.
8. Revisar que la respuesta incluya `trace.stages`.
9. Consultar el job con `GET /api/v1/jobs/{job_id}`.

## Evidencias esperadas

Si todo esta correcto:

- `/health` responde `status: ok`;
- `/api/v1/models` sigue listando modelos;
- `POST /api/v1/jobs/segment-video` con `dummy_lsec_segmenter` responde
  `COMPLETED`;
- aparecen al menos dos segmentos;
- `trace.runner` es `dummy`;
- `trace.stages` contiene metricas de validacion, cola, inferencia,
  postprocesamiento y total;
- `trace.state_history` muestra `RECEIVED`, `VALIDATING`, `QUEUED`, `RUNNING`,
  `POSTPROCESSING` y `COMPLETED`;
- `GET /api/v1/jobs/{job_id}` devuelve el mismo resultado guardado.

## Modelo instalado dummy

Tambien se puede instalar el paquete de ejemplo:

```text
examples/model_packages/dummy_runner_package/
```

Ese paquete usa `runtime.mode = dummy`, por lo que puede ejecutarse con
`DummyRunner` despues de instalarlo.

## Runtimes no ejecutables todavia

Los modelos `native` o `docker` pueden estar en el registry, pero en esta fase no
se ejecutan. Si se intenta segmentar con uno de ellos y esta `available`, el
middleware responde `RUNTIME_NOT_SUPPORTED`.

## Valor para la arquitectura final

La fase deja preparado el contrato interno que usara un modelo real:

- el runner recibe un `InferenceInput`;
- el modelo o runner devuelve probabilidades por frame;
- el postprocesador convierte esas probabilidades en segmentos;
- ELAN sigue recibiendo la misma forma de respuesta JSON.

Esto permite conectar PyTorch o Docker en fases futuras sin redisenar el endpoint
principal.

## Restricciones vigentes

- No se usa PyTorch.
- No se usa Docker.
- No se usa OpenCV ni FFmpeg.
- No se procesa video real.
- No se modifica ELAN.
- No se genera EAF.
- No se usa base de datos.
