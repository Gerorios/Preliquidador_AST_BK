# Marca "reemplaza al común" en el concepto específico

La regla histórica era que los conceptos **comunes y específicos siempre suman** (una línea cobra los comunes de su tarea más los específicos de su cliente/finca). Eso es correcto cuando el específico es un **plus adicional**, pero rompe el caso —real— en que el específico es el **precio total** de esa finca: p. ej. "carga de fruta por bins" se paga igual en 19 fincas (común), pero una finca cobra distinto, y al cargarle el específico esa finca terminaba cobrando **común + específico** cuando debía cobrar **solo el específico**.

Se agrega una marca booleana **`reemplaza_comun`** al `concepto_liquidacion` (solo tiene sentido en los específicos — los que tienen cliente/finca). Cuando una línea matchea un específico con `reemplaza_comun = True`, **se descartan los conceptos comunes de esa tarea para esa línea** y paga solo lo específico. Se aplica en los dos caminos de matching (generación y recálculo reactivo) para ser consistente.

## Por qué una marca y no una regla automática

No se puede inferir del dato si un específico "reemplaza" o "suma": común y específico de una misma tarea **no comparten código**, así que no hay forma de saber cuál común "equivale" al específico. Y existen ambos casos legítimos (reemplazo y plus-que-suma). Por eso la decisión la toma el liquidador con una marca explícita, en vez de una heurística que se equivocaría en la mitad de los casos y pagaría mal.

## Consecuencias

- **Default apagado ⇒ comportamiento histórico intacto.** La regla "comunes y específicos suman" sigue valiendo en todos lados salvo donde se marque; migración y cambio son retrocompatibles.
- El descarte es **por tarea**: un específico marcado suprime **todos** los comunes de esa tarea en esa línea (no "el equivalente", que no es identificable). Si en el futuro hiciera falta suprimir selectivamente, se refina.
- Otras fincas de la misma tarea, sin específico, siguen cobrando el común normal — la marca solo afecta a las líneas que matchean ese específico.
- Es un cambio **sensible al pago**: cubierto con tests (suma sin marca / solo específico con marca / otras fincas intactas / vía recálculo reactivo).
- Revierte parcialmente la redacción del glosario (`Concepto específico`), ahora condicionada a esta marca.

## Actualización (2026-07-14): la marca nace prendida (opt-out)

Al usarlo en la práctica, el caso "el específico es el precio total de la finca" (reemplaza) resultó ser el **normal**, y el "común base + específico plus que suma" el **raro**. Por eso el default se invirtió: al **crear** un concepto específico, `reemplaza_comun` nace en **True** (el liquidador lo destilda solo en el caso raro), en vez de nacer apagado. El motor de matching **no cambió** — sigue siendo la misma regla, solo cambió el valor por defecto al crear.

Alcance del cambio de default:
- Aplica **solo a específicos nuevos**. Los específicos **ya existentes conservan su valor** (no se flipean para no alterar pagos de quincenas ya definidas).
- El default se resuelve al crear: si el request no manda `reemplaza_comun`, se pone True para específicos (cliente/finca) y False para comunes; si lo manda explícito, se respeta.
- `copiar_quincena` sigue copiando el valor tal cual (no fuerza el nuevo default sobre lo copiado).
