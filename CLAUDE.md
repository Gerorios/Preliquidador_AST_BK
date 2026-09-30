@AGENTS.md

## Específico de Claude Code

Las reglas del proyecto están en `AGENTS.md`, que vale para cualquier agente. Acá va sólo
lo que existe en Claude Code.

- **Skills del repo**: `/commit` (la convención con sus barandas, en
  `.claude/skills/commit/SKILL.md`); `/grilling`, y sus atajos `/grill-me` y
  `/grill-with-docs`, para estresar un plan; `domain-modeling` para el glosario y los ADR;
  `/ponytail-review` para buscar sobre-ingeniería.
- **Bitácora**: la escribe el agente `bitacora` con `/bitacora`, y el commit lo hace quien
  lo despachó. Dos respaldos recuerdan preguntar después de un merge: un hook PostToolUse
  sobre `gh pr merge` y el `post-merge` de git.
- **Memoria de Claude**: guarda el estado entre sesiones (qué quedó a medias, trampas
  encontradas) y se actualiza en cada hito. Vive fuera del repo, en la máquina de quien la
  usa, y no la ve nadie más: lo que importe a una persona va a su archivo de la tabla
  "Dónde se anota cada cosa", y la memoria sólo apunta a ese archivo.
- **Lo de cada máquina** (rutas, herramientas fuera del PATH) va en `CLAUDE.local.md`, que
  no se commitea.
