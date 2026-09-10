---
description: Anota en la bitácora los merges nuevos de main (dispara el agente bitacora)
---

Despachá el agente `bitacora` para que anote los merges que entraron a `main`
y todavía no están en `docs/BITACORA.md`.

Pasos:

1. Averiguá cuál fue el último merge ya anotado: la fecha y los PRs de la
   última entrada de `docs/BITACORA.md`.
2. Listá los merges de `main` posteriores a eso (`git log --merges`).
3. Si no hay nada nuevo, decilo y terminá. No despaches el agente al vacío.
4. Si hay, despachá el agente `bitacora` pasándole qué merges cubrir.

Argumentos (opcional): $ARGUMENTS puede traer números de PR específicos a
anotar, o un rango de fechas. Si viene vacío, cubrí todo lo pendiente.
