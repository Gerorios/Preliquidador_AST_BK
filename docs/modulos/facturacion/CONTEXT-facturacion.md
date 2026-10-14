# Facturación — La Asturiana SRL

Lenguaje ubicuo del módulo **Facturación**, el registro y control de lo que el grupo le factura
a sus clientes por las tareas agrícolas (ver "Sistema y módulos" en `CONTEXT.md`; el índice de
glosarios es `CONTEXT-MAP.md`). Este archivo es un glosario: define qué ES cada término, no
cómo se implementa.

Escrito a partir de la entrevista sobre la planilla con la que hoy se lleva la facturación a
clientes y el informe de Power BI que la cruza contra lo cargado en el sistema de campo.

---

## El módulo

**Facturación**:
El módulo que registra cada Comprobante emitido a un cliente, lo traduce a tareas del sistema
de campo y lo cruza contra lo que efectivamente se trabajó, para saber qué falta facturar y
dónde se facturó de más o de menos. Cubre las tareas agrícolas; la cosecha queda fuera.
_Avoid_: confundirlo con el resultado operativo (facturación menos mano de obra y
combustible), que consolida varios módulos y no es parte de este.

**Pantallas de Facturación**:
Las Pantallas del módulo y qué es ver y qué es editar en cada una (Pantalla y Permiso están en `CONTEXT.md`):
- **Resumen**: ver, por mes y Cliente, lo trabajado, lo facturado y el Estado del mes, y abrir
  el Cruce de cada uno; editar es dejar una Revisión de diferencia.
- **Comprobantes**: ver los Comprobantes y sus Adjuntos; editar es cargarlos desde la Precarga,
  editarlos, adjuntar e importar Órdenes de facturación.
- **Equivalencias**: ver las Equivalencias de cada Cliente; editar es crearlas y cambiarlas.
- **Panel**: solo ver. Se ve desde Gerencial.

**Cliente**:
La empresa para la que el grupo trabaja en sus fincas, tal como figura en el maestro de
clientes del sistema de campo. Es el mismo Cliente que usan las tareas y la preliquidación.
_Avoid_: la razón social con que el cliente aparece en el sistema contable o en su portal;
"cliente agrupado" (el maestro de campo ya usa el nombre comercial).

**Empresa emisora**:
La Empresa del grupo que emite el Comprobante. Un mismo Cliente puede recibir comprobantes de
distintas empresas del grupo.

**Sistema contable**:
El sistema donde las contadoras emiten de verdad cada factura y nota de crédito. Facturación
no lo lee: registra lo emitido ahí y guarda su número para poder encontrarlo.

---

## Lo que se registra

**Comprobante**:
Lo que el grupo le emite a un Cliente en el Sistema contable: una Factura o una Nota de
crédito. Tiene Cliente, Empresa emisora, número del Sistema contable, Fecha de carga, Período
facturado, sus Líneas y sus Adjuntos. Se identifica por Empresa emisora y número.
_Avoid_: "factura" para hablar de los dos tipos a la vez.

**Factura**:
Comprobante que le cobra al Cliente las tareas hechas. Si se olvidó facturar algo, se emite
otra Factura, no se corrige la anterior.

**Nota de crédito**:
Comprobante que corrige una Factura hacia abajo. Apunta a la Factura que corrige, y sus
Líneas restan en el Cruce.

**Fecha de carga**:
El día en que se registró el Comprobante en Facturación. La pone el sistema y no se cambia.
_Avoid_: confundirla con el Período facturado, que es lo que decide en qué mes cuenta.

**Período facturado**:
Los días de trabajo que cobra o corrige el Comprobante: un desde y un hasta, siempre dentro de
un mismo mes, que es el mes en que cuenta lo facturado. Se propone solo (el mes desde el que se
abrió la Precarga, o el mes anterior a la Fecha de carga) y quien carga lo puede cambiar a una
quincena, a otro mes o a los días que quiera de un mismo mes.
_Avoid_: un período que cruce de un mes a otro.

**Línea de comprobante**:
Un renglón del Comprobante traducido al lenguaje del campo: tarea del sistema de campo, Unidad
de facturación, cantidad, precio unitario e importe neto (sin IVA). La finca es opcional. Cuenta
en el Período facturado de su Comprobante.
_Avoid_: el texto con que el cliente nombra la tarea; eso es lo que traduce la Equivalencia.

**Adjunto**:
El archivo que respalda un Comprobante, normalmente el PDF generado en el Sistema contable. Un
Comprobante puede tener varios (una reimpresión, una versión corregida que no cambia los
números).

**Comprobante histórico**:
Un Comprobante que vino de la planilla anterior al módulo. Puede no tener Empresa emisora ni
Adjunto, y no genera la Alerta "Falta comprobante". Puede no tener número, cuando la planilla no
lo anotó: junta las filas de un Cliente con la misma fecha a facturar, y pasa al Comprobante
con número cuando la planilla lo tenga. Uno sin número posterior al corte que fijó el usuario
se toma como todavía no facturado: sus Líneas no cuentan como facturado en el Cruce.

---

## Cómo se carga

**Precarga**:
El Comprobante que el módulo arma solo para que se cargue: una Línea por tarea trabajada en el
Período facturado, con la Cantidad del campo, la Unidad sugerida y el Precio sugerido, y la
Empresa emisora de la última Factura al Cliente. Quien carga completa el número y el Adjunto, y
puede cambiar todo. Si cambia el Período facturado, las Líneas se recalculan sólo si lo
confirma, porque se pierde lo que cambió a mano.

**Precio sugerido**:
El precio unitario de la última Factura al mismo Cliente por la misma tarea y en la misma
Unidad de facturación. Las Notas de crédito no cuentan. Si no hay una Factura así, la Línea
queda sin precio y marcada.
_Avoid_: tomar el precio de otro Cliente.

**Orden de facturación**:
El detalle de lo que el Cliente reconoce como trabajado en el período, que algunos clientes
publican en su portal para que se les facture. Cada cliente la manda en su propio formato.
_Avoid_: "OC" a secas; confundirla con el Comprobante (la orden la emite el cliente, el
comprobante el grupo).

**Importador de órdenes**:
La carga que lee el archivo de una Orden de facturación en el formato de un cliente y arma las
Líneas de la Precarga ya traducidas, en lugar de las de lo trabajado. Hay uno por formato.

**Equivalencia**:
La traducción guardada, por Cliente, de cómo el cliente nombra una tarea en su Orden de
facturación a la tarea del sistema de campo. Un renglón sin Equivalencia frena la importación
hasta que alguien la define, y queda guardada para la próxima.
_Avoid_: traducir por parecido de nombre.

---

## El control

**Unidad de facturación**:
La medida con que se le factura al Cliente una Línea de comprobante: horas de peón, horas de
tractor, plantas, hectáreas o tancadas, y las de cosecha (bins, bins C, bins M y viajes). La
elige quien carga la Línea, y decide cuál de las cantidades que se cargan en el campo se compara
contra lo facturado. Una misma tarea se puede facturar en una unidad un mes y en otra el
siguiente. Lo facturado en una unidad de cosecha queda fuera del Cruce y de las Alertas de
facturación, porque la cosecha no es parte del módulo.
_Avoid_: "grupo de facturación" (el nombre del diseño anterior, cuando la unidad era fija por
tarea); confundirla con el Grupo de pago de Preliquidación (cómo se le paga al trabajador) o con
el Grupo de tareas (el agrupador funcional).

**Unidad sugerida**:
La Unidad de facturación que cada tarea del sistema de campo trae por defecto: precarga la
Línea de comprobante al elegir la tarea, y es la que usa el Cruce para una tarea que todavía no
tiene Líneas en el mes. No obliga: la Línea puede facturar en otra. Una tarea facturable sin
Unidad sugerida genera un aviso. Se define en el sistema de campo, en cada tarea; Facturación la
lee y no la cambia.

**No facturable**:
La marca de una tarea del sistema de campo que no se le factura a ningún Cliente (por ejemplo,
una tarea interna). No entra al Cruce ni a las Alertas de facturación. Se define en el sistema
de campo, en cada tarea; Facturación la lee y no la cambia.

**Cantidad del campo**:
Lo trabajado para un Cliente según el sistema de campo, medido en la Unidad de facturación de
lo facturado, o en la Unidad sugerida de la tarea si todavía no hay nada facturado. En el campo
una misma tarea se carga con varias medidas a la vez (horas de peón, horas de máquina, plantas,
tancadas); sólo una cuenta para facturar.
_Avoid_: "cantidad LA", "cantidad final" (los nombres del informe anterior).

**Cruce**:
La comparación, para un Cliente y un mes, entre la Cantidad del campo y lo facturado, tarea por
tarea y agrupado por grupo de tareas. Cada tarea se abre en los partes del sistema de campo que
la forman. Se mira por mes completo, porque una diferencia de una quincena puede compensarse en
la siguiente.
_Avoid_: mirarlo por quincena.

**Diferencia**:
Lo facturado menos la Cantidad del campo, para una tarea en el mes del Cruce. Negativa es
facturado de menos. En porcentaje, se mide sobre la Cantidad del campo. En plata se valoriza con
el precio unitario de lo facturado.

**Estado del mes**:
Cómo está un Cliente en un mes, según el Cruce y sus Comprobantes:
- **Pendiente de facturar**: tuvo trabajo facturable y no tiene nada facturado.
- **Con diferencia**: en alguna tarea facturable, la Diferencia supera el Umbral de diferencia,
  para arriba o para abajo. Una tarea trabajada y no facturada también cuenta.
- **Falta comprobante**: alguno de sus Comprobantes no tiene ningún Adjunto (salvo los
  Comprobantes históricos).
- **Facturada**: ninguno de los anteriores. Si tuvo una Revisión de diferencia, lleva la nota
  "Diferencia revisada".
- **Mes en curso**: el mes todavía no terminó. Sólo se controla Falta comprobante; lo demás,
  desde el primer día del mes siguiente.
- **Antes del corte**: el mes es anterior al Mes de corte. No se controla nada.

Un mes puede tener varios a la vez (Con diferencia y Falta comprobante, o Mes en curso y Falta
comprobante). Pendiente de facturar y Facturada van siempre solos.

**Alerta de facturación**:
Los tres Estados del mes que piden que alguien haga algo: Pendiente de facturar, Con diferencia
y Falta comprobante. Cada una lleva a donde se resuelve, y se cuentan por separado. No corrige
nada: señala y deja la decisión a una persona.
_Avoid_: "verificación" (es el término de Terceros); "sin facturar", "facturado con diferencia"
y "sin comprobante" (los nombres anteriores).

**Revisión de diferencia**:
Lo que deja una persona cuando mira un mes Con diferencia y lo explica (por ejemplo, "se
compensó en el mes siguiente"). Guarda quién, cuándo, el comentario, que es obligatorio, y las
tareas que superaban el Umbral de diferencia en ese momento. Mientras superen esas mismas
tareas, el mes queda Facturada con la nota "Diferencia revisada"; si después supera otra,
vuelve a Con diferencia; si ya no supera ninguna, la Revisión queda en el registro.
_Avoid_: "Alerta revisada" (el nombre anterior).

**Umbral de diferencia**:
El porcentaje de Diferencia a partir del cual una tarea deja el mes Con diferencia. Es uno solo
para todos los Clientes y tareas, y lo cambia sólo el Admin.

**Mes de corte**:
El primer mes que se controla. Los anteriores se ven en el Resumen y en el Cruce como Antes del
corte y no generan Alertas de facturación. Lo mueve sólo el Admin.
