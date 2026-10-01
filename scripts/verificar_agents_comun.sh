#!/bin/sh
# Compara el bloque común (entre <!-- comun:inicio y <!-- comun:fin -->) del
# AGENTS.md de este repo con el del repo hermano, clonado al lado del checkout
# principal. Funciona igual desde el checkout principal y desde un worktree.
# Exit 0 si son iguales; 1 con el diff si difieren; 2 si no puede identificar
# el repo o encontrar el hermano.

BK=Gerorios/Preliquidador_AST_BK
FT=Gerorios/Preliquidador_AST_FT

# El repo se reconoce por su origin, no por el nombre de la carpeta.
# https://github.com/X/Y(.git) y git@github.com:X/Y(.git) quedan como X/Y.
repo_de() { git -C "$1" remote get-url origin 2>/dev/null | sed 's#\.git$##; s#^.*github\.com[:/]##'; }
falla() { echo "verificar_agents_comun: $1" >&2; exit 2; }

raiz=$(git rev-parse --show-toplevel) || falla "no estoy dentro de un repo git"
origen=$(repo_de "$raiz")
case "$origen" in
  "$BK") otro=$FT ;;
  "$FT") otro=$BK ;;
  *) falla "no reconozco el repo: origin es '$origen'" ;;
esac

# Desde un worktree, --show-toplevel es el worktree; el checkout principal es
# el padre del directorio .git común, y el hermano está clonado al lado.
comun=$(git rev-parse --path-format=absolute --git-common-dir) ||
  falla "no puedo ubicar el checkout principal"
principal=$(dirname "$comun")
hermano=
for d in "$(dirname "$principal")"/*/; do
  [ "$(repo_de "$d")" = "$otro" ] && { hermano=${d%/}; break; }
done
[ -n "$hermano" ] || falla "no encuentro el repo hermano ($otro) al lado de $principal"
[ -f "$hermano/AGENTS.md" ] || falla "el repo hermano $hermano no tiene AGENTS.md"

bloque() { sed -n '/<!-- comun:inicio/,/<!-- comun:fin -->/p' "$1" | tr -d '\r'; }
a=$(mktemp); b=$(mktemp)
bloque "$raiz/AGENTS.md" > "$a"; bloque "$hermano/AGENTS.md" > "$b"
if diff -u "$a" "$b" > "$a.diff"; then rm -f "$a" "$b" "$a.diff"; exit 0; fi
echo "El bloque común de AGENTS.md difiere del repo hermano ($hermano):" >&2
cat "$a.diff" >&2; rm -f "$a" "$b" "$a.diff"; exit 1
