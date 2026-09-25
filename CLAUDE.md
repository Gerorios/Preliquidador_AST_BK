# Sistema de gestión La Asturiana — backend

Monolito modular en FastAPI. Núcleo compartido (`app/core/`) + módulos autocontenidos
(`app/modulos/<m>/`). Módulos: **Preliquidación** (activo, en producción) y
**Liquidación Terceros** (molde, inactivo, lo construye Pitu).

**El front es otro repo**: `frontend_preliquidacion` (React + Vite, remote `AST_FT`).
Casi todo cambio de módulo necesita PRs hermanos en los dos.

## Antes de proponer una decisión de diseño

**Buscá primero en `docs/BITACORA.md`.** Ahí está el *por qué* de lo ya decidido, incluido
lo que se evaluó y se descartó. No se carga sola: hay que abrirla.

Sirve para no volver a proponer algo ya rechazado. Ejemplo real: la invitación por email
está descartada (mucha gente no tiene mail propio) y el sistema no manda correo — eso no
se deduce de ningún diff.

Si la decisión que buscás no está ahí, no asumas que no se tomó: preguntá.

## Dónde se anota cada cosa

Cada cosa que pasa tiene **un** lugar donde se anota. Se anota ahí en el momento, sin
esperar a que el usuario lo pida.

| Qué pasó | Dónde se anota | Cuándo |
|---|---|---|
| Cambio en el VPS o la infraestructura: config del servidor, paquetes, accesos, certificados, cómo se deploya | `docs/DEPLOY.md` (local, fuera de git) | en el momento del cambio |
| El *por qué* de un cambio de código: qué se eligió y qué se descartó | cuerpo del PR | al abrir el PR |
| Un merge a `main` | `docs/BITACORA.md`, con el agente `bitacora` | después de preguntar (ver abajo) |
| Un término del dominio: qué **es**, no cómo se implementa | `CONTEXT.md`, o el `CONTEXT-<módulo>.md` del módulo | con la skill `domain-modeling` |
| Una decisión de arquitectura, con sus alternativas descartadas | `docs/adr/` | sólo con el usuario |
| Una regla para construir un módulo | `docs/modulos/GUIA-MODULOS.md` | cuando cambia la regla |
| Cómo preparar una máquina de desarrollo | `docs/modulos/PUESTA-A-PUNTO.md` | cuando cambia |
| El plan de una tarea | `docs/superpowers/plans/AAAA-MM-DD-<tema>.md` | en la fase de plan |
| Estado entre sesiones de Claude: qué quedó a medias, trampas encontradas | memoria de Claude | en cada hito |

- **La memoria no cuenta como anotación para una persona.** Vive fuera del repo, en la
  máquina del usuario, y no la ve nadie más. Si algo le importa al usuario o a Pitu, va a su
  archivo de la tabla, y la memoria sólo apunta a ese archivo.
- **Al avisar "quedó anotado", se nombra el archivo.** Decir "lo anoté en memoria" solo no
  alcanza.
- **Los repos son públicos.** IPs, hosts, credenciales y datos de terceros nunca entran a
  git. Van a `docs/DEPLOY.md` o a `docs/modulos/*/fuentes/`, los dos fuera de git.
- **Si una skill manda anotar en otro lugar, vale esta tabla.**

Un ADR no es un resumen de lo que pasó: es un compromiso. No se escribe sin el usuario.

## Reglas de trabajo (el usuario las pidió explícitamente)

- **Rama antes de editar.** Nunca commitear directo a `main`. Única excepción:
  `docs/BITACORA.md`, que va directo (ver abajo).
- **NUNCA deployar al VPS sin OK explícito del usuario.** El sistema está en producción en
  https://preliquidacion.laasturianasrl.com.ar y lo usan personas reales. Mergear a `main`
  no es deployar.
- **Smoke tests reales**, no "debería andar". Si algo no se probó, decilo.
- **Implementar y después verificar de forma adversarial**: buscá activamente el error propio.
- Las **migraciones no se difieren**: van en el mismo PR que el código que las necesita.
- Anotar lo que se va haciendo en cada hito, en el lugar que corresponda según
  "Dónde se anota cada cosa".

## Commits

- **Formato**: `<tipo>(<scope>): <descripción>`, en español, sin punto final, hasta 72
  caracteres. Vocabulario **cerrado**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
  Si hace falta uno nuevo, se pregunta antes.
- **Cuerpo sólo si hubo una decisión real** (se eligió A sobre B, hay un riesgo, hay un
  porqué que el diff no muestra). Nunca de relleno: el agente `bitacora` lee estos mensajes
  y archiva como decisión lo que encuentre ahí.
- El detalle y las barandas, en `.claude/skills/commit/SKILL.md` (`/commit`).

## Base de datos

`db_propia` es **compartida por 4+ sistemas**; sólo las tablas del preliquidador son
nuestras. Nunca un drop general. La base `preliquidacion` **es el dato real de la empresa**,
no un entorno de pruebas: desarrollar contra `testing` (`DB_DEV_*` en el `.env`).

Por ADR-0013 las tablas en producción **no se renombran**. Cada módulo usa su prefijo
(`terceros_*`), y el núcleo es de sólo lectura para los módulos.

## Reglas de arquitectura (ADR-0013)

- Un módulo **nunca importa** a otro módulo. Lo compartido sube al núcleo.
- El núcleo **no importa** módulos (hay un test que lo verifica).
- Lo que usa un solo módulo vive en ese módulo; el núcleo crece sólo cuando dos lo necesitan.
- Dependencias nuevas **se aprueban antes** de agregarse (regla de stack de GUIA-MODULOS).

## Comandos

```bash
uvicorn app.main:app --reload     # desarrollo
pytest                            # 277 tests
python verificar_conexion.py      # chequear las tres conexiones (necesita PYTHONUTF8=1)
python scripts/asignar_modulo.py --email <mail> --modulo <preliquidacion|terceros> --rol <operador|gerente>
sh scripts/hooks/instalar.sh      # hooks de git, uno por clon
/bitacora                         # anotar en la bitácora los merges nuevos
```

`gh` **no está en el PATH**: invocarlo como `"/c/Program Files/GitHub CLI/gh.exe"`, y los
cuerpos de PR siempre con `--body-file` (nunca `--body` inline).

`main` exige una aprobación y no se puede auto-aprobar: el merge va con `--admin`.

## Después de cada merge a `main`, preguntar por la bitácora

Apenas se mergea un PR, **preguntarle al usuario si corro `/bitacora`**. Una línea, no un
párrafo: "quedó sin anotar el PR #N, ¿lo anoto?". Si dice que no, seguir sin insistir — no
se pierde nada, la próxima corrida lo cubre igual.

Porqué: el hook `post-merge` sólo avisa cuando la máquina del usuario actualiza `main`, y ese
aviso se pierde fácil entre la salida de otros comandos. La pregunta es el respaldo. Sin
ella, el diario se atrasa hasta que alguien se acuerda, que es exactamente como mueren estos
archivos.

Nunca correr `/bitacora` sin preguntar: escribe en `main` directo.

## La bitácora se commitea directo a `main`

Es la única excepción a "rama antes de editar", y vale **sólo** para `docs/BITACORA.md`.

Porqué: si la anotación fuera por PR, cada merge generaría un segundo merge para anotar el
primero, que a su vez habría que anotar. Cadena infinita. Y el archivo es append-only y no
ejecuta nada, así que un error ahí es una línea fea en un diario, no un bug.

No extender la excepción a ningún otro archivo. La regla existe para proteger el código.

## Al escribir un PR

El cuerpo del PR es la **única fuente** del *por qué* que la bitácora puede archivar. Dos o
tres líneas de "esto se decidió así porque, y se descartó aquello" alcanzan. Lo que no quede
escrito ahí se pierde, y en la próxima sesión alguien lo va a volver a proponer.

## Idioma

Español, con acentos correctos. Términos técnicos e identificadores en su forma original.
Textos públicos sin emojis.
