# Tarifas y seguros atados al id de la máquina

Pedido de Pitu (2026-10-07). Al reorganizar el maestro de maquinaria de Chinagro cambiaron
los nombres de las máquinas, y 420 tarifas de servicio y 10 seguros dejaron de encontrar
su máquina: estaban atados al nombre. Lo que ya decía el plan (3.1) es que los sistemas se
cruzan por id y no por nombre.

## Lo que decidió Pitu

- El maestro de máquinas y dueños es Chinagro. La Falda y la app del taller van a tener
  el id de Chinagro (lo están cargando). El dueño se escribe en los dos, pero el módulo lo
  busca en Chinagro.
- Los seguros salen de lo que está en Chinagro: colectivos, maquinaria y choferes. Flor
  sólo carga el importe.

## Cómo

- Migración `terceros/012`: `id_maquinaria` (el de Chinagro) en `terceros_hora_servicio`
  y en `terceros_tarifa_servicio`; `origen` e `id_origen` (el bien del padrón) en
  `terceros_precio_seguro`.
- Las horas de servicio traen el id de la máquina, y la clave con la que se reconcilian
  usa el id y no el nombre: renombrar una máquina no rehace la fila ni pierde lo que se
  movió de quincena.
- Una tarifa de servicio guarda el id de su máquina, resuelto desde las horas de servicio
  al cargarla. Copiar de otra quincena lo copia.
- **Al actualizar una quincena, las tarifas y los seguros siguen los renombres**: la tarifa
  toma el nombre actual de su máquina por el id, y el seguro de un colectivo o una máquina
  toma del padrón el dueño, el nombre y la patente actuales. El cruce sigue siendo por
  nombre, pero el nombre ya no puede quedar viejo. El seguro de un chofer no se toca: el
  mismo chofer aparece con cada dueño para el que manejó.
- El dueño de una máquina se lee igual en las tres consultas que lo usan (horas de
  servicio, padrón de seguros y dueños del taller): antes el padrón dejaba «SOSA  MARTA»
  con dos espacios y las horas de servicio «SOSA MARTA».
- Front: Seguros manda el bien (`origen`, `id_origen`) al cargar y cruza por él.
