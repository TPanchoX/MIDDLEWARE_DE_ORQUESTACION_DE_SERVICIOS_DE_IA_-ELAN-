# Comparación párrafo a párrafo — Capítulo 4 (original vs. corregido)

**Archivos comparados:**
- Original: `04_resultados_conclusiones.tex`
- Corregido: `04_resultados_conclusiones_CORREGIDO.tex`

**Verificación mecánica previa (automatizada con `diff` + `grep`):** los dos archivos comparten exactamente los mismos `\label{}`, `\ref{}`, `\cite{}`, `\includegraphics{}`, títulos de sección, menciones a los Anexos A–D y el conjunto completo de términos en `\textbf{}` y `\texttt{}` (nombres de clases, endpoints, variables y contenido técnico de tablas). Las cifras clave (33673.43, 32428.00, 34 181, 34 198, 8.51 s, 510 fotogramas, 59.94 FPS, 0.13 %, 52.45 MiB, 194.89 %, 1.4 GiB, 250 ms, E-01…E-15, quince escenarios) aparecen el mismo número de veces en ambos. **Las 4 tablas y las 6 figuras están copiadas literalmente, sin ningún cambio.** Lo único que difiere es la prosa.

Leyenda de cada bloque: **[O]** = texto original, **[C]** = texto corregido, **✔** = nota de validación.

---

## RESULTADOS

### Bloque 1 — Párrafo introductorio de Resultados

**[O]** «Los resultados se presentan en relación directa con los tres objetivos específicos del proyecto, de modo que cada evidencia puede relacionarse con una decisión de diseño, una acción de implementación y un criterio de verificación. Esta organización permite distinguir entre los productos construidos, los contratos técnicos que se implementaron y los resultados durante la validación final. Por lo tanto, cada bloque describe los entregables obtenidos, la forma en que se integran con la arquitectura general y las métricas o evidencias utilizadas para confirmar su funcionalidad.»

**[C]** «Los resultados de este capítulo siguen el orden de los tres objetivos específicos del proyecto, de manera que cada evidencia pueda rastrearse hasta una decisión de diseño, una acción de implementación y un criterio de verificación concretos. Organizarlos de este modo facilita distinguir entre los productos construidos, los contratos técnicos que los sostienen y el comportamiento observado durante la validación final; por ello, cada bloque describe los entregables obtenidos, la manera en que se articulan con la arquitectura general y las métricas o evidencias con las que se comprobó su funcionamiento.»

**✔** Se eliminó el eco «se presentan en relación / puede relacionarse» y la repetición «los resultados… los resultados». Tres oraciones cortas pasaron a dos con mejor hilado. Ningún dato técnico involucrado.

---

### Bloque 2 — Objetivo 1: párrafo principal (contratos y clases)

**[O]** «El primer objetivo específico planteaba analizar el mecanismo de extensión AVATecH de ELAN, combinando el estudio de la documentación oficial con la ingeniería inversa del código fuente, para definir los contratos de interfaz REST y el esquema de instalación de modelos que permiten integrar servicios externos de inferencia en el flujo de anotación. Su cumplimiento produjo dos resultados complementarios. Por un lado, los contratos: la solicitud y la respuesta de inferencia que viajan por HTTP (ejemplificadas en el Anexo B) y el esquema manifest.json que gobierna la instalación de modelos (Anexo A). Por otro, su materialización en código: cinco clases principales y un conjunto de DTO […] La pieza central es el reconocedor AIOrchestrationRecognizer, que cumple la interfaz Recognizer de ELAN y permite que la herramienta delegue el procesamiento de video al middleware sin cambiar la base del software. Con ello, ELAN conserva su ciclo de trabajo y el procesamiento especializado queda encapsulado en un componente externo, en línea con el propósito del protocolo AVATecH.»

**[C]** «El primer objetivo específico planteaba analizar el mecanismo de extensión AVATecH de ELAN, combinando el estudio de la documentación oficial con la ingeniería inversa del código fuente, con el fin de definir los contratos de interfaz REST y el esquema de instalación de modelos que hacen posible integrar servicios externos de inferencia en el flujo de anotación. De su cumplimiento se desprenden dos resultados que se complementan entre sí. El primero corresponde a los contratos: […] El segundo es su materialización en código: […] La pieza central de esta integración es el reconocedor AIOrchestrationRecognizer, que implementa la interfaz Recognizer de ELAN y hace que la herramienta delegue el procesamiento de video al middleware sin tocar la base del software; gracias a ello, ELAN conserva intacto su ciclo de trabajo mientras el procesamiento especializado queda encapsulado en un componente externo, en línea con el propósito con el que fue concebido el protocolo AVATecH.»

**✔** Intactos: Anexos A, B y D, `manifest.json`, paquete `mpi.eudico.client.annotator.recognizer.ai`, referencia al Código `lst:estructura_clases_elan`, cita `auer2014avatech`. Único ajuste semántico deliberado: «cumple la interfaz» → «implementa la interfaz», que es el término correcto en Java y coherente con cómo lo describe la metodología. Se varió «Por un lado / Por otro» → «El primero / El segundo» y se fundieron las dos últimas oraciones.

---

### Bloque 3 — Figura del panel (`fig:panel_elan`)

**[O]** «La Figura X muestra el panel de configuración AIOrchestrationRecognizerPanel tal como aparece en la interfaz de ELAN cuando el usuario selecciona el reconocedor *AI Orchestration Middleware Bridge*. Este panel convierte en controles visibles los parámetros que antes solo podían enviarse desde clientes externos: dirección del servidor, video a analizar, modelo de IA instalado, nivel de anotación destino y formato de etiqueta. La figura evidencia que la configuración necesaria para ejecutar una inferencia quedó incorporada en el mismo entorno donde el investigador revisa y edita sus anotaciones, sin pasos intermedios fuera de la herramienta.»

**[C]** «En la Figura X se aprecia el panel de configuración AIOrchestrationRecognizerPanel tal como aparece dentro de ELAN cuando el usuario selecciona el reconocedor *AI Orchestration Middleware Bridge*. Dicho panel traduce en controles visibles parámetros que hasta entonces solo podían enviarse desde clientes externos ---dirección del servidor, video a analizar, modelo de IA instalado, nivel de anotación destino y formato de etiqueta---, de modo que la configuración necesaria para lanzar una inferencia quedó incorporada al mismo entorno donde el investigador revisa y edita sus anotaciones, sin pasos intermedios fuera de la herramienta.»

**✔** Los cinco parámetros se conservan en el mismo orden. Se rompió el patrón «La Figura X muestra…» y se eliminó la tercera oración redundante («La figura evidencia que…») integrándola con «de modo que». Nota: `---` genera raya (—) al compilar en LaTeX; la metodología ya usa rayas, así que es consistente.

---

### Bloque 4 — Figura del diálogo de modelos (`fig:dialogo_modelos`)

**[O]** «La Figura X muestra el diálogo AIModelManagerDialog, accesible desde el botón *Gestionar modelos…* del panel. Este diálogo centraliza las operaciones de instalación, activación y desactivación de modelos sin que el usuario abandone el entorno de anotación de ELAN. Demuestra que la gestión del ciclo de vida de los modelos, que en el middleware ocurre mediante endpoints REST, quedó expuesta al usuario final a través de controles gráficos coherentes con la interfaz de ELAN: cada botón del diálogo corresponde a una operación HTTP que el investigador ya no necesita conocer.»

**[C]** «Por su parte, la Figura X recoge el diálogo AIModelManagerDialog, accesible desde el botón *Gestionar modelos…* del panel. Allí se concentran las operaciones de instalación, activación y desactivación de modelos sin que el usuario abandone el entorno de anotación: cada botón del diálogo corresponde a una operación HTTP del middleware que el investigador ya no necesita conocer, con lo cual la gestión del ciclo de vida de los modelos, resuelta internamente a través de endpoints REST, quedó expuesta al usuario final por medio de controles gráficos coherentes con la interfaz de ELAN.»

**✔** Mismo contenido reordenado: la idea de «cada botón = una operación HTTP» pasa a ser causa («con lo cual…») en vez de aparecer suelta al final. Se eliminó el verbo huérfano «Demuestra que…» (oración sin sujeto explícito en el original) y el doble «mediante/a través de».

---

### Bloque 5 — Cliente HTTP (`AIOrchestrationMiddlewareClient`)

**[O]** «El cliente HTTP …, implementado con java.net.http.HttpClient, usa exclusivamente HTTP/1.1 para garantizar compatibilidad con Uvicorn y evitar negociación automática de HTTP/2 […] El método installModel construye manualmente el cuerpo multipart/form-data para enviar paquetes ZIP sin dependencias externas, mientras que buildErrorMessage traduce los códigos de error […] La integración cumple el contrato AVATecH porque el reconocedor reporta progreso mediante RecognizerHost.setProgress(), devuelve segmentos mediante insertSegmentationAsTier() y responde a la cancelación del usuario mediante stop(). El procedimiento para compilar estas clases con Maven […] se describe paso a paso en el Anexo D…»

**[C]** «En cuanto al cliente HTTP …, implementado sobre java.net.http.HttpClient, este trabaja exclusivamente con HTTP/1.1 para asegurar la compatibilidad con Uvicorn y evitar que se negocie automáticamente HTTP/2 frente a un servidor que no lo ofrece por defecto. Su método installModel construye a mano el cuerpo multipart/form-data que transporta los paquetes ZIP, sin recurrir a dependencias externas, mientras que buildErrorMessage convierte los códigos de error estructurados del middleware en mensajes legibles […] La integración respeta el contrato AVATecH en sus tres puntos esenciales: el reconocedor informa el avance con RecognizerHost.setProgress(), entrega los segmentos con insertSegmentationAsTier() y atiende la cancelación del usuario a través de stop(). El procedimiento para compilar estas clases con Maven, registrar el reconocedor mediante el mecanismo SPI de Java e incorporar el JAR resultante a una instalación de ELAN 7.1 se detalla paso a paso en el Anexo D…»

**✔** Los tres métodos AVATecH, las citas (`java11_httpclient`, `uvicorn_docs`), Maven, SPI, ELAN 7.1 y el Anexo D están intactos. Se eliminó el triple «mediante… mediante… mediante» del original (quedó «con… con… a través de») y se añadió el conector «En cuanto a» para enlazar con los bloques anteriores.

---

### Bloque 6 — Objetivo 2: párrafo introductorio

**[O]** «Para dar cumplimiento al segundo objetivo específico, enfocado en codificar el núcleo del orquestador con Python y virtualización ligera mediante Docker, incorporando control de concurrencia y gestión del ciclo de vida de los contenedores para asegurar la estabilidad durante inferencias simultáneas, se desarrolló el servicio central del middleware. Este núcleo concentra la validación de solicitudes, la exposición de endpoints, la coordinación de jobs y la entrega de métricas operativas. La decisión de usar una API REST permitió que ELAN, Postman y otros clientes se comunicaran con el mismo contrato HTTP…»

**[C]** «El segundo objetivo específico exigía codificar el núcleo del orquestador con Python y virtualización ligera mediante Docker, incorporando control de concurrencia y gestión del ciclo de vida de los contenedores para sostener la estabilidad del sistema durante inferencias simultáneas. En respuesta a ese planteamiento se desarrolló el servicio central del middleware, que concentra la validación de solicitudes, la exposición de endpoints, la coordinación de jobs y la entrega de métricas operativas. Optar por una API REST hizo que ELAN, Postman y cualquier otro cliente conversaran con el mismo contrato HTTP sin depender del lenguaje interno de cada componente, en consonancia con el principio de interfaces desacopladas…»

**✔** El original abría con una oración subordinada de 45 palabras antes de llegar al verbo principal («se desarrolló»), difícil de seguir; se partió en dos conservando literalmente el enunciado del objetivo. Citas `fielding2000rest` y `fastapi2026features` intactas.

---

### Bloque 7 — Endpoints y MemoryStore

**[O]** «La API REST expone ocho endpoints organizados en cuatro grupos funcionales, tal como se resume en la Tabla X. El servidor Uvicorn sirve la aplicación FastAPI sobre el estándar ASGI y mantiene disponibles los endpoints de gestión, entre ellos GET /health y GET /api/v1/metrics, durante la ejecución de una inferencia prolongada. Además, el resultado de cada job queda disponible durante la sesión a través de GET /api/v1/jobs/{job_id}, gracias a un almacén en memoria (MemoryStore) […] Este conjunto confirma que el middleware no se limita a ejecutar inferencias: también ofrece las operaciones de observabilidad y administración necesarias…»

**[C]** «La API expone ocho endpoints organizados en cuatro grupos funcionales, resumidos en la Tabla X. El servidor Uvicorn sirve la aplicación FastAPI sobre el estándar ASGI y mantiene disponibles los endpoints de gestión ---entre ellos GET /health y GET /api/v1/metrics--- incluso mientras transcurre una inferencia prolongada. A ello se suma que el resultado de cada job permanece consultable durante la sesión a través de GET /api/v1/jobs/{job_id}, gracias a un almacén en memoria (MemoryStore) que conserva las respuestas completadas hasta el siguiente reinicio del servicio. Este conjunto pone de manifiesto que el middleware no se limita a ejecutar inferencias: ofrece además las operaciones de observabilidad y administración necesarias…»

**✔** Cambios solo de conectores («Además» → «A ello se suma que»; «confirma» → «pone de manifiesto», porque «confirma» se repetía mucho en el capítulo). Endpoints y `MemoryStore` idénticos.

---

### Bloque 8 — JobQueue y concurrencia

**[O]** «El componente JobQueue implementa una cola FIFO con límite configurable de concurrencia mediante collections.deque y threading.Event […] El parámetro MIDDLEWARE_MAX_CONCURRENT_JOBS, configurable desde el docker-compose.yml descrito en el Anexo C, controla cuántos backends Docker pueden ejecutar inferencias simultáneamente. Con el valor por defecto de 1, solo un contenedor carga pesos en memoria en cada instante, lo que reduce el riesgo de desbordamiento durante cargas concurrentes; mientras un job espera su turno, el resto de la API sigue respondiendo. La Tabla X presenta los resultados de la prueba controlada con dos solicitudes simultáneas y evidencia que la segunda permanece en cola…»

**[C]** «El componente JobQueue implementa una cola FIFO con límite configurable de concurrencia apoyándose en collections.deque y threading.Event […] Cuántos backends Docker pueden inferir a la vez lo decide el parámetro MIDDLEWARE_MAX_CONCURRENT_JOBS, ajustable desde el docker-compose.yml descrito en el Anexo C. Con el valor por defecto de 1, un solo contenedor carga pesos en memoria en cada instante, lo que reduce el riesgo de desbordamiento bajo cargas concurrentes; entretanto, mientras un job aguarda su turno, el resto de la API continúa respondiendo. La Tabla X recoge los resultados de la prueba controlada con dos solicitudes simultáneas y deja ver que la segunda permanece en cola hasta que la primera libera el slot de ejecución.»

**✔** Todos los identificadores técnicos y el Anexo C intactos; cita `python_threading` intacta. La inversión «Cuántos backends… lo decide el parámetro» rompe la cadencia sujeto-verbo-objeto repetida, un rasgo que ayuda a humanizar el texto.

**Tabla `tab:metricas_concurrencia`: sin cambios — copiada literal.**

---

### Bloque 9 — Interpretación de la tabla de concurrencia

**[O]** «La Tabla X demuestra de forma cuantitativa el aislamiento y el ordenamiento de peticiones del middleware. Al recibir dos solicitudes de inferencia en el mismo instante, los contadores internos pasaron a active_jobs = 1 y queued_jobs = 1: el mecanismo de exclusión mutua retuvo la segunda petición en la cola FIFO mientras el contenedor procesaba la primera, evitando la saturación de los recursos del equipo. Los contadores además son coherentes entre sí: los 10 jobs del histórico se reparten entre 7 completados, 1 expirado por timeout y los 2 de la prueba en curso (1 activo y 1 en cola). Asimismo, el tiempo registrado en last_exec_ms, cercano a 32.4 segundos, ofrece una línea base…»

**[C]** «Los valores de la Tabla X respaldan cuantitativamente tanto el aislamiento como el ordenamiento de peticiones del middleware. Al llegar dos solicitudes de inferencia en el mismo instante, los contadores internos pasaron a active_jobs = 1 y queued_jobs = 1: el mecanismo de exclusión mutua retuvo la segunda petición en la cola FIFO mientras el contenedor procesaba la primera, con lo cual se evitó saturar los recursos del equipo. Los contadores, además, resultan coherentes entre sí, pues los 10 jobs del histórico se reparten entre 7 completados, 1 expirado por timeout y los 2 de la prueba en curso (1 activo y 1 en cola). El tiempo registrado en last_exec_ms, cercano a 32.4 segundos, aporta a su vez una línea base del rendimiento del modelo de reconocimiento integrado.»

**✔** Aritmética verificada de nuevo: 7 + 1 + 2 = 10 ✓. Todos los contadores y el valor 32.4 s intactos. Solo cambian arranque («La Tabla demuestra» → «Los valores de la Tabla respaldan») y conectores («Asimismo» eliminado, era mecánico).

---

### Bloques 10 y 11 — Figuras de Postman (`fig:postman_health`, `fig:postman_metrics`)

**[O]** Ambos párrafos abrían igual: «La Figura X muestra la respuesta del endpoint…», y cerraban con «Esta evidencia confirma…» / «Esta información fue usada como evidencia…».

**[C]** El primero ahora abre por el escenario: «La Figura X corresponde al escenario E-01 de la validación final y presenta la respuesta del endpoint GET /health verificada desde Postman. Comprobar esta disponibilidad básica antecede, en el orden de las pruebas, a las operaciones más costosas del sistema, como la instalación de modelos o las inferencias sobre video.» El segundo abre con locativo: «En la Figura X puede observarse la respuesta del endpoint GET /api/v1/metrics después de ejecutar dos inferencias exitosas y un timeout forzado. La lectura de los contadores total_jobs, completed_jobs y timeout_jobs deja constancia de que el middleware, además de procesar solicitudes, conserva trazabilidad cuantitativa del desenlace de cada job; esta información sirvió como evidencia de observabilidad durante la validación final.»

**✔** E-01, los tres contadores y el hecho probado (2 exitosas + 1 timeout forzado) intactos. El matiz «antecede en el orden de las pruebas» es fiel al original («antes de ejecutar operaciones más costosas»).

---

### Bloque 12 — DockerRunner: párrafo introductorio

**[O]** «La gestión del ciclo de vida de los contenedores, segunda vertiente de este objetivo, se materializó en el componente DockerRunner y en el contrato de comunicación entre el middleware y el backend del modelo. Este resultado conecta la arquitectura de orquestación con el procesamiento real de video: el middleware no interpreta directamente las señas, sino que prepara el entorno, invoca el backend de IA, valida su respuesta y adapta los segmentos al formato que ELAN puede insertar en la línea de tiempo.»

**[C]** Idéntico salvo: «se materializó» → «tomó forma en» (evita repetir «materialización», ya usada en el Objetivo 1) y «conecta» → «enlaza»; la construcción «no interpreta…, sino que prepara» pasó a «no interpreta…; prepara», con punto y coma.

**✔** Sin cambios de contenido.

---

### Bloque 13 — DockerRunner: detalle y backend de validación

**[O]** «El DockerRunner traduce la ruta del video del sistema anfitrión al punto de montaje interno del contenedor, /data/videos, verifica la disponibilidad del backend mediante polling sobre GET /health con reintentos cada 250 ms y transforma la respuesta JSON del backend en objetos TemporalSegment validados por Pydantic. El aporte del TIC en este objetivo no es el modelo de reconocimiento en sí, sino la capa que permite integrarlo […] Para la validación se utilizó el backend lsec_bio_gloss_final_v1, cuyo desarrollo no forma parte del alcance de este trabajo…»

**[C]** «En concreto, el DockerRunner traduce la ruta del video […] verifica la disponibilidad del backend mediante polling sobre GET /health con reintentos cada 250 ms y transforma la respuesta JSON del backend en objetos TemporalSegment validados por Pydantic. Conviene subrayar que el aporte del TIC en este punto no es el modelo de reconocimiento en sí, sino la capa que hace posible integrarlo […] Para la validación se empleó el backend lsec_bio_gloss_final_v1, cuyo desarrollo queda fuera del alcance de este trabajo; su pipeline interno corre encapsulado en un contenedor Docker, con las dependencias aisladas tanto de ELAN como del middleware. El manifest completo con el que se instala este paquete se recoge en el Anexo A.»

**✔** Punto crítico validado: se mantiene explícito que **el modelo NO es aporte del TIC** y que el contrato es `/health` + `/infer` + `manifest.json`. Rutas, tiempos (250 ms), Pydantic, `lsec_bio_gloss_final_v1`, Anexo A y citas intactos.

---

### Bloque 14 — Figura de inferencia (`fig:postman_inferencia`)

**[O]** «La Figura X muestra la respuesta de una inferencia exitosa ejecutada desde Postman contra el endpoint POST /api/v1/jobs/segment-video. La respuesta incluye segmentos detectados, marcas temporales, etiquetas de glosa, predicciones alternativas y trazabilidad de ejecución. Esta figura vincula el contrato REST con el resultado lingüístico esperado, porque evidencia que el backend devuelve datos suficientes…»

**[C]** «La Figura X ilustra la respuesta de una inferencia exitosa ejecutada desde Postman contra el endpoint POST /api/v1/jobs/segment-video, con segmentos detectados, marcas temporales, etiquetas de glosa, predicciones alternativas y trazabilidad de ejecución. Su relevancia radica en que vincula el contrato REST con el resultado lingüístico esperado, al constatar que el backend devuelve datos suficientes para que el middleware construya anotaciones temporales compatibles con ELAN. Un ejemplo completo de esta respuesta, con la descripción campo por campo del objeto trace y de sus etapas, figura en el Anexo B.»

**✔** Tres oraciones → dos, mismos cinco elementos de la respuesta, Anexo B intacto.

---

### Bloque 15 — Latencia por etapas

**[O]** «La Tabla X resume los tiempos reales observados en el campo trace.stages […] Los valores corresponden a un video de LSEc con una duración de 8.51 segundos (510 fotogramas a 59.94 FPS) procesado en un equipo con CPU Intel Core i5 de 12.ª generación. La desagregación por etapas permite distinguir el costo de validación, espera en cola, arranque del contenedor, comprobación de disponibilidad, inferencia y postprocesamiento. La tabla evidencia que la sobrecarga introducida por la orquestación es marginal…»

**[C]** «Los tiempos reales observados en el campo trace.stages de la respuesta del middleware durante la inferencia de validación se resumen en la Tabla X. Los valores corresponden a un video de LSEc con una duración de 8.51 segundos (510 fotogramas a 59.94 FPS) procesado en un equipo con CPU Intel Core i5 de 12.ª generación. Desagregar la latencia por etapas ayuda a distinguir el costo de validación, espera en cola, arranque del contenedor, comprobación de disponibilidad, inferencia y postprocesamiento; de esa desagregación se desprende que la sobrecarga introducida por la orquestación es marginal, pues la suma de validación, cola y postprocesamiento apenas alcanza unos pocos milisegundos […] El arranque del contenedor registró 0 ms porque este ya se encontraba activo (*warm start*), condición habitual después de la primera ejecución.»

**✔** Cifras y explicación del *warm start* idénticas; solo se invirtió el arranque (el sujeto pasa a ser «los tiempos», no «la Tabla») y se enlazaron las dos últimas oraciones.

**Tabla `tab:latencia_etapas`: sin cambios — copiada literal.**

---

### Bloque 16 — Anotaciones en ELAN (`fig:elan_anotaciones`)

**[O]** «La Figura X muestra las anotaciones generadas por el sistema en la línea de tiempo de ELAN después de ejecutar el reconocedor desde el panel integrado, de acuerdo con los escenarios E-07 y E-08. Esta evidencia es relevante porque cierra el flujo completo: la inferencia se ejecuta fuera de ELAN, pero los resultados regresan como anotaciones temporales ubicadas en el nivel de anotación configurado. Las marcas de inicio y fin […] confirma que la segmentación temporal fue interpretada correctamente por la herramienta de anotación.»

**[C]** «Como cierre del flujo, la Figura X presenta las anotaciones generadas por el sistema en la línea de tiempo de ELAN tras ejecutar el reconocedor desde el panel integrado, de acuerdo con los escenarios E-07 y E-08. Su valor probatorio está en que completa el ciclo: la inferencia ocurre fuera de ELAN, pero los resultados regresan como anotaciones temporales ubicadas en el nivel de anotación configurado. Las marcas de inicio y fin de cada anotación deben coincidir con los intervalos de señas visibles en el video procesado, ya que esa correspondencia confirma que la herramienta de anotación interpretó correctamente la segmentación temporal.»

**✔** E-07/E-08 y el argumento del cierre de flujo intactos; la voz pasiva final («fue interpretada correctamente por») pasó a activa («la herramienta interpretó correctamente»).

---

### Bloque 17 — Objetivo 3: párrafo introductorio

**[O]** «El tercer objetivo específico, enfocado en validar el desempeño técnico del middleware mediante pruebas de carga en escenarios de anotación de LSEc, se cubrió con quince escenarios de validación distribuidos en cuatro categorías: conectividad, gestión de modelos, inferencia y manejo de errores. La validación midió latencia de comunicación, consumo de recursos computacionales y recuperación ante fallos. Esta organización permitió comprobar tanto el comportamiento observable desde las interfaces visibles para el usuario como la consistencia interna de archivos, métricas, contenedores y rutas montadas.»

**[C]** «El tercer objetivo específico, orientado a validar el desempeño técnico del middleware mediante pruebas de carga en escenarios de anotación de LSEc, se cubrió con quince escenarios distribuidos en cuatro categorías: conectividad, gestión de modelos, inferencia y manejo de errores. La validación midió latencia de comunicación, consumo de recursos computacionales y recuperación ante fallos, una combinación que abarcó tanto el comportamiento observable desde las interfaces visibles para el usuario como la consistencia interna de archivos, métricas, contenedores y rutas montadas.»

**✔** Se eliminó «escenarios de validación… La validación… Esta organización permitió comprobar» (tres apariciones de la misma raíz en tres oraciones). Categorías y alcance idénticos.

---

### Bloque 18 — Presentación de la tabla de escenarios

**[O]** «La Tabla X sintetiza los resultados de los escenarios más representativos de la validación final. Los identificadores E-01 a E-15 funcionan como etiquetas de trazabilidad para relacionar cada acción de prueba con su respuesta HTTP esperada, su resultado observado y la evidencia obtenida durante la ejecución.»

**[C]** Prácticamente igual; solo «para relacionar» → «que enlazan» y se quitó «los resultados de» (redundante con «sintetiza»).

**✔** **Tabla `tab:escenarios_validacion` (E-01 a E-15): sin cambios — copiada literal.**

---

### Bloque 19 — Consumo de recursos

**[O]** «La Tabla X resume el consumo de recursos medido con docker stats […] el middleware mantiene un perfil bajo (~0.13 % de CPU y ~52.45 MiB de RAM) […] El consumo intensivo se concentra en el contenedor del backend, que utiliza ~194.89 % de CPU (casi dos núcleos completos) y ~1.4 GiB de memoria […] Esta asimetría respalda una decisión de diseño central del sistema: como el costo computacional vive en el backend, es posible detener o reemplazar modelos sin afectar la disponibilidad del orquestador.»

**[C]** «Por otro lado, la Tabla X condensa el consumo de recursos medido con docker stats […] el primero mantiene un perfil bajo (~0.13 % de CPU y ~52.45 MiB de RAM), asociado estrictamente a la orquestación, la validación y las métricas, mientras que el gasto intensivo se concentra en el contenedor del backend, que utiliza ~194.89 % de CPU (casi dos núcleos completos) y ~1.4 GiB de memoria para ejecutar el pipeline de inferencia visual. Semejante asimetría respalda una decisión de diseño central del sistema: dado que el costo computacional vive en el backend, es posible detener o reemplazar modelos sin comprometer la disponibilidad del orquestador.»

**✔** Las cuatro cifras y la conclusión de diseño intactas; dos oraciones se unieron con «mientras que». «El consumo… consume… consumo» del original quedó en una sola aparición de la raíz. Cita `docker_cli_stats` intacta.

**Tabla `tab:consumo_recursos`: sin cambios — copiada literal.**

---

### Bloque 20 — Escenarios de caja blanca

**[O]** «Los escenarios de caja blanca confirmaron la consistencia del estado interno después de las operaciones principales. El archivo registry.json reflejó la entrada correcta del manifest tras la instalación; el mecanismo de bootstrap manifests recuperó el registro automáticamente después de eliminar registry.json y reiniciar el middleware; la traducción de la ruta del video quedó registrada en los logs del backend bajo el prefijo /data/videos; y docker inspect confirmó el montaje correcto del directorio de videos. Estas comprobaciones complementan los códigos HTTP porque verifican que el estado persistente y la infraestructura Docker quedan coherentes después de cada operación.»

**[C]** «En el plano interno, los escenarios de caja blanca corroboraron la consistencia del estado después de las operaciones principales: el archivo registry.json reflejó la entrada correcta del manifest tras la instalación; el mecanismo de bootstrap manifests reconstruyó el registro de forma automática después de eliminar registry.json y reiniciar el middleware; la traducción de la ruta del video quedó asentada en los logs del backend bajo el prefijo /data/videos; y docker inspect verificó el montaje correcto del directorio de videos. Estas comprobaciones complementan los códigos HTTP porque examinan que el estado persistente y la infraestructura Docker permanezcan coherentes tras cada operación.»

**✔** Las cuatro comprobaciones son las mismas y en el mismo orden. El original usaba «confirmaron… confirmó… verifican» — quedó «corroboraron… verificó… examinan». El conector «En el plano interno» contrasta con el comportamiento observable del bloque 17.

---

### Bloque 21 — Cierre de Resultados

**[O]** «En conjunto, los tres bloques de resultados cubren el ciclo completo del sistema: el primero demuestra que ELAN puede delegar el procesamiento […] Los anexos A a D complementan estos resultados con los artefactos necesarios para reproducirlos…»

**[C]** «Vistos en conjunto, los tres bloques de resultados recorren el ciclo completo del sistema: el primero prueba que ELAN puede delegar el procesamiento sin perder su flujo de anotación y que los contratos definidos sostienen esa comunicación; el segundo, que el orquestador regula la carga, administra los contenedores y devuelve la inferencia convertida en anotaciones temporales utilizables; y el tercero, que el comportamiento se mantiene predecible tanto en operación normal como frente a fallos. Los anexos A a D acompañan estos resultados con los artefactos necesarios para reproducirlos: el contrato de empaquetado, un ejemplo íntegro de respuesta, la configuración de despliegue y el procedimiento de compilación e integración en ELAN.»

**✔** Estructura trimembre y contenido de los cuatro anexos idénticos; solo sinónimos («cubren» → «recorren», «demuestra» → «prueba», «complementan» → «acompañan»).

---

## CONCLUSIONES

### Bloque 22 — Párrafo introductorio

**[O]** «El presente trabajo confirmó que es posible incorporar servicios de Inteligencia Artificial al flujo de anotación de ELAN sin alterar de manera profunda su arquitectura. La solución desarrollada actúa como una capa intermedia […] de modo que el investigador puede conservar su entorno habitual de trabajo mientras accede a resultados automáticos que luego pueden ser revisados y corregidos…»

**[C]** «El trabajo realizado confirmó que es posible acercar servicios de Inteligencia Artificial al flujo de anotación de ELAN sin alterar en profundidad su arquitectura. La solución desarrollada opera como una capa intermedia entre la herramienta de anotación y los modelos de reconocimiento, de suerte que el investigador conserva su entorno habitual de trabajo mientras accede a resultados automáticos que después puede revisar y corregir…»

**✔** «pueden ser revisados y corregidos» (pasiva) → «puede revisar y corregir» (activa). Sin cambios de fondo.

### Bloque 23 — Conclusión 1 (análisis de ELAN)

**[O]** «…Esta revisión fue fundamental para que la solución no funcionara como una herramienta aislada, sino como un apoyo integrado al proceso que ya realiza el investigador. En lugar de reemplazar el criterio humano, el sistema entrega segmentos y etiquetas preliminares que pueden ser aceptados, ajustados o descartados dentro de ELAN. De esta forma, la integración respeta el uso lingüístico de la herramienta y mantiene la anotación final bajo responsabilidad del especialista.»

**[C]** «…Sin esa revisión, la solución habría terminado funcionando como una herramienta aislada; con ella, en cambio, se consiguió un apoyo integrado al proceso que el investigador ya realiza. Lejos de reemplazar el criterio humano, el sistema entrega segmentos y etiquetas preliminares que pueden aceptarse, ajustarse o descartarse dentro de ELAN, de manera que la integración respeta el uso lingüístico de la herramienta y deja la anotación final bajo responsabilidad del especialista.»

**✔** Misma tesis con estructura contrafactual («Sin esa revisión… con ella, en cambio») en lugar de la fórmula «fue fundamental para que». Pasivas eliminadas.

### Bloque 24 — Conclusión 2 (separación de capas)

**✔** Cambios mínimos: «facilita la integración de tecnologías distintas» → «facilita conjugar tecnologías distintas»; «evita que las dependencias… afecten a ELAN» → «impide que las dependencias… alcancen a ELAN»; se añadió «los modelos, por su parte,» para variar la enumeración de tres miembros. Roles de ELAN / middleware / modelos idénticos.

### Bloque 25 — Conclusión 3 (arquitectura local)

**[O]** «El uso de una arquitectura local permitió proteger los videos […] Esta decisión es importante en escenarios de investigación, donde los equipos disponibles pueden tener capacidades limitadas…»

**[C]** «Apostar por una arquitectura local protegió los videos y anotaciones del investigador, puesto que la información no necesita salir de la estación de trabajo para ser procesada. A ello se añade que el control sobre la ejecución de inferencias evitó que varios procesos pesados compitieran sin coordinación por los mismos recursos del equipo, algo especialmente relevante en escenarios de investigación donde los equipos disponibles suelen tener capacidades limitadas y donde la estabilidad de la herramienta de anotación importa tanto como la precisión del modelo utilizado.»

**✔** Tres oraciones → dos, sin pérdida de contenido; se eliminó «El uso de… permitió» (patrón repetido en el capítulo).

### Bloque 26 — Conclusión 4 (manejo de fallos)

**✔** La lista de fallos (videos inexistentes, modelos no disponibles, timeouts, contenedores detenidos) pasó de subordinada con «como» a enumeración tras dos puntos. «Esto confirma que» → «Queda confirmado, con ello, que». Contenido intacto.

### Bloque 27 — Conclusión 5 (contribución principal)

**✔** Idéntica en contenido (arquitectura local, extensible y desacoplada; no sustituye la revisión lingüística; anotaciones temporales editables). Solo cambió la puntuación de la segunda oración («sino ofrecer» → «; ofrece, más bien,») y «reconstruir toda la herramienta» → «reconstruir la herramienta completa».

---

## RECOMENDACIONES

### Bloque 28 — Párrafo introductorio

**[O]** «A partir de los resultados obtenidos, el sistema puede seguir creciendo sin perder la idea central que guio este trabajo…»

**[C]** «Los resultados obtenidos indican que el sistema puede seguir creciendo sin perder la idea central que guio este trabajo…» — resto casi idéntico; «Las siguientes recomendaciones proponen mejoras futuras orientadas a» → «Las recomendaciones que siguen proponen mejoras futuras encaminadas a».

**✔** Sin cambios de fondo. (El original repetía «A partir de los resultados» que ya abría las Conclusiones.)

### Bloque 29 — Recomendación 1 (planificador de recursos)

**✔** «Conviene mejorar» → «Convendría afinar» (condicional, tono de propuesta); «Una posible línea de trabajo es» → «Una línea de trabajo posible es»; las dos últimas oraciones se unieron con punto y coma. Idea técnica (planificador CPU/GPU/memoria, límites para modelos exigentes) intacta.

### Bloque 30 — Recomendación 2 (servidor compartido)

**✔** Es la recomendación más técnica y se conserva casi literal: servidor institucional con GPU, comunicación por HTTP, URL del reconocedor apuntando a la IP, `MIDDLEWARE_MAX_CONCURRENT_JOBS` (con la aclaración del valor 1), repositorio centralizado de videos, autenticación y cifrado, y la reserva sobre soberanía de datos en la nube. Cambios: «abre una línea de crecimiento que conviene aprovechar» → «abre una vía de crecimiento que merece aprovecharse» (evita repetir «línea de trabajo» de la Rec. 1); «Dado que» → «Puesto que»; «Para dar ese salto se requieren» → «Dar ese salto exige»; «puede extenderse» → «admite extenderse».

### Bloque 31 — Recomendación 3 (base de datos ligera)

**✔** «Es aconsejable fortalecer» → «Es aconsejable robustecer»; los tres beneficios en infinitivo («registrar… consultar… reducir») pasaron a condicional («registraría… facilitaría… reduciría»), concordando con el tono de propuesta; «Esta mejora debería mantenerse» → «Eso sí, la mejora debería mantenerse». Principio de soberanía de datos intacto.

### Bloque 32 — Recomendación 4 (más modelos)

**✔** Dos oraciones se fundieron con gerundio («documentando y empaquetando»); «Esta continuidad» → «Semejante continuidad». Ejemplos (señas específicas, glosas amplias, información no manual) idénticos.

### Bloque 33 — Recomendación 5 (alternativas de glosa)

**✔** «También sería valioso mejorar» → «Otra mejora valiosa apunta a» (rompe la cadena de arranques con «También/Se debería»); «Esto ayudaría a que la revisión sea más transparente y útil» → «la revisión ganaría así en transparencia y utilidad». Contenido intacto.

### Bloque 34 — Recomendación 6 (evaluación lingüística)

**✔** Las tres oraciones del original se integraron en dos mediante una relativa («…una evaluación lingüística a cargo de especialistas en LSEc, que compare… y considere…»). Criterios (etiqueta correcta + tiempos de inicio/fin) y propósito (medir aporte real, orientar mejoras) idénticos.

---

## Veredicto de la segunda pasada

1. **Fidelidad técnica: verificada al 100 %.** Ningún dato, cifra, nombre de clase, endpoint, escenario, anexo o cita cambió. Las 4 tablas y las 6 figuras son copias literales.
2. **Dos ajustes semánticos deliberados** (ambos correctos y coherentes con la metodología): «cumple la interfaz» → «implementa la interfaz» (Bloque 2) y voz pasiva → activa en varios cierres.
3. **Correcciones aplicadas durante esta segunda pasada** (ecos que la primera versión corregida había introducido): se redujo «comprobar/comprueba» de 6 a 3 apariciones, «hizo posible/hace posible» de 4 a 3, y «por su parte» de 3 a 2.
4. **Pendiente de tu decisión:** reemplazar el contenido de `04_resultados_conclusiones.tex` por el de `04_resultados_conclusiones_CORREGIDO.tex` (o cambiar el `\input` en el `main.tex` de Overleaf).
