# Facturación — pantallas

Brief de UX del módulo (sección 8.3 de `GUIA-MODULOS.md`), trabajado con `/impeccable shape`.
Dice qué se ve y qué se hace en cada pantalla; el diseño visual se hace con `impeccable` al
construir cada una. Los términos son los de [`CONTEXT-facturacion.md`](CONTEXT-facturacion.md).

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
  del núcleo y los componentes que ya existen (barra de filtros común, tablas, chips, overlay
  "Procesando...", avisos).
- La idea central es **de lo general al detalle**: Pendientes → Cruce del Cliente → tarea →
  finca → parte de campo. Cada nivel responde "¿por qué no cierra?".

## Pantallas

En el orden de las etapas del módulo.

- **Pendientes** (la que abre el módulo): el último mes cerrado y, por Cliente, sus Alertas de
  facturación como chips (sin facturar, facturado con diferencia, sin comprobante).
  - Cada Alerta lleva a donde se resuelve: al Cruce del Cliente, o al Comprobante sin
    Adjunto.
  - "Marcar revisada" pide un comentario. Las Alertas revisadas se ocultan, con un filtro para
    verlas.
- **Cruce**: Cliente (o todos) + rango de fechas, que arranca en el mes.
  - Grupos de tareas que se abren en tareas: Cantidad del campo, facturado, Diferencia,
    Diferencia en pesos. Las que superan el Umbral de diferencia se marcan con algo más que
    color.
  - Al abrir una tarea se ven sus fincas, y en cada finca, de un lado los partes del sistema de
    campo (fecha, supervisor, cantidad) y del otro las Líneas de comprobante que la facturan.
- **Comprobantes**: listado con la barra de filtros común (Cliente, Empresa emisora, tipo, mes,
  "sin adjunto").
  - Alta y edición: cabecera (Cliente, Empresa emisora, tipo, número del Sistema contable,
    fecha y, en una Nota de crédito, la Factura que corrige) y una **grilla de líneas tipo
    planilla** (fecha, tarea con autocompletar, finca opcional, cantidad, precio, importe
    calculado), pensada para copiar mirando el PDF con Tab. Lo típico es de 1 a 15 líneas.
  - Adjuntos: subir, ver y quitar. La Nota de crédito se muestra con importe negativo.
- **Grupo de facturación**: la lista de tareas del sistema de campo con su Grupo de
  facturación editable. Las tareas sin grupo aparecen primero.
- **Equivalencias**: por Cliente, el texto con que el cliente nombra la tarea → tarea del
  sistema de campo.
- **Importar orden**: subir el archivo de la Orden de facturación, previsualizar los renglones
  traducidos, marcar los que no tienen Equivalencia y definirla ahí mismo, y confirmar para
  crear las Líneas.
- **Panel** (gerente): lo facturado por Cliente y por grupo de tareas en el período.

## Estados y volúmenes

- Volúmenes: alrededor de 55 Clientes activos y unas 135 tareas, de las cuales unas 100 son
  facturables. Un Comprobante tiene de 1 a 15 Líneas en general; una importación de una Orden
  de facturación grande trae cientos de renglones.
- Pendientes vacíos: "todo facturado en <mes>". El mes en curso no se evalúa, y la pantalla lo
  dice.
- Un Cliente sin trabajo y sin Comprobantes no aparece.
- Comprobante histórico: sin Empresa emisora ni Adjunto, con una marca y sin Alerta.
- Tarea sin Grupo de facturación: aviso en el Cruce.
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
- `PRODUCT.md` del front: sumar a las contadoras, el módulo y su vocabulario, con la primera
  etapa.
