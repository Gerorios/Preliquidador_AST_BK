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

## 2026-09-29 — ADR-0014: se desarrolla contra testing y sólo el VPS toca producción

**Mergeado**
- PR #55 (backend) — ADR-0014, que registra la decisión implementada en el PR #54;
  `AGENTS.md`, `DOCUMENTACION.md` y `GUIA-MODULOS.md` se alinean con él.

**Por frontera**
- Docs: nuevo `docs/adr/0014-desarrollo-en-testing-produccion-solo-desde-el-vps.md`.
  `AGENTS.md` cita el ADR y la guardia de arranque (`PERMITIR_BASE_PRODUCCION=1`, sólo
  en el `.env` del VPS); `DOCUMENTACION.md` deja de fijar el rango de ADR ("numeradas en
  orden"); `GUIA-MODULOS.md` pasa el próximo número a 0015.

**Decisiones**
- **La regla "desarrollo en `testing`, producción sólo desde el VPS" se hace cumplir con
  código y no con una instrucción escrita.** Porqué: la app lee una sola conexión propia,
  y un `.env` de desarrollo apuntando a producción hacía que un arranque local escribiera
  sobre el dato real. Descartado: la base única; el aviso en el banner como única medida
  (se conserva como complemento); la guardia en `Settings`, porque rompía tests y scripts.
- Lo que sigue no está en el PR: lo trae quien despachó esta anotación. El ADR formaliza
  una decisión ya tomada e implementada en el PR #54, no una nueva. El usuario eligió
  cerrar este PR de documentación antes de arrancar un plan de 7 puntos de seguridad y
  calidad surgido de un relevamiento del proyecto. Desde este merge, los merges los hace
  el agente pidiendo confirmación al usuario.

**Estado**
- Deploy: ninguno (sólo documentación).
- Migraciones: ninguna.

**Pendiente**
- El plan de 7 puntos de seguridad y calidad, todavía sin arrancar.

## 2026-09-29 — Plan de seguridad, PR 1: errores sin detalle interno, PyJWT y límite de login

**Mergeado**
- PR #56 (backend) — primer PR (de 6) del plan de seguridad y calidad: 500 genérico con
  código, `/health` sin textos, PyJWT en lugar de `python-jose`, `quote_plus` en las URLs
  de conexión, límite de intentos de login; entra además el plan
  `docs/superpowers/plans/2026-09-29-seguridad-y-calidad-relevamiento.md`. Sin PR hermano
  en el front.

**Por frontera**
- Núcleo: handler global en `app/main.py` que devuelve un 500 genérico con un código de 6
  caracteres y manda detalle y traceback al log (`app.errores`) con el mismo código.
  `/health` devuelve sólo `status` y un booleano por base; errores y tablas faltantes van
  al log (`app.health`). `auth.py` pasa a PyJWT; los tokens HS256 ya emitidos siguen
  valiendo. Nuevo `app/core/limite_login.py`: 5 fallos en 15 minutos por identificador
  normalizado (mail, email sintético o CUIL) dan 429 con `Retry-After` por 15 minutos; en
  memoria, chequeado antes del bcrypt, cuenta también usuarios inexistentes y un login
  correcto lo resetea. `utcnow()` sale: columnas con `ahora_utc()` (naive-UTC, mismos
  valores que antes) y `exp` del JWT aware. `config.py` aplica `quote_plus` a la
  contraseña de `url_externa` y `url_propia`, como ya hacía `url_sueldos`.
  `requirements.txt`: entra `PyJWT==2.15.1`, salen `python-jose` y `alembic`.
- Preliquidación: se borran los `except Exception → HTTPException(500, str(e))` de la
  API (15, según el PR); los mensajes de negocio (`ValueError`, 503, 409) no
  cambian. Se borra `POST /{id}/backfill-conceptos`, que llamaba a un método inexistente
  (siempre 500) y el front no usaba. Los modelos del módulo pasan a `ahora_utc()`.
- Docs: `README.md` y `GUIA-MODULOS.md` dejan de mencionar Alembic y nombran PyJWT; entra
  el plan de 6 PRs.

**Decisiones**
- **El alta de conceptos pierde su `try/except` en vez de devolver "ya existe".** Porqué:
  `uq_concepto_unif` nunca se dispara por la API, porque cliente o supervisor van siempre
  en NULL (ADR-0011), así que ese mensaje describiría un caso que no ocurre. Según quien
  despachó, fue la opción B que eligió el usuario durante la ejecución.
- **Límite de login por identificador y no por IP.** Porqué: toda una oficina sale por la
  misma IP. Descartado: `slowapi`/Redis, una dependencia nueva para un solo worker.
- **PyJWT en lugar de `python-jose`, y fuera `alembic`.** Porqué: `python-jose` tiene
  mantenimiento irregular y CVE-2024-33663/33664; `alembic` no se usaba. Según quien
  despachó, las dos cosas las aprobó el usuario en la entrevista.
- **Fechas naive-UTC en columnas y sólo el `exp` del JWT aware.** Porqué (del commit):
  no mezclar objetos aware y naive en la misma sesión.
- **El PR 2 del plan cambió de diseño a pedido del usuario:** no se crea ninguna tabla
  nueva en la base; sólo un manifiesto de migraciones y un chequeo de tablas y columnas
  faltantes al arrancar. Porqué (del plan): el riesgo es deployar código que necesita una
  columna que la base no tiene, y eso se detecta comparando el modelo con el esquema real.
  Descartados: la tabla de registro `migracion_aplicada` (el usuario no quiere tablas
  nuevas para esto) y el registro en un archivo fuera de la base (se desincroniza).
- Lo que sigue lo trae quien despachó: la ejecución fue por pares test rojo →
  implementación con el agente ejecutor.

**Estado**
- Deploy: no se hizo. Necesita `pip install -r requirements.txt` antes del restart (si
  falla, no reiniciar). PyJWT avisa si la `SECRET_KEY` tiene menos de 32 bytes; alargarla
  corta las sesiones abiertas. Rollback: revert del merge, `pip install` y restart.
- Migraciones: ninguna.
- Verificación (del PR): 352 tests en verde, cada paso con test rojo antes; revisión con
  0 urgent y 0 high; smoke contra `testing` con las tres bases OK, `/health` ok, 6 logins
  malos dan 5×401 y un 429 con `Retry-After: 900`, token inválido da 401, sin tracebacks.
  No probado: login con usuario real y navegación en el front.

**Pendiente**
- Deploy del backend (con OK del usuario).
- PRs 2 a 6 del plan.
- Hallazgo fuera de alcance que anota el PR: hoy se pueden cargar conceptos duplicados.
- Minor aceptados sin tocar (los lista el PR): 4 tests de endpoints del módulo quedaron en
  `tests/core/`; la fixture SQLite en memoria se repite en 5 archivos; `limite_login.py`
  lee una tupla por índice; el 429 dice "1 minutos" en el último minuto.

## 2026-09-30 — Plan de seguridad, PR 2: chequeo de tablas y columnas al arrancar y ORDEN.txt

**Mergeado**
- PR #57 (backend) — al arrancar, la app compara los modelos con la base propia y avisa
  si faltan tablas o columnas; entra `migrations/ORDEN.txt` con el orden de las 18
  migraciones. PR 2 de 6 del plan
  `docs/superpowers/plans/2026-09-29-seguridad-y-calidad-relevamiento.md`. Sin PR hermano
  en el front.

**Por frontera**
- Núcleo: nuevo `app/core/esquema.py` con `comparar_esquema(metadata, inspector)`, que
  detecta tablas y columnas del modelo que faltan en la base propia; columnas de más en la
  base no son error, y no compara tipos ni índices. Recibe el metadata por parámetro, así
  el núcleo no importa módulos (ADR-0013). En `app/main.py` el banner de arranque dice
  `ERROR: faltan tablas/columnas en la base propia (migraciones sin aplicar): ...` o
  `Tablas y columnas BD propia: verificadas`, y nunca aborta. Si el chequeo mismo falla,
  el banner avisa "no se pudo verificar" y el traceback va al log (`app.esquema`).
  `/health` da `status: "error"` si falta algo, sin nombres: sigue con sólo `status` y
  booleanos. Corrige lo anotado para el PR #56: los nombres de lo faltante ya no van al
  log de `app.health`, que ahora sólo remite al banner. stdout pasa a `line_buffering`.
- Prod y Datos: nuevo `migrations/ORDEN.txt`, orden explícito de todas las migraciones.
  ws1..ws16 y `fix_trazabilidad` van marcadas `historica`: ya están dentro de
  `000_esquema_base.sql` (exportado de producción) y fallan en una base nueva. Un test
  exige que cada `.sql` figure una sola vez, que no haya entradas inexistentes, que
  `historica` sea la única marca y que ninguna histórica vaya antes del 000. El orden
  ws5 → fix → ws7 sale de `git log`.
- Docs: `GUIA-MODULOS.md` §3.2, §3.3 y reglas 10 y 12 de §4.3 (toda migración nueva se
  agrega al final de `ORDEN.txt` en el mismo PR; qué dice el banner después del deploy);
  `README.md`; `migrations/terceros/LEEME.md`; el plan anota la opción A y el paso R1.

**Decisiones**
- **Sin tabla de registro de migraciones, sin script de aplicación y sin ADR.** Porqué:
  el usuario no quiere tablas nuevas para esto, y comparar el modelo con el esquema real
  detecta el caso que importa (código deployado sin su migración). Descartado: un
  registro en un archivo fuera de la base, que se desincroniza de la base real.
- **Si el chequeo mismo falla, `/health` no marca error** (opción A, elegida por el
  usuario). Porqué: no confundir un fallo del chequeo con migraciones faltantes; un
  problema de conexión ya se ve en `bd_propia`. Descartado: marcar `status: "error"`
  también en ese caso.
- **No abortar el arranque si falta algo.** Porqué: systemd entraría en bucle de
  reinicios.
- **No comparar tipos ni índices.** Porqué: darían falsos positivos entre MySQL y el ORM.
- **La regla nueva se sumó a las reglas 10 y 12 de la guía en vez de crear una 13.**
  Porqué: no renumerar reglas que se citan por número.
- **stdout con `line_buffering` (paso R1).** Porqué: bajo systemd stdout es un pipe y el
  banner, único lugar con los nombres faltantes, no llegaba al journal hasta el siguiente
  restart. Salió como high de la revisión y, según quien despachó, se arregló sin consultar
  al usuario, como manda el flujo para un high.

**Estado**
- Deploy: no se hizo. Según quien despachó, conviene deployarlo junto con el PR #56 (que
  necesita `pip install -r requirements.txt` antes del restart). Tras el restart, el
  journal tiene que mostrar `Tablas y columnas BD propia: verificadas`; si muestra
  `ERROR: faltan ...`, es una migración sin aplicar en producción: frenar y revisar antes
  de tocar nada. Rollback: revert del merge y restart.
- Migraciones: ninguna (sin DDL).
- Verificación (del PR): 364 tests en verde, y los 9 tocados por R1 en verde; cada paso
  con test rojo antes. Revisión con 0 urgent y 1 high (arreglado como R1). Smoke contra
  `testing` con stdout redirigido a archivo, como bajo systemd: el banner se leyó con el
  proceso vivo y dijo `verificadas`; `/health` dio `ok` con las tres bases en `true`.

**Pendiente**
- Deploy de los PRs #56 y #57 (con OK del usuario).
- Actualizar `docs/DEPLOY.md` (fuera de git): qué devuelve `/health` y que el orden de una
  base nueva lo da `ORDEN.txt`.
- PRs 3 a 6 del plan.
- Minor aceptados sin tocar (los lista el PR): `bool(tablas or columnas)` en `main.py`
  sería mejor como propiedad de `Diferencias`; "(migraciones sin aplicar)" repetido en
  banner y log; fixtures SQLite duplicadas entre `test_esquema.py` y
  `test_health_tablas.py`; el nombre de `test_health_tablas.py` ya no refleja que prueba
  también el arranque; el docstring de `test_esquema.py` cita "(PR2, paso 2.1)";
  `test_manifiesto_migraciones.py` tiene `BASE` ambiguo, `_entradas()` llamado dos veces y
  `MARCAS_VALIDAS` de un elemento.

## 2026-09-30 — Plan de seguridad, PR 3: tests de caracterización del servicio de Preliquidación

**Mergeado**
- PR #58 (backend) — tests de caracterización para los métodos y endpoints de
  Preliquidación sin cobertura; los bugs que destaparon quedan como xfail estricto. Sólo
  tests, no toca `app/`. Sin PR hermano en el front.

**Por frontera**
- Preliquidación: seis archivos nuevos en `tests/preliquidacion/` y uno ampliado. Cubren
  `listar_lineas`, `actualizar_linea` (auditoría en `AjusteManual`),
  `legajos_disponibles_de_linea`, `agregar_concepto`, `agregar_concepto_por_codigo`,
  `agregar_concepto_masivo`, `eliminar_concepto_masivo` y sus endpoints,
  `heredar_categorias_operario`, `recalcular_por_categoria`, `dashboard_verificacion`
  (excesos y resumen por empleado), `set_valor_hora_pulv` (en
  `test_control_tancadas_jornal.py`) y los endpoints `legajos-por-cuil` y
  `conceptos/buscar`. Quedan fijados tal como están algunos comportamientos raros: la
  auditoría de `actualizar_linea` guarda el texto `"None"` si el campo estaba vacío;
  `alerta_legajo` se apaga aunque la empresa enviada sea la misma; `agregar_concepto`
  recalcula `importe_total` desde los conceptos; un concepto agregado por código queda
  como manual (sobrevive a una regeneración); en Verificación, las personas sin legajo ni
  fecha se suman en un solo grupo.
- Docs: el plan `2026-09-29-seguridad-y-calidad-relevamiento.md` anota lo decidido en
  ejecución para el PR 3 (pasos 3.3, 3.5 y 3.7, y la regla de xfail).

**Decisiones**
- **Los bugs que destapan los tests quedan en la suite como
  `xfail(strict=True, raises=<excepción exacta>)`**, decidido por el usuario en ejecución.
  Porqué: siguen visibles y, el día del fix, el test pasa a XPASS y obliga a actualizarlo.
  Descartado: dejarlos fuera y anotarlos sólo en el PR (se pierden). Los arreglos van en
  una tarea aparte, con su propio plan.
- **Agrupar Verificación sólo por número de legajo es un bug**, decidido por el usuario.
  Porqué: el par empresa+legajo es el único (CONTEXT.md), así que dos personas con el
  mismo legajo en empresas distintas se suman: exceso falso y una sola fila en el resumen.
  Queda como xfail.
- **Heredar categorías desde la quincena anterior más reciente con asignaciones es
  correcto**, confirmado por el usuario. Se fija como comportamiento, no como bug. Porqué
  no registrado en el PR.
- **El xfail de `eliminar_concepto_masivo` es de entorno, no de producción.** Porqué:
  `IN :ids` con tupla funciona con pymysql (la interpola como `(1,2)`) y SQLite no la
  acepta. Se verificó renderizando con el dialecto MySQL, no contra un MySQL real.

**Bugs fijados como xfail (4 en la suite)**
- `agregar_concepto_por_codigo` con una regla sin precio en la quincena: `IndexError` y el
  endpoint da 500. `agregar_concepto_masivo` tiene lo mismo.
- `eliminar_concepto_masivo` (dos tests): el de entorno de arriba.
- `dashboard_verificacion` agrupa sólo por legajo.

**Estado**
- Deploy: no aplica (sólo tests). Rollback: revert del merge.
- Migraciones: ninguna.
- Verificación (del PR): `python -m pytest -q` con 437 passed y 4 xfailed; en cada paso se
  alteró un assert a propósito y el test falló. Revisión con 0 urgent y 0 high; el
  verificador confirmó que ningún test pasa con el código roto ni falla al azar.

**Pendiente**
- Tarea aparte de arreglos, con su propio plan: ofrecida al usuario, sin arrancar. Cuatro
  bugs: el `IndexError` de concepto por código y masivo, el `IN :ids` (pasar a
  `bindparam(expanding=True)`), la agrupación de Verificación por legajo y, con prioridad
  por decisión del usuario, el combo de `GET /conceptos/buscar`: aplica `limit(200)` antes
  de deduplicar y el front lo pide sin quincena, así que pierde códigos (en `testing`, 36
  códigos y el combo muestra 30; empeora con cada quincena). Este último no tiene test.
- Deploy de los PRs #56 y #57 (con OK del usuario), que sigue abierto.
- PRs 4 a 6 del plan.
- Minor aceptados sin tocar (los lista el PR): 4 tests de `test_dashboard_verificacion.py`
  dependen del orden de inserción (la query no tiene `order_by`); el xfail de legajos
  tiene dos asserts y sólo avisa cuando se arreglan excesos y resumen a la vez;
  `_con_service` en `test_endpoints_lineas.py` está fuera de un fixture; docstrings que
  citan pasos del plan.

## 2026-09-30 — Plan de seguridad, PR 4: mensualizados por CUIL desde el .env del servidor

**Mergeado**
- PR #60 (backend) — la lista de mensualizados sale del código y pasa a la variable
  `EMPLEADOS_MENSUALIZADOS_CUIL` del `.env` del servidor; cada línea trae `mensualizado`.
- PR #47 (frontend, hermano) — Verificación filtra con `!l.mensualizado` y deja de tener
  la lista de nombres en el código.

**Por frontera**
- Preliquidación: nuevo `app/modulos/preliquidacion/config.py` (`ConfigPreliquidacion`,
  `cuils_mensualizados()`, `es_mensualizado()`); un valor inválido en la variable se
  ignora con un aviso en el log, no aborta. `filtro_no_mensualizado()` reemplaza el filtro
  por nombre en los tres controles del servicio (Plantas/Tancadas vs Jornal) y en los
  cuatro KPIs de Gerencial; líneas sin CUIL no se excluyen y con la lista vacía el filtro
  no agrega condición. `GET /api/preliquidacion/{id}/lineas` trae `mensualizado: bool`
  (propiedad del modelo, default `False` en `LineaResponse`). En el front,
  `Verificacion.jsx` filtra por ese campo y pierde un `useEffect` importado sin uso.
- Prod y Datos: `.env.example` suma `EMPLEADOS_MENSUALIZADOS_CUIL` vacía (vacío = nadie).
- Docs: `DOCUMENTACION.md` y `CONTEXT-preliquidacion.md` dicen qué es un mensualizado
  (configuración del servidor, por CUIL); nota de una línea al ADR-0012, que citaba la
  constante borrada, aclarando que su decisión no cambia.

**Decisiones**
- **Por CUIL y no por nombre.** Porqué: el nombre cambia de formato entre sistemas y es un
  dato personal en un repo público.
- **En el módulo y no en el núcleo.** Porqué: lo usa un solo módulo (ADR-0013).
- **El campo viaja en la línea.** Porqué: así el front no guarda datos de personas.
  Descartado: una tabla con pantalla de administración (demasiado para dos personas);
  dejar la lista en el código.
- **La diferencia de normalización queda como minor**, decidido por el usuario en la
  revisión: la propiedad `mensualizado` normaliza guiones y el filtro SQL sólo hace
  `TRIM`, así que con un `cuit` con guiones en la base darían distinto. Porqué: hoy no
  pasa, el `cuit` viene como 11 dígitos sin guiones (verificado en `testing`).
- **Nota de una línea al ADR-0012**, decidido por el usuario en la revisión, en vez de
  dejarlo citando una constante que ya no existe.

**Estado**
- Deploy: no.
- Migraciones: ninguna.
- Verificación (del PR): `python -m pytest -q` con 460 passed y 4 xfailed; revisión en los
  dos repos con 0 urgent y 0 high. Smoke contra `testing` con los CUIL cargados sólo
  durante la prueba: todas las líneas de las dos personas marcadas, ninguna ajena marcada
  por error, y el filtro nuevo deja las mismas líneas que el viejo por nombre. El front
  compila. No probado: Verificación en el navegador. Los nombres de la lista vieja siguen
  en el historial de git de los dos repos (no se reescribe).

**Pendiente**
- Deploy, con OK del usuario y en este orden obligatorio: (1) agregar
  `EMPLEADOS_MENSUALIZADOS_CUIL` al `.env` del VPS (sin ella nadie queda mensualizado y
  esas personas vuelven a los controles y a Gerencial); (2) backend (el front viejo sigue
  andando: filtra por nombre e ignora el campo); (3) frontend (contra un backend viejo no
  filtra nada). Rollback: revert + restart en el back, swap a `frontend_old` en el front.
- Minor aceptados sin tocar (los lista el PR): comentarios que citan pasos del plan;
  `CUIL_MENSUALIZADO` y el fixture `mensualizado` repetidos en tres archivos de test;
  `test_mensualizados_config.py` importa `filtro_no_mensualizado` dentro de cada test.
- PRs 5 y 6 del plan.

## 2026-09-30 — Liquidación Terceros: etapas 1 a 10, cuotas y mover de quincena

**Mergeado**
- PR #59 (backend) — módulo Liquidación Terceros de la etapa 1 a la 10 del plan, más mover
  hechos de quincena y repartir repuestos en cuotas. Reemplaza el Excel de 19 hojas con el
  que hoy se liquida a los terceros. Trabajo de otro desarrollador del equipo.
- PR #46 (frontend, hermano) — pantallas del módulo: Inicio (tablero de quincenas),
  Quincena, Tarifario, Estaciones y Verificaciones, más los diálogos de mover de quincena
  y de cuotas.

**Por frontera**
- Liquidación Terceros: el módulo pasa a `activo=True` (deja de ser molde). Servicios
  nuevos en `app/modulos/terceros/services/`: consultas de origen, alertas de cruce, horas
  de taller, generar y actualizar la quincena, tarifario, cálculo del neto, grilla,
  verificaciones, estaciones de servicio y destino (mover de quincena). Scripts
  `importar_tarifas_del_excel.py` y `validar_terceros_etapa1.py`. En el front, la Quincena
  es el molde de las pantallas y la lógica de filtros encadenados vive en `filtrar.js`.
- Núcleo: `app/core/config.py` suma `taller_sheet_url` (vacío = la consulta de horas
  avisa que falta, sin romper el arranque); `tests/core/test_registro_modulos.py` se
  ajusta al módulo activo.
- Prod y Datos: siete migraciones nuevas, `migrations/terceros/001` a `007`, todas con
  prefijo `terceros_` y sin tocar tablas existentes, registradas en `migrations/ORDEN.txt`
  **sin** la marca `historica`. Dependencia nueva aprobada: `xlrd` (sólo para el `.xls` de
  Excel 97 de una estación). `.env.example` suma `TALLER_SHEET_URL`.
- Docs: `CONTEXT-terceros.md` y `plan-terceros.md` ampliados; nuevos
  `docs/modulos/taller/ESPECIFICACION-taller.md`, `docs/modulos/taller/fuentes/LEEME.md` y
  `docs/modulos/terceros/historial-conversaciones-previas.md`; `GUIA-MODULOS.md` dice que
  Terceros está activo y en construcción; `PUESTA-A-PUNTO.md` explica `TALLER_SHEET_URL`.

**Decisiones** (del cuerpo de los PR; cada commit del BK #59 trae además su porqué)
- **Las consultas de origen se traen tal cual del Excel.** Porqué: para poder validarlas
  contra él (07-2Q y 08-1Q coinciden fila por fila).
- **Sólo se alerta de lo accionable**, y cada alerta dice en qué sistema se corrige.
  Porqué no registrado en el PR.
- **Dos servicios de maquinaria**: la máquina del tercero trabaja (se le paga) o se repara
  (se le descuenta). La hora de jornal no se paga nunca. Porqué no registrado en el PR.
- **Actualizar la quincena reconcilia por clave en vez de rehacer**, como Preliquidación.
  Porqué: no pisa lo cargado a mano.
- **Tarifario por quincena: gana la regla más específica y el empate queda ambiguo.**
  Porqué: el módulo nunca elige un precio en silencio.
- **El neto cierra en dos cifras**: Total a facturar y, restándole los seguros, Total a
  pagar; siete estados con nombre en vez de un importe en cero. Porqué no registrado en
  el PR.
- **Verificaciones**: duplicados con la misma clave que la reconciliación, agrupados por el
  sistema donde se corrigen. Porqué no registrado en el PR.
- **Estaciones**: el mapeo de cada archivo vive en la base y no en el código. Cruce por
  vale, por patente y litros con dos días de tolerancia, y por patente a un carácter sólo
  si la del archivo no es de ningún colectivo. Porqué no registrado en el PR.
- **Un hecho movido de quincena se cobra con el tarifario de la quincena en que se
  generó.** Porqué: moverlo cambia cuándo, no cuánto.
- **Cuotas quincenales e iguales, con el importe escrito y no derivado.** Porqué no
  registrado en el PR.
- **Datos personales**: antes de publicar la rama se reescribió su historial (nunca se
  había publicado) para sacar la IP del servidor de las bases, mails personales y nombres
  reales de terceros; en tests y documentos son inventados, siempre el mismo por persona.
  Porqué: el repo es público.
- **Front: la Quincena es el molde de todas las pantallas.** Porqué: en Estaciones una
  tabla por problema obligaba a elegir cuál mirar antes de saber qué se buscaba.
- **Front: los filtros encadenan y su lógica vive en `filtrar.js`.** Porqué: estaba
  copiada en cuatro pantallas y alguna iba a quedar sin encadenar.
- **Front: al cargar una tarifa, nada tildado es «cualquiera»** (alcanza a lo que
  aparezca mañana) **y todos tildados es una regla por cada uno.** Porqué: así un capataz
  nuevo no cobra un precio que nadie le pactó.
- **Front: sin leyendas explicativas en pantalla**; las dos que avisaban algo que cambia
  lo que pasa pasaron a la ayuda del botón. Porqué no registrado en el PR.
- **Front: mover de quincena y cuotas se editan en un diálogo.** Porqué: la tabla es más
  ancha que la pantalla y el formulario quedaba lejos del botón.
- **El conflicto de `.env.example` con `main`** (las dos ramas agregaban una variable al
  final: `TALLER_SHEET_URL` y `EMPLEADOS_MENSUALIZADOS_CUIL`) se resolvió, a pedido del
  usuario, con un commit de merge en la rama del PR (c15b4f7) que deja los dos bloques.
- **Se mergeó sin pasar por la revisión de código de dos ejes**, por decisión del usuario.
  Porqué no registrado en el PR.

**Estado**
- Deploy: no.
- Migraciones: `terceros/001` a `007` traen DDL, a aplicar en testing y producción con el
  deploy. El PR dice que se aplicaron y probaron en `testing` durante el desarrollo, y
  que en producción no existe ninguna tabla `terceros_`.
- Verificación: el PR informa `pytest` con 688 en verde, arranque contra `testing` con el
  chequeo de esquema confirmando tablas y columnas, y pruebas por HTTP contra `testing`
  con datos reales de agosto (cruce de estaciones, mover un viaje conservando su precio,
  un repuesto repartido en tres cuotas que suman exacto). Después del merge de `main`
  (c15b4f7), la suite con todo mezclado dio 783 passed y 4 xfailed. El FT #46 no tenía
  conflictos y compiló; cada pantalla la revisó el usuario contra agosto en `testing`. No
  probados de punta a punta en el navegador: los diálogos de mover de quincena y de
  cuotas.

**Pendiente**
- Deploy, con OK del usuario: migraciones `terceros/001` a `007` en testing y producción;
  `TALLER_SHEET_URL` en el `.env` del VPS (la URL la entrega el usuario); instalar `xlrd`;
  backend y después frontend (el FT #46 no tiene de dónde leer sin los endpoints y las
  migraciones del BK #59). Con el deploy el módulo queda activo en producción. Se suma al
  deploy pendiente del PR 4, que también necesita su variable en el `.env` del VPS.
- La aceptación de la etapa 7: que agosto dé igual que la liquidación hecha a mano.
  Faltan precios de horas de servicio y definir quién aprueba las horas de taller; está
  en el plan.
- El desarrollador de Terceros tiene que hacer `git pull` en su rama, que ahora tiene el
  merge c15b4f7.
- La revisión de código de dos ejes sobre este PR, que no se hizo.

## 2026-09-30 — Plan de seguridad, PR 5: ESLint con reglas de hooks en el front

**Mergeado**
- PR #48 (frontend) — ESLint 9 con las reglas de hooks, script `npm run lint`, y cada
  warning de hooks de Preliquidación corregido a mano. Sin PR hermano en el backend.

**Por frontera**
- Preliquidación (front): `eslint.config.js` nuevo (flat config: `@eslint/js`
  recommended, `eslint-plugin-react-hooks` con `rules-of-hooks` en error y
  `exhaustive-deps` en warn, `globals`; `no-unused-vars` ignora nombres con mayúscula o
  `_` porque, sin `eslint-plugin-react`, no ve el uso en JSX). Dependencias de desarrollo
  nuevas: `eslint` 9.39.5, `@eslint/js` 9.39.5, `eslint-plugin-react-hooks` 7.1.1,
  `globals` 17.12.0 (hay que pedir `@eslint/js@^9`: sin eso baja la 10, que pide eslint
  10). Código muerto fuera: la prop `mutCrear` de `FilaFaltante` (Conceptos) y
  `TIPOS_CONCEPTO` (PanelLinea). Correcciones: `InputBusqueda` (debounce con
  `onChangeRef`; el borrado externo compara contra el `value` anterior guardado en un ref),
  `PanelLinea` (el reset por cambio de línea queda en `[linea.id]` con el lint silenciado;
  el dedup de conceptos optimistas suma la dependencia con un guard que devuelve la misma
  referencia), `Revision` (sale `lineas` de un `useMemo` que no la leía), `Verificacion`
  (`filtrarBusqueda` pasa a función pura fuera del componente) y `FiltrosBar` (queda como
  estaba, con el lint silenciado y su porqué en un comentario).
- Liquidación Terceros (front): sin cambios; el lint le marca 5 warnings (ver Pendiente).
- Docs (front): `npm run lint` en el README ("Puesta en marcha") y en `AGENTS.md`
  ("Comandos"), como paso antes de un PR.

**Decisiones**
- **Cada warning se razonó a mano, uno por uno.** Porqué: en pantallas sin tests, agregar
  dependencias mecánicamente puede dejar un input que no tipea o un refetch en bucle.
  Descartado: Prettier (reformatearía todo el repo) y el lint en el pre-commit.
- **`FiltrosBar` queda como estaba.** El paso del plan (agregar `busqueda` a las
  dependencias) estaba mal: lo detectó el agente ejecutor, frenó, y el usuario eligió
  dejar el comportamiento como estaba. Porqué: con ese cambio el buscador de Verificación
  se borraba 200 ms después de cada tecla.
- **`PanelLinea` resetea sólo por cambio de línea.** Porqué: un refetch pisaría lo que se
  está editando. El guard del dedup, porque sin él entra en bucle infinito. Descartado
  (queda como alternativa no hecha): montar `<PanelLinea key={linea.id}>` y resetear por
  remount.
- **`InputBusqueda` guarda el `value` anterior en un ref.** Porqué: agregar `texto` a las
  dependencias borraba lo que se tipea.
- **Los archivos de Liquidación Terceros no se tocan**, por decisión del usuario. Porqué
  (del PR): cada warning se revisa a mano y agregar la dependencia puede no ser lo
  correcto.
- **Sin `eslint-plugin-react`.** Porqué no registrado en el PR.

**Estado**
- Deploy: no.
- Migraciones: ninguna.
- Verificación (del PR): `npm run lint` con 0 errores y 5 warnings, todos en Terceros;
  `npm run build` verde. Prueba manual del usuario en el navegador contra `testing`:
  Verificación (tipear y esperar sin que se borre, limpiar, contadores por sección),
  Revisión (buscador; editar sin guardar y agregar concepto sin que se pise ni se duplique;
  cambiar de línea; liquidación por persona), Conceptos (filtro del panel de precios),
  Mantenimiento, Gerencial y logout; sin errores de la app en la consola. Revisión de
  código: 0 urgent, 1 high (faltaba `npm run lint` en README y `AGENTS.md`, arreglado).

**Pendiente**
- **Para el usuario, dueño del proyecto, y para el desarrollador de Liquidación
  Terceros**: los 5 warnings de `react-hooks/exhaustive-deps` que quedaron sin tocar, a
  revisar uno por uno:
  - `src/modulos/terceros/components/FiltroMultiple.jsx:51` (falta `mostrar`)
  - `src/modulos/terceros/pages/Grilla.jsx:131` (falta `pasaTercero`)
  - `src/modulos/terceros/pages/Grilla.jsx:150` (falta `pasa`)
  - `src/modulos/terceros/pages/Grilla.jsx:184` (falta `pasaTercero`)
  - `src/modulos/terceros/pages/Grilla.jsx:188` (falta `pasa`)
- El checkout principal del front necesita `npm install` para tener eslint.
- La regla 24 de `GUIA-MODULOS.md` (`npm run lint` antes de un PR), en un PR de docs del
  backend.
- Deploy, con OK del usuario: sólo frontend (`npm run build` y swap de carpeta; sin
  cambios de contrato con el backend).
- Minor sin tocar (los lista el PR): `onChangeRef.current = onChange` se asigna durante el
  render en `InputBusqueda` (para endurecerlo, en un `useLayoutEffect`); un comentario
  suelto en `PanelLinea.jsx:6`; el comentario del lint silenciado en `FiltrosBar` nombra a
  Verificación.
- Tarea aparte ofrecida: `scripts/verificar_agents_comun.sh` no compara nada cuando se
  corre desde un worktree, porque reconoce el repo por el nombre de la carpeta.
- PR 6 del plan.

## 2026-09-30 — Plan de seguridad, PR 5: `npm run lint` entra en los chequeos antes de un PR

**Mergeado**
- PR #61 (backend) — la regla 24 de `GUIA-MODULOS.md` suma `npm run lint` sin errores a
  los chequeos antes de abrir un PR; cierra el PR 5 del plan. PR hermano ya mergeado: el
  FT #48, que trajo el lint.

**Por frontera**
- Docs: regla 24 y lista de "Tests y build" de §6.1 en `GUIA-MODULOS.md`; la misma línea
  en "Antes de abrir un PR" de `PUESTA-A-PUNTO.md`. El plan
  (`docs/superpowers/plans/2026-09-29-seguridad-y-calidad-relevamiento.md`) registra lo
  decidido al ejecutar el PR 5: el comando de instalación con `@eslint/js@^9`, la
  corrección de `FiltrosBar` y los 5 warnings de Terceros como pendientes.

**Decisiones**
- **La regla va en un PR aparte, después del lint.** Porqué: la guía vive en el backend y
  el lint en el front; mergeada antes, pedía un comando que no existía.

**Estado**
- Deploy: nada que deployar.
- Migraciones: ninguna.

**Pendiente**
- Queda cerrado el pendiente "regla 24 de `GUIA-MODULOS.md`" de la entrada del FT #48.
- PR 6 del plan.

## 2026-09-30 — Plan de seguridad, PR 6: caché compartido entre pantallas y logout que lo vacía

**Mergeado**
- PR #49 (frontend) — las pantallas de Preliquidación comparten las claves de React Query
  y el logout vacía el caché; cierra el PR 6, el último del plan.
- PR #62 (backend) — notas de ejecución del PR 6 en el plan.

**Por frontera**
- Preliquidación (front): claves centralizadas en
  `src/modulos/preliquidacion/services/claves.js` (`preliquidaciones`, `lineas(id)`,
  `stats(id)` y los prefijos `todasLasLineas`/`todasLasStats`; `Number(id)` normaliza el
  id). Una sola lista de preliquidaciones para Dashboard, Conceptos, Revisión (ahora un
  `select` sobre la lista), Verificación y Categorías; generar o actualizar en el
  Dashboard invalida también líneas y estadísticas. Verificación y Revisión comparten las
  líneas, y las invalidaciones de Conceptos alcanzan ahora a Verificación. En "Sin
  concepto" cada fila se identifica por tarea, cliente y finca en vez de por su posición,
  y los cuatro radios de alcance usan esa clave.
- Núcleo (front): `src/core/queryClient.js` exporta la instancia; `authStore.logout`
  cancela y vacía el caché antes de limpiar el token, un solo lugar para Layout, Inicio,
  Login y el 401. El interceptor de 401 sólo actúa si todavía hay token.
- Docs: el plan (`docs/superpowers/plans/2026-09-29-seguridad-y-calidad-relevamiento.md`)
  registra los ajustes del PR 6: los números de línea de 6.2 y 6.3 se corrieron, las
  estadísticas de Revisión también pasan a `claves.stats(id)`, y la corrección del 6.5.

**Decisiones**
- **Claves compartidas en un solo archivo.** Porqué: con claves escritas a mano, las
  pantallas guardaban el mismo dato en cachés distintas, y generar una quincena o cambiar
  un precio no llegaba a las otras pantallas hasta el F5.
- **El logout vacía el caché en un solo lugar (`authStore`).** Porqué: evita que un camino
  se olvide de vaciarlo y otro usuario vea datos del anterior. Descartado: un helper
  `cerrarSesion()` llamado desde cuatro lugares.
- **El 401 sólo redirige si todavía hay token.** Porqué: varios 401 simultáneos, una sola
  redirección.
- **"Sin concepto" con clave estable por fila.** Porqué: con la posición como key, al crear
  una regla la fila siguiente heredaba el estado de la que desaparecía. El paso 6.5 del
  plan tenía mal los nombres de campo (`nombre_*` en vez de `*_nombre`; con esos nombres
  todas las filas quedaban con la misma clave): el agente ejecutor frenó y el usuario
  eligió aplicarlo con los nombres reales, con una clave que distingue `null` de vacío y
  en los cuatro radios.
- **Revisión y Verificación comparten la clave de líneas.** Porqué: piden la misma URL sin
  filtros; el filtro de mensualizados es en el cliente, así que compartir no mezcla datos.

**Estado**
- Deploy: no.
- Migraciones: ninguna.
- Verificación (del PR): `npm run lint` con 0 errores (los 5 warnings de Terceros) y
  `npm run build` verde. Prueba manual del usuario en el navegador contra `testing`:
  generar una quincena y verla en Conceptos sin F5, Revisión entrando por URL, cambiar un
  precio y ver el recálculo en Verificación, editar en Revisión y verlo en Verificación,
  logout desde el menú y desde Inicio, entrar con otro usuario, y "Sin concepto" (crear
  regla, "Listo" y "Otra", dos filas abiertas); sin errores en consola ni respuestas
  4xx/5xx en el backend. Revisión de código: 0 urgent, 0 high; el verificador confirmó que
  ningún camino deja datos de un usuario visibles para otro.

**Pendiente**
- **El plan de seguridad y calidad queda completo**: todos sus PRs están mergeados
  (backend #56, #57, #58, #60, #61, #62; frontend #47, #48, #49). **Ninguno está
  deployado.** Deploy completo, con OK del usuario, en este orden:
  1. `pip install -r requirements.txt` en el VPS (entran PyJWT y xlrd).
  2. `EMPLEADOS_MENSUALIZADOS_CUIL` y `TALLER_SHEET_URL` en el `.env` del VPS.
  3. Migraciones `terceros/001-007` en producción.
  4. Backend, verificando en el arranque el banner "Tablas y columnas BD propia:
     verificadas".
  5. Después, frontend (`npm run build` y swap de carpeta; rollback a `frontend_old`).
- Para el usuario, dueño del proyecto:
  - Los 5 warnings de hooks de Liquidación Terceros (ver la entrada del FT #48).
  - `docs/DEPLOY.md` sigue fuera de git.
  - Tareas aparte ofrecidas: los bugs de conceptos, Verificación y el combo de
    `/conceptos/buscar`, con el combo como prioridad; `scripts/verificar_agents_comun.sh`
    que no compara nada desde un worktree; conceptos duplicados en el maestro.
- Minor sin tocar (los lista el PR #49): el par de invalidaciones de líneas y estadísticas
  está repetido en tres lugares (Conceptos dos veces, Dashboard); el comentario del núcleo
  en `src/core/api.js` usa "Revisión" como ejemplo.
- Queda cerrado el pendiente "PR 6 del plan" de las entradas anteriores.

## 2026-09-30 — `verificar_agents_comun.sh` reconoce el repo por su origin, también desde un worktree

**Mergeado**
- PR #63 (backend) — `scripts/verificar_agents_comun.sh` identifica el repo por
  `git remote get-url origin` en vez de por el nombre de la carpeta; suma el plan
  `docs/superpowers/plans/2026-09-30-verificar-agents-worktree.md`.
- PR #50 (frontend) — el mismo script, idéntico byte a byte.

**Por frontera**
- Docs: el script que compara el bloque común de `AGENTS.md` entre los dos repos (vive en
  `scripts/`, fuera de las cinco fronteras). Reconoce `Gerorios/Preliquidador_AST_BK` y
  `Gerorios/Preliquidador_AST_FT` en https o ssh, con o sin `.git`. Al hermano lo busca
  entre las carpetas al lado del checkout principal (padre de
  `git rev-parse --git-common-dir`), también por su origin. Plan nuevo en
  `docs/superpowers/plans/`.

**Decisiones**
- **El hermano se busca por su origin, no por el nombre de la carpeta.** Porqué: corrido
  desde un worktree (`.claude/worktrees/<algo>`) el script imprimía "no reconozco el repo"
  y salía con 0 sin comparar, así que un cambio al bloque común hecho en un worktree podía
  pasar sin aviso; buscando por origin deja de depender de cómo se llamen las carpetas.
- **Exit 2 con mensaje claro** si no reconoce el repo, no encuentra al hermano o el
  hermano no tiene `AGENTS.md` (antes, exit 0 en silencio). Exit 1 sigue siendo "el bloque
  difiere". El hook `pre-commit` no cambia: avisa sin frenar.

**Estado**
- Deploy: nada que deployar (tooling de desarrollo). Los hooks instalados ya llaman al
  script desde `scripts/`; no hace falta reinstalarlos.
- Migraciones: ninguna.
- Verificación (del PR): rojo con el script viejo desde un worktree; exit 0 con el nuevo
  desde worktree y checkout principal en los dos repos; bloque alterado a propósito, exit 1
  con el diff; repos de juguete con origin desconocido o sin hermano, exit 2. Suite del
  backend 783 passed, 4 xfailed; build del front OK. Revisión: 0 urgent, 0 high, 2 minor.

**Pendiente**
- Queda cerrada la tarea aparte ofrecida "`scripts/verificar_agents_comun.sh` no compara
  nada desde un worktree" de las entradas del FT #48 y del FT #49.
- Minor sin tocar (los lista el PR): nombres mejorables en el script (`otro`, `comun`,
  `BK`/`FT`); fuera de un repo, `git rev-parse` deja su propio `fatal:` además del
  mensaje del script.

## 2026-09-30 — Deploy a producción del plan de seguridad y calidad y de Liquidación Terceros

Entrada correctiva, a pedido del usuario: no anota un merge sino el deploy de trabajo ya
mergeado y anotado. Corrige el "Ninguno está deployado" de la entrada del PR 6 (FT #49 y
BK #62), que era cierto al escribirse y dejó de serlo ese mismo día. Fuente: la sección
"Deploy del 2026-09-30" de `docs/DEPLOY.md` (local, fuera de git), donde está el detalle
técnico.

**Qué se deployó**
- Backend: de `dad6649` (merge del BK #54) a `0dc474f`. Entran el BK #55 (ADR-0014), los BK
  #56, #57, #58, #60, #61 y #62 (plan de seguridad y calidad) y el BK #59 (Liquidación
  Terceros). El BK #63, mergeado después, no entra.
- Frontend: al `main` en `ddbee72`, el merge del FT #49. Incluye los FT #46 (Terceros),
  #47, #48 y #49 (plan de seguridad y calidad); el FT #50, mergeado después, no entra. Desde
  qué versión del front se partió no está registrado.
- Autorizado por el usuario paso por paso.

**Por frontera**
- Prod y Datos: dependencias nuevas instaladas (PyJWT 2.15.1 y xlrd 2.0.1); migraciones
  `terceros/001` a `007` aplicadas en producción; dos variables nuevas en el `.env` del
  servidor, `EMPLEADOS_MENSUALIZADOS_CUIL` con valor y `TALLER_SHEET_URL` vacía.
- Liquidación Terceros: el módulo queda activo en producción. Por ahora lo ve sólo el admin.
- Preliquidación: los mensualizados salen de la variable del servidor; el front deployado
  filtra por el campo `mensualizado` (FT #47) y comparte el caché entre pantallas (FT #49).
- Núcleo: en producción quedan los cambios de los BK #56 y #57 (500 genérico, PyJWT, límite
  de login, chequeo de tablas y columnas al arrancar).

**Orden en que se hizo**
1. Código del backend actualizado e instalación de dependencias, sin reiniciar.
2. Migraciones `terceros/001` a `007` en producción, con un script de una sola vez que sigue
   `migrations/ORDEN.txt`, frena en el primer error y al final compara el esquema con los
   modelos: 31 sentencias, sin errores, nada faltante. Antes no existía ninguna tabla
   `terceros_`.
3. Las dos variables nuevas en el `.env`, con respaldo previo. Los CUIL de
   `EMPLEADOS_MENSUALIZADOS_CUIL` se sacaron de la base sin imprimirse.
4. Reinicio del backend.
5. Frontend con swap de carpeta; la versión anterior queda como rollback.

**Decisiones**
- **`TALLER_SHEET_URL` se deja vacía y la URL se carga después**, decisión del usuario.
  Porqué no registrado en `docs/DEPLOY.md`.
- **`python-jose` y `alembic` quedan instalados en el servidor, sin uso.** Porqué no
  registrado en `docs/DEPLOY.md`.

**Estado**
- Deploy: sí, backend y frontend en producción.
- Migraciones: `terceros/001` a `007` en producción. Ninguna otra.
- Verificación (de `docs/DEPLOY.md`): un solo arranque, con el banner de la base propia OK
  apuntando a producción y `Tablas y columnas BD propia: verificadas`; `/health` ok; el
  bundle del front, con el mismo md5 en local y en el servidor; smoke del usuario en el
  sitio real, "anda bien". Log sin errores internos, salvo dos 502 de
  `/api/terceros/alertas`, esperados mientras `TALLER_SHEET_URL` esté vacía: el endpoint
  no devuelve alertas a medias sin la app del taller.
- Rollback registrado: para las migraciones, borrar las tablas `terceros_*` (son nuevas);
  para el front, volver a la carpeta anterior.

**Pendiente**
- Para el usuario, dueño del proyecto:
  - Cargar `TALLER_SHEET_URL` en el `.env` del servidor y reiniciar el backend. Hasta
    entonces `/api/terceros/alertas` responde 502.
  - Asignar el módulo Terceros desde Administración a los usuarios que corresponda.
- Quedan cerrados los pendientes de deploy de las entradas anteriores: el de los BK #56 y
  #57, el del PR 4 (BK #60 + FT #47, con su variable), el del BK #59 + FT #46 (migraciones,
  xlrd, backend y después frontend), el del FT #48 y la lista de cinco pasos de la entrada
  del PR 6. También el de actualizar `docs/DEPLOY.md` con lo que devuelve `/health` y el
  orden de `ORDEN.txt` (entrada del BK #57): la sección "Actualizar" de ese archivo ya lo
  dice.
- Siguen abiertos, sin cambios por este deploy: la aceptación de la etapa 7 de Terceros y
  la revisión de código de dos ejes del BK #59 (entrada del BK #59); los 5 warnings de hooks
  de Terceros (entrada del FT #48); las tareas aparte de conceptos, Verificación y el combo
  de `/conceptos/buscar`, y de conceptos duplicados (entrada del PR 6).

## 2026-10-01 — El combo "Agregar concepto por código" deja de perder códigos y pide la quincena abierta

**Mergeado**
- PR #64 (backend) — `GET /api/precios/conceptos/buscar` agrupa por `(codigo, tipo)` en SQL,
  muestra sólo códigos con precio y aplica el tope de 200 después de agrupar. Trae el plan
  `docs/superpowers/plans/2026-09-30-combo-y-verificacion.md`.
- PR #51 (frontend) — el combo de `PanelLinea.jsx` y de `LiquidacionPersona` (en
  `Revision.jsx`) pide los códigos de la quincena de la planilla abierta, con la clave
  compartida `conceptosCombo(quincena)` en `services/claves.js`. Hermano del BK #64.

**Por frontera**
- Preliquidación: antes el endpoint aplicaba `order_by(codigo).limit(200)` sobre las filas
  de `concepto_liquidacion` y deduplicaba en Python después del límite; como hay muchas
  filas por código y quincena, el límite se comía los códigos más altos (en `testing`, 36
  códigos y el combo mostraba 30). Ahora el contrato sigue igual (`[{codigo, tipo}]` por
  código, mismos filtros `q`) y sin `quincena` agrupa todas. En el front, antes el combo
  mostraba códigos de todas las quincenas y elegir uno ausente en la quincena abierta hacía
  fallar el alta con "No existe el código X en el maestro de esta quincena".
- Docs: plan del combo y de la verificación por empresa, en dos PR.

**Decisiones**
- **Sólo aparecen códigos con al menos un precio en la quincena.** Porqué: decisión del
  usuario, lo que aparece se puede agregar.
- **Si un código tiene más de un tipo, sale el más frecuente; empate, por nombre de tipo
  ascendente, resuelto en Python sobre la tabla ya agrupada.** Porqué: en SQL pediría
  window functions o subconsultas correlacionadas, no portables entre MySQL (producción,
  versión no verificada) y SQLite (tests); el desempate en Python además no depende de la
  collation. Descartado: `ANY_VALUE` y window functions.
- **Con `q` texto el filtro de tipo se aplica antes de agrupar**: un código buscado por
  "jornal" sale con tipo JORNAL aunque tenga más filas de otro tipo. Porqué: es lo que se
  buscó.
- **La quincena va en la clave de caché del front, y la consulta sólo corre con quincena.**
  Porqué: cada planilla tiene su propia lista en caché, y nunca se muestra la lista de todas
  las quincenas mientras carga la planilla. La clave vive en `claves.js` porque la comparten
  dos componentes.
- **Una quincena sin maestro de precios deja el combo vacío.** Porqué: decisión del usuario
  de dejarlo así por ahora.

**Estado**
- Deploy: no. Backend y front se pueden deployar en cualquier orden (el endpoint ya
  aceptaba `quincena`). Rollback: revertir el merge y redeployar; sin cambios de esquema.
- Migraciones: ninguna.
- Verificación: 4 tests nuevos en `tests/preliquidacion/test_endpoints_lineas.py`, suite
  `787 passed, 4 xfailed`; prueba de sólo lectura contra `testing` que coincide con
  `COUNT(DISTINCT codigo)` con precio en las 4 quincenas con maestro; front con lint y build
  ok; prueba del usuario en el navegador con las dos ramas, contra `testing`.

**Pendiente**
- Deploy de BK #64 y FT #51, con OK explícito del usuario.
- Sigue el PR 2 del plan, hermanos backend y front: Verificación agrupa por empresa y
  legajo, `eliminar_concepto_masivo` con `bindparam` expanding, y `LiquidacionPersona`
  distingue a la persona por empresa y legajo.
- Tareas aparte, fuera de este plan: el precio que se aplica al agregar un código a mano
  (`.first()` toma una regla cualquiera del código) y el error 500 con precio vacío; esa
  sesión está en pausa.
- Deuda del FT #51: el bloque `useQuery` del combo está repetido en `PanelLinea.jsx` y
  `Revision.jsx`, candidato a un hook propio en un PR aparte.
- La tarea aparte del combo de `/conceptos/buscar` (listada como abierta en el deploy del
  2026-09-30) queda resuelta en código; falta el deploy.

## 2026-10-01 — Borrado masivo de conceptos con `bindparam` expanding; se descarta agrupar Verificación por empresa y legajo

Segunda entrada del día: la de arriba (BK #64 / FT #51) ya estaba escrita cuando entró este
merge, y la bitácora es append-only.

**Mergeado**
- PR #65 (backend, merge `78401bf`) — `eliminar_concepto_masivo` pasa a
  `bindparam("ids", expanding=True)`, se borra una línea muerta de `dashboard_verificacion`,
  se sacan 2 `xfail` y se anotan en el plan la ejecución y el cambio de alcance de la etapa 2.
  Sin PR hermano de front.

**Por frontera**
- Preliquidación: `POST /api/preliquidacion/lineas/concepto-masivo/eliminar` arma el
  `DELETE ... WHERE linea_id IN :ids` con `bindparam` expanding y lista, igual que el resto
  del service. En MySQL ya andaba (pymysql interpola la tupla); en SQLite no compilaba. Se
  borra `exceso_horas = exceso_tancadas = exceso_plantas = []` de `dashboard_verificacion`.
  En `tests/preliquidacion/test_concepto_masivo.py` salen los dos `xfail(strict=True)` del
  `IN :ids`.
- Docs: `docs/superpowers/plans/2026-09-30-combo-y-verificacion.md` suma notas de ejecución
  y el cambio de alcance de la etapa 2.

**Decisiones**
- **Se descarta agrupar Verificación y `LiquidacionPersona` por (empresa, legajo).** Porqué:
  en `testing`, todos los legajos repetidos entre empresas son la misma persona (mismo
  nombre; las líneas de la segunda empresa tienen alerta de legajo) y en ninguna planilla
  hay dos personas distintas con el mismo legajo. El cambio no arreglaba nada visible y
  partía en dos a personas reales: escondía un exceso repartido entre empresas y separaba
  la línea que se quiere reasignar de empresa en la liquidación masiva. Decisión del
  usuario.
- **Si aparece el caso real, el arreglo es agrupar por CUIL (persona real), no por
  (empresa, legajo).** El xfail `test_mismo_legajo_en_empresas_distintas_no_se_mezcla` queda
  como documentación de esa deuda. El trabajo descartado quedó en ramas locales
  `respaldo/verificacion-empresa-legajo`, sin pushear, por si se retoma.
- Esto corrige el "Pendiente" de la entrada anterior de hoy: el PR 2 del plan no incluye
  la agrupación por empresa y legajo en Verificación ni en `LiquidacionPersona`, y no tuvo
  PR de front. De ese PR 2 entró sólo el `bindparam` expanding.

**Estado**
- Deploy: no. Va junto con BK #64 y FT #51, que también esperan deploy. Rollback: revertir
  el merge y redeployar el backend; sin cambios de esquema.
- Migraciones: ninguna.
- Verificación: los 2 tests de borrado masivo, sin el xfail, fallaban con
  `OperationalError ... near "?"` en SQLite y pasan con el cambio. Suite
  `789 passed, 2 xfailed` (antes 787 / 4). Prueba de sólo lectura contra `testing` (MySQL):
  el mismo `IN :ids` con expanding arma bien la consulta, con un SELECT equivalente.

**Pendiente**
- Deploy de BK #64, FT #51 y BK #65, con OK explícito del usuario.
- Los dos xfail que quedan: la agrupación por legajo (deuda documentada, arreglo por CUIL
  si aparece el caso) y el error 500 con precio vacío en `agregar_concepto_por_codigo`
  (tarea aparte, en pausa junto con el precio que se aplica al agregar un código a mano).

## 2026-10-01 — Deploy a producción del combo de conceptos y del borrado masivo

Entrada correctiva, a pedido del usuario: no anota un merge sino el deploy de trabajo ya
mergeado y anotado. Corrige el "Deploy: no" de las dos entradas anteriores de hoy (BK #64 /
FT #51 y BK #65), que era cierto al escribirse y dejó de serlo ese mismo día. El detalle
técnico está en `docs/DEPLOY.md` (local, fuera de git).

**Qué se deployó**
- Backend: de `0dc474f` a `37f068a`. Entran el BK #63 (`verificar_agents_comun` desde
  worktrees; es un script y no corre en producción), el BK #64 (el combo de conceptos
  agrupa en SQL y sólo con precio) y el BK #65 (borrado masivo con `bindparam` expanding),
  más commits de bitácora y planes.
- Frontend: de `ddbee72` a `eb180dc`. Entran el FT #50 (script) y el FT #51 (el combo pide
  la quincena abierta).
- Autorizado por el usuario.

**Por frontera**
- Preliquidación: en producción queda el combo de `/conceptos/buscar` del BK #64 y FT #51,
  y el borrado masivo del BK #65.
- Prod y Datos: sin migraciones ni dependencias nuevas.

**Estado**
- Deploy: sí, backend y frontend en producción. Frontend con swap de carpeta; la versión
  anterior queda como rollback.
- Migraciones: ninguna.
- Verificación: un solo arranque del backend, conectado a la base de producción, con
  tablas verificadas; `/health` ok; log sin errores tras el deploy. Bundle del front con el
  mismo md5 en local y en el servidor; sitio responde 200.
- Nota operativa: el arranque del backend tardó unos 7 s y el comando de deploy espera 5 s
  antes de consultar `/health`. El detalle quedó en `docs/DEPLOY.md`.

**Pendiente**
- Smoke del usuario en el sitio real: el combo en una quincena con precios.
- Quedan cerrados los pendientes de deploy de las dos entradas anteriores de hoy (BK #64,
  FT #51 y BK #65).
- Sigue abierta, en pausa, la tarea aparte del precio que se aplica al agregar un código a
  mano y del error 500 con precio vacío.

## 2026-10-01 — Una regla del maestro siempre tiene código y precio > 0 (ADR-0016)

**Mergeado**
- PR #66 (backend, merge `7b1084a`, rama `fix/regla-completa`): el backend rechaza con 422,
  y un texto en español, las reglas de `concepto_liquidacion` sin código, sin precio o con
  precio <= 0. Aplica en el alta, la edición, el precio masivo y la copia entre quincenas.
  También entran ADR-0016 y el plan `docs/superpowers/plans/2026-10-01-regla-completa.md`.
- PR #52 (frontend, merge `3c6158c`), hermano del anterior: Conceptos y el panel por
  concepto avisan antes de mandar ("Ingresá un código", "Ingresá un precio mayor que 0").

**Por frontera**
- Preliquidación (back): las validaciones están en `schemas.py`, con `AfterValidator` y un
  `ValueError` en español, la misma convención que `Quincena`.
  - Alta (`POST /precios/conceptos`): `codigo` y `precio` son obligatorios. Usa
    `validate_default=True`, así que un campo que no vino y uno que vino null dan el mismo
    mensaje.
  - Edición (`PATCH /precios/conceptos/{id}`): sigue siendo parcial. Se rechaza mandar
    `codigo: null`, `precio: null` o un precio <= 0. `categoria` y `supervisor_nombre` en
    null siguen limpiando el valor.
  - Precio masivo: exige precio > 0. Antes aceptaba 0.
  - Copia entre quincenas (`precios.py`): no copia las reglas incompletas y las cuenta en
    el detalle ("N omitidas por incompletas"). Si todas son incompletas, responde 200 igual.
    Una incompleta que ya existe en el destino cuenta como incompleta, no como "ya existía".
  - Tests: 26 nuevos en `tests/preliquidacion/test_regla_completa.py`, y 3 tests ajustados
    porque creaban reglas vacías.
- Preliquidación (front): la validación se agrega en `ReglaRow`, en las tres formas de alta,
  en el precio por fila y en el masivo del panel de precios, y en el precio en celda y el
  alta por código de `PanelPorConcepto`. Hay un helper nuevo `precioPositivo` y una
  constante `MSG_PRECIO` en `conceptosConstantes.js`. "Sin código" y "sin precio" se siguen
  mostrando, porque quedan reglas viejas así.
- Docs: ADR-0016 nuevo, el plan, y la definición de **Concepto** en
  `CONTEXT-preliquidacion.md`, que ahora dice que siempre tiene código y precio > 0.

**Decisiones**
- **Una regla vacía deja de ser un estado válido del maestro.** Porqué: hasta ahora una
  regla vacía era un olvido que se notaba recién en la línea, como "línea incompleta", y la
  copia lo pasaba a la quincena siguiente. Lo pidió Gero el 2026-10-01. Descartado: dejarlo
  como estaba.
- **Se exige precio > 0, no sólo que haya precio.** Porqué: una regla con precio 0 tampoco
  completa la línea (ADR-0003). Descartado: aceptar precio 0.
- **Se valida en el backend además del front.** Porqué: un front viejo en caché, o cualquier
  otro llamado a la API, podía seguir grabando reglas vacías. Descartado: validar sólo en el
  front.
- **Sin DDL `NOT NULL` ni `CHECK precio > 0`.** Porqué: obligaba a limpiar producción y a
  aplicar DDL, y aportaba poco frente a la validación en la API. ADR-0016 lo rechaza "por
  ahora": se revisa si aparece otro camino de escritura que no pase por la API.
- **La copia omite las reglas incompletas y avisa.** Porqué: el ADR dice que el liquidador
  las carga completas en la quincena nueva. Es la única excepción a "copiar todo" de
  ADR-0004. Descartado: copiar la regla igual, o frenar toda la copia.
- **La copia responde 200 aunque todas sean incompletas, y no se agrega un campo
  `omitidas_incompletas` a `MensajeResponse`.** Porqué: Gero cerró las preguntas del plan
  (§8) con la recomendación. Porqué de fondo no registrado en el PR. Descartado: responder
  404, y agregar un toast aparte.
- **Las reglas viejas incompletas quedan como están.** Con el front nuevo, para guardar una
  hay que completarla. Cambia qué quiere decir "línea incompleta": que a la línea no le
  aplica ninguna regla, o que no hay regla para la categoría de la persona.

**Estado**
- Deploy: no, todavía. Gero pidió deployar a continuación; si se hace, va en una entrada
  aparte. El orden es primero el backend: con el front viejo, una regla vacía recibe el 422
  y el toast muestra el texto en español. Con el backend viejo, el front nuevo sólo valida
  de más. Rollback: revertir los PRs, porque no hay DDL ni datos tocados.
- Migraciones: ninguna.
- Verificación: suite backend `815 passed, 2 xfailed`; los 2 xfailed ya estaban. `npm run
  build` pasa y el lint no tiene errores nuevos. Smoke manual con backend y front locales
  contra `testing`; los datos de prueba se borraron. Revisión en dos ejes: 0 urgent, 0 high,
  9 minor sin tocar (listados en los cuerpos de los PRs).

**Pendiente**
- Antes del deploy: contar en producción, en sólo lectura, las reglas sin código, sin
  precio o con precio <= 0 por quincena. La próxima copia las va a omitir. En `testing`, al
  2026-10-01, no había ninguna.
- Deuda que ya existía, en una tarea aparte después de ese conteo:
  `preliquidacion_service.py` y el SQL de faltantes (`precios.py`) cuentan como completa una
  regla con precio <= 0. Una regla vieja con precio 0 paga 0 sin ninguna marca, contra
  ADR-0003.
- Nota para la tarea "Concepto extra" (en pausa, ADR-0015 reservado): con ADR-0016 se
  cierran sus preguntas abiertas 3 y 4. El caso "vaciar el precio borra el extra, con un 409
  antes" ya no puede pasar por PATCH, así que queda sólo "si se borra la regla, se borra el
  extra". El 404 por "regla sin precio" queda sólo para reglas viejas. Esa tarea rebasea
  sobre este merge. Detalle en §9 del plan.

## 2026-10-01 — Deploy a producción de la regla del maestro siempre completa (ADR-0016)

Entrada de deploy: no anota un merge sino el deploy de BK #66 y FT #52, ya anotados arriba.
Corrige su "Deploy: no", que era cierto al escribirse. El detalle técnico va en
`docs/DEPLOY.md` (local, fuera de git).

**Qué se deployó**
- Backend: de `37f068a` a `acf85a4` (BK #66 más bitácora).
- Frontend: de `eb180dc` a `3c6158c` (FT #52).
- Autorizado por el usuario.

**Estado**
- Antes del deploy, conteo de sólo lectura en producción de reglas sin código, sin precio o
  con precio <= 0: ninguna, en todas las quincenas. La copia entre quincenas no omite nada
  por ahora.
- Deploy: sí, backend y frontend. Frontend con swap de carpeta; la versión anterior queda
  como rollback.
- Migraciones: ninguna.
- Verificación: un solo arranque del backend, conectado a la base de producción, con tablas
  verificadas; `/health` ok; log sin errores. Bundle del front con el mismo md5 en local y
  en el servidor; sitio responde 200.

**Pendiente**
- Smoke del usuario en el sitio real: guardar una regla con precio vacío o 0 debe avisar.
- Siguen abiertas la deuda de precio <= 0 contado como completo (tarea aparte; con 0 reglas
  así en producción, sin urgencia) y la nota para "Concepto extra".

## 2026-10-01 — Concepto extra: el liquidador elige la opción y el extra sigue al maestro (ADR-0015)

**Mergeado**
- PR #67 (Preliquidador_AST_BK, merge `5c0ee74`): "Agregar concepto por código" deja de
  tomar la primera regla del código con `.first()`. Ahora ofrece opciones (precio, unidad
  base, tipo) y el extra sigue a su regla cuando se edita el maestro.
- PR #53 (Preliquidador_AST_FT, merge `db3a3fd`): diálogos para elegir la opción, para el
  código repetido y para el aviso de que se van a borrar extras, en Revisión y Conceptos.

**Por frontera**
- Preliquidación (back): "agregar por código", en una línea y masivo, responde 409
  `elegir_opcion` cuando el código tiene varias opciones, 409 `codigo_repetido` cuando la
  línea ya lo tiene (el masivo acepta `si_repetido` = `agregar` | `saltear`) y 404 claro
  cuando no tiene precio; antes era un 500 (`IndexError`) y sale su xfail. El masivo no
  escribe en ninguna línea si algo falla. El combo `GET /conceptos/buscar` deja afuera las
  reglas con categoría. PATCH, DELETE y precio masivo de una regla reatan o borran sus
  extras (409 `borra_extras` con confirmación por `?confirmar_borrado_extras=true`). El
  precio masivo nunca borra: con extras viejos que no puede reatar responde 409
  `extras_a_revisar`.
- Preliquidación (front): `DialogoOpcionExtra` en `PanelLinea` y `Revision`, y
  `DialogoBorraExtras` en `Conceptos`. El alta de `PanelLinea` pasa a `useMutation`.
- Docs: ADR-0015 nuevo, término **Concepto extra** en `CONTEXT-preliquidacion.md` y plan
  `docs/superpowers/plans/2026-09-30-concepto-extra.md`.

**Decisiones**
- **El liquidador elige el código y la opción, no la tarea.** Porqué: piensa en código,
  precio y unidad. Descartado: usar la regla que matchea la línea (el uso real es un plus de
  otra tarea y no matchea nada), que escriba el precio a mano (queda sin vínculo al
  maestro), que el sistema elija con un criterio fijo (sigue siendo adivinar) y que elija la
  tarea exacta (lo rechazó Gero).
- **La opción incluye la unidad.** Porqué: el importe es cantidad × precio y la cantidad
  depende de la unidad. El 449 tiene un solo precio, pero en una regla se paga fijo y en
  otra por jornal.
- **La opción viaja por valor y no por id de regla.** Porqué: el liquidador no elige la
  regla. Si la regla deja de existir entre el 409 y el reintento, el backend da un 404
  claro.
- **El extra se ata a la regla de la opción cuya tarea va primero alfabéticamente, y
  conserva la opción mientras otra regla la ofrezca.** Porqué: atarlo a esa regla es
  arbitrario, así que un cambio en ella no debe moverle el precio. Descartado: dejarlo
  congelado (lo rechazó Gero porque no sigue el impacto reactivo de ADR-0002).
- **Se reata o se borra antes del `db.delete`.** Porqué: la FK es `ON DELETE SET NULL`.
- **El flag de confirmación va por query.** Porqué: así no se toca
  `ConceptoUnifUpdateRequest`, que valida ADR-0016.
- **La descripción se corta a 150 caracteres, sin ampliar la columna.** Porqué: ampliarla
  era DDL para un caso que hoy no existe.
- **En el front, el foco por defecto va a "Cancelar"** en el diálogo de una línea y en el de
  borrado, y a "Saltear" en el masivo. Porqué: que un Enter accidental no pague ni borre.

**Estado**
- Deploy: no. Backend y front se deployan juntos, y las etapas A y B también: con A sin B,
  un PATCH de categoría puede dejar un extra atado a una regla que ya no lo admite. Con el
  back nuevo y el front viejo, un código con varias opciones o repetido no se agrega y el
  toast muestra el mensaje del 409. Rollback: revertir los dos merges; no hay cambios de
  esquema.
- Migraciones: ninguna (`concepto_adicional` ya tenía las columnas, ADR-0006).
  `pip install`: no hace falta.
- Verificación: suite backend `949 passed, 1 xfailed`; el xfailed es el de Verificación,
  ajeno a este PR. Front: lint sin errores nuevos y `npm run build` OK. Smoke con backend y
  front locales contra `testing` (quincena 2026-08-16), y al terminar `testing` quedó sin
  extras de prueba. No se probaron en la UI el masivo de Revisión ni el botón de confirmar
  el borrado; sí se probaron por API. Revisión: back 0 urgent y 2 high arreglados; front
  0 urgent y 1 high arreglado. Los minor que no se tocaron están en los cuerpos de los PRs.

**Pendiente**
- Cierra el pendiente "el precio que se aplica al agregar un código a mano" de las entradas
  anteriores, y también la nota para "Concepto extra" de las dos entradas de ADR-0016.
- Antes del deploy, con OK de Gero: la consulta de sólo lectura en producción de la sección
  "Pre-deploy" del plan. Cuenta, por quincena, los extras viejos, los que quedaron sin regla
  (van a quedar como manuales para siempre) y los atados a una regla que ya no los admite.
  Si aparece alguno, Gero decide antes de deployar.
- Una regla vieja con precio 0 aparecería como opción "$0". La consulta de pre-deploy lo
  deja ver. Sigue abierta la deuda de que un precio <= 0 cuenta como completo.
- Deuda previa: si un id se repite en `linea_ids`, el concepto se agrega dos veces en esa
  línea.

## 2026-10-01 — Deploy a producción del Concepto extra (ADR-0015)

Entrada de deploy: no anota un merge sino el deploy de BK #67 y FT #53, ya anotados arriba.
Corrige su "Deploy: no", que era cierto al escribirse. El detalle técnico va en
`docs/DEPLOY.md` (local, fuera de git).

**Qué se deployó**
- Backend: de `acf85a4` a `aab0af7` (BK #67 más bitácora). Sin dependencias nuevas.
- Frontend: de `3c6158c` a `db3a3fd` (FT #53), con build desde una copia idéntica a `main`.
- Backend y frontend juntos, con las etapas A y B, como pedía la entrada del merge.
- Autorizado por el usuario.

**Estado**
- Antes del deploy, la consulta de sólo lectura en producción de la sección "Pre-deploy" del
  plan: 0 conceptos agregados por código. No hay extras viejos, ni sin regla, ni atados a una
  regla que no los admita, así que no hubo nada que decidir.
- Deploy: sí, backend y frontend. Frontend con swap de carpeta; la versión anterior queda
  como rollback.
- Migraciones: ninguna.
- Verificación: un solo arranque del backend, conectado a la base de producción, con tablas
  verificadas; `/health` ok; log sin errores internos en los 10 minutos siguientes. Bundle
  del front con el mismo md5 en local y en el servidor; sitio responde 200.
- Rollback: revertir backend y frontend juntos (backend a `acf85a4`).

**Pendiente**
- Smoke del usuario en el sitio real: agregar a una línea un código con varias opciones (por
  ejemplo, el 902) y ver el diálogo para elegir la opción y el "(extra, de …)" en la línea.
- Queda cerrado el pendiente de pre-deploy de la entrada del merge. Siguen abiertas la deuda
  de precio <= 0 contado como completo y la de un id repetido en `linea_ids`.

## 2026-10-02 — Revisión ordena por columna y suma las líneas visibles en una fila TOTAL

**Mergeado**
- PR #54 (Preliquidador_AST_FT, merge `adb4d30`): en la tabla principal de Revisión, orden
  por clic en el encabezado y fila TOTAL fija abajo.
- PR #68 (Preliquidador_AST_BK, merge `e318d6b`), hermano del anterior: sólo el plan
  `docs/superpowers/plans/2026-10-02-revision-orden-totales.md`. Sin cambios de backend ni
  de API.

**Por frontera**
- Preliquidación (front): clic en un encabezado ordena ascendente (▲), descendente (▼) y
  vuelve al orden del server (empresa, empleado, fecha). Una columna a la vez. La alerta
  ordena por gravedad (DUPLICADO, INCOMPLETA, LEGAJO, EMPRESA), el legajo es numérico,
  cliente desempata por finca, conceptos por cantidad de extras y los textos sin mayúsculas
  ni acentos. Los vacíos ("—", incluido el 0) van siempre al final. La fila TOTAL suma
  horas jornal, horas máquina, tancadas, unidades e importe de las líneas visibles, y se
  oculta sin resultados. La lógica está en `pages/ordenarLineas.js` y
  `pages/totalesLineas.js`, sin React. La precedencia de alertas sale de `alertaDe`, que
  usan el badge y el orden. `package.json` suma el script `npm test` (`node --test`).
- Docs: el plan, en el backend.

**Decisiones**
- **Orden y fila TOTAL en la tabla principal de Revisión.** Porqué: lo pidieron el
  liquidador y el gerente para no contar a mano las unidades al filtrar. Descartado (fuera
  de alcance en el plan): `LiquidacionPersona`, Verificación y otras tablas, persistir el
  orden, ordenar por varias columnas y la cantidad de líneas en el TOTAL.
- **Las duplicadas suman en el TOTAL.** Porqué: el total coincide con la suma de lo que
  está en pantalla. Decisión de Gero.
- **El orden dura mientras se está en la pantalla** (estado de React) y al cambiarlo el
  scroll vuelve arriba. Gero aprobó las recomendaciones del plan. Porqué no registrado en el
  PR.
- **El 0 cuenta como vacío para ordenar.** Porqué: la pantalla ya lo muestra "—".
- **Primeros tests del front, con `node --test` y sin dependencias nuevas.** Porqué: la
  lógica pura se testea sin React. Descartado: Vitest, por ser dependencia nueva, como en los
  antecedentes de la bitácora.
- **Todo decimal pasa por `Number()` y cada total se redondea a 2 decimales.** Porqué: los
  decimales llegan del server como string ("95" quedaba después de "120"), y el redondeo
  sólo saca el error de punto flotante; las columnas son `Numeric(_, 2)`.
- **Sticky en los `td` del `tfoot`**, igual que el `thead th` existente.

**Estado**
- Deploy: no, todavía. Gero pidió el deploy del front; si se hace, va en una entrada
  aparte. Sólo front: el backend no cambia. Rollback: revertir el FT #54 y swap de carpeta
  del front.
- Migraciones: ninguna.
- Verificación: `npm test` 20/20, `npm run lint` 0 errores (las 5 warnings previas de
  Terceros), `npm run build` OK. Smoke en el navegador sobre la 2Q de agosto en `testing`
  (1.818 líneas): el TOTAL coincide con la suma de la API en las cinco columnas. No se probó
  editar una línea con un orden activo, para no escribir en `testing`. Revisión: 0 urgent,
  0 high, 6 minor sin tocar (listados en el cuerpo del FT #54).

**Pendiente**
- Smoke del usuario en el sitio real después del deploy, incluido editar una línea con un
  orden activo: se espera que la fila se mueva a su lugar nuevo y el orden siga.
- Deuda previa: el `border-bottom` del `thead th` sticky desaparece al scrollear
  (`index.css`), igual que el `border-top` del TOTAL. Arreglo propuesto en el FT #54:
  `box-shadow` inset.

## 2026-10-02 — Deploy a producción del orden por columna y la fila TOTAL en Revisión

Entrada de deploy: no anota un merge sino el deploy del FT #54, ya anotado arriba. Corrige
su "Deploy: no", que era cierto al escribirse. El detalle técnico va en `docs/DEPLOY.md`
(local, fuera de git).

**Qué se deployó**
- Frontend: de `db3a3fd` a `adb4d30` (FT #54), con build desde el checkout del front en
  `main`, idéntico a `origin/main`.
- Backend: sin cambios. El BK #68 es sólo docs y no se llevó al servidor.
- Autorizado por el usuario.

**Estado**
- Deploy: sí, sólo frontend, con swap de carpeta; la versión anterior queda como rollback.
- Migraciones: ninguna.
- Verificación: build con 44 assets; bundle `index-DmFS4wWh.js` con el mismo md5 en local y
  en el servidor; el sitio responde 200 y sirve el bundle nuevo; `/health` del backend ok.
- Rollback: volver a la carpeta anterior del front con el swap inverso.

**Pendiente**
- Smoke del usuario en el sitio real: ordenar por columna, ver la fila TOTAL al filtrar, y
  editar una línea con un orden activo (no probado antes del merge).
- Queda cerrado el pendiente de deploy de la entrada del merge.

## 2026-10-02 — Tancadas vs Jornal compara valor hora por hora de máquina

**Mergeado**
- PR #69 (Preliquidador_AST_BK, merge `fd76263`): el control Tancadas vs Jornal pasa a
  comparar el valor hora pagado por hora de máquina contra el valor hora de pulverización
  × 1,3, sin ningún ÷2. Incluye ADR-0017, glosario, `docs/AYUDA.md` y el plan
  `docs/superpowers/plans/2026-10-02-tancadas-vs-jornal.md`.
- PR #55 (Preliquidador_AST_FT, merge `adc284c`), hermano del anterior: la tabla
  `TancadasJornal` (Verificación y Vista gerencial) con las columnas del cálculo nuevo.

**Por frontera**
- Preliquidación (back): `control_tancadas_jornal` en `preliquidacion_service.py`. Por
  (cliente, finca, tarea): importe pagado = Σ importe real de los conceptos de tancada;
  valor hs/máquina pulv = importe pagado ÷ hs máquina; referencia = `valor_hora_pulv` de la
  quincena × 1,3; variación = (valor hora pagado − referencia) ÷ referencia, positiva = se
  pagó más caro. El total se recalcula sobre las sumas y sólo con las filas que tienen hs
  máquina; una fila sin hs máquina sale con `sin_hs_maquina` y sin valor hora ni variación. Sin
  valor hora cargado, referencia y variación en null, como antes. Contrato JSON roto a
  propósito: salen `valor_jornal`, `valor_tancada` y `diff`; entran `importe_pagado`,
  `valor_hora_maquina`, `valor_hora_referencia`, `variacion`, `sin_hs_maquina` y
  `totales.filas_sin_hs_maquina`. Los endpoints de Verificación y Gerencial no cambian.
  Comentario de `valor_hora_pulv` en `models.py` actualizado.
- Preliquidación (front): columnas Cliente · Finca · Tarea · Tancadas · Hs jornal · Hs
  máquina · Precio tancada · Importe pagado · Valor hs/máquina pulv · Valor hs pulv × 1,3 ·
  Variación. Variación positiva en rojo, en filas y total. Fila sin hs máquina con badge
  "sin hs máquina" y nota al pie con la cantidad de filas que no entran en la variación.
  Salen "Valor s/jornal", "Valor s/tancada" y "Diff". Formatters null-safe: con un backend
  viejo las columnas nuevas quedan en "—".
- Docs: ADR-0017 nuevo; el ADR-0007 lleva una nota de que su fórmula quedó reemplazada (lo
  demás sigue vigente); glosario de Preliquidación (Tancada, Valor hora pulverización);
  `docs/AYUDA.md`; el plan.

**Decisiones**
- **Valor hora pagado por hora de máquina contra valor hora pulv × 1,3, sin ÷2** (ADR-0017).
  Porqué: la fórmula anterior (`hsjornal/2 × valor_hora_pulv × 1,3` contra `tancadas/2 ×
  precio`) dividía por 2 un dato que el motor no divide al pagar, así que los montos salían
  a la mitad, y comparaba contra horas de jornal. Gero mostró la planilla con el cálculo que
  usan; un test la reproduce (267.780 / 34 = 7.875,88 contra 7.352 × 1,3 = 9.557,60 →
  −17,6 %). Descartado: la fórmula vieja; comparar contra hs jornal (la referencia es un
  valor hora de máquina, no de presencia).
- **El total sale de las sumas, no del promedio de las variaciones.** Porqué: un promedio de
  porcentajes miente; igual que en Plantas vs Jornal.
- **La referencia es `valor_hora_pulv`, no `valor_hora_tractorista`.** Porqué: son dos
  controles con dos parámetros; el liquidador carga en Valor hora pulverización el valor
  base y el sistema suma el 30 %.
- **El ADR-0017 reemplaza sólo la fórmula del ADR-0007**: el valor hora por quincena como
  dato y el recargo 1,3 fijo en código siguen vigentes.
- **El nombre del control y la barra "Valor hora pulverización" no cambian.** Decisión de
  Gero. Porqué no registrado en el PR.
- **Se aplica a todas las quincenas al leer**: cambian los números del control en las
  quincenas pasadas; lo pagado no cambia.

**Estado**
- Deploy: no, todavía. Gero lo pidió; si se hace, va en una entrada aparte. Orden: backend
  primero, front después, en la misma ventana (con el front viejo tres columnas quedan en
  "—", no rompe). Rollback: revertir los dos PRs y swap de carpeta del front; sin datos ni
  DDL.
- Migraciones: ninguna.
- Verificación: `test_control_tancadas_jornal.py` 13/13, suite del back 953 passed y 1
  xfailed, `test_asistente_docs.py` 6/6; front `npm run lint` 0 errores (5 warnings previas
  de Terceros), `npm run build` OK, `npm test` 20/20. Smoke contra `testing` con los dos
  PRs: importe igual a la suma de los conceptos de tancada; sin valor hora, "—" y aviso; con
  valor hora, referencia y variación correctas en fila y total; endpoint de Gerencial igual.
  No se vio en pantalla una fila sin hs máquina (no hay en `testing`); lo cubre un test.
  Revisión: 0 urgent, 0 high.

**Pendiente**
- Después del deploy, revisar que el valor cargado en la barra de la última quincena sea el
  valor base, sin recargo.
- Minor sin tocar (BK #69): aclarar en el glosario que "Valor hora pulverización" y "Valor
  hora tractorista" son el mismo número cargado aparte; el test
  `test_control_tancadas_calcula_valores_y_diff` todavía dice "diff" en el nombre.

## 2026-10-02 — Deploy a producción del control Tancadas vs Jornal por valor hora de máquina (ADR-0017)

Entrada de deploy: no anota un merge sino el deploy de BK #69 y FT #55, ya anotados arriba.
Corrige su "Deploy: no", que era cierto al escribirse. El detalle técnico va en
`docs/DEPLOY.md` (local, fuera de git).

**Qué se deployó**
- Backend: de `aab0af7` a `fd76263` (BK #69).
- Frontend: de `adb4d30` a `adc284c` (FT #55), con build desde el checkout del front en
  `main`, idéntico a `origin/main`.
- Backend primero y frontend después, en la misma ventana, como pedía la entrada del merge.
- Autorizado por el usuario.

**Estado**
- Deploy: sí, backend y frontend. Frontend con swap de carpeta; la versión anterior queda
  como rollback.
- Migraciones: ninguna.
- Verificación: un solo arranque del backend, conectado a la base de producción, con tablas
  verificadas; `/health` ok. Build del front con 44 assets y el mismo bundle en local y en el
  servidor; el sitio responde 200 y sirve el bundle nuevo.
- Verificación en producción, en sólo lectura: el control nuevo responde sin error en las
  últimas 4 quincenas. En la 1Q de septiembre muestra 9 filas, todas con hs máquina, y una
  variación total de +11,5 %.
- Rollback: revertir los dos PRs y swap inverso de la carpeta del front; sin datos ni DDL.

**Pendiente**
- Gero confirma que el valor hora pulverización cargado en la 1Q de septiembre (7.433,52)
  es el valor base y no uno ya recargado.
- Mirar el control en el sitio real.
- Queda cerrado el pendiente de deploy de la entrada del merge.

## 2026-10-04 — Un Concepto no se repite: la base lo impide (ADR-0018)

**Mergeado**
- PR #70 (Preliquidador_AST_BK, merge `02ebc60`): `concepto_liquidacion` deja de admitir dos
  reglas con la misma quincena, tarea, código, cliente, finca, supervisor y categoría.
  Incluye ADR-0018, el término "Concepto duplicado" en el glosario, una nota en ADR-0011,
  la migración `ws17_concepto_unico_normalizado.sql` y el plan
  `docs/superpowers/plans/2026-10-02-concepto-duplicado.md`. Sin PR hermano en el front: el
  toast ya muestra cualquier `detail` de texto.

**Por frontera**
- Preliquidación: `uq_concepto_unif` pasa a ser un índice único funcional sobre la clave
  normalizada (TRIM, sin distinguir mayúsculas, vacío = NULL); el precio no participa. Alta
  y edición en `precios.py` contestan 409 con texto ("Ya existe una regla para esta tarea
  con el código X..."). Copiar quincena saltea las reglas que ya existen en el destino y
  las repetidas del origen, comparando sin acentos; un choque por doble clic da 409 y no
  500. `models.py` declara el índice nuevo.
- Núcleo: sólo tests; `test_errores_internos.py` fija que el duplicado con el mensaje de
  MySQL da 409 sin filtrar SQL ni valores, y que cualquier otro error de base sigue en el
  500 genérico.
- Prod y Datos: `ws17` (verificación previa, backup en `concepto_liquidacion_bkp_ws17`, un
  ALTER atómico y rollback comentado), listada en `migrations/ORDEN.txt` como posterior al
  esquema base exportado.
- Docs: ADR-0018 nuevo (renumerado: se escribió como 0017 y ese número lo tomó Tancadas vs
  Jornal mientras se trabajaba). ADR-0011 corregido: su índice único no frenaba ningún
  repetido. Glosario de Preliquidación con "Concepto duplicado".

**Decisiones**
- **Una tarea que paga más lleva una sola regla con el precio total.** Porqué: el motor
  suma cada regla que matchea, así que una regla repetida paga dos veces. El hallazgo vino
  de una regla real cargada dos veces en una quincena ya pagada; el gerente confirmó que esa
  tarea paga combinada ("poda + 20%") y el dueño decidió que va una sola regla con el precio
  total. Descartado: dejar sumar dos reglas iguales a propósito (es pagar doble sin que se
  note en el maestro).
- **La garantía es un índice en la base, no un chequeo en la API.** Porqué: un doble clic
  pasa los dos chequeos, y la edición, la copia o un SQL a mano quedarían sin cubrir.
  Descartado: chequear sólo en la API.
- **No se bloquea el código repetido en toda la quincena.** Porqué: hoy el mismo código se
  usa a propósito en tareas distintas, y la copia entre quincenas fallaría. Descartado:
  unicidad por código en la quincena.
- **El índice viejo no servía.** Porqué: cada regla tiene cliente o supervisor en NULL
  (ADR-0011) y para la base dos NULL nunca son iguales.
- **UPPER también en MySQL**, aunque la collation ya ignora mayúsculas. Porqué: la
  expresión queda idéntica en MySQL y en SQLite.
- **La copia compara sin acentos.** Porqué: así compara la collation `utf8mb4_0900_ai_ci`,
  y la copia no choca contra el índice. Consecuencia aceptada en el ADR: la base es más
  estricta que el Matching en acentos.

**Estado**
- Deploy: no. El código no falla contra el índice viejo; sólo no frena repetidos hasta que
  se aplique la migración.
- Migraciones: `ws17` aplicada en `testing` (verificación previa 0, backup
  `concepto_liquidacion_bkp_ws17`, ALTER; `SHOW INDEX`: 7 partes, `Non_unique` 0). En
  producción, no.
- Verificación: suite completa después de integrar `main`, 969 passed y 1 xfailed (la
  preexistente); `test_concepto_duplicado.py` con 15 tests, cada uno visto fallar antes del
  cambio. Arranque real contra `testing` con tablas verificadas y sin avisos del índice.
  Smoke por HTTP: alta repetida, otra grafía y edición que choca dan 409 (la regla no
  cambia); copia dos veces, "0 copiados · 2 ya existían". No se probó el toast en el
  navegador. Revisión: 1 high (doble clic en Copiar daba 500) arreglado con su test; 6
  minor sin tocar; 4 descartados.
- Rollback: revertir el merge; en la base, el ALTER comentado al final de `ws17`.

**Pendiente**
- Deploy (para el dueño). Precondición: unificar desde la pantalla de Conceptos las 2
  reglas repetidas que hay en producción, verificar 0 repetidas con el `SELECT` de `ws17`,
  y recién ahí aplicar el ALTER y deployar.
- No correr `scripts/refrescar_testing.py` hasta que producción tenga el índice nuevo:
  pisaría el de `testing`.
- Después del deploy, en un PR aparte: regenerar `000_esquema_base.sql` y marcar `ws17`
  como `historica`.
- Minor sin tocar (BK #70): el encabezado de `ws17` no dice que no es idempotente; `_norm`
  de la copia no iguala Ł/Ø/Đ/Æ/Œ como la collation (daría 409); el `try/except
  IntegrityError` está repetido cuatro veces en `precios.py`; `_norm` duplica casi
  `_normalizar_nombre` del núcleo y comparte nombre con la de `solapamiento_service`, que se
  comporta distinto; el comentario de `models.py` dice "sin mayúsculas" en vez de "sin
  distinguir mayúsculas"; `COALESCE(codigo, -1)` iguala una regla sin código con una de
  código -1.
- Fuera de alcance: las líneas de campo repetidas por parte (tarea aparte, en curso).

## 2026-10-05 — Esquema base con el índice de ws17; ws17 pasa a histórica (cierre del ADR-0018)

**Mergeado**
- PR #71 (backend) — regenera `000_esquema_base.sql` desde producción con el
  `uq_concepto_unif` de `ws17` y marca `ws17` como `historica` en `migrations/ORDEN.txt`.

**Por frontera**
- Prod y Datos: en `000_esquema_base.sql` cambian sólo la fecha y el índice;
  `core/000_usuarios.sql` sólo la fecha (el script lo reescribe junto con el otro). Sale de
  `ORDEN.txt` el comentario que dejaba `ws17` pendiente.
- Docs: plan `docs/superpowers/plans/2026-10-04-esquema-base-ws17.md`.

**Decisiones**
- **Se regeneró desde producción, no desde `testing`.** Porqué: así lo dice la cabecera del
  archivo, y `testing` es una copia más vieja. No es riesgoso: ninguna migración posterior al
  000 sin `historica` (core/001, terceros/001-007) toca las tablas que exporta el script.

**Estado**
- Deploy: no hace falta (no cambia código ni base).
- Migraciones: ninguna.
- Verificación: `test_manifiesto_migraciones.py` 5 passed; suite completa 969 passed y 1
  xfailed (la preexistente). Sin revisión de código: es un archivo exportado y una línea del
  manifiesto.
- Corrige la entrada del 2026-10-04 (BK #70), que decía "Deploy: no" y dejaba pendientes el
  deploy y la regeneración del esquema: el BK #70 se deployó el 2026-10-04 (VPS `fd76263` →
  `a45e2c0`), con `ws17` aplicada en producción y en `testing`; el dueño probó el aviso en
  pantalla, y los backups `concepto_liquidacion_bkp_ws17` se borraron en las dos bases con su
  OK. La regeneración es este PR. Con el índice nuevo en producción, deja de regir la
  advertencia de no correr `scripts/refrescar_testing.py`.

**Pendiente**
- Los 6 minor del BK #70 (listados en la entrada del 2026-10-04).
- En `ORDEN.txt`, el comentario de Liquidación Terceros dice que sus migraciones no se
  aplicaron en producción; se aplicaron en el deploy del 2026-09-30.

## 2026-10-05 — Estado del trabajo (`docs/estado.md`), hook de arranque y skill `flujo-preliquidacion`

**Mergeado**
- PR #72 (backend) — agrega `docs/estado.md` (sólo lo vivo), el hook de arranque que
  imprime las 2 últimas entradas de la bitácora, la excepción de `main` ampliada a
  `docs/estado.md`, el agente `bitacora` y `/commit` adaptados, y la skill
  `flujo-preliquidacion`.
- PR #56 (front) — hermano: copia idéntica del hook con su `SessionStart`, bloque común de
  `AGENTS.md` igual al del backend, `CLAUDE.md` que importa el `estado.md` del backend y
  apunta a la skill, `.gitignore` con `.claude/worktrees/`.

**Por frontera**
- Docs: `docs/estado.md` nuevo; `AGENTS.md` (bloque común: "Estado del trabajo", "Bitácora
  y estado", fila nueva en "Dónde se anota cada cosa"), `CLAUDE.md`, `PUESTA-A-PUNTO.md`,
  `README.md`, `DOCUMENTACION.md`; `.claude/hooks/ultimas-entregas.mjs` y `SessionStart` en
  `.claude/settings.json` de los dos repos; agente `bitacora`, `/bitacora`, skill `commit`;
  skill nueva `.claude/skills/flujo-preliquidacion/`; `scripts/hooks/pre-commit` del backend
  (excepción "sólo `docs/BITACORA.md` y/o `docs/estado.md`", con `--no-renames`);
  `tests/hooks/` con 17 tests; plan
  `docs/superpowers/plans/2026-10-05-estado-y-flujo-preliquidacion.md`.

**Decisiones**
- Lo vivo en `docs/estado.md`, lo hecho en la bitácora. Porqué: lo pendiente vivía
  repartido entre la memoria de Claude (local, nadie más la ve) y las secciones "Pendiente"
  de cada entrada; ahora hay una sola lista compartida.
- **Se reabre la decisión del 2026-09-11** ("no extender la excepción de la bitácora"):
  `docs/estado.md` también va directo a `main`. Porqué: cambia en el mismo commit que
  cierra cada entrega, y por PR caería en la misma cadena de merges; tampoco ejecuta nada.
  Se edita en el checkout principal del backend, nunca en el worktree de una tarea. Repo
  público: sin IPs, hosts, URLs, credenciales, datos de terceros ni valores. Descartado:
  `estado.md` por PR (quedaría siempre atrasado) y fuera de git (Pitu no lo vería).
- La bitácora no cambia de orden (la más nueva abajo). Descartado: darla vuelta como el
  instructivo de origen.
- `flujo-preliquidacion` es una copia de la skill global `flujo` con lo de este sistema, y
  se usa en lugar de la global. Descartado: tocar la global (es genérica a propósito).
- El `pre-commit` usa `--no-renames`. Porqué: un `git mv` de cualquier archivo encima de
  `docs/estado.md` o `docs/BITACORA.md` pasaba en `main` y borraba el original sin PR (el
  hueco existía también con la bitácora; urgent de la revisión).

**Estado**
- Deploy: no aplica (no corre en el servidor).
- Migraciones: ninguna.
- Verificación: suite del backend 984 passed y 1 xfailed; hook probado a mano desde los
  dos repos, los worktrees y una carpeta vacía. Revisión: 1 urgent y 1 high arreglados, 6
  minor sin tocar (listados en el cuerpo del BK #72).
- Después del merge: `pre-commit` reinstalado en el clon de Gero; `verificar_agents_comun.sh`
  da 0 desde los dos repos; la carpeta de los dos repos tiene su `CLAUDE.md` y el hook
  (fuera de git); la memoria de Claude quedó sólo con preferencias.

**Pendiente**
- Probar una sesión nueva: aprobar el hook y responder "qué se hizo y qué está pendiente"
  sin leer archivos.
- Pitu: reinstalar los hooks en su clon del backend (`sh scripts/hooks/instalar.sh`); hasta
  entonces su `pre-commit` frena `docs/estado.md` en `main`.
- Deuda previa: la skill `commit` dice que las ramas son siempre `feature/` y el repo usa
  también `fix/`, `docs/` y `chore/`.

## 2026-10-07 — Alerta "Posible duplicado" en la línea (backend)

**Mergeado**
- PR #73 (backend) — alerta nueva en la línea, "Posible duplicado": una línea igual a otra
  de la quincena salvo en las horas (jornal o máquina), que paga una cantidad mayor a 0.
  Columna `es_posible_duplicado` con la migración `ws18`, marca en la API y en las
  estadísticas.

**Por frontera**
- Preliquidación: `motor_reglas.py` suma `clave_posible_duplicado`, `paga_cantidad` y
  `detectar_posibles_duplicados`; `detectar_duplicados` arma su clave a partir de la misma
  más las horas. Columna `es_posible_duplicado` en `preliquidacion_linea`, con el mismo
  ciclo que `es_duplicado` (se calcula al generar y se recalcula al actualizar con altas o
  bajas). API: la marca en cada línea, `posibles_duplicados` en las estadísticas (también
  en el lote), entra en `lineas_con_alerta` y en `solo_alertas`, y el mensaje de generar
  suma "· N posibles duplicados". 21 tests nuevos (`test_posible_duplicado.py` y ajustes
  en los de endpoints, estadísticas, generar y líneas).
- Prod y Datos: `migrations/preliquidacion/ws18_posible_duplicado.sql` agrega la columna y
  la llena para todas las quincenas existentes; `ws18` sumada a `migrations/ORDEN.txt`.
- Docs: "Línea duplicada" y "Posible duplicado" en
  `docs/modulos/preliquidacion/CONTEXT-preliquidacion.md`; plan
  `docs/superpowers/plans/2026-10-07-posible-duplicado.md`.

**Decisiones**
- Se exige cantidad > 0. Porqué: sin ese filtro, en `testing` salían 86 pares en 5
  quincenas, casi todos tareas por hora (talleres, traslados) que son trabajo real; con el
  filtro, sólo los del caso que originó la tarea. Descartado: marcar cualquier par igual
  salvo horas (demasiado ruido).
- Excluyente con Duplicado: una línea duplicada no lleva además esta marca. Porqué: el
  duplicado exacto ya dice más, y los contadores no se superponen.
- Columna guardada y no cálculo al vuelo. Porqué: mismo patrón que `es_duplicado`; horas y
  cantidades no se editan desde el sistema, así que la marca sólo cambia al generar o
  actualizar. Descartado: calcularla en cada lectura (los contadores son SQL y habría un
  mecanismo distinto al de duplicado).
- `ws18` llena las quincenas existentes. Porqué: sólo agrega una marca, no cambia importes
  ni conceptos.
- Cuenta en `lineas_con_alerta`. Porqué: decisión del usuario; sube el número de alertas de
  Inicio sin tocar su código.
- No cambian el Excel de exportación a sueldos ni la pantalla de Inicio. Porqué no
  registrado en el PR.
- Sin botón de descarte. Porqué: 2 casos en 5 quincenas.
- `dashboard_verificacion` no se toca. Porqué: ninguna pantalla lo usa.
- El campo es aditivo: el front actual sigue andando con este backend.

**Estado**
- Deploy: no.
- Migraciones: `ws18` aplicada en `testing` (no en producción).
- Verificación: suite completa 1007 passed, 1 xfailed (preexistente); cada par
  test+implementación con su test visto fallar antes. Antes de `ws18`, prueba en seco: el
  SQL del backfill y el motor en Python marcan exactamente las mismas líneas (4, los dos
  pares del caso real); después, 4 marcadas y 0 líneas con las dos marcas. Smoke por API
  contra `testing`: `/lineas` trae la marca, `/estadisticas` da `posibles_duplicados: 4`,
  `solo_alertas` las incluye, `generar` informa "· N posibles duplicados" y una segunda
  corrida deja todo igual (0 nuevas, 0 eliminadas). Revisión de dos ejes con verificador:
  0 urgent, 0 high, 6 minor, 4 descartados.

**Pendiente**
- PR hermano del front (Revisión y Verificación): todavía no abierto.
- Deploy sólo con OK. `ws18` es NO DIFERIBLE: aplicarla en producción antes de reiniciar el
  backend con este código; sin la columna, todo SELECT de líneas falla con "Unknown
  column".
- Hasta el deploy, no correr `scripts/refrescar_testing.py`: recrea las tablas de `testing`
  con el esquema de producción y borra la columna.
- Después del deploy, en PR aparte: regenerar `000_esquema_base.sql` y marcar `ws18` como
  `historica`.
- Rollback: `ALTER TABLE preliquidacion_linea DROP COLUMN es_posible_duplicado;` junto con
  el revert del PR (sin la columna, este código falla).
- Los 6 minor sin tocar, del cuerpo del BK #73:
  1. `ws18` quedó en `migrations/ORDEN.txt` dentro del bloque de preliquidación y no al
     final, como dice la regla literal; no puede fallar (no depende de las migraciones de
     Terceros).
  2. La condición "línea con alerta" vive en tres lugares (`estadisticas`,
     `estadisticas_batch`, `listar_lineas`): deuda previa que este cambio agranda; los tres
     quedaron iguales.
  3. El par `detectar_duplicados` + `detectar_posibles_duplicados` se repite en tres
     llamadas (en las tres el orden es correcto).
  4. `clave_posible_duplicado` también es la base de la clave de duplicado: tema de nombre.
  5. `(norm(hsjornal), norm(hsmaquina))` repetido en los dos detectores.
  6. La cabecera de `ws18` no nombra que la collation tampoco distingue mayúsculas en el
     legajo (la próxima actualización con altas o bajas lo corrige).

## 2026-10-07 — Alerta "Posible duplicado" en Revisión y Verificación (front)

**Mergeado**
- PR #57 (front) — pantallas de la alerta "Posible duplicado": badge, filtro, contador y
  aviso en Revisión; sección "Posibles duplicados" en Verificación. Hermano del BK #73.
- PR #74 (backend) — sólo docs: suma al plan el ajuste de lint de la etapa del front.

**Por frontera**
- Preliquidación (front): badge amarillo "POSIBLE DUPLICADO", segundo en la precedencia
  (DUPLICADO → POSIBLE DUPLICADO → INCOMPLETA → LEGAJO → EMPRESA, `ordenarLineas.js`);
  opción "Posible duplicado" en el filtro de alertas (`FiltrosBar.jsx`); contador propio en
  el banner (`AlertasBanner.jsx`); entra en "sólo alertas"; borde amarillo y aviso en el
  panel de la línea (`Revision.jsx`, `PanelLinea.jsx`). Verificación: sección "Posibles
  duplicados" con el molde de las otras, una tarjeta por persona, día y grupo con el
  importe en duda (la suma del grupo menos la línea de mayor importe) y, al abrirla, las
  líneas con hs jornal, hs máquina, tancadas, unidades, importe y badge. El agrupado vive
  en `pages/posiblesDuplicados.js`, lógica pura. 15 tests nuevos
  (`ordenarLineas.test.js` y `posiblesDuplicados.test.js`).
- Docs: `docs/superpowers/plans/2026-10-07-posible-duplicado.md` anota que el criterio
  "0 errores" de B3, B4 y B6 se midió con `npx eslint` sobre los archivos de cada paso.

**Decisiones**
- El agrupado de Verificación se calcula en el cliente, como las otras cinco secciones.
  Porqué: así le aplican la búsqueda, los filtros y la exclusión de mensualizados.
  Descartado: el endpoint `dashboard_verificacion`, que ninguna pantalla consume y no
  excluye mensualizados.
- Diseño con la línea actual. Porqué: decisión del usuario; viene una refacción completa de
  UX/UI después de esta tarea.
- Un grupo que por los filtros queda con una sola línea se oculta. Porqué: sin par no hay
  duda que mostrar.
- No cambia la pantalla de Inicio. Porqué: su número de alertas sube solo, porque el
  backend ya cuenta los posibles en `lineas_con_alerta`.
- No cambia el Excel de exportación. Porqué no registrado en el PR.
- "POSIBLE DUPLICADO" va segundo en la precedencia de badges. Porqué no registrado en el PR.
- El criterio de lint se mide por archivos tocados (BK #74). Porqué: `npm run lint` ya da 6
  errores en `main`, todos en `.claude/hooks/ultimas-entregas.mjs` (del FT #56); esa deuda
  quedó en "A futuro" de `docs/estado.md`.
- El front anda también contra un backend sin el campo (lo trata como falso): no hay orden
  obligatorio entre los dos deploys; el que importa es `ws18` antes de reiniciar el backend.

**Estado**
- Deploy: todavía no (se hace a continuación, con entrada de deploy aparte).
- Migraciones: ninguna en estos PRs (`ws18` es del BK #73, aplicada sólo en `testing`).
- Verificación: `npm test` 35/35 (cada test nuevo visto fallar antes); `npm run build` OK;
  `npx eslint` sobre los archivos tocados, 0 errores. Smoke en el navegador contra
  `testing`, en la quincena del caso que originó la tarea: banner con "· 4 posibles
  duplicados", el filtro muestra justo esas 4 líneas, el panel trae el aviso; Verificación
  con contador 2, las dos tarjetas con su importe en duda y, al abrir, las horas máquina
  distintas; la búsqueda filtra las tarjetas; Inicio muestra el mismo número de alertas que
  la barra de Revisión. Revisión de dos ejes con verificador: 0 urgent, 0 high, 6 minor, 4
  descartados.

**Pendiente**
- Deploy de BK #73 + FT #57, sólo con OK: `ws18` en producción antes de reiniciar el
  backend; hasta entonces, no correr `scripts/refrescar_testing.py`.
- Después del deploy, en PR aparte: regenerar `000_esquema_base.sql` y marcar `ws18` como
  `historica`.
- Rollback del front: revertir el PR y redeployar el front (swap de carpeta); no toca datos.
- Los 6 minor sin tocar, del cuerpo del FT #57:
  1. Los textos nuevos usan ⚠ y ✓, como los existentes, aunque `GUIA-MODULOS.md` (regla 22)
     dice "sin emojis en la interfaz": queda para la refacción de UX/UI, con los previos.
  2. En `claseLinea` (`Revision.jsx`) el `if` nuevo es redundante: la línea caería igual en
     `'alerta'` más abajo.
  3. La disyunción de flags de alerta está en `PanelLinea.jsx` y `Revision.jsx`, el literal
     'POSIBLE DUPLICADO' en 4 lugares y `ListaPosiblesDuplicados` rehace el badge: para la
     refacción.
  4. `valor` (importe en duda) y `decimal()` que devuelve 'None' (espejo de Python) son
     nombres explicados sólo por comentario.
  5. Misma persona y día con dos grupos (dos fincas): las dos tarjetas se ven iguales hasta
     abrirlas.
  6. El comentario de `decimal()` dice "como `normalizar_decimal`", pero `toFixed` no
     redondea igual que ROUND_HALF_UP; no puede fallar porque la API manda dos decimales.
- Visto en el smoke: el importe se muestra "$53.644,8" en vez de "$53.644,80" (cosmético).
  Lo de "Cargando líneas…" al cambiar de sección es previo y ya está en "A futuro".

## 2026-10-07 — Deploy a producción de la alerta "Posible duplicado"

Entrada de deploy: no anota un merge sino el deploy de BK #73, BK #74 y FT #57, ya anotados
arriba. Corrige su "Deploy: todavía no". El detalle técnico va en `docs/DEPLOY.md` (local,
fuera de git).

**Qué se deployó**
- Backend: de `a45e2c0` a `d35ea04` (BK #73 y #74 más la bitácora).
- Frontend: de `adc284c` a `93ba472` (FT #57), con build desde el checkout del front en
  `main`, idéntico a `origin/main`.
- Orden: código del backend sin reiniciar, `ws18`, reinicio del backend y frontend, en la
  misma ventana. Autorizado por el usuario.

**Decisiones** (porqués que las entradas del merge daban como no registrados; los dio el
usuario en la entrevista)
- No cambia el Excel de exportación a sueldos. Porqué: es lo que recibe sueldos y una
  columna nueva puede romper cómo lo leen; el posible duplicado es una duda para el
  liquidador, no un dato para sueldos.
- "POSIBLE DUPLICADO" va segundo en la precedencia de alertas. Porqué: es el único aviso,
  además del duplicado, que puede significar pagar dos veces; una línea incompleta no paga
  de más.

**Estado**
- Deploy: sí, backend y frontend. Frontend con swap de carpeta; la versión anterior queda
  como rollback.
- Migraciones: `ws18` aplicada en producción antes del reinicio. Antes, prueba en seco de
  sólo lectura: el SQL del backfill y el motor en Python marcan las mismas 4 líneas, todas
  de la quincena del caso que originó la tarea. Después: 4 marcadas y 0 líneas con las dos
  marcas. El primer intento del script cayó entre el ALTER y los UPDATE (sin efecto
  visible: la columna existía en 0 y corría el código viejo); el segundo completó.
- Verificación: un solo arranque del backend, conectado a la base de producción, con tablas
  y columnas verificadas; `/health` ok. Build del front con 44 assets y el mismo bundle en
  local y en el servidor; el sitio responde 200 y sirve el bundle nuevo. Smoke en sólo
  lectura con el servicio de la app: la quincena tiene 4 posibles duplicados, ninguna línea
  con las dos marcas, y las estadísticas (individual y por lote) y "sólo alertas" las
  cuentan. Journal sin errores.
- Rollback: backend al commit anterior y reinicio (el código viejo anda con la columna
  nueva); la columna se borra sólo junto con el revert del código; swap inverso de la
  carpeta del front.

**Pendiente**
- Mirar la alerta en el sitio real (Revisión y Verificación de la quincena del caso).
- PR aparte: regenerar `000_esquema_base.sql` y marcar `ws18` como `historica`.
- Queda cerrado el pendiente de deploy de las entradas del merge. Se puede volver a
  refrescar `testing` desde producción: las dos bases tienen la columna.

## 2026-10-08 — Skill `impeccable` en el front y regla de usarla en toda interfaz

**Mergeado**
- PR #75 (backend) — regla de interfaz con `impeccable` en `AGENTS.md`, `GUIA-MODULOS.md`
  (reglas 20 y 8.3) y la sección "Tareas con interfaz" de `flujo-preliquidacion`, con su plan.
- PR #58 (frontend, hermano) — instala la skill `impeccable` (copiada tal cual, con
  `LICENSE` y `NOTICE.md`) y sus 4 agentes, sin sus hooks; motor en `.impeccable/` del
  proyecto, ignorado por git y por eslint.

**Por frontera**
- Docs: sección nueva "Cambios de interfaz" en el bloque común de `AGENTS.md` (igual en los
  dos repos) y dos filas en "Dónde se anota cada cosa" (`DESIGN.md` y `PRODUCT.md` del
  front). `GUIA-MODULOS.md`: reglas 20 y 8.3. `flujo-preliquidacion`: qué comando de
  `impeccable` entra en cada fase.
- Preliquidación y Liquidación Terceros (front): todo cambio visual y toda feature nueva con
  interfaz se hacen con `impeccable`, en los dos módulos.

**Decisiones**
- Todo cambio visual o feature nueva usa `impeccable`, Terceros incluido. Porqué: pedido del
  usuario; la refacción de UX/UI posterior es sólo de Preliquidación y va en otra tarea.
- Instalada sólo en el repo del front. Porqué: pedido del usuario. Descartado: instalación
  global; el backend, que no tiene interfaz.
- Sin los hooks de `impeccable`. Porqué: correrían el motor en cada `Edit`/`Write` y al
  cerrar cada respuesta. Descartado: el instalador `npx impeccable install`, que escribe en
  carpetas globales del harness.
- La skill va copiada tal cual y se actualiza reemplazando la carpeta entera en un PR.
  Porqué: que el diff contra el original sea siempre cero.
- La estética se nombra en `src/index.css` "y en `DESIGN.md` cuando exista". Porqué:
  `DESIGN.md` recién lo escribe el `init` de la refacción, y una regla no puede apuntar a un
  archivo inexistente (high de la revisión).
- Descartado: el smoke "en escritorio y en celular" del primer borrador del flujo, porque
  nadie decidió exigir celular (high de la revisión); una regla 23 en la guía, porque
  renumeraría las siguientes y la bitácora cita "la regla 22".

**Estado**
- Deploy: no; no cambia la app.
- Migraciones: ninguna.
- Verificación: el motor 0.1.11 corrió con los dos lanzadores (`sh` y `.cmd`, exit 0) y bajó
  a `.impeccable/` del worktree. Lint del front: 6 errores, los mismos de `main`.
  `npm test` 35/35, build OK. pytest del backend: 1007 passed, 1 xfailed. Revisión de dos
  ejes: 0 urgent, 2 high arreglados, 2 minor sin tocar, 8 descartados.

**Pendiente**
- Deuda previa: dentro del `pre-commit`, `scripts/verificar_agents_comun.sh` no encuentra el
  repo hermano porque git exporta `GIT_DIR`, así que el chequeo del bloque común nunca corre
  al commitear. Sugerida como tarea aparte.
- Avisarle a Pitu que la regla de usar `impeccable` también le aplica en Terceros.
- Los 2 minor sin tocar están en el cuerpo del FT #58.
- Próximo: la refacción de UX/UI de Preliquidación, con el flujo completo y `/impeccable init`.

## 2026-10-08 — El chequeo del bloque común de `AGENTS.md` corre dentro del `pre-commit`

Cierra la deuda previa que anotó la entrada anterior.

**Mergeado**
- PR #76 (backend) — `scripts/verificar_agents_comun.sh` encuentra al repo hermano cuando lo
  llama el `pre-commit` desde un worktree; test nuevo y plan.
- PR #59 (frontend, hermano) — el mismo arreglo en su copia del script, idéntica a la del
  backend.

**Por frontera**
- Controles (repo, fuera de las fronteras de código): `repo_de()` del script corre el
  `git -C` sin las variables de `git rev-parse --local-env-vars`, en los dos repos.
  `tests/hooks/test_verificar_agents_comun.py` nuevo en el backend, que cubre también el
  script del front (el front no tiene pytest).
- Docs: plan `docs/superpowers/plans/2026-10-08-verificar-agents-en-hook.md`.

**Decisiones**
- Causa: al commitear desde un worktree, git le exporta `GIT_DIR` absoluto al hook, y
  `git -C <carpeta> remote get-url origin` devolvía el origin del repo propio para cualquier
  carpeta; el aviso nunca comparaba nada. Desde el checkout principal sólo pasa un
  `GIT_INDEX_FILE` relativo, que no molesta.
- Se limpian las variables de `git rev-parse --local-env-vars`. Porqué: es la lista que
  mantiene git (incluye `GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY` y las demás) y es POSIX puro.
  Descartado: `env -u` con las variables nombradas a mano; un `unset` al principio del
  script, porque las llamadas de arriba (`--show-toplevel`, `--git-common-dir`) sí tienen que
  respetar el repo del hook.

**Estado**
- Deploy: no; es tooling de desarrollo. Cada clon toma el arreglo con el próximo pull, sin
  reinstalar los hooks.
- Migraciones: ninguna.
- Verificación: los dos casos del test nuevo (script con `GIT_DIR` exportado; commit desde
  un worktree con el `pre-commit` real y un bloque distinto en el hermano) fallaron antes
  del arreglo con exit 2 y pasan después. `tests/hooks/`: 19 passed. Suite completa: 1009
  passed, 1 xfailed. Reproducción manual con `GIT_DIR` exportado: exit 0 desde los worktrees
  de los dos repos (en el front, antes exit 2); `diff` entre los dos scripts vacío. Revisión
  de dos ejes con verificador: 0 urgent, 0 high, 3 minor, 4 descartados.

**Pendiente**
- Los 3 minor sin tocar están en el cuerpo del BK #76 (helpers del test repetidos de
  `test_pre_commit.py`, un nombre de parámetro, una fixture sin usar).
- Deuda previa, ajena al PR: el script compara el `AGENTS.md` del directorio de trabajo y no
  el stageado. No frena commits.

## 2026-10-08 — Diseño del módulo Facturación

**Mergeado**
- PR #78 (backend) — sólo docs: glosario, pantallas y plan del módulo Facturación, y el
  ADR-0019. Sin PR hermano en el front.

**Por frontera**
- Docs: `docs/modulos/facturacion/` nuevo (`CONTEXT-facturacion.md`, `pantallas.md`,
  `plan-facturacion.md` y `fuentes/LEEME.md`), `docs/adr/0019-adjuntos-en-carpeta-del-vps.md`
  y la fila de Facturación en `CONTEXT-MAP.md`.

**Decisiones**
- Módulo solitario: no lee mano de obra de Preliquidación. Porqué: el resultado operativo
  (facturación − MO − combustible) queda para un futuro Gerencial que consolide módulos, con
  su propio ADR, y así el ADR-0013 queda intacto. Descartado: un contrato de lectura en el
  núcleo ahora.
- Carga manual más un importador por formato, con equivalencias guardadas por cliente.
  Descartado: leer el sistema contable (API paga y detalle dudoso para traducir a tareas).
- El Grupo de facturación de cada tarea decide qué cantidad del campo se compara; una tarea
  sin grupo avisa, mientras que el informe actual la deja en cero en silencio.
- Cruce por rango de fechas libre, que arranca en el mes. Descartado: por quincena, porque
  una diferencia de una quincena se compensa en la siguiente.
- Adjuntos en una carpeta del VPS (ADR-0019). Descartados: en la base y en Google Drive.
- Permisos por capacidades (consultar, cargar, mantener), para que el cambio de esquema de
  permisos sólo toque el mapeo.
- Cosecha fuera: se factura distinto y probablemente sea un submódulo.
- El plan de implementación se difiere hasta que estén mergeados el cambio de permisos y el
  refinamiento de Preliquidación. Porqué: cambian los componentes que el módulo reutiliza, y
  un plan hecho hoy habría que rehacerlo. Es un desvío de la skill aprobado por el usuario.
- Los nombres de clientes y los orígenes de los datos quedan en `fuentes/`, fuera de git,
  porque el repo es público.

**Estado**
- Deploy: no; sólo docs.
- Migraciones: ninguna.
- Verificación: sin tests ni revisión de código (sólo docs). Se controló que ningún archivo
  versionado tenga nombres de clientes, hosts ni URLs.

**Pendiente**
- El cambio del esquema de permisos (tarea aparte del núcleo) y el plan de implementación
  después del refinamiento.
- El respaldo de la carpeta de adjuntos y confirmar con las contadoras las horas del segundo
  tractor en pulverización (en `docs/estado.md`).

## 2026-10-08 — Refinamiento de la interfaz de Preliquidación y Gerencial

**Mergeado**
- PR #60 (front) — E0: `PRODUCT.md` (contexto de producto para `impeccable`) y `.impeccable/`
  en lista blanca del `.gitignore`.
- PR #61 (front) — E1: barra de filtros común, estado por pantalla al navegar e íconos en
  Revisión, el banner, el panel de la línea y Mantenimiento.
- PR #77 (backend) — E2: el listado de quincenas trae el desglose de alertas por tipo; entra
  el plan de la tarea.
- PR #62 (front) — E3: Inicio con el detalle de alertas y a todo el ancho, menú que recuerda
  si está contraído y "Generar" en la última quincena generada. Hermano del BK #77.
- PR #63 (front) — E4: Verificación con tablas ordenables y el detalle de la persona en un
  modal.
- PR #64 (front) — E5: Conceptos y Gerencial con la barra común.
- PR #79 (backend) — E6, sólo docs: `docs/AYUDA.md` describe la interfaz refinada y el plan
  suma los pasos R4 a R10.

**Por frontera**
- Núcleo (front): `src/core/ui/iconos.jsx` con 15 íconos nuevos y la prop `enTexto`, que
  alinea el ícono con el texto desde `Icono.module.css`. `src/core/layout/Layout.jsx`
  recuerda en `localStorage` (con try/catch) si el menú está contraído, también en Terceros;
  se borra la clase `shellCollapsed`, que no existía.
- Preliquidación (backend): `GET /preliquidacion/` devuelve por quincena `incompletas`,
  `duplicados`, `posibles_duplicados`, `alerta_legajo` y `sin_empresa`, con default 0
  (`api/preliquidacion.py`, `schemas.py`). Test nuevo:
  `tests/preliquidacion/test_listado_preliquidaciones.py`.
- Preliquidación (front):
  - Barra común (`components/FiltrosBar.jsx` con su CSS Module y `SelectorQuincena.jsx`):
    quincena, búsqueda, Filtros, alertas y Limpiar, siempre en ese orden, y la fila
    "Filtrando por" con un chip removible por filtro activo, incluidos la búsqueda y el
    "sólo alertas" del banner. Las opciones en cascada salen de lo que ya pasa la búsqueda y
    las alertas. Lógica pura con tests en `pages/`: `filtrarLineas.js`, `formatoQuincena.js`
    (un solo formato, "1ra quincena septiembre 2026"), `opcionesCascada.js` y
    `estadoGuardado.js`. El estado de cada pantalla vive en memoria (`estadoPantallas.js`):
    se borra con F5, al cerrar sesión y al entrar con otro usuario.
  - Revisión: la barra con selector de quincena, sin el filtro de Empresa, y filtros,
    búsqueda y orden conservados al ir y volver. Mantenimiento (`CategoriasOperarios.jsx`):
    quincena y búsqueda, arranca en la última quincena generada.
  - Inicio (`Dashboard.jsx`): cada quincena con alertas muestra cuántas son incompletas,
    duplicadas, posibles duplicados, legajo inválido y sin empresa, y un botón "Detalle"
    con qué significa cada tipo (`desgloseAlertas.js`, con test); sin el `max-width`, a todo
    el ancho y alto.
  - Verificación: las cuatro listas ordenables en los dos sentidos y de vuelta al original,
    con `aria-sort` (`TablaOrdenable.jsx`, `pages/ordenarFilas.js` con test), orden guardado
    por sección; el detalle de la persona en `ModalDetalle.jsx` (mouse, Enter o Espacio;
    Escape, cruz o click afuera; foco de vuelta en la fila). Plantas y Tancadas vs Jornal
    ordenables con el Total abajo (`ControlesJornal.jsx`), también en Gerencial. Se borra
    `InputBusqueda.jsx`.
  - Conceptos: una sola barra sobre las solapas con los filtros de la solapa abierta, un
    texto por solapa de alcance sobre cómo se combina su regla con las demás, y solapa,
    quincena, búsqueda y filtros guardados al navegar. Gerencial: la barra con período y
    empresa, a todo el ancho, estado guardado, en sólo lectura.
  - Íconos en vez de símbolos y emojis (▲▼, ✓, ✕, ⚠, ⊞, ↓, ⇄, ›) en todas esas pantallas.
    Tests del front: de 35 a 76.
- Docs: en el front, `PRODUCT.md`, `.gitignore` y la viñeta "Interfaz" de `CLAUDE.md`. En el
  backend, `docs/AYUDA.md` (sección nueva "Moverse por el sistema", historial con el
  desglose, Verificación con 7 controles, Conceptos con seis solapas y la vista "Por
  concepto", y una sección de la vista gerencial) y el plan
  `docs/superpowers/plans/2026-10-08-refinamiento-preliquidacion.md`, con R1 a R10.

**Decisiones**
- Se refina la estética actual, no se reemplaza (`PRODUCT.md`). Porqué: el usuario descartó
  un rediseño y las estéticas temáticas.
- Todo lo que entró lo vio y aprobó el usuario en un prototipo antes del plan (desvío de la
  skill aprobado por él). Porqué de cada pantalla, pedidos del usuario: los filtros en el
  mismo lugar en todas las pantallas y el estado guardado al navegar; que las alertas del
  historial digan qué está pendiente y que el Inicio se vea entero con el menú contraído;
  ordenar las tablas de Verificación y un detalle más claro; en Conceptos, sólo filtros y
  detalles y explicar qué regla aplica; en Gerencial, los mismos cambios que en
  Preliquidación en cuanto se pueda.
- De `.impeccable/` sólo van a git `config.json`, `design.json` y `live/config.json` (R1).
  Porqué: ahí `impeccable` guarda configuración que se comparte, y las capturas de
  `review/` salen de pantallas de `testing` con nombres reales en un repo público.
  Descartado: ignorar rutas sueltas (primer borrador), que dejaba versionables capturas,
  sesiones y mocks.
- La cascada y el estado guardado van en módulos puros. Porqué: testearlos con `npm test` sin
  React.
- El estado por pantalla se limpia en cualquier cambio de token, no sólo al pasar a null.
  Porqué: `/login` se abre con la sesión abierta y `login()` cambia de usuario sin pasar por
  null; quien entra no tiene que ver los filtros de la persona anterior.
- La alineación de los íconos va en un CSS Module del núcleo (prop `enTexto`). Porqué:
  GUIA-MODULOS regla 20 prohíbe CSS global nuevo. Descartado: la clase global `icono-texto`
  del prototipo y una excepción a la regla.
- Revisión sin el filtro de Empresa. Porqué: no se usa.
- El desglose de alertas sale del listado (BK #77). Porqué: `estadisticas_batch` ya calculaba
  esos conteos, así que no agrega consultas. Descartado: un pedido a `/estadisticas` por
  quincena en cada visita al Inicio, como hacía el prototipo.
- Se exponen cinco enteros con default 0 y no `por_empresa` entero. Porqué: el front sólo
  necesita cuántas líneas no tienen empresa, y el default deja andar a un cliente que no los
  lee y al front nuevo contra un backend viejo, sin orden obligatorio de deploy. No cambia
  qué cuenta `lineas_con_alerta` ni se toca `preliquidacion_service.py` (zona sensible).
- El Inicio vuelve a pedir el listado en cada visita (`refetchOnMount: 'always'`). Porqué:
  Revisión y Conceptos no lo invalidan al editar.
- El desglose se muestra sólo en las filas con líneas con alerta. Porqué: "sin empresa" no
  cuenta en el total de alertas (regla del backend, fuera de alcance) y una quincena OK no
  tiene que mostrar "Detalle".
- Contraste de los chips del historial (R5) y del dato destacado del modal (R7): texto en el
  color normal y el tono en el fondo y un borde, sin tocar tokens. Porqué: elección del
  usuario. Descartado: oscurecer los tokens de alerta, que afecta a todo el sistema, y
  dejarlo como estaba.
- En Verificación el orden se guarda por sección y no uno común. Porqué: cada tabla tiene
  columnas distintas.
- El modal devuelve el foco al elemento anterior y encierra el Tab (ajuste A5 del plan).
  Porqué no registrado en el PR.
- `InputBusqueda.jsx` se borra (A6). Porqué: la búsqueda vive en la barra común y el
  componente quedaba sin uso.
- La búsqueda de Conceptos se mantiene al cambiar de quincena (decisión del usuario) y se
  limpia al cambiar de solapa, como en `main`.
- R8: la barra de Conceptos se vuelve a montar sólo cuando Conceptos cambia la búsqueda desde
  afuera. Descartado: darle a `FiltrosBar` una búsqueda controlada, porque es un componente
  compartido por cinco pantallas; queda para otro PR.
- `docs/AYUDA.md` corrige también lo que ya estaba desactualizado antes del refinamiento
  ("4 pestañas" con "Específicos", emojis del menú, formatos viejos de quincena, el precio
  masivo mal explicado). Porqué: el asistente responde con esta guía. Suma la vista
  gerencial porque el asistente también atiende al gerente (el chat está montado en el marco
  Gerencial y el endpoint sólo pide sesión). Saca "Sueldos / Empleados (todavía no
  disponible)", porque la pantalla no existe.

**Estado**
- Deploy: no. Espera el OK del usuario y es de front y backend: el asistente lee
  `docs/AYUDA.md` una vez por proceso (`lru_cache` en `app/core/asistente.py`), así que la
  guía nueva necesita pull y reinicio del backend. Por los defaults del BK #77 no hay orden
  obligatorio entre los dos.
- Migraciones: ninguna.
- Respaldo del prototipo: rama local `respaldo/prototipo-refinamiento` del front, sin push.
  Los worktrees del front se borraron.
- Verificación:
  - Front: `npm test` 76/76, con cada par de lógica visto en rojo contra un stub;
    `npm run build` OK; `npx eslint` de los archivos tocados, 0 errores; detector de
    `impeccable`, sin hallazgos. Conformidad con el prototipo (FT #64): el diff contra
    `respaldo/prototipo-refinamiento` muestra sólo los ajustes A1 a A7, los arreglos R2 a
    R10 y los tests.
  - Backend: 1013 passed, 1 xfailed (BK #77); `tests/core/test_asistente_docs.py`, 6 passed
    (BK #79).
  - Smoke contra `testing` en cada etapa (el detalle está en cada PR). No probado: una
    cuenta sólo operador y otra sólo gerente (hay una sola cuenta).
  - Revisión de dos ejes con verificador en cada PR menos E6 (sólo docs, como define el
    plan); de E1 en adelante, también `/impeccable critique` y `audit`. Arreglados:
    - R1 (high, E0): la lista blanca de `.impeccable/`.
    - R2 (urgent, E1): al cambiar de quincena con el selector, el panel seguía con la línea
      de la quincena anterior y "Guardar" la editaba; Revisión se vuelve a montar con
      `key={id}`.
    - R3 y R6 (high, E1 y E4): Mantenimiento y Verificación decían "Todavía no hay
      quincenas generadas." mientras cargaba o si fallaba la lista.
    - R4 (high, E3): "Generar" quedaba habilitado con el mes en curso mientras cargaba el
      listado, y un clic temprano generaba la quincena equivocada.
    - R5 y R7 (high, E3 y E4): contrastes de 3,69, 3,89 y 4,26:1, que pasan a 11,62, 12,09 y
      13,22:1.
    - R8 (high, E5): la barra de Conceptos perdía el foco del selector con las flechas, y al
      volver a tocar la solapa el campo seguía con la búsqueda vieja.
    - R9 (high, E5): la variación de los KPI de Gerencial se leía sin signo y el badge
      "Reemplaza al común" quedó sin texto accesible.
    - R10 (deuda previa, pedida por el usuario, E5): Conceptos distingue carga y error de la
      lista de quincenas.

**Pendiente**
- Deploy de front y backend juntos, sólo con OK del usuario (en `docs/estado.md`).
- Decisiones del usuario: los contrastes de tokens compartidos por debajo de AA (`badge-*`;
  warn, danger e info sobre su `-dim`) y el padding de `FiltrosBar` (16 px) contra el de las
  páginas (24 o 28 px).
- Fuera de los PRs, código para más adelante: `app/core/asistente.py` le da al modelo, de
  ejemplo, el botón "▶ Generar / Actualizar", con un símbolo que ya no existe; y `/gerencial`
  no está en las `pantallas` de `rutas.jsx` del front, así que el asistente no sabe en qué
  pantalla está el gerente.
- Minors sin tocar, en el cuerpo de cada PR: 2 del FT #60, 9 del FT #61, 3 del BK #77, 9 del
  FT #62, 9 del FT #63 y 10 del FT #64. La deuda previa vista en las revisiones está en los
  cuerpos de FT #61 a FT #64.

## 2026-10-09 — Deploy a producción del refinamiento de Preliquidación y Gerencial

Entrada de deploy: no anota un merge sino el deploy del refinamiento (FT #60 a #64, BK #77 y
#79), ya anotado arriba. Corrige su "Deploy: no". El detalle técnico va en `docs/DEPLOY.md`
(local, fuera de git).

**Qué se deployó**
- Backend: de `d35ea04` a `46e4b2b` (BK #75 a #79). De código, sólo el BK #77; el resto son
  docs y tooling. El BK #79 trae `docs/AYUDA.md`, que el asistente lee una vez por proceso:
  por eso el backend se reinició en la misma ventana.
- Frontend: de `93ba472` a `5265bd4` (FT #58 a #64), con build desde el checkout del front
  en `main`, idéntico a `origin/main`.
- Orden: backend y después frontend, en la misma ventana. El BK #77 sólo agrega campos con
  default 0, así que no había orden obligatorio. Autorizado por el usuario.

**Estado**
- Deploy: sí, backend y frontend. Frontend con swap de carpeta; la versión anterior queda
  como rollback.
- Migraciones: ninguna. Dependencias nuevas: ninguna.
- Verificación: un solo arranque del backend, conectado a la base de producción, con tablas
  y columnas verificadas; `/health` ok. Build del front con 47 assets y el mismo bundle en
  local y en el servidor; el sitio responde 200 y sirve el bundle nuevo. Smoke en sólo
  lectura con el endpoint del listado: trae los cinco campos del desglose, y la quincena del
  2026-08-16 da los mismos números que el smoke del deploy anterior (150 líneas con alerta,
  10 duplicados, 4 posibles duplicados). Journal sin errores ni 5xx desde el reinicio.
- Rollback: backend al commit anterior y reinicio (el front nuevo muestra sólo el total de
  alertas contra el backend viejo); swap inverso de la carpeta del front. Sin DDL ni datos
  tocados.

**Pendiente**
- Mirar el refinamiento en el sitio real.
- En producción hay una quincena del 2026-10-16 generada y sin líneas; "Generar" del Inicio
  arranca en la última generada, así que va a proponer esa.
- Queda cerrado el pendiente de deploy de la entrada del refinamiento.
