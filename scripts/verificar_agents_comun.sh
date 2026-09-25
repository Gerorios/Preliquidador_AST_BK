#!/bin/sh
# Compara el bloque común (entre <!-- comun:inicio y <!-- comun:fin -->) del
# AGENTS.md de este repo con el del repo hermano, clonado al lado.
# Exit 0 si son iguales o si el hermano no está; exit 1 con el diff si difieren.

raiz=$(git rev-parse --show-toplevel) || exit 1
case "$(basename "$raiz")" in
  backend_preliquidacion) hermano="$raiz/../frontend_preliquidacion" ;;
  frontend_preliquidacion) hermano="$raiz/../backend_preliquidacion" ;;
  *) echo "verificar_agents_comun: no reconozco el repo $(basename "$raiz")" >&2; exit 0 ;;
esac
[ -f "$hermano/AGENTS.md" ] || exit 0

bloque() { sed -n '/<!-- comun:inicio/,/<!-- comun:fin -->/p' "$1" | tr -d '\r'; }
a=$(mktemp); b=$(mktemp)
bloque "$raiz/AGENTS.md" > "$a"; bloque "$hermano/AGENTS.md" > "$b"
if diff -u "$a" "$b" > "$a.diff"; then rm -f "$a" "$b" "$a.diff"; exit 0; fi
echo "El bloque común de AGENTS.md difiere del repo hermano:" >&2
cat "$a.diff" >&2; rm -f "$a" "$b" "$a.diff"; exit 1
