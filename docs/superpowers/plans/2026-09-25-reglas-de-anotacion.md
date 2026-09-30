# Reglas de anotación en el CLAUDE.md (carril corto)

**Pedido**: el usuario tiene que aclarar en cada sesión dónde se anota cada cosa. El
2026-09-25 un cambio en el VPS quedó sólo en la memoria de Claude, que vive fuera del repo
y no la ve nadie más.

**Causas**: el `CLAUDE.md` dice "anotar en la memoria en cada hito", no nombra
`docs/DEPLOY.md` y la tabla de documentos lista sólo cuatro. La skill global `flujo` manda
anotar en `.claude/Contexto/contexto-proyecto.md`, que en este repo no existe.

**Pasos**:
1. La sección "Los cuatro documentos" pasa a ser "Dónde se anota cada cosa", con una tabla
   única (qué pasó → archivo → cuándo) que incluye `docs/DEPLOY.md`, el cuerpo del PR,
   la bitácora, CONTEXT, ADR, la guía, PUESTA-A-PUNTO, los planes y la memoria.
2. Tres reglas: la memoria no cuenta como anotación para una persona; al avisar se nombra
   el archivo; lo sensible no entra a git porque los repos son públicos.
3. La línea de "Reglas de trabajo" sobre la memoria apunta a la sección nueva, y se aclara
   que la tabla le gana a una skill que diga otra cosa.
4. Fuera del repo: la skill `flujo` deja de nombrar `.claude/Contexto/contexto-proyecto.md`
   y remite a lo que diga el `CLAUDE.md` del repo.

**Verificación**: que los archivos que nombra la tabla existan y que el `CLAUDE.md` no quede
con dos reglas contradictorias. Son sólo docs: no hay tests, ni migración, ni deploy.
