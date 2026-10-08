# Skill impeccable en el front y regla de uso (carril corto)

1. **Qué se pide**: instalar la skill `impeccable` (pbakaus/impeccable, Apache-2.0, commit
   `778c8a7b71cc`) sólo en `frontend_preliquidacion`, con sus 4 agentes y sin sus hooks, y
   que toda tarea con cambio visual o feature nueva la use. La regla vale para todo el front
   (Preliquidación y Terceros); la refacción de UX/UI que viene después es sólo de
   Preliquidación.
2. **Front** (PR 1): `.claude/skills/impeccable/` y `.claude/agents/impeccable-*.md` copiados
   tal cual, más el `LICENSE` del original; `.claude/settings.json` suma
   `env.IMPECCABLE_HOME=.impeccable` (el motor que baja el lanzador queda en el proyecto, no
   en `~/.impeccable`); `.gitignore` suma `.impeccable/`; `.gitattributes` deja la carpeta
   de la skill sin conversión de fin de línea (el lanzador es `sh`); `eslint.config.js`
   ignora `.claude/skills/impeccable`; `CLAUDE.md` nombra la skill.
3. **Backend** (PR 2, hermano): bloque común de `AGENTS.md` (igual en los dos repos): regla
   "cambio visual o feature nueva con interfaz → `impeccable`", y en la tabla "Dónde se
   anota cada cosa" `PRODUCT.md` y `DESIGN.md` del front. `flujo-preliquidacion`: en qué
   fase entra cada comando (`shape` en entrevista/plan, `craft-floor` antes de editar,
   `critique`/`audit` en la revisión). `GUIA-MODULOS.md`: las reglas 20 y 8.3 pasan a
   decir que la estética la fija `DESIGN.md` del front y sólo cambia con `impeccable` y OK
   del usuario; siguen CSS Modules, tokens en `index.css`, sin Tailwind, sin dependencias
   sin aprobar y sin emojis.
4. **Sin test rojo**: no hay código de la app. Verificación: `sh scripts/verificar_agents_comun.sh`
   (igual en los dos worktrees), `npx eslint .` en el front no suma errores sobre `main`,
   `npm run build` OK, el lanzador responde (`impeccable.cmd` y `sh impeccable`) dejando el
   motor en `.impeccable/` y no en `~/.impeccable`, y una sesión nueva abierta en el front
   lista la skill.
5. **Paso R1** (revisión, high): la regla 20 y la 8.3 de `GUIA-MODULOS.md` y "Cambios de
   interfaz" de `AGENTS.md` daban `DESIGN.md` como vigente, y no existe hasta el `init`.
   Falla: quien arma una pantalla busca la estética ahí y no la encuentra. Arreglo: "la fija
   `src/index.css` (y `DESIGN.md` del front cuando exista)", igual en los dos `AGENTS.md`.
6. **Paso R2** (revisión, high): la sección nueva de `flujo-preliquidacion` pedía el smoke "en
   escritorio y en celular", una regla que nadie decidió. Falla: toda tarea de interfaz,
   Terceros incluido, exigiría una prueba en celular. Arreglo: "las pantallas tocadas".
7. **Fuera de alcance**: `/impeccable init` (escribe `PRODUCT.md`) y la refacción, que
   arrancan en la tarea siguiente con el flujo completo.
