# Plan de implementación — módulo Liquidación Terceros

**Estado**: etapas 1 a 6 hechas (del 2026-09-10 al 09-17). El plan se rehízo el **2026-09-16**, cuando apareció el segundo circuito —el servicio de maquinaria— y con él una forma distinta del módulo.
**Fecha de la decisión original**: 2026-09-09, sesión de grilling sobre el Excel que hoy resuelve el circuito.
**Quién lo construye**: Pitu. Revisión y merge, Gero (regla 4 de `GUIA-MODULOS.md`).

El glosario del dominio está en [`CONTEXT-terceros.md`](CONTEXT-terceros.md). Las fuentes originales —el Excel maestro, las consultas de Power Query, los archivos de las estaciones y el de seguros— están en `fuentes/`, **fuera de git** (ver `fuentes/LEEME.md`).

---

## 1. Qué reemplaza

Un Excel con 19 hojas que hoy arma la liquidación de terceros. Lo que el módulo tiene que resolver y el Excel no:

- **Un solo lugar** conectado a las fuentes, sin copiar y pegar entre hojas.
- **Precios como tabla**, no tipeados fila por fila. Hoy el precio de cada viaje se escribe a mano: unos 6.600 tipeos por año, con inconsistencias medibles.
- **Recibos congelados**: hoy un recibo ya enviado cambia solo si alguien corrige un dato viejo.
- **Verificaciones** —duplicados y cruces entre sistemas— que hoy se detectan a ojo o no se detectan.
- **La cuenta corriente en el recibo**: lo del período más lo que se debe, que hoy queda afuera.

---

## 2. Los dos servicios

Un Tercero le presta a la empresa uno de dos servicios, o los dos, y **cobra por un solo recibo**:

| Servicio | Se le paga | Se le descuenta |
|---|---|---|
| **Flete** | Viajes | Combustible, Repuestos, Seguros, Horas de reparación |
| **Maquinaria** | Horas de servicio | Repuestos, Seguros, Horas de reparación |

El combustible solo alcanza al flete. Lo demás es común a los dos.

**La distinción que más importa y la que más fácil se confunde**: la *Hora de reparación* es el mecánico de la empresa arreglando la máquina del Tercero (el Tercero nos debe) y la *Hora de servicio* es la máquina del Tercero trabajando en nuestras fincas (le pagamos). Las dos van en el mismo recibo, con signo opuesto. Antes las dos se llamaban "horas de taller".

**Medido el 2026-09-16** con la consulta del usuario: 2.244 registros en 2026, repartidos en tres partes diarios (cosecha 911, maquinaria 772, pulverizadas 561), 9 dueños. Son **17.560 horas de máquina** o **21.737 de jornal** según cuál se pague. Los dueños son los mismos que ya aparecen por repuestos y taller.

---

## 3. Decisiones tomadas

### 3.1 Identidad y cruce entre sistemas

**El sistema de campo es el maestro** de colectivos, maquinaria y sus dueños. El módulo no mantiene un padrón propio: si un dato está mal, se corrige en el origen, con su responsable.

**El puente entre sistemas es un identificador, no un nombre.** Medido en la etapa 3: de 46 maquinarias de terceros del sistema de campo, **solo 3 cruzan** con los otros dos sistemas por patente. El resto no tiene patente. Ninguna heurística lo arregla; hace falta un campo.

| Sistema | Qué se le pide |
|---|---|
| Sistema de campo | Un token más en `descripcion` de la maquinaria con **el dueño**. Es lo único que admite: campos separados por `;` |
| Sistema de compras | Un campo con **el id de la maquinaria del sistema de campo**. Es nuestro |
| App del taller | Una columna con **el id de la maquinaria del sistema de campo** |

**Nada se resuelve por parecido.** Un cruce que falla genera una Verificación accionable, no una adivinanza. La única excepción es sugerir, dentro de una alerta que ya existe, cuál podría ser la ficha equivalente — no cruza ni decide nada.

### 3.2 El Tarifario

Cinco tablas, todas **por quincena**, con copia desde la quincena que se elija y marca de heredada (mismo mecanismo del ADR-0004 de Preliquidación).

| Tabla | Dimensiones | Resultado |
|---|---|---|
| Viajes | tercero, cliente, finca, capataz | tipo de viaje + precio |
| Horas de servicio | tercero, cliente, finca, tarea | **unidad base** + precio |
| Combustible | tercero | precio por litro |
| Horas de reparación | tercero | precio por hora |
| Seguros | maquinaria, tercero | importe de la cuota |

- **Gana la regla más específica** (más dimensiones cargadas). Empate = ambiguo, lo resuelve el liquidador.
- **Sin tarifa, el hecho no entra al recibo**: queda listado aparte, nunca paga cero en silencio.
- **La unidad base de las horas de servicio la elige el liquidador**: se paga la hora de máquina o la hora de jornal según lo pactado, no según el dato. El sistema de campo carga las dos y no son iguales: en 2026 son 17.560 horas de máquina contra 21.737 de jornal, **4.177 de diferencia**.
- **Los seguros no llegan por archivo**: los carga a mano, dentro de la app, quien tiene los seguros a cargo. Es un cambio respecto del plan del 09-09, que asumía un Excel mensual.

### 3.3 Períodos y diferimiento

- La **quincena efectiva es un campo manual con motivo** en todas las tablas de hechos. No se puede derivar: además de la llegada tardía existe la excepción comercial.
- **Emitir el recibo congela** ese recibo y cierra la quincena para ese Tercero. Se puede reabrir con motivo.
- El sistema **propone** diferir lo que llegó después de la emisión; la decisión es del liquidador.
- **Seguros**: se imputan enteros a la 2da quincena del mes.

### 3.4 Horas de reparación

- Se cobran **solo las aprobadas**. Las pendientes esperan; cuando se aprueben entran en la quincena que esté abierta. Las rechazadas no se cobran nunca.
- El tablero muestra cuántas aprobadas, pendientes y rechazadas hay, para reclamar antes de liquidar.
- El módulo lee la app del taller **automáticamente** y guarda su propia copia, para que el recibo quede congelado al emitirse.

### 3.5 La cuenta y el recibo

- **No hay una sección aparte para cargar pagos.** Se trabaja sobre la grilla de la quincena, marcando los estados ahí mismo, con registro de auditoría de cada cambio.
- El recibo tiene tres bloques: **esta quincena**, **saldo anterior** y **en revisión** (listado sin sumar).
- **Dónde va el seguro depende de para quién es el recibo.** En el del Tercero va **afuera** del total a facturar: el bloque cierra en Total a facturar, sigue el detalle de los seguros, y abajo el Total a pagar. En el de la empresa va **adentro** del cálculo, y hay un solo total. Porqué: el Total a facturar del Tercero es lo que él copia en su factura, y el seguro no es un servicio que él preste — es una cuota adelantada que se le recupera; si entrara arriba facturaría de menos. Adentro de la empresa esa distinción no hace falta, lo que se quiere ver es cuánto se paga.
- **Los dos layouts cierran en el mismo número**: el Total a facturar del recibo de la empresa tiene que ser igual al Total a pagar del recibo del Tercero. Es un solo cálculo impreso de dos formas, y esa igualdad es el test.
- **Salida en PDF**, individual y en lote. Requiere `reportlab` — a aprobar según la regla de stack.
- **WhatsApp se manda a mano**, como hoy.

### 3.6 Combustible y estaciones de servicio

- Se cruza por **número de vale**: 1.325 cargas en el año, solo 12 sin vale.
- Tres estaciones son el 94,6%. **Cada archivo viene con layout distinto**, así que el mapeo de columnas se configura una vez por estación y queda guardado.
- **La Angostura no manda archivo digital**: llega por foto y se carga a mano en la app.
- En la grilla de la quincena, cada carga muestra **si su vale aparece en lo facturado por la estación**.
- La **flota liviana queda afuera**.

### 3.7 Nada de histórico

**No se migra nada.** El módulo arranca liquidando, no importando. La prueba de que funciona es que **agosto de 2026 dé lo mismo que la liquidación hecha a mano**. Esto reemplaza al plan del 09-09, que cargaba 2026 congelado hasta la 1ra de agosto.

Consecuencia: se cae la etapa de importación entera, y con ella la conciliación posterior con el liquidador. Queda un solo criterio de aceptación, más simple y más exigente.

---

## 4. Correcciones que el módulo introduce

Encontradas midiendo sobre los datos reales. Cambian números respecto del Excel.

| Qué | Estado hoy |
|---|---|
| **Fecha de los repuestos** | La consulta usa la fecha del encabezado del movimiento; la correcta es la de la descarga a la maquinaria. Medido sobre 2026: el 69% de las 1.320 líneas tiene las dos fechas distintas y el **46% cae en otra quincena**. Hay 60 líneas con encabezado de noviembre de 2025 y descarga en enero de 2026 |
| **Seguros** | Se liquidan por un circuito separado del Excel. El módulo los absorbe |
| **Máquinas sin cubrir** | El sistema de compras tiene máquinas de terceros que la app del taller no tiene |
| **Precios inconsistentes** | Con el precio tipeado por fila hay grupos de viajes idénticos con dos precios distintos alternados. El tarifario los elimina |
| **Ids duplicados** | 3 máquinas existen en compras y en el taller con id distinto; una tiene 27 líneas de repuestos este año que quedan de un lado solo |

---

## 5. Modelo de datos (borrador)

Todas con prefijo `terceros_`, en `migrations/terceros/001_crear_tablas.sql`. El padrón de terceros, colectivos y maquinaria **no se replica**.

| Tabla | Qué guarda |
|---|---|
| `terceros_liquidacion` | La cabecera por quincena: cuándo se generó, su estado |
| `terceros_viaje` | El viaje traído del sistema de campo, congelado, con su tarifa aplicada |
| `terceros_hora_servicio` | Las horas de maquinaria de tercero, con su unidad base y precio aplicados |
| `terceros_carga_combustible` | Las cargas, con litros, vale y precio aplicado |
| `terceros_repuesto` | Las salidas del sistema de compras, con el tercero resuelto y la marca de "no cobrar" con motivo |
| `terceros_hora_reparacion` | Copia de las horas aprobadas de la app del taller, con su precio |
| `terceros_seguro` | La cuota de cada póliza de la quincena |
| `terceros_tarifa_viaje` | tercero, cliente, finca, capataz → tipo y precio, con marca de heredada |
| `terceros_tarifa_servicio` | tercero, cliente, finca, tarea → unidad base y precio |
| `terceros_precio_combustible` | Precio por litro, por quincena y tercero |
| `terceros_precio_reparacion` | Precio de la hora de taller, por quincena y tercero |
| `terceros_precio_seguro` | Importe de la cuota, por maquinaria y tercero |
| `terceros_recibo` | Por tercero y quincena: totales, neto, pagado, saldo, estado, emisión |
| `terceros_ajuste` | Ajustes manuales con signo y motivo |
| `terceros_auditoria` | Registro de cambios manuales |
| `terceros_estacion_archivo` | Lo facturado por cada estación, con el mapeo de columnas guardado |

---

## 6. Etapas

Cada etapa termina con un PR mergeado. El criterio de aceptación de todas, a partir de la 6, es el mismo: **agosto de 2026 da lo mismo que la liquidación hecha a mano**.

| # | Qué | Termina cuando |
|---|---|---|
| 1 | ~~Las cuatro consultas de origen, en SQL parametrizado, con tests~~ | **Hecho (2026-09-10)** |
| 2 | ~~Ingesta y pantallas de solo lectura de la quincena~~ | **Hecho (2026-09-14)** |
| 3 | ~~Alertas de cruce entre los tres sistemas~~ | **Hecho (2026-09-16).** Pasan a ser parte de las Verificaciones |
| 4 | ~~**La quinta consulta: Horas de servicio**~~ | **Hecho (2026-09-16).** Ver abajo |
| 5 | ~~**Tablas propias, migración 001 y generar la quincena**~~ | **Hecho (2026-09-17).** Ver abajo |
| 6 | ~~**Tarifario**: las cinco tablas, por quincena, con copia y herencia~~ | **Hecho (2026-09-17).** Ver abajo |
| 7 | **Cálculo del neto**: aplicar la tarifa a cada hecho, regla más específica, ambiguos y sin tarifa a la vista. Cierra en **dos cifras**: Total a facturar y, restándole los seguros, Total a pagar | Los dos totales de agosto coinciden, tercero por tercero |
| 8 | **La grilla**: una sola pantalla filtrable por concepto, cliente, tercero y capataz, con exportar a Excel. Reemplaza las cuatro pantallas de la etapa 2 | El liquidador revisa agosto entero desde ahí |
| 9 | **Verificaciones por fuente**: duplicados en cada origen, más los cruces de la etapa 3 reorganizados | Se detecta un duplicado real antes de liquidar |
| 10 | **Estaciones de servicio**: subida de archivos con mapeo por estación, carga manual de La Angostura, y la marca del vale en la grilla | Se detecta un vale facturado y no cargado |
| 11 | **Cuenta corriente y recibo**: saldo, estados, emisión, congelado y PDF | Se manda una quincena real desde el sistema |
| 12 | **Panel gerencial** bajo `/api/terceros/gerencial` | Al final, con todo lo anterior en uso |

### Etapas 1 a 3 — cómo quedaron

**Etapa 1** (2026-09-10). Las cuatro consultas viven en `app/modulos/terceros/services/`. Tres son SQL contra el sistema de campo y el de compras; la cuarta baja el Sheet de la app del taller con `httpx` + `openpyxl`, sin dependencias nuevas, con la URL en `TALLER_SHEET_URL` fuera del repo. `scripts/validar_terceros_etapa1.py` las compara contra el Excel: `07-2Q` y `08-1Q` coinciden exacto, fila por fila y en los totales.

**Etapa 2** (2026-09-14). El módulo se activó al tener sus primeras pantallas. Un endpoint por conjunto y ninguno que los junte: hubo un `/resumen` y se sacó porque pedía los cuatro orígenes en serie y tardaba 15 segundos. Con cuatro, el navegador los pide en paralelo — 21,6 s a 12,1 s medidos. Estas pantallas las reemplaza la etapa 8.

**Etapa 6** (2026-09-17). `migrations/terceros/002_tarifario.sql` y la pantalla Tarifario, con las cinco tablas en solapas. Un solo juego de endpoints para los cinco (`/tarifario/{tipo}`) y una sola pantalla que arma sus columnas desde un descriptor: cinco circuitos iguales serían cinco lugares donde arreglar el mismo bug.

**Las dimensiones vacías se guardan como `''` y no como `NULL`.** Es la decisión menos obvia de la migración: en MySQL un UNIQUE deja pasar varias filas con NULL, así que con dimensiones nullable se podrían cargar dos reglas idénticas — justo el empate que el módulo no sabe resolver. Con `''` el índice único lo impide. Hacia afuera la API las devuelve como `null`, que es lo que significan.

**Copiar no pisa el destino**: trae sólo lo que falta, marcado como heredado. Editar un precio lo confirma —si alguien lo tocó, ya no es un precio arrastrado sin mirar— y también hay un botón de confirmar para dejarlo igual pero dicho por una persona.

**Etapa 5** (2026-09-17). `migrations/terceros/001_crear_tablas.sql` crea seis tablas: la cabecera de la quincena y una por conjunto. El Inicio pasa a ser el tablero de quincenas, con generar y actualizar.

**Generar no congela nada**: es una foto que se puede volver a sacar mientras el recibo no esté emitido. Actualizar **reconcilia por clave** en vez de rehacer —el mismo mecanismo que usa Preliquidación—: suma lo que apareció en el origen, saca lo que ya no está, y al borrar sacrifica primero las filas sin trabajo manual. Así se puede apretar Actualizar diez veces sin perder una quincena efectiva ni una marca de no cobrar.

Los precios **no** están en esta migración a propósito: se calculan en la etapa 7 y van con la suya, junto al código que los necesita.

Generar la 2da de agosto: **1.076 filas en 38 segundos**. Los inserts van en lote — uno por fila tardaba 82 segundos contra los 16 que cuesta leer los orígenes, así que casi todo el tiempo era ida y vuelta a la base.

**Etapa 4** (2026-09-16). `GET /api/terceros/horas-servicio`. La consulta la escribió el usuario contra Chinagro y se trajo tal cual; lo único que se cambió es el rango de fechas, que venía fijo en 2026. Sale de **tres** partes diarios —cosecha, maquinaria y pulverizadas, esta última por sus dos tractores— que son 2.244 filas en 2026. Trae **las dos horas**, jornal y máquina, porque cuál se paga lo decide la Unidad base de la tarifa: entre una y otra hay 4.177 horas de diferencia. Agosto da 178 filas en la 1ra quincena y 162 en la 2da.

En el mismo PR se renombró en el código lo que el glosario ya había renombrado: `/horas-taller` pasó a `/horas-reparacion`. Dejar el nombre viejo al lado del nuevo era exactamente la confusión que el glosario acababa de resolver.

**Etapa 3** (2026-09-16). `GET /api/terceros/alertas` y la pantalla de alertas, con seis tipos y el sistema donde se corrige cada uno. Dos criterios que salieron de medir: solo se alerta de lo accionable (de 11 máquinas sin par, 2 tenían movimiento) y la falta estructural no se lista fila por fila (43 de 46 maquinarias no cruzan, pero es una sola tarea). Esta pantalla se reorganiza en la etapa 9.

---

## 7. Pendientes

**Decisiones**
- **El rol de quien carga los seguros.** Hoy un módulo tiene `operador` y `gerente`. Quien carga los seguros no es ninguno de los dos: entra a una sola sección y no ve el resto. Agregar un tercer rol toca el núcleo, así que va en un PR aparte (regla 4 de `GUIA-MODULOS.md`).
- **La quincena de corte**: desde cuándo el módulo liquida en serio.
- **`reportlab`** como dependencia nueva para el PDF (etapa 11).

**Con el sistema de campo y sus responsables**
- El token del dueño en la descripción de la maquinaria.
- Un colectivo aparece con dos dueños distintos: ¿venta del vehículo o error de carga?
- Casos donde se cargó el nombre del capataz en lugar del dueño.
- **TRANSPORTE ALFONSO** tiene la descripción entera vacía y 13 viajes en 2026 (todos de BONETTO, abril y mayo). Definir si es TERCEROS, PROPIO o una ficha de baja.

**Con el liquidador**
- Los números de vale de cuatro dígitos de una de las estaciones.
- Si las cargas de la estación que no manda archivo se registran de alguna otra forma.

**Salidos de la etapa 1**
- **Ninguna hora de reparación de agosto está aprobada**: las 53 de la 1ra quincena están todas en `Pendiente`. Con la regla de "solo se cobran las aprobadas", esa quincena no cobraría una sola hora. Hay que definir quién aprueba y cuándo.
- **La heurística que deduce el tercero del nombre de la máquina falla** cuando el número de interno está separado del símbolo. No se afina: lo resuelve el campo propio del punto 3.1.
- **466 líneas de "MANO DE OBRA"** de enero a junio, con dos precios unitarios multiplicados por las horas, que suman $337 millones. Parece el total de una factura tomado como precio unitario. Fuera de lo validado, pero a resolver.

**Salidos de la etapa 2**
- **Una línea de horas de reparación desapareció del Sheet** entre el 9 y el 14 de septiembre, de una quincena ya liquidada. No fue rechazada: se borró. Confirma que la etapa 11 tiene que congelar el recibo al emitirlo.

**Salidos de importar el tarifario de agosto** (2026-09-17)

`scripts/importar_tarifas_del_excel.py` deriva las reglas del tarifario de los precios que hoy
están tipeados fila por fila. Agosto entero entró en **424 tarifas** (191 + 151 de viajes, 53 de
combustible, 25 de reparación, 4 de seguros). Lo que no entró, porque no se adivina:

- **Tres combinaciones de viaje con dos precios distintos en la misma quincena**: GODOY a ALSA
  SAN ANDRES ($180.000 y $190.000), ARANDA a LA CORUÑA LA FALDA ($200.000 y $220.000) y BUSTOS a
  CITRUSVIL LOS NOGALES ($185.000 y $210.000). Es exactamente lo que anticipa la sección 4.
- **Seis dueños con dos precios de combustible en la misma quincena**, y tres parecen error de
  tipeo más que negociación: CORNEJO con $239.000 contra $2.399 (dos ceros de más), EMPRESA 0001
  con $17.200 contra $2.035,24, y QUIROGA con una carga sin precio.
- **El precio de la hora de reparación es uno solo para todos** ($15.000 desde enero). El tarifario
  lo quiere por tercero, así que el importador se lo carga igual a cada uno; en cuanto se pacte
  distinto con alguien, la tabla ya lo soporta.
- **Los seguros del Excel son sólo los de la empresa** (EMPRESA 0001 y 0002), no los de los 32
  dueños que releva el grilling: esos van por el circuito separado que el módulo todavía no
  absorbió. Y se cargan por dueño, no por máquina, así que el importador repite el nombre en las
  dos columnas para no inventar un dato que el origen no tiene.

**Salidos de la etapa 3**
- **El puente entre compras y el taller ya está roto**: 3 máquinas con el mismo nombre y distinto id, una con 27 líneas de repuestos este año. Es lo primero a corregir antes de calcular.
- **Un colectivo lleva la patente de otro dueño** (DEMARCO, OSCAR con la de SALOMOM, FELIPE).
- Las alertas del sistema de campo que estaban abiertas **se corrigieron el 2026-09-16**: las 3 patentes inconsistentes y una de las dos propiedades inválidas.
