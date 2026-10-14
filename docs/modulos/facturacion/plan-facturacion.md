# Plan del módulo Facturación

**Estado**: diseño cerrado, sin código. Las dos dependencias ya están entregadas (ver
"Dependencias"). El plan de implementación se hace **por etapa** con el planificador, en
`docs/superpowers/plans/`: uno de las cinco etapas con archivos y tests concretos quedaría
viejo antes de llegar a la mitad (2026-10-11).
**Fecha de la decisión**: 2026-10-08, entrevista sobre la planilla de facturación a clientes y
el informe de Power BI que la cruza contra el sistema de campo. **Rediseño del flujo**:
2026-10-14, con un mockup aprobado por el usuario: las pantallas Pendientes y Cruce pasan a
Resumen y Detalle, la carga se hace con la Precarga y las Alertas pasan a ser Estados del mes
(secciones 3.2 a 3.4, 3.7 y 5).
**Quién lo construye**: Gero.

El glosario está en [`CONTEXT-facturacion.md`](CONTEXT-facturacion.md), las pantallas en
[`pantallas.md`](pantallas.md) y la decisión sobre los adjuntos en
[ADR-0019](../../adr/0019-adjuntos-en-carpeta-del-vps.md). Los nombres de los clientes, la
planilla de origen y los detalles del informe de Power BI están en `fuentes/`, **fuera de git**
(ver `fuentes/LEEME.md`).

---

## 1. Qué reemplaza

Una planilla de Google Sheets y un informe de Power BI:

- **La planilla**: cada factura emitida en el Sistema contable se pasa a mano, renglón por
  renglón, ya traducida a tareas del sistema de campo. Para los clientes que publican su Orden
  de facturación en un portal, hay una hoja por formato con la traducción a mano de cada
  renglón y otra con las equivalencias de ese cliente. Las contadoras leen la traducción y la
  vuelven a tipear.
- **El informe**: cruza lo facturado contra lo cargado en el sistema de campo, por cliente,
  grupo de tareas y mes.

Lo que el módulo resuelve y la planilla no:

- **Un solo lugar** para registrar, adjuntar y controlar, sin tipear dos veces lo que el
  cliente ya mandó.
- **Alertas** de lo que falta facturar, de lo facturado con diferencia y de lo que no tiene
  PDF, en vez de descubrirlo mirando el informe.
- **Reglas a la vista**: qué cantidad del campo se compara con cada tarea queda como dato
  editable, no escondido en una fórmula.

## 2. Alcance

**Entra**: las tareas agrícolas (planillas de maquinaria, pulverización y tareas manuales del
sistema de campo), la carga de Comprobantes, los Adjuntos, el Cruce, las Alertas de
facturación, los importadores de órdenes de los clientes con portal y un panel de lo
facturado.

**No entra**:

- **La cosecha.** Se factura distinto (bins, toneladas, viajes) y es probable que sea un
  submódulo propio. Ver "A futuro".
- **La mano de obra y el combustible.** El resultado operativo (facturación menos mano de obra
  y combustible) es de un futuro Gerencial que consolide módulos. Facturación no lee nada de
  Preliquidación (ADR-0013).
- **Leer el Sistema contable.** Su API es paga y no está claro que el detalle de una factura
  alcance para traducirla a tareas.

## 3. Decisiones tomadas

### 3.1 El Comprobante

- **Comprobante = cabecera + líneas.** Cabecera: Cliente, Empresa emisora, tipo, número del
  Sistema contable, Fecha de carga y Período facturado. Se identifica por **Empresa emisora y número**, y el sistema frena
  una carga repetida.
- **Dos tipos: Factura y Nota de crédito.** La Nota de crédito apunta a la Factura que corrige
  y sus Líneas **restan** en el Cruce. Si se olvidó facturar algo, se emite otra Factura. No se
  agrega la nota de débito hasta que aparezca un caso real.
- **Importes en neto, sin IVA.** El Cruce compara cantidades y neto; el total con IVA está en el
  PDF.
- **El Cliente es el del maestro de clientes del sistema de campo** (que ya usa el nombre
  comercial), leído a través del núcleo. Los clientes dados de baja no se ofrecen para
  Comprobantes nuevos, pero se ven en el histórico.
- **La Empresa emisora** es cualquier Empresa del grupo: un Cliente puede recibir Comprobantes
  de varias.
- **Dos fechas** (2026-10-14). La **Fecha de carga** es el día en que se registra, la pone el
  sistema y no se edita. El **Período facturado** (desde y hasta) dice qué trabajo cobra y en
  qué mes cuenta: se propone solo y la contadora lo puede cambiar al mes anterior, a una
  quincena o a otros días. **Queda siempre dentro de un mismo mes**: si una factura cobrara
  trabajo de dos meses, el Resumen no sabría dónde contarla, y el usuario confirmó que no pasa.
  Reemplaza a la fecha por Línea del diseño anterior (cualquier día del mes). Finca opcional.

### 3.2 La carga

- **La Precarga** (2026-10-14). La factura no se tipea desde cero: el módulo la arma con lo
  trabajado en el Período facturado, una Línea por tarea con la Cantidad del campo, la Unidad
  sugerida y el **Precio sugerido** (el de la última Factura al mismo Cliente, por la misma
  tarea y en la misma unidad; las Notas de crédito no cuentan; si no hay, queda vacío y
  marcado). La Empresa emisora sale de la última Factura al Cliente. La contadora completa el
  número y el PDF y puede cambiar todo. Si cambia el Período facturado, las Líneas se
  recalculan sólo si lo confirma. Descartado: tomar el precio de otro Cliente.
- **Dos fuentes para la Precarga.** Lo trabajado, para cualquier Cliente (de 1 a 15 líneas en
  general). Y un **Importador de órdenes por formato**, para los clientes que publican su orden
  en un portal: se abre desde la Precarga y reemplaza sus Líneas por las de la orden.
- **Equivalencias por Cliente**, guardadas en el módulo: cómo nombra el cliente la tarea → tarea
  del sistema de campo. Un renglón sin Equivalencia frena la importación hasta que alguien la
  define, y queda guardada para la próxima. La primera carga sale de las hojas de equivalencias
  de la planilla. Nada se traduce por parecido de nombre.
- **El primer importador es el del cliente con más volumen, en su formato nuevo.** El segundo
  cliente con portal va después. Cada formato nuevo es un importador más, sin rehacer los
  anteriores.

### 3.3 El Cruce

- **Unidad de facturación por Línea.** Cada Línea de comprobante dice en qué unidad se
  factura, y esa unidad dice qué cantidad del campo se compara con lo facturado:

  | Unidad de facturación | Cantidad del campo |
  |---|---|
  | Horas de peón | horas de jornal |
  | Horas de tractor | horas de máquina |
  | Plantas | unidades |
  | Hectáreas | unidades |
  | Tancadas | tancadas |
  | Bins, Bins C, Bins M, Viajes (cosecha) | no entra al Cruce |

  Las unidades de cosecha existen para que sus tareas y sus líneas históricas queden con la
  unidad que usa la planilla; quedan fuera del Cruce y de las Alertas hasta el submódulo de
  cosecha (decidido el 2026-10-11). Así una misma tarea se puede facturar por planta un mes y por hora otro, y el Cruce compara
  cada vez contra la medida correcta.
- **Unidad sugerida y No facturable por tarea.** Cada tarea del sistema de campo tiene una
  Unidad sugerida, que precarga la Línea y que el Cruce usa cuando la tarea todavía no tiene
  nada facturado en el rango, o la marca No facturable, que la deja fuera del Cruce y de las
  Alertas. Se definen en el sistema de campo (hoy, el tercer segmento de la descripción de la
  tarea) y el módulo las lee en vivo, sin copia: la app de campo es la dueña del dato y así no
  hay desfasajes (decidido el 2026-10-12). **Una tarea facturable sin Unidad sugerida genera un
  aviso en el Resumen** (etapa 3): el informe anterior la dejaba en cero sin decir nada.
- Decidido el 2026-10-11, al planificar la etapa 1. Descartado: la unidad fija por tarea del
  diseño original ("Grupo de facturación"), porque una tarea que un cliente pide facturar por
  hora y otro por planta comparaba horas contra plantas.
- Pendiente para el plan de la etapa 3: qué muestra el Cruce cuando una misma tarea se factura
  en dos unidades dentro del mes.
- **Clave del Cruce: Cliente + mes + tarea**, agrupado por grupo de tareas. Lo facturado cuenta
  en el mes de su Período facturado. La finca no es parte de la clave (en la planilla casi
  nunca se carga).
- **Se mira por mes completo** (2026-10-14; antes, rango libre que arrancaba en el mes). Una
  diferencia de una quincena puede compensarse en la siguiente; mirar por quincena generaría
  alarmas falsas. El Resumen junta varios meses, una fila por mes y Cliente.
- **La Diferencia en pesos** se valoriza con el precio unitario de lo facturado. No hay lista
  de precios pactados: la tabla de precios que tiene el informe es del proceso de liquidación
  anterior y no aplica.
- **El detalle llega hasta el parte de campo, sin pasar por la finca** (2026-10-14): tarea →
  sus partes del sistema de campo (fecha, dónde, supervisor, cantidad). Los Comprobantes del mes
  se abren aparte. Descartado: el nivel por finca del diseño anterior, que el mockup no
  necesitó.

### 3.4 El Estado del mes y las Alertas

Rediseñado el 2026-10-14. Cada mes y Cliente tiene un **Estado del mes**; tres de ellos son
**Alertas de facturación**, que piden que alguien haga algo:

- **Pendiente de facturar** (Alerta): tuvo trabajo facturable y no tiene nada facturado. Es
  sólo un estado del mes; el Comprobante histórico sin número posterior al corte no cuenta como
  facturado, y no tiene término propio.
- **Con diferencia** (Alerta): **por tarea, en cantidades**. Basta que una tarea facturable se
  aparte más del Umbral de diferencia, para arriba o para abajo; una tarea trabajada y no
  facturada también cuenta. Reemplaza el criterio por grupo de tareas del diseño anterior.
- **Falta comprobante** (Alerta): algún Comprobante del mes sin Adjunto, salvo los históricos.
- **Facturada**: ninguno de los anteriores.
- **Mes en curso**: el mes no terminó. Sólo se controla Falta comprobante, porque es de la
  factura y no del mes; lo demás, desde el primer día del mes siguiente.
- **Antes del corte**: anterior al Mes de corte. Se ve, pero no se controla.

Reglas:

- **Varios estados por fila.** Un mes puede tener varios (por ejemplo, Con diferencia y Falta
  comprobante). Cada uno es un link a donde se resuelve, y el botón de la fila va al más
  urgente: Pendiente de facturar, Con diferencia, Falta comprobante. Pendiente de facturar y
  Facturada van siempre solos. Los cuadros y el filtro de Estado cuentan cada Alerta por
  separado.
- **Umbral de diferencia**: uno solo para todos los Clientes y tareas, arranca en 5 % y lo
  cambia sólo el Admin. Uno por Cliente o por tarea se suma si hace falta.
- **Mes de corte**: arranca en octubre de 2026 y lo mueve sólo el Admin, por ejemplo cuando se
  terminó de revisar lo anterior. Reemplaza al corte fijo del diseño anterior.
- **Revisión de diferencia** (antes, Alerta revisada): sobre un mes Con diferencia, con un
  comentario obligatorio; guarda quién, cuándo y **las tareas que superaban** en ese momento.
  Si siguen superando las mismas, el mes queda Facturada con la nota "Diferencia revisada"; si
  supera una tarea que no estaba, vuelve a Con diferencia; si ya no supera ninguna, queda
  Facturada y la Revisión, en el registro. Si una diferencia se compensa entre meses, salta igual
  y se revisa: el sistema no adivina compensaciones. Sólo se revisa Con diferencia: un Pendiente
  de facturar no se marca como revisado (decisión del usuario).
- **Nombres**: los de la pantalla en todos lados. Salen "sin facturar", "facturado con
  diferencia", "sin comprobante" y "Alerta revisada".

### 3.5 Los Adjuntos

- **En una carpeta del VPS**, fuera de la del código, con la ruta en el `.env`; la base guarda
  la referencia (ADR-0019).
- **Varios por Comprobante** (hasta cinco): lo normal es uno, a veces una reimpresión o una
  versión corregida que no cambia los números.
- Sólo PDF e imagen, con tamaño máximo.

### 3.6 El histórico

- **Se migra la hoja de facturación de la planilla** (desde abril de 2025). Las líneas se
  agrupan en Comprobantes por número y Cliente. Lo que la planilla no tiene (Empresa emisora,
  PDF) queda vacío y el Comprobante se marca como **histórico**: no genera la alerta "sin
  comprobante".
- **La migración se puede correr más de una vez** y cada corrida suma sólo lo nuevo, sin
  duplicar. Entre la etapa de comprobantes y la del primer importador, las contadoras siguen
  cargando en la planilla, y el Cruce se valida con datos al día.
- Las líneas de cosecha de la planilla se migran igual (son lo facturado), pero quedan fuera
  del Cruce y de las Alertas.
- **Cuando entra el primer importador, la planilla queda congelada** como respaldo de sólo
  lectura.

### 3.7 Permisos: pantallas con Ver o Editar

El módulo declara sus pantallas (ADR-0020), y cada endpoint exige Ver o Editar en una de
ellas. Reemplazan a las tres capacidades del diseño original (consultar, cargar, mantener):

| Pantalla | Ver | Editar |
|---|---|---|
| **Resumen** | el Resumen y el Detalle de cada mes y Cliente | dejar una Revisión de diferencia |
| **Comprobantes** | los Comprobantes y sus Adjuntos | cargar con la Precarga y editar, adjuntar e importar Órdenes de facturación |
| **Equivalencias** | las Equivalencias por Cliente | crearlas y cambiarlas |
| **Panel** | sí, desde Gerencial | — (sólo Ver) |

- **Resumen reemplaza a Pendientes y Cruce** (2026-10-14): el Detalle es el Cruce de una fila
  del Resumen, y separarlos permitiría ver los estados sin poder ver por qué. Cómo se pasan las
  claves de pantalla ya declaradas (`pendientes` y `cruce`) lo decide el plan de la etapa 3:
  nadie tiene todavía el rol del módulo.
- **Importar orden va dentro de Comprobantes**, no como pantalla propia: importar es otra
  forma de crear Comprobantes, y separarlas permitiría importar sin poder cargar a mano.
- **El Umbral y el Mes de corte los cambia sólo el Admin.** Quien deja Revisiones no los puede
  tocar, para no hacer desaparecer las Alertas. Dónde los cambia lo decide la etapa 3.
- **El módulo no crea roles.** Al activarlo, el admin arma desde la Administración el rol de
  las contadoras y suma al de Gerente lo que corresponda. Las contadoras están en el padrón
  de empleados y se dan de alta como cualquier usuario.

## 4. Lo que el informe anterior hace y conviene no copiar

A revisar cuando se valide el Cruce contra el informe (etapa 3):

- **Pulverización con dos tractores**: el informe compara sólo las horas del primer tractor.
  Decidido el 2026-10-12: se cuenta un solo tractor; cuál, lo confirma la etapa 3.
- **Tarea sin unidad**: el informe la deja en cero en silencio. El módulo avisa en el Resumen
  (etapa 3).

## 5. Etapas

Cada etapa es un par de PRs hermanos (backend y frontend). Deploy sólo con OK.

| Etapa | Qué entra | Se da por buena cuando |
|---|---|---|
| **1** | El módulo registrado y activo, con sus pantallas. La **Unidad sugerida** y la marca **No facturable** de cada tarea, con su primera carga y la pantalla Unidad de medida por defecto. `PRODUCT.md` del front con las contadoras y el módulo. Esa pantalla, con su tabla y su primera carga, se retiró el 2026-10-12: la Unidad sugerida y No facturable se leen del sistema de campo. | Cada tarea tiene Unidad sugerida o es No facturable, y las que no tienen nada se ven primero. |
| **2** | **Comprobantes** (Factura y Nota de crédito, cabecera y líneas), **Adjuntos** en la carpeta del VPS y la **migración del histórico**, re-ejecutable. | El histórico migrado suma lo mismo que la planilla, por Cliente y mes. |
| **3** | **Resumen** y **Detalle** (el Cruce por mes, hasta los partes del campo), con el **Estado del mes**, las Alertas, la Revisión de diferencia, el Umbral y el Mes de corte (dónde los cambia el Admin, lo decide esta etapa). La **Precarga**, con el Período facturado, la Fecha de carga y el Precio sugerido. El aviso de tarea facturable sin Unidad sugerida, en el Resumen. Rediseñada el 2026-10-14; el plan puede partirla en dos. | El Cruce da los mismos números que el informe de Power BI para los meses ya cerrados, salvo las diferencias explicadas en la sección 4, y una factura del mes pasado se carga desde el Resumen con la Precarga. |
| **4** | **Importador del primer cliente con portal** (formato nuevo), dentro de la Precarga, y **Equivalencias** por Cliente, con su primera carga. **Las contadoras dejan la planilla.** | Una orden real se importa completa, y cada renglón sin Equivalencia frena hasta definirla. |
| **5** | **Importador del segundo cliente con portal** y **Panel** de lo facturado por mes, Cliente y grupo de tareas, en Gerencial. | Lo mismo que la etapa 4 para el segundo formato. |

## 6. Dependencias

1. **Cambio del esquema de permisos** (tarea aparte, del núcleo): entregado y deployado el
   2026-10-11 (ADR-0020). El módulo nace con pantallas.
2. **Refinamiento de Preliquidación**: entregado y deployado el 2026-10-09. Su barra de
   filtros, sus tablas, su aviso de error y su estado por pantalla son de Preliquidación
   (`src/modulos/preliquidacion/`), y un módulo no importa a otro (ADR-0013): para que
   Facturación los use, antes hace falta un PR del núcleo que los suba a `src/core/`. Las
   clases globales (`.input`, `.chip`, `.table-wrap`), el overlay "Procesando..." y
   `CargandoContenido` sí son del núcleo.

## 7. Pendientes

- **Respaldo de la carpeta de adjuntos** en el VPS. Se suma al pendiente de confirmar el
  respaldo de la base (ADR-0019).
- **Umbral de diferencia**: arranca en 5 %. Se ajusta con el uso. Dónde lo cambia el Admin lo
  decide la etapa 3.
- **El Período facturado de los Comprobantes históricos y de los ya cargados**: hoy cada Línea
  tiene su fecha. Cómo se pasa al Período facturado lo decide el plan de la etapa 3.- **Pegar varias filas desde Excel** en la grilla de líneas: por ahora no. Se agrega si las
  contadoras lo piden.

## 8. A futuro

- **Cosecha**, como submódulo. Antes hay que definir si se factura por bin o por tonelada, si
  el descarte se factura, y cuál de las dos reglas que hoy conviven en el informe es la buena.
- **Gerencial consolidado**: el resultado operativo (facturación menos mano de obra y
  combustible), como el informe que hoy hace eso en Power BI. Lleva su propio ADR, porque
  consolida módulos.
- **Lectura del Sistema contable** por API, si se paga y el detalle alcanza para traducir.
- **Otros clientes con portal**: un importador por formato.
