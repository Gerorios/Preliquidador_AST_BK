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
  frena. Única excepción: un commit que sólo toque `docs/BITACORA.md` (ver "Bitácora").
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

### Dónde se anota cada cosa

Cada cosa que pasa tiene **un** lugar donde se anota, en el momento, sin esperar a que el
usuario lo pida.

| Qué pasó | Dónde se anota | Cuándo |
|---|---|---|
| Cambio en el VPS o la infraestructura: config del servidor, paquetes, accesos, certificados, cómo se deploya | `docs/DEPLOY.md` (local, fuera de git) | en el momento del cambio |
| El *por qué* de un cambio de código: qué se eligió y qué se descartó | cuerpo del PR | al abrir el PR |
| Un merge a `main` | `docs/BITACORA.md` | después de preguntar (ver "Bitácora") |
| Un término del dominio: qué **es**, no cómo se implementa | el glosario que indica `CONTEXT-MAP.md`: `CONTEXT.md` si es del Sistema, el `CONTEXT-<módulo>.md` si es de un módulo | al cerrar el término |
| Una decisión de arquitectura, con sus alternativas descartadas | `docs/adr/` | sólo con el usuario |
| Una regla para construir un módulo | `docs/modulos/GUIA-MODULOS.md` | cuando cambia la regla |
| Cómo preparar una máquina de desarrollo | `docs/modulos/PUESTA-A-PUNTO.md` | cuando cambia |
| El plan de una tarea | `docs/superpowers/plans/AAAA-MM-DD-<tema>.md` | en la fase de plan |

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

### Bitácora

- Hay **una sola**, `docs/BITACORA.md` en el repo del backend: diario append-only de qué se
  mergeó y por qué.
- **Va directo a `main`**, y es la única excepción a "rama antes de editar". Porqué: si la
  anotación fuera por PR, cada merge generaría otro merge para anotar el primero, en cadena
  infinita. Y el archivo no ejecuta nada, así que un error ahí es una línea fea en un
  diario, no un bug. No extender la excepción a ningún otro archivo.
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
propia (`DB_PROPIA_*`) es la nuestra, y tiene dos bases:

- **`testing`**: el entorno de prueba del área. Es **compartida con otros sistemas**: tiene
  un espejo de nuestras tablas y tablas ajenas. Nunca un drop general; sólo se tocan las
  tablas nuestras. Para desarrollar, `DB_PROPIA_NAME=testing`.
- **`preliquidacion`**: **producción**. La usa el VPS y es el dato real de la empresa.
  Ninguna máquina de desarrollo apunta ahí.
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
