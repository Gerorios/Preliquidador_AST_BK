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
