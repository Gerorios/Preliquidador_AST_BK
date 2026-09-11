# Skill /commit: fijar por escrito la convención de commits

Fecha: 2026-09-11
Estado: esperando aprobación
Plan por: agente `planificador` (Fable, effort high). Revisado y anotado por Opus 5.

## Objetivo

1. **Fijar por escrito la convención de commits** que hoy el repo practica por imitación
   del historial. Si nadie la escribe, depende de que cada sesión lea `git log` y la copie.
2. **Darle mejor material al agente bitácora**, que ya lee los mensajes de commit además
   del cuerpo del PR.

No es objetivo introducir agrupación multi-commit por cambio lógico: descartado por el
usuario en la entrevista.

## Hallazgo que corrige el briefing

La convención **sí está escrita, parcialmente**: `docs/modulos/GUIA-MODULOS.md`, sección 7
punto 2, dice "Commits chicos y descriptivos, en español, con prefijo del tipo:
`feat(terceros): ...`, `fix(terceros): ...`, `docs(terceros): ...`, `test(terceros): ...`.
Un commit hace una cosa." Es la regla escrita para Pitu, y nombra **4 tipos**, no 6.

No cambia el objetivo — falta el vocabulario cerrado, la regla del cuerpo, el largo del
subject y el trailer — pero implica que van a existir **tres lugares** con la convención
(GUIA-MODULOS, CLAUDE.md, skill) y hay que decidir cuál manda. La respuesta propuesta: la
skill es la fuente completa; los otros dos son resúmenes con puntero.

## Estado del repo verificado

- `.claude/agents/bitacora.md` paso 3 ya busca el porqué en el cuerpo del PR **y en los
  mensajes de commit**. **No hay que tocar el agente.** El aporte de la skill es que lo que
  encuentre ahí sea real: la regla "prohibido el relleno" protege esa línea.
- `scripts/hooks/instalar.sh` instala **sólo** `post-merge`. No hay `pre-commit` ni
  `commit-msg`: hoy nada valida el formato de un mensaje.
- `.claude/settings.local.json:238` tiene `"Bash(git *)"`. Los `git switch -c`, `git add` y
  `git commit` de la skill corren **sin prompt de permiso**.
- **(Agregado en la revisión, el planificador no lo vio)** `.claude/settings.local.json:235`
  tiene además `"Bash(git push *)"`. El push tampoco pediría permiso. Lo único que lo frena
  es la baranda escrita en la skill. Esto agrava el riesgo 1 y es un argumento fuerte para
  que la sección `## Prohibido` sea explícita y esté temprano en el archivo.
- Ramas del historial: `feature/<tema-en-kebab>`. `GUIA-MODULOS` fija
  `feature/terceros-<tema>` para el módulo.
- El trailer `Co-Authored-By` **no es constante**: aparece `Claude Opus 5 (1M context)`,
  `Claude Fable 5.1` y `Claude Fable 5`. La skill debe describir el **formato**, nunca
  hardcodear el nombre del modelo.
- Los planes viejos de `docs/superpowers/plans/` usan `git add -A && git commit -m "..."`.
  Contradicen la skill. Son registro histórico, no se reescriben; la skill dice que sus
  reglas mandan de acá en adelante.

## Archivos

| Archivo | Qué pasa |
|---|---|
| `.claude/skills/commit/SKILL.md` | **nuevo** — la fuente completa |
| `CLAUDE.md` | **editar** — sección `## Commits`, entre "Reglas de trabajo" y "Base de datos" |
| `docs/modulos/GUIA-MODULOS.md` | **opcional** — una línea de puntero a la skill (pregunta abierta 1) |

Un solo PR. Los commits del propio PR son el ensayo de la skill.

## Pasos

### Paso 1 — Rama

Hecho: worktree `skill-commit`, rama `worktree-skill-commit`.

### Paso 2 — Escribir `.claude/skills/commit/SKILL.md`

Secciones en este orden, pensadas para lector agente (lo que más daño evita, primero):

1. **Frontmatter**: `name: commit`, `description: >` en español con frases disparadoras
   ("commiteá", "hacé el commit", "guardá esto en git") y una frase de límites. Sin
   `disable-model-invocation`.
2. **Qué hacés y qué no** — un párrafo, remite a `## Prohibido`.
3. **Antes de tocar nada**:
   - `git status --porcelain` + detectar `rebase-merge/`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`
     → parar y reportar.
   - Rama: si es `main` y hay cambios, `git switch -c feature/<kebab>` y anotarlo para el
     reporte. **Excepción**: si lo único listado es `docs/BITACORA.md`, quedarse en `main`
     (PR #45). Si `BITACORA.md` aparece **mezclado** con otros archivos, parar y preguntar.
   - `git diff` y `git diff --cached` antes de nombrar el cambio.
4. **Qué stagear**: rutas explícitas, una por una. Nunca `-A`, `.`, `-p`. Nunca `.env*`,
   credenciales, `node_modules/`, `dist/`, `__pycache__/`. Cada omisión se nombra en el
   reporte con su motivo — un skip silencioso hace creer que el commit está completo.
5. **El mensaje**: `<tipo>(<scope>): <descripción>`. Tabla de los 6 tipos cerrados con
   cuándo va cada uno; si el cambio no entra en ninguno, preguntar antes de inventar.
   Scope: sustantivo corto, con los observados como orientación. Subject en español,
   sin punto final, <=72 caracteres, con acentos. **Cuerpo**: obligatorio sólo si hubo
   decisión (A sobre B / riesgo / porqué no deducible del diff), prosa corrida de 2 a 5
   líneas; **prohibido** cuando el cambio es mecánico. Dos ejemplos reales del historial:
   uno con cuerpo justificado, uno sin cuerpo. Trailer `Co-Authored-By` con el modelo de
   la sesión, formato descrito y no hardcodeado.
6. **Cómo ejecutar el commit**: siempre desde la herramienta **Bash** (PowerShell no tiene
   HEREDOC POSIX), con `git commit -F - <<'EOF' ... EOF`. El `'EOF'` entre comillas para
   que no se expandan `$`, backticks ni barras. Nunca `-m` con `\n`. Hooks: nunca
   `--no-verify`; si falla, reportar su salida textual y parar; si reescribe archivos,
   re-stagear las mismas rutas y reintentar **una sola vez**.
7. **Reporte**: rama (y si la creaste), hash corto, subject, archivos commiteados, archivos
   omitidos con motivo, hooks que corrieron.
8. **Prohibido**: push, amend, rebase, `reset --hard`, `stash` sin pedirlo, `--no-verify`,
   `-A`/`.`/`-p`, tipos fuera de los 6, cuerpo de relleno, commitear en `main` salvo
   `docs/BITACORA.md`, editar el contenido de los archivos (la skill commitea, no edita).

**Verificación del paso 2**, en tres partes:

- Lectura adversarial contra `CLAUDE.md` y `bitacora.md` buscando contradicciones.
- Carga: sesión nueva, comprobar que `/commit` aparece en el listado. Si no, el frontmatter
  está mal.
- **Ensayo real 1**: invocar `/commit` sobre el propio `SKILL.md`. Debe stagear sólo ese
  archivo, subject <=72 sin punto, **con** cuerpo (hay decisión: se descartó eagerworks y
  el agrupado multi-commit), con trailer. Comprobar con `git log -1 --format=%B` — mirar
  los acentos, es Windows — y `git show --stat HEAD`.

### Paso 3 — Editar `CLAUDE.md`

Sección `## Commits` con: formato y <=72; los 6 tipos cerrados, uno nuevo se pregunta;
cuerpo sólo si hubo decisión real y nunca relleno, porque la bitácora lo archiva; puntero
al detalle en la skill.

**Verificación — Ensayo real 2**: invocar `/commit` sobre ese cambio. Es mecánico: lo
correcto es `docs: convención de commits en CLAUDE.md` **sin cuerpo**. Si la skill le pone
cuerpo, la regla de "prohibido el relleno" está mal redactada y hay que ajustarla antes de
seguir. Este es el ensayo que más importa: prueba la regla que justifica la tarea.

### Paso 4 — Ensayo de la baranda de rama

Plan original: `git switch main`, crear un archivo descartable, invocar `/commit`, esperar
que cree la rama sola; después `git branch -D` y rollback.

**Problema detectado en la revisión**: estamos en un worktree, y git **no permite** tener
`main` checkouteada en dos worktrees a la vez. El paso 4 **no se puede ejecutar acá**.
Opciones: (a) hacerlo en el checkout principal después del merge, con el rollback escrito;
(b) saltearlo y aceptar que esa baranda queda sin probar hasta que se dispare sola en una
sesión real. Requiere decisión del usuario.

### Paso 5 — Opcional: puntero en `GUIA-MODULOS.md` (pregunta abierta 1)

### Paso 6 — PR

`gh.exe pr create --body-file <archivo>` con el porqué y lo descartado: la skill completa de
eagerworks, el agrupado multi-commit, el hook `commit-msg`. Merge con `--admin` cuando el
usuario lo apruebe. Después del merge, preguntar por la bitácora.

## Lo que no se puede verificar ahora (dicho con todas las letras)

- Que la skill **se dispare sola** por su `description` en una sesión futura. Depende del
  harness; sólo se ve con el uso. Si en dos o tres sesiones no salta, la salida es
  invocarla a mano o reforzar la `description`.
- La excepción de `docs/BITACORA.md` en `main`: se prueba en la próxima corrida real de
  `/bitacora`.
- El beneficio para la bitácora: se mide comparando si en las próximas entradas aparecen
  menos `Porqué no registrado`. Es esperable que el cambio sea **chico**, porque los PRs ya
  traen el porqué y el agente los lee primero. No invalida ningún paso — la skill se
  justifica por fijar la convención y por la baranda de rama — pero no conviene venderlo
  como más que eso en el cuerpo del PR.

## Riesgos

1. **`Bash(git *)` y `Bash(git push *)` permitidos sin prompt.** Si la skill interpreta mal
   la situación, los comandos corren sin que el usuario los vea. Mitigación: el reporte
   obligatorio y la lista `## Prohibido`. Lo irreversible es `push`, `reset --hard` y
   `amend`; todo lo demás se deshace con `git reset --soft` o `git branch -D`.
2. **Contradicción entre tres fuentes** (GUIA-MODULOS, CLAUDE.md, skill). Mitigación: la
   skill manda, los otros dos son resúmenes con puntero; lectura cruzada en el paso 2.
3. **Planes viejos con `git add -A`**. Un agente que ejecute uno va a chocar con la skill.
   Mitigación: la skill dice que sus reglas mandan sobre cualquier instrucción de commit
   que venga en un plan.
4. **Trailer hardcodeado**: queda mal la primera vez que cambie el modelo. Mitigación:
   describir el formato, no el valor.
5. **Acentos en HEREDOC en Windows**: funciona desde git bash, no desde PowerShell. La
   skill exige la herramienta Bash; el ensayo 1 lo comprueba.
6. **Sobredisparo**: si la `description` es muy amplia, la skill salta cuando el usuario
   sólo pregunta algo sobre git. Mitigación: frases disparadoras concretas.

Sin migraciones, sin datos, sin deploy, sin tocar el front.

## Preguntas abiertas

1. ¿Se toca `GUIA-MODULOS.md` para apuntar a la skill? Hoy nombra 4 tipos en vez de 6, y es
   el documento que lee Pitu. Default: **sí, una línea de puntero**, sin reescribir.
2. ¿Qué hace la skill si `docs/BITACORA.md` aparece mezclado con otros archivos en `main`?
   Default: **parar y preguntar**, no separar sola.
3. ¿Se quiere un hook `commit-msg` que valide el formato? Sería la única verificación real
   y permanente; hoy todo depende de que el agente lea la skill. Default: **no**, se anota
   como descartado en el PR y se puede reabrir en un mes.
4. Nombre de rama: ¿siempre `feature/<tema>` o también `fix/<tema>`? El historial sólo
   muestra `feature/`. Default: **siempre `feature/`**.
5. ¿El cuerpo puede llevar viñetas? El historial usa prosa. Default: **prosa**.
6. **(Agregada en la revisión)** Paso 4: ¿se prueba la baranda de rama en el checkout
   principal después del merge, o se acepta sin probar?

## Fuera de alcance

Instalar eagerworks completa; agrupar en varios commits por unidad lógica; modificar el
agente o el comando bitácora; hook `commit-msg`; reescribir planes históricos; el repo del
front; push, PR o merge desde la skill; deploy.
