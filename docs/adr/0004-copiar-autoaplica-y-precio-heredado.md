# Copiar conceptos: auto-aplica al destino y marca precios heredados

Copiar conceptos de una quincena a otra es una creación masiva de conceptos, así que **auto-aplica** al destino: dispara el recálculo reactivo (ADR-0002) scopeado a las líneas de la quincena destino que ahora matchean un concepto copiado, dejando el destino consistente sin ningún botón manual. Además, los precios copiados se marcan como **heredados / sin confirmar**: pagan normal (no dejan la línea incompleta), pero quedan resaltados hasta que el liquidador los confirme, para no arrastrar un precio viejo en silencio si hubo un aumento entre quincenas.

## Consecuencias

- El endpoint de copiar (`precios.py:140`) deja de ser solo un INSERT: al terminar, corre el recálculo reactivo sobre las líneas afectadas del destino.
- `concepto_liquidacion` necesita una señal de "precio heredado sin confirmar" (flag booleano y/o quincena de origen). Confirmar un precio limpia la marca.
- Un precio heredado cuenta como completo para ADR-0003 (paga), pero se muestra resaltado y filtrable en la solapa de conceptos. Es una tercera safeguard de "nunca pagar algo en silencio", junto al no-cero (ADR-0003).
