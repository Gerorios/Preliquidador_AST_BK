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

## 2026-09-11 — La convención de commits, por escrito

**Mergeado**
- PR #47 (backend_preliquidacion) — skill `/commit` con la convención de
  mensajes del repo (`.claude/skills/commit/SKILL.md`, nuevo), resumen de tres
  viñetas en `CLAUDE.md`, corrección de la línea de `docs/modulos/GUIA-MODULOS.md`
  que nombraba cuatro tipos, y el plan en `docs/superpowers/plans/`.

**Por frontera**
- Docs: lo único tocado. Nada de aplicación, ni núcleo, ni módulos, ni front.
  La convención queda fijada como `<tipo>(<scope>): <descripción>` en español,
  con vocabulario cerrado a seis tipos (`feat`, `fix`, `refactor`, `docs`,
  `test`, `chore`).

**Decisiones**
- La regla central de la skill es **cuándo NO poner cuerpo**: sólo si hubo una
  decisión real. Porqué: el agente `bitacora` lee estos mensajes además del
  cuerpo del PR para archivar el porqué de cada merge, así que un cuerpo escrito
  para cumplir un formato se convierte en una decisión que nadie tomó, archivada
  como si alguien la hubiera tomado. Vacío es mejor que relleno.
- La convención se escribe en dos lados a propósito: el detalle en la skill, tres
  viñetas en `CLAUDE.md`. Porqué: la skill sólo se carga cuando se la invoca y
  `CLAUDE.md` se carga siempre; sin esas líneas la convención no regiría para
  quien commitea sin pasar por `/commit`.
- La guía de módulos se corrigió en el mismo PR. Porqué: es lo que lee Pitu y
  nombraba cuatro tipos, así que la convención quedaba bifurcada apenas se
  escribió la skill.
- `## Prohibido` va primero en el archivo de la skill y no al final. Porqué:
  `.claude/settings.local.json` permite `Bash(git *)` y `Bash(git push *)` sin
  prompt, y esa lista es lo único que frena un push o un `amend` accidental.
- Descartado: instalar la skill de eagerworks (`npx skills add`). Su aporte
  principal es agrupar los cambios en varios commits por unidad lógica, que acá
  no se quiere, y traía cuatro archivos de referencia, un `.eagerworks/commit.json`
  con namespace ajeno y un puntero a una skill `create-pr` inexistente. Se le
  tomaron tres ideas: inferir el vocabulario del historial propio, pasar el
  mensaje por HEREDOC y declarar por escrito los límites de mutación.
- Descartado por ahora: un hook `commit-msg` que valide el formato. Sería la
  única verificación permanente y real —hoy todo depende de que el agente lea la
  skill— pero se reabre si en un mes aparecen commits fuera de convención.
- Descartado: que la skill cree el PR o pushee. Termina en el commit.

**Estado**
- Deploy: no. Nada que deployar.
- Migraciones: ninguna.
- Tests: 277 passed (108s). Los 32 errores del primer intento fueron por el
  `.env` faltante en el worktree, no por el cambio.
- Dogfooding: los cuatro commits del PR se escribieron con las reglas de la skill,
  y los acentos por HEREDOC en Windows salieron correctos.

**Pendiente**
- Sin probar: la baranda de la skill que crea la rama sola cuando se está en
  `main`. No se puede ensayar desde un worktree, porque git no permite tener
  `main` checkouteada dos veces. Se prueba en el checkout principal o la primera
  vez que se dispare de verdad.

## 2026-09-18 — Tope de lectura en la externa y candado por quincena

**Mergeado**
- PR #48 (backend_preliquidacion) — dos barandas para "Generar / Actualizar
  quincena" a raíz del incidente del mismo día: `read_timeout=60` y
  `connect_timeout=10` en la conexión a la base externa de ADCP
  (servidor de ADCP), con 503 "La base de datos de campo (ADCP) no respondió
  a tiempo" si la consulta se traba; y un candado por quincena que devuelve 409
  "Ya hay una generación en curso para esta quincena" a la segunda corrida
  concurrente. Sin PR hermano en el front.

**Por frontera**
- Núcleo: `app/core/database.py` gana la excepción `ExternaNoDisponible`, junto
  al engine que la origina. `app/main.py` suma un handler global que la traduce
  a 503 para cualquier módulo.
- Preliquidación: `services/consulta_externa.py` pasa todas sus consultas a la
  externa por un helper que traduce `OperationalError` a `ExternaNoDisponible`
  (no sólo la consulta principal: también catálogo de tareas, clientes, fincas).
  `api/preliquidacion.py` incorpora el candado en memoria por quincena, que se
  libera siempre, también si la corrida falla. Tests nuevos:
  `tests/preliquidacion/test_consulta_externa_timeout.py` y 7 casos en
  `test_generar_api.py`.
- Prod y Datos: `docs/DEPLOY.md` anota que el candado, igual que el cache de
  sueldos, vive en memoria del proceso y que el diseño asume `--workers 1`.
- Docs: plan en `docs/superpowers/plans/2026-09-18-externa-timeout-y-concurrencia.md`.

**Incidente que lo originó**
- 2026-09-18, 15:45 a 15:57: el servidor de ADCP quedó bloqueado 12 minutos
  (llegó a su tope de 151 conexiones; nosotros sólo tenemos SELECT ahí). La
  consulta principal, que tarda 2 s, tardó entre 73 y 719 s. El front cortó a
  los 300 s con "timeout of 300000ms exceeded" sin decir qué pasaba y se
  acumularon 7 corridas simultáneas de la misma quincena, que se liberaron
  todas en el mismo segundo. No duplicaron líneas esta vez (1998 y 110 líneas,
  igual al campo), pero cada corrida calcula el diff antes de que las otras
  escriban, así que la carrera existe.

**Decisiones**
- Tope de **60 s**. Porqué: la consulta normal tarda 2 s, hay margen de sobra y
  el usuario se entera en un minuto en vez de en cinco; el front (300 s) y
  nginx (300 s) ya no llegan a cortar.
- El tope va **sólo en la externa**. Porqué: la base propia escribe y cortarla
  a mitad de un commit es peor que esperar; la de sueldos no participa en este
  flujo.
- `ExternaNoDisponible` vive en el **núcleo** con handler en `main.py`, no en el
  módulo. Porqué: así cualquier módulo recibe el 503 sin que el núcleo importe
  módulos (ADR-0013). Surgió de la revisión: la primera versión traducía sólo la
  consulta principal y un corte en las demás seguía dando 500 con "Lost
  connection to MySQL server".
- Candado **en memoria del proceso**, no en la base. Porqué: el deploy corre con
  `--workers 1`, anotado en `docs/DEPLOY.md` y en el código. Si algún día hay
  más workers, pasa a la base.
- Descartado: tocar el front. Porqué: el interceptor de `api.js` ya muestra
  `detail` de cualquier error y el botón ya se deshabilita mientras espera.

**Estado**
- Deploy: sí, al VPS de producción el 2026-09-18 ~17:45 UTC, con OK del usuario.
- Migraciones: ninguna. Sin cambio de contrato con el front. Rollback: revertir
  el merge.
- Tests: 284 en verde (277 + 7 nuevos). Smoke real contra ADCP con
  `read_timeout=1` y `SELECT SLEEP(10)`: corta a 1,00 s exacto, sin reintentos,
  y llega al usuario como `ExternaNoDisponible`. La consulta real con tope de 60
  sigue devolviendo las 1998 filas en ~2 s.

**Pendiente**
- Deuda preexistente, más seria que el candado: `Preliquidacion.quincena` guarda
  la fecha cruda, así que generar con 09-16 y después con 09-17 crea dos
  preliquidaciones con las mismas líneas. Amerita su propio fix.
- La clave del candado tampoco se normaliza a inicio de quincena: 09-16 y 09-17
  concurrentes esquivan el 409.
- `except OperationalError` es amplio: un error de credenciales (1045) también
  diría "reintentá en unos minutos"; la causa real queda en el log del servidor.
- Un `db_externa.execute` crudo en `precios.py`, fuera del servicio, sigue sin
  traducir.
- La aserción de que `engine_propia` no tiene `read_timeout` es vacía:
  `create_connect_args` no refleja `connect_args`.

## 2026-09-18 — PR #49, la API rechaza quincenas que no empiezan el 1 o el 16

**Mergeado**
- PR #49 (backend) — `fix(preliquidacion)`: las tres entradas que escriben
  (generar preliquidación, alta de concepto, copiar conceptos entre quincenas)
  devuelven 422 "La quincena debe empezar el 1 o el 16 del mes, no el 17" ante
  cualquier otra fecha. Sin PR hermano en el front.

**Por frontera**
- Núcleo: `app/core/quincena.py` gana `validar_quincena` y el tipo
  `Quincena = Annotated[date, AfterValidator(validar_quincena)]`, que sirve en
  esquemas Pydantic y en parámetros de FastAPI. Tests en
  `tests/core/test_quincena.py`.
- Preliquidación: `schemas.py` pasa `PreliquidacionGenerarRequest.quincena` y
  `ConceptoUnifRequest.quincena` de `date` a `Quincena`; `api/precios.py`
  cambia los dos Query de `copiar_quincena` a `Annotated[Quincena, Query()]`.
  Tests en `tests/preliquidacion/test_validar_quincena_api.py`.
- Docs: plan en `docs/superpowers/plans/2026-09-18-validar-quincena.md`.

**Origen**
- Deuda que dejó la revisión del PR #48 (anotada como pendiente en la entrada
  anterior). `calcular_rango_quincena` normalizaba en silencio cualquier día
  distinto de 1 a la segunda quincena, pero `Preliquidacion.quincena` es única
  por fecha cruda: generar con 16/9 y después con 17/9 creaba dos
  preliquidaciones con las mismas 110 líneas, y un concepto cargado al 17/9 no
  se aplicaba a la del 16/9. Producción estaba limpia (6 preliquidaciones,
  todas día 1 o 16) porque el front sólo ofrece esas dos fechas.

**Decisiones**
- **Rechazar con 422, no normalizar.** Porqué: una fecha que no es inicio de
  quincena viene de un cliente que está mal; normalizarla lo escondería.
- **El tipo `Quincena` vive en el núcleo**, junto a la definición del término
  (`app/core/quincena.py`), no en el módulo.
- **Sólo las tres entradas de escritura en este PR.** Porqué: los ~16
  parámetros de lectura de precios y gerencial devuelven vacío con una fecha
  mala, sin crear datos. Cubrirlos es mecánico y queda para otro PR si se
  quiere.
- **Trampa de FastAPI, documentada en el código:** en parámetros Query hay que
  escribir `Annotated[Quincena, Query()]`. Con `Quincena = Query(...)` FastAPI
  0.136 descarta el validador y un 17 pasa. Lo detectó el test de copiar en
  rojo; queda comentado en el núcleo y en el endpoint.
- Descartado: tocar el front. Porqué: ya manda 01 o 16.

**Estado**
- Deploy: sí, al VPS de producción el 2026-09-18 ~18:15 UTC, con OK del
  usuario; health ok.
- Migraciones: ninguna. Sin cambio de contrato con el front. Rollback: revertir
  el merge.
- Tests: 294 en verde (284 + 10 nuevos). Smoke real con la app completa y las
  bases reales: generar 17/9 → 422; copiar destino 17/9 → 422; generar 16/9 →
  200 con "0 nuevas · 0 eliminadas · 110 sin cambios".

**Pendiente**
- Los ~16 parámetros de lectura (precios y gerencial) siguen aceptando
  cualquier fecha; devuelven vacío, no crean datos.
- El interceptor del front muestra `detail` cuando es texto u objeto con
  `mensaje`; el 422 de FastAPI trae una lista, así que si alguna vez llegara se
  vería "Request failed with status 422". Hoy no puede llegar desde el front.
- Siguen abiertos del PR #48: la clave del candado no se normaliza (ahora un
  17 ya no entra, así que el caso 16/17 concurrente desaparece por esta vía),
  `except OperationalError` amplio, el `db_externa.execute` crudo en
  `precios.py`, y la aserción vacía sobre `engine_propia`.

## 2026-09-23 — La externa distingue acceso rechazado de corte, y grupos de pago da 503

**Mergeado**
- PR #50 (backend) — `fix(preliquidacion)`: `GET /api/precios/grupos-pago` pasa
  por `ConsultaExternaService._ejecutar` (503 claro en vez de 500 si ADCP se
  bloquea), y un acceso rechazado por ADCP ya no pide reintentar. Merge
  `c071e0b`. Sin PR hermano en el front.

**Por frontera**
- Preliquidación: `services/consulta_externa.py` gana `QUERY_GRUPOS_PAGO`,
  `obtener_grupos_pago()` y `CODIGOS_ACCESO_RECHAZADO = {1044, 1045, 1142, 1143}`;
  con esos códigos `_ejecutar` levanta `ExternaNoDisponible` con "rechazó el
  acceso del sistema. Reintentar no sirve: avisá a sistemas". El log `[EXTERNA]`
  ahora muestra el código. `api/precios.py` deja el `db_externa.execute` crudo.
  Tests en `tests/preliquidacion/test_consulta_externa_timeout.py`.
- Docs: plan en `docs/superpowers/plans/2026-09-23-externa-errores.md`.

**Origen**
- Dos deudas de la revisión del PR #48, anotadas como pendientes en las dos
  entradas anteriores: el `db_externa.execute` crudo en `precios.py` y el
  `except OperationalError` amplio. Porqué del segundo (del PR): si ADCP rota
  las credenciales, el liquidador reintentaría algo que nunca va a andar, y el
  log lo mostraría como lentitud.

**Decisiones**
- **Sigue siendo 503 en los dos casos**, aunque un acceso rechazado no es
  técnicamente "no disponible". Porqué: el contrato con el front no cambia (ya
  muestra el `detail` de un 503 tal cual) y no hace falta PR hermano.
- **Lista cerrada de códigos de acceso; todo lo demás = "no respondió".**
  Porqué: el default conservador es el comportamiento anterior. Descartado:
  enumerar los transitorios (2003, 2006, 2013…), porque un código no previsto
  quedaría sin traducir y volvería el 500.
- La revisión encontró un hallazgo high: `orig.args` vacío levantaba
  `IndexError` (500 en vez de 503). Se arregló en una línea con test.

**Estado**
- Deploy: sí, al VPS de producción el 2026-09-23, con OK explícito del usuario;
  health ok, servicio activo, sin errores en logs.
- Migraciones: ninguna. Sin cambio de API. Rollback: revertir el merge.
- Tests: 3 nuevos, vistos en rojo primero. Suite completa 296 en verde antes
  del arreglo de la revisión; después, el archivo afectado 6/6. Smoke real con
  las bases reales: `/grupos-pago` → 200 con los mismos 12 grupos que la
  consulta vieja corrida directo contra ADCP.
- No probado en real: un 1045 contra ADCP (exigiría un login fallido a
  propósito en un servidor que no controlamos). Cubierto sólo por test.

**Pendiente**
- El interceptor del front muestra mal el `detail` en lista de un 422. Se está
  atendiendo en `frontend_preliquidacion`; no está cerrado.
- Siguen abiertos del PR #48: la clave del candado no se normaliza y la
  aserción vacía sobre `engine_propia`. Los ~16 parámetros de lectura siguen
  aceptando cualquier fecha (del PR #49).

## 2026-09-23 — El front muestra el texto de un 422 de validación

**Mergeado**
- PR #43 (frontend) — `fix(core)`: el interceptor de `src/core/api.js` arma el
  mensaje con `mensajeDeError(detail)`, que entiende la lista de un 422 de
  FastAPI. Merge `4d702c4`, commit `fa336e1`. Sin PR hermano en el backend.

**Por frontera**
- Núcleo (front): `src/core/mensajeError.js` nuevo, maneja las tres formas de
  `detail`: texto, objeto con `mensaje` (el 409 de solapamiento) y lista de
  validación, uniendo los `msg` con "; " y sacando el prefijo "Value error, "
  de Pydantic. `err.status` y `err.detail` crudo no cambian (Conceptos.jsx
  sigue leyendo el 409 igual).

**Origen**
- La lista del 422 también es `object`, así que el código viejo buscaba
  `.mensaje`, no lo encontraba y mostraba "Request failed with status code
  422". Última deuda del incidente de ADCP (PRs #48, #49 y #50 del backend).

**Decisiones**
- **Función pura aparte.** Porqué: para poder probarla sin axios ni el store.
- **Sin framework de tests.** Porqué: el front no tiene, y sumar Vitest es una
  dependencia nueva que requiere aprobación. Se probó con un script desechable.

**Estado**
- Deploy: sí, al VPS de producción el 2026-09-23, con OK explícito del usuario.
  Swap de carpeta (`frontend_old` queda de rollback); md5 de `index.html`
  idéntico local/VPS (`35cb892f…`), 31 assets, rutas 200, el bundle contiene
  el código nuevo.
- Migraciones: ninguna. Sin cambio de API. Rollback: revertir el merge y
  redeployar el front.
- Tests: script de Node con 6 casos, visto en rojo y después verde; `npm run
  build` OK. Smoke real: `api.js` cargado con Vite desde Node contra el backend
  local, `POST /preliquidacion/generar` con quincena 17/9 → antes "Request
  failed with status code 422", ahora "La quincena debe empezar el 1 o el 16
  del mes, no el 17".
- No probado en el navegador (extensión de Chrome desconectada).
- Revisión adversarial: 0 urgent, 0 high.

**Pendiente**
- Cerrada la deuda del 422 anotada en las entradas de #49 y #50.
- Minor de la revisión, sin tocar: los 422 del propio Pydantic ("Field
  required") siguen en inglés y sin nombre de campo; `Login.jsx:48` usa axios
  directo y no pasa por este interceptor (preexistente).
- Siguen abiertos del PR #48: la clave del candado no se normaliza y la
  aserción vacía sobre `engine_propia`. Los ~16 parámetros de lectura siguen
  aceptando cualquier fecha (del PR #49).

## 2026-09-23 — Los README quedan como descripción general y los repos siguen públicos

**Mergeado**
- PR #51 (backend) — el README pasa a descripción general (qué es, stack,
  estructura por módulos, cómo levantarlo en local, dónde está la
  documentación); `docs/DEPLOY.md` sale del árbol y entra a `.gitignore`; se
  tacha el host de ADCP. Merge `66b9bf0`, commits `9666257` y `6439a5b`.
- PR #44 (frontend) — PR hermano, mismo criterio para el README del front.
  Merge `55feca3`.

**Por frontera**
- Docs: `README.md` de los dos repos reescritos (backend -268/+43, front
  -116/+31). `docs/DEPLOY.md` borrado del repo (186 líneas); queda sólo en la
  máquina de quien deploya. El nombre del host de ADCP se reemplaza por
  "servidor de ADCP" en `docs/superpowers/plans/2026-09-18-externa-timeout-y-concurrencia.md`
  y en la entrada del PR #48 de esta bitácora (el commit `6439a5b` editó esa
  línea vieja).
- Prod y Datos: `.gitignore` suma `docs/DEPLOY.md` con el comentario "viven
  sólo en la máquina de quien deploya, nunca en el repo público".

**Decisiones**
- **README sin detalle interno.** Porqué: el repo es público y el sistema es
  interno; el README viejo explicaba la mecánica de identidad y contraseña
  inicial, nombraba tablas y prefijos de las bases de terceros, describía la
  infraestructura de producción y listaba todos los endpoints, lo que no le
  sirve a quien lee el repo y le da un mapa a un tercero. La lista de endpoints
  sigue en `/docs` para quien corre el sistema. De paso se va lo desactualizado
  (el `create_all` al arrancar, sacado en el PR 3, y la base propia
  "compartida", que hoy es dedicada).
- **`docs/DEPLOY.md` fuera del repo.** Porqué: tenía IPs del VPS y del servidor
  de bases con comandos de acceso. El PR aclara que sacarlo del árbol no lo
  borra del historial. Descartado en el PR: limpiar el resto de `docs/`, por la
  misma razón (no lo saca del historial).
- **Los repos backend y frontend quedan públicos.** Decisión del usuario del
  2026-09-23, posterior al merge; cierra lo que el PR dejó "para decidir
  aparte". No está en el cuerpo del PR: la trae quien despachó esta anotación.
  Porqué: en GitHub Free la protección de ramas (`main` exige 1 aprobación) no
  se aplica en repos privados, y no se quiso pagar Pro (USD 4 por mes).
  Descartado: hacerlos privados; una organización gratuita con Pitu en sólo
  lectura trabajando desde un fork (demasiado cambio de remotes y de flujo); un
  hook local de pre-push (se saltea con `--no-verify`).

**Estado**
- Deploy: ninguno, son sólo docs. El VPS toma los cambios con el próximo pull.
- Migraciones: ninguna.
- Verificación (del PR): grep de los README nuevos sin coincidencias para CUIL,
  contraseña, dominio, hosting, IPs ni nombres de tablas externas; los archivos
  que referencian existen.
- Consecuencia de quedar públicos: en el historial de git siguen las IPs del
  VPS y del servidor de bases y los comandos SSH del `DEPLOY.md` viejo. No se
  encontraron contraseñas ni el `.env` en el historial.

**Pendiente**
- Confirmar que el VPS acepte SSH sólo con clave. No se verificó.

## 2026-09-25 — El CLAUDE.md dice dónde se anota cada cosa, y el SSH del VPS queda sólo con clave

**Mergeado**
- PR #52 (backend) — la sección "Los cuatro documentos" del `CLAUDE.md` pasa a
  ser "Dónde se anota cada cosa": una tabla única (qué pasó, archivo, cuándo) y
  cuatro reglas debajo. Suma un plan en
  `docs/superpowers/plans/2026-09-25-reglas-de-anotacion.md`. Merge `bdbd3da`,
  commit `b2ca2c2`. Sin PR hermano en el front.

**Por frontera**
- Docs: `CLAUDE.md` +25/-7. La tabla suma lo que faltaba: `docs/DEPLOY.md`
  (local, fuera de git) para todo lo operativo del VPS, el cuerpo del PR,
  `PUESTA-A-PUNTO.md`, los planes y la memoria de Claude. La regla de trabajo
  "anotar en la memoria del proyecto en cada hito" pasa a "en el lugar que
  corresponda según la tabla".
- Prod y Datos: sin cambios en el repo. El endurecimiento del SSH (abajo) se
  hizo en el VPS, no por PR.

**Decisiones**
- **Una tabla única en el `CLAUDE.md`, en vez de corregir cada skill.** Porqué:
  el usuario tenía que aclarar en cada sesión dónde anotar, y el endurecimiento
  del SSH del mismo día quedó sólo en la memoria de Claude, que vive fuera del
  repo y no la ve nadie más. La skill `flujo` es global, sirve a otro proyecto y
  nombraba `.claude/Contexto/contexto-proyecto.md`, que en este repo no existe.
  Descartado: reglas sueltas por skill.
- **Cuatro reglas bajo la tabla**: la memoria no cuenta como anotación para una
  persona; al avisar "quedó anotado" se nombra el archivo; IPs, hosts,
  credenciales y datos de terceros no entran a git porque los repos son
  públicos; si una skill manda anotar en otro lado, vale la tabla. Porqué: el
  mismo del punto anterior.
- **La skill global `flujo` remite al `CLAUDE.md` de cada repo.** Cambio fuera
  del repo; lo nombra el PR y lo confirma quien despachó esta anotación.

Lo que sigue no está en el PR: lo trae quien despachó esta anotación.
- **SSH del VPS sólo con clave**, con OK del usuario, antes del PR. Antes
  aceptaba contraseña para root por el orden en que se leen los drop-ins de
  cloud-init. Se instaló fail2ban. Probado: el ingreso con clave anda y el
  ingreso con contraseña se rechaza. El detalle operativo está en
  `docs/DEPLOY.md`, que es local y está fuera de git.
- **Se borraron las ramas remotas ya mergeadas** en los dos repos, 7 en total,
  después de verificar que ninguna tenía commits fuera de `main`.

**Estado**
- Deploy: ninguno de código; el PR es sólo docs. En el VPS cambió la
  configuración del SSH (ver arriba).
- Migraciones: ninguna.
- Verificación (del PR): existen todos los archivos que nombra la tabla;
  `docs/modulos/*/fuentes/` sigue ignorado por git; no queda ninguna regla vieja
  que contradiga la nueva (grep de "memoria" y "cuatro documentos").

**Pendiente**
- Cerrado el pendiente "Confirmar que el VPS acepte SSH sólo con clave" de la
  entrada del 2026-09-23.

## 2026-09-25 — Las reglas pasan a AGENTS.md y a controles, y la app no arranca contra producción sin permiso

**Mergeado**
- PR #53 (backend) — reorganiza el harness de agentes: controles en hooks y
  `settings.json`, `AGENTS.md` como fuente de reglas, un glosario por contexto
  con `CONTEXT-MAP.md` de índice y documentación al día sin listados de tablas.
  Merge `d0be3f4`. Plan: `docs/superpowers/plans/2026-09-25-reorganizar-harness.md`.
- PR #45 (frontend) — hermano del #53: `AGENTS.md` con el bloque común, controles
  y dos comentarios que apuntan al glosario nuevo. Merge `f885563`.
- PR #54 (backend) — la app no arranca contra la base de producción salvo que el
  `.env` tenga `PERMITIR_BASE_PRODUCCION=1`, y el banner muestra qué base se
  conectó. Merge `dad6649`.

**Por frontera**
- Núcleo: `app/core/config.py` suma `guardia_base_propia` y el campo
  `permitir_base_produccion`; la guardia corre en el `lifespan` de `app/main.py`.
  El asistente (`app/core/asistente.py`) carga el glosario del núcleo, el de
  Preliquidación y `docs/AYUDA.md`, con un test que falla si falta alguno. 9 tests
  nuevos de la guardia; la suite da 312 verdes.
- Preliquidación: sólo comentarios y docstrings, "categoría 1-7" pasa a 1-12. El
  front cambia dos comentarios.
- Prod y Datos: `deploy/provision.sh` avisa que producción necesita el permiso.
  `.env.example` pasa a `DB_PROPIA_NAME=testing` y explica cómo refrescar
  `testing` con `DB_PROPIA_*` apuntando ahí.
- Docs: `CLAUDE.md` baja a 20 líneas e importa `AGENTS.md` (en el front, 16).
  `CONTEXT.md` queda para el núcleo y nace
  `docs/modulos/preliquidacion/CONTEXT-preliquidacion.md`. `DOCUMENTACION.md` pasa
  a ser el mapa técnico. PUESTA-A-PUNTO dice que los repos son públicos y suma
  `instalar.sh`. El ADR-0008 se corrige (sin nombres de tablas, rango 1 a 12). El
  plan histórico de ws1-ws6 se mueve a `docs/superpowers/plans/`. Las skills
  `domain-modeling` y `grilling` suman pasos; `grilling` busca antecedentes en la
  bitácora y los ADR antes de preguntar.
- Controles (repo, fuera de las fronteras de código): `scripts/hooks/pre-commit`
  frena los commits en `main`; en el backend deja pasar sólo un commit que toque
  únicamente `docs/BITACORA.md`, en el front no tiene excepción.
  `.claude/settings.json` pide confirmación para `ssh`, `scp`, `sftp` y `rsync`. Un
  hook PostToolUse recuerda preguntar por `/bitacora` después de `gh pr merge`.
  `.gitattributes` fuerza LF en los `.sh`; `.gitignore` suma `CLAUDE.local.md` y
  `.claude/settings.local.json`.

**Decisiones**
- **Las reglas críticas van en hooks y permisos, no sólo en prosa.** Porqué: una
  instrucción en CLAUDE.md "es un pedido, no una garantía", según Anthropic.
  Descartado: `deny` para `ssh`/`scp`, porque el deploy legítimo existe; se usa
  `ask`.
- **El hook de bitácora usa `grep` y no `jq`, y mira sólo el comando.** Porqué:
  para no sumar dependencias en Windows; con `grep` sobre el JSON entero avisaba
  cuando un texto mencionaba el merge.
- **`AGENTS.md` es la fuente de las reglas y `CLAUDE.md` lo importa con
  `@AGENTS.md`.** Porqué: es el estándar que leen otros agentes, y a futuro puede
  usarse otro además de Claude Code. Sin symlink, por Windows. Lo de cada máquina
  (la ruta de `gh`) pasa a `CLAUDE.local.md`, fuera de git.
- **El bloque común va duplicado en los dos repos, entre marcadores, y lo compara
  `scripts/verificar_agents_comun.sh`.** Descartado: que el front remita al back,
  porque otra herramienta no sigue el puntero; e importar el del back, porque sólo
  le sirve a Claude Code.
- **Un glosario por contexto, con `CONTEXT-MAP.md` de índice.** Porqué:
  `CONTEXT.md` mezclaba el núcleo con Preliquidación, y la skill `domain-modeling`
  no encontraba el glosario de Terceros sin un mapa. Se sacaron tablas, columnas,
  endpoints, rutas y fechas, porque los repos son públicos y el glosario define qué
  es cada cosa, no cómo se implementa.
- **Los docs públicos no listan tablas; para saber qué hay, se consulta la base.**
  Porqué: decisión del usuario, con los repos públicos.
- **La app frena el arranque contra producción en vez de sólo avisar.** Porqué: el
  `.env` de desarrollo apuntaba a producción y la app sólo lee `DB_PROPIA_*`, así
  que un `uvicorn --reload` local escribía sobre el dato real. Un aviso en el
  banner no evita el error.
- **La guardia va en el `lifespan` y no en `Settings`.** Porqué: para no romper
  `pytest` ni los scripts, que importan la configuración sin arrancar la app; así
  el refresco de `testing` y `verificar_conexion.py` pueden seguir leyendo
  producción. Es la única razón por la que se aborta el arranque: una tabla
  faltante sigue sin abortarlo, para no meter a systemd en un bucle.

Lo que sigue no está en los PR: lo trae quien despachó esta anotación.
- **No se borra ninguna skill**, aunque se superpongan. Decisión del usuario.
- **`plan-terceros.md` conserva a propósito la tabla de las tablas que Pitu
  planea crear**, como excepción a "los docs no listan tablas". Decisión del
  usuario.
- **El ADR-0008 lo corrigió un agente con OK explícito del usuario.**
- **El `.env` local de Gero pasó a apuntar a `testing`**, con las credenciales de
  producción guardadas aparte para el refresco de `testing`.
- **Trampa encontrada**: la confirmación de `ssh` no funcionó en la sesión donde
  se creó el `settings.json` (había arrancado antes) y sí en sesiones nuevas; los
  hooks, en cambio, se recargaron en caliente.

**Estado**
- Deploy del backend el 2026-09-25, con OK del usuario (dato de quien despachó).
  Orden obligatorio, que el PR #54 marca como riesgo: primero la variable del
  permiso en el `.env` del VPS (el código viejo la ignora) y después el código.
  Verificado: el servicio arrancó una sola vez, sin bucle de reinicios; el banner
  muestra la base de producción; `/health` ok; sitio 200; el asistente responde
  términos de los dos glosarios (en local no se había podido probar porque el
  antivirus bloquea el HTTPS de Python).
- Front: no se deployó; sólo cambiaron comentarios.
- Migraciones: ninguna.
- Verificación (de los PR): el `pre-commit` probado con commits reales en `main` y
  en rama; la confirmación de `ssh` probada en sesiones nuevas; el hook de
  bitácora con 9 comandos simulados; los 47 términos del glosario viejo están en
  los dos nuevos; con el `.env` de producción sin permiso, `uvicorn` se niega a
  arrancar (exit 3) antes de abrir conexiones; contra `testing` arranca y
  `/health` da ok. `npm run build` compila en el front.

**Pendiente**
- Correr `sh scripts/hooks/instalar.sh` en cada clon, también los de Pitu.
- Aceptados sin arreglar (dato de quien despachó; los lista el PR #53): el hook de
  bitácora avisa si `gh pr merge` aparece al principio de una línea dentro de un
  heredoc, y también si el merge falla o sólo queda programado con `--auto`. Lo
  peor que pasa es una pregunta de más.
