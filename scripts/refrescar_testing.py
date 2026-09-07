"""
Refresca la base de DESARROLLO (`testing`) con la estructura y los datos de
las tablas del preliquidador tomadas de PRODUCCIÓN (`preliquidacion`).

Uso (desde la raíz del backend, con el venv activado):

    python scripts/refrescar_testing.py            # estructura + datos
    python scripts/refrescar_testing.py --solo-estructura
    python scripts/refrescar_testing.py --tablas usuarios,preliquidacion

Origen: la base propia del .env (DB_PROPIA_*), que en la máquina de Gero es
producción. Destino: variables DB_DEV_* del .env; si faltan, se piden por
consola (la contraseña no se muestra).

    DB_DEV_HOST=...      (default: el mismo host que DB_PROPIA_HOST)
    DB_DEV_PORT=3306
    DB_DEV_USER=...
    DB_DEV_PASSWORD=...
    DB_DEV_NAME=testing

Qué hace, en orden, dentro del destino:
  1. DROP + CREATE de cada tabla del preliquidador (solo las de la lista de
     abajo: `testing` tiene tablas de otros sistemas y NO se tocan).
  2. Copia de filas en lotes.
  3. Recrea las vistas (si el usuario destino no puede, avisa y sigue).

Protecciones: se niega a correr si origen y destino son la misma base, y
pide confirmación escribiendo el nombre del destino antes de borrar nada.
"""
import argparse
import getpass
import os
import re
import sys

import pymysql
from dotenv import load_dotenv

load_dotenv()

# Tablas del preliquidador, en orden de dependencias (padres primero).
# Cualquier otra tabla que haya en el destino se deja intacta.
TABLAS = [
    "usuarios",
    "preliquidacion",
    "concepto_liquidacion",
    "preliquidacion_linea",
    "concepto_adicional",
    "ajuste_manual",
    "categoria_operario",
]
VISTAS = ["vw_bi_lineas", "vw_bi_conceptos_pagados"]
LOTE = 1000


def conectar(host, port, user, password, db):
    return pymysql.connect(
        host=host, port=int(port), user=user, password=password, database=db,
        charset="utf8mb4", autocommit=False, cursorclass=pymysql.cursors.Cursor,
    )


def config_origen():
    return dict(
        host=os.environ["DB_PROPIA_HOST"], port=os.environ.get("DB_PROPIA_PORT", 3306),
        user=os.environ["DB_PROPIA_USER"], password=os.environ["DB_PROPIA_PASSWORD"],
        db=os.environ["DB_PROPIA_NAME"],
    )


def config_destino(origen):
    host = os.environ.get("DB_DEV_HOST") or origen["host"]
    port = os.environ.get("DB_DEV_PORT") or origen["port"]
    db = os.environ.get("DB_DEV_NAME") or "testing"
    user = os.environ.get("DB_DEV_USER") or input(f"Usuario MySQL para {db}@{host}: ").strip()
    password = os.environ.get("DB_DEV_PASSWORD") or getpass.getpass(f"Contraseña de {user}: ")
    return dict(host=host, port=port, user=user, password=password, db=db)


def limpiar_ddl_vista(ddl: str, db_origen: str) -> str:
    """SHOW CREATE VIEW trae DEFINER y SQL SECURITY del origen y, a veces, la
    base calificando las tablas. Nada de eso sirve en el destino."""
    ddl = re.sub(r"DEFINER=`[^`]*`@`[^`]*`\s*", "", ddl)
    ddl = re.sub(r"SQL SECURITY \w+\s*", "", ddl)
    ddl = ddl.replace(f"`{db_origen}`.", "")
    return ddl


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo-estructura", action="store_true", help="crear tablas vacías, sin copiar filas")
    ap.add_argument("--tablas", help="lista separada por comas; default: todas las del preliquidador")
    ap.add_argument("--si", action="store_true", help="no pedir confirmación (para scripts)")
    args = ap.parse_args()

    tablas = TABLAS if not args.tablas else [t.strip() for t in args.tablas.split(",") if t.strip()]
    desconocidas = [t for t in tablas if t not in TABLAS]
    if desconocidas:
        sys.exit(f"Tablas fuera de la lista del preliquidador: {desconocidas}. Este script no toca otras tablas.")

    origen = config_origen()
    destino = config_destino(origen)

    if (origen["host"], str(origen["port"]), origen["db"]) == (destino["host"], str(destino["port"]), destino["db"]):
        sys.exit("Origen y destino son la misma base. Abortado.")

    print(f"Origen : {origen['db']} @ {origen['host']} (usuario {origen['user']})")
    print(f"Destino: {destino['db']} @ {destino['host']} (usuario {destino['user']})")
    print(f"Tablas : {', '.join(tablas)}")
    print("Se van a BORRAR y recrear esas tablas en el destino. Las demás tablas del destino no se tocan.")
    if not args.si:
        if input(f"Escribí el nombre del destino para confirmar ({destino['db']}): ").strip() != destino["db"]:
            sys.exit("Confirmación incorrecta. Abortado.")

    src = conectar(**origen)
    dst = conectar(**destino)
    cs, cd = src.cursor(), dst.cursor()

    cd.execute("SET FOREIGN_KEY_CHECKS=0")
    cd.execute("SET UNIQUE_CHECKS=0")

    # 1. Estructura
    for t in tablas:
        cs.execute(f"SHOW CREATE TABLE `{t}`")
        ddl = cs.fetchone()[1]
        cd.execute(f"DROP TABLE IF EXISTS `{t}`")
        cd.execute(ddl)
        print(f"  estructura  {t}")
    dst.commit()

    # 2. Datos
    if not args.solo_estructura:
        for t in tablas:
            cs.execute(f"SELECT * FROM `{t}`")
            cols = [d[0] for d in cs.description]
            marcadores = ",".join(["%s"] * len(cols))
            sql = f"INSERT INTO `{t}` ({','.join(f'`{c}`' for c in cols)}) VALUES ({marcadores})"
            total = 0
            while True:
                filas = cs.fetchmany(LOTE)
                if not filas:
                    break
                cd.executemany(sql, filas)
                total += len(filas)
            dst.commit()
            print(f"  datos       {t}: {total} filas")

    cd.execute("SET FOREIGN_KEY_CHECKS=1")
    cd.execute("SET UNIQUE_CHECKS=1")

    # 3. Vistas (best effort)
    for v in VISTAS:
        try:
            cs.execute(f"SHOW CREATE VIEW `{v}`")
            ddl = limpiar_ddl_vista(cs.fetchone()[1], origen["db"])
            cd.execute(f"DROP VIEW IF EXISTS `{v}`")
            cd.execute(ddl)
            dst.commit()
            print(f"  vista       {v}")
        except Exception as e:  # noqa: BLE001 — informar y seguir
            dst.rollback()
            print(f"  vista       {v}: NO recreada ({str(e)[:120]})")

    # Verificación
    print("\nVerificación (filas origen -> destino):")
    ok = True
    for t in tablas:
        cs.execute(f"SELECT COUNT(*) FROM `{t}`")
        cd.execute(f"SELECT COUNT(*) FROM `{t}`")
        a, b = cs.fetchone()[0], cd.fetchone()[0]
        esperado = 0 if args.solo_estructura else a
        marca = "OK " if b == esperado else "DIF"
        ok &= b == esperado
        print(f"  {marca} {t}: {a} -> {b}")

    src.close()
    dst.close()
    print("\nListo." if ok else "\nTerminó con diferencias, revisar arriba.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
