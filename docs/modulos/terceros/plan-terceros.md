# Plan de implementación — módulo Liquidación Terceros

**Estado**: diseño acordado, sin código todavía. El molde está renombrado y registrado, inactivo.
**Fecha de la decisión**: 2026-09-09, sesión de grilling sobre el Excel que hoy resuelve el circuito.
**Quién lo construye**: Pitu. Revisión y merge, Gero (regla 4 de `GUIA-MODULOS.md`).

El glosario del dominio está en [`CONTEXT-terceros.md`](CONTEXT-terceros.md). Las fuentes originales —el Excel maestro, las consultas de Power Query, los archivos de las estaciones y el de seguros— están en `fuentes/`, **fuera de git** (ver `fuentes/LEEME.md`).

---

## 1. Qué reemplaza

Un Excel con 19 hojas que hoy arma la liquidación de terceros: cuatro hojas de aterrizaje donde caen las consultas, cuatro hojas de trabajo con las decisiones humanas, una grilla de 53 terceros × 24 quincenas, y las salidas (recibo, recibo de taller, tablero y controles).

Lo que el módulo tiene que resolver y el Excel no:

- **Un solo lugar** conectado a las fuentes, sin copiar y pegar entre hojas de aterrizaje y hojas de trabajo.
- **Precios como tabla**, no tipeados fila por fila. Hoy el precio de cada viaje se escribe a mano: unos 6.600 tipeos por año, con inconsistencias medibles.
- **Recibos congelados**: hoy un recibo ya enviado cambia solo si alguien corrige un dato viejo en el sistema de origen.
- **Alertas de cruce** entre los tres sistemas de origen, que hoy se detectan a ojo o no se detectan.
- **La cuenta corriente en el recibo**: lo del período más lo que se debe, que hoy queda afuera.

---

## 2. Decisiones tomadas

### 2.1 Identidad y cruce entre sistemas

**El sistema de campo es el maestro** de colectivos, maquinaria y sus dueños. El módulo no mantiene un padrón propio: si un dato está mal, se corrige en el sistema de origen, con su responsable. Esa fue una decisión explícita — no sumar un sistema más para mantener.

**El puente entre sistemas es un identificador, no un nombre.** Los tres sistemas nombran la misma máquina de tres maneras distintas y los ids son autoincrementales independientes, así que unir por texto obliga a tres personas a escribir lo mismo para siempre. En su lugar:

| Sistema | Qué se le pide |
|---|---|
| Sistema de campo | Un token más en `descripcion` de la maquinaria con **el dueño**, para que deje de estar embebido en el nombre. Es lo único que se puede pedir: el sistema no es nuestro y solo admite campos separados por `;` |
| Sistema de compras | Un campo con **el id de la maquinaria del sistema de campo**. Es nuestro, se puede modificar |
| App del taller | Una columna con **el id de la maquinaria del sistema de campo** en su maestro de máquinas |
| Archivo de seguros | Una columna con **el dueño escrito exactamente como lo escribe el sistema de campo**. Lo arma alguien de la empresa, se puede pedir |

El nombre deja de ser pegamento y pasa a ser **control**: el módulo compara los nombres de los tres sistemas y avisa cuando divergen, sin que la liquidación se caiga.

**Nada se resuelve por parecido.** Un cruce que falla genera una alerta accionable ("esta máquina no tiene id del sistema de campo", "este dueño del archivo de seguros no existe"), no una adivinanza.

### 2.2 Tarifas

- **Grano de quincena**, no vigencia por fecha. La razón es operativa: el flujo es cargar los precios de la quincena y, al liquidar la siguiente, **copiarlos desde la quincena que se elija**, dejando vacíos los que no tengan nada. Es el mismo mecanismo del ADR-0004 de Preliquidación, incluida la marca de heredado.
- **Seis dimensiones opcionales**: tercero, patente, chofer, cliente, finca, capataz. La combinación habitual es tercero + capataz.
- **El tipo de viaje es resultado de la regla, no clave**: la misma regla fija tipo y precio.
- **Gana la regla más específica** (más dimensiones cargadas). Empate = viaje ambiguo, lo resuelve el liquidador. Al crear una regla que pisa a otras, se muestra a cuántos viajes les cambia el precio y se pide confirmar, como el ADR-0011.
- **Sin tarifa, el viaje no entra al recibo**: queda listado aparte, nunca paga cero en silencio.
- **Combustible**: precio por litro por quincena y por tercero, sin más dimensiones.
- **Horas de taller**: valor de la hora con vigencia desde una fecha; se aplica el vigente a la fecha del trabajo.

### 2.3 Períodos y diferimiento

- La **quincena efectiva es un campo manual con motivo** en las cuatro tablas de gasto. No se puede derivar: además de la llegada tardía, existe la excepción comercial (no descontarle algo a un tercero esta quincena para ayudarlo).
- **Emitir el recibo congela** ese recibo y cierra la quincena para ese tercero. Se puede reabrir con motivo.
- El sistema **propone** diferir lo que llegó después de la emisión; la decisión es del liquidador.
- **Seguros**: se imputan enteros a la 2da quincena del mes. Se unifica también para los colectivos propios de la empresa, que hoy se parten al medio.

### 2.4 Horas de taller

- Se cobran **solo las aprobadas**. Las pendientes esperan; cuando se aprueben entran en la quincena que esté abierta. Las rechazadas no se cobran nunca. Con eso no hace falta ningún mecanismo de crédito ni reversión.
- El tablero de alertas muestra, para la quincena que se está por liquidar, **cuántas aprobadas, pendientes y rechazadas hay**, para poder reclamar antes de liquidar y no después.
- El módulo lee la app del taller **automáticamente** y guarda su propia copia, para que el recibo no dependa de que la fuente conteste y quede congelado al emitirse.

### 2.5 La cuenta y el recibo

- **No hay una sección aparte para cargar pagos.** Se trabaja sobre la grilla de la quincena, con los datos del sistema de campo ya cruzados contra el maestro de precios, marcando los estados ahí mismo. El importe pagado es un campo de la fila; el sistema guarda un **registro de auditoría** de cada cambio, como ya hace Preliquidación con los ajustes manuales.
- El recibo tiene tres bloques: **esta quincena** (el neto), **saldo anterior** (solo las quincenas que aplican al saldo) y **en revisión** (las que están en discusión, listadas sin sumar).
- La consulta del detalle de la cuenta es **una pantalla del módulo, para el liquidador**. Los terceros no acceden al sistema.
- **Salida en PDF**, con un botón para generar toda la grilla de la quincena de una y otro para un tercero puntual. Requiere una dependencia nueva (`reportlab`, pura Python) — a aprobar según la regla de stack de `GUIA-MODULOS.md`.
- **WhatsApp se manda a mano**, como hoy. Automatizarlo es la API de WhatsApp Business: alta en Meta, plantillas aprobadas, número dedicado y costo por conversación. El sistema saca el trabajo de armar los números, no el de adjuntar un archivo.

### 2.6 Conciliación de combustible

- Se cruza por **número de vale**, que en el sistema de campo está presente en el 99% de las cargas y es casi siempre numérico.
- Cada estación exporta un formato distinto y el vale aparece con otro nombre de columna en cada una. **Se sube el archivo tal cual y se mapean las columnas una vez por estación**; el mapeo queda guardado. Si una estación cambia el formato, el módulo no encuentra la columna y lo dice — falla a la vista, no en silencio.
- Los archivos traen **toda la empresa**, no solo colectivos: hay que filtrar por patente, normalizando espacios.
- La **flota liviana queda afuera** del módulo: no hay tercero a quien descontarle.
- Devuelve tres listas: facturado y no cargado, cargado y no facturado, y diferencias de litros. **No cambia la liquidación**; sirve para que el sistema de campo esté completo antes de emitir.

### 2.7 Carga del histórico

- **2026 entra congelado tal como se liquidó**, hasta la **1ra quincena de agosto** inclusive, que es hasta donde los números coinciden con los del liquidador. Precios tipeados, seguros como se cobraron, repuestos con la fecha vieja.
- **El módulo empieza a calcular de verdad desde una quincena de corte** a definir, cuando el desarrollo esté listo.
- El script de importación **se vuelve a correr** para extender el histórico congelado hasta la quincena del cambio, porque mientras se desarrolla se sigue liquidando en el Excel.
- Las reglas nuevas **no se aplican retroactivamente**. Un saldo que un tercero ya saldó no se mueve solo. Si interesa cuantificar lo que las reglas viejas dejaron sin cobrar, se hace como **informe aparte**, sin tocar saldos.
- La conciliación con el liquidador se hace **después** de importar, comparando en pantalla lo que da el módulo contra lo que dice el Excel.

---

## 3. Correcciones que el módulo introduce

Encontradas midiendo sobre los datos reales durante el grilling. Todas cambian números respecto del Excel actual, y por eso el histórico entra congelado y estas reglas rigen solo desde el corte.

| Qué | Estado hoy |
|---|---|
| **Fecha de los repuestos** | La consulta usa la fecha del encabezado del movimiento, pero la correcta es la de la descarga a la maquinaria. En 2026, la mitad de las líneas de terceros cae en otra quincena según cuál se use, y algunas en otro año |
| **Seguros** | Se liquidan por un circuito separado del Excel. El módulo los absorbe para que salga todo junto |
| **Máquinas sin cubrir** | El sistema de compras tiene máquinas de terceros que la app del taller no tiene, entre ellas la de un transportista cuyos repuestos hoy no llegan a su recibo |
| **Precios inconsistentes** | Con el precio tipeado por fila, hay grupos de viajes idénticos (mismo bus, día, destino y tipo) con dos precios distintos alternados. La tabla de tarifas los elimina |
| **Cargas sin origen registrado** | Al menos una estación de servicio no figura en el catálogo del sistema de campo ni tiene una sola carga registrada. A confirmar si esas cargas se registran de otra forma |

---

## 4. Modelo de datos (borrador)

Todas las tablas con prefijo `terceros_`, en `migrations/terceros/001_crear_tablas.sql`. El padrón de terceros, colectivos y maquinaria **no se replica**: vive en los sistemas de origen.

| Tabla | Qué guarda |
|---|---|
| `terceros_viaje` | El viaje traído del sistema de campo, congelado, con su precio y tipo aplicados, el origen (campo o manual), estado, quincena efectiva y motivo |
| `terceros_carga_combustible` | Ídem para las cargas, con litros, vale, precio aplicado |
| `terceros_repuesto` | Ídem para las salidas del sistema de compras, con el tercero resuelto y la marca de "no cobrar" con motivo |
| `terceros_hora_taller` | Copia de las horas aprobadas de la app del taller, con valor de hora aplicado |
| `terceros_seguro` | Las filas del archivo mensual, con tipo, sujeto, tercero e importe |
| `terceros_tarifa_viaje` | La regla por quincena: seis dimensiones opcionales → tipo y precio, con marca de heredada |
| `terceros_precio_combustible` | Precio por litro por quincena y tercero |
| `terceros_valor_hora_taller` | Valor de la hora con vigencia desde una fecha |
| `terceros_liquidacion` | La cabecera por tercero y quincena: totales, neto, pagado, saldo, estado, aplica al saldo, emisión |
| `terceros_ajuste` | Ajustes manuales con signo y motivo |
| `terceros_auditoria` | Registro de cambios manuales, como el `ajuste_manual` de Preliquidación |
| `terceros_mapeo_estacion` | El mapeo de columnas guardado por estación para la conciliación |

---

## 5. Etapas

Sigue el orden sugerido en la sección 9 de `GUIA-MODULOS.md`: primero lo que se puede validar contra el Excel, después lo que agrega valor nuevo. **Se construye en paralelo al ajuste de los sistemas de origen**, no después: las pantallas de alertas son la herramienta con la que ese ajuste se hace.

| # | Qué | Termina cuando |
|---|---|---|
| 1 | Las cuatro consultas dentro del módulo, en SQL parametrizado, con tests que fijan lo que devuelven | Los números coinciden con el Excel para una quincena conocida |
| 2 | Ingesta y pantallas de solo lectura: viajes, cargas, repuestos y horas de la quincena, con filtros | El liquidador ve los datos en el sistema y confirma que están bien |
| 3 | **Alertas de cruce** entre los tres sistemas | Empieza la limpieza de los sistemas de origen, guiada por la pantalla |
| 4 | Tablas propias, migración 001, tarifas y cálculo del neto, con tests de cada regla | Una quincena calcula igual que el Excel |
| 5 | Importación del histórico congelado y de las tarifas ya tipeadas | 2026 hasta la 1ra de agosto está adentro y concilia |
| 6 | Cuenta corriente, estados, emisión y congelado del recibo | Se puede cerrar una quincena completa |
| 7 | Recibo en PDF, individual y en lote | El liquidador manda una quincena real desde el sistema |
| 8 | Conciliación de combustible contra las estaciones | Se detecta un vale no cargado antes de emitir |
| 9 | Panel gerencial bajo `/api/terceros/gerencial` | Al final, con todo lo anterior en uso |

Cada etapa termina con un PR mergeado. A partir de la 2, con el usuario real mirándola.

---

## 6. Pendientes de confirmar

**Con el sistema de campo y sus responsables**
- El token del dueño en la descripción de la maquinaria. Hay máquinas de terceros marcadas como propias y al menos un tercero del taller que no existe en el catálogo.
- Un colectivo aparece con dos dueños distintos: definir si es una venta del vehículo o un error de carga, y qué pasa con el histórico cuando un colectivo cambia de manos.
- Casos donde se cargó el nombre del capataz en lugar del dueño. Ninguna validación automática los detecta.

**Con el liquidador**
- Qué son los números de vale de cuatro dígitos que aparecen en el archivo de una de las estaciones, distintos de los de cinco dígitos que sí cruzan.
- Si las cargas de la estación que no manda archivo digital se registran de alguna otra forma en el sistema de campo.
- La quincena de corte a partir de la cual el módulo liquida en serio.

**Con quien arma el archivo de seguros**
- La columna con el dueño escrito como lo escribe el sistema de campo, y el identificador de la maquinaria para las filas que no son de un colectivo.

**Con Gero**
- Aprobar `reportlab` como dependencia nueva para el PDF.
- La app del taller está publicada en la web sin restricción y expone datos personales de los mecánicos. No lo introduce el módulo, pero conviene que lo sepa quien la administra.

**Sueltos, a resolver leyendo el Excel**
- Ajustes manuales, detección de duplicados, carga manual de viajes que no vienen del sistema de campo, y el estado de cuenta anual.
