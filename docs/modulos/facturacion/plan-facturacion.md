# Plan del módulo Facturación

**Estado**: diseño cerrado, sin código. El plan de implementación (los pasos de cada etapa,
con archivos y tests) se hace con el planificador **cuando estén mergeados el cambio de
permisos y el refinamiento de Preliquidación** (ver "Dependencias"): hecho hoy, citaría
componentes del front que esas tareas están cambiando.
**Fecha de la decisión**: 2026-10-08, entrevista sobre la planilla de facturación a clientes y
el informe de Power BI que la cruza contra el sistema de campo.
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
  Sistema contable, fecha. Se identifica por **Empresa emisora y número**, y el sistema frena
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
- **Cada Línea lleva una fecha**, cualquier día del mes, sin forzar quincena. Finca opcional.

### 3.2 La carga

- **Dos vías.** A mano para cualquier Cliente: cabecera más una grilla de líneas tipo planilla
  (copiando del PDF, de 1 a 15 líneas en general). Y un **Importador de órdenes por formato**
  para los clientes que publican su orden en un portal.
- **Equivalencias por Cliente**, guardadas en el módulo: cómo nombra el cliente la tarea → tarea
  del sistema de campo. Un renglón sin Equivalencia frena la importación hasta que alguien la
  define, y queda guardada para la próxima. La primera carga sale de las hojas de equivalencias
  de la planilla. Nada se traduce por parecido de nombre.
- **El primer importador es el del cliente con más volumen, en su formato nuevo.** El segundo
  cliente con portal va después. Cada formato nuevo es un importador más, sin rehacer los
  anteriores.

### 3.3 El Cruce

- **Grupo de facturación por tarea.** Cada tarea del sistema de campo tiene un Grupo de
  facturación que dice qué cantidad del campo se compara con lo facturado:

  | Grupo de facturación | Cantidad del campo |
  |---|---|
  | Horas de peón | horas de jornal |
  | Horas de tractor | horas de máquina |
  | Plantas | unidades |
  | Hectáreas | unidades |
  | Tancadas | tancadas |
  | No facturable | no entra al Cruce |

  El módulo guarda el grupo y se edita desde una pantalla. La primera carga sale del maestro de
  tareas de la planilla. **Una tarea sin grupo genera un aviso**: el informe anterior la dejaba
  en cero sin decir nada.
- **Clave del Cruce: Cliente + rango de fechas + tarea**, agrupado por grupo de tareas. La finca
  sirve para abrir el detalle, no es parte de la clave (en la planilla casi nunca se carga).
- **El rango es libre y arranca en el mes completo.** Una diferencia de una quincena puede
  compensarse en la siguiente; mirar por quincena por defecto generaría alarmas falsas.
- **La Diferencia en pesos** se valoriza con el precio unitario de lo facturado. No hay lista
  de precios pactados: la tabla de precios que tiene el informe es del proceso de liquidación
  anterior y no aplica.
- **El detalle llega hasta el parte de campo**: tarea → finca → cada registro del sistema de
  campo de un lado y cada Línea de comprobante del otro.

### 3.4 Las Alertas de facturación

- **Tres alertas**, evaluadas **por mes cerrado** (nunca sobre el mes en curso):
  - **Sin facturar**: el Cliente tuvo trabajo facturable en el mes y no tiene Líneas en él.
  - **Facturado con diferencia**: en algún grupo de tareas, la Diferencia del mes supera el
    Umbral de diferencia (configurable; arranca en 5%).
  - **Sin comprobante**: un Comprobante sin Adjunto.
- **Mes de corte: octubre de 2026.** Lo anterior se ve en el Cruce, pero no genera pendientes.
- **Alerta revisada**: una persona la marca con un comentario ("se compensó en noviembre"), y
  queda registrado quién y cuándo. Deja de contar como pendiente. Si una diferencia se compensa
  entre meses, la alerta salta igual y se revisa: el sistema no adivina compensaciones.

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

### 3.7 Permisos: tres capacidades

El módulo no habla de roles sino de capacidades:

| Capacidad | Qué permite |
|---|---|
| **Consultar** | Pendientes, Cruce, Panel, Comprobantes y sus Adjuntos |
| **Cargar** | Crear y editar Comprobantes, importar órdenes, adjuntar |
| **Mantener** | Grupo de facturación, Equivalencias, Umbral de diferencia |

Con los roles de hoy: operador = las tres, gerente = consultar, admin = todo. Cuando cambie el
esquema de permisos (ver "Dependencias"), cambia sólo ese mapeo, no los endpoints. Las
contadoras están en el padrón de empleados y se dan de alta como cualquier usuario.

## 4. Lo que el informe anterior hace y conviene no copiar

A revisar cuando se valide el Cruce contra el informe (etapa 3):

- **Pulverización con dos tractores**: el informe compara sólo las horas del primer tractor.
  Si una tarea de pulverización se factura por horas, se cuenta de menos. Hay que confirmar
  cómo se factura antes de decidir si se suman las del segundo.
- **Tarea sin grupo de facturación**: el informe la deja en cero en silencio. El módulo avisa.

## 5. Etapas

Cada etapa es un par de PRs hermanos (backend y frontend). Deploy sólo con OK.

| Etapa | Qué entra | Se da por buena cuando |
|---|---|---|
| **1** | El módulo registrado y activo, con sus permisos. El **Grupo de facturación** de cada tarea, con su primera carga y su pantalla. `PRODUCT.md` del front con las contadoras y el módulo. | Todas las tareas facturables tienen grupo, y las que no lo tienen se ven primero. |
| **2** | **Comprobantes** (Factura y Nota de crédito, cabecera y líneas), **Adjuntos** en la carpeta del VPS y la **migración del histórico**, re-ejecutable. | El histórico migrado suma lo mismo que la planilla, por Cliente y mes. |
| **3** | **Cruce** (con el detalle hasta el parte de campo) y **Alertas de facturación** con Alerta revisada, Umbral y Mes de corte. Pantallas Pendientes y Cruce. | El Cruce da los mismos números que el informe de Power BI para los meses ya cerrados, salvo las diferencias explicadas en la sección 4. |
| **4** | **Importador del primer cliente con portal** (formato nuevo) y **Equivalencias** por Cliente, con su primera carga. **Las contadoras dejan la planilla.** | Una orden real se importa completa, y cada renglón sin Equivalencia frena hasta definirla. |
| **5** | **Importador del segundo cliente con portal** y **Panel** de lo facturado por Cliente y grupo de tareas. | Lo mismo que la etapa 4 para el segundo formato. |

## 6. Dependencias

1. **Cambio del esquema de permisos** (tarea aparte, del núcleo): se hace antes de la etapa 1,
   para que el módulo nazca con el esquema nuevo y no haya que migrar sus usuarios después.
2. **Refinamiento de Preliquidación** (en curso): Facturación reutiliza la barra de filtros
   común, las tablas y el estado por pantalla que esa tarea está cambiando. El plan de
   implementación se hace después de que termine.

## 7. Pendientes

- **Respaldo de la carpeta de adjuntos** en el VPS. Se suma al pendiente de confirmar el
  respaldo de la base (ADR-0019).
- **Umbral de diferencia**: arranca en 5%. Se ajusta con el uso.
- **Pegar varias filas desde Excel** en la grilla de líneas: por ahora no. Se agrega si las
  contadoras lo piden.
- **Horas del segundo tractor** en pulverización (sección 4): confirmar con las contadoras.

## 8. A futuro

- **Cosecha**, como submódulo. Antes hay que definir si se factura por bin o por tonelada, si
  el descarte se factura, y cuál de las dos reglas que hoy conviven en el informe es la buena.
- **Gerencial consolidado**: el resultado operativo (facturación menos mano de obra y
  combustible), como el informe que hoy hace eso en Power BI. Lleva su propio ADR, porque
  consolida módulos.
- **Lectura del Sistema contable** por API, si se paga y el detalle alcanza para traducir.
- **Otros clientes con portal**: un importador por formato.
