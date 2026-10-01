# verificar_agents_comun.sh desde worktrees (carril corto)

- **Qué**: el script decide qué repo es por el nombre de la carpeta; desde un worktree imprime
  "no reconozco el repo" y sale con exit 0 sin comparar. Pasa a identificar el repo por
  `git remote get-url origin` (`Gerorios/Preliquidador_AST_BK` = backend, `..._FT` = frontend,
  acepta https y ssh, con o sin `.git`).
- **Hermano**: checkout principal = carpeta padre de `git rev-parse --path-format=absolute
  --git-common-dir`; se busca entre las carpetas al lado de ese checkout la que tenga como origin
  el remoto del otro repo (así no depende de cómo se llame la carpeta). Se compara contra su
  `AGENTS.md`.
- **Falla (exit 2, mensaje claro)** si no reconoce el remoto o no encuentra el hermano. Exit 1
  sigue siendo "difieren". El `pre-commit` no cambia: sigue avisando sin frenar.
- **Archivos**: `scripts/verificar_agents_comun.sh` en los dos repos, idéntico (PRs hermanos).
- **Rojo primero**: correr el script actual desde el worktree → "no reconozco" + exit 0.
- **Verificación**: exit 0 desde checkout principal y desde worktree en los dos repos; con el
  bloque común alterado en el worktree → exit 1 con diff; restaurar → exit 0; remoto
  desconocido (clon temporal sin origin) → exit 2.
