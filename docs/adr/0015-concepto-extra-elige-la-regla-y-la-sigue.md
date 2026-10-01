# Concepto extra: el liquidador elige código y opción, y el extra conserva la opción

"Agregar por código" en Revisión (una línea o varias a la vez) se usa para sumar un **plus que no es de la tarea de la línea**. El maestro tiene varias reglas con el mismo código en una quincena, una por tarea, cliente, finca o supervisor, con precio, unidad base y tipo distintos (en `testing`, el código 902 está en decenas de tareas de una misma quincena). Hasta ahora el sistema tomaba la primera regla que encontraba con ese código, así que el precio pagado era arbitrario.

Se decidió que **el liquidador elige el código y, si hace falta, una opción**. Una opción es una combinación de precio y unidad base entre las reglas con precio y sin categoría de ese código en la quincena; el tipo se muestra sólo cuando hace falta para distinguir dos opciones. Si hay una sola opción, se agrega directo. El liquidador no ve tareas: detrás de una opción puede haber muchas. En un agregado masivo se elige una opción para todas las líneas marcadas, y cada línea calcula su cantidad.

El **Concepto extra** queda atado a la regla de la opción cuya tarea va primero por orden alfabético, y la línea muestra de qué tarea salió. **Conserva la opción elegida mientras alguna regla de ese código la siga ofreciendo**: si su regla cambia de precio o de unidad, se borra, o queda sin precio o sin código, el extra pasa a otra regla con la misma opción. Si ya no queda ninguna, el extra sigue a su regla con el precio o la unidad nuevos; y si la regla se borró o quedó sin precio o sin código, el extra se borra, con aviso y confirmación previa en Conceptos.

## Considered Options

- **Usar la regla que matchea la tarea, cliente, finca y supervisor de la línea, como el cálculo automático (rechazada).** El uso real es un plus de otra tarea: con la línea sola no hay ninguna regla que matchee.
- **Que el liquidador elija la tarea exacta (rechazada por el usuario).** Ataba el extra a una regla sin ambigüedad, pero el liquidador piensa en "código, precio y unidad", no en tareas, y la lista se volvía larga.
- **Que el liquidador escriba el precio (rechazada).** El precio quedaba sin vínculo al maestro y sin control.
- **Que el sistema elija con un criterio fijo, como el precio más alto o el más frecuente (rechazada).** Seguía siendo adivinar, y el liquidador no veía lo que pagaba.
- **Distinguir opciones sólo por precio (rechazada).** El importe es cantidad × precio, y la cantidad depende de la unidad: el código 449 tiene un solo precio, pero se paga como monto fijo en una regla y por jornal en otra.
- **Que el extra quede fijo con el precio con que se agregó (rechazada por el usuario).** Era el comportamiento previo y el cambio más chico, pero dejaba extras desalineados del maestro cuando se corrige un precio, en contra del impacto reactivo (ADR-0002).
- **Que el extra siga siempre a su regla, aunque otras reglas sigan ofreciendo su opción (rechazada por el usuario).** Atarlo a la primera tarea alfabética es arbitrario, y un cambio en esa regla le pegaba al extra aunque la opción que eligió el liquidador siguiera existiendo.

## Consecuencias

- Al pasar a otra regla, se elige otra vez la primera por orden alfabético de tarea, y se actualiza la tarea que muestra la línea.
- Si la regla recupera el precio después de que el extra se borró, el extra no vuelve solo: hay que agregarlo otra vez.
- Agregar un código que la línea ya tiene no se bloquea, porque puede ser legítimo. El sistema avisa y pide confirmación; en el masivo se elige entre agregarlo igual o saltear esas líneas.
- Las reglas por categoría (ADR-0008) no se ofrecen como extra.
- Un extra es un concepto ingresado por una persona y con vínculo a una regla. El concepto manual sin regla no cambia.
