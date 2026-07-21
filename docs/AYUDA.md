# Guía de ayuda del sistema — para el liquidador

> **Qué es este documento.** Es la base de conocimiento del **asistente de ayuda de uso** del
> sistema de preliquidación. Explica **cómo se usa el sistema**, paso a paso, con los nombres
> exactos de pantallas, botones y mensajes tal como aparecen en la aplicación.
>
> El asistente **no accede a datos reales** (no ve sueldos, no calcula liquidaciones, no toca la
> base). Solo ayuda a moverse por el sistema. Ante una duda de un número concreto, siempre hay
> que verificarlo en la pantalla correspondiente.
>
> Está redactado en el vocabulario del negocio. Los términos técnicos (quincena, concepto común,
> reemplaza al común, heredado, etc.) están definidos en el glosario `CONTEXT.md`.

---

## Carga de precios

Todo lo relacionado con precios vive en una sola pantalla.

### Dónde está

- En el **menú de la izquierda**, tocá **Conceptos** (ícono 💲).
- La pantalla se titula **"Maestro de Conceptos y Precios"**.
- Arriba a la derecha del título hay un **selector de quincena**. Todo lo que ves y cargás
  corresponde a la quincena elegida ahí. El selector arranca solo en la **quincena generada más
  reciente**. Si todavía no se generó ninguna, muestra *"— Sin quincenas generadas —"*.
- Las quincenas se leen como **"1ra MAY 2026"**, **"2da MAY 2026"** (primera y segunda mitad del
  mes).

### Las 4 pestañas

Debajo del título hay cuatro solapas:

1. **Sin concepto** — combinaciones de tarea/cliente/finca de la quincena que **todavía no
   tienen un precio completo cargado**. Si hay faltantes, la solapa muestra un número `(N)` y se
   pinta como alerta. Es tu lista de pendientes.
2. **Comunes** — los precios **comunes** (aplican a una tarea para todos los clientes).
3. **Específicos** — los precios **específicos** (de un cliente y finca puntual).
4. **Panel de precios** — la vista central para **cargar y editar precios**: los muestra todos
   juntos en una tabla plana, permite edición rápida y el **cambio masivo**.

### Concepto = precio. Común vs. específico

Un "concepto" es un precio cargado. Hay dos tipos y **los dos siempre suman**:

- **Común**: no tiene cliente. Aplica a **todas** las líneas de esa tarea.
- **Específico**: es de un **cliente y finca** puntuales. Suma *además* del común.
- **Reemplaza al común**: un específico puede marcarse para que esa línea **pague solo lo
  específico, sin sumar los comunes de la tarea**. Los específicos nuevos **nacen con esta marca
  tildada** (se puede destildar). En el Panel de precios se ve como el badge **"Reemplaza"** en
  la columna REEMPLAZA (ahí solo se muestra; para cambiarlo hay que ir a la regla en la pestaña
  Específicos).

### Cargar o editar UN precio (rápido, desde el Panel de precios)

1. Entrá a la pestaña **Panel de precios**.
2. La tabla tiene las columnas: **TAREA · CÓDIGO · CLIENTE · FINCA · CAT · UNIDAD · REEMPLAZA ·
   PRECIO ANTERIOR · PRECIO**.
   - En CLIENTE, un común se muestra como **"— (común)"**.
   - En PRECIO, si no hay valor dice **"sin precio"**.
   - La columna **PRECIO ANTERIOR** te muestra cuánto valía ese mismo concepto en la quincena
     anterior, para comparar de un vistazo.
3. **Hacé click sobre el valor de la columna PRECIO** de la fila que querés tocar.
4. Se abre un campo para escribir el número, con dos botones: **✓** (confirmar) y **✕**
   (cancelar).
5. Confirmá con **✓** o con **Enter**. Cancelás con **✕** o con **Escape**.
6. Si el precio quedó vacío o no es un número, aparece el aviso **"Ingresá un precio válido"**.
7. Al confirmar, aparece **"Precio actualizado"** y la pantalla se refresca sola.

### Cargar o editar un precio desde una regla (Comunes / Específicos)

Si querés tocar algo más que el precio (código, unidad, tipo, categoría, o la marca "Reemplaza
al común"):

1. Entrá a **Comunes** o **Específicos**.
2. Abrí el grupo (tarjeta plegable) con el chevron **▼ / ▲**.
3. En la fila de la regla, tocá **Editar**.
4. Se despliegan los campos: **Código · Unidad · Precio · Tipo · Categoría** (y en específicos, el
   checkbox **"Reemplaza al común"**).
5. Guardá con **✓** o cancelá con **✕**. Aparece **"Regla actualizada"**.

Para **agregar una regla nueva** dentro de un grupo: completá Código, Unidad, Precio, Tipo y
Categoría, y tocá **"+ Agregar regla"**. Si te falta el código, avisa **"Ingresá un código"**;
al guardar bien, **"Regla guardada"**.

### Cambio masivo de precios (aplicar el mismo precio a muchos)

**Importante:** el cambio masivo **no se hace tildando filas**. Se aplica a **todas las filas que
queden visibles** según los filtros. Es decir: primero **filtrás** para dejar a la vista solo lo
que querés cambiar, y después aplicás.

1. Andá a la pestaña **Panel de precios**.
2. Achicá lo visible usando los filtros (ver abajo) y/o la búsqueda por código, hasta que en la
   tabla queden solo las filas que querés cambiar. A la derecha de la barra hay un contador
   **"N de M conceptos"** (cuántas quedaron filtradas del total).
3. Escribí el nuevo precio en el campo **"$ precio"**.
4. Tocá el botón **"Aplicar a los filtrados (N)"** (N = cuántas filas quedaron). Mientras aplica
   muestra **"Aplicando..."**.
5. Aparece una confirmación del navegador: **"¿Aplicar $X a N fila(s)?"**. Aceptá para confirmar.
6. Al terminar, aparece **"Precio aplicado a N línea(s)"**, se limpia el campo y la pantalla se
   refresca.

Validaciones del masivo:
- Precio vacío o no numérico → **"Ingresá un precio válido"**.
- Sin filas filtradas → **"No hay filas para aplicar"**.

### Los filtros del Panel de precios

- **Búsqueda por código**: campo con el texto **"Filtrar por código..."** (filtra por el
  comienzo del código).
- **⚙ Filtros**: despliega los filtros multiselección **en cascada**:
  - **Tarea**, **Cliente**, **Finca**.
  - Cada uno es un desplegable con **"Seleccionar todos"** y chips que se pueden quitar. Por
    defecto están en **"— Todas —"**.
- **✕ Limpiar**: resetea todos los filtros y la búsqueda.

### ¿El cambio de precio impacta en Revisión?

**Sí, y es automático.** Cuando cargás, editás o aplicás precios en forma masiva, el sistema
**recalcula solo** las líneas afectadas de esa quincena. La pantalla de **Revisión** y sus
estadísticas **se actualizan reactivamente** — no hace falta recalcular a mano ni volver a
generar nada.

Si abriste Revisión en otra pestaña/momento y no ves el cambio reflejado, es cuestión de
refrescar esa vista; el cálculo del backend ya quedó actualizado.

### Copiar precios de una quincena a otra

- Botón **"⧉ Copiar de quincena anterior"** (arriba, junto al título).
- Copia todos los conceptos de la quincena de origen a la de destino. Los que ya existen en el
  destino **se omiten** (no se pisan).
- Si el destino ya tiene una preliquidación generada, además **recalcula** las líneas con el
  maestro actualizado.

### Ver qué precios faltan

- La pestaña **Sin concepto** lista las combinaciones tarea/cliente/finca de la quincena que
  **no tienen un precio completo** (un concepto necesita **código Y precio** para contar como
  completo; con código pero sin precio, no cuenta).
- Desde la pantalla de **Revisión**, cuando faltan conceptos, hay un botón **"Ir a Conceptos →"**
  que te trae directo a esta pantalla.

### Mensajes que podés ver (referencia rápida)

- **"Precio actualizado"** — guardaste un precio individual.
- **"Precio aplicado a N línea(s)"** — terminó el cambio masivo.
- **"Regla guardada" / "Regla actualizada" / "Regla eliminada"** — altas y ediciones de reglas.
- **"Ingresá un precio válido"** — el precio quedó vacío o no es número.
- **"No hay filas para aplicar"** — quisiste hacer un masivo sin filas filtradas.
- **"Ingresá un código"** — quisiste agregar una regla sin código.
- **"No hay conceptos cargados para esta quincena."** / **"Ningún concepto coincide con los
  filtros aplicados."** — la tabla del panel está vacía por falta de datos o por los filtros.

---

## Generar una quincena (preliquidación)

Es el punto de partida de todo el flujo. Se hace en la pantalla de inicio.

### Dónde está

- En el menú de la izquierda, tocá **Inicio** (ícono 🏠). Es la pantalla titulada
  **"Preliquidaciones"**, con el subtítulo *"Seleccioná una quincena para generar o continuar"*.

### Generar / actualizar una quincena

1. En el panel **"NUEVA QUINCENA"**, abrí el selector y elegí la quincena. Las opciones son los
   **últimos 3 meses**, cada mes dividido en **"1ra quincena {mes año}"** y **"2da quincena {mes
   año}"**.
2. Tocá el botón **"▶ Generar / Actualizar"**. **No pide confirmación**: arranca en el momento.
3. Mientras procesa, el botón muestra **"Procesando..."** y aparece el aviso *"Consultando datos
   de campo y aplicando reglas... esto puede tardar unos segundos."* (trae los datos de campo y
   aplica las reglas — puede demorar).
4. Al terminar aparece un aviso de éxito (**"Preliquidación generada"** o el detalle que devuelva
   el sistema) y la quincena queda listada en el **HISTORIAL**.

> El botón dice "Generar / **Actualizar**" porque el mismo botón sirve para **volver a generar**
> una quincena que ya existe (por ejemplo, si cambiaron datos de campo). Regenerar no duplica: se
> recalcula sobre la misma quincena.

### El HISTORIAL

Debajo hay una tabla con todas las preliquidaciones ya generadas, con columnas **QUINCENA ·
TOTAL LÍNEAS · ALERTAS**. En ALERTAS, cada quincena muestra **"N alertas"** (en amarillo) si tiene
pendientes, o **"OK"** (en verde) si no. Para trabajar una quincena, hacé click en su fila o en el
botón **"Abrir →"** — eso te lleva a la pantalla de **Revisión**.

---

## Revisión de una quincena

Es la pantalla donde se trabaja línea por línea una quincena ya generada.

### Cómo se entra

**No hay un ítem de menú para Revisión.** Se entra siempre desde **Inicio → HISTORIAL**, clickeando
la fila de la quincena (o su botón **"Abrir →"**). La quincena queda fijada por la preliquidación
que abriste (no hay selector de quincena acá).

### Qué muestra

Arriba (barra superior): **"← Volver"** (vuelve a Inicio), un contador **"N líneas"**, un contador
**"N alertas"** si las hay, y los botones **"⊞ Liquidación masiva"** y **"↓ Exportar Excel"**.

La tabla lista todas las líneas de la quincena, con columnas: alerta · **FECHA · EMPLEADO · LEGAJO
· EMPRESA · TAREA · SUPERVISOR · CLIENTE · FINCA · GRUPO PAGO · HS. JORN. · HS. MAQ. · TANC. ·
UNID. · IMPORTE · CONCEPTOS**. Un valor en cero o vacío se muestra como **"—"**.

**Filtros** (arriba de la tabla):
- Búsqueda: **"Buscar empleado, legajo, tarea..."**.
- **⚙ Filtros**: multiselección en cascada por Cliente, Finca, Tarea, Empresa, Grupo de pago y
  Supervisor.
- **Chips de alerta**: **Incompleta**, **Legajo inválido**, **Empresa a verificar**, **Duplicado**
  (para ver solo las líneas con ese problema).
- **✕ Limpiar** resetea todo.

**Banners de alerta** (arriba de todo, cuando corresponde):
- Si hay líneas incompletas: *"N líneas incompletas — cargá los conceptos y precios en el
  maestro"*, con un botón **"Ir a Conceptos →"** que te lleva directo a cargar precios.
- Si hay otras alertas: un resumen con el desglose y un botón **"Ver solo alertas →"**.

### Qué es una línea incompleta

Una línea queda **incompleta** cuando **le falta el código de concepto o el precio en el maestro**
— es decir, esa tarea/cliente/finca todavía no tiene un precio cargado que la cubra. Se marca con
el badge **"INCOMPLETA"** (en la columna de alerta y en la de GRUPO PAGO). **Se resuelve cargando
el precio en la pantalla de Conceptos** (el botón "Ir a Conceptos →" del banner te lleva).

### Abrir y editar una línea (panel lateral)

Al hacer click en una fila se abre un panel a la derecha con el detalle de esa línea:

- **DATOS DE CAMPO** (solo lectura): fecha, planilla, legajo de campo, horas jornal, horas
  máquina, tancadas, unidades, supervisor, tractor.
- **ASIGNACIÓN** (editable): **Empresa** (botones, por defecto ASTURIANA) y **Legajo asignado**
  (campo de texto).
- **PRECIO** (editable): **Grupo de pago** (desplegable).
- **CONCEPTOS DE LIQUIDACIÓN** (editable): la lista de conceptos que se pagan en esa línea (ver
  abajo).
- **Observación** (editable, opcional).
- Botón **"Guardar"** abajo. Al guardar aparece **"Línea actualizada"**.

> En este sistema no hay un botón separado de "ajuste manual": ajustar una línea a mano **es**
> editarla en este panel (empresa, legajo, grupo de pago, conceptos, observación) y tocar Guardar.

### Agregar o quitar conceptos a una línea

Dentro del panel, en **CONCEPTOS DE LIQUIDACIÓN**:

1. Tocá **"+ Agregar concepto por código"**.
2. Elegí el concepto en el desplegable (**"— Seleccionar concepto —"**, se listan como *código —
   tipo*).
3. Tocá **"Agregar"** (queda deshabilitado hasta que elijas uno). Aparece **"Concepto agregado"**.
4. Para quitar un concepto, tocá la **"✕"** al lado. Aparece **"Concepto eliminado"**.

Los conceptos marcados **"(auto)"** son los que el sistema puso automáticamente por las reglas; los
demás los agregaste a mano. Abajo hay un **Desglose** con el importe de cada uno y el total.

### Liquidación masiva (aplicar a varias líneas de una persona)

Con el botón **"⊞ Liquidación masiva"** de la barra superior:

1. Elegí un empleado (buscador **"Buscar por nombre o legajo..."**).
2. Se listan sus líneas con **casillas**. Tildá las que querés tocar.
3. Con líneas seleccionadas podés: **"+ Agregar concepto"** a todas, **quitar** un concepto que ya
   tengan, o **"⇄ Reasignar empresa"**.
4. Al reasignar empresa: si alguna línea no tiene CUIL, avisa que esas **hay que editarlas a mano**
   (no se pueden reasignar en masa).

---

## Exportar a Excel

- Se exporta desde la pantalla de **Revisión** (no desde Verificación).
- En la barra superior, tocá **"↓ Exportar Excel"** (mientras baja muestra **"Exportando…"**).
- Descarga **toda la quincena** en un archivo Excel (no solo lo filtrado en pantalla).
- Si falla, aparece **"No se pudo exportar el Excel"**.

---

## Verificación (controles antes de cerrar)

Es una pantalla de **control y auditoría**: sirve para detectar excesos y comparar formas de pago
**antes de cerrar** la quincena. Salvo un dato (el valor hora de pulverización), acá **no se cargan
datos** — se mira.

### Dónde está

- Menú **Verificación** (ícono ✅). Arriba se elige la quincena (**"— Seleccionar quincena —"**).

### Los 6 controles

Se navegan con los botones de sección; cada uno muestra un número si hay casos:

1. **⏱ Horas excedidas** — empleados con **más de 13 horas jornal** en un mismo día.
2. **📦 Tancadas excedidas** — más de **35 tancadas** en un día.
3. **🌱 Plantas excedidas** — más de **6.000 plantas** en un día.
4. **👤 Resumen por empleado** — importe, días trabajados y $/día por empleado.
5. **📊 Plantas vs Jornal** — compara el rendimiento pagado por planta contra el jornal.
6. **📊 Tancadas vs Jornal** — compara lo pagado por tancada contra el jornal.

En los controles de excesos, cada caso es una tarjeta que se **clickea para expandir** y ver el
detalle de las líneas. Hay buscador (**"Buscar empleado o legajo..."**) y filtros.

### Valor hora pulverización

En la sección **"Tancadas vs Jornal"** está el **único campo editable** de Verificación: el
**"Valor hora pulverización"**. Escribí el número y confirmá con **Enter** o el botón **"Guardar"**.
Sin ese valor cargado, la comparación de esa sección no se puede mostrar (*"Cargá el valor hora
para ver la comparación a jornal."*).

---

## Mantenimiento (categorías de operario)

Sirve para asignarle a cada operario de mantenimiento su **categoría** en una quincena.

### Dónde está

- Menú **Mantenimiento** (ícono 🔧). *(En el menú se llama "Mantenimiento"; la pantalla se titula
  "Categorías de operarios de mantenimiento".)*
- Arriba se elige la quincena (**"— Seleccionar quincena —"**). Sin quincena elegida no se ve la
  tabla.

### Asignar una categoría

1. Elegí la quincena.
2. (Opcional) Filtrá con **"Buscar por nombre, CUIL o legajo..."**.
3. En la fila del operario, abrí el desplegable de la columna **CATEGORÍA** y elegí de
   **Categoría 1** a **Categoría 7** (o **"— Sin categoría —"** para dejarlo sin asignar).
4. **Se guarda solo al elegir** (no hay botón por fila). Aparece **"Categoría actualizada"**.

Las filas de operarios **sin categoría** quedan resaltadas, para que se vean de un vistazo.

### Heredar de la quincena anterior

- El botón **"⇩ Heredar de quincena anterior"** copia las categorías asignadas en la quincena
  previa. Al terminar avisa cuántas heredó (**"Se heredaron N categoría(s) de la quincena
  anterior"**).

---

## Sueldos / Empleados (todavía no disponible)

La pantalla de **Empleados / Sueldos** aún **no está habilitada** — muestra un cartel de
*"Próximamente"*. Hoy el sistema no permite editar sueldos ni consultar legajos desde ahí; los
datos de sueldos se toman automáticamente de la base correspondiente al generar la quincena. Cuando
se habilite, se documenta acá.
