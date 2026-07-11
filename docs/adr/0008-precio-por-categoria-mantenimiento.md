# Precio por categoría de mantenimiento: dimensión `categoria` en el maestro, resuelta por persona (CUIL)

La tarea de mantenimiento mecánico (talleres) se paga distinto según la **categoría** (1–7) de cada operario, pero el sistema de campo la extrae siempre igual ("MANTENIMIENTO MECANICO (TALLERES)"), sin distinguir categoría, y el sistema de sueldos —donde vive una categoría de convenio— es de solo lectura y significa otra cosa. Se decidió **extender el maestro de conceptos** (`concepto_liquidacion`) con una columna `categoria` nullable en vez de crear un maestro y un motor de cálculo paralelos: un Concepto con `categoria = NULL` se comporta como siempre, y uno con `categoria = X` aplica a una línea **solo si la categoría de la persona (cruzada por CUIL) es X**. La categoría de cada persona vive en una tabla propia nueva `categoria_operario` con clave `(quincena, cuil)`, que el liquidador administra por quincena.

## Considered Options

- **Extender el maestro (elegida):** una columna `categoria` en `concepto_liquidacion` + un filtro en el matching por la categoría de la persona. Reusa toda la maquinaria existente: la misma UI del maestro, el matching, el recálculo reactivo (ADR-0002) y el congelado en `concepto_adicional` (que alimenta el export). El costo es un retoque puntual en el matching y ampliar el índice único.
- **Maestro separado + generador especial:** una tabla `precio_categoria_mantenimiento` dedicada y un generador de conceptos aparte, disparado al reconocer la tarea de taller por nombre. Rechazada: duplica matching, recálculo y UI, y obliga a hardcodear/parametrizar el nombre de la tarea.
- **Guardar la categoría en sueldos (`nuempleados`):** imposible —es solo lectura— y además esa categoría es de convenio, no varía por quincena a mano del liquidador, y probablemente signifique otra cosa.

## Consecuencias

- El índice único de `concepto_liquidacion` pasa a incluir `categoria`: `(quincena, tarea_nombre, cliente_nombre, finca_nombre, codigo, categoria)`. Sin esto, las 7 filas de mantenimiento (mismo código, distinta categoría) chocarían. Las filas viejas con `categoria = NULL` no se ven afectadas.
- La tarea de taller **no se hardcodea**: queda identificada por tener Conceptos con categoría cargados. Si mañana otra tarea se paga por categoría, alcanza con cargarle Conceptos con categoría.
- El cruce es por **CUIL** (identidad física de la persona), no por `(legajo, empresa)`: un operario cobra según su categoría sin importar bajo qué empresa/legajo se le cargó la línea, y sobrevive a las reasignaciones de empresa.
- Nuevo disparador de **recálculo reactivo**: cambiar la categoría de una persona regenera sus líneas de taller de la quincena, igual que hoy lo hace editar un precio del maestro (ADR-0002). Nunca queda un importe viejo colgado.
- Persona sin categoría asignada, o categoría sin precio cargado → la línea cae en la lógica existente de **Línea incompleta** (ADR-0003), sin inventar un estado nuevo; para el caso "sin categoría" se muestra un aviso distintivo.
- La categoría se **hereda** de la quincena anterior al abrir una nueva (misma filosofía que el Precio heredado, ADR-0004), para solo ajustar cambios.
