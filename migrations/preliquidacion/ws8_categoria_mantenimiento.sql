-- ─────────────────────────────────────────────────────────────────────────────
-- WS8 — Mantenimiento mecánico por categoría (ADR-0008)
-- Base: db_propia (sistema de preliquidación).
--
-- Agrega la columna `categoria` (1-7, nullable) al maestro concepto_liquidacion:
-- un concepto con categoria=NULL se comporta exactamente como hoy (aplica a
-- todas las líneas que matchean tarea/cliente/finca). Un concepto con
-- categoria=X aplica SOLO si la persona de la línea (cruzada por CUIL) tiene
-- esa categoría asignada en la tabla nueva categoria_operario para esa
-- quincena. El importe sigue calculándose igual (unidad_base='hsjornal').
--
-- ⚠️  NO ES DIFERIBLE — igual que WS7: el modelo ORM `ConceptoLiquidacion`
-- ahora declara la columna `categoria` y el índice único ahora la incluye.
-- Sin esta migración, cualquier INSERT/SELECT del ORM sobre concepto_liquidacion
-- fallaría ("Unknown column 'categoria'") o violaría el índice único viejo
-- (que no contempla categoria). Aplicar ANTES o exactamente junto con el
-- deploy de esta rama, no después.
--
-- El índice único viejo se llama `uq_concepto_unif` (nombre explícito que ya
-- traía el UniqueConstraint del modelo ORM — SQLAlchemy lo creó con ese
-- nombre exacto al crear la tabla). Si en tu base ese índice tiene otro
-- nombre (por ejemplo si se creó a mano o con otra herramienta de migración),
-- ajustá el nombre en el DROP INDEX de abajo antes de correr este script:
--   SHOW INDEX FROM concepto_liquidacion WHERE Key_name <> 'PRIMARY';
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE concepto_liquidacion
  ADD COLUMN categoria TINYINT NULL;

-- Recrear el índice único para incluir categoria (dos personas de distinta
-- categoría pueden tener, cada una, un concepto propio para la misma
-- tarea/cliente/finca/código).
ALTER TABLE concepto_liquidacion
  DROP INDEX uq_concepto_unif;

ALTER TABLE concepto_liquidacion
  ADD UNIQUE INDEX uq_concepto_unif (
    quincena, tarea_nombre, cliente_nombre, finca_nombre, codigo, categoria
  );

-- Categoría (1-7) de cada operario, administrada por el liquidador, por
-- quincena. Una persona puede cambiar de categoría de una quincena a otra.
CREATE TABLE categoria_operario (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  quincena  DATE NOT NULL,
  cuil      VARCHAR(20) NOT NULL,
  categoria TINYINT NOT NULL,
  UNIQUE KEY uq_categoria_operario (quincena, cuil)
);
