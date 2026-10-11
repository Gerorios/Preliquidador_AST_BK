@AGENTS.md

## Estado del trabajo (se carga en cada sesión)

@docs/estado.md

Cómo se mantiene: `AGENTS.md`, "Estado del trabajo".

## Específico de Claude Code

Las reglas del proyecto están en `AGENTS.md`, que vale para cualquier agente. Acá va sólo
lo que existe en Claude Code.

- **Skills del repo**: `/commit` (la convención con sus barandas, en
  `.claude/skills/commit/SKILL.md`); `/grilling`, y sus atajos `/grill-me` y
  `/grill-with-docs`, para estresar un plan; `domain-modeling` para el glosario y los ADR;
  `/ponytail-review` para buscar sobre-ingeniería; `flujo-preliquidacion`, la versión de
  este sistema de la skill global `flujo`, que se usa en lugar de la global (no las dos).
- **Bitácora**: la escribe el agente `bitacora` con `/bitacora`, que también actualiza
  `docs/estado.md`; quien lo despachó commitea los dos juntos a `main`. Dos respaldos
  recuerdan preguntar después de un merge: un hook PostToolUse sobre `gh pr merge` y el
  `post-merge` de git.
- **Memoria de Claude**: no guarda el estado de las tareas, que vive en `docs/estado.md`.
  Queda para las preferencias del usuario y las trampas de las herramientas. Vive fuera del
  repo, en la máquina de quien la usa, y no la ve nadie más: lo que importe a una persona
  va a su archivo de la tabla "Dónde se anota cada cosa", y la memoria sólo apunta a ese
  archivo.
- **Lo de cada máquina** (rutas, herramientas fuera del PATH) va en `CLAUDE.local.md`, que
  no se commitea.
