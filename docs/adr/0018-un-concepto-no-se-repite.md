# Un Concepto no se repite: la base lo impide

Dos Conceptos con la misma quincena, tarea, código, alcance (cliente, finca, supervisor) y categoría son el **mismo Concepto** y no pueden coexistir: el motor suma cada regla que matchea una línea, así que el repetido paga dos veces. Si una tarea tiene que pagar más, se carga **un solo Concepto con el precio total**. El precio no participa de la comparación: con otro precio sigue siendo la misma regla, y para cambiarlo se edita. Los textos se comparan como lo hace el Matching, sin distinguir mayúsculas ni espacios de más.

Lo garantiza un **índice único en la base**, y la API traduce el rechazo a un mensaje para el liquidador en el alta y en la edición. La copia entre quincenas saltea las reglas que ya existen en el destino y también las repetidas dentro del origen. El índice único que existía (`uq_concepto_unif`) no frenaba nada: cada regla tiene cliente o supervisor en NULL (ADR-0011), y para la base dos NULL nunca son iguales.

Pasó en la segunda quincena de agosto de 2026: una tarea que paga combinada ("poda + 20%") quedó cargada como dos reglas iguales con el mismo código. Para el gerente el monto era correcto, pero el maestro mostraba dos reglas donde había un solo precio, y nada impedía que la misma regla se repitiera por un doble clic, como pasó en la quincena siguiente.

## Considered Options

- **Bloquear el código repetido en toda la quincena** (rechazada): hoy el mismo código se usa legítimamente en tareas distintas (dos tareas que pagan los mismos códigos de horas, dos variantes de una poda con el mismo código), y la copia entre quincenas fallaría.
- **Chequear sólo en la API** (rechazada): dos pedidos casi simultáneos (el doble clic) pasan los dos el chequeo, y la edición, la copia o un SQL a mano quedarían sin cubrir. ADR-0016 eligió validar sólo en la API porque ahí el beneficio de la base era chico; acá es justamente lo que frena el caso real.
- **Dejar sumar dos reglas iguales a propósito** (rechazada): es la única forma de pagar doble sin que se note en el maestro. Una tarea que paga más lleva el precio total en una regla.

## Consecuencias

- **No se puede instalar con repetidos.** La migración falla si queda algún Concepto repetido. Antes del deploy se cuentan en producción, y el liquidador los unifica desde la pantalla de Conceptos.
- **Más estricto que el Matching en acentos.** La base compara sin distinguir acentos y el motor sí los distingue. Dos fincas que difieran sólo en un acento quedarían frenadas como la misma regla. Es un caso raro y se acepta. La copia entre quincenas compara igual que la base (sin acentos), para no chocar contra el índice.
- Cliente, finca y supervisor vacíos cuentan igual que sin cargar, como en el Matching.
