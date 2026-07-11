# Valor hora de pulverización configurable por quincena, con recargo fijo en código

El control **Tancadas vs Jornal** valoriza el trabajo de pulverización "a jornal" con la fórmula `hsjornal/2 × (valor_hora_pulv × 1,3)`, para compararlo contra lo que costó pagarlo "a tancada". El `valor_hora_pulv` (valor de una hora de jornal de pulverización) **cambia con el tiempo** —paritarias, acuerdos— así que se guarda como un dato editable **por quincena** (`preliquidacion.valor_hora_pulv`, nullable), que el liquidador carga a mano, en línea con el resto del sistema que ya está scopeado por quincena. El recargo `1,3`, en cambio, queda **fijo en código** (`RECARGO_PULV`): es una constante de negocio estable (el plus de pulverización) que no varía quincena a quincena, y separarlo del valor hora mantiene el input del liquidador como un único número simple (el valor hora "puro", no el ya recargado).

## Considered Options

- **Todo configurable** (valor hora × recargo, ambos por quincena): más flexible, pero pide al liquidador cargar dos números cuando el segundo casi nunca cambia, y abre la puerta a inconsistencias (recargos distintos entre quincenas sin razón real).
- **Todo hardcodeado**: descartado de entrada — el valor hora sube con las paritarias y hardcodearlo obliga a tocar código y redeployar en cada cambio.
- **Elegida**: valor hora por quincena (dato), recargo fijo en código (constante de negocio).

## Consecuencias

- Si algún día el recargo deja de ser fijo (p. ej. distinto por cliente o por tarea), esta decisión se revierte promoviendo `RECARGO_PULV` a dato — pero hoy no hay evidencia de que varíe, así que no se paga ese costo por adelantado.
- Si `valor_hora_pulv` está sin cargar (NULL) en una quincena, el control no puede valorizar "a jornal": las columnas VALOR S/JORNAL y DIFF se devuelven en `null` (no en 0), para no mostrar una comparación falsa contra un jornal de costo cero.
- Se guarda como columna en `preliquidacion` (no en una tabla de parámetros aparte) porque hoy es el único parámetro configurable por quincena y esa tabla ya tiene exactamente una fila por quincena; una tabla clave/valor recién pagaría con varios parámetros.
