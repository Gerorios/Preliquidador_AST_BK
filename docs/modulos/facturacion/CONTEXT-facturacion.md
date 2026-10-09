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
crédito. Tiene Cliente, Empresa emisora, número del Sistema contable, fecha, sus Líneas y sus
Adjuntos. Se identifica por Empresa emisora y número.
_Avoid_: "factura" para hablar de los dos tipos a la vez.

**Factura**:
Comprobante que le cobra al Cliente las tareas hechas. Si se olvidó facturar algo, se emite
otra Factura, no se corrige la anterior.

**Nota de crédito**:
Comprobante que corrige una Factura hacia abajo. Apunta a la Factura que corrige, y sus
Líneas restan en el Cruce.

**Línea de comprobante**:
Un renglón del Comprobante traducido al lenguaje del campo: fecha, tarea del sistema de campo,
cantidad, precio unitario e importe neto (sin IVA). La finca es opcional. La fecha puede ser
cualquier día del mes: no está atada a una quincena.
_Avoid_: el texto con que el cliente nombra la tarea; eso es lo que traduce la Equivalencia.

**Adjunto**:
El archivo que respalda un Comprobante, normalmente el PDF generado en el Sistema contable. Un
Comprobante puede tener varios (una reimpresión, una versión corregida que no cambia los
números).

**Comprobante histórico**:
Un Comprobante que vino de la planilla anterior al módulo. Puede no tener Empresa emisora ni
Adjunto, y no genera la Alerta "sin comprobante".

---

## Cómo se carga

**Orden de facturación**:
El detalle de lo que el Cliente reconoce como trabajado en el período, que algunos clientes
publican en su portal para que se les facture. Cada cliente la manda en su propio formato.
_Avoid_: "OC" a secas; confundirla con el Comprobante (la orden la emite el cliente, el
comprobante el grupo).

**Importador de órdenes**:
La carga que lee el archivo de una Orden de facturación en el formato de un cliente y arma las
Líneas del Comprobante ya traducidas. Hay uno por formato.

**Equivalencia**:
La traducción guardada, por Cliente, de cómo el cliente nombra una tarea en su Orden de
facturación a la tarea del sistema de campo. Un renglón sin Equivalencia frena la importación
hasta que alguien la define, y queda guardada para la próxima.
_Avoid_: traducir por parecido de nombre.

---

## El control

**Grupo de facturación**:
El atributo de cada tarea del sistema de campo que dice con qué medida se le factura al
cliente: horas de peón, horas de tractor, plantas, hectáreas o tancadas, o que no se factura.
Decide cuál de las cantidades que se cargan en el campo se compara contra lo facturado.
_Avoid_: confundirlo con el Grupo de pago de Preliquidación (cómo se le paga al trabajador) o
con el Grupo de tareas (el agrupador funcional).

**Cantidad del campo**:
Lo trabajado para un Cliente según el sistema de campo, medido en la unidad que fija el Grupo
de facturación de cada tarea. En el campo una misma tarea se carga con varias medidas a la vez
(horas de peón, horas de máquina, plantas, tancadas); sólo una cuenta para facturar.
_Avoid_: "cantidad LA", "cantidad final" (los nombres del informe anterior).

**Cruce**:
La comparación, para un Cliente y un rango de fechas, entre la Cantidad del campo y lo
facturado, tarea por tarea y agrupado por grupo de tareas. El rango es libre y arranca en el
mes completo, porque una diferencia de una quincena puede compensarse en la siguiente.
_Avoid_: mirarlo por quincena por defecto.

**Diferencia**:
Lo facturado menos la Cantidad del campo, para una tarea en el rango del Cruce. Negativa es
facturado de menos. En plata se valoriza con el precio unitario de lo facturado.

**Alerta de facturación**:
El aviso de que un Cliente necesita que alguien lo mire, sobre un mes ya cerrado y desde el
Mes de corte. Hay tres:
- **Sin facturar**: el Cliente tuvo trabajo facturable en el mes y no tiene ninguna Línea de
  comprobante en él.
- **Facturado con diferencia**: en algún grupo de tareas, la Diferencia del mes supera el
  Umbral de diferencia.
- **Sin comprobante**: un Comprobante que no tiene ningún Adjunto.

No corrige nada: señala y deja la decisión a una persona.
_Avoid_: "verificación" (es el término de Terceros); evaluarla sobre el mes en curso.

**Alerta revisada**:
Una Alerta de facturación que una persona ya miró y explicó (por ejemplo, "se compensó en el
mes siguiente"). Guarda quién la marcó, cuándo y el comentario, y deja de contar como
pendiente.

**Umbral de diferencia**:
El porcentaje de Diferencia a partir del cual un grupo de tareas genera la Alerta "facturado
con diferencia". Es configurable.

**Mes de corte**:
El primer mes que se evalúa para las Alertas de facturación. Los meses anteriores se ven en el
Cruce pero no generan pendientes.
