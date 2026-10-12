# La bitácora se anota sin preguntar

Fecha: 2026-10-11. Carril corto: sólo docs y el texto de un hook, sin código de la app.

- **Qué se pide:** después de cada merge a `main`, correr `/bitacora` sin preguntar. El
  push de `main` sigue esperando el OK del usuario.
- **Archivos:** `AGENTS.md` (bloque común, igual en los dos repos), `CLAUDE.md` y
  `.claude/hooks/recordar-bitacora.sh` de los dos repos, y la fase 5 de
  `.claude/skills/flujo-preliquidacion/SKILL.md` del backend.
- **Sin test rojo:** no hay código. Se verifica que el bloque común quede igual en los dos
  repos y que cada hook siga devolviendo JSON válido ante un `gh pr merge`.
- **Revisión:** ninguna ronda, por ser sólo docs (`flujo-preliquidacion`, fase 4).
