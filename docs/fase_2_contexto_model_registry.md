# Fase 2 - Registry de modelos

## Contexto
La Fase 1 ya implementó la base del middleware FastAPI con endpoints de health, listado de modelos, creación de jobs simulados y consulta de jobs.

Ahora se debe implementar el Registry de Modelos, que permitirá instalar, validar, listar y consultar modelos disponibles mediante paquetes de modelo.

## Objetivo de la Fase 2
Permitir que el middleware registre modelos desde paquetes `.zip` que contengan un `manifest.json` y archivos asociados.

## Alcance
Implementar:
- instalación de modelos desde zip;
- validación de manifest;
- persistencia simple del registry en archivo JSON;
- listado de modelos instalados;
- consulta de modelo por ID;
- activación/desactivación lógica de modelos;
- documentación técnica y funcional.

## Fuera de alcance
No implementar todavía:
- carga real de PyTorch;
- inferencia real;
- Docker runner;
- procesamiento real de video;
- integración con ELAN Java;
- ejecución de código arbitrario de modelos.

## Estructura esperada de un paquete de modelo

model_package.zip
 ├── manifest.json
 ├── weights/
 │   └── model.pt
 ├── config/
 │   └── preprocess.json
 ├── labels.json
 └── README.md

## Manifest esperado

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

## Validaciones obligatorias
El middleware debe validar:
- que el zip existe y se puede abrir;
- que contiene manifest.json;
- que el manifest tiene campos obligatorios;
- que model_id no está vacío;
- que version no está vacía;
- que task sea soportado;
- que runtime.mode sea soportado: dummy, native o docker;
- que runtime.framework sea soportado: dummy, pytorch o container;
- que los archivos declarados en artifacts existan dentro del zip;
- que no se instale un modelo duplicado con mismo model_id y versión;
- que no se permita path traversal dentro del zip.

## Directorios esperados

middleware/
 ├── app/
 │   ├── models_store/
 │   │   ├── registry.json
 │   │   └── installed/
 │   │       └── <model_id>/
 │   │           └── <version>/
 │   │               ├── manifest.json
 │   │               ├── weights/
 │   │               ├── config/
 │   │               └── labels.json

## Endpoints nuevos o mejorados

### POST /api/v1/models/install
Recibe un archivo zip por multipart/form-data.
Instala el modelo si el paquete es válido.

### GET /api/v1/models
Debe listar tanto el dummy inicial como los modelos instalados.

### GET /api/v1/models/{model_id}
Debe devolver detalle del modelo.

### PATCH /api/v1/models/{model_id}/status
Permite cambiar estado lógico:
- available
- disabled

## Estados de modelo
- available
- disabled
- invalid

## Criterios de aceptación
La fase se considera completa si:
- se puede instalar un paquete zip válido;
- se rechaza un zip sin manifest;
- se rechaza un manifest incompleto;
- se rechaza un paquete con artifacts inexistentes;
- se rechaza un modelo duplicado;
- GET /api/v1/models lista los modelos instalados;
- GET /api/v1/models/{model_id} devuelve detalle;
- PATCH permite activar/desactivar;
- el endpoint de segmentación de Fase 1 sigue funcionando con dummy_lsec_segmenter;
- existe documentación técnica;
- existe documentación funcional;
- README se actualiza.