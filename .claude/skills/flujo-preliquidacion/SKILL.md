---
name: flujo-preliquidacion
description: >
  La versión del Sistema de Preliquidación de La Asturiana de la skill `flujo`
  (backend_preliquidacion y frontend_preliquidacion): se usa en lugar de la
  global, nunca las dos. El circuito completo de una tarea de desarrollo, en dos
  carriles - corto para fixes y tareas simples (plan de 5 líneas, ejecución en
  sesión, una ronda de revisión) y completo para el resto (entrevista con ADRs y
  glosario, plan con el agente planificador Fable/high, ejecución por pares
  test+implementación con el agente ejecutor Opus/high, revisión con verificador
  y severidad). Usar al empezar cualquier tarea que modifique alguno de los dos
  repos. No usar para preguntas, explicaciones ni consultas de estado.
---

# Flujo de trabajo

Cinco fases y **dos carriles**. Cada fase termina en algo revisable, y **tres
fases frenan esperando al usuario** en los dos carriles. Nunca saltees una fase
en silencio: si la salteás, decilo y por qué.

**Esta es la skill de flujo del Sistema de Preliquidación**, para los dos
repos (`backend_preliquidacion` y `frontend_preliquidacion`). Se usa **en lugar
de la global `flujo`, nunca las dos**: esta es completa.

**Mandan `AGENTS.md` y `CLAUDE.md`** (y los `CLAUDE.local.md`, con lo de cada
máquina). El bloque común de `AGENTS.md` es idéntico en los dos repos; el
diario, el estado, el glosario y los ADR viven en el backend. Si algo de acá
choca con esos archivos, valen ellos. Si no definen algo que esta skill
necesita, preguntá en vez de asumir.

```
                 CORTO (fix / tarea simple)          COMPLETO (el resto)
0. Entrevista    solo si hay una decisión abierta     grilling + domain-modeling
1. Plan          vos, 5-10 líneas → archivo           planificador (Fable/high) → archivo
2. Aprobación    PARÁS ⏸ (OK de 30 s)                 PARÁS ⏸ + aviso
3. Ejecución     vos, en sesión, test rojo primero    ejecutor (Opus/high), un PAR por vez
4. Revisión      suite 1 vez → review → verificador   ídem, 2 rondas si toca zonas sensibles
                 → PARÁS ⏸                            → PARÁS ⏸ + aviso
5. Entrega       mostrar → OK → PR → merge → bitácora ídem                          ⏸
```

---

## Elegir el carril (antes de todo)

Leé el código afectado, dos minutos, y decidí. **Carril corto** si se cumplen
las cuatro:

1. La decisión ya está cerrada (el usuario dijo qué y cómo, o es un bug con
   comportamiento esperado obvio).
2. Hasta **3 archivos de código** (los tests y docs no cuentan).
3. **Sin DDL.**
4. **Sin cambio de contrato** entre partes que se deployan por separado: la
   API entre `backend_preliquidacion` y `frontend_preliquidacion`.

Si no, **carril completo**. Ante la duda, completo. Decilo en una línea al arrancar: "Carril corto: 1
archivo, sin API" o "Carril completo: hay DDL y decisiones abiertas". Si en el
medio descubrís que el corto no alcanza (aparece una decisión, un cuarto
archivo, un DDL), **pasás al completo desde donde estés y avisás**. Nunca al
revés en silencio.

**Antes de editar, aislá el trabajo.** Entrá al worktree con `EnterWorktree`
(las ediciones en el checkout compartido se rechazan), uno en cada repo que
toque la tarea. Dependencias en el worktree:

- **Frontend**: no instales. Enlazá el `node_modules` del checkout principal
  con un junction, desde el worktree:
  `cmd /c mklink /J node_modules <checkout principal del front>\node_modules`.
  **Antes de borrar el worktree, quitá el junction con `cmd /c rmdir
  node_modules`**, que borra sólo el enlace. **Nunca `rm -rf`** (ni ningún
  borrado recursivo) sobre el junction: sigue el enlace y vacía el
  `node_modules` del checkout principal.
- **Backend**: el venv del checkout principal sirve desde el worktree
  (activalo o llamá a su `python` por ruta absoluta); no crees otro.

**Configuración en el worktree**: nunca copies el `.env` real a un worktree
(el de una máquina de desarrollo puede traer credenciales de producción). Para
**tests**, creá un `.env` ficticio a partir de `.env.example` (hosts
`.invalid`, claves de prueba) o pasá las variables en línea al correr
`pytest`. Para **levantar la app**, exportá al proceso sólo las variables de
`testing` (`DB_PROPIA_NAME=testing`), nunca `DB_PROD_*` ni `DB_DEV_*`, y nunca
`PERMITIR_BASE_PRODUCCION` (ADR-0014: `preliquidacion` es producción y ninguna
máquina de desarrollo apunta ahí). Anotá en cada briefing cómo se cargan las
variables (ruta del `.env` ficticio o variables en línea).

Anotá la **ruta absoluta** de cada worktree: va en cada briefing.

---

## Fase 0 — Entrevista

**Completo:** cuando el pedido tiene decisiones abiertas que no te
corresponden — alcance, reglas de negocio, casos borde, qué se muestra.
**Antes de preguntar, buscá antecedentes** en `docs/BITACORA.md` y `docs/adr/`
del backend (grep por los términos del tema): ahí está el porqué de lo
decidido y lo descartado. Si no está, no asumas que no se decidió: preguntá.
Invocá `grilling` (una pregunta por vez, con tu recomendación, citando los
antecedentes que encontraste) y, si aparece vocabulario nuevo o una decisión
arquitectónica que sobrevive a la tarea, `domain-modeling` para el ADR y el
glosario (el que indique `CONTEXT-MAP.md`). **Un ADR es un compromiso y se
escribe sólo con el usuario**, nunca como resumen de lo que pasó. **Listá los
ADR en el worktree del backend, no en el checkout local**: puede estar atrasado
y te hace repetir un número.

**Corto:** sin entrevista. Si aparece **una** decisión abierta, una sola
pregunta con recomendación y seguís. Si aparecen dos o más, es completo.

**Cuándo saltearla en el completo:** el usuario ya dijo exactamente qué quiere
y cómo. Decilo: "salteo la entrevista porque el pedido ya está cerrado".

## Fase 1 — Plan

**Completo:** el planificador **no ve esta conversación**. Briefing completo:
pedido textual, decisiones cerradas con su porqué, ruta absoluta de cada
worktree, rutas concretas por dónde empezar, reglas de `AGENTS.md` y
`CLAUDE.md`, y lo que ya sabés del código. Lanzá `planificador` sin `model` ni
`effort`. Guardá el plan en `docs/superpowers/plans/AAAA-MM-DD-<tema>.md` **del
backend, aunque la tarea sea sólo de front** (el planificador no escribe).
**Los repos son públicos**: briefings, planes y PRs sin IPs, hosts,
credenciales, datos de terceros ni listados de tablas.
**Revisalo antes de mostrarlo**: si inventó un archivo o leyó mal una
convención, decilo junto al plan; si el problema vino del briefing, corregilo
y pedí el plan de nuevo.

**Corto:** sin planificador. Escribís vos el plan en **5 a 10 líneas** en el
mismo lugar que los planes del carril completo: qué se pide, archivos
que tocás, test que va a fallar primero, cómo se verifica. Un solo lugar para
los planes, siempre.

## Fase 2 — Aprobación ⏸

Mostrá en el chat: pasos, **riesgos y preguntas abiertas completos**, y la
ruta del archivo. **Parás.** Sin OK explícito no ejecutás, aunque parezca
obvio. Completo: mandá aviso (ver _Avisos_). Corto: sin aviso, es un OK de 30
segundos.

Con el OK, **actualizá `docs/estado.md`**: la tarea en "En curso", con su fase
y la ruta del plan, y el "Próximo paso". `estado.md` es sólo lo vivo (nada
entregado), va directo a `main` como la bitácora (la excepción de
`AGENTS.md`, "Bitácora y estado"), se commitea con `/commit` y nunca lleva IPs,
hosts, URLs, credenciales, datos de terceros ni valores. **Se edita en el
checkout principal del backend, en `main`; nunca en el worktree de la tarea**:
ahí viajaría en el PR y chocaría con lo que `/bitacora` cambia en `main`.

## Fase 3 — Ejecución

**Antes de empezar, decí en qué modelo corre esta sesión y quién ejecuta.**

### Carril completo: orquestás al `ejecutor`, un PAR por vez

Un **par** = el test rojo y la implementación que lo pone verde, sobre los
mismos archivos. Van en **un solo lanzamiento** del ejecutor: paga la lectura
del contexto una vez y devuelve las dos evidencias. Los pasos que no tienen
test (docs, comentarios) van solos.

Para cada par o paso:

1. Lanzá `ejecutor` con briefing completo: **ruta absoluta del worktree**,
   ruta del plan, número del par/paso, decisiones cerradas que aplican, reglas
   de `AGENTS.md` y `CLAUDE.md`, qué está hecho. Sin `model` ni `effort`. **El plan escrito
   es la única fuente de verdad**: si falta una decisión, primero al archivo,
   después el agente.
2. Cuando vuelva, leé el reporte. Para un par tiene que traer **las dos
   salidas**: el test fallando y el test pasando. Si falta el rojo, el par no
   está hecho: lo reanudás con `SendMessage` pidiéndolo.
3. **Verificás con el reporte y `git diff --stat`**: que tocó lo que dice y
   nada más, y que los números cierran. **No re-corras el spec por rutina**:
   solo si algo no cuadra (archivos de más, conteos que no coinciden, salida
   sospechosa). Ahí sí lo corrés vos y, si difiere, lo reanudás con lo que
   viste.
4. Según el encabezado: **HECHO** → siguiente. **FRENADO** → la pregunta al
   usuario tal cual, con aviso; al responder, **reanudá al mismo agente con
   `SendMessage`**, no lo relances. **PLAN ROTO** → frená, volvé a la fase 1 o
   preguntá. Incluye "un paso anterior figura hecho y no lo está".
5. Respetá el corte en PRs que marcó el plan: si toca los dos repos, PRs
   hermanos en el backend y en el frontend.

**Al avanzar** (etapa cerrada, revisión terminada, pausa), la sesión principal
actualiza en `docs/estado.md` la fase y el próximo paso, en el checkout
principal del backend (nunca en el worktree). El ejecutor no lo toca.

**Lo que el ejecutor no hace y queda para vos**, con OK explícito del usuario:
`git commit`, ramas, PRs, merge, deploy y todo DDL contra `preliquidacion`
(producción). Un paso de esos vuelve como FRENADO con sentencia, backup y
rollback. Toda DDL va primero a `testing`, que es compartida con otros
sistemas: sólo se tocan nuestras tablas, nunca un drop general. Las migraciones
van en el mismo PR que el código que las necesita.

El archivo del plan lo editás **solo vos**; si cambió durante la ejecución,
actualizalo para que refleje lo que se hizo.

### Carril corto: ejecutás vos, en sesión

Mismas reglas, sin agente: par por par, **test rojo primero y pegá la salida**,
después verde, spec del área y build. Frená si el plan estaba equivocado o algo
te bloquea. No intentes lo mismo cinco veces.

## Fase 4 — Revisión ⏸

En los dos carriles, **en este orden y una sola pasada**:

1. **Suite completa y build, UNA vez**, cuando terminaron todos los pasos.
   Pegá los números reales. **Distinguí regresión de flaky**: un test que
   falla se corre aislado; si pasa solo y es de un área ajena, es flaky y se
   anota, no se persigue.
2. **`revision-codigo`** (no el `code-review` incluido en Claude Code) sobre el diff contra el punto de partida. La skill lanza
   los revisores (completo: dos ejes en paralelo; corto: un solo agente con
   los dos ejes) y después el **`verificador-review`**, que comprueba cada
   hallazgo contra el código, tira los falsos y etiqueta el resto
   `urgent` / `high` / `minor`.
3. Regla mecánica: **`urgent` y `high` se arreglan; `minor` se listan en el
   PR y no se tocan.** Cómo se arreglan, **sin intervención del usuario**:
   - Cada `urgent`/`high` pasa a ser un **paso nuevo del plan** ("Paso R1,
     R2…") que agregás vos al archivo, con el hallazgo, el escenario de
     falla y el arreglo mínimo que trajo el verificador. Queda registrado
     por qué se tocó.
   - Arreglo de **hasta 2 archivos de código**: va como un **par** (test
     que reproduce el escenario de falla en rojo → arreglo → verde). Carril
     completo: lo hace el `ejecutor`; carril corto: vos en sesión. Sin
     planificador: el verificador ya dijo qué y dónde.
   - Arreglo **más grande**, o el verificador dice que el problema es de
     diseño: lanzás al `planificador` con el hallazgo como briefing y el
     plan entra como etapa nueva. **Acá sí frenás** para el OK del usuario,
     porque cambió el alcance.
   - Un `urgent` cuyo arreglo **contradice una decisión aprobada** (regla de
     negocio, alcance): frenás y consultás. Es la única otra intervención
     del usuario en esta fase.
4. Después de arreglar: **spec tocado + build**. Suite completa otra vez solo
   si el arreglo tocó más de un archivo de código.
5. **Rondas**: corto, **una**. Completo, **una**; **dos** si el diff toca
   las zonas sensibles (la segunda ronda revisa solo los arreglos). Solo docs
   o comentarios: **ninguna**. Zonas sensibles de este sistema:
   - **Motor de reglas y cálculo de importes**:
     `app/modulos/preliquidacion/services/motor_reglas.py` y
     `app/modulos/preliquidacion/services/preliquidacion_service.py`.
   - **Maestro de conceptos y precios**:
     `app/modulos/preliquidacion/api/precios.py`.
   - **Exportación a sueldos**:
     `app/modulos/preliquidacion/services/export_service.py` (y su ruta,
     `app/modulos/preliquidacion/api/export.py`).
   - **Autenticación, roles y permisos de módulos**: `app/core/auth.py`,
     `app/core/permisos.py`, los `permisos.py` de cada módulo, y en el front
     `src/core/authStore.js` y `src/core/permisos.js`.
   - **Migraciones y DDL**: `migrations/` y los `models.py` (`app/core/` y
     cada módulo).

   Los controles de lectura y las pantallas, con **una** ronda.
6. **Evidencia antes de afirmar.** No digas "pasa", "arreglado" ni "listo"
   sin haber corrido en esta misma fase el comando que lo prueba y leído su
   salida completa: conteo de tests, exit code, build. Si no lo corriste, decí
   que no está verificado.

Mostrá el resultado en una línea: "revisión: N urgent, N high arreglados, N
minor sin tocar". Mandá aviso si algo necesita su decisión (completo).

## Fase 5 — Entrega ⏸

1. **Mostrar el cambio al usuario y esperar su OK** antes del PR. Si lo quiere
   probar, levantá la app en local desde el worktree, contra `testing` (ver
   _Configuración en el worktree_).
2. Rama → commits con `/commit` → PR **bien comentado** (qué, por qué y qué se
   descartó, verificación, qué pasa después, rollback; el cuerpo del PR es la
   única fuente del porqué que archiva la bitácora), siempre con
   `--body-file`, nunca inline. Si la tarea toca los dos repos, **PRs hermanos**
   en el orden que marque el plan. Merge con OK: `main` exige una aprobación y
   no se puede auto-aprobar, así que va `gh pr merge N --merge --admin`.
3. Deploy **solo si lo pidió explícitamente**: mergear a `main` no es
   deployar, y el sistema está en producción. Con el par del otro repo si
   hubo cambio de API. El detalle del deploy va en `docs/DEPLOY.md` (local,
   fuera de git) y la bitácora lleva una **entrada de deploy aparte**, sin
   datos del servidor.
4. **Anotar el cierre**: después de cada merge, preguntá en una línea si se
   anota con `/bitacora`; si dice que no, seguí sin insistir. El agente
   `bitacora` escribe la entrada **al final** de `docs/BITACORA.md` (la más
   nueva abajo) y **saca la tarea de `docs/estado.md`** (si dejó algo
   pendiente, por ejemplo el smoke del usuario, queda sólo eso, en una línea).
   Commiteás **los dos juntos a `main`**, en el checkout principal del
   backend, con `/commit`. Si hubo deploy, su
   entrada va aparte. Al avisar que quedó anotado, nombrá los archivos.

---

## Avisos

Usá `PushNotification` cuando el trabajo **queda frenado esperando al usuario**
y hay chance de que se haya ido. Si está mirando la terminal, la herramienta lo
omite sola.

| Momento                        | Ejemplo                                                              |
| ------------------------------ | -------------------------------------------------------------------- |
| Plan listo (completo)          | `Plan listo: 4 etapas, 1 riesgo alto (migración). Espera tu OK.`     |
| Pregunta que bloquea           | `Frenado en el par 3: hay que decidir si la baja es lógica o real.`  |
| Tests en rojo que no resolvés  | `Build en rojo: 2 tests de auth fallan y no es flaky.`               |
| La revisión encontró un urgent | `Revisión: 1 urgent en permisos de módulos. Espera tu decisión.`     |
| Cambio listo para el PR        | `Listo para revisar: 6 archivos, 85 tests. Espera tu OK para el PR.` |

**No avises** de progreso rutinario, ni en el carril corto salvo que algo se
trabe. Una línea, menos de 200 caracteres, sin markdown, arrancando por lo
accionable.
