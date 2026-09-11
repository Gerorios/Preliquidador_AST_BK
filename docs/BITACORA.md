# Bitácora

Diario del proyecto: qué se mergeó, a qué frontera del sistema le pasó, y por
qué se decidió así. Lo escribe el agente `bitacora` (ver
`.claude/agents/bitacora.md`), disparado con `/bitacora` cuando entran merges a
`main`.

Sólo se agrega al final. Las entradas viejas no se corrigen: si algo dejó de
ser verdad, la entrada nueva lo dice, y la vieja queda como registro de lo que
se creía entonces.

El *qué* de cada cambio está en `git log`. Acá se guarda el **por qué**, que es
lo que se pierde entre sesiones. Ese porqué sale del cuerpo del PR: si no está
escrito ahí, la bitácora lo marca como no registrado.

---

## 2026-09-10 — El segundo módulo pasa a ser Liquidación Terceros y cierra la etapa 0 con la Administración de usuarios

Los dos PRs salieron de sesiones de grilling del 2026-09-09 y se mergearon a
`main` el 2026-09-10 (UTC), en ese orden: primero el renombrado, después el
PR 5, trayendo `main` a su rama con un merge intermedio (`3fbc0ca`). La entrada
se fecha por el merge, no por el grilling.

**Mergeado**
- PR #41 (back) — el módulo `fletes` pasa a `terceros` ("Liquidación Terceros"),
  con glosario y plan de implementación del módulo. Merge `ee8c0a8`.
- PR #42 (back) — Administración de usuarios desde el padrón de empleados,
  último PR de la etapa 0. Merge `e349e19`.
- PRs hermanos en el front (`frontend_preliquidacion`): FT #40 (renombrado del
  molde) y FT #41 (Administración). No se leyó ese repo; se nombran porque los
  cuerpos de los PRs del back los referencian.

**Por frontera**
- **Núcleo**: el padrón de sueldos se mudó desde el módulo de preliquidación a
  `app/core/sueldos_service.py` y ganó `buscar_personas()`. Nuevos
  `app/core/identidad.py` (CUIL, email sintético y su ida y vuelta),
  `app/core/usuarios_service.py` (alta en lote, reset de contraseña, las tres
  protecciones de admin) y `app/core/administracion.py` (seis endpoints bajo
  `/api/admin`, todos detrás del rol global `admin`). `auth.py` acepta login por
  CUIL o email, devuelve `password_inicial` y expone `POST /api/auth/password`.
  `permisos.py` suma la dependencia `requiere_admin`. La tupla `MODULOS` cambia
  la clave `fletes` por `terceros`.
- **Preliquidación**: sólo el ajuste de imports por la mudanza del padrón al
  núcleo. Sin cambio de comportamiento.
- **Liquidación Terceros**: `app/modulos/fletes/` → `app/modulos/terceros/`
  (clave `terceros`, prefijo `/api/terceros`, tablas `terceros_*`, etiqueta de
  rol "Liquidador de terceros"); `migrations/fletes` → `migrations/terceros`;
  `tests/fletes` → `tests/terceros`. El módulo **sigue inactivo**: no monta
  rutas ni aparece en el Inicio. Nuevos
  `docs/modulos/terceros/CONTEXT-terceros.md` (lenguaje ubicuo) y
  `docs/modulos/terceros/plan-terceros.md` (nueve etapas).
- **Prod y Datos**: **ninguna migración** — el esquema no cambia en ninguno de
  los dos PRs. El comentario de `migrations/core/001_usuario_modulo.sql` se dejó
  intacto por ser una migración ya aplicada en producción. `.gitignore` excluye
  `docs/modulos/*/fuentes/*` salvo su `LEEME.md`.
- **Docs**: `CONTEXT.md`, `README.md`, `docs/DOCUMENTACION.md`,
  `docs/modulos/GUIA-MODULOS.md` y `docs/modulos/PUESTA-A-PUNTO.md` pasan a
  hablar de Liquidación Terceros y suman los términos Administración y Padrón de
  empleados. Se agregó el plan
  `docs/superpowers/plans/2026-09-09-etapa0-pr5-administracion.md`.

**Decisiones**
- El módulo `fletes` se renombra a `terceros`. Porqué: el circuito que va a
  resolver es más grande que los fletes de colectivos — también liquida las
  horas de taller sobre maquinaria de terceros, y esas horas son un término del
  neto del recibo de flete (`Neto = Viajes − Combustible − Repuestos − Horas −
  Seguro + Ajustes`). "Fletes" era el nombre de la mitad chica: de las ~800
  horas de taller cobrables de 2026, sólo 56 corresponden a transportistas.
  Descartado: partirlo en dos módulos — la regla 2 de la guía prohíbe que un
  módulo importe a otro.
- Se renombra ahora y no después. Porqué: el molde son diez archivos casi vacíos
  y todavía no existe ninguna tabla; por ADR-0013 las tablas en producción no se
  renombran, así que después de la primera migración ya no se podría.
- La identidad de una persona es su CUIL. Porqué: el legajo se repite entre
  empresas (15.621 legajos para 19.755 filas de `nuempleados`) y el nombre no es
  único ni estable. Descartados: legajo y nombre.
- El usuario se guarda con email sintético
  `<cuil>@usuarios.laasturianasrl.com.ar`. Porqué: la columna `email` es
  `UNIQUE NOT NULL` y el PR no migra el esquema; el email sintético aprovecha
  esa restricción sin tocar la base. Nadie lo tipea: el login acepta el CUIL
  pelado, con guiones o sin, y los usuarios anteriores siguen entrando con su
  mail real.
- El sistema no manda correo. Porqué: no hay ningún canal de email instalado y a
  escala de tres usuarios traer un proveedor, un dominio remitente y el manejo
  de rebotes no se paga. Recuperación de contraseña: la resetea un admin.
- La contraseña inicial es el CUIL y cambiarla es voluntario (el aviso no
  bloquea). Porqué: así el alta múltiple no genera una contraseña distinta por
  persona que haya que repartir de a una — la instrucción es la misma frase para
  todos.
- Los usuarios no se borran, se desactivan. Porqué: tres tablas guardan
  auditoría apuntando a `usuarios` (`preliquidacion.creado_por`, que es
  `NOT NULL`; `concepto_liquidacion.ingresado_por`; `ajuste_manual.usuario_id`,
  con FK real sin `ON DELETE`), MySQL rechazaría el borrado de cualquier usuario
  con actividad y forzarlo destruiría el rastro de la liquidación.
- Tres protecciones impiden que el admin se deje afuera: no auto-desactivarse,
  no auto-quitarse el rol admin, nunca dejar cero admins activos. Porqué: sin
  correo, un sistema sin admin activo sólo se recupera entrando a MySQL a mano.
- El padrón se muda al núcleo. Porqué: es lo que el ADR-0013 ya había decidido
  ("el núcleo comparte lectura de Persona/Legajo/Empresa") y de paso le deja el
  padrón servido al segundo módulo. Corre sobre el cache en memoria que ya
  existía, así que no agrega consultas.
- `buscar_personas()` normaliza el CUIL, pero el cache del padrón no. Porqué: el
  padrón tiene ~41 registros con CUIL malformado que la Administración mostraba
  como marcables y el alta rechazaba después, duplicando el trabajo; normalizar
  también en `_cargar_cache` habría cambiado el comportamiento de
  `_por_cuil`/`legajos_por_cuil`/`legajo_por_cuil_y_empresa`, que la
  preliquidación usa en producción para cruzar personas por CUIL, sin necesidad.
- El material de origen del módulo Terceros queda fuera de git (sólo se commitea
  `fuentes/LEEME.md`). Porqué: los repos son públicos y el Excel maestro, las
  consultas, los archivos de las estaciones y el de seguros tienen nombres de
  terceros, precios pactados, saldos, personas y los hosts de las bases.
- `reportlab` para el PDF del recibo **queda pendiente de aprobación** y no se
  agrega en este PR. Porqué: la regla de stack de GUIA-MODULOS exige aprobar
  dependencias nuevas.

Decisiones de diseño del módulo Terceros que el plan fija, todavía sin código:

- El sistema de campo es el maestro; el módulo concilia y alerta, no mantiene un
  padrón propio, y el puente entre los tres sistemas es un identificador, no un
  nombre. Porqué: los tres nombran distinto a la misma máquina, y unir por texto
  obliga a tres personas a escribir igual para siempre.
- Tarifas por quincena, con copia desde la quincena que se elija (mismo
  mecanismo del ADR-0004), seis dimensiones opcionales, gana la más específica y
  el empate es ambiguo y lo resuelve el liquidador. Porqué: con el precio
  tipeado fila por fila aparecen grupos de viajes idénticos con dos precios
  distintos alternados.
- La quincena efectiva se carga a mano, con motivo. Porqué: además de la llegada
  tardía existe la excepción comercial (no descontarle algo a un tercero para
  ayudarlo), que no se deduce de ninguna fecha.
- Emitir el recibo lo congela. Porqué: hoy un recibo ya enviado cambia solo si
  alguien corrige un dato viejo en el origen.
- 2026 entra congelado hasta la 1ra quincena de agosto, tal como se liquidó.
  Porqué: las reglas nuevas no se aplican retroactivamente — un saldo que un
  tercero ya saldó no se mueve solo.

**Estado**
- Migraciones: ninguna. Los dos PRs declaran que el esquema no cambia; el deploy
  es swap de código y reinicio, y las sesiones abiertas no se cortan.
- Verificación registrada: 232 tests en verde al cerrar el PR #41; 277 al cerrar
  el PR #42 (232 + 45 nuevos, más 2 del arreglo de `buscar_personas`). El
  `openapi.json` pasó de 58 a 64 paths sin perder ninguno. La búsqueda del
  padrón y el alta se probaron contra datos reales en la base de desarrollo.
- La interfaz **no se ejecutó** durante el desarrollo del PR #42 (el entorno no
  tenía navegador): el front se verificó por lectura y compilación, el dueño la
  probó a mano, y ya apareció un defecto de esa clase que ninguna revisión de
  código atrapó — el formulario de login tenía `type="email"` y el navegador
  rechazaba un CUIL antes de enviarlo, corregido en el PR del front.
- Deploy: **no registrado en el cuerpo de los PRs ni en los commits.** Lo que sí
  dicen es que no hace falta migración.

**Pendiente**
- Confirmar que `terceros` y "Liquidación Terceros" son los nombres correctos
  antes de que existan tablas: después de la primera migración ya no se cambian.
- Aprobar (o no) `reportlab` como dependencia nueva.
- Revisar el plan de Terceros, sobre todo sus etapas y los pendientes por
  confirmar con cada sistema de origen.
- El módulo Terceros sigue inactivo. Bajo qué condición se activa: no
  registrado.
- Hallazgos del relevamiento que el módulo va a tener que corregir y que hoy
  están sólo escritos: la fecha de los repuestos (la consulta usa la del
  encabezado del movimiento en vez de la de la descarga a la maquinaria, y en
  2026 la mitad de las líneas de terceros cae en otra quincena según cuál se
  use, algunas en otro año); los seguros, que se liquidan por un circuito
  separado del Excel y el módulo absorbe; y las máquinas de terceros que el
  sistema de compras tiene y la app del taller no, entre ellas la de un
  transportista cuyos repuestos hoy no llegan a su recibo.

## 2026-09-10 — Agente escribano: la bitácora empieza a existir

**Mergeado**
- PR #43 (backend_preliquidacion) — agrega el agente `bitacora`, el comando
  `/bitacora`, un hook `post-merge` que avisa si entraron PRs sin anotar, su
  instalador, y `docs/BITACORA.md` con la primera entrada ya escrita.

**Por frontera**
- Docs y herramientas de trabajo: seis archivos nuevos, ninguno de aplicación.
  Sin migraciones, sin dependencias, sin tocar núcleo ni módulos.

**Decisiones**
- El disparador es el merge a `main`, no la apertura del PR. Porqué: un PR
  abierto es una propuesta, no una decisión; al diseñarlo había cuatro PRs
  abiertos que se solapaban en 7 archivos y sin orden de merge decidido, y un
  agente disparado por apertura habría anotado como verdad dos estados
  incompatibles. Descartado: disparar al abrir el PR.
- Dos niveles de autonomía: `docs/BITACORA.md` lo escribe el agente solo,
  `MEMORY.md` y `memory/*.md` van siempre con OK humano. Porqué: la bitácora es
  append-only y un error queda como línea fea que la entrada siguiente corrige;
  la memoria se carga como contexto en cada sesión, así que un error ahí se
  vuelve verdad sin que nadie lo note.
- El porqué sale del cuerpo del PR y nunca se deduce del diff; si no está
  escrito, el agente anota "Porqué no registrado en el PR". Porqué: es
  preferible una bitácora con huecos honestos a una con porqués inventados que
  después se citan como ciertos.
- `.gitattributes` fuerza LF en los hooks. Porqué: en Windows con `autocrlf`, un
  clon nuevo bajaba `post-merge` con CRLF y `sh` rechaza un shebang con `\r`.

**Estado**
- Deploy: no, no requiere.
- Migraciones: ninguna.
- La primera entrada se auditó a mano contra el código (archivos nuevos, 6
  endpoints `/api/admin`, `MODULOS`, prefijo `terceros_`, 277 tests).

**Pendiente**
- Los diez porqués sin registrar que dejó la primera corrida siguen abiertos
  (ver la entrada del 2026-09-10 anterior y el cuerpo del PR #43).
- El instalador de hooks corre por clon: `sh scripts/hooks/instalar.sh`.

## 2026-09-11 — CLAUDE.md, para que la bitácora se consulte

**Mergeado**
- PR #44 (backend_preliquidacion) — agrega `CLAUDE.md` (~90 líneas), único
  archivo del PR.

**Por frontera**
- Docs: nada de código, migraciones ni dependencias.

**Decisiones**
- Nombrar `docs/BITACORA.md` desde `CLAUDE.md`. Porqué: `CLAUDE.md` se carga en
  cada sesión y la bitácora no; sin algo que la nombre, el porqué archivado no
  se consulta nunca. El PR #43 construyó el archivo y no el reflejo de abrirlo.
- Bajar a `CLAUDE.md` las reglas de trabajo que vivían sólo en la memoria del
  asistente (rama antes de editar, no deployar sin OK, smoke tests reales,
  verificación adversarial, migraciones no diferibles). Porqué: depender de la
  memoria es frágil, y esas reglas existen porque el sistema está en producción
  y lo usan personas reales.
- Incluir la tabla de los cuatro documentos (`CONTEXT.md`, `docs/adr/`,
  `docs/BITACORA.md`, `docs/modulos/GUIA-MODULOS.md`). Porqué: se confunden
  entre sí y la confusión tiene consecuencias — un ADR es un compromiso con
  alternativas descartadas, no un resumen, y no se escribe sin el usuario.
- Dejarlo corto y sólo con lo no deducible leyendo el repo (trampas del entorno,
  reglas pedidas por el usuario, qué documento es cuál). Porqué: un `CLAUDE.md`
  largo se ignora.
- **Las entradas de esta bitácora se commitean directo a `main`, sin rama ni
  PR.** Porqué: si fueran por PR, cada anotación generaría otro merge que
  anotar, en cadena infinita. Es la única excepción a "rama antes de editar" y
  vale sólo para `docs/BITACORA.md`, que es append-only y no ejecuta nada.
  (Decisión tomada en conversación el 2026-09-11, no figura en ningún PR.)

**Estado**
- Deploy: no, no requiere.
- Migraciones: ninguna.

## 2026-09-11 — La excepción de la bitácora, escrita

**Mergeado**
- PR #45 (backend_preliquidacion) — deja por escrito que `docs/BITACORA.md` se
  commitea directo a `main` y que va una entrada por día de merge; toca
  `CLAUDE.md` y `.claude/agents/bitacora.md` (el contrato del agente escribano).
  Incluye además el commit con las entradas de los PRs #43 y #44.

**Por frontera**
- Docs: sólo documentación; nada de código, migraciones ni dependencias.

**Decisiones**
- Escribir la excepción en los dos lugares (`CLAUDE.md` y el contrato del
  agente). Porqué: es donde alguien la va a buscar, y con el motivo al lado para
  que en unos meses no parezca que la regla se aflojó sin razón. La tentación a
  evitar es extenderla: cualquier otro archivo sigue yendo por rama.
- Una entrada por día de merge, no una por tanda. Porqué: al anotar #43 y #44,
  mergeados en días distintos, el contrato no decía qué hacer con varios merges
  y habrían quedado en una sola entrada fechada arbitrariamente.
- No ajustar el tamaño de las entradas. Porqué: con tres escritas (151, 40 y 34
  líneas) la duda que dejó el PR #43 quedó medida — la larga cerraba una etapa
  con dos PRs grandes, un PR normal cae en 35-40 líneas.

**Estado**
- Deploy: no, no requiere.
- Migraciones: ninguna.

**Nota**
- La entrada anterior del 2026-09-11 anotaba esta decisión como "no figura en
  ningún PR". Este PR la deja registrada.

## 2026-09-11 — Los dos agujeros del circuito de la bitácora, tapados

**Mergeado**
- PR #46 (backend_preliquidacion) — agrega a `CLAUDE.md` la regla de preguntar
  al usuario, después de cada merge a `main`, si correr `/bitacora`.
- PR #42 (frontend_preliquidacion) — lleva al front el mismo circuito: hook
  `post-merge`, `scripts/hooks/instalar.sh`, `.gitattributes` (LF en los hooks)
  y un `CLAUDE.md` propio.

**Por frontera**
- Docs y herramientas de trabajo: nada de aplicación en ninguno de los dos
  repos. Sin dependencias, sin build, sin módulos ni núcleo tocados.

**Decisiones**
- Preguntar en una línea y no insistir si el usuario dice que no. Porqué: el
  hook `post-merge` sólo avisa cuando la máquina del usuario actualiza `main` y
  ese aviso se pierde entre la salida de otros comandos; y una pregunta larga
  repetida en cada merge se empieza a ignorar en una semana. Si dice que no, la
  próxima corrida cubre ese merge igual con su fecha correcta.
- El front avisa pero no escribe: el agente `bitacora` vive en el backend.
  Porqué: si se mergeaba algo sólo del front no avisaba nadie y el porqué se
  perdía — justo donde más se pierde, porque las decisiones de interfaz salen de
  una prueba manual y no de un diff (caso citado: el login con `type="email"`
  que rechazaba un CUIL con el backend en verde).
- **La bitácora sigue siendo una sola, en el backend.** Porqué: dos diarios para
  un mismo sistema serían dos versiones de la misma historia, y cuando no
  coincidan no se sabría cuál vale. (Decisión tomada en conversación el
  2026-09-11, no figura en el cuerpo de ningún PR.)
- `.gitattributes` en el front no es cosmético. Porqué: en Windows con
  `autocrlf`, un clon nuevo bajaría `post-merge` con CRLF y `sh` rechaza un
  shebang terminado en `\r`. Mismo bug que ya había aparecido en el backend.

**Estado**
- Deploy: no, ninguno de los dos lo requiere.
- Migraciones: ninguna.

**Pendiente**
- `scripts/hooks/instalar.sh` corre una vez por clon: cada clon nuevo del front
  queda sin el hook hasta que alguien lo instale.
