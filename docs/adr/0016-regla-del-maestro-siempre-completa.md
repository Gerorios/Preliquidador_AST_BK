# Una regla del maestro siempre tiene código y precio > 0

Un Concepto (regla del maestro, `concepto_liquidacion`) **no se puede guardar sin código ni sin precio, ni con precio 0 o negativo**. Lo exige el backend en todos los caminos que escriben esos campos (alta, edición, precio masivo y copia entre quincenas), y el front lo avisa antes de mandar. Hasta ahora una regla podía quedar vacía y la línea quedaba incompleta (ADR-0003). Desde esta decisión, una regla vacía no es un estado válido del maestro: "línea incompleta" pasa a querer decir que a la línea no le aplica ninguna regla, o que no hay regla para la categoría de la persona. Ya no puede querer decir que la regla existe pero está vacía.

La categoría y el supervisor siguen siendo opcionales, porque vacíos tienen significado (concepto sin categoría, ADR-0008; camino que no es por supervisor, ADR-0011). La unidad base y el tipo ya llevaban siempre un valor.

## Considered Options

- **Dejarlo como estaba** (rechazada): una regla vacía es un olvido que se ve recién en la línea, y la copia entre quincenas lo arrastra de una quincena a la otra.
- **Exigirlo sólo en el front** (rechazada): un front viejo en caché, o cualquier otro llamado a la API, sigue pudiendo grabar reglas vacías.
- **Aceptar precio 0** (rechazada): una regla con precio 0 no completa la línea (ADR-0003). Aceptarlo sería guardar la misma regla vacía con otro valor.
- **`NOT NULL` y `CHECK precio > 0` en la base** (rechazada por ahora): obliga a limpiar producción y a aplicar DDL, y el beneficio frente a la validación en la API es chico. Si después aparece otro camino de escritura que no pase por la API, se revisa.

## Consecuencias

- **Copia entre quincenas**: las reglas de origen sin código o sin precio no se copian, y el resultado las cuenta ("N omitidas por incompletas"). El liquidador las carga completas en la quincena nueva. Es la única excepción a "copiar todo" de ADR-0004. El precio heredado sigue igual: es un precio que existe, sólo que sin confirmar.
- **Edición**: sigue siendo parcial (lo que no se manda queda igual), pero mandar el código o el precio vacíos, o un precio <= 0, se rechaza. Una regla vieja incompleta se puede editar, y con el front nuevo hay que completarla para poder guardarla.
- **Reglas que ya existen incompletas** quedan como están. Antes del deploy se cuentan en producción desde el VPS. En `testing`, al 2026-10-01, no había ninguna.
- **Concepto extra** (tarea en curso, ADR-0015 reservado): una regla ya no puede quedar sin código ni sin precio por edición, así que el caso "vaciar el precio borra el extra" deja de existir. El "sin precio" que ese ADR trata queda sólo para reglas viejas.
