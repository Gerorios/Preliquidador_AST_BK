# Facturación — pantallas

Brief de UX del módulo (sección 8.3 de `GUIA-MODULOS.md`), trabajado con `/impeccable shape` y
rediseñado sobre un mockup aprobado por el usuario. Dice qué se ve y qué se hace en cada
pantalla; el diseño visual se termina con `impeccable` al construir cada una. Los términos son
los de [`CONTEXT-facturacion.md`](CONTEXT-facturacion.md).

## Para quién y en qué modo

- **Contadoras**: operan. Personal administrativo, en PC de escritorio, que necesita señales
  claras.
- **Gerente**: sólo consulta.
- Es una herramienta de trabajo diario sobre planillas: densidad sí, con jerarquía legible.

## El resultado que importa

Que a fin de mes ningún Cliente quede sin facturar, que cada Diferencia se explique o se
corrija, y que cada Comprobante tenga su Adjunto. La prueba de que funciona: el Cruce da los
mismos números que el informe de Power BI que hoy hace ese control.

## Dirección

- **Extensión del mundo actual**, no un diseño nuevo: los tokens de `src/index.css`, el layout
  del núcleo y lo que el núcleo ya tiene (las clases globales de campos, chips y tablas, el
  overlay "Procesando..." y `CargandoContenido`). Las pantallas copian la forma de
  Preliquidación: barra superior, barra de filtros con período y seleccionables, tabla con la
  fila TOTAL fija y panel lateral a la derecha. Lo que hoy es de Preliquidación (barra de
  filtros, tablas, aviso de error, estado por pantalla) pide antes un PR del núcleo que lo suba
  a `src/core/`.
- La idea central es **de lo general al detalle, y de ahí a la carga**: Resumen → Detalle del
  Cliente y el mes → partes del campo de una tarea. Desde el Resumen, lo que falta facturar se
  carga con la Precarga, ya armada con lo trabajado.

## Pantallas

- **Resumen** (la que abre el módulo):
  - Arriba, tres cuadros con las Alertas de facturación (Pendiente de facturar, Con diferencia
    y Falta comprobante), cada uno con su cantidad. Tocar uno filtra la tabla por esa Alerta.
  - Barra de filtros: período con atajos (Mes pasado, Este mes, Últimos 3 meses, Este año, Otro
    período) y seleccionables de Mes, Cliente y Estado. Arranca en el mes pasado.
  - Tabla, una fila por mes y Cliente: Horas peón, Horas tractor, Tancadas, Plantas, Hectáreas
    (lo trabajado según el campo), Facturado (neto), Estado y una acción. La fila TOTAL queda
    fija abajo.
  - La columna Estado muestra todos los Estados del mes de la fila. Cada etiqueta es un link a
    donde se resuelve: Con diferencia al Detalle, Falta comprobante al Comprobante sin
    Adjunto.
  - El botón de la fila lleva a la Alerta más urgente, en este orden: Pendiente de facturar
    (Cargar factura, abre la Precarga), Con diferencia (Ver diferencia), Falta comprobante
    (Adjuntar PDF). Sin Alertas, Ver detalle.
  - Una fila Facturada con Revisión de diferencia lleva la nota "Diferencia revisada". El mes
    en curso y los meses Antes del corte van en gris.
  - Un pie dice desde qué mes se controla, el Umbral de diferencia y que la cosecha no entra.
- **Detalle** (el Cruce de un Cliente en un mes):
  - Barra superior con el Cliente, el mes, el Estado del mes y los Comprobantes del mes como
    links.
  - Tabla por grupo de tareas y tarea: Unidad, Campo, Facturado, Diferencia y Dif. %. Las
    tareas que superan el Umbral de diferencia se marcan con una etiqueta, no sólo con color.
    Fila TOTAL del mes en pesos.
  - Al tocar una tarea, el panel lateral muestra la comparación y sus partes del campo: Fecha,
    Dónde, Supervisor y Cantidad, con el total. No se abre por finca.
  - "Marcar revisada" abre un panel con las tareas que superan y un comentario obligatorio.
    Una vez revisada, un aviso muestra quién, cuándo y el comentario, con "Deshacer".
  - No se factura desde acá: si falta facturar algo, se vuelve al Resumen.
- **Precarga** (cargar una factura o una nota de crédito):
  - Se abre desde el Resumen (con el mes y el Cliente de la fila) o con "Nueva factura" y
    "Nueva nota de crédito" en Comprobantes.
  - Datos de la factura: Tipo, Cliente, Empresa emisora (la de la última Factura al Cliente),
    Número (punto de venta y número), la Fecha de carga (hoy, sin editar) y el Período
    facturado.
  - El Período facturado tiene atajos (Mes pasado, Quincena pasada, Este mes, Otro período),
    Desde y Hasta, y dice en qué mes cuenta la factura. Si cruza de un mes a otro, queda en rojo
    y no se puede guardar. Si cambia, un aviso ofrece "Recalcular líneas" o "Dejar como
    están", y hasta elegir no se puede guardar.
  - Líneas: una por tarea trabajada en el período, con #, Tarea, Unidad (la Unidad sugerida),
    Campo (la Cantidad del campo, en amarillo si la cantidad no coincide), Cantidad, Precio
    unitario (el Precio sugerido; al pasar el mouse dice de qué factura sale), Importe y
    quitar. Sin Precio sugerido, el casillero queda vacío y marcado en rojo. Se pueden agregar
    líneas hasta 15, y todo se puede cambiar. Fila de Total neto.
  - Panel derecho: el PDF (arrastrar o elegir), el control del neto del PDF contra lo que suman
    las líneas (opcional), y "Falta para guardar" con lo que falta. Al pie, Cancelar y Guardar.
  - "Importar orden del portal" abre una ventana encima con los renglones de la Orden de
    facturación traducidos con las Equivalencias. Un renglón sin Equivalencia pide la tarea, con
    "Guardar para la próxima"; hasta completarlos no se puede usar la orden. Al usarla, las
    líneas se reemplazan por las de la orden y la columna Campo sigue mostrando lo trabajado.
- **Comprobante** (uno ya cargado, por ejemplo sin Adjunto):
  - Datos de la factura y sus líneas en sólo lectura, con el Período facturado y la Fecha de
    carga.
  - Panel lateral para adjuntar el PDF y ver los totales. Al adjuntarlo, el mes deja de tener
    Falta comprobante.
- **Comprobantes**: listado con la barra de filtros común (período y seleccionables de Cliente,
  Empresa emisora, Tipo, PDF y Origen, más la búsqueda por número), columnas Fecha, Número,
  Cliente, Empresa emisora, Origen, Neto y PDF ("Sin PDF" a la vista), y la fila TOTAL con la
  cantidad de facturas y de notas de crédito. Arriba, "Nueva factura" y "Nueva nota de
  crédito", que abren la Precarga. La Nota de crédito se muestra con importe negativo; un
  Comprobante histórico, con su marca y en sólo lectura.
- **Equivalencias**: tabla con Cliente, Texto del cliente, Tarea nuestra, Unidad y Último uso,
  con filtros de Cliente y Tarea y la búsqueda por texto. "Agregar equivalencia" abre el alta en el panel lateral.
  También se crean al importar una orden. Un mismo texto de un Cliente apunta a una sola tarea.
- **Panel** (gerente, en el marco de Gerencial): lo facturado en el período, neto de notas de
  crédito, por mes, por Cliente y por grupo de tareas, con filtros de Cliente, Grupo y Empresa
  emisora. Sólo consulta.

## Estados y volúmenes

- Volúmenes: alrededor de 55 Clientes activos y unas 135 tareas, de las cuales unas 100 son
  facturables. Un Comprobante tiene de 1 a 15 Líneas en general; una importación de una Orden
  de facturación grande trae cientos de renglones.
- Resumen sin filas con los filtros: "Nada con estos filtros".
- Un Cliente sin trabajo y sin Comprobantes en el mes no aparece.
- Comprobante histórico: sin Empresa emisora ni Adjunto, con una marca y sin Falta
  comprobante.
- Tarea facturable sin Unidad sugerida: aviso en el Resumen (etapa 3).
- La lectura del sistema de campo es lenta: indicador de carga. Toda escritura muestra el
  overlay.

## Límites

- Nada de cosecha.
- No se toca Preliquidación ni Liquidación Terceros.
- Ninguna dependencia nueva. Sin modo oscuro ni versión para celular.
- No se muestra el rol de la persona. Textos en español, sin emojis.

## Abierto

- Pegar varias filas desde Excel en la grilla de líneas: por ahora no; se agrega si las
  contadoras lo piden.
- Dónde cambia el Admin el Umbral de diferencia y el Mes de corte: lo decide la etapa 3.
- Dónde va el aviso de tarea facturable sin Unidad sugerida dentro del Resumen: lo decide la
  etapa 3.
