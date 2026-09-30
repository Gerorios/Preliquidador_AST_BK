# Desarrollo contra `testing`, producción sólo desde el VPS, y la app se niega a arrancar contra producción sin permiso

La base propia tiene dos versiones: `preliquidacion`, que es **producción** y el dato real de la empresa, y `testing`, el entorno de prueba del área, que es **compartido con otros sistemas** (tiene un espejo de nuestras tablas y tablas ajenas). Se decidió que **ninguna máquina de desarrollo apunte a producción**: en local se trabaja siempre contra `testing`, y sólo el VPS se conecta a `preliquidacion`. **Toda DDL se aplica primero en `testing`** y después en producción, así que el esquema de `testing` nunca queda atrasado. Que sus datos estén desactualizados no importa, y tener datos reales ahí está aceptado.

La regla se hace cumplir con código y no con una instrucción escrita: la app **se niega a arrancar** contra `preliquidacion` salvo que su `.env` tenga `PERMITIR_BASE_PRODUCCION=1`, y ese permiso lo lleva sólo el `.env` del VPS. El motivo concreto: la app lee una sola conexión propia, y un `.env` de desarrollo que apuntaba a producción hacía que un arranque local escribiera sobre el dato real.

## Considered Options

- **Una sola base para desarrollo y producción** (como estaba, rechazada): cualquier prueba local (generar una quincena, cambiar un precio, dar de alta un usuario) impactaba al instante en lo que ven los usuarios.
- **Sólo avisar en el banner del arranque qué base se conectó** (rechazada como única medida): un aviso no evita el error, se pierde entre la salida de otros comandos. Se conserva igual, como complemento: el banner muestra la base conectada.
- **Guardia en la configuración, al cargar el `.env`** (rechazada): la configuración la importan también los tests y los scripts, que legítimamente leen producción (el refresco de `testing`, el chequeo de conexiones). La guardia va en el arranque de la app, que es lo único que tiene que frenar.
- **Guardia en el arranque de la app (elegida).** Es la única razón por la que se aborta el arranque: una tabla faltante sigue sin abortarlo, para no meter a systemd en un bucle.

## Consecuencias

- **Orden obligatorio de deploy** cuando el VPS se monta de nuevo o cambia su `.env`: la variable del permiso tiene que estar antes de arrancar el código. Sin ella, la app no arranca y systemd entra en bucle de reinicios. `deploy/provision.sh` lo avisa.
- **Refrescar `testing` desde producción** requiere pasarle al script las credenciales de producción de forma explícita. Si no, se niega: con el `.env` en `testing`, origen y destino serían la misma base.
- Nunca un drop general en `testing`: es compartida, y sólo se tocan nuestras tablas.
- Cada módulo nuevo sigue el mismo circuito: sus migraciones se prueban primero en `testing`.
