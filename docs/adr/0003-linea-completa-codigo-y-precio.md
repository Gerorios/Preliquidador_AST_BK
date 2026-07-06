# Una sola noción de completitud: código y precio

Una línea está lista para liquidar cuando tiene **al menos un concepto aplicable con código y precio > 0**. Se colapsan las tres nociones previas de "falta algo" (solapa faltantes = sin ningún concepto, `alerta_sin_codigo`, `alerta_sin_precio`) en una única bandera de "línea incompleta". La solapa "Sin concepto" pasa a listar los combos `tarea + cliente + finca` cuyas líneas todavía no tienen un concepto **completo** (no solo los que no tienen "nada").

## Consecuencias

- Se elimina el fallback a `precio_a` en `_generar_conceptos_automaticos` (`preliquidacion_service.py:337`): un concepto sin precio ya no genera un `ConceptoAdicional` de importe 0. La línea queda marcada como incompleta. Esto evita liquidar sueldos en cero por un precio olvidado.
- El recálculo reactivo (ADR-0002) es el único responsable de setear/limpiar la bandera de incompleta; ya no depende del botón "recalcular precios" eliminado.
- Las dos columnas/banderas `alerta_sin_precio` y `alerta_sin_codigo` se unifican (o una se deriva de la otra) en una sola señal accionable para el liquidador.

## Estado de implementación (rama `ws3-completitud-unica`)

Hecho:
- Columna única `linea_incompleta` (default `True`) reemplaza `alerta_sin_precio`/`alerta_sin_codigo` en `models.py`, `schemas.py` (`LineaResponse`).
- `_procesar_fila_con_cache` (generación) y `_aplicar_conceptos_a_lineas` (recálculo reactivo/manual) calculan completitud sobre reglas con **código Y precio** — un concepto con código pero sin precio ya no cuenta como completo.
- `listar_lineas` (`solo_alertas`) y `estadisticas` (`incompletas`, `lineas_con_alerta`) migrados a la señal única.
- La query de faltantes (`precios.py: /conceptos/faltantes`) ahora exige `codigo IS NOT NULL AND precio IS NOT NULL` en el `EXISTS` — lista combos sin concepto **completo**, no solo sin nada.
- **Consecuencia directa encontrada al implementar:** `recalcular_precios` (el método viejo que escribía `alerta_sin_precio`/`precio_a` por SQL crudo) quedó roto por el cambio de columna y se eliminó por completo, junto con el endpoint `/recalcular`. Era vestigial desde WS1 (su único consumidor real, el control de PLANTA, ya se había redirigido). `aplicar()` (botón "Aplicar" de Revisión) se simplificó para solo llamar `aplicar_conceptos`.
- Frontend: chip/badge/alerta renombrados de "Sin precio" a "Incompleta"; se sacaron `recalcularPrecios` (rota, endpoint eliminado) y dos mutations muertas (`recalcular`/`aplicarConc`, sin botón que las disparara).
- Tests: 1 test nuevo (`test_codigo_sin_precio_no_cuenta_como_completa`) + los 17 existentes actualizados al nuevo nombre de campo — 18/18 verdes.
- **Migración distinta a WS1/WS2 — no diferible:** esta migración *agrega* una columna que el ORM escribe en cada INSERT de línea; sin aplicarla, `generar()` rompe en producción de inmediato (confirmado con un smoke test real que reprodujo el `OperationalError: Unknown column`). Se aplicó contra producción con backup previo (`preliquidacion_linea_bkp_ws3`, 1586 filas) y backfill correcto (442 líneas quedaron incompletas, coincide con el conteo de "sin precio" visto antes de esta rama). El servidor de desarrollo real (`uvicorn --reload`) absorbió el cambio de código sin downtime.
