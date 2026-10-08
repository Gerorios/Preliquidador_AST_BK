# Sistema de gestión La Asturiana — backend

Monolito modular en FastAPI. Núcleo compartido (`app/core/`) + módulos autocontenidos
(`app/modulos/<m>/`). Módulos: **Preliquidación** (activo, en producción) y
**Liquidación Terceros** (molde, inactivo, lo construye Pitu).

**El front es otro repo**: `frontend_preliquidacion` (React + Vite). Casi todo cambio de
módulo necesita PRs hermanos en los dos.

<!-- comun:inicio. Este bloque es idéntico en el AGENTS.md del backend y en el del
frontend. Si lo cambiás, cambialo en los dos: scripts/verificar_agents_comun.sh compara. -->
## Reglas comunes a los dos repos

Los dos repos comparten un solo diario, un solo glosario y un solo juego de ADR, que viven
en el repo del backend (`backend_preliquidacion`). Las rutas `docs/...`, `CONTEXT.md` y
`CONTEXT-MAP.md` de este bloque son de ese repo.

### Reglas de trabajo

- **Rama antes de editar.** Nunca commitear directo a `main`; el hook `pre-commit` lo
  frena. Única excepción: un commit que sólo toque `docs/BITACORA.md` y/o
  `docs/estado.md` (ver "Bitácora y estado").
- **Nunca deployar al VPS sin OK explícito del usuario.** El sistema está en producción y
  lo usan personas reales. Mergear a `main` no es deployar.
- **Smoke tests reales**, no "debería andar". Si algo no se probó, decirlo.
- **Implementar y después verificar de forma adversarial**: buscar activamente el error
  propio.
- **Las migraciones no se difieren**: van en el mismo PR que el código que las necesita.
- **Los repos son públicos.** IPs, hosts, credenciales, datos de terceros y listados de
  tablas nunca entran a git. Quien necesite saber qué tablas hay, consulta la base.

### Antes de proponer una decisión de diseño

Buscar antecedentes en `docs/BITACORA.md` y `docs/adr/` (grep por los términos del tema).
Ahí está el *por qué* de lo decidido, incluido lo que se evaluó y se descartó. Ejemplo
real: la invitación por email está descartada (mucha gente no tiene mail propio) y el
sistema no manda correo; eso no se deduce de ningún diff. Si no está, no asumir que no se
decidió: preguntar.

### Cambios de interfaz

- **Todo cambio visual y toda feature nueva con interfaz se hacen con la skill
  `impeccable`**, en los dos módulos del front. Vive en el repo del front
  (`.claude/skills/impeccable/`). Vale también para un ajuste chico: antes de editar
  interfaz se lee su `reference/craft-floor.md`. El momento de cada comando dentro de una
  tarea lo fija la skill `flujo-preliquidacion`.
- **La estética del sistema vive en los tokens de `src/index.css`** y, cuando exista, en
  `DESIGN.md` del front (tokens, tipografía, componentes). El contexto de producto para
  diseñar va en `PRODUCT.md` del front. Esos dos archivos los escribe `impeccable`.
  Cambiar la estética es una decisión del usuario.
- **`impeccable` no pasa por encima de las reglas del proyecto**: CSS Modules con los
  tokens de `src/index.css`, sin Tailwind ni librería de componentes, dependencias nuevas
  (fuentes incluidas) aprobadas antes, textos en español sin emojis y el feedback visible
  de `docs/modulos/GUIA-MODULOS.md`. Si choca con ellas, valen ellas y se pregunta.

### Dónde se anota cada cosa

Cada cosa que pasa tiene **un** lugar donde se anota, en el momento, sin esperar a que el
usuario lo pida.

| Qué pasó | Dónde se anota | Cuándo |
|---|---|---|
| Cambio en el VPS o la infraestructura: config del servidor, paquetes, accesos, certificados, cómo se deploya | `docs/DEPLOY.md` (local, fuera de git) | en el momento del cambio |
| El *por qué* de un cambio de código: qué se eligió y qué se descartó | cuerpo del PR | al abrir el PR |
| Lo que está en curso con su fase, el próximo paso, lo que espera al usuario y lo pospuesto | `docs/estado.md`, sólo lo vivo | al avanzar; al entregar se borra de ahí |
| Un merge a `main` | `docs/BITACORA.md`, y la tarea sale de `docs/estado.md` | después de preguntar (ver "Bitácora y estado") |
| Un término del dominio: qué **es**, no cómo se implementa | el glosario que indica `CONTEXT-MAP.md`: `CONTEXT.md` si es del Sistema, el `CONTEXT-<módulo>.md` si es de un módulo | al cerrar el término |
| Una decisión de arquitectura, con sus alternativas descartadas | `docs/adr/` | sólo con el usuario |
| Una regla para construir un módulo | `docs/modulos/GUIA-MODULOS.md` | cuando cambia la regla |
| Cómo preparar una máquina de desarrollo | `docs/modulos/PUESTA-A-PUNTO.md` | cuando cambia |
| El plan de una tarea | `docs/superpowers/plans/AAAA-MM-DD-<tema>.md` | en la fase de plan |
| La estética del sistema: tokens, tipografía, componentes | `DESIGN.md` del front | al cambiar la estética, con `impeccable` |
| Para quién y para qué es el sistema, como contexto de diseño | `PRODUCT.md` del front | con `/impeccable init`; sin datos de terceros |

- **Lo que un agente guarde en su propia memoria no cuenta como anotación para una
  persona.** Si algo le importa al usuario o a Pitu, va a su archivo de la tabla.
- **Al avisar "quedó anotado", se nombra el archivo.**
- **Si una herramienta o skill manda anotar en otro lugar, vale esta tabla.**

Un ADR no es un resumen de lo que pasó: es un compromiso. No se escribe sin el usuario.

### Commits y PRs

- **Formato**: `<tipo>(<scope>): <descripción>`, en español, sin punto final, hasta 72
  caracteres. Vocabulario **cerrado**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
  Si hace falta uno nuevo, se pregunta antes.
- **Cuerpo del commit sólo si hubo una decisión real** (se eligió A sobre B, hay un riesgo,
  hay un porqué que el diff no muestra). Nunca de relleno: la bitácora archiva como
  decisión lo que encuentre ahí.
- **El cuerpo del PR es la única fuente del *por qué*** que la bitácora puede archivar. Dos
  o tres líneas de "se decidió así porque, y se descartó aquello" alcanzan.
- `main` exige una aprobación y no se puede auto-aprobar: el merge va con `--admin`. Los
  cuerpos de PR, siempre desde archivo (`--body-file`), nunca inline.

### Estado del trabajo

Dos archivos del repo del backend, cada uno con un solo trabajo:

- **`docs/estado.md` es sólo lo vivo**: lo que está en curso (con su fase y su plan), el
  próximo paso, los pendientes del usuario (lo de Pitu también se le anota al usuario) y
  lo que quedó para más adelante, con su porqué. Nada entregado. En Claude Code lo importa
  `CLAUDE.md`, así que cada sesión arranca con él cargado.
- **`docs/BITACORA.md` es todo lo hecho**: una sección `## AAAA-MM-DD — Tema` por entrega,
  la más nueva **abajo**. Un hook de arranque (`.claude/hooks/ultimas-entregas.mjs`) le
  pasa a cada sesión las 2 últimas entradas.

Cómo se mantienen:

- **Al avanzar** (plan aprobado, paso cerrado, revisión terminada, pausa): la sesión
  principal actualiza en `estado.md` la fase y el próximo paso. Se edita en el checkout
  principal del backend, en `main`, como la bitácora; **nunca en el worktree de la tarea**
  (viajaría en el PR y chocaría con lo que el agente `bitacora` cambia en `main`).
- **Al entregar** (merge a `main`): el agente `bitacora` escribe la entrada al final de
  `BITACORA.md` y **saca esa tarea de `estado.md`**. Si dejó algo pendiente (por ejemplo,
  el smoke del usuario), queda en `estado.md` sólo eso, en una línea. Quien despachó al
  agente commitea los dos archivos juntos.
- **Lo que se descarta o se pospone** pasa a "A futuro" de `estado.md`, con una línea de
  por qué.
- **El repo es público y `estado.md` se edita seguido, directo a `main`**: nunca lleva
  IPs, hosts, URLs, credenciales, datos de terceros ni valores.

### Bitácora y estado

- Hay **una sola** bitácora, `docs/BITACORA.md` en el repo del backend: diario append-only
  de qué se mergeó y por qué. El estado vive al lado, en `docs/estado.md`.
- **Los dos van directo a `main`**, y son la única excepción a "rama antes de editar".
  Porqué: si la anotación fuera por PR, cada merge generaría otro merge para anotar el
  primero, en cadena infinita. Y ninguno de los dos ejecuta nada, así que un error ahí es
  una línea fea en un diario, no un bug. La excepción nació el 2026-09-11 sólo para la
  bitácora; el 2026-10-05 se reabrió esa decisión para sumar `estado.md`, que cambia en el
  mismo commit que cierra cada entrega: por PR caería en la misma cadena. No extender la
  excepción a ningún otro archivo.
- **Después de cada merge a `main`, preguntar al usuario** en una línea si se anota. Si dice
  que no, seguir sin insistir: la próxima corrida lo cubre igual. Nunca anotar sin
  preguntar, porque escribe en `main` directo.

### Idioma

Español, con acentos correctos. Términos técnicos e identificadores en su forma original.
Textos públicos sin emojis.
<!-- comun:fin -->

## Arquitectura (ADR-0013)

- Un módulo **nunca importa** a otro módulo. Lo compartido sube al núcleo.
- El núcleo **no importa** módulos (hay un test que lo verifica).
- Lo que usa un solo módulo vive en ese módulo; el núcleo crece sólo cuando dos lo necesitan.
- Dependencias nuevas **se aprueban antes** de agregarse (regla de stack de GUIA-MODULOS).

## Bases de datos

Tres conexiones: la base de campo y la de sueldos son de terceros y de **sólo lectura**; la
propia (`DB_PROPIA_*`) es la nuestra, y tiene dos bases (ADR-0014):

- **`testing`**: el entorno de prueba del área. Es **compartida con otros sistemas**: tiene
  un espejo de nuestras tablas y tablas ajenas. Nunca un drop general; sólo se tocan las
  tablas nuestras. Para desarrollar, `DB_PROPIA_NAME=testing`.
- **`preliquidacion`**: **producción**. La usa el VPS y es el dato real de la empresa.
  Ninguna máquina de desarrollo apunta ahí: la app se niega a arrancar contra ella sin
  `PERMITIR_BASE_PRODUCCION=1`, que sólo tiene el `.env` del VPS.
- **Toda DDL se aplica primero en `testing`** y después en producción.

Por ADR-0013 las tablas en producción **no se renombran**. Cada módulo usa su prefijo
(`terceros_*`), y el núcleo es de sólo lectura para los módulos.

## Comandos

```bash
uvicorn app.main:app --reload     # desarrollo (con el .env apuntando a testing)
pytest                            # toda la suite
python verificar_conexion.py      # chequear las tres conexiones (necesita PYTHONUTF8=1)
python scripts/asignar_modulo.py --email <mail> --modulo <preliquidacion|terceros> --rol <operador|gerente>
sh scripts/hooks/instalar.sh      # una vez por clon: instala post-merge y pre-commit
```
