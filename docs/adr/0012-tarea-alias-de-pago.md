# Tarea alias de pago: HORAS EXTRAS de taller paga con el maestro de la tarea canónica

El campo creó la tarea `MANTENIMIENTOS MECANICOS HORAS EXTRAS (TALLERES)` con un único propósito: **identificar** cuántas horas de `MANTENIMIENTOS MECANICOS (TALLERES)` fueron extras (ej. una carga de 20 hs se desdobla en 15 comunes + 5 extras), para que la liquidación formal las distinga en el Excel. El flujo de pago es idéntico: mismas categorías de operario (ADR-0008), mismos conceptos por categoría, mismos precios, sin recargo. Sin intervención, el liquidador tendría que duplicar en el maestro todos los conceptos de taller (hasta 12 categorías × caminos de matching) para una tarea que no es una tarea distinta.

Se introduce el concepto de **tarea alias de pago**: un mapeo hardcodeado `TAREAS_ALIAS_PAGO = {alias → canónica}` en `preliquidacion_service.py`. En el punto único de matching, la búsqueda de conceptos se hace con el nombre de la **canónica**; la línea conserva su `nombre_tarea` real (esa identificación es el propósito de la tarea). El alias es **total**: la tarea alias no existe para el maestro — excluida del panel de faltantes, y crear conceptos para ella devuelve error claro. El recálculo reactivo aplica el mapeo **en sentido inverso**: editar un concepto de la canónica recalcula también las líneas del alias, y la página de Mantenimiento trata las líneas del alias como líneas de taller (la persona aparece para asignarle categoría aunque solo tenga horas extras).

## Considered Options

- **Alias total hardcodeado (elegida).** Un diccionario constante, mismo patrón que `EMPLEADOS_MENSUALIZADOS`: el caso es único, nace de una decisión organizativa estable, y el comportamiento queda determinístico y testeable. La tarea alias jamás tiene reglas propias, así que nunca hay dos fuentes de verdad para la misma hora.
- **Equivalencias configurables por UI (rechazada).** Tabla nueva + migración + CRUD + pantalla + validación de ciclos, para un solo par conocido. Se reevalúa si aparecen dos o tres pares más.
- **Alias como fallback (rechazada).** Usar el maestro de la canónica solo si el alias no tiene reglas propias. Rechazada porque permite que una regla propia creada por error cambie el pago en silencio, y nadie podría razonar después por qué una quincena pagó distinto.
- **Que el liquidador duplique los conceptos (statu quo, rechazada).** Es exactamente el trabajo manual y propenso a divergencia de precios que se quiere evitar; cada cambio de precio habría que hacerlo dos veces.

## Consecuencias

- **Sensible al pago**: las líneas de la tarea alias pasan de "incompletas sin solución" a pagar con el maestro de taller existente. No hay retroactividad: al decidirse, ninguna quincena generada tenía líneas de la tarea alias.
- El recargo por hora extra **no existe en el preliquidador** — si algún día se paga distinto, es una feature nueva, no una extensión de este alias.
- El control de excesos (>13 hs/día) sigue sumando las horas reales de la persona sin importar la tarea: 15 comunes + 5 extras el mismo día siguen siendo un exceso de 20 hs (deseado — el desdoblamiento es administrativo, las horas son reales).
- Crear un concepto para la tarea alias devuelve 422 con mensaje explicando con qué tarea paga.
- Sin migración de base: el mapeo vive en código.
