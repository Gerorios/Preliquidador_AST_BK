# Impacto reactivo del maestro y eliminación del estado "revisado"

Se abandona el flujo de "editar y después apretar un botón para aplicar". Un cambio en el maestro de conceptos (crear/editar/borrar un concepto o completar un faltante) impacta **automáticamente** en la preliquidación, recalculando **solo las líneas afectadas** (las que matchean `tarea + cliente + finca` del concepto): regenera sus `ConceptoAdicional` automáticos (preservando los manuales, con `ingresado_por`), y actualiza `importe_total` + ambas alertas. En paralelo se elimina el estado **`revisado`** de las líneas: no aporta valor porque siempre puede haber cambios posteriores.

## Consecuencias

- Desaparecen los botones "Recalcular precios" y "Aplicar conceptos" como paso obligatorio. Puede quedar, opcionalmente, una acción manual de "recalcular toda la quincena" como red de seguridad, pero no es el camino normal.
- El recálculo debe ir scopeado a las líneas afectadas por rendimiento (no barrer toda la quincena en cada guardado del maestro).
- Cuando la edición cambia las **claves de matching** de un concepto (tarea/cliente/finca), el recálculo debe cubrir la **unión** del match anterior + el nuevo, para no dejar `ConceptoAdicional` fantasmas con total inflado en las líneas que dejaron de matchear. Para creaciones/borrados/cambios de solo-precio alcanza con el match único.
- Eliminar `revisado` toca: `models.py:148`, `schemas.py:17/64/82`, `api/preliquidacion.py:74/185/193`, y en `preliquidacion_service.py` los puntos `:317/:688/:696/:726/:818/:832-835`. En el frontend (repo aparte): botón "marcar como revisado" en `PanelLinea`, filtros de Revisión y stats del Dashboard.
- Como ya no hay líneas "dadas por buenas", el impacto automático nunca pisa un estado protegido: no hace falta lógica de protección de líneas revisadas.

## Estado de implementación (rama `ws2-modelo-reactivo`)

Hecho:
- `PreliquidacionService`: `_cache_conceptos_quincena` y `_aplicar_conceptos_a_lineas` extraídos de `aplicar_conceptos` (que ahora es un caso particular: recalcular *todas* las líneas de una preliquidación, conservado como acción manual de emergencia, ya no obligatoria).
- `_lineas_por_match(preliq_id, tarea, cliente, finca)`: matching case-insensitive (tarea filtrada en SQL, cliente/finca en Python con `.strip().upper()`, igual criterio que el resto del código).
- `recalcular_por_concepto(quincena, actual, anterior=None)`: nuevo método reactivo. Con `anterior` presente, recalcula la **unión** de líneas del match viejo + el nuevo (evita fantasmas al editar claves).
- Enganchado en los 3 endpoints CRUD de `precios.py` (crear/actualizar/eliminar concepto) — cubre también "completar un faltante", que reusa el mismo `crearConcepto` del frontend.
- `db_externa` pasó a ser opcional en `PreliquidacionService.__init__` para poder instanciarlo liviano desde `precios.py` sin la conexión externa.
- `revisado` eliminado por completo: columna (`models.py`), schemas, query param y filtro (`listar_lineas`), stats (`estadisticas`, `_agrupar_por_empresa`), y en el frontend: botón "marcar como revisada" (`PanelLinea`), filtro y badge (`Revision.jsx`), columnas REVISADAS/PROGRESO (`Dashboard.jsx`), estilos `.check`/`.checkDone`/`tr.revisada`.
- Tests: `tests/test_recalculo_reactivo.py` (5 tests, SQLite in-memory — la lógica nueva es SQLAlchemy puro, portable) cubriendo creación, no-impacto en otro cliente, unión viejo+nuevo al editar claves, y borrado. Smoke test end-to-end manual contra la app real (TestClient + quincena ficticia, limpiado después) confirmando crear/editar/borrar vía HTTP real.
- Migración `migrations/ws2_drop_columna_revisado.sql` (deprecate-then-drop, no ejecutada todavía).

Pendiente (fuera de WS2):
- La bandera única de "línea incompleta" (colapsar `alerta_sin_precio`/`alerta_sin_codigo`) es WS3, no tocada acá — `recalcular_por_concepto` sigue seteando `alerta_sin_codigo` con la semántica vieja.
- El botón "Aplicar" en la topbar de Revisión (`aplicarTodo`) sigue existiendo como acción manual; no se quitó de la UI en esta rama (queda como red de seguridad, tal como dice la consecuencia de arriba).
