# Guía para desarrollar e instalar un nuevo backend de modelo

Esta guía explica **paso a paso** cómo desarrollar un nuevo modelo de IA que sea compatible con el middleware ELAN-AI. Al seguirla, el modelo puede instalarse via `POST /api/v1/models/install` sin necesidad de modificar el middleware.

---

## 1. Conceptos clave

El middleware **no ejecuta** el modelo directamente. En cambio:
1. El desarrollador empaqueta su modelo en un contenedor Docker con una API HTTP interna.
2. El middleware instala el paquete (construye la imagen, arranca el contenedor).
3. Para cada inferencia, el middleware envía el video al backend y recibe los segmentos.

El backend es una **aplicación FastAPI independiente** que corre dentro de Docker, expone dos endpoints (`/health` y `/infer`), y es completamente responsable de la lógica de procesamiento.

---

## 2. Estructura obligatoria del paquete ZIP

```
mi_modelo_v1/
├── manifest.json                  ← OBLIGATORIO — metadatos del modelo
├── backend/
│   ├── Dockerfile                 ← OBLIGATORIO — imagen Docker del backend
│   ├── requirements.txt           ← dependencias Python
│   └── app/
│       ├── main.py                ← entry point FastAPI
│       └── ...                    ← tu lógica de procesamiento
├── weights/
│   └── modelo.pt                  ← pesos del modelo
├── vocab/
│   └── vocab.csv                  ← vocabulario (si aplica)
├── config/
│   └── config.json                ← configuración de hiperparámetros
└── README.md                      ← descripción del modelo
```

El middleware monta todo el contenido del ZIP como **contexto de build de Docker**. Esto significa que el `Dockerfile` puede copiar cualquier archivo del paquete (weights, config, vocab) dentro de la imagen.

---

## 3. El `manifest.json` — formato exacto

```json
{
  "model_id": "mi_modelo_v1",
  "name": "Nombre Legible de Mi Modelo",
  "version": "1.0.0",
  "task": "video_segmentation_and_gloss_classification",

  "runtime": {
    "mode": "docker",
    "framework": "container",
    "runner": "docker_http"
  },

  "artifacts": {
    "dockerfile":   "backend/Dockerfile",
    "requirements": "backend/requirements.txt",
    "weights":      "weights/modelo.pt",
    "config":       "config/config.json"
  },

  "backend_config": {
    "docker_image_name":   "mi-modelo",
    "docker_image_tag":    "1.0.0",
    "container_port":      8080,
    "health_path":         "/health",
    "infer_path":          "/infer",
    "startup_timeout_sec": 180
  },

  "container": {
    "internal_port":       8080,
    "health_path":         "/health",
    "infer_path":          "/infer",
    "startup_timeout_sec": 30
  },

  "input_contract": {
    "media_type": "video"
  },

  "output_contract": {
    "type":    "segments_with_gloss",
    "classes": ["O", "B", "I"]
  },

  "ui": {
    "default_label":       "MI_REGION",
    "default_target_tier": "AUTO_SEGMENTS",
    "label_mode":          "gloss_top1",
    "supports_threshold":  false
  }
}
```

### Reglas estrictas del manifest

| Campo | Restricción |
|---|---|
| `model_id` | Solo `[A-Za-z0-9_.-]`, no vacío |
| `version` | Solo `[A-Za-z0-9_.-]`, no vacío |
| `runtime.mode` | Debe ser exactamente `"docker"` |
| `runtime.framework` | Debe ser exactamente `"container"` |
| `runtime.runner` | Debe ser exactamente `"docker_http"` |
| `task` | `"video_segmentation"` o `"video_segmentation_and_gloss_classification"` |
| Todos los `artifacts` | Deben existir en el ZIP (el middleware los verifica antes de extraer) |
| `backend_config.docker_image_name` | Solo minúsculas, sin espacios (nombre de imagen Docker) |

---

## 4. El `Dockerfile` del backend

El Dockerfile construye la imagen del modelo. El **contexto de build es la raíz del paquete ZIP** (no la carpeta `backend/`). Esto permite copiar los pesos y configuraciones desde fuera de `backend/`.

```dockerfile
FROM python:3.11-slim

# Directorio de trabajo DENTRO del contenedor
WORKDIR /model_service

# Instalar dependencias del sistema (ajustar según el modelo)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        libgl1 \
        libegl1 \
        libgles2 \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copiar el código del backend
COPY backend/app ./app

# Copiar los artefactos del modelo (rutas RELATIVAS desde la raíz del ZIP)
COPY weights/  ./weights/
COPY vocab/    ./vocab/
COPY config/   ./config/

# Exponer el puerto interno
EXPOSE 8080

# Arrancar el servidor
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

> **Nota importante sobre librerías del sistema:** Si usas OpenCV y MediaPipe en Debian Bookworm (base de `python:3.11-slim`), necesitas `libgl1`, `libegl1`, `libgles2` (NO `libgl1-mesa-glx` que fue eliminado en Bookworm). Sin estas librerías, `import cv2` falla silenciosamente al iniciar uvicorn.

---

## 5. El backend FastAPI — contrato obligatorio

El backend DEBE exponer exactamente dos endpoints.

### 5.1 GET /health

El middleware llama a este endpoint para verificar que el modelo está cargado y listo.

**Respuesta 200 (modelo listo):**
```json
{"status": "ok"}
```

**Respuesta 503 (modelo no cargado):**
```json
{"status": "error", "detail": "Models failed to load: [mensaje de error]"}
```

> ⚠️ El middleware interpreta cualquier 5xx de `/health` como "backend no listo" y lee el campo `detail` para mostrar el error exacto al usuario. Devolver 503 con un `detail` informativo es crucial para debuggear problemas de carga de pesos.

---

### 5.2 POST /infer

El middleware envía este payload exacto:

```json
{
  "job_id": "job-test-001",
  "media": {
    "path": "/data/videos/mi_video.mp4"
  },
  "annotation": {
    "target_tier": "AUTO_GLOSS_SEGMENTS",
    "default_label": "LSEC_REGION",
    "label_mode": "gloss_top1"
  },
  "parameters": {},
  "model": {
    "model_id": "mi_modelo_v1",
    "version": "1.0.0"
  },
  "execution": {
    "device_preference": "auto",
    "runner": "auto",
    "timeout_sec": 300
  }
}
```

El backend debe devolver:

**Respuesta 200 (inferencia exitosa):**
```json
{
  "output_type": "segments_with_gloss",
  "media_info": {
    "fps": 29.97,
    "duration_ms": 5000,
    "total_frames": 150
  },
  "segments": [
    {
      "start_ms": 500,
      "end_ms": 1500,
      "label": "AYUDAR",
      "confidence": 0.85,
      "predictions": [
        {"rank": 1, "gloss_id": 16, "gloss": "AYUDAR",  "probability": 0.85},
        {"rank": 2, "gloss_id": 10, "gloss": "TRABAJAR", "probability": 0.08},
        {"rank": 3, "gloss_id": 2,  "gloss": "QUERER",   "probability": 0.04},
        {"rank": 4, "gloss_id": 1,  "gloss": "IR",       "probability": 0.02},
        {"rank": 5, "gloss_id": 7,  "gloss": "VER",      "probability": 0.01}
      ]
    }
  ]
}
```

**Respuesta 422 (error de procesamiento del video):**
```json
{
  "detail": "Keypoint extraction failed: Cannot open video: /data/videos/mi_video.mp4"
}
```

> El middleware captura el campo `detail` de cualquier error HTTP del backend y lo muestra directamente al usuario como `DOCKER_INFERENCE_ERROR`.

---

### 5.3 Campos obligatorios de la respuesta `/infer`

| Campo | Tipo | Descripción |
|---|---|---|
| `output_type` | string | `"segments_with_gloss"` o `"segments"` |
| `media_info.fps` | float | FPS del video procesado (> 0) |
| `media_info.duration_ms` | int | Duración en ms (> 0) |
| `media_info.total_frames` | int | Total de frames (> 0) |
| `segments[].start_ms` | int | Inicio del segmento en ms (≥ 0) |
| `segments[].end_ms` | int | Fin del segmento en ms (> start_ms) |
| `segments[].label` | string | Etiqueta principal del segmento |
| `segments[].confidence` | float | Confianza de la predicción (0.0–1.0) |

Campos opcionales pero recomendados:
- `segments[].predictions[]` — array de top-k predicciones con `rank`, `gloss_id`, `gloss`, `probability`
- `segments[].segment_id`, `start_frame`, `end_frame`, `duration_frames`

---

## 6. Ejemplo completo de backend mínimo (Python/FastAPI)

```python
# backend/app/main.py

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s — %(message)s")

# ── Estado global del modelo ───────────────────────────────────────────────
model = None
_loaded = False
_load_error = None

def load_model():
    global model, _loaded, _load_error
    try:
        import torch
        # Cargar tus pesos desde /model_service/weights/
        model = torch.load("/model_service/weights/modelo.pt", map_location="cpu")
        model.eval()
        _loaded = True
        logger.info("Modelo cargado correctamente.")
    except Exception as exc:
        _load_error = str(exc)
        logger.error("Error al cargar el modelo: %s", exc)

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield

app = FastAPI(lifespan=lifespan)

# ── Schemas de entrada ─────────────────────────────────────────────────────
class MediaInput(BaseModel):
    path: str

class InferRequest(BaseModel):
    job_id: str
    media: MediaInput
    annotation: dict = {}
    parameters: dict = {}
    model: dict = {}
    execution: dict = {}

# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    if _loaded:
        return {"status": "ok"}
    return JSONResponse(
        status_code=503,
        content={"status": "error", "detail": f"Model not loaded: {_load_error}"}
    )

@app.post("/infer")
def infer(request: InferRequest):
    video_path = request.media.path

    # 1. Procesar el video
    # 2. Ejecutar inferencia
    # 3. Construir segmentos
    segments = []

    return {
        "output_type": "segments_with_gloss",
        "media_info": {
            "fps": 30.0,
            "duration_ms": 5000,
            "total_frames": 150
        },
        "segments": segments
    }
```

---

## 7. Paso a paso para empaquetar e instalar

### Paso 1: Organizar los archivos

```
mi_modelo_v1/
├── manifest.json
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/main.py
├── weights/modelo.pt
├── config/config.json
└── README.md
```

### Paso 2: Crear el ZIP

```powershell
# En PowerShell, desde la carpeta que CONTIENE mi_modelo_v1/
Compress-Archive -Path mi_modelo_v1\* -DestinationPath mi_modelo_v1.zip
```

> Usar `mi_modelo_v1\*` (con `\*`), NO `mi_modelo_v1`. Con `\*` se empaquetan los archivos directamente en la raíz del ZIP.

### Paso 3: Verificar que el middleware está corriendo

```bash
curl http://localhost:8000/health
# Esperado: {"status": "ok", ...}
```

### Paso 4: Instalar el modelo

```bash
curl -X POST http://localhost:8000/api/v1/models/install \
     -F "file=@mi_modelo_v1.zip"
```

El middleware:
1. Valida el ZIP, el `manifest.json` y los artifacts declarados
2. Extrae el paquete a `installed/{model_id}/{version}/` y lo registra en `registry.json`
3. Ejecuta `docker build` (puede tardar varios minutos la primera vez)
4. Arranca el contenedor en la red `elan-ai-shared`
5. Espera el health check hasta `backend_config.startup_timeout_sec` (180 s en este ejemplo; 120 s si se omite)
6. Guarda el bootstrap manifest en `data/bootstrap_manifests/`

Si todo va bien, responde 200 con `{"message": "Model installed successfully.", "model": {...}}`.
Si el build, el arranque o el health check fallan, hace **rollback** (quita el modelo del registry y borra los archivos extraídos) y responde 400 `MODEL_PACKAGE_INVALID` con el detalle del error.

### Paso 5: Verificar que el modelo está instalado

```bash
curl http://localhost:8000/api/v1/models
```

### Paso 6: Ejecutar una inferencia

> `media.path` puede ser la ruta interna `/data/videos/...` o directamente la
> ruta del host (p. ej. `C:/Users/user/Videos/mi_video.mp4`): el middleware la
> traduce automáticamente si está dentro de `MIDDLEWARE_VIDEOS_DIR`.

```bash
curl -X POST http://localhost:8000/api/v1/jobs/segment-video \
     -H "Content-Type: application/json" \
     -d '{
       "job_id": "test-001",
       "media": {"path": "/data/videos/mi_video.mp4"},
       "annotation": {
         "target_tier": "AUTO_SEGMENTS",
         "default_label": "REGION",
         "label_mode": "gloss_top1"
       },
       "model": {
         "model_id": "mi_modelo_v1",
         "version": "1.0.0"
       },
       "execution": {"timeout_sec": 300}
     }'
```

---

## 8. Diagrama del ciclo de vida completo

```
DESARROLLADOR                     MIDDLEWARE                    DOCKER
     │                                │                            │
     │ POST /models/install (ZIP)     │                            │
     │ ──────────────────────────────►│                            │
     │                                │ docker build               │
     │                                │ ──────────────────────────►│
     │                                │ docker run --network       │
     │                                │ ──────────────────────────►│
     │                                │ GET /health (retry)        │
     │                                │ ──────────────────────────►│
     │                                │◄── 200 OK                  │
     │                                │ registry.json actualizado  │
     │◄── 200 {model: InstalledModel} │                            │
     │                                │                            │
     │ POST /jobs/segment-video       │                            │
     │ ──────────────────────────────►│                            │
     │                                │ ensure_container()         │
     │                                │ (reutiliza si corre)       │
     │                                │ GET /health                │
     │                                │ ──────────────────────────►│
     │                                │◄── 200 OK                  │
     │                                │ POST /infer                │
     │                                │ ──────────────────────────►│
     │                                │◄── {media_info, segments}  │
     │◄── 200 {segments, trace}       │                            │
```

---

## 9. Checklist de validación antes de instalar

Antes de subir el ZIP, verificar:

- [ ] `manifest.json` está en la **raíz** del ZIP (no dentro de una carpeta)
- [ ] `runtime.mode = "docker"`, `framework = "container"`, `runner = "docker_http"`
- [ ] `backend_config.docker_image_name` solo tiene minúsculas y guiones (sin espacios)
- [ ] Todos los archivos en `artifacts` existen en el ZIP
- [ ] El `Dockerfile` tiene `EXPOSE 8080` y el CMD inicia en `0.0.0.0:8080`
- [ ] El backend expone `GET /health` que devuelve 200 cuando el modelo está cargado
- [ ] El backend expone `POST /infer` que devuelve `{output_type, media_info, segments[]}`
- [ ] `media_info.fps > 0`, `duration_ms > 0`, `total_frames > 0`
- [ ] Cada segmento tiene `start_ms < end_ms` y `0.0 ≤ confidence ≤ 1.0`
- [ ] Las librerías del sistema requeridas por OpenCV/MediaPipe están en el `Dockerfile`
- [ ] El backend no crashea al iniciar (el contenedor se mantiene arriba y responde `/health`)

---

## 10. Debugging: errores comunes y soluciones

### El backend no pasa el health check (Connection refused / 503 persistente)

```bash
# Ver los logs del contenedor del modelo
docker logs elan-ai-model-mi_modelo_v1-1.0.0
```

Causas comunes:
- `import cv2` falla por librerías del sistema faltantes → agregar `libgl1`, `libegl1`, `libgles2` al Dockerfile
- `import mediapipe` falla si la versión no tiene `mp.solutions.holistic` → usar `mediapipe==0.10.9`
- El modelo `.pt` no coincide con la arquitectura definida → verificar los key names del state_dict

### Los pesos no cargan (state_dict mismatch)

Verificar que los nombres de capas de tu clase PyTorch coincidan exactamente con los del archivo `.pt`:
```python
import torch
ckpt = torch.load("modelo.pt", map_location="cpu")
print(list(ckpt.keys()))  # Ver los nombres reales de las capas
```

### Error "Cannot open video"

El video no está en `/data/videos/`. Verificar:
1. `MIDDLEWARE_VIDEOS_DIR` en `docker-compose.yml` apunta a la carpeta correcta
2. El archivo existe en esa carpeta
3. El contenedor fue creado **después** de configurar `MIDDLEWARE_VIDEOS_DIR` (si no, eliminarlo para que se recree)

### El middleware no puede instalar porque el modelo ya existe

```bash
# Limpiar el registry Y los bootstrap manifests (si no, el modelo se
# re-registra automáticamente al reiniciar), y reiniciar el middleware:
docker exec elan-ai-middleware sh -c 'echo "{\"models\":[]}" > /app/data/models_store/registry.json'
docker exec elan-ai-middleware sh -c 'rm -f /app/data/bootstrap_manifests/*.json'
docker compose restart middleware

# Para eliminar también los archivos del modelo:
docker exec elan-ai-middleware rm -rf /app/data/models_store/installed/<model_id>
```

> Nota: `docker compose down -v` **no** borra los modelos instalados, porque
> `./data/` es un bind mount del host y no un volumen con nombre.
