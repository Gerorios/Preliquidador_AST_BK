# El importe de una línea es la suma de sus conceptos adicionales

El importe total que cobra una persona por una línea nace **exclusivamente** de la suma de sus conceptos adicionales (cada uno `unidad_base × precio`). Se decidió así tras varias reuniones que descartaron el modelo anterior de "precio A / precio B", donde el liquidador elegía entre dos precios alternativos por tarea. En consecuencia: `importe_base` es siempre 0 y los campos `precio_a`, `precio_b`, `precio_usado` quedan como fósiles del modelo viejo (no impactan el cálculo).

## Consecuencias

- El selector de precio A/B debe salir de la pantalla de Revisión: hoy "elegir B" no cambia nada y confunde al liquidador.
- `precio_b`, `precio_usado`, `importe_base` y la columna muerta `detalle_concepto` quedan marcados como *deprecated* para eliminación futura del modelo y del schema de la DB.
- `precio_a` puede conservarse solo como referencia/display si aporta, pero no participa del total. Antes de retirarlo del todo hay que redirigir su único consumidor real, `control_plantas_jornal` (`preliquidacion_service.py:637`), para que tome el precio del concepto aplicable por-unidad (planta) en vez de `precio_a`. También se elimina el fallback a `precio_a` en `_generar_conceptos_automaticos` (ver ADR-0003).
- `calcular_importe`, `calcular_jornal` y `calcular_bins` (`motor_reglas.py:74-110`) son código muerto del modelo viejo (nadie los llama; el cálculo real pasa por `_recalcular_importe`) y se eliminan.

## Estado de implementación (rama `ws1-retirar-modelo-viejo-precios`)

Hecho:
- `calcular_importe`/`calcular_jornal`/`calcular_bins` y sus constantes (`GRUPOS_PAGO_*`, `VALOR_JORNAL`, `VALOR_BIN`, `HORAS_MINIMAS_JORNAL`, `CLIENTES_JORNAL_PROPORCIONAL`) eliminados de `motor_reglas.py`.
- `control_plantas_jornal` redirigido: el precio promedio sale del concepto del maestro con `unidad_base = unidades` (específico primero, común como fallback), no de `precio_a`.
- `_generar_conceptos_automaticos` ya no cae a `precio_a`: un concepto sin precio no genera `ConceptoAdicional` (evita importe 0 en silencio).
- `precio_b`/`precio_usado` eliminados del modelo (`models.py`), del enum `PrecioUsado` (eliminado), de `LineaResponse`/`LineaUpdateRequest` (`schemas.py`) y de `actualizar_linea`.
- Frontend: `PanelLinea.jsx` ya no trackea `precio_b`/`precio_usado` en el form/payload (no había selector visible, era plumbing muerto).
- Tests unitarios agregados (`tests/test_motor_reglas.py`, `tests/test_generar_conceptos.py`) cubriendo `calcular_cantidad_concepto` (incluido el borde de `jornal_tope1` a las 5h) y el nuevo comportamiento de "sin precio → sin fila".
- Script de migración `migrations/ws1_drop_columnas_precio_ab.sql` (deprecate-then-drop): dropea `precio_b`, `precio_usado` y la columna huérfana `detalle_concepto`. **No ejecutado en producción** — a criterio del usuario, después de deployar el código.

Pendiente (fuera de WS1):
- `importe_base` sigue en el modelo y se sigue escribiendo (siempre 0); su eliminación queda para un paso de limpieza posterior, no en esta rama.
- `Verificacion.jsx:85` todavía recalcula el control de plantas del lado del cliente usando `precio_a` — al retirar `precio_a` del todo (fuera del alcance de WS1), esa pantalla debe pasar a consumir el endpoint `control_plantas_jornal` ya redirigido.
- El selector A/B en Revisión: se confirmó que no existía como UI (solo plumbing en el form); no hubo componente visual que remover.
