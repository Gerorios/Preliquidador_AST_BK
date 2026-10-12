# Plan: la Unidad sugerida se lee del sistema de campo

**Fecha**: 2026-10-12
**Rama**: `feature/unidad-desde-campo`, con un worktree por repo en `.claude/worktrees/unidad-desde-campo`.
**PRs**: hermanos, uno de backend (BK) y uno de front (FT).

- **Rutas:** relativas a la raíz de cada repo; las del front van marcadas con *(front)*.
- **Números de línea:** son los de hoy. Al editar, ubicar por contenido.
- **Plan de la E1** (`docs/superpowers/plans/2026-10-11-facturacion-e1.md`): es registro histórico y no se edita.
- **Plan de la E2**: se alinea en B6.

## 0. Pedido y decisiones del usuario (2026-10-12)

- Pedido: "no deberiamos de tener una tabla de tareas nosotros si no consumir la que ya existe, esto para evitar tener desfasajes con las tareas que se creen en la APP, y si actualizan una unidad de medida sera desde ahi antes que desde nuestro modulo". Y: "ya no sera necesario esta pantalla por lo que tambien propongo quitarla".
- La Unidad sugerida y la marca No facturable se leen en vivo del sistema de campo (tercer segmento de la descripción de la tarea). Porqué: la app de campo es la dueña del dato y así no hay desfasajes.
- En pulverización con dos tractores se cuentan las horas de un solo tractor.

## 1. Qué se pide

La Unidad sugerida y la marca No facturable de cada tarea dejan de guardarse en Facturación.
- Se leen en vivo del sistema de campo, por id de tarea, del tercer segmento de su `descripcion`.
- Las tareas dadas de baja (estado 9) siguen afuera.

Por eso se retiran, en los dos repos:
- la pantalla Unidad de medida por defecto y sus endpoints;
- la tabla `facturacion_tarea`, en `testing` y en producción, con su primera carga;
- los permisos guardados de esa pantalla.

Y se ponen al día las docs y el plan de la E2.

## 2. Qué encontré en el código

### 2.1 Primero: lo que cambia el plan

1. **Vaciar `routers` rompe un test del núcleo.**
   - `tests/core/test_registro_modulos.py:31-38` exige que cada módulo activo monte rutas bajo `/api/<clave>`.
   - Facturación tiene que seguir activa y sin rutas, para que el editor de roles muestre sus pantallas y las claves queden fijas (D2 del plan de la E1).
   - El arreglo es una línea (B3), en este PR con commit propio (pregunta 2).
   - Se descarta `activo=False`: esconde las cinco pantallas del editor de roles, contradice el bloque común de `AGENTS.md` ("los tres activos") y la E2 la tendría que revertir.
2. **Hasta la E2, Facturación no tiene Tarjeta para nadie, tampoco para el admin.**
   - `tarjetasDe` (`src/core/accesos.js` *(front)*) arma la Tarjeta sólo si hay una entrada de menú visible donde aterrizar. Con `rutas = []` no hay ninguna, así que no hace falta tocar el núcleo.
   - La contracara: quien sólo tenga permisos de Facturación no puede entrar ("Sin tarjetas, el Login no deja entrar", `src/core/accesos.js:21`). Hoy el rol de las contadoras no tiene personas y no se asigna hasta la primera versión completa del módulo (decisión del usuario).
3. **Borrar permisos desde una migración del módulo va contra la regla 6** (`GUIA-MODULOS.md:275`): un módulo no escribe en las tablas del núcleo.
   - Va en la 002 con la excepción escrita en el encabezado (pregunta 3).
   - Limpiarlos desde la Administración no alcanza: un rol que sólo tenga `unidad` quedaría vacío, y eso no se guarda ("El rol tiene que dar acceso al menos a una pantalla.", `roles_service.py:149`).
4. **El tercer segmento no se corta en SQL.**
   - Con `SUBSTRING_INDEX`, una descripción de dos segmentos devuelve el segundo, que es el grupo de pago.
   - Es la falla latente del `grupo_factura` de Preliquidación (`app/modulos/preliquidacion/services/consulta_externa.py:224-230`, que no se toca).
   - El SQL trae la `descripcion` cruda y el corte va en Python, donde se prueba.
5. **La 001 se queda en el repo y en `ORDEN.txt`.** En una base nueva corre la 001 y después la 002, que la borra. No es `historica`: el `000` no tiene nada de Facturación.

### 2.2 Backend

**Sale**
- `app/modulos/facturacion/api/tareas.py`, con `GET /api/facturacion/tareas` (Ver en `unidad`) y `PATCH /api/facturacion/tareas/{tarea_id}` (Editar).
- `services/unidad_service.py` y `services/primera_carga.py` (deja `actualizado_por` en NULL, `:168-176`: así se distinguen las ediciones de personas).
- `scripts/importar_unidades_del_maestro.py`.
- El modelo `TareaFacturacion` de `models.py` y las dos clases de `schemas.py`.
- Sus tests: `test_modelo.py`, `test_primera_carga.py`, `test_script_primera_carga.py`, `test_tareas_endpoints.py`, `test_unidad_service.py`.

**Cambia**
- `app/modulos/facturacion/__init__.py`: hoy importa `api.tareas` (`:12`) y tiene `routers=(tareas.router,)` (`:19`).
- `permisos.py`: `PANTALLAS` tiene seis, con `unidad` en `:19`; las dependencias están en `:30-31`.
- `services/consulta_externa.py`: `QUERY_TAREAS` (`:21-28`) trae el id, el nombre y el primer segmento; `obtener_tareas()` (`:55-64`) devuelve `{tarea_id, nombre, grupo_tarea}`.
- `unidades.py`: `UNIDAD_DE_PLANILLA` (`:40-50`) tiene los nueve textos; `NO_FACTURABLE_PLANILLA` está en `:54`.
- `migrations/ORDEN.txt`: termina en la 001 (`:54-55`).
- `scripts/refrescar_testing.py:63`: `TABLAS` incluye la tabla.
- Tests que cambian: `test_migracion.py`, `test_mapa_permisos.py` (`ESPERADO` en `:29-32`), `test_registro_y_permisos.py` (seis pantallas, `:18-25`), `test_consulta_externa.py` (el SQL se prueba en `:73-83`), `test_unidades.py`.

**Sirve tal cual**
- `app/core/esquema.py`: "lo que sobra en la base no es error". El código nuevo arranca con "verificadas" aunque la tabla siga, y eso habilita el orden "código antes que DROP".
- `app/main.py:35-36`: importa `modelos` aunque el archivo no declare tablas.
- `tests/core/test_endpoints_con_permiso.py:69-81` (falla si una ruta nombra una pantalla que no está; no exige que cada pantalla tenga ruta), `tests/core/test_registro_modulos.py:81-93` (pasa con cinco pantallas), `tests/core/test_refrescar_testing.py` (obliga a sacar la tabla de `TABLAS` en el mismo paso que el modelo), `tests/core/test_manifiesto_migraciones.py`.
- Hasta la E2, `obtener_tareas()` y `normalizar_nombre` no tienen quien las llame. Se conservan a propósito: la E2 las usa.

### 2.3 Front

**Se borran**: `src/modulos/facturacion/pages/UnidadFacturacion.jsx` y su `.module.css`; `services/facturacion.js` (`listarTareas`, `definirTarea`).

**Cambian**
- `rutas.jsx`: tiene una sola ruta, `/facturacion/unidad` (`:24-26`, con `lazy` en `:1` y `:14`), y `pantallas` para el asistente (`:36-38`).
- `unidades.js`: se quedan las claves y las etiquetas (`:10-28`), que usa la grilla de la E2; salen los helpers de la pantalla (`:30-94`).
- `unidades.test.js`: tiene 14 tests y quedan 2 (`:28-43`).
- `PRODUCT.md:100-102` nombra la pantalla.

**No cambian**: `src/modulos/registro.js`, `src/core/accesos.js` y `src/App.jsx` (una ruta de layout sin hijas no coincide, y `path="*"` vuelve a `/`); `package.json:11` (el glob `src/modulos/facturacion/*.test.js` sigue encontrando archivo).

**Ojo con los grep**: `src/modulos/preliquidacion/services/preliquidacion.js:83` también tiene un `listarTareas`. Los grep de verificación van acotados.

### 2.4 Convenciones

- **Molde de migración:** `migrations/core/003_borrar_usuario_modulo.sql`.
- **Vuelta atrás comentada sin `;`**: el aplicador (`docs/superpowers/plans/2026-09-08-etapa0-pr3-permisos-por-modulo.md:585-599`) corta por `;`. Tiene `assert os.environ["DB_PROPIA_NAME"] == "testing"`.
- **Claves de pantalla:** se guardan en `rol_permiso` y no cambian (`GUIA-MODULOS.md:338`).
- **ADR-0013:** la traducción vive en `facturacion/unidades.py` y no se toma de Preliquidación.
- **Zonas sensibles:** `permisos.py`, `migrations/` y `models.py`: el PR BK lleva dos rondas de revisión.
- **Entorno de tests del backend.** No hay venv. Nunca el `.env` real. Variables en línea:
  ```bash
  DB_EXTERNA_HOST=externa.invalid DB_EXTERNA_USER=x DB_EXTERNA_PASSWORD=x DB_EXTERNA_NAME=x \
  DB_SUELDOS_HOST=sueldos.invalid DB_SUELDOS_USER=x DB_SUELDOS_PASSWORD=x DB_SUELDOS_NAME=x \
  DB_PROPIA_HOST=propia.invalid DB_PROPIA_USER=x DB_PROPIA_PASSWORD=x DB_PROPIA_NAME=testing \
  SECRET_KEY=clave-de-prueba-solo-para-tests python -m pytest -q
  ```
  En el resto del plan, `python -m pytest ...` supone ese entorno.

## 3. Pasos

### Etapa 0: preparación (sin PR)

**0.1 Entorno y números de partida (ejecutor)**
- Las dos ramas salen de `origin/main` (backend con BK #93, front con FT #75).
- Backend: `python -m pytest -q` (en BK #92 fueron 1227 passed y 1 xfailed) y `python -m pytest --collect-only -q tests/facturacion`.
- Front: el junction de `node_modules` ya está (se quita con `cmd /c rmdir node_modules`, nunca con un borrado recursivo); `npm test` (173); `npm run lint` (anotar los errores conocidos de `.claude/hooks/ultimas-entregas.mjs`); `npm run build`.
- **Verificación:** los números quedan en el reporte. B7 y F1 se comparan contra ellos.

**0.2 Pre-check en `testing` (sesión principal, sólo lectura; los resultados no van a git)**
```sql
SELECT COUNT(*) AS filas, SUM(actualizado_por IS NOT NULL) AS editadas_por_personas
FROM facturacion_tarea;

SELECT tarea_id, unidad_sugerida, no_facturable, actualizado_en
FROM facturacion_tarea WHERE actualizado_por IS NOT NULL;

SELECT r.nombre, p.nivel,
       (SELECT COUNT(*) FROM usuario_rol ur WHERE ur.rol_id = r.id) AS personas,
       (SELECT COUNT(*) FROM rol_permiso o WHERE o.rol_id = r.id
          AND NOT (o.modulo = 'facturacion' AND o.pantalla = 'unidad')) AS otros_permisos
FROM rol_permiso p JOIN rol r ON r.id = p.rol_id
WHERE p.modulo = 'facturacion' AND p.pantalla = 'unidad';
```
- Sirve para saber si hubo ediciones de personas, que se perderían, y qué roles quedan vacíos con el DELETE. Si hay ediciones, se frena (pregunta 7).

### Etapa 1: backend (PR BK)

**B1. Par: la traducción del texto de unidad**

- **Archivos:** `app/modulos/facturacion/unidades.py` y `tests/facturacion/test_unidades.py`.
- **Rojo** (falla con `ImportError`):
  - `traducir_unidad` devuelve su clave y `False` para `HORAS PEON`, `HORAS TRACTOR`, `PLANTA`, `HECTAREA`, `TANCADA`, `BINS`, `BINS C`, `BINS M` y `VIAJES`.
  - `NO FACTURABLE` da `(None, True)`.
  - Lo vacío (`""`, `"   "` y `None`) da `(None, False)`.
  - Lo desconocido (`"HORA PEON"`, `"KILOS"`, `"HECTAREAS"`) da `(None, False)`.
  - `" horas  peón "` da `horas_peon`; `"Hectárea"` da `hectareas`; `"bins c"` da `bins_c`, no `bins`; `"no  facturable"` da `(None, True)`.
  - `normalizar_texto(" Horas  Peón ")` da `"HORAS PEON"`, y `normalizar_texto(None)` da `""`.
  - Cada valor de `UNIDAD_DE_PLANILLA` es una de las nueve `UNIDADES`.
- **Verde:**
  ```python
  def normalizar_texto(texto) -> str:
      """Sin acentos (NFKD), con los espacios colapsados y en mayúsculas; None da ""."""

  def traducir_unidad(texto) -> tuple[str | None, bool]:
      """(clave, False) si es una de las nueve; (None, True) si es NO FACTURABLE;
      (None, False) si está vacío o no se conoce: Sin definir."""
  ```
  - Compara contra `UNIDAD_DE_PLANILLA` y `NO_FACTURABLE_PLANILLA`. Función pura, sólo con `unicodedata`. La va a usar también el histórico de la E2.
  - Comentarios al día: el docstring (`:3`), `UNIDADES_COSECHA` (`:22-23`) y `UNIDAD_DE_PLANILLA` (`:38-39`), que pasa a decir "el sistema de campo, tercer segmento de la descripción de la tarea, y la columna UM de la hoja de facturación". El nombre de la constante no cambia.
- **Verificación:** `python -m pytest tests/facturacion/test_unidades.py -q`, primero en rojo y después en verde.

**B2. Par: la consulta de tareas trae la Unidad sugerida**

- **Archivos:** `app/modulos/facturacion/services/consulta_externa.py` y `tests/facturacion/test_consulta_externa.py`.
- **Rojo:**
  - Las filas de `SesionFalsa` pasan a ser `(tarea_id, nombre_tarea, descripcion)`.
  - `obtener_tareas()` devuelve exactamente `{tarea_id, nombre, grupo_tarea, unidad_sugerida, no_facturable}`, sin `sin_definir` y sin el texto crudo, en el orden en que llegan.
  - Casos parametrizados:

    | `descripcion` | `grupo_tarea` | Unidad |
    |---|---|---|
    | `"G;P;PLANTA;EXTRA"` | `"G"` | `plantas` |
    | `"G;P;PLANTA"` | `"G"` | `plantas` |
    | `"G;HORAS PEON"` (dos segmentos: es la clave) | `"G"` | Sin definir |
    | `"G"` | `"G"` | Sin definir |
    | `""` y `None` | `None` | Sin definir |
    | `"G;P;"` | `"G"` | Sin definir |
    | `" G ; P ; horas  tractor "` | `"G"` | `horas_tractor` |
    | `"G;P;NO FACTURABLE"` | `"G"` | No facturable |
    | `";P;BINS C"` | `None` | `bins_c` |

  - El SQL tiene `ta.id AS tarea_id`, `ta.nombre AS nombre_tarea`, `ta.descripcion`, `WHERE ta.estado <> 9` y `ORDER BY ta.nombre`, y no tiene ni `SUBSTRING_INDEX` ni `grupo_pago`.
  - Siguen los 3 tests del campo caído y los 3 de `normalizar_nombre`.
- **Verde:**
  - `QUERY_TAREAS` sigue con la misma tabla, el mismo filtro y el mismo orden, pero trae `ta.descripcion AS descripcion`.
  - El corte se hace en Python: `partes = (descripcion or "").split(";")`; `grupo_tarea = partes[0].strip() or None`; el texto de la unidad es `partes[2]` sólo si hay tres partes o más (si no, `""`); después, `traducir_unidad(texto)`.
  - Docstrings y comentarios al día: el del módulo (`:3-5`), `QUERY_TAREAS` (`:17-20`), `normalizar_nombre` (`:35-38`) y `obtener_tareas` (`:56-59`).
- **Verificación:** `python -m pytest tests/facturacion tests/core/test_arquitectura.py -q`.

**B2b. Opcional (sesión principal, sólo lectura)**: un script de una vez, en el scratchpad y fuera del repo, que llame a `obtener_tareas()` contra el campo y muestre cuántas tareas hay por unidad, cuántas son No facturable, cuántas quedan Sin definir y cuáles cambian respecto de la tabla en `testing`. Nada va a git.

**B3. Paso suelto: el test del núcleo admite un módulo activo sin rutas**

- **Archivo:** `tests/core/test_registro_modulos.py:33`.
  ```python
  # Un módulo activo puede no tener rutas todavía (Facturación entre el
  # 2026-10-12 y la E2): publica sus pantallas y no monta nada.
  prefijos_activos = {f"/api/{m.clave}" for m in activos() if m.routers}
  ```
- **Verificación:** `python -m pytest tests/core/test_registro_modulos.py -q`, en verde antes y después de B4.
- Va en un commit propio, `test(core): un módulo activo puede no tener rutas todavía`.

**B4. Par (zona sensible: `permisos.py`): sale la pantalla `unidad` con sus endpoints**

- **Rojo:**
  - `tests/facturacion/test_registro_y_permisos.py`: `CATALOGO_FACTURACION` con cinco (pendientes, cruce `False`, comprobantes, equivalencias, panel `False`); los tests pasan a llamarse `..._cinco_...`; un assert con mensaje: `"unidad"` no está entre las claves, porque "se retiró el 2026-10-12 y no se reutiliza: un rol con permisos viejos ganaría la pantalla nueva"; el docstring, al día.
  - `tests/facturacion/test_mapa_permisos.py`: salen `VER_UNIDAD` y `EDITAR_UNIDAD`; `ESPERADO = {}`; `test_la_tabla_no_tiene_rutas` afirma `len(ESPERADO) == 0`; `_exige` y `F` se quedan, con un comentario para que la E2 sume ahí sus filas; `test_cada_endpoint_exige...` no cambia (falla mientras existan el GET y el PATCH).
- **Verde:**
  - `permisos.py`: cinco pantallas, en el orden de hoy; salen `ver_unidad`, `editar_unidad` y el import de `requiere_pantalla` (la E2 lo vuelve a sumar); los comentarios de `:10-14` y `:24-29`, al día, con el retiro de la clave `unidad`.
  - `__init__.py`: sale el import de `api.tareas`; `routers=()`; el docstring (`:8-10`) dice que el módulo está activo, con cinco pantallas declaradas y ninguna construida.
  - Se borran `api/tareas.py` y `services/unidad_service.py`. Se quedan `api/__init__.py` y `services/__init__.py`.
  - `schemas.py`: quedan sólo el docstring y la aclaración de que la E2 suma los suyos.
  - Se borran `tests/facturacion/test_tareas_endpoints.py` y `tests/facturacion/test_unidad_service.py`.
- **Verificación:** `python -m pytest tests/facturacion tests/core -q`.

**B5. Par (zonas sensibles: `migrations/` y `models.py`): sale la tabla**

- **Rojo:** se reescribe `tests/facturacion/test_migracion.py`. Salen el test de columnas y el import del modelo, y quedan estos seis controles:
  1. Ninguna línea comentada de la 001 ni de la 002 tiene `;` (test parametrizado).
  2. Las sentencias de la 002 son exactamente estas, cortadas como el aplicador, sin las líneas de comentario y con los espacios colapsados:
     ```python
     ["DELETE FROM rol_permiso WHERE modulo = 'facturacion' AND pantalla = 'unidad'",
      "DROP TABLE IF EXISTS facturacion_tarea"]
     ```
  3. El encabezado de la 002 tiene `-- NO DIFERIBLE`.
  4. En `ORDEN.txt`, la 002 va después de la 001 (no se pide que sea la última: la E2 suma la 003).
  5. Después de `import app.main`, `"facturacion_tarea"` no está en `Base.metadata.tables`.
  6. Ningún `.py` de `app/` ni de `scripts/` nombra `facturacion_tarea`: el código nuevo no lee la tabla.
- **Verde:**
  - `migrations/facturacion/002_borrar_unidad_por_tarea.sql`:
    ```sql
    -- facturacion/002 — Borra facturacion_tarea y los permisos guardados de la pantalla `unidad`.
    -- NO DIFERIBLE: va con el deploy de esta versión, DESPUÉS de reiniciar el backend. El código
    -- anterior lee la tabla y el de esta versión no (la Unidad sugerida se lee del sistema de campo).
    -- Idempotente: si la tabla o los permisos ya no están, no hace nada.
    -- En una base nueva sigue andando: la 001 crea la tabla y esta la borra (orden de ORDEN.txt).
    -- Toca rol_permiso, que es del núcleo: excepción a la regla 6 de GUIA-MODULOS.md, ver el plan
    -- docs/superpowers/plans/2026-10-12-unidad-desde-campo.md. La clave `unidad` se retiró y no se
    -- reutiliza, y sus permisos no tienen que quedar guardados.
    -- Vuelta atrás (sólo si se vuelve al código anterior): cargar el respaldo tomado antes de esta
    -- migración, que recrea la tabla con sus filas, y reinsertar las filas de rol_permiso del mismo
    -- respaldo. Sin respaldo, correr de nuevo la 001, que crea la tabla vacía. Recién después se
    -- vuelve el código.

    DELETE FROM rol_permiso WHERE modulo = 'facturacion' AND pantalla = 'unidad';

    DROP TABLE IF EXISTS facturacion_tarea;
    ```
  - `migrations/ORDEN.txt`: la 002 en la línea siguiente a la 001 (`:55`).
  - `migrations/facturacion/LEEME.md`: una línea para la 001 y otra para la 002; la regla "las líneas comentadas no llevan `;`".
  - `models.py`: queda sólo el docstring (hoy no hay tablas; la de la E1 se borró con `facturacion/002`; la E2 suma las suyas). No nombra la tabla, por el control 6. `modelos=` sigue apuntando a este archivo.
  - Se borran `services/primera_carga.py`, `scripts/importar_unidades_del_maestro.py` y los tests `test_modelo.py`, `test_primera_carga.py` y `test_script_primera_carga.py`.
  - `scripts/refrescar_testing.py`: sale `"facturacion_tarea"` de `TABLAS` (`:63`).
- **Verificación:** `python -m pytest tests/facturacion tests/core -q` y `python -m pytest --collect-only -q tests/facturacion`.

**B6. Paso suelto (sin test): docs y comentarios**

- `docs/modulos/GUIA-MODULOS.md`:
  - `:23`: el módulo todavía no tiene pantallas; la Unidad sugerida la lee del sistema de campo y la primera pantalla llega con la E2.
  - Árbol de carpetas: `:171` las cinco pantallas, ninguna construida; `:172` sale; `:173` `facturacion_*` lleva "(hoy ninguna)"; `:175` sólo `consulta_externa.py`; `:180` suma la 002; `:222` las nueve Unidades; `:223` sale.
  - `:230`: Terceros pasa a ser el ejemplo. `:234`: un módulo activo puede no tener `routers`; publica sus pantallas y no tiene Tarjeta. `:235`: "declara cinco sin ninguna construida". `:238`: los moldes pasan a ser `tests/terceros/test_registro_y_permisos.py` y `tests/terceros/test_mapa_permisos.py`. `:244`: el ejemplo pasa a ser `src/modulos/preliquidacion/pages/filtrarLineas.js`.
  - `:374`: la regla para retirar una pantalla: sale de `PANTALLAS`, de su ruta, del menú y del glosario; sus endpoints salen o pasan a otra pantalla en el mismo PR; **su clave no se reutiliza nunca**; sus permisos se borran con una migración aplicada después del deploy del código.
  - `:423`: `TABLAS` queda con "las del núcleo y Preliquidación".
- `docs/modulos/facturacion/plan-facturacion.md`:
  - 3.3 (`:107-113`): se definen en el sistema de campo (hoy, el tercer segmento de la descripción) y el módulo las lee en vivo, sin copia; decidido el 2026-10-12; el aviso de tarea facturable sin unidad va en Pendientes (E3). `:114-116` se queda.
  - 3.7: sale la fila `:173`; `:179-180` dice que dónde se edita el Umbral lo decide la E3, y que quien marca Alertas revisadas sigue sin poder subirlo.
  - Sección 4: `:190-192` "decidido el 2026-10-12: se cuenta un solo tractor"; `:193` el aviso va en Pendientes (E3).
  - Tabla de etapas: `:201` suma la nota del retiro; `:203` el Umbral pasa a "dónde se edita, lo decide esta etapa", y se suma el aviso en Pendientes.
  - Sección 7: `:222` el Umbral suma lo de la E3; `:225` sale.
- `docs/modulos/facturacion/pantallas.md`: `:54-56` sale; `:73` el aviso va en Pendientes (E3); "Abierto" suma el Umbral y salen `:88-89`.
- `docs/modulos/facturacion/CONTEXT-facturacion.md`: `:28-29` sale; Unidad sugerida (`:115-119`) y No facturable (`:121-123`) suman "Se define en el sistema de campo, en cada tarea; Facturación la lee y no la cambia".
- `docs/superpowers/plans/2026-10-11-facturacion-e2.md`:
  - La migración pasa de 002 a 003 en `:166`, `:409`, `:454`, `:464`, `:748`, `:763` y `:901`.
  - `:360`: "lo crea la E2 | Ver en `comprobantes` | `[{tarea_id, nombre, grupo_tarea, unidad_sugerida, no_facturable}]`". `:453`: `models.py` no tiene clases. `:512`: `routers` pasa de `()` al router nuevo. `:515`: el mapa pasa de 0 a 9 filas. `:517`: crear `GET /api/facturacion/tareas` con Ver en `comprobantes`.
  - Anexo: ítem 1 cinco pantallas y `routers=()`; ítem 3 la tabla la borró la 002; ítem 4 el GET lo crea la E2; ítem 5 `obtener_tareas()` con los campos nuevos y sin bajas; ítem 6 001, 002 y 003; ítem 8 el script se borró, pero la guarda (`--aplicar`, y `--confirmar-base <nombre>` fuera de `testing`) sigue descrita acá y en el PR #88; ítem 10 sin rutas ni servicio, `unidades.js` conserva las claves y FT-A crea el servicio.
  - Alineación: `:916-920` al día; una sección nueva del 2026-10-12: la E2 sale de `main` después de este merge.
- **Verificación:** `git diff --stat` muestra sólo estos archivos; `git grep -n -E "Unidad de medida por defecto|facturacion_tarea|primera_carga|unidad_service|importar_unidades"` sólo encuentra registros históricos (`BITACORA.md`, `estado.md`, los planes de la E1 y de la deuda chica, este plan, las notas de retiro, las dos migraciones con su `LEEME.md` y `test_migracion.py`).

**B7. Suite completa**: `python -m pytest -q` con 0 fallas, 1 xfailed y ningún skip nuevo; el reporte compara los passed y el `--collect-only` de `tests/facturacion` con los de 0.1.

### Etapa 2: front (PR FT), en paralelo con la etapa 1

**F0. `impeccable` (antes de editar)**: `.claude\skills\impeccable\scripts\impeccable.cmd context --target src/core/inicio/Inicio.jsx` y leer `.claude/skills/impeccable/reference/craft-floor.md`. Lo único visible que cambia es que desaparecen la Tarjeta y la entrada de menú de Facturación.

**F1. Paso suelto (sólo borrar)**
- Se borran *(front)*: `src/modulos/facturacion/pages/UnidadFacturacion.jsx`, `src/modulos/facturacion/pages/UnidadFacturacion.module.css` y `src/modulos/facturacion/services/facturacion.js`.
- `rutas.jsx`: salen `import { lazy }` y `UnidadFacturacion`; `rutas = []`; `nav` sigue derivado de `rutas`; `redirecciones = []`; `pantallas = {}`; `modulo` no cambia. Los comentarios de `:3-13` dicen que no hay ninguna pantalla construida (la de la E1 se retiró el 2026-10-12), que no hay menú ni Tarjeta para nadie y que una URL tipeada vuelve al Inicio; el de `:19-23`, que el ícono del menú se elige con la primera pantalla.
- `unidades.js`: quedan `UNIDADES`, `UNIDADES_COSECHA` y `ETIQUETAS`; sale `:30-94`; el encabezado (`:1-8`) y `:15`, al día.
- `unidades.test.js`: quedan los tests de `:28-38` y `:40-43`; salen `tareasDe`, `ids` y los otros 12 tests.
- **Verificación:** `npm test` 161 (173 − 12) sin fallas; `npm run lint` sin errores nuevos; `npm run build` sin errores; `git grep -n -E "UnidadFacturacion|definirTarea|listarTareas|services/facturacion" -- src/modulos/facturacion` y `git grep -n -E "UnidadFacturacion|facturacion/unidad" -- src` sin resultados.

**F2. `PRODUCT.md` (sesión principal)**: cambia `:100-102`:
> La Unidad sugerida y la marca No facturable de cada tarea se definen en el sistema de campo; el módulo las lee y no las cambia. La primera pantalla de uso llega con la etapa 2: Comprobantes.

**F3. Smoke en el navegador contra `testing`, con las dos ramas (sesión principal)**, con la tabla todavía en la base:
1. El banner dice "Tablas y columnas BD propia: verificadas" y `/health` da ok.
2. Con el admin, el Inicio no muestra Facturación ni en el Inicio ni en el menú.
3. `/facturacion/unidad` y `/facturacion` vuelven a `/`.
4. `GET /api/facturacion/tareas` da 404, y `GET /api/auth/modulos` muestra cinco pantallas de Facturación.
5. El editor de roles muestra las cinco. El rol de las contadoras se abre **sin guardar**.
6. Una pantalla de Preliquidación y una de Terceros abren, y la consola queda sin errores.

### Revisión

- **BK: dos rondas** (zonas sensibles). Foco: las sentencias y el encabezado de la 002; que nada en `app/` ni en `scripts/` lea la tabla; que B3 no tape un módulo que debería montar rutas; que las docs digan lo mismo que lo decidido.
- **FT: una ronda**, más `/impeccable critique` y `/impeccable audit` sobre `src/core/inicio/Inicio.jsx`. Sin `polish`.

### Etapa 3: pasos FRENADOS (sesión principal, cada uno con OK del usuario)

**S1. PRs y merges**: cuerpos con `--body-file` (el porqué con las palabras del usuario, el PR hermano, el orden de deploy y la vuelta atrás). Merge con `--merge --admin`: **primero el FT y enseguida el BK**, sin deploy en el medio. Después, `/bitacora` sin preguntar, commit a `main`, push con OK.

**S2. La 002 en `testing`, justo después de S1**
- Respaldo: los dos dumps de S4.2 contra `testing`, fuera del repo.
- Sentencia: `git pull` en el checkout principal y aplicar la 002 con el aplicador (assert de `testing`).
- Verificación: `SHOW TABLES LIKE 'facturacion\_tarea'` vacío; `SELECT COUNT(*) FROM rol_permiso WHERE modulo='facturacion' AND pantalla='unidad'` da 0; correrla de nuevo no da error; el backend de `main` dice "verificadas".
- Vuelta atrás: cargar los dos dumps.
- Aviso para el desarrollador de Terceros: hacer pull; un `main` viejo contra `testing` muestra "faltan" en el banner.

**S3. Smoke de `main` contra `testing`, ya sin la tabla**: los mismos seis puntos de F3.

**S4. Deploy a producción** (sólo con OK; entra también lo mergeado y sin deployar: BK #90 a #93 y FT #74 y #75)
1. Anotar el commit que corre en el backend y la carpeta actual del front.
2. Respaldo de la base según `docs/DEPLOY.md`, más dos dumps fuera del repo:
   ```bash
   mysqldump --single-transaction --skip-extended-insert <base> facturacion_tarea > facturacion_tarea_2026-10-12.sql
   mysqldump --single-transaction --skip-extended-insert --no-create-info \
     --where="modulo='facturacion' AND pantalla='unidad'" <base> rol_permiso > rol_permiso_unidad_2026-10-12.sql
   ```
   Verificación: `grep -c "INSERT INTO"` da las filas del pre-check, y el primer dump trae el `CREATE TABLE`.
3. Pre-check en producción, sólo lectura, con las consultas de 0.2. Si hay filas con `actualizado_por`, frenar y mostrárselas al usuario.
4. Front: build de `main` y swap de carpeta. Verificación: el Inicio no tiene Facturación.
5. Backend: `git pull` y reinicio. Verificación: "verificadas" con la tabla todavía en la base; `/health` ok; `GET /api/facturacion/tareas` da 404.
6. Aplicar la 002 como dice `docs/DEPLOY.md`.
7. Verificar que la tabla no está, que no quedan permisos de `unidad` y que `/health` da ok.
8. Smoke sin escribir: login del admin; el Inicio sin Facturación; `/facturacion/unidad` vuelve a `/`; el editor de roles con cinco pantallas; una pantalla de Preliquidación y una de Terceros; el anillo de foco de `.input` (FT #74).

**Vuelta atrás de S4**
- Antes del paso 6: el front vuelve a la carpeta anterior y el backend a `<commit anotado>` con reinicio; la tabla y los permisos están intactos.
- Después del paso 6: primero los datos (cargar los dos dumps y comparar con el pre-check) y recién después el código. Nunca se vuelve el código antes que la tabla, porque el backend anterior la lee.

**S5. Anotar**: entrada de deploy aparte en `docs/BITACORA.md`; en `docs/estado.md` salen "revisar las unidades raras en la pantalla" y "confirmar el segundo tractor"; el del rol de las contadoras pasa a "completarlo con la E2; hasta entonces no asignarlo, porque sin Tarjeta no se puede entrar"; se suma revisar en la app de campo las tareas facturables Sin definir; el próximo paso de la E2 recuerda que su migración es la 003.

### Corte en PRs y orden

- **PR BK** = etapa 1 (B1 a B7, con las docs). **PR FT** = etapa 2 (F1 y F2). Hermanos, en paralelo; F3 usa las dos ramas.
- Orden: merge del FT; merge del BK; `/bitacora`; la 002 en `testing`; el smoke; el deploy (swap del front, reinicio del backend y la 002 en producción); la bitácora del deploy y `estado.md`.
- La E2 sale de `main` después de estos merges y usa la migración 003.
- Commits propuestos (manda `/commit`):
  - B1: `feat(facturacion): traducir el texto de unidad del sistema de campo`
  - B2: `feat(facturacion): la consulta de tareas trae la Unidad sugerida`
  - B3: `test(core): un módulo activo puede no tener rutas todavía`
  - B4: `feat(facturacion): quitar la pantalla Unidad de medida por defecto`
  - B5: `feat(facturacion): borrar la tabla de la Unidad sugerida`
  - B6: `docs(facturacion): la Unidad sugerida se lee del sistema de campo`

## 4. Riesgos

| # | Riesgo | Nivel | Mitigación |
|---|---|---|---|
| 1 | La 002 borra datos: la tabla (134 filas en producción) y los permisos de `unidad`. | Alto | Respaldo de la base y dos dumps verificados; pre-check; vuelta atrás escrita en el encabezado y en S4. |
| 2 | El backend anterior sin la tabla da "faltan", `/health` en error y 500. | Alto | La 002 va después del reinicio y de ver "verificadas"; el control 6 de B5; en la vuelta atrás, primero la tabla. |
| 3 | Se pierden ediciones que hicieron personas desde la pantalla. | Medio | Pre-check por `actualizado_por`; si hay, se frena. |
| 4 | Textos del campo que no coinciden quedan Sin definir sin aviso hasta la E3. | Medio | Tests con los valores reales; B2b; pendiente en `estado.md`; el aviso de la E3. |
| 5 | Una descripción de dos segmentos se leería como unidad. | Medio | El corte va en Python, con el caso `"G;HORAS PEON"` fijado en un test. |
| 6 | `testing` es compartida: un refresco entre S2 y S4 trae de vuelta los permisos huérfanos, y uno desde un checkout viejo recrea la tabla. | Medio | No refrescar entre S2 y S4; si pasa, volver a correr la 002. |
| 7 | Un `main` viejo contra `testing` ve "faltan" en el banner. | Bajo | El aviso de S2. |
| 8 | Se rompen las reglas 6 y 4 de la GUIA. | Medio | Excepción escrita en la 002 y en el cuerpo del PR; dos rondas de revisión. |
| 9 | Si se reutilizara la clave `unidad`, la pantalla nueva les llegaría a roles viejos. | Bajo | Comentario en `permisos.py`, assert, regla en la GUIA y ninguna fila guardada. |
| 10 | Quien sólo tenga permisos de Facturación no puede entrar. | Bajo | El rol de las contadoras no tiene personas y no se asigna hasta la primera versión completa. |
| 11 | Una pestaña abierta en `/facturacion/unidad` da error después del reinicio. | Bajo | El front va antes que el backend; sólo la veía el admin. |
| 12 | El deploy lleva BK #90 a #93 y FT #74 y #75. | Medio | El smoke de S4.8. |

## 5. Preguntas abiertas, con lo que se asume

1. `activo` de Facturación: `True` con `routers=()`, relajando el test del núcleo (B3).
2. El cambio del test del núcleo va en este PR, con commit propio y nombrado en el cuerpo.
3. El DELETE de `rol_permiso` va en `facturacion/002`, con la excepción escrita.
4. Un rol que queda sin permisos se conserva vacío para la E2.
5. `obtener_tareas()` devuelve sólo los valores traducidos, sin el texto crudo ni `sin_definir`.
6. Los textos que no son los nueve ni NO FACTURABLE quedan Sin definir, sin alias; se corrigen en la app de campo.
7. Si hay ediciones de personas, se frena antes del DROP y decide el usuario.
8. Los dumps se guardan fuera del repo como mínimo hasta que la E2 esté en producción.
9. El DDL en `testing` va después de los merges.
10. Pulverización: se cuenta un solo tractor (decidido); cuál, lo confirma la E3 (se asume el primero, como el informe).
11. Dónde se edita el Umbral lo decide la E3; quien marca Alertas revisadas no lo puede subir.
12. Deploy: uno solo con lo pendiente, con OK del usuario.
13. Lo no verificado por el planificador: los nombres de columnas del pre-check (se confirman en `migrations/core/002_roles_y_permisos.sql`), el respaldo de `docs/DEPLOY.md`, `impeccable.cmd context --target` en Windows y el conteo exacto de la suite (se mide en 0.1).

## 6. Fuera de alcance

- La E2 y la E3: Comprobantes, el `GET /tareas` nuevo, el aviso en Pendientes, el Umbral.
- Escribir en el sistema de campo o corregir tareas en la app de campo.
- Las expresiones sin guarda de Preliquidación (`GRUPO_PAGO_EXPR` y `grupo_factura` de su `consulta_externa.py`).
- Un test general de `;` en los comentarios de todas las migraciones.
- Regenerar el `000` o marcar la 001 como `historica`.
- Borrar el rol de las contadoras, o una limpieza genérica de permisos huérfanos en el núcleo.
- Tests e2e.
- Editar el plan de la E1, o `docs/BITACORA.md` y `docs/estado.md` desde el worktree.
- Sumar las `terceros_*` a `TABLAS`.
