# Reorganización del harness de agentes (BK + FT) — carril completo

Plan del planificador, revisado. Cuando arranque la etapa A se copia a
`docs/superpowers/plans/2026-09-25-reorganizar-harness.md` en su rama.

## Decisiones cerradas por el usuario (2026-09-25)
- AGENTS.md como fuente de las reglas para agentes; CLAUDE.md = `@AGENTS.md` + lo específico de Claude Code. Sin symlinks.
- Controles reales: `ask` en ssh/scp; `pre-commit` que frena `main` salvo un commit con sólo `docs/BITACORA.md`; hook PostToolUse que recuerda `/bitacora` después de `gh pr merge`.
- Bases: `testing` = prueba del área, compartida con otros sistemas, toda DDL pasa primero por ahí. `preliquidacion` = producción (VPS).

## Respuestas del usuario a las preguntas abiertas (2026-09-25)
1. **No se borra ninguna skill.** `grill-me` y `grill-with-docs` se quedan. B sólo edita `grilling` (paso 0) y `domain-modeling` ("En este repo").
2. **Etapa E, sí.** El `.env` local pasa a `testing`; el VPS queda en producción con `PERMITIR_BASE_PRODUCCION=1`.
3. **Los docs públicos no listan tablas**, ni externas ni propias. Lo que la tabla C.4 mandaba a `DOCUMENTACION.md` como nombre de tabla o columna no va a ningún doc: el glosario lo describe en términos del dominio, y quien necesite la tabla consulta la base. En D, sacar además los listados de tablas que hoy tienen `DOCUMENTACION.md` §3, GUIA y PUESTA-A-PUNTO.

## Correcciones al plan tras verificar
- `settings.local.json` NO está trackeado en ningún repo (404 en GitHub): lo ignora `~/.config/git/ignore` de Gero. El paso 0 se reduce a agregarlo igual al `.gitignore` de cada repo (A.4), por las máquinas que no tengan ese global.
- Categoría: el código valida 1 a 12 (`schemas.py:153,170`, `le=12`). Los comentarios de `models.py:72,245` y `schemas.py:125` dicen "1-7" y están viejos: corregirlos en la etapa D.

## Etapas (PRs hermanos BK + FT)
- A. Controles: `scripts/hooks/pre-commit` + `instalar.sh`; `.claude/settings.json` compartido (ask ssh/scp/sftp/rsync, hook PostToolUse `Bash|PowerShell`); `.claude/hooks/recordar-bitacora.sh`; `.gitignore` con `CLAUDE.local.md` y `.claude/settings.local.json`; `.gitattributes` para `.claude/hooks/*`. Barrido de lo sensible.
- B. AGENTS.md (bloque común entre marcadores, duplicado en los dos repos y verificado por `scripts/verificar_agents_comun.sh`) + CLAUDE.md corto + `CLAUDE.local.md` (ruta de gh); se borran `grill-me` y `grill-with-docs`; `grilling` suma el paso 0 "buscar en BITACORA y ADRs"; `domain-modeling` suma "En este repo". Se actualizan los punteros (agente bitacora, skill commit, GUIA §6.3).
- C. `CONTEXT-MAP.md` + `CONTEXT.md` (núcleo) + `docs/modulos/preliquidacion/CONTEXT-preliquidacion.md`; sacar la implementación y las fechas del glosario (tabla C.4 del planificador); `app/core/asistente.py` `_DOCS` suma el glosario nuevo + test de existencia + smoke real contra testing. Docstrings "ver CONTEXT.md" del módulo. Necesita deploy con OK.
- D. `plan-implementacion.md` → `docs/superpowers/plans/`; `DOCUMENTACION.md` corregido (bases, Administración, categoría 1-12, ADRs hasta 0013, recibe lo que sale del glosario); PUESTA-A-PUNTO (repos públicos, `instalar.sh`, sin conteo de tests, CLAUDE.local.md); GUIA §12; README.
- E (opcional, OK aparte). Guardia de base en el lifespan: banner con el nombre de la base + negarse a arrancar contra `preliquidacion` sin `PERMITIR_BASE_PRODUCCION=1`. Orden del deploy: primero la variable en el `.env` del VPS, después el código. El `.env` de Gero pasa a `testing`.

## Verificación por etapa
Ver el reporte del planificador: prueba real del bloqueo en main y de la excepción de la bitácora, `ssh -V` pidiendo confirmación, hook probado con JSON simulado y end-to-end, `/context` mostrando AGENTS.md importado, `verificar_agents_comun.sh` exit 0, `pytest` verde, asistente respondiendo términos de los dos glosarios.
