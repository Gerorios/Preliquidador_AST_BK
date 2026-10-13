# Plan: columna "Min/tancada" (rendimiento de tancada) en Tancadas vs Jornal

Fecha: 2026-10-13. Skill `flujo-preliquidacion`, carril completo. El cambio toca el contrato JSON entre back y front (PRs hermanos, primero el del back) y modifica `preliquidacion_service.py`, que es zona sensible.

## 1. Qué se pide

El control Tancadas vs Jornal gana la columna "Min/tancada": cuántos minutos de máquina lleva una tancada, `hs máquina × 60 ÷ tancadas`, sin dividir por 2. Aparece en Verificación y, como el componente es compartido, también en la Vista gerencial.

- **Backend:** hace la cuenta y la devuelve en un campo nuevo, por fila y en `totales`. No toca ningún campo existente.
- **Frontend:** sólo la muestra, con 1 decimal, justo después de "Hs máquina". La columna se puede ordenar y también aparece en la fila Total.
- Sin DDL.

## 2. Qué encontré en el código

### Premisas del briefing que no se sostienen

1. **El front no usa vitest.** `npm test` es `node --test` sobre una lista fija de carpetas (`package.json:11`), y `components/` no está en esa lista. Además, `node --test` no puede importar `ControlesJornal.jsx`: tiene JSX e importa `../pages/Verificacion.module.css`. La convención del repo (`docs/superpowers/plans/2026-10-07-posible-duplicado.md:89-91`) es que la lógica pura va en `pages/*.js` con su `*.test.js`, y los componentes React se verifican con lint, build y smoke. En el front no hay lógica nueva: el cálculo es del back, y `src/core/ui/ordenarFilas.test.js` ya cubre que se ordene y que lo vacío vaya al final. Por eso **no hay test de front**: la columna se verifica en el navegador.
2. **No hay schema pydantic que ampliar.** Los dos endpoints del control (`GET /api/preliquidacion/{id}/control-tancadas-jornal`, en `api/preliquidacion.py:172-177`, y `GET /api/gerencial/control-tancadas`, en `api/gerencial.py:177-187`) devuelven el dict del servicio tal cual, sin `response_model`. El campo nuevo llega a los dos sin tocar ninguna ruta.
3. **La dependencia del front con el back deployado es blanda.** Los formatters de `TancadasJornal` son null-safe (`n == null` también atrapa `undefined`): front nuevo con back viejo muestra "—"; back nuevo con front viejo ignora el campo. Igual se deploya primero el back.
4. `tests/preliquidacion/test_panel_precios.py` no tiene nada de este control.

### Backend

`control_tancadas_jornal` está en `app/modulos/preliquidacion/services/preliquidacion_service.py:1259-1387`.

- Agrupa por (cliente, finca, tarea) con `_sumar_por_unidad_base(preliq_id, "tancadas", ["tancadas", "hsjornal", "hsmaquina"])`. Las líneas de personas mensualizadas ya vienen excluidas.
- En el loop (:1333-1365) ya existen `tancadas` y `hsmaquina` como float sin redondear (null cuenta como 0). La marca `sin_hs_maquina = not hsmaquina > 0` está en :1342. Los acumuladores de totales, sin redondear, están en :1328-1332 y :1346-1351.
- Convenciones: `round(x, 2)` y `None` cuando no hay valor; los ratios del total salen de sumas sin redondear, nunca del promedio de las filas; sin con qué calcular va null, no 0; guardas `not x > 0`; comentarios con el porqué (GUIA-MODULOS, regla 25).
- Nombre del campo: **`minutos_por_tancada`**, en la línea de `plantas_por_hsm` de Plantas vs Jornal.

**El motor paga la tancada aunque la línea no traiga tancadas** (`motor_reglas.py:126,131`; `preliquidacion_service.py:593-621`: concepto con cantidad 0). Por eso puede haber filas con hs máquina > 0 y tancadas 0 (pregunta 1).

**Tests existentes:** `tests/preliquidacion/test_control_tancadas_jornal.py`, 13 casos, SQLite en memoria (fixture `db`), helpers `_preliq`, `_linea` (`tancadas` no acepta `None` hoy) y `_aplicar_tancada`. Estilo: docstring con la cuenta a mano y `for d in (fila, tot)`.

**Nadie más lee esta respuesta** (ni la exportación). `scripts/snapshot_api.py` es manual: que su hash cambie es lo esperado.

### Contrato

Campo nuevo `minutos_por_tancada` en cada elemento de `filas` y en `totales`: float con 2 decimales, o `null`. Nada más cambia.

### Frontend

Todo en `src/modulos/preliquidacion/components/ControlesJornal.jsx`: `COLS_TANCADAS` (:22-34), y en `TancadasJornal` (:168-252) los formatters (:174-178), las celdas del cuerpo escritas a mano en el orden de `COLS_TANCADAS` (:207-220), el `tfoot` (:226-236) y la nota al pie (:241-247). `Verificacion.jsx` y `Gerencial.jsx` pasan la respuesta tal cual. `.pjTableWrap` tiene `overflow: auto` y el `thead` es sticky: la columna 12 entra con scroll horizontal, sin CSS nuevo.

### Docs

- `docs/AYUDA.md`: :522-523 (la línea del control) y :573-593 (columnas, fila sin hs máquina, fila Total).
- Glosario `docs/modulos/preliquidacion/CONTEXT-preliquidacion.md`: sección "Controles" (:136-148); Tancada en :114-116.
- Los dos textos van al prompt del asistente de ayuda (`app/core/asistente.py:31-35`); `tests/core/test_asistente_docs.py` controla que existan.
- **Choque de vocabulario:** "rendimiento" ya se usa en Plantas vs Jornal (plantas por hora: más es más rápido). Acá más minutos es más lento. El glosario los separa.
- **No hace falta ADR**: columna informativa; el total sigue el criterio del ADR-0017. Sin antecedentes de esta métrica en bitácora ni ADR.

## 3. Pasos

### Entorno

- `BK` = `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\backend_preliquidacion\.claude\worktrees\rendimiento-tancadas`, rama `feature/rendimiento-tancadas`.
- `FT` = `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion\.claude\worktrees\rendimiento-tancadas`, rama `feature/rendimiento-tancadas`. Su `node_modules` es un junction: nunca se borra en forma recursiva.
- Tests del back: `.env` ficticio en la raíz de `BK` desde `.env.example` (`DB_*_HOST=db.invalid`, `DB_*_USER/PASSWORD/NAME=x` salvo `DB_PROPIA_NAME=testing`, `SECRET_KEY=clave-de-prueba`). Nunca el `.env` real, nunca `DB_PROD_*` ni `PERMITIR_BASE_PRODUCCION`. Pytest desde la raíz de `BK`: `PYTHONUTF8=1 python -m pytest <ruta> -q`.
- Front desde `FT`: `npm test`, `npm run lint`, `npm run build`. En `main`, lint ya da 6 errores en `.claude/hooks/ultimas-entregas.mjs` y 5 warnings en Terceros.
- Línea de base antes de A0: `test_control_tancadas_jornal.py` 13 passed; en `FT`, anotar `npm test` y lint.
- El ejecutor no hace commits, ramas, PRs, merge ni deploy.

### Etapa A — Backend (PR 1, `backend_preliquidacion`)

#### Paso A0 — Docs, sin test

Va primero (GUIA-MODULOS, regla 26). Archivos: `CONTEXT-preliquidacion.md` y `docs/AYUDA.md`.

**Glosario**, en "Controles", después de Valor hora pulverización:

> **Rendimiento de tancada**:
> Cuántos minutos de máquina lleva una tancada en las tareas pagadas por tancada: horas de máquina × 60 ÷ tancadas, con la tancada tal como se registra (no se divide por 2; ver Tancada). Es un dato del control Tancadas vs Jornal (columna "Min/tancada"), no una comparación: no tiene referencia ni se carga. Sin horas de máquina o sin tancadas no hay rendimiento. El de varias filas juntas (el total) sale de las sumas de horas y de tancadas de las filas que lo tienen, no del promedio de sus rendimientos.
> _Avoid_: calcularlo con las horas de jornal (son de presencia, no de máquina); "rendimiento" a secas (en Plantas vs Jornal son plantas por hora, donde más es más rápido; acá más minutos es más lento); promediar los rendimientos de las filas.

**AYUDA.md**
- :522-523, al final de la línea del control: "…, y muestra cuántos minutos de máquina lleva cada tancada."
- :577-584, entre **Hs máquina** y **Precio tancada**: "**Min/tancada** (el rendimiento: cuántos minutos de máquina lleva cada tancada, horas de máquina × 60 ÷ tancadas)".
- :586-588, fila sin hs máquina: "…no tiene valor hora, minutos por tancada ni variación, y no entra en esos cálculos del total (una nota al pie dice cuántas filas quedaron afuera)."
- Viñeta nueva: "Una fila **sin tancadas** no tiene minutos por tancada (se ve —) y no entra en los minutos por tancada del total."
- :589-591, fila Total: "…su valor hora y su variación se calculan con las sumas de las filas que tienen horas de máquina, y sus minutos por tancada con las sumas de horas de máquina y de tancadas de las filas que los tienen (no son promedios de las filas)."

**Verificación:** `PYTHONUTF8=1 python -m pytest tests/core/test_asistente_docs.py -q` da 6 passed; `grep` encuentra "Min/tancada" en AYUDA y "Rendimiento de tancada" en el glosario.

Este plan también va en el PR 1.

#### Par A1 — `minutos_por_tancada` por fila

Archivos: `tests/preliquidacion/test_control_tancadas_jornal.py` y `app/modulos/preliquidacion/services/preliquidacion_service.py`.

**Rojo**
- `_linea` acepta `tancadas=None`, igual que `hsmaquina`.
- `test_ejemplo_planilla_valor_hora_maquina_vs_referencia`: `fila["minutos_por_tancada"] == 34.0` (34 × 60 ÷ 60; con ÷2 daría 68,0 y con hs jornal 54,0).
- `test_sin_valor_hora_pulv_devuelve_null_no_error`: `fila["minutos_por_tancada"] == 7.5` (5 × 60 ÷ 40).
- `test_fila_sin_hs_maquina_no_entra_en_la_variacion` (0 y null): fila A `12.0` (10 × 60 ÷ 50), fila B `None`.
- Nuevo `test_minutos_por_tancada_redondea_a_dos_decimales`: hs máquina 1 y tancadas 7 da `8.57`.
- Nuevo `test_fila_sin_tancadas_no_tiene_minutos_por_tancada`, parametrizado con tancadas `"0"` y `None`: fila A (FINCA 1, hs 10, tancadas 50, concepto 50) y fila D (FINCA 3, hs 4, sin tancadas, concepto de tancada con cantidad 0). D: `minutos_por_tancada is None`, `sin_hs_maquina is False`, `valor_hora_maquina == 0.0`. A: `12.0`. Sin `ZeroDivisionError`.
- Esperado: 7 fallan con `KeyError: 'minutos_por_tancada'` y 9 pasan.

**Verde** (sólo dentro del loop de `control_tancadas_jornal`)
- Después de `valor_hora_maquina`: `minutos_por_tancada = hsmaquina * 60 / tancadas` si `not sin_hs_maquina and tancadas > 0`; si no, `None`.
- En el dict de la fila, al lado de `"hsmaquina"`: `"minutos_por_tancada": round(m, 2) if m is not None else None`.
- Comentario con el porqué: no se divide por 2 (glosario: Tancada); sin hs máquina o sin tancadas va null, no 0.

**Verificación:** `test_control_tancadas_jornal.py` da 16 passed; `git diff --stat` sólo esos dos archivos.

#### Par A2 — `minutos_por_tancada` en `totales`

Mismos archivos.

**Rojo**
- `test_ejemplo_planilla_...`: `tot["minutos_por_tancada"] == 34.0`.
- `test_sin_valor_hora_pulv_...`: `tot["minutos_por_tancada"] == 7.5`.
- `test_fila_sin_hs_maquina_...` (0 y null): `12.0` (con la B adentro daría 8,57).
- `test_fila_sin_tancadas_...` ("0" y null): `12.0` (con las horas de D adentro daría 16,8). Depende de la pregunta 1.
- Nuevo `test_minutos_por_tancada_del_total_sale_de_las_sumas`: A (hs 10, tancadas 50) y C (FINCA 2, hs 6, tancadas 10) dan `16.0` (el promedio daría 24,0).
- Nuevo `test_minutos_por_tancada_del_total_es_null_sin_filas_con_rendimiento`, parametrizado: una sola fila sin hs máquina (hs 0, tancadas 20) y una sola sin tancadas (hs 4, tancadas 0): `None`, sin `ZeroDivisionError`.
- `test_excluye_lineas_de_empleados_mensualizados` (tabla vacía): `None`.
- Esperado: 10 fallan con `KeyError` y 9 pasan.

**Verde**
- Acumuladores nuevos sin redondear `thm_con_min` y `tt_con_min`, sumados sólo en las filas con `minutos_por_tancada` no nulo.
- `tmin = thm_con_min * 60 / tt_con_min if tt_con_min > 0 else None`.
- En `totales`, al lado de `"hsmaquina"`: `"minutos_por_tancada": round(tmin, 2) if tmin is not None else None`.
- Comentario: sólo entran las filas con rendimiento (las sin hs máquina lo deflacionarían, las sin tancadas lo inflarían), mismo criterio que el valor hora (ADR-0017).
- Una oración en el docstring de `control_tancadas_jornal`.

**Verificación:** 19 passed; nada fuera de `control_tancadas_jornal` y ningún campo existente cambiado.

### Etapa B — Frontend (PR 2, `frontend_preliquidacion`)

PR hermano del 1: se mergea y se deploya después.

#### Paso B1 — Columna "Min/tancada" (interfaz, sin test unitario)

Archivo: `src/modulos/preliquidacion/components/ControlesJornal.jsx`.

**Antes de editar:** `impeccable context --target src/modulos/preliquidacion/components/ControlesJornal.jsx` desde `FT` (en Windows, `.claude/skills/impeccable/scripts/impeccable.cmd`) y leer `.claude/skills/impeccable/reference/craft-floor.md`. Valen por encima las reglas de GUIA-MODULOS 4.5. Refinamiento de la tabla actual: sin `shape`, sin cambio de estética.

**Cambios**
- En `COLS_TANCADAS`, después de `hsmaquina`: `{ clave: 'minTancada', label: 'Min/tancada', valor: f => f.minutos_por_tancada, numerica: true }`.
- Formatter null-safe `fmtMin`: `n == null ? '—' : n.toLocaleString('es-AR', { maximumFractionDigits: 1 })`.
- En el cuerpo, después de la celda de Hs máquina: `<td className="mono">{fmtMin(f.minutos_por_tancada)}</td>`.
- En el Total, después de `totales.hsmaquina`: `<td className="mono">{fmtMin(totales.minutos_por_tancada)}</td>`.
- Nota al pie: "1 fila sin hs máquina no entra en la variación ni en los minutos por tancada" / "N filas sin hs máquina no entran en la variación ni en los minutos por tancada".
- No se tocan `Verificacion.jsx`, `Gerencial.jsx` ni el CSS.

**Verificación:** `npm test` igual a la línea de base; `npm run lint` sin errores ni warnings nuevos; `npm run build` bien; `grep -n "minutos_por_tancada"` da 3 líneas; `git diff --stat` un solo archivo.

#### Paso B2 — Smoke en el navegador (sesión principal)

Back desde `BK` con sólo las variables de `testing`; front desde `FT` con `npm run dev`; usuario de prueba de `testing` (clave en `../.claude/smoke-testing.env`, nunca al repo ni al chat). Quincena con filas en Tancadas vs Jornal; si no hay, se frena y se pregunta.

1. "Min/tancada" justo después de "Hs máquina", cada celda bajo su encabezado, en el cuerpo y en el Total.
2. Una fila hecha a mano coincide a 1 decimal.
3. El Total: Σ hs máquina × 60 ÷ Σ tancadas de las filas con valor.
4. Orden: mayor a menor, menor a mayor, original; "—" siempre al final.
5. Filas sin hs máquina o sin tancadas muestran "—" y la nota al pie. Si no hay en `testing`, se dice en el PR.
6. Con y sin valor hora pulverización, la columna no cambia; si se carga un valor para probar, se deja como estaba.
7. En la Vista gerencial, modo quincena: la misma columna, sólo lectura.
8. Con 12 columnas, el scroll horizontal queda dentro de la tabla y el encabezado sigue fijo.
9. Plantas vs Jornal sigue igual.

El PR no lleva nombres de clientes ni cifras reales de `testing`.

### Revisión (fase 4) y entrega (fase 5)

- Una sola vez con A y B terminadas: suite completa en `BK` y `npm test`, lint y build en `FT`.
- `revision-codigo` sobre los dos diffs, con `verificador-review`. Dos rondas: el diff toca `preliquidacion_service.py`, que la skill lista como zona sensible.
- `/impeccable critique` y `/impeccable audit` sobre la sección en Verificación y Gerencial; deuda previa como minor.
- PR 1 (BK): servicio, tests, glosario, AYUDA y plan. PR 2 (FT): `ControlesJornal.jsx`. Con `--body-file`. Porqué: el cálculo va en el back como el resto de las columnas derivadas (descartado: calcularlo en el front, que duplicaría la regla del total); el total sale de las sumas de las filas con rendimiento (descartado: el promedio de las filas).
- Deploy sólo con OK: primero el back, después el front.
- Rollback: revertir los PRs y swap de carpeta del front. Sin datos ni DDL.

## 4. Riesgos

| Riesgo | Mitigación |
|---|---|
| El total sale con un criterio no querido (filas con hs máquina y sin tancadas) | Pregunta 1 antes de A2; el test fija 12,0 contra 16,8 |
| Romper campos o totales existentes en zona sensible | Sólo se agrega, dentro de `control_tancadas_jornal`; los 13 tests existentes sólo suman asserts; dos rondas de revisión |
| `ZeroDivisionError` (500 en Verificación y Gerencial) | Guardas `> 0` en fila y total; tests con 0, null y tabla vacía |
| Leer mal el número: minutos por tancada **registrada** (viene doblada) | Glosario y AYUDA dicen "tal como se registra" |
| Confundirlo con el "rendimiento" de Plantas vs Jornal | `_Avoid_` del término nuevo |
| Celdas corridas o tabla demasiado ancha | Smoke B2 (puntos 1 y 8) y `/impeccable audit` |
| Deploy en otro orden | Front sin back: "—"; back sin front: se ignora |
| El asistente de ayuda repite AYUDA y glosario | Releer los textos contra el código final |
| Repos públicos | Datos inventados en tests, `.env` ficticio ignorado, PR sin datos de `testing` |

Sin migración, DDL ni escritura de datos: no hace falta backup.

## 5. Preguntas abiertas

1. ¿Una fila con hs máquina > 0 y tancadas 0 entra en el Min/tancada del total? Por defecto, no: el total usa sólo las filas que muestran Min/tancada.
2. La nota al pie pasa a decir "… no entran en la variación ni en los minutos por tancada". Las filas sin tancadas no se cuentan en la nota (haría falta un contador nuevo); lo explica AYUDA.
3. "1 decimal": hasta 1 decimal (34 · 8,6), como la Variación.
4. El término "Rendimiento de tancada" se suma al glosario con el texto de A0.

## 6. Fuera de alcance

- Columna nueva en Plantas vs Jornal.
- Umbral, resaltado o alerta para Min/tancada; tooltip en el encabezado.
- Contador de filas sin tancadas.
- Test unitario del front para `ControlesJornal.jsx`, o mover `COLS_TANCADAS` a un `.js`.
- Alinear a la derecha los números u otra deuda visual previa.
- `response_model` para los endpoints del control.
- La exportación a Excel.
- Los minors pendientes del BK #69.
- Un ADR nuevo.
- Dividir las tancadas por 2.
- El deploy (sólo con OK explícito).
