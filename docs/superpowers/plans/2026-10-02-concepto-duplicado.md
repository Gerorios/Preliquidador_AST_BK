# Plan: un Concepto no se repite (ADR-0018), backend

Rama `fix/conceptos-duplicados`. Un solo PR de backend con su migración; el frontend no cambia
(el toast ya muestra cualquier `detail` string). Decisiones en `docs/adr/0018-un-concepto-no-se-repite.md`
y en el término "Concepto duplicado" de `docs/modulos/preliquidacion/CONTEXT-preliquidacion.md`.

## Qué se pide

Que `concepto_liquidacion` no admita dos reglas con la misma quincena + tarea + código + cliente +
finca + supervisor + categoría. El precio no cuenta; se compara con TRIM y sin mayúsculas; NULL = ''.
La garantía es un índice único funcional (MySQL), replicado en SQLite para los tests. La API traduce
el rechazo a un 409 con `detail` string en alta y edición. `copiar_quincena` saltea con la misma clave.

## Lo que hay hoy (relevado)

- `app/modulos/preliquidacion/models.py:86-92`: `UniqueConstraint` sobre columnas crudas; no frena nada
  porque cliente o supervisor siempre es NULL (ADR-0011).
- `precios.py` `crear_concepto` (331-388): compuerta de solapamiento (409 dict) y después `db.commit()`
  sin try (384). `actualizar_concepto` (393-437): `setattr` crudo, `db.flush()` en 423 (ahí saltaría el
  duplicado, antes del 409 `borra_extras`), `commit` en 431. OJO: después de `db.rollback()` leer
  `concepto.codigo` devuelve el código VIEJO; capturar el intentado antes.
- `copiar_quincena` (473-557): `_clave` cruda (496-500). Formato de `detalle` fijado por
  `tests/preliquidacion/test_regla_completa.py:207,215,225`.
- Únicos constructores `ConceptoLiquidacion(`: `precios.py:365` y `:514`; único `setattr`: `:410`.
  `precio_masivo` y `eliminar_concepto` no tocan la clave. `ConceptoUnifUpdateRequest` no tiene
  tarea/cliente/finca: por PATCH la clave cambia sólo vía código, categoría o supervisor.
- Arranque: `app/core/esquema.py` compara sólo tablas y columnas, no índices.
- Migraciones: formato como `ws15_conceptos_cliente_supervisor.sql`; `migrations/ORDEN.txt` y
  `tests/core/test_manifiesto_migraciones.py` exigen listar cada `.sql` una vez. Última: `ws16`.
- `scripts/refrescar_testing.py` recrea tablas de testing con el `SHOW CREATE TABLE` de producción:
  pisa el índice nuevo de testing hasta que producción lo tenga.
- Mensajes de IntegrityError: SQLite `UNIQUE constraint failed: index 'uq_concepto_unif'`; pymysql
  `(1062, "Duplicate entry '...' for key 'concepto_liquidacion.uq_concepto_unif'")`. Detectar con
  `"uq_concepto_unif" in str(exc.orig)`.
- Test que el índice rompe: `tests/preliquidacion/test_concepto_masivo.py:259-271`
  (`test_masivo_dos_opciones_sin_elegir_no_escribe_nada`, dos reglas iguales en "TAREA X" cód. 461).
  El resto de los 21 archivos que crean conceptos está limpio.

## Decisiones técnicas (defaults del plan, confirmar en la aprobación)

1. La clave de la copia en Python quita acentos (NFD sin marcas `Mn`) además de TRIM+UPPER, para imitar
   `utf8mb4_0900_ai_ci` y que la copia nunca dispare el IntegrityError en MySQL.
2. UPPER también en el índice de MySQL: misma expresión en los dos motores.
3. Sin chequeo previo antes de la compuerta de solapamiento: un duplicado que además solapa pide
   confirmar el solapamiento y después da el 409 de duplicado. Caso raro; el resultado es correcto.
4. Las repetidas del origen en la copia se cuentan en "ya existían" (no cambia el formato del detalle).
5. Regenerar `000_esquema_base.sql` y marcar `ws17` histórica: después del deploy, PR aparte.
6. Migración: `migrations/preliquidacion/ws17_concepto_unico_normalizado.sql`.
7. Texto del 409: "Ya existe una regla para esta tarea con el código X. Si querés cambiar el precio,
   editá la existente."

## Etapa A — código

### Paso 1 — Índice funcional en el modelo
Archivos: `tests/preliquidacion/test_concepto_duplicado.py` (nuevo), `app/modulos/preliquidacion/models.py`,
`tests/preliquidacion/test_concepto_masivo.py`.
- Rojo (fixture SQLite como `test_conceptos_cliente_supervisor.py:25-32`, sólo ASCII):
  `test_indice_rechaza_dos_reglas_iguales` (iguales salvo precio → IntegrityError con
  `uq_concepto_unif` en `str(exc.value.orig)`); `test_indice_normaliza_espacios_y_mayusculas`;
  `test_indice_trata_vacio_como_nulo` (cliente/finca/supervisor None vs ""); verde de control
  `test_indice_permite_lo_legitimo` (mismo código en otra tarea, otra finca, otra categoría, otra
  quincena, cliente vs supervisor).
- Implementación: reemplazar el `UniqueConstraint` por
  ```python
  Index(
      "uq_concepto_unif",
      quincena,
      func.upper(func.trim(tarea_nombre)),
      func.coalesce(func.upper(func.trim(cliente_nombre)), ""),
      func.coalesce(func.upper(func.trim(finca_nombre)), ""),
      func.coalesce(func.upper(func.trim(supervisor_nombre)), ""),
      func.coalesce(codigo, -1),
      func.coalesce(categoria, 0),
      unique=True,
  )
  ```
  Importar `func`; no sacar `UniqueConstraint` del import (lo usan otras clases). Comentario de una
  línea: clave normalizada, el precio no participa (ADR-0018).
- Arreglo del test roto: `test_concepto_masivo.py:263` → `tarea="TAREA Y"` en la segunda regla.
- Verificación: los tres archivos + `tests/core/test_esquema.py`, después `pytest` completo.

### Paso 2 — Alta: duplicado → 409 string
Archivos: `tests/preliquidacion/test_concepto_duplicado.py`, `tests/core/test_errores_internos.py`,
`app/modulos/preliquidacion/api/precios.py`.
- Rojo: `test_crear_dos_veces_la_misma_regla_da_409_con_texto` (llamada directa; 409, detail str con el
  texto exacto, queda 1 fila, la sesión sigue usable); `test_crear_con_otra_grafia_da_409`;
  `test_409_duplicado_por_http_tiene_detail_string` (TestClient, `confirmar_solapamiento: true`);
  en `test_errores_internos.py`, `test_crear_concepto_con_duplicado_de_mysql_da_409_sin_sql` (orig con
  el texto de pymysql → 409 y nada del SQL en `r.text`). El test existente de 126-166 (IntegrityError
  sin el nombre del índice → 500) sigue verde; reescribir su comentario.
- Implementación: `from sqlalchemy.exc import IntegrityError`; helpers `_es_duplicado(exc)` y
  `_error_duplicado(codigo)` junto a `_error_borra_extras`; `try/except IntegrityError` en el
  `db.commit()` de `crear_concepto` con `db.rollback()`, 409 si es el índice y `raise` a secas si no.
  Reescribir el comentario 379-383.
- Verificación: `test_concepto_duplicado.py`, `test_errores_internos.py`, `test_solapamiento_por_cliente.py`,
  `test_reemplaza_default.py`.

### Paso 3 — Edición: duplicado → 409 string, con rollback
Archivos: `tests/preliquidacion/test_concepto_duplicado.py`, `app/modulos/preliquidacion/api/precios.py`.
- Rojo: `test_editar_codigo_que_choca_da_409_y_no_guarda` (el texto dice el código intentado; tras
  refresh, la fila conserva el viejo); `test_editar_categoria_que_choca_da_409`;
  `test_editar_supervisor_que_choca_da_409` (" perez " vs "PEREZ"); verde de control
  `test_editar_la_misma_regla_sin_cambiar_clave_sigue_andando`.
- Implementación: `codigo_intentado = concepto.codigo` tras los `setattr`; `try/except` alrededor del
  `db.flush()` (423) y del `db.commit()` (431) con el mismo manejo del paso 2.
- Verificación: `test_concepto_duplicado.py`, `test_copiar_heredado.py`,
  `test_concepto_extra_sigue_maestro.py`, `test_conceptos_cliente_supervisor.py`.

### Paso 4 — `copiar_quincena` con la clave normalizada
Archivos: `tests/preliquidacion/test_concepto_duplicado.py`, `app/modulos/preliquidacion/api/precios.py`.
- Rojo: `test_copiar_saltea_la_que_existe_con_otra_grafia` ("0 copiados · 1 ya existían", una fila);
  `test_copiar_trata_finca_vacia_como_nula`; `test_copiar_saltea_repetidas_dentro_del_origen`
  ("FINCA TIMBO" y "FINCA TIMBÓ" en el origen → "1 copiados · 1 ya existían"; posible porque SQLite no
  iguala acentos y la clave Python sí).
- Implementación: `_norm(s)` = strip + upper + sin marcas diacríticas; clave
  `(_norm(tarea), _norm(cliente), _norm(finca), _norm(supervisor), codigo, categoria)`; agregar cada
  clave encolada a `claves_existentes`. Actualizar comentario y docstring.
- Verificación: `test_concepto_duplicado.py`, `test_copiar_heredado.py`, `test_regla_completa.py`,
  `test_conceptos_cliente_supervisor.py`, `test_solapamiento_por_cliente.py`.

### Paso 5 — Migración + manifiesto
Archivos: `migrations/preliquidacion/ws17_concepto_unico_normalizado.sql`, `migrations/ORDEN.txt`.
- Rojo: el `.sql` sin entrada en `ORDEN.txt` → falla `test_manifiesto_migraciones.py`. Agregar la
  entrada al final → verde.
- Contenido (sin datos ni nombres): encabezado al estilo ws15 (qué y por qué, ADR-0018); verificación
  previa que debe dar 0 filas (SELECT agrupando por la misma clave normalizada, alias con sufijo `_n`,
  `HAVING COUNT(*) > 1`; si devuelve algo, no seguir y unificar desde Conceptos); backup
  `CREATE TABLE concepto_liquidacion_bkp_ws17 AS SELECT * FROM concepto_liquidacion;`; un solo
  `ALTER TABLE ... DROP INDEX uq_concepto_unif, ADD UNIQUE INDEX uq_concepto_unif (quincena,
  (UPPER(TRIM(tarea_nombre))), (COALESCE(UPPER(TRIM(cliente_nombre)), '')),
  (COALESCE(UPPER(TRIM(finca_nombre)), '')), (COALESCE(UPPER(TRIM(supervisor_nombre)), '')),
  (COALESCE(codigo, -1)), (COALESCE(categoria, 0)));` (atómico en MySQL 8); `SHOW INDEX` de
  comprobación; rollback comentado al índice viejo y `DROP TABLE` del backup al cerrar.

### Paso 6 — Docs
Media línea en "Consecuencias" del ADR-0018: la copia entre quincenas compara sin acentos, como la base.

## Etapa B — base de datos (condiciones del deploy, no código)

### Paso 7 — `testing` (antes de mergear; la limpieza con OK del usuario)
1. SELECT de verificación (hoy: 1 grupo).
2. Borrar la fila sobrante por la API apuntando a testing (`DELETE /api/precios/conceptos/{id}`), que
   recalcula y respeta ADR-0015. No por SQL crudo.
3. SELECT → 0. Backup → ALTER → `SHOW INDEX`.
4. Arrancar la app contra testing: banner "Tablas y columnas BD propia: verificadas", sin warnings del
   índice (si aparece "Unknown schema content", anotarlo).
5. Smoke: POST repetido → 409 en toast; PATCH que choca → 409 y la fila no cambia; copiar con repetidas
   → "ya existían", nunca 500; `pytest` verde.
6. No correr `refrescar_testing.py` hasta el deploy (pisaría el índice).

### Paso 8 — Producción (sólo en el deploy, con OK explícito)
Precondición: el liquidador unificó los 2 grupos repetidos desde Conceptos.
1. SELECT → 0 (si no, parar). 2. Backup → ALTER → `SHOW INDEX`. 3. Deploy del código → banner → smoke
del 7.5. 4. Anotar en `docs/DEPLOY.md` la DDL, el backup y el rollback.

## Riesgos

- DDL sobre el único índice de la tabla en producción: verificación previa, backup, ALTER atómico,
  rollback escrito, probado antes en testing. El código no depende del índice para funcionar.
- Error al crear el índice funcional (largo ≈ 2611 bytes < 3072; expresiones VARCHAR): no esperado; si
  pasa en testing se evalúa la columna generada.
- Reflexión de SQLAlchemy sobre key parts funcionales en el arranque: a lo sumo un warning; se ve en 7.4.
- Acentos: MySQL iguala "Ó"/"O" y "ñ"/"n"; aceptado por el ADR; la copia lo imita (decisión 1).
- `refrescar_testing.py` pisa el índice de testing hasta el deploy.
- El `Duplicate entry` de MySQL trae valores de la fila: nunca sale al front (texto fijo, test del paso 2).

## Fuera de alcance

Frontend; deduplicar en el motor; unificar los repetidos de producción (lo hace el liquidador);
bloquear el código en toda la quincena; editar tarea/cliente/finca por PATCH; tocar los scripts de
refresco y exportación; las líneas repetidas por parte de campo (tarea aparte).

## Revisión, ronda 1

### Paso R1 — `copiar_quincena` ataja el choque con el índice (high)
- Hallazgo: `bulk_save_objects` + `commit` no atajan `IntegrityError`. Escenario: doble clic en Copiar;
  los dos pedidos leen el destino antes de que alguno guarde y el segundo choca con `uq_concepto_unif`
  → 500 genérico (no paga mal: la base lo frena y descarta la transacción).
- Arreglo mínimo: el mismo `try/except IntegrityError` con `db.rollback()` y `_es_duplicado` alrededor del
  `commit` de la copia; si es el índice, 409 con detail string "Otra copia de esta quincena se hizo al
  mismo tiempo. Recargá la página para ver el resultado."; si no, `raise`.
- Test rojo: simular el choque (p. ej. reemplazar `db.commit` para que lance un `IntegrityError` cuyo
  `orig` nombre `uq_concepto_unif`, como en `tests/core/test_errores_internos.py`) → hoy 500/excepción,
  esperado 409 string y nada copiado.

Minor sin tocar (van al PR): idempotencia no declarada en el encabezado de ws17; `_norm` no iguala
Ł/Ø/Đ/Æ/Œ como la collation; el `try/except` repetido; `_norm` casi igual a `_normalizar_nombre` del
núcleo y homónima de la de `solapamiento_service`; comentario "sin mayúsculas" en `models.py`;
`COALESCE(codigo,-1)` frente a un código -1. Descartados: 4.
