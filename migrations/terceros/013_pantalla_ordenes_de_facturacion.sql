-- terceros/013 — El rol «Liquidador de terceros» suma la pantalla Órdenes de
-- facturación (etapa 11).
-- Aplicar UNA vez por base, junto con el deploy, DESPUÉS de core/002.
--
-- El ADR-0020 le da a ese rol todas las pantallas de Terceros. core/002 lo creó
-- con las cinco que había entonces; Órdenes de facturación llegó después. Sin
-- esta fila, quien liquida terceros no vería la pantalla con la que emite.
--
-- Idempotente: si el rol no existe o ya tiene el permiso, no hace nada.

INSERT INTO rol_permiso (rol_id, modulo, pantalla, nivel)
SELECT r.id, 'terceros', 'recibos', 'editar'
FROM rol r
WHERE r.nombre = 'Liquidador de terceros'
  AND NOT EXISTS (
      SELECT 1 FROM rol_permiso p
      WHERE p.rol_id = r.id AND p.modulo = 'terceros' AND p.pantalla = 'recibos'
  );
