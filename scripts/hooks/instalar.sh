#!/bin/sh
# Copia los hooks versionados a .git/hooks (que no se versiona).
# Correr una vez por clon: sh scripts/hooks/instalar.sh

raiz=$(git rev-parse --show-toplevel) || exit 1
destino="$raiz/.git/hooks"

for hook in post-merge; do
  cp "$raiz/scripts/hooks/$hook" "$destino/$hook" || exit 1
  chmod +x "$destino/$hook"
  echo "instalado: .git/hooks/$hook"
done
