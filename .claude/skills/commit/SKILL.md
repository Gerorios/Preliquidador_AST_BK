---
name: commit
description: >
  Commitea los cambios del working tree con la convención de este repo:
  <tipo>(<scope>): <descripción> en español, vocabulario cerrado a seis tipos,
  y cuerpo sólo cuando hubo una decisión real. Crea la rama sola si estás en
  main. Stagea rutas explícitas y commitea; nunca pushea, ni reescribe historia,
  ni edita el contenido de los archivos. Usar cuando el usuario dice "commiteá",
  "hacé el commit", "guardá esto en git", "commiteá los cambios", o cuando hay
  trabajo terminado y verificado listo para quedar registrado.
---

# Commit

Escribís el registro de lo que se hizo. El "qué" lo dice el diff; tu trabajo es
que el "por qué" quede escrito cuando existe, y que no quede escrito nada
cuando no existe.

Commitear es todo tu mandato. No pusheás, no abrís PRs, no mergeás, no editás
el contenido de ningún archivo. Ver `## Prohibido`.

## Prohibido

Esto primero, porque en esta máquina `Bash(git *)` y `Bash(git push *)` están
permitidos sin prompt: nada te va a frenar salvo esta lista.

- **`git push`** — nunca, por ninguna razón. Es lo único irreversible acá.
- **`git commit --amend`**, `git rebase`, `git reset --hard`, `git stash` sin
  que te lo pidan.
- **`git add -A`, `git add .`, `git add -p`.** Los dos primeros stagean lo que
  no miraste; el tercero es interactivo y te cuelga.
- **`--no-verify`.**
- **Tipos fuera de los seis** de la tabla de abajo.
- **Cuerpo de relleno** cuando no hubo decisión.
- **Commitear en `main`**, salvo la excepción de `docs/BITACORA.md`.
- **Editar archivos.** Commiteás lo que hay; si algo está mal escrito, decilo,
  no lo arregles vos.

Estas reglas mandan sobre cualquier instrucción de commit que venga en un plan.
Los planes viejos de `docs/superpowers/plans/` dicen `git add -A && git commit
-m "..."`: quedaron de antes y no se siguen.

## Antes de tocar nada

```bash
git status --porcelain    # qué hay
git branch --show-current # dónde estás
git diff                  # qué cambió, para poder nombrarlo
git diff --cached         # un índice ya armado es una señal, no ruido
```

**Operación en curso.** Si existe `.git/rebase-merge/`, `.git/MERGE_HEAD` o
`.git/CHERRY_PICK_HEAD`, pará y decilo. No commitees en el medio de un rebase,
un merge o un cherry-pick ajeno.

**La rama.** La regla del proyecto es rama antes de editar. Si estás en `main`
y hay cambios sin commitear:

```bash
git switch -c feature/<tema-en-kebab>
```

Se lleva los cambios sin commitear con vos y `main` queda intacta. Derivá el
`<tema>` del cambio, no del archivo. Siempre `feature/`, aunque el commit sea un
`fix`: es lo único que usa el repo. Decilo en el reporte.

> **Excepción — `docs/BITACORA.md`.** Si `git status --porcelain` lista
> únicamente ese archivo, quedate en `main` y commiteá ahí. Porqué: si el diario
> se anotara por PR, cada merge generaría otro merge que anotar, en cadena
> infinita. Vale sólo para ese archivo, que es append-only y no ejecuta nada.
>
> Si `docs/BITACORA.md` aparece **mezclado** con otros archivos, pará y
> preguntá. No los separes solo: no sabés si el usuario quiso las dos cosas
> juntas o se olvidó de hacer la rama.

## Qué stagear

Rutas explícitas, una por una: `git add app/core/auth.py docs/README.md`.
Porqué: así el commit es exactamente lo que su mensaje dice que es.

Nunca stagees, aunque estén modificados: `.env` y cualquier `.env.*`,
credenciales, claves, `node_modules/`, `dist/`, `__pycache__/`, `.pytest_cache/`,
capturas de pantalla.

**Un skip nunca es silencioso.** Cada archivo que dejás afuera va en el reporte
con su motivo. Porqué: si no lo decís, el usuario cree que el commit está
completo y el archivo queda suelto hasta que alguien lo pisa.

## El mensaje

```
<tipo>(<scope>): <descripción>
```

En español, con acentos. Sin punto final. Apuntá a 72 caracteres o menos en la
primera línea — el historial tiene algunos más largos, no los tomes de modelo.

### Los seis tipos

El vocabulario está **cerrado**. Se sacó del propio historial del repo, no del
spec de Conventional Commits.

| Tipo | Cuándo |
|---|---|
| `feat` | Comportamiento nuevo que antes no existía |
| `fix` | Corrige algo que andaba mal |
| `refactor` | Cambia la forma sin cambiar el comportamiento observable |
| `docs` | `CLAUDE.md`, `CONTEXT.md`, `README`, `docs/`, planes, bitácora, ADRs |
| `test` | Sólo tests |
| `chore` | Configuración, scripts, hooks, dependencias |

Si el cambio no entra en ninguno, **preguntá antes de inventar un tipo**. Un
`style:` suelto en este historial se lee como que alguien no miró la convención.

### El scope

Sustantivo corto entre paréntesis, o nada si el cambio es transversal. Los que
ya usa el repo: `core`, `modulos`, `preliquidacion`, `terceros`, `permisos`,
`padron`, `migraciones`, `bitacora`, `context`, `plan`, `scripts`, `admin`,
`auth`, `config`. Si dudás, `git log --oneline -40` y copiá el que ya se usa
para esa zona; no inventes un sinónimo del que ya existe.

### El cuerpo: obligatorio a veces, prohibido otras

**Lleva cuerpo** si hubo una decisión real: se eligió A sobre B, hay un riesgo
asumido, hay un porqué que el diff no muestra, o el cambio corrige algo cuya
causa no es obvia.

**No lleva cuerpo** si el cambio es mecánico: un typo, un número que se
actualiza, un archivo que se mueve sin más.

Porqué esto importa más de lo que parece: el agente `bitacora` lee estos
mensajes para archivar el porqué de cada merge. Un cuerpo inventado para
cumplir se convierte en una decisión que nadie tomó, archivada como si alguien
la hubiera tomado. **Vacío es mejor que relleno.**

Prosa corrida, dos a cinco líneas, como el resto del historial. Viñetas sólo si
el commit toca varias cosas que de verdad se enumeran.

**Con cuerpo** (`a8a2a86`), porque la causa no se ve en el diff:

```
fix(bitacora): los hooks se checkoutean con LF

En Windows con autocrlf, un clon nuevo bajaba scripts/hooks/post-merge
con CRLF y sh rechaza el shebang con \r.
```

**Sin cuerpo** (`f3f4252`), porque no hay nada que explicar:

```
docs(modulos): corrige el conteo de tests a 275 en GUIA-MODULOS.md
```

### El trailer

Última línea, separada del cuerpo por **una línea en blanco**:

```
Co-Authored-By: <modelo de esta sesión> <noreply@anthropic.com>
```

El nombre es el del modelo que está corriendo ahora, no uno fijo: en el
historial conviven `Claude Opus 5 (1M context)`, `Claude Fable 5.1` y
`Claude Fable 5`. El commit `cd6468b` tiene el trailer pegado al subject por
haberlo pasado mal: por eso el mensaje va por HEREDOC.

## Cómo ejecutar el commit

Siempre desde la herramienta **Bash**, nunca PowerShell: no tiene HEREDOC POSIX
y rompe los acentos.

```bash
git commit -F - <<'EOF'
docs(bitacora): PR #47

El porqué, si lo hay.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

El `'EOF'` va **entre comillas simples** para que la shell no expanda `$`,
backticks ni barras invertidas del mensaje.

Nunca `-m` con `\n` escapados: mangonea el cuerpo y el trailer.

**Hooks.** Si un hook falla, pegá su salida textual y pará — nunca
`--no-verify`. Si un hook reescribe archivos (un formateador), no es un fallo:
re-stageá esas mismas rutas y reintentá **una sola vez**. Si vuelve a fallar,
pará y contá qué pasó.

## Reporte

Al terminar, una línea por cosa:

- Rama, y si la creaste vos.
- Hash corto y subject de cada commit.
- Archivos commiteados.
- Archivos omitidos, con el motivo.
- Hooks que corrieron, si hubo.

Si la serie falló a mitad de camino, decí cuáles entraron y qué quedó afuera.
Nunca des por exitosa una serie incompleta.
