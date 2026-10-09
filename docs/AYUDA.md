# Guía de ayuda del sistema — para el liquidador y el gerente

> **Qué es este documento.** Es la base de conocimiento del **asistente de ayuda de uso** del
> sistema de preliquidación. Explica **cómo se usa el sistema**, paso a paso, con los nombres
> exactos de pantallas, botones y mensajes tal como aparecen en la aplicación.
>
> El asistente **no accede a datos reales** (no ve sueldos, no calcula liquidaciones, no toca la
> base). Solo ayuda a moverse por el sistema. Ante una duda de un número concreto, siempre hay
> que verificarlo en la pantalla correspondiente.
>
> Está redactado en el vocabulario del negocio. Los términos técnicos (quincena, concepto común,
> reemplaza al común, heredado, etc.) están definidos en los glosarios `CONTEXT.md` (el Sistema) y `docs/modulos/preliquidacion/CONTEXT-preliquidacion.md` (el módulo).

---

## Moverse por el sistema

### El Inicio y el menú

- Al entrar se ve el **Inicio** del sistema (*"Elegí dónde trabajar"*), con una tarjeta por
  módulo. La tarjeta **Preliquidación** lleva al liquidador al inicio del módulo (la pantalla
  **"Preliquidaciones"**) y al gerente a **Conceptos**. El gerente tiene además la tarjeta
  **Gerencial**.
- Dentro del módulo, el **menú de la izquierda** tiene **Inicio**, **Conceptos**,
  **Verificación** y **Mantenimiento** (el gerente ve solo **Conceptos**). Arriba de todo,
  **Módulos** vuelve al Inicio del sistema; abajo está **Cerrar sesión**.
- El botón **"« Contraer"** del pie achica el menú a solo íconos (pasando el mouse por cada ícono
  se ve su nombre); para volver a abrirlo se toca **"»"**. El sistema **recuerda** si dejaste el
  menú contraído, en ese navegador, también la próxima vez que entres.
- El botón **"Ayuda"**, abajo a la derecha, abre este asistente.

### La barra de filtros (igual en todas las pantallas)

Revisión, Verificación, Mantenimiento, Conceptos y Gerencial tienen arriba la **misma barra**, con
las cosas siempre en el mismo orden:

1. **Selector de quincena**. Las quincenas se leen como **"1ra quincena septiembre 2026"** y
   **"2da quincena septiembre 2026"** (primera y segunda mitad del mes); la más nueva va primero.
2. **Búsqueda** (el texto de ayuda del campo cambia según la pantalla).
3. Botón **Filtros**: abre los filtros de la pantalla. Cada filtro es un desplegable con
   casillas, una opción **"Seleccionar todos"**, y dice **"Todas"** mientras no elijas nada. Los
   filtros son **en cascada**: cada uno ofrece solo los valores que quedan con lo que ya elegiste
   en los demás (en Revisión, también con la búsqueda escrita y la alerta marcada). Con filtros
   elegidos, el botón muestra cuántos.
4. **Alertas** (solo en Revisión): ver más abajo.
5. **Limpiar**: aparece cuando hay algo filtrando y borra todo (búsqueda, filtros y alertas).

Debajo de la barra, la fila **"Filtrando por"** muestra cada cosa que está filtrando como un chip
(por ejemplo *Búsqueda: "…"*, *Cliente: …*, *Alerta: Duplicado*); la cruz de cada chip saca solo
ese filtro.

No todas las pantallas usan todo: Mantenimiento tiene solo quincena y búsqueda, y Gerencial solo
el período y la empresa.

### Lo que la pantalla recuerda al navegar

Cada pantalla del módulo **recuerda dónde la dejaste** mientras te movés por el sistema: la
quincena elegida, la búsqueda, los filtros, la solapa o sección abierta y el orden de las tablas.
Si filtrás Revisión, pasás a Conceptos y volvés, Revisión sigue filtrada.

Ese recuerdo se **borra** al **recargar la página (F5)**, al **cerrar sesión** y cuando entra
otra persona en el mismo navegador. Lo que sí queda guardado en el navegador aunque recargues es
si el menú estaba contraído y, en el Panel de precios, la vista elegida y el ancho de las
columnas.

### Con qué quincena arranca cada pantalla

- **Inicio** (Generar): arranca en la **última quincena generada**, si está entre las opciones del
  selector.
- **Verificación**, **Mantenimiento**, **Conceptos** y **Gerencial**: arrancan en la **última
  quincena generada**.
- **Revisión**: en la quincena que abriste desde el historial.

Mientras se carga la lista de quincenas, Verificación, Mantenimiento y Conceptos lo dicen
(**"Cargando quincenas…"**). Si no se pudo cargar, avisan **"No se pudieron cargar las quincenas. Probá recargar la página."**
(en el selector de Conceptos: **"No se pudieron cargar las quincenas"**). Solo cuando de verdad
no hay ninguna dicen **"Todavía no hay quincenas generadas."** (en Conceptos, **"Sin quincenas
generadas"**).

---

## Carga de precios

Todo lo relacionado con precios vive en una sola pantalla.

### Dónde está

- En el **menú de la izquierda**, tocá **Conceptos**.
- La pantalla se titula **"Maestro de Conceptos y Precios"**.
- Debajo del título está la barra de filtros, que empieza por el **selector de quincena**. Todo
  lo que ves y cargás corresponde a la quincena elegida ahí. El selector arranca solo en la
  **quincena generada más reciente**. Si todavía no se generó ninguna, muestra *"Sin quincenas
  generadas"*.
- La búsqueda escrita **se conserva al cambiar de quincena**; los filtros de las solapas de
  reglas se limpian.

### Las solapas

Debajo de la barra hay seis solapas:

1. **Sin concepto** — combinaciones de tarea/cliente/finca de la quincena que **todavía no
   tienen un concepto completo** (con código y precio). Si hay faltantes, la solapa muestra un
   número `(N)` y se pinta como alerta. Es tu lista de pendientes.
2. **Comunes** — las reglas **comunes**: valen para toda línea de la tarea, en cualquier cliente
   y finca.
3. **Por cliente** — valen para la tarea en cualquier finca de ese cliente.
4. **Por finca** — valen para la tarea solo en esa finca de ese cliente (los conceptos
   **específicos**).
5. **Por supervisor** — valen para la tarea cuando la supervisa esa persona.
6. **Panel de precios** — la vista central para **cargar y editar precios**: los muestra todos
   juntos, permite edición rápida y el **precio masivo**. Tiene dos vistas: **Por regla** y
   **Por concepto**.

Al cambiar de solapa se borran la búsqueda y los filtros de las solapas de reglas.

Qué ofrece la barra en cada solapa:
- **Sin concepto**: solo el selector de quincena.
- **Comunes**: búsqueda **"Buscar tarea..."**.
- **Por cliente**, **Por finca** y **Por supervisor**: búsqueda **"Buscar tarea, cliente, finca,
  supervisor..."** y **Filtros** por Tarea, Cliente, Finca y Supervisor.
- **Panel de precios**: búsqueda **"Filtrar por código..."** y **Filtros** por Tarea, Cliente,
  Finca y Supervisor.

### Cómo se combinan las reglas

Arriba de cada solapa de reglas (Comunes, Por cliente, Por finca, Por supervisor) hay un texto
que explica a qué alcanza ese tipo de regla y cómo se combinan:

- **Las reglas que coinciden con una línea se suman entre sí.** Una línea puede cobrar a la vez
  una común, una por cliente, una por finca y una por supervisor.
- **Reemplaza al común**: si una regla que no es común tiene tildado **"Reemplaza al común"**, a
  esa línea **no se le aplica la común de la tarea** (las demás reglas no comunes siguen
  sumando). Las reglas no comunes nuevas **nacen con esta marca tildada** (se puede destildar).
  En el Panel de precios (vista Por regla) se ve como una marca de tilde en la columna
  **REEMPLAZA**; ahí solo se muestra: para cambiarla hay que editar la regla en su solapa.

### Cargar o editar UN precio (rápido, desde el Panel de precios)

1. Entrá a la solapa **Panel de precios**, vista **Por regla**.
2. La tabla tiene una columna de casillas (para el precio masivo) y las columnas: **TAREA ·
   CÓDIGO · CLIENTE · FINCA · CAT · UNIDAD · REEMPLAZA · P. ANTERIOR · PRECIO**.
   - En CLIENTE, un común se muestra como **"— (común)"** y una regla por supervisor como
     **"Sup: …"**.
   - En PRECIO, si no hay valor dice **"sin precio"**.
   - La columna **P. ANTERIOR** te muestra cuánto valía ese mismo concepto en la quincena
     anterior, para comparar de un vistazo.
   - El ancho de cada columna se puede cambiar arrastrando el borde del encabezado; doble click
     en el borde lo vuelve a su ancho original.
3. **Hacé click sobre el valor de la columna PRECIO** de la fila que querés tocar.
4. Se abre un campo para escribir el número, con dos botones: uno con un tilde (**Guardar**) y
   otro con una cruz (**Cancelar**).
5. Confirmá con el tilde o con **Enter**. Cancelás con la cruz o con **Escape**.
6. Si el precio quedó vacío, no es un número o no es mayor que 0, aparece el aviso **"Ingresá un
   precio mayor que 0"**.
7. Al confirmar, aparece **"Precio actualizado"** y la pantalla se refresca sola.

### La vista Por concepto

En el Panel de precios, el botón **Por concepto** muestra el maestro agrupado: una tarjeta por
tarea, con una fila por **alcance** (común, cada cliente, cada finca, cada supervisor) y una
columna por cada código que esa tarea tiene en la quincena. Sirve para ver de un golpe si a algún
alcance le falta un código o un precio. El sistema recuerda cuál de las dos vistas usaste por
última vez.

- La tarjeta se abre o se cierra tocándola; **"Abrir todas"** y **"Cerrar todas"** las manejan
  juntas. La casilla **"Solo incompletos"** deja solo lo que tiene algo pendiente.
- La columna **Estado** de cada fila dice **"completo"**, **"falta …"** (los códigos que le
  faltan), **"… sin precio"**, **"N reglas sin código"** o, en las de supervisor, **"solo
  informativo — no se controla"**.
- El precio se edita igual que en la vista Por regla: click sobre el valor (o sobre **"sin
  precio"**), tilde o Enter para guardar. Si cambió respecto de la quincena anterior se ve
  **"ant. $…"**, y un precio copiado de otra quincena sin confirmar se marca **"heredado"**.
- Donde dice **"falta"**, un click abre el alta de ese código para ese alcance (**"Crear … para
  …:"**): elegí unidad, precio, tipo y categoría, y tocá **"Guardar"** (o **"Cancelar"**).
- El precio masivo **no** está en esta vista: está en **Por regla**.

### Cargar o editar un precio desde una regla (Comunes, Por cliente, Por finca, Por supervisor)

Si querés tocar algo más que el precio (código, unidad, tipo, categoría, o la marca "Reemplaza
al común"):

1. Entrá a la solapa de la regla (**Comunes**, **Por cliente**, **Por finca** o **Por
   supervisor**).
2. Abrí el grupo (tarjeta plegable) tocándolo; la flecha de la derecha indica si está abierto.
3. En la fila de la regla, tocá **Editar**.
4. Se despliegan los campos: **Código · Unidad · Precio · Tipo · Categoría** (y en las que no son
   comunes, la casilla **"Reemplaza al común"**).
5. Guardá con el tilde o cancelá con la cruz. Aparece **"Regla actualizada"**.

Para **eliminar** una regla, tocá el botón con la cruz de su fila (**Eliminar**), al lado de
**Editar**. No pide confirmación. Aparece **"Regla eliminada"**.

Para **agregar una regla nueva** dentro de un grupo: completá Código, Unidad, Precio, Tipo y
Categoría, y tocá **"+ Agregar regla"**. Si te falta el código, avisa **"Ingresá un código"**;
al guardar bien, **"Regla guardada"**, y el sistema pregunta **"¿Crear otra regla para …?"** con
**"Sí, otra"** y **"No, listo"**.

Para crear un grupo que todavía no existe, usá **"+ Nuevo"** (arriba de la lista): elegí la
**Tarea**, el **Alcance** (**Común**, **Por cliente**, **Por finca** o **Por supervisor**) y,
según el alcance, el cliente, la finca o el supervisor; completá código, unidad, precio, tipo y
categoría, y tocá **"Guardar"**. Si falta algo avisa **"Completá la tarea"**, **"Completá el
cliente"**, **"Seleccioná un supervisor"** o **"Ingresá un código"**.

### Avisos al guardar o borrar una regla

- **"Esta regla se va a SUMAR a reglas ya existentes"**: aparece cuando una regla por cliente y
  reglas por finca del mismo cliente van a pagar juntas las mismas líneas (un solapamiento por
  cliente). Muestra las reglas y cuántas líneas se ven afectadas, y avisa si alguna cobraría el
  mismo código **DOS VECES**. Podés **"Cancelar"**, **"Sumar igual"** o, si se ofrece, **"Crear
  solo para …"** (la finca que faltaba).
- Cuando la quincena ya tiene solapamientos, arriba de las solapas aparece la franja **"Esta
  quincena tiene N solapamiento(s) por cliente que suma(n)"**, con los botones **"Ver por
  cliente"** y **"Ver específicas"** que llevan a las reglas involucradas.
- **"Se van a borrar conceptos extra"**: aparece si editar o borrar la regla deja sin efecto
  conceptos que se agregaron a mano por código en Revisión. Podés **"Cancelar"** o **"Borrar
  extras y continuar"**.

### Precio masivo o cambio masivo (aplicar el mismo precio a muchos)

El precio masivo se aplica a las filas **visibles y tildadas** del Panel de precios (vista **Por
regla**). Al filtrar, **todas las filas que quedan están tildadas**: primero **filtrás** para dejar
a la vista lo que querés cambiar y, si hace falta, **destildás** las que no querés tocar.

1. Andá a la solapa **Panel de precios**, vista **Por regla**.
2. Achicá lo visible con la búsqueda por código y los **Filtros** de la barra.
3. Si querés dejar alguna fila afuera, destildá su casilla. La casilla del encabezado tilda o
   destilda todas las filas filtradas. A la derecha se ve **"N de M conceptos"** (cuántas quedaron
   filtradas del total) o, si destildaste alguna, **"N destildada(s) conservan su precio"**.
4. Escribí el nuevo precio en el campo **"$ precio"**.
5. Tocá **"Aplicar a la selección (N de M)"** (N = filas tildadas, M = filas filtradas). Mientras
   aplica muestra **"Aplicando..."**.
6. Aparece una confirmación del navegador: **"¿Aplicar $X a N fila(s)?"** (si destildaste
   alguna, agrega cuántas conservan su precio). Aceptá para confirmar.
7. Al terminar, aparece **"Precio aplicado a N línea(s)"**, se limpia el campo y la pantalla se
   refresca.

Cambiar la búsqueda, un filtro o la quincena vuelve a tildar todas las filas.

Validaciones del masivo:
- Precio vacío, no numérico o no mayor que 0 → **"Ingresá un precio mayor que 0"**.
- Sin filas tildadas → el botón queda deshabilitado.

### ¿El cambio de precio impacta en Revisión?

**Sí, y es automático.** Cuando cargás, editás o aplicás precios en forma masiva, el sistema
**recalcula solo** las líneas afectadas de esa quincena. La pantalla de **Revisión** y sus
estadísticas **se actualizan reactivamente** — no hace falta recalcular a mano ni volver a
generar nada.

Si abriste Revisión en otra pestaña/momento y no ves el cambio reflejado, es cuestión de
refrescar esa vista; el cálculo del backend ya quedó actualizado.

### Copiar precios de una quincena a otra

- Botón **"Copiar de quincena anterior"**, a la derecha del título. Aparece en las solapas
  **Comunes**, **Por cliente**, **Por finca** y **Por supervisor**.
- Se abre una franja **"Copiar desde:"**: elegí la quincena de origen y tocá **"Copiar"**
  (mientras copia muestra **"Copiando..."**), o **"Cancelar"**. El destino es la quincena elegida
  en la barra.
- Copia todos los conceptos de la quincena de origen a la de destino. Los que ya existen en el
  destino **se omiten** (no se pisan).
- Si el destino ya tiene una preliquidación generada, además **recalcula** las líneas con el
  maestro actualizado.
- Si la copia trae solapamientos por cliente, avisa **"Atención: N solapamiento(s) por cliente
  heredado(s). Revisá la franja de aviso."**

### Ver qué precios faltan

- La solapa **Sin concepto** lista las combinaciones tarea/cliente/finca de la quincena que
  **no tienen un concepto completo** (un concepto necesita **código Y precio** para contar como
  completo; con código pero sin precio, no cuenta). Columnas: **TAREA · CLIENTE · FINCA**. Si no
  falta nada: *"Todas las tareas de esta quincena tienen concepto cargado."*
- Un click en la fila la abre para crear la regla ahí mismo: elegí el alcance (**Por finca**,
  **Por cliente**, **Por supervisor** o **Común**), completá código, unidad, precio, tipo y
  categoría, y tocá **"Guardar"**.
- Desde la pantalla de **Revisión**, cuando hay líneas incompletas, hay un botón **"Ir a
  Conceptos →"** que te trae directo a esta pantalla.

### Mensajes que podés ver (referencia rápida)

- **"Precio actualizado"** — guardaste un precio individual.
- **"Precio aplicado a N línea(s)"** — terminó el precio masivo.
- **"Regla guardada" / "Regla actualizada" / "Regla eliminada"** — altas, ediciones y bajas de
  reglas.
- **"Ingresá un precio mayor que 0"** — el precio quedó vacío, no es número o no es mayor que 0.
- **"Ingresá un código"** — quisiste agregar una regla sin código.
- **"No hay conceptos cargados para esta quincena."** / **"Ningún concepto coincide con los
  filtros aplicados."** — la tabla del panel está vacía por falta de datos o por los filtros.
- **"No hay conceptos … para esta quincena. Usá "+ Nuevo" para agregar."** — la solapa de reglas
  está vacía.

---

## Generar una quincena (preliquidación)

Es el punto de partida de todo el flujo. Se hace en la pantalla de inicio del módulo.

### Dónde está

- En el menú de la izquierda, tocá **Inicio**. Es la pantalla titulada **"Preliquidaciones"**,
  con el subtítulo *"Seleccioná una quincena para generar o continuar"*. Ocupa todo el ancho de
  la ventana.

### Generar / actualizar una quincena

1. En el panel **"NUEVA QUINCENA"**, abrí el selector y elegí la quincena. Las opciones son los
   **últimos 3 meses**, cada mes dividido en **"1ra quincena {mes año}"** y **"2da quincena {mes
   año}"**. El selector arranca en la **última quincena generada** (si está entre esas opciones).
   Mientras se carga el historial, el selector y el botón quedan deshabilitados.
2. Tocá el botón **"Generar / Actualizar"**. **No pide confirmación**: arranca en el momento.
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
TOTAL LÍNEAS · ALERTAS**. En el historial las quincenas se leen como **"1ra septiembre 2026"**.

En ALERTAS, cada quincena muestra **"N líneas con alerta"** (en amarillo) si tiene pendientes, o
**"OK"** (en verde) si no. Al lado va el **desglose por tipo** de alerta, por ejemplo **"3
incompletas"**, **"1 duplicada"**, **"2 posibles duplicados"**, **"1 legajo inválido"**, **"1 sin
empresa"** (solo los tipos que tienen casos).

El botón **"Detalle"** despliega debajo de la fila qué significa cada tipo (se cierra con
**"Ocultar detalle"**):
- **incompletas**: *"Sin concepto o sin precio: no pagan nada hasta cargar la regla en
  Conceptos."*
- **duplicadas**: *"Igual a otra línea en todo lo que trae del campo: es una carga repetida y se
  corrige en el campo."*
- **posibles duplicados**: *"Igual a otra línea salvo en las horas: puede ser una doble carga o dos
  trabajos reales."*
- **legajo inválido**: *"El legajo no se pudo confirmar en el padrón de sueldos de la empresa:
  revisar a quién se le paga."*
- **sin empresa**: *"Sin empresa asignada: no se sabe por qué empresa se liquida."*

Como una línea puede tener más de una alerta, los números del desglose pueden sumar más que el
total (el detalle lo aclara).

Para trabajar una quincena, hacé click en su fila o en el botón **"Abrir →"** — eso te lleva a la
pantalla de **Revisión**.

---

## Revisión de una quincena

Es la pantalla donde se trabaja línea por línea una quincena ya generada.

### Cómo se entra

**No hay un ítem de menú para Revisión.** Se entra desde **Inicio → HISTORIAL**, clickeando la
fila de la quincena (o su botón **"Abrir →"**). Una vez adentro, el **selector de quincena** de la
barra de filtros te deja pasar a otra quincena sin volver al Inicio; la búsqueda, los filtros y el
orden se conservan al cambiar de quincena, y el panel de la línea abierta se cierra.

### Qué muestra

Arriba (barra superior): **"← Volver"** (vuelve a Inicio), un contador **"N líneas"**, un contador
**"N alertas"** si las hay, y los botones **"Liquidación masiva"** y **"Exportar Excel"**.

La tabla lista todas las líneas de la quincena, con columnas: la de alerta (sin título),
**FECHA**, **EMPLEADO**, **LEGAJO**, **EMPRESA**, **TAREA**, **SUPERVISOR**, **CLIENTE · FINCA**
(una sola columna), **GRUPO PAGO**, **HS. JORN.**, **HS. MAQ.**, **TANC.**, **UNID.**,
**IMPORTE** y **CONCEPTOS**. Un valor en cero o vacío se muestra como **"—"**. Al pie, la fila
**TOTAL** suma las horas, tancadas, unidades e importe de las líneas que se ven (con los filtros
aplicados).

Un click en el encabezado de una columna **ordena** la tabla por esa columna; un segundo click
invierte el orden y un tercero vuelve al orden original.

**Barra de filtros** (arriba de la tabla):
- Selector de quincena.
- Búsqueda: **"Buscar empleado, legajo, tarea..."**.
- **Filtros**: multiselección en cascada por Cliente, Finca, Tarea, Grupo de pago y Supervisor.
  En Revisión **no hay filtro de Empresa**.
- **Alertas**: **Incompleta**, **Legajo inválido**, **Empresa a verificar**, **Duplicado** y
  **Posible duplicado** (para ver solo las líneas con ese problema; se marca una por vez y un
  segundo click la desmarca).
- **Limpiar** resetea todo.

Si ningún resultado coincide: *"Sin resultados para los filtros aplicados."*

**Banners de alerta** (arriba de todo, cuando corresponde):
- Si hay líneas incompletas: *"N líneas incompletas — cargá los conceptos y precios en el
  maestro"*, con un botón **"Ir a Conceptos →"** que te lleva directo a cargar precios.
- Si no hay incompletas pero hay otras alertas: *"N alertas sin resolver:"* con el desglose y un
  botón **"Ver solo alertas →"**, que deja a la vista solo las líneas con alguna alerta (en la
  fila "Filtrando por" aparece el chip **"Sólo líneas con alerta"**).

### Qué es una línea incompleta

Una línea queda **incompleta** cuando **no tiene ningún concepto aplicable con código y precio**
en el maestro — es decir, esa tarea/cliente/finca todavía no tiene un concepto cargado que la
cubra. Se marca con el badge **"INCOMPLETA"** (en la columna de alerta y en la de GRUPO PAGO).
**Se resuelve cargando el concepto en la pantalla de Conceptos** (el botón "Ir a Conceptos →" del
banner te lleva).

La columna de alerta muestra una sola marca por línea, la más grave: **DUPLICADO**, **POSIBLE
DUPLICADO**, **INCOMPLETA**, **LEGAJO** o **EMPRESA**.

### Abrir y editar una línea (panel lateral)

Al hacer click en una fila se abre un panel a la derecha con el detalle de esa línea (se cierra con
la cruz de arriba):

- Si la línea tiene alertas, arriba se listan: **"Línea duplicada"**, **"Posible duplicado: otra
  línea igual con distintas horas"**, **"Legajo no validado"**, **"Línea incompleta: falta código
  o precio"**.
- **DATOS DE CAMPO** (solo lectura): fecha, planilla, legajo de campo, horas jornal, horas
  máquina, tancadas, unidades, supervisor, tractor.
- **ASIGNACIÓN** (editable):
  - Si el sistema encuentra a la persona (por su CUIL) en las empresas, un desplegable
    **"Empresa / Legajo"** con las empresas donde tiene legajo (*EMPRESA — legajo*); al elegir la
    empresa, el legajo la acompaña. Si tiene una sola, lo aclara: *"Esta persona tiene una sola
    empresa/legajo."*
  - Si no (*"Sin CUIL: asignación manual."*): **Empresa** (botones) y **Legajo asignado** (campo
    de texto).
- **CONCEPTOS DE LIQUIDACIÓN**: la lista de conceptos que se pagan en esa línea (ver abajo).
- **Desglose** con el importe de cada concepto y el total.
- **Observación** (editable, opcional).
- Botón **"Guardar"** abajo: guarda la asignación y la observación. Al guardar aparece **"Línea
  actualizada"**.

> En este sistema no hay un botón separado de "ajuste manual": ajustar una línea a mano **es**
> editarla en este panel (empresa, legajo, conceptos, observación). Los conceptos se agregan y se
> quitan en el momento; la empresa, el legajo y la observación se guardan con **Guardar**.

### Agregar o quitar conceptos a una línea

Dentro del panel, en **CONCEPTOS DE LIQUIDACIÓN**:

1. Tocá **"+ Agregar concepto por código"**.
2. Elegí el concepto en el desplegable (**"— Seleccionar concepto —"**, se listan como *código —
   tipo*).
3. Tocá **"Agregar"** (queda deshabilitado hasta que elijas uno; **"Cancelar"** cierra sin
   agregar). Aparece **"Concepto agregado"**.
4. Para quitar un concepto, tocá la cruz al lado. Aparece **"Concepto eliminado"**.

Si el código tiene más de una opción en la quincena, el sistema pregunta **"Código N: elegí una
opción"** (cada opción con su precio y unidad). Si la línea ya tiene ese código, avisa **"El código
N ya está cargado"** y podés **"Agregar igual"** o **"Cancelar"**.

Los conceptos marcados **"(auto)"** son los que el sistema puso automáticamente por las reglas; los
demás los agregaste a mano. Si la línea no tiene ninguno: *"Sin conceptos de liquidación"*.

### Liquidación masiva (aplicar a varias líneas de una persona)

Con el botón **"Liquidación masiva"** de la barra superior (para volver, **"← Volver a
tabla"**):

1. Elegí un empleado (buscador **"Buscar por nombre o legajo..."**).
2. Se listan sus líneas con **casillas**. Tildá las que querés tocar (**"← Volver"** vuelve a la
   lista de empleados).
3. Con líneas seleccionadas podés:
   - **"+ Agregar concepto"**: elegí el concepto en **"— Seleccionar concepto —"** y tocá
     **"Aplicar"**. Si algunas líneas ya tienen ese código, el sistema pregunta si **saltear** las
     que ya lo tienen o **"Agregar igual a todas"**.
   - **Quitar** un concepto que ya tengan, con los botones **"Quitar cód. N (cantidad)"**.
   - **"Reasignar empresa"**: aparece un bloque por persona (CUIL) con **"— Elegir empresa —"**;
     confirmá con **"Confirmar reasignación"**. Aparece **"Empresa reasignada"**.
4. Al reasignar empresa: si alguna línea no tiene CUIL, avisa que esas **hay que editarlas a mano**
   (no se pueden reasignar en masa).

---

## Exportar a Excel

- Se exporta desde la pantalla de **Revisión** (no desde Verificación).
- En la barra superior, tocá **"Exportar Excel"** (mientras baja muestra **"Exportando…"**).
- Descarga **toda la quincena** en un archivo Excel (no solo lo filtrado en pantalla).
- Si falla, aparece **"No se pudo exportar el Excel"**.

---

## Verificación (controles antes de cerrar)

Es una pantalla de **control y auditoría**: sirve para detectar excesos y comparar formas de pago
**antes de cerrar** la quincena. Salvo dos datos (el valor hora tractorista y el valor hora de
pulverización), acá **no se cargan datos** — se mira.

Las **personas mensualizadas** (cobran un sueldo fijo, no por jornal) no entran en ningún control
de Verificación; en Revisión siguen apareciendo.

### Dónde está

- Menú **Verificación**. La pantalla se titula **"Verificación"**.
- La barra de filtros tiene el **selector de quincena** (arranca en la última quincena generada),
  la búsqueda **"Buscar empleado o legajo..."** y **Filtros** por Cliente, Finca, Tarea, Empresa,
  Grupo de pago y Supervisor. Al cambiar de quincena se limpian la búsqueda y los filtros.

### Los 7 controles

Se navegan con los botones de sección; cada uno dice debajo qué mide y, en los que cuentan casos,
muestra cuántos hay:

1. **Horas excedidas** (*> 13 hs/día*) — empleados con **más de 13 horas jornal** en un mismo día.
2. **Tancadas excedidas** (*> 35/día*) — más de **35 tancadas** en un día.
3. **Plantas excedidas** (*> 6.000/día*) — más de **6.000 plantas** en un día (cuenta las
   unidades de las líneas con grupo de pago PLANTA).
4. **Resumen por empleado** (*importe · días · $/día*) — importe, días trabajados y $ por día de
   cada empleado.
5. **Plantas vs Jornal** — compara el rendimiento pagado por planta contra el jornal.
6. **Tancadas vs Jornal** — compara el valor hora que salió la pulverización pagada por
   tancada contra el valor hora de pulverización + 30 %.
7. **Posibles duplicados** (*mismas unidades, distintas horas*) — grupos de líneas iguales salvo
   en las horas, en un mismo día.

### Tablas ordenables y detalle

Cada control es una **tabla**. Un click en el encabezado de una columna ordena por ella: en las
columnas de números, primero de **mayor a menor** (lo que se busca en un control es lo más alto);
en las de texto, de la A a la Z. Un segundo click invierte el orden y un tercero vuelve al orden
original. Cada control recuerda su propio orden.

En **Horas excedidas**, **Tancadas excedidas**, **Plantas excedidas**, **Resumen por empleado** y
**Posibles duplicados**, un click en una fila (o **Enter** con la fila marcada) abre el
**detalle** en una ventana: arriba, el nombre, el legajo y los datos clave del caso; abajo, las
líneas. La ventana se cierra con la cruz (**Cerrar**), con **Escape** o con un click afuera.

- **Excesos** (columnas **Empleado · Legajo · Fecha · Líneas** y la cantidad del control): el
  detalle muestra **"Horas jornal del día"**, **"Tancadas del día"**, **"Plantas del día"** y las
  líneas de ese día con tarea, cliente, finca y supervisor, más la fila **"Total del día"**. Si no
  hay casos: *"No hay excesos para este control."*
- **Resumen por empleado** (columnas **Empleado · Legajo · Empresa · Días · $ por día · Total
  quincena**): el detalle muestra **"Total de la quincena"**, **"Días trabajados"**, **"$ por
  día"** y cada línea con sus conceptos.
- **Posibles duplicados** (columnas **Empleado · Legajo · Fecha · Líneas · Importe en duda**): el
  **importe en duda** es lo que sobraría si solo una de las líneas del grupo fuera trabajo real
  (la suma del grupo menos la línea de mayor importe). El detalle muestra las líneas del grupo
  lado a lado. Si no hay: *"No hay posibles duplicados."*

**Plantas vs Jornal** y **Tancadas vs Jornal** se ordenan igual, pero no abren detalle. Toman
toda la quincena: la búsqueda y los filtros de la barra no cambian esas dos tablas (en Plantas vs
Jornal la búsqueda ni aparece).

### Valor hora tractorista (Plantas vs Jornal)

En la sección **"Plantas vs Jornal"** hay un campo editable: el **"Valor hora tractorista"** —
cuánto vale **una hora** del tractorista. Escribí el número y confirmá con **Enter** o el botón
**"Guardar"**. Sin el valor cargado se ve el aviso *"Cargá el valor hora del tractorista para ver
la comparación a jornal."*

La tabla tiene las columnas **Cliente · Finca · Tarea · Precio pagado · Un · Hs · Plantas/Hsm ·
Plantas/Hsm×8 · Prom Jornal · Jornadas · Jornal tractorista · %Dif**, y una fila **Total**. Con el
valor hora cargado, la tabla muestra el **Jornal tractorista** (el valor hora × 8, el mismo para
todas las filas) y el **%Dif**: cuánto más caro (+, resaltado) o más barato (−) cobra la jornada
pagada por planta (**Prom Jornal**) que ese jornal tractorista. Sin el valor cargado, esas
columnas quedan vacías. La columna **Jornadas** (horas de máquina ÷ 8) es informativa. El precio
por planta de cada fila (**Precio pagado**) es el **realmente pagado** en las líneas (si hubo
precios distintos, el promedio ponderado).

### Valor hora pulverización

En la sección **"Tancadas vs Jornal"** está el otro campo editable de Verificación: el
**"Valor hora pulverización"**. Escribí el **valor hora base** (el del tractorista), **sin
recargo**: el sistema le suma el 30 % solo. Confirmá con **Enter** o el botón **"Guardar"**.

La tabla tiene una fila por cliente, finca y tarea pagada por tancada, con estas columnas:
**Tancadas**, **Hs jornal**, **Hs máquina**, **Precio tancada** (el realmente pagado; si hubo
precios distintos, el promedio ponderado), **Importe pagado** (lo que se pagó por esas
tancadas), **Valor hs/máquina pulv** (importe pagado ÷ horas de máquina), **Valor hs pulv × 1,3**
(el valor hora cargado + 30 %) y **Variación**: cuánto más caro (+, resaltado) o más barato (−)
salió la hora de máquina pagada por tancada que esa referencia. Las tancadas se toman tal como
vienen, sin dividir por 2, y las horas de jornal se muestran como dato pero no entran en la
cuenta.

- Una fila **sin horas de máquina** se muestra igual, con la marca **"sin hs máquina"**, pero no
  tiene valor hora ni variación, y no entra en la variación del total (una nota al pie dice
  cuántas filas quedaron afuera).
- La fila **Total** suma tancadas, horas e importe de todas las filas; su valor hora y su
  variación se calculan con las sumas de las filas que tienen horas de máquina (no es un
  promedio de las variaciones).
- Sin el valor hora cargado (*"Cargá el valor hora para ver la comparación a jornal."*), las
  columnas **Valor hs pulv × 1,3** y **Variación** quedan vacías.

---

## Mantenimiento (categorías de operario)

Sirve para asignarle a cada operario de mantenimiento su **categoría** en una quincena.

### Dónde está

- Menú **Mantenimiento**. *(En el menú se llama "Mantenimiento"; la pantalla se titula
  "Categorías de operarios de mantenimiento".)*
- La barra de filtros tiene el **selector de quincena**, que arranca en la **última quincena
  generada**, y la búsqueda **"Buscar por nombre, CUIL o legajo..."**.

### Asignar una categoría

1. Elegí la quincena (si no es la que ya aparece).
2. (Opcional) Filtrá con **"Buscar por nombre, CUIL o legajo..."**.
3. En la fila del operario, abrí el desplegable de la columna **CATEGORÍA** y elegí de
   **Categoría 1** a **Categoría 12** (o **"— Sin categoría —"** para dejarlo sin asignar).
4. **Se guarda solo al elegir** (no hay botón por fila). Aparece **"Categoría actualizada"**.

La tabla tiene las columnas **EMPLEADO · LEGAJO · CUIL · CATEGORÍA**, y al lado del botón de
heredar se ve cuántos operarios hay (**"N operario(s)"**). Las filas de operarios **sin
categoría** quedan resaltadas, para que se vean de un vistazo. Si la quincena no tiene
operarios: *"No hay operarios de mantenimiento para esta quincena."*

### Heredar de la quincena anterior

- El botón **"Heredar de quincena anterior"** copia las categorías asignadas en la quincena
  previa (mientras trabaja muestra **"Heredando..."**). Al terminar avisa cuántas heredó (**"Se
  heredaron N categoría(s) de la quincena anterior"**).

---

## Vista gerencial (para el gerente)

Es un tablero de **solo lectura** con la **mano de obra gastada**: cuánto se pagó, cómo viene
evolucionando y dónde hay desvíos. Solo la ve el gerente.

### Dónde está

- En el Inicio del sistema, tarjeta **Gerencial**. La pantalla se titula **"Vista gerencial"** y
  ocupa todo el ancho. En su menú, la entrada **Preliquidación** es este tablero.

### Elegir el período y la empresa

En la barra de arriba:
- **Quincena** / **Mes**: elige si se mira una quincena o un mes completo (sus dos quincenas).
- El selector del período (arranca en la última quincena o el último mes con datos).
- **"Todas las empresas"** o una empresa puntual.

El subtítulo repite lo elegido (*"Mano de obra gastada · … · todas las empresas"*). La pantalla
recuerda el período, la empresa y el umbral mientras navegás (se borran con F5 o al cerrar
sesión).

### Qué muestra

- **MANO DE OBRA DEL PERÍODO**, con la variación contra el período anterior (por ejemplo
  *"+N % vs … del período anterior"*, con una flecha hacia arriba o hacia abajo), **PERSONAS** y **$ / HORA JORNAL**.
- **¿POR QUÉ VARIÓ?**: separa la variación en tres efectos que suman la variación total:
  **Dotación** (cantidad de personas), **Actividad** (horas de jornal por persona) y **Precio** ($
  pagado por hora de jornal).
- **EVOLUCIÓN POR QUINCENA**: un gráfico de columnas; pasando el mouse por una columna se ve su
  total y la cantidad de personas.
- **POR CLIENTE** y **POR GRUPO DE TAREAS**: barras con el total y el porcentaje. Un click en un
  grupo de tareas muestra sus tareas; **"← Volver a grupos"** vuelve.
- **DESVÍOS POR PERSONA**: cada persona contra su propia media de las últimas quincenas. Se
  muestran solo las que superan el **"Umbral de alerta"** (en %, editable; marcadas **"sobre
  umbral"**). El botón **"Ver las N personas sin desvío sobre el umbral"** muestra el resto, y
  **"N personas sin historial comparable"** lista a quienes no tienen historia suficiente.
- **DESVÍOS POR CLIENTE**: lo mismo por cliente, con el mismo umbral.
- **Control Plantas vs Jornal** y **Control Tancadas vs Jornal**: se despliegan con su botón y
  muestran las mismas tablas que Verificación, **solo para mirar** (las columnas se ordenan con un
  click en el encabezado). El valor hora lo carga el liquidador; si todavía no lo cargó, dice
  *"El liquidador todavía no cargó este valor para la quincena."* Estos controles son por
  quincena: en modo Mes avisan *"Elegí una quincena para ver este control (no aplica al mes
  completo)."*

Al pie, una nota recuerda que *"La quincena en curso sigue en revisión: sus importes pueden
cambiar hasta que el liquidador la cierre."* Si todavía no hay ninguna: *"Todavía no hay
preliquidaciones generadas."*

El gerente también puede operar **Conceptos** completo (precios, reglas, precio masivo, copiar
quincena), igual que el liquidador: ver "Carga de precios".

---

## Sueldos / Empleados

No hay una pantalla de **Empleados** ni de **Sueldos**. Hoy el sistema no permite editar sueldos
ni consultar legajos desde la aplicación; los datos de sueldos se toman automáticamente de la base
correspondiente al generar la quincena.
