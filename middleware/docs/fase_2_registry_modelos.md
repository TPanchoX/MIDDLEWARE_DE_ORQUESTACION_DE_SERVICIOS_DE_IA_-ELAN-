# Fase 2 — Registry de Modelos

## 1. Descripción general

El registry de modelos permite **instalar, validar, listar y gestionar** modelos desde paquetes ZIP. Cada paquete contiene un `manifest.json` que declara metadatos, artefactos y configuración del backend Docker.

Al instalar un paquete:
1. El middleware extrae el ZIP y valida el manifest.
2. Construye la imagen Docker del backend (`docker build`).
3. Arranca el contenedor y espera que el health check devuelva 200.
4. Registra el modelo en el archivo `registry.json` del volumen.
5. Si cualquier paso falla, hace rollback completo (elimina archivos e imagen).

---

## 2. Persistencia del registry

### En producción (Docker Compose)

El registry real vive en el **volumen Docker** `middleware_models`, montado en `/app/data/models_store` dentro del contenedor. Este volumen **persiste entre reinicios** del middleware.

```
Volumen Docker middleware_models
└── /app/data/models_store/
    ├── registry.json             ← índice de modelos instalados
    └── lsec_bio_gloss_final_v1/
        └── 1.0.0/
            ├── manifest.json
            ├── weights/
            ├── vocab/
            ├── config/
            └── backend/
```

### Comandos útiles para inspeccionar el registry

```bash
# Ver modelos instalados vía API:
curl http://localhost:8000/api/v1/models

# Ver el registry JSON directamente en el volumen:
docker exec elan-ai-middleware cat /app/data/models_store/registry.json

# Resetear el registry (vaciar — los contenedores de modelo no se eliminan):
docker exec elan-ai-middleware sh -c 'echo "{\"models\":[]}" > /app/data/models_store/registry.json'

# Eliminar el volumen completo (⚠️ destruye todos los modelos instalados):
docker compose down -v
```

---

## 3. Estructura del paquete ZIP

```
mi_modelo_v1.zip
├── manifest.json                  ← OBLIGATORIO — en la raíz del ZIP
├── backend/
│   ├── Dockerfile                 ← imagen del modelo
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       └── ...
├── weights/
│   ├── modelo.pt
│   └── otro_peso.pt
├── vocab/
│   └── glosario.csv
├── config/
│   └── pipeline_config.json
└── README.md
```

### Notas sobre la creación del ZIP en Windows (PowerShell)

```powershell
# Desde la carpeta que CONTIENE lsec_bio_gloss_final_v1/:
cd middleware\model_packages
Compress-Archive -Path lsec_bio_gloss_final_v1\* -DestinationPath lsec_bio_gloss_final_v1.zip
```

> ⚠️ **Importante**: usar `-Path lsec_bio_gloss_final_v1\*` (con `\*`), NO `-Path lsec_bio_gloss_final_v1`. La segunda forma incluye el nombre de la carpeta como prefijo en el ZIP, lo que el middleware detecta y corrige automáticamente. Sin embargo, la forma con `\*` es más limpia.

---

## 4. Formato exacto del `manifest.json`

El manifest tiene 8 secciones. Todas son **obligatorias** salvo donde se indica.

```json
{
  "model_id": "lsec_bio_gloss_final_v1",
  "name": "Nombre legible del modelo",
  "version": "1.0.0",
  "task": "video_segmentation_and_gloss_classification",

  "runtime": {
    "mode": "docker",
    "framework": "container",
    "runner": "docker_http"
  },

  "artifacts": {
    "weights_bio":  "weights/best_bio_segmenter_v2.pt",
    "weights_gloss":"weights/best_keypoint_transformer_v11.pt",
    "vocab":        "vocab/gloss_vocab_top20.csv",
    "config":       "config/pipeline_config.json",
    "dockerfile":   "backend/Dockerfile",
    "requirements": "backend/requirements.txt",
    "app_main":     "backend/app/main.py"
  },

  "backend_config": {
    "docker_image_name":    "lsec-bio-gloss-final",
    "docker_image_tag":     "1.0.0",
    "container_port":       8080,
    "health_path":          "/health",
    "infer_path":           "/infer",
    "startup_timeout_sec":  180
  },

  "container": {
    "internal_port":       8080,
    "health_path":         "/health",
    "infer_path":          "/infer",
    "startup_timeout_sec": 30
  },

  "input_contract": {
    "media_type":   "video",
    "feature_type": "keypoints",
    "input_dim":    356
  },

  "output_contract": {
    "type":    "segments_with_gloss",
    "classes": ["O", "B", "I"],
    "top_k":   5
  },

  "ui": {
    "default_label":       "LSEC_REGION",
    "default_target_tier": "AUTO_GLOSS_SEGMENTS",
    "label_mode":          "gloss_top1",
    "supports_threshold":  false
  }
}
```

### Descripción de cada sección

#### `runtime` — modo de ejecución
| Campo | Valor requerido | Descripción |
|---|---|---|
| `mode` | `"docker"` | Único modo soportado actualmente |
| `framework` | `"container"` | Único framework soportado |
| `runner` | `"docker_http"` | Selecciona `DockerRunner` |

#### `artifacts` — archivos del paquete
- Cada valor es una ruta **relativa** dentro del ZIP.
- Todos los archivos declarados deben existir dentro del ZIP.
- Se validan antes de la extracción (el middleware rechaza ZIPs con artifacts faltantes).
- El middleware NO requiere una clave `docker_image` en artifacts — la deriva automáticamente de `backend_config.docker_image_name:docker_image_tag`.

#### `backend_config` — usado durante la **instalación**
| Campo | Descripción |
|---|---|
| `docker_image_name` | Nombre de la imagen Docker a construir |
| `docker_image_tag` | Tag de la imagen |
| `container_port` | Puerto en que escucha el backend dentro del contenedor |
| `health_path` | Endpoint de health check del backend |
| `infer_path` | Endpoint de inferencia del backend |
| `startup_timeout_sec` | Segundos máximos para esperar que el contenedor sea healthy tras instalación |

#### `container` — usado durante la **inferencia**
| Campo | Descripción |
|---|---|
| `internal_port` | Puerto interno del contenedor (igual a `container_port`) |
| `health_path` | Health check del backend |
| `infer_path` | Endpoint de inferencia |
| `startup_timeout_sec` | Timeout del health check durante cada inferencia (si el contenedor fue reiniciado) |

> La diferencia entre `backend_config` y `container`: `backend_config.startup_timeout_sec` (180 s) es el tiempo que el middleware espera cuando **instala** el modelo (el backend puede tardar en cargar los pesos). `container.startup_timeout_sec` (30 s) es el tiempo máximo cuando el middleware simplemente verifica que el contenedor ya running responde.

#### `task` — tarea del modelo
Valores soportados: `"video_segmentation"` | `"video_segmentation_and_gloss_classification"`

---

## 5. Validaciones que aplica el middleware

Al recibir el ZIP, el middleware valida en orden:

1. **El ZIP se puede abrir** — no está corrupto.
2. **Contiene `manifest.json` en la raíz** — si el ZIP tiene un directorio raíz único (prefijo), el middleware lo detecta y lo descarta automáticamente.
3. **El manifest es JSON válido** y cumple el schema Pydantic (`ModelManifest`).
4. **`model_id`** no está vacío y solo contiene `[A-Za-z0-9_.-]`.
5. **`version`** no está vacía y solo contiene `[A-Za-z0-9_.-]`.
6. **`task`** es un valor soportado.
7. **`runtime.mode`** es `"docker"`.
8. **`runtime.framework`** es `"container"`.
9. **Todos los artifacts** declarados existen dentro del ZIP.
10. **Ninguna ruta de artifact es insegura** (no permite `..`, rutas absolutas, ni barras iniciales).
11. **El modelo no está ya instalado** — misma combinación `(model_id, version)` se rechaza.

---

## 6. Flujo completo de instalación

```
POST /api/v1/models/install (multipart ZIP)
│
├── 1. Recibir y guardar ZIP temporal
├── 2. Abrir ZIP y detectar prefijo de carpeta
├── 3. Leer manifest.json (con o sin prefijo)
├── 4. Validar manifest contra schema Pydantic
├── 5. Verificar que todos los artifacts existen en el ZIP
├── 6. Verificar que no existe (model_id, version) en el registry
├── 7. Extraer ZIP a: /app/data/models_store/{model_id}/{version}/
│
├── 8. Docker build ──────────────────────────────────────────────┐
│       path=  install_path (raíz del paquete)                   │
│       dockerfile= backend/Dockerfile                           │
│       tag= {docker_image_name}:{docker_image_tag}              │
│                                                                 │
├── 9. Docker run ───────────────────────────────────────────────┤
│       network= elan-ai-shared                                   │
│       name= elan-ai-model-{model_id}-{version}                  │
│       volumes= {MIDDLEWARE_VIDEOS_DIR}:/data/videos:ro          │
│                                                                 │
├── 10. Health check (esperar hasta startup_timeout_sec) ────────┤
│        GET http://{container_name}:{port}/health                │
│        ✓ 200 → continuar                                        │
│        ✗ 503 → leer body JSON → mostrar error del backend       │
│        ✗ timeout → mostrar error de conexión                    │
│                                                                 │
├── 11. Registrar en registry.json ──────────────────────────────┘
│
└── Respuesta 200: {message, model: InstalledModel}

En cualquier fallo de los pasos 8–11:
  → Eliminar directorio extraído
  → Eliminar imagen Docker (si se construyó)
  → Respuesta 422: {error_code, detail}
```

---

## 7. Endpoint POST /api/v1/models/install — contrato exacto

**Método:** `POST`  
**URL:** `http://localhost:8000/api/v1/models/install`  
**Content-Type:** `multipart/form-data`  
**Campo del formulario:** `file` (archivo ZIP)

### Ejemplo con curl

```bash
curl -X POST http://localhost:8000/api/v1/models/install \
     -F "file=@lsec_bio_gloss_final_v1.zip"
```

### Ejemplo con PowerShell

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/models/install" `
    -Method POST `
    -Form @{ file = Get-Item ".\lsec_bio_gloss_final_v1.zip" }
```

### Response 200 (éxito)

```json
{
  "message": "Model 'lsec_bio_gloss_final_v1' version '1.0.0' installed successfully.",
  "model": {
    "model_id": "lsec_bio_gloss_final_v1",
    "name": "LSEC BIO Gloss Pipeline — Implementacion Final Tesis",
    "version": "1.0.0",
    "task": "video_segmentation_and_gloss_classification",
    "runtime": {"mode": "docker", "framework": "container", "runner": "docker_http"},
    "artifacts": { "...": "..." },
    "status": "available",
    "installed_at": "2026-05-27T14:00:00.000000",
    "install_path": "/app/data/models_store/lsec_bio_gloss_final_v1/1.0.0",
    "source": "installed"
  }
}
```

### Errores posibles

| Código HTTP | error_code | Causa |
|---|---|---|
| 422 | `MODEL_MANIFEST_NOT_FOUND` | No hay `manifest.json` en el ZIP |
| 422 | `MODEL_PACKAGE_INVALID` | Manifest inválido, artifact faltante, Docker build fallido, contenedor no saludable |
| 409 | `MODEL_ALREADY_EXISTS` | Ya existe `(model_id, version)` en el registry |

---

## 8. Resolución de problemas frecuentes en la instalación

### Error: `MODEL_MANIFEST_NOT_FOUND`
El ZIP no tiene `manifest.json` en la raíz. En Windows, verificar que se usó `-Path carpeta\*` y no `-Path carpeta`.

### Error: Docker build fallido
Ver el mensaje de error en `detail`. Causas comunes:
- Paquete del sistema no existe en la imagen base (ej: nombre cambiado en Debian Bookworm).
- Error de sintaxis en el `Dockerfile`.

### Error: Connection refused (contenedor no healthy)
El contenedor arrancó pero el backend no responde. Inspeccionar los logs:
```bash
docker logs elan-ai-model-lsec_bio_gloss_final_v1-1.0.0
```
Causas comunes: falta de librerías del sistema, error en las importaciones Python.

### Error: `MODEL_ALREADY_EXISTS` aunque no hay modelos
El registry del **volumen Docker** tiene una entrada que el filesystem local no tiene. Limpiar:
```bash
docker exec elan-ai-middleware sh -c 'echo "{\"models\":[]}" > /app/data/models_store/registry.json'
```

---

## 9. Nombre del contenedor Docker

El middleware genera el nombre del contenedor automáticamente:

```
elan-ai-model-{model_id}-{version}
```

Con `model_id=lsec_bio_gloss_final_v1` y `version=1.0.0`:
```
elan-ai-model-lsec_bio_gloss_final_v1-1.0.0
```

Caracteres no permitidos en nombres de contenedor (`[^a-z0-9_.-]`) se reemplazan por `-`.

---

## 10. Comandos de gestión post-instalación

```bash
# Ver modelos instalados
curl http://localhost:8000/api/v1/models

# Ver detalle de un modelo
curl http://localhost:8000/api/v1/models/lsec_bio_gloss_final_v1

# Desactivar un modelo (sigue instalado pero el middleware lo rechaza para inferencia)
curl -X PATCH http://localhost:8000/api/v1/models/lsec_bio_gloss_final_v1/status \
     -H "Content-Type: application/json" \
     -d '{"status": "disabled"}'

# Reactivar
curl -X PATCH http://localhost:8000/api/v1/models/lsec_bio_gloss_final_v1/status \
     -H "Content-Type: application/json" \
     -d '{"status": "available"}'

# Eliminar manualmente el contenedor del modelo
docker rm -f elan-ai-model-lsec_bio_gloss_final_v1-1.0.0

# Eliminar la imagen Docker del modelo
docker rmi lsec-bio-gloss-final:1.0.0
```
