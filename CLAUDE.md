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

## Los cuatro documentos y qué es cada uno

| Archivo | Qué es | Quién lo toca |
|---|---|---|
| `CONTEXT.md` | Glosario del dominio: qué **es** cada término, no cómo se implementa | skill `domain-modeling` |
| `docs/adr/` | Decisiones de arquitectura con sus alternativas descartadas | el usuario, nunca un agente solo |
| `docs/BITACORA.md` | Diario append-only: qué se mergeó y **por qué** | agente `bitacora` |
| `docs/modulos/GUIA-MODULOS.md` | Las reglas para construir un módulo | quien cambie las reglas |

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
- Anotar lo que se va haciendo en la memoria del proyecto, en cada hito.

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
