# `concepto_adicional` como hecho autocontenido (precio + cantidad + origen)

`concepto_adicional` es la tabla de hechos de nómina: cada fila representa "a esta persona, este día, se le reconoció este concepto por tanta plata". Hasta ahora solo guardaba el `importe` final (`cantidad × precio`), descartando ambos factores. Como `concepto_liquidacion.precio` es mutable (se edita todo el tiempo — es el corazón del modelo reactivo, ADR-0002), no había forma confiable de responder después "¿a qué precio se le pagó?" o "¿por qué cantidad?" sin arriesgarse a leer un precio ya desactualizado del maestro.

Se agregan tres columnas a `concepto_adicional`:
- `precio` — precio unitario usado en el cálculo, congelado en el momento.
- `cantidad` — cantidad de unidades reconocidas (según `unidad_base`), congelada en el momento.
- `concepto_liquidacion_id` — FK a la regla exacta del maestro que originó el concepto (nullable: los conceptos manuales, sin código, no tienen origen en el maestro).

De paso se expone `unidad_base` en `ConceptoAdicionalResponse` — ya existía en el modelo pero nunca había llegado a la API.

## Consecuencias

- `ON DELETE SET NULL` en la FK: si se borra una regla del maestro, el hecho histórico de plata pagada no se toca — solo se pierde el link hacia una regla que ya no existe.
- El snapshot (`precio`/`cantidad`) **no queda congelado para siempre mientras la preliquidación sigue abierta**: si se edita el precio del maestro, el modelo reactivo (ADR-0002) borra y regenera el `ConceptoAdicional`, y el nuevo snapshot refleja el precio real recién usado. Esto es correcto por diseño — el snapshot protege contra *leer* un precio ya desactualizado vía join, no contra que el propio sistema recalcule mientras la quincena sigue viva.
- Los conceptos manuales (`agregar_concepto`, sin código) quedan con `precio`/`cantidad`/`concepto_liquidacion_id` en `NULL` — no tienen origen en el maestro, es correcto.
- Se limpiaron las tablas transaccionales de producción (`preliquidacion`, `preliquidacion_linea`, `concepto_adicional`, `ajuste_manual`) a pedido explícito del usuario, con backup previo (`*_bkp_trazabilidad`) — no se intentó backfillear el histórico viejo (habría requerido el mismo join frágil de 5 columnas que este fix reemplaza, y podía mentir si el maestro había cambiado desde entonces).
- Habilita análisis de BI real: "con qué conceptos, a qué precio y por qué cantidad se le pagó a cada persona" queda respondible desde `concepto_adicional` sola, sin joins frágiles por texto.
