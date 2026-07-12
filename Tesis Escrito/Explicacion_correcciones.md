# Explicación de correcciones aplicadas al escrito del TIC

Fecha: 05/07/2026
Origen: observaciones del tutor sobre la primera versión enviada a revisión.

Este documento resume, observación por observación, qué se cambió, en qué archivo
y por qué. Al final hay una sección de **pasos pendientes** que deben hacerse en el
documento principal (Overleaf) para que todo compile con el nuevo formato.

---

## Observación 1 — Uso del concepto "middleware" (vs. componente / módulo)

**Qué se hizo:**

- En `02_marco_teorico.tex`, sección *Patrones de integración y rol del middleware*,
  se agregaron dos párrafos nuevos:
  1. Una definición formal de middleware en el sentido de ingeniería de software
     (capa intermedia entre aplicaciones independientes que les da servicios de
     comunicación e intercambio de datos), aclarando que aunque el término nació
     en el ámbito de sistemas distribuidos/comunicaciones, su uso consolidado en
     arquitectura de software es más amplio. Se sustenta con la referencia clásica
     de Bernstein (1996), *Middleware: A Model for Distributed System Services*,
     Communications of the ACM — referencia real y verificable, agregada a
     `referencias.bib` con la clave `bernstein1996middleware`.
  2. Un párrafo que explica por qué NO se cataloga la solución como "componente"
     ni "módulo": un módulo vive dentro del proceso, lenguaje y ciclo de vida de
     una aplicación; un componente se integra y se despliega junto con ella. Lo
     desarrollado es un proceso autónomo que se instala, actualiza y ejecuta por
     separado y atiende por red — eso es exactamente un middleware. Se aclara que
     la única pieza que sí es un "componente" en sentido estricto es el
     reconocedor Java dentro de ELAN.
- En `03_metodologia.tex`, sección *Enfoque y tipo de trabajo*, se añadió una
  aclaración breve del término remitiendo al marco teórico, y se reemplazó
  "componente de software" por "middleware" donde generaba ambigüedad.
- En `01_introduccion.tex` se aclaró que el middleware es un software
  independiente de ELAN (no una librería) y se corrigió "El alcance del
  componente" por "El alcance del trabajo".

## Observación 2 — Justificación de HTTP en un entorno local (y por qué no un .jar)

**Qué se hizo:**

- En `03_metodologia.tex`, subsección *Análisis y diseño*, el análisis de
  alternativas pasó de tres a **cuatro** opciones: se agregó explícitamente la
  alternativa de "empaquetar todo como librería JAR dentro de ELAN" y las razones
  técnicas de su descarte: los modelos son pipelines en Python con dependencias
  nativas y pesos de cientos de MB (no se pueden meter en un JAR), y una librería
  compartiría el ciclo de vida de ELAN (cada actualización de modelo obligaría a
  recompilar/redistribuir la herramienta; un fallo del modelo tumbaría ELAN).
- En el párrafo de la alternativa adoptada se agregó la justificación explícita
  de HTTP en local (la que se le comentó al tutor verbalmente): relación
  cliente-servidor, costo despreciable por loopback, aislamiento de procesos,
  frontera Java–Python verificable y testeable con Postman/curl, actualización de
  modelos sin recompilar ELAN, y que la misma interfaz sirve si el servidor se
  mueve a otra máquina.
- En `01_introduccion.tex` quedó explícito el rol de cliente (ELAN) y servidor
  local de inferencias (middleware + modelos).

## Observación 3 — Posibilidad de varios clientes en red

**Qué se hizo:**

- En `03_metodologia.tex`, sección *Despliegue y configuración del entorno*, se
  agregó un párrafo que explica que el despliegue local es el escenario previsto
  pero no un límite de la arquitectura: publicando el puerto en la IP del equipo,
  varias estaciones con ELAN pueden apuntar su URL al mismo middleware; la cola
  FIFO atiende en orden de llegada y `MIDDLEWARE_MAX_CONCURRENT_JOBS` define el
  paralelismo (con 1, las peticiones simultáneas esperan turno).
- En el Anexo C se agregó la indicación práctica: cambiar la publicación del
  puerto de `"127.0.0.1:8000:8000"` a `"8000:8000"`, apuntar los clientes a la IP
  del servidor, y considerar autenticación/cifrado y el ajuste de la concurrencia.
- En `02_marco_teorico.tex` (sección REST) se añadió media frase sobre que la
  relación cliente-servidor permite atender varios clientes sin cambiar el
  contrato.

## Observación 4 — Recomendación de migrar a un servidor potente / nube

**Qué se hizo:**

- En `04_resultados_conclusiones.tex`, sección *Recomendaciones*, se agregó una
  recomendación nueva (segunda de la lista): trasladar el orquestador y los
  modelos a un equipo de altas prestaciones (p. ej., servidor institucional con
  GPU) como servidor de inferencias compartido para un laboratorio, detallando
  los ajustes necesarios (publicar el puerto, ampliar la concurrencia,
  centralizar videos, autenticación/cifrado) y la variante de despliegue en la
  nube, con la advertencia sobre la soberanía de datos.

## Observación 5 — Visibilizar la metodología y el ciclo completo de desarrollo

**Qué se hizo (todo en `03_metodologia.tex`):**

- En *Enfoque y tipo de trabajo* ahora se nombra explícitamente la metodología:
  **modelo iterativo e incremental**, indicando qué toma de los marcos ágiles
  (como Scrum) y por qué no se usaron sus ceremonias/roles (trabajo individual).
  Se enumeran las etapas clásicas cubiertas: requerimientos, análisis y diseño,
  implementación, pruebas y despliegue.
- La sección "Proceso de desarrollo: fases iterativas" se renombró a
  **"Proceso de desarrollo: ciclo de vida del software"** y ahora abre con la
  nueva **Figura del ciclo de vida** (hecha en TikZ, no requiere imagen externa):
  Requerimientos → Análisis y diseño → Implementación (fases 1–5) → Pruebas y
  validación (fase 6) → Despliegue, con flechas de retroalimentación.
- Se agregó la subsección nueva **"Levantamiento de requerimientos"** con una
  tabla de requerimientos funcionales (RF-01 a RF-08) y no funcionales (RNF-01 a
  RNF-05). Todos derivan de lo realmente implementado (instalación por ZIP,
  activar/desactivar, inferencia, métricas, Docker, integración en ELAN, etc.);
  no se inventó ninguna funcionalidad.
- Se agregó un **diagrama de clases** (TikZ) de los servicios del middleware con
  las clases y métodos reales del código (`JobService`, `ModelRegistryService`,
  `JobQueue`, `MetricsService`, `RunnerSelector`, `DockerRunner`/`BaseRunner`,
  `DockerService`, `DockerLifecycleService`, `MemoryStore`) y sus relaciones,
  verificados contra el código fuente en `middleware/app/`.
- La introducción del capítulo ahora anuncia el recorrido completo del ciclo de
  vida (la implementación quedó como fases 1–5 y las pruebas como fase 6, que es
  lo que realmente ocurrió).

## Observación 6 — Metodología más clara y menos técnica (detalle a anexos)

**Qué se hizo:**

- La introducción del capítulo de metodología ahora avisa que el capítulo explica
  a nivel conceptual y que la profundidad técnica está en los Anexos A–D.
- Se simplificaron los pasajes más cargados de jerga, conservando el contenido:
  - Fase 2: se quitó el nombre de la función interna del bootstrap; queda la idea.
  - Fase 3: la explicación de la trazabilidad ahora remite al Anexo B.
  - Fase 4: la cola de trabajos se explica primero con su regla simple (cupo
    máximo + orden de llegada) y ya no se detallan `deque`/`Event`/`Lock` en el
    cuerpo; las métricas y el timeout se describen sin nombres de archivos ni
    excepciones internas.
  - Fase 5: el detalle del "boundary" del multipart (los dos guiones) se resumió
    y se remite a la tabla de problemas frecuentes del Anexo D, donde ya estaba
    documentado.

## Observación 7 — Numeración Tabla 3.1 / Figura 2.4 / Código 2.1

**Qué se hizo:**

- Se creó el archivo **`preambulo_correcciones.tex`** con:
  - `\counterwithin{table}{section}` y `\counterwithin{figure}{section}` →
    tablas y figuras numeradas por capítulo (Tabla 2.1, Figura 3.2, …).
  - Un nuevo tipo flotante **"Código"** (`\DeclareCaptionType[within=section]{codigo}[Código][Índice de códigos]`)
    que reemplaza al antiguo "Listado" y se numera por capítulo (Código 2.1, …).
  - Los paquetes TikZ necesarios para las dos figuras nuevas.
- En `03_metodologia.tex` y `04_resultados_conclusiones.tex` se cambiaron todos
  los `\captionof{listing}` por `\captionof{codigo}` y las menciones "Listado X"
  por "Código X".
- En los anexos, los bloques de código que estaban mal etiquetados como *figuras*
  ahora son *códigos*, y tablas/códigos se numeran por anexo (Tabla A.1,
  Código C.2, …) mediante contadores reiniciados al inicio de cada anexo.
- **Verificado**: se compiló localmente un documento de prueba con MiKTeX y el
  resultado muestra "Figura 2.1", "Código 2.1", "Código 2.2", etc.

## Observación 8 — Anexos menos jerarquizados y títulos sin negrilla

**Qué se hizo (reescritura de `Anexos_finales.tex`):**

- Cada anexo tiene ahora **un solo título** descriptivo
  (p. ej. "ANEXO A. Esquema completo del archivo manifest.json") en
  **letra normal, sin negrilla** (se fuerza con `\normalfont`).
- Se eliminaron todas las subsecciones y subsubsecciones internas (A.1, A.1.1,
  etc.). El contenido se reorganizó como prosa continua con frases de transición
  ("Respecto del campo task…", "En cuanto al objeto artifacts…", "Para cerrar el
  anexo…"), manteniendo íntegras todas las tablas y bloques de código.
- No se perdió información: todo lo que estaba bajo los antiguos subtítulos sigue
  presente, solo cambió la forma de presentarlo.

## Observación 9 — Revisión exhaustiva de citas y referencias

**Qué se hizo:**

- **Se eliminaron de `referencias.bib` 7 entradas que nunca se citaban en el
  texto** (estaban "haciendo bulto"): PyTorch, MediaPipe, LSTM (Hochreiter),
  Transformer (Vaswani), chunking (Ramshaw), CMDI (Broeder) y el artículo de
  REST/GraphQL/gRPC (Niswar).
- **Se agregó** la referencia real `bernstein1996middleware` (ver Observación 1).
- **Se quitaron citas decorativas** que no respaldaban la afirmación donde
  estaban colocadas, entre otras:
  - `fielding2000rest` duplicada en un mismo párrafo del marco teórico y en
    afirmaciones de la Fase 6 que no hablan de REST.
  - `sigelman2010dapper` (Dapper/Google) quedó citada una sola vez, justo donde
    se define trazabilidad distribuida; se quitó de los otros dos lugares.
  - `python311docs` citada junto a un párrafo de Docker sin relación.
  - Pares `pydantic/fastapi` repetidos: se conservan donde se describe la
    capacidad de la herramienta y se quitaron donde la frase describe el
    comportamiento de nuestro sistema.
- **Referencias a anexos**: ya existían en varios puntos y se agregaron nuevas
  (Fase 3 → Anexo B; Fase 5 → Anexo D; despliegue multi-cliente → Anexo C y
  recomendaciones).

## Otras correcciones menores (de paso)

- `01_introduccion.tex`: "Eudico Language Annotar" → "EUDICO Linguistic
  Annotator" (nombre correcto de ELAN); "Artifical" → "Artificial";
  "creación o entrenamientos" → "creación o entrenamiento".
- `02_marco_teorico.tex`: se corrigieron erratas y frases confusas:
  "señal(audio" → "señal (audio"; "validación y aceptar de las anotaciones" →
  "validación y aceptación…"; "mantenimientodado" → frase reescrita; "la
  herramienta de anotación se comunica con los otros lenguajes" → frase
  reescrita.

---

## PASOS PENDIENTES (manuales, en Overleaf / documento principal)

1. **Agregar al preámbulo del `main.tex`** (antes de `\begin{document}`):
   ```latex
   \input{preambulo_correcciones}
   ```
   Si el main ya carga el paquete `caption`, se puede borrar la línea
   `\usepackage{caption}` de `preambulo_correcciones.tex` para evitar un posible
   conflicto de opciones.
2. Si al compilar las tablas aparecen como "Cuadro X.Y" en lugar de "Tabla X.Y",
   cambiar la carga de babel a `\usepackage[spanish,es-tabla]{babel}` (o dejarlo
   como esté si ya muestra "Tabla").
3. Si el documento tenía definido el tipo flotante `listing` en el preámbulo
   (algo como `\DeclareCaptionType{listing}[Listado]...`), esa línea ya no se
   usa y puede eliminarse.
4. Recompilar 2 veces (y BibTeX) para que se actualicen números y referencias
   cruzadas.
5. Revisar el índice/lista de tablas y figuras: con la nueva numeración por
   capítulo se regeneran solos, pero conviene verlos una vez.
6. Las figuras nuevas (ciclo de vida y diagrama de clases) están hechas en TikZ
   dentro del propio `.tex`, así que **no** hay que subir ninguna imagen nueva a
   la carpeta `Diagramas/`.

## Qué NO se tocó

- Los resultados, métricas y evidencias (tablas de latencia, consumo, escenarios
  E-01 a E-15) quedaron tal cual: no se inventó ni alteró ningún dato.
- Los manuales anexos (`Manual_Tecnico_...` y `Manual_Usuario_...`) no requerían
  cambios para estas observaciones (no usan "Listado" ni numeración por capítulo,
  al ser documentos independientes).
- El código del middleware y del cliente Java no se modificó; todos los cambios
  son del escrito.

---
---

# SEGUNDA RONDA DE CORRECCIONES — 06/07/2026

Novedades detectadas después de aplicar la primera ronda. Los cambios se hicieron
en dos lugares a la vez: en los archivos de capítulo sueltos (`01_...`, `03_...`,
`04_...`, `Anexos_finales.tex`, `referencias.bib`) y en el documento completo
`Codigo_TIC_ENTERO_LATEX.tex`, que refleja el main de Overleaf. **La forma más
directa de llevar todo a Overleaf es reemplazar el contenido del main con el
`Codigo_TIC_ENTERO_LATEX.tex` corregido** (ver pasos pendientes al final).

## Novedad 1 — La aclaración "es un middleware, no un componente/módulo" estaba en el capítulo equivocado

**Problema:** el marco teórico es estado del arte; no debe hablar de lo que
nosotros implementamos ni justificar decisiones propias. Sin embargo, ahí estaban
las frases "Ese es precisamente el papel del software desarrollado en este
trabajo..." y todo el párrafo "Esta precisión también explica por qué la solución
no se cataloga como un componente o un módulo...".

**Qué se hizo:**

- En el **marco teórico** (sección *Patrones de integración y rol del
  middleware*) quedaron solo las definiciones generales: qué es un middleware
  (Bernstein 1996), qué es un módulo, qué es un componente (Szyperski 2002) y en
  qué se diferencian entre sí, **sin ninguna mención a la solución del TIC**.
  El archivo suelto `02_marco_teorico.tex` ya tenía esta versión de una sesión
  anterior; lo que faltaba era actualizar el main de Overleaf, que seguía con la
  versión antigua. El `Codigo_TIC_ENTERO_LATEX.tex` ya quedó sincronizado.
- La justificación aplicada a **nuestra** solución (proceso autónomo, se instala
  y actualiza por separado, corre en su propio contenedor, atiende por red; la
  única pieza que sí es un componente es el reconocedor Java dentro de ELAN) se
  movió al capítulo de **Metodología → Enfoque y tipo de trabajo**, como párrafo
  nuevo a continuación de la aclaración corta que ya existía ahí. Ese es el lugar
  correcto: es una decisión/caracterización del trabajo, no teoría.
- Se agregó a `referencias.bib` la entrada **`szyperski2002component`**
  (Szyperski, *Component Software: Beyond Object-Oriented Programming*, 2.ª ed.,
  Addison-Wesley, 2002), porque el marco teórico corregido la cita y no existía
  en el `.bib` (habría dado cita indefinida al compilar).

**Sobre HTTP:** se revisó lo mismo para la justificación del uso de HTTP. En el
marco teórico (sección REST) solo hay teoría general, y la justificación aplicada
a nuestra solución ya estaba en Metodología → *Análisis y diseño* (análisis de
las 4 alternativas). Estaba en el lugar correcto; **no hizo falta mover nada**.

## Novedad 2 — El diagrama de clases TikZ compilaba mal

**Qué se hizo:**

- Se creó el archivo **`Diagramas/diagrama_clases_middleware.drawio`** con el
  mismo diagrama (mismas clases, métodos y relaciones que el TikZ, que a su vez
  fueron verificados contra el código real de `middleware/app/`). Se abre en
  https://app.diagrams.net o en la aplicación de escritorio de draw.io.
- En `03_metodologia.tex` (y en el ENTERO) el bloque TikZ del diagrama de clases
  se reemplazó por una figura con imagen:
  `\includegraphics[width=0.97\textwidth]{Diagramas/diagrama_clases_middleware.png}`.
  La `\caption` y el `\label{fig:diagrama_clases}` se conservaron, así que las
  referencias cruzadas del texto no cambian.
- **La figura TikZ del ciclo de vida (Figura del ciclo de desarrollo) se dejó
  como está**, porque la novedad reportada era solo del diagrama de clases.

**Pendiente tuyo:** abrir el `.drawio` en draw.io, exportar como PNG
(Archivo → Exportar como → PNG, zoom 200 % o 300 DPI para que se vea nítido) con
el nombre `diagrama_clases_middleware.png` y subirlo a la carpeta `Diagramas/`
de Overleaf.

## Novedad 3 — Anexos con numeración romana de páginas + faltaba el capítulo 5

**Problema:** después de las referencias, el main hacía
`\pagenumbering{Roman}` y retomaba el contador de los preliminares, por lo que
los anexos salían con páginas romanas (X, XI, ...) tanto en el pie de página como
en el índice.

**Qué se hizo (en el ENTERO / main de Overleaf):**

- Se eliminó el bloque `\appendix` + `\pagenumbering{Roman}` +
  `\setcounter{page}{...}`. Ahora los anexos **continúan la numeración arábiga**
  del cuerpo (verificado en compilación local: Anexo A en pág. 57, tras terminar
  las referencias en la 56).
- Se agregó el **capítulo 5: ANEXOS** (`\section[ANEXOS]{Anexos}`) con un párrafo
  corto que presenta qué contiene cada anexo (A–D detalle técnico, E–G enlaces).
  Los títulos "ANEXO A...", "ANEXO B..." siguen igual que antes (sin numerar,
  con su entrada en el índice).
- De paso se eliminó un bloque de comentarios que estaba **triplicado** en el
  main justo antes del Anexo A.

## Novedad 4 — Títulos de capítulos en mayúsculas en el índice

**Qué se hizo:** se usó el argumento opcional de `\section`, que controla el
texto que va al índice, dejando el título del cuerpo intacto (este ya sale en
mayúsculas por el `\MakeUppercase` del formato de títulos):

- `\section[INTRODUCCIÓN]{Introducción}` (en `01_introduccion.tex`)
- `\section[METODOLOGÍA]{Metodología}` (en `03_metodologia.tex`)
- `\section[RESULTADOS, CONCLUSIONES Y RECOMENDACIONES]{...}` (en `04_...`)
- `\section[REFERENCIAS BIBLIOGRÁFICAS]{Referencias bibliográficas}` (en el main)
- `\section[ANEXOS]{Anexos}` (nuevo, en el main)

Los subtítulos (1.1, 2.3, etc.) quedaron tal como estaban. Verificado en el
`.toc` de la compilación local: los cinco capítulos aparecen en mayúsculas y el
resto sin cambios.

## Novedad 5 — Tres anexos nuevos con los enlaces del proyecto

Se agregaron al final de `Anexos_finales.tex` (y del ENTERO), cortos y en el
mismo estilo de los demás:

- **ANEXO E. Repositorio del código fuente del middleware** — presenta el repo
  de GitHub y qué contiene (la app FastAPI con la estructura del Código de la
  metodología, Dockerfile, docker-compose, requirements).
- **ANEXO F. Repositorio del código fuente de ELAN 7.1 modificado** — presenta el
  repo con el árbol fuente de ELAN + el paquete `...recognizer.ai`, y remite al
  Anexo D para compilarlo.
- **ANEXO G. Manuales de uso y de desarrollo del sistema** — enlace a la carpeta
  compartida de OneDrive con el manual de usuario (investigadores) y el manual
  técnico (desarrolladores de backends).

> **IMPORTANTE:** las tres URL son **de ejemplo** (están marcadas con
> `% TODO: reemplazar por la URL real...` en el código). Hay que reemplazarlas
> por los enlaces reales de tus repositorios y de tu carpeta OneDrive.

## Novedad 6 — Nombres de anexos en números romanos (solo en el ENTERO)

**Qué se hizo (a pedido expreso, solo cambio de nombres, en
`Codigo_TIC_ENTERO_LATEX.tex`):**

- Los anexos pasaron de letras a números romanos: ANEXO A→I, B→II, C→III,
  D→IV, E→V, F→VI, G→VII (títulos y entradas del índice).
- Para no dejar referencias rotas, también se actualizaron las menciones dentro
  del texto ("ver Anexo~B" → "ver Anexo~II", "los Anexos A, B, C y D" →
  "los Anexos I, II, III y IV", etc.).
- Los contadores por anexo se renombraron en consecuencia para que las tablas y
  códigos coincidan con el título del anexo donde viven: Tabla A.1 → Tabla I.1,
  Código B.2 → Código II.2, etc. (si prefieres que conserven las letras, es
  revertir los `\renewcommand{\thetable}{I.\arabic{table}}` y compañía).
- Verificado con compilación local: el índice muestra ANEXO I a VII y el PDF
  genera sin errores.
- **Ojo:** este cambio se hizo únicamente en el ENTERO (que es lo que va al main
  de Overleaf). El archivo suelto `Anexos_finales.tex` y las menciones en
  `03_metodologia.tex` / `04_resultados_conclusiones.tex` siguen con letras; si
  se quiere mantener los sueltos como respaldo fiel, habría que replicar ahí el
  mismo renombre.

## Verificación realizada

Se compiló localmente el documento completo con MiKTeX (pdflatex + biber + 2
pasadas, con un stub para las imágenes que solo existen en Overleaf):

- PDF de 80 páginas generado **sin errores** y **sin citas indefinidas**.
- Índice: capítulos 1–5 en mayúsculas; anexos E, F y G presentes.
- Páginas de anexos en arábigo continuo (A=57, B=61, C=65, D=67, E=70, F=71, G=71).
- La entrada `szyperski2002component` se resuelve en la bibliografía.

## PASOS PENDIENTES en Overleaf

1. Reemplazar el contenido del `main.tex` de Overleaf con el de
   `Codigo_TIC_ENTERO_LATEX.tex` corregido (o, si prefieres ir por partes,
   actualizar los capítulos con los archivos sueltos y aplicar a mano en el main:
   título de referencias con `[REFERENCIAS BIBLIOGRÁFICAS]`, bloque de anexos sin
   numeración romana y nuevo capítulo 5).
2. Agregar la entrada `szyperski2002component` a `referencias_ieee.bib` de
   Overleaf (está en el `referencias.bib` local, justo después de la de
   Bernstein).
3. Exportar el PNG del diagrama de clases desde draw.io y subirlo como
   `Diagramas/diagrama_clases_middleware.png`.
4. Reemplazar las 3 URL de ejemplo de los Anexos E, F y G por las reales.
5. Recompilar (XeLaTeX/pdfLaTeX → Biber → 2 compilaciones más) y revisar el
   índice una vez.
