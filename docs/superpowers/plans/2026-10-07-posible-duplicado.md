# Plan: alerta "Posible duplicado" en la línea (backend + frontend)

Skill `flujo-preliquidacion`, carril completo (DDL, cambio de contrato de API, dos repos).
Zonas sensibles tocadas: `motor_reglas.py`, `preliquidacion_service.py`, `models.py`,
`migrations/` → dos rondas de revisión.

- `BK` = `backend_preliquidacion/.claude/worktrees/posible-duplicado` (rama `feature/posible-duplicado`, desde 122f4c4)
- `FT` = `frontend_preliquidacion/.claude/worktrees/posible-duplicado` (rama `feature/posible-duplicado`, desde cb83181; `node_modules` es un junction al checkout principal: nunca borrarlo recursivo, se quita con `cmd /c rmdir node_modules`)

Las rutas de abajo son relativas a cada worktree.

## Decisiones cerradas (entrevista con Gero, 2026-10-07)

1. **Criterio**: una línea es posible duplicado si existe otra de la misma preliquidación
   igual en planilla, fecha, legajo, empleado, tarea, cliente, finca, tractor, unidades y
   tancadas (misma normalización que `detectar_duplicados`), con unidades > 0 o tancadas > 0,
   y con horas distintas (jornal o máquina). Porqué de la cantidad > 0: sin el filtro, en
   `testing` salen 86 pares en 5 quincenas, casi todos tareas por hora que son trabajo real;
   con el filtro, sólo los 2 pares del caso que originó la tarea.
2. **Excluyente con Duplicado**: una línea con `es_duplicado` no lleva además la marca nueva.
3. **Columna `es_posible_duplicado`**, mismo ciclo que `es_duplicado` (generar y actualizar).
4. **Migración `ws18`** que agrega la columna y la llena para todas las quincenas existentes.
5. **Revisión**: badge amarillo "POSIBLE DUPLICADO", segundo en precedencia (DUPLICADO →
   POSIBLE DUPLICADO → INCOMPLETA → LEGAJO → EMPRESA), opción en el filtro de alertas,
   contador propio en el banner, entra en "sólo alertas", aviso en el panel de la línea.
6. **Verificación**: sección "Posibles duplicados" con el diseño actual (la refacción completa
   de UX/UI viene después de esta tarea): tarjeta por persona + día + grupo, importe en duda a
   la derecha, detalle con hs máquina e importe.
7. **Mensaje** de generar/actualizar con "· N posibles duplicados".
8. **No cambian** el Excel de exportación a sueldos ni la pantalla de Inicio. Sin descarte.
9. **Glosario** con "Línea duplicada" y "Posible duplicado" (texto en el paso A7). Sin ADR.
10. `docs/estado.md` no se toca en el plan: lo edita la sesión principal en `main`.

---

## 1. Qué encontré en el código

### Premisas del briefing que no coinciden con el código

1. **Verificación no consume `dashboard_verificacion`.** `src/modulos/preliquidacion/pages/Verificacion.jsx`
   calcula horas/tancadas/plantas/resumen en cliente a partir de `listarLineas`
   (`calcularExcesos` :23-53, `calcularResumenEmpleados` :55-83) sobre `lineasFiltradas`
   (:130-139), que ya excluye mensualizados (:125-128) y aplica los filtros de `FiltrosBar`;
   la búsqueda se aplica después (`filtrarBusqueda` :89-93, :169-172). Ningún archivo del
   front llama a `GET /{id}/dashboard-verificacion`, y ese endpoint no excluye mensualizados.
   Por eso la sección nueva se calcula en el front (B2), como las otras cinco.
2. **`solo_alertas` vive en dos lugares**: el backend lo filtra en `listar_lineas`
   (`preliquidacion_service.py:1398-1403`), pero el front no manda el parámetro y replica la
   condición en cliente (`Revision.jsx:475`). Se tocan los dos.
3. **La columna real `es_duplicado` es `tinyint(1) DEFAULT NULL`**
   (`migrations/preliquidacion/000_esquema_base.sql:69`). La nueva va `NOT NULL DEFAULT 0`.
4. **`AlertasBanner` no tiene prop para posibles** (`components/AlertasBanner.jsx:1-27`).
5. **`estadisticas` cuenta `lineas_con_alerta` como OR de tres flags**
   (`preliquidacion_service.py:1776-1782`) y ese número llega al topbar de Revisión y al
   badge "alertas" de Inicio (`pages/Dashboard.jsx:117-118`). Sumar la flag nueva al OR sube
   ese número sin tocar código de Inicio.
6. **`tests/preliquidacion/test_generar_api.py:25-26`**: el `ServiceFake.estadisticas` no
   trae `posibles_duplicados`; con el mensaje nuevo esos tests dan 500 si no se actualiza.

### Lo que existe y sirve

- `normalizar_decimal` (`motor_reglas.py:6-23`); `_n` en el service es un alias (:69).
  `detectar_duplicados` (`motor_reglas.py:118-142`) arma la clave con `.strip().upper()` en
  nombres, `.strip()` en legajo, `str()` en fecha y `norm()` en los 4 numéricos.
- `generar` (`preliquidacion_service.py:134-191`): `detectar_duplicados(filas)` (:150) y
  `_procesar_fila_con_cache(..., es_duplicado=...)` (:155-162). `actualizar_quincena` hace lo
  mismo con `filas_nuevas` (:271-286) y después `_recalcular_flags_duplicado` (:312-313, sólo
  si hubo altas o bajas). `_procesar_fila_con_cache`: firma :486-495, setea `es_duplicado` :565.
- `_recalcular_flags_duplicado` (:319-338) arma dicts desde las líneas y reaplica el motor.
- `estadisticas` (:1771-1797) y `estadisticas_batch` (:1815-1875): conteos SQL;
  `test_estadisticas_sql.py:79-91` fija el dict exacto de una quincena vacía y :94-113 que
  batch == individual.
- `listar_lineas` (:1387-1410); `test_lineas_service.py:112-123` fija qué entra en `solo_alertas`.
- `export_service.py:76-96` enumera columnas explícitas: la columna nueva no cambia el Excel.
- Modelo: `models.py:169-173`. Esquema de tests: `Base.metadata.create_all` sobre SQLite.
- Migraciones: cabecera estilo `ws16_valor_hora_tractorista.sql`; `ws17` trae comprobación
  y rollback; `ws3_completitud_unica.sql` es el precedente de `ADD COLUMN` + backfill.
  `tests/core/test_manifiesto_migraciones.py` exige cada `.sql` en `ORDEN.txt`.
- Arranque (`app/main.py:79-94`): sin la columna, todo SELECT sobre `preliquidacion_linea`
  falla con "Unknown column". La migración es NO DIFERIBLE.
- `scripts/refrescar_testing.py:127` recrea las tablas de `testing` con el esquema de
  producción: pisa la columna nueva en `testing` mientras producción no la tenga.
- Front, Revisión: `pages/ordenarLineas.js:16-24` (`PRECEDENCIA_ALERTAS`, `alertaDe`),
  `Revision.jsx:31-36` (`BADGE_ALERTA`), :466-475 (filtros y `solo_alertas`), :573-578
  (`claseLinea`), :609-625 (banners), `components/FiltrosBar.jsx:3-8` y :169-177,
  `components/PanelLinea.jsx:188-195`.
- Front, Verificación: `SECCIONES` :14-21, nav con contador :214-238, contenido :243-251,
  `ListaExceso` :260-301, grillas en `Verificacion.module.css:171-196`.
- Tests del front: `node --test` sobre `pages/*.test.js`; la convención es lógica pura en
  `pages/*.js` sin React con su `*.test.js` al lado. Los componentes React se verifican con
  `npm run lint`, `npm run build` y smoke en el navegador.

### Entorno del ejecutor

- Backend: no hay venv; se usa el `python` global de la máquina (no crear venv). Para
  tests, `.env` ficticio en el worktree a partir de `.env.example` (todos los
  `DB_*_HOST=db.invalid`, `DB_*_PASSWORD=x`, `SECRET_KEY=clave-de-prueba`,
  `DB_PROPIA_NAME=testing`), confirmando antes que `.env` está en `.gitignore`. Nunca copiar
  el `.env` real; nunca `DB_PROD_*` ni `PERMITIR_BASE_PRODUCCION`. Comando:
  `python -m pytest -q` (la ruta tiene espacios: entre comillas).
- Frontend: `npm test`, `npm run lint`, `npm run build` desde el worktree.
- El ejecutor no corre DDL ni levanta la app contra `testing`: esos pasos vuelven FRENADO.

---

## 2. Pasos

Cada PAR es un solo lanzamiento del ejecutor con el test rojo (pegar la salida) y la
implementación que lo pone verde. Commits: la sesión principal, con `/commit`.

### Etapa A — Backend (PR 1: `backend_preliquidacion`)

#### Par A1 — Detección en el motor
Archivos: `tests/preliquidacion/test_posible_duplicado.py` (nuevo),
`app/modulos/preliquidacion/services/motor_reglas.py`.

Rojo. Tests puros (sin DB, `MotorReglas(None)` como en `test_motor_reglas.py`). Helper
`_fila(**kw)` con datos inventados. Casos:
- `test_mismas_unidades_distinta_hs_maquina_son_posibles`: f1 (unidades 500, hsmaquina 4) y
  f2 (igual, hsmaquina 5) → `detectar_posibles_duplicados([f1, f2]) == {0, 1}` y
  `detectar_duplicados([f1, f2]) == set()`.
- `test_mismas_tancadas_distinta_hs_jornal_son_posibles`.
- `test_sin_cantidad_no_es_posible`: unidades 0 y tancadas None, horas distintas → `set()`
  (parametrizar con `None`, `0`, `"0.00"`).
- `test_cantidad_distinta_no_es_posible` (500 vs 501).
- `test_otra_fecha_persona_o_finca_no_es_posible` (parametrizado sobre fecha_tarea, legajo,
  nombre_finca, nombre_tractor).
- `test_duplicado_no_es_ademas_posible`: A, B idénticas (4 hs) y C igual salvo 5 hs →
  `dup = detectar_duplicados(...) == {0, 1}`; `detectar_posibles_duplicados(..., dup) == {2}`.
- `test_grupo_de_solo_identicas_no_genera_posibles`: A, B, C idénticas → `set()`.
- `test_dos_pares_identicos_entre_si_no_generan_posibles`: A, B (4 hs) y C, D (5 hs) → todas
  duplicadas, posibles `set()`.
- `test_normaliza_como_detectar_duplicados`: unidades `"12.985"` vs `"12.99"`, finca
  `" finca 1 "` vs `"FINCA 1"`, planilla en minúsculas → `{0, 1}`.
Comando: `python -m pytest tests/preliquidacion/test_posible_duplicado.py -q` → falla con
`AttributeError`.

Verde. En `motor_reglas.py`, al lado de `detectar_duplicados`:
- Funciones de módulo: `clave_posible_duplicado(linea: dict) -> tuple` = la clave de
  `detectar_duplicados` sin `hsjornal`/`hsmaquina`; `paga_cantidad(linea: dict) -> bool` =
  unidades o tancadas normalizadas, no nulas y > 0.
- `MotorReglas.detectar_posibles_duplicados(self, lineas, duplicados=frozenset()) -> set[int]`:
  agrupa por `clave_posible_duplicado` sólo las filas con `paga_cantidad`; si un grupo tiene 2
  o más pares distintos `(norm(hsjornal), norm(hsmaquina))`, marca los índices del grupo que
  no estén en `duplicados`. Docstring con el criterio y el porqué de la cantidad > 0.
- Refactor mínimo: `detectar_duplicados` arma su clave como
  `clave_posible_duplicado(linea) + (norm(hsjornal), norm(hsmaquina))`, para que haya una sola
  definición; `test_detectar_duplicados_normaliza_igual_que_la_clave`
  (`test_actualizar_quincena.py:341-349`) sigue verde.
Verificación: el archivo nuevo + `test_motor_reglas.py` + `test_actualizar_quincena.py`.

#### Par A2 — Columna en el modelo y ciclo generar/actualizar
Archivos: `tests/preliquidacion/test_posible_duplicado.py`, `app/modulos/preliquidacion/models.py`,
`app/modulos/preliquidacion/services/preliquidacion_service.py`.

Rojo. Sección nueva con la fixture `db` (SQLite, FKs ON, `Usuario(id=1)`), `FakeExterna`,
`_fila`, `_svc` copiados de `test_actualizar_quincena.py:18-85` (pasar `unidades=500` y
`hsmaquina` por parámetro):
- `test_generar_marca_posible_duplicado_en_el_par`.
- `test_generar_no_marca_posible_a_la_duplicada` (A, B idénticas + C).
- `test_actualizar_prende_posible_al_llegar_la_segunda_linea` (espejo de
  `test_flag_duplicado_se_prende_al_agregar_copia_incremental`).
- `test_actualizar_apaga_posible_al_borrar_la_companera`.
- `test_sin_cambios_no_toca_la_marca`.
Comando: mismo archivo → `AttributeError: ... 'es_posible_duplicado'`.

Verde.
- `models.py:170`: `es_posible_duplicado = Column(Boolean, default=False, nullable=False)` con
  comentario de dos líneas (criterio, excluyente, ws18).
- `preliquidacion_service.py`: `generar` y `actualizar_quincena` calculan
  `indices_posibles = self.motor.detectar_posibles_duplicados(filas, indices_duplicados)` y lo
  pasan a `_procesar_fila_con_cache` (parámetro nuevo `es_posible_duplicado: bool = False`,
  seteado en el constructor). `_recalcular_flags_duplicado` extrae el armado del dict a
  `@staticmethod _fila_de_linea(l) -> dict` y actualiza las dos flags sólo si cambiaron;
  docstring y comentario de :307-311 actualizados.
Verificación: `test_posible_duplicado.py`, `test_actualizar_quincena.py`,
`test_generar_conceptos.py`, `test_export_excel.py` (el Excel no se mueve),
`tests/core/test_esquema.py`.

#### Par A3 — Migración `ws18` y manifiesto
Archivos: `migrations/preliquidacion/ws18_posible_duplicado.sql` (nuevo), `migrations/ORDEN.txt`.

Rojo: crear el `.sql` y correr `tests/core/test_manifiesto_migraciones.py` → falla
("migraciones que no están en ORDEN.txt"). Verde: agregar
`preliquidacion/ws18_posible_duplicado.sql` (sin marca) después de `ws17`.

Cabecera al estilo ws16/ws17 (sin datos ni nombres reales): qué hace; NO ES DIFERIBLE
(aplicar primero en `testing`, después en producción, antes de reiniciar el backend nuevo);
el backfill es una semilla única y el servicio recalcula en Python en cada actualización con
altas o bajas; divergencias conocidas SQL vs Python (la collation iguala acentos, Python sólo
mayúsculas); `scripts/refrescar_testing.py` pisa la columna en `testing` mientras producción
no la tenga; reintento: si el `ADD COLUMN` ya se aplicó, correr sólo los `UPDATE`
(idempotentes).

```sql
-- 1) Columna.
ALTER TABLE preliquidacion_linea
  ADD COLUMN es_posible_duplicado TINYINT(1) NOT NULL DEFAULT 0;

-- 2) Backfill. Misma clave que el motor sin las horas; cantidad > 0; horas distintas dentro
--    del grupo (MIN <> MAX del par de horas como texto equivale a "dos o más pares
--    distintos"); nunca sobre una duplicada.
UPDATE preliquidacion_linea SET es_posible_duplicado = 0;

UPDATE preliquidacion_linea l
JOIN (
  SELECT id, MIN(hs) OVER w AS hs_min, MAX(hs) OVER w AS hs_max
  FROM (
    SELECT id, preliquidacion_id,
           UPPER(TRIM(COALESCE(planilla, '')))        AS planilla_n,
           fecha_tarea,
           TRIM(COALESCE(legajo_campo, ''))           AS legajo_n,
           UPPER(TRIM(COALESCE(nombre_empleado, ''))) AS empleado_n,
           UPPER(TRIM(COALESCE(nombre_tarea, '')))    AS tarea_n,
           UPPER(TRIM(COALESCE(nombre_cliente, '')))  AS cliente_n,
           UPPER(TRIM(COALESCE(nombre_finca, '')))    AS finca_n,
           UPPER(TRIM(COALESCE(nombre_tractor, '')))  AS tractor_n,
           tancadas, unidades,
           CONCAT(COALESCE(CAST(hsjornal AS CHAR), 'None'), '|',
                  COALESCE(CAST(hsmaquina AS CHAR), 'None')) AS hs
    FROM preliquidacion_linea
    WHERE COALESCE(unidades, 0) > 0 OR COALESCE(tancadas, 0) > 0
  ) b
  WINDOW w AS (PARTITION BY preliquidacion_id, planilla_n, fecha_tarea, legajo_n, empleado_n,
                            tarea_n, cliente_n, finca_n, tractor_n, tancadas, unidades)
) g ON g.id = l.id
SET l.es_posible_duplicado = 1
WHERE g.hs_min <> g.hs_max
  AND COALESCE(l.es_duplicado, 0) = 0;

-- 3) Comprobación: conteo por quincena, y ninguna línea con las dos marcas.
SELECT p.quincena, COUNT(*) AS posibles
FROM preliquidacion_linea l JOIN preliquidacion p ON p.id = l.preliquidacion_id
WHERE l.es_posible_duplicado = 1 GROUP BY p.quincena ORDER BY p.quincena;
SELECT COUNT(*) FROM preliquidacion_linea WHERE es_posible_duplicado = 1 AND es_duplicado = 1;  -- 0

-- Rollback (comentado): ALTER TABLE preliquidacion_linea DROP COLUMN es_posible_duplicado;
```

Verificación: `test_manifiesto_migraciones.py` verde. La aplicación en `testing` es A8.

#### Par A4 — Estadísticas y `solo_alertas`
Archivos: `tests/preliquidacion/test_estadisticas_sql.py`, `tests/preliquidacion/test_lineas_service.py`,
`app/modulos/preliquidacion/services/preliquidacion_service.py`.

Rojo.
- `test_estadisticas_sql.py`: `_linea` suma `es_posible_duplicado=False`; en
  `test_estadisticas_cuenta_correctamente` una línea más con la flag → `posibles_duplicados == 1`,
  `total_lineas == 7`, `lineas_con_alerta == 5`; en `test_estadisticas_preliquidacion_vacia`
  sumar `"posibles_duplicados": 0` al dict exacto.
- `test_lineas_service.py::test_listar_solo_alertas_no_incluye_alerta_empresa`: una línea con
  `es_posible_duplicado=True` entra en el set.
Comando: los dos archivos → `KeyError` y set distinto.

Verde. `estadisticas` y `estadisticas_batch`: `func.sum(case(...))` para la flag nueva, clave
`posibles_duplicados`, incluida en el `or_` de `lineas_con_alerta` y en el dict inicial del
batch. `listar_lineas`: `| (PreliquidacionLinea.es_posible_duplicado == True)`.
Verificación: los dos archivos + `test_endpoints_lineas.py`.

#### Par A5 — Schema de línea y mensaje de generar
Archivos: `tests/preliquidacion/test_endpoints_lineas.py`, `tests/preliquidacion/test_generar_api.py`,
`app/modulos/preliquidacion/schemas.py`, `app/modulos/preliquidacion/api/preliquidacion.py`.

Rojo.
- `test_listar_lineas_expone_es_posible_duplicado` → `KeyError`.
- `test_generar_api.py`: el fake devuelve `"posibles_duplicados": 0`; test nuevo
  `test_detalle_de_generar_informa_posibles_duplicados` → falla por el texto.

Verde. `schemas.py:67`: `es_posible_duplicado: bool = False`. `api/preliquidacion.py:79-80`:
`f"{stats['duplicados']} duplicados · {stats['posibles_duplicados']} posibles duplicados"`.
Verificación: los dos archivos + `test_validar_quincena_api.py`.

Ajuste en la ejecución: la suite completa rompió
`test_mensualizados_config.py::test_linea_response_trae_mensualizado`, porque su helper
`_linea_suelta` arma una línea sin pasar por la base (el `default` de la columna recién se
aplica al INSERT) y no traía la flag nueva. Se suma `es_posible_duplicado=False` al helper,
como ya trae las otras flags. Descartado: `Optional[bool]` en el schema (la API podría
devolver `null`) y un default de Python en el modelo (zona sensible, sin necesidad).

#### Paso A6 — (eliminado en la revisión de la sesión principal)
El planificador proponía la clave `posibles_duplicados` en `dashboard_verificacion`. Se
saca: ese endpoint no lo usa ninguna pantalla (ver premisa 1), y duplicaría en el backend la
lógica que la sección calcula en el front (B2).

#### Paso A7 — Glosario (sin test)
Archivo: `docs/modulos/preliquidacion/CONTEXT-preliquidacion.md`, entre "Línea incompleta" y
"Grupo de pago", texto literal aprobado:

```
**Línea duplicada**:
Línea igual a otra de la misma quincena en todo lo que trae del campo: planilla, fecha, persona, tarea, cliente, finca, tractor, horas y cantidades. Indica una carga repetida en el campo; el sistema la marca y no la corrige: se corrige en el campo.
_Avoid_: confundirla con el Concepto duplicado (una regla repetida en el maestro).

**Posible duplicado**:
Línea igual a otra en todo salvo en las horas (jornal o máquina), con la misma cantidad pagada (unidades o tancadas, mayor a 0). Es una duda para el liquidador, no un error seguro: pueden ser dos trabajos reales. Una Línea duplicada no es además Posible duplicado.
_Avoid_: "casi duplicado", "duplicado parcial".
```

Verificación: leer el archivo; `tests/core/test_asistente_docs.py` verde si valida glosarios.

#### Paso A8 — FRENADO: aplicar `ws18` en `testing` y smoke del backend (sesión principal)
1. Correr `ws18` en `testing` (ALTER, UPDATEs, comprobaciones). Esperado: la quincena
   2026-08-16 con 4 líneas marcadas y 0 líneas con las dos marcas.
2. Levantar el backend del worktree contra `testing` (sólo variables de `testing`).
3. Smoke por API: `/lineas` trae `es_posible_duplicado`; `/estadisticas` trae
   `posibles_duplicados` y `lineas_con_alerta` lo incluye; `POST /generar` sobre esa quincena
   informa "· N posibles duplicados" y, sin altas ni bajas, las marcas quedan como las dejó
   el backfill.
4. No correr `scripts/refrescar_testing.py` hasta el deploy.

#### Paso A9 — Cierre del backend
Suite completa (pegar conteo), revisión en dos rondas, PR 1 con `--body-file`: qué, por qué,
descartados, verificación, qué pasa después (deploy sólo con OK: `ws18` en producción ANTES
de reiniciar el backend; después regenerar `000_esquema_base.sql` y marcar `ws18` histórica
en PR aparte), rollback (`DROP COLUMN` + revert). Incluye este plan.

### Etapa B — Frontend (PR 2: `frontend_preliquidacion`, después del PR 1)

Ajuste en la ejecución: `npm run lint` ya da 6 errores en `main`, todos en
`.claude/hooks/ultimas-entregas.mjs` (`process` sin `globals.node`, del FT #56). El criterio
"0 errores" de B3, B4 y B6 se mide con `npx eslint` sobre los archivos que toca cada paso;
la deuda del hook va a "A futuro" de `docs/estado.md`.

#### Par B1 — Precedencia de alertas
Archivos: `src/modulos/preliquidacion/pages/ordenarLineas.test.js`, `src/modulos/preliquidacion/pages/ordenarLineas.js`.

Rojo: `alertaDe({ es_duplicado: true, es_posible_duplicado: true })` → `'DUPLICADO'`;
`alertaDe({ es_posible_duplicado: true, linea_incompleta: true })` → `'POSIBLE DUPLICADO'`; el
orden por alerta la ubica entre DUPLICADO e INCOMPLETA (asc y desc). `npm test` → fail.

Verde: `PRECEDENCIA_ALERTAS = ['DUPLICADO', 'POSIBLE DUPLICADO', 'INCOMPLETA', 'LEGAJO', 'EMPRESA']`;
`alertaDe` devuelve `'POSIBLE DUPLICADO'` después de `es_duplicado`.

#### Par B2 — Agrupado puro para Verificación
Archivos: `src/modulos/preliquidacion/pages/posiblesDuplicados.test.js` (nuevo),
`src/modulos/preliquidacion/pages/posiblesDuplicados.js` (nuevo).

Rojo (stub que devuelve `[]`). Tests `node:test`, decimales como strings:
- sin líneas marcadas → `[]`.
- par marcado (hsmaquina '4' y '5', unidades '500', importe '400' y '500') → un item
  `{ clave, legajo, nombre_empleado, fecha, lineas, valor: 400 }`.
- A, B duplicadas + C marcada, misma clave → un item con 3 líneas; `valor` = suma − mayor.
- misma persona/día, dos fincas → dos items.
- normaliza mayúsculas y espacios en nombres.
- una línea marcada cuya compañera se filtró → `[]`.
- orden por `valor` descendente.

Verde: `agruparPosiblesDuplicados(lineas)` con la clave de `clave_posible_duplicado`
(nombres normalizados, cantidades como texto), sólo líneas con cantidad > 0; grupos con ≥ 2
líneas y alguna `es_posible_duplicado`; `legajo = legajo_asignado || legajo_campo || ''`;
`valor` = suma de importes − el mayor, a 2 decimales; `clave` = ids unidos con `-`.
Comentario de cabecera: vive acá para que búsqueda, filtros y mensualizados apliquen como en
las otras secciones.

#### Paso B3 — Revisión: badge, filtro, banner, panel (lint + build + smoke)
- `Revision.jsx`: `BADGE_ALERTA['POSIBLE DUPLICADO'] = 'badge-warn'`; filtro
  `es_posible_duplicado`; `solo_alertas` suma la flag; `claseLinea` devuelve `'alerta'` para
  posible (después de duplicado); banner recibe `posiblesDuplicados={stats.posibles_duplicados}`.
- `FiltrosBar.jsx`: opción `{ value: 'es_posible_duplicado', label: 'Posible duplicado' }`.
- `AlertasBanner.jsx`: prop `posiblesDuplicados` → `· N posibles duplicados`.
- `PanelLinea.jsx`: aviso `⚠ Posible duplicado: otra línea igual con distintas horas`.
Verificación: `npm run lint` (0 errores), `npm run build`.

#### Paso B4 — Verificación: sección "Posibles duplicados"
- `SECCIONES` suma `{ key: 'posibles-duplicados', label: '⚠ Posibles duplicados', umbral: 'mismas unidades, distintas horas' }`.
- `useMemo` sobre `lineasFiltradas` + `filtrarBusqueda`; contador en la nav; render.
- `ListaPosiblesDuplicados` con el molde de `ListaExceso`: vacío → `✓ No hay posibles duplicados.`;
  tarjeta con nombre, legajo, fecha y el importe en duda a la derecha (con `title` que lo
  explica); detalle `Tarea · Cliente · Finca · Superv. · Hs.jorn. · Hs.máq. · Tanc. · Unid. · Importe`
  y, por línea, un badge chico DUPLICADO o POSIBLE DUPLICADO.
- CSS: `.lineasHeadPosibles` / `.lineaRowPosibles` copiando `.lineasHead` / `.lineaRow`.
Verificación: `npm run lint`, `npm run build`.

#### Paso B5 — Smoke en el navegador (backend del worktree contra `testing` con `ws18`)
Quincena 2026-08-16: badge y borde amarillos en las 4 líneas y orden por alerta correcto;
chip "Posible duplicado" y "sólo alertas"; banner; panel; Verificación con contador 2, dos
tarjetas con importe en duda, búsqueda y filtros que las reducen; Inicio con el número de
alertas incluyendo las posibles; toast de generar con "· N posibles duplicados".

#### Paso B6 — Cierre del front
`npm test`, `npm run lint`, `npm run build`. Revisión (una ronda). PR 2 con `--body-file`.

---

## 3. Riesgos

- **DDL + backfill en producción (alto).** `ws18` se prueba antes en `testing` (A8); rollback
  escrito; NO DIFERIBLE. Sólo la sesión principal corre DDL, con OK del usuario.
- **Divergencia SQL vs Python en el backfill** (collation con acentos). Mitigación:
  comprobación en A8 (el caso real tiene que dar 4) y recálculo en Python en cada
  actualización con altas o bajas.
- **`refrescar_testing.py` pisa la columna en `testing`** hasta el deploy.
- **Deploy desfasado front/back**: el campo es aditivo, no rompe en ningún orden.
- **`lineas_con_alerta` incluye los posibles**: sube el número de Inicio y del topbar.
- **Tests que cambian de contrato**: `test_estadisticas_sql.py`, `test_generar_api.py`.
  Están en sus pares; si alguno falla fuera de ese par, es PLAN ROTO.

## 4. Preguntas abiertas

Cerradas por Gero al aprobar el plan (2026-10-07):

1. `es_posible_duplicado` **cuenta** en `lineas_con_alerta` (topbar de Revisión, banner y el
   número de alertas de Inicio, que sube sin tocar su código).
2. Verificación calcula la sección **en el front** (B2), como las otras; `dashboard_verificacion`
   no se toca.
3. Importe en duda = suma del grupo − la línea de mayor importe.
4. En el detalle, Tanc. y Unid. van en columnas separadas.
5. Un grupo que por los filtros queda con una sola línea **se oculta**.
6. Columna `TINYINT(1) NOT NULL DEFAULT 0`.
7. Marcar `ws18` histórica y regenerar `000_esquema_base.sql` después del deploy, en PR aparte.

## 5. Fuera de alcance

Excel de exportación, pantalla de Inicio (sólo cambia el número que ya muestra), botón de
descarte, editar horas o cantidades, corregir las líneas del caso real (se corrige en el
campo), ADR, `docs/estado.md`, deploy y regeneración de `000_esquema_base.sql` (PR aparte),
el endpoint `dashboard_verificacion`.
