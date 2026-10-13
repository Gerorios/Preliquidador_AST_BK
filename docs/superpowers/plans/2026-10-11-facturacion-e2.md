# Facturación, etapa 2: Comprobantes, Adjuntos y migración del histórico

Fecha: 2026-10-11.

Sale de:
- `docs/modulos/facturacion/plan-facturacion.md` (sección 5, etapa 2);
- `pantallas.md`;
- `CONTEXT-facturacion.md`;
- el ADR-0019.

Va por el carril completo porque hay DDL, permisos, archivos que suben los usuarios y una carga de datos en producción.

La E1 se planifica en paralelo. Lo que este plan supone de ella se marca **(supuesto E1)** y se junta en el anexo final.

## Antes de empezar: premisas que no se cumplen

1. **La barra de filtros, las tablas y el estado por pantalla no son del núcleo.**
   - `plan-facturacion.md` (sección 6) y `pantallas.md` dicen que Facturación los "reutiliza".
   - Pero viven en Preliquidación: `src/modulos/preliquidacion/components/FiltrosBar.jsx`, `TablaOrdenable.jsx` y `src/modulos/preliquidacion/estadoPantallas.js`.
   - Dependen de `pages/opcionesCascada.js`, `pages/ordenarFilas.js`, `pages/estadoGuardado.js` y `pages/filtrarLineas.js` (`CAMPOS_LINEAS`).
   - Un módulo no importa a otro (ADR-0013), así que hay que subirlos a `src/core/` en un PR de núcleo aparte (PR-0). Eso toca 5 páginas de Preliquidación.
   - Si la E1 ya lo hace, PR-0 desaparece.
2. **El núcleo no lee clientes, fincas, tareas ni empresas.**
   - El plan dice que el Cliente se lee "a través del núcleo", pero `app/core/` no tiene ninguna de esas lecturas.
   - Las de Preliquidación (`app/modulos/preliquidacion/services/consulta_externa.py:209-233`) devuelven nombres, sin id.
   - Facturación escribe las suyas, con id, en su `consulta_externa`.
3. **Hoy "empresa" sale de la base de sueldos.**
   - Es un DISTINCT con caché de 10 minutos, en `app/modulos/preliquidacion/api/preliquidacion.py:102-128`, dentro de Preliquidación.
   - Facturación copia esa consulta (sección 3.1, decisión 8; pregunta 9).
4. **nginx corta los pedidos de más de 1 MB.**
   - `deploy/nginx-preliquidacion.conf` no fija `client_max_body_size`, y el default de nginx es 1 MB.
   - Un PDF de 2 MB recibiría un 413 en HTML antes de llegar al backend.
   - Se corrige en la plantilla (BK-B) y en el VPS (FRENADO F4).
5. **La planilla no dice ni el tipo ni la Empresa emisora, y FACT N° no siempre es un número.**
   - No hay columna de tipo ni ningún importe negativo.
   - "Nosotros" mezcla fechas y notas.
   - Hay 11 filas con dos números en FACT N°, con la forma "`<n>-<m>`", "`<n> - <m>`" o "`F.<n> - NC <m>`"; casi todas son de cosecha. Se pasan tal cual (pregunta 3).
   - Hay 69 filas sin número (vacías o con "-"), de 5 Clientes. También se migran (pregunta 4).
   - Hay una fila con "#VALUE!" como importe.
   - Hay unas 250 filas con número y FECHA FAC vacía.
   - La sección 3.4 resuelve cada caso; lo que no me corresponde va a preguntas abiertas.
6. **El export tiene 990 filas, pero `fuentes/origenes.md` habla de unas 1,9 mil en el mismo período.** Si salió filtrado, la aceptación se mide contra un recorte (pregunta 1).

## 1. Qué se pide

Tres partes:
- **Comprobantes:** Factura y Nota de crédito, cada una con cabecera y Líneas. Se cargan y editan a mano desde la pantalla Comprobantes.
- **Adjuntos:** PDF o imagen, hasta 5 por Comprobante, en una carpeta del VPS fuera del código.
- **Migración del histórico:** un script que lee el CSV de la planilla y se puede correr varias veces sin duplicar.

Se da por buena cuando el histórico migrado suma lo mismo que la planilla, por Cliente y mes. Se mide con un informe del mismo script.

## 2. Qué encontré en el código

### 2.1 Lo que ya existe y sirve

**Permisos**
- `app/core/permisos.py`: `requiere_pantalla(modulo, *pantallas, nivel)` expone `.requisito`. Con varias pantallas, alcanza con una.
- Patrón a copiar: `app/modulos/terceros/permisos.py`.
- `tests/terceros/test_mapa_permisos.py` fija la tabla exacta de rutas y su conteo.
- `tests/core/test_endpoints_con_permiso.py` exige que cada ruta `/api/*` tenga exactamente un requisito.
- Los roles de prueba con pantallas que no están en `SEMILLA` se arman con `SimpleNamespace` (`tests/roles_de_prueba.py`).

**Subida y descarga**
- Terceros recibe un `UploadFile` en `app/modulos/terceros/api/terceros.py` (`POST /estaciones/{id_}/subir`): lo lee con `archivo.file.read()` y convierte `ArchivoInvalido` en 422. No limita el tamaño ni guarda en disco.
- `python-multipart` ya está en `requirements.txt`. No hay ninguna librería de detección de tipo, así que la detección va por firmas a mano.
- Descarga en el backend: `app/modulos/preliquidacion/api/export.py:33` (`StreamingResponse` + `Content-Disposition`).
- Descarga en el front: `src/modulos/preliquidacion/services/preliquidacion.js:157-166` (`responseType: 'blob'` + objectURL).
- La sesión viaja en un header Bearer (`src/core/api.js:12-18`). Un `<a href>` directo al endpoint no lleva el token.

**Configuración y guardas**
- Configuración por módulo: `app/modulos/preliquidacion/config.py` (un `BaseSettings` propio, que se lee al usarse para poder hacer monkeypatch).
- Guarda de base: `app/core/config.py:10-21` (`guardia_base_propia`, `permitir_base_produccion`).
- `scripts/importar_tarifas_del_excel.py:134` sólo escribe en `testing`.

**Scripts de carga**
- `scripts/importar_tarifas_del_excel.py`: simula por defecto y escribe con `--aplicar`. No adivina: lista lo inconsistente y lo saltea.
- `scripts/validar_terceros_etapa1.py`: valida contra la fuente y sale con 0 o 1.

**Modelos y migraciones**
- `app/modulos/terceros/models.py`:
  - `Numeric`, y `creado_por` como FK a `usuarios.id` con `from app.core.models import Usuario  # noqa: F401`;
  - `UniqueConstraint` con nombre;
  - `SIN_DIMENSION`, porque MySQL acepta varios NULL en un UNIQUE;
  - importes siempre positivos, con el signo dado por el concepto.
- `migrations/terceros/006_estaciones.sql`: encabezado `-- NO DIFERIBLE`, InnoDB utf8mb4, FK/KEY/UNIQUE con nombre.
- `tests/core/test_manifiesto_migraciones.py` controla `migrations/ORDEN.txt`.
- Ningún test compara el modelo con el SQL. Lo hace `comparar_esquema` al arrancar contra la base (`app/core/esquema.py`).

**Tests de referencia**
- Consultas externas con `SesionFalsa`: `tests/terceros/test_consulta_externa.py:25-49`.
- API con servicios falsos: `tests/terceros/test_api_terceros.py`.
- SQLite en memoria: `tests/terceros/test_estaciones.py`.
- Decimales: `app/modulos/terceros/schemas.py` usa `Decimal`, que sale como texto en el JSON.

**Front**
- `CargandoOverlay` está montado en `src/core/layout/Layout.jsx:48` con `useIsMutating()`. Toda escritura con `useMutation` muestra "Procesando..." sola.
- `CargandoContenido({texto})` sirve para lecturas lentas.
- `mensajeDeError` (`src/core/mensajeError.js`) usa `detail.mensaje` cuando `detail` es un objeto.
- `puedeEditar` está en `src/core/permisos.js:18`.
- `ProtectedRoute` sólo exige Ver (`src/core/layout/ProtectedRoute.jsx:17`).
- Ruta con id y `menu: false`: `src/modulos/preliquidacion/rutas.jsx:25`.
- Subida con FormData: `src/modulos/terceros/services/terceros.js:170-174`.
- `npm test` corre `node --test` con globs fijos (`package.json:11`). Los tests de Facturación no corren hasta sumar su glob, y sólo prueban funciones puras, sin render.

**Otros**
- El maestro de campo marca la baja con `estado = 9`: todas las consultas filtran `estado <> 9` (`consulta_externa.py:211, 219-220, 231`).
- `.gitignore` ignora `docs/modulos/*/fuentes/*` salvo `LEEME.md`, así que el CSV no entra a git.
- `scripts/refrescar_testing.py` no copia las tablas de Terceros. `tests/core/test_refrescar_testing.py` exige que cada tabla listada exista en el modelo.

### 2.2 La planilla exportada (sólo formato)

**Archivo:** `fuentes/planilla-facturacion.csv`, en el checkout principal y fuera de git. Está en UTF-8, quizás con BOM, con fin de línea CRLF, separado por comas y con comillas.

**Columnas**

| Columna | Uso |
|---|---|
| FECHA A FACTURAR (d/m/aaaa, el 1 o el 16) | Fecha de la Línea |
| CLIENTE | Se resuelve contra el maestro |
| FINCA | Casi siempre vacía; opcional |
| TAREA | Se resuelve contra el maestro |
| UM | Unidad de la Línea |
| CANT FACTURA | Cantidad |
| PRECIO UNIT | Precio unitario |
| FACTURA | Importe |
| FACT N° | Número del Comprobante |
| FECHA FAC (d/m/aaaa o d/m/aa) | Fecha del Comprobante |
| QUINCENA A FACTURAR, GRUPO TAREA, Nosotros | Se ignoran |

**Formato de los números (es-AR)**
- Aparecen como "1.234,56", "1234,5", "12,5", "1234", "$1.234,56" o "$ 1.234,56".
- Algunos vienen con "-" o "#VALUE!".

**Lo que se observa en los datos**
- El importe a veces no es cantidad por precio: el precio se ve redondeado y hay errores de tipeo. El histórico guarda el importe de la planilla tal cual.
- Un mismo número aparece en filas de dos Clientes distintos. Eso confirma que la agrupación tiene que ser por número **y** Cliente.
- Un Comprobante puede tener Líneas de varios meses (por ejemplo, transportes de cosecha).

**Conteos que pasó el usuario**
- UM: PLANTA 496, TANCADA 176, HORAS TRACTOR 150, HORAS PEON 14, HECTAREA 5, NO FACTURABLE 1, vacía 1, BINS 89, BINS M 28, BINS C 14, VIAJES 17. Suman 991 contra 990 filas.
- La simulación da los números exactos.

### 2.3 Convenciones a respetar

- Las tablas llevan el prefijo `facturacion_`. La migración va en `migrations/facturacion/` y se suma al final de `ORDEN.txt`, con `-- NO DIFERIBLE`.
- El router va en `/api/facturacion`, con rutas en español con guiones (GUIA, regla 13).
- Cada endpoint declara pantalla y nivel (GUIA, regla 14).
- `detail` es un objeto `{tipo, mensaje, ...}` cuando la interfaz tiene que reaccionar (GUIA, regla 15).
- Schemas Pydantic para todo.
- Las excepciones de dominio se definen en el servicio y el router las traduce a códigos HTTP.
- Comentarios con el porqué.
- En el front:
  - CSS Modules con los tokens de `src/index.css`;
  - textos en español sin emojis;
  - sin dependencias nuevas;
  - toasts con react-hot-toast;
  - React Query.
- Interfaz con `impeccable`. Antes de editar: `impeccable context` (en Windows `.claude/skills/impeccable/scripts/impeccable.cmd`), el playbook `reference/new-work.md` y leer `reference/craft-floor.md`. En la revisión: `/impeccable critique` y `/impeccable audit`.
- Zonas sensibles, con dos rondas de revisión: los `permisos.py`, `migrations/` y los `models.py`.

## 3. Pasos

### 3.1 Decisiones

**Modelo.** Una migración, `migrations/facturacion/003_comprobantes.sql` (la `001` es de la E1 y la `002` la borra), crea las tres tablas.

`facturacion_comprobante`:

| Columna | Tipo | Nota |
|---|---|---|
| `id` | INT PK AI | |
| `tipo` | VARCHAR(20) NOT NULL | `factura` o `nota_credito` |
| `cliente_id` | INT NOT NULL | id del maestro de clientes de campo |
| `cliente_nombre` | VARCHAR(150) NOT NULL | Copia al guardar: el listado no lee la base de campo |
| `empresa_emisora` | VARCHAR(100) NULL | Vacía sólo en históricos |
| `numero` | VARCHAR(30) NULL | Normalizado. Vacío sólo en un histórico sin número (pregunta 4) |
| `fecha` | DATE NULL | Vacía sólo en históricos sin FECHA FAC |
| `factura_corregida_id` | INT NULL, FK a la misma tabla | Obligatoria en una NC cargada a mano |
| `es_historico` | TINYINT(1) NOT NULL DEFAULT 0 | |
| `pendiente_de_facturar` | TINYINT(1) NOT NULL DEFAULT 0 | Sólo en un histórico sin número posterior al corte: el Cruce (E3) no cuenta sus Líneas como facturado (pregunta 4) |
| `clave_identidad` | VARCHAR(160) NOT NULL UNIQUE | `E\|<empresa>\|<tipo>\|<numero>` (con el tipo desde R3); en un histórico, `H\|<cliente_id>\|<numero>`; en un histórico sin número, `S\|<cliente_id>\|<fecha a facturar AAAA-MM-DD>` |
| `creado_en`, `creado_por` | DATETIME; INT NULL con FK a `usuarios` | |
| `actualizado_en`, `actualizado_por` | NULL; INT NULL con FK a `usuarios` | |

- Índices: `(cliente_id, numero)` y `(fecha)`.
- Por qué existe `clave_identidad`:
  - el histórico no tiene Empresa, MySQL acepta varios NULL en un UNIQUE, y en la planilla el mismo número aparece para dos Clientes;
  - la clave la calcula el servicio y la base la hace cumplir;
  - de eso depende el "sin duplicar" de la migración.

`facturacion_linea`:

| Columna | Tipo | Nota |
|---|---|---|
| `id` | | |
| `comprobante_id` | INT NOT NULL, FK con ON DELETE CASCADE | |
| `orden` | SMALLINT | |
| `fecha` | DATE NOT NULL | |
| `tarea_id` | INT NOT NULL | |
| `tarea_nombre` | VARCHAR(150) NOT NULL | Copia del maestro |
| `unidad` | VARCHAR(20) NOT NULL | Una de las 9 |
| `finca_id`, `finca_nombre` | NULL | Las dos o ninguna |
| `cantidad` | DECIMAL(14,2) | |
| `precio_unitario` | DECIMAL(14,4) | |
| `importe` | DECIMAL(14,2) | Siempre >= 0: el signo lo da el tipo, como en Terceros |

- Índices: `(comprobante_id)` y `(tarea_id, fecha)`, este último para el Cruce de la E3.

`facturacion_adjunto`:

| Columna | Tipo | Nota |
|---|---|---|
| `id` | | |
| `comprobante_id` | INT NOT NULL, FK **sin cascada** | |
| `nombre_original` | VARCHAR(255) | Saneado; sólo para mostrar |
| `nombre_en_disco` | VARCHAR(64) UNIQUE | `uuid4().hex` + la extensión del tipo detectado |
| `tipo_contenido` | VARCHAR(50) | El detectado por contenido |
| `tamano_bytes` | INT | |
| `subido_en` | DATETIME | |
| `subido_por` | INT NULL con FK a `usuarios` | |

- Sin cascada: borrar un Comprobante con adjuntos pasa por el servicio, que borra los archivos. Además, el DELETE de vuelta atrás de los históricos falla si alguno ya tiene adjunto, que es lo que se quiere.

**Unidades (supuesto E1 para las claves).** `horas_peon`, `horas_tractor`, `plantas`, `hectareas`, `tancadas`, `bins`, `bins_c`, `bins_m`, `viajes`. Las de cosecha no llevan ninguna marca aparte: la E3 las deja fuera del Cruce por su unidad.

**Reglas del Comprobante (servicio):**
1. Normalización:
   - número: se recortan los extremos, se colapsan los espacios y se pasa a mayúsculas; no admite `|` ni puede quedar vacío (sólo la migración crea Comprobantes sin número);
   - Empresa: recorte y mayúsculas.
2. Alta:
   - Cliente activo (estado distinto de 9);
   - Empresa, número, fecha y tipo obligatorios;
   - la Empresa normalizada, hasta 100 caracteres; una Factura no lleva `factura_corregida_id` (`comprobante_invalido` en ese campo; agregado en la ejecución, par A4);
   - el número normalizado tiene hasta 30 caracteres, el largo de la columna; más largo da 422 `comprobante_invalido` con `campo="numero"` (agregado en la ejecución, par A1);
   - al menos una Línea.
3. Línea:
   - tarea del maestro y unidad entre las 9;
   - finca opcional, pero del Cliente;
   - cantidad > 0 y precio >= 0;
   - `importe = round(cantidad × precio, 2)` con ROUND_HALF_UP, calculado en el backend. Los nombres se copian del maestro.
   - la cantidad admite hasta 2 decimales y 12 cifras enteras, y el precio hasta 4 y 10, como sus columnas; lo que no entra da `linea_invalida` en ese campo, y un importe que no entra en la suya, en `importe` (agregado en la ejecución, par A4).
4. Repetidos:
   - una Empresa con un número que ya existe **en el mismo tipo** da 409 `comprobante_repetido`: Facturas y Notas de crédito numeran aparte (decisión del usuario, 2026-10-12, revisión de BK-A; paso R3);
   - una **Factura** de un Cliente con un número que ya tiene un histórico da 409 `historico_mismo_numero`. Evita contar dos veces mientras la planilla siga viva (pregunta 13). Los históricos son siempre Facturas, así que una Nota de crédito no choca con ellos (R3).
5. Nota de crédito:
   - `factura_corregida_id` es obligatorio y apunta a una **Factura del mismo Cliente**, que puede ser histórica;
   - la Empresa no se valida;
   - el total sale negativo.
6. Una tarea marcada No facturable se acepta (pregunta 5); el aviso lo muestra el front.
7. Edición y borrado:
   - el PUT reemplaza la cabecera y todas las Líneas;
   - un histórico no se edita ni se borra (409 `historico_no_editable`, pregunta 6); sus adjuntos sí se pueden subir y quitar;
   - una Factura con Notas de crédito no cambia de Cliente ni de tipo, y no se borra (409 `factura_con_notas`);
   - conservar un Cliente que pasó a baja se permite; lo mismo una tarea que pasó a baja en una Línea, si esa tarea ya estaba en el Comprobante;
   - edición simultánea (pregunta 18): el PUT trae `actualizado_en` tal como lo devolvió el detalle (null si nunca se editó); si no coincide con el de la base, otra persona lo cambió y responde 409 `comprobante_modificado`, sin tocar nada;
   - el DELETE borra también los adjuntos, archivos incluidos (pregunta 15).
8. Lecturas del campo:
   - clientes activos, fincas por cliente y empresas, cada una con caché de proceso de 10 minutos, como `preliquidacion.py:102-128`;
   - las empresas copian la consulta de Preliquidación, que tiene 4 líneas: subirla al núcleo obligaría a tocar Preliquidación para que no quede duplicada igual; si aparece un tercer uso, se sube.
   - el listado y el detalle no leen la base de campo, porque usan las copias.

**Adjuntos:**
- **Configuración**
  - `app/modulos/facturacion/config.py` define `FACTURACION_ADJUNTOS_DIR`, una ruta absoluta. Las constantes del módulo son `TAMANO_MAXIMO = 10 MB` y `MAXIMO_POR_COMPROBANTE = 5`.
  - Si la variable está vacía, la carpeta no existe o está dentro del repo, se responde 503 `adjuntos_sin_configurar`. El arranque no se frena: el resto de la app anda.
- **Tipo por contenido**
  - Firmas: PDF `%PDF-`, PNG `\x89PNG\r\n\x1a\n`, JPEG `\xff\xd8\xff`.
  - La extensión tiene que ser `.pdf`, `.png`, `.jpg` o `.jpeg` **y** coincidir con el tipo detectado. Sin SVG (XSS) ni HEIC.
- **Tamaño:** se lee `archivo.file.read(TAMANO_MAXIMO + 1)` y, si hay más bytes, se responde 413.
- **Path traversal**
  - El nombre en disco lo genera el sistema; el del usuario sólo se guarda saneado (sin ruta ni caracteres de control, hasta 255).
  - Antes de abrir o borrar, se resuelve la ruta y se verifica que siga dentro de la carpeta.
  - La descarga busca por `(comprobante_id, adjunto_id)` y nunca usa una ruta que mande el cliente.
- **Escritura**
  - Se escribe a un temporal en la misma carpeta y se hace `os.replace`.
  - Si falla el commit, se borra el archivo.
  - Para quitar, se borra primero la fila y después el archivo, tolerando que falte: un archivo huérfano es menos grave que una fila que apunta a la nada.
- **Concurrencia:** el límite de 5 se cuenta con el Comprobante bloqueado (`with_for_update()`; en SQLite no hace nada).
- **Respuesta del GET**
  - `Content-Type` es el detectado al subir; nunca el que declaró el navegador.
  - Lleva `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store` y `Content-Disposition: inline; filename="<ascii>"; filename*=UTF-8''<codificado>`.
- **Front**
  - El archivo se pide como blob con `api.js` y se abre en una pestaña nueva. La pestaña se abre en el mismo click, para esquivar el bloqueador de ventanas; si el navegador la bloquea, se descarga.
  - Con `responseType: 'blob'`, el `detail` de un error llega como Blob y `api.js` no lo puede leer, así que el mensaje se arma con el `status`.

**Migración del histórico.** Toda la lógica pura va en `app/modulos/facturacion/services/historico.py`, que se prueba con SQLite y maestros falsos. El script `scripts/migrar_historico_facturacion.py` es una capa fina encima.

- **Lectura**
  - CSV en `utf-8-sig`, con `,` o `;` detectado en el encabezado.
  - Los encabezados se buscan por nombre (recortados y en mayúsculas). Si falta alguno, se responde con un error que lista los que faltan.
  - Si no encuentra el archivo, avisa que `fuentes/` está fuera de git.
- **Números y fechas**
  - Números en formato es-AR, sin "$". Si hay coma, es el decimal y los puntos son de miles. Sin coma, los puntos son de miles sólo en grupos de 3 dígitos. Si hay más decimales que los de la columna, se marca ilegible.
  - Fechas `d/m/aaaa` o `d/m/aa`.
- **UM a unidad:** se compara sin acentos, en mayúsculas y con los espacios colapsados.

  | UM | Unidad |
  |---|---|
  | PLANTA | plantas |
  | TANCADA | tancadas |
  | HORAS TRACTOR | horas_tractor |
  | HORAS PEON | horas_peon |
  | HECTAREA | hectareas |
  | BINS | bins |
  | BINS C | bins_c |
  | BINS M | bins_m |
  | VIAJES | viajes |
  | NO FACTURABLE, vacía o cualquier otra | Se omite el Comprobante (pregunta 2) |

- **Número**
  - Sólo dígitos, después de recortar.
  - Vacío o "-" cuenta como "sin número": la fila se migra en un Comprobante sin número (ver Agrupado; pregunta 4).
  - Un número compuesto ("`<n> - <m>`", "`F.<n> - NC <m>`") se migra tal cual, con la normalización de la regla 1: las contadoras identificaban así ese detalle (pregunta 3). Si supera los 30 caracteres, se omite su grupo y se lista.
  - Cualquier otro texto también se migra tal cual; sólo `|` lo vuelve ilegible.
- **Resolución contra el maestro**
  - Cliente y tarea por nombre exacto, después de normalizar mayúsculas, espacios y acentos. Incluye los dados de baja, porque el histórico los muestra.
  - No hay ningún parecido de nombres: si no aparece o el nombre es ambiguo, se omite el Comprobante (pregunta 14).
  - Una finca que no se encuentra deja la Línea sin finca y genera un aviso; no frena nada.
- **Agrupado:** por `(cliente_id, número)`, en el orden del CSV.
  - **Sin número** (pregunta 4): por `(cliente_id, FECHA A FACTURAR)`; con el export de hoy, 69 filas dan 14 Comprobantes. Una fila sin número y sin FECHA A FACTURAR se omite y se lista.
  - **Corte**: un grupo sin número con FECHA A FACTURAR hasta el 2026-07-31 cuenta como facturado (se facturó y no se anotó el número); uno posterior queda `pendiente_de_facturar`, por las dudas. Lo decidió el usuario el 2026-10-12: las 58 filas viejas (septiembre de 2025 a febrero de 2026) como facturadas, y las 11 recientes (agosto y septiembre de 2026) como no facturadas. El corte es una constante del servicio, `SIN_NUMERO_FACTURADO_HASTA`.
  - Fecha del Comprobante: la única FECHA FAC no vacía del grupo. Si no hay ninguna, queda NULL; si hay dos distintas, conflicto y se omite el grupo.
  - Tipo: siempre `factura`. Un importe o una cantidad negativos omiten el grupo (pregunta 7).
  - Empresa: NULL.
  - Cantidad 0: se migra tal cual.
  - El importe es el de la planilla, sin recalcular.
- **Todo o nada por Comprobante:** una Línea mala omite su grupo entero, con el motivo de esa Línea, así nunca queda un Comprobante a medias.
- **Desde:** `--desde 2025-04-01`. Un grupo con alguna Línea anterior se omite.
- **Idempotencia** por `clave_identidad` `H|...`:
  - si existe y es igual, no se toca;
  - si existe y cambió (multiconjunto de Líneas o fecha), se informa; con `--reemplazar-cambiados` se reemplazan las Líneas y la fecha, conservando el id y los adjuntos (pregunta 8);
  - si el mismo Cliente y número ya fue cargado a mano, se omite el grupo;
  - un histórico de la base que ya no está en el CSV se informa y no se borra;
  - los sin número (clave `S`) se recalculan en cada corrida con `--aplicar`, sin esperar a `--reemplazar-cambiados`: si una fila ganó número en la planilla, pasa a su Comprobante numerado en la misma corrida y sale del sin número; uno que queda sin filas se borra. Así una fila nunca cuenta dos veces. Uno con Adjuntos no se borra ni se cambia: se informa y la salida no es 0.
- **Conciliación por (Cliente, mes):** el mes es el de FECHA A FACTURAR (pregunta 10).
  - `planilla` = todas las filas con importe legible, desde la fecha de inicio;
  - `sin_numero`, que es parte de lo migrable;
  - `omitido`, abierto por motivo;
  - `pendiente`, la parte de `sin_numero` posterior al corte, sólo informativa;
  - `migrable` = planilla − omitido;
  - `en_base` = suma de los históricos de la base;
  - `diferencia` = migrable − en_base.
- **Salida del script**
  - Por consola: conteos por motivo, nombres de cliente y tarea no resueltos (distintos, con su cantidad) y sólo las celdas con diferencia distinta de 0.
  - `--informe <ruta>` escribe la tabla completa en CSV. Se recomienda dejarla dentro de `fuentes/`, que está fuera de git.
  - **Sale con 0** sólo si no queda nada nuevo, nada cambiado y todas las diferencias son 0.
- **Guarda de escritura**
  - `--aplicar` se permite si la base es `testing`, o si es la de producción **y** `permitir_base_produccion` está activo, es decir, en el VPS. En producción, además, pide tipear el nombre de la base. Cualquier otra base se rechaza.
  - Esto se aparta a propósito del script de tarifas, que sólo escribe en `testing`, porque el histórico tiene que quedar en producción. Va en el cuerpo del PR.
- **La salida tiene nombres de clientes:** nunca se pega en PRs, en la bitácora ni en `estado.md`. En el PR van sólo los conteos y "diferencias: 0".

### 3.2 Contrato de la API

Prefijo `/api/facturacion`, en un router nuevo: `app/modulos/facturacion/api/comprobantes.py`. Todas las rutas son de la pantalla `comprobantes`.

| # | Método y ruta | Nivel | Respuesta |
|---|---|---|---|
| 1 | `GET /comprobantes` | ver | 200 `[ComprobanteFila]` |
| 2 | `GET /comprobantes/{id}` | ver | 200 `ComprobanteDetalle` · 404 |
| 3 | `POST /comprobantes` | editar | 201 `ComprobanteDetalle` · 409 · 422 · 503 |
| 4 | `PUT /comprobantes/{id}` | editar | 200 `ComprobanteDetalle` · 404 · 409 · 422 · 503 |
| 5 | `DELETE /comprobantes/{id}` | editar | 204 · 404 · 409 · 503 (`adjuntos_sin_configurar`, sólo si tiene adjuntos y la carpeta no está configurada: no se borra nada; decisión del usuario en B3, 2026-10-12) |
| 6 | `POST /comprobantes/{id}/adjuntos` (multipart, campo `archivo`) | editar | 201 `Adjunto` · 404 · 409 · 413 · 422 · 503 |
| 7 | `GET /comprobantes/{id}/adjuntos/{adjunto_id}` | ver | 200 el archivo · 404 · 503 |
| 8 | `DELETE /comprobantes/{id}/adjuntos/{adjunto_id}` | editar | 204 · 404 · 503 |
| 9 | `GET /clientes` (sólo activos) | ver | 200 `[{id, nombre}]` · 503 |
| 10 | `GET /clientes/{cliente_id}/fincas` | ver | 200 `[{id, nombre}]` · 503 |
| 11 | `GET /empresas` | ver | 200 `["..."]` · 503 |
| — | `GET /tareas` (lo crea la E2) | ver en `comprobantes` | `[{tarea_id, nombre, grupo_tarea, unidad_sugerida, no_facturable}]` |

**Entrada de POST y PUT:**
```json
{"tipo": "factura", "cliente_id": 12, "empresa_emisora": "TEXTO", "numero": "TEXTO",
 "fecha": "2026-10-05", "factura_corregida_id": null, "actualizado_en": null,
 "lineas": [{"fecha": "2026-09-16", "tarea_id": 7, "unidad": "plantas", "finca_id": null,
             "cantidad": "1234.50", "precio_unitario": "98.1234"}]}
```

**Decimales:**
- Entran como número o como texto con punto decimal.
- Salen como texto (`Decimal`, igual que en Terceros).
- El front convierte el formato argentino antes de mandar.

**`ComprobanteFila`:**
- Campos: `id`, `tipo`, `numero` (o null), `fecha` (o null), `mes`, `cliente_id`, `cliente_nombre`, `empresa_emisora` (o null), `es_historico`, `pendiente_de_facturar`, `cantidad_lineas`, `cantidad_adjuntos`, `total_neto`.
- `mes` es "AAAA-MM" de la primera Línea (pregunta 10).
- `total_neto` va con signo: negativo en una NC.
- Orden: por `fecha` o, si falta, por la fecha de la primera Línea, de la más nueva a la más vieja.

**`ComprobanteDetalle`:** los campos de la fila, más:
- `factura_corregida: {id, numero, fecha}` o null;
- `notas_credito: [{id, numero, fecha}]`;
- `lineas: [{id, orden, fecha, tarea_id, tarea_nombre, unidad, finca_id, finca_nombre, cantidad, precio_unitario, importe}]`, con `importe` positivo (el front lo muestra negativo en una NC);
- `adjuntos: [{id, nombre_original, tipo_contenido, tamano_bytes, subido_en}]`;
- `creado_en`, `actualizado_en`.

**Errores:**

| Código | `detail` |
|---|---|
| 404 | Texto. Excepción: `{tipo: "archivo_no_encontrado", mensaje}` cuando la fila existe y el archivo no, por ejemplo en `testing` |
| 409 | `{tipo: "comprobante_repetido", mensaje, comprobante_id}` |
| 409 | `{tipo: "historico_mismo_numero", mensaje, comprobante_id}` |
| 409 | `{tipo: "historico_no_editable", mensaje}` |
| 409 | `{tipo: "factura_con_notas", mensaje}` (también si la base frena el borrado porque otra persona le cargó una Nota en ese momento) |
| 409 | `{tipo: "comprobante_modificado", mensaje}`: el PUT trae un `actualizado_en` viejo (pregunta 18) |
| 409 | `{tipo: "limite_adjuntos", mensaje}` |
| 422 | `{tipo: "comprobante_invalido", mensaje, campo}` |
| 422 | `{tipo: "linea_invalida", mensaje, fila, campo}`, con `fila` desde 1 |
| 422 | La lista de validación de FastAPI (`mensajeDeError` ya la maneja) |
| 413 | `{tipo: "adjunto_muy_grande", mensaje}` |
| 422 | `{tipo: "adjunto_invalido", mensaje}` |
| 503 | `{tipo: "adjuntos_sin_configurar", mensaje}` |
| 503 | El texto de `ExternaNoDisponible`, que ya maneja `app/main.py` |

### 3.3 Corte en PRs y orden

1. **PR-0, núcleo del front**, sólo si la E1 no lo hace. Se puede hacer ya, en paralelo con BK-A.
2. **BK-A y FT-A, hermanos**: comprobantes, migración 003 con las tres tablas, lecturas del campo, mapa de permisos, listado y alta/edición. El FT-A arranca en paralelo contra el contrato.
3. **BK-B y FT-B, hermanos**: adjuntos. Van después del merge de BK-A.
4. **BK-C, sólo backend**: el histórico. Va después del merge de BK-A y en paralelo con BK-B.
5. **Un solo deploy de toda la E2**, con OK (FRENADOS F4 a F8).
   - **Cambio del 2026-10-12 (decisión del usuario):** Facturación no se deploya al final de la E2 sino cuando el módulo esté terminado entero, con todas sus etapas. Los PRs se siguen mergeando a `main`. Si antes hay que deployar otra cosa, el código de Facturación viaja escondido (nadie tiene su rol, así que no aparece en el menú ni en el Inicio), y ese deploy lleva la 003 a producción (F5), porque crea tablas nuevas y vacías que no tocan nada existente. Se descartó apagar el módulo sólo en producción (trabajo de más) y una rama larga de Facturación fuera de `main` (BK-A y FT-A ya están en `main`, y juntaría choques con el núcleo y con Terceros). F4 a F8 quedan para ese deploy.

Todo arranca de `main` con la E1 mergeada.

### 3.4 PR-0: subir la barra y las tablas al núcleo del front (solo si la E1 no lo hace)

**0.1 Par: mover y parametrizar**
- Archivos:
  - de `src/modulos/preliquidacion/components/` a `src/core/ui/`: `FiltrosBar.jsx`, `TablaOrdenable.jsx` y sus `.module.css`;
  - de `src/modulos/preliquidacion/pages/` a `src/core/ui/`: `opcionesCascada.js` y `ordenarFilas.js`;
  - de `src/modulos/preliquidacion/` a `src/core/`: `estadoPantallas.js`, junto con `pages/estadoGuardado.js`;
  - los imports de `Revision.jsx`, `Verificacion.jsx`, `Gerencial.jsx`, `Conceptos.jsx` y `CategoriasOperarios.jsx`;
  - `package.json`.
- `CAMPOS_LINEAS` y `ALERTAS` pasan de defaults a props: Preliquidación los pasa explícitos.
- Rojo: mover `opcionesCascada.test.js`, `ordenarFilas.test.js` y `estadoGuardado.test.js` a su lugar nuevo, con el glob en `package.json`. Fallan porque los módulos todavía no están ahí.
- Verde: mover los archivos y corregir los imports.
- Verificación:
  - `npm test`, `npm run build` y `npm run lint`, con los mismos 6 errores conocidos de `.claude/hooks`;
  - smoke en el navegador de Revisión, Verificación y Conceptos: filtros, orden y estado al ir y volver.

### 3.5 BK-A: Comprobantes (backend)

**A1. Par: reglas puras**
- Archivos: `app/modulos/facturacion/services/reglas_comprobante.py` y `tests/facturacion/test_reglas_comprobante.py`.
- Rojo (falla con ImportError):
  - `normalizar_numero` (espacios, mayúsculas; rechaza vacío y `|`);
  - `normalizar_empresa`;
  - `clave_identidad`, en sus dos formas, `E` y `H`;
  - `calcular_importe`, con estos casos fijos que reusa el front:

    | Cantidad | Precio | Importe |
    |---|---|---|
    | 3 | 0.005 | 0.02 |
    | 1.5 | 2.3333 | 3.50 |
    | 56710 | 313.56 | 17781987.60 |

  - `total_firmado` (negativo en una NC).
- Verificación: `python -m pytest tests/facturacion/test_reglas_comprobante.py -q`.

**A2. Par: modelo y migración**
- Archivos:
  - `app/modulos/facturacion/models.py` (hoy sin clases): suma `Comprobante`, `LineaComprobante` y `Adjunto`;
  - `migrations/facturacion/003_comprobantes.sql`;
  - `migrations/ORDEN.txt`;
  - `tests/facturacion/test_modelo_comprobantes.py`.
- Rojo (SQLite con `create_all`):
  - un Comprobante con 2 Líneas se lee en el orden de las Líneas;
  - una `clave_identidad` repetida da `IntegrityError`;
  - borrar el Comprobante borra sus Líneas por la cascada de la relación;
  - un `nombre_en_disco` repetido da `IntegrityError`.
- Verde:
  - los modelos;
  - el SQL con encabezado `-- facturacion/003 — ...`, `-- NO DIFERIBLE` y "aplicar una vez por base", más la vuelta atrás comentada (sección 4, riesgo 1);
  - la línea en `ORDEN.txt`.
- Verificación: `python -m pytest tests/facturacion/test_modelo_comprobantes.py tests/core/test_manifiesto_migraciones.py tests/core/test_refrescar_testing.py -q`. Además, controlar que las columnas del SQL y del modelo sean las mismas; el control de verdad es F1.

**A3. Par: lecturas del campo**
- Archivos: `app/modulos/facturacion/services/consulta_externa.py` (E1) y `tests/facturacion/test_consulta_externa_comprobantes.py`.
- Rojo (con `SesionFalsa`, como `tests/terceros/test_consulta_externa.py:25-49`):
  - `clientes()` devuelve `{id, nombre, activo}` y sólo los activos;
  - `clientes(incluir_baja=True)` trae también los de baja, con `activo=False`;
  - `fincas_de_cliente(7)` pasa `cliente_id=7`;
  - `todas_las_fincas()`, para el script, trae `{id, nombre, cliente_id}`;
  - `empresas()` va a la sesión de sueldos, recorta, saca vacíos y ordena;
  - la segunda llamada dentro de los 10 minutos no vuelve a consultar (monkeypatch del reloj).
  - `obtener_tareas()` no trae las tareas dadas de baja: si la E2 las necesita, se suma acá.
- Verde: SQL `text()` con el estilo y el filtro `estado <> 9` de `app/modulos/preliquidacion/services/consulta_externa.py:209-223`, pero con ids. El de empresas copia `preliquidacion.py:120-124`.
- Verificación: correr el archivo de tests. Los datos reales se ven en F1.

**A4. Par: servicio, alta**
- Archivos: `app/modulos/facturacion/services/comprobantes_service.py`, `app/modulos/facturacion/schemas.py` (E1: suma las entradas) y `tests/facturacion/test_comprobantes_service.py`.
- Excepciones del servicio: `ComprobanteNoEncontrado`, `ComprobanteRepetido(comprobante_id)`, `HistoricoMismoNumero(comprobante_id)`, `HistoricoNoEditable`, `FacturaConNotas`, `ComprobanteInvalido(campo)`, `LineaInvalida(fila, campo)`.
- Rojo (SQLite y una consulta falsa con 2 clientes, uno de baja, 3 tareas, una No facturable, y fincas). Los casos son los de la sección 3.1, reglas 1 a 6:
  - copias del maestro, importe calculado y clave `E`;
  - repetido con espacios o minúsculas distintas;
  - mismo número que un histórico;
  - Cliente de baja;
  - tarea inexistente (`fila=2`);
  - unidad fuera de las 9;
  - finca de otro Cliente;
  - cantidad 0 y precio negativo;
  - sin Líneas;
  - tarea No facturable, que se acepta;
  - NC sin Factura, NC que apunta a una NC o a una Factura de otro Cliente, y NC válida con total negativo.
- Verificación: correr el archivo de tests.

**A5. Par: servicio, edición, borrado, listado y detalle**
- Archivos: los mismos que en A4.
- Rojo (sección 3.1, regla 7):
  - el PUT reemplaza las Líneas y sella `actualizado_por`;
  - el PUT o el DELETE de un histórico da 409;
  - una Factura con NC no cambia de Cliente ni de tipo y no se borra;
  - conservar un Cliente de baja se permite;
  - `listar()` trae signo, conteos, `mes` y orden;
  - `detalle()` trae Líneas, `factura_corregida` y `notas_credito`.
- Verificación: correr el archivo de tests.

**A5b. Par: lo que A5 dejó a la vista (agregado en la ejecución)**
- Archivos: los mismos que en A4 y A5.
- Rojo:
  - el PUT con un `actualizado_en` distinto del de la base da `ComprobanteModificado` (409 `comprobante_modificado`) y no toca nada; con el mismo, o null en uno nunca editado, pasa; en el alta el campo se ignora;
  - una Línea cuya tarea pasó a baja se conserva al editar si esa tarea ya estaba en el Comprobante; una tarea de baja nueva da `linea_invalida`;
  - si la base frena el DELETE de una Factura por una Nota cargada en ese momento (`IntegrityError`), sale `FacturaConNotas`, no un 500 (el test simula el `IntegrityError`).
- Verificación: `python -m pytest tests/facturacion -q`.

**A6. Par: router y mapa de permisos**
- Archivos:
  - `app/modulos/facturacion/api/comprobantes.py`;
  - `app/modulos/facturacion/__init__.py` (`routers` pasa de `()` al router nuevo);
  - `app/modulos/facturacion/permisos.py` (E1: `ver_comprobantes` y `editar_comprobantes` si no están; zona sensible);
  - `app/modulos/facturacion/schemas.py` (salidas);
  - `tests/facturacion/test_mapa_permisos.py` (hoy con `ESPERADO` vacío: suma las filas 1 a 5, 9 a 11 y la de `GET /tareas`, y el conteo pasa de 0 a 9);
  - `tests/facturacion/test_api_comprobantes.py`.
- Se crea `GET /api/facturacion/tareas` con Ver en `comprobantes`, sobre `obtener_tareas()` de la `consulta_externa`, con su fila en el mapa.
- Rojo:
  - el mapa con las filas sin ruta;
  - la API con servicio falso (como `tests/terceros/test_api_terceros.py`): 201 con cuerpo; cada excepción da su código y su `detail` del contrato; quien sólo ve recibe 403 en las escrituras y 200 en los GET; quien no tiene la pantalla recibe 403.
- Verificación: `python -m pytest tests/facturacion tests/core/test_endpoints_con_permiso.py tests/core/test_arquitectura.py -q`.

**A7. Paso: suite completa**
- `python -m pytest -q`, con los números en el reporte.
- Después, **F1**: el DDL en `testing`, y el backend de la rama arrancando con "verificadas".

**R1. Par: dos guardados a la vez no mezclan las Líneas (revisión de BK-A, urgent)**
- Hallazgo: `editar` lee la fila sin bloquearla y el UPDATE no depende del `actualizado_en` que se comparó. Entre la comparación y el commit se consulta el campo (`obtener_tareas()` no tiene caché), así que la ventana dura lo que tarde esa base.
- Escenario de falla: A y B abren el mismo Comprobante y guardan casi a la vez. Las dos pasan la comparación. B borra por id las Líneas que leyó, que A ya reemplazó (borra 0), y suma las suyas: el Comprobante queda con las Líneas de A y las de B, con el total inflado, y sin ningún 409.
- Arreglo: justo antes de reemplazar las Líneas, un UPDATE de la cabecera condicionado a `id` y al `actualizado_en` leído (null-safe: un Comprobante nunca editado tiene null). Si no afecta exactamente 1 fila, `ComprobanteModificado` y rollback. En MySQL el UPDATE toma el lock de la fila y evalúa contra el último valor confirmado, así que el segundo guardado espera al primero y recibe el 409. La comparación del principio se queda, para cortar antes sin consultar el campo.
- Archivos: `app/modulos/facturacion/services/comprobantes_service.py` y `tests/facturacion/test_comprobantes_service.py`.
- Rojo: el guardado de A se intercala dentro de la consulta de tareas de B (monkeypatch, como en A4); B tiene que recibir `ComprobanteModificado` y el Comprobante quedar exactamente con las Líneas de A.
- Verificación: `python -m pytest tests/facturacion -q`.

**R2. Par: una finca dada de baja no traba la edición (revisión de BK-A, high)**
- Hallazgo: la regla 7 conserva el Cliente y la tarea de baja, pero no la finca. Las fincas de un Cliente se leen sin las de baja.
- Escenario de falla: un Comprobante tiene una Línea con una finca que después se dio de baja en el campo. Al corregir sólo el número, esa Línea da `linea_invalida` ("Esa finca no es del Cliente") y la única salida es quitarle la finca.
- Arreglo: igual que `tareas_previas`. Si el Cliente no cambia, las fincas que ya tenían las Líneas del Comprobante se aceptan aunque el campo ya no las liste. Su nombre es el que estaba guardado. Una finca de baja nueva sigue dando `linea_invalida`.
- Archivos: `app/modulos/facturacion/services/comprobantes_service.py` y `tests/facturacion/test_comprobantes_service.py`.
- Rojo: editar un Comprobante cuya finca ya no figura en las fincas del Cliente, conservando esa Línea, pasa; una finca de baja que el Comprobante no tenía da `linea_invalida` (una finca previa se acepta en cualquier Línea, como las tareas: el PUT no distingue Líneas viejas de nuevas); cambiar de Cliente con esa finca da `linea_invalida`.
- Verificación: `python -m pytest tests/facturacion -q`.

**R3. Par: Facturas y Notas de crédito numeran aparte (decisión del usuario en la revisión de BK-A)**
- Pregunta que abrió la revisión: con la clave `E|<empresa>|<numero>`, una Nota de crédito con el mismo número que una Factura de la misma Empresa daba 409 `comprobante_repetido`. El usuario confirmó que numeran aparte (2026-10-12).
- Cambio:
  - la clave de un Comprobante cargado a mano pasa a `E|<empresa>|<tipo>|<numero>`, con el tipo tal cual (`factura` o `nota_credito`). Las formas `H` y `S` no cambian: los históricos son siempre Facturas. El largo entra en la columna (2 + 100 + 1 + 12 + 1 + 30 < 160);
  - `historico_mismo_numero` se controla sólo en una Factura;
  - el comentario de la `003_comprobantes.sql` y la docstring de `clave_identidad` se actualizan. La 003 todavía no está en producción y en `testing` sus tablas están vacías: el DDL no cambia, sólo el comentario.
- Archivos: `app/modulos/facturacion/services/reglas_comprobante.py`, `app/modulos/facturacion/services/comprobantes_service.py`, `migrations/facturacion/003_comprobantes.sql` (sólo el comentario), `tests/facturacion/test_reglas_comprobante.py` y `tests/facturacion/test_comprobantes_service.py`.
- Rojo:
  - la clave manual incluye el tipo, y un tipo que no sea `factura` ni `nota_credito` da `ValueError`;
  - una Nota de crédito con el mismo número y la misma Empresa que una Factura se da de alta;
  - dos Facturas, o dos Notas, con el mismo número y la misma Empresa siguen dando `ComprobanteRepetido`;
  - una Nota de crédito con el número de un histórico del mismo Cliente se da de alta, y una Factura sigue dando `HistoricoMismoNumero`;
  - al editar, pasar una Factura a Nota de crédito con un número que ya tiene otra Nota de la misma Empresa da `ComprobanteRepetido`.
- Verificación: `python -m pytest tests/facturacion -q`.

**R4. Par: una Nota cargada a la vez no queda colgada de algo que ya no es Factura (segunda ronda de revisión de BK-A, high)**
- Hallazgo: la regla 7 (una Factura con Notas no cambia de Cliente ni de tipo) y la regla 5 (la Nota apunta a una Factura del mismo Cliente) se controlan con lecturas sin bloqueo. Crear una Nota no cambia el `actualizado_en` de la Factura, así que el UPDATE condicionado de R1 no lo ve.
- Escenario de falla: A pasa la Factura F a Nota de crédito, o a otro Cliente. Al mismo tiempo, B carga la Nota N sobre F. Las dos pasan sus controles. N queda corrigiendo algo que ya no es Factura, o una Factura de otro Cliente. Ningún importe sale mal, pero el vínculo queda inválido y N da 422 al editarla.
- Arreglo (el mínimo del verificador, los dos lados):
  1. En `editar`, si cambian el tipo o el Cliente, después del UPDATE condicionado se repite `_tiene_notas` con lectura bloqueante (`with_for_update(read=True)`). Si hay Notas, `FacturaConNotas` y rollback.
  2. En `_validar_factura_corregida`, la Factura se lee con `with_for_update(read=True)`.
  - En MySQL, el que llega segundo espera al primero y ve lo que confirmó. En SQLite no hay bloqueo: el test prueba el orden, no la espera.
- Archivos: `app/modulos/facturacion/services/comprobantes_service.py` y `tests/facturacion/test_comprobantes_service.py`.
- Rojo, con dos sesiones (como el fixture `dos_sesiones` de R1):
  - la Nota de B se confirma después del primer `_tiene_notas` de A y antes de su UPDATE (monkeypatch dentro de la consulta de tareas de A); A tiene que recibir `FacturaConNotas`, y F seguir siendo Factura del mismo Cliente;
  - lo mismo cuando A cambia de Cliente.
- Verificación: `python -m pytest tests/facturacion -q`. Sin tercera ronda de revisión: la regla es dos como máximo.

### 3.6 FT-A: listado y alta/edición (front)

**FA0. Paso: arrancar `impeccable`**
- `impeccable context --target src/modulos/facturacion/pages/Comprobantes.jsx`.
- Después `reference/new-work.md` (superficie nueva sobre el mundo existente) y leer `reference/craft-floor.md` antes de editar.
- El brief ya está hecho: `docs/modulos/facturacion/pantallas.md` del backend.

**FA1. Par: números**
- Archivos: `src/modulos/facturacion/numeros.js`, `numeros.test.js` y `package.json` (glob `src/modulos/facturacion/*.test.js` si la E1 no lo sumó).
- Rojo:
  - `leerNumero` lee es-AR y devuelve texto con punto decimal, o null. Casos:

    | Entrada | Salida |
    |---|---|
    | "1.234,56" | "1234.56" |
    | "1.500" | "1500" |
    | "12,5" | "12.5" |
    | "$ 1.234,56" | "1234.56" |
    | "abc" | null |

  - `importeDeLinea` con BigInt en centavos y ROUND_HALF_UP, con los mismos casos de A1;
  - `formatoPesos` (es-AR, con signo).
- Verificación: `npm test`.

**FA2. Par: reglas de la grilla**
- Archivos: `src/modulos/facturacion/lineas.js` y su test.
- Rojo:
  - `validarLinea` (los mismos casos que el backend, con mensajes en español);
  - `unidadAlElegirTarea` precarga la Unidad sugerida sólo si la unidad no se tocó, y una tarea sin sugerida deja la unidad vacía;
  - `avisoDeLinea` avisa si la tarea es No facturable;
  - `totalFirmado`.
- Verificación: `npm test`.

**FA3. Par: filas del listado**
- Archivos: `src/modulos/facturacion/listado.js` y su test.
- Rojo:
  - campos para la barra común: Cliente, Empresa emisora ("Sin empresa" en un histórico), Tipo, Mes ("ago 2025") y Adjunto;
  - "Sin adjunto" excluye a los históricos, que no generan la Alerta;
  - un histórico sin número muestra "Sin número" en la columna del número, y uno `pendiente_de_facturar` lleva además la etiqueta "Pendiente de facturar";
  - la búsqueda funciona por número y por Cliente.
- Verificación: `npm test`.

**FA3b. Par: el filtro Mes en orden de fecha (agregado por la sesión principal al cerrar FA3)**
- Hallazgo: `opcionesCascada` del núcleo ordena las opciones como texto, así que el filtro Mes queda "abr 2026, ago 2025, …" en lugar de por fecha. `FiltrosBar` hace lo mismo con los valores elegidos que ya no tienen opción.
- Archivos: `src/core/ui/opcionesCascada.js` y su test, `src/core/ui/FiltrosBar.jsx`, y `src/modulos/facturacion/listado.js` y su test.
- Rojo:
  - un campo puede traer un `orden` opcional (un comparador de valores); sin él, el orden sigue siendo el de hoy, y Preliquidación no cambia;
  - el campo Mes de `CAMPOS_COMPROBANTES` trae un `orden` del más nuevo al más viejo.
- Verificación: `npm test` (incluye los tests del núcleo).

**FA4. Paso: servicio y rutas**
- `src/modulos/facturacion/services/comprobantes.js`, con todo por `src/core/api.js`.
- `rutas.jsx` (E1):
  - `/facturacion/comprobantes`, con `menu: true` si la E1 no la tiene;
  - `/facturacion/comprobantes/nuevo` y `/facturacion/comprobantes/:id`, con `menu: false` y `pantalla: 'comprobantes'`;
  - las `pantallas` del asistente, incluido `'/facturacion/comprobantes/*'`.
- Verificación: `npm run build` y `npm run lint`.

**FA5. Paso visual: listado `pages/Comprobantes.jsx`**
- La barra común y `TablaOrdenable` (PR-0). La barra recibe `campos`, `alertas` (la de "Sin adjunto") y su propio `placeholderBusqueda` (por número o Cliente): sin él, muestra el texto por defecto de Preliquidación (revisión del PR-0).
- Marca "Histórico"; NC en negativo.
- "Nuevo comprobante" sólo si `puedeEditar(usuario, 'facturacion', 'comprobantes')`.
- Filtros guardados con `useEstadoPantalla('facturacion.comprobantes.filtros', {})`.
- Verificación en el navegador, contra BK-A en `testing`: filtros, orden, y que un rol de sólo Ver no tenga el botón.

**FA6. Paso visual: `pages/Comprobante.jsx` y `components/GrillaLineas.jsx`**
- Cabecera:
  - Cliente, sólo activos; un Cliente de baja ya guardado se muestra igual;
  - Empresa, Tipo, Número y Fecha;
  - en una NC, la Factura corregida, elegida entre las Facturas de ese Cliente que ya trae el listado.
- Grilla:
  - recorrible con Tab: fecha, tarea con autocompletar entre las ~135, unidad precargada, finca del Cliente, cantidad, precio, importe calculado;
  - agregar y quitar filas, y el total;
  - si conviene, que la fecha copie la de la fila anterior (lo decide `shape`).
- Guardar con `useMutation`: el overlay es global y hay toasts.
- Ante `comprobante_repetido` o `historico_mismo_numero`, aviso con enlace al existente.
- Ante `linea_invalida`, se marca la fila.
- El PUT reenvía `actualizado_en` tal cual lo trajo el detalle (texto, sin zona horaria). Ante `comprobante_modificado`, aviso de que otra persona lo cambió y opción de volver a abrirlo.
- `CargandoContenido` mientras cargan clientes, tareas, fincas y empresas.
- Un histórico, o alguien sin Editar, ven todo en sólo lectura.
- Borrar pide confirmación. En `nuevo` sin Editar, se vuelve al listado.
- Verificación en el navegador:
  - una Factura con 3 Líneas;
  - una NC que la corrige;
  - un número repetido;
  - edición y borrado;
  - un rol de sólo Ver.
  - Además, `npm run build` y `npm run lint`.

**FA7. Paso: revisión visual (fase 4)**
- `/impeccable critique` y `/impeccable audit` sobre las dos pantallas.

**Revisión de FT-A (sesión principal, 2026-10-12): 0 urgent, 3 high, 14 minor.** Los high se arreglan en RA1 a RA3. Además, por la regla 4 de GUIA-MODULOS §4.1, lo del núcleo de FA3b (`opcionesCascada.js`, su test y `FiltrosBar.jsx`) va en un PR aparte y chico, que se mergea antes que el de FT-A. Sin ese PR, el `orden` de `listado.js` se ignora y nada se rompe.

**RA1. Par: quitar una línea se puede deshacer (revisión de FT-A, high)**
- Hallazgo: el botón Quitar borra la fila sin confirmación ni deshacer (`components/GrillaLineas.jsx`, `pages/Comprobante.jsx`, `quitarFila`).
- Escenario de falla: después del precio, Tab lleva a Quitar (el importe no recibe foco). Un Enter borra la línea; el foco pasa al Quitar de la fila vecina y otro Enter borra esa también. Se puede guardar con líneas de menos.
- Arreglo: el quitar y el restaurar pasan a funciones puras de `formulario.js`. En `quitarFila`, si la fila no está vacía, un toast "Se quitó la línea N" con un botón Deshacer que la devuelve a su mismo lugar. Una fila vacía se quita sin toast.
- Archivos: `src/modulos/facturacion/formulario.js` y su test, y `src/modulos/facturacion/pages/Comprobante.jsx`.
- Rojo: quitar la fila del índice i y restaurarla la deja en el índice i con los mismos datos, también cuando se quitó la última o la primera.
- Verificación: `npm test`; el toast con Deshacer, en el navegador.

**RA2. Paso visual: avisar antes de perder lo cargado (revisión de FT-A, high)**
- Hallazgo: al salir sin guardar se pierde todo sin aviso. La marca "Hay cambios sin guardar" no aparece en el alta (`Comprobante.jsx`, condición `!esNuevo`) y no hay `beforeunload`.
- Escenario de falla: en un alta se cargan 12 líneas y se toca "← Comprobantes" o se cierra la pestaña: se pierde todo.
- Arreglo: la marca también en el alta; `beforeunload` mientras haya cambios sin guardar; el enlace "← Comprobantes" pide confirmación si hay cambios (patrón de `src/core/administracion/ListaRoles.jsx`). El menú lateral no se puede frenar con `BrowserRouter` sin tocar el núcleo: queda como límite, anotado en el PR.
- Archivos: `src/modulos/facturacion/pages/Comprobante.jsx`.
- Verificación: en el navegador, y `npm run build`.

**RA3. Paso visual: el Tipo se lee completo (revisión de FT-A, high)**
- Hallazgo: a 1280 px el segmentado del Tipo se corta ("Nota de crédi", "actura"): columna `auto` de la cabecera, `min-width: 0` en el fieldset y `overflow: hidden` en `.segmentado` (`pages/Comprobante.module.css`).
- Arreglo: que la columna del Tipo tome el ancho de su contenido (`max-content`, o una clase propia del fieldset sin `min-width: 0`), ajustando los mínimos de las otras para que la cabecera siga entrando a 1280 px.
- Archivos: `src/modulos/facturacion/pages/Comprobante.module.css`.
- Verificación: en el navegador a 1280 px, y `npm run build`.

**RA4. Paso: la pantalla no queda en blanco si una lectura no trae datos (visto en el smoke de RA1 a RA3, high)**
- Hallazgo: `Comprobante` (export por defecto de `pages/Comprobante.jsx`) espera con `isLoading` y frena con `isError && !data`. Una consulta en pausa o cancelada sin datos queda en `pending` sin buscar: `isLoading` y `isError` dan falso, y `Formulario` recibe `tareas` (o `clientes`, `empresas`) `undefined` y revienta en `tareas.map`.
- Escenario de falla: visto en el navegador al reiniciar el backend con la pantalla de alta abierta (`TypeError: Cannot read properties of undefined (reading 'map')`, pantalla en blanco). También puede pasar si se corta la red al abrir la pantalla (React Query pausa las consultas sin conexión).
- Arreglo: esperar con `isPending` (no hay datos todavía) en lugar de `isLoading`, para las lecturas del campo y para el detalle; el aviso de error sigue igual.
- Archivos: `src/modulos/facturacion/pages/Comprobante.jsx`.
- Verificación: `npm run build`; en el navegador, abrir el alta con el backend apagado y volver a prenderlo: se ve el aviso o el "Leyendo…", nunca la pantalla en blanco.

### 3.7 BK-B: Adjuntos (backend)

**B1. Par: tipo por contenido**
- Archivos: `app/modulos/facturacion/services/adjuntos_service.py` y `tests/facturacion/test_adjuntos.py`.
- Rojo:
  - se aceptan las tres firmas;
  - se rechazan texto, HTML, SVG y ZIP;
  - se rechaza un `.pdf` que contiene un PNG;
  - `.PDF` y `.jpeg` sirven;
  - `.svg`, `.heic` y `.exe` no.
- Verificación: `python -m pytest tests/facturacion/test_adjuntos.py -q`.

**B2. Par: carpeta**
- Archivos: `app/modulos/facturacion/config.py` y el mismo archivo de tests.
- Rojo (monkeypatch de la configuración):
  - vacía, inexistente o dentro del repo da `AdjuntosSinConfigurar`, con un mensaje distinto en cada caso;
  - `tmp_path` sirve.
- Verificación: correr el archivo de tests.

**B3. Par: subir, abrir y quitar**
- Rojo (SQLite y `tmp_path`):
  - subir guarda el archivo con el nombre `uuid` y su extensión, y la fila con el nombre saneado (`../../x.pdf` queda `x.pdf`);
  - el 6.º adjunto da `LimiteAdjuntos`;
  - más de 10 MB da `AdjuntoMuyGrande`, sin dejar archivo;
  - un contenido inválido no deja archivo;
  - un commit fallido (monkeypatch) no deja archivo;
  - abrir algo de otro Comprobante da "no encontrado";
  - un archivo faltante da `ArchivoNoEncontrado`;
  - un `nombre_en_disco` alterado a `../x` se rechaza;
  - quitar tolera que el archivo falte;
  - `ComprobantesService.borrar()` borra los adjuntos.
- Verificación: correr el archivo de tests.

**B4. Par: endpoints de adjuntos**
- Archivos: `api/comprobantes.py`, `test_api_comprobantes.py` y `test_mapa_permisos.py` (filas 6 a 8; el conteo sube 3).
- Rojo:
  - multipart con `TestClient`: 201, 413, 422, 409 y 503;
  - el GET devuelve los bytes con su `Content-Type`, `nosniff` y `filename*`;
  - quien sólo ve puede hacer GET pero no POST ni DELETE.
- Verificación: `python -m pytest tests/facturacion -q`.

**B5. Paso: configuración y documentación**
- `.env.example`: una sección "Módulo Facturación" con `FACTURACION_ADJUNTOS_DIR=`. Explica que es una ruta absoluta fuera del código y que, vacía, los adjuntos responden 503.
- `deploy/nginx-preliquidacion.conf`: `client_max_body_size 12m;` dentro de `location /api/`, con el porqué: 10 MB más el margen del multipart.
- `docs/modulos/PUESTA-A-PUNTO.md`: crear una carpeta local fuera del repo y apuntar la variable.
- Si `docs/DOCUMENTACION.md` lista las variables, se suma esta.
- Verificación: `python -m pytest -q` completo.

**Revisión de BK-B, ronda 1 (sesión principal, 2026-10-13):** 0 urgent, 1 high, 13 minor (van al PR), 6 descartados.

**RB1. Par: el límite de 5 con dos subidas a la vez (high)**
- Hallazgo: en `AdjuntosService.subir` el conteo de adjuntos es una lectura sin bloqueo. `get_usuario_actual` usa la misma sesión del request y, cuando vence su caché de 60 s, su SELECT fija la foto de REPEATABLE READ (MySQL) antes del `FOR UPDATE` del Comprobante.
- Escenario: un Comprobante con 4 adjuntos; A y B suben a la vez con la caché vencida. B espera el bloqueo, A commitea, el `count` de B lee la foto vieja (4), pasa, y quedan 6.
- Arreglo mínimo: el conteo con lectura bloqueante (`.with_for_update()`, que lee lo último commiteado), manteniendo antes el bloqueo del Comprobante. Archivos: `app/modulos/facturacion/services/adjuntos_service.py` y `tests/facturacion/test_adjuntos.py`. SQLite no reproduce la carrera: el test controla que el conteo pide la lectura bloqueante.
- Ajuste del ejecutor, aceptado: el conteo bloqueante solo deja un deadlock posible en MySQL contra `quitar` y `ComprobantesService.borrar`, que bloquean en otro orden. Por eso las tres escrituras sobre los adjuntos de un Comprobante toman el mismo orden: primero el Comprobante (`with_for_update()`), después sus adjuntos. `quitar` bloquea el Comprobante antes de borrar la fila; `borrar` toma el Comprobante con `with_for_update()` y lee sus adjuntos con lectura bloqueante (si no, podría no ver uno recién subido y chocar con la FK). Suma `app/modulos/facturacion/services/comprobantes_service.py`. Se descartó cerrar la transacción antes del bloqueo con un `rollback()`: no agrega bloqueos, pero el porqué no se ve en el código.
- Verificación: `python -m pytest tests/facturacion -q`.

### 3.8 FT-B: Adjuntos (front)

**FB1. Par: reglas de adjuntos**
- Archivos: `src/modulos/facturacion/adjuntos.js` y su test.
- Rojo:
  - `validarArchivo(file, cantidad)`: extensión, menos de 10 MB y menos de 5 adjuntos, con mensajes en español;
  - `mensajeDeAdjunto(error)` por `status` (403, 404, 413, 503 y otro), porque el `detail` de un blob no se puede leer.
- Verificación: `npm test`.

**FB2. Paso visual: `components/Adjuntos.jsx` en el detalle**
- La lista, "Subir" (`accept=".pdf,.png,.jpg,.jpeg"`), "Ver" (pestaña nueva y revocar la URL al rato) y "Quitar" con confirmación.
- Quien sólo ve tiene la lista y "Ver".
- Servicio:
  - `subirAdjunto` con FormData, como en Terceros;
  - `verAdjunto` como blob;
  - `quitarAdjunto`.
- Verificación en el navegador:
  - un PDF, un PNG y un JPG;
  - un `.pdf` falso;
  - el 6.º archivo;
  - un archivo de más de 10 MB;
  - ver y quitar;
  - un rol de sólo Ver.

**FB3. Paso: revisión visual**
- `/impeccable critique` y `/impeccable audit` del detalle con adjuntos.

### 3.9 BK-C: Histórico (backend)

**C1. Par: lectura**
- Archivos: `app/modulos/facturacion/services/historico.py` y `tests/facturacion/test_historico.py`. Datos inventados: "CLIENTE UNO", "TAREA A".
- Rojo:
  - `leer_numero_ar`, con los casos de la sección 3.1 más "-" y "#VALUE!";
  - `leer_fecha`, con `d/m/aa`, inválida y vacía;
  - `leer_planilla` en un `tmp_path` con BOM, CRLF y `;`;
  - un encabezado faltante da un error que lo nombra.
- Verificación: `python -m pytest tests/facturacion/test_historico.py -q`.

**C2. Par: UM y número**
- Rojo:
  - la tabla de UM de la sección 3.1, con acentos y espacios;
  - el número: dígitos, vacío o "-" (sin número), y los compuestos tal cual.
- Verificación: correr el archivo de tests.

**C3. Par: clasificación y agrupado**
- Funciones puras con un `Maestros` falso.
- Rojo, cada regla de la sección 3.1:
  - el agrupado, y el mismo número con dos Clientes;
  - el sin número: por Cliente y FECHA A FACTURAR, el corte (el 2026-07-31 cuenta como facturado, el 2026-08-01 queda pendiente) y la fila sin FECHA A FACTURAR que se omite;
  - la fecha única, vacía o en conflicto;
  - el todo o nada, por UM no traducible, importe ilegible, valor negativo, tarea o Cliente no resueltos o Cliente ambiguo;
  - la fecha de inicio;
  - la finca no encontrada, que da aviso;
  - la cantidad 0.
- Verificación: correr el archivo de tests.

**C4. Par: aplicar**
- Rojo (SQLite):
  - la primera corrida crea N Comprobantes con `es_historico`, Empresa NULL y clave `H`;
  - la segunda crea 0;
  - un Comprobante que cambió se informa, y con el flag se reemplaza manteniendo el id y los adjuntos;
  - si existe uno cargado a mano, se omite;
  - un histórico que salió del CSV se informa y no se borra;
  - una fila sin número que gana número pasa a su Comprobante numerado en la misma corrida, y el sin número vacío se borra; uno con Adjuntos se informa y no se toca.
- Verificación: correr el archivo de tests.

**C5. Par: conciliación**
- Rojo:
  - planilla = migrable + omitido, en cada Cliente y mes, con el sin número dentro de lo migrable;
  - después de aplicar, todas las diferencias dan 0 y `codigo_de_salida()` da 0;
  - si se borra un Comprobante de la base, aparece la diferencia y la salida da 1.
- Verificación: correr el archivo de tests.

**C6. Par: script y guarda**
- Archivos: `scripts/migrar_historico_facturacion.py` y `tests/facturacion/test_script_historico.py`.
- Rojo:
  - `puede_aplicar(base, permitir)` en los cuatro casos de la sección 3.1;
  - un CSV faltante da un mensaje que nombra `fuentes/` y sale con 1;
  - la simulación no escribe (filas antes y después);
  - `--informe` escribe la tabla completa.
- Verificación: `python -m pytest tests/facturacion -q`, y después `python -m pytest -q`.

**C7. Paso con el usuario: simulación real contra `testing`, sin escribir**
- Correrlo con el CSV local, sin `--aplicar`.
- Revisar con el usuario los conteos por motivo y lo no resuelto, en la consola, sin que nada vaya a git.
- Si el usuario corrige la planilla, vuelve a exportar y se repite.
- Después viene **F3**.

### 3.10 Pasos FRENADOS (los hace la sesión principal, con OK del usuario)

- **F1. DDL en `testing`** (BK-A):
  - script con `assert database == "testing"`;
  - antes, `SHOW TABLES LIKE 'facturacion\_comprobante'`, y lo mismo con las otras dos, tiene que dar vacío;
  - se aplica la 003 y sólo se tocan esas tablas;
  - después, el backend de la rama arranca con "Tablas y columnas BD propia: verificadas".
- **F2. Carpeta de adjuntos local** fuera del repo, con la variable en el `.env` de la máquina del smoke. No se copia el `.env` real al worktree.
- **F3. Histórico en `testing`**:
  - correr con `--aplicar` después de C7;
  - volver a simular: tiene que salir con 0;
  - el usuario revisa el informe.
- **F4. VPS, antes del deploy**:
  - carpeta de adjuntos fuera de la del código, del usuario `deploy` y con permisos 750;
  - la variable en el `.env` del VPS;
  - `client_max_body_size` en la configuración de nginx del VPS, con `nginx -t` y recarga;
  - **definir el respaldo de la carpeta** (pendiente del ADR-0019);
  - todo anotado en `docs/DEPLOY.md`.
- **F5. Producción**:
  - **respaldo de la base** antes del DDL;
  - aplicar la 003;
  - verificar que existan las tablas;
  - la vuelta atrás está escrita (sección 4, riesgo 1).
- **F6. Deploy** del backend y del front (swap de carpeta).
- **F7. Histórico en producción**:
  - el CSV por scp a una ruta fuera del código;
  - simular, revisar con el usuario, `--aplicar` tipeando el nombre de la base y volver a simular, que tiene que salir con 0;
  - **borrar el CSV del VPS**.
- **F8. Smoke en producción**:
  - el listado carga y un histórico abre en sólo lectura;
  - el primer adjunto real lo sube el usuario.

### 3.11 Antes de cada PR

- `python -m pytest -q`, `npm test`, `npm run build` y `npm run lint`.
- BK-A tiene dos rondas de revisión (migraciones, modelos y permisos). Para BK-B recomiendo también dos, porque recibe archivos de usuarios.
- Cuerpos de PR con el porqué:
  - la clave de identidad;
  - el todo o nada;
  - la guarda que admite producción;
  - la consulta de empresas copiada;
  - sin nombres de clientes.

## 4. Riesgos

1. **DDL en producción (alto).**
   - Respaldo de la base antes de F5.
   - Vuelta atrás del código: el commit anterior. Las tablas nuevas no molestan al código viejo.
   - Vuelta atrás de la base, sólo si no hay datos reales: `DROP TABLE facturacion_adjunto; DROP TABLE facturacion_linea; DROP TABLE facturacion_comprobante;`, en ese orden.
   - Con datos reales: restaurar el respaldo.
2. **Carga del histórico en producción (alto).** Escribe dato real en lote.
   - Mitigación: simulación revisada, `--aplicar` con confirmación tipeada y una segunda simulación que sale con 0.
   - Vuelta atrás, justo después de la carga: `DELETE FROM facturacion_comprobante WHERE es_historico = 1;`. Las Líneas caen por cascada, y si algún histórico ya tiene adjunto la FK lo frena, a propósito.
3. **Datos de terceros.**
   - El CSV y la salida del script tienen nombres.
   - El CSV sólo vive en `fuentes/` (ignorado) y en el VPS durante F7, y se borra después.
   - Los tests usan datos inventados.
   - En los PR y en la bitácora van sólo conteos.
4. **Archivos subidos: XSS, falsificación de tipo, path traversal.**
   - Tipo detectado por firma y `Content-Type` propio.
   - Sin SVG, con `nosniff`.
   - Nombre en disco generado y control de que la ruta quede dentro de la carpeta.
   - Tests en B1 a B3.
5. **Adjuntos sin respaldo.**
   - Perder el disco del VPS es perder los PDFs (ADR-0019).
   - Mitigación: F4 define el respaldo antes de habilitar la carga en producción. Si el usuario decide seguir sin él, que quede dicho en `docs/DEPLOY.md`.
6. **nginx 413 en HTML.**
   - Mitigación: F4, el control de tamaño en el front (FB1) y el mensaje por `status`.
7. **Contar dos veces** mientras la planilla siga viva:
   - el 409 `historico_mismo_numero`;
   - el script omite los cargados a mano;
   - la pregunta 13.
8. **La planilla cambia entre corridas.**
   - Los cambiados se informan y sólo se reemplazan con el flag.
   - Lo que sale de la planilla se informa y no se borra.
9. **La base de campo es lenta o se cae.**
   - Caché de 10 minutos.
   - El listado y el detalle no dependen de ella.
   - Las escrituras dan 503 con mensaje.
10. **Cosas de la planilla que la E3 va a ver.**
    - Hay UM que no coinciden con la tarea, por ejemplo una tarea "HORAS" con UM PLANTA.
    - Hay importes distintos de cantidad por precio.
    - El histórico respeta la planilla, así que el Cruce de esos meses puede diferir del Power BI, que usa el grupo de la tarea. A la E3 le toca listarlos con una consulta.
11. **Mover la barra común (PR-0) toca pantallas en producción.**
    - Mitigación: sus tests se mudan con ella y hay smoke de las tres pantallas.
12. **Suite en el worktree.**
    - `settings = Settings()` exige variables al importar y `tests/conftest.py` no carga ninguna.
    - Hay que confirmar cómo se corre sin el `.env` real; por ejemplo, con variables ficticias en la sesión.
13. **Disco.** Lo esperable son cientos de MB por año; el peor caso son 50 MB por Comprobante. Mirar el espacio libre en F4.

## 5. Preguntas abiertas (con lo que asumo si nadie contesta)

1. **¿El export tiene toda la hoja desde abril de 2025?** Son 990 filas contra las ~1,9 mil de `origenes.md`.
   - **Cerrada (2026-10-11):** el usuario lo exportó completo, sin filtros. La aceptación se mide contra estas 990 filas; el número de `origenes.md` queda viejo.
2. **UM "NO FACTURABLE" (1 fila, de cosecha y con importe) y UM vacía (1 fila, cuya tarea tampoco está en el maestro).**
   - Recomiendo omitir su Comprobante, listarlo y que el usuario ponga la UM real en la planilla.
   - Descarto usar la Unidad sugerida, porque adivina.
   - **Cerrada:** omitir y listar.
3. **FACT N° compuesto (12 filas).** ¿Qué significa "`<n> - <m>`"?
   - Supuesto: se omiten y se listan, y el usuario corrige la planilla.
   - Alternativa: migrar el texto tal cual como número.
   - **Cerrada (2026-10-12):** se migran tal cual. Las contadoras identificaban con esos dos números ese detalle. Son 11 filas.
4. **Filas sin número.**
   - Recomiendo no migrarlas: no son Comprobantes, e inventarles un número duplicaría el real.
   - Se informan aparte por Cliente y mes, y entran solas en la corrida en que la planilla tenga el número.
   - **Cerrada (2026-10-12), distinta de lo recomendado:** se migran todas, tengan o no número. Son 69 filas de 5 Clientes. Se agrupan en un Comprobante sin número por Cliente y FECHA A FACTURAR (14 con el export de hoy); cuando la planilla tenga el número, la corrida siguiente las pasa al Comprobante numerado. Las de FECHA A FACTURAR hasta el 2026-07-31 cuentan como facturadas; las posteriores, como pendientes de facturar, por las dudas. Ver sección 3.1, "Agrupado".
5. **Tarea No facturable en una Línea cargada a mano.**
   - Supuesto: se permite, con un aviso en la fila. Lo emitido se registra tal cual.
   - **Cerrada:** queda el supuesto.
6. **Históricos de sólo lectura, salvo los adjuntos.**
   - Supuesto: sí. La idempotencia depende de que no cambien.
   - **Cerrada:** queda el supuesto.
7. **Notas de crédito en la planilla.** No hay negativos ni columna de tipo.
   - Supuesto: todo histórico entra como Factura, y un negativo se omite y se lista.
   - **Cerrada:** queda el supuesto.
8. **`--reemplazar-cambiados`.**
   - Supuesto: se incluye, porque la planilla sigue viva hasta la E4.
   - **Cerrada:** queda el supuesto.
9. **¿Las Empresas emisoras son las de la base de sueldos?**
   - Supuesto: sí, con el DISTINCT copiado.
   - **Cerrada (2026-10-12):** sí, las de la base de sueldos.
10. **"Mes" del listado y de la conciliación.**
    - Supuesto: el de las Líneas (FECHA A FACTURAR), que es como se organiza la planilla y como cuentan el Cruce y las Alertas.
    - Unas 250 filas no tienen fecha de factura.
    - **Cerrada:** queda el supuesto.
11. **Formato del número del Sistema contable: ¿lleva punto de venta?**
    - Supuesto: texto libre normalizado, sin tocar ceros, copiado tal cual figura en el PDF.
    - **Cerrada:** queda el supuesto.
12. **Tamaño y formatos de los adjuntos.**
    - Supuesto: 10 MB; PDF, PNG y JPEG.
    - **Cerrada:** queda el supuesto.
13. **¿Las contadoras cargan en el módulo durante la E2 y la E3?**
    - Supuesto: no. La planilla manda hasta la E4, y el módulo se usa para probar y adjuntar.
    - **Cerrada (2026-10-12):** no. Las contadoras siguen con la planilla hasta que el módulo esté probado, aprobado y revisado por completo.
14. **Tareas o clientes de la planilla que no estén en el maestro** (por ejemplo, las de cosecha).
    - Supuesto: se omiten y se listan.
    - Si son muchas, se decide antes de F3; por ejemplo, admitir una tarea sin id para las Líneas de cosecha.
    - **Cerrada:** queda el supuesto.
15. **Borrar Comprobantes.**
    - Supuesto: se permite con los no históricos, con confirmación, y no con una Factura que tiene NC.
    - **Cerrada:** queda el supuesto.
16. **¿El importe de la Línea es siempre cantidad por precio?**
    - Supuesto: sí, con precio de hasta 4 decimales. Si el PDF redondea distinto, se ajusta el precio.
    - **Cerrada:** queda el supuesto.
17. **Mismo Cliente y número que un histórico: ¿bloquear siempre?**
    - Supuesto: sí (409). Si aparece un caso real de dos Empresas con el mismo número, se revisa.
    - **Cerrada:** queda el supuesto.
18. **Dos contadoras cargando a la vez** (lo pidió el usuario el 2026-10-11: puede pasar y el sistema tiene que estar preparado).
    - Dos casos: las dos cargan el mismo Comprobante (que no quede duplicado ni dé 500), y una edita un Comprobante que la otra cambió o borró recién (¿gana la última o se avisa el conflicto?).
    - Supuesto: el duplicado lo frena la base con un índice único y responde 409 con un mensaje claro; para la edición, se avisa el conflicto comparando la fecha de la última modificación, porque un Comprobante tiene varios campos y pisar el trabajo de la otra es caro. En la E1 (Unidad de medida por defecto) el usuario eligió "gana la última", porque es un valor por defecto que se cambia poco.
    - **Cerrada:** queda el supuesto.

## 6. Fuera de alcance

- Cruce, Alertas, Pendientes, Equivalencias, importadores y Panel (E3 a E5). También listar las UM que no coinciden con la Unidad sugerida. La E3 no cuenta como facturado las Líneas de un Comprobante `pendiente_de_facturar`.
- La nota de débito.
- Pegar filas desde Excel.
- Tests e2e.
- Las columnas QUINCENA, GRUPO TAREA y "Nosotros" de la planilla: las notas de "Nosotros" no se migran.
- Sumar las tablas de Facturación a `scripts/refrescar_testing.py`, porque Terceros tampoco está. Si se suma, en `testing` los adjuntos copiados de producción responden 404 `archivo_no_encontrado`, como prevé el ADR-0019.
- Subir la consulta de empresas al núcleo y refactorizar el endpoint de Preliquidación.
- `AYUDA-facturacion.md` (GUIA, regla 28): va cuando el módulo sea de uso diario, en la E4 (pregunta 13).
- Validar rangos de fechas o que el total de una NC no supere al de su Factura.

## Anexo: Supuestos sobre la E1

**Backend**
1. Existe `app/modulos/facturacion/` con:
   - `__init__.py`: `ModuloInfo(clave="facturacion", activo=True, routers=(), modelos="app.modulos.facturacion.models", pantallas=PANTALLAS)`;
   - `permisos.py`: `MODULO = "facturacion"` y `PANTALLAS` con cinco: `pendientes`, `cruce` (`editable=False`), `comprobantes`, `equivalencias` y `panel` (`editable=False`). La clave `unidad` se retiró el 2026-10-12 y no se reutiliza;
   - `models.py`, `schemas.py`, `api/` y `services/consulta_externa.py`.
2. Las claves de unidad son las 9 de la sección 3.1, en una constante del módulo; por ejemplo, `UNIDADES` en `app/modulos/facturacion/unidades.py`.
3. La tabla `facturacion_tarea` de la E1 la borró `facturacion/002` (2026-10-12): la Unidad sugerida y No facturable se leen del sistema de campo.
4. `GET /api/facturacion/tareas` no existe: lo crea la E2 (paso A6), con Ver en `comprobantes`, y devuelve `[{tarea_id, nombre, grupo_tarea, unidad_sugerida, no_facturable}]`.
5. La `consulta_externa` tiene `obtener_tareas()`, que devuelve `{tarea_id, nombre, grupo_tarea, unidad_sugerida, no_facturable}` sin las dadas de baja; la Unidad sugerida sale del tercer segmento de la descripción de la tarea. La E2 necesita además las dadas de baja para el histórico.
6. La migración de la E1 es `migrations/facturacion/001_*.sql` y la `002` borra su tabla; la de la E2 es `003`.
7. Existe `tests/facturacion/test_mapa_permisos.py`, con `ESPERADO` y una prueba del conteo.
8. El script de primera carga de la E1 se borró el 2026-10-12. Su guarda (`--aplicar`, y `--confirmar-base <nombre>` fuera de `testing`) sigue descrita acá, en la alineación con la E1, y en el PR #88; con ella se alinea la de la sección 3.1.
9. No existe `app/modulos/facturacion/config.py`; lo crea la E2.

**Front**
10. Existe `src/modulos/facturacion/rutas.jsx` (`PREFIJO = '/facturacion'`, `MODULO = 'facturacion'`), registrado en `src/modulos/registro.js`, sin rutas ni servicio. `unidades.js` conserva las claves y las etiquetas de las 9 unidades, y el servicio lo crea el FT-A.
11. Si la E1 mueve FiltrosBar, TablaOrdenable y el estado por pantalla al núcleo, el PR-0 desaparece.
12. Si la E1 tiene tests, `package.json` ya incluye `src/modulos/facturacion/*.test.js`.
13. `PRODUCT.md` del front ya suma a las contadoras.

## Alineación con el plan de la E1 (sesión principal, 2026-10-11)

El plan de la E1 (`2026-10-11-facturacion-e1.md`) confirma casi todo el anexo. Las diferencias, ya corregidas arriba o a seguir al ejecutar:

- **La clave de la pantalla de la E1 era `unidad`**, no `unidad_facturacion`: `tests/core/test_registro_modulos.py` exige claves `[a-z]+`. Se retiró el 2026-10-12 (ver la sección siguiente) y no se reutiliza.
- **La tabla de la E1 era `facturacion_tarea`** (`tarea_id` del campo, `unidad_sugerida`, `no_facturable`, `actualizado_en`, `actualizado_por`). La borró `facturacion/002` el 2026-10-12.
- **`GET /api/facturacion/tareas`** de la E1 se retiró el 2026-10-12 con su pantalla. La E2 lo crea con Ver en `comprobantes` y suma su fila en `tests/facturacion/test_mapa_permisos.py`, como dice el paso A6.
- **La consulta del campo de la E1** filtra las bajas y expone `normalizar_nombre()`; desde el 2026-10-12 trae también la Unidad sugerida y No facturable de cada tarea. La E2 suma la lectura con bajas para el histórico, sin cambiar la de la E1.
- **La guarda de escritura de los scripts**: el script de la E1 (borrado el 2026-10-12) usaba `--aplicar` y, sobre una base que no sea `testing`, además `--confirmar-base <nombre>`. El script del histórico usa la misma convención en vez de pedir que se tipee el nombre.
- **La barra de filtros, las tablas y el estado por pantalla** no los sube la E1: el PR-0 de este plan queda.
- **La E2 sale de `main` después del merge de BK-E1** (las dos tocan `permisos.py`, `__init__.py`, `ORDEN.txt` y el test del mapa).

## Alineación con la Unidad sugerida leída del campo (sesión principal, 2026-10-12)

El plan `2026-10-12-unidad-desde-campo.md` retiró la pantalla Unidad de medida por defecto, sus endpoints, la tabla `facturacion_tarea` y los permisos guardados de `unidad`: la Unidad sugerida y No facturable se leen en vivo del sistema de campo. Lo que cambia acá ya está corregido arriba:

- **La migración de la E2 es la `003`**: la `002` borra la tabla de la E1.
- **`GET /api/facturacion/tareas` lo crea la E2**, con Ver en `comprobantes`.
- **El módulo arranca sin rutas**: `routers=()`, `models.py` sin clases y el mapa de permisos con 0 filas.
- **La E2 sale de `main` después del merge de ese PR** (toca `permisos.py`, `__init__.py`, `models.py`, `ORDEN.txt` y el test del mapa).
