# Liquidación Terceros — La Asturiana SRL

Lenguaje ubicuo del módulo **Liquidación Terceros**, el segundo módulo del Sistema (ver "Sistema y módulos" en `CONTEXT.md`). Este archivo es un glosario: define qué ES cada término, no cómo se implementa.

Escrito a partir de la sesión de grilling del 2026-09-09 sobre el Excel que hoy resuelve el circuito. Las decisiones de diseño y el orden de trabajo están en [`plan-terceros.md`](plan-terceros.md); las fuentes originales (el Excel maestro, las consultas de Power Query y los archivos de las estaciones y de seguros) están en `fuentes/`, fuera de git.

---

## El módulo

**Liquidación Terceros**:
El módulo que liquida lo que la empresa le paga y le descuenta a los terceros que le prestan servicio. Cubre dos circuitos que comparten el mismo sujeto que cobra: **Fletes** (traslado de personal a las fincas en colectivos) y **Horas de taller** (mano de obra propia aplicada a maquinaria ajena). No son dos módulos porque las horas de taller son un término del neto del recibo de flete.
_Avoid_: llamarlo "Fletes" — los fletes son uno de sus dos circuitos, y el más chico en cantidad de terceros.

**Tercero**:
La persona o empresa a la que se le liquida: el que cobra los viajes y al que se le descuenta lo que consumió. Puede ser transportista (tiene colectivos), contratista de maquinaria (tiene máquinas que se reparan en el taller), o las dos cosas. Es el sujeto del Recibo y el titular del Saldo.
_Avoid_: "dueño de colectivo" (deja afuera a los contratistas de maquinaria, que son la mayoría de los terceros del taller), "proveedor"

**Colectivo**:
El vehículo con el que un Tercero traslada personal a las fincas, identificado por su **patente**. Un Tercero puede tener muchos colectivos. En el sistema de campo cada colectivo es una fila cuyo `nombre` es, en realidad, **el nombre de su dueño** — por eso un mismo nombre aparece repetido en tantas filas como vehículos tenga.
_Avoid_: usar "colectivo" para hablar del dueño, aunque el sistema de campo lo haga

**Maquinaria de tercero**:
Máquina (tractor, cargadora, pulverizadora, elevador) que pertenece a un Tercero y que se repara en el taller de la empresa. Existe en tres sistemas a la vez con tres identificadores distintos y tres nombres distintos; el puente entre ellos es el **id del sistema de campo**, no el nombre.

**Quincena**:
El período de liquidación, el mismo corte que el resto del Sistema: 1ra = días 1 a 15, 2da = 16 a fin de mes. En el Excel de origen se escribe `MM-1Q` / `MM-2Q`.

---

## Lo que se liquida

**Recibo**:
El documento que se le manda a cada Tercero al cerrar la quincena, con el detalle de lo que se le paga y lo que se le descuenta, el saldo anterior y el total. Es lo que el Tercero usa para emitir su factura. Se emite uno por Tercero y por Quincena, y **una vez emitido queda congelado**: lo que llegue después va al siguiente.

**Recibo de taller**:
El Recibo de un Tercero que **no** es transportista y por lo tanto no tiene recibo de flete: solo lleva sus horas de taller. Es la mayoría de los terceros del taller.

**Neto a pagar**:
Lo que resulta del Recibo de flete:
`Viajes − Combustible − Repuestos − Horas de taller − Seguros + Ajustes`.
Positivo la empresa le paga al Tercero; negativo el Tercero le debe a la empresa.

**Viaje**:
Un traslado de personal a una finca, cargado por el Supervisor en el sistema de campo con su colectivo, chofer, cliente, finca y capataz. La cantidad puede ser **0,5** — medio viaje es normal. Es el único componente del neto que se paga; todos los demás se descuentan.

**Carga de combustible**:
Litros que un colectivo cargó en una estación habilitada, respaldados por un **Vale**. Se descuenta al Tercero al precio por litro que tenga pactado.

**Vale**:
El comprobante físico que el Supervisor le entrega al chofer y sin el cual no puede cargar combustible. Su número es el que identifica la carga en el sistema de campo y **el que permite cruzarla contra lo que factura la estación**.

**Repuesto**:
Repuesto, lubricante o reparación que salió del taller de la empresa hacia una Maquinaria de tercero. Se descuenta al dueño de esa máquina. Su fecha es la de la **descarga a la maquinaria**, no la del encabezado del movimiento ni la de la factura de compra.

**Hora de taller**:
Hora que un mecánico de la empresa dedicó a reparar una Maquinaria de tercero, cargada en la app del taller. Se descuenta al dueño de la máquina, al valor de la hora vigente a la fecha del trabajo. La hora total incluye preparación y traslado. **Solo se cobran las horas aprobadas**: una pendiente todavía no se cobra, y una rechazada no se cobra nunca.

**Seguro**:
Cuota que la empresa le descuenta al Tercero por las pólizas que le cubre. Son de tres clases — del vehículo o la máquina (automotor), del chofer en relación de dependencia, y de accidentes personales — y llegan en un archivo mensual. **Se imputan enteras a la 2da quincena del mes**, no se parten.
_Avoid_: pensar que es solo de los colectivos propios de la empresa; alcanza a colectivos y a maquinaria de terceros

**Ajuste**:
Corrección manual con signo sobre el Recibo, con motivo. Positivo le paga más, negativo le descuenta.

---

## Cómo se determina cuánto se paga

**Tarifa de viaje**:
Regla que el liquidador carga **por quincena** y que determina el Tipo de viaje y el precio. Se define sobre seis dimensiones opcionales —tercero, patente, chofer, cliente, finca y capataz— y la combinación habitual es **tercero + capataz**, porque el capataz identifica adónde va el viaje. No hay ninguna regla que se pueda derivar de los datos: el precio se pacta con cada dueño.
_Avoid_: buscarle una fórmula; es una negociación, no un cálculo

**Tipo de viaje**:
Corto o Largo. No es una clave de la Tarifa sino su **resultado**: la misma regla que fija el precio fija el tipo. No se deduce del destino — un mismo cliente y finca tiene viajes de los dos tipos.

**Regla más específica**:
Cuando dos Tarifas alcanzan al mismo Viaje, gana **la que tiene más dimensiones cargadas**: una regla con más condiciones es una excepción deliberada sobre una más general. Si empatan en cantidad de dimensiones, el viaje queda **ambiguo** y lo resuelve el liquidador; el sistema no elige en silencio.

**Tarifa heredada**:
Tarifa que vino copiada de otra quincena y todavía no fue confirmada. Se usa igual, pero queda resaltada hasta confirmarse, para no arrastrar un precio viejo sin darse cuenta. (Mismo criterio que el Precio heredado de Preliquidación, ADR-0004.)

**Precio del combustible**:
Precio por litro que se le descuenta a un Tercero, cargado **por quincena y por tercero**. No depende de la estación ni del tipo de carga.

**Valor de la hora de taller**:
Precio de la hora de mano de obra, con vigencia desde una fecha. A una hora se le aplica el valor vigente **a la fecha del trabajo**, no el de hoy.

---

## Cuándo se cobra

**Quincena de imputación**:
La quincena a la que un gasto pertenece por su fecha.

**Quincena efectiva**:
La quincena en la que un gasto **realmente se cobra o se descuenta**, cuando no es la de su fecha. La carga el liquidador a mano, con **motivo**, y existe por dos razones distintas que conviene no confundir: porque el dato llegó tarde (la gente sigue cargando viajes después de cerrada la quincena, y el recibo sale a los tres días), o porque la empresa **decidió** no descontarle algo a un Tercero esa quincena para ayudarlo. La segunda no se deduce de ninguna fecha.

**Quincena de liquidación**:
La que efectivamente se usa para liquidar: la Quincena efectiva si está cargada, si no la de imputación. Es la que filtran todas las cuentas del Recibo.

**Emisión del recibo**:
El momento en que el Recibo se manda al Tercero. Cierra esa quincena para ese Tercero y **congela** el documento: lo que se corrija o llegue después no cambia lo ya enviado, aparece en el Recibo siguiente. Se puede reabrir, con motivo.

**Llegada tardía**:
Un gasto cuya fecha de carga es posterior a la emisión del Recibo de su quincena. El sistema la detecta y **propone** diferirla; la decisión es del liquidador.
_Avoid_: "Alcahuete" (así se llamaba la alerta en el Excel)

---

## La cuenta

**Saldo de la quincena**:
`Neto a pagar − lo efectivamente pagado` para un Tercero en una quincena.

**Saldo acumulado**:
El arrastre de los saldos de todas las quincenas anteriores del mismo Tercero. Es lo que el Recibo muestra como saldo anterior y lo que hace que el total a pagar no sea solo el neto del período.

**Quincena en revisión**:
Quincena cuyo saldo está en discusión con el Tercero y que por eso **no suma** al Saldo acumulado del Recibo: se muestra aparte, como línea informativa, para que se vea que el tema no se olvidó sin ensuciar el número que el Tercero tiene que facturar.

---

## Los sistemas de origen y el cruce

**Sistema de campo**:
El sistema operativo de la empresa donde los Supervisores cargan los viajes y las cargas de combustible, y donde vive el maestro de colectivos y de maquinaria. **Es el maestro**: si un dato está mal, se corrige ahí y no en el módulo. De solo lectura para el Sistema.

**Sistema de compras**:
El sistema donde se registran las salidas de repuestos y las reparaciones hacia las máquinas. De solo lectura. Es la misma base que el Sistema usa como maestro de personal.

**App del taller**:
La aplicación donde los mecánicos cargan las horas trabajadas sobre cada máquina, con su estado de aprobación. El módulo la lee sola, sin que nadie suba nada.

**Alerta de cruce**:
Aviso de que un dato de un sistema no encuentra su par en otro: una máquina sin id del sistema de campo, un tercero de un archivo de seguros que el sistema de campo no conoce, un vale facturado por una estación que no está cargado. **No se adivina ni se descarta en silencio**: se avisa, y se corrige en el sistema que corresponde, con su responsable. Es la regla que gobierna todos los cruces del módulo.
_Avoid_: resolver un cruce fallido por parecido de nombre

**Conciliación de combustible**:
Control que compara lo que factura una estación de servicio contra lo que está cargado en el Sistema de campo, cruzando por número de Vale. Devuelve tres listas: lo que la estación facturó y no está cargado (lo que hay que pedirle al Supervisor, y la plata que si no se pierde), lo cargado que la estación no facturó, y lo que está en los dos con litros distintos. No cambia la liquidación: sirve para que el Sistema de campo esté completo antes de emitir los Recibos.
