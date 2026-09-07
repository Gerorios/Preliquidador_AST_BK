# Monolito modular con núcleo compartido: el sistema crece por módulos, no por servicios

El preliquidador de sueldos deja de ser el sistema entero y pasa a ser el primer **módulo** de un sistema de gestión al que se le van a sumar otros circuitos de liquidación, empezando por **fletes** (2026-09, desarrollado en colaboración con una segunda desarrolladora que tiene el contexto del dominio y hoy resuelve ese circuito con un Excel conectado a la misma base del sistema de campo). La pregunta era cómo agregar módulos sin que cada uno duplique login, deploy y acceso a las bases, y sin que el código de un módulo se entremezcle con el de otro.

Se decide un **monolito modular**: un solo backend FastAPI y un solo frontend React, en los mismos dos repos de hoy, donde cada módulo vive en su propia carpeta (`app/modulos/<modulo>/` y `src/modulos/<modulo>/`) y solo se apoya en un **núcleo compartido** explícito (`app/core/`, `src/core/`): autenticación y permisos, conexiones a las tres bases, lecturas comunes del sistema de campo y del maestro de sueldos (cliente, finca, persona/legajo, empresa), utilidad de quincena, layout y componentes visuales. El código actual de preliquidación se **reordena** a esa estructura antes de que empiece el segundo módulo, sin cambiar comportamiento.

## Considered Options

- **Monolito modular en los mismos repos (elegida).** Un login, un deploy, una base, un VPS. El aislamiento entre módulos es una convención verificable (carpeta propia, prefijo de tablas, router propio, tests propios, prohibido importar de otro módulo) en vez de una frontera de red. Con dos desarrolladores y un VPS chico, es la única opción cuyo costo fijo no crece por módulo.
- **Servicios separados que comparten login (rechazada).** Un backend y un frontend por módulo, colgados bajo el mismo dominio por nginx. Aísla de verdad, pero duplica proceso systemd, deploy, manejo de sesión y conexiones por módulo, y obliga a resolver autenticación cruzada desde el día uno. No hay carga ni equipo que lo justifique.
- **Sistemas independientes (rechazada).** Cada circuito su propia app. Es el statu quo del Excel llevado a web: nada se unifica, el gerente sigue mirando dos lugares, y los usuarios tienen dos contraseñas.
- **Módulos dentro de la estructura por capas actual (rechazada).** Seguir con `app/api/`, `app/services/`, `app/models/models.py` únicos y meter fletes ahí. Es lo que pasaría sin decisión: al tercer módulo nadie sabe qué archivo pertenece a qué circuito, y un cambio de fletes puede romper preliquidación sin que el diff lo muestre.

## Decisiones asociadas (mismo grilling, 2026-09-07)

- **Datos**: misma base `preliquidacion`, tablas de cada módulo nuevo con prefijo propio (`fletes_`). Las tablas actuales de preliquidación no se renombran (producción con datos reales). Migraciones SQL manuales como hasta ahora, pero en carpeta por módulo (`migrations/<modulo>/`).
- **Permisos por módulo**: `admin` global; por módulo, roles `operador` y `gerente` (tabla `usuario_modulo`). Un operador no ve las vistas operativas de otro módulo; el gerente ve el analítico de los módulos que tiene asignados. Los usuarios actuales migran a preliquidación con su rol de hoy.
- **Gerencial por módulo**: cada módulo trae su propio panel bajo `/api/<modulo>/gerencial`; una entrada "Gerencial" del sistema muestra una solapa por módulo. Sin consolidación entre módulos por ahora. Es la última etapa de cada módulo.
- **Nombre**: se renombra solo lo visible (título, login, menú). URL quizás más adelante. Repos, base, servicio systemd y carpetas del VPS **nunca** se renombran.
- **Bases externas**: cada módulo tiene su propio archivo de consultas al sistema de campo, SQL crudo parametrizado y de solo lectura, como `consulta_externa.py` hoy. El núcleo solo expone la conexión.
- **Ambiente**: desarrollo contra la base `testing` (credenciales propias del responsable); producción sigue en `preliquidacion`. Migraciones se prueban en `testing` y se aplican a producción solo junto con el deploy, por el responsable del sistema.
- **Flujo**: rama por feature (`feature/<modulo>-<tema>`), PR, revisión y merge únicamente por el responsable del sistema, deploy únicamente por él. Nadie modifica archivos fuera de su módulo sin avisar; cambios al núcleo van en PR separado y chico.

## Consecuencias

- Antes de que empiece el módulo de fletes hay un trabajo de **reordenamiento** del preliquidador a la estructura modular (movimiento de archivos, sin cambio de comportamiento, cubierto por la suite de tests). Hasta que no esté, el segundo módulo no puede codearse; sí puede especificarse.
- Aparece una tabla nueva de permisos y una dependencia `requiere_modulo(<modulo>, <rol>)` que reemplaza a `requiere_rol`. Los endpoints actuales se mapean uno a uno.
- La regla "nunca escribir en las bases externas" y "nunca importar de otro módulo" pasan a ser parte del checklist de revisión de cada PR.
- Si algún día un módulo necesita escalar aparte (carga, equipo, ciclo de deploy distinto), la frontera por carpeta hace que extraerlo a un servicio sea un movimiento, no una reescritura. Esa es la puerta que esta decisión deja abierta, no un plan.
- La guía para incorporar un módulo es `docs/modulos/GUIA-MODULOS.md`.
