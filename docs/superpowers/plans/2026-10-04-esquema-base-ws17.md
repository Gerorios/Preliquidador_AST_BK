# Plan: esquema base con el índice de ws17 (carril corto)

Rama `chore/esquema-base-ws17`. Cierre del ADR-0018 (BK #70), pendiente anotado en la bitácora y en
`docs/DEPLOY.md`: ws17 ya está aplicada en producción y en `testing`.

1. **Qué**: regenerar `migrations/preliquidacion/000_esquema_base.sql` con `scripts/exportar_esquema.py`
   desde **producción** (sólo `SHOW CREATE TABLE`), para que traiga el `uq_concepto_unif` funcional, y marcar
   `preliquidacion/ws17_concepto_unico_normalizado.sql` como `historica` en `migrations/ORDEN.txt` (con el
   comentario que dejó el PR #70 actualizado).
2. **Cómo se corre**: desde el worktree, con `DB_PROPIA_*` tomadas de las `DB_PROD_*` del `.env` principal sólo
   para ese proceso (el script lee `DB_PROPIA_*`). No se copia ningún `.env` al worktree.
3. **Seguro**: ninguna migración posterior al 000 sin marca `historica` (core/001, terceros/001-007) toca las
   tablas que exporta el script. El script también reescribe `migrations/core/000_usuarios.sql`: si cambia algo
   además de la fecha, se muestra y se decide antes de commitear.
4. **Test rojo**: no hay uno natural (es un archivo exportado). La verificación es el diff: en el 000 de
   preliquidación sólo deben cambiar la fecha de la cabecera y el `UNIQUE KEY uq_concepto_unif`; el diff no
   puede traer datos (`SHOW CREATE TABLE` no los trae) ni hosts.
5. **Verificación**: `pytest tests/core/test_manifiesto_migraciones.py` (incluye "las históricas van después del
   esquema base") y la suite completa una vez.
