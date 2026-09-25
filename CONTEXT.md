# Sistema de gestión La Asturiana — núcleo

Lenguaje ubicuo del **Sistema**: lo que comparten todos los Módulos. Este archivo es un
glosario: define qué ES cada término, no cómo se implementa. Los términos de cada módulo
están en su propio glosario; el índice es [`CONTEXT-MAP.md`](CONTEXT-MAP.md).

## Sistema y módulos

**Sistema**:
El conjunto que comparten todos los Módulos: usuarios, roles, acceso a las bases externas, la Quincena, el menú y el login. El nombre visible es "Sistema de gestión La Asturiana"; los nombres internos (repos, base, servicio) siguen diciendo "preliquidacion" y no se renombran (ADR-0013).
_Avoid_: llamar "Preliquidación" al sistema completo; ese es el nombre de un módulo.

**Módulo**:
Unidad funcional autocontenida del Sistema que resuelve un circuito de negocio (Preliquidación de sueldos, Liquidación Terceros). Tiene sus propios datos, pantallas, reglas, tests y panel gerencial, y solo se apoya en el Núcleo compartido. Dos módulos nunca escriben los datos del otro; leerse entre sí solo pasa a través del Núcleo.
_Avoid_: "sección", "pantalla" (una pantalla es parte de un módulo, no un módulo)

**Núcleo compartido**:
Lo que el Sistema ofrece a todos los Módulos: autenticación y roles, conexión de solo lectura al sistema de campo y al maestro de sueldos, lectura de Cliente, Finca, Persona/Legajo y Empresa, la Quincena, y los componentes visuales comunes (layout, menú, avisos, overlays). Es de lectura para los módulos: ningún módulo escribe datos del Núcleo salvo a través de sus servicios. Crece solo cuando dos módulos necesitan lo mismo; lo que usa un solo módulo vive en ese módulo.
_Avoid_: "utils", "común" (ambiguo con Concepto común)

**Módulo activo**:
Un módulo registrado puede estar inactivo: su código existe, pero el Sistema no monta sus pantallas ni su API ni muestra su Tarjeta en el Inicio. Liquidación Terceros nace inactivo y se activa cuando tenga su primera pantalla real.

## Pantallas del Sistema

**Inicio**:
La pantalla a la que llega toda persona al entrar al Sistema: la saluda por su nombre, y le ofrece una Tarjeta por cada Módulo al que tiene acceso, más una tarjeta de Gerencial si es gerente o admin en algún módulo con panel gerencial, y una de Administración si es admin. Se pasa siempre por Inicio, aunque la persona tenga acceso a un solo módulo. Es también el único lugar donde viven las dos acciones de cuenta —cambiar la propia contraseña y cerrar sesión—, al pie de las tarjetas: dentro de un Módulo solo se puede cerrar sesión, y el cambio de contraseña se ofrece además en la Administración.
_Avoid_: confundir con el "Inicio" del módulo Preliquidación (el Dashboard de quincenas, otra pantalla).

**Tarjeta**:
La entrada a un Módulo (o a Gerencial, o a la Administración) desde el Inicio: ícono, nombre y una línea de descripción. Solo se muestra si el módulo está activo y la persona tiene rol en él (el admin las ve todas). No muestra el rol de la persona: ver Etiqueta de rol.

**Administración**:
La pantalla del Sistema, visible solo para el rol Admin, donde se da de alta a una persona buscándola en el Padrón de empleados, se le asignan su rol global y sus roles por Módulo, y se gestionan los usuarios existentes (activar/desactivar, cambiar rol, reiniciar contraseña). El identificador de la persona es su CUIL: el alta le genera un email sintético derivado del CUIL, y la contraseña inicial es el CUIL, que cada persona puede cambiar cuando quiera desde su propia sesión. Los usuarios no se borran: se desactivan.
_Avoid_: ABM de usuarios (nombre técnico, no el término de dominio); confundir con los scripts de consola, que quedan como alternativa y como salida de emergencia si el Admin pierde su propio acceso.

**Padrón de empleados**:
El listado de empleados del maestro de sueldos (solo lectura) de donde sale el alta de una persona en la Administración: apellido y nombre, CUIL, y sus legajos por Empresa. El Sistema nunca escribe en él.

## Roles

**Rol**:
Nivel de acceso de un usuario del Sistema. Hay un rol **global**, Admin, y por cada Módulo un usuario puede tener rol Operador o Gerente (uno por usuario y módulo). Qué puede hacer cada rol dentro de un módulo lo define ese módulo. La restricción se aplica en el backend, no solo en pantalla.

**Admin**:
Rol global del Sistema: ve y opera todos los módulos y administra usuarios y permisos desde la Administración. No es un rol de módulo.

**Operador (de módulo)**:
Rol dentro de un Módulo: quien opera el circuito completo de ese módulo (en Preliquidación, el liquidador; en Liquidación Terceros, quien liquida a los terceros). Un operador de un módulo no ve las pantallas operativas de otro módulo. En Preliquidación se muestra como Preliquidador (ver Etiqueta de rol).

**Gerente (de módulo)**:
Rol dentro de un Módulo que accede al panel gerencial de ese módulo y a lo que el módulo decida abrirle. Una misma persona puede ser gerente de varios módulos y entonces ve el analítico de todos ellos.

**Etiqueta de rol**:
El nombre visible que cada módulo le da a sus roles de módulo. El código interno siempre es `operador`/`gerente`; en Preliquidación el operador se muestra como **Preliquidador**. Se usa **solo en la Administración**, para que el Admin elija y lea los roles con palabras y no con códigos: a la propia persona el Sistema **no le muestra en ninguna pantalla** qué rol tiene.
_Avoid_: usar "operador" en pantalla; mostrarle a alguien su propio rol.

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
