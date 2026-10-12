# Docs viejos desde la Facturación E1 (carril corto)

Pedido del usuario (2026-10-11): arreglar los docs que quedaron viejos con la Facturación E1.
Sólo docs y comentarios: sin DDL, sin API, sin código que corra. PRs hermanos: BK primero, FT después.

1. `AGENTS.md` del backend y del front, primer párrafo (fuera del bloque común): tres módulos activos;
   Preliquidación y Facturación en producción, Terceros en producción desde el 2026-09-30 y en
   construcción (lo construye Pitu).
2. `.claude/agents/bitacora.md` (backend): sumar la frontera **Facturación**
   (`app/modulos/facturacion/` y su front).
3. `docs/modulos/GUIA-MODULOS.md` §6.2: `refrescar_testing.py` copia la lista del script (núcleo,
   Preliquidación y Facturación); las `terceros_*` existen desde el 2026-09-30 y todavía no están en
   la lista.
4. `scripts/refrescar_testing.py`, sólo el docstring: "tablas del preliquidador" pasa a "tablas de la
   lista"; el origen ya no es producción en la máquina de desarrollo (el `.env` apunta a `testing` y
   producción se pasa como override, según `CLAUDE.local.md`); "venv activado" sale.
5. `GUIA-MODULOS.md` §1, §3.2 y §3.3 (sumado por el usuario al aprobar): §1 cuenta los tres
   módulos; en el árbol de §3.2 salen "molde, inactivo" y entra Facturación; §3.3 deja de ser "cómo
   activar el molde de Terceros" y pasa a "cómo se suma un módulo", con lo que ya existe de Terceros
   y Facturación como ejemplos.

Sin test rojo: no hay comportamiento. Verificación: `sh scripts/verificar_agents_comun.sh` en los dos
repos, `python -m pytest tests/core/test_refrescar_testing.py -q` y `git diff` de sólo docs y
comentarios. Revisión: ninguna ronda (sólo docs y comentarios).

6. `CONTEXT.md` (sumado por el usuario, con domain-modeling): "Módulo activo" deja de decir que
   Terceros nace inactivo (un módulo puede nacer inactivo; activo no es terminado) y "Módulo" nombra
   a Facturación.

Fuera de alcance: el encabezado de
`migrations/core/002` (zona sensible, PR aparte en "A futuro") y sumar las `terceros_*` al script.
