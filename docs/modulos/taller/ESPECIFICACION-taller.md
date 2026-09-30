# Módulo Taller — especificación

**Qué es este documento**: el relevamiento de lo que hoy hacen las dos apps de AppSheet
con las que los mecánicos cargan sus horas, escrito para poder reemplazarlas por un
**módulo del Sistema de gestión La Asturiana**. Describe lo que existe, marca lo que
está mal y separa lo que todavía falta preguntar.

**Estado**: 2026-09-14. Las secciones 1 a 7 son el relevamiento de lo que existe hoy;
las 8 a 10, lo que se decidió y lo que se pidió; la 11, lo que todavía falta. Falta
escribir el glosario (`CONTEXT-taller.md`) y el plan por etapas (`plan-taller.md`):
este archivo es el insumo de los dos.

**De dónde sale cada cosa**: todo lo que está en las secciones 1 a 7 está tomado
literal de la documentación que genera AppSheet (`fuentes/`, fuera de git) y es
verificable ahí. Lo que es interpretación mía está marcado con *(inferido)*. Las
secciones 8 y 10 son de Pitu, del 2026-09-14.

**Cómo se llama**: el módulo se llama **Taller** (D1). No confundir con "horas de
taller", que en el módulo **Liquidación Terceros** significa otra cosa — *lo que se le
descuenta a un tercero por la mano de obra aplicada a su máquina* (ver
`../terceros/CONTEXT-terceros.md`). Taller es **la carga y aprobación del parte diario
del mecánico**, y es la fuente de la que sale aquello.

---

## 1. Qué reemplaza

Dos apps de AppSheet **casi idénticas**, las dos sobre el mismo Google Sheet:

| App | Versión | Para quién |
| Horas Taller - Mecánicos | V2.1 | El mecánico que carga sus propias horas |
| Horas Taller - Encargados | V2.2 | El encargado que carga por los mecánicos de su sitio y aprueba las tareas |

Las dos tienen **10 tablas, 85 columnas, 6 slices, 32 vistas, 7 format rules,
23 acciones y 0 automatizaciones**. Las diferencias reales entre ambas son cuatro y
están en la sección 7: **no son dos aplicaciones, es una con dos configuraciones**.
En el módulo nuevo son **un solo módulo con dos roles**.

Los datos viven en `BD_Horas.gsheet`, en el Drive de la empresa
(`/appsheet/data/HorasTaller-230377743/`). Ese mismo Sheet, publicado en la web, es
hoy la fuente de las horas de taller del Excel de fletes (ver
`fletes/ESPECIFICACION.md`, punto 4.2). **Cuando este módulo exista, esa cadena
—AppSheet → Sheet → publicación web → Power Query → Excel— desaparece.**

---

## 2. El circuito

```
  MECÁNICO / ENCARGADO                    JEFE
  ─────────────────────                   ────
  Cargar Tarea
    └─ crea un Encabezado (fecha + mecánico)
       └─ y dentro N líneas de trabajo  ──────►  Aprobar Tareas
          Estado = Pendiente                     (ve solo las Pendientes)
                                                   │
                                        ┌──────────┴──────────┐
                                        ▼                     ▼
                                     Aprobar               Rechazar
                                 Estado=Aprobado        pide Motivo
                                     (fin)              Estado=Rechazado
                                                              │
  Tareas Rechazadas  ◄────────────────────────────────────────┘
    └─ Reenviar tarea → Estado = Pendiente, se borra el motivo
```

En paralelo, el jefe tiene un tablero **Empleados sin Cargas** con dos listas: los
mecánicos que no cargaron **hoy** y los que no cargaron **ayer**.

Una carga tiene **dos niveles**: un `Encabezado` (una fecha y un mecánico) y debajo
las **líneas** de `BD_Horas`, una por cada trabajo hecho. El formulario de carga es
anidado: se abre el encabezado y se van agregando líneas adentro (hasta 5 visibles a
la vez, `MaxNestedRows: 5`).

---

## 3. Modelo de datos

Diez tablas. Una es interna de AppSheet (`_Per User Settings`, se descarta), dos son
transaccionales y siete son maestros.

### 3.1 `Encabezado` — la carga de un día

Una fila por (mecánico, fecha). Es el padre de las líneas.

| Columna | Tipo | Regla |
|---|---|---|
| `RegistroID` | Texto | **Clave**. `UNIQUEID()` |
| `usermail` | Email | Solo lectura. `USEREMAIL()` — quién cargó de verdad |
| `Fecha` | Fecha | Etiqueta. Valor inicial `TODAY()` |
| `Cuil` | Ref → `Maestro_Mecanicos.CUIL` | El mecánico **para el que** se carga |
| `Related BD_Horas` | Lista | Virtual. Las líneas hijas. Solo se muestra si hay `Cuil` |

La distinción entre `usermail` (quién carga) y `Cuil` (por quién se carga) es lo que
permite que un encargado cargue por otro. **Se conserva.**

### 3.2 `BD_Horas` — la línea, el hecho

Una fila por trabajo. Es la tabla que importa.

| Columna | Tipo | Cómo se llena | Regla |
|---|---|---|---|
| `LineaID` | Texto | `UNIQUEID()` | **Clave**, oculta |
| `RegistroID` | Ref → `Encabezado` | automático | `IsAPartOf` = la línea muere con su encabezado |
| `Fecha` | Fecha | hereda del encabezado | etiqueta |
| `Cuil` | Número | hereda del encabezado | oculta |
| `Mecánico` | Texto | `[RegistroID].[Cuil].[Apellido, Nombre]` | calculada |
| `Lugar` | Ref → `Maestro_Lugar` | elige | **Es el que manda todo el formulario** |
| `Sector` | Ref → `Maestro_sector` | elige | |
| `Supervisor` | Ref → `Maestro_Supervisores` | elige | solo si el Lugar contiene `CAMPO` |
| `Finca` | Texto | de `Maestro_Fincas[Fincas]` | solo si `CAMPO` **y** hay Supervisor |
| `Rubro` | Ref → `Maestro_Rubros` | elige | solo si `TALLER`, o si `CAMPO` **y** hay Finca |
| `Sub Rubro` | Texto | los sub-rubros de ese Rubro | `SELECT(Maestro_Rubros[Sub Rubro], [Rubro]=…)` |
| `Tipo` | Texto | de `Maestro_Maquinas[tipo]` | solo si hay Sub Rubro |
| `Máquina` | Texto | las máquinas de ese Tipo | solo si hay Tipo |
| `id_maquina` | Texto | `LOOKUP(Máquina → Maestro_Maquinas)` | calculada **a partir del nombre** ⚠ |
| `Horas` | Decimal | escribe | solo si hay Máquina. **Entre 0,5 y 24** |
| `Horas_Preparacion` | Decimal | escribe | solo si `CAMPO` y hay Máquina. Máx 24 |
| `Horas_Traslado` | Decimal | escribe | solo si `CAMPO` y hay Máquina. Entre 0,5 y 24 |
| `Motivo_Rotura` | Enum | `Negligencia` / `Rotura por Desgaste` | solo si hay Máquina |
| `Tipo_Reparacion` | Enum | `Rotura` / `Mantenimiento Campaña` | solo si hay Máquina **y** `TALLER` |
| `Conductor` | Ref → `Maestro_Mecanicos` | elige | solo si `CAMPO`, y solo entre los de Sector `TRACTORISTA` |
| `Descripción` | Texto | escribe | libre |
| `Estado` | Enum | automático | `Aprobado` / `Pendiente` / `Rechazado`. Nace **Pendiente** |
| `Motivo Rechazo` | Texto largo | lo escribe el jefe | editable **solo** dentro del formulario de rechazo |
| `Email_Usuario` | Email | `USEREMAIL()` | solo lectura. Es la base de los permisos |

### 3.3 Los maestros

| Tabla | Clave | Editable desde la app | Contenido |
|---|---|---|---|
| `Maestro_Mecanicos` | `CUIL` | No | Legajo, Apellido y nombre, `Mecanico` (SI/NO), Sector, Sitio, Email |
| `Maestro_Maquinas` | `id_maquina` | No | nombre, Tipo, `propiedad` (PROPIA/TERCEROS), marca, modelo, actividad |
| `Maestro_Rubros` | `Rubro` | No | Rubro, Sub Rubro, Tiempo Aproximado |
| `Maestro_sector` | `Sector` | No | |
| `Maestro_Lugar` | `Lugar` | No | Los `TALLER X` y `CAMPO X` |
| `Maestro_Supervisores` | `Apellido_Nombre` | No | Tipo_Pago (JORNAL/MENSUAL), CUIT |
| `Maestro_Fincas` | `Fincas` | **Sí** | Es el único maestro que se puede tocar desde la app ⚠ |

`Maestro_Mecanicos` tiene además dos columnas calculadas que existen solo para el
tablero de control:

```
Tiene_Carga_Hoy  = COUNT(SELECT(BD_Horas[LineaID], [Cuil]=CUIL y [Fecha]=TODAY()))   > 0
Tiene_Carga_Ayer = COUNT(SELECT(BD_Horas[LineaID], [Cuil]=CUIL y [Fecha]=TODAY()-1)) > 0
```

---

## 4. Las reglas del formulario

Esto es lo que hay que reproducir sin cambiar una coma: es el único lugar donde está
escrito cómo se carga bien una hora de taller. El formulario es **en cascada** y
**`Lugar` es la raíz**: todo lo demás aparece o no según diga `TALLER` o `CAMPO`.

**Si el Lugar contiene TALLER:**

```
Lugar → Rubro → Sub Rubro → Tipo → Máquina → Horas
                                      └──────→ Motivo_Rotura
                                      └──────→ Tipo_Reparacion
```

**Si el Lugar contiene CAMPO:**

```
Lugar → Supervisor → Finca → Rubro → Sub Rubro → Tipo → Máquina → Horas
  └──→ Conductor (solo tractoristas)                       └────→ Horas_Preparacion
                                                           └────→ Horas_Traslado
                                                           └────→ Motivo_Rotura
```

Los campos no aparecen vacíos y grises: **directamente no se muestran** hasta que el
campo del que dependen esté lleno. Esa es la razón por la que el formulario se puede
completar en un celular sin equivocarse, y hay que conservarla.

### Validaciones

| Campo | Límite |
|---|---|
| `Horas` | mínimo 0,5 — máximo 24 |
| `Horas_Traslado` | mínimo 0,5 — máximo 24 |
| `Horas_Preparacion` | máximo 24 (el mínimo de 0,5 está solo en la app de Encargados) |
| `Sub Rubro` | tiene que pertenecer al `Rubro` elegido |
| `Máquina` | tiene que pertenecer al `Tipo` elegido |
| `Conductor` | solo mecánicos cuyo Sector contenga `TRACTORISTA` |

**No hay validación de que el total de horas del día cierre en algo.** Un mecánico
puede cargar seis líneas de 24 horas. El módulo sí lo controla, pero contra el reloj y
al día siguiente (D7 y R1), así que sigue abierto si además hace falta un tope en el
propio formulario.

---

## 5. Los estados

| De | Acción | A | Quién | Qué más pasa |
|---|---|---|---|---|
| — | crear | `Pendiente` | mecánico / encargado | |
| `Pendiente` | **Aprobar** | `Aprobado` | jefe | Se puede en lote. Pide confirmación |
| `Pendiente` | **Rechazar** | `Rechazado` | jefe | Abre un formulario y **exige** el motivo. De a una |
| `Rechazado` | **Reenviar** | `Pendiente` | el que cargó | Borra el motivo. Se puede en lote |

`Aprobado` es terminal: no hay acción que lo saque de ahí, y hoy una hora aprobada por
error no tiene vuelta atrás. En el módulo sigue siendo terminal para todos **menos para
el Admin**, que es el único que puede tocarla (D3).

El rechazo está armado como una acción compuesta de dos pasos —abrir el formulario
`Rechazar_Tarea` y, al guardarlo, poner el estado en `Rechazado`—. El efecto es que
**no se puede rechazar sin escribir el motivo**, y eso hay que mantenerlo.

Ayudas visuales que hoy existen y conviene conservar: el botón de aprobar en verde,
el de rechazar en rojo, la fecha en rojo cuando la línea está rechazada, y el motivo
de rechazo en rojo y en mayúsculas en la pantalla del mecánico.

---

## 6. Quién ve qué

Hoy los permisos están **escritos a mano dentro de las fórmulas, con los emails de
las personas**. El slice `Mis_Tareas` dice, literal:

| Email | Qué ve |
|---|---|
| `administracion@ejemplo.com` | Todo |
| `encargado.lafalda@ejemplo.com` | Lugar = TALLER LA FALDA o CAMPO LA FALDA |
| `encargado.montegrande@ejemplo.com` | TALLER / CAMPO MONTE GRANDE |
| `encargado1.caspinchango@ejemplo.com` | TALLER / CAMPO CASPINCHANGO |
| `encargado2.caspinchango@ejemplo.com` | TALLER / CAMPO CASPINCHANGO |
| cualquier otro | Solo sus propias líneas (`Email_Usuario = USEREMAIL()`) |

Y además hay **dos pantallas enteras** que se muestran solo si el email es
`Encargado.lafalda@ejemplo.com`: *Aprobar Tareas* y *Empleados sin Cargas*.

Esto es lo primero que hay que tirar. En el módulo nuevo es lo que el Sistema ya
sabe hacer: **un rol y un alcance (el Lugar o el Sitio) asignados a la persona desde
la pantalla de Administración**, y la identidad por **CUIL**, no por cuenta de Gmail.
La sección 8 lo detalla.

---

## 7. En qué se diferencian las dos apps

Cuatro cosas, y ninguna justifica que sean dos aplicaciones:

| | Mecánicos V2.1 | Encargados V2.2 |
|---|---|---|
| Slice `Cargas_dia_ayer` | **sin filtro de fecha** | solo hoy y ayer |
| Mínimo de `Horas_Preparacion` | sin mínimo | 0,5 |
| Pantalla *Tareas Rechazadas* | oculta para el jefe | visible para todos |
| Color del botón Aprobar | color del tema | verde |

Todo lo demás —tablas, columnas, reglas, estados, acciones— es idéntico.

---

## 8. Decisiones tomadas

Respondidas por Pitu el 2026-09-14 sobre el borrador de este documento.

| # | Decisión | Consecuencia |
|---|---|---|
| D1 | **El módulo se llama Taller.** | Queda resuelto el choque con "horas de taller" de Terceros, que es otra cosa. |
| D2 | **No hace falta que funcione sin señal.** | Se cae todo el trabajo de PWA offline: base local, cola de sincronización, resolución de conflictos, login sin red. El módulo es una pantalla web más del Sistema, con el mismo login y el mismo deploy. **Es la decisión que más achica el módulo.** |
| D3 | **Una tarea aprobada no se toca.** Solo el Admin puede. | El estado `Aprobado` es terminal para todos menos para el rol Admin del Sistema. |
| D4 | **Se puede borrar o anular, pero solo mientras no esté aprobada.** | Una vez aprobada, ni el que la cargó ni el jefe la borran. |
| D5 | **El rechazo no manda avisos por fuera de la app**: el mecánico lo ve al entrar. | No hay mails ni notificaciones. Sí hay alerta dentro de la app (ver R4). |
| D6 | **Los maestros salen de La Falda**, no se mantienen a mano. | Hay que mapear cada maestro contra su tabla de origen (pendiente, ver sección 11). |
| D7 | **Las horas del día se cotejan contra el reloj**, que se carga en Chinagro y llega con un día de atraso. | Entra una fuente nueva de solo lectura: `adcp_laasturiana_prod`. El cotejo es sobre días ya cerrados, no sobre el día que se está cargando (ver R1). |
| D8 | **Terceros toma de acá solo las horas cargadas.** El cruce con el maestro de precios y la emisión del recibo son del módulo Terceros. | **Taller no sabe nada de plata.** No tiene precios, ni saldos, ni recibos. Eso lo mantiene chico y es la frontera entre los dos módulos. |
| D9 | **Solo se aprueba en La Falda.** Las cargas de `TALLER LA FALDA` y `CAMPO LA FALDA` pasan por aprobación; las de Monte Grande y Caspinchango **no se aprueban**. | El circuito de aprobación **no aplica a todos los Lugares**. Hay que definir qué pasa con las horas de los sitios que no aprueban (ver sección 11). |
| D10 | **El borrado deja rastro**: se ve quién borró y cuándo. | La línea no desaparece — queda anulada y visible para quien tenga que auditarla. |

---

## 9. Lo que el módulo tiene que resolver y AppSheet no

Esto es lo que hay que arreglar aunque nadie lo haya pedido: son defectos de la
solución actual, no funcionalidad nueva.

| Problema de hoy | Qué hace el módulo |
|---|---|
| **Permisos con emails hardcodeados** en fórmulas y en la visibilidad de las pantallas. Entra alguien nuevo y hay que editar la app. | Rol por módulo + alcance por Lugar/Sitio, asignados desde Administración. Identidad por **CUIL**, como el resto del Sistema. |
| **Dos apps que hay que mantener sincronizadas** y que ya divergieron en cuatro puntos. | Un módulo, dos roles. |
| **Las líneas guardan el nombre de la máquina** y derivan el id con un `LOOKUP`. Renombrar una máquina rompe el histórico. La especificación de fletes ya dice que el cruce va **por id, nunca por nombre**. | La línea guarda `id_maquina`. El nombre se muestra, no se guarda. |
| **Los datos salen por un Sheet publicado en la web** para que Power Query los lea. | Las horas viven en la base del Sistema; los módulos que las necesiten las leen de ahí (D8). |
| **Cualquiera puede borrar sus líneas**, incluso ya aprobadas, sin dejar rastro. | Resuelto por D3, D4 y D10: solo se borra lo no aprobado, y queda quién lo borró y cuándo. |
| **`Maestro_Fincas` debiera venir de chinagro, es donde nacen los nombres de las fincas por las tareas que se cargan en ese sistema.
| **Una hora aprobada por error no tiene vuelta atrás.** | Resuelto por D3: el Admin puede. |

---

## 10. Lo que se pidió que tenga

Ocho pedidos de Pitu, del 2026-09-14. Están **en sus palabras** y ordenados como los
escribió; abajo de cada uno, qué implica y qué falta definir antes de construirlo.

**La "R" es de requisito**, y el número es el orden de la lista original: R1 es el
punto **a**, R2 el **b**, y así hasta R8 que es el **h**. Sirve para poder nombrarlos
en el plan sin repetir el párrafo entero.

### R1 — Comparar contra el reloj

> Los usuarios que cargan puedan ver la cantidad de horas declaradas en Chinagro vs lo
> que ellos le cargaron a esa persona para ese día.

Entra una fuente nueva de solo lectura: el fichaje del reloj, que se carga en Chinagro
(`adcp_laasturiana_prod`, la misma base de la que salen los viajes de fletes).

**El cotejo es sobre el día anterior**, confirmado el 2026-09-14: el dato del reloj
llega al día siguiente (D7), así que la pantalla compara días ya cerrados. No es una
validación del formulario, es un control de ayer para atrás.

*Falta definir*: qué tabla y qué campo de Chinagro tienen el fichaje; cuánta diferencia
se considera aceptable; si es solo informativo o si dispara algo. EL SQL PARA EXTRAER LOS DATOS LO COMPARTO,
DEBIERA SER IGUAL LA CANTIDAD DE HORAS DE CHINAGRO VS APP, NO DISPARA NADA DESDE LA APP ES PARA QUE EL 
RESPONSABLE CORRESPONDIENTE TOME ACCION SOBRE ESO.

### R2 — Pantalla de lo cargado, con filtros

> Que los usuarios puedan ver en una pantalla lo que le van cargando a cada mecánico y
> tengan filtros: de fecha, mecánico, lugar, etc.

Hoy existe algo parecido (*Tareas Registradas*) pero está agrupado por mecánico y
**sin ningún filtro**: se ve todo o nada.

*Falta definir*: la lista final de filtros. Y que cada usuario vea solo lo que le
corresponde por su alcance, que es lo que resuelve el rol (sección 9).

### R3 — No modificar lo aprobado

> Que los usuarios no puedan modificar una tarea ya aprobada.

Ya resuelto por **D3**. No hace falta nada más.

### R4 — Alerta de rechazadas, y bloqueo a los dos días

> Que los usuarios si tienen una tarea rechazada tengan alguna alerta o ícono
> indicándoles, y no los deje cargar una tarea nueva si luego de 2 días no solucionaron
> todas sus tareas rechazadas.

Son dos cosas distintas. La alerta es simple: un contador visible de tareas rechazadas
sin resolver. El bloqueo es la regla más fuerte de todo el módulo, y quedó definida así
(2026-09-14):

- **El bloqueo es por mecánico, no por usuario.** Lo que se traba es cargarle a *ese*
  mecánico que tiene algo rechazado. Un encargado que carga por diez sigue pudiendo
  cargarle a los otros nueve. Es lo que hace que la regla sea usable.
- **Se libera con el reenvío**, no con la aprobación. En cuanto el mecánico corrige y
  reenvía, se habilita. No queda a merced de que el jefe la vuelva a mirar.

Dicho de otra forma: el bloqueo cuenta las tareas **rechazadas y no reenviadas** de ese
mecánico con más de dos días de antigüedad. Reenviar las saca de esa cuenta aunque
después el jefe las vuelva a rechazar — y ahí el reloj arranca de nuevo.

*Falta definir*: si los dos días son corridos o hábiles. Salvo que digas otra cosa,
van **corridos** desde el rechazo, que es lo más simple de entender para el que la
sufre. CORRIDOS

### R5 — Filtros en la pantalla de aprobación

> Que la vista de aprobaciones para encargados se pueda filtrar por fecha, usuario,
> lugar, etc.

Hoy la pantalla *Aprobar Tareas* muestra todas las pendientes agrupadas por mecánico,
sin filtros. Mismo pedido que R2, del otro lado del circuito.

### R6 — Hace cuánto que no carga

> Alerta de hace cuánto tiempo no tiene nada cargado cada mecánico.

Hoy esto existe pero es binario y de dos días: *sin carga hoy* y *sin carga ayer*. Se
convierte en **días desde la última carga**, que además sirve para ordenar la lista por
el que peor está.

*Falta definir*: a partir de cuántos días alerta, y si entran todos o solo los marcados
como mecánico en el maestro. SI TIENE MAS DE 2 DIAS SIN CARGA ENTRA EN LA ALERTA. ENTRAN LOS QUE SON MECANICOS NADA MAS.

### R7 — Exportar a Excel

> Se pueda exportar a Excel la información.

El Sistema ya exporta a Excel en el módulo de Preliquidación (`openpyxl`), así que hay
de dónde copiar.

*Falta definir*: qué pantallas llevan botón de exportar.

### R8 — Estado de cuenta de horas por empleado

> Un estado de "cuenta" de horas de cada empleado, para que puedan enviárselo al
> empleado.

**Es informativo: el empleado no firma nada** (2026-09-14). Es un resumen de sus horas
para que pueda verlas, no un documento formal. Eso lo simplifica mucho: no hace falta
congelarlo, ni versionarlo, ni dejar constancia de que se entregó.

*Falta definir*: de qué período (¿la quincena, el mes, un rango que se elige?), si
muestra el detalle línea por línea o solo los totales por rubro o por máquina, y si
alcanza con el Excel de R7 o hace falta algo más presentable. EL PERIODO ELEGIDO, DETALLE LINEA POR LINEA DE QUE ES LO QUE 
CARGO. QUE SEA APERTURADO, ES DECIR PRIMERO VER A NIVEL FECHAS CUANTO TIENE CARGADO Y UNA COLUMNA VS CHINAGRO Y QUE DESUES PUEDA 
IR ABRIENDO CADA DIA Y VER QUE CARGO.

---

## 11. Lo que falta

### Hay que relevarlo

- **La sección Security de las dos apps de AppSheet.** La documentación generada no la
  incluye: no sabemos si hay *security filters* a nivel tabla ni la lista real de
  usuarios con acceso. Hacen falta capturas de `Security → Require Sign-In` y
  `Security → Options`.
- **El mapeo de los maestros contra La Falda** (D6): qué tabla y qué campos alimentan
  máquinas, mecánicos, rubros, sectores, lugares, supervisores y fincas. Lo puedo ir a
  buscar a la base y traerlo para que lo corrijas.
- **Dónde está el fichaje del reloj en Chinagro** (D7, R1).
- **El contenido actual de los maestros**: cuántas fincas, cuántos lugares, qué sectores.
- **El volumen**: cuántas líneas por día y cuántos mecánicos cargan.

### Decisiones que faltan

1. **Qué pasa con las horas de los sitios que no aprueban.** D9 dice que solo se aprueba
   en La Falda. Entonces las horas de Monte Grande y Caspinchango, ¿quedan `Pendiente`
   para siempre, o nacen válidas sin pasar por el circuito? No es un detalle: 

   - **Terceros toma las horas aprobadas** (D8). Si las de esos dos sitios nunca se
     aprueban, nunca llegan al recibo del tercero — o Terceros tiene que tomar también
     las pendientes, y entonces "aprobado" deja de significar lo mismo en todos lados.
   - **El bloqueo de R4 se apoya en el rechazo.** Donde no hay aprobación no hay rechazo,
     así que en esos dos sitios la regla de los dos días no existe.
   - La pantalla de "sin carga" (R6) y el cotejo con el reloj (R1) sí siguen aplicando a
     todos, porque no dependen del estado.

   Lo más limpio sería que el estado no dependa del sitio sino de si ese Lugar tiene
   aprobador asignado: donde no lo hay, la línea queda **aprobada automáticamente** al
   guardarse, y se distingue de las otras por quién la aprobó. Pero es una decisión de
   negocio, no técnica. SI, SI EL LUGAR ES LA FALDA O CAMPO LA FALDA DEBEN APROBARSE; DE LO CONTRARIO
SALEN COMO APROBADAS.

2. **El tope de horas del día**: el reloj (R1) compara contra días cerrados, así que no
   sirve para frenar una carga en el momento. Pitu lo va a ver con el jefe de taller
   (2026-09-14). Hasta que haya un número, el formulario no corta nada.

Resueltas el 2026-09-14: el bloqueo de R4 (por mecánico, se libera al reenviar), el
carácter del resumen de R8 (informativo, no se firma), el rastro del borrado (D10) y
quién aprueba (D9). De R4 queda un detalle menor —días corridos o hábiles— y de R8, el
período y el nivel de detalle.

### Tres detalles sospechosos de la app actual

Ninguno es urgente, pero conviene mirarlos antes de copiar la lógica tal cual:

- La condición de visibilidad de `Tipo` dice `ISNOTBLANK([SubRubro])`, **sin espacio**,
  pero la columna se llama `Sub Rubro`. O AppSheet lo tolera, o esa condición nunca
  se evalúa como se pretendía.
- La clave de `Maestro_Supervisores` es `Apellido_Nombre` pero su valor inicial es
  `UNIQUEID()`. Si alguien da de alta un supervisor desde la app, queda con un código
  aleatorio por nombre.
- Los permisos comparan `USEREMAIL()` contra `"Encargado.lafalda@ejemplo.com"` en las
  pantallas y contra `"encargado.lafalda@ejemplo.com"` en el slice — misma persona, distinta
  mayúscula.

---

## Anexo 1 — de dónde sale cada dato

Todo lo de las secciones 3 a 7 está en la documentación que genera AppSheet, en
`fuentes/` (fuera de git; ver `fuentes/LEEME.md` para volver a generarla).

| Sección de este documento | Sección del PDF |
|---|---|
| 3. Modelo de datos | `Data → Tables` y `Data → Columns` |
| 4. Reglas del formulario | Los `Show_If` y `Valid_If` de cada columna |
| 5. Los estados | `Behavior → Actions` (Aprobar, Rechazar, Reenviar_Tarea) y `UX → Format Rules` |
| 6. Quién ve qué | `Data → Slices` (`Mis_Tareas`, `Rechazadas`, `Revisión_Jefe`) y el `Show if` de cada vista |
| 7. Diferencias | Comparación de los dos PDF |


## Anexo 2 - De donde debieran salir los datos
Maestro Maquinaria: debiera salir del sistema la falda directamente, no de una hoja de Google Sheet.
Maestro Rubro y Subrubro: debiera salir del sistema la falda directamente, no de una hoja de Google Sheet.
Maestro Personal: debiera salir del sistema la falda directamente, no de una hoja de Google Sheet. Aquí hay una vista para eso.
Maestro Fincas: debiera salir de Chinagro que es la aplicación donde se cargan las tareas de campo.
Maestro Lugar: debiera salir del sistema la falda directamente, no de una hoja de Google Sheet.





