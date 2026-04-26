# Fase 1 - Base funcional del middleware

## Que permite hacer esta fase

Esta fase deja listo un servicio local que puede:

- confirmar que el middleware esta encendido;
- mostrar el modelo dummy disponible;
- recibir una solicitud de segmentacion de video;
- devolver segmentos simulados;
- guardar el resultado en memoria para consultarlo despues.

## Que significa en palabras simples

Todavia no se analiza un video real ni se ejecuta inteligencia artificial real. Lo que existe ahora es la base del puente: una API local que ya sabe recibir solicitudes con la forma correcta, responder en JSON y comportarse como lo hara el middleware final cuando se conecten las siguientes fases.

## Como probar

1. Entrar al directorio `middleware`.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Ejecutar `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.
4. Probar `GET /health`.
5. Probar `GET /api/v1/models`.
6. Enviar un `POST /api/v1/jobs/segment-video`.
7. Consultar el job creado con `GET /api/v1/jobs/{job_id}`.

## Evidencias esperadas

Si todo esta correcto:

- `/health` responde `status: ok`
- `/api/v1/models` devuelve `dummy_lsec_segmenter`
- el `POST` de segmentacion responde `status: COMPLETED`
- la consulta por `job_id` devuelve el mismo resultado guardado

## Valor para la arquitectura final

Esta fase reduce riesgo porque fija desde ahora:

- el contrato HTTP que consumira ELAN;
- la forma JSON de entrada y salida;
- la separacion entre API, servicios y almacenamiento;
- el punto exacto donde mas adelante se conectaran runners reales y modelos de IA.
