# Liquidación Terceros — La Asturiana SRL

Lenguaje ubicuo del módulo **Liquidación Terceros**, el segundo módulo del Sistema (ver "Sistema y módulos" en `CONTEXT.md`). Este archivo es un glosario: define qué ES cada término, no cómo se implementa.

Escrito a partir de la sesión de grilling del 2026-09-09 y revisado el 2026-09-16, cuando apareció el segundo circuito (servicio de maquinaria). Las decisiones de diseño y el orden de trabajo están en [`plan-terceros.md`](plan-terceros.md); las fuentes originales están en `fuentes/`, fuera de git.

---

## El módulo

**Liquidación Terceros**:
El módulo que liquida lo que la empresa le paga y le descuenta a los terceros que le prestan servicio. Cubre dos servicios distintos con el mismo sujeto que cobra y el mismo recibo: el Servicio de flete y el Servicio de maquinaria.
_Avoid_: llamarlo "Fletes" — el flete es uno de sus dos servicios

**Tercero**:
La persona o empresa a la que se le liquida: la que cobra por lo que presta y a la que se le descuenta lo que consumió. Es el sujeto del Recibo y el titular del Saldo.
_Avoid_: "dueño de colectivo" (deja afuera a los de maquinaria), "proveedor"

**Servicio de flete**:
Un Tercero traslada personal a las fincas con sus Colectivos. Lo que se le paga son los Viajes.
_Avoid_: "fletes" a secas cuando se habla del módulo entero

**Servicio de maquinaria**:
Un Tercero pone su Maquinaria a trabajar en las fincas de la empresa. Lo que se le paga son las Horas de servicio.
_Avoid_: confundirlo con el taller — acá la máquina del Tercero **trabaja**; en el taller la **reparan**

**Colectivo**:
El vehículo con el que un Tercero presta el Servicio de flete, identificado por su **patente**. Un Tercero puede tener muchos. En el sistema de campo cada colectivo es una fila cuyo `nombre` es, en realidad, el nombre de su dueño.
_Avoid_: usar "colectivo" para hablar del dueño, aunque el sistema de campo lo haga

**Maquinaria de tercero**:
Máquina (tractor, cargadora, pulverizadora, elevador) que pertenece a un Tercero. Participa de los dos lados del recibo: **trabaja** en las fincas (Hora de servicio, se paga) y **se repara** en el taller de la empresa (Hora de reparación y Repuesto, se descuentan).

**Quincena**:
El período de liquidación, el mismo corte que el resto del Sistema: 1ra = días 1 a 15, 2da = 16 a fin de mes. En el Excel de origen se escribe `MM-1Q` / `MM-2Q`.

---

## Lo que se le paga al Tercero

**Viaje**:
Un traslado de personal a una finca, cargado por el Supervisor en el sistema de campo con su colectivo, chofer, cliente, finca y capataz. La cantidad puede ser **0,5**: medio viaje es normal.

**Tipo de viaje**:
Corto o Largo. No es una clave de la Tarifa sino su **resultado**: la misma regla que fija el precio fija el tipo. No se deduce del destino — un mismo cliente y finca tiene viajes de los dos tipos.

**Hora de servicio**:
Hora que una Maquinaria de tercero trabajó en una finca de la empresa, cargada en el sistema de campo junto con su cliente, finca y tarea. Es lo que se le paga al dueño por el Servicio de maquinaria.
_Avoid_: "hora de máquina" (es el nombre de una Unidad base, no del hecho), "hora de taller"

---

## Lo que se le descuenta al Tercero

**Carga de combustible**:
Litros que un Colectivo cargó en una estación habilitada, respaldados por un **Vale**. Solo alcanza al Servicio de flete.

**Vale**:
El comprobante físico que el Supervisor le entrega al chofer y sin el cual no puede cargar combustible. Su número es el que identifica la carga en el sistema de campo y el que permite cruzarla contra lo que factura la estación.

**Repuesto**:
Repuesto, lubricante o reparación que salió del taller de la empresa hacia una Maquinaria de tercero. Su fecha es la de la **descarga a la maquinaria**, no la del encabezado del movimiento ni la de la factura de compra.

**Hora de reparación**:
Hora que un mecánico de la empresa dedicó a reparar una Maquinaria de tercero, cargada en la app del taller. La hora total incluye preparación y traslado. **Solo se cobran las aprobadas**: una pendiente todavía no se cobra, y una rechazada no se cobra nunca.
_Avoid_: "hora de taller" (se confundía con la Hora de servicio, que va en el sentido contrario)

**Seguro**:
Cuota que la empresa le descuenta al Tercero por las pólizas que le cubre. Son de tres clases —del vehículo o la máquina (automotor), del chofer en relación de dependencia, y de accidentes personales— y **se imputan enteras a la 2da quincena del mes**, no se parten. En el Recibo van **después del Total a facturar**, en su propio bloque: el Tercero no los factura.
_Avoid_: pensar que es solo de los colectivos propios; alcanza a colectivos y a maquinaria de terceros

---

## El Recibo

**Recibo**:
El documento que se le manda a cada Tercero al cerrar la quincena, con el detalle de lo que se le paga y lo que se le descuenta, el saldo anterior y el total. Es lo que el Tercero usa para emitir su factura. Se emite uno por Tercero y por Quincena, y **una vez emitido queda congelado**: lo que llegue después va al siguiente. Cierra con **dos cifras y no con una**: el Total a facturar, después el detalle de los Seguros, y recién entonces el Total a pagar.

**Total a facturar**:
Lo que el Tercero le factura a la empresa por la quincena:
`Viajes + Horas de servicio − Combustible − Repuestos − Horas de reparación + Ajustes`.
**El Seguro no entra acá.** Es la cifra que el Tercero copia en su factura, y el seguro no es algo que él le venda a la empresa: es una cuota que la empresa le adelantó y le recupera al pagarle. Meterlo adentro haría que facture de menos.

**Total a pagar**:
`Total a facturar − Seguros`. Es lo que la empresa efectivamente le transfiere, y no coincide con lo que el Tercero factura.
Positivo la empresa le paga al Tercero; negativo el Tercero le debe. Un Tercero que presta un solo servicio simplemente tiene el otro término en cero; no son dos recibos distintos.
_Avoid_: "Neto a pagar" a secas — servía cuando el seguro iba adentro de un total único, y ahora son dos cifras que no dan lo mismo

**Ajuste**:
Corrección manual con signo sobre el Recibo, con motivo. Positivo le paga más, negativo le descuenta.

---

## El Tarifario

**Tarifario**:
El maestro de precios del módulo: cinco tablas, una por cada cosa que se paga o se descuenta. Todas son **por quincena** y ninguna se deriva de los datos — cada precio se pacta con cada Tercero.
_Avoid_: buscarle una fórmula a un precio; es una negociación, no un cálculo

**Tarifa de viaje**:
Regla que determina el Tipo de viaje y el precio de un Viaje, sobre cuatro dimensiones: tercero, cliente, finca y capataz. La combinación habitual es **tercero + capataz**, porque el capataz identifica adónde va el viaje.

**Tarifa de servicio**:
Regla que determina el precio de una Hora de servicio, sobre cuatro dimensiones: tercero, cliente, finca y tarea. Además de un precio, fija la **Unidad base**.

**Unidad base**:
Sobre qué medida se calcula una Tarifa de servicio: la **hora de máquina** o la **cantidad** que midió la tarea. Cuál de las dos es lo pactado con cada Tercero, no una propiedad del dato. La hora de jornal no se paga nunca, aunque el sistema de campo también la cargue. Es el mismo término y el mismo criterio que la Unidad base de Preliquidación (ver `CONTEXT.md`).
_Avoid_: pagar por hora de jornal; dar por sentado que se paga la hora de máquina

**Unidad de la tarea**:
De qué son las cantidades que el sistema de campo carga en un trabajo: BINS, TANCADAS, HORAS, HORAS TRACTOR o JORNAL. Viene del catálogo de tareas y es **informativa**: dice qué mide la tarea, no cómo se paga. Una tarea medida en bins puede pagarse igual por hora — eso lo decide la Unidad base de la tarifa. Es el mismo papel que el Grupo de pago en Preliquidación.
_Avoid_: usarla como criterio de precio; sumar cantidades sin mirarla, que mezcla bins con tancadas y con horas

**Precio del combustible**:
Precio por litro que se le descuenta a un Tercero. No depende de la estación ni del tipo de carga.

**Precio de la hora de reparación**:
Precio de la hora de mano de obra del taller, por Tercero.

**Precio del seguro**:
Importe de la cuota de una póliza, por Tercero, clase de póliza y sujeto cubierto. **Lo carga a mano quien tiene a cargo los seguros**, dentro de la app: no llega por archivo ni se deduce de ningún sistema. Se elige del Padrón de asegurables en vez de escribirse, porque un nombre tipeado tiene que coincidir exacto con el del sistema de campo o el seguro no se le imputa a nadie.

**Sujeto del seguro**:
Qué o a quién cubre una póliza: una máquina o un colectivo si es del automotor, una persona si es del chofer. Las tres clases —automotor, relación de dependencia y accidentes personales— se reparten entre esas dos naturalezas, y por eso el sujeto no es siempre un bien.
_Avoid_: llamarlo "maquinaria" — deja afuera al chofer, que es la mitad de las pólizas

**Padrón de asegurables**:
La lista de todo lo que la empresa le asegura a los Terceros: sus Colectivos, su Maquinaria y sus choferes. Sale del sistema de campo, que es el maestro; los choferes no tienen padrón propio y se deducen de quién manejó cada colectivo en el último año.

**Regla más específica**:
Cuando dos Tarifas alcanzan al mismo hecho, gana **la que tiene más dimensiones cargadas**: una regla con más condiciones es una excepción deliberada sobre una más general. Si empatan en cantidad de dimensiones, el hecho queda **ambiguo** y lo resuelve el liquidador; el sistema no elige en silencio.

**Tarifa heredada**:
Tarifa que vino copiada de otra quincena y todavía no fue confirmada. Se usa igual, pero queda resaltada hasta confirmarse, para no arrastrar un precio viejo sin darse cuenta. (Mismo criterio que el Precio heredado de Preliquidación, ADR-0004.)

**Sin tarifa**:
Un hecho al que ninguna Tarifa alcanza. **No entra al Recibo y no paga cero en silencio**: queda listado aparte hasta que el liquidador le cargue el precio.

---

## Cuándo se cobra

**Quincena de imputación**:
La quincena a la que un hecho pertenece por su fecha.

**Quincena efectiva**:
La quincena en la que un hecho **realmente se cobra o se descuenta**, cuando no es la de su fecha. La carga el liquidador a mano, con **motivo**, y existe por dos razones que conviene no confundir: porque el dato llegó tarde (la gente sigue cargando después de cerrada la quincena, y el recibo sale a los tres días), o porque la empresa **decidió** no descontarle algo a un Tercero esa quincena para ayudarlo. La segunda no se deduce de ninguna fecha.

**Quincena de liquidación**:
La que efectivamente se usa para liquidar: la Quincena efectiva si está cargada, si no la de imputación. Es la que filtran todas las cuentas del Recibo.

**Emisión del recibo**:
El momento en que el Recibo se manda al Tercero. Cierra esa quincena para ese Tercero y **congela** el documento: lo que se corrija o llegue después no cambia lo ya enviado, aparece en el Recibo siguiente. Se puede reabrir, con motivo.

**Llegada tardía**:
Un hecho cuya fecha de carga es posterior a la emisión del Recibo de su quincena. El sistema la detecta y **propone** diferirla; la decisión es del liquidador.
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

## Los sistemas de origen

**Sistema de campo**:
El sistema donde los Supervisores cargan los Viajes, las Cargas de combustible y las Horas de servicio, y donde vive el maestro de colectivos y de maquinaria. **Es el maestro**: si un dato está mal, se corrige ahí y no en el módulo. De solo lectura para el Sistema.

**Sistema de compras**:
El sistema donde se registran las salidas de Repuestos y las reparaciones hacia las máquinas. De solo lectura. Es la misma base que el Sistema usa como maestro de personal.

**App del taller**:
La aplicación donde los mecánicos cargan las Horas de reparación sobre cada máquina, con su estado de aprobación. El módulo la lee sola, sin que nadie suba nada.

**Estación de servicio**:
El comercio donde se cargan los Colectivos. Cada una factura aparte y en su propio formato; lo que factura se sube a la app para contrastarlo contra lo cargado en el Sistema de campo. La que no manda archivo digital se carga a mano.

---

## Los controles

**Verificación**:
Control que corre sobre los datos de una quincena y avisa de algo que hay que mirar **antes** de liquidar. No corrige nada ni frena la liquidación: señala, dice dónde se corrige y deja la decisión en manos de una persona. Se organizan por fuente de datos, porque el responsable de corregir es distinto en cada una.
_Avoid_: "alerta" a secas (era el nombre viejo, de cuando el único control era el de cruce)

**Duplicado**:
Dos cargas del mismo hecho en la misma fuente — el mismo viaje cargado dos veces, la misma carga de combustible, el mismo repuesto. Es la Verificación más común y la que más plata mueve.

**Alerta de cruce**:
La Verificación de que un dato de un sistema no encuentra su par en otro: una máquina que el sistema de compras tiene y la app del taller no, un vale facturado por una estación que no está cargado. **Nada se resuelve por parecido**: un cruce que falla genera un aviso accionable, no una adivinanza.
_Avoid_: resolver un cruce fallido por parecido de nombre

**Conciliación de combustible**:
La Verificación que compara lo que factura una Estación de servicio contra lo cargado en el Sistema de campo, cruzando por número de Vale. Devuelve tres listas: lo facturado y no cargado (la plata que si no se pierde), lo cargado y no facturado, y lo que está en los dos con litros distintos.
