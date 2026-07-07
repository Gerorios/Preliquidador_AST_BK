# Feedback global de UI y reducción de latencia

Tres decisiones tomadas al atacar la queja de "la app se siente colgada y sin feedback".

## Feedback global de actividad

En vez de cablear un spinner por pantalla, hay un único indicador global (`ActivityBar`) que usa `useIsFetching` + `useIsMutating` de React Query: aparece automáticamente en cualquier operación en vuelo ("Guardando…"/"Cargando…"). Además, un cambio de concepto invalida también las queries de Revisión (`['lineas']`, `['stats']`) para que el impacto reactivo (ADR-0002) se vea reflejado sin recargar. Toasts movidos a top-center, más visibles.

## N+1 en el recálculo reactivo (bug de performance)

`_aplicar_conceptos_a_lineas` hacía `commit()` después del DELETE de conceptos automáticos. Con `expire_on_commit` (default de SQLAlchemy), eso expira los objetos ya cargados, y el loop posterior disparaba **una query de recarga por línea** contra la base remota. Un concepto común sobre 427 líneas tardaba **241s**. Se reestructuró para trabajar en memoria: snapshot del importe de conceptos manuales antes de tocar la sesión, DELETE sin commit, importe calculado inline, un solo commit al final. Medido: **241.40s → 1.53s (157x)**. Regla general para este código: **no acceder atributos de objetos ORM después de un commit intermedio** si se van a recorrer muchas filas contra la base remota.

## Cache del maestro de sueldos a nivel de proceso

`SueldosService` recargaba las ~15.500 personas de la base remota en cada request (~12s), porque se instancia por-request. Ahora el índice se carga **una vez por proceso** y se reusa entre instancias, con un **TTL de 30 min**.

**Trade-off aceptado:** si se da de alta o modifica un empleado en `nuempleados`, la app no lo ve hasta que vence el TTL o se reinicia el proceso. Se consideró aceptable porque el maestro de empleados casi no cambia y rara vez impacta la quincena que se está generando. **Mitigación:** endpoint `POST /api/preliquidacion/refrescar-sueldos` para forzar la recarga sin reiniciar. Single-worker (uvicorn --reload) → sin locks.
