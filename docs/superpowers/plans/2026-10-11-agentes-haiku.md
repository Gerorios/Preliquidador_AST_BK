# Agentes en Haiku 5.5: Explore y corredor de tests

Carril corto: sin código de la app, sin DDL, sin cambio de API. Ramas `chore/agentes-haiku`
en los dos repos.

**Qué se pide.** Usar Haiku 5.5 (`claude-haiku-5-5`) en las tareas que no necesitan juicio:
buscar en el código y correr la suite. El verificador y los demás agentes no cambian
(decisión del usuario, 2026-10-11).

**Archivos.**
1. `.claude/agents/Explore.md` en los dos repos, idénticos: sólo lectura (Read, Grep, Glob),
   reemplaza al Explore integrado, que corre en el modelo de la sesión. Devuelve rutas y
   líneas; nunca afirma que algo "no se usa" sin mostrar la búsqueda.
2. `.claude/agents/corredor-tests.md` en los dos repos, idénticos: corre el comando que le
   pasan (`pytest` o `npm test`) con las variables del briefing, re-corre aislado cada test
   que falle y devuelve la línea de resumen literal, el exit code y los fallos. No edita.
3. Copia de los dos en `.claude/agents/` de la carpeta de los dos repos (local, fuera de
   git), como el hook de arranque.
4. `flujo-preliquidacion`: cuándo se usa cada uno; la suite de la fase 4 la corre el
   `corredor-tests`, y su resumen literal cuenta como evidencia.
5. `CLAUDE.md` de los dos repos: una línea con los dos agentes.

**Test.** No hay test automático: son prompts. Verificación con una búsqueda real con el
Explore nuevo y la suite del backend con el `corredor-tests`, comparando contra lo esperado
(el modelo se confirma en el resultado del agente). Requiere Claude Code 2.1.293 o más.

**Revisión.** Ninguna ronda: no hay código (regla de la skill para docs y configuración).

## Verificación (2026-10-11)

Con Claude Code 2.1.296, en sesiones nuevas (`claude -p`) desde la carpeta de los dos repos:

- `Explore`: "¿dónde se define `estadisticas_batch`?" devolvió
  `preliquidacion_service.py:1840`, correcto. `modelUsage` muestra `claude-haiku-5-5`.
- `corredor-tests`, suite del backend en este worktree con `.env` ficticio:
  `1013 passed, 1 xfailed, 60 warnings in 316.24s`, exit 0, igual a la salida cruda de
  pytest. En `claude-haiku-5-5`. En un primer intento con una ruta de intérprete que no
  existe, frenó con exit 127 y pidió la ruta, sin improvisar ni instalar nada.
- Una sesión ya abierta no ve agentes nuevos hasta que se reabre (el Explore integrado
  sigue en el modelo de la sesión); por eso la copia en la carpeta de los dos repos.
