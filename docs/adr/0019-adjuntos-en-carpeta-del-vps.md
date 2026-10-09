# Los adjuntos se guardan en una carpeta del VPS y la base guarda sólo su referencia

Facturación es el primer módulo que guarda archivos: el PDF de cada comprobante emitido en el sistema contable. Se decidió guardarlos en una **carpeta del VPS, fuera de la carpeta del código**, cuya ruta viene del `.env`. La base propia guarda sólo los datos del archivo (nombre original, tipo, tamaño, quién lo subió y cuándo) y el nombre con que quedó en disco, que lo genera el sistema y nunca es el que trae el usuario. Al decidirlo, el disco del VPS estaba al 4% de uso y los PDFs de un año se estiman en cientos de MB. **La regla vale para cualquier módulo que necesite guardar archivos.**

## Considered Options

- **En la base propia, en una tabla aparte** (rechazada): un solo respaldo y nada que configurar en el servidor, pero la base crece con archivos y refrescar `testing` desde producción copiaría todos los PDFs cada vez.
- **En Google Drive, por API** (rechazada): una dependencia nueva, credenciales de una cuenta de servicio y un tercero en el camino de cada carga. Si Drive falla, falla la carga del comprobante.
- **Carpeta en el VPS** (elegida): sin dependencias nuevas ni servicios externos, y la base no crece.

## Consecuencias

- **La carpeta necesita su propio respaldo**: el de la base no la cubre. Hasta que se confirme, perder el disco del VPS es perder los adjuntos, aunque los comprobantes sigan en la base.
- Un deploy nunca toca la carpeta: vive fuera de la del código.
- En desarrollo, cada máquina usa una carpeta local. Un adjunto cargado contra `testing` desde una máquina no existe en otra.
- Refrescar `testing` desde producción copia las referencias pero no los archivos: en `testing`, los adjuntos de producción figuran y no se pueden abrir.
- Se aceptan sólo PDF e imagen, con un tamaño máximo.
