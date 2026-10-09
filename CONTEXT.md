# Sistema de gestión La Asturiana — núcleo

Lenguaje ubicuo del **Sistema**: lo que comparten todos los Módulos. Este archivo es un
glosario: define qué ES cada término, no cómo se implementa. Los términos de cada módulo
están en su propio glosario; el índice es [`CONTEXT-MAP.md`](CONTEXT-MAP.md).

## Sistema y módulos

**Sistema**:
El conjunto que comparten todos los Módulos: usuarios, roles y permisos, acceso a las bases externas, la Quincena, el menú y el login. El nombre visible es "Sistema de gestión La Asturiana"; los nombres internos (repos, base, servicio) siguen diciendo "preliquidacion" y no se renombran (ADR-0013).
_Avoid_: llamar "Preliquidación" al sistema completo; ese es el nombre de un módulo.

**Módulo**:
Unidad funcional autocontenida del Sistema que resuelve un circuito de negocio (Preliquidación de sueldos, Liquidación Terceros). Tiene sus propios datos, pantallas, reglas, tests y panel gerencial, y solo se apoya en el Núcleo compartido. Dos módulos nunca escriben los datos del otro; leerse entre sí solo pasa a través del Núcleo.
_Avoid_: "sección", "pantalla" (una pantalla es parte de un módulo, no un módulo)

**Núcleo compartido**:
Lo que el Sistema ofrece a todos los Módulos: autenticación, roles y permisos, conexión de solo lectura al sistema de campo y al maestro de sueldos, lectura de Cliente, Finca, Persona/Legajo y Empresa, la Quincena, y los componentes visuales comunes (layout, menú, avisos, overlays). Es de lectura para los módulos: ningún módulo escribe datos del Núcleo salvo a través de sus servicios. Crece solo cuando dos módulos necesitan lo mismo; lo que usa un solo módulo vive en ese módulo.
_Avoid_: "utils", "común" (ambiguo con Concepto común)

**Módulo activo**:
Un módulo registrado puede estar inactivo: su código existe, pero el Sistema no monta sus pantallas ni su API ni muestra su Tarjeta en el Inicio. Liquidación Terceros nace inactivo y se activa cuando tenga su primera pantalla real.

## Pantallas del Sistema

**Inicio**:
La pantalla a la que llega toda persona al entrar al Sistema: la saluda por su nombre, y le ofrece una Tarjeta por cada Módulo al que tiene acceso, más una tarjeta de Gerencial si puede ver la Vista gerencial de algún módulo, y una de Administración si es admin. Se pasa siempre por Inicio, aunque la persona tenga acceso a un solo módulo. Es también el único lugar donde viven las dos acciones de cuenta —cambiar la propia contraseña y cerrar sesión—, al pie de las tarjetas: dentro de un Módulo solo se puede cerrar sesión, y el cambio de contraseña se ofrece además en la Administración.
_Avoid_: confundir con el "Inicio" del módulo Preliquidación (el Dashboard de quincenas, otra pantalla).

**Tarjeta**:
La entrada a un Módulo (o a Gerencial, o a la Administración) desde el Inicio: ícono, nombre y una línea de descripción. Solo se muestra si el módulo está activo y la persona tiene permiso en alguna de sus pantallas (el admin las ve todas). No muestra los roles de la persona.

**Administración**:
La pantalla del Sistema, visible solo para el Admin, donde se da de alta a una persona buscándola en el Padrón de empleados, se le asignan sus roles y la marca de admin, se gestionan los usuarios existentes (activar/desactivar, cambiar roles, reiniciar contraseña) y se arman los Roles con sus Permisos. El identificador de la persona es su CUIL: el alta le genera un email sintético derivado del CUIL, y la contraseña inicial es el CUIL, que cada persona puede cambiar cuando quiera desde su propia sesión. Los usuarios no se borran: se desactivan.
_Avoid_: ABM de usuarios (nombre técnico, no el término de dominio); confundir con los scripts de consola, que quedan como alternativa y como salida de emergencia si el Admin pierde su propio acceso.

**Padrón de empleados**:
El listado de empleados del maestro de sueldos (solo lectura) de donde sale el alta de una persona en la Administración: apellido y nombre, CUIL, y sus legajos por Empresa. El Sistema nunca escribe en él.

## Roles y permisos

**Pantalla**:
Parte de un Módulo con nombre propio en su menú (Revisión, Conceptos, Tarifario…). Es la unidad sobre la que se dan los Permisos. Cada glosario de módulo lista sus pantallas y qué es ver y qué es editar en cada una. Las pantallas del Sistema no llevan Permisos: el Inicio lo ve toda persona, y la Administración solo el Admin.
_Avoid_: "submódulo", "sección"; confundir con el Módulo entero.

**Permiso**:
Ver o Editar una Pantalla. Editar incluye ver. Una pantalla sin acción propia solo tiene Ver. Quien no tiene permiso en ninguna pantalla de un Módulo no ve ese Módulo, y quien no tiene permiso en una pantalla no la ve. Cada dato que el Sistema entrega pide Ver en alguna pantalla que lo usa, y la restricción se aplica en el backend, no solo en pantalla.
_Avoid_: "capacidad" (nombre provisorio del diseño de Facturación); "acceso al módulo" como permiso aparte.

**Rol**:
Un conjunto de Permisos con un nombre, que el Admin arma y cambia desde la Administración sin programar. Puede reunir pantallas de varios Módulos. Una persona tiene uno o más roles y sus permisos se suman. Cambiar un rol cambia enseguida lo que pueden todas las personas que lo tienen, y un rol que alguien tiene no se puede borrar. A la persona el Sistema no le muestra qué roles tiene: solo ve sus pantallas.
_Avoid_: "rol de módulo", "perfil"; Operador y Gerente como roles fijos (esquema anterior, ADR-0020); "etiqueta de rol".

**Admin**:
Marca global de una persona, aparte de los Roles: ve y edita todo, y es la única que administra usuarios y roles desde la Administración. No se arma con Permisos. El Sistema nunca queda sin un admin activo.
_Avoid_: tratarlo como un Rol más.

## Términos que usan todos los módulos

**Quincena**:
Período de liquidación: del 1 al 15, o del 16 al fin de mes. Se identifica por su fecha de inicio, que siempre es un día 1 o un día 16.

**Persona**:
Un trabajador, identificado por su **CUIL**. Una persona puede tener **varios legajos**, uno por cada empresa en la que está dada de alta.
_Avoid_: empleado (úsese para el nombre display), legajo (una persona no ES un legajo)

**Legajo**:
Identificador de una persona **dentro de una empresa** en el sistema de sueldos. El par (empresa, legajo) es único; el CUIL agrupa todos los legajos de la misma persona.

**Empresa**:
Entidad que paga (LA ASTURIANA, PAMPLONA, …). Una persona tiene un legajo por cada empresa en la que está dada de alta.
