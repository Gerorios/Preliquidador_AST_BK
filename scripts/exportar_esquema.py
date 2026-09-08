"""
Vuelca el CREATE TABLE real de las tablas del sistema desde la base propia del
.env (producción) a archivos SQL versionados. SOLO LECTURA (SHOW CREATE TABLE).

    python scripts/exportar_esquema.py
"""
import os
import re
from datetime import date
from pathlib import Path

import pymysql
from dotenv import load_dotenv

load_dotenv()
RAIZ = Path(__file__).resolve().parents[1]
DESTINOS = {
    "migrations/core/000_usuarios.sql": ["usuarios"],
    "migrations/preliquidacion/000_esquema_base.sql": [
        "preliquidacion", "concepto_liquidacion", "preliquidacion_linea",
        "concepto_adicional", "ajuste_manual", "categoria_operario",
    ],
}
CABECERA = """-- Esquema base generado con scripts/exportar_esquema.py desde la base real
-- ({db}) el {fecha}. Es el punto de partida para una base nueva: correr este
-- archivo y después las migraciones siguientes de la carpeta en orden.
-- NO editar a mano: regenerar con el script.

"""


def main():
    con = pymysql.connect(
        host=os.environ["DB_PROPIA_HOST"], port=int(os.environ.get("DB_PROPIA_PORT", 3306)),
        user=os.environ["DB_PROPIA_USER"], password=os.environ["DB_PROPIA_PASSWORD"],
        database=os.environ["DB_PROPIA_NAME"], charset="utf8mb4",
    )
    cur = con.cursor()
    for destino, tablas in DESTINOS.items():
        partes = [CABECERA.format(db=os.environ["DB_PROPIA_NAME"], fecha=date.today().isoformat())]
        for t in tablas:
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            ddl = cur.fetchone()[1]
            ddl = ddl.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
            # AUTO_INCREMENT=N es estado, no esquema.
            ddl = re.sub(r"\s*AUTO_INCREMENT=\d+", "", ddl)
            partes.append(f"-- {t}\n{ddl};\n\n")
        ruta = RAIZ / destino
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("".join(partes), encoding="utf-8")
        print(f"escrito {destino} ({len(tablas)} tablas)")
    con.close()


if __name__ == "__main__":
    main()
