# Unidad base "Jornal tope 1 + excedente" (jornal_tope1_mas_excedente)

Había tareas que se pagan "a jornal" pero cuya jornada real puede superar las 10 horas, y ninguna unidad base existente las representaba bien: `jornal_tope1` **ignora todo excedente** (12 hs pagan lo mismo que 5), `fijo` ni mira las horas, y `hsjornal` paga por hora cruda (sin la noción de jornal ni la escalera de media jornada).

Se agrega la unidad base **`jornal_tope1_mas_excedente`**: idéntica a `jornal_tope1` hasta las 10 horas, y proporcional por encima. La escalera completa sobre las horas de jornal de la línea:

| Horas de jornal | Jornales (cantidad) |
|---|---|
| 0 | 0 |
| más de 0 y menos de 5 | 0,5 |
| de 5,00 a 10,00 (inclusive) | 1 |
| más de 10 | horas / 10, redondeado a 2 decimales |

11 hs → 1,1 · 12 hs → 1,2 · 11,25 hs → 1,13. La función es continua en el 10 (10/10 = 1, sin salto).

## Decisiones de borde (confirmadas en grilling, 2026-08-05)

- **0 horas → 0 jornales** (no 0,5): igual que `jornal_tope1`. Una línea sin horas de jornal (solo tancadas/unidades) no debe cobrar medio jornal en silencio.
- **5,00 hs exactas → 1 jornal**: mismo borde que `jornal_tope1` (`>= 5`). Las 5 horas clavadas se cargan mucho (media jornada redonda); las dos reglas hermanas tratan el borde igual para no obligar al liquidador a recordar dos semánticas.
- **Redondeo a 2 decimales dentro de la regla** (ROUND_HALF_UP), no librado a la base: `concepto_adicional.cantidad` es `Numeric(10,2)` y `hsjornal` trae 2 decimales, así que horas/10 puede dar 3 decimales (11,25 → 1,125). Se redondea comercialmente en el motor (→ 1,13) en vez de migrar la columna a más decimales: el error máximo es medio centésimo de jornal — centavos — y no justifica un ALTER de `concepto_adicional` en producción.

## Consecuencias

- **Sensible al pago**: una vez que existan conceptos con esta unidad, cambiar la semántica de la escalera cambia plata liquidada. Cualquier ajuste futuro debe ser una unidad nueva, no una edición de esta.
- `concepto_liquidacion.unidad_base` es un **ENUM nativo de MySQL**: el valor nuevo requiere la migración **ws13** (`ALTER TABLE ... MODIFY`), **no diferible** — sin ella, crear un concepto con esta unidad falla en producción.
- Cubierta con tests de los 4 tramos, los bordes 5,00 y 10,00, el redondeo (11,25/11,24) y horas NULL.
- El divisor 10 y los cortes 5/10 están **cableados en la regla** (como el ×1,3 de pulverización, ADR-0007): si algún día la jornada de referencia deja de ser 10 hs, será otra unidad u otra decisión explícita, no un parámetro.
