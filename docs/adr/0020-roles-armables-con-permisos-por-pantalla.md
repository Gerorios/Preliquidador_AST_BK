# Roles armables por el admin, con permisos de ver o editar por pantalla

Hasta ahora cada persona tenía, por módulo, un rol fijo, operador o gerente, y lo que podía cada uno estaba escrito en el código de cada módulo (ADR-0013). Con el uso aparecieron necesidades que ese esquema no cubre sin programar: el gerente necesita mirar Verificación y los precios de Conceptos, y Facturación se diseñó con tres niveles (consultar, cargar y mantener) que no entran en operador/gerente. Se decide que un **Rol** sea un conjunto de **Permisos** con nombre que el admin arma desde la Administración, y que un Permiso sea **Ver** o **Editar** una **Pantalla** (Editar incluye Ver). Una persona tiene uno o más roles y sus permisos se suman. El admin sigue siendo una marca global aparte, que puede todo. Decidido con el usuario el 2026-10-09.

## Considered Options

- **Roles fijos por módulo, como hasta ahora** (rechazada): cada caso nuevo, como el del gerente, es un cambio de código y un deploy.
- **Lector / editor / admin por módulo** (rechazada): era la idea inicial, pero da acceso a un módulo entero o a nada. No resuelve que el gerente vea Verificación sin ver Revisión.
- **Roles armables con permiso por pantalla** (elegida): el admin cambia lo que puede cada rol sin programar. La pantalla es la unidad que el usuario reconoce en el menú.
- **Permisos por acción, más finos que la pantalla** (rechazada): cada botón con su permiso hace la grilla del admin ilegible, y no apareció ningún caso que lo pida.
- **Un solo rol por persona** (rechazada): obliga a crear un rol por cada combinación, por ejemplo "preliquidador y liquidador de terceros".

## Consecuencias

- **Cada lectura pide su permiso.** Todo dato que entrega el backend pide Ver en alguna pantalla que lo usa. Se cierran lecturas que hoy sólo piden sesión iniciada, como el maestro de precios.
- **La migración no cambia el acceso de nadie.** Se crean tres roles que copian lo de hoy, y cada persona recibe el suyo:
  - "Preliquidador": todas las pantallas de Preliquidación salvo la Vista gerencial;
  - "Gerente": la Vista gerencial y Conceptos, con Editar;
  - "Liquidador de terceros": todas las pantallas de Terceros.

  Después, el admin le suma Verificación al Gerente desde la Administración.
- **Roles en uso.**
  - Cambiar un rol vale enseguida para todas las personas que lo tienen, y antes de guardar se avisa cuántas son.
  - Un rol que alguien tiene no se puede borrar.
  - A la persona no se le muestra qué roles tiene: sólo ve sus pantallas.
- **Cada módulo declara sus pantallas.** Al entrar a un módulo, la persona aterriza en la primera pantalla que puede ver. Un módulo nuevo suma sus pantallas a la lista que ofrece la Administración. Facturación nace así, y su plan cambia las "capacidades" por pantallas cuando empiece.
- **El admin no cambia.** Sigue aparte de los roles, con las protecciones de hoy para que el Sistema nunca quede sin un admin activo.
- **Reemplaza la parte de permisos del ADR-0013:** los roles `operador` y `gerente` por módulo y la tabla `usuario_modulo`. El resto del ADR-0013 sigue vigente.
