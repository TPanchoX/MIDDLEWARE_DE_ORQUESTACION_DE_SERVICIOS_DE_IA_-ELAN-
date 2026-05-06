# Fase 2 - Registry de modelos funcional

## Que permite hacer esta fase

Esta fase permite registrar modelos en el middleware sin ejecutarlos todavia.
Un usuario puede entregar un paquete zip con un `manifest.json` y los archivos
declarados por ese manifest. El middleware valida el paquete, lo guarda en disco
y lo lista como modelo disponible.

## Que significa en palabras simples

El middleware ya no tiene solamente el modelo dummy fijo. Ahora puede recibir
paquetes de modelos, revisar que tengan la estructura correcta y guardarlos para
uso futuro. Todavia no se hace inferencia real: el sistema solo prepara el
inventario confiable de modelos que mas adelante podran conectarse con PyTorch o
Docker.

## Como preparar un paquete de prueba

Existe un paquete ejemplo en:

```text
examples/model_packages/dummy_valid_package/
```

Desde PowerShell:

```powershell
cd examples/model_packages/dummy_valid_package
Compress-Archive -Path .\* -DestinationPath ..\lsec_segmenter_v1.zip -Force
cd ../../..
```

El zip debe tener `manifest.json` en la raiz. No debe quedar dentro de una
carpeta adicional.

## Como probar

1. Entrar al directorio `middleware`.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Ejecutar `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.
4. Probar `GET /health`.
5. Probar `GET /api/v1/models` y verificar que aparece `dummy_lsec_segmenter`.
6. Crear el zip de ejemplo.
7. Instalarlo con `POST /api/v1/models/install`.
8. Consultarlo con `GET /api/v1/models/lsec_segmenter_v1`.
9. Desactivarlo con `PATCH /api/v1/models/lsec_segmenter_v1/status`.
10. Intentar crear un job con el modelo desactivado y verificar el error
    `MODEL_DISABLED`.

## Evidencias esperadas

Si todo esta correcto:

- `/health` responde `status: ok`;
- `/api/v1/models` lista el dummy y el modelo instalado;
- la instalacion de un zip valido responde `Model installed successfully.`;
- un zip sin `manifest.json` responde `MODEL_MANIFEST_NOT_FOUND`;
- un manifest incompleto responde `MODEL_MANIFEST_INVALID`;
- un artifact faltante responde `MODEL_ARTIFACT_MISSING`;
- instalar dos veces el mismo modelo y version responde `MODEL_ALREADY_EXISTS`;
- consultar un modelo inexistente responde `MODEL_NOT_FOUND`;
- usar en un job un modelo `disabled` responde `MODEL_DISABLED`.

## Valor para la arquitectura final

Esta fase separa la gestion de modelos de la ejecucion de modelos. Eso permite
que futuras fases puedan:

- leer metadata del modelo antes de ejecutarlo;
- ubicar pesos y configuraciones instaladas;
- elegir un runner nativo o Docker segun el manifest;
- validar contratos de entrada y salida antes de integrar inferencia real;
- mantener estable la API consumida por ELAN.

## Restricciones vigentes

- No se carga PyTorch.
- No se ejecuta Docker.
- No se procesa video.
- No se modifica ELAN.
- No se ejecuta codigo incluido dentro del paquete.
- No se usa base de datos.
