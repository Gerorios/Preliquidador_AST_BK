# Facturación — Etapa 1: el módulo y la pantalla Unidad de medida por defecto

Plan de implementación de la E1 de `docs/modulos/facturacion/plan-facturacion.md` (sección 5).
- Glosario: `CONTEXT-facturacion.md`.
- Brief de UX: `pantallas.md`.
- Backend en la rama `feature/facturacion-e1`; front en su worktree `facturacion-e1`.
- Interfaz con la skill `impeccable` del front (`.claude/skills/impeccable/`).

Carril completo: hay DDL, un contrato de API nuevo y permisos. Lo hizo el planificador el 2026-10-11, en paralelo con el de la E2 (`2026-10-11-facturacion-e2.md`), que ya está alineado con este.

## 1. Qué se pide

Registrar y activar el módulo Facturación con sus seis pantallas declaradas para el editor de roles. Construir la única de esta etapa, **Unidad de medida por defecto**: cada tarea del sistema de campo tiene una Unidad sugerida o la marca No facturable, y las que no tienen nada se ven primero. Sumar una primera carga desde el maestro de tareas de la planilla (un script sobre un CSV) y actualizar `PRODUCT.md` del front con las contadoras y el módulo.

Se da por buena cuando cada tarea activa del campo tiene Unidad sugerida o es No facturable, y las que no tienen nada se ven primero.

## 2. Qué encontré en el código

### 2.1 Primero: una premisa de los docs que no se cumple

`plan-facturacion.md` (sección 6) dice que Facturación "reutiliza su barra de filtros común, sus tablas y su estado por pantalla" del refinamiento de Preliquidación, y `pantallas.md` ("Dirección") habla de "los componentes que ya existen". Esos componentes **no están en el núcleo**:
- `FiltrosBar.jsx`, `TablaOrdenable.jsx` y `AvisoError.jsx` viven en `src/modulos/preliquidacion/components/`;
- `estadoPantallas.js` vive en `src/modulos/preliquidacion/`.

Por ADR-0013 un módulo no importa a otro. Para usarlos, antes hace falta un PR del núcleo que los suba a `src/core/`.

- **La E1 no los necesita.** Su pantalla es una lista de unas 135 filas con búsqueda y un chip, y alcanza con lo que sí es del núcleo: las clases globales `.input`, `select.input`, `.chip`, `.chip-active` y `.table-wrap`, más `CargandoContenido`, `CargandoOverlay` y `mensajeDeError`.
- **La E2 sí los va a querer** (Comprobantes con "la barra de filtros común"). El PR del núcleo va antes de su front (es el PR-0 del plan de la E2).
- El paso B8 corrige esas dos líneas de los docs.

### 2.2 Lo que ya existe y sirve

**Backend: registro y permisos**
- `app/modulos/__init__.py` registra los módulos, uno por línea. `ModuloInfo` y `Pantalla` están en `app/core/modulos.py`.
- `app/main.py` importa los `modelos` de los módulos activos: así entran a `Base.metadata` y al chequeo del arranque. También monta sus routers.
- Los permisos por pantalla salen de `requiere_pantalla` (`app/core/permisos.py`). El patrón está en `app/modulos/terceros/permisos.py`: `MODULO`, `PANTALLAS` y las dependencias `ver_x`/`editar_x`, definidas una sola vez.

**Backend: lectura del sistema de campo**
- Si el campo no responde, sale un 503: `ExternaNoDisponible` (`app/core/database.py`) tiene un handler global en `app/main.py`.
- La traducción de `OperationalError` a esa excepción sólo está en Preliquidación (`app/modulos/preliquidacion/services/consulta_externa.py`). Terceros no la tiene.
- El maestro de tareas lo lee `QUERY_TAREAS` de Preliquidación.
  - Trae el nombre y los tres segmentos de `descripcion`: grupo de tareas, grupo de pago y un `grupo_factura` que nadie usa.
  - No trae el id, aunque el maestro lo tiene: las consultas de partes unen la tarea por id (en Preliquidación y en `app/modulos/terceros/services/consulta_externa.py`).
- `tarea_canonica` (`app/modulos/preliquidacion/services/preliquidacion_service.py`) normaliza los nombres de tarea.
  - Hace `strip().upper()` y aplica un alias **de pago** (ADR-0012).
  - No colapsa los espacios internos.

**Backend: esquema y scripts**
- Al arrancar se compara el esquema (`app/main.py`). El arranque no aborta: imprime `ERROR: faltan tablas…` y `/health` da `"error"`.
- Hay un script de carga de referencia: `scripts/importar_tarifas_del_excel.py`. Simula si no se pasa `--aplicar`, usa `sys.path.insert` y las sesiones del núcleo.
- La guardia de base es `guardia_base_propia` (`app/core/config.py`).

**Backend: tests que fijan comportamiento**
- `tests/core/test_registro_modulos.py`:
  - exige exactamente dos módulos. **Se rompe** (B5);
  - todo módulo activo monta algo bajo `/api/<clave>`;
  - las claves de pantalla son `[a-z]+` y alguna es editable.
- `tests/core/test_endpoints_con_permiso.py`: cada ruta `/api/*` tiene exactamente un requisito, con pantallas del catálogo. No exige que cada pantalla tenga ruta.
- `tests/core/test_arquitectura.py`: los módulos no se importan entre sí.
- También se miran `tests/core/test_manifiesto_migraciones.py` y `tests/core/test_refrescar_testing.py`.
- `tests/core/test_scripts_usuarios.py` corre una regex sobre todos los `scripts/*.py`.

**Frontend**
- El registro de módulos está en `src/modulos/registro.js`. El descriptor de referencia es `src/modulos/terceros/rutas.jsx`: rutas `lazy`, `nav` derivado de las rutas, `pantallas` para el asistente y `gerencial: null`.
- Los accesos salen de `menuDe`, `homeDeModulo` y `tarjetasDe` (`src/core/accesos.js`):
  - una pantalla sin entrada de menú no da tarjeta (`src/core/accesos.test.js`, el caso de Revisión);
  - sin tarjetas, el Login no deja entrar (`src/core/pages/Login.jsx`);
  - una URL desconocida vuelve al Inicio (`src/App.jsx`).
- `puedeEditar(usuario, modulo, pantalla)` está en `src/core/permisos.js`.
- La pantalla más parecida es `src/modulos/preliquidacion/pages/CategoriasOperarios.jsx`: muestra un select si se puede editar y texto si sólo se puede ver, y marca con borde `--warn` lo que falta.
- `Revision.jsx` es el precedente de actualizar el caché con lo que devuelve la escritura, sin volver a leer.
- Los tests son puros, con `node --test` y sin dependencias. El script `test` de `package.json` enumera globs por carpeta y no incluye `src/modulos/facturacion/`.
- `src/core/ui/iconos.jsx` no tiene ícono de Facturación. Terceros reusó íconos existentes para no tocar el núcleo.

### 2.3 Lo que hay que crear

No existe nada de Facturación en ninguno de los dos repos. Faltan `app/modulos/facturacion/`, `tests/facturacion/`, `migrations/facturacion/` y `src/modulos/facturacion/`.

### 2.4 Decisiones

**Cerradas con el usuario antes de este plan (2026-10-11):**
- seis pantallas;
- por tarea, Unidad sugerida o No facturable, y la Unidad de facturación va en la Línea desde la E2;
- nueve unidades, incluidas las cuatro de cosecha, sin tercera marca;
- tareas = maestro del sistema de campo, con tabla propia `facturacion_*`;
- primera carga por script sobre un CSV;
- el módulo no crea roles;
- el Umbral y el Mes de corte no entran.

**D1. Las seis pantallas**, en `app/modulos/facturacion/permisos.py` y en el orden del editor de roles. Las claves se guardan en la base (`rol_permiso.pantalla`) y no cambian.

| Clave | Nombre | Editable | Ver / Editar | En la E1 |
|---|---|---|---|---|
| `pendientes` | Pendientes | sí | las Alertas / marcarlas revisadas | declarada |
| `cruce` | Cruce | no | sólo ver | declarada |
| `comprobantes` | Comprobantes | sí | comprobantes y adjuntos / cargar, editar, adjuntar, importar órdenes | declarada |
| `unidad` | Unidad de medida por defecto | sí | Unidad sugerida y No facturable (desde la E3, el Umbral) | **construida** |
| `equivalencias` | Equivalencias | sí | ver / crear y cambiar | declarada |
| `panel` | Panel | no | sólo ver | declarada |

Ninguna tiene `requiere`.

**D2. Quien entra a una pantalla no construida no ve nada, y no se rompe.**
- Las cinco se declaran en el backend: aparecen en el editor de roles y en `/api/auth/modulos`. No tienen endpoint, ni ruta, ni entrada de menú.
- Quien sólo tenga pantallas futuras no ve la tarjeta de Facturación, igual que quien sólo tiene Revisión. Si es su único permiso, el Login no lo deja entrar. Una URL tipeada vuelve al Inicio.
- **Por qué no una página "en construcción":** llenaría el menú de entradas vacías, y la tarjeta podría aterrizar en una de ellas.
- **Por qué declararlas igual:** las claves quedan fijas desde el principio, y ningún test exige que una pantalla tenga ruta.

**D3. La tarea se identifica por el id del sistema de campo (`tarea_id`), no por el nombre.**
- **Por qué:**
  - los partes del campo apuntan a la tarea por id, y el Cruce de la E3 los lee en vivo desde abril de 2025;
  - un renombre en el campo no hace perder la Unidad sugerida;
  - nada garantiza que el nombre sea único.
- Preliquidación y Terceros usan el nombre porque guardan una foto por quincena. Acá se guarda un atributo permanente de la tarea.
- **Costo:** el CSV y el histórico de la E2 vienen por nombre. Se traducen a id una sola vez, con el mismo normalizador.

**D4. Una tabla propia, `facturacion_tarea`**, con una fila por cada tarea del campo que tiene algo definido. **Sin fila = Sin definir.**

| Columna | Tipo | Notas |
|---|---|---|
| `id` | `INT AUTO_INCREMENT PRIMARY KEY` | convención de los módulos |
| `tarea_id` | `INT NOT NULL` | id de la tarea en el campo; `UNIQUE KEY uq_facturacion_tarea_tarea_id` |
| `unidad_sugerida` | `VARCHAR(20) NULL` | una de las nueve claves de D5 |
| `no_facturable` | `TINYINT(1) NOT NULL DEFAULT 0` | |
| `actualizado_en` | `DATETIME NOT NULL` | lo pone el modelo con `ahora_utc` (`app/core/models.py`) |
| `actualizado_por` | `INT NULL` | FK a `usuarios(id)` `ON DELETE SET NULL`; NULL = lo cargó el script |

- **Invariante:** cada fila tiene **exactamente una** de las dos cosas. Lo controla el servicio: la base no tiene CHECK, como el resto del esquema. Volver a Sin definir borra la fila.
- **Dos columnas y no una "valor"**, porque son dos conceptos del glosario. La E2 usa las mismas claves de unidad en sus Líneas, donde "No facturable" no existe, y la E3 filtra por `no_facturable`.
- **Si el campo da de baja una tarea, su fila no se borra.** Deja de verse en la lista, y el Cruce de la E3 todavía puede necesitarla para partes viejos.

**D5. Las nueve Unidades de facturación.** Viven en `app/modulos/facturacion/unidades.py`, con espejo en `src/modulos/facturacion/unidades.js` y un test en cada lado que fija las nueve.

| Clave | Etiqueta | Texto en la planilla |
|---|---|---|
| `horas_peon` | Horas de peón | HORAS PEON |
| `horas_tractor` | Horas de tractor | HORAS TRACTOR |
| `plantas` | Plantas | PLANTA |
| `hectareas` | Hectáreas | HECTAREA |
| `tancadas` | Tancadas | TANCADA |
| `bins` | Bins | BINS |
| `bins_c` | Bins C | BINS C |
| `bins_m` | Bins M | BINS M |
| `viajes` | Viajes | VIAJES |

- Las últimas cuatro forman `UNIDADES_COSECHA`.
- En la E1, una tarea con unidad de cosecha cuenta como **con unidad**, no como pendiente. Sacarlas del Cruce y de las Alertas es de la E3.
- "NO FACTURABLE" de la planilla no es una unidad: es la marca.
- En la base va la clave; la etiqueta vive en el código.

**D6. El módulo lee el campo por su cuenta** (`app/modulos/facturacion/services/consulta_externa.py`).
- Su `QUERY_TAREAS` trae id, nombre y el primer segmento de `descripcion` como grupo de tareas. Usa la misma tabla, el mismo filtro de bajas y el mismo orden que la de Preliquidación: el SQL se copia, no se importa.
- Copia también la traducción de `OperationalError` a `ExternaNoDisponible`, con los mismos dos mensajes.
- Suma `normalizar_nombre(nombre) = " ".join((nombre or "").split()).upper()`. Es como `tarea_canonica`, pero colapsa los espacios internos (el CSV trae dobles espacios) y **no** aplica el alias de pago.

**D7. La primera carga.** La lógica pura va en `app/modulos/facturacion/services/primera_carga.py`. El script `scripts/importar_unidades_del_maestro.py` es una cáscara.
- **Lectura:** usa `csv` de la biblioteca estándar, con `utf-8-sig` y `;`. Valida el encabezado `nombre_tarea;grupo_tarea;grupo_factura`.
- **Cruce:** por `normalizar_nombre` contra las tareas activas del campo. **Sólo inserta las tareas que todavía no tienen fila.**
- **Modos y guardias:**
  - simula por defecto y escribe con `--aplicar`;
  - `guardia_base_propia` siempre;
  - con `--aplicar` sobre una base que no sea `testing`, además `--confirmar-base <nombre>`.
- **El informe tiene estas secciones:**
  - a cargar (unidades y No facturables);
  - sin grupo;
  - grupo desconocido;
  - no está entre las activas del campo;
  - nombre ambiguo en el campo;
  - repetida en el CSV con grupos distintos (no se carga ninguna de las dos);
  - ya definidas: no se tocan, y se listan las que el CSV contradice;
  - tareas activas del campo que no están en el CSV.
- **Con el CSV real se espera:** 96 Unidades sugeridas y 38 No facturables, menos lo que no cruce, y 1 tarea sin grupo.

**D8. En el front no se usa nada de Preliquidación** (ver 2.1). El error de carga lo muestra un aviso propio de la pantalla.
- Después de guardar, el caché se actualiza con el ítem que devuelve el PATCH (`setQueryData`), sin volver a leer el campo y sin reordenar.
- Esto se aparta a propósito de la regla 19 de GUIA ("invalidando las queries"): invalidar relee el campo, que es lento, y movería la fila bajo el cursor. El precedente es `Revision.jsx`.

### 2.5 Contrato de la API

El router va en `app/modulos/facturacion/api/tareas.py`, con `APIRouter(prefix="/api/facturacion", tags=["Facturación"])`. Los errores llevan `detail` en español.

**`GET /api/facturacion/tareas`** — pide Ver en `facturacion.unidad`.

Respuesta 200:
```json
[
  {"tarea_id": 123, "nombre": "…", "grupo_tarea": "…",
   "unidad_sugerida": null, "no_facturable": false, "sin_definir": true}
]
```
- Trae todas las tareas activas del campo (`estado <> 9`).
- Orden: primero las `sin_definir`. Dentro de cada grupo, el orden del campo (por nombre).
- `grupo_tarea` puede ser `null`.
- `sin_definir` quiere decir sin Unidad sugerida y sin la marca.

Errores:
- 401 sin sesión.
- 403 "No tenés permiso para esta operación".
- 503 con el mensaje de base de campo no disponible.

**`PATCH /api/facturacion/tareas/{tarea_id}`** — pide Editar en `facturacion.unidad`.

El cuerpo lleva los dos campos, obligatorios: es el estado completo de la tarea.

| Cuerpo | Resultado |
|---|---|
| `{"unidad_sugerida": "<clave>", "no_facturable": false}` | Unidad sugerida |
| `{"unidad_sugerida": null, "no_facturable": true}` | No facturable |
| `{"unidad_sugerida": null, "no_facturable": false}` | vuelve a Sin definir (borra la fila) |

Respuestas:
- **200:** el ítem, con la misma forma que en el GET.
- **422** en tres casos:
  - "Una tarea tiene Unidad sugerida o es No facturable, no las dos.";
  - "Unidad de facturación desconocida: <valor>.";
  - cuerpo mal formado o `tarea_id` que no es un número. Es el 422 de FastAPI, una lista con `msg`, que el front ya lee con `mensajeDeError`.
- **404:** "La tarea no está entre las activas del sistema de campo."
- **401, 403 y 503.** El PATCH valida la tarea contra el campo, así que si el campo no responde tampoco se puede guardar.

Claves válidas de `unidad_sugerida`: `horas_peon`, `horas_tractor`, `plantas`, `hectareas`, `tancadas`, `bins`, `bins_c`, `bins_m`, `viajes`.

## 3. Pasos

Todo se hace en los worktrees `facturacion-e1` de cada repo.
- Los pasos "par" van test rojo primero, implementación después.
- Ningún paso toca `docs/estado.md` ni `docs/BITACORA.md`.
- Los pasos FRENADOS los hace la sesión principal.

### Etapa 0 — Preparación

**0.1 Entorno.**
- **Backend:** un `.env` ficticio en el worktree, armado desde `.env.example` (hosts `.invalid`, claves de prueba, `DB_PROPIA_NAME=testing`). Nunca el `.env` real, ni `DB_PROD_*`, ni `DB_DEV_*`, ni `PERMITIR_BASE_PRODUCCION`.
- **Front:** el junction de `node_modules` ya está creado (`cmd /c mklink /J`). Se quita con `cmd /c rmdir node_modules`, nunca con un borrado recursivo.
- **Verificación:**
  - `python -m pytest -q` en verde, anotando el conteo (referencia: 1137 passed y 1 xfailed en el BK #87);
  - `npm test` en verde y `npm run build` sin errores;
  - `npm run lint` sólo con los 6 errores conocidos de `.claude/hooks/ultimas-entregas.mjs`.

**0.2 FRENADO — pre-check de las bases.**
- Correr `SHOW TABLES LIKE 'facturacion%'` en `testing` y en producción.
- Tiene que dar vacío en las dos: `testing` es compartida y ningún otro sistema puede estar usando el prefijo. Si no da vacío, se frena todo.
- El resultado no se copia al PR.

### Etapa 1 — Backend (PR BK-E1)

**B1. Las unidades (par).**
- **Test:** `tests/facturacion/__init__.py` (vacío) y `tests/facturacion/test_unidades.py`:
  - `UNIDADES` son las nueve claves de D5, en ese orden, y `UNIDADES_COSECHA` son las últimas cuatro;
  - cada unidad tiene su etiqueta en `ETIQUETAS`;
  - `UNIDAD_DE_PLANILLA` traduce los nueve textos de la planilla, y "NO FACTURABLE" no está ahí: es `NO_FACTURABLE_PLANILLA`.
- **Implementación:**
  - `app/modulos/facturacion/__init__.py`, por ahora sólo con el docstring del módulo (el `MODULO` llega en B5);
  - `app/modulos/facturacion/unidades.py`.
- **Verificación:** `python -m pytest tests/facturacion -q`.

**B2. La tabla (par). Zona sensible: `models.py` y `migrations/`.**
- **Test** `tests/facturacion/test_migracion.py`, copiando las partes (c) y (d) de `tests/core/test_migracion_roles.py`:
  - las columnas de cada `CREATE TABLE IF NOT EXISTS` son las del modelo. Se reusan la regex y `NO_SON_COLUMNAS` de ese test, salteando las líneas `--`. El archivo crea sólo `facturacion_tarea`;
  - ninguna línea comentada tiene texto después de un `;`.
- **Test** `tests/facturacion/test_modelo.py`, con SQLite en memoria:
  - una fila nace con `actualizado_en` naive en UTC, como en `tests/core/test_fechas_utc.py`;
  - una segunda fila con el mismo `tarea_id` falla.
- **Implementación:**
  - `app/modulos/facturacion/models.py`: el modelo `TareaFacturacion` sobre `facturacion_tarea` (D4). Importa `Usuario` y `ahora_utc` de `app.core.models`, con el comentario de `app/modulos/terceros/models.py` que explica por qué se importa `Usuario`.
  - `migrations/facturacion/001_unidad_por_tarea.sql`:
    - un encabezado como el de `terceros/007`: `-- facturacion/001 — …` y `-- NO DIFERIBLE: el código de esta versión la lee y la escribe.`;
    - el porqué de "sin fila = Sin definir" y de la clave por id;
    - `CREATE TABLE IF NOT EXISTS … ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;`;
    - la vuelta atrás comentada (`-- DROP TABLE IF EXISTS facturacion_tarea`), **sin `;`**.
  - `migrations/facturacion/LEEME.md`: tres líneas, como `migrations/terceros/LEEME.md`.
  - `migrations/ORDEN.txt`: al final, el comentario `# Facturación (docs/modulos/facturacion/plan-facturacion.md).` y la línea `facturacion/001_unidad_por_tarea.sql`.
- **Verificación:** `python -m pytest tests/facturacion tests/core/test_manifiesto_migraciones.py -q`.

**B3. La lectura del campo (par).**
- **Test** `tests/facturacion/test_consulta_externa.py`:
  - con una sesión falsa (el patrón `SesionFalsa`/`ResultadoFalso` de `tests/terceros/test_consulta_externa.py`), `obtener_tareas()` devuelve `{"tarea_id", "nombre", "grupo_tarea"}` en el orden en que llegan;
  - el SQL trae el id y filtra las bajas. Se verifica con asserts sobre el texto, porque MySQL no corre en SQLite;
  - un `OperationalError` 2013 da `ExternaNoDisponible` con "no respondió", y uno 1045 da "rechazó el acceso" (el patrón de `tests/preliquidacion/test_consulta_externa_timeout.py`);
  - `normalizar_nombre("  tarea   uno ")` da `"TAREA UNO"`, `normalizar_nombre(None)` da `""`, y no se aplica ningún alias.
- **Implementación:** `app/modulos/facturacion/services/__init__.py` y `services/consulta_externa.py`, según D6.
- **Verificación:** `python -m pytest tests/facturacion tests/core/test_arquitectura.py -q`. El test de arquitectura confirma que no se importó nada de Preliquidación.

**B4. La regla de la Unidad de facturación (par).**
- **Test** `tests/facturacion/test_unidad_service.py`, con SQLite en memoria (fixture como `tests/preliquidacion/test_concepto_extra_endpoints.py`) y las tareas del campo como listas:
  1. una tarea sin fila tiene `sin_definir` en true;
  2. con una unidad agrícola, false;
  3. con `bins_c`, false (es el criterio de la E1);
  4. No facturable, false;
  5. las sin definir van primero, y cada grupo conserva el orden del campo;
  6. la fila de una tarea que ya no está activa no aparece en la lista y no se borra;
  7. `definir` crea la fila; cambiar de una unidad a No facturable deja `unidad_sugerida` en NULL; `None, False` borra la fila;
  8. las dos a la vez dan un error con el texto del contrato;
  9. una unidad desconocida da un error que nombra el valor;
  10. una tarea que no está activa da un error de no encontrada;
  11. se guardan `actualizado_por` y `actualizado_en`.
- **Implementación:** `app/modulos/facturacion/services/unidad_service.py`:
  - `UnidadService(db)`, con `listar(tareas_del_campo)` y `definir(tareas_del_campo, tarea_id, unidad_sugerida, no_facturable, usuario_id)`;
  - las excepciones de dominio `DefinicionInvalida` y `TareaNoEncontrada`, al estilo de `TarifaInvalida` de Terceros.
- **Verificación:** `python -m pytest tests/facturacion -q`.

**B5. Permisos, API y registro (par). Zona sensible: `permisos.py`.**
- **Test** `tests/facturacion/test_registro_y_permisos.py`:
  - `MODULO.clave == "facturacion"` y el módulo está activo;
  - `CATALOGO_FACTURACION` (las seis de D1, con nombre y editable) es igual a las `PANTALLAS`, y ninguna tiene `requiere`;
  - `/api/auth/modulos`, como admin, publica las seis en orden. Se llama con `TestClient(app)` sin `with`, como en `tests/core/test_registro_modulos.py`.
- **Test** `tests/facturacion/test_mapa_permisos.py`: una copia de `tests/terceros/test_mapa_permisos.py` con:
  - `PREFIJO = "/api/facturacion"`;
  - `ESPERADO` con las dos rutas: `GET /api/facturacion/tareas` con Ver en `unidad` y `PATCH /api/facturacion/tareas/{tarea_id}` con Editar en `unidad`;
  - `test_la_tabla_tiene_las_2_rutas`.
- **Test** `tests/facturacion/test_tareas_endpoints.py`:
  - **Montaje:** usa `app.main.app`, para que actúe el handler del 503. Tiene overrides de `get_db_propia` (SQLite), del `get_consulta_externa` del módulo (uno falso) y de `get_usuario_actual`, y los limpia al terminar.
  - **Rol de prueba:** es local; `tests/roles_de_prueba.py` no se toca, porque su `SEMILLA` la fija `core/002`.
    ```python
    SimpleNamespace(id=1, nombre="Contadora", email="c@t.com", rol="usuario", activo=True,
        roles=[SimpleNamespace(nombre="Contadora de prueba",
            permisos=[SimpleNamespace(modulo="facturacion", pantalla="unidad", nivel="editar")])])
    ```
  - **Casos:**
    - con Ver: GET da 200 con las sin definir primero, y PATCH da 403;
    - con Editar: PATCH da 200 con el ítem; 422 por las dos a la vez; 422 por unidad desconocida; 404 por tarea inactiva; `{null, false}` da 200 con `sin_definir` en true; un cuerpo al que le falta un campo da 422;
    - el Preliquidador de la semilla (`rol_de_semilla("Preliquidador")`): GET da 403;
    - con el campo caído (el falso levanta `ExternaNoDisponible`), GET y PATCH dan 503 con el mensaje.
- **Tests del núcleo** (`tests/core/test_registro_modulos.py`):
  - el conjunto de módulos pasa a ser los tres, y el test cambia de nombre porque ya no son "los dos";
  - en el test del núcleo que revisa imports se suma `assert "app.modulos.facturacion" not in contenido`;
  - *(agregado en la ejecución)* `tests/core/test_administracion_roles.py` usaba `"facturacion"` como ejemplo de módulo fuera del catálogo (líneas 157, 164 y 250). Al registrarse el módulo, ese ejemplo deja de valer: se cambia por `"inexistente"`, para que los dos tests sigan probando lo mismo.
- **Implementación:**
  - `app/modulos/facturacion/permisos.py`: `MODULO`, `PANTALLAS` (D1), `ver_unidad` y `editar_unidad`. Las otras cinco pantallas no tienen dependencia hasta su etapa.
  - `app/modulos/facturacion/schemas.py` (regla 16): `TareaFacturacionOut` y `DefinirTareaIn`. Los dos campos son obligatorios: `unidad_sugerida: Optional[str]` sin default y `no_facturable: bool`. La regla vive en el servicio y no en Pydantic, para que la compartan la API y el script.
  - `app/modulos/facturacion/api/__init__.py` y `api/tareas.py`:
    - los getters `get_consulta_externa(db_externa=Depends(get_db_externa))` y `get_unidades(db_propia=Depends(get_db_propia))`, como en `app/modulos/terceros/api/terceros.py`;
    - el GET con `dependencies=[Depends(ver_unidad)]`;
    - el PATCH con `usuario=Depends(editar_unidad)`;
    - `DefinicionInvalida` se traduce a 422 y `TareaNoEncontrada` a 404. `ExternaNoDisponible` sigue de largo hasta el handler global.
  - `app/modulos/facturacion/__init__.py`, como `app/modulos/terceros/__init__.py`:
    ```python
    MODULO = ModuloInfo(clave="facturacion", nombre="Facturación", descripcion=…,
        activo=True, routers=(tareas.router,), panel_gerencial=False,
        modelos="app.modulos.facturacion.models", pantallas=PANTALLAS)
    ```
  - `app/modulos/__init__.py`: el import y `REGISTRO = (PRELIQUIDACION, TERCEROS, FACTURACION)`. Es el único cambio fuera del módulo, además de los tests del núcleo.
- **Verificación:**
  - `python -m pytest tests/facturacion tests/core -q`;
  - después, la suite completa con `python -m pytest -q`: el conteo de 0.1 más los tests nuevos, sin fallas;
  - `tests/core/test_endpoints_con_permiso.py` tiene que pasar sin cambios.

**B6. La primera carga (par).**
- **Test** `tests/facturacion/test_primera_carga.py`: lógica pura, con un CSV ficticio escrito en `tmp_path` que trae BOM, dobles espacios, espacio final y minúsculas.
  - lee el formato, y rechaza otro encabezado con un error claro;
  - cruza por `normalizar_nombre` de los dos lados;
  - traduce los nueve textos y NO FACTURABLE; BINS y BINS C quedan como Unidad sugerida;
  - cada sección del informe de D7 tiene su caso;
  - lo que ya tiene fila no se toca, y lo que se carga va con `actualizado_por` en NULL;
  - planificar de nuevo después de aplicar da 0 a cargar.
- **Test** `tests/facturacion/test_script_primera_carga.py`: prueba `main(argv)` con el patrón de `tests/core/test_scripts_usuarios.py`, reemplazando con monkeypatch `SessionPropia`, la lectura del campo y `settings.db_propia_name`.
  - sin `--aplicar` no escribe;
  - con `--aplicar` escribe;
  - con un archivo que no existe, sale con 1 y dice que el CSV vive en `docs/modulos/facturacion/fuentes/`, fuera de git;
  - con `--aplicar` sobre una base que no es `testing` y sin `--confirmar-base` con ese nombre, no escribe y sale distinto de 0;
  - si `guardia_base_propia` frena, no conecta.
- **Implementación:**
  - `app/modulos/facturacion/services/primera_carga.py`: `leer_maestro(ruta)`, `planificar(filas, tareas_del_campo, definidas)` y `aplicar(db, plan)`.
  - `scripts/importar_unidades_del_maestro.py`:
    - un docstring de uso: `--csv <ruta>` obligatorio, `--aplicar` y `--confirmar-base <nombre>`;
    - el `sys.path.insert` de `scripts/importar_tarifas_del_excel.py`;
    - `construir_parser()` y `main(argv) -> int`;
    - imprime el informe con conteos;
    - no puede contener los identificadores de la regex de `tests/core/test_scripts_usuarios.py`.
- **Verificación:** `python -m pytest tests/facturacion tests/core/test_scripts_usuarios.py -q`.

**B7. `refrescar_testing.py` (suelto).**
- En `scripts/refrescar_testing.py`, sumar `"facturacion_tarea"` al final de `TABLAS`, como pide GUIA-MODULOS §6.2.
- Reescribir el comentario viejo de `TABLAS`, que todavía dice que Terceros es un molde sin migraciones.
- No pisa la carga de `testing`: antes del deploy la tabla no existe en producción, y el script saltea lo que no existe en el origen.
- **Verificación:** `python -m pytest tests/core/test_refrescar_testing.py -q`.

**B8. Docs del módulo (suelto).**
- Corregir `docs/modulos/facturacion/plan-facturacion.md` (sección 6) y `pantallas.md` ("Dirección") para que digan:
  - la barra de filtros, las tablas, el aviso de error y el estado por pantalla son de Preliquidación, y usarlos pide antes un PR del núcleo;
  - las clases globales, el overlay y `CargandoContenido` sí son del núcleo.
- **Verificación:** `git diff --stat` muestra sólo esos dos archivos de docs.

### Etapa 2 — Frontend (PR FT-E1)

**F1. `PRODUCT.md` (suelto, con impeccable).**
- Se corre `/impeccable init` sobre el `PRODUCT.md` que ya existe, en modo actualización (`reference/init.md`).
- La fuente son `CONTEXT-facturacion.md` y `pantallas.md` del backend. Se suman:
  - las contadoras como usuarias: personal administrativo, en PC de escritorio, que necesita señales claras;
  - para qué es el módulo, y que trabaja sobre meses cerrados;
  - su vocabulario: Comprobante, Línea de comprobante, Unidad de facturación, Unidad sugerida, No facturable, Cruce, Alerta;
  - que el sistema pasa a tener tres módulos.
- Sin nombres de clientes ni cantidades que no estén en los docs.
- Si `init` pregunta algo que los docs no contestan, el paso queda FRENADO hasta que la sesión principal le pregunte al usuario.
- **Verificación:** el diff conserva el esquema del archivo y no tiene emojis ni datos de terceros.

**F2. Las unidades del front (par).**
- **Test** `src/modulos/facturacion/unidades.test.js`, con `node:test` como `src/core/accesos.test.js`:
  - las nueve claves y etiquetas en el orden de D5, y las cuatro de cosecha;
  - `valorDeTarea(tarea)` y `cuerpoDesdeValor(valor)` van y vuelven para Sin definir, una unidad agrícola, una de cosecha y No facturable;
  - `etiquetaDe(tarea)`;
  - `filtrarTareas(tareas, { texto, soloSinDefinir })` busca por nombre o por grupo de tareas sin distinguir mayúsculas, como `filtrarLineas.js`;
  - `contarSinDefinir(tareas)`.
- En `package.json`, sumar `"src/modulos/facturacion/*.test.js"` al script `test`.
- **Implementación:** `src/modulos/facturacion/unidades.js`, sin imports, para que lo cargue `node --test`.
- **Verificación:** `npm test`.

**F3. Servicio y registro (suelto: no tiene lógica).**
- `src/modulos/facturacion/services/facturacion.js`: `listarTareas()` y `definirTarea(tareaId, cuerpo)`, por `src/core/api.js`, con el patrón de `src/modulos/terceros/services/terceros.js`.
- `src/modulos/facturacion/rutas.jsx`, con el patrón de `src/modulos/terceros/rutas.jsx`:
  - una sola ruta, `/facturacion/unidad`, con `pantalla: 'unidad'`, label "Unidad de medida por defecto" y `menu: true`;
  - `nav` derivado, `redirecciones = []` y su entrada en `pantallas` para el asistente;
  - el descriptor con un `icono` que ya exista, `activo: true` y `gerencial: null`;
  - un comentario que diga por qué las otras cinco pantallas todavía no tienen ruta.
- `src/modulos/registro.js`: el import y `TODOS = [preliquidacion, terceros, facturacion]`.
- **Verificación:** `npm run build`, `npm run lint` sin errores nuevos y `npm test`. `accesos.test.js` no cambia, porque usa descriptores falsos.

**F4. La pantalla Unidad de medida por defecto (visual, con impeccable).**
- **Antes de editar:**
  - correr `.claude/skills/impeccable/scripts/impeccable.cmd context --target src/modulos/facturacion/pages/UnidadFacturacion.jsx`;
  - seguir el playbook `reference/new-work.md` (una superficie nueva dentro del mundo actual, que se preserva), en modo Operate (`reference/operate.md`);
  - leer `reference/craft-floor.md`;
  - tomar como brief las secciones "Unidad de medida por defecto", "Estados y volúmenes" y "Límites" de `pantallas.md` del backend;
  - si el lanzador no anda, seguir "Launcher unavailable" del `SKILL.md`.
- **Archivos:** `src/modulos/facturacion/pages/UnidadFacturacion.jsx` y `UnidadFacturacion.module.css`, con los tokens de `src/index.css`.
- **Comportamiento fijo** (el diseño lo resuelve impeccable dentro de esto):
  - **Carga:** `useQuery` de `listarTareas`, con `CargandoContenido` y un texto que diga que se está leyendo el sistema de campo.
  - **Error:** si la carga falla (503 u otro), un aviso propio con el `detail` (`mensajeDeError`, de `src/core/mensajeError.js`) y un botón "Reintentar".
  - **Tabla:** con `.table-wrap` y las columnas Tarea, Grupo de tareas y Unidad de facturación.
  - **Edición:**
    - con Editar (`puedeEditar(usuario, 'facturacion', 'unidad')`), un `select.input` por fila con Sin definir, las cinco agrícolas, un grupo "Cosecha" con las cuatro, y No facturable;
    - con sólo Ver, el texto.
  - **Lo que falta:** las sin definir llevan una marca que no sea sólo color (como `.filaSinCategoria` de `CategoriasOperarios`, más el texto "Sin definir"), y arriba va un resumen "N tareas sin definir".
  - **Filtros:** búsqueda (`.input`) y un chip "Sólo sin definir" (`.chip`/`.chip-active`). Con el chip activo, una tarea recién definida sale de la vista: es lo esperable en una cola de trabajo, y la crítica lo puede revisar.
  - **Guardado:** con `useMutation(definirTarea)`. El overlay "Procesando…" sale solo, va `toast.success` o `toast.error`, y el caché se actualiza con `setQueryData` y el ítem devuelto (D8).
  - Textos en español, sin emojis.
- **Verificación:**
  - `npm run build`, `npm run lint` y `npm test`;
  - en el navegador, en S3;
  - en la revisión, `/impeccable critique` y `/impeccable audit` sobre `src/modulos/facturacion/pages/UnidadFacturacion.jsx`, que cubren también la tarjeta del Inicio y la entrada de menú;
  - sin `polish`, porque no cambia la estética.

### Etapa 3 — FRENADOS (sesión principal)

**S1.** Es el pre-check de 0.2.

**S2. DDL en `testing`**, antes de mergear BK-E1.
- Aplicar `migrations/facturacion/001_unidad_por_tarea.sql` con el aplicador del paso 1.4 de `docs/superpowers/plans/2026-10-09-esquema-permisos.md`:
  - `assert os.environ["DB_PROPIA_NAME"] == "testing"`;
  - las variables reales van al proceso sin pasar por el `.env` del worktree, que sigue siendo el ficticio.
- **Verificación:**
  - `SHOW CREATE TABLE facturacion_tarea` coincide con el archivo;
  - el backend de la rama, levantado contra `testing`, imprime "Tablas y columnas BD propia: verificadas";
  - `/health` no da `"error"`.

**S3. Smoke contra `testing`.**
- **API, como admin:**
  - `GET /api/facturacion/tareas` trae las tareas activas: unas 135, todas sin definir;
  - un PATCH a una tarea, y otro que la vuelve a Sin definir, la dejan como estaba.
- **Navegador**, con el front de la rama (`npm run dev`) y el backend de la rama:
  - el admin ve la tarjeta y el menú;
  - la pantalla carga con el indicador, guarda con overlay y toast, y la fila no salta;
  - el editor de roles de Administración muestra las seis pantallas;
  - **modo Ver:** se prueba con un rol temporal con `unidad: ver` sobre un usuario de prueba de `testing`, y después se borran los dos. Si no hay usuario de prueba, se anota que el modo Ver sólo quedó cubierto por los tests.

**S4. Primera carga en `testing`**, antes de mergear BK-E1: si aparece un error del script, se arregla en el mismo PR.
1. Desde el worktree, con las variables apuntando a `testing`, correr `python scripts/importar_unidades_del_maestro.py --csv "<checkout principal>/docs/modulos/facturacion/fuentes/maestro-tareas.csv"`.
2. Revisar el informe con el usuario. Las listas tienen nombres de tareas: se ven en la sesión y no se pegan en el PR.
3. Correr con `--aplicar`.
4. Simular de nuevo: tiene que dar 0 a cargar.
5. En la pantalla, las sin definir tienen que ser la tarea sin grupo, las que no cruzaron y las del campo que no están en el CSV.

**S5. Deploy de BK-E1 y FT-E1 juntos, sólo con OK del usuario.**
1. Respaldo de la base de producción fuera del repo, como dice `docs/DEPLOY.md`. La migración sólo crea una tabla nueva y no toca datos, pero el respaldo va igual.
2. Aplicar `facturacion/001` en producción **antes** de reiniciar: el código viejo ignora la tabla.
3. `git pull` y reinicio. El banner tiene que decir "verificadas" y `/health` tiene que dar `ok`.
4. Build del front y swap de carpeta.
5. Smoke sin escribir:
   - `/api/auth/modulos` publica Facturación con sus seis pantallas;
   - el admin ve la tarjeta y la lista carga;
   - el editor de roles muestra las seis.

**Vuelta atrás**, escrita antes de empezar:
- volver a la carpeta anterior del front;
- en el backend, `git checkout` del commit anterior y reinicio;
- `DROP TABLE IF EXISTS facturacion_tarea`, sólo si se revierte la etapa entera. El código viejo convive con la tabla, así que puede quedar.

**S6. Primera carga en producción**, con OK y después de S5.
- En el VPS, con el CSV copiado a una carpeta temporal fuera del repo:
  1. simular con `--confirmar-base preliquidacion`;
  2. revisar el informe;
  3. correr con `--aplicar`;
  4. volver a simular: tiene que dar 0;
  5. borrar el CSV.
- **Vuelta atrás de la carga:** `DELETE FROM facturacion_tarea WHERE actualizado_por IS NULL`. Borra sólo lo que puso el script y nadie tocó después.
- **Queda para el usuario:**
  - armar en Administración el rol de las contadoras, con Editar en `unidad`;
  - completar las tareas que quedaron sin definir.

### 3.5 Corte en PRs y orden de merge

- **BK-E1 (backend):** pasos B1 a B8. Se mergea después de S2 y S4.
  - Lleva dos rondas de revisión por zona sensible: el `permisos.py` del módulo, `models.py` y `migrations/`.
  - Antes de abrir el PR, `python -m pytest -q` en verde (regla 24).
- **FT-E1 (front):** pasos F1 a F4.
  - Se desarrolla en paralelo, contra el contrato de 2.5.
  - Se mergea **después** de BK-E1: el admin ve la tarjeta apenas el front registra el módulo, y sin el backend la pantalla da 404.
  - Antes de abrir el PR: `npm run build`, `npm run lint` y `npm test`.
- **Deploy:** los dos juntos (S5). La carga de producción va después (S6), con su propio OK.
- **Commits:** `feat(facturacion): …`, `test(facturacion): …` y `docs(facturacion): …`. El porqué de la clave por id, de las pantallas sin ruta y del `setQueryData` va en el cuerpo de cada PR.

### 3.6 Lo que consume la E2

**Desde BK-E1**
- **La tabla y su regla:** `facturacion_tarea` y `TareaFacturacion`. Sin fila = Sin definir; una fila tiene Unidad sugerida o No facturable, nunca las dos.
- **Las unidades** (`app/modulos/facturacion/unidades.py`):
  - `UNIDADES`, `UNIDADES_COSECHA` y `ETIQUETAS` son el vocabulario de la Unidad de facturación de cada Línea;
  - `UNIDAD_DE_PLANILLA` y `NO_FACTURABLE_PLANILLA` traducen la columna UM de la hoja de facturación (BINS M y VIAJES ya están).
- **La clave de la tarea en las Líneas:** `tarea_id`, el id del campo.
- **El maestro del campo:** `ConsultaExternaService.obtener_tareas()` y `normalizar_nombre()`, en `app/modulos/facturacion/services/consulta_externa.py`. Sirven para traducir a id los nombres del histórico.
- **Los permisos:**
  - `MODULO` y `PANTALLAS`, con las seis ya declaradas: la E2 no las vuelve a declarar;
  - la convención `ver_x`/`editar_x`: la E2 define `ver_comprobantes` y `editar_comprobantes`;
  - si Comprobantes necesita la lista de tareas para precargar la Línea, puede ampliar el GET con una dependencia nueva, `requiere_pantalla(MODULO, "unidad", "comprobantes")`, y actualizar el mapa de permisos.
- **El registro y las migraciones:** la E2 suma su router a `routers` en `app/modulos/facturacion/__init__.py`. Sus migraciones arrancan en `facturacion/002_…`, debajo de la línea de la E1 en `ORDEN.txt`.
- **El orden de las ramas:** la E2 se ramifica de `main` después del merge de BK-E1, o rebasea. Las dos tocan `permisos.py`, `__init__.py`, `ORDEN.txt` y `tests/facturacion/test_mapa_permisos.py`.

**Desde FT-E1**
- `src/modulos/facturacion/unidades.js`, `services/facturacion.js` y `rutas.jsx`.
  - Las rutas nuevas se insertan en el orden de las pantallas, para que Pendientes quede primera cuando exista.
  - `homeDeModulo` aterriza en la primera entrada visible del menú.
- `PRODUCT.md` ya con las contadoras.

**Antes de su front:** si la E2 quiere la barra de filtros, las tablas o el estado por pantalla de Preliquidación, hace falta un PR del núcleo que los suba a `src/core/` (ver 2.1).

### 3.7 Pasos agregados en la revisión (2026-10-11)

La revisión dio 0 urgent y 0 high. Estos pasos los pidió el usuario: tres minor del front y
el caso de dos contadoras cargando a la vez. Regla decidida por el usuario para esta
pantalla: **gana la última que guarda**, sin error y sin aviso de conflicto. El control
fuerte se diseña en la E2, para los comprobantes.

**Paso R1 (backend): dos PATCH a la vez no dan 500.**
- *Escenario de falla:* dos personas definen al mismo tiempo una tarea Sin definir. Las dos
  ven que no tiene fila y la insertan. El UNIQUE frena a la segunda con `IntegrityError` y
  esa persona recibe un 500. Pasa lo mismo si una la deja Sin definir (borra la fila)
  mientras la otra la cambia: el UPDATE no encuentra la fila (`StaleDataError`).
- *Arreglo:* en `UnidadService.definir`, si el commit falla por eso, `rollback` y se vuelve
  a hacer la escritura una vez sobre lo que haya en la base. Así gana la última, sin 500.
- *Par:* un test que simula la fila creada por otra sesión entre la lectura y el commit (rojo
  con 500 o excepción, verde con el valor nuevo guardado). Archivos:
  `services/unidad_service.py` y su test.

**Paso R2 (front): tres minor de la pantalla y la lista al día.**
1. *El select guarda cada opción que se recorre con las flechas.* Con el teclado, el cambio
   queda pendiente en la fila y se guarda al salir del select (blur) o con Enter. Con el
   mouse se guarda al elegir, como ahora. El overlay no tapa el foco.
2. *El foco no se ve en las filas Sin definir.* Un anillo `:focus-visible` propio del
   módulo con `--accent`, sin tocar `.input` del núcleo.
3. *Con "Sólo sin definir" activo, el foco cae al `<body>` al guardar.* La fila sigue
   saliendo de la vista, como dice F4, y el foco pasa al select de la fila que queda en su
   lugar (la siguiente; si era la última, la anterior; si no queda ninguna, el chip).
4. *La lista al día con dos personas:* la consulta de esta pantalla vuelve a leer al volver
   a la pestaña (`refetchOnWindowFocus: true` sólo en ella; el núcleo lo apaga para todo).
- Archivos: `pages/UnidadFacturacion.jsx` y `.module.css`. Verificación: `npm test`,
  `npm run build`, `npm run lint` y un control en el navegador contra `testing`.

## 4. Riesgos

| Riesgo | Qué se toca / qué se rompe | Mitigación |
|---|---|---|
| **DDL en `testing` y en producción (riesgo alto: cambio de esquema)** | Crea una tabla nueva sin tocar datos existentes. `testing` es compartida | Pre-check 0.2; `CREATE TABLE IF NOT EXISTS`; sólo nuestra tabla; respaldo antes en producción; vuelta atrás escrita (S5) |
| Backend reiniciado sin la migración | El banner da `ERROR: faltan tablas`, `/health` da `"error"` y los endpoints de Facturación fallan con 500. El resto del sistema anda | Migración antes del reinicio (S5, punto 2); mirar el banner |
| Front deployado o mergeado antes que el backend | El admin ve la tarjeta y la pantalla da 404 | Orden de merge de 3.5; deploy conjunto |
| Claves de pantalla o nombre de tabla mal elegidos | En la práctica no se pueden cambiar: `rol_permiso` guarda las claves, y las tablas no se renombran (ADR-0013) | Confirmarlos antes de mergear BK-E1 (preguntas 1 y 2) |
| Cambios en el maestro del campo | Un renombre conserva el id y la unidad. Una baja con alta nueva da otro id, y la tarea vuelve a Sin definir (queda arriba, visible). Si el campo reciclara ids, una tarea heredaría la unidad de otra; desde el repo no se puede verificar | Clave por id (D3); la pantalla muestra primero lo pendiente; si aparece un caso de id reciclado, se le pregunta a quien administra el campo |
| Nombres que no cruzan en la carga (tildes, typos, dobles espacios, repetidos) | Esas tareas quedan Sin definir | Normalización de D6; informe por secciones; se completan a mano en la pantalla |
| El script escribe en producción | Inserta filas en `facturacion_tarea` | Simula por defecto; `guardia_base_propia`; `--confirmar-base`; sólo completa lo vacío; corre en el VPS con OK; vuelta atrás por `actualizado_por IS NULL` (S6) |
| CSV con otro formato o codificación | El script no lo lee | Valida el encabezado y sale con un error claro; por lo que se vio, el archivo actual es UTF-8 |
| CSV en el VPS | Datos de la empresa fuera del repo | Carpeta temporal fuera del repo, que se borra al terminar; nunca va a git |
| Campo caído o lento | GET y PATCH dan 503 | Mensaje del handler global; indicador de carga y "Reintentar". El PATCH valida contra el campo a propósito, para no crear filas de ids que no existen |
| Pantallas declaradas sin construir | Un rol que sólo tiene esas deja a la persona sin tarjeta; si es su único permiso, no entra | D2; el cuerpo del PR lo dice; nadie tiene permisos de Facturación hasta que el usuario arme el rol |
| Ramas paralelas E1 y E2 | Conflictos en `permisos.py`, `__init__.py`, `ORDEN.txt` y el test de mapa | 3.6: la E2 parte de `main` después de BK-E1 |
| Traducción de errores del campo copiada | Dos copias que pueden divergir | Pregunta 6 |
| Dos personas editan la misma tarea | Gana la última | Aceptado: son pocas personas y el dato se corrige en la misma pantalla |

## 5. Preguntas abiertas

1. **Las claves de las seis pantallas** (`pendientes`, `cruce`, `comprobantes`, `unidad`, `equivalencias`, `panel`). Se guardan en la base y no cambian.
   - *Si nadie contesta:* estas, confirmadas antes de mergear BK-E1.
2. **El nombre de la tabla (`facturacion_tarea`) y del script (`importar_unidades_del_maestro.py`).**
   - *Si nadie contesta:* estos.
3. **El ícono de Facturación.** Uno propio sería un PR del núcleo aparte.
   - *Si nadie contesta:* `conceptos` para la tarjeta y `mantenimiento` para la entrada de menú, a confirmar en la crítica de F4.
4. **Quién completa lo que la carga deja sin definir:** la tarea sin grupo, lo que no cruce y las tareas del campo que no están en el CSV.
   - *Si nadie contesta:* el usuario o las contadoras, desde la pantalla, después del deploy. Va a los pendientes del usuario.
5. **¿El `grupo_factura` que el campo ya guarda en la descripción de cada tarea es el mismo dato que el CSV?** `QUERY_TAREAS` de Preliquidación lo lee y nadie lo usa. Si lo es, la carga podría salir del campo por id, sin cruzar nombres.
   - *Si nadie contesta:* se sigue con el CSV, como se decidió; en S4 se puede comparar a mano.
6. **Subir al núcleo la traducción de errores del campo.** Desde esta etapa la tienen dos módulos.
   - *Si nadie contesta:* se copia en la E1, y el PR del núcleo queda en "A futuro".
7. **Quién corre la carga en producción y cómo llega el CSV al VPS.**
   - *Si nadie contesta:* la sesión principal, con OK, como en S6.

## 6. Fuera de alcance

**Lo que llega en otras etapas**
- El Umbral de diferencia y el Mes de corte (E3).
- Las pantallas Pendientes, Cruce, Comprobantes, Equivalencias y Panel, con sus endpoints, rutas y dependencias.
- El importador de órdenes, los Adjuntos y el histórico (E2).
- Sacar las unidades de cosecha del Cruce y de las Alertas (E3). La E1 sólo las guarda.

**Lo que no se hace**
- Una tercera marca para la cosecha: está descartada.
- Mover `FiltrosBar`, `TablaOrdenable`, `AvisoError` y `estadoPantallas` al núcleo.
- Un ícono propio.
- `AYUDA-facturacion.md` (regla 28), y que el asistente lea docs de Facturación: `app/core/asistente.py` sólo carga los de Preliquidación.
- Subir al núcleo la traducción de errores del campo.
- Sumar las tablas `terceros_*` a `refrescar_testing.py`.
- Crear roles por migración.
- Tests e2e: Playwright sería una dependencia nueva.
- Cualquier cambio en Preliquidación o en Terceros.
- Tocar `docs/estado.md` y `docs/BITACORA.md` en la rama.
