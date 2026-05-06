# Fase 2 - Registry de modelos tecnico

## Objetivo tecnico

Extender el middleware FastAPI para instalar, validar, persistir, listar y
consultar modelos empaquetados como zip. La fase define el contrato de
instalacion y deja preparado el punto de conexion para runners reales en fases
posteriores.

## Arquitectura de la fase

Flujo principal:

Cliente HTTP -> FastAPI -> `ModelRegistryService` -> validacion de zip ->
`app/models_store/installed/` + `app/models_store/registry.json`

Componentes:

- `app/api/routes_models.py`: expone instalacion, listado, detalle y cambio de
  estado.
- `app/schemas/models.py`: define manifest, runtime, artifacts, contratos,
  modelo instalado, respuesta de instalacion y cambio de estado.
- `app/services/model_registry_service.py`: valida paquetes, controla errores,
  copia archivos seguros y persiste el registry.
- `app/models_store/registry.json`: registry persistente simple en JSON.
- `app/models_store/installed/`: almacenamiento de paquetes instalados.

## Endpoints

### `GET /api/v1/models`

Lista modelos disponibles en formato resumido. Incluye siempre el modelo dummy
`dummy_lsec_segmenter` y los modelos instalados desde zip.

### `POST /api/v1/models/install`

Recibe multipart/form-data con el campo `file`. El archivo debe ser un zip con
`manifest.json` en la raiz.

Validaciones:

- el archivo existe y se puede abrir como zip;
- el zip contiene archivos;
- no hay rutas absolutas, rutas con `..`, rutas con drive de Windows ni
  backslashes;
- existe `manifest.json` en la raiz;
- `manifest.json` es JSON UTF-8 valido;
- el manifest cumple el schema Pydantic;
- `task` soportado: `video_segmentation`;
- `runtime.mode` soportado: `dummy`, `native`, `docker`;
- `runtime.framework` soportado: `dummy`, `pytorch`, `container`;
- cada artifact declarado existe dentro del zip;
- no existe un modelo con el mismo `model_id` y `version`;
- no existe ya el directorio de instalacion destino.

### `GET /api/v1/models/{model_id}`

Devuelve el detalle completo del modelo. Si se requiere una version especifica
se puede usar `?version=1.0.0`.

### `PATCH /api/v1/models/{model_id}/status`

Actualiza el estado logico de un modelo a `available` o `disabled`. Tambien
acepta `?version=1.0.0`.

### `POST /api/v1/jobs/segment-video`

Mantiene el contrato de Fase 1. Antes de crear el job simulado, valida que el
modelo exista y que su estado sea `available`.

## Manifest

Ejemplo minimo esperado:

```json
{
  "model_id": "lsec_segmenter_v1",
  "name": "LSEC Binary Segmenter",
  "version": "1.0.0",
  "task": "video_segmentation",
  "runtime": {
    "mode": "native",
    "framework": "pytorch"
  },
  "artifacts": {
    "weights": "weights/model.pt",
    "preprocess_config": "config/preprocess.json",
    "labels": "labels.json"
  },
  "input_contract": {
    "media_type": "video",
    "layout": "B,T,C,H,W",
    "window_size": 16,
    "channels": 3,
    "height": 224,
    "width": 224
  },
  "output_contract": {
    "type": "frame_probabilities",
    "classes": ["background", "gesture"]
  },
  "ui": {
    "default_label": "LSEC_REGION",
    "supports_threshold": true
  }
}
```

## Schemas Pydantic

- `ModelRuntime`
- `ModelInputContract`
- `ModelOutputContract`
- `ModelUiConfig`
- `ModelManifest`
- `InstalledModel`
- `RegisteredModel`
- `ModelListResponse`
- `ModelDetailResponse`
- `ModelInstallResponse`
- `ModelStatusUpdateRequest`
- `ModelStatusUpdateResponse`

## Persistencia

El registry se guarda en:

```text
app/models_store/registry.json
```

Los modelos instalados se extraen en:

```text
app/models_store/installed/<model_id>/<version>/
```

No se usa base de datos. Los jobs siguen en memoria como en Fase 1.

## Manejo de errores

- `MODEL_PACKAGE_INVALID`: zip vacio, no zip, sin archivos o con rutas inseguras.
- `MODEL_MANIFEST_NOT_FOUND`: no existe `manifest.json` en la raiz del zip.
- `MODEL_MANIFEST_INVALID`: JSON invalido o campos incompatibles con el schema.
- `MODEL_ARTIFACT_MISSING`: artifact declarado pero ausente en el zip.
- `MODEL_ALREADY_EXISTS`: ya existe el mismo `model_id` y `version`.
- `MODEL_NOT_FOUND`: consulta o job con modelo inexistente.
- `MODEL_DISABLED`: job solicitado con modelo desactivado.

## Decisiones tecnicas

- El registry es un archivo JSON para mantener la fase simple y auditable.
- La extraccion se hace despues de validar todas las rutas del zip.
- No se ejecuta codigo ni se importa nada desde el paquete.
- El modelo dummy se mantiene como modelo `builtin`.
- El listado usa un resumen compatible; el detalle expone el manifest completo.

## Limitaciones

- No carga pesos PyTorch.
- No ejecuta Docker.
- No procesa video real.
- No verifica compatibilidad binaria de artifacts.
- No implementa versionado avanzado ni eliminacion de modelos.
- No modifica ELAN.
