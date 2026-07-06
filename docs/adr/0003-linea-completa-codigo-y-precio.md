# Una sola noción de completitud: código y precio

Una línea está lista para liquidar cuando tiene **al menos un concepto aplicable con código y precio > 0**. Se colapsan las tres nociones previas de "falta algo" (solapa faltantes = sin ningún concepto, `alerta_sin_codigo`, `alerta_sin_precio`) en una única bandera de "línea incompleta". La solapa "Sin concepto" pasa a listar los combos `tarea + cliente + finca` cuyas líneas todavía no tienen un concepto **completo** (no solo los que no tienen "nada").

## Consecuencias

- Se elimina el fallback a `precio_a` en `_generar_conceptos_automaticos` (`preliquidacion_service.py:337`): un concepto sin precio ya no genera un `ConceptoAdicional` de importe 0. La línea queda marcada como incompleta. Esto evita liquidar sueldos en cero por un precio olvidado.
- El recálculo reactivo (ADR-0002) es el único responsable de setear/limpiar la bandera de incompleta; ya no depende del botón "recalcular precios" eliminado.
- Las dos columnas/banderas `alerta_sin_precio` y `alerta_sin_codigo` se unifican (o una se deriva de la otra) en una sola señal accionable para el liquidador.
