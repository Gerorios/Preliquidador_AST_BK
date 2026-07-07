# Plan de implementación — refactor preliquidación

Consolidado de la sesión de grilling. Cada workstream referencia su ADR. Orden sugerido por dependencias. **Nada de esto está implementado todavía**; es el plan acordado.

## WS1 — Retirar el modelo viejo de precios (ADR-0001)

1. **Precondición:** redirigir `control_plantas_jornal` (`preliquidacion_service.py:637`) para que el `precio_promedio` salga del **concepto aplicable por-unidad (planta)**, no de `precio_a`.
2. Eliminar el fallback a `precio_a` en `_generar_conceptos_automaticos` (`:337`) — sin precio, la línea queda incompleta (ver WS3), nunca paga 0 (ADR-0003).
3. Eliminar código muerto: `calcular_importe`, `calcular_jornal`, `calcular_bins` (`motor_reglas.py:74-110`).
4. Deprecar y luego eliminar columnas: `precio_b`, `precio_usado`, `importe_base`, `detalle_concepto` (modelo + migración DB).
5. Sacar `precio_b`/`precio_usado` de `actualizar_linea` (`:724-725`) y de los schemas (`schemas.py:60-61,80-81`).
6. Fr

ontend: quitar el selector precio A/B de la pantalla de Revisión.

## WS2 — Modelo reactivo + sin botones + sin "revisado" (ADR-0002)

1. Implementar recálculo reactivo **scopeado a líneas afectadas**, disparado en create/update/delete de concepto y al completar un faltante. En cambios de clave (tarea/cliente/finca), recalcular la **unión** del match viejo + nuevo (evita conceptos fantasma).
2. Eliminar los botones "Recalcular precios" y "Aplicar conceptos" como paso obligatorio. Opcional: dejar una acción manual "recalcular toda la quincena" como red de seguridad.
3. Eliminar el estado `revisado`: `models.py:148`, `schemas.py:17,64,82`, `api/preliquidacion.py:74,185,193`, `preliquidacion_service.py:317,688,696,726,818,832-835`; frontend: botón "marcar revisado" en `PanelLinea`, filtros de Revisión, stats del Dashboard.

## WS3 — Completitud única: código y precio (ADR-0003)

1. Unificar `alerta_sin_precio` + `alerta_sin_codigo` en una sola bandera "línea incompleta" = no tiene ningún concepto aplicable con **código y precio > 0**.
2. Ajustar la query de faltantes (`precios.py:186`) para listar los combos cuyas líneas no tienen concepto **completo** (no solo los sin nada).
3. El recálculo reactivo (WS2) es el único que setea/limpia esta bandera.

## WS4 — Reasignación masiva de empresa (feature nueva) ✅ implementado (rama `ws4-reasignacion-masiva-empresa`)

1. ~~Endpoint: legajos disponibles por CUIL~~ → `SueldosService.legajos_por_cuil`/`legajo_por_cuil_y_empresa` + `POST /api/preliquidacion/lineas/legajos-por-cuil`.
2. ~~Endpoint POST de reasignación masiva~~ → `POST /api/preliquidacion/lineas/reasignar-empresa`, reusa el patrón de `AjusteManual` de `actualizar_linea`.
3. Líneas con `cuit` vacío quedan en `sin_cuil` en la respuesta de `legajos-por-cuil` (el picker las excluye).
4. Frontend: se extendió `LiquidacionPersona` (ya existía, agrupaba por legajo para conceptos masivos) con la acción "⇄ Reasignar empresa" — abre un picker por CUIL con los pares (empresa, legajo) reales de esa persona.
5. La reasignación persiste sola — confirmado: `_aplicar_conceptos_a_lineas`/`recalcular_por_concepto` nunca tocan `empresa_asignada`/`legajo_asignado`.

**Verificación:** 4 tests unitarios (SQLite, `SueldosService` con cache poblado a mano) + smoke test HTTP real (TestClient) contra una persona real de `db_sueldos` con dos legajos (LA ASTURIANA:4314, PROSELECT:20848) — confirmó agrupación, reasignación con el legajo correcto, bloqueo cuando la persona no tiene legajo en la empresa destino, y 6 `AjusteManual` de auditoría. Verificación visual parcial: una captura real mostró el picker de personas con el caso real de doble legajo (ALBORNOZ, HUGO FERNANDO — legajo 19320 en LA ASTURIANA y 20204 en PAMPLONA); el resto del click-through visual quedó bloqueado por saturación de recursos del entorno de pruebas (no del código — confirmado con el smoke test HTTP).

## WS5 — Copiar conceptos: auto-aplicar + precio heredado (ADR-0004)

1. Al copiar (`precios.py:140`), disparar el recálculo reactivo (WS2) sobre las líneas afectadas del destino.
2. Agregar señal de "precio heredado / sin confirmar" en `concepto_liquidacion` (flag booleano y/o quincena de origen) + migración.
3. Confirmar un precio limpia la marca. Frontend: resaltar y permitir filtrar los heredados. Un heredado paga normal (cuenta como completo en WS3).

## WS6 — Rediseño visual del frontend (repo `frontend_preliquidacion`)

**Dirección acordada: evolucionar el sistema de diseño actual, no reemplazarlo.** Se mantiene la identidad de marca (paleta terracota `#C3403A` + oliva `#6D8B46` sobre dark `#15120f`, tipografía IBM Plex Sans/Mono, densidad de data-tool) y se sube la vara en jerarquía, espaciado, estados y consistencia. Alcance: Revisión, Conceptos (3 solapas), Verificación, Dashboard y Layout. Encarar con brainstorming + el skill `frontend-design`.

### Punto de partida (lo que ya existe)
- Design system en `src/index.css`: tokens de color/espaciado/radios, clases `.btn`/`.badge`/`.input`/`.card` y tabla con header sticky + estados de fila por borde izquierdo (`alerta`/`revisada`/`duplicado`).
- Shell con sidebar colapsable (`components/layout/Layout`).
- Stack: React 18, React Router 6, React Query 5, Zustand, react-hot-toast; `@tanstack/react-table` instalado pero las tablas están hechas a mano.
- **Patrón de WS4 ya existe:** `LiquidacionPersona` en `Revision.jsx` agrupa por persona + multiselección para conceptos masivos. La reasignación de empresa extiende ese componente.

### Cambios visuales atados a los otros workstreams
- **Revisión** (`pages/Revision.jsx`, 533 líneas — descomponer): quitar selector precio A/B (WS1); quitar checkbox/estilo "revisado" `tr.revisada` + `.check/.checkDone` (WS2); reemplazar los dos estados de alerta por **un único estado visual "incompleta"** (WS3); extender `LiquidacionPersona` a **reasignación masiva de empresa** con picker por persona (WS4).
- **Conceptos** (`pages/Conceptos.jsx`): resaltado + filtro de **precios heredados** sin confirmar (WS5); solapa "Sin concepto" lista combos sin concepto completo (WS3).
- **Dashboard/Verificación**: tablas de excesos y resumen por empleado (umbrales tal cual).

### Entregables sugeridos
Auditoría del design system → refinar tokens y componentes base (botones, tablas, badges, estados) → mockups por pantalla → aprobación → implementación pantalla por pantalla. Evaluar adoptar `@tanstack/react-table` para orden/virtualización si los listados son grandes.

## Limpieza de documentación

- `.claude/contexto.md` queda **superado** por `CONTEXT.md` (glosario) + los ADRs. Borrarlo o marcarlo obsoleto.
- Corregir el comentario muerto `preliquidacion_service.py:269` ("grupo_pago para el importe base" — `importe_base` es siempre 0).

## Dependencias

- WS3 depende de WS2 (el recálculo reactivo setea la bandera de completitud).
- WS5 depende de WS2 (copiar usa el mismo recálculo reactivo).
- WS1 paso 1 (redirigir el control de PLANTA) es precondición para eliminar `precio_a`.
- WS4 es independiente; se puede hacer en cualquier momento.
- WS6 (rediseño visual) va **después o coordinado con WS2–WS5**: esos cambian qué muestra cada pantalla (sin A/B, sin "revisado", alerta única "incompleta", precio heredado, multiselección de empresa). Rediseñar antes sería sobre pantallas que están por cambiar. Se hace en el repo `frontend_preliquidacion`.
