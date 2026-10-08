# Chequeo del bloque común de AGENTS.md dentro del hook pre-commit

Carril corto: un archivo de código por repo, sin DDL, sin API.

- **Qué**: dentro de un hook, git exporta `GIT_DIR` (y `GIT_INDEX_FILE`), así que
  `repo_de()` en `scripts/verificar_agents_comun.sh` lee el origin del repo propio para
  cualquier carpeta y nunca encuentra al hermano: el aviso del `pre-commit` no compara nada.
- **Arreglo**: en `repo_de()`, correr el `git -C` en un subshell sin las variables locales
  de git (`unset $(git rev-parse --local-env-vars)`, la lista oficial que usa git en sus
  propios scripts). Las llamadas de arriba (`--show-toplevel`, `--git-common-dir`) quedan
  como están: ésas sí tienen que respetar el repo del hook.
- **Archivos**: `scripts/verificar_agents_comun.sh` en el backend y el mismo cambio en el
  front (PR hermano; el script es idéntico en los dos).
- **Test rojo primero**: `tests/hooks/test_verificar_agents_comun.py` arma dos repos de
  juguete al lado (origins BK y FT) y (1) corre el script con `GIT_DIR` exportado: espera
  exit 0 y hoy da 2; (2) commitea un cambio en `AGENTS.md` con el `pre-commit` real
  instalado y un bloque distinto en el hermano: espera "difiere" en stderr, hoy dice "no
  encuentro el repo hermano".
- **Verificación**: el test nuevo rojo y después verde, `tests/hooks/` completo, suite
  completa una vez. El front no tiene pytest: el test del backend cubre el script, y se
  verifica a mano que los dos scripts quedan idénticos y que la reproducción con `GIT_DIR`
  pasa desde el front.
