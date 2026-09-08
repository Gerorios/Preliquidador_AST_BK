-- ─────────────────────────────────────────────────────────────────────────────
-- WS15 — Conceptos por cliente y por supervisor (ADR-0011)
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega la columna `supervisor_nombre` (VARCHAR(150), nullable) al maestro
-- concepto_liquidacion: un concepto con supervisor_nombre cargado aplica a
-- las líneas de esa tarea cuyo nombre_supervisor coincida (comparación
-- normalizada, igual que cliente/finca). Además pasa a ser válido cargar un
-- concepto con cliente y SIN finca ("por cliente": aplica a esa tarea+cliente
-- en cualquier finca) — eso no requiere cambio de esquema, solo se documenta.
-- Los 4 caminos (común / por cliente / específico / por supervisor) SUMAN.
--
-- ⚠️  NO ES DIFERIBLE — igual que WS7/WS8: el modelo ORM `ConceptoLiquidacion`
-- ahora declara la columna `supervisor_nombre` y el índice único ahora la
-- incluye. Sin esta migración, cualquier SELECT/INSERT del ORM sobre
-- concepto_liquidacion fallaría ("Unknown column 'supervisor_nombre'").
-- Aplicar ANTES o exactamente junto con el deploy de esta rama, no después.
--
-- El índice único viejo se llama `uq_concepto_unif` (nombre explícito que ya
-- traía el UniqueConstraint del modelo ORM — SQLAlchemy lo creó con ese
-- nombre exacto al crear la tabla). Si en tu base ese índice tiene otro
-- nombre (por ejemplo si se creó a mano o con otra herramienta de migración),
-- ajustá el nombre en el DROP INDEX de abajo antes de correr este script:
--   SHOW INDEX FROM concepto_liquidacion WHERE Key_name <> 'PRIMARY';
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE concepto_liquidacion
  ADD COLUMN supervisor_nombre VARCHAR(150) NULL;

-- Recrear el índice único para incluir supervisor_nombre (dos supervisores
-- distintos pueden tener, cada uno, un concepto propio para la misma
-- tarea/código, y ninguno pisa al común).
ALTER TABLE concepto_liquidacion
  DROP INDEX uq_concepto_unif;

ALTER TABLE concepto_liquidacion
  ADD UNIQUE INDEX uq_concepto_unif (
    quincena, tarea_nombre, cliente_nombre, finca_nombre, codigo, categoria,
    supervisor_nombre
  );
