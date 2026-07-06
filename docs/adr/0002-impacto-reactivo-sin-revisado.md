# Impacto reactivo del maestro y eliminación del estado "revisado"

Se abandona el flujo de "editar y después apretar un botón para aplicar". Un cambio en el maestro de conceptos (crear/editar/borrar un concepto o completar un faltante) impacta **automáticamente** en la preliquidación, recalculando **solo las líneas afectadas** (las que matchean `tarea + cliente + finca` del concepto): regenera sus `ConceptoAdicional` automáticos (preservando los manuales, con `ingresado_por`), y actualiza `importe_total` + ambas alertas. En paralelo se elimina el estado **`revisado`** de las líneas: no aporta valor porque siempre puede haber cambios posteriores.

## Consecuencias

- Desaparecen los botones "Recalcular precios" y "Aplicar conceptos" como paso obligatorio. Puede quedar, opcionalmente, una acción manual de "recalcular toda la quincena" como red de seguridad, pero no es el camino normal.
- El recálculo debe ir scopeado a las líneas afectadas por rendimiento (no barrer toda la quincena en cada guardado del maestro).
- Cuando la edición cambia las **claves de matching** de un concepto (tarea/cliente/finca), el recálculo debe cubrir la **unión** del match anterior + el nuevo, para no dejar `ConceptoAdicional` fantasmas con total inflado en las líneas que dejaron de matchear. Para creaciones/borrados/cambios de solo-precio alcanza con el match único.
- Eliminar `revisado` toca: `models.py:148`, `schemas.py:17/64/82`, `api/preliquidacion.py:74/185/193`, y en `preliquidacion_service.py` los puntos `:317/:688/:696/:726/:818/:832-835`. En el frontend (repo aparte): botón "marcar como revisado" en `PanelLinea`, filtros de Revisión y stats del Dashboard.
- Como ya no hay líneas "dadas por buenas", el impacto automático nunca pisa un estado protegido: no hace falta lógica de protección de líneas revisadas.
