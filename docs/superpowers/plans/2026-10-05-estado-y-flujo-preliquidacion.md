# Plan: estado + bitácora y skill `flujo-preliquidacion`

Skill `flujo`, carril completo (dos repos, cambia la regla de `main`, hooks en varios
lugares, decisiones abiertas al arrancar). Base: instructivo "estado solo con lo vivo,
bitácora con lo hecho" de otro proyecto de Gero, adaptado.

- `BK` = `backend_preliquidacion/.claude/worktrees/estado-y-flujo` (rama `docs/estado-y-flujo`, desde 39a5e1d)
- `FT` = `frontend_preliquidacion/.claude/worktrees/estado-y-flujo` (rama `docs/estado-y-flujo`, desde adc284c)
- `RAIZ` = carpeta `Sistema_Preliquidacion` (no es repo; ahí se abren casi todas las sesiones)
- `BK_MAIN` / `FT_MAIN` = checkouts principales; `MEM` = memoria de Claude de la máquina de Gero

## Decisiones cerradas (entrevista con Gero, 2026-10-05)

1. `docs/estado.md` en el BK con **sólo lo vivo** (En curso con fase y plan, Próximo paso,
   Pendientes del usuario —de Gero y de Pitu, lo de Pitu también se le anota a Gero—, A
   futuro con su porqué). Nada entregado. **Va directo a `main`**: se reabre la decisión del
   2026-09-11 ("no extender la excepción") y la excepción cubre `docs/BITACORA.md` y
   `docs/estado.md`, con el mismo porqué (por PR sería una cadena de merges; no ejecuta
   nada). Repo público: sin IPs, hosts, URLs, credenciales, datos de terceros ni valores.
2. `docs/BITACORA.md` no cambia de orden (la más nueva abajo, append-only).
3. Hook `SessionStart` (`startup|resume|clear|compact`, timeout 10) que imprime las **2
   últimas** entradas de la bitácora, tope 8.000 caracteres, sale 0 siempre. En RAIZ (fuera
   de git), BK y FT.
4. `CLAUDE.md` de RAIZ (nuevo, fuera de git), BK y FT importan `estado.md`.
5. `AGENTS.md` de los dos repos: regla "Estado del trabajo" y excepción ampliada, dentro del
   bloque común.
6. Skill **`flujo-preliquidacion`** en el BK (`.claude/skills/flujo-preliquidacion/`): copia
   de la global adaptada (junction de `node_modules`, `.env` del worktree, zonas sensibles
   con 2 rondas, regla estado/bitácora en la entrega, lo que el proyecto ya define). La
   global no se toca. Zonas sensibles: motor de reglas y cálculo de importes, maestro de
   conceptos y precios, exportación a sueldos, autenticación/roles/permisos de módulos,
   migraciones y DDL. Controles de lectura y pantallas: 1 ronda.
7. El agente `bitacora`, al anotar un merge, también saca la tarea de `estado.md` y deja en
   una línea lo pendiente; quien lo despachó commitea los dos juntos a `main`. Los avances
   (plan aprobado, pausa, revisión) los actualiza la sesión principal.
8. Memoria de Claude: comparar los archivos de tareas contra la bitácora, completar lo que
   falte en la bitácora o en `estado.md`, y borrarlos. Quedan las reglas de Gero.

## Qué hay en el código

- `BK/.claude/settings.json` y `FT/.claude/settings.json`: idénticos, `permissions.ask` para
  ssh/scp y `PostToolUse` con `recordar-bitacora.sh` vía `$CLAUDE_PROJECT_DIR`. `.gitattributes`
  de los dos repos ya fuerza LF en `.claude/hooks/*` y `scripts/hooks/*`.
- `BK/scripts/hooks/pre-commit` L17-18: `[ "$stageados" = "docs/BITACORA.md" ] && exit 0`;
  L2-4 y L23 nombran la excepción. El del FT no tiene excepción y no cambia. Se instalan por
  copia (`scripts/hooks/instalar.sh`): tras el merge hay que reinstalar en cada clon del BK.
- Sin tests de hooks/scripts en `tests/`; el pre-commit se probó a mano (bitácora L814).
- Bitácora: `## AAAA-MM-DD — Tema`, secciones `**Mergeado** / **Por frontera** /
  **Decisiones** / **Estado** / **Pendiente**`; entradas de deploy aparte. Las dos últimas
  suman ~5.600 caracteres (hay entradas de ~9.000).
- `BK/.claude/agents/bitacora.md` ("Vale sólo para este archivo", sección "La memoria") y
  `BK/.claude/commands/bitacora.md` lo despachan.
- **`BK/.claude/skills/commit/SKILL.md` L35 y L67-74 tienen la excepción escrita**: sin
  actualizarla, `/commit` se niega a commitear bitácora + estado juntos en `main`.
- El bullet "Memoria de Claude" de los `CLAUDE.md` dice que la memoria guarda el estado
  entre sesiones: contradice el esquema nuevo, se reescribe.
- **Visibilidad de la skill**: una sesión abierta en RAIZ ve las skills del BK con prefijo
  (`backend_preliquidacion:grilling`, comprobado en la sesión que armó este plan), así que
  `flujo-preliquidacion` aparece como `backend_preliquidacion:flujo-preliquidacion`. Una sesión
  abierta sólo en el FT no la ve: el `CLAUDE.md` del FT apunta al archivo.
- `FT_MAIN` muestra `.claude/worktrees/` como untracked: se suma `.claude/worktrees/` al
  `.gitignore` de los dos repos.
- Deuda "precio <= 0": `preliquidacion_service.py` `reglas_completas` y el SQL de faltantes
  (citar por nombre, no por línea).
- `MEM/proyecto-preliquidacion.md` está vencida (dice que se pushea directo a `main`): se borra.

## Pasos

### Etapa A — PR BK

**A0.** Guardar este plan (sesión principal).

**Par A1 — hook `ultimas-entregas.mjs`.** `BK/tests/hooks/__init__.py`,
`BK/tests/hooks/test_ultimas_entregas.py` (pytest con `subprocess` y `node`; `pytest.skip`
si falta `node`), `BK/.claude/hooks/ultimas-entregas.mjs`. Casos con bitácoras de juguete
(`## 2026-01-01 — A`, `B`, `C`): (1) `CLAUDE_PROJECT_DIR` = raíz con
`backend_preliquidacion/docs/BITACORA.md`: imprime B y C, no A, B antes que C, exit 0;
(2) `CLAUDE_PROJECT_DIR` = `backend_preliquidacion`: igual; (3) worktree del FT
(`frontend_preliquidacion/.claude/worktrees/x`): encuentra la del BK subiendo por los
ancestros; (4) clon con otro nombre: usa su propia `docs/BITACORA.md`; (5) sin bitácora:
vacío, exit 0; (6) una sola entrada; (7) más de 8.000 caracteres: recorta con aviso; (8)
CRLF; (9) el encabezado dice "la más reciente al final" y da la ruta de `docs/estado.md`.
Rojo: no existe el `.mjs`. Verde: `.mjs` adaptado del instructivo: `ENTRADAS = 2`,
`secciones.slice(-ENTRADAS)` en orden de archivo, búsqueda de
`<ancestro>/backend_preliquidacion/docs/BITACORA.md` subiendo desde `CLAUDE_PROJECT_DIR`
(o cwd), si no `<CLAUDE_PROJECT_DIR>/docs/BITACORA.md`, si no exit 0; imprime las rutas
absolutas de la bitácora y de `estado.md` usadas; tope 8.000; try/catch; exit 0.
Verificación: `python -m pytest tests/hooks/test_ultimas_entregas.py -q`; a mano
`node .claude/hooks/ultimas-entregas.mjs`; `git check-attr eol` → lf.

**Par A2 — `pre-commit` con la excepción ampliada.** `BK/tests/hooks/test_pre_commit.py`
(repo temporal en `tmp_path`, hook copiado, semilla con `--no-verify` sólo ahí; skip si falta
`git`), `BK/scripts/hooks/pre-commit`. Casos en `main`: sólo BITACORA → 0; sólo estado → 0
(rojo hoy); los dos → 0 (rojo hoy); estado + README → 1 con "Commit frenado"; sólo README →
1; en rama, README → 0. Verde:

```sh
stageados=$(git diff --cached --name-only)
otros=$(printf '%s\n' "$stageados" | grep -vx -e 'docs/BITACORA.md' -e 'docs/estado.md')
[ -n "$stageados" ] && [ -z "$otros" ] && exit 0
```

más L2-4 y L23 ("Única excepción: un commit que sólo toque docs/BITACORA.md y/o
docs/estado.md"). `sh -n` sin errores. Verificación: `python -m pytest tests/hooks -q`.

**A3.** `BK/.claude/settings.json`: bloque `SessionStart` al lado del `PostToolUse`
(`node "$CLAUDE_PROJECT_DIR/.claude/hooks/ultimas-entregas.mjs"`, timeout 10). JSON válido.

**A4.** `BK/docs/estado.md` inicial (forma del instructivo; cabecera: "lo entregado está en
`docs/BITACORA.md` (la más nueva abajo); la regla en `AGENTS.md`"):
- **En curso**: esta tarea, con su plan y fase.
- **Próximo paso**: mergear BK y FT, reinstalar el `pre-commit` (`sh scripts/hooks/instalar.sh`),
  probar el arranque en una sesión nueva, `/bitacora`.
- **Pendientes del usuario**: cargar `TALLER_SHEET_URL` en el `.env` del servidor y reiniciar
  (hasta entonces las alertas de Terceros responden 502 a propósito); asignar el módulo
  Terceros desde Administración; smoke en el sitio real de Concepto extra (BK #67 / FT #53),
  orden y TOTAL en Revisión (FT #54, incluido editar con orden activo) y Tancadas vs Jornal
  (BK #69 / FT #55); confirmar que el valor hora pulverización de la 1Q de septiembre es el
  valor base sin recargo; decidir si se borra la regla de tancada de prueba en `testing`
  (1Q de septiembre); confirmar si las líneas de campo repetidas por parte en agosto fueron
  dos pasadas reales; actualizar en `docs/DEPLOY.md` (local) la nota de migraciones
  históricas (ws17 ya es `historica`, BK #71); aceptación de la etapa 7 de Terceros y la
  revisión de dos ejes del BK #59 (de Pitu).
- **A futuro**: 5 warnings `react-hooks/exhaustive-deps` en Terceros; el control de
  completitud cuenta precio <= 0 como completo (sin urgencia); un id repetido en `linea_ids`
  agrega el concepto dos veces (BK #67); minors de BK #70, FT #54 y BK #69; comentario viejo de
  Terceros en `migrations/ORDEN.txt`; agrupar Verificación por (empresa, legajo) descartado
  salvo caso real (entonces por CUIL; respaldo en ramas locales); deudas menores del incidente
  del 2026-09-18/23: ver la bitácora de esas fechas.
- Verificación: grep sin IPs, URLs, contraseñas ni mails; menos de ~60 líneas.

**A5.** `BK/AGENTS.md`, bloque común: bullet de "rama antes de editar" con la excepción
ampliada; fila nueva en "Dónde se anota cada cosa" para `docs/estado.md` y la de merge suma
"y la tarea sale de `docs/estado.md`"; sección nueva `### Estado del trabajo` (adaptación del
Paso 5 del instructivo, la más nueva **abajo**, menciona el hook); `### Bitácora` →
`### Bitácora y estado` con la excepción de los dos archivos, su porqué y la reapertura;
"No extender la excepción a ningún otro archivo".

**A6.** `BK/CLAUDE.md`: `## Estado del trabajo (se carga en cada sesión)` con `@docs/estado.md`;
"Skills del repo" suma `flujo-preliquidacion`; "Bitácora" suma que actualiza `estado.md`;
"Memoria de Claude" reescrito (no guarda estado de tareas).

**A7.** `bitacora.md` (agente: descripción, paso 4, subsección `docs/estado.md` con
autonomía acotada, "La memoria", salida con el diff de `estado.md`); `commands/bitacora.md`
(commitear los dos juntos); `skills/commit/SKILL.md` L35 y L67-74 (los dos archivos, solos o
juntos; mezclados con otros → parar); `docs/modulos/PUESTA-A-PUNTO.md` (pre-commit y §8),
`README.md` y `docs/DOCUMENTACION.md` (fila para `estado.md`). `.gitignore` suma
`.claude/worktrees/`. Verificación: grep de "Vale sólo para" y de la excepción vieja sin
coincidencias fuera de la bitácora y planes viejos.

**A8.** `BK/.claude/skills/flujo-preliquidacion/SKILL.md`: copia de la global con
`name: flujo-preliquidacion` y description "versión del Sistema de Preliquidación de `flujo`;
se usa en lugar de la global". Reemplaza "Esta skill es genérica…" por: (a) worktrees con
junction de `node_modules` (`cmd /c mklink /J`), quitarlo con `cmd /c rmdir` antes de borrar
el worktree, nunca `rm -rf` sobre el junction; el venv del BK sirve desde el worktree;
(b) `.env`: ficticio para tests (hosts `.invalid`) o variables en línea; para levantar la app
sólo las de `testing` exportadas al proceso, nunca `DB_PROD_*` ni `DB_DEV_*` (ADR-0014);
(c) zonas sensibles con sus archivos; (d) estado/bitácora en fases 2, 3 y 5; (e) lo que el
proyecto define (plan en `docs/superpowers/plans/` del BK, PRs hermanos, `--body-file`,
`gh pr merge N --merge --admin`, deploy sólo con OK y detalle en `docs/DEPLOY.md` local más
entrada de deploy en la bitácora, `testing` vs `preliquidacion`, repos públicos, `/commit`,
`grilling` con antecedentes, ADR sólo con el usuario). Verificación: frontmatter; grep sin
nombres de otros proyectos.

**A9.** Suite completa; commits con `/commit` (`test`, `chore`, `docs`); PR con `--body-file`
(incluye la reapertura de la decisión del 2026-09-11 y "después del merge: `sh
scripts/hooks/instalar.sh` en cada clon del BK"); merge con OK; en `BK_MAIN`: pull,
`instalar.sh`, `grep -c estado.md .git/hooks/pre-commit`.

### Etapa B — PR FT (se mergea después del BK)

**B1.** Copia idéntica del `.mjs` y bloque `SessionStart` en `FT/.claude/settings.json`;
`cmp` contra el del BK; prueba a mano con `CLAUDE_PROJECT_DIR` en `FT_MAIN`, en el worktree y
en una carpeta vacía (sin salida, exit 0).
**B2.** Bloque común de `AGENTS.md` idéntico al del BK (diff vacío worktree contra worktree);
`.gitignore` suma `.claude/worktrees/`.
**B3.** `FT/CLAUDE.md`: `@../backend_preliquidacion/docs/estado.md` (en un worktree no
resuelve; la ruta la imprime el hook), puntero a la skill `flujo-preliquidacion` del BK,
"Memoria de Claude" reescrito.
**B4.** Sin código: lint y build no aplican. Commits, PR, merge con OK; con los dos `main`
pulleados, `sh scripts/verificar_agents_comun.sh` → 0 desde los dos.

### Etapa C — RAIZ (fuera de git)

**C1.** `RAIZ/.claude/hooks/ultimas-entregas.mjs` (copia, `cmp`) y `SessionStart` en
`RAIZ/.claude/settings.local.json` sin tocar `permissions`.
**C2.** `RAIZ/CLAUDE.md`: `@backend_preliquidacion/docs/estado.md` + tres líneas (dos repos y
dónde están las reglas; para tareas que modifiquen un repo usar
`backend_preliquidacion:flujo-preliquidacion` en lugar de la global; dónde está la bitácora).
**C3.** Prueba de punta a punta en sesiones nuevas (RAIZ, `BK_MAIN`, `FT_MAIN`): aprobar el
hook la primera vez; `/memory` muestra el import; "¿qué se hizo último y qué está
pendiente?" se responde sin leer archivos; `/clear` y repetir; en RAIZ la skill aparece.

### Etapa D — memoria (sesión principal, con OK de Gero sobre el cuadro)

Lo de los archivos de tareas está en la bitácora o en `docs/DEPLOY.md`, salvo lo que A4 suma
a `estado.md`. Borrar los 7 de tareas y `proyecto-preliquidacion.md`; `MEMORY.md` queda con
`seguir-skills-sin-desvios` y `usuario-dueno-proyecto` (con una línea: el estado vive en
`backend_preliquidacion/docs/estado.md`).

### Etapa E — después de los merges

Borrar worktrees `estado-y-flujo` (y `esquema-base-ws17` si sigue) y ramas; `/bitacora`: el
agente escribe la entrada y edita `estado.md` por primera vez; commit de los dos juntos en
`main` con `/commit` (prueba real de la excepción y de la skill `commit`).

**Corte de PRs:** BK (todo lo de la etapa A, `estado.md` inicial incluido: la regla que lo
habilita entra con ese PR) y FT (etapa B). Orden: BK primero.

### Pasos de la revisión (2026-10-05)

Ejecución A1-A8 y B1-B3 hecha: `tests/hooks` 15/15, suite del backend 984 passed y
1 xfailed. Revisión (una ronda): 1 urgent, 1 high, 6 minor sin tocar, 5 descartados.

**Paso R1 (urgent, par).** `scripts/hooks/pre-commit:17`: `git diff --cached --name-only`
lista sólo el nombre nuevo de un renombre, así que en `main` pasa un commit que borra
`docs/estado.md` y después `git mv app/x.py docs/estado.md` (borra código sin PR). El hueco
existía también con `BITACORA.md`. Arreglo: `--no-renames`. Test rojo en
`tests/hooks/test_pre_commit.py`: borrar `docs/estado.md` en un commit (pasa), después
`git mv README.md docs/estado.md` y esperar rc 1; ídem con `BITACORA.md`.

**Paso R2 (high, docs).** `.claude/skills/flujo-preliquidacion/SKILL.md` (fase 2 y "al
avanzar") y `AGENTS.md` (bloque común, "Al avanzar", en los dos repos): no dicen dónde se
edita `docs/estado.md`. Si la sesión lo edita en el worktree, viaja en el PR de la tarea y
choca con lo que `/bitacora` cambia en `main`. Arreglo: "se edita en el checkout principal
del backend, en `main`, como la bitácora; nunca en el worktree de la tarea". Bloque común
idéntico en los dos repos.

**Hecho R1 y R2.** R1: `--no-renames`, 2 casos nuevos en rojo antes del arreglo; `tests/hooks` 17/17.
R2: la regla quedó en la skill (fases 2, 3 y 5) y en el bloque común de los dos `AGENTS.md`.
Minor sin tocar (van al PR): porqué de la excepción vs commits "al avanzar"; la regla repetida
en ~9 lugares; `.mjs` copiado sin chequeo de igualdad; glifo ⏸ heredado; comentario de
`exitCode`; líneas sin cortar en la skill.

## Riesgos

1. Aprobación del hook la primera vez en cada lugar: se prueba en C3.
2. Sesión abierta sólo en el FT no ve la skill: puntero en `FT/CLAUDE.md`.
3. CRLF: `.gitattributes` cubre los hooks; el caso 8 de A1 cubre la bitácora con CRLF.
4. `@../` desde un worktree del FT no resuelve: el hook imprime la ruta real.
5. El hook depende del nombre de carpeta `backend_preliquidacion` (fijado en PUESTA-A-PUNTO).
6. Tope de 8.000: con entradas largas recorta la segunda, con aviso.
7. Repo público: `estado.md` se edita seguido y directo a `main`; regla escrita y grep.
8. Reapertura de la decisión del 2026-09-11: registrada en PR y bitácora; el resto de los
   archivos sigue frenado (casos 4-5 de A2).
9. Hook instalado por copia: hasta reinstalar, el pre-commit viejo frena `estado.md`.
10. Tests dependen de `node` y `git`: skip si faltan.
11. Junction de `node_modules`: nunca `rm -rf`.
12. Borrar memoria es irreversible: después de A4 y con OK.

Sin migraciones, DDL, deploy ni datos tocados.

## Preguntas abiertas — cerradas (Gero aprobó las recomendaciones, 2026-10-05)

1. Tests de hooks en pytest (`tests/hooks/`) con skip: sí.
2. ~~Junction de la skill en RAIZ~~: no hace falta (la skill del BK se ve desde RAIZ con prefijo).
3. Si `@../` no carga en `FT_MAIN`, el hook imprime además el inicio de `estado.md`: se decide
   con la evidencia de B3.
4. Pendientes encontrados en la bitácora (id repetido en `linea_ids`, etapa 7 de Terceros,
   revisión del BK #59) entran; los del 2026-09-18/23 como una línea remitiendo a la bitácora.
5. `.claude/worktrees/` al `.gitignore` de los dos repos: sí.
6. El hook imprime en orden de archivo (penúltima, última).
7. Copia del hook en RAIZ (no apuntar al del BK): sí, como la decisión 3.
8. Borrar `proyecto-preliquidacion.md`: sí.

## Fuera de alcance

La skill global `flujo`; el orden o el formato de la bitácora; el `pre-commit` del FT,
`post-merge`, `recordar-bitacora.sh`, `instalar.sh`; resolver los pendientes de `estado.md`;
deploy.
