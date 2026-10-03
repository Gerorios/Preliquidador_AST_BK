# El control Tancadas vs Jornal compara el valor hora pagado por hora de máquina contra el valor hora de pulverización × 1,3, sin dividir por 2

El control **Tancadas vs Jornal** compara, por cliente, finca y tarea, el **valor hora efectivamente pagado por hora de máquina** en las tareas pagadas por tancada (Σ importe de los conceptos de tancada ÷ Σ horas de máquina) contra una **referencia**: el Valor hora pulverización que el liquidador carga por quincena, multiplicado por el recargo fijo 1,3. La variación es (valor hora pagado − referencia) ÷ referencia. La tancada se registra ida y vuelta (el dato viene doblado), pero el pago la toma tal como viene y el control hace lo mismo: **no hay ningún ÷2**. Las horas de jornal se muestran como dato pero no participan del cálculo. El total se recalcula sobre las sumas y sólo con las filas que tienen horas de máquina; una fila sin horas de máquina se muestra pero no tiene variación.

Reemplaza **sólo la fórmula** del ADR-0007; lo demás (valor hora por quincena como dato, recargo 1,3 fijo en código) sigue vigente.

## Considered Options

- **La fórmula anterior** (`hsjornal/2 × valor_hora_pulv × 1,3` contra `tancadas/2 × precio`), rechazada: dividía por 2 un dato que el pago no divide y comparaba contra horas de jornal; no coincidía con la planilla del liquidador.
- **Comparar contra horas de jornal** (sin ÷2), rechazada: la referencia es un valor hora de máquina, no de presencia.
- **Promediar las variaciones de las filas para el total**, rechazada: un promedio de porcentajes miente; el total se recalcula sobre las sumas, como en Plantas vs Jornal.
- **Usar `valor_hora_tractorista`** (el de Plantas vs Jornal), rechazada: son dos controles con dos parámetros; el liquidador carga en Valor hora pulverización el valor hora base y el sistema le suma el 30 %.

## Consecuencias

- Salen "Valor s/jornal", "Valor s/tancada" y "Diff"; entran "Precio tancada", "Importe pagado", "Valor hs/máquina pulv", "Valor hs pulv × 1,3" y "Variación".
- Se aplica a todas las quincenas al leer: cambian los números de las quincenas pasadas; lo pagado no.
- Sin el valor hora cargado, referencia y variación quedan en null, como hasta ahora.
- Sin migración de base.
